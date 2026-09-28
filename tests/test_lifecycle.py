"""Triage, Jev (optional), permissions, quota failover and gated cleanup (mock server only)."""

from __future__ import annotations

import pytest

from bat_agent_connector import lifecycle, orchestrate, registry, triage
from bat_agent_connector.config import JevConfig
from bat_agent_connector.errors import WriteRefused
from bat_agent_connector.jev import Jev

QUOTA_MSG = (
    "You've hit your monthly spend limit · raise it at example.invalid/settings/usage · "
    "your weekly limit resets Sep 28, 4pm (America/New_York)"
)
NOW_MS = 1_790_000_000_000


def msg(i, role, text):
    return {"id": f"x{i}", "role": role, "content": text, "timestamp": NOW_MS + i * 1000}


# --------------------------------------------------------------------------- patterns
@pytest.mark.parametrize(
    "text",
    [
        QUOTA_MSG,
        "You've hit your limit · resets 5pm (UTC)",
        "Claude AI usage limit reached|1790000000",
        "Credit balance is too low",
        "Error: insufficient_quota - You exceeded your current quota",
        "5-hour limit reached ∙ resets 3am",
    ],
)
def test_quota_patterns(text):
    c = triage.classify_messages([msg(0, "user", "do it"), msg(1, "assistant", text)])
    assert c["state"] == "quota_exhausted" and c["source"] == "pattern" and c["confidence"] > 0.9
    assert c["evidence"]


def test_quota_resets_parsed():
    c = triage.classify_messages([msg(0, "user", "go"), msg(1, "assistant", QUOTA_MSG)])
    assert c["resets"].startswith("Sep 28, 4pm")
    c = triage.classify_messages([msg(0, "user", "go"), msg(1, "assistant", "Claude AI usage limit reached|1790000000")])
    assert c["resets"]


def test_other_states():
    base = [msg(0, "user", "go")]
    assert triage.classify_messages(base + [msg(1, "assistant", "API Error: 529 overloaded")])["state"] == (
        "rate_limited_transient"
    )
    assert triage.classify_messages(base, streaming=True)["state"] == "working"
    p = {"kind": "permission", "toolName": "Bash", "input_preview": "pytest"}
    assert triage.classify_messages(base, pending=p)["state"] == "waiting_permission"
    long_report = "Done. " + "All tests pass and the change is committed. " * 20
    assert triage.classify_messages(base + [msg(1, "assistant", long_report)])["state"] == "done_idle"
    amb = triage.classify_messages(base + [msg(1, "assistant", "Error: something odd failed to start")])
    assert amb["state"] == "error_other" and amb["ambiguous"]
    # quota message answered later by real work -> not exhausted
    later = base + [msg(1, "assistant", QUOTA_MSG), msg(2, "user", "continue"), msg(3, "assistant", long_report)]
    assert triage.classify_messages(later)["state"] == "done_idle"


# --------------------------------------------------------------------------- jev (optional)
async def test_jev_off_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    j = Jev(JevConfig())
    assert not j.enabled and j.status() == "no-api-key"
    assert await j.classify_state("x") is None
    c = {"state": "error_other", "ambiguous": True, "source": "pattern", "confidence": 0.5}
    assert (await triage.refine_with_jev(j, dict(c), [], "auto"))["source"] == "pattern"


