"""Standalone registry-owned BAT worktrees: no checkpoint, integration or task carrier record."""
from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from pathlib import Path

import pytest

from bat_agent_connector import api_auth, cleanup, orchestrate, registry
from tests.operation_helpers import settle_operations
from tests.test_cleanup import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    add_receipt,
    apply,
    git,
    known_live_terminals,
    snapshot,
)
from tests.test_cleanup import (
    daemon as standalone_daemon,
)
from tests.test_cleanup import (
    human as standalone_human,
)

daemon = standalone_daemon
human = standalone_human


@pytest.fixture(autouse=True)
async def close_clients(daemon):
    yield
    await daemon.inventory.fleet.close()
    await daemon.fleet.close()


async def standalone_worktree(d, mock, human, tmp_path, *, managed=True, host="h1"):
    repo = tmp_path / ("managed" if managed else "outside") / ("standalone" if host == "h1" else host + "-standalone")
    repo.parent.mkdir(parents=True, exist_ok=True)
    git(repo.parent, "clone", "-q", "--no-hardlinks", str(human), str(repo))
    git(repo, "config", "batc.managed-clone", "true")
    workspace = mock.ws_doc["workspaces"][0 if host == "h1" else 1]
    workspace["folderPath"] = str(repo)
    mock.handlers["git:getRoot"] = lambda p: git(p["cwd"], "rev-parse", "--show-toplevel")

    def create(p):
        path = repo / ".bat-worktrees" / p["sessionId"]
        branch = "bat/worktree-" + p["sessionId"]
        git(repo, "worktree", "add", "-q", "-b", branch, str(path), "main")
        return {"success": True, "worktreePath": str(path), "branchName": branch, "sourceBranch": "main"}

    mock.handlers["worktree:create"] = create
    started = await orchestrate.session_start(d.fleet, host, workspace["id"], confirm=True, use_worktree=True)
    assert started["started"] and registry.get(host, started["session_id"])["origin_root"] == str(repo)
    assert not d.journal.db.execute("SELECT 1 FROM checkpoint_runs").fetchone()
    assert not d.journal.db.execute("SELECT 1 FROM integration_previews").fetchone()
    assert not d.journal.db.execute("SELECT 1 FROM tasks").fetchone()
    return repo, started


async def linked_work_item(d, *refs):
    person = api_auth.Principal("planner", frozenset({"manage"}))
    for host in {ref.split("/", 1)[0] for ref in refs}:
        await d.inventory.refresh_host(host)

    async def manage(action, target, params, key):
        op, _ = d.ops.create(person, action=action, target=target, params=params, idempotency_key=key)
        await settle_operations(d.ops, timeout=30)
        done = d.ops.get(op["operation_id"])
        assert done["status"] == "succeeded", done
        return done["result"]

    project = await manage("project.create", {}, {"name": "Standalone"}, "standalone-project")
    item = await manage("work_item.create", {"project_id": project["project_id"]},
                        {"title": "Standalone work"}, "standalone-item")
    for ref in refs:
        await manage("work_item.link", {"work_item_id": item["work_item_id"]},
                     {"kind": "session", "ref": ref}, "link-" + ref)
    return {"kind": "work_item", "work_item_id": item["work_item_id"]}


