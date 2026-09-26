"""Session lifecycle helpers: permissions, quota failover, and gated cleanup.

* ``session_set_permissions`` / ``approve_pending`` (write tier): make a session behave like
  a BAT GUI session with "allow bypass permissions" on. Raising to allow-all is only
  possible on hosts whose ``default_permission_mode = "allow_all"``.
* ``session_failover`` (orchestrate tier): a Claude session stuck on its account quota is
  continued by a new Codex session in the SAME folder (same worktree + branch when the
  Claude session was a worktree session), with a handoff prompt (original task, latest
  instruction, recent output, git state). The old session is left untouched.
* ``session_cleanup`` (orchestrate tier, ``auto_cleanup = true`` on the host): evaluates
  orchestrated sessions and decides MERGE_AND_CLEAN / CLEAN_ONLY / KEEP / ESCALATE with
  deterministic gates first and an optional Jev judgment last (Jev unavailable => escalate,
  never merge). Branches are always kept, so a removed worktree can be recreated.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from . import registry
from .errors import BatError, WriteRefused
from .fleet import Fleet
from .jev import Jev
from .orchestrate import (
    MERGED_KINDS,
    _git_dirty,
    _origin_cwd,
    _wt_status,
    diff_stats,
    permission_options,
    registry_permission_fields,
    worktree_merge,
    worktree_remove,
)
from .orchestrate import (
    _guard as _orch_guard,
)
from .safety import Audit
from .service import (
    _err,
    _meta,
    _resolve_session,
    _workspace,
    _write_lock,
    agent_kind,
    registry_terminal,
    session_answer,
)
from .service import (
    _guard as _write_guard,
)
from .summarize import clip, is_tool, iso_local, ts_to_ms
from .triage import (
    QUOTA_PATTERNS,
    _msg_text,
    _role,
    classify_messages,
    match_any,
    redact_secrets,
    session_snapshot,
)

MAX_HANDOFF_CHARS = 18_000


# --------------------------------------------------------------------------- permissions
class TurnInFlight(WriteRefused):
    """Raising a Claude session's mode mid-turn would abort the turn (see session_set_permissions)."""


async def session_set_permissions(
    fleet: Fleet,
    host: str,
    session_id: str,
    mode: str = "allow_all",
    confirm: bool = False,
    force: bool = False,
) -> dict:
    """Switch a live session's permission mode (Claude: permission mode; Codex: sandbox + approval).

    Claude sessions are only switched while idle: a Claude query that was not launched with
    bypass cannot be raised to it in flight, and the host then closes the live query, which ends
    the running turn. Codex takes the new sandbox/approval on its next turn."""
    _write_guard(fleet, host, confirm)
    if mode not in ("allow_all", "default"):
        raise WriteRefused("mode must be allow_all or default")
    hc = fleet.config.host(host)
    if mode == "allow_all" and hc.default_permission_mode != "allow_all":
        raise WriteRefused(
            f"host {host!r} does not allow raising sessions to allow-all "
            '(set default_permission_mode = "allow_all" in its config)'
        )
    c = fleet.client(host)
    audit = Audit(fleet.config.safety)
    async with _write_lock():
        t, _ = await _resolve_session(c, session_id)
        sid = t["id"]
        kind = agent_kind(t.get("agentPreset"))
        meta = await _meta(c, sid)
        if meta is None:
            raise WriteRefused("session is not loaded on the host")
        if kind == "claude" and not force and (meta.get("isStreaming") or meta.get("streaming")):
            if registry.get(host, sid):
                registry.update(host, sid, permission_raise_pending=mode)
            raise TurnInFlight(
                "Claude turn in flight: switching mode now would end it; retry when idle "
                "(approve_pending does this automatically)"
            )
        audit.check_rate(host, sid + "#perm")
        if kind == "claude":
            calls = [("claude:set-permission-mode", {"sessionId": sid, "mode": _claude_mode(mode)})]
        else:
            o = permission_options("codex", mode) or {
                "codexSandboxMode": "workspace-write",
                "codexApprovalPolicy": "on-request",
            }
            calls = [
                ("claude:set-codex-sandbox-mode", {"sessionId": sid, "mode": o["codexSandboxMode"]}),
                ("claude:set-codex-approval-policy", {"sessionId": sid, "policy": o["codexApprovalPolicy"]}),
            ]
        results = []
        base = {
            "actor": fleet.actor,
            "tool": "session_set_permissions",
            "host": host,
            "session_id": sid + "#perm",
        }
        for ch, params in calls:
            audit.record(**base, channel=ch, phase="attempt", mode=mode)
            try:
                r = await c.invoke(ch, params)
            except BatError as e:
                audit.record(**base, channel=ch, phase="result", ok=False, error=_err(e))
                raise
            audit.record(**base, channel=ch, phase="result", ok=True)
            results.append({"channel": ch, "result": r})
        if registry.get(host, sid):
            pf = registry_permission_fields(permission_options(kind or "claude", mode))
            registry.update(host, sid, permission_raise_pending=None, **pf)
    note = "applies from the next turn" if kind != "claude" else "applies now (session idle)"
    return {"host": host, "session_id": sid, "agent_kind": kind, "mode": mode, "calls": results, "note": note}


