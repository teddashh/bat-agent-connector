"""Operation handlers for /api/v1, MCP and CLI. Each wraps an existing connector function.

Session actions refuse sessions created in BAT twice: at admission (registry and inventory facts, so the caller gets
403 and no operation is stored) and again inside the call (the live resource policy check in service.py).
"""

from __future__ import annotations

import hashlib

from . import registry, resource_policy, service, task_control
from .api_auth import Principal
from .errors import TaskControlRefused
from .operations import ActionDef, NeedsAttention, OpContext, OperationError, OperationService


def _fleet(ops: OperationService):
    return ops.context["fleet"]


def _admit_session(ops: OperationService, principal: Principal, target: dict, params: dict, pre: dict,
                   action: str = "send") -> None:
    fleet = _fleet(ops)
    host, sid = target["host"], target["session_id"]
    if host not in fleet.config.hosts:
        raise OperationError("UNKNOWN_HOST", f"unknown host {host!r}", 404)
    if not fleet.writes_enabled(host):
        raise OperationError("TIER_DISABLED", f"the write tier is off for host {host}", 403)
    inventory = ops.context.get("inventory")
    row = inventory.get_session(host, sid) if inventory else None
    has_tab = bool(row and row.get("has_tab"))
    if row is None and registry.get(host, sid) is None:
        # Not observed yet and never created by the connector: nothing proves it is writable.
        raise OperationError("UNKNOWN_READ_ONLY", "the session is not in the inventory or the connector registry",
                             403)
    verdict = resource_policy.classify_row_for_read(fleet.config.host(host), sid, has_tab=has_tab,
                                                    entries=registry.list_entries(host))
    if verdict["api_access"] != "managed":
        raise OperationError(verdict.get("read_only_code", "READ_ONLY"),
                             f"session {sid[:8]} is {verdict['provenance']} and read-only through the API", 403)
    task_id = task_control.owner_task(fleet, host, sid)
    if task_id:
        coordinator = ops.context.get("coordinator")
        if coordinator is None:
            raise OperationError("TASK_OWNER_UNAVAILABLE", "task coordinator unavailable", 409)
        try:
            task_control.check(coordinator.journal, task_id, host, sid,
                               action, pre.get("control_version"))
        except TaskControlRefused as exc:
            raise OperationError(exc.code, str(exc), 409) from None


def _admit_send(ops: OperationService, principal: Principal, target: dict, params: dict, pre: dict) -> None:
    if target.get("task_id"):
        from .task_actions import admit_send
        admit_send(ops, principal, target, params, pre)
        return
    if not all(isinstance(target.get(k), str) and target[k] for k in SESSION_TARGET):
        raise OperationError("INVALID_TARGET", "host and session_id are required", 422)
    text = params.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > service.MAX_PROMPT_CHARS:
        raise OperationError("INVALID_PARAMS", f"text must be 1-{service.MAX_PROMPT_CHARS} characters", 422)
    _admit_session(ops, principal, target, params, pre)


async def _send(ctx: OpContext) -> dict:
    if ctx.target.get("task_id"):
        from .task_actions import send
        return await send(ctx)
    fleet = _fleet(ctx.service)
    host, sid = ctx.target["host"], ctx.target["session_id"]
    text = ctx.params["text"]
    mid = "batc-" + ctx.operation_id  # the clientMessageId BAT echoes back for Claude sessions

    async def send() -> dict:
        r = await service.session_send(fleet, host, sid, text, confirm=True, message_id=mid,
                                       queue=bool(ctx.params.get("queue")), tool="api:" + ctx.actor,
                                       retry_on_disconnect=False, control_version=ctx.preconditions.get("control_version"),
                                       operation_id=ctx.operation_id)
        return {k: r.get(k) for k in ("message_id", "accepted", "queued", "turn_marker", "turn_attribution",
                                      "marker_source", "resumed")}

    async def reconcile(_request: dict) -> dict | None:
        turn = registry.get_turn(host, sid, mid)
        if turn:  # recorded only after BAT accepted this exact clientMessageId
            return {"message_id": mid, "accepted": True, "queued": turn.get("queued"), "turn_marker": mid}
        # The reply may have been lost after BAT took the frame: BAT echoes a Claude prompt as a user message
        # whose id is the clientMessageId. Codex ignores that id, so a lost Codex reply stays unproven.
        c = fleet.client(host)
        kind = service.agent_kind((registry.get(host, sid) or {}).get("agent_preset"))
        if kind == "codex":
            return None
        state = await service._live_state(c, sid, kind, await service._meta(c, sid))
        if any(isinstance(m, dict) and m.get("id") == mid and m.get("role") == "user"
               for m in (state or {}).get("messages") or []):
            return {"message_id": mid, "accepted": True, "turn_marker": mid, "settled_by": "bat_transcript"}
        return None

    r = await ctx.step("send", send, request={"message_id": mid,
                                              "text_sha256": hashlib.sha256(text.encode()).hexdigest()},
                       reconcile=reconcile)
    if not r.get("accepted"):
        raise NeedsAttention("NOT_ACCEPTED", "BAT did not accept the message")
    return r


