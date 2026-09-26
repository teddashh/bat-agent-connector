"""Local registry of sessions started by the orchestrate tier.

BAT only lists sessions that have a tab in the host's workspace document. Sessions
started headlessly (without tab registration) are tracked here so the connector
can still find, cap, review and clean them up.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
from pathlib import Path

from .config import state_dir


def registry_path() -> Path:
    return state_dir() / "orchestrated.json"


@contextlib.contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
        return [e for e in data.get("sessions", []) if isinstance(e, dict)]
    except (OSError, ValueError):
        return []


def _write(path: Path, items: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"sessions": items}, fh, indent=1)
    os.replace(tmp, path)


def list_entries(host: str | None = None, active_only: bool = False) -> list[dict]:
    items = _read(registry_path())
    if host:
        items = [e for e in items if e.get("host") == host]
    if active_only:
        items = [e for e in items if e.get("status") == "active"]
    return items


def get(host: str, session_id: str) -> dict | None:
    for e in _read(registry_path()):
        if e.get("host") == host and e.get("session_id") == session_id:
            return e
    return None


def find_prefix(host: str, prefix: str) -> list[dict]:
    return [
        e
        for e in _read(registry_path())
        if e.get("host") == host and str(e.get("session_id", "")).startswith(prefix)
    ]


def reserve(host: str, entry: dict, max_active: int, replaces: str | None = None) -> None:
    """Atomically check the per-host cap and add an entry (status=starting).

    ``replaces``: session id of an active entry this one takes over (failover in the same
    worktree). It is marked ``superseded`` in the same transaction, so the pair counts once.
    """
    from .errors import WriteRefused

    p = registry_path()
    with _locked(p):
        items = _read(p)
        if replaces:
            for e in items:
                if e.get("host") == host and e.get("session_id") == replaces and e.get("status") == "active":
                    e.update(status="superseded", superseded_by=entry.get("session_id"), updated_at=time.time())
        active = [e for e in items if e.get("host") == host and e.get("status") in ("active", "starting")]
        if len(active) >= max_active:
            raise WriteRefused(
                f"orchestrate cap reached on {host}: {len(active)} active orchestrated sessions "
                f"(orchestrate_max_sessions={max_active}); remove finished worktrees first"
            )
        entry = {**entry, "host": host, "status": "starting", "created_at": time.time()}
        items.append(entry)
        _write(p, items)


def update(host: str, session_id: str, **fields) -> None:
    p = registry_path()
    with _locked(p):
        items = _read(p)
        for e in items:
            if e.get("host") == host and e.get("session_id") == session_id:
                e.update(fields)
                e["updated_at"] = time.time()
        _write(p, items)