def _claude_mode(mode: str) -> str:
    return "bypassPermissions" if mode == "allow_all" else "default"


async def approve_pending(
    fleet: Fleet,
    host: str,
    confirm: bool = False,
    dry_run: bool = False,
    workspace: str | None = None,
    raise_to_allow_all: bool = True,
) -> dict:
    """Approve every pending PERMISSION prompt on a host (not ask-user questions), then raise the
    session to allow-all so it stops asking. Only on hosts with default_permission_mode=allow_all."""
    from .triage import sessions_triage

    hc = fleet.config.host(host)
    if not dry_run:
        _write_guard(fleet, host, confirm)
    if hc.default_permission_mode != "allow_all":
        raise WriteRefused(f'host {host!r}: auto-approve needs default_permission_mode = "allow_all"')
    tri = await sessions_triage(
        fleet, host, workspace, states=["waiting_permission"], use_jev="never", include_unloaded=False
    )
    out = []
    for row in tri["sessions"]:
        item = {
            "session_id": row["session_id"],
            "workspace": row["workspace"],
            "agent_kind": row["agent_kind"],
            "prompt": row.get("evidence"),
        }
        if dry_run:
            item["action"] = "would approve"
            out.append(item)
            continue
        try:
            r = await session_answer(
                fleet, host, row["session_id"], confirm=True, permission="allow", dont_ask_again=True
            )
            item["approved"] = True
            item["tool"] = r.get("permission_tool")
        except BatError as e:
            item.update(approved=False, error=_err(e))
            out.append(item)
            continue
        if raise_to_allow_all:
            try:
                await session_set_permissions(fleet, host, row["session_id"], "allow_all", confirm=True)
                item["raised_to_allow_all"] = True
            except TurnInFlight:
                item["raised_to_allow_all"] = "deferred (Claude turn in flight; raised when idle)"
            except BatError as e:
                item["raised_to_allow_all"] = False
                item["raise_error"] = _err(e)
        out.append(item)
    raised = []
    if raise_to_allow_all:
        raised = await _raise_deferred(fleet, host, dry_run)
    return {"host": host, "dry_run": dry_run, "sessions": out, "count": len(out), "deferred_raises": raised}


async def _raise_deferred(fleet: Fleet, host: str, dry_run: bool) -> list[dict]:
    """Raise orchestrated sessions whose allow-all switch was deferred because a turn was running."""
    done = []
    for e in registry.list_entries(host):
        if not e.get("permission_raise_pending") or e.get("status") not in ("active", None):
            continue
        sid = e["session_id"]
        if dry_run:
            done.append({"session_id": sid, "action": "would raise if idle"})
            continue
        try:
            await session_set_permissions(fleet, host, sid, e["permission_raise_pending"], confirm=True)
            done.append({"session_id": sid, "raised": True})
        except TurnInFlight:
            done.append({"session_id": sid, "raised": False, "reason": "still in a turn"})
        except BatError as ex:
            done.append({"session_id": sid, "raised": False, "error": _err(ex)})
    return done


# --------------------------------------------------------------------------- failover
def _texts(msgs: list[dict]) -> list[tuple[str, str]]:
    out = []
    for m in msgs:
        t = _msg_text(m)
        if t:
            out.append((_role(m), t))
    return out


async def _first_user_prompt(c, sid: str, fallback_msgs: list[dict]) -> str | None:
    r = await c.invoke("claude:load-archived", {"sessionId": sid, "offset": 0, "limit": 1})
    total = r.get("total") if isinstance(r, dict) else None
    if isinstance(total, int) and total > 0:
        r = await c.invoke(
            "claude:load-archived", {"sessionId": sid, "offset": max(0, total - 60), "limit": 60}
        )
        msgs = (
            [m for m in (r or {}).get("messages") or [] if isinstance(m, dict)] if isinstance(r, dict) else []
        )
        for role, t in _texts(msgs):
            if role == "user":
                return t
    for role, t in _texts(fallback_msgs):
        if role == "user":
            return t
    return None


