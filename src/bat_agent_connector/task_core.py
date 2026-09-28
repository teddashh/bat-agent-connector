"""Deterministic task coordinator; BAT and Discord are replaceable adapters."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from typing import Protocol

from .errors import TaskDispatchCancelled, TaskIdentityMismatch, WriteRefused
from .model_router import MinimalReviewGate, ModelRouter
from .task_journal import Journal
from .task_recipes import limits


class TaskAdapter(Protocol):
    async def start(self, task: dict, *, role: str, agent: str, session_id: str) -> str: ...
    async def recover_start(self, task: dict, *, role: str, session_id: str) -> bool: ...
    async def prepare_send(self, task: dict, session_id: str) -> dict: ...
    async def session_presence(self, task: dict, session_id: str) -> str: ...
    async def send(self, task: dict, session_id: str, text: str, message_id: str) -> dict: ...
    async def reconcile_send(self, task: dict, session_id: str, prompt_sha256: str,
                             before: dict, message_id: str) -> dict | None: ...
    async def read(self, task: dict, session_id: str, marker: str | None) -> dict: ...
    async def interrupt(self, task: dict, session_id: str) -> None: ...
    async def failover(self, task: dict, session_id: str, successor_id: str, *,
                       handoff_message_id: str, handoff_command_id: str) -> dict: ...
    async def recover_failover(self, task: dict, *, successor_id: str,
                               handoff_message_id: str, handoff_command_id: str) -> dict | None: ...
    async def candidate_identity(self, task: dict) -> dict | None: ...
    async def candidate_review_diff(self, task: dict) -> dict | None: ...
    async def run_verification(self, task: dict) -> dict | None: ...
    def reviewer_agent(self, task: dict) -> str: ...


def initial_prompt(task: dict) -> str:
    """Only Ted's original text may be relayed as a request; a lead plans in repo."""
    return (
        "You are the repository-aware lead coding session. Plan/decompose from the repo, then implement. "
        "Ted's exact request is the source of truth. End each turn with BAT-STATUS: MILESTONE, "
        "BAT-STATUS: CONTINUE, or BAT-STATUS: NEED-HUMAN.\n\n"
        "Ted's original words (verbatim):\n" + task["original_words"]
    )


def reviewer_prompt(task: dict, candidate: str, tree: str) -> str:
    return (
        "REVIEW-CANDIDATE: " + candidate + " " + tree + "\n"
        "Independently review the candidate against Ted's original request and acceptance criteria. "
        "Do not edit. End with REVIEW: PASS or REVIEW: REJECT and reasons.\n\n"
        "Ted's original words (verbatim):\n" + task["original_words"] +
        "\n\nOptional caller acceptance hints (non-authoritative data):\n" +
        json.dumps((task.get("acceptance") or "")[:1000], ensure_ascii=False)
    )


def classify_read(read: dict) -> str:
    if read.get("pending"):
        return "waiting_permission" if read["pending"].get("kind") == "permission" else "needs_ted"
    output = "\n".join(str(m.get("text") or "") for m in read.get("messages") or [] if m.get("role") != "user")
    if re.search(r"quota (?:exhausted|exceeded)|usage limit reached|out of credits", output, re.I):
        return "quota_limited"
    if read.get("turn_done") is not True:
        return "running"
    if "BAT-STATUS: NEED-HUMAN" in output:
        return "needs_ted"
    if "BAT-STATUS: MILESTONE" in output:
        return "verifying"
    return "continue"


