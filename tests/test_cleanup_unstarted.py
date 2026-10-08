"""E01/E02/plan §23: unstarted reservations and observed absence have definitive receipts."""
from __future__ import annotations

import asyncio
import copy
import json
import time
from types import SimpleNamespace

import pytest

from bat_agent_connector import api_auth, cleanup, registry
from bat_agent_connector.operations import OpContext, OperationError
from tests.operation_helpers import settle_operations
from tests.test_api_v1 import http
from tests.test_cleanup_uncertainty import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    apply,
    close_clients,
    known_live_terminals,
    setup_work,
)
from tests.test_cleanup_uncertainty import daemon as checkpoint_daemon
from tests.test_cleanup_uncertainty import human as checkpoint_human

daemon = checkpoint_daemon
human = checkpoint_human


class SimulatedCrash(BaseException):
    pass


async def crash_before_item(d, doc, monkeypatch, kind="session"):
    op, _ = d.ops.create(CLEANER, **copy.deepcopy(cleanup.apply_request(doc, "crash-" + doc["preview_id"])))
    op = d.ops._transition(op["operation_id"], "running")
    execute = cleanup._execute_item

    async def crash(ctx, item, payload):
        if item["kind"] == kind:
            raise SimulatedCrash()
        await execute(ctx, item, payload)

    with monkeypatch.context() as patch:
        patch.setattr(cleanup, "_execute_item", crash)
        with pytest.raises(SimulatedCrash):
            await cleanup._run(OpContext(d.ops, op))
    return d.ops.get(op["operation_id"])


def reservations(op_id):
    document = json.loads(registry.registry_path().read_text())
    return ([g for g in document.get("cleanup_guards", {}).values()
             if g["operation_id"] == op_id and g["status"] == "reserved"],
            [s for s in document["sessions"] if s.get("cleanup_reservation") == op_id])


async def apply_after_refusal(d, target, refused_id):
    doc = await cleanup.preview(d.ops, CLEANER, target)
    assert doc["ready"]
    op, _ = d.ops.create(CLEANER, **cleanup.apply_request(doc, "after-refusal-" + refused_id))
    await settle_operations(d.ops, timeout=60)
    return d.ops.get(op["operation_id"])


@pytest.mark.parametrize("code", ["PREVIEW_EXPIRED", "PREVIEW_MISMATCH", "INTERNAL"])
async def test_e01_resumed_unstarted_refusal_releases_all_reservations(daemon, mock, monkeypatch, code):
    cp, _ = await setup_work(daemon, mock)
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    crashed = await crash_before_item(daemon, doc, monkeypatch)
    op_id = crashed["operation_id"]
    assert not crashed["steps"]
    assert reservations(op_id)[0] and reservations(op_id)[1]
    # Include every owned marker, plus one detached session marker, to exercise operation-wide release.
    owner = cleanup._OWNER.set(op_id)
    try:
        for item in doc["items"]:
            if item["decision"] == "reclaim":
                cleanup._mark(item, op_id, "reserved")
    finally:
        cleanup._OWNER.reset(owner)
    path = registry.registry_path()
    with registry._locked(path):
        document = json.loads(path.read_text())
        document["sessions"].append({"host": "h1", "session_id": "detached-marker", "cleanup_reservation": op_id})
        registry._write_document(path, document)
    assert any(r["status"] == "running" for r in cleanup.receipts(daemon.ops, op_id))
    with monkeypatch.context() as patch:
        if code == "PREVIEW_EXPIRED":
            patch.setattr(cleanup, "time", SimpleNamespace(time=lambda: doc["expires_at"] + 1,
                                                          monotonic=time.monotonic))
        elif code == "PREVIEW_MISMATCH":
            params = {**crashed["params"], "preview_token": crashed["params"]["preview_token"] + ".changed"}
            daemon.journal.db.execute("UPDATE operations SET params=? WHERE operation_id=?", (json.dumps(params), op_id))
        else:
            daemon.journal.db.execute("UPDATE cleanup_runs SET document='{' WHERE operation_id=?", (op_id,))
        await settle_operations(daemon.ops, timeout=60)
    done = daemon.ops.get(op_id)
    assert done["status"] == "failed" and done["error_code"] == code, done
    assert reservations(op_id) == ([], [])
    rows = cleanup.receipts(daemon.ops, op_id)
    assert all(r["status"] in {"failed", "retained", "already_absent"} for r in rows)
    assert all(r["error"]["code"] == code and r["after_state"]["guard_released"] for r in rows if r["status"] == "failed")
    assert done["result"]["items"] == rows
    assert (await apply_after_refusal(daemon, target, op_id))["status"] == "succeeded"


