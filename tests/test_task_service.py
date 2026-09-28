from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from bat_agent_connector import goose_acp, lifecycle, mcp_server, orchestrate, registry, service, task_bat
from bat_agent_connector.errors import WriteRefused
from bat_agent_connector.goose_acp import PINNED_GOOSE_VERSION, GooseACP, GooseConfig
from bat_agent_connector.model_router import ModelRouter, RouterConfig
from bat_agent_connector.pm_providers import (
    AgyShimAdapter,
    ProviderCatalog,
    ProviderEntry,
    ProviderSetupError,
    ProviderSwitcher,
    UncertainPrompt,
    classify_provider_error,
)
from bat_agent_connector.task_core import TaskCoordinator
from bat_agent_connector.task_daemon import TaskDaemon
from bat_agent_connector.task_discord import DiscordPublisher
from bat_agent_connector.task_handoff import history_excerpt, ledger_summary
from bat_agent_connector.task_journal import Journal
from bat_agent_connector.task_verifier import ObservedVerifier, VerificationSettings
from tests.conftest import make_config

WORDS = "請保留 `原文`，不要改成英文。\n第二行：修好它。"


async def test_goose_executable_version_is_pinned(tmp_path):
    binary = tmp_path / "goose"
    binary.write_text("#!/bin/sh\necho 'goose 1.52.0'\n")
    binary.chmod(0o700)
    goose = GooseACP(GooseConfig(command=(str(binary), "acp")))
    assert await goose.check_pinned_version() == PINNED_GOOSE_VERSION
    binary.write_text("#!/bin/sh\necho 'goose 1.53.0'\n")
    with pytest.raises(RuntimeError, match="pinned ACP contract version"):
        await goose.check_pinned_version()


def submit(journal, **kw):
    return journal.submit(project="p", host="h1", workspace="w", original_words=WORDS,
                          acceptance="tests pass", idempotency_key="discord:message:1", **kw)


class FakeBAT:
    def __init__(self):
        self.starts = []
        self.sends = []
        self.reads = {}
        self.identity = {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "clean": True}
        self.diff_excerpt = None
        self.verifier_available = True
        self.reviewer_kind = "codex"
        self.started_ids = set()
        self.vanished_ids = set()
        self.presence_override = None
        self.successors = {}
        self.failover_allowed = False
        self.start_error = False
        self.start_gate = None
        self.prepare_kind = "claude"
        self.failover_calls = 0
        self.interrupts = 0
        self.send_error = False
        self.reconcile_echo = None
        self.active_sends = 0
        self.max_active_sends = 0

    async def start(self, task, *, role, agent, session_id):
        self.starts.append((role, agent, session_id))
        self.started_ids.add(session_id)
        if self.start_gate is not None:
            await self.start_gate.wait()
        if self.start_error:
            raise TimeoutError("start response lost")
        return session_id

    async def recover_start(self, task, *, role, session_id):
        return session_id in self.started_ids

    async def prepare_send(self, task, session_id):
        return {"agent_kind": self.prepare_kind,
                "before_cursor": "2026-09-27T00:00:00+00:00" if self.prepare_kind == "codex" else None}

    async def session_presence(self, task, session_id):
        if self.presence_override:
            return self.presence_override
        return "vanished" if session_id in self.vanished_ids else "present"

    async def send(self, task, session_id, text, message_id):
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        await asyncio.sleep(0)
        self.active_sends -= 1
        self.sends.append((session_id, text, message_id))
        if self.send_error:
            raise TimeoutError("lost response after possible acceptance")
        return {"accepted": True, "turn_marker": message_id if self.prepare_kind == "claude"
                else "2026-09-27T00:00:00+00:00",
                "turn_attribution": "exact_echo" if self.prepare_kind == "claude" else "timestamp_cursor"}

    async def read(self, task, session_id, marker):
        read = self.reads.get(session_id, {"turn_started": False, "turn_done": False}).copy()
        read.setdefault("streaming", False)
        if read.get("turn_started") and "turn_attribution" not in read:
            read["turn_attribution"] = "correlated"
        return read

    async def reconcile_send(self, task, session_id, prompt_sha256, before, message_id):
        echo = self.reconcile_echo
        if (echo and echo["session_id"] == session_id and echo["message_id"] == message_id
                and hashlib.sha256(echo["text"].encode()).hexdigest() == prompt_sha256):
            return {"accepted": True, "turn_marker": echo["turn_id"],
                    "turn_attribution": "exact_echo"}
        return None

    async def interrupt(self, task, session_id):
        self.interrupts += 1

    async def failover(self, task, session_id, successor_id, *, handoff_message_id, handoff_command_id):
        self.failover_calls += 1
        if not self.failover_allowed:
            raise ValueError("Codex cannot Claude-to-Codex fail over")
        self.sends.append((successor_id, "handoff for task " + task["task_id"], handoff_message_id))
        self.successors[session_id] = {"session_id": successor_id, "marker": handoff_message_id}
        return self.successors[session_id]

    async def recover_failover(self, task, *, successor_id, handoff_message_id, handoff_command_id):
        return self.successors.get(task["session_id"])

    async def candidate_identity(self, task):
        return self.identity

    async def candidate_diff_excerpt(self, task):
        return self.diff_excerpt

    async def run_verification(self, task):
        if not self.verifier_available:
            return None
        return {"source": "observed_runner", **{k: self.identity[k] for k in ("candidate_commit", "tree_hash")},
                "command": "pytest -q", "exit_code": 0, "log_ref": "journal:fake", "output_sha256": "c" * 64}

    def reviewer_agent(self, task):
        return self.reviewer_kind


def test_journal_idempotency_restart_and_metrics(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    assert task["original_words"] == WORDS
    assert submit(j)["task_id"] == task["task_id"]
    with pytest.raises(ValueError, match="different task"):
        j.submit(project="p", host="h1", workspace="w", original_words="rewritten",
                 idempotency_key="discord:message:1")
    assert j.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert j.db.execute("PRAGMA synchronous").fetchone()[0] == 2
    j.close()
    j = Journal(path)
    assert j.get(task["task_id"])["original_words"] == WORDS
    assert j.get(task["task_id"])["delivered"] is False
    assert j.get(task["task_id"])["time_to_deliver_s"] is None
    with pytest.raises(ValueError, match="invalid transition"):
        j.change(task["task_id"], "done")
    j.request_ted(task["task_id"], "need choice")
    assert j.get(task["task_id"])["ted_interventions"] == 0
    j.ted_action(task["task_id"], action="pause", source_message_id="discord:ted:1")
    j.ted_action(task["task_id"], action="pause", source_message_id="discord:ted:1")
    assert j.get(task["task_id"])["ted_interventions"] == 1
    j.close()


async def test_timeout_no_resend_and_reconcile(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    fake = FakeBAT()
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["state"] == "uncertain"
    assert len(fake.sends) == 1
    sid = j.get(task["task_id"])["session_id"]
    j.close()
    j = Journal(path)
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    assert len(fake.sends) == 1
    fake.reads[sid] = {"turn_started": True, "turn_done": False,
                       "turn_attribution": "correlated"}
    assert (await core.tick(task["task_id"]))["state"] == "running"
    assert len(fake.sends) == 1
    j.close()


async def test_send_timeout_after_acceptance_read_back_exact_prompt(tmp_path):
    class AcceptedThenLost(FakeBAT):
        async def send(self, task, session_id, text, message_id):
            self.reconcile_echo = {"session_id": session_id, "message_id": message_id,
                                   "text": text, "turn_id": "user-confirmed-1"}
            await super().send(task, session_id, text, message_id)

    path = tmp_path / "tasks.db"
    journal = Journal(path)
    task = submit(journal)
    fake = AcceptedThenLost()
    fake.prepare_kind = "codex"
    fake.send_error = True
    core = TaskCoordinator(journal, fake)
    result = await core.tick(task["task_id"])
    assert result["state"] == "running" and result["turn_marker"] == "user-confirmed-1"
    assert len(fake.sends) == 1
    send = next(c for c in journal.commands(task["task_id"]) if c["kind"] == "send")
    assert send["status"] == "accepted" and send["marker"] == "user-confirmed-1"
    assert "send_reconciled_delivered" in [e["kind"] for e in journal.events(task["task_id"])]
    journal.close()
    journal = Journal(path)
    await TaskCoordinator(journal, fake).tick(task["task_id"])
    assert len(fake.sends) == 1
    journal.close()


async def test_codex_accepted_timestamp_requires_exact_read_back(tmp_path):
    class AcceptedTimestampBAT(FakeBAT):
        async def send(self, task, session_id, text, message_id):
            self.reconcile_echo = {"session_id": session_id, "message_id": message_id,
                                   "text": text, "turn_id": "user-codex-exact"}
            return await super().send(task, session_id, text, message_id)

    journal = Journal(tmp_path / "accepted.db")
    task = submit(journal)
    fake = AcceptedTimestampBAT()
    fake.prepare_kind = "codex"
    result = await TaskCoordinator(journal, fake).tick(task["task_id"])
    assert result["state"] == "running" and result["turn_marker"] == "user-codex-exact"
    send = next(c for c in journal.commands(task["task_id"]) if c["kind"] == "send")
    assert send["status"] == "accepted" and send["marker"] == "user-codex-exact"
    assert len(fake.sends) == 1
    assert "send_reconciled_delivered" in [e["kind"] for e in journal.events(task["task_id"])]
    journal.close()

    journal = Journal(tmp_path / "unproven.db")
    task = submit(journal)
    fake = FakeBAT()
    fake.prepare_kind = "codex"
    core = TaskCoordinator(journal, fake)
    result = await core.tick(task["task_id"])
    assert result["state"] == "uncertain" and not result["delivered"]
    fake.reads[result["session_id"]] = {"turn_started": True, "turn_done": True,
                                         "turn_attribution": "timestamp_cursor",
                                         "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.sends) == 1
    journal.close()


async def test_bat_read_back_requires_exact_new_user_echo(fleet_factory, mock):
    fleet = fleet_factory()
    adapter = task_bat.BatTaskAdapter(fleet)
    sid = "sess-codex-0002"
    mock.states[sid]["isStreaming"] = False
    prompt = "Ted's exact original request\nBAT-STATUS: MILESTONE"
    before = await adapter.prepare_send({"host": "h1"}, sid)
    mock.states[sid]["messages"].append({"id": "assistant-unrelated", "role": "assistant",
                                          "content": "REVIEW: PASS", "timestamp": 1_900_000_000_000})
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    assert await adapter.reconcile_send({"host": "h1"}, sid, digest, before, "batc-lost") is None
    mock.states[sid]["messages"].append({"id": "user-exact", "role": "user",
                                          "content": prompt, "timestamp": 1_900_000_000_001})
    proof = await adapter.reconcile_send({"host": "h1"}, sid, digest, before, "batc-lost")
    assert proof["turn_marker"] == "user-exact"
    read = await service.session_read(fleet, "h1", sid, after=proof["turn_marker"])
    assert read["turn_attribution"] == "correlated"
    assert await adapter.reconcile_send({"host": "h1"}, sid, "0" * 64, before, "batc-lost") is None
    later_before = await adapter.prepare_send({"host": "h1"}, sid)
    mock.states[sid]["messages"].append({"id": "assistant-later", "role": "assistant",
                                          "content": "REVIEW: PASS", "timestamp": 1_900_000_000_002})
    assert await adapter.reconcile_send({"host": "h1"}, sid, digest, later_before, "batc-later") is None
    await fleet.close()


async def test_verification_deadline_and_failure_do_not_stall_worker(tmp_path, mock):
    daemon = TaskDaemon(make_config(mock), db_path=tmp_path / "tasks.db")
    daemon.verification_timeout_s = 1
    hung = daemon.journal.submit(project="p", host="h1", workspace="w", original_words="hung",
                                 idempotency_key="hung")
    failed = daemon.journal.submit(project="p", host="h1", workspace="w", original_words="failed",
                                   idempotency_key="failed")
    healthy = daemon.journal.submit(project="p", host="h1", workspace="w", original_words="healthy",
                                    idempotency_key="healthy")
    for item in (hung, failed, healthy):
        daemon.journal.change(item["task_id"], "dispatching")
        daemon.journal.change(item["task_id"], "verifying")
    calls = []

    async def tick(task_id):
        calls.append(task_id)
        if task_id == hung["task_id"]:
            await asyncio.Event().wait()
        if task_id == failed["task_id"]:
            raise RuntimeError("private verifier detail must stay out of journal")

    daemon.coordinator.tick = tick
    for item in (hung, failed, healthy):
        daemon.journal.db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?",
                                  (time.time(), item["task_id"]))
        await daemon._tick_task(item["task_id"])
    assert all(item["task_id"] in calls for item in (hung, failed, healthy))
    assert daemon.journal.get(hung["task_id"])["state"] == "needs_ted"
    assert daemon.journal.get(failed["task_id"])["state"] == "needs_ted"
    assert daemon.journal.get(healthy["task_id"])["state"] == "verifying"
    assert "verification_timeout" in [e["kind"] for e in daemon.journal.events(hung["task_id"])]
    assert "verification_error" in [e["kind"] for e in daemon.journal.events(failed["task_id"])]
    assert "private verifier detail" not in json.dumps(daemon.journal.events(failed["task_id"]))
    daemon.journal.db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?",
                              (time.time() - 2, healthy["task_id"]))
    before = len(calls)
    await daemon._tick_task(healthy["task_id"])
    assert len(calls) == before
    assert daemon.journal.get(healthy["task_id"])["state"] == "needs_ted"
    assert "verification_deadline" in [e["kind"] for e in daemon.journal.events(healthy["task_id"])]
    await daemon.fleet.close()
    daemon.journal.close()


async def test_codex_timestamp_never_proves_lost_send_or_review(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    fake.prepare_kind = "codex"
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    sid = j.get(task["task_id"])["session_id"]
    fake.reads[sid] = {"turn_started": True, "turn_done": True,
                       "turn_attribution": "timestamp_cursor",
                       "messages": [{"role": "assistant", "text": "REVIEW: PASS\nBAT-STATUS: MILESTONE"}]}
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert not j.get(task["task_id"])["delivered"] and len(fake.sends) == 1
    j.close()

    j = Journal(tmp_path / "review.db")
    task = submit(j)
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    lead = j.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    fake.prepare_kind = "codex"
    await core.tick(task["task_id"])
    reviewer = j.get(task["task_id"])["reviewer_session_id"]
    assert j.get(task["task_id"])["state"] == "uncertain"
    fake.reads[reviewer] = {"turn_started": True, "turn_done": True, "streaming": False,
                            "turn_attribution": "timestamp_cursor", "first_turn_proven": True,
                            "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert not j.get(task["task_id"])["delivered"]
    assert len([x for x in fake.sends if x[0] == reviewer]) == 1
    j.close()


async def test_operator_reconcile_is_command_scoped_and_dispatches_new_prompt(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    fake = FakeBAT()
    fake.send_error = True
    daemon.adapter = fake
    daemon.coordinator = TaskCoordinator(daemon.journal, fake)
    task = submit(daemon.journal)
    await daemon.coordinator.tick(task["task_id"])
    command = next(c for c in daemon.journal.commands(task["task_id"]) if c["kind"] == "send")
    assert command["status"] == "uncertain"
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async def rpc(token, method, params):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        body = json.dumps({"method": method, "params": params}).encode()
        writer.write(b"POST /rpc HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " +
                     token.encode() + b"\r\nContent-Length: " + str(len(body)).encode() +
                     b"\r\n\r\n" + body)
        await writer.drain()
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
        return raw.split(b"\r\n\r\n", 1)[0], json.loads(raw.split(b"\r\n\r\n", 1)[1])

    params = {"task_id": task["task_id"], "command_id": command["command_id"],
              "outcome": "not_delivered", "actor": "operator", "source": "ticket:123",
              "evidence": "inspected BAT turn list and found no matching user prompt",
              "next_prompt": "Inspect the repo and report current state for this task."}
    try:
        status, result = await rpc(daemon._admin_token, "work_reconcile", params)
        assert b"400 Bad Request" in status and result["error"] == "ValueError"
        status, result = await rpc(daemon._admin_token, "work_reconcile_capability",
                                   {"task_id": task["task_id"], "command_id": command["command_id"]})
        assert b"200 OK" in status
        cap = result["result"]["capability"]
        status, result = await rpc(cap, "work_reconcile", {**params, "task_id": "other-task"})
        assert b"400 Bad Request" in status
        fake.send_error = False
        status, result = await rpc(cap, "work_reconcile", params)
        assert b"200 OK" in status and result["result"]["state"] == "running"
        assert len(fake.sends) == 2 and fake.sends[1][1] == params["next_prompt"]
        assert fake.sends[0][1] != fake.sends[1][1]
        assert daemon.journal.command_get(command["command_id"])["status"] == "resolved_not_delivered"
        rec = daemon.journal.reconciliations(task["task_id"])[0]
        assert (rec["actor"], rec["source"], rec["outcome"]) == ("operator", "ticket:123", "not_delivered")
        status, _ = await rpc(cap, "work_reconcile", params)
        assert b"400 Bad Request" in status
        assert len(fake.sends) == 2
    finally:
        server.close()
        await server.wait_closed()
        await daemon.fleet.close()
        daemon.journal.close()


async def test_operator_followup_intent_survives_crash_without_automatic_send(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    fake = FakeBAT()
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    old = next(c for c in j.commands(task["task_id"]) if c["kind"] == "send")
    cap = j.issue_reconcile_capability(task["task_id"], old["command_id"])
    followup = "New explicit operator instruction"
    result = j.resolve_send(task["task_id"], old["command_id"], token=cap, outcome="superseded",
                            actor="operator", source="ticket:456", evidence="previous turn superseded",
                            next_prompt_sha256=hashlib.sha256(followup.encode()).hexdigest(),
                            next_before={"agent_kind": "claude"})
    new_command = j.command_get(result["_next_command_id"])
    assert new_command["status"] == "needs_review"
    j.close()
    j = Journal(path)
    assert (await TaskCoordinator(j, fake).tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.sends) == 1
    assert j.command_get(new_command["command_id"])["status"] == "uncertain"
    j.close()


async def test_task_bat_adapter_contract_with_mock_host(fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=True,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="adapter-contract")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    lead = "task-lead-contract"
    start_command, _ = j.command(task["task_id"], "start_lead", lead,
                                 {"role": "lead", "agent": "codex"}, "adapter-contract-start")
    assert await adapter.start(task, role="lead", agent="codex", session_id=lead) == lead
    start = next(i for i in mock.invokes if i["channel"] == "claude:start-session"
                 and i["params"]["sessionId"] == lead)
    assert start["params"]["options"]["agentPreset"] == "codex-agent-worktree"
    assert not any(t.get("id") == lead for t in mock.ws_doc["terminals"])
    assert await adapter.recover_start(task, role="lead", session_id=lead)
    j.command_status(start_command["command_id"], "settled")
    j.add_branch(task["task_id"], session_id=lead, provider="codex", role="lead", reason="start")
    j.change(task["task_id"], "dispatching")
    task = j.change(task["task_id"], "accepted", fields={"session_id": lead})
    before = await adapter.prepare_send(task, lead)
    assert before["agent_kind"] == "codex" and before["before_cursor"]
    prompt = "synthetic contract prompt"
    command, _ = j.command(task["task_id"], "send", lead,
                           {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}, "contract-send")
    send = await adapter.send(task, lead, prompt, command["message_id"])
    assert send["accepted"]
    reviewer = "task-review-contract"
    assert await adapter.start(task, role="reviewer", agent="codex", session_id=reviewer) == reviewer
    review_start = next(i for i in mock.invokes if i["channel"] == "claude:start-session"
                        and i["params"]["sessionId"] == reviewer)
    opts = review_start["params"]["options"]
    assert opts["codexSandboxMode"] == "read-only" and opts["codexApprovalPolicy"] == "never"
    assert opts["cwd"] == start["params"]["options"]["cwd"]
    assert not any(t.get("id") == reviewer for t in mock.ws_doc["terminals"])
    j.close()


async def test_task_initial_send_after_start_ignores_only_start_spacing(fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True,
                          safety={"write_min_interval_s": 60, "max_writes_per_hour": 100})
    journal = Journal(tmp_path / "initial-spacing.db")
    task = journal.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                          idempotency_key="initial-spacing")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), journal)
    session_id = "task-initial-spacing"
    assert await adapter.start(task, role="lead", agent="claude", session_id=session_id) == session_id
    task = journal.change(task["task_id"], "dispatching")
    task = journal.change(task["task_id"], "accepted", fields={"session_id": session_id})
    prompt = "first lead prompt"
    command, _ = journal.command(task["task_id"], "send", session_id,
                                 {"purpose": "lead:initial",
                                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()},
                                 "initial-spacing:send")
    sent = await adapter.send(task, session_id, prompt, command["message_id"])
    assert sent["accepted"]
    assert len([i for i in mock.invokes if i["channel"] == "claude:send-message"
                and i["params"]["sessionId"] == session_id]) == 1
    with pytest.raises(WriteRefused, match="rate limit"):
        await service.session_send(fleet, "h1", session_id, "later prompt", confirm=True)
    journal.close()
    await fleet.close()


async def test_task_reservation_excludes_paused_lead_from_legacy_cleanup(
        fleet_factory, mock, tmp_path, monkeypatch):
    fleet = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True,
                          safety={"write_min_interval_s": 0})
    journal = Journal(tmp_path / "tasks.db")
    task = journal.submit(project="p", host="h1", workspace="demo-project",
                          original_words=WORDS, idempotency_key="paused-reserved-lead")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), journal)
    core = TaskCoordinator(journal, adapter)
    original_start = adapter.start
    started = {}
    original_reserve = registry.reserve
    reserved = []

    def tagged_reservation(host, entry, max_active, replaces=None):
        result = original_reserve(host, entry, max_active, replaces=replaces)
        reserved.append(registry.get(host, entry["session_id"]))
        return result

    async def pause_after_start(*args, **kwargs):
        sid = await original_start(*args, **kwargs)
        started["sid"] = sid
        assert registry.get("h1", sid)["task_id"] == task["task_id"]
        journal.pause(task["task_id"])
        return sid

    monkeypatch.setattr(registry, "reserve", tagged_reservation)
    monkeypatch.setattr(adapter, "start", pause_after_start)
    result = await core.tick(task["task_id"])
    sid = started["sid"]
    assert result["paused"] and result["state"] == "accepted"
    assert reserved and reserved[0]["task_id"] == task["task_id"]
    assert not any(i["channel"] == "claude:send-message" and
                   i["params"].get("sessionId") == sid for i in mock.invokes)
    decision = await lifecycle.session_cleanup(fleet, "h1", session_id=sid,
                                               confirm=True, dry_run=False, min_idle_s=0)
    assert decision["decisions"][0]["decision"] == "KEEP"
    main = await lifecycle.main_session(fleet, "h1", "demo-project")
    assert not main or main["session_id"] != sid
    assert registry.get("h1", sid)["task_id"] == task["task_id"]
    journal.close()
    await fleet.close()


