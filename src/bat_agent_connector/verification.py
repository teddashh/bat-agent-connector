"""Explicit, commit-bound execution evidence for cleanup decisions.

BAT's remote protocol cannot execute a verifier. A trusted caller records a run
performed in the candidate environment; this module checks the host's HEAD and
clean working tree both on admission and when cleanup evaluates the record.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .config import state_dir
from .errors import WriteRefused
from .redact import redact, redact_secrets
from .registry import _locked

SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


def path() -> Path:
    return state_dir() / "verification.json"


def _read(p: Path) -> list[dict]:
    try:
        return json.loads(p.read_text()).get("records", [])
    except (OSError, ValueError):
        return []


def get(host: str, session_id: str) -> dict | None:
    return next(
        (r for r in reversed(_read(path())) if r.get("host") == host and r.get("session_id") == session_id),
        None,
    )


def record(
    host: str,
    session_id: str,
    *,
    candidate_commit: str,
    command: str,
    exit_code: int,
    environment: str,
    log_ref: str,
    actor: str,
) -> dict:
    if not SHA.fullmatch(candidate_commit):
        raise WriteRefused("candidate_commit must be a Git commit hash")
    if not command.strip() or not environment.strip() or not log_ref.strip():
        raise WriteRefused("command, environment and log_ref are required")
    if len(command) > 4000 or len(environment) > 4000 or len(log_ref) > 2000:
        raise WriteRefused("verification field is too long")
    if any(redact_secrets(redact(value)) != value for value in (command, environment, log_ref)):
        raise WriteRefused("verification metadata must not contain credentials; provide a sanitized command")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise WriteRefused("exit_code must be an integer")
    row = {
        "host": host,
        "session_id": session_id,
        "candidate_commit": candidate_commit.lower(),
        "command": command,
        "exit_code": exit_code,
        "environment": environment,
        "log_ref": log_ref,
        "actor": actor,
        "recorded_at": time.time(),
    }
    p = path()
    with _locked(p):
        rows = [r for r in _read(p) if not (r.get("host") == host and r.get("session_id") == session_id)]
        rows.append(row)
        tmp = p.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"records": rows}, fh, indent=1)
        os.replace(tmp, p)
    return row


def matches(record: dict | None, head: str | None) -> bool:
    return bool(
        record
        and head
        and record.get("exit_code") == 0
        and record.get("candidate_commit") == head.lower()
        and record.get("command")
        and record.get("environment")
        and record.get("log_ref")
    )
