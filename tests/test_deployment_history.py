"""Delivery/observation integration: append-only saved facts and step 1→2→3."""
import json

import pytest

from bat_agent_connector import deployment_store as store
from bat_agent_connector.observation import Observation
from bat_agent_connector.task_journal import LATEST_DATA_STEP, Journal
from tests.test_deployment_config import legacy_operations


def prepare(j):
    ops = legacy_operations(j)
    j.db.execute("UPDATE operations SET target=? WHERE operation_id=?",
                 (json.dumps({"recipe": "prod", "host": "h1", "session_id": "source"}), ops[0]["operation_id"]))
    j.db.execute("PRAGMA user_version=2")
    store.backfill(j)
    return store.deployment(j.db, operation_id=ops[0]["operation_id"])


def test_upgrade_runs_observation_before_delivery_and_never_rewrites_existing_events(tmp_path):
    path = tmp_path / "upgrade.db"
    j = Journal(path)
    legacy_operations(j)
    original = [tuple(r) for r in j.db.execute("SELECT * FROM api_events ORDER BY seq")]
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == LATEST_DATA_STEP == 3
    assert [tuple(r) for r in j.db.execute("SELECT * FROM api_events ORDER BY seq")][:len(original)] == original
    rows = j.db.execute("SELECT e.seq,c.context FROM api_events e JOIN api_event_context c ON e.seq=c.seq "
                        "WHERE e.kind='deployment.backfilled'").fetchall()
    assert len(rows) == 2
    assert all(json.loads(r["context"])["occurred_at"] is None for r in rows)
    assert all(json.loads(r["context"])["operation_id"] for r in rows)
    head = j.api_head()
    j.close()
    j = Journal(path)
    assert j.api_head() == head
    j.close()


def test_deployment_changes_are_indexed_without_verifier_bodies_or_configuration(tmp_path):
    j = Journal(tmp_path / "history.db")
    dep = prepare(j)
    head = j.api_head()
    facts = {"verified": False, "error_code": "DEPLOY_VERSION_MISMATCH",
             "html_url": "https://github.com/example/repository/actions/runs/12?token=private-query#private-fragment",
             "evidence": {"runtime": {"authorization": "private-authorization", "body": "private-body"}},
             "diagnostic": "private-diagnostic"}
    assert store.update(j, dep["deployment_id"], state="needs_attention", facts=facts)
    updates = [e for e in j.api_events(head)["events"] if e["kind"] == "deployment.updated"]
    assert len(updates) == 1
    event = updates[0]
    assert event["body"]["source_sha"] == "a" * 40
    assert event["body"]["provider_url"] == "https://github.com/example/repository/actions/runs/12"
    assert event["body"]["operation_id"] == dep["operation_id"]
    assert not any(value in json.dumps(event) for value in ("private-query", "private-fragment", "private-body",
                                                          "private-authorization", "private-diagnostic"))
    history = Observation(j).history("session", "h1/source")["events"]
    saved = next(e for e in history if e["seq"] == event["seq"])
    assert saved["body"]["deployment_id"] == dep["deployment_id"]
    assert saved["body"]["state"] == "needs_attention"
    assert saved["body"]["source_sha"] == "a" * 40
    head = j.api_head()
    assert store.update(j, dep["deployment_id"], state="needs_attention", facts=facts)
    assert j.api_head() == head  # identical reconciliation creates no duplicate fact
    j.close()


def test_deployment_fact_and_state_roll_back_together(tmp_path):
    j = Journal(tmp_path / "rollback.db")
    dep = prepare(j)
    head = j.api_head()
    with pytest.raises(RuntimeError):
        with j.tx():
            store.update(j, dep["deployment_id"], state="failed")
            raise RuntimeError("fixture rollback")
    assert j.api_head() == head
    assert store.deployment(j.db, deployment_id=dep["deployment_id"])["state"] == dep["state"]
    j.close()
