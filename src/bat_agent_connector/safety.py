"""Write-side safety: audit log (append-only JSONL) and rate limiting derived from it."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .config import SafetyConfig, state_dir
from .errors import WriteRefused


def audit_path() -> Path:
    return state_dir() / "audit.jsonl"


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Audit:
    def __init__(self, safety: SafetyConfig, path: Path | None = None) -> None:
        self.safety = safety
        self.path = path or audit_path()

    def _tail(self, max_lines: int = 2000) -> list[dict]:
        try:
            with self.path.open("rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 512 * 1024))
                lines = fh.read().decode("utf-8", "replace").splitlines()[-max_lines:]
        except OSError:
            return []
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out

    def check_rate(self, host: str, session_id: str, now: float | None = None) -> None:
        now = now or time.time()
        entries = [e for e in self._tail() if e.get("phase") == "attempt"]
        hour = [e for e in entries if now - float(e.get("at", 0)) < 3600]
        if len(hour) >= self.safety.max_writes_per_hour:
            raise WriteRefused(
                f"rate limit: {len(hour)} writes in the last hour (max_writes_per_hour={self.safety.max_writes_per_hour})"
            )
        same = [e for e in hour if e.get("host") == host and e.get("session_id") == session_id]
        if same:
            age = now - max(float(e.get("at", 0)) for e in same)
            if age < self.safety.write_min_interval_s:
                raise WriteRefused(
                    f"rate limit: last write to this session was {age:.0f}s ago "
                    f"(write_min_interval_s={self.safety.write_min_interval_s:.0f})"
                )

    def record(self, **fields: Any) -> None:
        text = fields.pop("text", None)
        if text is not None:
            fields["text_sha256_16"] = text_fingerprint(text)
            fields["text_len"] = len(text)
            n = self.safety.audit_preview_chars
            if n > 0:
                fields["text_preview"] = text[:n]
        fields.setdefault("at", time.time())
        fields["at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(fields["at"]))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(fields, ensure_ascii=False, default=str)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as fh:
            fh.write(line + "\n")
