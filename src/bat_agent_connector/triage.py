"""Session-state triage: is a session working, waiting, done, or stuck on a quota?

Deterministic string patterns decide first (fast, no network). Only ambiguous cases
(an error-ish short message that matches no known pattern) are sent to the optional
Jev judgment layer (see jev.py); when Jev is off or fails, the pattern result stands.

States: quota_exhausted, rate_limited_transient, waiting_permission, waiting_question,
working, done_idle, error_other, unknown.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from . import registry
from .client import BatClient
from .fleet import Fleet
from .jev import Jev
from .redact import redact_secrets
from .service import (
    _agent_terminals,
    _err,
    _gather_limited,
    _hosts,
    _meta,
    _state_safe,
    _workspace,
    agent_kind,
    registry_terminal,
)
from .summarize import _content_text, clip, is_tool, iso_local, summarize_pending, ts_to_ms

STATES = (
    "quota_exhausted",
    "rate_limited_transient",
    "waiting_permission",
    "waiting_question",
    "working",
    "done_idle",
    "error_other",
    "unknown",
)

# Known account-quota / usage-limit / credit messages (Claude Code, Codex, API errors).
QUOTA_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bhit your (?:\w+ ){0,2}limit\b",  # "You've hit your limit", "... your monthly spend limit"
        r"\busage limit (?:has been |was )?(?:reached|exceeded|hit)\b",
        r"\bclaude (?:ai )?usage limit\b",
        r"\b(?:weekly|monthly|daily|5-hour|five-hour|session) (?:usage |spend(?:ing)? )?limit (?:reached|exceeded|hit)\b",
        r"\bspend(?:ing)? limit\b.{0,80}\b(?:raise|reached|exceeded|resets?)\b",
        r"\bcredit balance is too low\b",
        r"\bout of (?:extra )?(?:usage|credits)\b",
        r"\b(?:insufficient_quota|quota (?:exceeded|exhausted)|exceeded your (?:current )?quota)\b",
        r"\blimit reached\b.{0,60}\bresets?\b",
    )
]
TRANSIENT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\b(?:http |status |error |api error:? )?429\b",
        r"\brate[ _-]?limit(?:ed|ing)?\b",
        r"\btoo many requests\b",
        r"\boverloaded(?:_error)?\b",
        r"\b(?:api error:? )?529\b",
        r"\btemporarily unavailable\b",
        r"\bretrying in \d+",
    )
]
# Error-ish wording that is worth a second opinion when the message is short.
WEAK_PATTERN = re.compile(
    r"\b(?:limit|quota|credit|billing|api error|error|exception|failed to|unavailable|denied|expired)\b", re.I
)
RESETS_RE = re.compile(r"\bresets?\s+(?:at\s+|on\s+|in\s+)?([^·|\n]{3,60})", re.I)
EPOCH_RE = re.compile(r"usage limit reached\|(\d{10})", re.I)
WEAK_MAX_CHARS = 600


def _msg_text(m: dict) -> str:
    if is_tool(m):
        return ""
    return _content_text(m.get("content") if "content" in m else m.get("text")).strip()


def _role(m: dict) -> str:
    return str(m.get("role") or m.get("type") or "?")


def _evidence_line(text: str, rx: re.Pattern | None = None) -> str:
    lines = [ln.strip() for ln in redact_secrets(text).splitlines() if ln.strip()]
    if rx is not None:
        for ln in lines:
            if rx.search(ln):
                return clip(ln, 240)
    return clip(lines[-1] if lines else text, 240)


def _resets(text: str) -> str | None:
    m = EPOCH_RE.search(text)
    if m:
        return iso_local(int(m.group(1)) * 1000)
    m = RESETS_RE.search(text)
    return m.group(1).strip().rstrip(".") if m else None


def match_any(patterns: list[re.Pattern], text: str) -> re.Pattern | None:
    for rx in patterns:
        if rx.search(text):
            return rx
    return None


def classify_messages(
    msgs: list[dict], *, streaming: bool = False, pending: dict | None = None
) -> dict[str, Any]:
    """Deterministic classification from the newest messages (oldest first in ``msgs``)."""
    out: dict[str, Any] = {"state": "unknown", "source": "pattern", "confidence": 0.3, "evidence": None}
    if pending:
        kind = pending.get("kind")
        if kind == "permission":
            out.update(
                state="waiting_permission",
                confidence=0.99,
                evidence=clip(
                    f"permission: {pending.get('toolName')} {pending.get('input_preview') or ''}", 240
                ),
            )
        else:
            q = (pending.get("questions") or [{}])[0].get("question") if pending.get("questions") else None
            out.update(state="waiting_question", confidence=0.99, evidence=clip(f"question: {q or ''}", 240))
        return out
    texts = [(m, _msg_text(m)) for m in msgs]
    texts = [(m, t) for m, t in texts if t]
    last_user = max((i for i, (m, _) in enumerate(texts) if _role(m) == "user"), default=-1)
    replies = [(m, t) for m, t in texts[last_user + 1 :] if _role(m) != "user"]
    newest = replies[-1][1] if replies else ""
    if streaming:
        out.update(
            state="working", confidence=0.9, evidence=_evidence_line(newest) if newest else "streaming"
        )
        return out
    # quota: newest reply, or any reply since the last user prompt with nothing substantive after it
    for idx in range(len(replies) - 1, -1, -1):
        t = replies[idx][1]
        rx = match_any(QUOTA_PATTERNS, t)
        if rx:
            later = [x for _, x in replies[idx + 1 :] if not match_any(QUOTA_PATTERNS, x)]
            if not any(len(x) > 200 for x in later):
                out.update(
                    state="quota_exhausted",
                    confidence=0.97,
                    evidence=_evidence_line(t, rx),
                    resets=_resets(t),
                )
                return out
        break
    if not replies:
        if last_user >= 0:
            out.update(state="unknown", confidence=0.3, evidence=_evidence_line(texts[last_user][1]))
            out["ambiguous"] = True
        return out
    rx = match_any(TRANSIENT_PATTERNS, newest)
    if rx and len(newest) <= WEAK_MAX_CHARS:
        out.update(
            state="rate_limited_transient",
            confidence=0.8,
            evidence=_evidence_line(newest, rx),
            resets=_resets(newest),
        )
        out["ambiguous"] = bool(_resets(newest))  # a reset time hints at a longer quota; ask Jev
        return out
    if len(newest) <= WEAK_MAX_CHARS and WEAK_PATTERN.search(newest):
        out.update(state="error_other", confidence=0.5, evidence=_evidence_line(newest, WEAK_PATTERN))
        out["ambiguous"] = True
        return out
    out.update(state="done_idle", confidence=0.7, evidence=_evidence_line(newest))
    return out


def excerpt(msgs: list[dict], max_chars: int = 4000) -> str:
    parts = []
    for m in msgs[-30:]:
        t = _msg_text(m)
        if t:
            parts.append(f"[{_role(m)}] {clip(t, 800)}")
        elif is_tool(m):
            parts.append(f"[tool {m.get('toolName')} {m.get('status') or ''}]")
    return redact_secrets("\n".join(parts))[-max_chars:]


async def refine_with_jev(jev: Jev | None, cls: dict, msgs: list[dict], use_jev: str) -> dict:
    """Ask Jev about ambiguous results (or all, with use_jev='always'). Fail-open: keep the pattern result."""
    if jev is None or use_jev == "never" or not jev.enabled:
        return cls
    if cls["state"] in ("waiting_permission", "waiting_question", "working"):
        return cls
    if use_jev == "auto" and not cls.get("ambiguous"):
        return cls
    r = await jev.classify_state(excerpt(msgs))
    if not r:
        cls["jev"] = "unavailable"
        return cls
    cls = {
        **cls,
        "pattern_state": cls["state"],
        "state": r["state"],
        "source": "jev",
        "confidence": r["confidence"],
    }
    if cls["state"] == "done_idle" and cls.get("pattern_state") == "done_idle":
        cls["source"] = "pattern+jev"
    return cls


async def session_snapshot(c: BatClient, t: dict, meta: dict | None, tail: int = 40) -> dict:
    """Recent messages (oldest first), pending prompt and streaming flag for one session."""
    kind = agent_kind(t.get("agentPreset"))
    msgs: list[dict] = []
    pending = None
    streaming = bool((meta or {}).get("isStreaming"))
    if _state_safe(kind, meta):
        st = await c.invoke("claude:get-session-state", {"sessionId": t["id"]})
        if isinstance(st, dict):
            msgs = [m for m in st.get("messages") or [] if isinstance(m, dict)]
            streaming = streaming or bool(st.get("isStreaming"))
            pending = summarize_pending(st.get("pendingPermission"), "permission") or summarize_pending(
                st.get("pendingAskUser"), "ask_user"
            )
    if not msgs:
        r = await c.invoke("claude:load-archived", {"sessionId": t["id"], "offset": 0, "limit": tail})
        if isinstance(r, dict):
            msgs = [m for m in r.get("messages") or [] if isinstance(m, dict)]
    return {"messages": msgs[-tail:], "pending": pending, "streaming": streaming}


async def _host_triage(
    fleet: Fleet,
    jev: Jev | None,
    name: str,
    workspace: str | None,
    agent: str | None,
    use_jev: str,
    include_unloaded: bool,
) -> list[dict]:
    c = fleet.client(name)
    ws = await _workspace(c)
    ws_by_id = {w.get("id"): w for w in ws.get("workspaces") or []}
    terms = _agent_terminals(ws)
    known = {t.get("id") for t in terms}
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

    async def one(t: dict, m: Any) -> dict | None:
        meta = m if isinstance(m, dict) else None
        if meta is None and not include_unloaded:
            return None
        w = ws_by_id.get(t.get("workspaceId")) or {}
        row: dict[str, Any] = {
            "host": name,
            "session_id": t.get("id"),
            "workspace": w.get("name"),
            "agent_kind": agent_kind(t.get("agentPreset")),
            "cwd": t.get("cwd") or (meta or {}).get("cwd"),
            "worktree_branch": t.get("worktreeBranch"),
            "loaded": meta is not None,
            "orchestrated": bool(t.get("_orchestrated")) or registry.get(name, t.get("id")) is not None,
        }
        try:
            snap = await session_snapshot(c, t, meta)
            cls = classify_messages(snap["messages"], streaming=snap["streaming"], pending=snap["pending"])
            cls = await refine_with_jev(jev, cls, snap["messages"], use_jev)
            ts = [ts_to_ms(x.get("timestamp") or x.get("completedAt")) for x in snap["messages"]]
            last = max((x for x in ts if x), default=None)
            cls.pop("ambiguous", None)
            row.update(cls)
            row["last_activity"] = iso_local(last)
            row["streaming"] = snap["streaming"]
        except Exception as e:  # noqa: BLE001
            row.update(state="unknown", source="error", confidence=0.0, evidence=_err(e))
        return row

    rows = await _gather_limited([one(t, m) for t, m in zip(terms, metas, strict=True)], limit=6)
    return [r for r in rows if isinstance(r, dict)]


async def sessions_triage(
    fleet: Fleet,
    host: str | None = None,
    workspace: str | None = None,
    agent: str | None = None,
    states: list[str] | None = None,
    use_jev: str = "auto",
    include_unloaded: bool = True,
) -> dict:
    if use_jev not in ("auto", "always", "never"):
        raise ValueError("use_jev must be auto, always or never")
    for s in states or []:
        if s not in STATES:
            raise ValueError(f"unknown state {s!r}; one of {', '.join(STATES)}")
    jev = Jev(fleet.config.jev)
    names = _hosts(fleet, host)
    t0 = time.monotonic()
    res = await asyncio.gather(
        *(_host_triage(fleet, jev, n, workspace, agent, use_jev, include_unloaded) for n in names),
        return_exceptions=True,
    )
    rows, errors = [], {}
    for n, r in zip(names, res, strict=True):
        if isinstance(r, BaseException):
            errors[n] = _err(r)
        else:
            rows.extend(r)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    if states:
        rows = [r for r in rows if r["state"] in states]
    order = {s: i for i, s in enumerate(STATES)}
    rows.sort(key=lambda r: (order.get(r["state"], 99), r["host"], str(r.get("workspace"))))
    return {
        "sessions": rows,
        "count": len(rows),
        "counts_by_state": counts,
        "jev": jev.status(),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "errors": errors,
    }
