"""B01/B03, 計畫 §08/§11: real checkpoint writes project immutable versions and shared worktree IDs."""

from bat_agent_connector.observation import Observation
from bat_agent_connector.resource_ids import worktree_id
from tests import test_checkpoints as cp_tests

human = cp_tests.human
daemon = cp_tests.daemon


async def test_b01_b03_checkpoint_source_run_steps_and_worktree_history(daemon, mock):
    cp = await cp_tests.make_checkpoint(daemon)
    op = await cp_tests.run(daemon, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]},
                            {"instructions": "private instructions", "agent": "claude"})
    assert op["status"] == "succeeded", op
    sid = op["result"]["session_id"]
    obs = Observation(daemon.journal)
    wid = worktree_id("h1", "checkpoint.continue", op["operation_id"], "worktree")
    assert obs.resource("session", "h1/" + sid)["worktree_id"] == wid
    source = obs.history("session", "h1/" + cp_tests.MANUAL, limit=200)["events"]
    run = obs.history("session", "h1/" + sid, limit=200)["events"]
    wt = obs.history("worktree", wid, limit=200)["events"]
    for events in (source, run, wt):
        assert len(events) == len({e["seq"] for e in events})
        assert "checkpoint.continued" in {e["kind"] for e in events}
        assert any(e["kind"].startswith("operation.step.") for e in events)
    captured = next(e for e in source if e["kind"] == "checkpoint.created")
    assert captured["context"]["source_versions"][0]["sha"] == cp["commit_sha"]
    continued = next(e for e in run if e["kind"] == "checkpoint.continued")
    assert continued["context"]["actor"] == cp_tests.OPERATOR.actor
    assert continued["context"]["actor_basis"] == "authenticated_principal"
    assert continued["context"]["operation_id"] == op["operation_id"]
    assert continued["context"]["session_resource_ids"] == sorted(["h1/" + sid, "h1/" + cp_tests.MANUAL])
    assert continued["context"]["worktree_ids"] == [wid]
    assert "private instructions" not in str(run)


async def test_b01_b03_receipt_versions_are_fixed_at_the_writer_transition(daemon):
    import time
    from types import SimpleNamespace

    from bat_agent_connector import integration
    from bat_agent_connector.operations import ActionDef

    cp = await cp_tests.make_checkpoint(daemon)
    async def unused(ctx):
        return {}
    daemon.ops.register(ActionDef("fixture.receipt", "observe", "Fixture only", unused))
    op, _ = daemon.ops.create(cp_tests.OPERATOR, action="fixture.receipt", target={"host": "h1"}, idempotency_key="receipt")
    with daemon.journal.tx():
        daemon.journal.db.execute("""INSERT INTO integration_receipts(operation_id,seq,preview_id,repository,
            pull_number,head_ref,source_kind,source_id,source_host,location_class,pinned_sha,mode,source_key,status,
            actor,created_at,updated_at) VALUES(?,1,'fixture-preview','o/r',1,'feature','checkpoint',?,'h1',
            'human',?,'merge','fixture-source','pending',?,?,?)""",
            (op["operation_id"], cp["checkpoint_id"], cp["commit_sha"], cp_tests.OPERATOR.actor, time.time(), time.time()))
    ctx = SimpleNamespace(service=daemon.ops, operation_id=op["operation_id"], actor=cp_tests.OPERATOR.actor,
                          op={"external_refs": {"repository": "o/r", "pull_number": 1}})
    integration._receipt_update(ctx, 1, ("pending",), "integration.composed", status="composed", base_sha="a" * 40, integrated_sha="b" * 40)
    integration._receipt_update(ctx, 1, ("composed",), "integration.delivered", status="delivered", delivered_sha="c" * 40)
    events = Observation(daemon.journal).history("session", "h1/" + cp_tests.MANUAL, kind=["integration.composed", "integration.delivered"])["events"]
    assert len(events) == 2
    composed = next(e for e in events if e["kind"] == "integration.composed")
    delivered = next(e for e in events if e["kind"] == "integration.delivered")
    assert composed["context"]["operation_id"] == op["operation_id"]
    assert composed["context"]["source_versions"][0]["sha"] == cp["commit_sha"]
    assert {v["sha"] for v in composed["context"]["result_versions"]} == {"a" * 40, "b" * 40}
    assert "c" * 40 in {v["sha"] for v in delivered["context"]["result_versions"]}
    assert all(e["context"]["actor"] == cp_tests.OPERATOR.actor for e in events)