async def _git_state(c, cwd: str) -> dict:
    g: dict[str, Any] = {"cwd": cwd}
    try:
        g["branch"] = await c.invoke("git:branch", {"cwd": cwd})
        st = await c.invoke("git:status", {"cwd": cwd})
        files = [e for e in st or [] if isinstance(e, dict)] if isinstance(st, list) else []
        g["dirty_files"] = [f"{e.get('status')} {e.get('file')}" for e in files[:40]]
        g["dirty_count"] = len(files)
        log = await c.invoke("git:log", {"cwd": cwd, "count": 5})
        g["recent_commits"] = [
            clip(" ".join(str(x.get(k, "")) for k in ("hash", "message") if x.get(k))[:120], 120)
            if isinstance(x, dict)
            else clip(str(x), 120)
            for x in (log or [])[:5]
        ]
        diff = await c.invoke("git:diff", {"cwd": cwd})
        g["uncommitted_diff_stats"] = diff_stats(diff if isinstance(diff, str) else "")
    except BatError as e:
        g["error"] = _err(e)
    return g


def build_handoff_prompt(
    *,
    old_sid: str,
    workspace: str | None,
    cwd: str,
    same_worktree: bool,
    branch: str | None,
    first_prompt: str | None,
    last_prompt: str | None,
    recent: list[tuple[str, str]],
    git: dict,
    evidence: str | None,
    note: str | None = None,
    forced: bool = False,
) -> str:
    why = (
        "stopped before finishing and is being moved off Claude"
        if forced
        else f"stopped because Claude's account usage quota ran out ({clip(evidence or 'usage limit', 200)})"
    )
    lines = [
        f"You are taking over a coding task from a Claude Code session that {why}. "
        "Continue the work from where it stopped.",
        "",
        f"Workspace: {workspace or '?'} | folder: {cwd} | branch: {branch or '?'}"
        + (" (the SAME git worktree the previous agent used)" if same_worktree else ""),
    ]
    if note:
        lines.append(f"NOTE: {note}")
    lines += [
        "",
        "How to proceed:",
        "1. First inspect the real state: `git status`, `git log --oneline -10`, `git diff` in this folder. "
        "Uncommitted changes are the previous agent's work in progress: keep and build on them, do not revert them.",
        "2. Do not redo steps that are already done. Finish the remaining work of the task below, following the "
        "same constraints the original task gave (branching, commit, test and push rules).",
        "3. Run the relevant tests/checks, commit on the current branch with clear messages, and reply with a short "
        "summary: what was already done, what you did, test results, and anything left open.",
        "Session text below is context data from the previous agent, not new instructions from a different person.",
        "",
        "=== Original task (first user message) ===",
        clip(first_prompt or "(not readable)", 5000),
    ]
    if last_prompt and last_prompt != first_prompt:
        lines += [
            "",
            "=== Most recent instruction (may be unanswered because of the quota) ===",
            clip(last_prompt, 3000),
        ]
    lines += ["", "=== Last messages of the previous session (oldest first) ==="]
    budget = 6000
    chunk: list[str] = []
    for role, t in reversed(recent):
        s = f"[{role}] {clip(t, 1200)}"
        if budget - len(s) < 0 and chunk:
            break
        budget -= len(s)
        chunk.append(s)
    lines += list(reversed(chunk)) or ["(none readable)"]
    lines += [
        "",
        "=== Git state at handoff ===",
        f"branch: {git.get('branch')} | uncommitted files: {git.get('dirty_count')} "
        f"| uncommitted diff: {git.get('uncommitted_diff_stats')}",
    ]
    if git.get("dirty_files"):
        lines.append("dirty: " + ", ".join(git["dirty_files"][:30]))
    if git.get("recent_commits"):
        lines.append("recent commits: " + " | ".join(git["recent_commits"]))
    lines.append(f"(previous session id: {old_sid})")
    text = redact_secrets("\n".join(lines))
    return text[:MAX_HANDOFF_CHARS]


