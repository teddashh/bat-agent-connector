from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import subprocess
import sys

import pytest

from bat_agent_connector import mcp_server
from bat_agent_connector.goose_acp import GooseACP, GooseConfig
from bat_agent_connector.model_router import ModelRouter, RouterConfig
from bat_agent_connector.pm_providers import (
    AgyShimAdapter,
    ProviderCatalog,
    ProviderEntry,
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


def submit(journal, **kw):
    return journal.submit(project="p", host="h1", workspace="w", original_words=WORDS,
                          acceptance="tests pass", idempotency_key="discord:message:1", **kw)


class FakeBAT:
    def __init__(self):
        self.starts = []
        self.sends = []
        self.reads = {}
        self.identity = {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "clean": True}
        self.verifier_available = True
        self.reviewer_kind = "codex"
        self.started_ids = set()
        self.successors = {}
        self.failover_allowed = False
        self.start_error = False
        self.start_gate = None
        self.prepare_kind = "claude"
        self.failover_calls = 0
        self.interrupts = 0
        self.send_error = False
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

    async def send(self, task, session_id, text, message_id):
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        await asyncio.sleep(0)
        self.active_sends -= 1
        self.sends.append((session_id, text, message_id))
        if self.send_error:
            raise TimeoutError("lost response after possible acceptance")
        return {"accepted": True, "turn_marker": message_id if self.prepare_kind == "claude"
                else "2026-09-27T00:00:00+00:00"}

    async def read(self, task, session_id, marker):
        read = self.reads.get(session_id, {"turn_started": False, "turn_done": False}).copy()
        if read.get("turn_started") and "turn_attribution" not in read:
            read["turn_attribution"] = "correlated"
        return read

    async def interrupt(self, task, session_id):
        self.interrupts += 1

    async def failover(self, task, session_id, successor_id):
        self.failover_calls += 1
        if not self.failover_allowed:
            raise ValueError("Codex cannot Claude-to-Codex fail over")
        self.successors[session_id] = {"session_id": successor_id, "marker": "handoff-" + successor_id}
        return self.successors[session_id]

    async def recover_failover(self, task, *, successor_id):
        return self.successors.get(task["session_id"])

    async def candidate_identity(self, task):
        return self.identity

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
    successor = (await core.tick(task["task_id"]))["session_id"]
    assert successor != task["session_id"]
    assert fake.failover_calls == 1
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
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude", 10),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp"),
        ProviderEntry("agy-gemini-flash", "agy-shim", "http://127.0.0.1:18795/v1", "gemini", 0),
    ])
    router = ModelRouter(j, FakeJev("status_relay", 0.9),
                         RouterConfig(allow_gemini_status=True), catalog)
    assert (await router.choose(tid, "update", "status"))["provider"] == "agy-gemini-flash"
    router = ModelRouter(j, FakeJev("review", 0.4), RouterConfig(agy_claude_daily_cap=1), catalog)
    assert (await router.choose(tid, "review", "candidate"))["provider"] == "agy-claude"
    router.record_provider_result("agy-claude", "success")
    assert (await router.choose(tid, "review2", "candidate"))["provider"] == "codex"
    router = ModelRouter(j, FakeJev(None))
    assert (await router.choose(tid, "unknown", "?"))["provider"] == "codex"
    assert len(j.routes(tid)) == 4
    assert all(e["kind"] == "model_route" for e in j.events(tid)[-4:])
    j.close()


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
for line in sys.stdin:
    req=json.loads(line)
    if req["method"] == "initialize":
        reply(req,{"protocolVersion":2,"agentCapabilities":{}})
    elif req["method"] == "session/new":
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
    assert (tmp_path / "private").stat().st_mode & 0o777 == 0o700
    assert open(result["archive_path"]).read() == data
    j.close()


def test_provider_switches_branch_and_uncertain_never_replays(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    entries = [ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:9999/v1", "claude", 1),
               ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp")]
    catalog = ProviderCatalog(entries)
    switcher = ProviderSwitcher(j, catalog)
    assert switcher.initial(task["task_id"]) == "agy-claude"
    assert switcher.fallback(task["task_id"], "agy-claude", outcome="quota_error",
                             prompt_status="not_sent") == "codex"
    branches = j.get(task["task_id"])["branches"]
    assert [b["provider"] for b in branches] == ["agy-claude", "codex"]
    assert j.get(task["task_id"])["branch_ids"] == [b["branch_id"] for b in branches]
    assert branches[1]["parent_branch_id"] == branches[0]["branch_id"]
    with pytest.raises(UncertainPrompt):
        switcher.fallback(task["task_id"], "codex", outcome="auth_error", prompt_status="uncertain")
    assert len(j.get(task["task_id"])["branches"]) == 2
    j.close()


async def test_agy_provider_contract_with_fake_endpoint():
    seen = []

    async def handle(reader, writer):
        request = await reader.readuntil(b"\r\n\r\n")
        seen.append(request)
        body = b'{"data":[{"id":"claude"}]}'
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " +
                     str(len(body)).encode() + b"\r\n\r\n" + body)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        entry = ProviderEntry("agy-claude", "agy-shim", f"http://127.0.0.1:{port}/v1", "claude", 2)
        adapter = AgyShimAdapter()
        assert await adapter.contract_probe(entry, {"BATC_AGY_SHIM_TOKEN": "fake-local-token"})
        assert seen and b"GET /v1/models" in seen[0]
    finally:
        server.close()
        await server.wait_closed()


async def test_goose_provider_fallback_before_prompt_only(tmp_path, monkeypatch):
    script = tmp_path / "fake_acp.py"
    script.write_text('''import json, os, sys
log=sys.argv[1]
for line in sys.stdin:
    req=json.loads(line)
    with open(log,"a") as f: f.write(os.environ["GOOSE_PROVIDER"]+":"+req["method"]+":"+str("BATC_PRIVATE_TEST_SECRET" in os.environ)+"\\n")
    if req["method"]=="initialize" and os.environ["GOOSE_PROVIDER"]=="openai":
        result={"jsonrpc":"2.0","id":req["id"],"error":{"status":429}}
    elif req["method"]=="session/new":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"s"}}
    elif req["method"]=="session/prompt":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end_turn"}}
    else:
        result={"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":2}}
    print(json.dumps(result),flush=True)
''')
    log = tmp_path / "calls.txt"
    monkeypatch.setenv("BATC_AGY_SHIM_TOKEN", "fake-local-token")
    monkeypatch.setenv("BATC_PRIVATE_TEST_SECRET", "must-not-enter-Goose")
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude", 1),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp"),
    ])
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, engine="goose")
    goose = GooseACP(GooseConfig(enabled=True, timeout_s=5), catalog)
    result = await goose.run_task(task, str(tmp_path), capability="synthetic",
                                  command=(sys.executable, "-u", str(script), str(log)), journal=j)
    assert result["stop_reason"] == "end_turn"
    lines = log.read_text().splitlines()
    assert lines.count("openai:session/prompt:False") == 0
    assert lines.count("chatgpt_codex:session/prompt:False") == 1
    assert all(line.endswith(":False") for line in lines)
    assert [b["provider"] for b in j.branches(task["task_id"])] == ["agy-claude", "codex"]
    assert j.provider_unavailable("agy-claude", since=0)
    j.close()


