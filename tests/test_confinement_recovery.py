"""A10 review regressions: distinguish unsent refusals from acknowledged and unsettled starts."""

from __future__ import annotations

import json

import pytest

from bat_agent_connector import confinement, lifecycle, orchestrate, registry, task_bat
from bat_agent_connector.errors import InvokeError
from bat_agent_connector.task_core import TaskCoordinator
from bat_agent_connector.task_journal import Journal
from bat_agent_connector.task_verifier import ObservedVerifier, VerificationSettings
from tests.conftest import adopt
from tests.test_confinement import ACCOUNT, MANAGED, AccountRunner
from tests.test_lifecycle import _add_wt_claude
from tests.test_task_service import FakeBAT, submit


class RefuseAtFrame(AccountRunner):
    async def run(self, host, script, timeout_s=None):
        self.scripts.append(script)
        return json.dumps({"status": "verified" if len(self.scripts) == 1 else "unknown",
                           "reason": "fixture_identity_unreadable"})


def reviewer_adapter(fleet, mock, journal, monkeypatch):
    lead = _add_wt_claude(mock)
    registry.update("h1", lead, workspace_name="demo-project")
    task = journal.submit(project="p", host="h1", workspace="demo-project", original_words="Review fixture",
                          idempotency_key="review-fixture")
    journal.add_branch(task["task_id"], session_id=lead, provider="claude", role="lead", reason="start")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), journal)

    async def present(*args, **kwargs):
        return "present"

    monkeypatch.setattr(adapter, "session_presence", present)
    return adapter, {**task, "session_id": lead}


@pytest.mark.parametrize("path", ["start", "failover", "reviewer"])
@pytest.mark.parametrize("retain", [False, True])
async def test_host_account_refusal_before_frame_releases_start(
        fleet_factory, mock, tmp_path, monkeypatch, path, retain):
    f = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, default_permission_mode="confined",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    f.confinement_runner = RefuseAtFrame()
    journal = Journal(tmp_path / "tasks.db")
    try:
        with pytest.raises(confinement.ConfinementRefused, match="HOST_ACCOUNT_UNVERIFIED") as error:
            if path == "start":
                await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True,
                                                retain_on_error=retain)
            elif path == "failover":
                lead = _add_wt_claude(mock)
                await lifecycle.session_failover(f, "h1", lead, confirm=True)
            else:
                adapter, task = reviewer_adapter(f, mock, journal, monkeypatch)
                await adapter.start(task, role="reviewer", agent="codex", session_id="review-refused")
        assert error.value.sent is False
        assert "claude:start-session" not in mock.channels()
        entry = registry.list_entries("h1")[-1]
        assert entry["status"] == "failed" and entry["start_sent"] is False
        assert not entry.get("start_uncertain")
        assert len(f.confinement_runner.scripts) == 2  # admission, then frame; never retried
        if path == "start":
            assert ("worktree:remove" in mock.channels()) is not retain
        if path == "reviewer":
            assert not any(i["channel"] == "claude:get-session-meta" and
                           i["params"]["sessionId"] == "review-refused" for i in mock.invokes)
    finally:
        await f.close()
        journal.close()


@pytest.mark.parametrize("role", ["lead", "reviewer"])
async def test_task_start_refused_before_frame_needs_ted_not_uncertain(tmp_path, role):
    class RefusedBAT(FakeBAT):
        async def start(self, *args, **kwargs):
            raise confinement.ConfinementRefused("HOST_ACCOUNT_UNVERIFIED", "fixture", sent=False)

    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    try:
        result = await TaskCoordinator(journal, RefusedBAT())._start(task, role=role)
        assert result["state"] == "needs_ted"
        command = journal.commands(task["task_id"])[0]
        assert command["kind"] == "start_" + role and command["status"] == "rejected"
        event = next(e for e in journal.events(task["task_id"]) if e["kind"] == "start_rejected")
        assert json.loads(event["body"])["code"] == "HOST_ACCOUNT_UNVERIFIED"
        assert not any('"to": "uncertain"' in e["body"] for e in journal.events(task["task_id"]))
    finally:
        journal.close()


