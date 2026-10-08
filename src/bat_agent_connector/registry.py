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


def ensure_existing(host: str, entry: dict) -> None:
    """Restore local lookup for a BAT session verified by task journal and host meta."""
    p = registry_path()
    with _locked(p):
        items = _read(p)
        for old in items:
            if old.get("host") == host and old.get("session_id") == entry.get("session_id"):
                if (old.get("task_id") not in {None, entry.get("task_id")}
                        or old.get("role") not in {None, entry.get("role")}
                        or any(old.get(key) not in {None, entry.get(key)} for key in (
                            "workspace_id", "origin_cwd", "cwd", "worktree_path", "branch",
                            "agent_preset"))):
                    raise ValueError("local session entry changed during BAT identity verification")
                old.update(entry)
                old["status"] = "active"
                old["updated_at"] = time.time()
                _write(p, items)
                return
        items.append({**entry, "host": host, "status": "active", "created_at": time.time(),
                      "recovered_from": "task_journal"})
        _write(p, items)


def find_prefix(host: str, prefix: str) -> list[dict]:
    return [
        e
        for e in _read(registry_path())
        if e.get("host") == host and str(e.get("session_id", "")).startswith(prefix)
    ]


def reserve(host: str, entry: dict, max_active: int, replaces: str | None = None) -> dict | None:
    """Atomically check the per-host cap and add an entry (status=starting).

    ``replaces``: session id of an active entry this one takes over (failover in the same
    worktree). It is marked ``superseded`` in the same transaction, so the pair counts once.
    """
    from .errors import WriteRefused

    p = registry_path()
    with _locked(p):
        items = _read(p)
        # The earlier caller-side lookup is only a hint. This check and the reservation
        # must share the flock, including when two independent MCP processes race.
        old = entry.get("failover_of")
        if old:
            existing = next((e for e in items if e.get("host") == host and
                             e.get("failover_of") == old and e.get("status") in ("starting", "active")), None)
            if existing:
                return existing
            worktree = entry.get("worktree_path")
            if worktree and any(e.get("host") == host and e.get("worktree_path") == worktree and
                                e.get("failover_of") and e.get("status") in ("starting", "active")
                                for e in items):
                raise WriteRefused("another active failover successor already owns this worktree")
        if replaces:
            for e in items:
                if e.get("host") == host and e.get("session_id") == replaces and e.get("status") == "active":
                    e.update(status="superseded", superseded_by=entry.get("session_id"), updated_at=time.time())
        # A crash can leave the original starting row intact. Explicit false is
        # durable proof that this exact reserved ID never reached the transport.
        items = [e for e in items if not (e.get("host") == host and e.get("session_id") == entry["session_id"]
                                        and e.get("status") in {"failed", "starting"} and e.get("start_sent") is False)]
        active = [e for e in items if e.get("host") == host and e.get("status") in ("active", "starting")]
        if len(active) >= max_active:
            raise WriteRefused(
                f"orchestrate cap reached on {host}: {len(active)} active orchestrated sessions "
                f"(orchestrate_max_sessions={max_active}); remove finished worktrees first"
            )
        entry = {**entry, "host": host, "status": "starting", "created_at": time.time()}
        items.append(entry)
        _write(p, items)
    return None


def fail_reservation(host: str, session_id: str, replaces: str | None = None) -> None:
    """Fail a successor and undo only the predecessor handoff owned by it."""
    p = registry_path()
    with _locked(p):
        items = _read(p)
        for e in items:
            if e.get("host") == host and e.get("session_id") == session_id:
                e.update(status="failed", updated_at=time.time())
            if (replaces and e.get("host") == host and e.get("session_id") == replaces
                    and e.get("superseded_by") == session_id):
                e.update(status="active", superseded_by=None, updated_at=time.time())
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


def claim_warm(host: str, session_id: str, *, previous_task_id: str, task_id: str,
               workspace_id: str, cwd: str, branch: str) -> None:
    """Transfer one completed task's lead session under the registry flock."""
    from .errors import TaskIdentityMismatch

    p = registry_path()
    with _locked(p):
        items = _read(p)
        matches = [e for e in items if e.get("host") == host and e.get("session_id") == session_id]
        if (len(matches) != 1 or matches[0].get("task_id") != previous_task_id
                or matches[0].get("role") != "lead" or matches[0].get("status") != "active"
                or matches[0].get("workspace_id") != workspace_id
                or matches[0].get("cwd") != cwd or matches[0].get("worktree_path") != cwd
                or matches[0].get("branch") != branch
                or any(e.get("host") == host and e.get("failover_of") == session_id
                       and e.get("status") in {"active", "starting"} for e in items)):
            raise TaskIdentityMismatch("warm session ownership changed before claim")
        matches[0].update(task_id=task_id, title="task " + task_id[:8],
                          warm_from_task_id=previous_task_id, updated_at=time.time())
        _write(p, items)


