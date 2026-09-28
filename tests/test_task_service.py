from __future__ import annotations

import asyncio
import json
import sys

import pytest

from bat_agent_connector import mcp_server
from bat_agent_connector.goose_acp import GooseACP, GooseConfig
from bat_agent_connector.model_router import ModelRouter, RouterConfig
from bat_agent_connector.task_core import TaskCoordinator
from bat_agent_connector.task_daemon import TaskDaemon
from bat_agent_connector.task_discord import DiscordPublisher
from bat_agent_connector.task_journal import Journal
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
        self.evidence = None
        self.failover_calls = 0
        self.interrupts = 0
        self.send_error = False
        self.active_sends = 0
        self.max_active_sends = 0

    async def start(self, task, *, role, agent):
        self.starts.append((role, agent))
        return "reviewer-0001" if role == "reviewer" else "lead-0001"

    async def send(self, task, session_id, text, message_id):
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        await asyncio.sleep(0)
        self.active_sends -= 1
        self.sends.append((session_id, text, message_id))
        if self.send_error:
            raise TimeoutError("lost response after possible acceptance")
        return {"accepted": True, "turn_marker": message_id}

    async def read(self, task, session_id, marker):
        return self.reads.get(session_id, {"turn_started": False, "turn_done": False})

    async def interrupt(self, task, session_id):
        self.interrupts += 1

    async def failover(self, task, session_id):
        self.failover_calls += 1
        return "codex-0001"

    async def verification(self, task):
        return self.evidence


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
    j.close()
    j = Journal(path)
    assert j.get(task["task_id"])["original_words"] == WORDS
    assert j.get(task["task_id"])["delivered"] is False
    assert j.get(task["task_id"])["time_to_deliver_s"] is None
    with pytest.raises(ValueError, match="invalid transition"):
        j.change(task["task_id"], "done")
    j.intervention(task["task_id"])
    assert j.get(task["task_id"])["ted_interventions"] == 1
    j.close()


async def test_timeout_no_resend_and_reconcile(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    fake.send_error = True
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["state"] == "uncertain"
    assert len(fake.sends) == 1
    await core.tick(task["task_id"])
    assert len(fake.sends) == 1
    # BAT's exact echo proves acceptance; recovery observes instead of resending.
    fake.reads["lead-0001"] = {"turn_started": True, "turn_done": False,
                                "turn_attribution": "exact_echo"}
    assert (await core.tick(task["task_id"]))["state"] == "running"
    assert len(fake.sends) == 1
    j.close()


async def test_rules_review_verification_failover_pause_and_writer(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j, interpretation="Hermes guessed the wrong feature")
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    assert fake.sends[0][1].count(WORDS) == 1
    assert "Hermes guessed the wrong feature" not in fake.sends[0][1]
    assert j.get(task["task_id"])["interpretation"] == "Hermes guessed the wrong feature"
    fake.reads["lead-0001"] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "working"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["continuations"] == 1
    await core.pause(task["task_id"], abort_current=True)
    assert fake.interrupts == 1
    before = len(fake.sends)
    await core.tick(task["task_id"])
    assert len(fake.sends) == before
    j.resume(task["task_id"])
    fake.reads["lead-0001"] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["state"] == "verifying"
    await core.tick(task["task_id"])
    assert not any(role == "reviewer" for role, _ in fake.starts)
    fake.evidence = {"candidate_commit": "abc1234", "exit_code": 0, "current": True,
                     "claude_quota_available": False}
    await core.tick(task["task_id"])
    assert ("reviewer", "codex") in fake.starts
    fake.reads["reviewer-0001"] = {"turn_done": True,
                                    "messages": [{"role": "assistant", "text": "REVIEW: REJECT needs tests"}]}
    await core.tick(task["task_id"])
    assert j.get(task["task_id"])["review_rejections"] == 1
    fake.reads["lead-0001"] = {"turn_started": True, "turn_done": True,
                                "messages": [{"role": "assistant", "text": "BAT-STATUS: MILESTONE"}]}
    await core.tick(task["task_id"])
    fake.evidence = {**fake.evidence, "candidate_commit": "def5678", "claude_quota_available": True}
    await core.tick(task["task_id"])
    assert ("reviewer", "claude") in fake.starts
    fake.reads["reviewer-0001"] = {"turn_done": True,
                                    "messages": [{"role": "assistant", "text": "REVIEW: PASS"}]}
    done = await core.tick(task["task_id"])
    assert done["state"] == "done" and done["delivered"]
    assert done["time_to_deliver_s"] is not None
    j.close()


async def test_failover_and_single_writer(tmp_path):
    j = Journal(tmp_path / "tasks.db")
    task = submit(j)
    fake = FakeBAT()
    core = TaskCoordinator(j, fake)
    await core.tick(task["task_id"])
    j.change(task["task_id"], "quota_limited")
    assert (await core.tick(task["task_id"]))["session_id"] == "codex-0001"
    assert fake.failover_calls == 1
    # Two sends to the same BAT session serialize in the daemon.
    current = j.get(task["task_id"])
    await asyncio.gather(core._send(current, "codex-0001", "a", "a"),
                         core._send(current, "codex-0001", "b", "b"))
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
    router = ModelRouter(j, FakeJev("status_relay", 0.9))
    assert (await router.choose(tid, "update", "status"))["provider"] == "agy-gemini-flash"
    router = ModelRouter(j, FakeJev("review", 0.4), RouterConfig(agy_claude_daily_cap=1))
    assert (await router.choose(tid, "review", "candidate"))["provider"] == "agy-claude"
    router.record_provider_result("agy-claude", "success")
    assert (await router.choose(tid, "review2", "candidate"))["provider"] == "codex-subscription"
    router = ModelRouter(j, FakeJev(None))
    assert (await router.choose(tid, "unknown", "?"))["provider"] == "codex-subscription"
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
    script.write_text('''import json, subprocess, sys
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
        p=subprocess.Popen([scoped[0]["command"],*scoped[0]["args"]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
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
    goose = GooseACP(GooseConfig(timeout_s=20))
    try:
        result = await goose.run_task(task, str(tmp_path), command=(sys.executable, "-u", str(script)))
        assert result["stop_reason"] == "end_turn"
        assert len(fake.sends) == 1 and fake.sends[0][1] == "check task"
    finally:
        server.close()
        await server.wait_closed()
        await daemon.fleet.close()
        daemon.journal.close()