@pytest.mark.parametrize("path", ["start", "failover"])
async def test_general_start_unreadable_meta_records_unknown_and_keeps_session(fleet_factory, mock, path):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="allow_all",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    lead = _add_wt_claude(mock) if path == "failover" else None
    client = f.client("h1")
    invoke = client.invoke

    async def unreadable(channel, params=None, **kwargs):
        if channel == "claude:get-session-meta" and params["sessionId"] != lead:
            raise InvokeError("fixture metadata unavailable")
        return await invoke(channel, params, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(client, "invoke", unreadable)
    try:
        result = (await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
                  if path == "start" else await lifecycle.session_failover(f, "h1", lead, confirm=True))
        sid = result.get("session_id") or result["new_session_id"]
        entry = registry.get("h1", sid)
        assert entry["status"] == "active" and entry["confinement"]["verification"]["status"] == "unknown"
        assert entry["confinement"]["level"] == "none"
        assert "worktree:remove" not in mock.channels()
    finally:
        monkeypatch.undo()
        await f.close()


@pytest.mark.parametrize("path", ["start", "failover"])
@pytest.mark.parametrize("confined", [False, True])
async def test_post_start_mismatch_keeps_reservation_and_worktree(fleet_factory, mock, path, confined):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="confined" if confined else "allow_all",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    lead = _add_wt_claude(mock) if path == "failover" else None
    client = f.client("h1")
    invoke = client.invoke

    async def drift(channel, params=None, **kwargs):
        result = await invoke(channel, params, **kwargs)
        if channel == "claude:start-session":
            meta = mock.metas[params["sessionId"]]
            meta.update({"permissionMode": "plan"} if path == "start" else {"codexSandboxMode": "read-only"})
        return result

    client.invoke = drift
    try:
        with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_MISMATCH"):
            if path == "start":
                await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
            else:
                await lifecycle.session_failover(f, "h1", lead, confirm=True)
        entry = registry.list_entries("h1")[-1]
        assert entry["status"] == "uncertain" and entry["error_code"] == "CONFINEMENT_MISMATCH"
        assert entry["confinement"]["verification"]["status"] == "mismatch"
        assert entry.get("worktree_path") and entry["session_id"] in mock.metas
        assert "worktree:remove" not in mock.channels() and "claude:send-message" not in mock.channels()
    finally:
        await f.close()


async def test_reviewer_start_meta_failure_still_activates(fleet_factory, mock, tmp_path, monkeypatch):
    f = fleet_factory(writes=True, orchestrate=True, **MANAGED)
    journal = Journal(tmp_path / "tasks.db")
    adapter, task = reviewer_adapter(f, mock, journal, monkeypatch)
    client = f.client("h1")
    invoke = client.invoke

    async def unreadable(channel, params=None, **kwargs):
        if channel == "claude:get-session-meta" and params["sessionId"] == "review-unreadable":
            raise InvokeError("fixture metadata unavailable")
        return await invoke(channel, params, **kwargs)

    monkeypatch.setattr(client, "invoke", unreadable)
    try:
        sid = await adapter.start(task, role="reviewer", agent="codex", session_id="review-unreadable")
        entry = registry.get("h1", sid)
        assert entry["status"] == "active"
        assert entry["confinement"]["verification"] == {
            "status": "unknown", "reason": "session_unloaded", "observed_options": {}}
        assert mock.channels().count("claude:start-session") == 1
    finally:
        await f.close()
        journal.close()


async def test_legacy_codex_predecessor_uses_its_recorded_agent(fleet_factory):
    f = fleet_factory(writes=True, default_permission_mode="allow_all", **MANAGED)
    adopt("legacy-codex", agent_preset="codex-agent", write_scope="confined",
          agent_params={"sandboxMode": "read-only", "approvalPolicy": "never"})
    try:
        options, scope, _ = await confinement.start_decision(
            f, "h1", "codex", confined=True, predecessor=registry.get("h1", "legacy-codex"))
        assert options == {"codexSandboxMode": "read-only", "codexApprovalPolicy": "never"}
        assert scope == "confined"
    finally:
        await f.close()


@pytest.mark.parametrize("outcome", ["confirmed", "mismatch", "unreadable", "null"])
async def test_confined_failover_unsettled_successor_reads_back_before_new_attempt(fleet_factory, mock, outcome):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="confined",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    lead = _add_wt_claude(mock)
    options = confinement.CONFINED_OPTIONS["codex"]
    previous = registry.get("h1", lead)
    registry.reserve("h1", {**previous, "session_id": "unsettled-successor", "failover_of": lead,
                            "agent_preset": "codex-agent-worktree", "write_scope": "confined",
                            "confinement": confinement.snapshot("codex", options), "start_uncertain": True}, 4)
    if outcome in {"confirmed", "mismatch"}:
        mock.metas["unsettled-successor"] = {"cwd": previous["cwd"], **options}
        if outcome == "mismatch":
            mock.metas["unsettled-successor"]["codexSandboxMode"] = "danger-full-access"
    elif outcome == "unreadable":
        invoke = f.client("h1").invoke

        async def unreadable(channel, params=None, **kwargs):
            if channel == "claude:get-session-meta" and params["sessionId"] == "unsettled-successor":
                raise InvokeError("fixture metadata unavailable")
            return await invoke(channel, params, **kwargs)

        f.client("h1").invoke = unreadable
    try:
        if outcome == "confirmed":
            result = await lifecycle.session_failover(f, "h1", lead, confirm=True)
            assert result["new_session_id"] == "unsettled-successor" and result["skipped"]
            entry = registry.get("h1", "unsettled-successor")
            assert entry["status"] == "active" and not entry["start_uncertain"]
            assert entry["confinement"]["verification"]["status"] == "options_confirmed"
        else:
            code = "CONFINEMENT_MISMATCH" if outcome == "mismatch" else "CONFINEMENT_START_UNSETTLED"
            with pytest.raises(confinement.ConfinementRefused, match=code):
                await lifecycle.session_failover(f, "h1", lead, confirm=True)
            assert registry.get("h1", "unsettled-successor")["start_uncertain"]
        assert "claude:start-session" not in mock.channels()
    finally:
        await f.close()