async def test_jev_fail_open_and_validation(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")
    j = Jev(JevConfig(timeout_s=0.5))

    def boom(body, key):
        raise TimeoutError("slow")

    monkeypatch.setattr(j, "_post", boom)
    assert await j.classify_state("x") is None
    c = await triage.refine_with_jev(j, {"state": "error_other", "ambiguous": True, "source": "pattern"}, [], "auto")
    assert c["state"] == "error_other" and c["jev"] == "unavailable"

    probs = dict.fromkeys(("rate_limited_transient", "waiting_permission", "working", "done_idle", "error_other"), 0.0)
    good = {"answers": {"state": {"type": "choice", "choice": "quota_exhausted", "confidence": 0.93,
                                  "probabilities": {**probs, "quota_exhausted": 1.0}}}}
    monkeypatch.setattr(j, "_post", lambda b, k: good)
    c = await triage.refine_with_jev(j, {"state": "error_other", "ambiguous": True, "source": "pattern"}, [], "auto")
    assert c["state"] == "quota_exhausted" and c["source"] == "jev" and c["confidence"] == 0.93
    bad = {"answers": {"state": {"type": "choice", "choice": "nonsense", "confidence": 0.9, "probabilities": {}}}}
    monkeypatch.setattr(j, "_post", lambda b, k: bad)
    assert await j.classify_state("x") is None  # invalid answers are rejected, never trusted


def test_jev_config_disabled_flag(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")
    assert Jev(JevConfig(enabled="false")).enabled is False


# --------------------------------------------------------------------------- triage over the mock
async def test_sessions_triage_quota(fleet_factory, mock, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    mock.states["sess-claude-0001"]["messages"].append(msg(99, "assistant", QUOTA_MSG))
    f = fleet_factory()
    r = await triage.sessions_triage(f, "h1", states=["quota_exhausted"])
    assert [s["session_id"] for s in r["sessions"]] == ["sess-claude-0001"]
    row = r["sessions"][0]
    assert row["source"] == "pattern" and "spend limit" in row["evidence"] and r["jev"] == "no-api-key"
    assert r["counts_by_state"]["working"] == 1  # the streaming codex session
    await f.close()


# --------------------------------------------------------------------------- failover
def _add_wt_claude(mock, sid="wt-claude-0007"):
    mock.ws_doc["terminals"].append(
        {
            "id": sid,
            "workspaceId": "ws-1",
            "title": "Claude Agent",
            "agentPreset": "claude-code-worktree",
            "cwd": "/srv/demo/.bat-worktrees/abc",
            "worktreePath": "/srv/demo/.bat-worktrees/abc",
            "worktreeBranch": "bat/worktree-abc",
        }
    )
    mock.metas[sid] = {"cwd": "/srv/demo/.bat-worktrees/abc", "isStreaming": False}
    mock.states[sid] = {
        "isStreaming": False,
        "messages": [
            msg(0, "user", "ORIGINAL TASK: add the login API"),
            msg(1, "assistant", "Working on it; endpoints drafted."),
            msg(2, "user", "also add tests"),
            msg(3, "assistant", QUOTA_MSG),
        ],
    }
    mock.git_branch["/srv/demo/.bat-worktrees/abc"] = "bat/worktree-abc"
    mock.worktrees[sid] = {"worktreePath": "/srv/demo/.bat-worktrees/abc",
                           "branchName": "bat/worktree-abc", "sourceBranch": "main",
                           "diff": "", "merged": False, "mergedKind": "unknown"}
    mock.git_status["/srv/demo/.bat-worktrees/abc"] = [{"status": "M", "file": "api.py"}]
    return sid


@pytest.mark.parametrize("reply", [
    {"ok": True, "sessionId": "wrong-successor"}, {"ok": True},
])
async def test_failover_rejects_missing_or_mismatched_successor_ack(fleet_factory, mock, reply):
    sid = _add_wt_claude(mock)
    fleet = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    mock.handlers["claude:start-session"] = lambda params: reply
    try:
        with pytest.raises(WriteRefused, match="reserved session ID"):
            await lifecycle.session_failover(fleet, "h1", sid, confirm=True)
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()


async def test_failover_rejects_host_worktree_branch_change(fleet_factory, mock):
    sid = _add_wt_claude(mock)
    fleet = fleet_factory(writes=True, orchestrate=True)
    mock.worktrees[sid]["branchName"] = "bat/worktree-different"
    try:
        with pytest.raises(WriteRefused, match="worktree branch"):
            await lifecycle.session_failover(fleet, "h1", sid, confirm=True)
        assert not any(i["channel"] == "claude:start-session" for i in mock.invokes)
    finally:
        await fleet.close()


async def test_failover_same_worktree(fleet_factory, mock):
    sid = _add_wt_claude(mock)
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="allow_all")
    with pytest.raises(WriteRefused, match="confirm"):
        await lifecycle.session_failover(f, "h1", sid)
    dry = await lifecycle.session_failover(f, "h1", sid, dry_run=True)
    assert dry["dry_run"] and dry["same_worktree"] and "claude:start-session" not in mock.channels()
    r = await lifecycle.session_failover(f, "h1", sid, confirm=True)
    assert r["old_session_id"] == sid and r["new_session_id"] != sid and r["same_worktree"]
    assert r["branch"] == "bat/worktree-abc" and r["prompt_sent"] and r["counts_toward_cap"]
    assert "worktree:create" not in mock.channels()
    start = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert start["agentPreset"] == "codex-agent-worktree" and start["useWorktree"] is True
    assert start["worktreePath"] == "/srv/demo/.bat-worktrees/abc" and start["cwd"] == "/srv/demo"
    assert start["codexSandboxMode"] == "danger-full-access" and start["codexApprovalPolicy"] == "never"
    sent = next(i for i in mock.invokes if i["channel"] == "claude:send-message")["params"]["prompt"]
    assert "ORIGINAL TASK" in sent and "also add tests" in sent and "bat/worktree-abc" in sent
    assert "M api.py" in sent and "spend limit" in sent
    assert all(i["params"].get("sessionId") != sid for i in mock.invokes if i["channel"] == "claude:send-message")
    e = registry.get("h1", r["new_session_id"])
    assert e["failover_of"] == sid and e["status"] == "active" and e["worktree_path"].endswith("/abc")
    again = await lifecycle.session_failover(f, "h1", sid, confirm=True)
    assert again["skipped"] and again["new_session_id"] == r["new_session_id"]
    sends = len([i for i in mock.invokes if i["channel"] == "claude:send-message"])
    with pytest.raises(WriteRefused, match="reserved successor and handoff"):
        await lifecycle.session_failover(f, "h1", sid, confirm=True,
                                         successor_session_id="another-reservation",
                                         handoff_message_id="batc-another-handoff",
                                         handoff_command_id="another-command")
    assert len([i for i in mock.invokes if i["channel"] == "claude:send-message"]) == sends
    await f.close()


async def test_failover_refuses_non_exhausted_and_non_claude(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True)
    with pytest.raises(WriteRefused, match="does not look quota-exhausted"):
        await lifecycle.session_failover(f, "h1", "sess-claude-0001", confirm=True)
    with pytest.raises(WriteRefused, match="not a Claude"):
        await lifecycle.session_failover(f, "h1", "sess-codex-0002", confirm=True)
    await f.close()


async def test_failover_main_checkout_and_all_exhausted(fleet_factory, mock):
    mock.states["sess-claude-0001"]["messages"].append(msg(99, "assistant", QUOTA_MSG))
    f = fleet_factory(writes=True, orchestrate=True)
    r = await lifecycle.session_failover(f, "h1", all_exhausted=True, confirm=True)
    assert r["count"] == 1 and r["exhausted_found"] == 1
    fo = r["failovers"][0]
    assert fo["same_worktree"] is False and fo["cwd"] == "/srv/demo"
    start = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert start["agentPreset"] == "codex-agent" and "useWorktree" not in start
    assert "codexSandboxMode" not in start  # host default_permission_mode = default
    await f.close()


async def test_failover_of_orchestrated_session_does_not_double_count(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    a = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
    b = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)  # cap (2) reached
    sid = a["session_id"]
    mock.states[sid] = {"isStreaming": False, "messages": [msg(0, "user", "task"), msg(1, "assistant", QUOTA_MSG)]}
    r = await lifecycle.session_failover(f, "h1", sid, confirm=True)
    assert r["same_worktree"] and r["counts_toward_cap"] is False
    assert registry.get("h1", sid)["status"] == "superseded"
    assert len(registry.list_entries("h1", active_only=True)) == 2 and b["session_id"]
    await f.close()


# --------------------------------------------------------------------------- permissions
async def test_session_start_allow_all_defaults(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="allow_all")
    await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
    o = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert o["permissionMode"] == "bypassPermissions"
    await f.close()
    f2 = fleet_factory(writes=True, orchestrate=True)
    mock.invokes.clear()
    await orchestrate.session_start(f2, "h1", "demo-project", "codex", confirm=True)
    o = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert "codexSandboxMode" not in o and "permissionMode" not in o
    await f2.close()


async def test_set_permissions_and_approve_pending(fleet_factory, mock):
    f = fleet_factory(writes=True)
    with pytest.raises(WriteRefused, match="allow-all"):
        await lifecycle.session_set_permissions(f, "h1", "sess-codex-0002", confirm=True)
    await f.close()
    mock.states["sess-codex-0002"]["pendingPermission"] = {"toolUseId": "tu1", "toolName": "Bash", "input": {"command": "pytest"}}
    mock.metas["sess-codex-0002"]["isStreaming"] = False
    f = fleet_factory(writes=True, default_permission_mode="allow_all")
    dry = await lifecycle.approve_pending(f, "h1", dry_run=True)
    assert dry["count"] == 1 and "claude:resolve-permission" not in mock.channels()
    r = await lifecycle.approve_pending(f, "h1", confirm=True)
    item = r["sessions"][0]
    assert item["approved"] and item["raised_to_allow_all"]
    res = next(i for i in mock.invokes if i["channel"] == "claude:resolve-permission")["params"]["result"]
    assert res["behavior"] == "allow" and res["dontAskAgain"] is True
    assert [c for c, _ in mock.perm_calls] == ["claude:set-codex-sandbox-mode", "claude:set-codex-approval-policy"]
    await f.close()


async def test_claude_mode_not_switched_mid_turn(fleet_factory, mock):
    f = fleet_factory(writes=True, default_permission_mode="allow_all")
    mock.metas["sess-claude-0001"]["isStreaming"] = True
    with pytest.raises(lifecycle.TurnInFlight):
        await lifecycle.session_set_permissions(f, "h1", "sess-claude-0001", confirm=True)
    assert mock.perm_calls == []
    mock.metas["sess-claude-0001"]["isStreaming"] = False
    r = await lifecycle.session_set_permissions(f, "h1", "sess-claude-0001", confirm=True)
    assert r["mode"] == "allow_all"
    assert mock.perm_calls[0][0] == "claude:set-permission-mode"
    await f.close()


# --------------------------------------------------------------------------- cleanup
async def _finished_wt(f, mock, kind="unknown", diff="", verified=True):
    r = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    sid = r["session_id"]
    mock.worktrees[sid].update(mergedKind=kind, diff=diff)
    mock.states[sid] = {
        "isStreaming": False,
        "messages": [
            msg(0, "user", "Add feature X. Commit on your branch, run tests, report results."),
            {"id": "t1", "toolName": "Bash", "input": {"command": "uv run pytest -q"}, "status": "completed",
             "timestamp": NOW_MS + 2000},
            msg(3, "assistant", "Done: feature X implemented, 12 tests pass, committed on the branch."),
        ],
    }
    if verified:
        await lifecycle.session_record_verification(
            f, "h1", sid, "abc1234", "uv run pytest -q", 0,
            "mock host /srv/demo worktree, Python 3.12", "artifacts/test-run.log", confirm=True,
        )
    return r


async def test_shared_worktree_reviewer_never_owns_cleanup(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True,
                      safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock)
    registry.update("h1", r["session_id"], role="reviewer", lead_session_id="lead-session")
    decision = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=True)
    row = decision["decisions"][0]
    assert row["decision"] == "KEEP" and not row["remove_worktree"] and not row["stop"]
    await f.close()


async def test_legacy_cleanup_and_main_relay_skip_task_owned_sessions(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True,
                      safety={"write_min_interval_s": 0})
    started = await _finished_wt(f, mock)
    sid = started["session_id"]
    registry.update("h1", sid, task_id="task-service-owned")
    decision = await lifecycle.session_cleanup(f, "h1", session_id=sid,
                                               confirm=True, dry_run=False, min_idle_s=0)
    assert decision["decisions"][0]["decision"] == "KEEP"
    assert not any(i["channel"] in {"worktree:remove", "claude:stop-session"}
                   and i["params"].get("sessionId") == sid for i in mock.invokes)
    for old in ("sess-claude-0001", "sess-codex-0002"):
        registry.ensure_existing("h1", {"session_id": old, "task_id": "task-service-owned"})
    assert await lifecycle.main_session(f, "h1", "demo-project") is None
    await f.close()


async def test_cleanup_clean_only_and_apply(fleet_factory, mock, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock)
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    row = d["decisions"][0]
    assert row["decision"] == "CLEAN_ONLY" and "no changes" in row["reasons"][0]
    assert not any(i["channel"] in ("worktree:remove", "claude:stop-session") for i in mock.invokes)
    with pytest.raises(WriteRefused, match="auto_cleanup"):
        await lifecycle.session_cleanup(f, "h1", confirm=True, dry_run=False)
    await f.close()
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    d = await lifecycle.session_cleanup(f, "h1", confirm=True, dry_run=False)
    row = d["decisions"][0]
    assert "agent stopped" in row["actions"] and any("kept" in a for a in row["actions"])
    rm = next(i for i in mock.invokes if i["channel"] == "worktree:remove")
    assert rm["params"]["deleteBranch"] is False
    assert registry.get("h1", r["session_id"])["status"] == "cleaned"
    await f.close()


async def test_cleanup_merge_needs_jev(fleet_factory, mock, monkeypatch):
    diff = "diff --git a/x.py b/x.py\n+++ b/x.py\n+print('x')\n"
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    await _finished_wt(f, mock, "ahead", diff)
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    assert d["decisions"][0]["decision"] == "ESCALATE" and "Jev unavailable" in d["escalation_summary"]

    async def fake_gate(self, task, final, diff_excerpt, tests):
        return {"claims_done": 0.95, "diff_verdict": "safe_complete", "diff_confidence": 0.9, "tests_ok": 0.9}

    monkeypatch.setattr(Jev, "merge_gate", fake_gate)
    d = await lifecycle.session_cleanup(f, "h1", confirm=True, dry_run=False)
    row = d["decisions"][0]
    assert row["decision"] == "MERGE_AND_CLEAN" and row["actions"][0].startswith("merged")
    assert "worktree:merge" in mock.channels() and "claude:stop-session" in mock.channels()
    await f.close()


async def test_cleanup_requires_commit_bound_execution_not_jev(fleet_factory, mock, monkeypatch):
    diff = "diff --git a/x.py b/x.py\n+++ b/x.py\n+print('x')\n"
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock, "ahead", diff, verified=False)

    async def optimistic_gate(self, task, final, diff_excerpt, tests):
        return {"claims_done": 0.99, "diff_verdict": "safe_complete", "diff_confidence": 0.99, "tests_ok": 0.99}

    monkeypatch.setattr(Jev, "merge_gate", optimistic_gate)
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=True)
    assert d["decisions"][0]["decision"] == "ESCALATE"
    assert not d["decisions"][0]["gates"]["verified_candidate"]
    mock.states[r["session_id"]]["messages"][-1] = msg(3, "assistant", "BAT-STATUS: MILESTONE finished")
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=True)
    assert d["decisions"][0]["decision"] == "ESCALATE"
    assert d["decisions"][0]["gates"]["agent_claims_complete"]

    await lifecycle.session_record_verification(
        f, "h1", r["session_id"], "abc1234", "uv run pytest -q", 0,
        "mock host, Python 3.12", "artifacts/pytest.log", confirm=True,
    )
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=True)
    assert d["decisions"][0]["decision"] == "MERGE_AND_CLEAN"
    assert d["decisions"][0]["gates"]["verified_candidate"]

    wt = r["worktree_path"]
    mock.git_logs = {wt: [{"hash": "def5678"}]}
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=True)
    assert d["decisions"][0]["decision"] == "ESCALATE"
    assert not d["decisions"][0]["gates"]["verified_candidate"]
    await f.close()