@pytest.mark.parametrize("scope", ["host", "work_item"])
async def test_e01_standalone_bat_worktree_and_branch_are_reclaimed(daemon, mock, human, tmp_path, scope):
    repo, started = await standalone_worktree(daemon, mock, human, tmp_path)
    sid, path = started["session_id"], Path(started["worktree_path"])
    target = {"kind": "host", "host": "h1"} if scope == "host" else await linked_work_item(daemon, "h1/" + sid)
    # Delivery proof comes from the session receipt, never from an unchanged or ancestral HEAD.
    add_receipt(daemon, {"observation": {"head": git(path, "rev-parse", "HEAD")}},
                source_kind="session", source_id=sid)
    before = snapshot(human)
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    wt = next((i for i in doc["items"] if i["kind"] == "worktree" and i["path"] == str(path)), None)
    assert wt is not None, [(i["kind"], i.get("path")) for i in doc["items"]]
    branch = next(i for i in doc["items"] if i["kind"] == "local_branch" and i["branch"] == started["branch"])
    carrier = next(i for i in doc["items"] if i["kind"] == "clone" and i["path"] == str(repo))
    assert wt["decision"] == branch["decision"] == "reclaim", (wt["reasons"], branch["reasons"])
    assert branch["dependencies"] == [wt["resource_id"]]
    assert carrier["decision"] == "retain" and "RETAINED_CONTENT_STORE" in {r["code"] for r in carrier["reasons"]}
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    receipts = {r["resource_id"]: r for r in cleanup.receipts(daemon.ops, done["operation_id"])}
    assert receipts[wt["resource_id"]]["status"] == receipts[branch["resource_id"]]["status"] == "succeeded"
    assert not path.exists() and repo.exists()
    assert not git(repo, "for-each-ref", "refs/heads/" + started["branch"])
    for item in (wt, branch):
        assert git(repo, "rev-parse", "refs/batc/retained/" + item["resource_id"] + "/" + item["observation"]["head"])
        phases = [r["name"].split(".")[2] for r in daemon.journal.db.execute(
            "SELECT name FROM operation_steps WHERE operation_id=? AND name LIKE ? ORDER BY seq",
            (done["operation_id"], "item." + item["resource_id"] + ".%"))]
        assert phases[:2] == ["preserve", "remove"]
    assert snapshot(human) == before
    assert len([i for i in mock.invokes if i["channel"] == "claude:stop-session"]) == 1
    assert not any(i["channel"] == "worktree:remove" for i in mock.invokes)


@pytest.mark.parametrize("mismatch", ["carrier", "branch"])
async def test_e01_standalone_bat_worktree_live_binding_mismatch_is_retained(daemon, mock, human, tmp_path, mismatch):
    repo, started = await standalone_worktree(daemon, mock, human, tmp_path)
    path = Path(started["worktree_path"])
    if mismatch == "carrier":
        other = repo.parent / "other"
        git(repo.parent, "clone", "-q", "--no-hardlinks", str(human), str(other))
        git(other, "config", "batc.managed-clone", "true")
        git(repo, "worktree", "remove", str(path))
        git(other, "worktree", "add", "-q", "-b", started["branch"], str(path), "main")
    else:
        git(path, "switch", "-qc", "bat/different")
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    wt = next(i for i in doc["items"] if i["kind"] == "worktree" and i["path"] == str(path))
    assert wt["decision"] == "retain" and "BINDING_MISMATCH" in {r["code"] for r in wt["reasons"]}
    session = next(i for i in doc["items"] if i.get("session_id") == started["session_id"])
    assert session["decision"] == "retain"
    assert path.exists() and not any(i["channel"] == "claude:stop-session" for i in mock.invokes)


async def test_e01_standalone_bat_worktree_outside_managed_roots_is_listed_and_retained(daemon, mock, human, tmp_path):
    repo, started = await standalone_worktree(daemon, mock, human, tmp_path, managed=False)
    before = snapshot(repo)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    wt = next(i for i in doc["items"] if i["kind"] == "worktree" and i["path"] == started["worktree_path"])
    assert not wt["proven"] and wt["decision"] == "retain"
    assert "WORKDIR_NOT_MANAGED" in {r["code"] for r in wt["reasons"]}
    assert not doc["ready"] and snapshot(repo) == before
    assert Path(started["worktree_path"]).exists()
    assert not any(i["channel"] in {"claude:stop-session", "worktree:remove"} for i in mock.invokes)


