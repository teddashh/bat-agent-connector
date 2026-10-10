"""B01/B03, 計畫 §08/§10/§11/§16: project merged delivery facts without inferring local resources."""

import json

import pytest

from bat_agent_connector import pr_delivery
from bat_agent_connector.observation import Observation, remember, worktree
from tests import test_delivery as delivery_tests

gh = delivery_tests.gh
make_daemon = delivery_tests.make_daemon


@pytest.mark.parametrize("binding", ["session", "worktree", None])
async def test_b01_b03_delivered_merge_history_uses_only_explicit_refs(make_daemon, gh, binding):
    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD, body="private PR body")
    gh.pulls[7]["title"] = "private PR title"
    with d.journal.tx():
        wid = worktree(d.journal, "h1", "registry", "source@123", "worktree", path="/srv/worktree",
                       session_id="source" if binding == "session" else None)
    remember(d.ops.db, "session", "h1/source", host="h1", session_id="source")
    op, _ = await delivery_tests.merge_op(d)
    preview_id = op["params"]["preview_id"]
    preview = pr_delivery.get_preview(d.ops.db, preview_id)
    # Re-reading an unchanged saved preview does not append an event per read.
    head = d.journal.api_head()
    document = {k: v for k, v in preview.items() if k not in {"preview_id", "digest", "created_at", "expires_at"}}
    assert pr_delivery.save_preview(d.ops, document)["preview_id"] == preview_id
    assert d.journal.api_head() == head
    if binding:
        d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id" if binding == "session" else "worktree_id": "source" if binding == "session" else wid})
    done = await delivery_tests.settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    obs = Observation(d.journal)
    session = obs.history("session", "h1/source", limit=200)["events"]
    events = obs.history("worktree", wid, limit=200)["events"]
    if binding is None:
        assert not session and not events
        assert not d.ops.db.execute("""SELECT 1 FROM api_event_resources r JOIN api_events e USING(seq)
            WHERE e.resource_type='operation' AND e.resource_id=?""", (op["operation_id"],)).fetchall()
    else:
        if binding == "worktree":
            assert not session
        else:
            assert {e["seq"] for e in session} == {e["seq"] for e in events}
        assert len(events) == len({e["seq"] for e in events})
        verified = next(e for e in events if e["kind"] == "operation.step.succeeded" and e["body"]["step"] == "merge.verify")
        assert verified["body"]["response"]["verified"] is True
        assert verified["body"]["response"]["merged_sha"] == delivery_tests.MERGED
        assert verified["context"]["operation_id"] == op["operation_id"]
        assert verified["context"]["actor"] == delivery_tests.OPERATOR.actor
        assert delivery_tests.HEAD in {v["sha"] for v in verified["context"]["source_versions"]}
        assert delivery_tests.MERGED in {v["sha"] for v in verified["context"]["result_versions"]}
        succeeded = next(e for e in events if e["kind"] == "operation.succeeded")
        assert delivery_tests.MERGED in {v["sha"] for v in succeeded["context"]["result_versions"]}
        preview_event = next(e for e in events if e["kind"] == "delivery.merge_previewed")
        assert preview_event["resource_id"] == preview_id
        assert preview_event["body"]["target"]["number"] == 7
        assert preview_event["body"]["target"]["head_repo_id"] == preview["target"]["head_repo_id"]
        assert preview_event["body"]["files_may_be_truncated"] is False
        assert preview_event["context"]["actor"] is None
        assert preview_event["context"]["actor_basis"] == "unknown"
        assert preview_event["context"]["observer"] == "delivery-service"
        assert delivery_tests.HEAD in {v["sha"] for v in preview_event["context"]["source_versions"]}
        # Later binding indexes earlier facts without rewriting their original provenance.
        assert preview_event["context"]["session_resource_ids"] == []
    raw = " ".join(r[0] for r in d.ops.db.execute("SELECT body FROM api_events"))
    assert "private PR title" not in raw and "private PR body" not in raw
    assert "private PR title" not in json.dumps(events) and "private PR body" not in json.dumps(events)


