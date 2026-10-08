"""B01/B02: session keyset cursors are validated independently of inventory rows."""

import asyncio
import base64
import hashlib
import json
import time
from urllib.parse import urlencode

import pytest

from bat_agent_connector import cli, mcp_server
from bat_agent_connector.inventory import Inventory
from bat_agent_connector.task_journal import Journal
from tests.conftest import make_config
from tests.test_api_v1 import daemon as _daemon
from tests.test_api_v1 import http, token
from tests.test_api_v1 import served as _served

daemon = _daemon
served = _served


def encode(payload):
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode(cursor):
    return json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))


def payload(order, head, **filters):
    # Public filter contract, including defaults: a same-filter forged token must still be refused.
    defaults = {"host": None, "provenance": None, "api_access": None, "attention": None,
                "include_gone": False, "order": order, "profile_id": None, "project_id": [],
                "work_item_id": None, "execution_id": None, "provider": None,
                "has_tab": None, "loaded": None, "streaming": None, "lifecycle": None,
                "stale": None, "relation_scope": "history"}
    defaults.update(filters)
    return {"v": 1, "f": hashlib.sha256(json.dumps(defaults, sort_keys=True).encode()).hexdigest()[:16],
            "a": head, "k": ([-10] if order == "activity" else []) + ["h1", "sid-0"]}


def corrupt(token, case):
    if case == "payload-null":
        return None
    if case == "payload-list":
        return list(token.values())
    field, kind = case.split(":", 1)
    values = {"null": None, "bool": True, "string": "1", "float": 1.0, "negative": -1,
              "future": token["a"] + 1, "nan": float("nan"), "inf": float("inf"),
              "huge": 2**100, "underflow": -(2**63) - 1, "object": {}, "list": [],
              "surrogate": "\ud800", "unsupported": 2}
    if field == "missing":
        del token[kind]
    elif field == "extra":
        token[kind] = 1
    elif field in {"host", "sid", "sort"}:
        token["k"][{"host": -2, "sid": -1, "sort": 0}[field]] = values[kind]
    else:
        token[field] = values[kind]
    return token


COMMON_BAD = ["payload-null", "payload-list", "missing:k", "missing:a", "missing:f", "extra:x",
              "v:null", "v:bool", "v:float", "v:unsupported", "f:null", "f:object",
              "a:null", "a:bool", "a:string", "a:float", "a:negative", "a:future", "a:huge",
              "a:nan", "a:inf", "k:null", "k:bool", "k:string", "k:object", "k:list",
              "host:null", "host:bool", "host:object", "host:surrogate",
              "sid:null", "sid:bool", "sid:object", "sid:surrogate"]
SORT_BAD = ["sort:null", "sort:bool", "sort:string", "sort:float", "sort:huge", "sort:underflow",
            "sort:nan", "sort:inf", "sort:object"]


@pytest.mark.parametrize(("order", "case"), [(order, case) for order in ("id", "activity")
                                            for case in COMMON_BAD + (SORT_BAD if order == "activity" else [])])
def test_inventory_invalid_cursor_precedes_session_queries(mock, tmp_path, order, case):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    cursor = encode(corrupt(payload(order, j.api_head()), case))
    reads = []
    j.db.set_trace_callback(reads.append)
    with pytest.raises(ValueError, match="cursor does not match"):
        inv.list_sessions(order=order, cursor=cursor)
    assert not any("sessions_observed" in sql or "observation_resources" in sql for sql in reads)
    if case != "a:future":
        assert reads == []
    j.close()


@pytest.mark.parametrize("cursor", ["", "not-base64", "é", False, 42, [], {}])
def test_inventory_invalid_cursor_encoding(mock, tmp_path, cursor):
    j = Journal(tmp_path / "j.db")
    with pytest.raises(ValueError, match="cursor does not match"):
        Inventory(j, make_config(mock)).list_sessions(cursor=cursor)
    j.close()