async def test_e01_resumed_expired_run_with_steps_keeps_reservations_and_finishes(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    crashed = await crash_before_item(daemon, doc, monkeypatch, "worktree")
    assert crashed["steps"] and all(s["status"] == "succeeded" for s in crashed["steps"])
    assert reservations(crashed["operation_id"])[0]

    def no_release(*args):
        pytest.fail("a resumed run with external steps must not release unstarted reservations")

    with monkeypatch.context() as patch:
        patch.setattr(cleanup, "time", SimpleNamespace(time=lambda: doc["expires_at"] + 1,
                                                      monotonic=time.monotonic))
        patch.setattr(cleanup, "_release_unstarted", no_release)
        await settle_operations(daemon.ops, timeout=60)
    done = daemon.ops.get(crashed["operation_id"])
    assert done["status"] == "succeeded", done
    assert reservations(done["operation_id"]) == ([], [])


async def test_e01_expiry_after_read_only_failure_settles_unstarted_uncertainty(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target)

    async def unavailable(*args):
        raise OSError("read-only observation unavailable before any external step")

    with monkeypatch.context() as patch:
        patch.setattr(cleanup, "_execute_item", unavailable)
        done = await apply(daemon, doc)
    assert done["status"] == "uncertain" and not done["steps"]
    assert reservations(done["operation_id"])[0]
    daemon.journal.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (done["operation_id"],))
    with monkeypatch.context() as patch:
        patch.setattr(cleanup, "time", SimpleNamespace(time=lambda: doc["expires_at"] + 1,
                                                      monotonic=time.monotonic))
        await settle_operations(daemon.ops, timeout=60)
    failed = daemon.ops.get(done["operation_id"])
    assert failed["status"] == "failed" and failed["error_code"] == "PREVIEW_EXPIRED", failed
    assert reservations(done["operation_id"]) == ([], [])
    assert all(r["status"] in {"failed", "retained", "already_absent"} for r in cleanup.receipts(daemon.ops, done["operation_id"]))
    assert (await apply_after_refusal(daemon, target, done["operation_id"]))["status"] == "succeeded"


