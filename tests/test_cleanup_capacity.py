"""E01/E02/plan §23: retirement frees runtime capacity without inventing resource cleanup."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bat_agent_connector import cleanup, lifecycle, orchestrate, registry, resource_policy, service
from bat_agent_connector.errors import ResourceReadOnly, WriteRefused
from tests.test_cleanup_standalone import (  # noqa: F401 - real Git/MockBat fixtures
    CLEANER,
    add_receipt,
    apply,
    close_clients,
    git,
    known_live_terminals,
    linked_work_item,
    standalone_worktree,
)
from tests.test_cleanup_standalone import daemon as standalone_daemon
from tests.test_cleanup_standalone import human as standalone_human
from tests.test_relay import msg

daemon = standalone_daemon
human = standalone_human


async def planner(d, mock, human, tmp_path):
    repo, start = await standalone_worktree(d, mock, human, tmp_path)
    sid = start["session_id"]
    registry.update("h1", sid, role="planner")
    mock.states[sid] = {"isStreaming": False, "messages": [msg(0, "user", "plan"), msg(1, "assistant",
        '```bat-fanout\n[{"title":"A","prompt":"task A"},{"title":"B","prompt":"task B"}]\n```')]}
    d.fleet.config.hosts["h1"] = replace(d.fleet.config.host("h1"), orchestrate_max_sessions=3)
    return repo, start


async def test_e01_confirmed_planner_stop_frees_capacity_and_worktree_stays_reclaimable(daemon, mock, human, tmp_path):
    repo, start = await planner(daemon, mock, human, tmp_path)
    sid = start["session_id"]
    original = registry.get("h1", sid)
    target = await linked_work_item(daemon, "h1/" + sid)
    result = await lifecycle.fanout_from_plan(daemon.fleet, "h1", sid, confirm=True)
    assert result["planner_cleanup"]["stopped"], result
    retired = registry.get("h1", sid)
    assert retired["status"] == "stopped" and retired["stopped_by"] == daemon.fleet.actor
    for key in ("created_at", "origin_root", "worktree_path", "branch"):
        assert retired[key] == original[key]
    assert len(registry.list_entries("h1", active_only=True)) == 2
    after = await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True)
    assert after["started"]
    with pytest.raises(WriteRefused, match="cap reached"):
        await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True)
    add_receipt(daemon, {"observation": {"head": git(start["worktree_path"], "rev-parse", "HEAD")}},
                source_kind="session", source_id=sid)
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    wt = next(i for i in doc["items"] if i["kind"] == "worktree" and i["path"] == start["worktree_path"])
    assert wt["decision"] == "reclaim", wt
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    assert not Path(start["worktree_path"]).exists() and repo.exists()
    assert registry.get("h1", sid) == retired  # a non-counted planner's stop history is not rewritten.
    assert not cleanup.lookup(daemon.journal.db, next(i["resource_id"] for i in doc["items"] if i.get("session_id") == sid))


@pytest.mark.parametrize("failure", ["ack", "still_loaded", "read_failed"])
async def test_e01_unconfirmed_planner_stop_stays_counted(daemon, mock, human, tmp_path, failure):
    _, start = await planner(daemon, mock, human, tmp_path)
    sid = start["session_id"]
    original = registry.get("h1", sid)
    if failure == "ack":
        mock.handlers["claude:stop-session"] = lambda p: {"ok": False}
    elif failure == "still_loaded":
        mock.handlers["claude:stop-session"] = lambda p: {"ok": True}
    else:
        def failed(p):
            if p["sessionId"] == sid and mock.metas[sid] is None:
                raise RuntimeError("stop read-back unavailable")
            return mock.metas.get(p["sessionId"])
        mock.handlers["claude:get-session-meta"] = failed
    result = await lifecycle.fanout_from_plan(daemon.fleet, "h1", sid, confirm=True)
    assert not result["planner_cleanup"]["stopped"] and result["planner_cleanup"]["reason"]
    assert registry.get("h1", sid) == original
    assert len(registry.list_entries("h1", active_only=True)) == 3
    with pytest.raises(WriteRefused, match="cap reached"):
        await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True)


@pytest.mark.parametrize("carrier", ["reclaimed", "already_absent", "retained"])
async def test_e01_absent_session_capacity_follows_carrier_receipt(daemon, mock, human, tmp_path, carrier):
    _, start = await standalone_worktree(daemon, mock, human, tmp_path)
    sid, path = start["session_id"], Path(start["worktree_path"])
    add_receipt(daemon, {"observation": {"head": git(path, "rev-parse", "HEAD")}}, source_kind="session", source_id=sid)
    mock.metas[sid] = None
    if carrier == "already_absent":
        git(path.parent.parent, "worktree", "remove", str(path))
    elif carrier == "retained":
        (path / "uncommitted.txt").write_text("keep working here")
    # A separate managed idle runtime makes this mixed plan applyable even when the carrier stays.
    await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True, use_worktree=False)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    absent = next(i for i in doc["items"] if i.get("session_id") == sid)
    assert absent["decision"] == "already_absent"
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    row = registry.get("h1", sid)
    assert row["status"] == ("active" if carrier == "retained" else "absent_at_cleanup")
    if carrier != "retained":
        assert row["retirement"]["operation_id"] == done["operation_id"]
        receipt = next(r for r in done["result"]["items"] if r["resource_id"] == absent["resource_id"])
        assert receipt["status"] == "already_absent" and receipt["after_state"]["stopped_by_cleanup"] is False
    assert not cleanup.lookup(daemon.journal.db, absent["resource_id"])
    assert not row.get("tombstone_resource_id")


@pytest.mark.parametrize("status", sorted(registry.RETIRED))
async def test_e01_retired_session_refuses_send_resume_and_same_id_start(daemon, mock, human, tmp_path, status):
    _, start = await standalone_worktree(daemon, mock, human, tmp_path)
    sid = start["session_id"]
    original = registry.get("h1", sid)
    mismatch = registry.retire("h1", sid, status, created_at=original["created_at"] + 1, actor="person", reason="wrong generation")
    assert mismatch == {"capacity_released": False, "registry_status": "active", "capacity_reason": "generation_changed"}
    assert registry.get("h1", sid)["status"] == "active"
    registry.retire("h1", sid, status, created_at=original["created_at"], actor="person", reason="confirmed retirement")
    mock.metas[sid] = None
    before = len(mock.invokes)
    cls = resource_policy.classify(daemon.fleet.config.host("h1"), sid, terminal=service.registry_terminal(original),
                                   entries=registry.list_entries("h1"))
    assert cls.provenance == "connector_managed" and cls.registry_status == status
    with pytest.raises(ResourceReadOnly, match="SESSION_RETIRED"):
        await service.session_send(daemon.fleet, "h1", sid, "resume", confirm=True, ensure_loaded=True)
    with pytest.raises(ResourceReadOnly, match="SESSION_RETIRED"):
        await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True, session_id=sid)
    with pytest.raises(ResourceReadOnly, match="SESSION_RETIRED"):
        registry.ensure_existing("h1", original)
    assert not any(i["channel"] in {"claude:client-resume", "claude:send-message", "claude:start-session", "worktree:create"}
                   for i in mock.invokes[before:])
    assert registry.get("h1", sid)["status"] == status


async def test_e01_absent_session_without_worktree_leaves_cap(daemon, mock, human, tmp_path):
    _, live = await standalone_worktree(daemon, mock, human, tmp_path)
    idle = await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True, use_worktree=False)
    mock.metas[idle["session_id"]] = None
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    row = registry.get("h1", idle["session_id"])
    assert row["status"] == "absent_at_cleanup" and row["retirement"]["carrier_resource_id"] is None
    assert row["retirement"]["operation_id"] == done["operation_id"]
    assert not row.get("tombstone_resource_id")
    assert registry.get("h1", live["session_id"])["status"] == "cleaned"


@pytest.mark.parametrize("removed", [True, False])
async def test_e01_legacy_worktree_remove_keeps_runtime_retired(daemon, mock, human, tmp_path, removed):
    repo, start = await standalone_worktree(daemon, mock, human, tmp_path)
    sid, path = start["session_id"], Path(start["worktree_path"])
    registry.retire("h1", sid, "stopped", created_at=registry.get("h1", sid)["created_at"],
                    actor="person", reason="confirmed stop")
    mock.metas[sid] = None

    def remove(p):
        if removed:
            git(repo, "worktree", "remove", str(path))
            mock.worktrees.pop(sid, None)
        return {"success": removed}

    mock.handlers["worktree:remove"] = remove
    mock.handlers["git:getRoot"] = lambda p: git(p["cwd"], "rev-parse", "--show-toplevel") if Path(p["cwd"]).exists() else None
    result = await orchestrate.worktree_remove(daemon.fleet, "h1", sid, confirm=True)
    assert result["removed"] is removed
    row = registry.get("h1", sid)
    assert row["status"] == "stopped" and row["worktree_removed"] is removed
    with pytest.raises(ResourceReadOnly, match="SESSION_RETIRED"):
        await service.session_send(daemon.fleet, "h1", sid, "resume", confirm=True, ensure_loaded=True)
    assert not registry.list_entries("h1", active_only=True)
