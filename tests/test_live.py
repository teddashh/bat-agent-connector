"""Live READ-ONLY integration test against real BAT hosts.

Runs only with BATC_LIVE=1. Uses the real config (BATC_LIVE_CONFIG or
~/.config/bat-agent-connector/hosts.toml) and the real, stable deviceId.
The fleet is forced read-only and every channel sent is checked to be a read channel.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bat_agent_connector import channels, orchestrate, service
from bat_agent_connector.client import BatClient
from bat_agent_connector.config import load_config
from bat_agent_connector.fleet import Fleet

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("BATC_LIVE") != "1", reason="set BATC_LIVE=1")]

REAL_CFG_DIR = Path(os.environ.get("BATC_LIVE_CONFIG_DIR", "~/.config/bat-agent-connector")).expanduser()
REPORT = os.environ.get("BATC_LIVE_REPORT")


@pytest.fixture
def live_fleet(monkeypatch):
    monkeypatch.setenv("BATC_CONFIG_DIR", str(REAL_CFG_DIR))  # real, stable deviceId
    sent: list[str] = []
    orig = BatClient._invoke_checked

    async def spy(self, canonical, params, timeout):
        assert canonical in channels.READ_CHANNELS, f"non-read channel attempted live: {canonical}"
        sent.append(canonical)
        return await orig(self, canonical, params, timeout)

    monkeypatch.setattr(BatClient, "_invoke_checked", spy)
    cfg = load_config(os.environ.get("BATC_LIVE_CONFIG") or REAL_CFG_DIR / "hosts.toml")
    f = Fleet(cfg, read_only=True, idle_timeout=0, actor="live-test")
    assert not f.any_writes
    yield f, sent


async def test_live_read_only_all_hosts(live_fleet):
    f, sent = live_fleet
    report: dict = {}
    hl = await service.hosts_list(f)
    assert hl["read_only"] is True
    for h in hl["hosts"]:
        assert h["reachable"], h
        report[h["name"]] = {"version": h["server_version"], "ping_ms": h["ping_ms"]}
    for name in f.config.hosts:
        st = await service.host_status(f, name)
        ws = await service.workspaces_list(f, name)
        ss = await service.sessions_list(f, name, limit=500)
        assert not ws["errors"] and not ss["errors"]
        idle = [s for s in ss["sessions"] if s["loaded"] and not s["streaming"] and not s["pending"]] or [
            s for s in ss["sessions"] if not s["streaming"]
        ]
        rd = None
        if idle:
            rd = await service.session_read(f, name, idle[0]["session_id"], last_n=5, max_chars=4000)
            assert rd["session_id"] == idle[0]["session_id"]
        wt = await orchestrate.worktree_status(f, name)
        report[name].update(
            workspaces=st["workspaces"], terminals=st["terminals"], agent_sessions=st["agent_sessions"],
            loaded=st["loaded"], streaming=st["streaming"], sessions_listed=ss["count"],
            ping_median_ms=st["latency"]["ping_median_ms"], read_session=(idle[0]["session_id"][:8] if idle else None),
            read_messages=(len(rd["messages"]) if rd else 0), worktrees=wt["count"],
        )
    await f.close()
    assert sent and all(c in channels.READ_CHANNELS for c in sent)
    report["_channels_used"] = sorted(set(sent))
    if REPORT:
        Path(REPORT).write_text(json.dumps(report, indent=1))