def _admit_answer(ops: OperationService, principal: Principal, target: dict, params: dict, pre: dict) -> None:
    # The exact prompt is required: without it an answer could land on whatever prompt is pending next, and a
    # read-back could not tell this prompt from another one.
    if not isinstance(params.get("tool_use_id"), str) or not params["tool_use_id"]:
        raise OperationError("INVALID_PARAMS", "tool_use_id (the pending prompt's toolUseId) is required", 422)
    if ("answers" in params) == ("permission" in params):
        raise OperationError("INVALID_PARAMS", "pass exactly one of answers or permission", 422)
    if "permission" in params and params["permission"] not in {"allow", "deny"}:
        raise OperationError("INVALID_PARAMS", "permission must be allow or deny", 422)
    _admit_session(ops, principal, target, params, pre, "answer")


async def _answer(ctx: OpContext) -> dict:
    fleet = _fleet(ctx.service)
    host, sid, p = ctx.target["host"], ctx.target["session_id"], ctx.params

    async def answer() -> dict:
        r = await service.session_answer(fleet, host, sid, confirm=True, answers=p.get("answers"),
                                         permission=p.get("permission"), deny_message=p.get("deny_message"),
                                         tool_use_id=p.get("tool_use_id"),
                                         control_version=ctx.preconditions.get("control_version"),
                                         operation_id=ctx.operation_id)
        return {k: r.get(k) for k in ("channel", "tool_use_id", "questions", "answered", "permission")}

    async def reconcile(request: dict) -> dict | None:
        # The answer cleared the pending prompt if BAT no longer shows that tool use as pending.
        c = fleet.client(host)
        kind = service.agent_kind((registry.get(host, sid) or {}).get("agent_preset"))
        state = await service._live_state(c, sid, kind, await service._meta(c, sid))
        pending = (state or {}).get("pendingAskUser") or (state or {}).get("pendingPermission") \
            if isinstance(state, dict) else None
        if isinstance(state, dict) and not (isinstance(pending, dict)
                                            and pending.get("toolUseId") == request.get("tool_use_id")):
            return {"tool_use_id": request.get("tool_use_id"), "settled_by": "pending_prompt_cleared"}
        return None

    return await ctx.step("answer", answer, request={"tool_use_id": p.get("tool_use_id")}, reconcile=reconcile)


def _admit_interrupt(ops: OperationService, principal: Principal, target: dict, params: dict, pre: dict) -> None:
    if params.get("mode", "soft") not in {"soft", "hard"}:
        raise OperationError("INVALID_PARAMS", "mode must be soft or hard", 422)
    _admit_session(ops, principal, target, params, pre, "interrupt")


async def _interrupt(ctx: OpContext) -> dict:
    fleet = _fleet(ctx.service)
    host, sid = ctx.target["host"], ctx.target["session_id"]

    async def interrupt() -> dict:
        r = await service.session_interrupt(fleet, host, sid, ctx.params.get("mode", "soft"), confirm=True,
                                            control_version=ctx.preconditions.get("control_version"),
                                            operation_id=ctx.operation_id)
        return {"channel": r.get("channel"), "mode": r.get("mode")}

    async def reconcile(_request: dict) -> dict | None:
        meta = await fleet.client(host).invoke("claude:get-session-meta", {"sessionId": sid})
        if isinstance(meta, dict) and not meta.get("isStreaming"):
            return {"settled_by": "session_not_streaming"}
        return None

    return await ctx.step("interrupt", interrupt, reconcile=reconcile)


SESSION_TARGET = ("host", "session_id")
ACTIONS = [
    ActionDef("session.send", "operate", "Send a message to a connector-managed session",
              _send, _admit_send),
    ActionDef("session.answer", "operate", "Answer a managed session's pending question or permission prompt",
              _answer, _admit_answer, SESSION_TARGET),
    ActionDef("session.interrupt", "operate", "Interrupt a managed session's running turn",
              _interrupt, _admit_interrupt, SESSION_TARGET),
]
