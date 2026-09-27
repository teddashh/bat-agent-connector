"""Turn markers: a send/relay returns turn_marker; session_wait/session_read(after=...) ignore older output."""

from __future__ import annotations

import asyncio

import pytest

from bat_agent_connector import lifecycle, service
from bat_agent_connector.errors import BatError

SID = "sess-claude-0001"


def test_marker_ms_parsing():
    assert service.marker_ms(None) is None
    assert service.marker_ms("user-1790486096680") == 1790486096680
    assert service.marker_ms("1790486096680") == 1790486096680
    assert service.marker_ms(1790486096680) == 1790486096680
    assert service.marker_ms("2026-09-27T01:14:56+00:00") == 1790471696000
    with pytest.raises(BatError):
        service.marker_ms("not-a-marker")


async def test_send_returns_marker_and_read_hides_previous_turn(fleet_factory, mock):
    mock.echo_sends = True
    f = fleet_factory(writes=True)
    r = await service.session_send(f, "h1", SID, "four new requests", confirm=True)
    assert r["marker_source"] == "sent_message"
    assert r["turn_marker"].startswith("user-") and r["after_ms"]

    # right after the send: idle, no reply yet -> the previous turn's messages must not come back
    rd = await service.session_read(f, "h1", SID, after=r["turn_marker"])
    assert rd["messages"] == [] and rd["turn_started"] is False and rd["turn_done"] is False
    assert "do NOT report" in rd["note"]
    plain = await service.session_read(f, "h1", SID, last_n=3)
    assert any("live message" in (m["text"] or "") for m in plain["messages"])  # old behaviour unchanged

    # the session answers the new turn
    mock.states[SID]["messages"].append(
        {"id": "new-1", "role": "assistant", "content": "working on the 4 items", "timestamp": r["after_ms"] + 5}
    )
    rd = await service.session_read(f, "h1", SID, after=r["turn_marker"])
    assert [m["text"] for m in rd["messages"]] == ["working on the 4 items"]
    assert rd["turn_done"] is True
    await f.close()


async def test_wait_after_ignores_stale_idle_then_returns_on_reply(fleet_factory, mock):
    mock.echo_sends = True
    f = fleet_factory(writes=True)
    r = await service.session_send(f, "h1", SID, "new task", confirm=True)
    marker = r["turn_marker"]

    # stale idle: the session has not replied after the marker -> must NOT return "idle"
    w = await service.session_wait(f, "h1", SID, timeout_s=1, after=marker)
    assert w["status"] == "timeout" and w["turn_started"] is False and "not started" in w["note"]

    async def answer():
        await asyncio.sleep(0.3)
        mock.metas[SID]["isStreaming"] = True
        await mock.broadcast("agent:turn-end", {"sessionId": SID})  # an older turn ending: still streaming
        await asyncio.sleep(0.3)
        mock.states[SID]["messages"].append(
            {"id": "new-2", "role": "assistant", "content": "done", "timestamp": r["after_ms"] + 10}
        )
        mock.metas[SID]["isStreaming"] = False
        await mock.broadcast("agent:turn-end", {"sessionId": SID})

    t = asyncio.create_task(answer())
    w = await service.session_wait(f, "h1", SID, timeout_s=5, after=marker)
    await t
    assert w["status"] == "event" and w["event"] == "agent:turn-end" and w["turn_done"] is True

    # already answered -> returns at once
    w = await service.session_wait(f, "h1", SID, timeout_s=5, after=marker)
    assert w["status"] == "done" and w["elapsed_s"] < 2
    await f.close()


async def test_marker_fallback_without_echo(fleet_factory, mock):
    f = fleet_factory(writes=True)  # mock does not echo the prompt
    r = await service.session_send(f, "h1", SID, "x", confirm=True)
    assert r["marker_source"] == "last_message_before_send"
    assert r["after_ms"] == 1_790_000_020_000  # newest message before the send (host clock)
    await f.close()


async def test_relay_surfaces_marker(fleet_factory, mock):
    mock.echo_sends = True
    f = fleet_factory(writes=True)
    r = await lifecycle.session_relay(f, "h1", session_id=SID, message="1. fix chat\n2. mobile", confirm=True)
    assert r["sent"] is True and r["turn_marker"].startswith("user-")
    assert f'after="{r["turn_marker"]}"' in r["next"]
    await f.close()