async def test_cleanup_rechecks_candidate_before_merge(fleet_factory, mock, monkeypatch):
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock, "ahead", "diff --git a/x b/x\n+++ b/x\n+code\n")

    async def confident_gate(self, task, final, diff_excerpt, tests):
        return {"claims_done": 0.95, "diff_verdict": "safe_complete", "diff_confidence": 0.95, "tests_ok": 0.95}

    monkeypatch.setattr(Jev, "merge_gate", confident_gate)
    original = lifecycle._evaluate

    async def change_after_evaluation(*args, **kwargs):
        row = await original(*args, **kwargs)
        mock.git_logs = {r["worktree_path"]: [{"hash": "def5678"}]}
        return row

    monkeypatch.setattr(lifecycle, "_evaluate", change_after_evaluation)
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], dry_run=False, confirm=True)
    assert d["decisions"][0]["decision"] == "ESCALATE"
    assert "worktree:merge" not in mock.channels()
    await f.close()


async def test_cleanup_escalates_risky_and_keeps_working(fleet_factory, mock, monkeypatch):
    secret = "diff --git a/cfg.py b/cfg.py\n+++ b/cfg.py\n+AWS = 'AKIA" + "QX7ZK2LMN4PR8TVW'\n"
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    await _finished_wt(f, mock, "ahead", secret)
    r2 = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    mock.metas[r2["session_id"]]["isStreaming"] = True
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    by = {x["session_id"]: x for x in d["decisions"]}
    assert by[r2["session_id"]]["decision"] == "KEEP"
    esc = [x for x in d["decisions"] if x["decision"] == "ESCALATE"]
    assert esc and "secret" in esc[0]["reasons"][0]
    await f.close()


