"""Deterministic task coordinator; BAT and Discord are replaceable adapters."""

from __future__ import annotations

import asyncio
import re
from typing import Protocol

from .task_journal import Journal
from .task_recipes import limits


class TaskAdapter(Protocol):
    async def start(self, task: dict, *, role: str, agent: str) -> str: ...
    async def send(self, task: dict, session_id: str, text: str, message_id: str) -> dict: ...
    async def read(self, task: dict, session_id: str, marker: str | None) -> dict: ...
    async def interrupt(self, task: dict, session_id: str) -> None: ...
    async def failover(self, task: dict, session_id: str) -> str: ...
    async def verification(self, task: dict) -> dict | None: ...


def initial_prompt(task: dict) -> str:
    """Only Ted's original text may be relayed as a request; a lead plans in repo."""
    return (
        "You are the repository-aware lead coding session. Plan/decompose from the repo, then implement. "
        "Ted's exact request is the source of truth. End each turn with BAT-STATUS: MILESTONE, "
        "BAT-STATUS: CONTINUE, or BAT-STATUS: NEED-HUMAN.\n\n"
        "Ted's original words (verbatim):\n" + task["original_words"] +
        "\n\nAcceptance criteria:\n" + task["acceptance"]
    )


def reviewer_prompt(task: dict, candidate: str) -> str:
    return (
        "Independently review the candidate against Ted's original request and acceptance criteria. "
        "Do not edit. End with REVIEW: PASS or REVIEW: REJECT and reasons.\n\n"
        "Ted's original words (verbatim):\n" + task["original_words"] +
        "\n\nAcceptance criteria:\n" + task["acceptance"] + "\nCandidate commit: " + candidate
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
                 max_review_rejections: int = 2):
        self.journal = journal
        self.adapter = adapter
        self.max_continuations = max_continuations
        self.max_review_rejections = max_review_rejections
        self._writers: dict[tuple[str, str], asyncio.Lock] = {}

    def _lock(self, host: str, sid: str) -> asyncio.Lock:
        return self._writers.setdefault((host, sid), asyncio.Lock())

    async def pause(self, task_id: str, *, abort_current: bool = False) -> dict:
        task = self.journal.pause(task_id, abort_current=abort_current)
        if abort_current and task["session_id"]:
            async with self._lock(task["host"], task["session_id"]):
                await self.adapter.interrupt(task, task["session_id"])
        return self.journal.get(task_id)

    async def tick(self, task_id: str) -> dict:
        task = self.journal.get(task_id)
        if task["paused"] or task["state"] in {"done", "failed", "human_owned", "needs_ted"}:
            return task
        cmds = self.journal.commands(task_id)
        pending = next((c for c in reversed(cmds) if c["status"] in {"intent", "uncertain"}), None)
        if pending:
            # An intent may have reached BAT before a crash. Never dispatch it again.
            if pending["status"] == "intent":
                self.journal.command_status(pending["command_id"], "uncertain")
                return self.journal.change(task_id, "uncertain")
            if pending["kind"] != "send":
                return self.journal.change(task_id, "uncertain")
            return await self._reconcile(task, cmds)
        if task["state"] == "uncertain":
            return await self._reconcile(task, cmds)
        if task["state"] == "queued":
            return await self._start(task, role="lead", agent="codex")
        if task["state"] == "verifying":
            return await self._verify_and_review(task)
        if task["state"] == "quota_limited":
            return await self._failover(task)
        if task["state"] in {"accepted", "running", "dispatching", "waiting_permission"}:
            return await self._observe(task, cmds)
        return task

    async def _start(self, task: dict, *, role: str, agent: str) -> dict:
        key = f"{task['task_id']}:{role}:start:{task['review_rejections']}"
        command, fresh = self.journal.command(task["task_id"], "start_" + role, None, {}, key)
        if not fresh:
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.change(task["task_id"], "dispatching")
        try:
            sid = await self.adapter.start(task, role=role, agent=agent)
        except Exception:
            self.journal.command_status(command["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.command_status(command["command_id"], "settled")
        field = "reviewer_session_id" if role == "reviewer" else "session_id"
        self.journal.change(task["task_id"], "verifying" if role == "reviewer" else "accepted", fields={field: sid})
        prompt = reviewer_prompt(task, task["verification_commit"]) if role == "reviewer" else initial_prompt(task)
        return await self._send(self.journal.get(task["task_id"]), sid, prompt, role + ":initial")

    async def _send(self, task: dict, sid: str, text: str, purpose: str) -> dict:
        async with self._lock(task["host"], sid):
            task = self.journal.get(task["task_id"])
            if task["paused"]:
                return task
            key = f"{task['task_id']}:{purpose}:{task['review_rejections']}:{task['continuations']}"
            cmd, fresh = self.journal.command(task["task_id"], "send", sid, {"text": text}, key)
            if not fresh:
                return self.journal.change(task["task_id"], "uncertain")
            try:
                r = await self.adapter.send(task, sid, text, cmd["message_id"])
            except Exception:
                self.journal.command_status(cmd["command_id"], "uncertain")
                return self.journal.change(task["task_id"], "uncertain")
            if not r.get("accepted"):
                self.journal.command_status(cmd["command_id"], "rejected")
                return self.journal.change(task["task_id"], "needs_ted")
            marker = r.get("turn_marker") or cmd["message_id"]
            self.journal.command_status(cmd["command_id"], "accepted", marker=marker)
            state = "verifying" if sid == task.get("reviewer_session_id") else "running"
            return self.journal.change(task["task_id"], state, fields={"turn_marker": marker})

    async def _observe(self, task: dict, cmds: list[dict]) -> dict:
        sid = task["session_id"]
        if not sid:
            return self.journal.change(task["task_id"], "uncertain")
        read = await self.adapter.read(task, sid, task["turn_marker"])
        if read.get("turn_attribution") in {"unknown", "uncertain"}:
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

    async def _reconcile(self, task: dict, cmds: list[dict]) -> dict:
        latest = next((c for c in reversed(cmds) if c["kind"] == "send"), None)
        if not latest or not task["session_id"]:
            return task
        read = await self.adapter.read(task, latest["session_id"], latest["marker"] or latest["message_id"])
        if read.get("turn_started") is True and read.get("turn_attribution") == "exact_echo":
            self.journal.command_status(latest["command_id"], "accepted",
                                        marker=latest["marker"] or latest["message_id"])
            return self.journal.change(task["task_id"], "running", fields={"turn_marker": latest["marker"] or latest["message_id"]})
        return task  # unknown is not permission to resend

    async def _failover(self, task: dict) -> dict:
        cmd, fresh = self.journal.command(task["task_id"], "failover", task["session_id"], {},
                                          f"{task['task_id']}:failover:{task['session_id']}")
        if not fresh:
            return self.journal.change(task["task_id"], "uncertain")
        try:
            sid = await self.adapter.failover(task, task["session_id"])
        except Exception:
            self.journal.command_status(cmd["command_id"], "uncertain")
            return self.journal.change(task["task_id"], "uncertain")
        self.journal.command_status(cmd["command_id"], "settled")
        return self.journal.change(task["task_id"], "running", fields={"session_id": sid, "turn_marker": None})

    async def _verify_and_review(self, task: dict) -> dict:
        evidence = await self.adapter.verification(task)
        if not evidence or evidence.get("exit_code") != 0 or not evidence.get("current"):
            return task
        commit = evidence["candidate_commit"]
        if task["verification_commit"] != commit:
            task = self.journal.change(task["task_id"], "verifying", fields={"verification_commit": commit})
        if not task["reviewer_session_id"]:
            agent = "claude" if evidence.get("claude_quota_available") else "codex"
            return await self._start(task, role="reviewer", agent=agent)
        read = await self.adapter.read(task, task["reviewer_session_id"], task["turn_marker"])
        if read.get("turn_done") is not True:
            return task
        output = "\n".join(str(m.get("text") or "") for m in read.get("messages") or [] if m.get("role") != "user")
        if "REVIEW: PASS" in output:
            # Check commit again: review and tests must refer to the current candidate.
            fresh = await self.adapter.verification(task)
            if not fresh or not fresh.get("current") or fresh.get("candidate_commit") != commit:
                return self.journal.change(task["task_id"], "needs_ted")
            return self.journal.change(task["task_id"], "done", fields={"review_passed": 1,
                                       "result": output[-3000:]}, event="delivered")
        if "REVIEW: REJECT" in output:
            n = task["review_rejections"] + 1
            if n > min(self.max_review_rejections, limits(task["recipe"])[1]):
                return self.journal.change(task["task_id"], "needs_ted", fields={"review_rejections": n})
            self.journal.change(task["task_id"], "accepted", fields={"review_rejections": n,
                                      "reviewer_session_id": None, "verification_commit": None})
            return await self._send(self.journal.get(task["task_id"]), task["session_id"],
                                    "Independent review rejected the candidate. Address the review findings, rerun tests, "
                                    "and report a new milestone.\n" + output[-3000:], "review_rework")
        return task