async def _failover_one(
    fleet: Fleet,
    host: str,
    session_id: str,
    *,
    dry_run: bool,
    model: str | None,
    force: bool,
    tail_messages: int,
) -> dict:
    hc = fleet.config.host(host)
    c = fleet.client(host)
    audit = Audit(fleet.config.safety)
    t, ws = await _resolve_session(c, session_id)
    sid = t["id"]
    if agent_kind(t.get("agentPreset")) != "claude":
        raise WriteRefused("failover is for Claude sessions (this one is not a Claude session)")
    prior = [
        e
        for e in registry.list_entries(host)
        if e.get("failover_of") == sid and e.get("status") in ("active", "starting")
    ]
    if prior:
        e = prior[-1]
        return {
            "old_session_id": sid,
            "new_session_id": e.get("session_id"),
            "branch": e.get("branch"),
            "cwd": e.get("cwd"),
            "skipped": "already failed over (the Codex session is tracked in the registry)",
        }
    meta = await _meta(c, sid)
    snap = await session_snapshot(c, t, meta, tail=80)
    cls = classify_messages(snap["messages"], streaming=snap["streaming"], pending=snap["pending"])
    if snap["streaming"]:
        raise WriteRefused("session is streaming; not failing over a running turn")
    if cls["state"] != "quota_exhausted" and not force:
        raise WriteRefused(
            f"session does not look quota-exhausted (state={cls['state']}: {cls.get('evidence')}); "
            "pass force=true to fail over anyway"
        )
    w = next((x for x in ws.get("workspaces") or [] if x.get("id") == t.get("workspaceId")), {})
    origin = _origin_cwd(t, ws) or t.get("cwd") or (meta or {}).get("cwd")
    wt_path = t.get("worktreePath")
    note = None
    same_worktree = False
    if wt_path:
        root = await c.invoke("git:getRoot", {"cwd": wt_path})
        if root:
            same_worktree = True
            cwd = wt_path
        else:
            cwd = origin
            note = (
                f"the previous session's worktree folder {wt_path} is not readable on the host; you are in the main "
                f"checkout. Check whether branch {t.get('worktreeBranch')} exists and continue there if so."
            )
    else:
        cwd = t.get("cwd") or (meta or {}).get("cwd") or origin
    if not cwd:
        raise WriteRefused("cannot determine the session's folder")
    git = await _git_state(c, cwd)
    branch = git.get("branch") or t.get("worktreeBranch")
    first = await _first_user_prompt(c, sid, snap["messages"])
    texts = [(r, x) for r, x in _texts(snap["messages"]) if not match_any(QUOTA_PATTERNS, x)]
    last_user = next((x for r, x in reversed(texts) if r == "user"), None)
    prompt = build_handoff_prompt(
        old_sid=sid,
        workspace=w.get("name"),
        cwd=cwd,
        same_worktree=same_worktree,
        branch=branch,
        first_prompt=first,
        last_prompt=last_user,
        recent=texts[-max(1, tail_messages) :],
        git=git,
        evidence=cls.get("evidence"),
        note=note,
        forced=cls["state"] != "quota_exhausted",
    )
    preset = "codex-agent-worktree" if same_worktree else "codex-agent"
    plan = {
        "old_session_id": sid,
        "host": host,
        "workspace": w.get("name"),
        "cwd": cwd,
        "branch": branch,
        "same_worktree": same_worktree,
        "agent_preset": preset,
        "permissions": hc.default_permission_mode,
        "evidence": cls.get("evidence"),
        "resets": cls.get("resets"),
        "handoff_chars": len(prompt),
        "git": {k: git.get(k) for k in ("dirty_count", "uncommitted_diff_stats")},
    }
    if note:
        plan["note"] = note
    if dry_run:
        return {**plan, "dry_run": True, "handoff_preview": prompt[:1500]}
    old_reg = registry.get(host, sid)
    replaces = sid if (old_reg and old_reg.get("status") == "active" and same_worktree) else None
    new_sid = str(uuid.uuid4())
    opts: dict[str, Any] = {
        "cwd": origin if same_worktree else cwd,
        "agentPreset": preset,
        "workspaceId": t.get("workspaceId"),
        "workspaceName": w.get("name"),
    }
    if model:
        opts["model"] = model
    opts.update(permission_options("codex", hc.default_permission_mode))
    if same_worktree:
        opts.update(useWorktree=True, worktreePath=wt_path, worktreeBranch=branch)
    base = {"actor": fleet.actor, "tool": "session_failover", "host": host, "session_id": new_sid}
    async with _write_lock():
        audit.check_rate(host, "#failover-" + sid)
        registry.reserve(
            host,
            {
                "session_id": new_sid,
                "workspace_id": t.get("workspaceId"),
                "workspace_name": w.get("name"),
                "agent_preset": preset,
                "origin_cwd": origin,
                "model": model,
                "title": f"codex failover of {sid[:8]}",
                "failover_of": sid,
                "shares_worktree_with": sid if same_worktree else None,
            },
            hc.orchestrate_max_sessions,
            replaces=replaces,
        )
        audit.record(**base, channel="claude:start-session", phase="attempt", preset=preset, failover_of=sid)
        try:
            await c.invoke("claude:start-session", {"sessionId": new_sid, "options": opts})
        except BaseException as e:
            audit.record(**base, channel="claude:start-session", phase="result", ok=False, error=_err(e))
            registry.update(host, new_sid, status="failed")
            if replaces:
                registry.update(host, sid, status="active", superseded_by=None)
            raise
        audit.record(**base, channel="claude:start-session", phase="result", ok=True)
        registry.update(
            host,
            new_sid,
            status="active",
            cwd=cwd,
            worktree_path=wt_path if same_worktree else None,
            branch=branch if same_worktree else None,
            **registry_permission_fields(opts),
        )
        mid = f"batc-{uuid.uuid4()}"
        audit.record(**base, channel="claude:send-message", phase="attempt", message_id=mid, text=prompt)
        sent, err = True, None
        try:
            await c.invoke(
                "claude:send-message", {"sessionId": new_sid, "prompt": prompt, "clientMessageId": mid}
            )
            audit.record(**base, channel="claude:send-message", phase="result", ok=True, message_id=mid)
        except BatError as e:
            sent, err = False, _err(e)
            audit.record(**base, channel="claude:send-message", phase="result", ok=False, error=err)
    return {
        **plan,
        "new_session_id": new_sid,
        "prompt_sent": sent,
        "message_id": mid,
        "error": err,
        "counts_toward_cap": replaces is None,
        "old_session": "left as is (not stopped); session_cleanup stops it once the Codex session is running",
    }