async def test_goose_uncertain_prompt_does_not_switch(tmp_path, monkeypatch):
    script = tmp_path / "fake_acp.py"
    script.write_text('''import json, os, sys
for line in sys.stdin:
    req=json.loads(line)
    if req["method"]=="session/prompt":
        with open(sys.argv[1],"a") as f: f.write(os.environ["GOOSE_PROVIDER"]+"\\n")
        result={"jsonrpc":"2.0","id":req["id"],"error":{"status":429}}
    elif req["method"]=="session/new":
        result={"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"s"}}
    else:
        result={"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":2}}
    print(json.dumps(result),flush=True)
''')
    log = tmp_path / "prompts.txt"
    monkeypatch.setenv("BATC_AGY_SHIM_TOKEN", "fake-local-token")
    catalog = ProviderCatalog([
        ProviderEntry("agy-claude", "agy-shim", "http://127.0.0.1:18795/v1", "claude", 1),
        ProviderEntry("codex", "codex-acp"), ProviderEntry("claude", "claude-acp"),
    ])
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, engine="goose")
    goose = GooseACP(GooseConfig(enabled=True, timeout_s=5), catalog)
    with pytest.raises(UncertainPrompt):
        await goose.run_task(task, str(tmp_path), capability="synthetic",
                             command=(sys.executable, "-u", str(script), str(log)), journal=j)
    assert log.read_text().splitlines() == ["openai"]
    assert [b["provider"] for b in j.branches(task["task_id"])] == ["agy-claude"]
    j.close()


async def test_failover_recovers_reserved_successor_without_reuse(tmp_path):
    class LostReplyBAT(FakeBAT):
        async def failover(self, task, session_id, successor_id):
            await super().failover(task, session_id, successor_id)
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
    assert recovered["state"] == "running" and recovered["session_id"] != old_sid
    assert fake.failover_calls == 1
    assert [b["provider"] for b in recovered["branches"]] == ["claude", "codex"]
    j.close()


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
    path = tmp_path / "providers.toml"
    path.write_text('''fallback_order = ["agy-claude", "codex", "claude"]
[[providers]]
id = "agy-claude"
kind = "agy-shim"
base_url = "http://127.0.0.1:18795/v1"
model = "claude"
daily_cap = 2
[[providers]]
id = "codex"
kind = "codex-acp"
[[providers]]
id = "claude"
kind = "claude-acp"
''')
    path.chmod(0o600)
    catalog = ProviderCatalog.from_file(path)
    assert catalog.order == ("agy-claude", "codex", "claude")
    assert catalog.environment("codex", {})["GOOSE_PROVIDER"] == "chatgpt_codex"
    assert catalog.environment("claude", {})["GOOSE_PROVIDER"] == "claude-acp"
    assert classify_provider_error(status=429) == "rate_limited"
    assert classify_provider_error(code="insufficient_quota") == "quota_error"
    assert classify_provider_error(status=401) == "auth_error"
    assert classify_provider_error(code="unknown") is None
    path.chmod(0o644)
    with pytest.raises(ValueError, match="mode 0600"):
        ProviderCatalog.from_file(path)


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
        commands={"p": (sys.executable, "-c", "print('proof')")}, artifact_dir=str(artifacts)))
    task = {"task_id": "synthetic", "host": "local", "project": "p"}
    result = await runner.observe(task, str(repo))
    assert result and result["exit_code"] == 0
    assert result["output_sha256"] == hashlib.sha256(b"proof\n").hexdigest()
    assert result["candidate_commit"] == (await runner.identity(task, str(repo)))["candidate_commit"]
    assert os.stat(result["log_ref"]).st_mode & 0o777 == 0o600
    assert artifacts.stat().st_mode & 0o777 == 0o700
    (repo / "code.txt").write_text("dirty")
    assert await runner.observe(task, str(repo)) is None
