"""BAT adapter for the task coordinator. No host-side changes."""

from __future__ import annotations

import uuid

from . import lifecycle, orchestrate, registry, service, verification
from .fleet import Fleet


class BatTaskAdapter:
    def __init__(self, fleet: Fleet):
        self.fleet = fleet

    async def start(self, task: dict, *, role: str, agent: str) -> str:
        host = task["host"]
        if role == "lead":
            r = await orchestrate.session_start(self.fleet, host, task["workspace"], agent,
                                                confirm=True, prompt=None, use_worktree=True,
                                                title="task " + task["task_id"][:8])
            return r["session_id"]
        # An independent reviewer must inspect the same candidate worktree while
        # the lead has stopped writing. A new BAT session gets no write permission.
        lead = registry.get(host, task["session_id"])
        if not lead or not lead.get("cwd"):
            raise ValueError("lead worktree unavailable for reviewer")
        hc = self.fleet.config.host(host)
        sid = str(uuid.uuid4())
        preset = orchestrate.PRESETS[(agent, False)]
        entry = {"session_id": sid, "workspace_id": lead["workspace_id"],
                 "workspace_name": lead["workspace_name"], "agent_preset": preset,
                 "origin_cwd": lead["origin_cwd"], "cwd": lead["cwd"],
                 "title": "review " + task["task_id"][:8], "role": "reviewer"}
        registry.reserve(host, entry, hc.orchestrate_max_sessions)
        opts = {"cwd": lead["cwd"], "agentPreset": preset,
                "workspaceId": lead["workspace_id"], "workspaceName": lead["workspace_name"]}
        if agent == "codex":
            opts.update(codexSandboxMode="read-only", codexApprovalPolicy="never")
        else:
            opts["permissionMode"] = "plan"
        try:
            await self.fleet.client(host).invoke("claude:start-session", {"sessionId": sid, "options": opts},
                                                retry_on_disconnect=False)
        except BaseException:
            registry.fail_reservation(host, sid)
            raise
        registry.update(host, sid, status="active", cwd=lead["cwd"])
        return sid

    async def send(self, task: dict, session_id: str, text: str, message_id: str) -> dict:
        return await service.session_send(self.fleet, task["host"], session_id, text, confirm=True,
                                          message_id=message_id, retry_on_disconnect=False)

    async def read(self, task: dict, session_id: str, marker: str | None) -> dict:
        return await service.session_read(self.fleet, task["host"], session_id, after=marker)

    async def interrupt(self, task: dict, session_id: str) -> None:
        await service.session_interrupt(self.fleet, task["host"], session_id, "hard", confirm=True)

    async def failover(self, task: dict, session_id: str) -> str:
        r = await lifecycle.session_failover(self.fleet, task["host"], session_id, confirm=True)
        return r["new_session_id"]

    async def verification(self, task: dict) -> dict | None:
        rec = verification.get(task["host"], task["session_id"])
        if not rec:
            return None
        c = self.fleet.client(task["host"])
        entry = registry.get(task["host"], task["session_id"])
        if not entry:
            return None
        cwd = entry.get("worktree_path") or entry.get("cwd")
        head = await lifecycle._candidate_head(c, cwd)
        dirty = await lifecycle._git_dirty(c, cwd)
        return {**rec, "current": head == rec["candidate_commit"] and dirty == []
                and verification.matches(rec, head)}

    async def record_verification(self, task: dict, *, candidate_commit: str, command: str,
                                  exit_code: int, environment: str, log_ref: str) -> dict:
        return await lifecycle.session_record_verification(
            self.fleet, task["host"], task["session_id"], candidate_commit, command,
            exit_code, environment, log_ref, confirm=True,
        )