async def test_headless_session_lookup_restored_from_task_branch_and_bat_meta(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="headless-lookup")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "headless-started-session"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        j.add_branch(task["task_id"], session_id=sid, provider="claude", role="lead", reason="start")
        j.change(task["task_id"], "dispatching")
        task = j.change(task["task_id"], "accepted", fields={"session_id": sid})
        assert not any(t.get("id") == sid for t in mock.ws_doc["terminals"])
        task_bat.registry.registry_path().unlink()
        assert task_bat.registry.get("h1", sid) is None
        assert await adapter.session_presence(task, sid) == "present"
        assert task_bat.registry.get("h1", sid)["recovered_from"] == "task_journal"
        assert (await adapter.prepare_send(task, sid))["agent_kind"] == "claude"
        prompt = "first prompt"
        command, _ = j.command(task["task_id"], "send", sid,
                               {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}, "headless-send")
        assert (await adapter.send(task, sid, prompt, command["message_id"]))["accepted"]
        assert len([i for i in mock.invokes if i["channel"] == "claude:send-message"
                    and i["params"]["sessionId"] == sid]) == 1
    finally:
        await fleet.close()
        j.close()


async def test_bat_presence_distinguishes_orphan_worktree_from_vanished_session(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="presence-contract")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "presence-session"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        j.add_branch(task["task_id"], session_id=sid, provider="claude", role="lead", reason="start")
        mock.metas[sid] = None
        assert await adapter.session_presence(task, sid) == "uncertain"
        assert task_bat.registry.get("h1", sid)["status"] == "active"
        mock.worktrees.pop(sid)
        assert await adapter.session_presence(task, sid) == "uncertain"
        assert task_bat.registry.get("h1", sid)["status"] == "active"
    finally:
        await fleet.close()
        j.close()


async def test_bat_restart_null_meta_and_worktree_never_creates_replacement(
        fleet_factory, mock, tmp_path):
    path = tmp_path / "tasks.db"
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(path)
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="restart-null-presence")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "restart-unloaded-session"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        j.add_branch(task["task_id"], session_id=sid, provider="claude", role="lead", reason="start")
        j.change(task["task_id"], "dispatching")
        j.change(task["task_id"], "accepted", fields={"session_id": sid})
        disk_worktree = mock.worktrees.pop(sid)
        loaded_meta = mock.metas[sid]
        mock.metas[sid] = None  # BAT restart unloads runtime; disk worktree remains.
        assert (await TaskCoordinator(j, adapter).tick(task["task_id"]))["state"] == "uncertain"
        assert j.get(task["task_id"])["session_replacements"] == 0
        assert not any(c["kind"] == "send" for c in j.commands(task["task_id"]))
        j.close()
        j = Journal(path)
        adapter.journal = j
        core = TaskCoordinator(j, adapter)
        assert (await core.tick(task["task_id"]))["state"] == "uncertain"
        assert len(j.get(task["task_id"])["branches"]) == 1
        mock.worktrees[sid] = disk_worktree
        mock.metas[sid] = loaded_meta
        assert (await core.tick(task["task_id"]))["state"] == "accepted"
        assert (await core.tick(task["task_id"]))["state"] == "running"
        assert j.get(task["task_id"])["session_replacements"] == 0
        assert len([i for i in mock.invokes if i["channel"] == "claude:send-message"
                    and i["params"]["sessionId"] == sid]) == 1
    finally:
        await fleet.close()
        j.close()


async def test_lead_meta_present_but_bat_worktree_null_blocks_initial_send(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="null-worktree-loaded-meta")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "loaded-meta-null-worktree"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        j.add_branch(task["task_id"], session_id=sid, provider="claude", role="lead", reason="start")
        j.change(task["task_id"], "dispatching")
        task = j.change(task["task_id"], "accepted", fields={"session_id": sid})
        saved = task_bat.registry.get("h1", sid)
        assert saved["worktree_path"] and saved["branch"] and mock.metas[sid]
        assert mock.dispatch("git:getRoot", {"cwd": saved["worktree_path"]}) == saved["worktree_path"]
        mock.worktrees.pop(sid)
        assert await adapter.session_presence(task, sid) == "uncertain"
        assert (await TaskCoordinator(j, adapter).tick(task["task_id"]))["state"] == "uncertain"
        assert j.get(task["task_id"])["session_replacements"] == 0
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()
        j.close()


async def test_headless_reviewer_restores_from_lead_worktree_when_own_status_null(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="reviewer-lookup")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    lead_sid, reviewer_sid = "review-lead", "review-headless"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=lead_sid)
        j.add_branch(task["task_id"], session_id=lead_sid, provider="claude", role="lead", reason="start")
        j.change(task["task_id"], "dispatching")
        task = j.change(task["task_id"], "accepted", fields={"session_id": lead_sid})
        lead_path = task_bat.registry.get("h1", lead_sid)["worktree_path"]
        j.command(task["task_id"], "start_reviewer", reviewer_sid,
                  {"role": "reviewer", "agent": "codex"}, "reviewer-recovery-intent")
        assert await adapter.start(task, role="reviewer", agent="codex", session_id=reviewer_sid) == reviewer_sid
        path = task_bat.registry.registry_path()
        task_bat.registry._write(path, [e for e in task_bat.registry.list_entries()
                                        if e.get("session_id") != reviewer_sid])
        assert task_bat.registry.get("h1", reviewer_sid) is None
        assert await adapter.recover_start(task, role="reviewer", session_id=reviewer_sid)
        task_bat.registry._write(path, [e for e in task_bat.registry.list_entries()
                                        if e.get("session_id") != reviewer_sid])
        j.add_branch(task["task_id"], session_id=reviewer_sid, provider="codex", role="reviewer",
                     reason="start")
        assert await adapter.session_presence(task, reviewer_sid) == "present"
        reviewer = task_bat.registry.get("h1", reviewer_sid)
        assert reviewer["cwd"] == reviewer["worktree_path"] == lead_path
        assert reviewer["lead_session_id"] == lead_sid and reviewer["role"] == "reviewer"
        assert reviewer["agent_preset"] == "codex-agent"
        start = next(c for c in j.commands(task["task_id"]) if c["kind"] == "start_reviewer")
        j.command_status(start["command_id"], "settled")
        task = j.change(task["task_id"], "verifying", fields={"reviewer_session_id": reviewer_sid})
        prompt = "review candidate"
        command, _ = j.command(task["task_id"], "send", reviewer_sid,
                               {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}, "reviewer-send")
        assert (await adapter.send(task, reviewer_sid, prompt, command["message_id"]))["accepted"]
    finally:
        await fleet.close()
        j.close()


