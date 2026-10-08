"""E01/E02/plan §23: historical resources remain readable after their host leaves config."""
from __future__ import annotations

import time
from dataclasses import replace

import pytest

from bat_agent_connector import cleanup
from bat_agent_connector.operations import OperationError
from tests.test_cleanup_standalone import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    add_receipt,
    apply,
    close_clients,
    git,
    known_live_terminals,
    linked_work_item,
    standalone_worktree,
)
from tests.test_cleanup_standalone import (
    daemon as standalone_daemon,
)
from tests.test_cleanup_standalone import (
    human as standalone_human,
)

daemon = standalone_daemon
human = standalone_human


async def test_e01_removed_host_history_is_retained_without_live_calls(daemon, mock, human, tmp_path, monkeypatch):
    daemon.fleet.config.hosts["h2"] = replace(daemon.fleet.config.host("h1"), name="h2")
    _, healthy = await standalone_worktree(daemon, mock, human, tmp_path)
    _, historical = await standalone_worktree(daemon, mock, human, tmp_path, host="h2")
    target = await linked_work_item(daemon, "h1/" + healthy["session_id"], "h2/" + historical["session_id"])
    add_receipt(daemon, {"observation": {"head": git(healthy["worktree_path"], "rev-parse", "HEAD")}},
                source_kind="session", source_id=healthy["session_id"])
    daemon.fleet.config.hosts.pop("h2")
    called = []
    for fleet in (daemon.fleet, daemon.inventory.fleet):
        original = fleet.client

        def configured_client(host, original=original):
            called.append(host)
            assert host in daemon.fleet.config.hosts, "cleanup tried to open an unconfigured host"
            return original(host)

        monkeypatch.setattr(fleet, "client", configured_client)
    doc = await cleanup.preview(daemon.ops, CLEANER, target)
    old = next(i for i in doc["items"] if i["host"] == "h2" and i.get("session_id") == historical["session_id"])
    assert old["decision"] == "retain" and not old["steps"] and not old["proven"]
    assert "OBSERVATION_UNAVAILABLE" in {r["code"] for r in old["reasons"]}
    assert {i["kind"] for i in doc["items"] if i["host"] == "h1" and i["decision"] == "reclaim"} == {
        "session", "worktree", "local_branch"}
    assert "h2" not in called
    current = await cleanup.snapshot(daemon.ops, doc["target"], doc["choices"], only=old["resource_id"])
    assert next(i for i in current["items"] if i["resource_id"] == old["resource_id"])["decision"] == "retain"
    done = await apply(daemon, doc)
    assert done["status"] == "succeeded", done
    row = next(r for r in cleanup.receipts(daemon.ops, done["operation_id"]) if r["resource_id"] == old["resource_id"])
    assert row["status"] == "retained"

    # Audit private read entry points too: no runner/client lookup on a removed host.
    before = len(called)
    runner = daemon.ops.context["git_runner"]
    original_available = runner.available

    def configured_runner(host):
        assert host in daemon.fleet.config.hosts
        return original_available(host)

    monkeypatch.setattr(runner, "available", configured_runner)
    with pytest.raises(OperationError, match="OBSERVATION_UNAVAILABLE"):
        await cleanup._host_call(daemon.ops, "h2", {})
    assert (await cleanup._terminal_observations(daemon.ops, "h2", time.monotonic() + 1))[0]["error"] == "OBSERVATION_UNAVAILABLE"
    assert (await cleanup._runtime(daemon.ops, old, time.monotonic() + 1))["error"] == "OBSERVATION_UNAVAILABLE"
    cleanup.guard("h2", session_id=historical["session_id"], path=historical["worktree_path"])
    assert len(called) == before

    # Real pins from the healthy apply stay listed as unavailable when that host is later removed too.
    daemon.fleet.config.hosts.pop("h1")
    refs = await cleanup.retained(daemon.ops)
    assert refs["unavailable"] and not refs["retained"]
    assert all(r["reason"] == "OBSERVATION_UNAVAILABLE" for r in refs["unavailable"])
    assert len(called) == before