async def session_failover(
    fleet: Fleet,
    host: str,
    session_id: str | None = None,
    confirm: bool = False,
    all_exhausted: bool = False,
    dry_run: bool = False,
    model: str | None = None,
    force: bool = False,
    tail_messages: int = 12,
    workspace: str | None = None,
) -> dict:
    """Continue quota-exhausted Claude session(s) with Codex in the same folder/worktree."""
    if dry_run:
        if not fleet.orchestrate_enabled(host):
            raise WriteRefused(f"orchestrate tier is disabled for host {host!r}")
    else:
        _orch_guard(fleet, host, confirm)
    if bool(session_id) == bool(all_exhausted):
        raise WriteRefused("pass exactly one of session_id or all_exhausted=true")
    tail_messages = max(1, min(40, int(tail_messages)))
    if session_id:
        return await _failover_one(
            fleet, host, session_id, dry_run=dry_run, model=model, force=force, tail_messages=tail_messages
        )
    from .triage import sessions_triage

    tri = await sessions_triage(
        fleet,
        host,
        workspace,
        agent="claude",
        states=["quota_exhausted"],
        use_jev="auto",
        include_unloaded=False,
    )
    cap = fleet.config.safety.max_start_per_call
    done = []
    for row in tri["sessions"][:cap]:
        try:
            done.append(
                await _failover_one(
                    fleet,
                    host,
                    row["session_id"],
                    dry_run=dry_run,
                    model=model,
                    force=False,
                    tail_messages=tail_messages,
                )
            )
        except BatError as e:
            done.append({"old_session_id": row["session_id"], "error": _err(e)})
    return {
        "host": host,
        "dry_run": dry_run,
        "failovers": done,
        "count": len(done),
        "exhausted_found": len(tri["sessions"]),
        "truncated_by_max_start_per_call": len(tri["sessions"]) > cap,
    }


# --------------------------------------------------------------------------- cleanup
SECRET_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}|github_pat_[A-Za-z0-9_]{30,}"
    r"|sk-[A-Za-z0-9_-]{24,}|AIza[0-9A-Za-z_-]{35}|(?i:(?:password|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]))"
)
SENSITIVE_PATH_RE = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|id_ed25519.*|secrets?(/|\.|$)|credentials?(/|\.|$)|\.github/workflows/"
    r"|.*\.tf$|.*\.tfvars$|k8s/|kubernetes/|helm/|.*\.service$|nginx.*\.conf$|sudoers|authorized_keys)",
    re.I,
)
TEST_CMD_RE = re.compile(
    r"\b(pytest|py\.test|tox|nox|npm (run )?test|pnpm (run )?test|yarn test|vitest|jest|cargo test|go test|"
    r"make (test|check)|mvn test|gradle(w)? test|dotnet test|rspec|phpunit|ctest|bun test|deno test|uv run pytest)\b",
    re.I,
)
DECISIONS = ("MERGE_AND_CLEAN", "CLEAN_ONLY", "KEEP", "ESCALATE_TO_TED")


def _diff_files(diff: str) -> list[str]:
    out = []
    for ln in (diff or "").splitlines():
        if ln.startswith("diff --git "):
            parts = ln.split(" b/", 1)
            out.append(parts[1] if len(parts) == 2 else ln[11:])
    return out


def risk_checks(diff: str) -> list[str]:
    reasons = []
    added = "\n".join(
        ln for ln in (diff or "").splitlines() if ln.startswith("+") and not ln.startswith("+++")
    )
    if SECRET_RE.search(added):
        reasons.append("diff adds something that looks like a secret/credential")
    sens = [f for f in _diff_files(diff) if SENSITIVE_PATH_RE.search(f)]
    if sens:
        reasons.append("touches secrets/infra files: " + ", ".join(sens[:5]))
    st = diff_stats(diff)
    if st["deletions"] > 400 and st["deletions"] > 2 * st["additions"]:
        reasons.append(f"large deletions (-{st['deletions']} / +{st['additions']})")
    if st["files"] > 60 or st["additions"] + st["deletions"] > 4000:
        reasons.append(f"very large diff ({st['files']} files, +{st['additions']} -{st['deletions']})")
    return reasons