async def test_existing_registry_row_requires_matching_bat_metadata_and_worktree(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="stale-row")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "stale-registry-row"
    try:
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        j.add_branch(task["task_id"], session_id=sid, provider="claude", role="lead", reason="start")
        good_cwd = mock.metas[sid]["cwd"]
        mock.metas[sid]["cwd"] = "/srv/other"
        assert await adapter.session_presence(task, sid) == "uncertain"
        mock.metas[sid]["cwd"] = good_cwd
        task_bat.registry.update("h1", sid, cwd="/srv/other")
        assert await adapter.session_presence(task, sid) == "uncertain"
        task_bat.registry.update("h1", sid, cwd=good_cwd, worktree_path="/srv/other")
        assert await adapter.session_presence(task, sid) == "uncertain"
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()
        j.close()


async def test_start_ack_recovery_uses_reserved_id_when_local_registry_lost(
        fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="recover-start-lookup")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    sid = "reserved-start-session"
    try:
        j.command(task["task_id"], "start_lead", sid, {"role": "lead", "agent": "claude"},
                  "start-intent-test")
        await adapter.start(task, role="lead", agent="claude", session_id=sid)
        task_bat.registry.registry_path().unlink()
        assert await adapter.recover_start(task, role="lead", session_id=sid)
        assert task_bat.registry.get("h1", sid)["recovered_from"] == "task_journal"
        assert not any(t.get("id") == sid for t in mock.ws_doc["terminals"])
    finally:
        await fleet.close()
        j.close()


@pytest.mark.parametrize("reply", [
    {"ok": True, "sessionId": "different-session"}, {"ok": True},
])
async def test_bat_start_rejects_missing_or_mismatched_session_id(fleet_factory, mock, reply):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    mock.handlers["claude:start-session"] = lambda p: reply
    try:
        with pytest.raises(WriteRefused, match="reserved session ID"):
            await task_bat.orchestrate.session_start(
                fleet, "h1", "demo-project", "claude", confirm=True, prompt=None,
                session_id="reserved-session", retain_on_error=True)
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()


@pytest.mark.parametrize("reply", [
    {"ok": True, "sessionId": "different-reviewer"}, {"ok": True},
])
async def test_reviewer_start_rejects_missing_or_mismatched_session_id(
        fleet_factory, mock, tmp_path, reply):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="review-ack")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    try:
        await adapter.start(task, role="lead", agent="claude", session_id="review-ack-lead")
        j.add_branch(task["task_id"], session_id="review-ack-lead", provider="claude",
                     role="lead", reason="start")
        task = {**task, "session_id": "review-ack-lead"}
        mock.handlers["claude:start-session"] = lambda p: reply
        with pytest.raises(WriteRefused, match="reviewer start"):
            await adapter.start(task, role="reviewer", agent="codex", session_id="review-ack-reviewer")
        assert task_bat.registry.get("h1", "review-ack-reviewer")["status"] == "uncertain"
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()
        j.close()


async def test_vanished_initial_session_one_replacement_and_restart(tmp_path):
    class VanishesOnStart(FakeBAT):
        async def start(self, task, *, role, agent, session_id):
            sid = await super().start(task, role=role, agent=agent, session_id=session_id)
            self.vanished_ids.add(sid)
            return sid

    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    fake = VanishesOnStart()
    core = TaskCoordinator(j, fake)
    result = await core.tick(task["task_id"])
    assert result["state"] == "queued" and result["session_replacements"] == 1
    assert result["task_id"] == task["task_id"] and result["original_words"] == WORDS
    assert fake.sends == []
    first = result["branches"][0]["session_id"]
    j.close()
    j = Journal(path)
    core = TaskCoordinator(j, fake)
    result = await core.tick(task["task_id"])
    assert result["state"] == "needs_ted" and result["session_replacements"] == 1
    assert [b["session_id"] for b in result["branches"]] == [first, fake.starts[1][2]]
    assert result["branches"][1]["reason"] == "vanished_replacement"
    assert fake.sends == [] and len(fake.starts) == 2
    await core.tick(task["task_id"])
    assert len(fake.starts) == 2
    j.close()


async def test_vanished_after_uncertain_initial_send_never_replaced(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    fake = FakeBAT()
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    fake.vanished_ids.add(j.get(task["task_id"])["session_id"])
    j.close()
    j = Journal(path)
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["state"] == "uncertain"
    assert j.get(task["task_id"])["session_replacements"] == 0
    assert len(fake.sends) == 1 and len(fake.starts) == 1
    j.close()


async def test_start_then_rejected_send_with_vanished_session_replaces_once(tmp_path):
    class RejectedAfterStart(FakeBAT):
        async def send(self, task, session_id, text, message_id):
            self.vanished_ids.add(session_id)
            self.sends.append((session_id, text, message_id))
            return {"accepted": False, "reason": "session absent"}

    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j)
    fake = RejectedAfterStart()
    core = TaskCoordinator(j, fake)
    result = await core.tick(task["task_id"])
    assert result["state"] == "queued" and result["session_replacements"] == 1
    assert j.commands(task["task_id"])[-1]["status"] == "rejected"
    assert len(fake.sends) == 1
    j.close()
    j = Journal(path)
    result = await TaskCoordinator(j, fake).tick(task["task_id"])
    assert result["state"] == "needs_ted" and result["session_replacements"] == 1
    assert len(fake.sends) == 2 and fake.sends[0][0] != fake.sends[1][0]
    assert fake.sends[0][1] == fake.sends[1][1]  # one fresh command for the new branch
    assert fake.sends[0][2] != fake.sends[1][2]
    j.close()


async def test_pause_during_final_presence_check_cancels_unsent_command(tmp_path):
    class PresenceGateBAT(FakeBAT):
        def __init__(self):
            super().__init__()
            self.probes = 0
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def session_presence(self, task, session_id):
            self.probes += 1
            if self.probes == 2:
                self.entered.set()
                await self.release.wait()
            return "present"

    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = PresenceGateBAT()
    core = TaskCoordinator(j, fake)
    tick = asyncio.create_task(core.tick(task["task_id"]))
    await asyncio.wait_for(fake.entered.wait(), 2)
    paused = await core.pause(task["task_id"])
    assert paused["paused"]
    fake.release.set()
    result = await asyncio.wait_for(tick, 2)
    assert result["paused"] and fake.sends == []
    sends = [c for c in j.commands(task["task_id"]) if c["kind"] == "send"]
    assert len(sends) == 1 and sends[0]["status"] == "cancelled"
    j.resume(task["task_id"])
    assert (await core.tick(task["task_id"]))["state"] == "running"
    assert len(fake.sends) == 1 and fake.sends[0][2] != sends[0]["message_id"]
    j.close()


async def test_pause_during_late_session_send_lookup_blocks_bat_frame(
        fleet_factory, mock, tmp_path, monkeypatch):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    mock.echo_sends = True
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="late-send-pause")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    core = TaskCoordinator(j, adapter)
    entered, release = asyncio.Event(), asyncio.Event()
    original = service._live_state
    gated = False

    async def late_lookup(*args):
        nonlocal gated
        if (not gated and any(c["kind"] == "send" and c["status"] == "needs_review"
                              for c in j.commands(task["task_id"]))):
            gated = True
            entered.set()
            await release.wait()
        return await original(*args)

    monkeypatch.setattr(service, "_live_state", late_lookup)
    try:
        tick = asyncio.create_task(core.tick(task["task_id"]))
        await asyncio.wait_for(entered.wait(), 5)
        assert j.pause(task["task_id"])["paused"]
        release.set()
        assert (await asyncio.wait_for(tick, 5))["paused"]
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
        sends = [c for c in j.commands(task["task_id"]) if c["kind"] == "send"]
        assert len(sends) == 1 and sends[0]["status"] == "cancelled"
        j.resume(task["task_id"])
        await core.tick(task["task_id"])
        sent = [i for i in mock.invokes if i["channel"] == "claude:send-message"]
        assert len(sent) == 1 and sent[0]["params"]["clientMessageId"] != sends[0]["message_id"]
    finally:
        release.set()
        await fleet.close()
        j.close()


async def test_settled_reviewer_start_requires_presence_before_prompt(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    lead = j.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    fake.presence_override = "uncertain"
    result = await core.tick(task["task_id"])
    reviewer = result["reviewer_session_id"]
    assert reviewer and result["state"] == "uncertain"
    assert not any(sid == reviewer for sid, _, _ in fake.sends)
    assert any(c["kind"] == "start_reviewer" and c["status"] == "settled"
               for c in j.commands(task["task_id"]))
    fake.presence_override = None
    assert (await core.tick(task["task_id"]))["state"] == "verifying"
    assert (await core.tick(task["task_id"]))["state"] == "verifying"
    assert len([sid for sid, _, _ in fake.sends if sid == reviewer]) == 1
    j.close()


async def test_bat_adapter_recovers_codex_successor_without_handoff_turn_proof(
        fleet_factory, mock, monkeypatch, tmp_path):
    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal, lead_agent="claude")
    journal.change(task["task_id"], "dispatching")
    journal.change(task["task_id"], "accepted", fields={"session_id": "old-contract"})
    journal.change(task["task_id"], "running")
    task = journal.change(task["task_id"], "quota_limited")
    _, handoff = journal.reserve_failover(task["task_id"], "old-contract", "successor-contract")
    frame_hash = hashlib.sha256(b"contract handoff").hexdigest()
    journal.command_prompt_hash(handoff["command_id"], frame_hash)
    fleet = fleet_factory(writes=True, orchestrate=True)
    path, branch = "/srv/demo/.bat-worktrees/contract", "bat/worktree-contract"
    mock.metas["successor-contract"] = {"cwd": path, "isStreaming": False}
    mock.worktrees["old-contract"] = {"worktreePath": path, "branchName": branch}
    mock.worktrees["successor-contract"] = {"worktreePath": path, "branchName": branch}
    old = {"session_id": "old-contract", "worktree_path": path, "branch": branch}
    successor = {"session_id": "successor-contract", "failover_of": "old-contract",
                 "shares_worktree_with": "old-contract", "status": "active",
                 "task_id": task["task_id"],
                 "worktree_path": path, "branch": branch,
                 "handoff_status": "sent", "handoff_message_id": handoff["message_id"],
                 "handoff_command_id": handoff["command_id"], "handoff_frame_sha256": frame_hash}
    monkeypatch.setattr(task_bat.registry, "get", lambda host, sid: {
        "old-contract": old, "successor-contract": successor}.get(sid))
    adapter = task_bat.BatTaskAdapter(fleet, journal=journal)
    try:
        found = await adapter.recover_failover(task, successor_id="successor-contract",
                                              handoff_message_id=handoff["message_id"],
                                              handoff_command_id=handoff["command_id"])
        assert found == {"session_id": "successor-contract", "marker": handoff["message_id"]}
        successor["handoff_frame_sha256"] = hashlib.sha256(b"different frame").hexdigest()
        assert (await adapter.recover_failover(task, successor_id="successor-contract",
                handoff_message_id=handoff["message_id"], handoff_command_id=handoff["command_id"])) == {
                    "identity_mismatch": True}
        successor["handoff_frame_sha256"] = frame_hash
        mock.worktrees["successor-contract"]["branchName"] = "bat/other"
        assert (await adapter.recover_failover(task, successor_id="successor-contract",
                handoff_message_id=handoff["message_id"], handoff_command_id=handoff["command_id"])) == {
                    "identity_mismatch": True}
        mock.worktrees["successor-contract"]["branchName"] = branch
        successor["handoff_command_id"] = "old-handoff"
        assert (await adapter.recover_failover(task, successor_id="successor-contract",
                handoff_message_id=handoff["message_id"], handoff_command_id=handoff["command_id"])) == {
                    "identity_mismatch": True}
        successor["handoff_command_id"] = handoff["command_id"]
        mock.worktrees["successor-contract"] = None
        assert await adapter.recover_failover(task, successor_id="successor-contract",
                handoff_message_id=handoff["message_id"], handoff_command_id=handoff["command_id"]) is None
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()
        journal.close()


