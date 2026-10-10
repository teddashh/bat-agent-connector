from __future__ import annotations

import json

import pytest

from bat_agent_connector import managed_repairs, work_items
from bat_agent_connector.operations import OperationError
from tests.test_artifacts import PERSON, action
from tests.test_checkpoints import bat_writes, snapshot
from tests.test_repository_sync import STARTER, envelope, preview, settle
from tests.test_repository_sync import world as world  # noqa: F401


def source(d, *, status="failed", scan="scan_123"):
    managed_repairs.install(d.ops)
    profile = d.fleet.config.host("h1").profile_id
    value = {"host": "h1", "profile_id": profile, "scan_id": scan, "status": status,
             "error_code": "SOURCE_UNAVAILABLE", "complete_enumeration": False,
             "errors": ["fixture-private-error-token"], "binding_version": "fixed-binding"}
    d.ops.db.execute("INSERT OR REPLACE INTO discovery_latest VALUES(?,?,?,?)",
                     ("h1", profile, "fixed-binding", json.dumps(value)))
    return {"kind": "discovery", "host": "h1", "profile_id": profile}


async def prepared(w):
    d = w["d"]
    project = (await action(d, "project.create", params={"name": "repair project", "repositories": ["o/r"]}))["result"]["project_id"]
    selector = source(d)
    doc = managed_repairs.read(d.ops, PERSON, project, selector)
    request = dict(action="repair.create", target={"project_id": project}, params={"source": selector},
                   preconditions={"expected_project_version": doc["expected_project_version"],
                                  "expected_evidence_digest": doc["evidence_digest"]}, idempotency_key="fixed-repair")
    return project, doc, request


async def test_repair_create_reuses_exact_work_and_preserves_private_errors(world, mock):
    w, d = world, world["d"]
    project, doc, request = await prepared(w)
    before = snapshot(w["human"])
    assert "fixture-private-error-token" not in json.dumps(doc)
    op, _ = d.ops.create(PERSON, **request)
    op = await settle(w, op)
    assert op["status"] == "succeeded", op
    replay, created = d.ops.create(PERSON, **request)
    assert not created and replay["operation_id"] == op["operation_id"]
    second, _ = d.ops.create(PERSON, **{**request, "idempotency_key": "another-client-same-evidence"})
    second = await settle(w, second)
    assert second["result"]["reused"] and second["result"]["work_item_id"] == op["result"]["work_item_id"]
    item = work_items._get_item(d.ops.db, op["result"]["work_item_id"])
    assert doc["evidence_digest"] in item["request"]
    assert managed_repairs.read(d.ops, PERSON, project, doc["source"])["existing"]["work_item_id"] == item["work_item_id"]
    assert snapshot(w["human"]) == before and bat_writes(mock) == []
    with pytest.raises(OperationError, match="FORBIDDEN"):
        d.ops.create(STARTER, **{**request, "idempotency_key": "wrong-scope"})


async def test_evidence_changed_after_admission_does_not_create_repair(world):
    _, _, request = await prepared(world)
    op, _ = world["d"].ops.create(PERSON, **request)
    source(world["d"], scan="scan_later")
    op = await settle(world, op)
    assert op["status"] == "failed" and op["error_code"] == "EVIDENCE_CHANGED"
    assert not world["d"].ops.db.execute("SELECT 1 FROM managed_repair_intents").fetchone()


async def test_reviewed_repair_dispatch_is_managed_linked_and_reuses_operation(world, mock):
    w, d = world, world["d"]
    pid, _, creation = await prepared(w)
    repair, _ = d.ops.create(PERSON, **creation)
    repair = await settle(w, repair)
    item = work_items._get_item(d.ops.db, repair["result"]["work_item_id"])
    request = envelope(await preview(w), project_id=pid, work_item_id=item["work_item_id"], prompt=item["request"])
    request["preconditions"].update(expected_project_version=1, expected_work_item_fingerprint=work_items.fingerprint(item))
    before = snapshot(w["human"])
    with pytest.raises(OperationError, match="manage"):
        d.ops.create(STARTER, **request)
    op, _ = d.ops.create(PERSON, **request)
    op = await settle(w, op)
    assert op["status"] == "succeeded", (op["error_code"], op["status_reason"])
    links = work_items.work_item_get(d.ops.db, item["work_item_id"])["links"]
    assert [(link["kind"], link["ref"]) for link in links] == [("operation", op["operation_id"])]
    assert snapshot(w["human"]) == before
    before_writes = len(bat_writes(mock))
    replay, created = d.ops.create(PERSON, **request)
    assert not created and replay["operation_id"] == op["operation_id"]
    with pytest.raises(OperationError, match="REPAIR_ALREADY_DISPATCHED"):
        d.ops.create(PERSON, **{**request, "idempotency_key": "accidental-new-key"})
    assert len(bat_writes(mock)) == before_writes
    assert managed_repairs.read(d.ops, PERSON, pid, creation["params"]["source"])["existing"]["dispatch_operation_id"] == op["operation_id"]


async def test_repair_dispatch_rechecks_item_before_managed_effects(world, mock):
    w, d = world, world["d"]
    pid, _, creation = await prepared(w)
    repair, _ = d.ops.create(PERSON, **creation)
    repair = await settle(w, repair)
    item = work_items._get_item(d.ops.db, repair["result"]["work_item_id"])
    request = envelope(await preview(w), project_id=pid, work_item_id=item["work_item_id"], prompt=item["request"])
    request["preconditions"].update(expected_project_version=1, expected_work_item_fingerprint=work_items.fingerprint(item))
    with pytest.raises(OperationError, match="REPAIR_CHANGED"):
        d.ops.create(PERSON, **{**request, "params": {**request["params"], "prompt": "replace evidence with arbitrary instructions"}})
    op, _ = d.ops.create(PERSON, **request)
    d.ops.db.execute("UPDATE work_items SET goal='changed reviewed task' WHERE work_item_id=?", (item["work_item_id"],))
    op = await settle(w, op)
    assert op["status"] == "failed" and op["error_code"] == "WORK_ITEM_CHANGED"
    assert bat_writes(mock) == []
    assert not d.ops.db.execute("SELECT 1 FROM managed_repair_launches").fetchone()
