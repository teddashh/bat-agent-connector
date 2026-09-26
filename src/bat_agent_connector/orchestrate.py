"""Worktree status (read tier) and the opt-in orchestrate tier.

BAT 3.2.12 host semantics this module relies on (see docs/ORCHESTRATE.md):

* ``worktree:create {sessionId, cwd, installPnpm}``: the HOST picks the folder
  (``<git root>/.bat-worktrees/<8 hex>``) and branch (``bat/worktree-<8 hex>``);
  a client cannot choose the branch name.
* ``claude:start-session {sessionId, options}``: Codex when ``options.agentPreset``
  is a codex preset, otherwise Claude (Node sidecar). Worktree sessions pass
  ``useWorktree/worktreePath/worktreeBranch`` with ``cwd`` = the worktree folder.
* ``worktree:status`` returns diff/branch/sourceBranch/merged/mergedKind
  (ancestor | patch-equivalent | ahead | diverged | unknown) from host memory.
* ``worktree:merge`` runs ``git checkout <source>`` (if needed) + ``merge --no-ff``
  in the MAIN checkout and does not abort on conflicts, so we only call it when the
  merge is provably conflict-free (mergedKind == ahead) and the main checkout is
  clean and already on the source branch.
* ``worktree:remove`` always force-removes the folder; ``deleteBranch`` runs
  ``git branch -D``. We pre-check dirty files and unmerged commits.
* A started session gets no GUI tab unless it is appended to the workspace
  document (``workspace:save``, whole-document replace). That is opt-in
  (``orchestrate_register_tabs``) and done append-only with verification.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from . import registry
from .errors import BatError, WriteRefused
from .fleet import Fleet
from .safety import Audit
from .service import _err, _meta, _resolve_session, _workspace, _write_lock, agent_kind

MERGED_KINDS = {"ancestor", "patch-equivalent"}


def diff_stats(diff: str | None) -> dict:
    files, add, dele = 0, 0, 0
    for line in (diff or "").splitlines():
        if line.startswith("diff --git "):
            files += 1
        elif line.startswith("+") and not line.startswith("+++"):
            add += 1
        elif line.startswith("-") and not line.startswith("---"):
            dele += 1
    return {"files": files, "additions": add, "deletions": dele}


async def _git_dirty(c, cwd: str | None) -> list[dict] | None:
    if not cwd:
        return None
    root = await c.invoke("git:getRoot", {"cwd": cwd})
    if not root:
        return None  # not a repo / unknown -> caller treats as unknown
    st = await c.invoke("git:status", {"cwd": cwd})
    return [e for e in st or [] if isinstance(e, dict)] if isinstance(st, list) else None


def _origin_cwd(t: dict, ws: dict) -> str | None:
    if t.get("_origin_cwd"):
        return t["_origin_cwd"]
    w = next((x for x in ws.get("workspaces") or [] if x.get("id") == t.get("workspaceId")), {})
    return w.get("folderPath")


async def _wt_status(c, t: dict, *, allow_rehydrate: bool) -> tuple[dict | None, bool]:
    st = await c.invoke("worktree:status", {"sessionId": t["id"]})
    if isinstance(st, dict):
        return st, False
    snap = await c.invoke("claude:get-worktree-status", {"sessionId": t["id"]})
    if isinstance(snap, dict) and snap:
        return snap, False
    if allow_rehydrate and t.get("worktreePath") and t.get("worktreeBranch"):
        await c.invoke(
            "worktree:rehydrate",
            {
                "sessionId": t["id"],
                "cwd": t.get("_origin_cwd") or t.get("cwd"),
                "worktreePath": t["worktreePath"],
                "branchName": t["worktreeBranch"],
            },
        )
        st = await c.invoke("worktree:status", {"sessionId": t["id"]})
        return (st if isinstance(st, dict) else None), True
    return None, False


def _summ(host: str, t: dict, st: dict | None, include_diff: bool, max_diff_chars: int) -> dict:
    d: dict[str, Any] = {
        "host": host,
        "session_id": t.get("id"),
        "agent_kind": agent_kind(t.get("agentPreset")),
        "worktree_path": (st or {}).get("worktreePath") or t.get("worktreePath"),
        "branch": (st or {}).get("branchName") or t.get("worktreeBranch"),
        "source_branch": (st or {}).get("sourceBranch"),
        "merged": (st or {}).get("merged"),
        "merged_kind": (st or {}).get("mergedKind"),
        "tracked_by_host": st is not None,
        "diff_stats": diff_stats((st or {}).get("diff")),
    }
    if include_diff and st:
        diff = st.get("diff") or ""
        d["diff"] = diff[:max_diff_chars]
        d["diff_truncated"] = len(diff) > max_diff_chars
    if st is None:
        d["note"] = (
            "host has no worktree state for this session (e.g. after a host restart); orchestrate tier can rehydrate"
        )
    return d


# --------------------------------------------------------------------------- read tier
async def worktree_status(fleet: Fleet, host: str, workspace: str | None = None) -> dict:
    """All worktree sessions on a host (tabs with a worktree + orchestrated sessions)."""
    c = fleet.client(host)
    ws = await _workspace(c)
    ws_by_id = {w.get("id"): w for w in ws.get("workspaces") or []}
    terms = [t for t in ws.get("terminals") or [] if t.get("worktreePath")]
    known = {t.get("id") for t in terms}
    from .service import registry_terminal

    for e in registry.list_entries(host, active_only=True):
        if e.get("session_id") not in known and e.get("worktree_path"):
            terms.append(registry_terminal(e))
    if workspace:
        wl = workspace.lower()
        terms = [
            t
            for t in terms
            if wl in str((ws_by_id.get(t.get("workspaceId")) or {}).get("name", "")).lower()
            or str(t.get("workspaceId", "")).startswith(workspace)
        ]
    out = []
    for t in terms:
        try:
            st, _ = await _wt_status(c, t, allow_rehydrate=False)
            row = _summ(host, t, st, False, 0)
        except BatError as e:
            row = {"host": host, "session_id": t.get("id"), "error": _err(e)}
        row["workspace"] = (ws_by_id.get(t.get("workspaceId")) or {}).get("name")
        row["orchestrated"] = registry.get(host, t.get("id")) is not None
        out.append(row)
    return {"host": host, "worktrees": out, "count": len(out)}


async def session_worktree_status(
    fleet: Fleet, host: str, session_id: str, include_diff: bool = False, max_diff_chars: int = 20000
) -> dict:
    c = fleet.client(host)
    t, ws = await _resolve_session(c, session_id)
    max_diff_chars = max(0, min(100_000, int(max_diff_chars)))
    st, _ = await _wt_status(c, t, allow_rehydrate=False)
    d = _summ(host, t, st, include_diff, max_diff_chars)
    wt = d["worktree_path"]
    dirty = await _git_dirty(c, wt) if wt else None
    d["worktree_dirty_files"] = None if dirty is None else len(dirty)
    d["worktree_dirty_preview"] = [f"{e.get('status')} {e.get('file')}" for e in (dirty or [])[:20]]
    origin = _origin_cwd(t, ws)
    if origin:
        d["main_checkout_branch"] = await c.invoke("git:branch", {"cwd": origin})
        md = await _git_dirty(c, origin)
        d["main_checkout_dirty_files"] = None if md is None else len(md)
    meta = await _meta(c, t["id"])
    d["loaded"] = meta is not None
    d["streaming"] = bool((meta or {}).get("isStreaming"))
    return d


# --------------------------------------------------------------------------- orchestrate tier
def _guard(fleet: Fleet, host: str, confirm: bool) -> None:
    if not fleet.orchestrate_enabled(host):
        raise WriteRefused(
            f"orchestrate tier is disabled for host {host!r} (needs writes = true and orchestrate = true)"
        )
    if confirm is not True:
        raise WriteRefused("orchestrate tools require confirm=true")


def permission_options(agent: str, mode: str, claude_mode: str | None = None) -> dict:
    """Start/resume options that mirror BAT's GUI permission setting.

    ``allow_all`` = what BAT does with "allow bypass permissions" on: Claude runs in
    ``bypassPermissions``; Codex starts with sandbox ``danger-full-access`` and approval ``never``.
    ``default`` sends nothing (the agent asks before tools, BAT's conservative default).
    """
    if agent == "claude":
        if claude_mode:
            return {"permissionMode": claude_mode}
        return {"permissionMode": "bypassPermissions"} if mode == "allow_all" else {}
    if mode == "allow_all":
        return {"codexSandboxMode": "danger-full-access", "codexApprovalPolicy": "never"}
    return {}


def registry_permission_fields(opts: dict) -> dict:
    ap = {}
    if opts.get("codexSandboxMode"):
        ap["sandboxMode"] = opts["codexSandboxMode"]
    if opts.get("codexApprovalPolicy"):
        ap["approvalPolicy"] = opts["codexApprovalPolicy"]
    return {"permission_mode_claude": opts.get("permissionMode"), "agent_params": ap or None}


PRESETS = {
    ("claude", True): "claude-code-worktree",
    ("claude", False): "claude-code",
    ("codex", True): "codex-agent-worktree",
    ("codex", False): "codex-agent",
}


async def session_start(
    fleet: Fleet,
    host: str,
    workspace: str,
    agent: str = "claude",
    confirm: bool = False,
    prompt: str | None = None,
    model: str | None = None,
    use_worktree: bool = True,
    title: str | None = None,
    permission_mode: str | None = None,
) -> dict:
    _guard(fleet, host, confirm)
    if agent not in ("claude", "codex"):
        raise WriteRefused("agent must be claude or codex")
    if prompt is not None and len(prompt) > 20_000:
        raise WriteRefused("prompt is longer than 20000 characters")
    hc = fleet.config.host(host)
    c = fleet.client(host)
    audit = Audit(fleet.config.safety)
    ws = await _workspace(c)
    wsl = [w for w in ws.get("workspaces") or [] if w.get("id") == workspace or w.get("name") == workspace]
    if not wsl:
        wsl = [w for w in ws.get("workspaces") or [] if workspace.lower() in str(w.get("name", "")).lower()]
    if len(wsl) != 1:
        raise WriteRefused(
            f"workspace {workspace!r} matched {len(wsl)} workspaces on {host}; use the exact name or id"
        )
    w = wsl[0]
    folder = str(w.get("folderPath") or "").strip()
    if not folder:
        raise WriteRefused("workspace has no folderPath")
    preset = PRESETS[(agent, bool(use_worktree))]
    if agent == "codex" and not model and hc.codex_model:
        model = hc.codex_model
    sid = str(uuid.uuid4())
    async with _write_lock():
        audit.check_rate(host, "#orchestrate-start-" + sid)
        registry.reserve(
            host,
            {
                "session_id": sid,
                "workspace_id": w.get("id"),
                "workspace_name": w.get("name"),
                "agent_preset": preset,
                "origin_cwd": folder,
                "model": model,
                "title": title,
            },
            hc.orchestrate_max_sessions,
        )
        base = {"actor": fleet.actor, "tool": "session_start", "host": host, "session_id": sid}
        wt: dict = {}
        try:
            if use_worktree:
                audit.record(**base, channel="worktree:create", phase="attempt")
                wt = await c.invoke(
                    "worktree:create", {"sessionId": sid, "cwd": folder, "installPnpm": False}
                )
                if not isinstance(wt, dict) or wt.get("success") is False or not wt.get("worktreePath"):
                    err = (wt or {}).get("error") if isinstance(wt, dict) else "unexpected reply"
                    audit.record(**base, channel="worktree:create", phase="result", ok=False, error=str(err))
                    raise WriteRefused(f"worktree:create failed: {err}")
                audit.record(
                    **base, channel="worktree:create", phase="result", ok=True, branch=wt.get("branchName")
                )
            cwd = wt.get("worktreePath") or folder
            opts = {
                "cwd": cwd,
                "agentPreset": preset,
                "workspaceId": w.get("id"),
                "workspaceName": w.get("name"),
            }
            if model:
                opts["model"] = model
            opts.update(permission_options(agent, hc.default_permission_mode, permission_mode))
            if use_worktree:
                opts.update(
                    useWorktree=True, worktreePath=wt["worktreePath"], worktreeBranch=wt.get("branchName")
                )
            audit.record(**base, channel="claude:start-session", phase="attempt", preset=preset)
            try:
                await c.invoke("claude:start-session", {"sessionId": sid, "options": opts})
            except BatError as e:
                audit.record(**base, channel="claude:start-session", phase="result", ok=False, error=_err(e))
                if use_worktree:  # fresh worktree with no commits: safe to roll back
                    await c.invoke("worktree:remove", {"sessionId": sid, "deleteBranch": True})
                    audit.record(**base, channel="worktree:remove", phase="rollback", ok=True)
                raise
            audit.record(**base, channel="claude:start-session", phase="result", ok=True)
        except BaseException:
            registry.update(host, sid, status="failed")
            raise
        registry.update(
            host,
            sid,
            status="active",
            cwd=cwd,
            worktree_path=wt.get("worktreePath"),
            branch=wt.get("branchName"),
            **registry_permission_fields(opts),
        )
        tab = None
        if hc.orchestrate_register_tabs:
            term = {
                "id": sid,
                "workspaceId": w.get("id"),
                "title": title or f"{agent} (orchestrated)",
                "type": "terminal",
                "cwd": cwd,
                "agentPreset": preset,
            }
            if model:
                term["model"] = model
            pf = registry_permission_fields(opts)
            if pf["permission_mode_claude"]:
                term["permissionMode"] = pf["permission_mode_claude"]
            if pf["agent_params"]:
                term["agentParams"] = pf["agent_params"]
            if use_worktree:
                term.update(worktreePath=wt["worktreePath"], worktreeBranch=wt.get("branchName"))
            try:
                tab = await c.append_workspace_terminal(hc.profile_id, term)
            except BatError as e:
                tab = {"appended": False, "error": _err(e)}
            audit.record(
                **base,
                channel="workspace:save",
                phase="append-terminal",
                ok=bool(tab.get("appended")),
                lost_terminals=len(tab.get("lost_terminals") or []),
            )
            registry.update(host, sid, tab_registered=bool(tab.get("appended")))
        mid = None
        if prompt:
            mid = f"batc-{uuid.uuid4()}"
            audit.record(**base, channel="claude:send-message", phase="attempt", message_id=mid, text=prompt)
            try:
                await c.invoke(
                    "claude:send-message", {"sessionId": sid, "prompt": prompt, "clientMessageId": mid}
                )
                audit.record(**base, channel="claude:send-message", phase="result", ok=True, message_id=mid)
            except BatError as e:
                audit.record(**base, channel="claude:send-message", phase="result", ok=False, error=_err(e))
                return {
                    "host": host,
                    "session_id": sid,
                    "started": True,
                    "prompt_sent": False,
                    "error": _err(e),
                    "worktree_path": wt.get("worktreePath"),
                    "branch": wt.get("branchName"),
                    "tab": tab,
                }
    return {
        "host": host,
        "session_id": sid,
        "started": True,
        "agent_preset": preset,
        "workspace": w.get("name"),
        "worktree_path": wt.get("worktreePath"),
        "branch": wt.get("branchName"),
        "tab": tab,
        "prompt_sent": bool(prompt),
        "message_id": mid,
        "permissions": hc.default_permission_mode if not permission_mode else permission_mode,
        "note": None
        if tab and tab.get("appended")
        else "no GUI tab registered (orchestrate_register_tabs=false); tracked in the local registry",
    }


async def worktree_merge(fleet: Fleet, host: str, session_id: str, confirm: bool = False) -> dict:
    _guard(fleet, host, confirm)
    c = fleet.client(host)
    audit = Audit(fleet.config.safety)
    async with _write_lock():
        t, ws = await _resolve_session(c, session_id)
        sid = t["id"]
        audit.check_rate(host, sid + "#merge")
        st, rehydrated = await _wt_status(c, t, allow_rehydrate=True)
        if not st:
            raise WriteRefused("host does not track a worktree for this session")
        kind = st.get("mergedKind")
        report = _summ(host, t, st, False, 0)
        report["rehydrated"] = rehydrated
        if kind in MERGED_KINDS:
            return {**report, "merged_now": False, "reason": "already merged"}
        if kind == "unknown":
            return {
                **report,
                "merged_now": False,
                "reason": "no new commits on the worktree branch (or unknown state)",
            }
        if kind != "ahead":
            return {
                **report,
                "merged_now": False,
                "reason": f"branch is {kind}: merging could conflict. Ask the session to rebase onto "
                f"{st.get('sourceBranch')} (or merge manually); never forced",
            }
        meta = await _meta(c, sid)
        if (meta or {}).get("isStreaming"):
            return {**report, "merged_now": False, "reason": "session is still streaming; wait for turn end"}
        dirty = await _git_dirty(c, st.get("worktreePath"))
        if dirty is None:
            return {**report, "merged_now": False, "reason": "cannot read worktree git status"}
        if dirty:
            return {
                **report,
                "merged_now": False,
                "worktree_dirty_files": len(dirty),
                "reason": "worktree has uncommitted changes (they would not be merged); ask the session to commit",
            }
        origin = _origin_cwd(t, ws)
        if not origin:
            return {**report, "merged_now": False, "reason": "cannot determine the main checkout folder"}
        cur = await c.invoke("git:branch", {"cwd": origin})
        if cur != st.get("sourceBranch"):
            return {
                **report,
                "merged_now": False,
                "reason": f"main checkout is on {cur!r}, not {st.get('sourceBranch')!r}; BAT would switch "
                "branches there, so refusing",
            }
        mdirty = await _git_dirty(c, origin)
        if mdirty is None or mdirty:
            return {
                **report,
                "merged_now": False,
                "reason": "main checkout has uncommitted changes (or status unreadable); refusing",
            }
        base = {"actor": fleet.actor, "tool": "worktree_merge", "host": host, "session_id": sid + "#merge"}
        audit.record(**base, channel="worktree:merge", phase="attempt", branch=st.get("branchName"))
        r = await c.invoke("worktree:merge", {"sessionId": sid, "strategy": "merge"})
        ok = isinstance(r, dict) and r.get("success") is True
        audit.record(
            **base,
            channel="worktree:merge",
            phase="result",
            ok=ok,
            error=None if ok else str((r or {}).get("error") if isinstance(r, dict) else r)[:300],
        )
        after = await _git_dirty(c, origin)
        return {
            **report,
            "merged_now": ok,
            "result": r,
            "main_checkout_clean_after": after == [] if after is not None else None,
        }


async def worktree_remove(
    fleet: Fleet,
    host: str,
    session_id: str,
    confirm: bool = False,
    delete_branch: bool = False,
    allow_unmerged: bool = False,
    discard_uncommitted: bool = False,
) -> dict:
    _guard(fleet, host, confirm)
    c = fleet.client(host)
    audit = Audit(fleet.config.safety)
    async with _write_lock():
        t, _ = await _resolve_session(c, session_id)
        sid = t["id"]
        audit.check_rate(host, sid + "#remove")
        st, rehydrated = await _wt_status(c, t, allow_rehydrate=True)
        if not st:
            raise WriteRefused("host does not track a worktree for this session")
        report = _summ(host, t, st, False, 0)
        meta = await _meta(c, sid)
        if (meta or {}).get("isStreaming"):
            return {
                **report,
                "removed": False,
                "reason": "session is still streaming; interrupt or wait first",
            }
        dirty = await _git_dirty(c, st.get("worktreePath"))
        if dirty is None and not discard_uncommitted:
            return {
                **report,
                "removed": False,
                "reason": "cannot read worktree git status; pass discard_uncommitted=true to override",
            }
        if dirty and not discard_uncommitted:
            return {
                **report,
                "removed": False,
                "worktree_dirty_files": len(dirty),
                "reason": "worktree has uncommitted changes; BAT force-removes the folder. Pass discard_uncommitted=true to accept losing them",
            }
        kind = st.get("mergedKind")
        has_unmerged = kind in ("ahead", "diverged")
        if delete_branch and has_unmerged and not allow_unmerged:
            return {
                **report,
                "removed": False,
                "reason": f"branch has unmerged commits ({kind}); keep the branch (delete_branch=false) or pass allow_unmerged=true",
            }
        base = {"actor": fleet.actor, "tool": "worktree_remove", "host": host, "session_id": sid + "#remove"}
        audit.record(
            **base,
            channel="worktree:remove",
            phase="attempt",
            delete_branch=delete_branch,
            unmerged=has_unmerged,
            dirty=len(dirty or []),
        )
        wt_path = st.get("worktreePath") or t.get("worktreePath")
        branch = st.get("branchName") or t.get("worktreeBranch")
        # BAT's worktree:remove silently "succeeds" when its worktree manager has no record for the session
        # (e.g. a failover session that reused an existing worktree, or after a host restart). Register first.
        if not isinstance(await c.invoke("worktree:status", {"sessionId": sid}), dict) and wt_path and branch:
            e = registry.get(host, sid) or {}
            await c.invoke(
                "worktree:rehydrate",
                {
                    "sessionId": sid,
                    "cwd": e.get("origin_cwd") or t.get("_origin_cwd") or t.get("cwd"),
                    "worktreePath": wt_path,
                    "branchName": branch,
                },
            )
            rehydrated = True
        r = await c.invoke("worktree:remove", {"sessionId": sid, "deleteBranch": bool(delete_branch)})
        ok = isinstance(r, dict) and r.get("success") is True
        still_there = False
        if ok and wt_path:
            root = await c.invoke("git:getRoot", {"cwd": wt_path})
            still_there = bool(root) and str(root).rstrip("/") == str(wt_path).rstrip("/")
            ok = not still_there
        audit.record(**base, channel="worktree:remove", phase="result", ok=ok, still_there=still_there)
        if registry.get(host, sid):
            registry.update(host, sid, status="removed" if ok else "active")
    return {
        **report,
        "removed": ok,
        **({"reason": "host reported success but the worktree folder is still there"} if still_there else {}),
        "branch_deleted": bool(delete_branch and ok),
        "rehydrated": rehydrated,
        "note": "the agent session itself is not stopped (the connector never exposes stop/reset)",
    }


# --------------------------------------------------------------------------- fan-out planning (CLI/skill helper)
_TASK_RE = re.compile(r"^\s*(?:[-*]\s+\[\s?\]\s+|\d+[.)]\s+|#{2,3}\s+)(.+?)\s*$")


def fanout_plan(plan_text: str, *, max_tasks: int = 8, context_chars: int = 1500) -> dict:
    """Split a markdown plan into independent task prompts.

    Tasks are unchecked checklist items (``- [ ] ...``), numbered items, or ``##``/``###``
    headings (with the text under them). The orchestrator should review and edit the
    result; it is a starting point, not a decision.
    """
    lines = plan_text.splitlines()
    tasks: list[dict] = []
    cur: dict | None = None
    for ln in lines:
        m = _TASK_RE.match(ln)
        if m:
            if cur:
                tasks.append(cur)
            cur = {"title": m.group(1).strip()[:200], "body": []}
        elif cur is not None and ln.strip():
            cur["body"].append(ln.rstrip())
    if cur:
        tasks.append(cur)
    header = "\n".join(lines[:40])[:context_chars]
    out = []
    for i, tk in enumerate(tasks[:max_tasks], 1):
        body = "\n".join(tk["body"])[:4000]
        prompt = (
            f"You are one of several parallel agents, working in your own git worktree/branch.\n"
            f"Task {i}/{min(len(tasks), max_tasks)}: {tk['title']}\n\n{body}\n\n"
            f"Plan context (excerpt):\n{header}\n\n"
            "Rules: stay within this task's scope; do not edit files other tasks own; commit your work on "
            "this branch with clear messages; run the relevant tests; when done, reply with a short summary, "
            "the files changed and test results. Do not merge or push."
        )
        out.append({"index": i, "title": tk["title"], "prompt": prompt})
    return {"tasks": out, "count": len(out), "total_found": len(tasks), "truncated": len(tasks) > max_tasks}


def read_plan(path: str) -> str:
    p = Path(path).expanduser()
    if p.stat().st_size > 512 * 1024:
        raise BatError("plan file is larger than 512 KiB")
    return p.read_text()