async def test_operator_review_pass_requires_current_candidate_and_turn_reference(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    lead = j.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    fake.prepare_kind = "codex"
    await core.tick(task["task_id"])
    reviewer = j.get(task["task_id"])["reviewer_session_id"]
    command = next(c for c in reversed(j.commands(task["task_id"])) if c["kind"] == "send")
    assert command["session_id"] == reviewer and command["status"] == "uncertain"
    cap = j.issue_reconcile_capability(task["task_id"], command["command_id"])
    identity = fake.identity
    with pytest.raises(ValueError, match="turn reference"):
        await core.resolve_command(task["task_id"], command["command_id"], token=cap,
                                   outcome="delivered", actor="operator", source="ticket:review",
                                   evidence="inspected reviewer turn", observed_result="review_pass",
                                   candidate_commit=identity["candidate_commit"], tree_hash=identity["tree_hash"])
    with pytest.raises(ValueError, match="candidate changed"):
        await core.resolve_command(task["task_id"], command["command_id"], token=cap,
                                   outcome="delivered", actor="operator", source="ticket:review",
                                   evidence="inspected reviewer turn", observed_result="review_pass",
                                   turn_ref="bat-message:77", candidate_commit="d" * 40,
                                   tree_hash=identity["tree_hash"])
    done = await core.resolve_command(task["task_id"], command["command_id"], token=cap,
                                      outcome="delivered", actor="operator", source="ticket:review",
                                      evidence="BAT reviewer message 77 explicitly passed candidate",
                                      observed_result="review_pass", turn_ref="bat-message:77",
                                      candidate_commit=identity["candidate_commit"],
                                      tree_hash=identity["tree_hash"])
    assert done["state"] == "done" and done["delivered"]
    assert j.reconciliations(task["task_id"])[0]["turn_ref"] == "bat-message:77"
    j.close()


async def test_rules_review_verification_failover_pause_and_writer(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, interpretation="Hermes guessed the wrong feature")
    fake = FakeBAT()
    fake.verifier_available = False
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    lead = j.get(task["task_id"])["session_id"]
    assert fake.sends[0][1].count(WORDS) == 1
    assert "Hermes guessed the wrong feature" not in fake.sends[0][1]
    assert "tests pass" not in fake.sends[0][1]
    assert j.get(task["task_id"])["interpretation"] == "Hermes guessed the wrong feature"
    fake.reads[lead] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "working"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["continuations"] == 1
    await core.pause(task["task_id"], abort_current=True)
    assert fake.interrupts == 1
    before = len(fake.sends)
    await core.tick(task["task_id"])
    assert len(fake.sends) == before
    j.resume(task["task_id"])
    fake.reads[lead] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["state"] == "verifying"
    await core.tick(task["task_id"])
    assert not any(role == "reviewer" for role, _, _ in fake.starts)
    fake.verifier_available = True
    await core.tick(task["task_id"])
    assert any(role == "reviewer" and agent == "codex" for role, agent, _ in fake.starts)
    reviewer = j.get(task["task_id"])["reviewer_session_id"]
    fake.reads[reviewer] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                            "first_turn_proven": True,
                            "messages": [{"role": "assistant", "text": "REVIEW: REJECT needs tests"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["review_rejections"] == 1
    fake.reads[lead] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    fake.identity = {"candidate_commit": "d" * 40, "tree_hash": "e" * 40, "clean": True}
    fake.reviewer_kind = "claude"
    await core.tick(task["task_id"])
    assert any(role == "reviewer" and agent == "claude" for role, agent, _ in fake.starts)
    reviewer2 = j.get(task["task_id"])["reviewer_session_id"]
    assert reviewer2 != reviewer
    fake.reads[reviewer2] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                             "first_turn_proven": True,
                             "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    done = await core.tick(task["task_id"])
    assert done["state"] == "done" and done["delivered"]
    assert done["time_to_deliver_s"] is not None
    j.close()


async def test_failover_and_single_writer(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, lead_agent="claude")
    fake = FakeBAT()
    fake.failover_allowed = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    j.change(task["task_id"], "quota_limited")
    successor_task = await core.tick(task["task_id"])
    successor = successor_task["session_id"]
    assert successor != task["session_id"]
    assert successor_task["state"] == "uncertain"
    assert fake.failover_calls == 1
    handoff = next(c for c in j.commands(task["task_id"]) if c["kind"] == "send"
                   and json.loads(c["payload"]).get("purpose") == "failover_handoff")
    cap = j.issue_reconcile_capability(task["task_id"], handoff["command_id"])
    await core.resolve_command(task["task_id"], handoff["command_id"], token=cap,
                               outcome="superseded", actor="operator", source="test:handoff",
                               evidence="synthetic handoff turn inspected", next_prompt="Inspect task state")
    # Two sends to the same BAT session serialize in the daemon.
    current = j.get(task["task_id"])
    await asyncio.gather(core._send(current, successor, "a", "a"),
                         core._send(current, successor, "b", "b"))
    assert fake.max_active_sends == 1
    j.close()


class FakeDiscord:
    def __init__(self):
        self.posts = []
        self.edits = []

    async def post(self, channel_id, text):
        self.posts.append((channel_id, text))
        return str(len(self.posts))

    async def edit(self, channel_id, message_id, text):
        self.edits.append((channel_id, message_id, text))

    async def find_marker(self, channel_id, marker):
        return next((str(i) for i, (channel, text) in enumerate(self.posts, 1)
                     if channel == channel_id and marker in text), None)

    async def message_matches(self, channel_id, message_id, marker):
        index = int(message_id) - 1
        return (0 <= index < len(self.posts) and self.posts[index][0] == channel_id
                and marker in self.posts[index][1])


async def test_discord_dedup_and_one_board(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, discord_thread_id="thread")
    fake = FakeDiscord()
    p = DiscordPublisher(j, fake, "board")
    await p.flush()
    await p.flush()
    assert [x[0] for x in fake.posts] == ["thread", "board"]
    j.change(task["task_id"], "dispatching")
    await p.flush()
    assert [x[0] for x in fake.posts] == ["thread", "board", "thread"]
    assert len(fake.edits) == 1
    j.close()


class FakeJev:
    def __init__(self, choice="planning", confidence=0.5):
        self.choice = choice
        self.confidence = confidence

    async def ask(self, state, questions):
        if self.choice is None:
            return None
        return {"step_type": {"choice": self.choice, "confidence": self.confidence}}


async def test_router_cap_quota_and_fail_open(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    tid = task["task_id"]
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude-opus-4-6-thinking", 10),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5"),
        ProviderEntry("agy-gemini-flash", "agy-shim", "http://127.0.0.1:18795/v1", "gemini", 0),
    ])
    router = ModelRouter(j, FakeJev("status_relay", 0.9),
                         RouterConfig(allow_gemini_status=True), catalog)
    assert (await router.choose(tid, "update", "status"))["provider"] == "agy-gemini-flash"
    router = ModelRouter(j, FakeJev("review", 0.4), RouterConfig(agy_claude_daily_cap=1), catalog)
    assert (await router.choose(tid, "review", "candidate"))["provider"] == "claude"
    router.record_provider_result("claude", "quota_error")
    assert (await router.choose(tid, "review2", "candidate"))["provider"] == "agy-claude"
    router.record_provider_result("agy-claude", "success")
    assert (await router.choose(tid, "review3", "candidate"))["provider"] == "codex"
    router = ModelRouter(j, FakeJev(None))
    assert (await router.choose(tid, "unknown", "?"))["provider"] == "codex"
    assert len(j.routes(tid)) == 5
    assert all(e["kind"] == "model_route" for e in j.events(tid)[-5:])
    j.close()


async def test_router_rejects_invalid_confidence_and_prescreen_scores(tmp_path):
    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18796/v1",
                      "claude-opus-4-6-thinking", 10),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5"),
    ])

    class InvalidJev:
        async def ask(self, state, questions):
            return {"step_type": {"choice": "review", "confidence": float("nan")}}

        async def merge_gate(self, *args):
            return {"diff_verdict": "unsafe", "diff_confidence": float("nan"), "tests_ok": 1}

    router = ModelRouter(journal, InvalidJev(), catalog=catalog)
    routed = await router.choose(task["task_id"], "review:invalid", "review",
                                 expected_type="review", high_stakes=True)
    assert routed["provider"] == "codex" and routed["reason"] == "jev_unavailable"
    assert await router.prescreen(task["task_id"], commit="a" * 40, tree="b" * 40,
                                  request="x", final_output="done", diff_excerpt="diff --git", tests="ok") is None
    assert not any(e["kind"] == "jev_prescreen" for e in journal.events(task["task_id"]))
    journal.close()


async def test_router_provider_override_and_recipe_precedence(tmp_path, monkeypatch):
    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal, engine="goose")
    router = ModelRouter(journal, FakeJev("planning", 0.9))
    choice = await router.choose(task["task_id"], "planning:recipe", "plan",
                                 expected_type="planning", provider_override="claude")
    assert choice["provider"] == "claude" and choice["reason"] == "task_or_recipe_override"
    assert (await router.choose(task["task_id"], "planning:recipe", "plan")) == choice
    monkeypatch.setattr(goose_acp, "load", lambda _name: {
        "instructions": "plan", "prompt": "do it", "pm_provider": "claude"})
    seen = []

    async def fake_run(*args, **kwargs):
        seen.append(kwargs["provider_id"])
        return {"stop_reason": "end_turn"}

    goose = GooseACP()
    monkeypatch.setattr(goose, "run", fake_run)
    await goose.run_task({**task, "_route_provider": "codex"}, str(tmp_path), capability="synthetic")
    assert seen == ["claude"]
    journal.close()


async def test_pause_while_jev_routes_start_does_not_start_bat(tmp_path):
    class SlowRouter:
        def __init__(self):
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def choose(self, *args, **kwargs):
            self.entered.set()
            await self.release.wait()
            return {"provider": "codex"}

    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    fake = FakeBAT()
    router = SlowRouter()
    core = TaskCoordinator(journal, fake, router=router)
    tick = asyncio.create_task(core.tick(task["task_id"]))
    await asyncio.wait_for(router.entered.wait(), 2)
    assert (await core.pause(task["task_id"]))["paused"]
    router.release.set()
    assert (await asyncio.wait_for(tick, 2))["paused"]
    assert fake.starts == [] and fake.sends == []
    journal.close()


async def test_candidate_change_during_jev_route_does_not_start_review(tmp_path):
    fake = FakeBAT()

    class MutatingRouter:
        changed = False

        async def choose(self, *args, **kwargs):
            if kwargs.get("expected_type") == "verification" and not self.changed:
                self.changed = True
                fake.identity = {"candidate_commit": "c" * 40, "tree_hash": "d" * 40, "clean": True}
            return {"provider": "codex"}

    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    router = MutatingRouter()
    core = TaskCoordinator(journal, fake, router=router)
    await core.tick(task["task_id"])
    lead = journal.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    await core.tick(task["task_id"])
    current = journal.get(task["task_id"])
    assert router.changed and current["reviewer_session_id"] is None
    assert current["verification_commit"] is None
    journal.close()


async def test_rules_route_each_pm_phase_and_jev_prescreen_is_advisory(tmp_path):
    class PhaseJev:
        async def ask(self, state, questions):
            step_type = state["step"].split(" ", 1)[0]
            confidence = 0.95 if step_type in {"status_relay", "implementation"} else 0.35
            return {"step_type": {"choice": step_type, "confidence": confidence}}

        async def merge_gate(self, task, final_output, diff_excerpt, tests):
            assert "diff --git" in diff_excerpt and "exit=0" in tests
            return {"diff_verdict": "unsafe", "diff_confidence": 0.9,
                    "tests_ok": 0.9, "claims_done": 0.9}

    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18796/v1",
                      "claude-opus-4-6-thinking", 10),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5"),
        ProviderEntry("agy-gemini-flash", "agy-shim", "http://127.0.0.1:18796/v1",
                      "gemini-flash-test"),
    ])
    router = ModelRouter(journal, PhaseJev(), RouterConfig(), catalog)
    fake = FakeBAT()
    fake.reviewer_kind = "claude"
    fake.diff_excerpt = "diff --git a/a.py b/a.py\n+safe change"
    core = TaskCoordinator(journal, fake, router=router)
    await core.tick(task["task_id"])
    lead = journal.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True,
                        "turn_attribution": "correlated", "streaming": False,
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    await core.tick(task["task_id"])
    reviewer = journal.get(task["task_id"])["reviewer_session_id"]
    assert reviewer and reviewer != lead
    fake.reads[reviewer] = {"turn_started": True, "turn_done": True,
                            "turn_attribution": "correlated", "first_turn_proven": True,
                            "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    assert (await core.tick(task["task_id"]))["state"] == "done"
    routes = journal.routes(task["task_id"])
    assert {r["step_type"] for r in routes} == {
        "planning", "implementation", "status_relay", "verification", "review"}
    assert all(r["provider"] == "claude" for r in routes
               if r["step_type"] in {"planning", "verification", "review"})
    assert all(r["provider"] == "agy-gemini-flash" for r in routes
               if r["step_type"] in {"status_relay", "implementation"})
    prescreen = [e for e in journal.events(task["task_id"]) if e["kind"] == "jev_prescreen"]
    assert len(prescreen) == 1 and json.loads(prescreen[0]["body"])["verdict"] == "unsafe"
    assert journal.get(task["task_id"])["delivered"]  # advisory signal cannot replace reviewer PASS
    journal.close()


async def test_work_status_exposes_router_metrics_and_jev_fails_open(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock), db_path=tmp_path / "tasks.db")
    task = submit(daemon.journal)
    daemon.router.classifier = FakeJev(None)
    first = await daemon.call("work_status", {"task_id": task["task_id"]})
    second = await daemon.call("work_status", {"task_id": task["task_id"]})
    assert first["routing_metrics"] == second["routing_metrics"]
    assert first["routing_metrics"]["count"] == 1
    assert first["routing_decisions"][0]["step_type"] == "status_relay"
    assert first["routing_decisions"][0]["provider"] == "codex"
    assert first["routing_decisions"][0]["reason"] == "jev_unavailable"
    await daemon.fleet.close()
    daemon.journal.close()


async def test_mcp_work_submit_returns_without_bat(mock, monkeypatch):
    seen = {}

    def fake_request(method, **params):
        seen.update(method=method, **params)
        return {"task_id": "task-1", "state": "queued"}

    monkeypatch.setattr(mcp_server, "task_request", fake_request)
    server, fleet = mcp_server.build_server(make_config(mock, writes=True, orchestrate=True))
    result = await server.call_tool("work_submit", {"project": "p", "host": "h1", "workspace": "w",
                                                    "original_words": WORDS, "idempotency_key": "discord:1"})
    assert "task-1" in json.dumps(result.model_dump(), default=str)
    assert seen["original_words"] == WORDS and seen["method"] == "work_submit"
    await fleet.close()


