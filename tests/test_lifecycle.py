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
    mock.git_status["/srv/demo/.bat-worktrees/abc"] = [{"status": "M", "file": "api.py"}]
    return sid


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
async def _finished_wt(f, mock, kind="unknown", diff=""):
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
    return r


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
    assert d["decisions"][0]["decision"] == "ESCALATE_TO_TED" and "Jev unavailable" in d["escalation_summary"]

    async def fake_gate(self, task, final, diff_excerpt, tests):
        return {"claims_done": 0.95, "diff_verdict": "safe_complete", "diff_confidence": 0.9, "tests_ok": 0.9}

    monkeypatch.setattr(Jev, "merge_gate", fake_gate)
    d = await lifecycle.session_cleanup(f, "h1", confirm=True, dry_run=False)
    row = d["decisions"][0]
    assert row["decision"] == "MERGE_AND_CLEAN" and row["actions"][0].startswith("merged")
    assert "worktree:merge" in mock.channels() and "claude:stop-session" in mock.channels()
    await f.close()


async def test_cleanup_escalates_risky_and_keeps_working(fleet_factory, mock, monkeypatch):
    secret = "diff --git a/cfg.py b/cfg.py\n+++ b/cfg.py\n+AWS = 'AKIA" + "ABCDEFGHIJKLMNOP'\n"
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    await _finished_wt(f, mock, "ahead", secret)
    r2 = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    mock.metas[r2["session_id"]]["isStreaming"] = True
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    by = {x["session_id"]: x for x in d["decisions"]}
    assert by[r2["session_id"]]["decision"] == "KEEP"
    esc = [x for x in d["decisions"] if x["decision"] == "ESCALATE_TO_TED"]
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
    assert new["decision"] in ("KEEP", "ESCALATE_TO_TED")  # dirty shared worktree is never removed
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