async def test_cleanup_stops_superseded_claude_after_failover(fleet_factory, mock):
    sid = _add_wt_claude(mock)
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    fo = await lifecycle.session_failover(f, "h1", sid, confirm=True)
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    by = {x["session_id"]: x for x in d["decisions"]}
    assert by[sid]["decision"] == "CLEAN_ONLY" and by[sid]["stop"] and not by[sid]["remove_worktree"]
    new = by[fo["new_session_id"]]
    assert new["decision"] in ("KEEP", "ESCALATE")  # dirty shared worktree is never removed
    d = await lifecycle.session_cleanup(f, "h1", confirm=True, dry_run=False, session_id=sid)
    assert "agent stopped" in d["decisions"][0]["actions"]
    assert "worktree:remove" not in mock.channels()
    await f.close()


def test_redact_secrets_in_handoff():
    from bat_agent_connector.redact import redact_secrets

    hook = "https://discord.com/api/webhooks/123456789/" + "A" * 60
    t = redact_secrets(f"add {hook} and token = {'x' * 30} ghp_{'b' * 36}")
    assert "AAAA" not in t and "xxxx" not in t and "bbbb" not in t
    assert "discord.com/api/webhooks/123456789/[REDACTED]" in t
    p = lifecycle.build_handoff_prompt(
        old_sid="s", workspace="w", cwd="/srv/w", same_worktree=False, branch="main",
        first_prompt=f"post to {hook}", last_prompt=None, recent=[], git={}, evidence="limit",
    )
    assert "AAAA" not in p and "[REDACTED]" in p