async def test_daemon_submit_is_journal_only(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    try:
        result = await asyncio.wait_for(daemon.call("work_submit", {
            "project": "p", "host": "h1", "workspace": "w", "original_words": WORDS,
            "idempotency_key": "discord:message:1"}), timeout=0.5)
        assert result["state"] == "queued"
        assert daemon.journal.get(result["task_id"])["original_words"] == WORDS
    finally:
        await daemon.fleet.close()
        daemon.journal.close()


async def test_goose_acp_scoped_tool_smoke(mock, tmp_path, monkeypatch):
    """Fake ACP Goose invokes a real scoped MCP tool backed by fake BAT."""
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    fake = FakeBAT()
    daemon.adapter = fake
    daemon.coordinator = TaskCoordinator(daemon.journal, fake)
    task = submit(daemon.journal, engine="goose")
    daemon.journal.change(task["task_id"], "dispatching")
    daemon.journal.change(task["task_id"], "accepted", fields={"session_id": "lead-0001"})
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    script = tmp_path / "fake_goose.py"
    script.write_text('''import json, os, subprocess, sys
def reply(req, result):
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)
initialized = False
for line in sys.stdin:
    req=json.loads(line)
    if req["method"] == "initialize":
        reply(req,{"protocolVersion":1,"agentCapabilities":{}})
    elif req["method"] == "notifications/initialized":
        initialized = True
    elif req["method"] == "session/new":
        assert initialized

        scoped=req["params"]["mcpServers"]
        assert len(scoped)==1 and scoped[0]["name"]=="bat-task"
        reply(req,{"sessionId":"fake-goose-session"})
    elif req["method"] == "session/prompt":
        env=os.environ.copy()
        for item in scoped[0]["env"]: env[item["name"]]=item["value"]
        p=subprocess.Popen([scoped[0]["command"],*scoped[0]["args"]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
        def call(obj):
            p.stdin.write(json.dumps(obj)+"\\n");p.stdin.flush()
            return json.loads(p.stdout.readline())
        call({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"fake-goose","version":"1"}}})
        p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\\n");p.stdin.flush()
        result=call({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"task_send","arguments":{"text":"check task","step_id":"one"}}})
        print(json.dumps({"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":json.dumps(result)}}}}), flush=True)
        p.terminate();p.wait()
        reply(req,{"stopReason":"end_turn"})
''')
    goose = GooseACP(GooseConfig(timeout_s=20, enabled=True, provider="codex"))
    try:
        capability = daemon.journal.issue_capability(task["task_id"])
        result = await goose.run_task(task, str(tmp_path), capability=capability,
                                      command=(sys.executable, "-u", str(script)))
        assert result["stop_reason"] == "end_turn"
        assert len(fake.sends) == 1 and fake.sends[0][1] == "check task"
    finally:
        server.close()
        await server.wait_closed()
        await daemon.fleet.close()
        daemon.journal.close()


async def test_uncertain_submission_marker_and_busy_rejection(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    sends = [c for c in j.commands(task["task_id"]) if c["kind"] == "send"]
    assert len(sends) == 1 and sends[0]["status"] == "uncertain"
    assert any(e["kind"] == "command_intent" and json.loads(e["body"]).get("needs_review")
               for e in j.events(task["task_id"]))
    await core.tick(task["task_id"])
    assert len(fake.sends) == 1
    with pytest.raises(ValueError, match="does not allow dispatch"):
        j.command(task["task_id"], "send", j.get(task["task_id"])["session_id"], {}, "another-step")
    j.close()

    class BusyBAT(FakeBAT):
        async def send(self, task, session_id, text, message_id):
            self.sends.append((session_id, text, message_id))
            return {"accepted": False, "reason": "busy"}

    j = Journal(tmp_path / "busy.db")
    task = submit(j)
    busy = BusyBAT()
    core = TaskCoordinator(j, busy)
    assert (await core.tick(task["task_id"]))["state"] == "needs_ted"
    assert [c["status"] for c in j.commands(task["task_id"]) if c["kind"] == "send"] == ["rejected"]
    await core.tick(task["task_id"])
    assert len(busy.sends) == 1
    j.close()


async def test_start_recovery_pause_during_start_and_branch_history(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    fake.start_error = True
    core = TaskCoordinator(j, fake)
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.starts) == 1
    fake.start_error = False
    assert (await core.tick(task["task_id"]))["state"] == "accepted"
    await core.tick(task["task_id"])
    assert len(fake.starts) == 1 and len(fake.sends) == 1
    assert j.get(task["task_id"])["branches"][0]["session_id"] == fake.starts[0][2]
    j.close()

    j = Journal(tmp_path / "paused.db")
    task = submit(j)
    fake = FakeBAT()
    fake.start_gate = asyncio.Event()
    core = TaskCoordinator(j, fake)
    tick = asyncio.create_task(core.tick(task["task_id"]))
    while not fake.starts:
        await asyncio.sleep(0)
    await core.pause(task["task_id"])
    fake.start_gate.set()
    paused = await tick
    assert paused["paused"] and paused["state"] == "accepted" and not fake.sends
    j.resume(task["task_id"])
    await core.tick(task["task_id"])
    assert len(fake.sends) == 1
    j.close()


async def test_candidate_change_requires_fresh_review_and_attribution(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    lead = j.get(task["task_id"])["session_id"]
    fake.reads[lead] = {"turn_started": True, "turn_done": True,
                        "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    await core.tick(task["task_id"])
    old = j.get(task["task_id"])["reviewer_session_id"]
    fake.reads[old] = {"turn_started": True, "turn_done": True, "turn_attribution": "correlated",
                       "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    assert (await core.tick(task["task_id"]))["state"] == "verifying"
    fake.reads[old]["first_turn_proven"] = True
    fake.identity = {"candidate_commit": "d" * 40, "tree_hash": "e" * 40, "clean": True}
    assert (await core.tick(task["task_id"]))["state"] == "verifying"
    assert j.get(task["task_id"])["reviewer_session_id"] != old
    assert not j.get(task["task_id"])["delivered"]
    j.close()


def test_ledger_handoff_archive_and_permissions(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    summary = ledger_summary(j, task["task_id"])
    assert task["task_id"] in summary and WORDS in summary
    assert "Hermes" not in summary
    data = "H" * 12_000 + "M" * 50_000 + "T" * 148_001
    result = history_excerpt(data, tmp_path / "private", task["task_id"])
    assert result["truncated"] and "middle omitted" in result["excerpt"]
    assert "M" * 1000 not in result["excerpt"]
    assert result["excerpt"].count("H") >= 12_000
    assert result["excerpt"].count("T") >= 148_000
    assert os.stat(result["archive_path"]).st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR
    assert os.stat(result["excerpt_path"]).st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR
    assert Path(result["excerpt_path"]).read_text() == result["excerpt"]
    assert (tmp_path / "private").stat().st_mode & 0o777 == 0o700
    assert open(result["archive_path"]).read() == data
    j.close()


async def test_live_failover_uses_private_history_fallback_when_ledger_unavailable(mock, tmp_path, monkeypatch):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    task = submit(daemon.journal, lead_agent="claude")
    daemon.journal.change(task["task_id"], "dispatching")
    daemon.journal.change(task["task_id"], "accepted", fields={"session_id": "old"})
    daemon.journal.change(task["task_id"], "running")
    task = daemon.journal.change(task["task_id"], "quota_limited")
    _, handoff = daemon.journal.reserve_failover(task["task_id"], "old", "successor")
    monkeypatch.setenv("BATC_TASK_LOCAL_HOST_ALIAS", "h1")
    monkeypatch.setattr(task_bat.registry, "get", lambda host, sid: {"agent_preset": "claude-agent"})

    def broken_summary(journal, task_id, **kwargs):
        raise ValueError("ledger unavailable")

    monkeypatch.setattr(task_bat, "ledger_summary", broken_summary)
    history = "H" * 12_000 + "M" * 50_000 + "T" * 148_001

    async def fake_read(*args, **kwargs):
        return {"messages": [{"role": "assistant", "text": history}], "next_offset": None}

    observed = {}

    async def fake_failover(*args, **kwargs):
        observed.update(kwargs)
        kwargs["before_handoff_send"]("synthetic BAT handoff\n" + kwargs["instructions"])
        return {"new_session_id": "successor", "prompt_sent": True, "message_id": "handoff"}

    monkeypatch.setattr(task_bat.service, "session_read", fake_read)
    monkeypatch.setattr(task_bat.lifecycle, "session_failover", fake_failover)
    async def verified(*args):
        return True
    monkeypatch.setattr(daemon.adapter, "_verified_failover_successor", verified)
    try:
        result = await daemon.adapter.failover(task, "old", "successor",
                                               handoff_message_id=handoff["message_id"],
                                               handoff_command_id=handoff["command_id"])
        assert result["session_id"] == "successor"
        assert observed["ledger_only"] is True
        files = list((tmp_path / "handoff-archive").glob("*.txt"))
        full = next(p for p in files if not p.name.endswith(".excerpt.txt"))
        excerpt = next(p for p in files if p.name.endswith(".excerpt.txt"))
        assert full.stat().st_mode & 0o777 == 0o600
        assert excerpt.stat().st_mode & 0o777 == 0o600
        assert "H" * 11_980 in excerpt.read_text() and "T" * 148_000 in excerpt.read_text()
        assert str(excerpt) in observed["instructions"] and str(full) in observed["instructions"]
    finally:
        await daemon.fleet.close()
        daemon.journal.close()


async def test_history_fallback_preserves_chronological_page_order(mock, tmp_path, monkeypatch):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    task = submit(daemon.journal, lead_agent="claude")

    async def fake_read(*args, **kwargs):
        if kwargs["offset"] == 0:
            return {"messages": [{"role": "user", "text": "middle"},
                                 {"role": "assistant", "text": "latest"}], "next_offset": 2}
        return {"messages": [{"role": "user", "text": "earliest"}], "next_offset": None}

    monkeypatch.setattr(task_bat.service, "session_read", fake_read)
    try:
        assert await daemon.adapter._history_for_fallback(task, "old") == (
            "user: earliest\nuser: middle\nassistant: latest")
    finally:
        await daemon.fleet.close()
        daemon.journal.close()


def test_provider_switches_branch_and_uncertain_never_replays(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    entries = [ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:9999/v1", "claude-opus-4-6-thinking", 1),
               ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5")]
    catalog = ProviderCatalog(entries)
    switcher = ProviderSwitcher(j, catalog)
    assert switcher.initial(task["task_id"]) == "claude"
    assert switcher.fallback(task["task_id"], "claude", outcome="quota_error",
                             prompt_status="not_sent") == "agy-claude"
    assert switcher.fallback(task["task_id"], "agy-claude", outcome="rate_limited",
                             prompt_status="not_sent") == "codex"
    branches = j.get(task["task_id"])["branches"]
    assert [b["provider"] for b in branches] == ["claude", "agy-claude", "codex"]
    assert j.get(task["task_id"])["branch_ids"] == [b["branch_id"] for b in branches]
    assert branches[1]["parent_branch_id"] == branches[0]["branch_id"]
    with pytest.raises(UncertainPrompt):
        switcher.fallback(task["task_id"], "codex", outcome="auth_error", prompt_status="uncertain")
    assert len(j.get(task["task_id"])["branches"]) == 3
    j.close()


def test_provider_starts_on_agy_after_primary_quota_recorded(tmp_path):
    journal = Journal(tmp_path / "tasks.db")
    task = submit(journal)
    journal.provider_use("claude", "quota_error")
    switcher = ProviderSwitcher(journal, ProviderCatalog())
    assert switcher.initial(task["task_id"]) == "agy-claude"
    assert [branch["provider"] for branch in journal.branches(task["task_id"])] == ["agy-claude"]
    journal.close()


async def test_agy_provider_contract_with_fake_endpoint():
    seen = []

    async def handle(reader, writer):
        request = await reader.readuntil(b"\r\n\r\n")
        seen.append(request)
        body = b'{"data":[{"id":"claude-opus-4-6-thinking"}]}'
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " +
                     str(len(body)).encode() + b"\r\n\r\n" + body)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        entry = ProviderEntry("agy-claude", "agy-shim", f"http://127.0.0.1:{port}/v1",
                              "claude-opus-4-6-thinking", 2)
        adapter = AgyShimAdapter()
        assert await adapter.contract_probe(entry, {"BATC_AGY_SHIM_TOKEN": "fake-local-token"})
        wrong_model = ProviderEntry("other", "openai-compatible", f"http://127.0.0.1:{port}/v1",
                                    "missing-model", 2)
        assert not await adapter.contract_probe(wrong_model, {"BATC_AGY_SHIM_TOKEN": "fake-local-token"})
        assert seen and b"GET /v1/models" in seen[0]
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("failure", ["quota", "setup"])
async def test_goose_provider_fallback_before_prompt_only(tmp_path, monkeypatch, failure):
    script = tmp_path / "fake_acp.py"
    script.write_text('''import json, os, sys
log=sys.argv[1]
for line in sys.stdin:
    req=json.loads(line)
    with open(log,"a") as f: f.write(os.environ["GOOSE_PROVIDER"]+":"+os.environ["GOOSE_MODEL"]+":"+req["method"]+":"+str("BATC_PRIVATE_TEST_SECRET" in os.environ)+"\\n")
    if req["method"]=="notifications/initialized":
        continue
    if req["method"]=="initialize" and os.environ["GOOSE_PROVIDER"]=="claude-acp" and sys.argv[2]=="quota":
        result={"jsonrpc":"2.0","id":req["id"],"error":{"status":429}}
    elif req["method"]=="session/new" and os.environ["GOOSE_PROVIDER"]=="claude-acp" and sys.argv[2]=="setup":
        result={"jsonrpc":"2.0","id":req["id"],"error":{"code":"unsupported_model"}}
    elif req["method"]=="session/new":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"s"}}
    elif req["method"]=="session/prompt":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end_turn"}}
    else:
        result={"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1}}
    print(json.dumps(result),flush=True)
''')
    log = tmp_path / "calls.txt"
    monkeypatch.setenv("BATC_AGY_SHIM_TOKEN", "fake-local-token")
    monkeypatch.setenv("BATC_PRIVATE_TEST_SECRET", "must-not-enter-Goose")
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude-opus-4-6-thinking", 1),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5"),
    ])
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, engine="goose")
    goose = GooseACP(GooseConfig(enabled=True, timeout_s=5), catalog)
    result = await goose.run_task(task, str(tmp_path), capability="synthetic",
                                  command=(sys.executable, "-u", str(script), str(log), failure), journal=j)
    assert result["stop_reason"] == "end_turn"
    lines = log.read_text().splitlines()
    assert lines.count("claude-acp:claude-opus-5-5:session/prompt:False") == 0
    assert lines.count("openai:claude-opus-4-6-thinking:session/prompt:False") == 1
    assert all(line.endswith(":False") for line in lines)
    assert [b["provider"] for b in j.branches(task["task_id"])] == ["claude", "agy-claude"]
    assert j.provider_unavailable("claude", since=0)
    j.close()


async def test_goose_uncertain_prompt_does_not_switch(tmp_path, monkeypatch):
    script = tmp_path / "fake_acp.py"
    script.write_text('''import json, os, sys
for line in sys.stdin:
    req=json.loads(line)
    if req["method"]=="notifications/initialized":
        continue
    if req["method"]=="session/prompt":
        with open(sys.argv[1],"a") as f: f.write(os.environ["GOOSE_PROVIDER"]+"\\n")
        result={"jsonrpc":"2.0","id":req["id"],"error":{"status":429}}
    elif req["method"]=="session/new":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"s"}}
    else:
        result={"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1}}
    print(json.dumps(result),flush=True)
''')
    log = tmp_path / "prompts.txt"
    monkeypatch.setenv("BATC_AGY_SHIM_TOKEN", "fake-local-token")
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude-opus-4-6-thinking", 1),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp", model="claude-opus-5-5"),
    ])
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, engine="goose")
    goose = GooseACP(GooseConfig(enabled=True, timeout_s=5), catalog)
    with pytest.raises(UncertainPrompt):
        await goose.run_task(task, str(tmp_path), capability="synthetic",
                             command=(sys.executable, "-u", str(script), str(log)), journal=j)
    assert log.read_text().splitlines() == ["claude-acp"]
    assert [b["provider"] for b in j.branches(task["task_id"])] == ["claude"]
    j.close()


