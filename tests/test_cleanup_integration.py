"""Cleanup integration scopes, plan §23/E01/E02: real Git, MockBat and FakeGitHub only."""
from __future__ import annotations

import pytest

from bat_agent_connector import cleanup, registry
from bat_agent_connector.operations import OperationError
from tests.test_cleanup import CLEANER
from tests.test_cleanup import known_live_terminals as cleanup_terminals
from tests.test_integration import conflicted
from tests.test_integration import gh as integration_gh
from tests.test_integration import hermetic_git as integration_git
from tests.test_integration import world as integration_world

gh = integration_gh
hermetic_git = integration_git
world = integration_world
known_live_terminals = cleanup_terminals


async def test_e01_removed_host_known_only_by_failed_prepare_remains_inspectable(world, monkeypatch):
    w = world

    def interrupted():
        raise OperationError("PREPARE_INTERRUPTED", "fixture failure after creating the integration area", 409)

    w.runner.after["preview-prepare"] = interrupted
    failed = await w.run("integration.preview", {"host": "h1", "repository": "o/r", "pull_number": 1},
                         {"sources": [{"kind": "branch", "id": "main"}]})
    assert failed["status"] == "failed" and failed["error_code"] == "PREPARE_INTERRUPTED", failed
    assert w.area().exists()
    assert not registry.list_entries()
    for table in ("checkpoints", "checkpoint_runs", "integration_previews", "tasks", "sessions_observed"):
        assert not w.d.journal.db.execute(f"SELECT 1 FROM {table}").fetchone()  # noqa: S608 - fixed table names
    target = {"kind": "integration", "operation_id": failed["operation_id"]}
    before = await cleanup.preview(w.d.ops, CLEANER, target)
    identities = {i["resource_id"] for i in before["items"] if i["kind"] in {"integration_area", "temporary"}}
    assert {i["kind"] for i in before["items"]} >= {"integration_area", "temporary"}
    w.d.fleet.config.hosts.pop("h1")

    def unavailable(*args, **kwargs):
        pytest.fail("historical-host preview must not look up a client or execute a host command")

    monkeypatch.setattr(w.d.fleet, "client", unavailable)
    monkeypatch.setattr(w.d.inventory.fleet, "client", unavailable)
    monkeypatch.setattr(w.runner, "available", unavailable)
    monkeypatch.setattr(w.runner, "run", unavailable)
    historical = await cleanup.preview(w.d.ops, CLEANER, {"kind": "host", "host": "h1"})
    direct = await cleanup.preview(w.d.ops, CLEANER, target)
    assert {i["resource_id"] for i in historical["items"]} == identities == {i["resource_id"] for i in direct["items"]}
    assert all(i["decision"] == "retain" and not i["steps"] and
               "OBSERVATION_UNAVAILABLE" in {r["code"] for r in i["reasons"]} for i in historical["items"])
    assert not historical["ready"]
    with pytest.raises(OperationError, match="UNKNOWN_HOST"):
        await cleanup.preview(w.d.ops, CLEANER, {"kind": "host", "host": "unknown-host"})


async def test_e01_integration_preview_apply_and_handoff_expand_to_same_resources(world):
    w = world
    doc, applied, _, _ = await conflicted(w)
    handoff = await w.run("integration.handoff", {"operation_id": applied["operation_id"]},
                          {"agent": "claude", "instructions": "Resolve both sources"})
    assert handoff["status"] == "succeeded", handoff
    preview_op = w.d.journal.db.execute("SELECT operation_id FROM integration_previews WHERE preview_id=?",
                                       (doc["preview_id"],)).fetchone()[0]
    # The handoff has only an apply target: expansion must traverse handoff -> apply -> preview.
    assert "preview_id" not in handoff["params"]
    assert handoff["target"]["operation_id"] == applied["operation_id"]
    assert applied["params"]["preview_id"] == doc["preview_id"]
    snapshots = []
    for op_id in (preview_op, applied["operation_id"], handoff["operation_id"]):
        preview = await cleanup.preview(w.d.ops, CLEANER, {"kind": "integration", "operation_id": op_id})
        snapshots.append({i["resource_id"]: i for i in preview["items"]})
    items = list(snapshots[0].values())
    sources = {s["id"] for s in doc["sources"]}
    assert {i["creation_evidence"]["intent"] for i in items if i.get("flavor") == "checkpoint" and
            i["kind"] == "worktree"} == sources
    assert any(i["kind"] == "integration_area" and i["path"] == str(w.area().parent) for i in items)
    assert any(i["kind"] == "git_pin" and i["repository"] == str(w.area().parent) for i in items)
    assert any(i["kind"] == "worktree" and i.get("flavor") == "repair" and
               i["path"] == handoff["result"]["worktree_path"] for i in items)
    assert any(i["kind"] == "session" and i["session_id"] == handoff["result"]["session_id"] for i in items)
    assert snapshots[0] == snapshots[1] == snapshots[2]
