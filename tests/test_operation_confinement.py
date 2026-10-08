"""A10: an operator attention boundary never implies an external call can be repeated."""

import pytest

from bat_agent_connector.api_auth import Principal
from bat_agent_connector.operations import RERUN, ActionDef, NeedsAttention, OperationService
from bat_agent_connector.task_journal import Journal
from tests.operation_helpers import settle_operations


@pytest.mark.parametrize("recovery", ["none", "unknown", "rerun", "result"])
async def test_needs_attention_step_resumes_only_with_reconciliation_proof(tmp_path, recovery):
    calls = 0
    reads = 0

    async def effect():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise NeedsAttention("FIXTURE_ATTENTION", "check the reserved effect before continuing")
        return {"confirmed": "new"}

    async def reconcile(request):
        nonlocal reads
        reads += 1
        assert request == {"reserved_id": "same-id"}
        return {"unknown": None, "rerun": RERUN, "result": {"confirmed": "existing"}}[recovery]

    async def run(ctx):
        return await ctx.step("external", effect, request={"reserved_id": "same-id"},
                              reconcile=None if recovery == "none" else reconcile)

    journal = Journal(tmp_path / "operations.db")
    principal = Principal("fixture", frozenset({"operate"}))
    try:
        ops = OperationService(journal, actions=[ActionDef("fixture", "operate", "test", run)])
        op, _ = ops.create(principal, action="fixture", idempotency_key="original-intent")
        op_id = op["operation_id"]
        await settle_operations(ops)
        first = ops.get(op_id)
        assert first["status"] == "needs_attention" and first["error_code"] == "FIXTURE_ATTENTION"
        assert first["steps"][0]["status"] == "uncertain" and calls == 1
        journal.close()
        journal = Journal(tmp_path / "operations.db")
        ops = OperationService(journal, actions=[ActionDef("fixture", "operate", "test", run)])
        ops.resume(principal, op_id)
        await settle_operations(ops)
        result = ops.get(op_id)
        assert reads == (0 if recovery == "none" else 1)
        assert calls == (2 if recovery == "rerun" else 1)
        if recovery in {"none", "unknown"}:
            assert result["status"] == "uncertain" and result["steps"][0]["status"] == "uncertain"
        else:
            assert result["status"] == "succeeded" and result["steps"][0]["status"] == "succeeded"
            assert result["result"] == {"confirmed": "new" if recovery == "rerun" else "existing"}
    finally:
        journal.close()