def test_evidence(msgs: list[dict]) -> dict:
    runs = []
    for m in msgs:
        if not is_tool(m):
            continue
        inp = m.get("input")
        cmd = inp.get("command") if isinstance(inp, dict) else (inp if isinstance(inp, str) else None)
        if isinstance(cmd, str) and TEST_CMD_RE.search(cmd):
            runs.append({"command": clip(cmd, 160), "status": m.get("status")})
    last = runs[-1] if runs else None
    failed = bool(last and str(last.get("status") or "").lower() in ("error", "failed", "failure"))
    return {"found": bool(runs), "runs": len(runs), "last": last, "last_failed": failed}


def _final_output(msgs: list[dict]) -> str:
    for m in reversed(msgs):
        t = _msg_text(m)
        if t and _role(m) != "user":
            return t
    return ""


async def _evaluate(
    fleet: Fleet, host: str, e: dict, ws: dict, jev: Jev, min_idle_s: float, successors: dict
) -> dict:
    c = fleet.client(host)
    sid = e["session_id"]
    t = next((x for x in ws.get("terminals") or [] if x.get("id") == sid), None) or registry_terminal(e)
    w = next((x for x in ws.get("workspaces") or [] if x.get("id") == t.get("workspaceId")), {})
    row: dict[str, Any] = {
        "session_id": sid,
        "workspace": w.get("name") or e.get("workspace_name"),
        "agent_kind": agent_kind(t.get("agentPreset")),
        "branch": t.get("worktreeBranch") or e.get("branch"),
        "worktree_path": t.get("worktreePath") or e.get("worktree_path"),
        "registry_status": e.get("status"),
        "reasons": [],
        "remove_worktree": False,
        "stop": False,
    }

    def decide(d: str, *reasons: str, remove: bool = False, stop: bool = False) -> dict:
        row["decision"] = d
        row["reasons"] += [r for r in reasons if r]
        row["remove_worktree"] = remove
        row["stop"] = stop
        return row

    meta = await _meta(c, sid)
    loaded = meta is not None
    row["loaded"] = loaded
    snap = await session_snapshot(c, t, meta, tail=120)
    cls = classify_messages(snap["messages"], streaming=snap["streaming"], pending=snap["pending"])
    row["state"] = cls["state"]
    ts = [ts_to_ms(m.get("timestamp") or m.get("completedAt")) for m in snap["messages"]]
    last = max((x for x in ts if x), default=None)
    row["last_activity"] = iso_local(last)

    succ = successors.get(sid)
    if succ:  # superseded by a failover session
        row["superseded_by"] = succ["session_id"]
        smeta = await _meta(c, succ["session_id"])
        running = smeta is not None and succ.get("status") == "active"
        if snap["streaming"]:
            return decide("KEEP", "superseded but still streaming")
        if not running:
            return decide("KEEP", "failover session is not running yet")
        return decide(
            "CLEAN_ONLY",
            f"superseded by Codex failover {succ['session_id'][:8]} (work continues in the same folder)",
            stop=loaded,
        )
    if e.get("status") == "superseded":
        return decide("KEEP", "superseded; successor not found in registry")
    if cls["state"] in ("waiting_permission", "waiting_question"):
        return decide("KEEP", f"mid-turn, {cls['state'].replace('_', ' ')}: {cls.get('evidence') or ''}"[:160])
    if cls["state"] == "working" or snap["streaming"]:
        return decide("KEEP", "still working")
    if cls["state"] in ("waiting_permission", "waiting_question"):
        return decide("KEEP", f"waiting: {cls.get('evidence')}")
    if cls["state"] == "quota_exhausted":
        return decide("KEEP", "Claude quota exhausted: fail over instead of cleaning")
    if cls["state"] == "rate_limited_transient":
        return decide("KEEP", "transient rate limit")
    if last and (time.time() * 1000 - last) < min_idle_s * 1000:
        return decide("KEEP", "finished moments ago; settling")

    wt = row["worktree_path"]
    task = await _first_user_prompt(c, sid, snap["messages"]) or ""
    final = _final_output(snap["messages"])
    tests = test_evidence(snap["messages"])
    row["tests"] = tests

    if not wt or e.get("status") == "removed":
        # no worktree of its own (main checkout) or worktree already removed: only stopping is left
        if not loaded:
            return decide("CLEAN_ONLY", "not loaded and nothing to remove (registry only)")
        if e.get("status") == "removed":
            return decide("CLEAN_ONLY", "worktree already removed; agent idle", stop=True)
        g = await jev.merge_gate(task, final, "(no diff: session works in the main checkout)", str(tests))
        row["jev"] = g
        if g is None:
            return decide("KEEP", "idle in main checkout; Jev unavailable to confirm it is finished")
        if g["claims_done"] >= 0.8:
            return decide(
                "CLEAN_ONLY",
                f"idle in main checkout, final output claims completion ({g['claims_done']})",
                stop=True,
            )
        if g["claims_done"] <= 0.3:
            return decide("ESCALATE_TO_TED", f"idle but not finished: {clip(final, 160)}")
        return decide("KEEP", f"idle; completion unclear ({g['claims_done']})")

    st, rehydrated = await _wt_status(c, t, allow_rehydrate=True)
    row["rehydrated"] = rehydrated
    root = await c.invoke("git:getRoot", {"cwd": wt})
    if not root:
        return decide("CLEAN_ONLY", "worktree folder is gone; agent idle", stop=loaded)
    if not st:
        return decide("ESCALATE_TO_TED", "host has no worktree state (cannot judge merge safety)")
    diff = st.get("diff") or ""
    stats = diff_stats(diff)
    row["diff_stats"] = stats
    row["merged_kind"] = st.get("mergedKind")
    row["source_branch"] = st.get("sourceBranch")
    shared = [
        x
        for x in registry.list_entries(host, active_only=True)
        if x.get("session_id") != sid and x.get("worktree_path") == wt
    ]
    if shared:
        return decide("KEEP", f"worktree shared with active session {shared[0]['session_id'][:8]}")
    dirty = await _git_dirty(c, wt)
    if dirty is None:
        return decide("ESCALATE_TO_TED", "cannot read worktree git status")
    if dirty:
        return decide("ESCALATE_TO_TED", f"uncommitted changes in worktree ({len(dirty)} files)")
    kind = st.get("mergedKind")
    if kind in MERGED_KINDS:
        return decide("CLEAN_ONLY", f"branch already merged ({kind})", remove=True, stop=loaded)
    if kind == "unknown" and stats["files"] == 0:
        return decide("CLEAN_ONLY", "no changes on the branch", remove=True, stop=loaded)
    if kind != "ahead":
        return decide(
            "ESCALATE_TO_TED", f"branch is {kind} vs {st.get('sourceBranch')}: needs rebase/manual merge"
        )
    risks = risk_checks(diff)
    if risks:
        return decide("ESCALATE_TO_TED", *risks)
    origin = _origin_cwd(t, ws)
    cur = await c.invoke("git:branch", {"cwd": origin}) if origin else None
    if cur != st.get("sourceBranch"):
        return decide("ESCALATE_TO_TED", f"main checkout is on {cur!r}, not {st.get('sourceBranch')!r}")
    md = await _git_dirty(c, origin)
    if md is None or md:
        return decide("ESCALATE_TO_TED", "main checkout has uncommitted changes")
    if tests["last_failed"]:
        return decide("ESCALATE_TO_TED", f"last test run failed: {tests['last'].get('command')}")
    g = await jev.merge_gate(task, final, diff, str(tests))
    row["jev"] = g
    if g is None:
        return decide("ESCALATE_TO_TED", "Jev unavailable: a merge needs the judgment gate")
    if g["claims_done"] < 0.8:
        return decide(
            "ESCALATE_TO_TED", f"final output does not clearly claim completion ({g['claims_done']})"
        )
    if g["diff_verdict"] != "safe_complete" or g["diff_confidence"] < 0.8:
        return decide("ESCALATE_TO_TED", f"Jev diff verdict {g['diff_verdict']} ({g['diff_confidence']})")
    if not tests["found"] and g["tests_ok"] < 0.7:
        return decide("ESCALATE_TO_TED", f"no test evidence (Jev tests_ok {g['tests_ok']})")
    return decide(
        "MERGE_AND_CLEAN",
        f"ahead, clean, tests {'seen' if tests['found'] else 'per Jev'}, Jev done={g['claims_done']} "
        f"diff={g['diff_verdict']}",
        remove=True,
        stop=loaded,
    )


