"""HTTP/native product reads keep exact sources, scope and finite page contracts."""
from __future__ import annotations

import asyncio
import json
from urllib.parse import urlencode

from bat_agent_connector import managed_setup
from tests.operation_helpers import settle_operations
from tests.test_api_v1 import daemon as daemon  # noqa: F401
from tests.test_api_v1 import http, token, write_frames
from tests.test_api_v1 import served as served  # noqa: F401
from tests.test_artifacts import action
from tests.test_managed_setup import installed as installed  # noqa: F401
from tests.test_session_instructions import record


async def test_fixed_repair_routes_authorize_and_create_without_host_writes(served, mock):
    d, port = served
    observer = token(d, "route-observer", "observe")
    manager = token(d, "route-manager", "manage")
    project = (await action(d, "project.create", params={"name": "Fixed repair"}))["result"]["project_id"]
    status, caps = await http(port, "GET", "/api/v1/capabilities", tok=observer)
    assert status == 200 and caps["features"]["managed_repairs"]["fixed_evidence"]
    assert any(a["action"] == "repair.create" and not a["allowed"] for a in caps["actions"])
    profile = caps["hosts"][0]["profile_id"]
    assert profile == d.fleet.config.host("h1").profile_id
    source = {"kind": "discovery", "host": "h1", "profile_id": profile}
    d.ops.db.execute("INSERT INTO discovery_latest VALUES(?,?,?,?)", ("h1", profile, "binding",
        json.dumps({"status": "failed", "scan_id": "scan_fixture", "error_code": "SOURCE_UNAVAILABLE",
                    "errors": ["private-fixture-token"]})))
    path = f"/api/v1/projects/{project}/repair-evidence?" + urlencode(source)
    assert (await http(port, "GET", path))[0] == 401
    assert (await http(port, "GET", path, tok=manager))[0] == 403
    status, evidence = await http(port, "GET", path, tok=observer)
    assert status == 200 and evidence["source"] == source
    assert "private-fixture-token" not in json.dumps(evidence)
    body = {"action": "repair.create", "target": {"project_id": project}, "params": {"source": source},
            "preconditions": {"expected_project_version": evidence["expected_project_version"],
                              "expected_evidence_digest": evidence["evidence_digest"]}}
    assert (await http(port, "POST", "/api/v1/operations", tok=observer, body=body,
                       headers={"Idempotency-Key": "refused-repair"}))[0] == 403
    status, accepted = await http(port, "POST", "/api/v1/operations", tok=manager, body=body,
                                  headers={"Idempotency-Key": "route-repair"})
    assert status == 202
    await settle_operations(d.ops)
    status, accepted = await http(port, "GET", "/api/v1/operations/" + accepted["operation"]["operation_id"], tok=observer)
    assert status == 200 and accepted["operation"]["status"] == "succeeded", accepted
    wid = accepted["operation"]["result"]["work_item_id"]
    item_path = f"/api/v1/work-items/{wid}/repair"
    assert (await http(port, "GET", item_path, tok=manager))[0] == 403
    status, repair = await http(port, "GET", item_path, tok=observer)
    assert status == 200 and repair["dispatchable"] and repair["dispatch_operation_id"] is None
    assert repair["evidence_digest"] in repair["request"]
    assert (await http(port, "GET", item_path + "?source=other", tok=observer))[0] == 422
    assert (await http(port, "GET", item_path + "?cursor=", tok=observer))[0] == 422
    assert write_frames(mock) == []
    for query in ["", "kind=discovery&host=h1", "kind=discovery&host=h1&profile_id=",
                  urlencode(source) + "&host=h1", urlencode(source) + "&prompt=override",
                  urlencode(source) + "&operation_id=op_" + "0" * 32,
                  "kind=operation&operation_id=bad", "kind=operation&operation_id=%0A"]:
        assert (await http(port, "GET", f"/api/v1/projects/{project}/repair-evidence?" + query,
                           tok=observer))[0] == 422, query
    assert (await http(port, "GET", path.replace("host=h1", "host=unknown"), tok=observer))[0] == 404
    assert (await http(port, "GET", path.replace("profile_id=" + profile, "profile_id=old"), tok=observer))[0] == 409