def test_decision_alias():
    assert lifecycle.normalize_decision("escalate_to_ted") == "ESCALATE"
    assert "ESCALATE" in lifecycle.DECISIONS


def test_handoff_custom_instructions():
    p = lifecycle.build_handoff_prompt(
        old_sid="s", workspace="w", cwd="/srv/w", same_worktree=True, branch="b",
        first_prompt="task", last_prompt=None, recent=[], git={}, evidence="limit",
        instructions="Only commit the work in progress.",
    )
    assert "Only commit the work in progress." in p and "How to proceed" not in p
    assert "Continue the work" not in p


async def test_codex_model_default_and_archive_cleanup(fleet_factory, mock, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, codex_model="gpt-x-test", orchestrate_max_sessions=8,
                      safety={"write_min_interval_s": 0})
    await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    o = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert o["model"] == "gpt-x-test"
    mock.invokes.clear()
    await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
    o = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert o.get("model") != "gpt-x-test"
    # an ahead branch marked archive-only is cleaned (branch kept), never merged
    r = await _finished_wt(f, mock, kind="ahead", diff="diff --git a/x b/x\n+++ b/x\n+wip\n")
    registry.update("h1", r["session_id"], cleanup_policy="archive")
    d = await lifecycle.session_cleanup(f, "h1", session_id=r["session_id"], confirm=True, dry_run=False)
    row = d["decisions"][0]
    assert row["decision"] == "CLEAN_ONLY" and "archive" in row["reasons"][0]
    assert "worktree:merge" not in mock.channels()
    rm = next(i for i in mock.invokes if i["channel"] == "worktree:remove")
    assert rm["params"]["deleteBranch"] is False
    await f.close()


