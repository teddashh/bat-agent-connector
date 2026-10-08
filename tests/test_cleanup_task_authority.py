"""Cleanup retains task carriers using the same durable owner lookup as runtime controls."""

import copy
from pathlib import Path

import pytest

from bat_agent_connector import cleanup, registry, task_control
from tests.test_cleanup import CLEANER, apply, setup_work
from tests.test_cleanup import daemon as cleanup_daemon
from tests.test_cleanup import human as cleanup_human
from tests.test_cleanup import known_live_terminals as cleanup_live_terminals

daemon = cleanup_daemon
human = cleanup_human
known_live_terminals = cleanup_live_terminals


def historical_owner(daemon, sid, source):
    journal = daemon.journal
    task = journal.submit(project="fixture", host="h1", workspace="demo-project", original_words="task-owned work",
                          idempotency_key="ownership-" + sid)
    if source == "command":
        command, _ = journal.command(task["task_id"], "start_lead", sid, {}, "start-" + sid)
        journal.command_status(command["command_id"], "cancelled")
    else:
        journal.add_branch(task["task_id"], session_id=sid, provider="codex", role="lead", reason="recorded start")
    assert journal.get(task["task_id"])["session_id"] is None
    assert registry.get("h1", sid).get("task_id") is None
    assert task_control.owner_task(daemon.fleet, "h1", sid) == task["task_id"]
    return task["task_id"]


@pytest.mark.parametrize("source", ["command", "branch"])
async def test_historical_task_binding_retains_cleanup_carrier_without_registry_tag(daemon, mock, source):
    cp, op = await setup_work(daemon, mock)
    sid = op["result"]["session_id"]
    task_id = historical_owner(daemon, sid, source)
    before = list(daemon.journal.db.iterdump()), registry.registry_path().read_bytes(), copy.deepcopy(mock.invokes)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    for item in doc["items"]:
        if item["kind"] in {"session", "worktree", "local_branch"}:
            assert item["task_owned"] and task_id in item["original_ids"]
            assert item["decision"] == "retain" and "TASK_OWNED" in {r["code"] for r in item["reasons"]}
    assert not doc["ready"]
    assert list(daemon.journal.db.iterdump()) == before[0]
    assert registry.registry_path().read_bytes() == before[1]
    assert not any(i["channel"] in {"claude:stop-session", "worktree:remove"} for i in mock.invokes[len(before[2]):])


@pytest.mark.parametrize("phase", ["lock.session", "preserve"])
async def test_late_task_binding_is_checked_before_cleanup_host_effect(daemon, mock, monkeypatch, phase):
    cp, op = await setup_work(daemon, mock)
    sid, path = op["result"]["session_id"], op["result"]["worktree_path"]
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    assert doc["ready"]
    original, reached = cleanup._host_call, []

    async def race(ops, host, req, timeout=cleanup.READ_DEADLINE_S, *, locked_check=None, locked_action=None):
        if locked_check and req.get("phase") == phase:
            check = locked_check
            async def new_owner():
                historical_owner(daemon, sid, "branch")
                reached.append(phase)
                await check()
            locked_check = new_owner
        return await original(ops, host, req, timeout, locked_check=locked_check, locked_action=locked_action)

    monkeypatch.setattr(cleanup, "_host_call", race)
    before = len(mock.invokes)
    done = await apply(daemon, doc)
    assert reached == [phase] and done["status"] == "needs_attention", done
    assert any(r["error"] and r["error"].get("refused_code", r["error"]["code"]) == "PREVIEW_STALE"
               for r in cleanup.receipts(daemon.ops, done["operation_id"]))
    assert Path(path).exists()
    stops = [i for i in mock.invokes[before:] if i["channel"] == "claude:stop-session"]
    assert len(stops) == (0 if phase == "lock.session" else 1)