async def test_goose_pinned_protocol_rejects_unknown_version(tmp_path):
    script = tmp_path / "wrong_version.py"
    script.write_text('''import json, sys
for line in sys.stdin:
    req=json.loads(line)
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":2}}),flush=True)
''')
    goose = GooseACP(GooseConfig(enabled=True, provider="codex", timeout_s=5))
    with pytest.raises(RuntimeError, match="pinned version 1"):
        await goose.run("synthetic", str(tmp_path), "hello", capability="synthetic",
                        command=(sys.executable, "-u", str(script)))


async def test_failover_recovers_reserved_successor_without_reuse(tmp_path):
    class LostReplyBAT(FakeBAT):
        async def failover(self, task, session_id, successor_id, **kwargs):
            await super().failover(task, session_id, successor_id, **kwargs)
            raise TimeoutError("successor accepted but reply lost")

    j = Journal(tmp_path / "tasks.db")
    task = submit(j, lead_agent="claude")
    fake = LostReplyBAT()
    fake.failover_allowed = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    old_sid = j.get(task["task_id"])["session_id"]
    j.change(task["task_id"], "quota_limited")
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    recovered = await core.tick(task["task_id"])
    assert recovered["state"] == "uncertain" and recovered["session_id"] != old_sid
    assert fake.failover_calls == 1
    handoff = next(c for c in j.commands(task["task_id"]) if c["kind"] == "send"
                   and json.loads(c["payload"]).get("purpose") == "failover_handoff")
    assert handoff["status"] == "uncertain"
    assert [b["provider"] for b in recovered["branches"]] == ["claude", "codex"]
    j.close()


async def test_normal_failover_refuses_different_successor_response(tmp_path):
    class WrongReplyBAT(FakeBAT):
        async def failover(self, task, session_id, successor_id, **kwargs):
            result = await super().failover(task, session_id, successor_id, **kwargs)
            return {**result, "session_id": "previous-successor"}

    j = Journal(tmp_path / "tasks.db")
    task = submit(j, lead_agent="claude")
    fake = WrongReplyBAT()
    fake.failover_allowed = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    old_sid = j.get(task["task_id"])["session_id"]
    j.change(task["task_id"], "quota_limited")
    result = await core.tick(task["task_id"])
    cmds = j.commands(task["task_id"])
    failover = next(c for c in cmds if c["kind"] == "failover")
    handoff = next(c for c in cmds if json.loads(c["payload"]).get("purpose") == "failover_handoff")
    assert result["state"] == "uncertain" and result["session_id"] == old_sid
    assert [b["session_id"] for b in result["branches"]] == [old_sid]
    assert failover["session_id"] == handoff["session_id"] != "previous-successor"
    assert json.loads(failover["payload"])["operator_only"] is True
    sends = len(fake.sends)
    await core.tick(task["task_id"])
    assert len(fake.sends) == sends and fake.failover_calls == 1
    j.close()


async def test_recovery_conflict_stays_operator_only_after_registry_changes(tmp_path):
    class LostReplyBAT(FakeBAT):
        async def failover(self, task, session_id, successor_id, **kwargs):
            await super().failover(task, session_id, successor_id, **kwargs)
            raise TimeoutError("accepted successor, lost response")

    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j, lead_agent="claude")
    fake = LostReplyBAT()
    fake.failover_allowed = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    old_sid = j.get(task["task_id"])["session_id"]
    j.change(task["task_id"], "quota_limited")
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    failover = next(c for c in j.commands(task["task_id"]) if c["kind"] == "failover")
    handoff = j.command_get(json.loads(failover["payload"])["handoff_command_id"])
    reserved = failover["session_id"]
    fake.successors[old_sid] = {"session_id": "previous-successor", "marker": handoff["message_id"]}
    assert (await core.tick(task["task_id"]))["session_id"] == old_sid
    assert json.loads(j.command_get(failover["command_id"])["payload"])["operator_only"] is True
    fake.successors[old_sid] = {"session_id": reserved, "marker": handoff["message_id"]}
    j.close()
    j = Journal(path)
    core = TaskCoordinator(j, fake)
    assert (await core.tick(task["task_id"]))["session_id"] == old_sid
    assert len(j.get(task["task_id"])["branches"]) == 1 and fake.failover_calls == 1
    cap = j.issue_reconcile_capability(task["task_id"], failover["command_id"])
    reconciled = await core.resolve_command(task["task_id"], failover["command_id"], token=cap,
                                            outcome="superseded", actor="operator", source="incident:42",
                                            evidence="reserved successor identity cannot be verified")
    assert reconciled["state"] == "human_owned" and reconciled["session_id"] == old_sid
    assert j.command_get(failover["command_id"])["status"] == "resolved_superseded"
    assert j.command_get(handoff["command_id"])["status"] == "resolved_superseded"
    assert len(j.get(task["task_id"])["branches"]) == 1
    j.close()


@pytest.mark.parametrize("wait_stage", ["start_ack", "identity_lookup", "send_transport"])
async def test_pause_during_failover_wait_never_submits_handoff(
        fleet_factory, mock, tmp_path, monkeypatch, wait_stage):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    started = await orchestrate.session_start(fleet, "h1", "demo-project", "claude",
                                              confirm=True, prompt=None, use_worktree=True)
    old_sid = started["session_id"]
    mock.states[old_sid]["messages"] = [{"role": "assistant", "content": "You've hit your usage limit",
                                          "timestamp": 1_790_000_000_000}]
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="pause-failover:" + wait_stage, lead_agent="claude")
    j.change(task["task_id"], "dispatching")
    j.change(task["task_id"], "accepted", fields={"session_id": old_sid})
    j.add_branch(task["task_id"], session_id=old_sid, provider="claude", role="lead", reason="test")
    j.change(task["task_id"], "running")
    j.change(task["task_id"], "quota_limited")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    core = TaskCoordinator(j, adapter)
    client = fleet.client("h1")
    entered, release = asyncio.Event(), asyncio.Event()
    if wait_stage in {"start_ack", "identity_lookup"}:
        original_invoke = client.invoke

        async def held_invoke(channel, params=None, **kwargs):
            reply = await original_invoke(channel, params, **kwargs)
            if ((wait_stage == "start_ack" and channel == "claude:start-session"
                 and params["sessionId"] != old_sid)
                    or (wait_stage == "identity_lookup" and channel == "worktree:status"
                        and params["sessionId"] != old_sid)):
                entered.set()
                await release.wait()
            return reply

        monkeypatch.setattr(client, "invoke", held_invoke)
    else:
        original_checked = client._invoke_checked

        async def held_checked(channel, params, timeout, **kwargs):
            if channel == "claude:send-message" and params["sessionId"] != old_sid:
                entered.set()
                await release.wait()
            return await original_checked(channel, params, timeout, **kwargs)

        monkeypatch.setattr(client, "_invoke_checked", held_checked)
    try:
        tick = asyncio.create_task(core.tick(task["task_id"]))
        await asyncio.wait_for(entered.wait(), 5)
        assert (await core.pause(task["task_id"]))["paused"]
        release.set()
        paused = await asyncio.wait_for(tick, 5)
        assert paused["state"] == "uncertain" and paused["paused"]
        assert paused["session_id"] == old_sid and len(paused["branches"]) == 1
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
        failover = next(c for c in j.commands(task["task_id"]) if c["kind"] == "failover")
        handoff = j.command_get(json.loads(failover["payload"])["handoff_command_id"])
        assert json.loads(failover["payload"])["operator_only"] is True
        assert handoff["status"] == "uncertain"
        j.resume(task["task_id"])
        assert (await core.tick(task["task_id"]))["state"] == "uncertain"
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        release.set()
        await fleet.close()
        j.close()


@pytest.mark.parametrize("mismatch", ["successor_cwd", "successor_branch",
                                      "actual_frame_prompt", "late_registry_branch",
                                      "late_registry_owner", "late_git_root"])
async def test_failover_rejects_wrong_successor_or_frame_before_handoff(
        fleet_factory, mock, tmp_path, monkeypatch, mismatch):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    started = await orchestrate.session_start(fleet, "h1", "demo-project", "claude",
                                              confirm=True, prompt=None, use_worktree=True)
    old_sid = started["session_id"]
    mock.states[old_sid]["messages"] = [{"role": "assistant", "content": "You've hit your usage limit",
                                          "timestamp": 1_790_000_000_000}]
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="wrong-failover:" + mismatch, lead_agent="claude")
    j.change(task["task_id"], "dispatching")
    j.change(task["task_id"], "accepted", fields={"session_id": old_sid})
    j.add_branch(task["task_id"], session_id=old_sid, provider="claude", role="lead", reason="test")
    j.change(task["task_id"], "running")
    j.change(task["task_id"], "quota_limited")
    core = TaskCoordinator(j, task_bat.BatTaskAdapter(
        fleet, ObservedVerifier(VerificationSettings()), j))
    client = fleet.client("h1")
    original_invoke = client.invoke

    async def changed_invoke(channel, params=None, **kwargs):
        if channel == "claude:send-message" and mismatch == "actual_frame_prompt":
            return await original_invoke(channel, {**params, "prompt": params["prompt"] + " ALTERED"}, **kwargs)
        if channel == "claude:send-message" and mismatch == "late_registry_branch":
            registry.update("h1", params["sessionId"], branch="bat/wrong-branch")
        if channel == "claude:send-message" and mismatch == "late_git_root":
            mock.handlers["git:getRoot"] = lambda _: "/srv/other"
        if channel == "claude:send-message" and mismatch == "late_registry_owner":
            original_guard = kwargs["frame_guard"]

            def changed_guard(frame):
                registry.update("h1", params["sessionId"], failover_of="unrelated-session")
                original_guard(frame)

            kwargs["frame_guard"] = changed_guard
        result = await original_invoke(channel, params, **kwargs)
        if channel == "claude:start-session" and params["sessionId"] != old_sid:
            sid = params["sessionId"]
            if mismatch == "successor_cwd":
                mock.metas[sid]["cwd"] = "/srv/other"
            elif mismatch == "successor_branch":
                mock.worktrees[sid]["branchName"] = "bat/wrong-branch"
        return result

    monkeypatch.setattr(client, "invoke", changed_invoke)
    try:
        result = await core.tick(task["task_id"])
        assert result["state"] == "uncertain" and result["session_id"] == old_sid
        assert len(result["branches"]) == 1
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
        failover = next(c for c in j.commands(task["task_id"]) if c["kind"] == "failover")
        handoff = j.command_get(json.loads(failover["payload"])["handoff_command_id"])
        assert json.loads(failover["payload"])["operator_only"] is True
        assert handoff["status"] == "uncertain"
        assert json.loads(handoff["payload"])["prompt_sha256"]
        assert (await core.tick(task["task_id"]))["session_id"] == old_sid
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        await fleet.close()
        j.close()


@pytest.mark.parametrize("change", ["git_root", "branch", "failover_of"])
async def test_failover_rechecks_identity_after_semaphore_wait(
        fleet_factory, mock, tmp_path, monkeypatch, change):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    started = await orchestrate.session_start(fleet, "h1", "demo-project", "claude",
                                              confirm=True, prompt=None, use_worktree=True)
    old_sid = started["session_id"]
    mock.states[old_sid]["messages"] = [{"role": "assistant", "content": "You've hit your usage limit",
                                          "timestamp": 1_790_000_000_000}]
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="sem-wait:" + change, lead_agent="claude")
    j.change(task["task_id"], "dispatching")
    j.change(task["task_id"], "accepted", fields={"session_id": old_sid})
    j.add_branch(task["task_id"], session_id=old_sid, provider="claude", role="lead", reason="test")
    j.change(task["task_id"], "running")
    j.change(task["task_id"], "quota_limited")
    core = TaskCoordinator(j, task_bat.BatTaskAdapter(
        fleet, ObservedVerifier(VerificationSettings()), j))
    client = fleet.client("h1")
    original_checked = client._invoke_checked
    entered = asyncio.Event()
    blocked_sem = asyncio.Semaphore(1)
    await blocked_sem.acquire()

    async def waiting_checked(channel, params, timeout, **kwargs):
        if channel != "claude:send-message":
            return await original_checked(channel, params, timeout, **kwargs)
        old_sem = client._sem
        client._sem = blocked_sem
        entered.set()
        try:
            return await original_checked(channel, params, timeout, **kwargs)
        finally:
            client._sem = old_sem

    monkeypatch.setattr(client, "_invoke_checked", waiting_checked)
    try:
        tick = asyncio.create_task(core.tick(task["task_id"]))
        await asyncio.wait_for(entered.wait(), 5)
        failover = next(c for c in j.commands(task["task_id"]) if c["kind"] == "failover")
        successor = failover["session_id"]
        if change == "git_root":
            mock.handlers["git:getRoot"] = lambda _: "/srv/other"
        elif change == "branch":
            mock.worktrees[successor]["branchName"] = "bat/wrong-branch"
        else:
            registry.update("h1", successor, failover_of="unrelated-session")
        blocked_sem.release()
        result = await asyncio.wait_for(tick, 5)
        handoff = j.command_get(json.loads(failover["payload"])["handoff_command_id"])
        assert result["state"] == "uncertain" and result["session_id"] == old_sid
        assert len(result["branches"]) == 1 and handoff["status"] == "uncertain"
        assert json.loads(j.command_get(failover["command_id"])["payload"])["operator_only"] is True
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
        await core.tick(task["task_id"])
        assert not any(i["channel"] == "claude:send-message" for i in mock.invokes)
    finally:
        blocked_sem.release()
        await fleet.close()
        j.close()


async def test_verified_successor_handoff_frame_hash_survives_restart(fleet_factory, mock, tmp_path):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    started = await orchestrate.session_start(fleet, "h1", "demo-project", "claude",
                                              confirm=True, prompt=None, use_worktree=True)
    old_sid = started["session_id"]
    mock.states[old_sid]["messages"] = [{"role": "assistant", "content": "You've hit your usage limit",
                                          "timestamp": 1_790_000_000_000}]
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="verified-handoff", lead_agent="claude")
    j.change(task["task_id"], "dispatching")
    j.change(task["task_id"], "accepted", fields={"session_id": old_sid})
    j.add_branch(task["task_id"], session_id=old_sid, provider="claude", role="lead", reason="test")
    j.change(task["task_id"], "running")
    old_task = j.change(task["task_id"], "quota_limited")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    try:
        result = await TaskCoordinator(j, adapter).tick(task["task_id"])
        assert result["state"] == "uncertain" and result["session_id"] != old_sid
        assert len(result["branches"]) == 2
        sends = [i for i in mock.invokes if i["channel"] == "claude:send-message"]
        assert len(sends) == 1 and sends[0]["params"]["sessionId"] == result["session_id"]
        failover = next(c for c in j.commands(task["task_id"]) if c["kind"] == "failover")
        handoff = j.command_get(json.loads(failover["payload"])["handoff_command_id"])
        actual_hash = hashlib.sha256(sends[0]["params"]["prompt"].encode()).hexdigest()
        assert json.loads(handoff["payload"])["prompt_sha256"] == actual_hash
        assert registry.get("h1", result["session_id"])["handoff_frame_sha256"] == actual_hash
        j.close()
        reopened = Journal(path)
        adapter.journal = reopened
        try:
            assert await adapter.recover_failover(old_task, successor_id=result["session_id"],
                                                  handoff_message_id=handoff["message_id"],
                                                  handoff_command_id=handoff["command_id"]) == {
                                                      "session_id": result["session_id"],
                                                      "marker": handoff["message_id"]}
        finally:
            reopened.close()
    finally:
        await fleet.close()


