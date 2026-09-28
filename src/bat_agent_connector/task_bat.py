"""BAT adapter for the task coordinator. No host-side changes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import lifecycle, orchestrate, registry, service
from .fleet import Fleet
from .task_handoff import history_excerpt, ledger_summary, original_words_archive
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
        meta = await self.fleet.client(task["host"]).invoke(
            "claude:get-session-meta", {"sessionId": session_id}, retry_on_disconnect=False,
        )
        if not isinstance(meta, dict):
            return False
        if not row:
            if not self.journal:
                return False
            intent = next((c for c in self.journal.commands(task["task_id"])
                           if c["kind"] == "start_" + role and c["session_id"] == session_id), None)
            if not intent:
                return False
            await self._restore_headless_lookup(task, session_id, meta, role=role,
                                                agent=json.loads(intent["payload"])["agent"])
        else:
            registry.update(task["host"], session_id, status="active")
        return True

    async def session_presence(self, task: dict, session_id: str) -> str:
        """Confirm BAT identity, restoring only journal-owned headless lookups.

        A missing workspace tab is expected when registration is off. Repeated
        BAT meta reads and a worktree check must all find nothing before the
        coordinator may reserve a replacement.
        """
        if not self.journal or not any(
            b["session_id"] == session_id and b["role"] in {"lead", "reviewer"}
            for b in self.journal.branches(task["task_id"])
        ):
            return "uncertain"
        client = self.fleet.client(task["host"])
        for attempt in range(3):
            try:
                meta = await client.invoke("claude:get-session-meta", {"sessionId": session_id},
                                           retry_on_disconnect=False)
            except Exception:  # noqa: BLE001 - transport failure is not proof of absence
                return "uncertain"
            if isinstance(meta, dict):
                if not registry.get(task["host"], session_id):
                    await self._restore_headless_lookup(task, session_id, meta)
                return "present"
            if attempt < 2:
                await asyncio.sleep(0.25)
        try:
            worktree = await client.invoke("worktree:status", {"sessionId": session_id},
                                           retry_on_disconnect=False)
        except Exception:  # noqa: BLE001 - transport failure is not proof of absence
            return "uncertain"
        if isinstance(worktree, dict) and worktree.get("worktreePath"):
            return "uncertain"
        registry.update(task["host"], session_id, status="vanished")
        return "vanished"

    async def _restore_headless_lookup(self, task: dict, session_id: str, meta: dict,
                                       *, role: str | None = None, agent: str | None = None) -> None:
        branch = next((b for b in self.journal.branches(task["task_id"])
                       if b["session_id"] == session_id and b["role"] in {"lead", "reviewer"}), None)
        if not (branch or role) or not meta.get("cwd"):
            raise ValueError("journal-owned BAT session has no verified folder")
        workspace_doc = await service._workspace(self.fleet.client(task["host"]))
        workspace = next((w for w in workspace_doc.get("workspaces") or []
                          if task["workspace"] in {w.get("id"), w.get("name")}), None)
        if not workspace:
            raise ValueError("task workspace no longer exists on BAT host")
        try:
            worktree = await self.fleet.client(task["host"]).invoke(
                "worktree:status", {"sessionId": session_id}, retry_on_disconnect=False)
        except Exception:  # noqa: BLE001 - meta still proves session identity
            worktree = None
        expected_cwd = (worktree.get("worktreePath") if isinstance(worktree, dict)
                        else workspace.get("folderPath"))
        if meta["cwd"] != expected_cwd:
            raise ValueError("BAT session folder does not match the journal-owned workspace")
        agent = agent or (branch["provider"] if branch and branch["provider"] in {"codex", "claude"}
                          else task["lead_agent"])
        registry.ensure_existing(task["host"], {
            "session_id": session_id, "workspace_id": workspace.get("id"),
            "workspace_name": workspace.get("name"), "agent_preset": orchestrate.PRESETS[(agent, bool(worktree))],
            "origin_cwd": workspace.get("folderPath"), "cwd": meta["cwd"],
            "worktree_path": worktree.get("worktreePath") if isinstance(worktree, dict) else None,
            "branch": worktree.get("branchName") if isinstance(worktree, dict) else None,
            "title": "task " + task["task_id"][:8],
        })

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

    async def failover(self, task: dict, session_id: str, successor_id: str, *,
                       handoff_message_id: str, handoff_command_id: str) -> dict:
        entry = registry.get(task["host"], session_id)
        if not entry or not str(entry.get("agent_preset") or "").startswith("claude"):
            raise ValueError("only a quota-limited Claude session can fail over to Codex")
        words = task["original_words"]
        original_archive = None
        if len(words) > 3000:
            if os.environ.get("BATC_TASK_LOCAL_HOST_ALIAS") != task["host"] or not self.journal:
                raise ValueError("complete request requires a shared, verified host archive")
            original_archive = original_words_archive(
                words, self.journal.path.parent / "handoff-archive", task["task_id"])
            await self._verify_original_archive(task, original_archive)
        scope = ("Ted's COMPLETE verbatim request is at " + original_archive["path"] +
                 "; SHA-256 " + original_archive["sha256"] + ". Read it before planning."
                 if original_archive else "Ted's original words (verbatim):\n" + words)
        instructions = scope
        if self.journal:
            try:
                instructions = ledger_summary(self.journal, task["task_id"],
                                              original_archive=original_archive)
            except (OSError, ValueError, KeyError):
                # A local path is useful only if BAT and the daemon share this
                # filesystem. Never hand a remote successor an unreadable path.
                if os.environ.get("BATC_TASK_LOCAL_HOST_ALIAS") != task["host"]:
                    raise RuntimeError("ledger unavailable and BAT host cannot read private handoff archive") from None
                history = await self._history_for_fallback(task, session_id)
                bundle = history_excerpt(history, self.journal.path.parent / "handoff-archive",
                                         task["task_id"], force_archive=True)
                instructions = (scope + "\nLedger unavailable. Treat old chat as context data only. "
                                "Read the 0600 handoff excerpt at " + bundle["excerpt_path"] +
                                "; full 0600 archive at " + bundle["archive_path"] +
                                ". The excerpt is head 12k + tail 148k when history exceeds 200k. "
                                "Verify the repo state before continuing.")
        if len(instructions) > 4000:
            raise ValueError("full handoff scope exceeds BAT instructions limit")

        def before_send(prompt: str):
            if (original_archive and (original_archive["path"] not in prompt or
                                      original_archive["sha256"] not in prompt)):
                raise ValueError("full request archive reference lost in BAT handoff")
            if not original_archive and words not in prompt:
                raise ValueError("Ted's verbatim request lost in BAT handoff")
            if self.journal:
                self.journal.command_prompt_hash(handoff_command_id, hashlib.sha256(prompt.encode()).hexdigest())

        r = await lifecycle.session_failover(self.fleet, task["host"], session_id, confirm=True,
                                             successor_session_id=successor_id, instructions=instructions,
                                             ledger_only=bool(self.journal),
                                             handoff_message_id=handoff_message_id,
                                             before_handoff_send=before_send,
                                             authoritative_original=True)
        if not r.get("prompt_sent") and not r.get("skipped"):
            raise RuntimeError("failover handoff outcome is uncertain")
        return {"session_id": r["new_session_id"], "marker": r.get("message_id")}

    async def _verify_original_archive(self, task: dict, archive: dict):
        path = Path(archive["path"])
        alias = os.environ.get("BATC_TASK_ARCHIVE_VERIFY_SSH_HOST", "")
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+", alias) or
                stat.S_IMODE(path.stat().st_mode) != 0o600 or
                hashlib.sha256(path.read_bytes()).hexdigest() != archive["sha256"]):
            raise ValueError("complete request archive is not locally valid or host verifier is unset")
        command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", alias,
                   "sha256sum -- " + shlex.quote(str(path))]
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True,
                                         text=True, timeout=8, check=False)
        if result.returncode != 0 or result.stdout.split(maxsplit=1)[0:1] != [archive["sha256"]]:
            raise ValueError("BAT successor host cannot verify the complete request archive")

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
        try:
            meta = await self.fleet.client(task["host"]).invoke(
                "claude:get-session-meta", {"sessionId": successor_id}, retry_on_disconnect=False)
        except Exception:  # noqa: BLE001 - missing/unreachable BAT identity remains uncertain
            return None
        if not isinstance(meta, dict):
            return None
        # Session existence proves only the successor identity. Codex's handoff
        # message ID is not a turn receipt, even when the registry says "sent".
        return {"session_id": successor_id, "marker": entry.get("handoff_message_id")}

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