@pytest.mark.parametrize("order", ["id", "activity"])
@pytest.mark.parametrize("legacy", [False, True])
def test_inventory_valid_cursor_reopens_and_keeps_catchup_boundary(mock, tmp_path, order, legacy):
    path = tmp_path / "j.db"
    j = Journal(path)
    config = make_config(mock)
    inv = Inventory(j, config)
    rows = [{"session_id": f"sid-{n}", "last_activity_ms": n // 2, "has_tab": True} for n in range(7)]
    inv._record_success("h1", time.time(), rows, "test")
    first = inv.list_sessions(order=order, limit=2)
    token_body = decode(first["next_cursor"])
    assert token_body["v"] == 1
    assert all(type(r[0]) is int for r in j.db.execute("SELECT sort_key FROM sessions_observed"))
    if legacy:
        del token_body["v"]
    cursor = encode(token_body)
    ids = [s["resource_id"] for s in first["sessions"]]
    j.close()
    j = Journal(path)
    inv = Inventory(j, config)
    rows[0]["has_tab"] = False
    inv._record_success("h1", time.time(), rows, "test")
    assert j.api_head() > first["as_of"]
    while cursor:
        page = inv.list_sessions(order=order, limit=2, cursor=cursor)
        assert page["as_of"] == first["as_of"]
        ids += [s["resource_id"] for s in page["sessions"]]
        cursor = page["next_cursor"]
    expected = sorted(rows, key=lambda r: ((-r["last_activity_ms"],) if order == "activity" else ()) + (r["session_id"],))
    assert ids == ["h1/" + r["session_id"] for r in expected]
    assert len(ids) == len(set(ids)) == 7
    assert any(e["kind"] == "session.updated" and e["resource_id"] == "h1/sid-0"
               for e in j.api_events(first["as_of"])["events"])
    # The zero boundary is valid, unlike negative/future values.
    token_body["a"] = 0
    assert inv.list_sessions(order=order, cursor=encode(token_body))["as_of"] == 0
    j.close()


@pytest.mark.parametrize("order", ["id", "activity"])
@pytest.mark.parametrize("case", ["payload-null", "k:null", "host:object", "sid:bool",
                                 "a:negative", "a:future", "a:bool", "a:nan", "v:unsupported"])
async def test_inventory_cursor_http_mcp_cli_empty_filtered_populated(served, monkeypatch, capsys, order, case):
    d, port = served
    viewer = token(d, "viewer", "observe")
    monkeypatch.setenv("BATC_API_TOKEN", viewer)
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    server, fleet = mcp_server.build_server(d.fleet.config, read_only=True)
    try:
        for state in ("empty", "filtered", "populated"):
            if state == "filtered":
                d.inventory._record_success("h1", time.time(), [{"session_id": "sid-1", "agent_kind": "codex"}], "test")
            filters = {"provider": "claude"} if state == "filtered" else {}
            baseline = d.inventory.list_sessions(order=order, **filters)
            assert baseline["count"] == (1 if state == "populated" else 0)
            cursor = encode(corrupt(payload(order, baseline["as_of"], **filters), case))
            params = {"order": order, "cursor": cursor, **filters}
            status, error = await http(port, "GET", "/api/v1/sessions?" + urlencode(params), tok=viewer)
            assert status == 422 and error["error"]["code"] == "INVALID_REQUEST", error
            assert "cursor does not match" in error["error"]["message"]
            with pytest.raises(mcp_server.ToolError, match="cursor does not match"):
                await server.call_tool("inventory_sessions", params)
            command = ["--json", "inventory", "sessions", "--order", order, "--cursor", cursor]
            if filters:
                command += ["--provider", filters["provider"]]
            assert await asyncio.to_thread(cli.main, command) == 1
            output = capsys.readouterr()
            assert output.out == "" and "cursor does not match" in output.err
    finally:
        await fleet.close()
