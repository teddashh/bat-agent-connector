from __future__ import annotations

import json

import pytest

from bat_agent_connector.config import parse_config, tomllib
from bat_agent_connector.errors import ConfigError
from bat_agent_connector.importer import read_bat_profiles, render_hosts_toml
from bat_agent_connector.mcp_server import (
    OPERATION_TOOLS,
    ORCHESTRATE_TOOLS,
    READ_TOOLS,
    WRITE_TOOLS,
    build_server,
)
from tests.conftest import make_config


async def _names(cfg, **kw):
    server, _ = build_server(cfg, **kw)
    return {t.name for t in await server.list_tools()}


async def test_tool_registration_tiers(mock):
    # Accepted start keys remain recoverable after a local host tier is disabled.
    # Current central authorization still decides whether a new key can start work.
    central = {"session_start", "session_relay", "work_continue_from_repository"}
    assert await _names(make_config(mock)) == set(READ_TOOLS + OPERATION_TOOLS) | central
    assert await _names(make_config(mock, writes=True)) == set(READ_TOOLS + OPERATION_TOOLS + WRITE_TOOLS) | central
    assert await _names(make_config(mock, writes=True, orchestrate=True)) == set(
        READ_TOOLS + OPERATION_TOOLS + WRITE_TOOLS + ORCHESTRATE_TOOLS
    ) | central
    assert await _names(make_config(mock, writes=True, orchestrate=True), read_only=True) == set(READ_TOOLS)


async def test_operation_tools_need_confirm_and_the_callers_own_token(mock, monkeypatch):
    server, fleet = build_server(make_config(mock))
    monkeypatch.delenv("BATC_API_TOKEN", raising=False)
    for args, needle in (({"operation_id": "op_" + "0" * 32}, "confirm=true"),
                         ({"operation_id": "op_" + "0" * 32, "confirm": True}, "BATC_API_TOKEN")):
        try:
            res = await server.call_tool("operation_cancel", args)
            text = json.dumps(res.model_dump() if hasattr(res, "model_dump") else res, default=str)
        except Exception as e:  # noqa: BLE001 - the server may raise the tool's refusal instead
            text = str(e)
        assert needle in text
    await fleet.close()


async def test_mcp_call_read_tool(mock):
    server, fleet = build_server(make_config(mock))
    res = await server.call_tool("sessions_list", {"host": "h1"})
    text = json.dumps(res.model_dump() if hasattr(res, "model_dump") else res, default=str)
    assert "sess-claude-0001" in text
    await fleet.close()


def test_config_rejects_inline_token_and_bad_tiers():
    base = {"url": "wss://127.0.0.1:1/", "fingerprint": "AA" * 32, "token_ref": "env:X"}
    with pytest.raises(ConfigError):
        parse_config({"hosts": {"a": {**base, "token": "abc"}}})
    with pytest.raises(ConfigError):
        parse_config({"hosts": {"a": {**base, "orchestrate": True}}})
    with pytest.raises(ConfigError):
        parse_config({"hosts": {"a": {**base, "url": "ws://x"}}})
    cfg = parse_config({"hosts": {"a": base}})
    assert "abc" not in repr(cfg.host("a"))


def test_importer_never_copies_tokens(tmp_path):
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    (pdir / "index.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {"id": "default", "type": "local"},
                    {
                        "id": "box-a",
                        "name": "Box A",
                        "type": "remote",
                        "remoteHost": "127.0.0.9",
                        "remotePort": 9009,
                        "remoteFingerprint": "AB:" * 31 + "AB",
                        "remoteProfileId": "default",
                    },
                ]
            }
        )
    )
    (pdir / "remote-tokens.enc.json").write_text(
        json.dumps({"enc": False, "data": json.dumps({"tokens": {"box-a": "SUPERSECRETTOKEN"}})})
    )
    text = render_hosts_toml(read_bat_profiles(pdir), profiles_dir=str(pdir), rename={"box-a": "a1"})
    assert "SUPERSECRETTOKEN" not in text and 'token_ref = "bat-profile:box-a"' in text
    cfg = parse_config(tomllib.loads(text))
    h = cfg.host("a1")
    assert h.writes is False and h.url == "wss://127.0.0.9:9009/"
    assert h.resolve_token() == "SUPERSECRETTOKEN"
