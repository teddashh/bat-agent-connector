"""Operations linked to the original task journal and coordinator commands."""

from __future__ import annotations

import asyncio
import json

from . import api_actions, api_auth, task_control
from .operations import ActionDef, OperationError, Uncertain

METHODS = {"work_submit": "task.submit", "work_pause": "task.pause", "work_resume": "task.resume",
           "work_mark_stage": "task.mark_stage", "task_send": "session.send",
           "task_run_verification": "task.verify", "task_request_ted": "task.request_ted",
           "work_reconcile": "task.command.reconcile"}


def _task_capability(ops, principal, tid):
    prefix = "task:" + tid + ":"
    if not principal.actor.startswith(prefix):
        return False
    digest = principal.actor[len(prefix):]
    return bool(ops.db.execute("SELECT 1 FROM capabilities WHERE token_hash=? AND task_id=? "
                               "AND scope='task' AND expires_at>strftime('%s','now')", (digest, tid)).fetchone())


def admit_task(ops, principal, target, params, pre):
    tid = target.get("task_id")
    if not isinstance(tid, str) or not tid:
        raise OperationError("INVALID_TARGET", "task_id is required", 422)
    if principal and principal.actor.startswith("task:") and not principal.actor.startswith("task:" + tid + ":"):
        raise OperationError("FORBIDDEN", "capability is bound to a different task", 403)
    if principal and principal.actor.startswith("reconcile:") and not principal.actor.startswith("reconcile:" + tid + ":"):
        raise OperationError("FORBIDDEN", "capability is bound to a different task", 403)
    task = ops.journal.get(tid)
    version = pre.get("control_version")
    if version is not None and (type(version) is not int or version != task["control_version"]):
        raise OperationError("CONTROL_VERSION_CONFLICT", "task control_version changed", 409)
    return task


def admit_submit(ops, principal, target, params, pre):
    for key in ("host", "workspace"):
        if not isinstance(target.get(key), str) or not target[key].strip():
            raise OperationError("INVALID_TARGET", key + " is required", 422)
    if not ops.context["fleet"].orchestrate_enabled(target["host"]):
        raise OperationError("TIER_DISABLED", "task host needs writes=true and orchestrate=true", 403)
    if (not isinstance(params.get("project"), str) or not params["project"].strip()
            or not isinstance(params.get("original_words"), str) or not params["original_words"].strip()
            or len(params["original_words"]) > 19_000):
        raise OperationError("INVALID_PARAMS", "project and original_words are required", 422)
    if params.get("continuation"):
        ops.journal.get(params.get("parent_task_id"))


def admit_control(ops, principal, target, params, pre):
    admit_task(ops, principal, target, params, pre)
    if params.get("actor", "service") not in {"service", "ted"}:
        raise OperationError("INVALID_PARAMS", "invalid actor", 422)
    if params.get("actor") == "ted" and not params.get("source_message_id"):
        raise OperationError("INVALID_PARAMS", "Ted action requires source_message_id", 422)
    if "abort_current" in params and type(params["abort_current"]) is not bool:
        raise OperationError("INVALID_PARAMS", "abort_current must be a boolean", 422)


def admit_stage(ops, principal, target, params, pre):
    task = admit_task(ops, principal, target, params, pre)
    if (params.get("stage") not in ops.journal.DELIVERY_STAGES[1:]
            or not isinstance(params.get("ref"), str) or not params["ref"].strip() or len(params["ref"]) > 300
            or params.get("actor", "service") not in {"service", "ted", "hermes", "executor"}):
        raise OperationError("INVALID_PARAMS", "stage, ref and actor must be valid", 422)
    if task["state"] != "done" or not task["verification_commit"]:
        raise OperationError("TASK_STATE_BLOCKED", "only a verified done task can be marked", 409)


def admit_request_ted(ops, principal, target, params, pre):
    admit_scoped(ops, principal, target, params, pre)
    if not isinstance(params.get("reason"), str) or not params["reason"].strip():
        raise OperationError("INVALID_PARAMS", "reason is required", 422)


def admit_send(ops, principal, target, params, pre):
    task = admit_task(ops, principal, target, params, pre)
    if not principal.admin and not _task_capability(ops, principal, task["task_id"]):
        raise OperationError("FORBIDDEN", "task send requires a task capability", 403)
    if (task["engine"] != "goose" or not isinstance(params.get("text"), str) or not params["text"].strip()
            or len(params["text"]) > 18_000 or not isinstance(params.get("step_id"), str)
            or not 0 < len(params["step_id"]) <= 128):
        raise OperationError("INVALID_PARAMS", "Goose task, text and step_id are required", 422)
    if not task.get("session_id"):
        raise OperationError("TASK_STATE_BLOCKED", "task has no current BAT session", 409)
    api_actions._admit_session(ops, principal, {"host": task["host"], "session_id": task["session_id"]},
                               params, pre)


def admit_scoped(ops, principal, target, params, pre):
    task = admit_task(ops, principal, target, params, pre)
    if task["engine"] != "goose" or (not principal.admin and not _task_capability(ops, principal, task["task_id"])):
        raise OperationError("FORBIDDEN", "a Goose task capability is required", 403)
    if task["paused"]:
        raise OperationError("TASK_PAUSED", "task is paused", 409)
    if task["state"] in {"done", "failed", "human_owned", "needs_ted", "uncertain"}:
        raise OperationError("TASK_STATE_BLOCKED", "task is not dispatchable", 409)


def admit_verify(ops, principal, target, params, pre):
    admit_scoped(ops, principal, target, params, pre)
    if params:
        raise OperationError("INVALID_PARAMS", "caller-supplied verification evidence is forbidden", 422)