async def test_b01_delivery_preview_late_binding_respects_history_as_of(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD)
    with d.journal.tx():
        first = d.journal.api_event("session", "h1/source", "session.added", {})
        d.journal.api_event("session", "h1/source", "session.updated", {})
    op, _ = await delivery_tests.merge_op(d)
    obs = Observation(d.journal)
    baseline = obs.history("session", "h1/source", limit=1)
    d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "source"})
    tail = obs.history("session", "h1/source", limit=1, cursor=baseline["next_cursor"])
    assert [e["seq"] for e in tail["events"]] == [first]
    assert tail["as_of"] == baseline["as_of"] and tail["next_cursor"] is None
    current = obs.history("session", "h1/source", limit=200)["events"]
    preview = next(e for e in current if e["kind"] == "delivery.merge_previewed")
    linked = d.ops.db.execute("SELECT linked_at_seq FROM api_event_resources WHERE seq=? AND resource_type='session'", (preview["seq"],)).fetchone()[0]
    assert linked > baseline["as_of"]
    d.ops.cancel(delivery_tests.OPERATOR, op["operation_id"])


async def test_b03_merge_receipt_history_keeps_moved_base_shas_without_commit_messages(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD)
    gh.merge_mode = "enqueue"
    op, _ = await delivery_tests.merge_op(d)
    d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "source"})
    assert (await delivery_tests.settle(d, op["operation_id"], 2))["status"] == "waiting_external"
    newer = "c" * 40
    gh.commits[newer] = {"sha": newer, "parents": [{"sha": "b" * 40}], "commit": {"message": "private commit message"}}
    gh.branches["main"] = newer
    gh.merge(7)
    done = await delivery_tests.settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    events = Observation(d.journal).history("session", "h1/source", limit=200)["events"]
    verified = next(e for e in events if e["kind"] == "operation.step.succeeded" and e["body"]["step"] == "merge.verify")
    receipt = verified["body"]["response"]
    assert receipt["merged_onto_base_sha"] == newer and receipt["base_moved"] is True
    assert receipt["other_commits_count"] == 1
    assert receipt["other_commits"] == [{"sha": newer, "parents": ["b" * 40]}]
    assert {v["sha"] for v in verified["context"]["result_versions"]} == {newer, delivery_tests.MERGED}
    # A later mutable refs update cannot rewrite the saved receipt's versions.
    d.ops._merge_refs(op["operation_id"], {"merged_sha": "e" * 40})
    after = next(e for e in Observation(d.journal).history("session", "h1/source", limit=200)["events"] if e["seq"] == verified["seq"])
    assert after == verified
    assert "private commit message" not in json.dumps(events)
    assert "private commit message" not in " ".join(r[0] for r in d.ops.db.execute("SELECT body FROM api_events"))


@pytest.mark.parametrize("conflict", [False, True])
async def test_b03_metadata_settlement_history_has_codes_without_pr_text(make_daemon, gh, conflict):
    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD, body="private original body")
    gh.pulls[7]["title"] = "private original title"
    gh.patch_mode = "lost_before"
    op = await delivery_tests.update_op(d, params={"title": "private intended title", "body": "private intended body"})
    d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "source"})
    unknown = await delivery_tests.settle(d, op["operation_id"])
    assert unknown["status"] == "needs_attention" and unknown["error_code"] == "UNCERTAIN_UNRESOLVED"
    if conflict:
        gh.pulls[7].update(title="private third title", body="private third body")
    d.ops.db.execute("UPDATE operation_steps SET started_at=? WHERE operation_id=? AND name='pr.metadata.write'",
                     (pr_delivery.time.time() - pr_delivery.METADATA_SETTLE_S - 1, op["operation_id"]))
    await pr_delivery.reconcile_metadata(d.ops)
    head = d.journal.api_head()
    await pr_delivery.reconcile_metadata(d.ops)
    assert d.journal.api_head() == head and gh.count("PATCH", ".") == 1
    events = Observation(d.journal).history("session", "h1/source", limit=200)["events"]
    settled = [e for e in events if e["kind"] == "delivery.metadata_settled"]
    assert len(settled) == 1
    event = settled[0]
    assert event["body"]["status"] == ("conflict" if conflict else "not_applied")
    assert event["body"]["code"] == ("PR_METADATA_CONFLICT" if conflict else "PR_METADATA_NOT_APPLIED")
    assert event["context"]["operation_id"] == op["operation_id"]
    assert event["context"]["observer"] == "delivery-service"
    assert event["context"]["actor"] is None and event["context"]["actor_basis"] == "unknown"
    assert "private" not in json.dumps(events)
    assert "private" not in " ".join(r[0] for r in d.ops.db.execute("SELECT body FROM api_events"))


