from __future__ import annotations

import pytest

from bat_agent_connector import channels, lifecycle, registry, triage
from bat_agent_connector.errors import BatError
from bat_agent_connector.relay import build_relay, parse_fanout, parse_status

NOW_MS = 1_790_000_000_000
TED = "幫我把登入頁改成支援 passkey，順便看一下\n  錯字   和 `code` 格式?!"


def msg(i, role, text):
    return {"id": f"r{i}", "role": role, "content": text, "timestamp": NOW_MS + i * 1000}


@pytest.mark.parametrize(
    "text,kind,detail",
    [
        ("done.\n\nBAT-STATUS: MILESTONE phase 7 grant IDs", "MILESTONE", "phase 7 grant IDs"),
        ("**BAT-STATUS: CONTINUE** wire the settings page", "CONTINUE", "wire the settings page"),
        ("需要你決定。\nBAT-STATUS: NEED-TED 要用哪個 OAuth app?", "NEED_HUMAN", "要用哪個 OAuth app?"),
        ("BAT-STATUS: need_human — pick a DB", "NEED_HUMAN", "pick a DB"),
        ("`BAT-STATUS: DONE`", "MILESTONE", ""),
        ("BAT-STATUS: CONTINUE a\n...\nBAT-STATUS: MILESTONE b", "MILESTONE", "b"),
    ],
)
def test_parse_status(text, kind, detail):
    st = parse_status(text)
    assert st["kind"] == kind and st["detail"] == detail


def test_parse_status_absent():
    assert parse_status("all good, committed abc1234") is None


def test_relay_is_verbatim_with_labeled_brief():
    brief = {"goal": "Add passkey login", "constraints": ["no new deps"], "acceptance": "tests pass"}
    t = build_relay(TED, host="host1", workspace="web", channel="host1-web", thread="passkey",
                    earlier=["先做後端"], brief=brief, human_name="Ted", relay_name="Hermes")
    begin = "----- BEGIN MESSAGE FROM TED (verbatim, unedited) -----\n"
    body = t.split(begin, 1)[1].split("\n----- END MESSAGE FROM TED -----", 1)[0]
    assert body == TED  # byte-for-byte
    assert "先做後端" in t and "#host1-web" in t and "host1/web" in t and "thread: passkey" in t
    brief_part = t.split("----- BEGIN HERMES BRIEF (Hermes's interpretation, not Ted's words) -----", 1)[1]
    assert "Goal: Add passkey login" in brief_part and "- no new deps" in brief_part
    assert t.index(begin) < t.index("HERMES BRIEF")  # original first, brief below
    assert "source of truth" in t and "INTERPRETATION:" in t and "BAT-STATUS: NEED-TED" in t
    assert "bat-fanout" not in t


def test_relay_fanout_request():
    t = build_relay("split this", host="h", workspace="w", request_fanout=True, max_items=3)
    assert "```bat-fanout" in t and "at most 3 items" in t and "BAT-STATUS: MILESTONE fan-out plan ready" in t
    assert "BAT-STATUS: NEED-HUMAN" in t


def test_parse_fanout():
    text = 'plan:\n```bat-fanout\n[{"title": "API", "prompt": "Do A\\nexactly", "area": ["api/"]},' \
           ' {"title": "UI", "prompt": "Do B", "files": "ui/"}]\n```\nBAT-STATUS: MILESTONE fan-out plan ready'
    p = parse_fanout(text, 4)
    assert [t["prompt"] for t in p["tasks"]] == ["Do A\nexactly", "Do B"]
    assert p["tasks"][0]["area"] == "api/" and p["tasks"][1]["area"] == "ui/"
    with pytest.raises(BatError, match="cap is 1"):
        parse_fanout(text, 1)
    with pytest.raises(BatError, match="no ```bat-fanout"):
        parse_fanout("nothing", 4)
    with pytest.raises(BatError, match="valid JSON"):
        parse_fanout("```bat-fanout\n[{oops\n```", 4)
    with pytest.raises(BatError, match="no prompt"):
        parse_fanout('```bat-fanout\n[{"title": "x"}]\n```', 4)


def test_triage_prefers_marker():
    msgs = [msg(0, "user", "go"), msg(1, "assistant", "Error: something failed\nBAT-STATUS: NEED-TED choose")]
    c = triage.classify_messages(msgs)
    assert c["state"] == "waiting_question" and c["source"] == "marker" and c["bat_status"]["kind"] == "NEED_HUMAN"
    msgs[-1] = msg(1, "assistant", "step 2 done\nBAT-STATUS: CONTINUE step 3")
    c = triage.classify_messages(msgs)
    assert c["state"] == "done_idle" and c["source"] == "marker"


