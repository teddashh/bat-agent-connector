"""E01/E02 / plan §23: reviewed absence alone can release exhausted runtime capacity."""
from __future__ import annotations

from dataclasses import replace

import pytest

from bat_agent_connector import cleanup, orchestrate, registry
from bat_agent_connector.errors import WriteRefused
from bat_agent_connector.operations import OperationError
from tests.test_checkpoints import bat_writes
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


async def absent_runtime(d, mock, human, tmp_path, carrier):
    if carrier == "none":
        repo = tmp_path / "managed" / "main-checkout"
        repo.parent.mkdir(parents=True, exist_ok=True)
        git(repo.parent, "clone", "-q", str(human), str(repo))
        mock.ws_doc["workspaces"][0]["folderPath"] = str(repo)
        mock.handlers["git:getRoot"] = lambda p: git(p["cwd"], "rev-parse", "--show-toplevel")
        start = await orchestrate.session_start(d.fleet, "h1", "demo-project", confirm=True, use_worktree=False)
    else:
        repo, start = await standalone_worktree(d, mock, human, tmp_path)
        head = git(repo, "rev-parse", "HEAD")
        add_receipt(d, {"observation": {"head": head}}, source_kind="session", source_id=start["session_id"])
        git(repo, "worktree", "remove", start["worktree_path"])
        git(repo, "branch", "-D", start["branch"])
    mock.metas[start["session_id"]] = None
    return repo, start


@pytest.mark.parametrize("carrier", ["none", "absent"])
async def test_e01_all_absent_host_releases_capacity_without_external_mutation(daemon, mock, human, tmp_path, carrier):
    repo, start = await absent_runtime(daemon, mock, human, tmp_path, carrier)
    daemon.fleet.config.hosts["h1"] = replace(daemon.fleet.config.host("h1"), orchestrate_max_sessions=1)
    with pytest.raises(WriteRefused, match="cap reached"):
        await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True, use_worktree=False)
    before = registry.registry_path().read_bytes()
    mock.invokes.clear()
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    assert registry.registry_path().read_bytes() == before
    assert not any(i["decision"] == "reclaim" for i in doc["items"])
    assert doc["ready"], doc
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    receipt = next(r for r in done["result"]["items"] if r["plan"].get("session_id") == start["session_id"])
    assert receipt["status"] == "already_absent" and receipt["after_state"]["capacity_released"]
    assert registry.get("h1", start["session_id"])["status"] == "absent_at_cleanup"
    assert not bat_writes(mock)
    assert not daemon.journal.db.execute("SELECT 1 FROM operation_steps WHERE operation_id=?", (done["operation_id"],)).fetchone()
    assert not daemon.journal.db.execute("SELECT 1 FROM resource_tombstones").fetchone()
    assert repo.exists()
    again = await cleanup.preview(daemon.ops, CLEANER, doc["target"])
    assert not again["ready"]
    with pytest.raises(OperationError, match="PREVIEW_BLOCKED"):
        daemon.ops.create(CLEANER, **cleanup.apply_request(again, "already-retired"))
    assert (await orchestrate.session_start(daemon.fleet, "h1", "demo-project", confirm=True,
                                            use_worktree=False))["started"]


async def test_e01_absent_runtime_with_retained_carrier_cannot_enable_bookkeeping_apply(daemon, mock, human, tmp_path):
    _, start = await standalone_worktree(daemon, mock, human, tmp_path)
    mock.metas[start["session_id"]] = None
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "host", "host": "h1"})
    assert next(i for i in doc["items"] if i["kind"] == "worktree")["decision"] == "retain"
    assert not doc["ready"]
    with pytest.raises(OperationError, match="PREVIEW_BLOCKED"):
        daemon.ops.create(CLEANER, **cleanup.apply_request(doc, "retained-carrier"))
    assert registry.get("h1", start["session_id"])["status"] == "active"
