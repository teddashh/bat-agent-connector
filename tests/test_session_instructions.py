from __future__ import annotations

import json

import pytest

from bat_agent_connector import api_auth, session_instructions
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config

PERSON = api_auth.Principal("viewer", frozenset({"observe"}))


@pytest.fixture
async def daemon(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock), tmp_path / "journal" / "tasks.sqlite3")
    daemon.acquire_owner()
    try:
        yield daemon
    finally:
        await daemon.artifact_store.close_reaper()
        await daemon.api.session_observation.close()
        await daemon.inventory.close()
        await daemon.fleet.close()
        daemon.journal.close()


def record(d, index, status="accepted", *, sid="exact", target=None, refs=None, result=None):
    oid = "op_" + f"{index:032x}"
    d.ops.db.execute("""INSERT INTO operations(operation_id,actor,entry,idem_key,request_hash,action,target,
        params,preconditions,status,created_at,updated_at,external_refs,result) VALUES(?,?,'fixture',?,?,
        'session.send',?,'{"text":"<script>data only</script>","queue":true}','{}',?,100,100,?,?)""",
        (oid, "sender", str(index), str(index), json.dumps(target or {"host": "h1", "session_id": sid}), status,
         json.dumps(refs or {}), json.dumps(result) if result is not None else None))
    return oid


def test_historical_queue_receipt_never_claims_live_position_or_revocation(daemon):
    accepted = record(daemon, 1, "succeeded", result={"accepted": True, "queued": True, "message_id": "same-message"})
    uncertain = record(daemon, 2, "uncertain")
    pending = record(daemon, 3)
    cancelled = record(daemon, 4, "cancelled")
    rows = {row["operation_id"]: row for row in session_instructions.read(daemon.ops, PERSON, "h1", "exact")["instructions"]}
    assert rows[accepted]["phase"] == "accepted" and rows[accepted]["was_queued"] is True
    assert rows[uncertain]["phase"] == "unconfirmed" and rows[uncertain]["accepted"] is None
    assert rows[pending]["phase"] == "pending" and rows[pending]["was_queued"] is None
    assert rows[cancelled]["phase"] == "operation_cancelled" and rows[cancelled]["accepted"] is None
    assert all(row["queue_position"] is None and not row["per_message_cancel"] for row in rows.values())
    assert rows[accepted]["text_excerpt"] == "<script>data only</script>"
    assert "idempotency_key" not in rows[accepted]


def test_exact_bound_session_and_tied_timestamp_pagination(daemon):
    wanted = [record(daemon, n) for n in range(1, 5)]
    record(daemon, 5, sid="different")
    resolved = record(daemon, 6, target={"host": "h1", "session_id": "legacy-short-name"},
                      refs={"resolved_target": {"host": "h1", "session_id": "exact"}})
    record(daemon, 7, refs={"resolved_target": {"host": "h1", "session_id": "different"}})
    first = session_instructions.read(daemon.ops, PERSON, "h1", "exact", limit=2)
    all_rows, cursor = first["instructions"], first["next_cursor"]
    # A new newer row never shifts the older-page boundary or duplicates a row.
    record(daemon, 8)
    while cursor:
        page = session_instructions.read(daemon.ops, PERSON, "h1", "exact", limit=2, cursor=cursor)
        all_rows += page["instructions"]
        cursor = page["next_cursor"]
    assert [row["operation_id"] for row in all_rows] == [resolved, *reversed(wanted)]
    with pytest.raises(OperationError, match="INVALID_CURSOR"):
        session_instructions.read(daemon.ops, PERSON, "h1", "different", cursor=first["next_cursor"])
    with pytest.raises(OperationError, match="FORBIDDEN"):
        session_instructions.read(daemon.ops, api_auth.Principal("none", frozenset()), "h1", "exact")


def test_committed_send_step_is_preserved_before_outer_operation_settles(daemon):
    oid = record(daemon, 1, "running")
    daemon.ops._step_start(oid, "send", {"message_id": "fixed-marker"})
    daemon.ops._step_done(oid, "send", {"accepted": True, "queued": False})
    row = session_instructions.read(daemon.ops, PERSON, "h1", "exact")["instructions"][0]
    assert row["phase"] == "accepted" and row["operation_status"] == "running"
    assert row["message_id"] == "fixed-marker" and row["receipt_recorded_at"] is not None
