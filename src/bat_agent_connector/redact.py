"""Secret redaction helpers. Tokens must never be logged, returned or persisted."""

from __future__ import annotations

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
