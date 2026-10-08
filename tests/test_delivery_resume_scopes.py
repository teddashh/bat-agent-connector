"""C07 / Tauri v2 §18: composite resume never expands the current principal's scopes."""

from __future__ import annotations

import pytest

from bat_agent_connector import api_auth
from bat_agent_connector.operations import OperationError
from tests import test_delivery as fixtures
from tests.test_delivery import HEAD, TED, merge_op, settle

gh = fixtures.gh
make_daemon = fixtures.make_daemon


@pytest.mark.parametrize("actor", [TED.actor, "other-agent"])
@pytest.mark.parametrize("scopes", [(), ("observe",), ("merge",), ("deploy",), ("merge", "deploy")])
async def test_c07_combined_resume_requires_both_current_scopes(make_daemon, gh, actor, scopes):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = await merge_op(d, action="delivery.merge_and_deploy", recipe="prod")
    oid = op["operation_id"]
    d.ops._transition(oid, "running")
    d.ops._transition(oid, "needs_attention", reason="reviewed recovery")
    before = d.ops.get(oid)
    events = d.journal.db.execute("SELECT COUNT(*) FROM api_events").fetchone()[0]
    requests = list(gh.requests)
    caller = api_auth.Principal(actor, frozenset(scopes))

    if {"merge", "deploy"} <= set(scopes):
        assert d.ops.resume(caller, oid)["status"] == "running"
        assert d.ops.get(oid)["actor"] == TED.actor
    else:
        with pytest.raises(OperationError) as refused:
            d.ops.resume(caller, oid)
        assert refused.value.code == "FORBIDDEN" and refused.value.status == 403
        assert d.ops.get(oid) == before
        assert d.journal.db.execute("SELECT COUNT(*) FROM api_events").fetchone()[0] == events
    assert gh.requests == requests


async def test_c07_combined_resume_admin_keeps_existing_authority(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = await merge_op(d, action="delivery.merge_and_deploy", recipe="prod")
    d.ops._transition(op["operation_id"], "running")
    d.ops._transition(op["operation_id"], "needs_attention")
    admin = api_auth.Principal("local-admin", frozenset(), admin=True)
    assert d.ops.resume(admin, op["operation_id"])["status"] == "running"


async def test_c07_scope_refusal_after_merge_keeps_receipts_for_authorized_resume(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = await merge_op(d, action="delivery.merge_and_deploy", recipe="prod")
    oid = op["operation_id"]
    waiting = await settle(d, oid, 1)
    assert waiting["status"] == "waiting_external", waiting
    assert gh.count("PUT", "/merge") == 1 and gh.count("POST", "dispatches") == 1
    d.ops._transition(oid, "running")
    d.ops._transition(oid, "needs_attention", reason="operator must restore provider access")
    before = d.ops.get(oid)
    with pytest.raises(OperationError, match="FORBIDDEN"):
        d.ops.resume(api_auth.Principal(TED.actor, frozenset({"observe", "merge"})), oid)
    assert d.ops.get(oid) == before
    d.ops.resume(TED, oid)
    again = await settle(d, oid, 1)
    assert again["status"] == "waiting_external", again
    assert again["external_refs"]["merged_sha"] == before["external_refs"]["merged_sha"]
    assert gh.count("PUT", "/merge") == 1 and gh.count("POST", "dispatches") == 1
