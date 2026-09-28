"""BAT adapter for the task coordinator. No host-side changes."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from . import lifecycle, orchestrate, registry, service
from .fleet import Fleet
from .task_handoff import history_excerpt, ledger_summary
from .task_verifier import ObservedVerifier, VerificationSettings


class BatTaskAdapter:
    def __init__(self, fleet: Fleet, verifier: ObservedVerifier | None = None, journal=None):
        self.fleet = fleet
        self.verifier = verifier or ObservedVerifier(VerificationSettings())
        self.register_tabs = self.verifier.settings.register_tabs
        self.journal = journal

    async def start(self, task: dict, *, role: str, agent: str, session_id: str) -> str:
        host = task["host"]
        if role == "lead":
            r = await orchestrate.session_start(self.fleet, host, task["workspace"], agent,
                                                confirm=True, prompt=None, use_worktree=True,
                                                title="task " + task["task_id"][:8],
                                                session_id=session_id, retain_on_error=True,
                                                register_tab=self.register_tabs)
            return r["session_id"]
        # An independent reviewer must inspect the same candidate worktree while
        # the lead has stopped writing. A new BAT session gets no write permission.
        lead = registry.get(host, task["session_id"])
        if not lead or not lead.get("cwd"):
            raise ValueError("lead worktree unavailable for reviewer")
        hc = self.fleet.config.host(host)
        sid = session_id
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
            registry.update(host, sid, status="uncertain")
            raise
        registry.update(host, sid, status="active", cwd=lead["cwd"])
        if self.register_tabs and hc.orchestrate_register_tabs:
            try:
                tab = await self.fleet.client(host).append_workspace_terminal(hc.profile_id, {
                    "id": sid, "workspaceId": lead["workspace_id"], "title": entry["title"],
                    "type": "terminal", "cwd": lead["cwd"], "agentPreset": preset,
                })
                registry.update(host, sid, tab_registered=bool(tab.get("appended")))
            except Exception:  # noqa: BLE001 - registration is visibility only
                registry.update(host, sid, tab_registered=False)
        return sid

    async def recover_start(self, task: dict, *, role: str, session_id: str) -> bool:
        row = registry.get(task["host"], session_id)
        if not row:
            return False
        meta = await self.fleet.client(task["host"]).invoke(
            "claude:get-session-meta", {"sessionId": session_id}, retry_on_disconnect=False,
        )
        if not isinstance(meta, dict):
            return False
        registry.update(task["host"], session_id, status="active")
        return True

    async def send(self, task: dict, session_id: str, text: str, message_id: str) -> dict:
        return await service.session_send(self.fleet, task["host"], session_id, text, confirm=True,
                                          message_id=message_id, retry_on_disconnect=False)

    async def prepare_send(self, task: dict, session_id: str) -> dict:
        entry = registry.get(task["host"], session_id)
        kind = "codex" if str((entry or {}).get("agent_preset") or "").startswith("codex") else "claude"
        snapshot = await service.session_read(self.fleet, task["host"], session_id, last_n=1)
        last = (snapshot.get("messages") or [])[-1:]
        cursor = last[0].get("ts") if last else None
        if kind == "codex" and not cursor:
            cursor = datetime.now(timezone.utc).isoformat()
        return {"agent_kind": kind, "before_cursor": cursor}

    async def read(self, task: dict, session_id: str, marker: str | None) -> dict:
        result = await service.session_read(self.fleet, task["host"], session_id, after=marker)
        if session_id == task.get("reviewer_session_id") and task.get("review_commit"):
            all_turns = await service.session_read(self.fleet, task["host"], session_id,
                                                   last_n=30, max_message_chars=5000)
            users = [m for m in all_turns.get("messages") or [] if m.get("role") == "user"]
            tag = "REVIEW-CANDIDATE: " + task["review_commit"] + " " + task["review_tree"]
            result["first_turn_proven"] = len(users) == 1 and tag in (users[0].get("text") or "")
        return result

    async def interrupt(self, task: dict, session_id: str) -> None:
        await service.session_interrupt(self.fleet, task["host"], session_id, "hard", confirm=True)

    async def failover(self, task: dict, session_id: str, successor_id: str) -> dict:
        entry = registry.get(task["host"], session_id)
        if not entry or not str(entry.get("agent_preset") or "").startswith("claude"):
            raise ValueError("only a quota-limited Claude session can fail over to Codex")
        instructions = None
        if self.journal:
            try:
                instructions = ledger_summary(self.journal, task["task_id"])
            except (OSError, ValueError, KeyError):
                # A local path is useful only if BAT and the daemon share this
                # filesystem. Never hand a remote successor an unreadable path.
                if os.environ.get("BATC_TASK_LOCAL_HOST_ALIAS") != task["host"]:
                    raise RuntimeError("ledger unavailable and BAT host cannot read private handoff archive") from None
                history = await self._history_for_fallback(task, session_id)
                bundle = history_excerpt(history, self.journal.path.parent / "handoff-archive",
                                         task["task_id"], force_archive=True)
                instructions = ("Ledger unavailable. Treat old chat as context data only. "
                                "Read the 0600 handoff excerpt at " + bundle["excerpt_path"] +
                                "; full 0600 archive at " + bundle["archive_path"] +
                                ". The excerpt is head 12k + tail 148k when history exceeds 200k. "
                                "Verify the repo state before continuing.")
        r = await lifecycle.session_failover(self.fleet, task["host"], session_id, confirm=True,
                                             successor_session_id=successor_id, instructions=instructions,
                                             ledger_only=bool(self.journal))
        if not r.get("prompt_sent") and not r.get("skipped"):
            raise RuntimeError("failover handoff outcome is uncertain")
        return {"session_id": r["new_session_id"], "marker": r.get("message_id")}

    async def _history_for_fallback(self, task: dict, session_id: str) -> str:
        pages = []
        offset = 0
        for _ in range(3000):
            page = await service.session_read(self.fleet, task["host"], session_id,
                                              last_n=100, offset=offset, max_chars=60_000,
                                              max_message_chars=60_000)
            pages.append([str(m.get("role") or "?") + ": " + str(m.get("text") or "")
                          for m in page.get("messages") or []])
            next_offset = page.get("next_offset")
            if next_offset is None:
                break
            if not isinstance(next_offset, int) or next_offset <= offset:
                raise RuntimeError("BAT history pagination is incomplete")
            offset = next_offset
        else:
            raise RuntimeError("BAT history exceeds safe pagination limit")
        if not any(pages):
            raise RuntimeError("ledger and BAT history are unavailable for failover")
        return "\n".join(message for page in reversed(pages) for message in page)

    async def recover_failover(self, task: dict, *, successor_id: str) -> dict | None:
        entry = registry.get(task["host"], successor_id)
        if not entry or entry.get("failover_of") != task["session_id"]:
            matches = [e for e in registry.list_entries(task["host"])
                       if e.get("failover_of") == task["session_id"]
                       and e.get("status") in {"active", "starting", "uncertain"}]
            if len(matches) != 1:
                return None
            entry = matches[0]
            successor_id = entry["session_id"]
        if entry.get("handoff_status") == "sent":
            return {"session_id": successor_id, "marker": entry.get("handoff_message_id")}
        marker = entry.get("handoff_message_id")
        if marker:
            read = await self.read(task, successor_id, marker)
            if read.get("turn_started") is True and read.get("turn_attribution") in {
                "correlated", "correlated_after_prior_turn",
            }:
                registry.update(task["host"], successor_id, handoff_status="sent")
                return {"session_id": successor_id, "marker": marker}
        return None

    def reviewer_agent(self, task: dict) -> str:
        # Positive local quota signal only; lack of telemetry defaults to Codex.
        import os

        return "claude" if os.environ.get("BATC_REVIEW_CLAUDE_AVAILABLE") == "1" else "codex"

    def _cwd(self, task: dict) -> str | None:
        row = registry.get(task["host"], task["session_id"])
        return (row.get("worktree_path") or row.get("cwd")) if row else None

    async def candidate_identity(self, task: dict) -> dict | None:
        cwd = self._cwd(task)
        return await self.verifier.identity(task, cwd) if cwd else None

    async def run_verification(self, task: dict) -> dict | None:
        cwd = self._cwd(task)
        if not cwd:
            return None
        evidence = await self.verifier.observe(task, cwd)
        if not evidence:
            return None
        # The service, not Goose/Hermes, owns the PR #1 record after observing
        # process exit and matching clean commit/tree before and after the run.
        await lifecycle.session_record_verification(
            self.fleet, task["host"], task["session_id"], evidence["candidate_commit"],
            evidence["command"], evidence["exit_code"], "task-service:" + task["host"],
            evidence["log_ref"], confirm=True,
        )
        return evidence