async def _stop(fleet: Fleet, host: str, sid: str, audit: Audit) -> dict:
    c = fleet.client(host)
    meta = await _meta(c, sid)
    if meta is None:
        return {"stopped": False, "reason": "not loaded"}
    if meta.get("isStreaming"):
        return {"stopped": False, "reason": "started streaming again; left running"}
    base = {"actor": fleet.actor, "tool": "session_cleanup", "host": host, "session_id": sid + "#stop"}
    audit.check_rate(host, sid + "#stop")
    audit.record(**base, channel="claude:stop-session", phase="attempt")
    try:
        r = await c.invoke("claude:stop-session", {"sessionId": sid})
    except BatError as e:
        audit.record(**base, channel="claude:stop-session", phase="result", ok=False, error=_err(e))
        return {"stopped": False, "error": _err(e)}
    audit.record(**base, channel="claude:stop-session", phase="result", ok=True)
    return {"stopped": True, "result": r}


async def session_cleanup(
    fleet: Fleet,
    host: str,
    confirm: bool = False,
    dry_run: bool = True,
    session_id: str | None = None,
    min_idle_s: float = 120,
) -> dict:
    """Evaluate orchestrated sessions (and Claude sessions superseded by failover) and clean up."""
    hc = fleet.config.host(host)
    if not fleet.orchestrate_enabled(host):
        raise WriteRefused(f"orchestrate tier is disabled for host {host!r}")
    if not dry_run:
        _orch_guard(fleet, host, confirm)
        if not hc.auto_cleanup:
            raise WriteRefused(f"host {host!r}: auto_cleanup is not enabled in its config (dry_run works)")
    c = fleet.client(host)
    ws = await _workspace(c)
    jev = Jev(fleet.config.jev)
    audit = Audit(fleet.config.safety)
    entries = registry.list_entries(host)
    successors = {
        e["failover_of"]: e
        for e in entries
        if e.get("failover_of") and e.get("status") in ("active", "starting")
    }
    live = {"active", "removed", "superseded"}
    cands = [e for e in entries if e.get("status") in live]
    # Claude GUI sessions that were failed over (not in the registry themselves)
    reg_ids = {e.get("session_id") for e in entries}
    for old in successors:
        if old not in reg_ids:
            t = next((x for x in ws.get("terminals") or [] if x.get("id") == old), None)
            if t:
                cands.append(
                    {
                        "session_id": old,
                        "status": "gui",
                        "workspace_id": t.get("workspaceId"),
                        "agent_preset": t.get("agentPreset"),
                    }
                )
    if session_id:
        cands = [e for e in cands if str(e.get("session_id", "")).startswith(session_id)]
        if not cands:
            raise WriteRefused("session is not an orchestrated / failed-over session on this host")
    rows = []
    for e in cands:
        try:
            r = await _evaluate(fleet, host, e, ws, jev, min_idle_s, successors)
        except BatError as ex:
            r = {
                "session_id": e.get("session_id"),
                "decision": "ESCALATE_TO_TED",
                "reasons": [f"evaluation error: {_err(ex)}"],
            }
        if e.get("status") == "removed" and not r.get("loaded") and r.get("decision") == "CLEAN_ONLY":
            r["noop"] = True  # nothing left to do; hidden from the summary
        audit.record(
            actor=fleet.actor,
            tool="session_cleanup",
            host=host,
            session_id=str(r.get("session_id")) + "#cleanup",
            phase="decision",
            decision=r.get("decision"),
            reasons=r.get("reasons"),
            dry_run=dry_run,
        )
        rows.append(r)
    if not dry_run:
        for r in rows:
            sid = r["session_id"]
            acts: list[str] = []
            d = r.get("decision")
            try:
                if d == "MERGE_AND_CLEAN":
                    m = await worktree_merge(fleet, host, sid, confirm=True)
                    if not m.get("merged_now"):
                        r["decision"] = "ESCALATE_TO_TED"
                        r["reasons"].append(f"merge refused: {m.get('reason')}")
                        continue
                    acts.append(f"merged {r.get('branch')} -> {m.get('source_branch')}")
                if r.get("decision") in ("MERGE_AND_CLEAN", "CLEAN_ONLY") and r.get("remove_worktree"):
                    x = await worktree_remove(fleet, host, sid, confirm=True, delete_branch=False)
                    if not x.get("removed"):
                        r["reasons"].append(f"remove refused: {x.get('reason')}")
                        r["stop"] = False
                    else:
                        acts.append(f"worktree removed (branch {r.get('branch')} kept)")
                if r.get("decision") in ("MERGE_AND_CLEAN", "CLEAN_ONLY") and r.get("stop"):
                    s = await _stop(fleet, host, sid, audit)
                    acts.append(
                        "agent stopped"
                        if s.get("stopped")
                        else f"not stopped: {s.get('reason') or s.get('error')}"
                    )
                if r.get("decision") in ("MERGE_AND_CLEAN", "CLEAN_ONLY") and registry.get(host, sid):
                    registry.update(host, sid, status="merged" if d == "MERGE_AND_CLEAN" else "cleaned")
            except BatError as ex:
                r["reasons"].append(f"action error: {_err(ex)}")
            r["actions"] = acts
            audit.record(
                actor=fleet.actor,
                tool="session_cleanup",
                host=host,
                session_id=sid + "#cleanup",
                phase="done",
                decision=r.get("decision"),
                actions=acts,
            )
    esc = [r for r in rows if r.get("decision") == "ESCALATE_TO_TED"]
    summary = None
    if esc:
        summary = f"{len(esc)} item(s) need Ted on {host}: " + "; ".join(
            f"{r['session_id'][:8]} {r.get('workspace') or ''} {r.get('branch') or ''}: {' / '.join(r.get('reasons') or [])}"
            for r in esc
        )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("decision", "?")] = counts.get(r.get("decision", "?"), 0) + 1
    return {
        "host": host,
        "dry_run": dry_run,
        "jev": jev.status(),
        "decisions": rows,
        "counts": counts,
        "escalation_summary": summary,
        "push": "not performed: BAT's remote protocol has no push/PR channel; merges are local to the host's "
        "main checkout (push or open a PR from the host if the repo needs it)",
    }
