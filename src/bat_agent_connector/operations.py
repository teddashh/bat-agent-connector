"""Durable operations: one record per Dashboard, MCP or CLI action, shared by every entry point.

An operation is persisted (intent, actor, idempotency key, preconditions) before anything reaches BAT, Git or a
provider. Each external call is a named step whose intent is committed first; a timeout or lost connection leaves
the step ``uncertain`` and is settled by reading state back, never by sending again. HTTP (/api/v1), MCP and CLI
all call ``OperationService.create`` and read the same rows, so they share one permission, precondition, execution
and record path. Design: docs/design/api-v1.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .api_auth import Principal
from .errors import (
    BatError,
    ConnectionLost,
    InvokeTimeout,
    ResourceReadOnly,
    TaskControlRefused,
    WriteRefused,
)
from .redact import redact

STATES = ("accepted", "running", "waiting_checks", "waiting_external", "needs_attention", "uncertain",
          "succeeded", "failed", "cancelled")
TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
# Rows the worker picks up again (``running`` after a restart replays its steps).
RUNNABLE = ("accepted", "running", "waiting_checks", "waiting_external", "uncertain")
ALLOWED = {
    "accepted": {"running", "failed", "cancelled"},
    "running": {"running", "waiting_checks", "waiting_external", "needs_attention", "uncertain", "succeeded",
                "failed", "cancelled"},
    "waiting_checks": {"running", "cancelled"},
    "waiting_external": {"running", "cancelled"},
    # No uncertain -> cancelled: a cancel waits for the read-back, so "cancelled" never hides a step that ran.
    "uncertain": {"running", "needs_attention"},
    "needs_attention": {"running", "cancelled", "failed"},
}
UNCERTAIN_RETRY_S = (30.0, 60.0, 120.0, 300.0, 600.0)


class AmbiguousOutcome(Exception):
    """An external call whose effect is unknown (timeout, lost connection, 5xx after sending)."""


AMBIGUOUS = (InvokeTimeout, ConnectionLost, asyncio.TimeoutError, AmbiguousOutcome)
# A reconcile function returns RERUN when it proved the earlier attempt had no effect and the call is safe to
# make again (for example a merge request deduplicated by the provider). Only use it with such proof.
RERUN: dict = {"__rerun__": True}


class OperationError(Exception):
    """A request the service refuses; ``status`` is the HTTP status the API returns."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code, self.message, self.status = code, message, status
        super().__init__(f"[{code}] {message}")


class NeedsAttention(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code, self.message = code, message
        super().__init__(message)


class Wait(Exception):
    """Pause the operation in ``waiting_checks``/``waiting_external`` and run it again after ``delay_s``."""

    def __init__(self, status: str, reason: str, delay_s: float = 30.0, refs: dict | None = None) -> None:
        if status not in {"waiting_checks", "waiting_external"}:
            raise ValueError("wait status must be waiting_checks or waiting_external")
        self.status, self.reason, self.delay_s, self.refs = status, reason, max(1.0, delay_s), refs or {}
        super().__init__(reason)


class Uncertain(Exception):
    def __init__(self, step: str, message: str) -> None:
        self.step, self.message = step, message
        super().__init__(message)


class StepFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code, self.message = code, message
        super().__init__(message)


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class ActionDef:
    """One action: its scope, its static admission check, and its handler."""

    name: str
    scope: str
    summary: str
    run: Callable[[OpContext], Awaitable[dict]]
    admit: Callable[[OperationService, Principal, dict, dict, dict], None] | None = None
    target_keys: tuple[str, ...] = ()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, ResourceReadOnly | TaskControlRefused):
        return exc.code
    if isinstance(exc, StepFailed | NeedsAttention | OperationError):
        return exc.code
    if isinstance(exc, WriteRefused):
        return "REFUSED"
    if isinstance(exc, BatError):
        return "BAT_ERROR"
    return "INTERNAL"