async def test_failover_codex_model_and_instructions(fleet_factory, mock):
    sid = _add_wt_claude(mock)
    f = fleet_factory(writes=True, orchestrate=True, codex_model="gpt-x-test")
    r = await lifecycle.session_failover(f, "h1", sid, confirm=True, instructions="Only commit the WIP.",
                                         archive_only=True)
    start = next(i for i in mock.invokes if i["channel"] == "claude:start-session")["params"]["options"]
    assert start["model"] == "gpt-x-test" and r["archive_only"]
    sent = next(i for i in mock.invokes if i["channel"] == "claude:send-message")["params"]["prompt"]
    assert "Only commit the WIP." in sent
    assert registry.get("h1", r["new_session_id"])["cleanup_policy"] == "archive"
    await f.close()


ZH_DONE = (
    "已完成並提交至分支 `bat/worktree-df43e6d3`。\n\nCommit：`6e15a05 phase7: add guarded watch reports`\n\n"
    "驗證全部通過：\n- `cargo test --workspace`\n\n工作目錄乾淨。測試未向真實 Discord webhook 發送請求。"
)


@pytest.mark.parametrize(
    "text,done",
    [
        (ZH_DONE, True),
        ("完成，已提交 commit a1b2c3d，全部通過。", True),
        ("Done: implemented X, all tests pass. Commit `deadbee` on bat/wt-1.", True),
        ("已完成大部分，但尚未提交；需要你確認要用哪個 API。", False),
        ("實作完成 80%，仍失敗 2 個測試，commit 1234abcd 為暫存。", False),
        ("已完成並提交。", False),  # no commit named: Jev decides alone
        ("Committed `abc1234`, but should I also migrate the DB?", False),
        ("I will commit next.", False),
        ("已完成並提交 commit `9f8e7d6`，驗證全部通過。尚未 push。", True),  # not pushed is the normal BAT flow
    ],
)
def test_completion_markers_language_independent(text, done):
    assert lifecycle.completion_markers(text)["claims_done"] is done