async def test_e01_resumed_mismatch_with_steps_never_releases_guard(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    crashed = await crash_before_item(daemon, doc, monkeypatch, "worktree")
    before = reservations(crashed["operation_id"])
    assert crashed["steps"] and before[0]
    params = {**crashed["params"], "preview_token": crashed["params"]["preview_token"] + ".changed"}
    daemon.journal.db.execute("UPDATE operations SET params=? WHERE operation_id=?",
                              (json.dumps(params), crashed["operation_id"]))
    await settle_operations(daemon.ops, timeout=60)
    done = daemon.ops.get(crashed["operation_id"])
    assert done["status"] == "failed" and done["error_code"] == "PREVIEW_MISMATCH"
    assert reservations(done["operation_id"]) == before


async def test_e01_dependency_refusal_keeps_unresolved_call_reserved(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    crashed = await crash_before_item(daemon, doc, monkeypatch)
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    name = "item." + item["resource_id"] + ".preserve.a1"
    daemon.ops._step_start(crashed["operation_id"], name, {"phase": "preserve"})
    # Exercise an unsettled prerequisite receipt while this item's durable call remains unresolved.
    async def unsettled_prerequisite(ctx, current, payload):
        assert current["kind"] == "session"

    monkeypatch.setattr(cleanup, "_execute_item", unsettled_prerequisite)
    await settle_operations(daemon.ops, timeout=60)
    done = daemon.ops.get(crashed["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "UNCERTAIN_UNRESOLVED", done
    assert any(g["path"] == item["path"] for g in reservations(done["operation_id"])[0])
    row = next(r for r in cleanup.receipts(daemon.ops, done["operation_id"]) if r["resource_id"] == item["resource_id"])
    assert row["status"] == "uncertain" and row["error"]["refused_code"] == "DEPENDENCY_FAILED"
    assert next(s for s in done["steps"] if s["name"] == name)["status"] == "started"


@pytest.mark.parametrize("where", ["validate", "reservation", "set_refs"])
async def test_e01_refusal_before_first_step_releases_guard(daemon, mock, monkeypatch, where):
    cp, _ = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    original = cleanup._mark

    if where == "validate":
        async def refuse(*args):
            raise OperationError("PREVIEW_STALE", "changed before first step", 409)
        monkeypatch.setattr(cleanup, "_execute_item", refuse)
    elif where == "reservation":
        def mark(item, op_id, status):
            original(item, op_id, status)
            if status == "reserved":
                raise OperationError("PREVIEW_STALE", "refused after reservation", 409)
        monkeypatch.setattr(cleanup, "_mark", mark)
    else:
        def set_refs(*args, **kwargs):
            raise OperationError("PREVIEW_STALE", "refused before the item loop", 409)
        monkeypatch.setattr(OpContext, "set_refs", set_refs)
    done = await apply(daemon, doc)
    assert done["status"] == ("failed" if where == "set_refs" else "needs_attention")
    assert done["error_code"] == "PREVIEW_STALE"
    assert not done["steps"] and reservations(done["operation_id"]) == ([], [])
    rows = cleanup.receipts(daemon.ops, done["operation_id"])
    assert all(r["status"] not in {"pending", "running", "uncertain"} for r in rows)


@pytest.mark.parametrize("explicit_dependency", [False, True])
async def test_e01_already_absent_receipt_and_satisfied_dependency(daemon, mock, monkeypatch, explicit_dependency):
    cp, started = await setup_work(daemon, mock)
    mock.metas[started["result"]["session_id"]] = None
    original_snapshot = cleanup.snapshot
    absent_id = None

    async def snapshot(*args, **kwargs):
        nonlocal absent_id
        document = await original_snapshot(*args, **kwargs)
        if explicit_dependency:
            absent = next((i for i in document["items"] if i["kind"] == "session" and i["decision"] == "already_absent"), None)
            if absent:
                absent_id = absent["resource_id"]
            for item in document["items"]:
                if item["kind"] == "worktree" and item["decision"] == "reclaim":
                    item["dependencies"].append(absent_id)
        return document

    monkeypatch.setattr(cleanup, "snapshot", snapshot)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    absent = next(i for i in doc["items"] if i["kind"] == "session" and i["decision"] == "already_absent")
    worktree = next(i for i in doc["items"] if i["kind"] == "worktree")
    assert worktree["decision"] == "reclaim"
    execute = cleanup._execute_item
    executed = []

    async def record(ctx, item, payload):
        executed.append(item["resource_id"])
        await execute(ctx, item, payload)

    monkeypatch.setattr(cleanup, "_execute_item", record)
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    assert absent["resource_id"] not in executed and worktree["resource_id"] in executed
    rows = {r["resource_id"]: r for r in done["result"]["items"]}
    assert rows[absent["resource_id"]]["status"] == "already_absent"
    assert rows[worktree["resource_id"]]["status"] == "succeeded"
    assert done["result"]["summary"]["already_absent"] == sum(r["status"] == "already_absent" for r in rows.values())
    assert done["result"]["summary"]["retained"] == sum(r["status"] == "retained" for r in rows.values())
    assert not any(s["name"].startswith("item." + absent["resource_id"] + ".") for s in done["steps"])
    assert not any(frame["channel"] == "claude:stop-session" for frame in mock.invokes)
    assert not cleanup.lookup(daemon.journal.db, absent["resource_id"])
    assert absent["resource_id"] not in json.loads(registry.registry_path().read_text()).get("cleanup_guards", {})
    assert registry.get("h1", absent["session_id"])["status"] != "cleaned"
    token = api_auth.issue(daemon.journal.db, CLEANER.actor, sorted(CLEANER.scopes))
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        status, body = await http(port, "GET", "/api/v1/operations/" + done["operation_id"], tok=token)
        assert status == 200
        receipt = next(r for r in body["cleanup_receipts"] if r["resource_id"] == absent["resource_id"])
        assert receipt["status"] == "already_absent" and receipt["completed_phases"] == []
        status, body = await http(port, "GET", "/api/v1/cleanup-tombstones?original_id=" + absent["resource_id"], tok=token)
        assert status == 200 and body["tombstones"] == []
    finally:
        server.close()
        await server.wait_closed()