@dataclass
class OpContext:
    service: OperationService
    op: dict
    replayed: list[str] = field(default_factory=list)

    @property
    def operation_id(self) -> str:
        return self.op["operation_id"]

    @property
    def target(self) -> dict:
        return self.op["target"]

    @property
    def params(self) -> dict:
        return self.op["params"]

    @property
    def preconditions(self) -> dict:
        return self.op["preconditions"]

    @property
    def actor(self) -> str:
        return self.op["actor"]

    def check_cancel(self) -> None:
        row = self.service.db.execute("SELECT cancel_requested FROM operations WHERE operation_id=?",
                                      (self.operation_id,)).fetchone()
        if row and row["cancel_requested"]:
            raise Cancelled()

    def set_refs(self, **refs: Any) -> None:
        self.service._merge_refs(self.operation_id, refs)

    def effect(self, name: str, fn: Callable[[], dict], *, request: dict | None = None) -> dict:
        """Commit a local task effect and its receipt in one journal transaction.

        A started receipt without a result proves the effect transaction rolled back. Replaying the
        original journal method is safe; no BAT/provider call may run inside this callback.
        """
        row = self.service.db.execute("SELECT * FROM operation_steps WHERE operation_id=? AND name=?",
                                      (self.operation_id, name)).fetchone()
        if row and row["status"] == "succeeded":
            self.replayed.append(name)
            return json.loads(row["response"] or "{}")
        self.check_cancel()
        if row is None:
            self.service._step_start(self.operation_id, name, request or {})
        with self.service.journal.tx():
            result = fn()
            self.service._step_done(self.operation_id, name, result or {})
        return result or {}

    async def step(self, name: str, fn: Callable[[], Awaitable[dict]], *, request: dict | None = None,
                   reconcile: Callable[[dict], Awaitable[dict | None]] | None = None) -> dict:
        """Run one external call exactly once from this record's point of view.

        A finished step returns its stored response. A step whose earlier run never recorded an outcome (process
        restart, timeout, lost connection) is ``uncertain``: ``reconcile`` reads the outside world back and returns
        the response, or None when the outcome still cannot be proven. The call is never repeated.
        """
        db = self.service.db
        row = db.execute("SELECT * FROM operation_steps WHERE operation_id=? AND name=?",
                         (self.operation_id, name)).fetchone()
        if row is not None:
            if row["status"] == "succeeded":
                self.replayed.append(name)
                return json.loads(row["response"] or "{}")
            if row["status"] == "failed":
                err = json.loads(row["error"] or "{}")
                raise StepFailed(err.get("code", "STEP_FAILED"), err.get("message", "step failed earlier"))
            try:
                recovered = await reconcile(json.loads(row["request"])) if reconcile else None
            except (*AMBIGUOUS, BatError, OSError):  # the read-back itself failed: still unproven, try later
                recovered = None
            if recovered is None:
                self.service._step_status(self.operation_id, name, "uncertain")
                raise Uncertain(name, f"outcome of step {name!r} is not proven; reading it back again later")
            if recovered is not RERUN:
                self.service._step_done(self.operation_id, name, recovered, reconciled=True)
                return recovered
            try:  # proven not to have happened: a cancel requested meanwhile stops here instead of sending it now
                self.check_cancel()
            except Cancelled:
                self.service._step_status(self.operation_id, name, "failed",
                                          error={"code": "CANCELLED", "message": "proven not sent; cancelled"})
                raise
            self.service._step_restart(self.operation_id, name, request or {})
        else:
            self.check_cancel()
            self.service._step_start(self.operation_id, name, request or {})
        try:
            response = await fn()
        except (*AMBIGUOUS, OSError) as exc:  # OSError: local bookkeeping may fail after the external call
            self.service._step_status(self.operation_id, name, "uncertain",
                                      error={"code": "UNCERTAIN", "message": redact(f"{type(exc).__name__}: {exc}")})
            raise Uncertain(name, f"step {name!r} may or may not have happened ({type(exc).__name__})") from None
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised as a definitive failure
            code = _error_code(exc)
            message = redact(str(exc)) if isinstance(exc, BatError | OperationError | StepFailed) else type(exc).__name__
            self.service._step_status(self.operation_id, name, "failed", error={"code": code, "message": message})
            raise StepFailed(code, message) from exc
        self.service._step_done(self.operation_id, name, response or {})
        return response or {}


