from __future__ import annotations

import pytest

from bat_agent_connector.config import parse_config
from bat_agent_connector.fleet import Fleet
from tests.mockbat import TOKEN, MockBat


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("BATC_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("BATC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("BATC_TEST_TOKEN", TOKEN)
    monkeypatch.delenv("BATC_DEVICE_ID", raising=False)
    yield tmp_path


@pytest.fixture
async def mock():
    m = MockBat()
    await m.start()
    yield m
    await m.stop()


def make_config(
    mock: MockBat, *, writes=False, orchestrate=False, tabs=False, fingerprint=None, safety=None, **host_extra
):
    host = {
        "url": mock.url,
        "fingerprint": fingerprint or mock.fingerprint,
        "token_ref": "env:BATC_TEST_TOKEN",
        "writes": writes,
        "orchestrate": orchestrate,
        "orchestrate_register_tabs": tabs,
        "orchestrate_max_sessions": 2,
        **host_extra,
    }
    return parse_config({"hosts": {"h1": host}, "safety": safety or {"write_min_interval_s": 60}})


@pytest.fixture
def fleet_factory(mock):
    fleets = []

    def make(**kw):
        read_only = kw.pop("read_only", False)
        f = Fleet(make_config(mock, **kw), read_only=read_only, idle_timeout=0, actor="test")
        fleets.append(f)
        return f

    yield make