async def test_e01_standalone_bat_release_keeps_undelivered_branch(daemon, mock, human, tmp_path):
    repo, started = await standalone_worktree(daemon, mock, human, tmp_path)
    target = {"kind": "host", "host": "h1"}
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    wt = next(i for i in doc["items"] if i["kind"] == "worktree" and i["path"] == started["worktree_path"])
    assert "RESULTS_NOT_DELIVERED" in {r["code"] for r in wt["reasons"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target, {"release_undelivered": [wt["resource_id"]]})
    branch = next(i for i in doc["items"] if i["kind"] == "local_branch")
    assert branch["decision"] == "retain" and "RESULTS_NOT_DELIVERED" in {r["code"] for r in branch["reasons"]}
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    assert not Path(wt["path"]).exists()
    assert git(repo, "rev-parse", started["branch"]) == wt["observation"]["head"]
    assert git(repo, "rev-parse", "refs/batc/retained/" + wt["resource_id"] + "/" + wt["observation"]["head"])


async def test_e01_multi_host_apply_observes_only_each_items_host(daemon, mock, human, tmp_path, monkeypatch):
    daemon.fleet.config.hosts["h2"] = replace(daemon.fleet.config.host("h1"), name="h2")
    repo, healthy = await standalone_worktree(daemon, mock, human, tmp_path)
    _, unavailable = await standalone_worktree(daemon, mock, human, tmp_path, host="h2")
    target = await linked_work_item(daemon, "h1/" + healthy["session_id"], "h2/" + unavailable["session_id"])
    add_receipt(daemon, {"observation": {"head": git(healthy["worktree_path"], "rev-parse", "HEAD")}},
                source_kind="session", source_id=healthy["session_id"])
    monkeypatch.setattr(cleanup, "READ_DEADLINE_S", 2)
    original_read, original_snapshot = cleanup._terminal_observations, cleanup.snapshot
    pending = asyncio.Event()
    terminal_reads, item_reads = [], []
    current_only = None

    async def terminals(ops, host, deadline):
        terminal_reads.append((current_only, host))
        if host == "h2":
            # The other host never replies. Bound the read using the real per-host deadline.
            await asyncio.wait_for(pending.wait(), max(.001, deadline - time.monotonic()))
        return await original_read(ops, host, deadline)

    async def observed(*args, **kwargs):
        nonlocal current_only
        previous, current_only = current_only, kwargs.get("only")
        if current_only:
            item_reads.append(current_only)
        try:
            return await original_snapshot(*args, **kwargs)
        finally:
            current_only = previous

    monkeypatch.setattr(cleanup, "_terminal_observations", terminals)
    monkeypatch.setattr(cleanup, "snapshot", observed)
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    reclaimed = {i["resource_id"] for i in doc["items"] if i["host"] == "h1" and i["decision"] == "reclaim"}
    assert {i["kind"] for i in doc["items"] if i["resource_id"] in reclaimed} == {"session", "worktree", "local_branch"}
    blocked = [i for i in doc["items"] if i["host"] == "h2" and i["kind"] in {"session", "worktree"}]
    assert {i["kind"] for i in blocked} == {"session", "worktree"}
    assert all(i["decision"] == "retain" and "OBSERVATION_UNAVAILABLE" in {r["code"] for r in i["reasons"]} for i in blocked)
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    receipts = {r["resource_id"]: r for r in cleanup.receipts(daemon.ops, done["operation_id"])}
    assert all(receipts[rid]["status"] == "succeeded" for rid in reclaimed)
    assert all(receipts[i["resource_id"]]["status"] == "retained" for i in blocked)
    assert set(item_reads) == reclaimed
    assert {only for only, host in terminal_reads if only} == reclaimed
    assert all(host == "h1" for only, host in terminal_reads if only), terminal_reads
    # Only the initial preview and apply's whole-plan validation pay the unavailable host's deadline.
    assert [only for only, host in terminal_reads if host == "h2"] == [None, None]
    assert not Path(healthy["worktree_path"]).exists() and Path(unavailable["worktree_path"]).exists()
    assert not git(repo, "for-each-ref", "refs/heads/" + healthy["branch"])
    assert [i["params"]["sessionId"] for i in mock.invokes if i["channel"] == "claude:stop-session"] == [healthy["session_id"]]