class OperationService:
    def __init__(self, journal, *, actions: list[ActionDef] | None = None) -> None:
        self.journal = journal
        self.db = journal.db
        self.actions: dict[str, ActionDef] = {}
        self._active: dict[str, asyncio.Task] = {}
        self._wake: asyncio.Event | None = None
        self.context: dict[str, Any] = {}  # handlers' shared dependencies (fleet, inventory, ...)
        for a in actions or []:
            self.register(a)

    def register(self, action: ActionDef) -> None:
        if action.name in self.actions:
            raise ValueError(f"action {action.name} is already registered")
        self.actions[action.name] = action

    # ------------------------------------------------------------------ records
    def _row(self, operation_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        return self._decode(row) if row else None

    @staticmethod
    def _decode(row) -> dict:
        op = dict(row)
        for key in ("target", "params", "preconditions"):
            op[key] = json.loads(op[key])
        for key in ("result", "external_refs"):
            op[key] = json.loads(op[key]) if op[key] else None
        op["cancel_requested"] = bool(op["cancel_requested"])
        op.pop("request_hash", None)
        return op

    def get(self, operation_id: str, *, steps: bool = True) -> dict:
        op = self._row(operation_id)
        if op is None:
            raise OperationError("NOT_FOUND", "operation not found", 404)
        if steps:
            op["steps"] = [{"seq": r["seq"], "name": r["name"], "status": r["status"],
                            "external_ref": r["external_ref"],
                            "error": json.loads(r["error"]) if r["error"] else None,
                            "started_at": r["started_at"], "finished_at": r["finished_at"]}
                           for r in self.db.execute("""SELECT * FROM operation_steps WHERE operation_id=?
                               ORDER BY seq""", (operation_id,))]
        return op

    def list(self, *, statuses: list[str] | None = None, actor: str | None = None, action: str | None = None,
             before: float | None = None, limit: int = 50) -> dict:
        limit = max(1, min(200, int(limit)))
        sql, args = "SELECT * FROM operations WHERE 1=1", []
        if statuses:
            bad = [s for s in statuses if s not in STATES]
            if bad:
                raise OperationError("INVALID_FILTER", f"unknown status {bad[0]!r}", 422)
            sql += f" AND status IN ({','.join('?' * len(statuses))})"  # noqa: S608 - placeholders only
            args += statuses
        if actor:
            sql, args = sql + " AND actor=?", [*args, actor]
        if action:
            sql, args = sql + " AND action=?", [*args, action]
        if before is not None:
            sql, args = sql + " AND created_at<?", [*args, float(before)]
        rows = self.db.execute(sql + " ORDER BY created_at DESC LIMIT ?", (*args, limit + 1)).fetchall()
        ops = [self._decode(r) for r in rows[:limit]]
        return {"operations": ops, "next_before": ops[-1]["created_at"] if len(rows) > limit else None}

    def _transition(self, operation_id: str, status: str, *, reason: str | None = None,
                    error_code: str | None = None, result: dict | None = None, next_run_at: float = 0.0,
                    attempts: int | None = None, uncertain_tries: int | None = None,
                    actor: str | None = None) -> dict:
        with self.journal.tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise OperationError("NOT_FOUND", "operation not found", 404)
            old = row["status"]
            if old in TERMINAL:
                return self._decode(row)
            if status not in ALLOWED.get(old, set()):
                raise ValueError(f"operation transition {old} -> {status} is not allowed")
            now = time.time()
            self.db.execute("""UPDATE operations SET status=?,status_reason=?,error_code=?,
                result=COALESCE(?,result),next_run_at=?,attempts=COALESCE(?,attempts),
                uncertain_tries=COALESCE(?,uncertain_tries),version=version+1,updated_at=? WHERE operation_id=?""",
                            (status, (reason or "")[:500] or None, error_code,
                             _canonical(result) if result is not None else None, next_run_at, attempts,
                             uncertain_tries, now, operation_id))
            if status != old:
                self.journal.api_event("operation", operation_id, "operation." + status,
                                       {"action": row["action"], "from": old, "to": status,
                                        "error_code": error_code, "reason": (reason or "")[:200] or None},
                                       actor=actor or row["actor"])
        return self._row(operation_id)

    def _merge_refs(self, operation_id: str, refs: dict) -> None:
        with self.journal.tx():
            row = self.db.execute("SELECT external_refs FROM operations WHERE operation_id=?",
                                  (operation_id,)).fetchone()
            merged = {**(json.loads(row["external_refs"]) if row and row["external_refs"] else {}), **refs}
            self.db.execute("UPDATE operations SET external_refs=?,updated_at=? WHERE operation_id=?",
                            (_canonical(merged), time.time(), operation_id))

    def _step_start(self, operation_id: str, name: str, request: dict) -> None:
        with self.journal.tx():
            seq = self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM operation_steps WHERE operation_id=?",
                                  (operation_id,)).fetchone()[0]
            self.db.execute("""INSERT INTO operation_steps(operation_id,seq,name,status,request,started_at)
                VALUES(?,?,?,?,?,?)""", (operation_id, seq, name, "started", _canonical(request), time.time()))

    def _step_restart(self, operation_id: str, name: str, request: dict) -> None:
        with self.journal.tx():
            self.db.execute("""UPDATE operation_steps SET status='started',request=?,response=NULL,error=NULL,
                started_at=?,finished_at=NULL WHERE operation_id=? AND name=?""",
                            (_canonical(request), time.time(), operation_id, name))

    def _step_done(self, operation_id: str, name: str, response: dict, *, reconciled: bool = False) -> None:
        with self.journal.tx():
            self.db.execute("""UPDATE operation_steps SET status='succeeded',response=?,finished_at=?,
                external_ref=COALESCE(?,external_ref) WHERE operation_id=? AND name=?""",
                            (_canonical({**response, **({"reconciled": True} if reconciled else {})}),
                             time.time(), response.get("external_ref"), operation_id, name))

    def _step_status(self, operation_id: str, name: str, status: str, *, error: dict | None = None) -> None:
        with self.journal.tx():
            self.db.execute("""UPDATE operation_steps SET status=?,error=COALESCE(?,error),
                finished_at=CASE WHEN ?='failed' THEN ? ELSE finished_at END WHERE operation_id=? AND name=?""",
                            (status, _canonical(error) if error else None, status, time.time(), operation_id,
                             name))

    # ------------------------------------------------------------------ create / cancel
    def create(self, principal: Principal, *, action: str, target: dict | None = None, params: dict | None = None,
               preconditions: dict | None = None, idempotency_key: str, entry: str = "http") -> tuple[dict, bool]:
        """Persist an operation (or return the one this key already created). Returns (operation, created)."""
        adef = self.actions.get(action)
        if adef is None:
            raise OperationError("UNKNOWN_ACTION", f"unknown action {action!r}", 422)
        if not principal.allows(adef.scope):
            raise OperationError("FORBIDDEN", f"{action} needs the {adef.scope!r} scope", 403)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 200:
            raise OperationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency_key must be 1-200 characters", 422)
        target, params, preconditions = target or {}, params or {}, preconditions or {}
        if not all(isinstance(x, dict) for x in (target, params, preconditions)):
            raise OperationError("INVALID_REQUEST", "target, params and preconditions must be objects", 422)
        missing = [k for k in adef.target_keys if not isinstance(target.get(k), str) or not target[k]]
        if missing:
            raise OperationError("INVALID_TARGET", f"target needs {', '.join(missing)}", 422)
        request_hash = hashlib.sha256(_canonical({"action": action, "target": target, "params": params,
                                                  "preconditions": preconditions}).encode()).hexdigest()
        key = idempotency_key.strip()
        existing = self.db.execute("SELECT * FROM operations WHERE actor=? AND idem_key=?",
                                   (principal.actor, key)).fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise OperationError("IDEMPOTENCY_CONFLICT",
                                     "this idempotency_key was already used for a different request", 409)
            return self._decode(existing), False
        if adef.admit:
            adef.admit(self, principal, target, params, preconditions)
        operation_id = "op_" + uuid.uuid4().hex
        now = time.time()
        with self.journal.tx():
            self.db.execute("""INSERT INTO operations(operation_id,actor,entry,idem_key,request_hash,action,target,
                params,preconditions,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (operation_id, principal.actor, entry[:20], key, request_hash, action,
                             _canonical(target), _canonical(params), _canonical(preconditions), "accepted", now,
                             now))
            self.journal.api_event("operation", operation_id, "operation.accepted",
                                   {"action": action, "target": target, "entry": entry}, actor=principal.actor)
        self.kick()
        return self._row(operation_id), True

    def _may_steer(self, principal: Principal, op: dict, verb: str) -> None:
        adef = self.actions.get(op["action"])
        if not (op["actor"] == principal.actor or principal.admin or (adef and principal.allows(adef.scope))):
            raise OperationError("FORBIDDEN", f"{verb} needs the operation's own actor or its {op['action']} scope",
                                 403)

    def _running(self, operation_id: str) -> bool:
        task = self._active.get(operation_id)
        return task is not None and not task.done()

    def cancel(self, principal: Principal, operation_id: str) -> dict:
        """Stop an operation before its next step. A step that may already have run is read back first, so a
        cancelled operation never hides an action that happened."""
        op = self.get(operation_id, steps=False)
        self._may_steer(principal, op, "cancel")
        if op["status"] in TERMINAL:
            return op
        self.db.execute("UPDATE operations SET cancel_requested=1,updated_at=? WHERE operation_id=?",
                        (time.time(), operation_id))
        if not self._running(operation_id):
            if op["status"] in {"accepted", "waiting_checks", "waiting_external"}:
                return self._transition(operation_id, "cancelled", actor=principal.actor,
                                        reason=f"cancelled by {principal.actor} before the next step")
            if op["status"] == "needs_attention":
                open_steps = [r["name"] for r in self.db.execute(
                    "SELECT name FROM operation_steps WHERE operation_id=? AND status IN ('started','uncertain')",
                    (operation_id,))]
                note = f"; the outcome of {', '.join(open_steps)} was never proven" if open_steps else ""
                return self._transition(operation_id, "cancelled", actor=principal.actor,
                                        reason=f"cancelled by {principal.actor}{note}")
            if op["status"] == "uncertain":  # read the step back now; the run stops before any new step
                self.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (operation_id,))
        self.kick()
        return self.get(operation_id, steps=False)

    def resume(self, principal: Principal, operation_id: str) -> dict:
        """Run a needs_attention operation again: finished steps replay, an unproven step is read back (never
        re-sent), and the handler's checks run afresh."""
        op = self.get(operation_id, steps=False)
        self._may_steer(principal, op, "resume")
        if op["status"] != "needs_attention":
            raise OperationError("NOT_RESUMABLE", f"only needs_attention operations resume (this one is "
                                 f"{op['status']})", 409)
        op = self._transition(operation_id, "running", reason=f"resumed by {principal.actor}", uncertain_tries=0,
                              actor=principal.actor)
        self.kick()
        return op

    # ------------------------------------------------------------------ execution
    def kick(self) -> None:
        if self._wake is not None:
            self._wake.set()

    async def run_due(self) -> None:
        now = time.time()
        placeholders = ",".join("?" * len(RUNNABLE))
        rows = self.db.execute(f"""SELECT operation_id FROM operations WHERE status IN ({placeholders})
            AND next_run_at<=? ORDER BY created_at""", (*RUNNABLE, now)).fetchall()  # noqa: S608
        for row in rows:
            op_id = row["operation_id"]
            if not self._running(op_id):
                task = asyncio.create_task(self._execute(op_id), name=f"op-{op_id[:11]}")
                self._active[op_id] = task
                task.add_done_callback(
                    lambda t, k=op_id: self._active.pop(k, None) if self._active.get(k) is t else None)

    async def loop(self, interval_s: float = 1.0) -> None:
        self._wake = asyncio.Event()
        while True:
            try:
                await self.run_due()
            except Exception as exc:  # noqa: BLE001 - one bad row must not stop the loop
                logging.warning("operation loop error: %s", type(exc).__name__)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wake.wait(), interval_s)
            self._wake.clear()

    async def drain(self, timeout: float = 5.0) -> None:
        """Run due operations until nothing is runnable now (tests and one-shot CLI use)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await self.run_due()
            pending = [t for t in self._active.values() if not t.done()]
            if not pending:
                return
            await asyncio.wait(pending, timeout=max(0.01, deadline - time.monotonic()))

    async def wait(self, operation_id: str, timeout: float) -> dict:
        """Return once the operation leaves accepted/running, or after ``timeout`` seconds."""
        deadline = time.monotonic() + max(0.0, min(timeout, 60.0))
        while True:
            op = self.get(operation_id)
            if op["status"] not in {"accepted", "running"} or time.monotonic() >= deadline:
                return op
            await asyncio.sleep(0.1)

    async def _execute(self, operation_id: str) -> None:
        op = self._row(operation_id)
        if op is None or op["status"] in TERMINAL:
            return
        adef = self.actions.get(op["action"])
        if adef is None:
            self._transition(operation_id, "failed", error_code="UNKNOWN_ACTION",
                             reason=f"no handler for {op['action']} in this connector version")
            return
        if op["cancel_requested"] and op["status"] not in {"running", "uncertain"}:
            self._transition(operation_id, "cancelled", reason="cancelled before the next step")
            return
        if op["status"] != "running":
            op = self._transition(operation_id, "running", attempts=op["attempts"] + 1)
        ctx = OpContext(self, op)
        try:
            result = await adef.run(ctx)
        except Cancelled:
            self._transition(operation_id, "cancelled", reason="cancelled between steps")
        except Wait as w:
            if w.refs:
                self._merge_refs(operation_id, w.refs)
            self._transition(operation_id, w.status, reason=w.reason, next_run_at=time.time() + w.delay_s,
                             uncertain_tries=0)
        except NeedsAttention as n:
            self._transition(operation_id, "needs_attention", error_code=n.code, reason=n.message)
        except Uncertain as u:
            # Its own budget: resumes from waiting_* do not use up the read-backs.
            tries = op["uncertain_tries"] + 1
            if tries > len(UNCERTAIN_RETRY_S):
                self._transition(operation_id, "uncertain", error_code="UNCERTAIN", reason=u.message,
                                 uncertain_tries=tries)
                self._transition(operation_id, "needs_attention", error_code="UNCERTAIN_UNRESOLVED",
                                 reason=f"{u.message}; read-back did not settle it after {tries} attempts")
            else:
                self._transition(operation_id, "uncertain", error_code="UNCERTAIN", reason=u.message,
                                 next_run_at=time.time() + UNCERTAIN_RETRY_S[tries - 1], uncertain_tries=tries)
        except StepFailed as f:
            self._transition(operation_id, "failed", error_code=f.code, reason=f.message)
        except (OperationError, ResourceReadOnly, WriteRefused, BatError) as e:
            self._transition(operation_id, "failed", error_code=_error_code(e), reason=redact(str(e)))
        except Exception as e:  # noqa: BLE001 - never leave a row running without an outcome
            logging.warning("operation %s handler error: %s", operation_id, type(e).__name__)
            self._transition(operation_id, "failed", error_code="INTERNAL", reason=type(e).__name__)
        else:
            self._transition(operation_id, "succeeded", result=result or {})