def admit_reconcile(ops, principal, target, params, pre):
    admit_task(ops, principal, target, params, pre)
    cid = target.get("command_id")
    prefix = f"reconcile:{target['task_id']}:{cid}:"
    if not principal.actor.startswith(prefix):
        raise OperationError("FORBIDDEN", "command-scoped reconciliation capability required", 403)
    digest = principal.actor[len(prefix):]
    row = ops.db.execute("SELECT 1 FROM capabilities WHERE token_hash=? AND task_id=? AND command_id=? "
                         "AND scope='reconcile' AND expires_at>strftime('%s','now')",
                         (digest, target["task_id"], cid)).fetchone()
    if not row:
        raise OperationError("FORBIDDEN", "reconciliation capability is invalid", 403)


async def run(ctx):
    method = next(k for k, v in METHODS.items() if v == ctx.op["action"])
    params = {**ctx.params, **ctx.target}
    params.pop("legacy_idempotency_key", None)
    if ctx.op["action"] == "task.submit":
        # New task keys are operation identities; the old global task key is only a local-admin bridge.
        bridge = ctx.service.db.execute(
            "SELECT response FROM operation_steps WHERE operation_id=? AND name='legacy_task_key' AND status='succeeded'",
            (ctx.operation_id,)).fetchone()
        params["idempotency_key"] = json.loads(bridge["response"])["key"] if bridge and ctx.actor == api_auth.ADMIN_ACTOR else ctx.operation_id
    if ctx.op["action"] == "task.command.reconcile":
        params["_capability_hash"] = ctx.actor.rsplit(":", 1)[1]
    async def execute():
        receipt_name = {"task.pause": "task_pause", "task.resume": "task_resume", "task.mark_stage": "task_mark_stage",
                        "task.verify": "task_verification", "task.request_ted": "task_request_ted",
                        "task.command.reconcile": "task_reconcile"}.get(ctx.op["action"])
        receipt = ctx.service.db.execute(
            "SELECT response FROM operation_steps WHERE operation_id=? AND name=? AND status='succeeded'",
            (ctx.operation_id, receipt_name)).fetchone() if receipt_name else None
        if receipt and ctx.op["action"] in {"task.resume", "task.mark_stage", "task.verify", "task.request_ted"}:
            return json.loads(receipt["response"])
        if not receipt and ctx.op["action"] != "task.submit":
            admit_task(ctx.service, None, ctx.target, ctx.params, ctx.preconditions)
        if ctx.op["action"] == "task.verify":
            task = ctx.service.journal.get(ctx.target["task_id"])
            task_control.check(ctx.service.journal, task["task_id"], task["host"], task["session_id"],
                               "verify", ctx.preconditions.get("control_version"))
        try:
            return await ctx.service.context["daemon"].call(method, params, _ctx=ctx)
        except ValueError as exc:
            code = "IDEMPOTENCY_CONFLICT" if "idempotency_key already belongs" in str(exc) else "INVALID_PARAMS"
            raise OperationError(code, str(exc), 409 if code == "IDEMPOTENCY_CONFLICT" else 422) from None
    if ctx.op["action"] in {"task.verify", "task.request_ted", "task.mark_stage"}:
        async with ctx.service.context["coordinator"]._task_locks.setdefault(ctx.target["task_id"], asyncio.Lock()):
            result = await execute()
    else:
        result = await execute()
    if result.get("task_id"):
        ctx.set_refs(task_id=result["task_id"])
    if ctx.op["action"] == "task.command.reconcile" and ctx.params.get("next_prompt") and result.get("state") == "uncertain":
        raise Uncertain("task_dispatch", "new follow-up command requires reconciliation")
    return result


async def send(ctx):
    coordinator = ctx.service.context["coordinator"]
    tid = ctx.target["task_id"]
    async with coordinator._task_locks.setdefault(tid, asyncio.Lock()):
        def bind():
            task = coordinator.journal.get(tid)
            version = ctx.preconditions.get("control_version")
            if version is not None and version != task["control_version"]:
                raise OperationError("CONTROL_VERSION_CONFLICT", "task control_version changed", 409)
            return {"host": task["host"], "session_id": task["session_id"], "control_version": task["control_version"]}
        binding = ctx.effect("task_binding", bind)
        ctx.set_refs(task_id=tid, **binding)
        recovering = ctx.service.db.execute(
            "SELECT 1 FROM operation_steps WHERE operation_id=? AND name='task_send_command' AND status='succeeded'",
            (ctx.operation_id,)).fetchone()
        task = coordinator.journal.get(tid) if recovering else task_control.check(
            coordinator.journal, tid, binding["host"], binding["session_id"], "send", binding["control_version"])
        result = await coordinator._send(task, binding["session_id"], ctx.params["text"],
                                          "goose:" + ctx.params["step_id"], operation=ctx)
        if result["state"] == "uncertain":
            raise Uncertain("task_send", "original task send requires reconciliation")
        return result


ACTIONS = [
    ActionDef("task.submit", "start", "Submit exact words to the existing Task Service", run, admit_submit),
    ActionDef("task.pause", "operate", "Pause task dispatch and optionally abort its turn", run, admit_control, ("task_id",)),
    ActionDef("task.resume", "operate", "Resume task dispatch after command reconciliation", run, admit_control, ("task_id",)),
    ActionDef("task.mark_stage", "manage", "Record adoption, merge or deployment of a verified task", run, admit_stage, ("task_id",)),
    ActionDef("task.verify", "operate", "Run the trusted task verifier", run, admit_verify, ("task_id",)),
    ActionDef("task.request_ted", "operate", "Stop task dispatch for a human decision", run, admit_request_ted, ("task_id",)),
    ActionDef("task.command.reconcile", "operate", "Resolve the original uncertain task command", run, admit_reconcile,
              ("task_id", "command_id")),
]