async def test_lost_codex_handoff_stays_scoped_uncertain_across_restart(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    task = submit(j, lead_agent="claude")
    fake = FakeBAT()
    fake.failover_allowed = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    j.change(task["task_id"], "quota_limited")
    result = await core.tick(task["task_id"])
    successor = result["session_id"]
    assert result["state"] == "uncertain"
    handoff = next(c for c in j.commands(task["task_id"]) if c["kind"] == "send"
                   and json.loads(c["payload"]).get("purpose") == "failover_handoff")
    assert handoff["status"] == "uncertain" and handoff["session_id"] == successor
    assert fake.sends[-1][2] == handoff["message_id"]
    fake.reads[successor] = {"turn_started": True, "turn_done": True,
                             "turn_attribution": "echo_not_visible", "streaming": False,
                             "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    sends = len(fake.sends)
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.sends) == sends and fake.failover_calls == 1 and not j.get(task["task_id"])["delivered"]
    j.close()
    j = Journal(path)
    core = TaskCoordinator(j, fake)
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.sends) == sends
    cap = j.issue_reconcile_capability(task["task_id"], handoff["command_id"])
    fake.reads[successor]["streaming"] = True
    with pytest.raises(ValueError, match="confirmed idle"):
        await core.resolve_command(task["task_id"], handoff["command_id"], token=cap,
                                   outcome="delivered", actor="operator", source="ticket:handoff",
                                   evidence="inspected exact successor and handoff command",
                                   next_prompt="Inspect task state after the handoff")
    fake.reads[successor]["streaming"] = False
    fake.prepare_kind = "codex"
    result = await core.resolve_command(task["task_id"], handoff["command_id"], token=cap,
                                        outcome="delivered", actor="operator", source="ticket:handoff",
                                        evidence="inspected exact successor and handoff command",
                                        next_prompt="Inspect task state after the handoff")
    assert result["state"] == "uncertain" and len(fake.sends) == sends + 1
    assert fake.sends[-1][1] != fake.sends[-2][1]
    assert fake.failover_calls == 1
    assert j.command_get(handoff["command_id"])["status"] == "resolved_delivered"
    assert not j.get(task["task_id"])["delivered"]
    assert (await core.tick(task["task_id"]))["state"] == "uncertain"
    assert len(fake.sends) == sends + 1
    j.close()


def test_handoff_ledger_preserves_words_beyond_old_2200_limit(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    words = "前" * 2201 + "完整結尾"
    task = j.submit(project="p", host="h1", workspace="w", original_words=words,
                    idempotency_key="long-request")
    assert words in ledger_summary(j, task["task_id"])
    prompt = task_bat.lifecycle.build_handoff_prompt(
        old_sid="old", workspace="w", cwd="/tmp/synthetic", same_worktree=True,
        branch="feat/test", first_prompt=None, last_prompt=None, recent=[], git={},
        evidence="quota", instructions=ledger_summary(j, task["task_id"]),
        authoritative_original=True)
    assert words in prompt and "overrides the original task's scope" not in prompt
    j.close()
    j = Journal(path)
    assert j.get(task["task_id"])["original_words"] == words
    assert words in ledger_summary(j, task["task_id"])
    with pytest.raises(ValueError, match="too long"):
        j.submit(project="p", host="h1", workspace="w", original_words="x" * 19_001,
                 idempotency_key="over-bat-limit")
    j.close()


@pytest.mark.parametrize("word_count", [17_950, 18_050])
async def test_failover_full_original_archive_verified_and_restart(mock, tmp_path, monkeypatch, word_count):
    path = tmp_path / "tasks.db"
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), path)
    words = "Ted 原話。" + "字" * word_count + "END-VERBATIM"
    task = daemon.journal.submit(project="p", host="h1", workspace="w", original_words=words,
                                 idempotency_key=f"long:{word_count}", lead_agent="claude")
    daemon.journal.change(task["task_id"], "dispatching")
    daemon.journal.change(task["task_id"], "accepted", fields={"session_id": "old"})
    daemon.journal.change(task["task_id"], "running")
    task = daemon.journal.change(task["task_id"], "quota_limited")
    _, handoff = daemon.journal.reserve_failover(task["task_id"], "old", "successor")
    monkeypatch.setenv("BATC_TASK_LOCAL_HOST_ALIAS", "h1")
    monkeypatch.setattr(task_bat.registry, "get", lambda host, sid: {"agent_preset": "claude-agent"})
    called = []

    async def fake_failover(*args, **kwargs):
        called.append(kwargs)
        kwargs["before_handoff_send"]("synthetic BAT handoff\n" + kwargs["instructions"])
        return {"new_session_id": "successor", "prompt_sent": True,
                "message_id": kwargs["handoff_message_id"]}

    monkeypatch.setattr(task_bat.lifecycle, "session_failover", fake_failover)
    async def verified(*args):
        return True
    monkeypatch.setattr(daemon.adapter, "_verified_failover_successor", verified)
    try:
        with pytest.raises(ValueError, match="host verifier is unset"):
            await daemon.adapter.failover(task, "old", "successor",
                                          handoff_message_id=handoff["message_id"],
                                          handoff_command_id=handoff["command_id"])
        assert not called
        monkeypatch.setenv("BATC_TASK_ARCHIVE_VERIFY_SSH_HOST", "bat-local-user")

        monkeypatch.setattr(task_bat.subprocess, "run", lambda command, **kwargs:
                            subprocess.CompletedProcess(command, 1, "", "unreadable"))
        with pytest.raises(ValueError, match="cannot verify"):
            await daemon.adapter.failover(task, "old", "successor",
                                          handoff_message_id=handoff["message_id"],
                                          handoff_command_id=handoff["command_id"])
        assert not called

        def fake_ssh(command, **kwargs):
            archive = next(p for p in (tmp_path / "handoff-archive").glob("*.original.txt")
                           if str(p) in command[-1])
            return subprocess.CompletedProcess(command, 0,
                                               hashlib.sha256(archive.read_bytes()).hexdigest() + "  file\n", "")

        monkeypatch.setattr(task_bat.subprocess, "run", fake_ssh)
        result = await daemon.adapter.failover(task, "old", "successor",
                                               handoff_message_id=handoff["message_id"],
                                               handoff_command_id=handoff["command_id"])
        assert result["marker"] == handoff["message_id"] and len(called) == 1
        archives = list((tmp_path / "handoff-archive").glob("*.original.txt"))
        referenced = next(p for p in archives if str(p) in called[0]["instructions"])
        assert referenced.stat().st_mode & 0o777 == 0o600
        assert referenced.read_text() == words
        assert hashlib.sha256(words.encode()).hexdigest() in called[0]["instructions"]
        assert json.loads(daemon.journal.command_get(handoff["command_id"])["payload"])["prompt_sha256"]
        daemon.journal.close()
        reopened = Journal(path)
        assert reopened.get(task["task_id"])["original_words"] == referenced.read_text()
        reopened.close()
    finally:
        await daemon.fleet.close()


async def test_discord_claim_recovery_after_restart(tmp_path):
    path = tmp_path / "tasks.db"
    j = Journal(path)
    submit(j, discord_thread_id="thread")
    event = j.discord_events()[0]
    assert j.claim_discord_event(event["event_id"])
    fake = FakeDiscord()
    await fake.post("thread", f"BATC-EVENT:{event['event_id']}\nposted before crash")
    assert j.board_claim("board", "BATC-BOARD:board\n任務看板")
    await fake.post("board", "BATC-BOARD:board\n任務看板")
    j.close()
    j = Journal(path)
    await DiscordPublisher(j, fake, "board").flush()
    assert len(fake.posts) == 2
    assert not j.discord_inflight() and not j.discord_unresolved()
    assert j.board_get("board")["message_id"] == "2"
    j.close()


async def test_discord_confirm_found_id_checks_marker(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    submit(j, discord_thread_id="thread")
    event = j.discord_events()[0]
    assert j.claim_discord_event(event["event_id"])
    j.discord_mark_unresolved(event["event_id"])
    fake = FakeDiscord()
    wrong = await fake.post("thread", "unrelated message")
    found = await fake.post("thread", f"BATC-EVENT:{event['event_id']}\nposted earlier")
    publisher = DiscordPublisher(j, fake, "board")
    with pytest.raises(ValueError, match="does not match"):
        await publisher.confirm_found(event_id=event["event_id"], message_id=wrong)
    assert (await publisher.confirm_found(event_id=event["event_id"], message_id=found))["status"] == "sent"
    assert j.discord_event_get(event["event_id"])["discord_message_id"] == found
    assert j.board_claim("board", "BATC-BOARD:board\n任務看板")
    j.board_mark_unresolved("board")
    board_mid = await fake.post("board", "BATC-BOARD:board\n任務看板")
    assert (await publisher.confirm_found(board_channel_id="board", message_id=board_mid))["status"] == "sent"
    j.close()


async def test_daemon_lock_and_rpc_task_scope(mock, tmp_path):
    path = tmp_path / "tasks.db"
    first = TaskDaemon(make_config(mock, writes=True, orchestrate=True), path)
    second = TaskDaemon(make_config(mock, writes=True, orchestrate=True), path)
    first.acquire_owner()
    with pytest.raises(RuntimeError, match="another task daemon"):
        second.acquire_owner()
    first.release_owner()
    second.acquire_owner()
    second.release_owner()
    task_a = submit(first.journal, engine="goose")
    task_b = first.journal.submit(project="p", host="h1", workspace="w", original_words="other",
                                  engine="goose", idempotency_key="discord:message:2")
    with pytest.raises(ValueError, match="caller-supplied"):
        await first.call("task_run_verification", {"task_id": task_a["task_id"], "exit_code": 0})
    cap = first.journal.issue_capability(task_a["task_id"])
    server = await asyncio.start_server(first._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async def rpc(token, method, task_id):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        body = json.dumps({"method": method, "params": {"task_id": task_id}}).encode()
        writer.write(b"POST /rpc HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " +
                     token.encode() + b"\r\nContent-Length: " + str(len(body)).encode() +
                     b"\r\n\r\n" + body)
        await writer.drain()
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
        return raw

    try:
        assert b"authorization failed" not in await rpc(first._admin_token, "work_status", task_a["task_id"])
        assert b"400 Bad Request" in await rpc("bad", "work_status", task_a["task_id"])
        assert b"400 Bad Request" in await rpc(cap, "work_status", task_a["task_id"])
        assert b"400 Bad Request" in await rpc(cap, "task_read", task_b["task_id"])
    finally:
        server.close()
        await server.wait_closed()
        await first.fleet.close()
        await second.fleet.close()
        first.journal.close()
        second.journal.close()


async def test_live_goose_remains_disabled_after_restart(mock, tmp_path):
    path = tmp_path / "tasks.db"
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), path)
    task = submit(daemon.journal, engine="goose")
    await daemon._tick_task(task["task_id"])
    assert daemon.journal.get(task["task_id"])["state"] == "uncertain"
    await daemon.fleet.close()
    daemon.journal.close()
    again = TaskDaemon(make_config(mock, writes=True, orchestrate=True), path)
    try:
        await again._tick_task(task["task_id"])
        assert again.journal.get(task["task_id"])["state"] == "uncertain"
        assert not again.journal.commands(task["task_id"])
        with pytest.raises(ValueError, match="disabled"):
            await again.call("work_submit", {"project": "p", "host": "h1", "workspace": "w",
                                              "original_words": WORDS, "idempotency_key": "new",
                                              "engine": "goose"})
    finally:
        await again.fleet.close()
        again.journal.close()


def test_provider_config_contract_and_structured_errors(tmp_path):
    assert GooseConfig().provider == "claude"
    assert ProviderCatalog().order == ("claude", "agy-claude", "codex")
    assert ProviderCatalog().entry("claude").model == "claude-opus-5-5"
    assert ProviderCatalog().entry("agy-claude").model == "claude-opus-4-6-thinking"
    with pytest.raises(ValueError, match="claude-opus-5-5"):
        ProviderEntry("claude", "claude-acp", model="claude-sonnet-5")
    with pytest.raises(ValueError, match="Opus|opus"):
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18796/v1",
                      "claude-sonnet-4-6", 2)
    path = tmp_path / "providers.toml"
    path.write_text('''fallback_order = ["claude", "agy-claude", "codex"]
[[providers]]
id = "claude"
kind = "claude-acp"
model = "claude-opus-5-5"
[[providers]]
id = "agy-claude"
kind = "agy-shim"
base_url = "http://127.0.0.1:18795/v1"
model = "claude-opus-4-6-thinking"
daily_cap = 2
[[providers]]
id = "codex"
kind = "codex-acp"
''')
    path.chmod(0o600)
    catalog = ProviderCatalog.from_file(path)
    assert catalog.order == ("claude", "agy-claude", "codex")
    assert catalog.environment("codex", {})["GOOSE_PROVIDER"] == "chatgpt_codex"
    assert catalog.environment("claude", {}) == {"GOOSE_PROVIDER": "claude-acp",
                                                   "GOOSE_MODEL": "claude-opus-5-5"}
    gemini = ProviderCatalog([ProviderEntry("gemini", "gemini", model="gemini-flash")], ("gemini",))
    assert gemini.environment("gemini", {}) == {"GOOSE_PROVIDER": "gemini", "GOOSE_MODEL": "gemini-flash"}
    with pytest.raises(ProviderSetupError, match="Gemini model"):
        ProviderCatalog([ProviderEntry("gemini", "gemini")], ("gemini",)).environment("gemini", {})
    assert classify_provider_error(status=429) == "rate_limited"
    assert classify_provider_error(code="insufficient_quota") == "quota_error"
    assert classify_provider_error(status=401) == "auth_error"
    assert classify_provider_error(code="unknown") is None
    path.chmod(0o644)
    with pytest.raises(ValueError, match="mode 0600"):
        ProviderCatalog.from_file(path)