async def test_relay_dry_run_targets_managed_session_never_a_bat_session(fleet_factory, mock):
    from bat_agent_connector import orchestrate

    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    d = await lifecycle.session_relay(f, "h1", TED, workspace="demo-project", dry_run=True)
    assert d["no_session"] and d["session_id"] is None  # Ted's BAT sessions are not relay targets
    r = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    d = await lifecycle.session_relay(f, "h1", TED, workspace="demo-project", dry_run=True, brief="goal: x")
    assert d["sent"] is False and TED in d["text"] and d["session_id"] == r["session_id"]
    s = await lifecycle.session_relay(f, "h1", TED, session_id=r["session_id"], confirm=True)
    assert s["sent"] is True
    await f.close()


async def test_relay_to_bat_session_starts_a_new_worktree_instead(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    n = await lifecycle.session_relay(f, "h1", TED, session_id="sess-claude-0001", confirm=True)
    assert n["sent"] is False and n["read_only"] and n["read_only_code"] == "MANUAL_READ_ONLY"
    s = await lifecycle.session_relay(f, "h1", TED, session_id="sess-claude-0001", confirm=True,
                                      start_if_missing=True)
    assert s["started"] and s["session_id"] != "sess-claude-0001"
    assert s["result"]["worktree_path"].startswith("/srv/demo/.bat-worktrees/")
    assert not any(i["params"].get("sessionId") == "sess-claude-0001" and i["channel"] in channels.WRITE_CHANNELS
                   for i in mock.invokes)
    await f.close()


async def test_relay_without_session(fleet_factory, mock, monkeypatch):
    async def none(*a, **k):
        return None

    monkeypatch.setattr(lifecycle, "main_session", none)
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0})
    d = await lifecycle.session_relay(f, "h1", TED, workspace="other", dry_run=True)
    assert d["no_session"] and d["session_id"] is None and TED in d["text"]
    n = await lifecycle.session_relay(f, "h1", TED, workspace="other", confirm=True)
    assert n["sent"] is False and n["no_session"]
    s = await lifecycle.session_relay(f, "h1", TED, workspace="other", confirm=True, start_if_missing=True)
    assert s["sent"] and s["started"] and s["session_id"]
    await f.close()


async def test_fanout_from_planner_starts_verbatim_and_cleans_planner(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, orchestrate_max_sessions=4,
                      safety={"write_min_interval_s": 0})
    p = await lifecycle.fanout_plan_session(f, "h1", "demo-project", "split the work", max_items=2, confirm=True)
    sid = p["session_id"]
    assert registry.get("h1", sid)["role"] == "planner"
    block = '```bat-fanout\n[{"title": "A", "prompt": "Exact prompt A"}, {"title": "B", "prompt": "Exact prompt B"}]\n```'
    mock.states[sid] = {"isStreaming": False, "messages": [
        msg(0, "user", "plan"), msg(1, "assistant", block + "\nBAT-STATUS: MILESTONE fan-out plan ready")]}
    d = await lifecycle.fanout_from_plan(f, "h1", sid, dry_run=True)
    assert [t["title"] for t in d["plan"]] == ["A", "B"]
    d = await lifecycle.fanout_from_plan(f, "h1", sid, confirm=True)
    assert len(d["started"]) == 2 and all("session_id" in x for x in d["started"])
    sent = [i["params"].get("prompt") or i["params"].get("text") or "" for i in mock.invokes
            if i["channel"] in ("claude:send-message", "claude:start-session")]
    assert any(x.startswith("Exact prompt A\n\n") for x in sent) and any(x.startswith("Exact prompt B") for x in sent)
    assert "agent stopped" in str(d["planner_cleanup"])
    await f.close()


@pytest.mark.parametrize(
    "line,decision",
    [("BAT-STATUS: CONTINUE step 3", "KEEP"), ("BAT-STATUS: NEED-TED which API key?", "ESCALATE")],
)
async def test_cleanup_respects_marker(fleet_factory, mock, line, decision):
    from tests.test_lifecycle import _finished_wt

    diff = "diff --git a/x.py b/x.py\n+++ b/x.py\n+print('x')\n"
    f = fleet_factory(writes=True, orchestrate=True, auto_cleanup=True, safety={"write_min_interval_s": 0})
    r = await _finished_wt(f, mock, "ahead", diff)
    mock.states[r["session_id"]]["messages"][-1] = msg(3, "assistant", f"Committed abc1234.\n{line}")
    d = await lifecycle.session_cleanup(f, "h1", dry_run=True)
    assert d["decisions"][0]["decision"] == decision
    await f.close()
