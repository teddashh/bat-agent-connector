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
from .errors import TaskDispatchCancelled, TaskIdentityMismatch, WriteRefused
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
        if await self.session_presence(task, task["session_id"]) != "present":
            raise ValueError("lead worktree identity is unproven for reviewer")
        lead = registry.get(host, task["session_id"])
        if not lead or not lead.get("cwd"):
            raise ValueError("lead worktree unavailable for reviewer")
        hc = self.fleet.config.host(host)
        sid = session_id
        preset = orchestrate.PRESETS[(agent, False)]
        entry = {"session_id": sid, "workspace_id": lead["workspace_id"],
                 "workspace_name": lead["workspace_name"], "agent_preset": preset,
                 "origin_cwd": lead["origin_cwd"], "cwd": lead["cwd"],
                 "worktree_path": lead.get("worktree_path"), "branch": lead.get("branch"),
                 "lead_session_id": task["session_id"], "task_id": task["task_id"],
                 "title": "review " + task["task_id"][:8], "role": "reviewer"}
        registry.reserve(host, entry, hc.orchestrate_max_sessions)
        opts = {"cwd": lead["cwd"], "agentPreset": preset,
                "workspaceId": lead["workspace_id"], "workspaceName": lead["workspace_name"]}
        if agent == "codex":
            opts.update(codexSandboxMode="read-only", codexApprovalPolicy="never")
        else:
            opts["permissionMode"] = "plan"
        try:
            started = await self.fleet.client(host).invoke(
                "claude:start-session", {"sessionId": sid, "options": opts}, retry_on_disconnect=False)
            if (not isinstance(started, dict) or started.get("ok") is False or
                    started.get("sessionId") != sid):
                raise WriteRefused("BAT reviewer start did not confirm the reserved session ID")
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
        meta = await self.fleet.client(task["host"]).invoke(
            "claude:get-session-meta", {"sessionId": session_id}, retry_on_disconnect=False,
        )
        if not isinstance(meta, dict):
            return False
        if not self.journal:
            return False
        intent = next((c for c in self.journal.commands(task["task_id"])
                       if c["kind"] == "start_" + role and c["session_id"] == session_id), None)
        if not intent:
            return False
        try:
            await self._restore_headless_lookup(task, session_id, meta, role=role,
                                                agent=json.loads(intent["payload"])["agent"])
        except Exception:  # noqa: BLE001 - recovery must fail closed on host/identity errors
            return False
        return True

    async def session_presence(self, task: dict, session_id: str) -> str:
        """Confirm BAT identity, restoring only journal-owned headless lookups.

        A missing workspace tab is expected when registration is off. BAT null
        metadata or worktree status can also mean an unloaded/restarting host;
        these replies never prove a session vanished.
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
                try:
                    await self._restore_headless_lookup(task, session_id, meta)
                except Exception:  # noqa: BLE001 - no verified lookup, so no prompt
                    return "uncertain"
                return "present"
            if attempt < 2:
                await asyncio.sleep(0.25)
        # Worktree status may also be null after a BAT restart while its disk
        # directory persists. Only a future host-side explicit absence proof
        # may return "vanished"; journal replacement remains fail closed today.
        return "uncertain"

    async def _restore_headless_lookup(self, task: dict, session_id: str, meta: dict,
                                       *, role: str | None = None, agent: str | None = None) -> None:
        branch = next((b for b in self.journal.branches(task["task_id"])
                       if b["session_id"] == session_id and b["role"] in {"lead", "reviewer"}), None)
        if (not (branch or role) or (branch and role and branch["role"] != role)
                or not meta.get("cwd")):
            raise ValueError("journal-owned BAT session has no verified folder")
        role = role or branch["role"]
        agent = agent or (branch["provider"] if branch else task["lead_agent"])
        if agent not in {"codex", "claude"}:
            raise ValueError("journal-owned BAT session has an invalid agent")
        client = self.fleet.client(task["host"])
        workspace_doc = await service._workspace(client)
        workspace = next((w for w in workspace_doc.get("workspaces") or []
                          if task["workspace"] in {w.get("id"), w.get("name")}), None)
        if not workspace:
            raise ValueError("task workspace no longer exists on BAT host")
        existing = registry.get(task["host"], session_id)
        if existing and (existing.get("task_id") not in {None, task["task_id"]}
                         or existing.get("role") not in {None, role}):
            raise ValueError("local session entry belongs to another task or role")
        try:
            worktree = await client.invoke(
                "worktree:status", {"sessionId": session_id}, retry_on_disconnect=False)
        except Exception as exc:  # noqa: BLE001 - no worktree proof on transport failure
            raise ValueError("BAT worktree identity is unavailable") from exc
        lead_id = task.get("session_id") if role == "reviewer" else None
        if role == "reviewer":
            if not lead_id or not any(b["session_id"] == lead_id and b["role"] == "lead"
                                      for b in self.journal.branches(task["task_id"])):
                raise ValueError("reviewer has no journal-owned lead")
            lead = registry.get(task["host"], lead_id)
            if not lead:
                lead_meta = await client.invoke("claude:get-session-meta", {"sessionId": lead_id},
                                                retry_on_disconnect=False)
                if not isinstance(lead_meta, dict):
                    raise ValueError("lead worktree identity is unavailable")
                await self._restore_headless_lookup(task, lead_id, lead_meta)
                lead = registry.get(task["host"], lead_id)
            if (not lead or lead.get("task_id") not in {None, task["task_id"]}
                    or lead.get("workspace_id") != workspace.get("id")
                    or lead.get("origin_cwd") != workspace.get("folderPath")
                    or not lead.get("worktree_path") or lead.get("cwd") != lead["worktree_path"]):
                raise ValueError("reviewer lead worktree identity does not match task")
            expected_cwd = lead["worktree_path"]
            lead_status = await client.invoke("worktree:status", {"sessionId": lead_id},
                                              retry_on_disconnect=False)
            if (not isinstance(lead_status, dict) or lead_status.get("worktreePath") != expected_cwd
                    or lead_status.get("branchName") != lead.get("branch")):
                raise ValueError("lead worktree changed before reviewer lookup")
            if isinstance(worktree, dict) and worktree.get("worktreePath") != expected_cwd:
                raise ValueError("reviewer worktree differs from lead")
            branch_name = lead.get("branch")
        else:
            if (not isinstance(worktree, dict) or not worktree.get("worktreePath")
                    or not worktree.get("branchName")):
                raise ValueError("lead worktree is not registered on BAT host")
            expected_cwd = worktree["worktreePath"]
            branch_name = worktree["branchName"]
        if (meta["cwd"] != expected_cwd or
                await client.invoke("git:getRoot", {"cwd": expected_cwd}, retry_on_disconnect=False)
                != expected_cwd):
            raise ValueError("BAT session folder does not match the journal-owned workspace")
        preset = orchestrate.PRESETS[(agent, role == "lead")]
        if existing and any(existing.get(key) not in {None, expected}
                            for key, expected in (
                                ("workspace_id", workspace.get("id")),
                                ("origin_cwd", workspace.get("folderPath")),
                                ("cwd", expected_cwd), ("worktree_path", expected_cwd),
                                ("branch", branch_name), ("agent_preset", preset))):
            raise ValueError("local session entry conflicts with BAT and task identity")
        registry.ensure_existing(task["host"], {
            "session_id": session_id, "workspace_id": workspace.get("id"),
            "workspace_name": workspace.get("name"), "agent_preset": preset,
            "origin_cwd": workspace.get("folderPath"), "cwd": expected_cwd,
            "worktree_path": expected_cwd, "branch": branch_name,
            "role": role, "task_id": task["task_id"], "lead_session_id": lead_id,
            "title": ("review " if role == "reviewer" else "task ") + task["task_id"][:8],
        })

    async def send(self, task: dict, session_id: str, text: str, message_id: str) -> dict:
        def before_invoke() -> None:
            if not self.journal:
                return
            current = self.journal.get(task["task_id"])
            command = self.journal.send_for_message(task["task_id"], session_id, message_id)
            if (current["paused"] or current["control_version"] != task["control_version"]
                    or session_id not in {current.get("session_id"), current.get("reviewer_session_id")}
                    or not command or command["status"] != "needs_review"
                    or json.loads(command["payload"]).get("prompt_sha256") != hashlib.sha256(text.encode()).hexdigest()):
                raise TaskDispatchCancelled("task send was cancelled before BAT invoke")

        return await service.session_send(self.fleet, task["host"], session_id, text, confirm=True,
                                          message_id=message_id, retry_on_disconnect=False,
                                          before_invoke=before_invoke)

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
                                             handoff_command_id=handoff_command_id,
                                             before_handoff_send=before_send,
                                             authoritative_original=True)
        if not r.get("prompt_sent") and not r.get("skipped"):
            raise RuntimeError("failover handoff outcome is uncertain")
        if r.get("new_session_id") != successor_id:
            raise TaskIdentityMismatch("BAT returned a different failover successor")
        identity = await self._verified_failover_successor(
            task, successor_id, handoff_message_id, handoff_command_id)
        if identity is False:
            raise TaskIdentityMismatch("reserved failover successor conflicts with BAT identity")
        if identity is None:
            raise RuntimeError("reserved failover successor and handoff identity are unproven")
        return {"session_id": successor_id, "marker": handoff_message_id}

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

    async def _verified_failover_successor(self, task: dict, successor_id: str,
                                           handoff_message_id: str, handoff_command_id: str) -> bool | None:
        """Require exact journal, registry and BAT host identity; null host data is unknown."""
        if not self.journal:
            return None
        try:
            handoff = self.journal.command_get(handoff_command_id)
            hp = json.loads(handoff["payload"])
            failover = next(c for c in self.journal.commands(task["task_id"])
                            if c["kind"] == "failover" and c["session_id"] == successor_id
                            and json.loads(c["payload"]).get("handoff_command_id") == handoff_command_id)
            fp = json.loads(failover["payload"])
            old = registry.get(task["host"], task["session_id"])
            entry = registry.get(task["host"], successor_id)
            if not old or not entry:
                return (False if any(e.get("failover_of") == task["session_id"] and
                                     e.get("status") in {"active", "starting", "uncertain"}
                                     for e in registry.list_entries(task["host"])) else None)
            path, branch = old["worktree_path"], old["branch"]
            if (handoff["task_id"] != task["task_id"] or handoff["kind"] != "send"
                    or handoff["session_id"] != successor_id or handoff["message_id"] != handoff_message_id
                    or hp.get("purpose") != "failover_handoff"
                    or hp.get("old_session_id") != task["session_id"]
                    or not re.fullmatch(r"[0-9a-f]{64}", str(hp.get("prompt_sha256") or ""))
                    or fp.get("old_session_id") != task["session_id"]
                    or not path or not branch
                    or entry.get("session_id") != successor_id
                    or entry.get("failover_of") != task["session_id"]
                    or entry.get("shares_worktree_with") != task["session_id"]
                    or entry.get("worktree_path") != path or entry.get("branch") != branch
                    or entry.get("handoff_message_id") != handoff_message_id
                    or entry.get("handoff_command_id") != handoff_command_id
                    or entry.get("handoff_status") not in {"sent", "uncertain"}):
                return False
            client = self.fleet.client(task["host"])
            meta = await client.invoke(
                "claude:get-session-meta", {"sessionId": successor_id}, retry_on_disconnect=False)
            old_status = await client.invoke(
                "worktree:status", {"sessionId": task["session_id"]}, retry_on_disconnect=False)
            new_status = await client.invoke(
                "worktree:status", {"sessionId": successor_id}, retry_on_disconnect=False)
            root = await client.invoke("git:getRoot", {"cwd": path}, retry_on_disconnect=False)
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
            return False
        except Exception:  # noqa: BLE001 - missing/unreachable BAT identity remains uncertain
            return None
        if (not isinstance(meta, dict) or not isinstance(old_status, dict)
                or not isinstance(new_status, dict) or root is None):
            return None
        return (meta.get("cwd") == path and root == path
                and all(st.get("worktreePath") == path and st.get("branchName") == branch
                        for st in (old_status, new_status)))

    async def recover_failover(self, task: dict, *, successor_id: str,
                               handoff_message_id: str, handoff_command_id: str) -> dict | None:
        identity = await self._verified_failover_successor(task, successor_id, handoff_message_id,
                                                           handoff_command_id)
        if identity is False:
            return {"identity_mismatch": True}
        if identity is None:
            return None
        # This proves a successor exists, not that Codex accepted its prompt.
        return {"session_id": successor_id, "marker": handoff_message_id}

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