async def test_instruction_routes_scoped_page_and_historical_queue_receipts(served):
    d, port = served
    observer, manager = token(d, "instruction-reader", "observe"), token(d, "no-read", "manage")
    oldest = record(d, 1, "succeeded", result={"accepted": True, "queued": True})
    newest = record(d, 2, "uncertain")
    record(d, 3, sid="other")
    path = "/api/v1/sessions/h1/exact/instructions"
    assert (await http(port, "GET", path))[0] == 401
    assert (await http(port, "GET", path, tok=manager))[0] == 403
    status, page = await http(port, "GET", path + "?limit=1", tok=observer)
    assert status == 200 and [i["operation_id"] for i in page["instructions"]] == [newest]
    assert page["instructions"][0]["phase"] == "unconfirmed" and not page["live_queue_available"]
    status, older = await http(port, "GET", path + "?" + urlencode({"limit": 1, "cursor": page["next_cursor"]}), tok=observer)
    assert status == 200 and [i["operation_id"] for i in older["instructions"]] == [oldest]
    assert older["instructions"][0]["was_queued"] and older["instructions"][0]["queue_position"] is None
    assert not older["per_message_cancel"] and older["interrupt_scope"] == "session"
    assert (await http(port, "GET", path.replace("exact", "other") + "?cursor=" + page["next_cursor"], tok=observer))[0] == 422
    for query in ["limit=0", "limit=101", "limit=-1", "limit=1.0", "limit=", "limit=1&limit=2",
                  "cursor=", "cursor=bad", "cursor=" + "a" * 2049, "host=h1", "cancel=true"]:
        assert (await http(port, "GET", path + "?" + query, tok=observer))[0] == 422, query
    assert (await http(port, "GET", path.replace("/h1/", "/unknown/"), tok=observer))[0] == 404
    assert (await http(port, "GET", path.replace("exact", "a" * 257), tok=observer))[0] == 422


async def test_verification_admission_rejection_is_explicit_without_operation(installed):
    d, principal, _ = installed
    credential = token(d, principal.actor, *principal.scopes)
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    try:
        status, error = await http(server.sockets[0].getsockname()[1], "POST", "/api/v1/operations", tok=credential,
            headers={"Idempotency-Key": "invalid-verification"}, body={"action": "setup.verification", "target": {},
            "params": {"commands": {"project": "ambiguous shell string"}, "timeout_s": 60},
            "preconditions": {"config_revision": managed_setup.state(d, principal)["revision"]}})
        assert status == 422 and error["error"]["admission_refused"]
        assert not d.ops.db.execute("SELECT 1 FROM operations WHERE idem_key='invalid-verification'").fetchone()
    finally:
        server.close()
        await server.wait_closed()


async def test_product_catalog_and_result_queries_reject_ambiguous_values_before_reads(served, mock):
    d, port = served
    observer = token(d, "product-query-reader", "observe")
    for path in [
        "/hosts/h1/preferences?agent=claude&agent=codex",
        "/hosts/h1/preferences?agent=",
        "/hosts/h1/preferences?session_id=",
        "/hosts/h1/preferences?refresh=",
        "/hosts/h1/preferences?refresh=1&refresh=0",
        "/hosts/h1/preferences?refresh=yes",
        "/projects/prj_00000000000000000000/skills?host=h1&workspace_id=one&workspace_id=two",
        "/projects/prj_00000000000000000000/skills?host=h1&workspace_id=",
        "/projects/prj_00000000000000000000/skills?host=h1&workspace_id=one&refresh=YES",
        "/work-items/wi_00000000000000000000/result-sources?limit=1&limit=2",
        "/work-items/wi_00000000000000000000/result-sources?limit=",
        "/work-items/wi_00000000000000000000/result-sources?limit=%2B1",
        "/work-items/wi_00000000000000000000/result-sources?after=",
    ]:
        assert (await http(port, "GET", "/api/v1" + path, tok=observer))[0] == 422, path
    assert mock.invokes == []
