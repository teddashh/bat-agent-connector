"""High-level operations shared by the MCP server and the CLI.

Every function returns JSON-serializable dicts. Token values never appear in
results; errors are redacted.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
import uuid
from typing import Any

from . import registry
from .client import BatClient, event_session_id
from .errors import BatError, InvokeError, WriteRefused
from .fleet import Fleet
from .redact import redact
from .safety import Audit
from .summarize import clip, iso_local, summarize_message, summarize_pending, ts_to_ms

MAX_LAST_N = 100
MAX_READ_CHARS = 60_000
MAX_PROMPT_CHARS = 20_000
_write_locks: dict[int, asyncio.Lock] = {}


def _write_lock() -> asyncio.Lock:
    loop_id = id(asyncio.get_running_loop())
    lock = _write_locks.get(loop_id)
    if lock is None:
        lock = _write_locks[loop_id] = asyncio.Lock()
    return lock


def _err(e: BaseException) -> str:
    if isinstance(e, BatError):
        return redact(e)
    return redact(f"{type(e).__name__}: {e}")


def agent_kind(preset: str | None) -> str | None:
    if not preset:
        return None
    p = preset.lower()
    if p.startswith("codex"):
        return "codex"
    if p.startswith("claude"):
        return "claude"
    return p


def _age(ms: int | None) -> str | None:
    if not ms:
        return None
    s = max(0, time.time() - ms / 1000)
    if s < 90:
        return f"{int(s)}s"
    if s < 5400:
        return f"{int(s / 60)}m"
    if s < 172800:
        return f"{s / 3600:.1f}h"
    return f"{int(s / 86400)}d"


def _hosts(fleet: Fleet, host: str | None) -> list[str]:
    if host:
        fleet.config.host(host)
        return [host]
    return list(fleet.config.hosts)


async def _gather_limited(coros: list, limit: int = 8) -> list:
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            try:
                return await c
            except Exception as e:  # noqa: BLE001
                return e

    return await asyncio.gather(*(run(c) for c in coros))


async def _workspace(c: BatClient) -> dict:
    raw = await c.invoke("workspace:load", {"profileId": c.host.profile_id})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    return raw if isinstance(raw, dict) else {}


def _agent_terminals(ws: dict) -> list[dict]:
    return [t for t in ws.get("terminals") or [] if isinstance(t, dict) and t.get("agentPreset")]


async def _meta(c: BatClient, sid: str) -> dict | None:
    m = await c.invoke("claude:get-session-meta", {"sessionId": sid})
    return m if isinstance(m, dict) else None


def _state_safe(kind: str | None, meta: dict | None) -> bool:
    """get-session-state on a Claude record without cwd makes the sidecar drop that record; avoid it."""
    if not meta:
        return False
    if kind == "claude":
        return bool(str(meta.get("cwd") or "").strip())
    return True


def registry_terminal(e: dict) -> dict:
    """Synthesize a workspace-like terminal record for a tab-less orchestrated session."""
    return {
        "id": e.get("session_id"),
        "agentPreset": e.get("agent_preset"),
        "cwd": e.get("cwd"),
        "workspaceId": e.get("workspace_id"),
        "title": e.get("title") or "orchestrated",
        "model": e.get("model"),
        "worktreePath": e.get("worktree_path"),
        "worktreeBranch": e.get("branch"),
        "_orchestrated": True,
        "_origin_cwd": e.get("origin_cwd"),
    }


async def _resolve_session(c: BatClient, session_id: str, ws: dict | None = None) -> tuple[dict, dict]:
    ws = ws if ws is not None else await _workspace(c)
    sid = (session_id or "").strip()
    if len(sid) < 6:
        raise BatError("session_id must be the full id or a unique prefix of at least 6 characters")
    terms = ws.get("terminals") or []
    exact = [t for t in terms if t.get("id") == sid]
    matches = exact or [t for t in terms if str(t.get("id", "")).startswith(sid)]
    if not matches:
        regs = registry.find_prefix(c.host.name, sid)
        if len(regs) == 1:
            return registry_terminal(regs[0]), ws
        raise BatError(f"session {sid!r} not found on host {c.host.name}")
    if len(matches) > 1:
        raise BatError(f"session prefix {sid!r} is ambiguous on host {c.host.name}")
    t = matches[0]
    if not t.get("agentPreset"):
        raise BatError(f"terminal {t.get('id')} is a plain shell, not an agent session")
    return t, ws


# --------------------------------------------------------------------------- read tools
async def hosts_list(fleet: Fleet, probe: bool = True) -> dict:
    async def one(name: str) -> dict:
        hc = fleet.config.host(name)
        d: dict[str, Any] = {
            "name": name,
            "url": hc.url,
            "writes_enabled": fleet.writes_enabled(name),
            "orchestrate_enabled": fleet.orchestrate_enabled(name),
            "token_ref_kind": hc.token_kind,
            "token_available": hc.token_available(),
        }
        if probe:
            c = fleet.client(name)
            try:
                rtt = await c.ping()
                d.update(
                    reachable=True,
                    server_version=c.auth_info.get("serverVersion"),
                    protocol=c.auth_info.get("protocol"),
                    ping_ms=round(rtt),
                )
            except Exception as e:  # noqa: BLE001
                d.update(reachable=False, error=_err(e))
        return d

    items = await asyncio.gather(*(one(n) for n in fleet.config.hosts))
    return {"hosts": list(items), "count": len(items), "read_only": not fleet.any_writes}


async def host_status(fleet: Fleet, host: str) -> dict:
    c = fleet.client(host)
    was_connected = c.connected
    await c.connect()
    pings = [round(await c.ping()) for _ in range(3)]
    version = await c.invoke("app:get-version", {})
    profiles = await c.invoke("profile:list", {})
    ws = await _workspace(c)
    agents = _agent_terminals(ws)
    metas = await _gather_limited([_meta(c, t["id"]) for t in agents])
    loaded = [m for m in metas if isinstance(m, dict)]
    streaming = [m for m in loaded if m.get("isStreaming") is True]
    kinds: dict[str, int] = {}
    for t in agents:
        k = agent_kind(t.get("agentPreset")) or "?"
        kinds[k] = kinds.get(k, 0) + 1
    return {
        "host": host,
        "server_version": c.auth_info.get("serverVersion") or version,
        "app_version": version,
        "protocol": c.auth_info.get("protocol"),
        "capabilities": c.auth_info.get("capabilities"),
        "latency": {
            "connect_ms": None if was_connected or c.connect_ms is None else round(c.connect_ms),
            "auth_ms": None if was_connected or c.auth_ms is None else round(c.auth_ms),
            "ping_ms": pings,
            "ping_median_ms": statistics.median(pings),
        },
        "profiles": len((profiles or {}).get("profiles") or []) if isinstance(profiles, dict) else None,
        "workspaces": len(ws.get("workspaces") or []),
        "terminals": len(ws.get("terminals") or []),
        "agent_sessions": len(agents),
        "agent_sessions_by_kind": kinds,
        "loaded": len(loaded),
        "streaming": len(streaming),
        "meta_errors": sum(1 for m in metas if isinstance(m, Exception)),
        "writes_enabled": fleet.writes_enabled(host),
        "orchestrate_enabled": fleet.orchestrate_enabled(host),
    }


async def workspaces_list(fleet: Fleet, host: str | None = None) -> dict:
    async def one(name: str) -> tuple[str, Any]:
        try:
            ws = await _workspace(fleet.client(name))
        except Exception as e:  # noqa: BLE001
            return name, e
        terms = ws.get("terminals") or []
        out = []
        for w in ws.get("workspaces") or []:
            mine = [t for t in terms if t.get("workspaceId") == w.get("id")]
            out.append(
                {
                    "host": name,
                    "workspace_id": w.get("id"),
                    "name": w.get("name"),
                    "folder": w.get("folderPath"),
                    "terminals": len(mine),
                    "agent_sessions": sum(1 for t in mine if t.get("agentPreset")),
                    "active": w.get("id") == ws.get("activeWorkspaceId"),
                }
            )
        return name, out

    res = await asyncio.gather(*(one(n) for n in _hosts(fleet, host)))
    items, errors = [], {}
    for name, r in res:
        if isinstance(r, Exception):
            errors[name] = _err(r)
        else:
            items.extend(r)
    return {"workspaces": items, "count": len(items), "errors": errors}


async def _host_sessions(
    fleet: Fleet,
    name: str,
    workspace: str | None,
    agent: str | None,
    check_pending: str,
    activity_sources: bool,
) -> list[dict]:
    c = fleet.client(name)
    ws = await _workspace(c)
    ws_by_id = {w.get("id"): w for w in ws.get("workspaces") or []}
    terms = _agent_terminals(ws)
    known = {t.get("id") for t in terms}
    orchestrated_ids = {e.get("session_id") for e in registry.list_entries(name)}
    for e in registry.list_entries(name, active_only=True):
        if e.get("session_id") not in known:
            terms.append(registry_terminal(e))
    if workspace:
        wl = workspace.lower()
        terms = [
            t
            for t in terms
            if str(t.get("workspaceId", "")).startswith(workspace)
            or wl in str((ws_by_id.get(t.get("workspaceId")) or {}).get("name", "")).lower()
        ]
    if agent:
        terms = [t for t in terms if agent_kind(t.get("agentPreset")) == agent.lower()]
    metas = await _gather_limited([_meta(c, t["id"]) for t in terms])
    recent_attention = {
        e.get("sessionId")
        for e in c.recent_events
        if e.get("channel") in ("agent:ask-user", "agent:permission-request")
    }
    rows: list[dict] = []
    for t, m in zip(terms, metas, strict=True):
        meta = m if isinstance(m, dict) else None
        kind = agent_kind(t.get("agentPreset"))
        w = ws_by_id.get(t.get("workspaceId")) or {}
        last_ms = ts_to_ms((meta or {}).get("lastDataAt"))
        row: dict[str, Any] = {
            "host": name,
            "session_id": t.get("id"),
            "workspace": w.get("name"),
            "workspace_id": t.get("workspaceId"),
            "title": t.get("title"),
            "cwd": t.get("cwd") or (meta or {}).get("cwd"),
            "agent_preset": t.get("agentPreset"),
            "agent_kind": kind,
            "model": (meta or {}).get("model") or t.get("model"),
            "loaded": meta is not None,
            "streaming": (meta or {}).get("isStreaming") if meta else False,
            "runtime_status": (meta or {}).get("runtimeStatus"),
            "num_turns": (meta or {}).get("numTurns"),
            "worktree_branch": t.get("worktreeBranch"),
            "orchestrated": t.get("id") in orchestrated_ids,
            "has_tab": not t.get("_orchestrated", False),
            "pending": None,
            "last_activity_ms": last_ms,
            "last_activity_source": "host" if last_ms else None,
        }
        if isinstance(m, Exception):
            row["meta_error"] = _err(m)
        rows.append(row)

    async def fill_archive(row: dict) -> None:
        r = await c.invoke("claude:load-archived", {"sessionId": row["session_id"], "offset": 0, "limit": 1})
        if isinstance(r, dict):
            row["archived_total"] = r.get("total")
            msgs = r.get("messages") or []
            if msgs and isinstance(msgs[-1], dict):
                ms = ts_to_ms(msgs[-1].get("timestamp") or msgs[-1].get("completedAt"))
                if ms and (not row["last_activity_ms"] or ms > row["last_activity_ms"]):
                    row["last_activity_ms"] = ms
                    row["last_activity_source"] = "archive"

    async def fill_pending(row: dict, meta: dict) -> None:
        st = await c.invoke("claude:get-session-state", {"sessionId": row["session_id"]})
        if isinstance(st, dict):
            p = summarize_pending(st.get("pendingAskUser"), "ask_user") or summarize_pending(
                st.get("pendingPermission"), "permission"
            )
            row["pending"] = p
            msgs = st.get("messages") or []
            for mm in reversed(msgs):
                ms = ts_to_ms(mm.get("timestamp") or mm.get("completedAt")) if isinstance(mm, dict) else None
                if ms:
                    if not row["last_activity_ms"] or ms > row["last_activity_ms"]:
                        row["last_activity_ms"] = ms
                        row["last_activity_source"] = "state"
                    break

    async def fill_transcripts(cwd: str, group: list[dict]) -> None:
        # Claude transcript files on the host: timestamp = file mtime (cheap, parsed host-side).
        # Not used for Codex: the host scans every rollout file for that, which can take minutes.
        r = await c.invoke("claude:list-sessions", {"cwd": cwd, "agentKind": "claude"}, timeout=20)
        by_sdk = (
            {e.get("sdkSessionId"): e for e in r or [] if isinstance(e, dict)} if isinstance(r, list) else {}
        )
        for row in group:
            e = by_sdk.get(row.pop("_sdk", None))
            ms = ts_to_ms(e.get("timestamp")) if e else None
            if ms and (not row["last_activity_ms"] or ms > row["last_activity_ms"]):
                row["last_activity_ms"] = ms
                row["last_activity_source"] = "transcript"

    if activity_sources:
        groups: dict[str, list[dict]] = {}
        for row, t in zip(rows, terms, strict=True):
            if row["agent_kind"] == "claude" and row["cwd"] and t.get("sdkSessionId"):
                row["_sdk"] = t.get("sdkSessionId")
                groups.setdefault(row["cwd"], []).append(row)
        await _gather_limited([fill_transcripts(cwd, g) for cwd, g in groups.items()], limit=3)
    for row in rows:
        row.pop("_sdk", None)

    jobs = []
    for row, m in zip(rows, metas, strict=True):
        meta = m if isinstance(m, dict) else None
        if activity_sources and not row["last_activity_ms"]:
            jobs.append(fill_archive(row))
        want_pending = check_pending == "all" or (
            check_pending == "auto"
            and meta is not None
            and (row["streaming"] or row["runtime_status"] or row["session_id"] in recent_attention)
        )
        if want_pending and _state_safe(row["agent_kind"], meta):
            jobs.append(fill_pending(row, meta))
    await _gather_limited(jobs, limit=4)
    return rows


async def sessions_list(
    fleet: Fleet,
    host: str | None = None,
    workspace: str | None = None,
    agent: str | None = None,
    only_loaded: bool = False,
    active_within_hours: float | None = None,
    check_pending: str = "auto",
    activity_sources: bool = True,
    limit: int = 50,
) -> dict:
    if check_pending not in ("auto", "all", "none"):
        raise BatError("check_pending must be auto, all or none")
    names = _hosts(fleet, host)
    res = await asyncio.gather(
        *(_host_sessions(fleet, n, workspace, agent, check_pending, activity_sources) for n in names),
        return_exceptions=True,
    )
    rows, errors = [], {}
    for n, r in zip(names, res, strict=True):
        if isinstance(r, BaseException):
            errors[n] = _err(r)
        else:
            rows.extend(r)
    if only_loaded:
        rows = [r for r in rows if r["loaded"]]
    if active_within_hours is not None:
        cutoff = (time.time() - active_within_hours * 3600) * 1000
        rows = [r for r in rows if (r["last_activity_ms"] or 0) >= cutoff]
    rows.sort(key=lambda r: r["last_activity_ms"] or 0, reverse=True)
    total = len(rows)
    limit = max(1, min(500, int(limit)))
    rows = rows[:limit]
    for r in rows:
        ms = r.pop("last_activity_ms")
        r["last_activity"] = iso_local(ms)
        r["last_activity_age"] = _age(ms)
    return {"sessions": rows, "count": len(rows), "total_matched": total, "errors": errors}


async def session_read(
    fleet: Fleet,
    host: str,
    session_id: str,
    last_n: int = 20,
    offset: int = 0,
    include_tools: bool = False,
    max_chars: int = 12_000,
    max_message_chars: int = 2_000,
) -> dict:
    last_n = max(1, min(MAX_LAST_N, int(last_n)))
    offset = max(0, int(offset))
    max_chars = max(500, min(MAX_READ_CHARS, int(max_chars)))
    max_message_chars = max(100, min(max_chars, int(max_message_chars)))
    c = fleet.client(host)
    t, ws = await _resolve_session(c, session_id)
    sid = t["id"]
    kind = agent_kind(t.get("agentPreset"))
    meta = await _meta(c, sid)
    state = None
    if _state_safe(kind, meta):
        st = await c.invoke("claude:get-session-state", {"sessionId": sid})
        state = st if isinstance(st, dict) else None
    live = [m for m in (state or {}).get("messages") or [] if isinstance(m, dict)]
    live_ids = {m.get("id") for m in live}

    def shown(m: dict) -> bool:
        return summarize_message(m, include_tools=include_tools, max_chars=50) is not None

    newest_first = list(reversed(live))
    want = offset + last_n
    archive_total = None
    arch_off = 0
    raw_budget = 3000
    while sum(1 for m in newest_first if shown(m)) < want and raw_budget > 0:
        chunk = min(200, raw_budget)
        r = await c.invoke("claude:load-archived", {"sessionId": sid, "offset": arch_off, "limit": chunk})
        if not isinstance(r, dict):
            break
        archive_total = r.get("total", archive_total)
        msgs = [m for m in r.get("messages") or [] if isinstance(m, dict)]
        if not msgs:
            break
        for m in reversed(msgs):
            if m.get("id") not in live_ids:
                newest_first.append(m)
        arch_off += len(msgs)
        raw_budget -= len(msgs)
        if not r.get("hasMore"):
            break

    visible = [m for m in newest_first if shown(m)]
    page = visible[offset : offset + last_n]
    out_msgs: list[dict] = []
    used = 0
    truncated = False
    for m in page:  # newest first, so the size cap keeps the most recent messages
        s = summarize_message(m, include_tools=include_tools, max_chars=max_message_chars)
        if s is None:
            continue
        size = len(s.get("text") or "") + 80
        if used + size > max_chars and out_msgs:
            truncated = True
            break
        used += size
        out_msgs.append(s)
    out_msgs.reverse()
    has_more = len(visible) > offset + len(out_msgs) or bool(archive_total and arch_off < archive_total)
    pending = None
    if state:
        pending = summarize_pending(state.get("pendingAskUser"), "ask_user") or summarize_pending(
            state.get("pendingPermission"), "permission"
        )
    w = next((x for x in ws.get("workspaces") or [] if x.get("id") == t.get("workspaceId")), {})
    m = meta or {}
    return {
        "host": host,
        "session_id": sid,
        "workspace": w.get("name"),
        "title": t.get("title"),
        "agent_kind": kind,
        "loaded": meta is not None,
        "streaming": bool((state or {}).get("isStreaming") or m.get("isStreaming")),
        "streaming_text_tail": clip((state or {}).get("streamingText") or "", 1000)[-1000:] or None,
        "pending": pending,
        "meta": {
            "model": m.get("model") or t.get("model"),
            "num_turns": m.get("numTurns"),
            "context_tokens": m.get("contextTokens"),
            "context_window": m.get("contextWindow"),
            "last_data_at": iso_local(ts_to_ms(m.get("lastDataAt"))),
            "cwd": m.get("cwd") or t.get("cwd"),
        },
        "messages": out_msgs,
        "offset": offset,
        "next_offset": offset + len(out_msgs) if has_more else None,
        "truncated_by_size": truncated,
        "live_items": len(live),
        "archived_total": archive_total,
        "include_tools": include_tools,
    }


WAIT_SETS = {
    "attention": {"agent:turn-end", "agent:ask-user", "agent:permission-request", "agent:error"},
    "turn-end": {"agent:turn-end"},
    "ask-user": {"agent:ask-user", "agent:permission-request"},
}


async def session_wait(
    fleet: Fleet,
    host: str,
    session_id: str,
    until: str = "attention",
    timeout_s: float = 120,
    require_new: bool = False,
) -> dict:
    if until not in WAIT_SETS:
        raise BatError(f"until must be one of {', '.join(WAIT_SETS)}")
    timeout_s = max(1.0, min(1800.0, float(timeout_s)))
    c = fleet.client(host)
    t, _ = await _resolve_session(c, session_id)
    sid = t["id"]
    kind = agent_kind(t.get("agentPreset"))
    channels = WAIT_SETS[until]
    sub = c.subscribe(lambda ev: ev.get("channel") in channels and event_session_id(ev) == sid, maxsize=64)
    t0 = time.monotonic()
    try:
        meta = await _meta(c, sid)
        if not require_new:
            if until in ("attention", "turn-end") and not (meta or {}).get("isStreaming"):
                return {
                    "host": host,
                    "session_id": sid,
                    "status": "idle",
                    "event": None,
                    "elapsed_s": 0.0,
                    "loaded": meta is not None,
                }
            if until in ("attention", "ask-user") and _state_safe(kind, meta):
                st = await c.invoke("claude:get-session-state", {"sessionId": sid})
                if isinstance(st, dict):
                    p = summarize_pending(st.get("pendingAskUser"), "ask_user") or summarize_pending(
                        st.get("pendingPermission"), "permission"
                    )
                    if p:
                        return {
                            "host": host,
                            "session_id": sid,
                            "status": "pending",
                            "event": None,
                            "pending": p,
                            "elapsed_s": round(time.monotonic() - t0, 1),
                        }
        while True:
            remaining = timeout_s - (time.monotonic() - t0)
            if remaining <= 0:
                return {
                    "host": host,
                    "session_id": sid,
                    "status": "timeout",
                    "event": None,
                    "elapsed_s": round(time.monotonic() - t0, 1),
                }
            c.last_used = time.monotonic()  # keep the idle reaper away while waiting
            ev = await sub.get(timeout=min(10.0, remaining))
            if ev is not None:
                return {
                    "host": host,
                    "session_id": sid,
                    "status": "event",
                    "event": ev.get("channel"),
                    "elapsed_s": round(time.monotonic() - t0, 1),
                }
            if not c.connected:
                # reconnect; events during the gap are lost, so re-check the live state
                await c.connect()
                meta = await _meta(c, sid)
                if until in ("attention", "turn-end") and not (meta or {}).get("isStreaming"):
                    return {
                        "host": host,
                        "session_id": sid,
                        "status": "idle",
                        "event": None,
                        "note": "reconnected; session no longer streaming",
                        "elapsed_s": round(time.monotonic() - t0, 1),
                    }
    finally:
        c.unsubscribe(sub)


# --------------------------------------------------------------------------- write tools
def _audit(fleet: Fleet) -> Audit:
    return Audit(fleet.config.safety)


def _guard(fleet: Fleet, host: str, confirm: bool) -> None:
    if not fleet.writes_enabled(host):
        raise WriteRefused(
            f"writes are disabled for host {host!r} (set writes = true in its config to enable)"
        )
    if confirm is not True:
        raise WriteRefused("write tools require confirm=true")


def _resume_params(t: dict, ws: dict) -> dict:
    cwd = str(t.get("cwd") or "").strip()
    if not cwd:
        raise WriteRefused("session is not loaded and its workspace record has no cwd; open it in BAT first")
    w = next((x for x in ws.get("workspaces") or [] if x.get("id") == t.get("workspaceId")), {})
    opts = {
        "cwd": cwd,
        "agentPreset": t.get("agentPreset"),
        "model": t.get("model"),
        "permissionMode": t.get("permissionMode"),
        "effort": t.get("effort"),
        "workspaceId": t.get("workspaceId"),
        "workspaceName": w.get("name"),
    }
    return {
        "sessionId": t["id"],
        "sdkSessionId": t.get("sdkSessionId"),
        "options": {k: v for k, v in opts.items() if v not in (None, "")},
    }


async def session_send(
    fleet: Fleet,
    host: str,
    session_id: str,
    text: str,
    confirm: bool = False,
    message_id: str | None = None,
    ensure_loaded: bool = True,
    queue: bool = False,
    tool: str = "session_send",
) -> dict:
    _guard(fleet, host, confirm)
    if not isinstance(text, str) or not text.strip():
        raise WriteRefused("text must be a non-empty string")
    if len(text) > MAX_PROMPT_CHARS:
        raise WriteRefused(f"text is longer than {MAX_PROMPT_CHARS} characters")
    c = fleet.client(host)
    audit = _audit(fleet)
    async with _write_lock():
        t, ws = await _resolve_session(c, session_id)
        sid = t["id"]
        audit.check_rate(host, sid)
        meta = await _meta(c, sid)
        resumed = False
        if meta is None:
            if not ensure_loaded:
                raise WriteRefused(
                    "session is not loaded on the host (pass ensure_loaded=true to client-resume it)"
                )
            params = _resume_params(t, ws)
            audit.record(
                actor=fleet.actor,
                tool=tool,
                host=host,
                session_id=sid,
                channel="claude:client-resume",
                phase="attempt",
            )
            try:
                await c.invoke("claude:client-resume", params)
            except BatError as e:
                audit.record(
                    actor=fleet.actor,
                    tool=tool,
                    host=host,
                    session_id=sid,
                    channel="claude:client-resume",
                    phase="result",
                    ok=False,
                    error=_err(e),
                )
                raise
            resumed = True
            meta = await _meta(c, sid)
        if (meta or {}).get("isStreaming") and not queue:
            raise WriteRefused(
                "session is currently streaming a turn; pass queue=true to queue the message behind it"
            )
        mid = message_id or f"batc-{uuid.uuid4()}"
        audit.record(
            actor=fleet.actor,
            tool=tool,
            host=host,
            session_id=sid,
            channel="claude:send-message",
            message_id=mid,
            phase="attempt",
            text=text,
        )
        try:
            r = await c.invoke(
                "claude:send-message", {"sessionId": sid, "prompt": text, "clientMessageId": mid}
            )
        except BatError as e:
            audit.record(
                actor=fleet.actor,
                tool=tool,
                host=host,
                session_id=sid,
                channel="claude:send-message",
                message_id=mid,
                phase="result",
                ok=False,
                error=_err(e),
            )
            raise
        r = r if isinstance(r, dict) else {"result": r}
        audit.record(
            actor=fleet.actor,
            tool=tool,
            host=host,
            session_id=sid,
            channel="claude:send-message",
            message_id=mid,
            phase="result",
            ok=bool(r.get("ok", True)),
            queued=r.get("queued"),
        )
    return {
        "host": host,
        "session_id": sid,
        "message_id": mid,
        "accepted": r.get("accepted", r.get("ok")),
        "queued": r.get("queued"),
        "resumed": resumed,
        "note": "reuse message_id to retry safely; the host de-duplicates by it",
    }


async def session_continue(
    fleet: Fleet,
    host: str,
    session_id: str,
    confirm: bool = False,
    text: str = "continue",
    queue: bool = False,
    message_id: str | None = None,
) -> dict:
    return await session_send(
        fleet,
        host,
        session_id,
        text,
        confirm=confirm,
        queue=queue,
        message_id=message_id,
        tool="session_continue",
    )


async def session_interrupt(
    fleet: Fleet, host: str, session_id: str, mode: str = "soft", confirm: bool = False
) -> dict:
    _guard(fleet, host, confirm)
    if mode not in ("soft", "hard"):
        raise WriteRefused("mode must be soft or hard")
    c = fleet.client(host)
    audit = _audit(fleet)
    async with _write_lock():
        t, _ = await _resolve_session(c, session_id)
        sid = t["id"]
        kind = agent_kind(t.get("agentPreset"))
        audit.check_rate(host, sid + "#interrupt")
        channel = "claude:interrupt-turn" if (mode == "soft" and kind == "claude") else "claude:abort-session"
        audit.record(
            actor=fleet.actor,
            tool="session_interrupt",
            host=host,
            session_id=sid + "#interrupt",
            channel=channel,
            mode=mode,
            phase="attempt",
        )
        try:
            r = await c.invoke(channel, {"sessionId": sid})
        except BatError as e:
            audit.record(
                actor=fleet.actor,
                tool="session_interrupt",
                host=host,
                session_id=sid + "#interrupt",
                channel=channel,
                phase="result",
                ok=False,
                error=_err(e),
            )
            raise
        audit.record(
            actor=fleet.actor,
            tool="session_interrupt",
            host=host,
            session_id=sid + "#interrupt",
            channel=channel,
            phase="result",
            ok=True,
        )
    note = None
    if mode == "soft" and kind != "claude":
        note = "Codex has no soft interrupt; used abort-session (turn interrupt, session stays)"
    return {"host": host, "session_id": sid, "mode": mode, "channel": channel, "result": r, "note": note}


async def session_answer(
    fleet: Fleet,
    host: str,
    session_id: str,
    confirm: bool = False,
    answers: dict[str, str] | list[str] | None = None,
    permission: str | None = None,
    deny_message: str | None = None,
    tool_use_id: str | None = None,
) -> dict:
    _guard(fleet, host, confirm)
    if (answers is None) == (permission is None):
        raise WriteRefused("pass exactly one of answers (for ask-user) or permission (allow|deny)")
    c = fleet.client(host)
    audit = _audit(fleet)
    async with _write_lock():
        t, _ = await _resolve_session(c, session_id)
        sid = t["id"]
        kind = agent_kind(t.get("agentPreset"))
        meta = await _meta(c, sid)
        if not _state_safe(kind, meta):
            raise WriteRefused("session is not loaded on the host; nothing to answer")
        st = await c.invoke("claude:get-session-state", {"sessionId": sid})
        st = st if isinstance(st, dict) else {}
        audit.check_rate(host, sid + "#answer")
        if answers is not None:
            pend = st.get("pendingAskUser")
            if not isinstance(pend, dict):
                raise WriteRefused("session has no pending ask-user question")
            tuid = pend.get("toolUseId")
            if tool_use_id and tool_use_id != tuid:
                raise WriteRefused("tool_use_id does not match the pending question")
            questions = [
                str(q.get("question", "")) for q in pend.get("questions") or [] if isinstance(q, dict)
            ]
            if isinstance(answers, list):
                if len(answers) > len(questions):
                    raise WriteRefused(f"got {len(answers)} answers for {len(questions)} questions")
                amap = {questions[i] or str(i): str(a) for i, a in enumerate(answers)}
            elif isinstance(answers, dict):
                amap = {}
                for k, v in answers.items():
                    if k in questions:
                        amap[k] = str(v)
                    elif k.isdigit() and int(k) < len(questions):
                        amap[questions[int(k)] or k] = str(v)
                    else:
                        raise WriteRefused("answer keys must be question texts or 0-based question indexes")
            else:
                raise WriteRefused("answers must be a list or an object")
            channel, params = (
                "claude:resolve-ask-user",
                {"sessionId": sid, "toolUseId": tuid, "answers": amap},
            )
            detail = {"questions": len(questions), "answered": len(amap)}
        else:
            pend = st.get("pendingPermission")
            if not isinstance(pend, dict):
                raise WriteRefused("session has no pending permission request")
            tuid = pend.get("toolUseId")
            if tool_use_id and tool_use_id != tuid:
                raise WriteRefused("tool_use_id does not match the pending permission request")
            if permission == "allow":
                result = {"behavior": "allow", "updatedInput": pend.get("input")}
            elif permission == "deny":
                result = {
                    "behavior": "deny",
                    "message": (
                        deny_message
                        or "The user doesn't want to proceed with this tool use. "
                        "Stop and wait for further instructions."
                    )[:2000],
                }
            else:
                raise WriteRefused("permission must be allow or deny")
            channel, params = (
                "claude:resolve-permission",
                {"sessionId": sid, "toolUseId": tuid, "result": result},
            )
            detail = {"permission": permission, "permission_tool": pend.get("toolName")}
        audit.record(
            actor=fleet.actor,
            tool="session_answer",
            host=host,
            session_id=sid + "#answer",
            channel=channel,
            phase="attempt",
            **detail,
        )
        try:
            r = await c.invoke(channel, params)
        except InvokeError as e:
            audit.record(
                actor=fleet.actor,
                tool="session_answer",
                host=host,
                session_id=sid + "#answer",
                channel=channel,
                phase="result",
                ok=False,
                error=_err(e),
            )
            raise
        audit.record(
            actor=fleet.actor,
            tool="session_answer",
            host=host,
            session_id=sid + "#answer",
            channel=channel,
            phase="result",
            ok=True,
        )
    return {"host": host, "session_id": sid, "channel": channel, "tool_use_id": tuid, "result": r, **detail}
