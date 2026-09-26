"""Core client: auth v2, pinning, allowlist, backpressure, reconnect, redaction."""

from __future__ import annotations

import asyncio
import json

import pytest

from bat_agent_connector import channels
from bat_agent_connector.client import BatClient
from bat_agent_connector.config import device_id
from bat_agent_connector.errors import AuthError, ChannelNotAllowed, FingerprintMismatch
from tests.conftest import make_config
from tests.mockbat import TOKEN


def client_for(mock, **kw):
    cfg = make_config(
        mock, **{k: v for k, v in kw.items() if k in ("writes", "orchestrate", "tabs", "fingerprint")}
    )
    return BatClient(cfg.host("h1"), device_id="dev-test")


async def test_auth_v2_and_ping(mock):
    async with client_for(mock) as c:
        assert c.auth_info["protocol"] == "bat-remote/v2"
        assert c.auth_info["serverVersion"] == "9.9.9"
        assert await c.ping() >= 0
    auth = mock.auth_frames[0]
    assert auth["protocols"] == ["bat-remote/v2"]
    assert auth["clientInfo"]["deviceId"] == "dev-test"


async def test_stable_device_id(isolated_dirs):
    a = device_id()
    b = device_id()
    assert a == b and a.startswith("batc-")


async def test_bad_token_is_rejected_and_not_leaked(mock, monkeypatch):
    monkeypatch.setenv("BATC_TEST_TOKEN", "wrong-token-value-xyz")
    c = client_for(mock)
    with pytest.raises(AuthError) as ei:
        await c.connect()
    assert "wrong-token-value-xyz" not in str(ei.value)


async def test_pinning_mismatch_rejected_before_auth(mock):
    c = client_for(mock, fingerprint="00" * 32)
    with pytest.raises(FingerprintMismatch):
        await c.connect()
    await asyncio.sleep(0.1)
    assert mock.auth_frames == []  # token never sent


async def test_legacy_downgrade_refused(mock):
    mock.protocol = "bat-remote/legacy-v1"
    with pytest.raises(AuthError):
        await client_for(mock).connect()


@pytest.mark.parametrize(
    "channel",
    [
        "claude:stop-session",
        "claude:reset-session",
        "pty:kill",
        "pty:write",
        "fs:delete-path",
        "fs:readFile",
        "settings:save",
        "workspace:save",
        "runtime:install",
        "app:install-update",
        "claude:account-switch",
        "agent:stop-session",
        "claude:cleanup-worktree",
        "made:up",
    ],
)
async def test_never_exposed_channels_blocked_even_with_all_tiers(mock, channel):
    async with client_for(mock, writes=True, orchestrate=True, tabs=True) as c:
        with pytest.raises(ChannelNotAllowed):
            await c.invoke(channel, {})
    assert channel not in mock.channels()


@pytest.mark.parametrize("channel", sorted(channels.WRITE_CHANNELS) + ["agent:send-message"])
async def test_write_channels_blocked_when_writes_disabled(mock, channel):
    async with client_for(mock) as c:
        with pytest.raises(ChannelNotAllowed):
            await c.invoke(channel, {"sessionId": "x"})
    assert mock.invokes == []


@pytest.mark.parametrize("channel", sorted(channels.ORCHESTRATE_CHANNELS))
async def test_orchestrate_channels_need_orchestrate_tier(mock, channel):
    async with client_for(mock, writes=True) as c:
        with pytest.raises(ChannelNotAllowed):
            await c.invoke(channel, {"sessionId": "x"})
    assert mock.invokes == []


async def test_write_allowed_when_enabled(mock):
    async with client_for(mock, writes=True) as c:
        r = await c.invoke(
            "agent:send-message", {"sessionId": "sess-claude-0001", "prompt": "hi", "clientMessageId": "m1"}
        )
    assert r["accepted"] is True
    assert mock.channels() == ["claude:send-message"]  # alias folded


def test_never_exposed_examples_are_not_allowlisted():
    allowed = channels.READ_CHANNELS | channels.WRITE_CHANNELS | channels.ORCHESTRATE_CHANNELS
    assert not (channels.NEVER_EXPOSED_EXAMPLES & allowed)


async def test_backpressure_reader_keeps_draining(mock):
    mock.flood_before_reply = 3000
    async with client_for(mock) as c:
        sub = c.subscribe(maxsize=100)  # never consumed
        r = await c.invoke("app:get-version", {})
        assert r == "9.9.9"
        assert sub.dropped >= 2900 and len(sub.queue) == 100
        assert c.events_seen >= 3000
        assert c.connected


async def test_reconnect_after_drop(mock):
    async with client_for(mock) as c:
        await c.invoke("app:get-version", {})
        await mock.drop_all()
        await asyncio.sleep(0.2)
        assert await c.invoke("app:get-version", {}) == "9.9.9"
    assert len(mock.auth_frames) == 2


async def test_frames_never_contain_token_after_auth(mock):
    async with client_for(mock) as c:
        await c.invoke("workspace:load", {"profileId": "default"})
    non_auth = [f for f in mock.frames if f.get("type") != "auth"]
    assert TOKEN not in json.dumps(non_auth)