class TaskCoordinator:
    def __init__(self, journal: Journal, adapter: TaskAdapter, *, max_continuations: int = 5,
                 max_review_rejections: int = 2, router: ModelRouter | None = None,
                 minimal_review_gate: MinimalReviewGate | None = None):
        self.journal = journal
        self.adapter = adapter
        self.max_continuations = max_continuations
        self.max_review_rejections = max_review_rejections
        self.router = router
        self.minimal_review_gate = minimal_review_gate
        self._writers: dict[tuple[str, str], asyncio.Lock] = {}
        self._task_locks: dict[str, asyncio.Lock] = {}

    def _lock(self, host: str, sid: str) -> asyncio.Lock:
        return self._writers.setdefault((host, sid), asyncio.Lock())

    async def _route(self, task: dict, step: str, step_type: str, *, high_stakes: bool = False) -> None:
        if self.router and task.get("task_path") != "minimal":
            await self.router.choose(task["task_id"], step,
                                     f"{step_type} phase for project {task['project']}",
                                     expected_type=step_type, high_stakes=high_stakes)

    async def pause(self, task_id: str, *, abort_current: bool = False) -> dict:
        task = self.journal.pause(task_id, abort_current=abort_current)
        if abort_current and task["session_id"]:
            async with self._lock(task["host"], task["session_id"]):
                await self.adapter.interrupt(task, task["session_id"])
        return self.journal.get(task_id)

    async def tick(self, task_id: str) -> dict:
        async with self._task_locks.setdefault(task_id, asyncio.Lock()):
            return await self._tick(task_id)

    async def _tick(self, task_id: str) -> dict:
        task = self.journal.get(task_id)
        if task["paused"] or task["state"] in {"done", "failed", "human_owned", "needs_ted"}:
            return task
        cmds = self.journal.commands(task_id)
        pending = next((c for c in cmds if c["kind"] == "failover" and
                        c["status"] in {"intent", "uncertain"}), None)
        if pending is None:
            pending = next((c for c in reversed(cmds)
                            if c["status"] in {"intent", "needs_review", "uncertain"}), None)
        if pending:
            # An intent may have reached BAT before a crash. Never dispatch it again.
            if pending["status"] in {"intent", "needs_review"}:
                self.journal.command_status(pending["command_id"], "uncertain")
                task = self.journal.change(task_id, "uncertain")
            return await self._reconcile_command(task, pending)
        if task["state"] == "uncertain":
            # A presence probe before any prompt may have been inconclusive
            # during BAT restart. No send intent exists, so checking again is
            # safe; a prompt is still created only after positive identity.
            sid = task.get("reviewer_session_id") or task.get("session_id")
            if sid and not any(c["kind"] == "send" and c["session_id"] == sid for c in cmds):
                if await self.adapter.session_presence(task, sid) == "present":
                    return self.journal.change(task_id, "verifying" if task.get("reviewer_session_id")
                                               else "accepted", event="session_presence_restored")
            return task
        if task["state"] == "queued":
            return await self._start(task, role="lead", agent=task["lead_agent"])
        if task["state"] == "verifying":
            return await self._verify_and_review(task)
        if task["state"] == "quota_limited":
            return await self._failover(task)
        if task["state"] == "accepted" and task["session_id"] and not any(
            c["kind"] == "send" and c["session_id"] == task["session_id"]
            and c["status"] != "cancelled" for c in cmds
        ):
            return await self._send(task, task["session_id"], initial_prompt(task), "lead:initial")
        if task["state"] in {"accepted", "running", "dispatching", "waiting_permission"}:
            return await self._observe(task, cmds)
        return task

    async def _start(self, task: dict, *, role: str, agent: str) -> dict:
        stage = "review" if role == "reviewer" else "planning"
        await self._route(task, f"{stage}:start:{task.get('review_commit') or 'lead'}:"
                          f"{task['control_version']}:{task['review_rejections']}:"
                          f"{task['session_replacements']}", stage, high_stakes=True)
        task = self.journal.get(task["task_id"])
        if task["paused"]:
            return task
        candidate_key = task.get("review_commit") if role == "reviewer" else "lead"
        key = (f"{task['task_id']}:{role}:start:{candidate_key}:{task['review_rejections']}:"
               f"{task['control_version']}:{task['session_replacements']}")
        warm_id = None
        if role == "lead" and task.get("task_path") == "minimal" and not task.get("base_branch"):
            finder = getattr(self.adapter, "find_warm", None)
            if callable(finder):
                try:
                    warm_id = await finder(task)
                except Exception:  # noqa: BLE001 - an unproven warm session is never adopted
                    warm_id = None
        sid = warm_id or str(uuid.uuid4())
        command, fresh = self.journal.command(task["task_id"], "start_" + role, sid,
                                               {"role": role, "agent": agent,
                                                "warm_session_id": warm_id}, key)
        if not fresh:
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.change(task["task_id"], "dispatching")
        if self.journal.get(task["task_id"])["paused"]:
            self.journal.command_status(command["command_id"], "cancelled")
            return self.journal.change(task["task_id"], "verifying" if role == "reviewer" else "queued")
        try:
            started_sid = await self.adapter.start({**task, "_warm_session_id": warm_id},
                                                   role=role, agent=agent, session_id=sid)
            if started_sid != sid:
                raise TaskIdentityMismatch("BAT start changed the reserved task session ID")
        except Exception:
            self.journal.command_status(command["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.command_status(command["command_id"], "settled")
        self.journal.add_branch(task["task_id"], session_id=sid, provider=agent, role=role,
                                reason=("warm_reuse" if warm_id else "vanished_replacement"
                                        if role == "lead" and task["session_replacements"] else "start"),
                                parent_branch_id=(task["branches"][-1]["branch_id"]
                                                                   if task["branches"] else None))
        field = "reviewer_session_id" if role == "reviewer" else "session_id"
        self.journal.change(task["task_id"], "verifying" if role == "reviewer" else "accepted", fields={field: sid})
        if self.journal.get(task["task_id"])["paused"]:
            return self.journal.get(task["task_id"])
        prompt = (reviewer_prompt(task, task["review_commit"], task["review_tree"])
                  if role == "reviewer" else initial_prompt(task))
        return await self._send(self.journal.get(task["task_id"]), sid, prompt, role + ":initial")

    async def _send(self, task: dict, sid: str, text: str, purpose: str,
                    *, prepared_command: dict | None = None) -> dict:
        async with self._lock(task["host"], sid):
            task = self.journal.get(task["task_id"])
            if task["paused"]:
                return task
            send_type = "review" if purpose.startswith("reviewer:") else "implementation"
            await self._route(task, f"{send_type}:send:{purpose}:{sid}:"
                              f"{task['control_version']}:{task['continuations']}:"
                              f"{task['review_rejections']}", send_type,
                              high_stakes=send_type == "review")
            task = self.journal.get(task["task_id"])
            if task["paused"]:
                return task
            initial_lead = purpose == "lead:initial" and prepared_command is None and sid == task["session_id"]
            initial_reviewer = (purpose == "reviewer:initial" and prepared_command is None
                                and sid == task.get("reviewer_session_id"))
            if initial_lead or initial_reviewer:
                presence = await self.adapter.session_presence(task, sid)
                task = self.journal.get(task["task_id"])
                if task["paused"]:
                    return task
                if initial_lead and presence == "vanished":
                    return self.journal.mark_initial_session_vanished(task["task_id"], sid)
                if presence != "present":
                    return self.journal.change(task["task_id"], "uncertain",
                                               event="initial_session_unproven")
            if prepared_command:
                cmd = self.journal.command_get(prepared_command["command_id"])
                payload = json.loads(cmd["payload"])
                if (cmd["status"] != "needs_review" or cmd["session_id"] != sid or
                        payload.get("prompt_sha256") != hashlib.sha256(text.encode()).hexdigest()):
                    raise ValueError("prepared operator prompt does not match journal intent")
                before = payload["before"]
            else:
                key = (f"{task['task_id']}:{purpose}:{task['review_rejections']}:{task['continuations']}:"
                       f"{task['control_version']}:"
                       f"{task.get('review_commit') if sid == task.get('reviewer_session_id') else sid}")
                before = await self.adapter.prepare_send(task, sid)
                if self.journal.get(task["task_id"])["paused"]:
                    return self.journal.get(task["task_id"])
                cmd, fresh = self.journal.command(task["task_id"], "send", sid,
                                                   {"purpose": purpose, "before": before,
                                                    "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()}, key)
                if not fresh:
                    return self.journal.change(task["task_id"], "uncertain")
            if initial_lead or initial_reviewer:
                presence = await self.adapter.session_presence(task, sid)
                task = self.journal.get(task["task_id"])
                if task["paused"]:
                    self.journal.command_status(cmd["command_id"], "cancelled")
                    return task
                if presence != "present":
                    self.journal.command_status(cmd["command_id"],
                                                "rejected" if presence == "vanished" else "uncertain")
                    if initial_lead and presence == "vanished":
                        return self.journal.mark_initial_session_vanished(task["task_id"], sid)
                    return self.journal.change(task["task_id"], "uncertain", event="initial_session_unproven")
            task = self.journal.get(task["task_id"])
            if task["paused"]:
                self.journal.command_status(cmd["command_id"], "cancelled")
                return task
            reconciled = False
            try:
                r = await self.adapter.send(task, sid, text, cmd["message_id"])
            except TaskDispatchCancelled:
                self.journal.command_status(cmd["command_id"], "cancelled")
                return self.journal.get(task["task_id"])
            except WriteRefused:
                # Local streaming/rate guard rejected before BAT send-message.
                current = self.journal.get(task["task_id"])
                if current["paused"] or current["control_version"] != task["control_version"]:
                    self.journal.command_status(cmd["command_id"], "cancelled")
                    return current
                self.journal.command_status(cmd["command_id"], "rejected")
                if initial_lead and await self.adapter.session_presence(task, sid) == "vanished":
                    return self.journal.mark_initial_session_vanished(task["task_id"], sid)
                return self.journal.change(task["task_id"], "needs_ted")
            except Exception:
                # The BAT frame may have been accepted before its reply was lost.
                # Read only; the durable send intent is never dispatched again.
                try:
                    r = await asyncio.wait_for(self.adapter.reconcile_send(
                        task, sid, hashlib.sha256(text.encode()).hexdigest(), before,
                        cmd["message_id"]), timeout=5)
                except Exception:  # noqa: BLE001 - missing proof stays uncertain
                    r = None
                if (not r or not r.get("accepted") or r.get("turn_attribution") != "exact_echo"
                        or not r.get("turn_marker")):
                    self.journal.command_status(cmd["command_id"], "uncertain")
                    return self.journal.change(task["task_id"], "uncertain")
                reconciled = True
            if not r.get("accepted"):
                self.journal.command_status(cmd["command_id"], "rejected")
                if initial_lead and await self.adapter.session_presence(task, sid) == "vanished":
                    return self.journal.mark_initial_session_vanished(task["task_id"], sid)
                return self.journal.change(task["task_id"], "needs_ted")
            if before.get("agent_kind") == "codex" and r.get("turn_attribution") != "exact_echo":
                # An accepted Codex ACK can still carry only a timestamp. Read
                # back the exact user echo before deciding it is unproven.
                try:
                    proof = await asyncio.wait_for(self.adapter.reconcile_send(
                        task, sid, hashlib.sha256(text.encode()).hexdigest(), before,
                        cmd["message_id"]), timeout=5)
                except Exception:  # noqa: BLE001 - absent proof stays uncertain
                    proof = None
                if (proof and proof.get("accepted") and proof.get("turn_attribution") == "exact_echo"
                        and proof.get("turn_marker")):
                    r = proof
                    reconciled = True
                else:
                    # A later timestamped assistant reply cannot own this turn.
                    marker = r.get("turn_marker") or before.get("before_cursor")
                    self.journal.command_status(cmd["command_id"], "uncertain", marker=marker)
                    return self.journal.change(task["task_id"], "uncertain")
            marker = r.get("turn_marker") or (before.get("before_cursor") if before.get("agent_kind") == "codex"
                                               else cmd["message_id"])
            if not marker:
                self.journal.command_status(cmd["command_id"], "uncertain")
                return self.journal.change(task["task_id"], "uncertain")
            self.journal.command_status(cmd["command_id"], "accepted", marker=marker)
            state = "verifying" if sid == task.get("reviewer_session_id") else "running"
            field = "review_marker" if state == "verifying" else "turn_marker"
            return self.journal.change(task["task_id"], state, fields={field: marker},
                                       event="send_reconciled_delivered" if reconciled else None)

    async def _observe(self, task: dict, cmds: list[dict]) -> dict:
        sid = task["session_id"]
        if not sid:
            return self.journal.change(task["task_id"], "uncertain")
        read = await self.adapter.read(task, sid, task["turn_marker"])
        if read.get("turn_done") or read.get("pending"):
            await self._route(task, f"status:{sid}:{task['turn_marker']}:"
                              f"{task['continuations']}:{task['state']}", "status_relay")
        if read.get("turn_attribution") in {"unknown", "uncertain", "echo_not_visible",
                                            "queued_unconfirmed", "timestamp_cursor"}:
            self._mark_unproven_send(task["task_id"], sid)
            return self.journal.change(task["task_id"], "uncertain")
        if read.get("turn_done") and (read.get("turn_started") is not True or
                                      read.get("turn_attribution") not in {
                                          "correlated", "correlated_after_prior_turn",
                                      }):
            self._mark_unproven_send(task["task_id"], sid)
            return self.journal.change(task["task_id"], "uncertain")
        decision = classify_read(read)
        if decision == "continue":
            if task["continuations"] >= min(self.max_continuations, limits(task["recipe"])[0]):
                return self.journal.change(task["task_id"], "needs_ted")
            self.journal.change(task["task_id"], "accepted", fields={"continuations": task["continuations"] + 1})
            return await self._send(self.journal.get(task["task_id"]), sid,
                                    "Continue toward Ted's acceptance criteria. Report a blocker or milestone.",
                                    "continue")
        if decision == "verifying":
            return self.journal.change(task["task_id"], "verifying")
        return self.journal.change(task["task_id"], decision)

    async def _reconcile_command(self, task: dict, cmd: dict) -> dict:
        kind, sid = cmd["kind"], cmd["session_id"]
        if kind.startswith("start_"):
            role = kind.removeprefix("start_")
            if await self.adapter.recover_start(task, role=role, session_id=sid):
                self.journal.command_status(cmd["command_id"], "settled")
                self.journal.add_branch(task["task_id"], session_id=sid,
                                        provider=json.loads(cmd["payload"])["agent"], role=role,
                                        reason="recovered_start")
                field = "reviewer_session_id" if role == "reviewer" else "session_id"
                return self.journal.change(task["task_id"], "verifying" if role == "reviewer" else "accepted",
                                           fields={field: sid})
            return self.journal.change(task["task_id"], "uncertain")
        if kind == "failover":
            if json.loads(cmd["payload"]).get("operator_only"):
                return self.journal.change(task["task_id"], "uncertain")
            handoff = self._bound_handoff(task, cmd)
            if not handoff:
                self.journal.command_operator_only(cmd["command_id"], "handoff_command_binding")
                return self.journal.change(task["task_id"], "uncertain")
            found = await self.adapter.recover_failover(
                task, successor_id=sid, handoff_message_id=handoff["message_id"],
                handoff_command_id=handoff["command_id"])
            if found and (found.get("identity_mismatch") or found.get("session_id") != sid
                          or found.get("marker") != handoff["message_id"]):
                self.journal.command_operator_only(cmd["command_id"], "successor_identity")
                return self.journal.change(task["task_id"], "uncertain")
            if found:
                self.journal.command_status(cmd["command_id"], "settled", marker=found.get("marker"))
                self.journal.command_status(handoff["command_id"], "uncertain", marker=found.get("marker"))
                self.journal.add_branch(task["task_id"], session_id=found["session_id"],
                                        provider="codex", role="lead", reason="recovered_failover",
                                        parent_branch_id=(task["branches"][-1]["branch_id"]
                                                          if task["branches"] else None))
                return self.journal.change(task["task_id"], "uncertain",
                                           fields={"session_id": found["session_id"],
                                                   "turn_marker": None, "lead_agent": "codex"})
            return self.journal.change(task["task_id"], "uncertain")
        if kind != "send":
            return self.journal.change(task["task_id"], "uncertain")
        before = json.loads(cmd["payload"]).get("before") or {}
        proof = None
        try:
            proof = await asyncio.wait_for(self.adapter.reconcile_send(
                task, sid, json.loads(cmd["payload"])["prompt_sha256"], before,
                cmd["message_id"]), timeout=5)
        except Exception:  # noqa: BLE001 - recovery must fail closed
            proof = None
        if proof and proof.get("accepted") and proof.get("turn_attribution") == "exact_echo":
            marker = proof.get("turn_marker")
            if marker:
                self.journal.command_status(cmd["command_id"], "accepted", marker=marker)
                reviewer = sid == task.get("reviewer_session_id")
                return self.journal.change(task["task_id"], "verifying" if reviewer else "running",
                                           fields={"review_marker" if reviewer else "turn_marker": marker},
                                           event="send_reconciled_delivered")
        marker = cmd["marker"] or (before.get("before_cursor") if before.get("agent_kind") == "codex"
                                   else cmd["message_id"])
        if not marker:
            return self.journal.change(task["task_id"], "uncertain")
        read = await self.adapter.read(task, sid, marker)
        attribution = read.get("turn_attribution")
        if read.get("turn_started") is True and attribution in {"correlated", "correlated_after_prior_turn"}:
            pass
        else:
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.command_status(cmd["command_id"], "accepted", marker=marker)
        reviewer = sid == task.get("reviewer_session_id")
        return self.journal.change(task["task_id"], "verifying" if reviewer else "running",
                                   fields={"review_marker" if reviewer else "turn_marker": marker})

    async def _failover(self, task: dict) -> dict:
        successor = str(uuid.uuid4())
        cmd, handoff = self.journal.reserve_failover(task["task_id"], task["session_id"], successor)
        if self.journal.get(task["task_id"])["paused"]:
            # No BAT call has started; both durable intents can be cancelled.
            self.journal.command_status(cmd["command_id"], "cancelled")
            self.journal.command_status(handoff["command_id"], "cancelled")
            return self.journal.get(task["task_id"])
        try:
            result = await self.adapter.failover(task, task["session_id"], successor,
                                                 handoff_message_id=handoff["message_id"],
                                                 handoff_command_id=handoff["command_id"])
        except TaskDispatchCancelled:
            self.journal.command_operator_only(cmd["command_id"], "paused_before_handoff_send")
            self.journal.command_status(handoff["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        except TaskIdentityMismatch:
            self.journal.command_operator_only(cmd["command_id"], "successor_identity")
            self.journal.command_status(handoff["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        except Exception:
            self.journal.command_status(cmd["command_id"], "uncertain")
            self.journal.command_status(handoff["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        if (not self._bound_handoff(task, cmd) or result.get("session_id") != successor
                or result.get("marker") != handoff["message_id"]):
            self.journal.command_operator_only(cmd["command_id"], "successor_or_handoff_response")
            self.journal.command_status(handoff["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.command_status(cmd["command_id"], "settled", marker=result.get("marker"))
        self.journal.command_status(handoff["command_id"], "uncertain", marker=result.get("marker"))
        self.journal.add_branch(task["task_id"], session_id=result["session_id"], provider="codex",
                                role="lead", reason="quota_failover",
                                parent_branch_id=(task["branches"][-1]["branch_id"]
                                                  if task["branches"] else None))
        return self.journal.change(task["task_id"], "uncertain",
                                   fields={"session_id": result["session_id"], "turn_marker": None,
                                           "lead_agent": "codex"})

    def _bound_handoff(self, task: dict, failover: dict) -> dict | None:
        """Only the journal's reserved successor and handoff command may advance failover."""
        try:
            payload = json.loads(failover["payload"])
            handoff = self.journal.command_get(payload["handoff_command_id"])
            hp = json.loads(handoff["payload"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if (failover["task_id"] != task["task_id"] or failover["kind"] != "failover"
                or payload.get("old_session_id") != task["session_id"]
                or handoff["task_id"] != task["task_id"] or handoff["kind"] != "send"
                or handoff["session_id"] != failover["session_id"]
                or handoff["status"] not in {"needs_review", "uncertain"}
                or hp.get("purpose") != "failover_handoff"
                or hp.get("old_session_id") != task["session_id"]
                or not handoff.get("message_id")):
            return None
        return handoff

    async def _verify_and_review(self, task: dict) -> dict:
        candidate = await self.adapter.candidate_identity(task)
        if not candidate or not candidate.get("clean"):
            return task
        commit, tree = candidate["candidate_commit"], candidate["tree_hash"]
        await self._route(task, f"verification:{commit}:{tree}", "verification", high_stakes=True)
        task = self.journal.get(task["task_id"])
        if task["paused"]:
            return task
        if self.router:
            fresh = await self.adapter.candidate_identity(task)
            if (not fresh or not fresh.get("clean")
                    or (fresh["candidate_commit"], fresh["tree_hash"]) != (commit, tree)):
                return task
        if (task["verification_commit"], task["verification_tree"]) != (commit, tree):
            task = self.journal.change(task["task_id"], "verifying", fields={
                "verification_commit": None, "verification_tree": None, "reviewer_session_id": None,
                "review_commit": None, "review_tree": None, "review_marker": None, "review_passed": 0,
            }, event="candidate_changed")
        evidence = self.journal.observed_verification(task["task_id"])
        if not evidence or (evidence["candidate_commit"], evidence["tree_hash"]) != (commit, tree):
            observed = await self.adapter.run_verification(task)
            if not observed:
                return task  # no configured trusted runner; no caller-supplied evidence accepted
            evidence = self.journal.record_observed_verification(task["task_id"], observed)
        if evidence["exit_code"] != 0:
            return self.journal.change(task["task_id"], "needs_ted", event="verification_failed")
        if not task["verification_commit"]:
            task = self.journal.change(task["task_id"], "verifying", fields={
                "verification_commit": commit, "verification_tree": tree,
            })
        small = task.get("task_path") == "minimal" and task["recipe"] == "small-task-with-tests"
        if small and not task["reviewer_session_id"]:
            lead_read = await self.adapter.read(task, task["session_id"], task["turn_marker"])
            if lead_read.get("streaming") is not False or lead_read.get("pending"):
                return task
            existing = self.journal.minimal_review_gate(task["task_id"], commit, tree)
            if existing and existing["verdict"] == "pending":
                existing = self.journal.finish_minimal_review(task["task_id"], commit, tree, {
                    "verdict": "escalate", "confidence": None, "jev_backend": None,
                    "reason": "pending_after_restart"})
            if not existing:
                reader = getattr(self.adapter, "candidate_review_diff", None)
                try:
                    candidate_diff = await reader(task) if callable(reader) else None
                except Exception:  # noqa: BLE001 - unavailable diff requires full review
                    candidate_diff = None
                diff = candidate_diff.get("diff", "") if isinstance(candidate_diff, dict) else ""
                paths = candidate_diff.get("paths", []) if isinstance(candidate_diff, dict) else []
                if not isinstance(diff, str) or not isinstance(paths, list):
                    diff, paths = "", []
                digest = hashlib.sha256(diff.encode()).hexdigest()
                threshold = (self.minimal_review_gate.config.minimal_review_confidence_threshold
                             if self.minimal_review_gate else 1.0)
                try:
                    self.journal.reserve_minimal_review(task["task_id"], commit, tree, digest, threshold)
                except ValueError:
                    return self.journal.change(task["task_id"], "needs_ted", event="review_diff_changed")
                decision = (await self.minimal_review_gate.judge(
                    original_words=task["original_words"], diff=diff, paths=paths)
                    if self.minimal_review_gate else
                    {"verdict": "escalate", "confidence": None, "jev_backend": None,
                     "reason": "jev_unavailable_or_invalid"})
                existing = self.journal.finish_minimal_review(task["task_id"], commit, tree, decision)
            task = self.journal.get(task["task_id"])
            fresh = await self.adapter.candidate_identity(task)
            if task["paused"] or not fresh or not fresh.get("clean") or (
                    fresh["candidate_commit"], fresh["tree_hash"]) != (commit, tree):
                return task
            if existing["verdict"] == "pass":
                return self.journal.change(task["task_id"], "done", fields={
                    "result": "Trusted tests and Jev review gate passed on the clean candidate",
                }, event="delivered_jev_review_gate")
        if not task["reviewer_session_id"]:
            lead_read = await self.adapter.read(task, task["session_id"], task["turn_marker"])
            if lead_read.get("streaming") is not False or lead_read.get("pending"):
                return task
            if (self.router and task.get("task_path") != "minimal"
                    and not self.journal.jev_prescreen_for_candidate(task["task_id"], commit, tree)):
                diff_reader = getattr(self.adapter, "candidate_diff_excerpt", None)
                try:
                    diff = await diff_reader(task) if callable(diff_reader) else None
                except Exception:  # noqa: BLE001 - advisory pre-screen cannot block review
                    diff = None
                if diff:
                    final = "\n".join(str(m.get("text") or "") for m in lead_read.get("messages") or []
                                      if m.get("role") == "assistant")[-3000:]
                    await self.router.prescreen(task["task_id"], commit=commit, tree=tree,
                                                request=task["original_words"], final_output=final,
                                                diff_excerpt=diff,
                                                tests=f"{evidence['command']} exit={evidence['exit_code']}")
                task = self.journal.get(task["task_id"])
                fresh = await self.adapter.candidate_identity(task)
                if (task["paused"] or not fresh or not fresh.get("clean")
                        or (fresh["candidate_commit"], fresh["tree_hash"]) != (commit, tree)):
                    return task
            task = self.journal.change(task["task_id"], "verifying", fields={
                "review_commit": commit, "review_tree": tree, "review_marker": None,
            })
            agent = self.adapter.reviewer_agent(task)
            return await self._start(task, role="reviewer", agent=agent)
        if not task["review_marker"]:
            return await self._send(task, task["reviewer_session_id"],
                                    reviewer_prompt(task, commit, tree), "reviewer:initial")
        read = await self.adapter.read(task, task["reviewer_session_id"], task["review_marker"])
        attributed = read.get("first_turn_proven") is True and read.get("turn_attribution") in {
            "correlated", "correlated_after_prior_turn",
        }
        if read.get("turn_attribution") == "timestamp_cursor" and read.get("turn_started"):
            self._mark_unproven_send(task["task_id"], task["reviewer_session_id"])
            return self.journal.change(task["task_id"], "uncertain")
        if not (read.get("turn_started") is True and read.get("turn_done") is True and attributed):
            return task
        output = "\n".join(str(m.get("text") or "") for m in read.get("messages") or [] if m.get("role") != "user")
        if "REVIEW: PASS" in output:
            lead_read = await self.adapter.read(task, task["session_id"], task["turn_marker"])
            if lead_read.get("streaming") is not False or lead_read.get("pending"):
                return task
            fresh = await self.adapter.candidate_identity(task)
            if not fresh or not fresh.get("clean") or (fresh["candidate_commit"], fresh["tree_hash"]) != (commit, tree):
                return self.journal.change(task["task_id"], "verifying", fields={
                    "reviewer_session_id": None, "review_marker": None,
                    "review_commit": None, "review_tree": None, "review_passed": 0,
                }, event="candidate_changed_during_review")
            return self.journal.change(task["task_id"], "done", fields={"review_passed": 1,
                                       "result": output[-3000:]}, event="delivered")
        if "REVIEW: REJECT" in output:
            n = task["review_rejections"] + 1
            if n > min(self.max_review_rejections, limits(task["recipe"])[1]):
                return self.journal.change(task["task_id"], "needs_ted", fields={"review_rejections": n})
            self.journal.change(task["task_id"], "accepted", fields={"review_rejections": n,
                                      "reviewer_session_id": None, "review_marker": None,
                                      "review_commit": None, "review_tree": None,
                                      "verification_commit": None, "verification_tree": None})
            return await self._send(self.journal.get(task["task_id"]), task["session_id"],
                                    "Independent review rejected the candidate. Address the review findings, rerun tests, "
                                    "and report a new milestone.\n" + output[-3000:], "review_rework")
        return task

    def _mark_unproven_send(self, task_id: str, session_id: str):
        for cmd in reversed(self.journal.commands(task_id)):
            if cmd["kind"] == "send" and cmd["session_id"] == session_id and cmd["status"] == "accepted":
                self.journal.command_status(cmd["command_id"], "uncertain")
                break

    async def resolve_command(self, task_id: str, command_id: str, *, token: str, outcome: str,
                              actor: str, source: str, evidence: str,
                              observed_result: str = "none", turn_ref: str | None = None,
                              candidate_commit: str | None = None, tree_hash: str | None = None,
                              next_prompt: str | None = None) -> dict:
        """An explicit operator attestation for one uncertain command, never a replay."""
        async with self._task_locks.setdefault(task_id, asyncio.Lock()):
            task = self.journal.get(task_id)
            command = self.journal.command_get(command_id)
            if command["task_id"] != task_id or command["status"] != "uncertain":
                raise ValueError("command is not uncertain for this task")
            if command["kind"] == "failover":
                if next_prompt is not None or observed_result != "none" or turn_ref:
                    raise ValueError("failover reconciliation cannot send or attest a turn")
                handoff = self._bound_handoff(task, command)
                if not handoff:
                    raise ValueError("failover handoff command binding is invalid")
                return self.journal.resolve_failover(task_id, command_id, handoff["command_id"],
                                                     token=token, outcome=outcome, actor=actor,
                                                     source=source, evidence=evidence)
            if next_prompt is not None:
                if not isinstance(next_prompt, str) or not next_prompt.strip() or len(next_prompt) > 18_000:
                    raise ValueError("invalid new prompt")
                read = await self.adapter.read(task, command["session_id"], command["marker"])
                if read.get("streaming") is not False or read.get("pending"):
                    raise ValueError("BAT session must be confirmed idle before new prompt")
                next_before = await self.adapter.prepare_send(task, command["session_id"])
            else:
                next_before = None
            if observed_result == "review_pass":
                lead_read = await self.adapter.read(task, task["session_id"], task["turn_marker"])
                if lead_read.get("streaming") is not False or lead_read.get("pending"):
                    raise ValueError("lead session must be settled before review resolution")
                identity = await self.adapter.candidate_identity(task)
                if (not identity or not identity.get("clean") or
                        (identity["candidate_commit"], identity["tree_hash"]) !=
                        (candidate_commit, tree_hash)):
                    raise ValueError("candidate changed before operator review resolution")
                read = await self.adapter.read(task, command["session_id"], command["marker"])
                if read.get("streaming") is not False:
                    raise ValueError("reviewer turn is still active")
            result = self.journal.resolve_send(
                task_id, command_id, token=token, outcome=outcome, actor=actor,
                source=source, evidence=evidence, observed_result=observed_result,
                turn_ref=turn_ref, candidate_commit=candidate_commit, tree_hash=tree_hash,
                next_prompt_sha256=hashlib.sha256(next_prompt.encode()).hexdigest()
                if next_prompt is not None else None, next_before=next_before,
            )
            if next_prompt is not None:
                return await self._send(result, command["session_id"], next_prompt,
                                        "operator:" + command_id,
                                        prepared_command={"command_id": result["_next_command_id"]})
            return result
