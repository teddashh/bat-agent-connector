"""Cleanup integration scopes, plan §23/E01/E02: real Git, MockBat and FakeGitHub only."""
from __future__ import annotations

from bat_agent_connector import cleanup
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
