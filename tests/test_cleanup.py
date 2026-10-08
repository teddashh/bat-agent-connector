"""Managed cleanup, plan §23/E01/E02: real temporary Git repositories and MockBat only."""
from __future__ import annotations

import asyncio
import copy
from pathlib import Path

import pytest

from bat_agent_connector import api_auth, cleanup, lifecycle, orchestrate, registry
from bat_agent_connector.operations import OperationError
from tests.test_checkpoints import (  # noqa: F401 - pytest fixtures shared with real Git checkpoint tests
    LocalRunner,
    git,
    make_checkpoint,
    run,
    snapshot,
)
from tests.test_checkpoints import (
    daemon as checkpoint_daemon,
)
from tests.test_checkpoints import (
    human as checkpoint_human,
)

daemon = checkpoint_daemon
human = checkpoint_human

CLEANER = api_auth.Principal("cleaner", frozenset({"observe", "cleanup"}))
DISCARDER = api_auth.Principal("person", frozenset({"observe", "cleanup", "cleanup_discard"}))


async def setup_work(d, mock):
    cp = await make_checkpoint(d)
    op = await run(d, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]}, {"instructions": "finish"})
    assert op["status"] == "succeeded", op
    sid = op["result"]["session_id"]
    mock.metas[sid]["isStreaming"] = False
    return cp, op


async def apply(d, doc, principal=CLEANER):
    op, _ = d.ops.create(principal, **copy.deepcopy(cleanup.apply_request(doc, "apply-" + doc["preview_id"])))
    await d.ops.drain(timeout=60)
    return d.ops.get(op["operation_id"])


async def test_e01_preview_is_pure_and_signed_plan_cannot_be_changed(daemon, mock, human):
    cp, op = await setup_work(daemon, mock)
    clone = Path(op["external_refs"]["clone_path"])
    before, manual = git(clone, "for-each-ref"), snapshot(human)
    db = list(daemon.journal.db.iterdump())
    reg = registry.registry_path().read_bytes()
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    assert doc["ready"], [(i["kind"], i["reasons"], i.get("observation")) for i in doc["items"]]
    assert before == git(clone, "for-each-ref") and manual == snapshot(human)
    assert db == list(daemon.journal.db.iterdump()) and reg == registry.registry_path().read_bytes()
    req = cleanup.apply_request(doc, "wrong")
    req["preconditions"]["preview_fingerprint"] = "wrong"
    with pytest.raises(OperationError, match="PREVIEW_MISMATCH"):
        daemon.ops.create(CLEANER, **req)
    req = cleanup.apply_request(doc, "actor")
    with pytest.raises(OperationError, match="PREVIEW_MISMATCH"):
        daemon.ops.create(DISCARDER, **req)
    req = cleanup.apply_request(doc, "tamper")
    req["params"]["preview_token"] += "broken"
    with pytest.raises(OperationError, match="PREVIEW_TOKEN_INVALID"):
        daemon.ops.create(CLEANER, **req)


async def test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs(daemon, mock, human):
    cp, op = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    wt = next(i for i in doc["items"] if i["kind"] == "worktree")
    assert not Path(wt["path"]).exists()
    assert git(wt["repository"], "rev-parse", "refs/batc/retained/" + wt["resource_id"] + "/" + wt["observation"]["head"])
    assert git(wt["repository"], "show-ref", "--heads")
    assert wt["branch"] not in git(wt["repository"], "for-each-ref", "refs/heads/")
    assert Path(wt["repository"]).exists()
    ret = await cleanup.retained(daemon.ops)
    assert ret["retained"] and not ret["unavailable"]
    assert cleanup.lookup(daemon.journal.db, cp["checkpoint_id"])


async def test_e01_release_keeps_commits_with_cleanup_scope(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    wt = Path(op["result"]["worktree_path"])
    git(wt, "config", "user.name", "test")
    git(wt, "config", "user.email", "test@example.invalid")
    (wt / "result.txt").write_text("undelivered")
    git(wt, "add", ".")
    git(wt, "commit", "-qm", "result")
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    assert "RESULTS_NOT_DELIVERED" in {r["code"] for r in item["reasons"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target, {"release_undelivered": [item["resource_id"]]})
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    assert git(item["repository"], "rev-parse", item["branch"]) == item["observation"]["head"]
    assert not wt.exists()


async def test_e01_discard_requires_cleanup_discard(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    wt = Path(op["result"]["worktree_path"])
    (wt / "uncommitted.txt").write_text("content")
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    with pytest.raises(OperationError, match="DISCARD_SCOPE_REQUIRED"):
        await cleanup.preview(daemon.ops, CLEANER, target, {"discard_uncommitted": [item["resource_id"]]})
    doc = await cleanup.preview(daemon.ops, DISCARDER, target, {"discard_uncommitted": [item["resource_id"]]})
    done = await apply(daemon, doc, DISCARDER)
    assert done["status"] == "succeeded", done
    assert not wt.exists()


async def test_e01_stale_any_item_stops_before_mutation_and_reports_changes(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    (Path(op["result"]["worktree_path"]) / "changed.txt").write_text("changed")
    count = len(mock.invokes)
    done = await apply(daemon, doc)
    assert done["error_code"] == "PREVIEW_STALE", done
    assert not [i for i in mock.invokes[count:] if i["channel"] == "claude:stop-session"]
    assert not daemon.journal.db.execute("SELECT * FROM cleanup_retained").fetchall()


async def test_e01_task_owned_resources_are_retained(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    registry.update("h1", op["result"]["session_id"], task_id="task-owned")
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    assert all("TASK_OWNED" in {r["code"] for r in i["reasons"]} for i in doc["items"] if i["kind"] in
               {"session", "worktree", "local_branch"})
    assert not doc["ready"]


async def test_e01_previews_serialize_per_host_and_share_read_deadline(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    original = daemon.ops.context["git_runner"]
    active = maximum = 0
    class SlowRunner(LocalRunner):
        async def run(self, host, script, timeout_s=None):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(.08)
                return await original.run(host, script, timeout_s)
            finally:
                active -= 1
    daemon.ops.context["git_runner"] = SlowRunner()
    monkeypatch.setattr(cleanup, "READ_DEADLINE_S", .05)
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    docs = await asyncio.gather(*(cleanup.preview(daemon.ops, CLEANER, target) for _ in range(3)))
    assert maximum == 1
    assert all(any(r["code"] == "OBSERVATION_UNAVAILABLE" for i in d["items"] for r in i["reasons"]) for d in docs)


async def test_e01_guard_refuses_legacy_writes_on_reserved_and_cleaned_resources(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    sid = op["result"]["session_id"]
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    item = next(i for i in doc["items"] if i["kind"] == "session")
    cleanup._mark(item, "op-test", "reserved")
    from bat_agent_connector.errors import ResourceReadOnly
    with pytest.raises(ResourceReadOnly, match="CLEANUP_IN_PROGRESS"):
        await orchestrate.worktree_remove(daemon.fleet, "h1", sid, confirm=True)
    cleanup._release(item, "op-test")
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    with pytest.raises(ResourceReadOnly, match="RESOURCE_CLEANED"):
        await orchestrate.worktree_remove(daemon.fleet, "h1", sid, confirm=True)


async def test_e01_legacy_apply_is_disabled_and_auto_cleanup_still_loads(daemon, mock):
    daemon.fleet.config.host("h1").auto_cleanup = True
    with pytest.raises(OperationError, match="LEGACY_CLEANUP_DISABLED"):
        await lifecycle.session_cleanup(daemon.fleet, "h1", confirm=True, dry_run=False)