def test_apply_markers_lifts_low_jev_score_only_with_markers():
    g = lifecycle._apply_markers({"claims_done": 0.53}, ZH_DONE)
    assert g["claims_done"] == 0.9 and g["claims_done_jev"] == 0.53 and g["markers"]["commit"] == "6e15a05"
    g = lifecycle._apply_markers({"claims_done": 0.53}, "已完成大部分，但尚未提交。commit 1234abc")
    assert g["claims_done"] == 0.53
    assert lifecycle._apply_markers(None, ZH_DONE) is None


def test_final_output_skips_bat_system_notices():
    msgs = [msg(0, "assistant", ZH_DONE), msg(1, "system", "BAT ignored 1 late event from an older Codex turn.")]
    assert lifecycle._final_output(msgs).startswith("已完成")


async def test_jev_merge_gate_prompt_is_language_neutral(monkeypatch):
    seen = {}

    async def fake_ask(self, state, questions):
        seen.update(questions=questions, state=state)
        return None

    monkeypatch.setattr(Jev, "ask", fake_ask)
    await Jev(JevConfig()).merge_gate("", ZH_DONE, "diff", "{}")
    ins = seen["questions"]["claims_done"]["instructions"]
    assert "any language" in ins and "Chinese" in ins and "may be empty" in ins
    assert seen["state"]["final_output"].startswith("已完成")


