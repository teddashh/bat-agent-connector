"""Secret redaction helpers. Tokens must never be logged, returned or persisted.

`redact` masks the connector's own registered secrets; `redact_secrets` masks credential-looking
strings in session text before it leaves the host session (handoffs, Jev requests, chat relays)."""

from __future__ import annotations

import re
import threading

_lock = threading.Lock()
_secrets: set[str] = set()


def register_secret(value: str | None) -> None:
    if value and len(value) >= 6:
        with _lock:
            _secrets.add(value)


def redact(text: object) -> str:
    s = str(text)
    with _lock:
        secrets = list(_secrets)
    for sec in secrets:
        if sec in s:
            s = s.replace(sec, "<redacted>")
    return s


REDACT_RE = re.compile(
    r"(discord(?:app)?\.com/api/webhooks/\d+/)[\w-]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"
    r"|\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|sk-[A-Za-z0-9_-]{24,}|AIza[0-9A-Za-z_-]{35}|glpat-[A-Za-z0-9_-]{20})"
    r"|(?i:(bearer\s+))[A-Za-z0-9._~+/-]{24,}=*"
    r"|(?i:((?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|token)\s*[:=]\s*['\"]?))"
    r"[^\s'\"]{12,}"
)


def redact_secrets(text: str | None) -> str:
    """Mask things that look like credentials before text leaves the host session (handoff prompts,
    Jev requests, tool output that may be relayed to chat)."""
    if not text:
        return text or ""

    def sub(m: re.Match) -> str:
        keep = m.group(1) or m.group(2) or m.group(3) or ""
        return keep + "[REDACTED]"

    return REDACT_RE.sub(sub, text)
