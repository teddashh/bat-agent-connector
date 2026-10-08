"""A05/A07/A09: operation admission and the single Task Service authority."""

import json

import pytest

from bat_agent_connector import registry, service
from bat_agent_connector.errors import OwnerConflict
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config


def test_a09_same_fleet_different_journals_refuses_second_owner(mock, tmp_path):
    config = make_config(mock, writes=True, orchestrate=True)
    first = TaskDaemon(config, tmp_path / "first" / "tasks.db")
    second = TaskDaemon(config, tmp_path / "second" / "tasks.db")
    first.acquire_owner()
    pointer = registry.registry_path().parent / service.TASK_SERVICE_POINTER
    before = pointer.read_bytes()
    try:
        with pytest.raises(OwnerConflict) as caught:
            second.acquire_owner()
        assert caught.value.code == "OWNER_CONFLICT"
        assert caught.value.owner == json.loads(before)
        assert pointer.read_bytes() == before
        assert not second._db_path.parent.exists()  # no journal/token/provider initialization
        first.journal.db.execute("UPDATE daemon_owner SET heartbeat_at=0")
        with pytest.raises(OwnerConflict):
            second.acquire_owner()  # a stale heartbeat cannot steal a live flock
    finally:
        first.journal.close()
    second.acquire_owner()
    assert json.loads(pointer.read_text())["db_path"] == str(second._db_path.resolve())
    assert json.loads(pointer.read_text())["owner_id"] != json.loads(before)["owner_id"]
    second.journal.close()


def test_a09_restart_releases_lease_and_reuses_journal(mock, tmp_path):
    config = make_config(mock, writes=True, orchestrate=True)
    path = tmp_path / "tasks.db"
    first = TaskDaemon(config, path)
    task = first.journal.submit(project="p", host="h1", workspace="w", original_words="do it",
                                idempotency_key="original")
    first.journal.close()
    second = TaskDaemon(config, path)
    try:
        assert second.journal.get(task["task_id"])["original_words"] == "do it"
        assert second.journal.db.execute("SELECT owner_id FROM daemon_owner").fetchone()[0] == second._owner_id
    finally:
        second.journal.close()
