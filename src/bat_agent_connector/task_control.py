"""Task authority at the shared service layer, including the last BAT-frame boundary."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import inspect
import json
import sqlite3
from dataclasses import dataclass, field

from . import registry, resource_policy
from .errors import TaskControlRefused, WriteRefused

RUNTIME_KINDS = {"send", "answer", "interrupt", "permissions", "failover"}


def admission_binding(task, *, session=False, role="lead"):
    binding = {"task_id": task["task_id"], "control_version": task["control_version"]}
    if session:
        field = "reviewer_session_id" if role == "reviewer" else "session_id"
        binding.update(host=task["host"], session_id=task.get(field), role=role)
    return binding


def check_binding(ctx):
    binding = ctx.admission_binding
    if not binding:  # pre-upgrade operations retain their original execution-time binding
        return None
    task = ctx.service.journal.get(binding["task_id"])
    if task["control_version"] != binding["control_version"]:
        raise TaskControlRefused("CONTROL_VERSION_CONFLICT", "task control_version changed since admission")
    if "session_id" in binding:
        sid = binding["session_id"]
        role = binding["role"]
        field = "reviewer_session_id" if role == "reviewer" else "session_id"
        if task["host"] != binding["host"] or task.get(field) != sid:
            raise TaskControlRefused("TASK_BINDING_MISMATCH", "task session changed since admission")
    return task


def owner_task(fleet, host, sid):
    owner = registry.get(host, sid) or {}
    if owner.get("task_id"):
        return owner["task_id"]
    coordinator = getattr(fleet, "task_coordinator", None)
    def find(db):
        row = db.execute("SELECT task_id FROM tasks WHERE host=? AND (session_id=? OR reviewer_session_id=?) "
                         "ORDER BY submitted_at DESC LIMIT 1", (host, sid, sid)).fetchone()
        if not row:
            row = db.execute("SELECT c.task_id FROM commands c JOIN tasks t ON t.task_id=c.task_id "
                             "WHERE t.host=? AND c.session_id=? AND c.kind LIKE 'start_%' "
                             "UNION SELECT b.task_id FROM branches b JOIN tasks t ON t.task_id=b.task_id "
                             "WHERE t.host=? AND b.session_id=? LIMIT 1", (host, sid, host, sid)).fetchone()
        return row[0] if row else None
    if coordinator:
        return find(coordinator.journal.db)
    from .service import task_service_db
    path = task_service_db()
    if path:
        try:
            with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.2)) as db:
                return find(db)
        except sqlite3.Error:
            pass
    return None


def check(journal, task_id: str, host: str, sid: str, action: str, version=None, *, command_id=None):
    try:
        task = journal.get(task_id)
    except (ValueError, KeyError):
        raise TaskControlRefused("TASK_OWNER_UNAVAILABLE", "task owner row is unavailable") from None
    owner = registry.get(host, sid)
    if task["host"] != host or not owner or owner.get("task_id") != task_id:
        raise TaskControlRefused("TASK_BINDING_MISMATCH", "task session ownership does not match")
    if task.get("session_id") != sid or owner.get("role") != "lead":
        raise TaskControlRefused("TASK_STATE_BLOCKED", "only the task's current lead accepts external control")
    if version is not None and (type(version) is not int or version != task["control_version"]):
        raise TaskControlRefused("CONTROL_VERSION_CONFLICT", "task control_version changed")
    if task["paused"]:
        raise TaskControlRefused("TASK_PAUSED", "task is paused")
    if task["state"] == "verifying":
        raise TaskControlRefused("TASK_VERIFYING", "task is verifying")
    pending = [c for c in journal.commands(task_id) if c["command_id"] != command_id
               and c["status"] in {"intent", "needs_review", "uncertain"}
               and (c["kind"] in RUNTIME_KINDS or c["kind"].startswith("start_"))]
    if pending:
        raise TaskControlRefused("TASK_COMMAND_PENDING", "task has a command requiring reconciliation")
    if task["state"] == "uncertain":
        raise TaskControlRefused("TASK_RECONCILIATION_REQUIRED", "task needs reconciliation")
    if (task["state"] not in {"accepted", "running", "waiting_permission"}
            or task["state"] == "waiting_permission" and action == "send"):
        raise TaskControlRefused("TASK_STATE_BLOCKED", "task state does not allow this control")
    return task


@dataclass(frozen=True)
class FrameGuard:
    journal: object
    task_id: str
    host: str
    session_id: str
    version: int
    command_id: str | None = None
    action: str = "send"
    internal: bool = False
    abort: bool = False
    prompt_sha256: str | None = None
    frames: list = field(default_factory=list, compare=False)

    def __call__(self):
        # Only the command's effect frames count; preliminary writes use check() directly.
        self.check()
        self.frames.append(True)

    def check(self):
        if getattr(self.journal, "owner_valid", None) and not self.journal.owner_valid():
            raise TaskControlRefused("TASK_OWNER_UNAVAILABLE", "fleet owner lease is no longer held")
        task = self.journal.get(self.task_id)
        owner = registry.get(self.host, self.session_id)
        if (task["host"] != self.host or self.session_id not in
                {task.get("session_id"), task.get("reviewer_session_id")}
                or not owner or owner.get("task_id") != self.task_id
                or owner.get("role") != ("reviewer" if self.session_id == task.get("reviewer_session_id") else "lead")):
            raise TaskControlRefused("TASK_BINDING_MISMATCH", "task session binding changed before BAT frame")
        if task["control_version"] != self.version:
            raise TaskControlRefused("CONTROL_VERSION_CONFLICT", "task control_version changed before BAT frame")
        if self.abort:
            if not task["paused"]:
                raise TaskControlRefused("CONTROL_VERSION_CONFLICT", "pause no longer owns the abort")
            return
        if task["paused"]:
            raise TaskControlRefused("TASK_PAUSED", "task paused before BAT frame")
        if self.internal and self.action == "verify":
            if task["state"] not in {"accepted", "running", "verifying"}:
                raise TaskControlRefused("TASK_STATE_BLOCKED", "task no longer allows trusted verification")
            return
        command = self.journal.command_get(self.command_id) if self.command_id else None
        if (not command or command["kind"] != self.action or command["task_id"] != self.task_id or command["session_id"] != self.session_id
                or command["status"] not in {"intent", "needs_review"}):
            raise TaskControlRefused("TASK_COMMAND_PENDING", "frame has no dispatchable task command")
        if self.action == "send" and (not self.prompt_sha256 or
                json.loads(command["payload"]).get("prompt_sha256") != self.prompt_sha256):
            raise TaskControlRefused("TASK_BINDING_MISMATCH", "task command does not bind this prompt")
        if self.internal:
            # Reviewer/rework sends are allowed only by the original coordinator's journaled intent.
            if command["kind"] != "send" or task["state"] not in {"accepted", "running", "verifying", "dispatching"}:
                raise TaskControlRefused("TASK_STATE_BLOCKED", "internal task command is no longer dispatchable")
        else:
            check(self.journal, self.task_id, self.host, self.session_id, self.action,
                  self.version, command_id=self.command_id)


def guarded(action):
    """Route task-owned legacy calls to the owner before taking the host write lock."""
    def decorate(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            from . import service
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            fleet, host, sid = values["fleet"], values["host"], values["session_id"]
            guard = values.get("_task_guard")
            if guard is not None:
                if (not isinstance(guard, FrameGuard) or guard.host != host or guard.session_id != sid
                        or guard.action != action):
                    raise TaskControlRefused("TASK_BINDING_MISMATCH", "invalid task frame authority")
                if action == "send" and hashlib.sha256(str(values.get("text", "")).encode()).hexdigest() != guard.prompt_sha256:
                    raise TaskControlRefused("TASK_BINDING_MISMATCH", "task frame authority binds a different prompt")
                guard.check()
                return await fn(*args, **kwargs)
            service._guard(fleet, host, values["confirm"])
            if action == "permissions" and values["mode"] == "allow_all" and fleet.config.host(host).default_permission_mode != "allow_all":
                raise WriteRefused(f"host {host!r} does not allow raising sessions to allow-all "
                                   '(set default_permission_mode = "allow_all" in its config)')
            tab, _ = await service._resolve_session(fleet.client(host), sid)
            sid = tab["id"]
            await resource_policy.authorize_session(fleet, host, "session." + action, tab)
            task_id = owner_task(fleet, host, sid)
            if not task_id:
                return await fn(*args, **kwargs)
            coordinator = getattr(fleet, "task_coordinator", None)
            params = {k: v for k, v in values.items() if k not in
                      {"fleet", "host", "session_id", "_task_guard", "before_invoke", "initial_task_send"}}
            if coordinator:
                return await coordinator.session_control(task_id, host, sid, action, params, fn)
            # A second client observes the canonical journal, then enters the existing owner over RPC.
            db = service.task_service_db()
            if db is None:
                raise TaskControlRefused("TASK_OWNER_UNAVAILABLE", "task-owned session state is unavailable (owner pointer missing)")
            try:
                with contextlib.closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.2)) as conn:
                    conn.row_factory = sqlite3.Row
                    class Reader:
                        def get(self, tid):
                            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
                            if row is None:
                                raise ValueError("missing task")
                            return dict(row)

                        def commands(self, tid):
                            return [dict(r) for r in conn.execute("SELECT * FROM commands WHERE task_id=?", (tid,))]
                    task = check(Reader(), task_id, host, sid, action, params.get("control_version"))
                pointer = json.loads((registry.registry_path().parent / service.TASK_SERVICE_POINTER).read_text())
                from .task_daemon import request
                params["control_version"] = task["control_version"]
                return await asyncio.to_thread(request, "task_session_control", timeout=60,
                                               _url=pointer.get("endpoint"),
                                               _auth_token=(db.parent / "task-admin.token").read_text().strip(),
                                               task_id=task_id,
                                               host=host, session_id=sid, action=action, control=params)
            except TaskControlRefused:
                raise
            except (OSError, ValueError, sqlite3.Error) as exc:
                code = str(exc).split(":", 1)[0]
                if code.startswith(("TASK_", "CONTROL_VERSION_")):
                    raise TaskControlRefused(code, "task owner refused the control") from None
                raise TaskControlRefused("TASK_OWNER_UNAVAILABLE", "task owner cannot be reached") from None
        return wrapper
    return decorate


def refuse_owned(fleet, host, sid):
    if owner_task(fleet, host, sid):
        raise TaskControlRefused("TASK_OWNED_CONTROL_REQUIRED", "use the Task Service for this owned session")
