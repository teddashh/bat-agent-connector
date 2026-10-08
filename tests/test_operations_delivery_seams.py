"""A05/A07 and C05/C07: Task Service receipts preserve delivery recovery (plan §09/§10/§15)."""

import json

import pytest

from bat_agent_connector import delivery, pr_delivery
from bat_agent_connector.errors import TaskControlRefused
from bat_agent_connector.operations import OpContext, OperationError
from tests.test_delivery import (
    HEAD,
    TED,
    default_merge_op,
    restart_delivery_service,
    settle,
    update_op,
)
from tests.test_delivery import (
    gh as gh,
)
from tests.test_delivery import (
    make_daemon as make_daemon,
)


async def test_a05_c07_effect_receipts_preserve_delivery_step_replay_and_reconcile(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op = await update_op(d)
    ctx = OpContext(d.ops, d.ops._row(op["operation_id"]))
    effects = []

    def effect():
        effects.append("committed")
        return {"recorded": True}

    assert ctx.effect("task_command", effect) == {"recorded": True}
    assert not delivery._sent_write(ctx)
    with pytest.raises(OperationError, match="GITHUB_403"):
        delivery._read_result(403, {"message": "refused before any write"}, "read PR", ctx)
    assert gh.count("PATCH", ".") == 0
    gh.patch_mode = "lost_after"
    first = await settle(d, op["operation_id"], 1)
    assert first["status"] == "uncertain" and delivery._sent_write(ctx)
    assert [(s["name"], s["status"]) for s in first["steps"]] == [
        ("task_command", "succeeded"), ("pr.metadata.plan", "succeeded"), ("pr.metadata.write", "uncertain")]
    restart_delivery_service(d)
    replay = OpContext(d.ops, d.ops._row(op["operation_id"]))
    assert replay.effect("task_command", effect) == {"recorded": True}
    assert effects == ["committed"] and replay.replayed == ["task_command"]
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["observed_intent"]
    assert all(s["status"] == "succeeded" for s in done["steps"])
    assert gh.count("PATCH", ".") == 1


async def test_a05_c07_failed_nested_effect_preserves_outer_delivery_commits(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.add_pr(8, "c" * 40)
    outer_op = await update_op(d)
    card = await delivery.pr_preview(d.ops, "o/r", 8)
    inner_op, _ = d.ops.create(TED, action="github.pr.update", target={"repository": "o/r", "pull_number": 8},
                               params={"title": "Inner change"}, idempotency_key="inner",
                               preconditions={"expected_metadata_digest": card["metadata_digest"]})
    document = await pr_delivery.scope(d.ops, "o/r", 7, "squash")
    ctx = OpContext(d.ops, d.ops._row(outer_op["operation_id"]))
    inner = {}

    def change_then_fail():
        inner["preview"] = pr_delivery.save_preview(d.ops, {**document, "warnings": ["inner transaction"]})
        inner["receipt"] = pr_delivery.settle_not_applied(d.ops, inner_op["operation_id"], 0,
                                                         {"title": "Original", "body": ""})
        raise TaskControlRefused("CONTROL_VERSION_CONFLICT", "control changed before the effect committed")

    with d.journal.tx():
        outer_preview = pr_delivery.save_preview(d.ops, {**document, "warnings": ["outer transaction"]})
        outer_receipt = pr_delivery.settle_not_applied(d.ops, outer_op["operation_id"], 0,
                                                      {"title": "Original", "body": ""})
        with pytest.raises(TaskControlRefused, match="CONTROL_VERSION_CONFLICT"):
            ctx.effect("task_command", change_then_fail)
        assert d.journal.db.in_transaction  # the caller still owns its outer transaction
        assert inner["receipt"]["status"] == "not_applied"
    assert not d.journal.db.in_transaction
    assert pr_delivery.get_preview(d.journal.db, outer_preview["preview_id"]) == outer_preview
    assert pr_delivery.metadata_settlement(d.ops, outer_op["operation_id"]) == outer_receipt
    assert pr_delivery.metadata_settlement(d.ops, inner_op["operation_id"]) is None
    assert not d.journal.db.execute("SELECT 1 FROM pr_merge_previews WHERE preview_id=?",
                                    (inner["preview"]["preview_id"],)).fetchone()
    assert [(s["name"], s["status"]) for s in d.ops.get(outer_op["operation_id"])["steps"]] == [
        ("task_command", "started")]
    assert gh.count("PATCH", ".") == gh.count("PUT", ".") == 0


@pytest.mark.parametrize("policy,code", [({"merge_methods": ("squash",)}, "INVALID_PARAMS"),
                                      ({"allow_merge": False}, "MERGE_DISABLED")])
async def test_c05_stopped_merge_reconcile_preserves_request_for_later_readback(make_daemon, gh, policy, code):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "fail_500"
    _, op = await default_merge_op(d)
    op_id = op["operation_id"]
    first = await settle(d, op_id, 1)
    before = next(s for s in first["steps"] if s["name"] == "merge.submit")
    assert first["status"] == before["status"] == "uncertain"
    request = d.journal.db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='merge.submit'",
                                   (op_id,)).fetchone()[0]
    restart_delivery_service(d, default_merge_method="squash", **policy)
    held = await settle(d, op_id)
    step = next(s for s in held["steps"] if s["name"] == "merge.submit")
    assert held["status"] == "needs_attention" and held["error_code"] == code
    assert step["status"] == "uncertain"
    assert d.journal.db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='merge.submit'",
                                (op_id,)).fetchone()[0] == request
    assert gh.count("PUT", ".") == 1
    gh.merge(7)  # a late outcome becomes visible while the resend policy remains revoked
    d.ops.resume(TED, op_id)
    done = await settle(d, op_id)
    step = next(s for s in done["steps"] if s["name"] == "merge.submit")
    assert done["status"] == "succeeded" and done["result"]["verified"]
    assert step["status"] == "succeeded"
    saved = d.journal.db.execute("SELECT request,response FROM operation_steps "
                                 "WHERE operation_id=? AND name='merge.submit'", (op_id,)).fetchone()
    assert saved["request"] == request and json.loads(saved["response"])["observed_only"]
    assert gh.count("PUT", ".") == 1