@pytest.mark.parametrize("backfilled", [False, True])
async def test_b03_acknowledged_conflict_settlement_is_in_history_without_pr_text(make_daemon, gh, backfilled):
    """B03/C07, §08/§10/§11/§15: ACK conflicts share first-insert history and the legacy backfill path."""
    from bat_agent_connector.task_journal import LATEST_DATA_STEP, Journal

    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD, body="private original body")
    gh.pulls[7]["title"] = "private original title"
    op = await delivery_tests.update_op(d, params={"title": "private intended title", "body": "private intended body"})
    d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "source"})
    gh.patch_after = lambda pr: pr.update(title="private concurrent title", body="private concurrent body")
    done = await delivery_tests.settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "PR_METADATA_CONFLICT"
    assert done["external_refs"]["write_acknowledged"] is True
    assert done["external_refs"]["verification_pending"] is False
    receipt = pr_delivery.metadata_settlement(d.ops, op["operation_id"])
    assert receipt["observed"] == {"title": "private concurrent title", "body": "private concurrent body"}
    original_row = tuple(d.ops.db.execute("SELECT * FROM pr_metadata_settlements WHERE operation_id=?", (op["operation_id"],)).fetchone())
    head, changes = d.journal.api_head(), d.ops.db.total_changes
    # A repeated insert cannot replace the conclusion or append another event.
    assert pr_delivery.save_metadata_settlement(d.ops, op["operation_id"], {**receipt, "status": "not_applied"}) == receipt
    assert d.journal.api_head() == head and d.ops.db.total_changes == changes
    await pr_delivery.reconcile_metadata(d.ops)
    assert d.journal.api_head() == head and gh.count("PATCH", ".") == 1
    journal = d.journal
    if backfilled:
        # Main's legacy journal has the raw ACK receipt but no observation settlement event.
        journal.db.execute("DELETE FROM api_events WHERE resource_type='operation' AND resource_id=? AND kind='delivery.metadata_settled'", (op["operation_id"],))
        journal.db.execute("PRAGMA user_version=1")
        path = journal.path
        journal.close()
        journal = Journal(path)
        assert journal.db.execute("PRAGMA user_version").fetchone()[0] == LATEST_DATA_STEP
        assert tuple(journal.db.execute("SELECT * FROM pr_metadata_settlements WHERE operation_id=?", (op["operation_id"],)).fetchone()) == original_row
        assert journal.db.execute("SELECT status FROM operations WHERE operation_id=?", (op["operation_id"],)).fetchone()[0] == "needs_attention"
        events = journal.api_events(kind="history.backfilled", related_resource_type="session", related_resource_id="h1/source")["events"]
        settled = [e for e in events if e["body"]["source_table"] == "pr_metadata_settlements"]
        assert settled[0]["body"]["saved_snapshot"]["code"] == "PR_METADATA_CONFLICT"
        assert settled[0]["body"]["saved_snapshot"]["status"] == "conflict"
        # ISO timestamps have microsecond precision; the raw receipt equality above stays exact.
        assert settled[0]["context"]["occurred_at_epoch"] == pytest.approx(receipt["settled_at"], rel=0, abs=1e-6)
        assert not any(e["kind"] == "history.backfilled" for e in journal.api_events()["events"])
    else:
        events = journal.api_events(resource_type="operation", resource_id=op["operation_id"])["events"]
        settled = [e for e in events if e["kind"] == "delivery.metadata_settled"]
        assert settled[0]["body"]["code"] == "PR_METADATA_CONFLICT"
        assert settled[0]["body"]["status"] == "conflict"
    assert len(settled) == 1
    event = settled[0]
    assert event["context"]["operation_id"] == op["operation_id"]
    assert event["context"]["observer"] == "delivery-service"
    assert event["context"]["actor"] is None and event["context"]["actor_basis"] == "unknown"
    assert "private" not in json.dumps(events)
    history = Observation(journal).history("session", "h1/source", limit=200)["events"]
    assert event["seq"] in {e["seq"] for e in history}
    assert "private" not in json.dumps(history)
    assert any(e["body"].get("refs", {}).get("write_acknowledged") is True for e in history)
    if backfilled:
        head = journal.api_head()
        journal.close()
        journal = Journal(path)
        assert journal.api_head() == head and journal.db.total_changes == 0
        journal.close()


