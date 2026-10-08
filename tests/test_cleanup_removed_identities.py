"""E01/E02/plan §23: creation identities outlive host configuration, without host calls."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bat_agent_connector import api_auth, cleanup
from bat_agent_connector.operations import OperationError
from tests.test_cleanup import repair_facts, setup_work
from tests.test_cleanup_standalone import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    add_receipt,
    apply,
    close_clients,
    git,
    known_live_terminals,
    standalone_worktree,
)
from tests.test_cleanup_standalone import daemon as standalone_daemon
from tests.test_cleanup_standalone import human as standalone_human

daemon = standalone_daemon
human = standalone_human


async def work_item(d, links):
    person = api_auth.Principal("planner", frozenset({"manage"}))

    async def manage(action, target, params, key):
        op, _ = d.ops.create(person, action=action, target=target, params=params, idempotency_key=key)
        await d.ops.drain(timeout=30)
        result = d.ops.get(op["operation_id"])
        assert result["status"] == "succeeded", result
        return result["result"]

    p = await manage("project.create", {}, {"name": "Historical resources"}, "history-project")
    item = await manage("work_item.create", {"project_id": p["project_id"]}, {"title": "Keep identities"}, "history-item")
    for kind, ref in links:
        await manage("work_item.link", {"work_item_id": item["work_item_id"]}, {"kind": kind, "ref": ref}, "link-" + ref)
    return {"kind": "work_item", "work_item_id": item["work_item_id"]}


def recorded(items):
    return {(i["kind"], i.get("path"), i.get("branch")): i["resource_id"] for i in items
            if i["host"] == "h1" and i["kind"] in {"session", "worktree", "local_branch", "clone", "integration_area"}}


@pytest.mark.parametrize("source", ["checkpoint", "task", "repair", "registry"])
async def test_e01_removed_host_keeps_every_creation_identity_and_apply_is_read_only(
        daemon, mock, human, tmp_path, monkeypatch, source):
    daemon.fleet.config.hosts["h2"] = replace(daemon.fleet.config.host("h1"), name="h2")
    _, healthy = await standalone_worktree(daemon, mock, human, tmp_path, host="h2")
    direct = None
    if source == "registry":
        _, old = await standalone_worktree(daemon, mock, human, tmp_path)
        source_link = "session", "h1/" + old["session_id"]
        path = old["worktree_path"]
    elif source == "task":
        repo = tmp_path / "managed" / "task-carrier"
        git(repo.parent, "clone", "-q", "--no-hardlinks", str(human), str(repo))
        git(repo, "config", "batc.managed-clone", "true")
        task = daemon.journal.submit(project="p", host="h1", workspace="ws-demo", original_words="keep task history",
                                     idempotency_key="historical-task")
        suffix = task["task_id"].replace("-", "")[:12]
        path = str(repo / ".bat-worktrees" / ("batc-task-" + suffix))
        branch = "batc/task-" + suffix
        git(repo, "worktree", "add", "-q", "-b", branch, path, "HEAD")
        daemon.journal.change(task["task_id"], "dispatching", fields={"external_worktree_path": path,
            "external_branch": branch, "base_commit": git(repo, "rev-parse", "HEAD")})
        source_link = "task", task["task_id"]
    else:
        # Checkpoint prepare also probes its not-yet-created destination; use MockBat's default
        # root response for that admission, then restore the real Git reads for cleanup.
        root = mock.handlers.pop("git:getRoot")
        try:
            cp, op = await setup_work(daemon, mock)
        finally:
            mock.handlers["git:getRoot"] = root
        source_link = "checkpoint", cp["checkpoint_id"]
        path = op["result"]["worktree_path"]
        direct = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
        if source == "repair":
            _, wt, handoff, _ = repair_facts(daemon, cp, op, human)
            path = str(wt)
            source_link = "operation", handoff
            direct = {"kind": "integration", "operation_id": handoff}
    add_receipt(daemon, {"observation": {"head": git(healthy["worktree_path"], "rev-parse", "HEAD")}},
                source_kind="session", source_id=healthy["session_id"], source_host="h2")
    await daemon.inventory.refresh_host("h1")
    await daemon.inventory.refresh_host("h2")
    target = await work_item(daemon, [source_link, ("session", "h2/" + healthy["session_id"])])
    before = await cleanup.preview(daemon.ops, CLEANER, target)
    old_ids = recorded(before["items"])
    assert {k[0] for k in old_ids} >= {"worktree", "local_branch", "integration_area" if source == "repair" else "clone"}
    assert any(k[0] == "worktree" and k[1] == path for k in old_ids)
    before_direct = await cleanup.preview(daemon.ops, CLEANER, direct) if direct else None
    daemon.fleet.config.hosts.pop("h1")
    calls = []
    for fleet in (daemon.fleet, daemon.inventory.fleet):
        client = fleet.client

        def configured(host, client=client):
            calls.append(host)
            assert host != "h1", "removed host must not construct a BAT client"
            return client(host)

        monkeypatch.setattr(fleet, "client", configured)
    runner = daemon.ops.context["git_runner"]
    run, available = runner.run, runner.available

    async def configured_run(host, *args, **kwargs):
        assert host != "h1", "removed host must not run SSH"
        return await run(host, *args, **kwargs)

    def configured_available(host):
        assert host != "h1", "removed host must not check SSH availability"
        return available(host)

    monkeypatch.setattr(runner, "run", configured_run)
    monkeypatch.setattr(runner, "available", configured_available)
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    assert recorded(doc["items"]) == old_ids
    removed = [i for i in doc["items"] if i["host"] == "h1"]
    assert removed and all(i["decision"] == "retain" and not i["steps"] and
                          "OBSERVATION_UNAVAILABLE" in {r["code"] for r in i["reasons"]} for i in removed)
    historical = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    assert not historical["ready"] and all(i["decision"] == "retain" for i in historical["items"])
    if direct:
        assert recorded((await cleanup.preview(daemon.ops, CLEANER, direct))["items"]) == recorded(before_direct["items"])
    for item in removed:
        current = await cleanup.snapshot(daemon.ops, doc["target"], doc["choices"], only=item["resource_id"])
        assert next(i for i in current["items"] if i["resource_id"] == item["resource_id"])["decision"] == "retain"
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    receipts = {r["resource_id"]: r for r in done["result"]["items"]}
    assert all(receipts[i["resource_id"]]["status"] == "retained" for i in removed)
    assert {r["plan"]["kind"] for r in receipts.values() if r["plan"]["host"] == "h2" and r["status"] == "succeeded"} == {
        "session", "worktree", "local_branch"}
    assert "h1" not in calls and Path(path).exists()
    async def never_checked():
        pytest.fail("a removed host must be refused before the locked gate")
    with pytest.raises(OperationError, match="OBSERVATION_UNAVAILABLE"):
        await cleanup._host_call(daemon.ops, "h1", {"phase": "remove.worktree"}, locked_check=never_checked)
