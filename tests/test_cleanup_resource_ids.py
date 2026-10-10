"""Observation and cleanup share registry creation IDs; paths never prove ownership."""

import copy
import json

import pytest

from bat_agent_connector import api_auth, cleanup, observation, registry
from bat_agent_connector.resource_ids import worktree_id
from tests.test_cleanup import daemon as cleanup_daemon
from tests.test_cleanup import human as cleanup_human

daemon = cleanup_daemon
human = cleanup_human


def entries(d, relationship):
    clone = d.fleet.config.host("h1").managed_roots[0] + "/standalone"
    path = clone + "/.bat-worktrees/root"
    root = {"host": "h1", "session_id": "root", "created_at": "123.4560", "status": "active",
            "worktree_path": path, "cwd": path, "origin_root": clone, "branch": "bat/worktree-root"}
    middle = {**root, "session_id": "middle", "created_at": 124, "failover_of": "root"}
    child = {**root, "session_id": "child", "created_at": 125}
    child.update({"failover_of": "middle"} if relationship == "failover" else
                 {"shares_worktree_with": "middle"} if relationship == "shared" else
                 {"role": "reviewer", "lead_session_id": "middle"})
    return [root, middle, child]


@pytest.mark.parametrize("relationship", ["failover", "shared", "reviewer"])
@pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 2, 0)])
def test_cleanup_uses_observation_creation_root_independent_of_registry_order(daemon, monkeypatch, relationship, order):
    original = entries(daemon, relationship)
    rows = [original[index] for index in order]
    before = copy.deepcopy(rows)
    monkeypatch.setattr(registry, "list_entries", lambda: rows)
    items, _, _, worktrees, _, _ = cleanup._all(daemon.ops)
    expected = worktree_id("h1", "registry", "root@123.4560", "worktree")
    assert {item["resource_id"] for item in worktrees.values()} == {expected}
    assert all(item["worktree_id"] == expected for item in items.values() if item["kind"] == "session")
    assert next(iter(worktrees.values()))["proven"] is True
    observation.registry_bindings(daemon.journal, "h1", rows)
    observed = [observation.body(r[0])["worktree_id"] for r in daemon.journal.db.execute(
        "SELECT body FROM observation_resources WHERE resource_type='session'")]
    assert observed and set(observed) == {expected}
    assert rows == before


@pytest.mark.parametrize("maker", ["worktree_made_by", "checkpoint_id", "integration_operation_id", "legacy_branch"])
def test_cleanup_never_claims_connector_made_registry_carrier_as_bat(daemon, monkeypatch, maker):
    rows = entries(daemon, "failover")
    if maker == "legacy_branch":
        rows[0]["branch"] = "batc/cp-legacy"
    else:
        rows[0][maker] = "connector" if maker == "worktree_made_by" else "known-creation"
    monkeypatch.setattr(registry, "list_entries", lambda: list(reversed(rows)))
    _, _, _, worktrees, _, _ = cleanup._all(daemon.ops)
    assert not any(item["flavor"] == "bat" for item in worktrees.values())


async def test_cleaned_session_document_stays_shared_and_read_only_after_host_removal(daemon, mock):
    db = daemon.journal.db
    doc = {"resource_id": "cr_cleaned", "kind": "session", "host": "removed-host",
           "original_ids": ["removed-host/old-session"], "path": "/old/location"}
    with daemon.journal.tx():
        db.execute("INSERT INTO resource_tombstones VALUES(?,?,?,?,?,?)",
                   (doc["resource_id"], "generation", doc["host"], "session", json.dumps(doc), 1))
        db.execute("INSERT INTO cleanup_aliases VALUES(?,?,?,?)",
                   ("session", "removed-host/old-session", doc["host"], doc["resource_id"]))
    before, calls = list(db.iterdump()), copy.deepcopy(mock.invokes)
    shared = daemon.inventory.session_document("removed-host", "old-session")
    reader = api_auth.Principal("reader", frozenset({"observe"}))
    status, http = await daemon.api.session(query={}, host="removed-host", sid="old-session", principal=reader)
    assert status == 200 and http == shared
    assert shared["session"] is None and shared["cleanup"] == [doc]
    assert shared["relations_summary"] == []
    assert list(db.iterdump()) == before and mock.invokes == calls