async def test_b03_delivery_snapshot_backfill_preserves_version_chain_and_private_text(make_daemon, gh, monkeypatch):
    from bat_agent_connector import observation
    from bat_agent_connector.task_journal import LATEST_DATA_STEP, Journal

    d = make_daemon()
    gh.add_pr(7, delivery_tests.HEAD, body="private body")
    gh.pulls[7]["title"] = "private title"
    op, _ = await delivery_tests.merge_op(d)
    d.ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "source"})
    assert (await delivery_tests.settle(d, op["operation_id"]))["status"] == "succeeded"
    # Simulate main's version-1 journal, already containing delivery tables and saved facts.
    d.ops.db.execute("DELETE FROM api_events WHERE kind='delivery.merge_previewed'")
    receipt = {"status": "not_applied", "code": "PR_METADATA_NOT_APPLIED", "observed": {"title": "private title", "body": "private body"}, "settled_at": 124}
    d.ops.db.execute("INSERT INTO pr_metadata_settlements VALUES(?,?)", (op["operation_id"], json.dumps(receipt)))
    d.ops.db.execute("PRAGMA user_version=1")
    snapshots = {table: [tuple(r) for r in d.ops.db.execute(f"SELECT * FROM {table}")] for table in ("pr_merge_previews", "pr_metadata_settlements", "pr_merge_scope_reads")}
    path = d.journal.path
    d.journal.close()
    calls, original = [], observation.backfill

    def capture(journal):
        calls.append(journal.db.execute("PRAGMA user_version").fetchone()[0])
        original(journal)

    monkeypatch.setattr(observation, "backfill", capture)
    j = Journal(path)
    assert calls == [1] and j.db.execute("PRAGMA user_version").fetchone()[0] == LATEST_DATA_STEP
    events = Observation(j).history("session", "h1/source", limit=200)["events"]
    facts = [e for e in j.api_events(kind="history.backfilled", limit=500)["events"] if e["body"]["source_table"] in snapshots]
    assert {e["body"]["source_table"] for e in facts} == {"pr_merge_previews", "pr_metadata_settlements"}
    # Both saved facts predate the operation's session binding; the later link cannot rewrite their scope.
    assert {e["seq"] for e in facts}.isdisjoint(e["seq"] for e in events)
    assert all(e["context"]["session_resource_ids"] == [] for e in facts)
    settlement = next(e for e in facts if e["body"]["source_table"] == "pr_metadata_settlements")
    assert settlement["context"]["operation_id"] == op["operation_id"]
    assert settlement["context"]["occurred_at_epoch"] == 124
    assert all(e["context"]["observer"] == "delivery-service" and e["context"]["actor"] is None for e in facts)
    assert "private" not in json.dumps(events)
    assert "private" not in json.dumps(facts)
    head, changes = j.api_head(), j.db.total_changes
    original(j)  # Idempotent source keys also prevent duplication if interrupted work is retried.
    assert j.api_head() == head and j.db.total_changes == changes
    j.close()
    j = Journal(path)
    assert calls == [1] and j.api_head() == head and j.db.total_changes == 0
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == LATEST_DATA_STEP
    for table, rows in snapshots.items():
        assert [tuple(r) for r in j.db.execute(f"SELECT * FROM {table}")] == rows
    j.close()