def confirm_failover_start(host: str, session_id: str, *, message_id: str, **fields) -> dict:
    """Activate a read-back without overwriting a concurrently recorded handoff.

    Older start blocks could not attempt a handoff before settling their start.
    Backfill their null fence and message ID under the same registry flock.
    """
    from . import confinement
    from .errors import TaskIdentityMismatch

    p = registry_path()
    with _locked(p):
        items = _read(p)
        successor = next((e for e in items if e.get("host") == host and e.get("session_id") == session_id), None)
        if not successor or not successor.get("failover_of"):
            raise TaskIdentityMismatch("reserved successor disappeared during start read-back")
        confinement.guard_start_record(successor)
        if (successor.get("start_uncertain") or successor.get("status") == "starting") and successor.get("handoff_status") == "pending":
            successor.setdefault("handoff_frame_sha256", None)
            if not successor.get("handoff_message_id"):
                successor["handoff_message_id"] = message_id
        successor.update(fields, updated_at=time.time())
        _write(p, items)
        return successor


def claim_handoff_frame(host: str, successor_id: str, message_id: str, prompt_sha256: str) -> None:
    """Consume the durable proof of an unsent failover handoff before transport.

    Explicit null means this reservation uses the frame fence; a missing key in
    a legacy row is not proof. The flock also fences separate daemon processes.
    Task Service's ownership guard still runs on the actual frame afterwards.
    """
    from .errors import TaskIdentityMismatch

    p = registry_path()
    with _locked(p):
        items = _read(p)
        successor = next((e for e in items if e.get("host") == host and
                          e.get("session_id") == successor_id), None)
        if (not successor or not successor.get("failover_of") or successor.get("status") != "active"
                or successor.get("handoff_status") != "pending"
                or successor.get("handoff_message_id") != message_id
                or "handoff_frame_sha256" not in successor or successor["handoff_frame_sha256"] is not None):
            raise TaskIdentityMismatch("failover handoff may already have been attempted")
        successor.update(handoff_frame_sha256=prompt_sha256, updated_at=time.time())
        _write(p, items)


def record_handoff_frame(host: str, *, old_session_id: str, successor_id: str, task_id: str,
                         worktree_path: str, branch: str, command_id: str,
                         message_id: str, prompt_sha256: str) -> None:
    """Atomically bind an actual BAT frame to the still-owned successor registry row."""
    from .errors import TaskIdentityMismatch

    p = registry_path()
    with _locked(p):
        items = _read(p)
        old = next((e for e in items if e.get("host") == host and
                    e.get("session_id") == old_session_id), None)
        successor = next((e for e in items if e.get("host") == host and
                          e.get("session_id") == successor_id), None)
        if (not old or old.get("worktree_path") != worktree_path or old.get("branch") != branch
                or not successor or successor.get("session_id") != successor_id
                or successor.get("failover_of") != old_session_id
                or successor.get("shares_worktree_with") != old_session_id
                or successor.get("task_id") != task_id
                or successor.get("worktree_path") != worktree_path
                or successor.get("cwd") != worktree_path or successor.get("branch") != branch
                or successor.get("status") != "active" or successor.get("handoff_status") != "pending"
                or successor.get("handoff_command_id") != command_id
                or successor.get("handoff_message_id") != message_id):
            raise TaskIdentityMismatch("successor registry ownership changed before BAT handoff frame")
        successor["handoff_frame_sha256"] = prompt_sha256
        successor["updated_at"] = time.time()
        _write(p, items)


def turn_path() -> Path:
    return state_dir() / "turns.json"


def record_turn(host: str, session_id: str, message_id: str, *, queued: bool, baseline_turns: int | None) -> None:
    """Keep the accepted command identity across separate batc/MCP calls on this machine."""
    p = turn_path()
    with _locked(p):
        try:
            items = json.loads(p.read_text()).get("turns", [])
        except (OSError, ValueError):
            items = []
        if any(e.get("host") == host and e.get("session_id") == session_id and
               e.get("message_id") == message_id for e in items):
            return  # preserve the original queue fence on an idempotent retry
        items.append({"host": host, "session_id": session_id, "message_id": message_id,
                      "queued": queued, "baseline_turns": baseline_turns, "accepted_at": time.time()})
        fd = os.open(p.with_suffix(".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"turns": items[-1000:]}, fh)
        os.replace(p.with_suffix(".tmp"), p)


def get_turn(host: str, session_id: str, message_id: str) -> dict | None:
    try:
        items = json.loads(turn_path().read_text()).get("turns", [])
    except (OSError, ValueError):
        return None
    return next((e for e in reversed(items) if e.get("host") == host and
                 e.get("session_id") == session_id and e.get("message_id") == message_id), None)


def update_turn_boundary(host: str, session_id: str, message_id: str, boundary_ms: int) -> None:
    p = turn_path()
    with _locked(p):
        try:
            items = json.loads(p.read_text()).get("turns", [])
        except (OSError, ValueError):
            return
        for e in items:
            if e.get("host") == host and e.get("session_id") == session_id and e.get("message_id") == message_id:
                e.setdefault("boundary_ms", boundary_ms)
        fd = os.open(p.with_suffix(".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"turns": items}, fh)
        os.replace(p.with_suffix(".tmp"), p)