def test_observed_verifier_ssh_command_keeps_remote_script_quoted():
    from bat_agent_connector.task_verifier import _remote_command

    cmd = _remote_command("castle", "/srv/work tree", ("pytest", "-q", "tests/test_task_service.py"))
    assert cmd[:4] == ("ssh", "-o", "BatchMode=yes", "castle")
    import shlex
    script = "cd -- " + shlex.quote("/srv/work tree") + " && pytest -q tests/test_task_service.py"
    assert cmd[4] == "sh -lc " + shlex.quote(script)


async def test_observed_verification_artifact_bound_to_clean_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "code.txt").write_text("candidate")
    subprocess.run(["git", "-C", str(repo), "add", "code.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "candidate"], check=True)
    artifacts = tmp_path / "artifacts"
    runner = ObservedVerifier(VerificationSettings(
        commands={"p": (sys.executable, "-c", "print('proof')", "fake-private-argument")},
        artifact_dir=str(artifacts)))
    task = {"task_id": "synthetic", "host": "local", "project": "p"}
    result = await runner.observe(task, str(repo))
    assert result and result["exit_code"] == 0
    assert result["output_sha256"] == hashlib.sha256(b"proof\n").hexdigest()
    assert result["candidate_commit"] == (await runner.identity(task, str(repo)))["candidate_commit"]
    assert result["command"].startswith("argv_sha256:")
    assert "fake-private-argument" not in json.dumps(result)
    assert os.stat(result["log_ref"]).st_mode & 0o777 == 0o600
    assert artifacts.stat().st_mode & 0o777 == 0o700
    (repo / "code.txt").write_text("dirty")
    assert await runner.observe(task, str(repo)) is None

@pytest.mark.asyncio
async def test_external_worktree_creation_is_restart_idempotent(tmp_path, fleet_factory, monkeypatch):
    journal = Journal(tmp_path / "tasks.sqlite3")
    task = journal.submit(project="p", host="h1", workspace="w", original_words="x",
                          base_branch="feat/task-service", idempotency_key="external-restart")
    adapter = task_bat.BatTaskAdapter(
        fleet_factory(), ObservedVerifier(VerificationSettings(ssh_hosts={"h1": "castle"})), journal
    )
    scripts = []

    async def folder(_task):
        return "/srv/repo"

    async def ssh(_task, script):
        scripts.append(script)
        return ""

    async def identity(_task, _cwd):
        return {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "clean": True}

    monkeypatch.setattr(adapter, "_workspace_folder", folder)
    monkeypatch.setattr(adapter, "_ssh_script", ssh)
    monkeypatch.setattr(adapter.verifier, "identity", identity)
    first = await adapter._ensure_external_worktree(task)
    second = await adapter._ensure_external_worktree(journal.get(task["task_id"]))
    assert first == second
    assert len(scripts) == 2 and all("worktree list --porcelain" in script for script in scripts)


@pytest.mark.asyncio
async def test_external_worktree_script_quotes_workspace_path(tmp_path, fleet_factory, monkeypatch):
    journal = Journal(tmp_path / "tasks.sqlite3")
    task = journal.submit(project="p", host="h1", workspace="w", original_words="x",
                          base_branch="feat/task-service", idempotency_key="quoted-root")
    adapter = task_bat.BatTaskAdapter(
        fleet_factory(), ObservedVerifier(VerificationSettings(ssh_hosts={"h1": "castle"})), journal)
    scripts = []

    async def capture(_task, script):
        scripts.append(script)
        return ""

    async def identity(_task, _cwd):
        return {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "clean": True}

    async def folder(_task):
        return "/srv/Ted's repo"

    monkeypatch.setattr(adapter, "_workspace_folder", folder)
    monkeypatch.setattr(adapter, "_ssh_script", capture)
    monkeypatch.setattr(adapter.verifier, "identity", identity)
    await adapter._ensure_external_worktree(task)
    assert subprocess.run(["bash", "-n", "-c", scripts[0]], check=False).returncode == 0
    assert '"$ref"' in scripts[0]


@pytest.mark.asyncio
async def test_external_cleanup_retains_unmerged_commit_and_recovers_after_restart(
        tmp_path, fleet_factory, monkeypatch):
    root = tmp_path / "Ted's repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "code.txt").write_text("base")
    subprocess.run(["git", "-C", str(root), "add", "code.txt"], check=True)
    commit = ["git", "-C", str(root), "-c", "user.name=Test",
              "-c", "user.email=test@example.invalid", "commit", "-qm"]
    subprocess.run([*commit, "base"], check=True)
    journal_path = tmp_path / "tasks.db"
    journal = Journal(journal_path)
    task = journal.submit(project="p", host="h1", workspace="w", original_words="keep work",
                          idempotency_key="cleanup-retain")
    suffix = task["task_id"].replace("-", "")[:12]
    branch = f"batc/task-{suffix}"
    path = root / ".bat-worktrees" / f"batc-task-{suffix}"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", "-b",
                    branch, str(path), "HEAD"], check=True)
    (path / "code.txt").write_text("unmerged candidate")
    subprocess.run(["git", "-C", str(path), "add", "code.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "candidate"], check=True)
    candidate = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                               check=True, capture_output=True, text=True).stdout.strip()
    journal.change(task["task_id"], "dispatching", fields={
        "external_worktree_path": str(path), "external_branch": branch})
    journal.change(task["task_id"], "failed")
    adapter = task_bat.BatTaskAdapter(fleet_factory(),
        ObservedVerifier(VerificationSettings(ssh_hosts={"h1": "unused"})), journal)

    async def folder(_task):
        return str(root)

    async def local_shell(_task, script):
        result = subprocess.run(["sh", "-lc", script], capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError(result.stderr or result.stdout or "cleanup failed")
        return result.stdout.strip()

    monkeypatch.setattr(adapter, "_workspace_folder", folder)
    monkeypatch.setattr(adapter, "_ssh_script", local_shell)
    (path / "untracked.txt").write_text("do not discard")
    with pytest.raises(ValueError):
        await adapter.cleanup_external_worktree(journal.get(task["task_id"]))
    assert path.exists()
    (path / "untracked.txt").unlink()
    with pytest.raises(ValueError):
        await adapter.cleanup_external_worktree({**journal.get(task["task_id"]),
                                                 "state": "done", "verification_commit": "0" * 40})
    assert path.exists()
    first = await adapter.cleanup_external_worktree(journal.get(task["task_id"]))
    assert first == {"path": str(path), "branch": branch,
                     "retained_ref": f"refs/batc/tasks/{suffix}",
                     "commit": candidate, "mode": "removed"}
    assert not path.exists()
    journal.close()  # Crash after Git removal but before journal settlement.
    journal = Journal(journal_path)
    assert [t["task_id"] for t in journal.list_cleanup_pending()] == [task["task_id"]]
    second = await adapter.cleanup_external_worktree(journal.get(task["task_id"]))
    assert second["mode"] == "already_removed" and second["commit"] == candidate
    journal.complete_external_cleanup(task["task_id"], second)
    assert not journal.list_cleanup_pending()
    assert journal.get(task["task_id"])["external_worktree_path"] is None
    assert any(e["kind"] == "external_worktree_retained" for e in journal.events(task["task_id"]))
    for ref in (f"refs/heads/{branch}", f"refs/batc/tasks/{suffix}"):
        value = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", ref],
                               check=True, capture_output=True, text=True).stdout.strip()
        assert value == candidate
    journal.close()


@pytest.mark.asyncio
async def test_terminal_cleanup_requires_proof_before_journal_path_is_cleared(mock, tmp_path, monkeypatch):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    task = submit(daemon.journal)
    suffix = task["task_id"].replace("-", "")[:12]
    path = f"/srv/project/.bat-worktrees/batc-task-{suffix}"
    branch = f"batc/task-{suffix}"
    daemon.journal.change(task["task_id"], "dispatching", fields={
        "external_worktree_path": path, "external_branch": branch})
    daemon.journal.change(task["task_id"], "failed")
    proof = {"path": path, "branch": branch, "retained_ref": f"refs/batc/tasks/{suffix}",
             "commit": "a" * 40, "mode": "removed"}

    async def no_proof(_task):
        return None

    monkeypatch.setattr(daemon.adapter, "cleanup_external_worktree", no_proof)
    await daemon._tick_task(task["task_id"])
    assert daemon.journal.get(task["task_id"])["external_worktree_path"] == path
    assert task["task_id"] in daemon._cleanup_retry_after

    async def retained(_task):
        return proof

    monkeypatch.setattr(daemon.adapter, "cleanup_external_worktree", retained)
    await daemon._tick_task(task["task_id"])
    assert daemon.journal.get(task["task_id"])["external_worktree_path"] is None
    assert task["task_id"] not in daemon._cleanup_retry_after
    assert any(e["kind"] == "external_worktree_retained"
               for e in daemon.journal.events(task["task_id"]))
    daemon.journal.close()

@pytest.mark.asyncio
async def test_goose_acp_error_settles_from_bat_readback(mock, tmp_path, monkeypatch, caplog):
    """A lost ACP terminal reply must not discard a committed, idle BAT turn."""
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True), tmp_path / "tasks.db")
    task = submit(daemon.journal, engine="goose")
    daemon.journal.change(task["task_id"], "dispatching")
    daemon.journal.change(task["task_id"], "accepted", fields={"session_id": "lead-readback"})
    monkeypatch.setattr(registry, "get", lambda _host, _sid: {"cwd": "/remote/not-on-box"})

    async def fail_run(*args, **kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_ERROR_DO_NOT_LOG")

    async def identity(_task):
        return {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "clean": True}

    async def read(_task, _sid, _marker):
        return {"streaming": False, "pending": None}

    class FakeGoose:
        config = GooseConfig(enabled=True)
        run_task = fail_run
    monkeypatch.setattr(daemon, "goose", FakeGoose())
    monkeypatch.setattr(daemon.adapter, "candidate_identity", identity)
    monkeypatch.setattr(daemon.adapter, "read", read)
    await daemon._tick_task(task["task_id"])
    settled = daemon.journal.get(task["task_id"])
    command = next(c for c in daemon.journal.commands(task["task_id"]) if c["kind"] == "goose_run")
    assert settled["state"] == "verifying"
    assert command["status"] == "settled"
    assert any(e["kind"] == "goose_readback_settled" for e in daemon.journal.events(task["task_id"]))
    assert "PRIVATE_PROVIDER_ERROR_DO_NOT_LOG" not in caplog.text
    await daemon.fleet.close()
    daemon.journal.close()

def test_agy_adapter_model_effort_policy(monkeypatch):
    monkeypatch.setenv("BATC_AGY_SHIM_TOKEN", "local-token")
    adapter = AgyShimAdapter()
    claude = ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18797/v1",
                           "claude-opus-4-6-thinking", 1)
    gemini = ProviderEntry("agy-gemini", "agy-shim", "http://127.0.0.1:18797/v1",
                           "gemini-3.8-flash", 1)
    assert adapter.environment(claude, {"BATC_AGY_SHIM_TOKEN": "local-token"})["BATC_AGY_REQUEST_POLICY"] == "omit_reasoning_effort"
    assert adapter.environment(gemini, {"BATC_AGY_SHIM_TOKEN": "local-token"})["BATC_AGY_REQUEST_POLICY"] == "pass_reasoning_effort"

@pytest.mark.asyncio
async def test_session_presence_retries_transient_workspace_timeout(fleet_factory, tmp_path, monkeypatch):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="presence-retry")
    sid = "presence-retry-session"
    j.add_branch(task["task_id"], session_id=sid, provider="codex", role="lead", reason="start")
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    calls = 0
    client = fleet.client("h1")
    async def invoke(channel, params, **kwargs):
        nonlocal calls
        if channel == "claude:get-session-meta":
            calls += 1
            if calls < 3:
                raise TimeoutError("workspace:load transient timeout")
            return {"cwd": "/srv/demo", "isStreaming": False}
        return {}
    monkeypatch.setattr(client, "invoke", invoke)
    async def restore(*args, **kwargs):
        return None
    monkeypatch.setattr(adapter, "_restore_headless_lookup", restore)
    try:
        assert await adapter.session_presence(task, sid) == "present"
        assert calls == 3
    finally:
        await fleet.close()
        j.close()


@pytest.mark.asyncio
async def test_reviewer_start_polls_existing_session_after_start_timeout(
        fleet_factory, tmp_path, monkeypatch):
    fleet = fleet_factory(writes=True, orchestrate=True, tabs=False,
                          safety={"write_min_interval_s": 0})
    j = Journal(tmp_path / "tasks.db")
    task = j.submit(project="p", host="h1", workspace="demo-project", original_words=WORDS,
                    idempotency_key="reviewer-start-retry")
    lead = "reviewer-start-lead"
    j.add_branch(task["task_id"], session_id=lead, provider="codex", role="lead", reason="start")
    task = {**task, "session_id": lead}
    adapter = task_bat.BatTaskAdapter(fleet, ObservedVerifier(VerificationSettings()), j)
    lead_entry = {"session_id": lead, "workspace_id": "ws-1", "workspace_name": "demo-project",
                  "origin_cwd": "/srv/demo", "cwd": "/srv/demo", "worktree_path": "/srv/demo",
                  "branch": "branch", "agent_preset": "codex-agent"}
    monkeypatch.setattr(task_bat.registry, "get", lambda _h, sid: lead_entry if sid == lead else None)
    monkeypatch.setattr(task_bat.registry, "reserve", lambda *a, **k: None)
    monkeypatch.setattr(task_bat.registry, "update", lambda *a, **k: None)
    monkeypatch.setattr(adapter, "session_presence", lambda *a, **k: asyncio.sleep(0, result="present"))
    calls = []
    client = fleet.client("h1")
    async def invoke(channel, params, **kwargs):
        calls.append(channel)
        if channel == "claude:start-session":
            raise TimeoutError("castle workspace load timeout")
        if channel == "claude:get-session-meta":
            return {"cwd": "/srv/demo", "isStreaming": False}
        return {}
    monkeypatch.setattr(client, "invoke", invoke)
    try:
        result = await adapter.start({**task, "branches": [{"session_id": lead, "role": "lead"}]},
                                     role="reviewer", agent="codex", session_id="reviewer-retry")
        assert result == "reviewer-retry"
        assert calls.count("claude:start-session") == 1
        assert "claude:get-session-meta" in calls
    finally:
        await fleet.close()
        j.close()