async def test_cleanup_merges_zh_tw_completion(fleet_factory, mock, monkeypatch):
    diff = "diff --git a/x.rs b/x.rs\n+++ b/x.rs\n+fn x() {}\n"
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock, "ahead", diff)
    mock.states[r["session_id"]]["messages"][-1] = msg(3, "assistant", ZH_DONE)

    async def zh_blind_gate(self, task, final, diff_excerpt, tests):
        return {"claims_done": 0.53, "diff_verdict": "safe_complete", "diff_confidence": 0.95, "tests_ok": 0.9}

    monkeypatch.setattr(Jev, "merge_gate", zh_blind_gate)
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    row = d["decisions"][0]
    assert row["decision"] == "MERGE_AND_CLEAN", row
    assert row["jev"]["claims_done_jev"] == 0.53
    await f.close()


async def test_cleanup_rebuilds_empty_branch_diff(fleet_factory, mock, monkeypatch):
    """BAT returns an empty worktree diff when git's output exceeds a pipe buffer; rebuild it per commit/file."""
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock, "ahead", "")
    wt = mock.worktrees[r["session_id"]]["worktreePath"]
    mock.git_logs = {wt: [{"hash": "c2c2c2c2"}, {"hash": "c1c1c1c1"}, {"hash": "abc1234"}]}
    await lifecycle.session_record_verification(
        f, "h1", r["session_id"], "c2c2c2c2", "uv run pytest -q", 0,
        "mock host /srv/demo worktree, Python 3.12", "artifacts/test-run-2.log", confirm=True,
    )
    mock.commit_files = {
        "c1c1c1c1": [{"status": "M", "file": "src/x.rs"}],
        "c2c2c2c2": [{"status": "A", "file": "assets/big.json"}],
    }
    mock.commit_diffs = {("c1c1c1c1", "src/x.rs"): "diff --git a/src/x.rs b/src/x.rs\n+++ b/src/x.rs\n+fn x() {}\n"}
    seen = {}

    async def gate(self, task, final, diff_excerpt, tests):
        seen["diff"] = diff_excerpt
        return {"claims_done": 0.95, "diff_verdict": "safe_complete", "diff_confidence": 0.9, "tests_ok": 0.9}

    monkeypatch.setattr(Jev, "merge_gate", gate)
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    row = d["decisions"][0]
    assert row["decision"] == "MERGE_AND_CLEAN", row
    assert "+fn x() {}" in seen["diff"] and "assets/big.json" in seen["diff"]
    fb = row["diff_fallback"]
    assert fb["commits"] == ["c1c1c1c1", "c2c2c2c2"] and fb["unavailable"] == ["assets/big.json"]
    assert row["diff_stats"]["files"] == 2
    # main's HEAD not on the branch: no rebuild, Jev sees nothing and stays unsure
    mock.git_logs = {wt: [{"hash": "c2c2c2c2"}]}
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    assert d["decisions"][0]["diff_fallback"]["commits"] == [] and seen["diff"] == ""
    await f.close()


def test_placeholder_secrets_do_not_trip_risk_check():
    fake = 'let tok' + 'en = "' + "abcdefghijklmnopqrstuvwxyz" + '0123456789.ABC_def-ghi";\n'
    hook = '"https://discord.com/api/webhooks/123456/{token}"\n'
    diff = "diff --git a/t.rs b/t.rs\n+++ b/t.rs\n+" + fake + "+" + hook + '+api_key = "your-api-key-here"\n'
    assert lifecycle.risk_checks(diff) == []
    real = "diff --git a/c.py b/c.py\n+++ b/c.py\n+tok" + "en = 'Qm9vN3kLp2" + "XzR7tVw4Yh8JdS'\n"
    assert "secret" in lifecycle.risk_checks(real)[0]
    assert "secret" in lifecycle.risk_checks("+AWS = 'AKIA" + "QX7ZK2LMN4PR8TVW'\n")[0]
