"""V2 §14 / B02, B05, T11: one journal, scoped checkpoints, replay and explicit resnapshot."""
from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from urllib.parse import urlencode

import pytest

from bat_agent_connector import api_auth, dashboard_sync
from bat_agent_connector.api_v1 import ApiV1
from bat_agent_connector.task_journal import Journal
from tests.test_api_v1 import daemon as api_daemon
from tests.test_api_v1 import http, token
from tests.test_api_v1 import served as api_served

daemon = api_daemon
served = api_served

VIEWER = api_auth.Principal("viewer", frozenset({"observe"}))


def append(j, value):
    return j.api_event("session", "h1/example-session", "session.updated", {"revision": value})


def replay(j, sync, principal=VIEWER, **kwargs):
    cp = sync["checkpoint"]
    return dashboard_sync.event_page(j, principal, cp["cursor"], token=cp["token"], **kwargs)


def test_b05_sync_identity_survives_restart_without_consuming_a_data_step(tmp_path):
    path = tmp_path / "journal.db"
    j = Journal(path)
    append(j, 1)
    first = dashboard_sync.checkpoint(j, VIEWER)
    j.db.execute("PRAGMA user_version=17")
    j.close()
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 17
    assert dashboard_sync.checkpoint(j, VIEWER) == first
    assert replay(j, first)["events"] == []
    j.close()


@pytest.mark.parametrize("change", ["actor", "scope", "admin", "foreign"])
def test_t11_sync_checkpoint_is_bound_to_journal_and_effective_principal(tmp_path, change):
    j = Journal(tmp_path / "one.db")
    first = dashboard_sync.checkpoint(j, VIEWER)
    principal = VIEWER
    if change == "foreign":
        j.close()
        j = Journal(tmp_path / "two.db")
    else:
        principal = api_auth.Principal("other" if change == "actor" else VIEWER.actor,
            frozenset({"observe", "operate"}) if change == "scope" else VIEWER.scopes, change == "admin")
    with pytest.raises(dashboard_sync.ResetRequired) as exc:
        replay(j, first, principal)
    assert exc.value.reason == ("server_changed" if change == "foreign" else "principal_changed")
    j.close()


def test_b02_restored_journal_detects_regression_and_divergent_reused_sequence(tmp_path):
    path, backup = tmp_path / "journal.db", tmp_path / "backup.db"
    j = Journal(path)
    append(j, 1)
    original = dashboard_sync.checkpoint(j, VIEWER)
    with sqlite3.connect(backup) as dest:
        j.db.backup(dest)
    append(j, 2)
    later = replay(j, original)["sync"]
    j.close()
    shutil.copyfile(backup, path)
    j = Journal(path)
    assert dashboard_sync.identity(j, VIEWER)["server_id"] == original["server_id"]
    with pytest.raises(dashboard_sync.ResetRequired, match="cursor_ahead"):
        replay(j, later)
    append(j, "restored and diverged")
    with pytest.raises(dashboard_sync.ResetRequired, match="history_changed"):
        replay(j, later)
    assert replay(j, original)["events"][0]["body"]["revision"] == "restored and diverged"
    j.close()


def test_b02_retention_keeps_head_and_explicitly_resets_expired_cursor(tmp_path):
    j = Journal(tmp_path / "journal.db")
    initial = dashboard_sync.checkpoint(j, VIEWER)
    for n in range(3):
        append(j, n)
    head = j.api_head()
    j.db.execute("DELETE FROM api_events")
    assert j.api_head() == head
    with pytest.raises(dashboard_sync.ResetRequired, match="cursor_expired"):
        replay(j, initial)
    fresh = dashboard_sync.checkpoint(j, VIEWER)
    assert fresh["retained_after"] == head and fresh["checkpoint"]["cursor"] == head
    assert replay(j, fresh)["events"] == []
    assert append(j, "next") > head
    assert len(replay(j, fresh)["events"]) == 1
    j.close()


def test_b02_pages_refresh_checkpoint_and_hidden_events_advance_without_shape_change(tmp_path):
    j = Journal(tmp_path / "journal.db")
    initial = dashboard_sync.checkpoint(j, VIEWER)
    append(j, 1)
    append(j, 2)
    j.api_event("system", "migration", "history.backfilled", {})
    first = replay(j, initial, limit=1)
    assert first["has_more"] and first["sync"]["checkpoint"]["cursor"] == first["next_cursor"]
    second = replay(j, first["sync"], limit=1)
    assert not second["has_more"] and second["next_cursor"] == j.api_head()
    assert second["sync"]["checkpoint"]["cursor"] == second["head_cursor"]
    legacy = dashboard_sync.event_page(j, VIEWER, j.api_head())
    assert legacy == {"events": [], "next_cursor": j.api_head(), "head_cursor": j.api_head(), "has_more": False}
    with pytest.raises(dashboard_sync.ResetRequired, match="checkpoint_cursor_mismatch"):
        dashboard_sync.event_page(j, VIEWER, first["next_cursor"], token=initial["checkpoint"]["token"])
    with pytest.raises(dashboard_sync.ResetRequired, match="checkpoint_invalid"):
        dashboard_sync.event_page(j, VIEWER, 0, token=initial["checkpoint"]["token"][:-5] + "wrong")
    j.close()


async def test_t11_bootstrap_auth_identity_and_checkpoint_before_snapshot_reads(served, monkeypatch):
    d, port = served
    viewer = token(d, "viewer", "observe")
    operator = token(d, "operator", "operate")
    assert (await http(port, "GET", "/api/v1/bootstrap"))[0] == 401
    assert (await http(port, "GET", "/api/v1/bootstrap", tok=operator))[0] == 403
    original = d.inventory.hosts_document
    captured = []

    def snapshot_with_change(**kwargs):
        captured.append(append(d.journal, "during snapshot"))
        return original(**kwargs)

    def no_live_calls(*args, **kwargs):
        pytest.fail("bootstrap must read persisted state without constructing a BAT client")

    monkeypatch.setattr(d.inventory, "hosts_document", snapshot_with_change)
    monkeypatch.setattr(d.fleet, "client", no_live_calls)
    monkeypatch.setattr(d.inventory.fleet, "client", no_live_calls)
    status, bootstrap = await http(port, "GET", "/api/v1/bootstrap", tok=viewer)
    assert status == 200, bootstrap
    cp = bootstrap["sync"]["checkpoint"]
    assert cp["cursor"] < captured[0]
    assert bootstrap["pagination"] == {"atomic": False, "session_order": "id"}
    assert set(bootstrap["snapshot"]) == {"hosts", "sessions", "projects", "work_items", "operations"}
    assert bootstrap["capabilities"]["identity"] == {key: bootstrap["sync"][key] for key in ("server_id", "principal_id")}
    status, page = await http(port, "GET", "/api/v1/events?" + urlencode({"after": cp["cursor"], "checkpoint": cp["token"]}), tok=viewer)
    assert status == 200 and any(e["seq"] == captured[0] for e in page["events"])
    assert page["sync"]["checkpoint"]["cursor"] == page["next_cursor"]
    other = token(d, "other", "observe")
    status, reset = await http(port, "GET", "/api/v1/events?" + urlencode({"after": cp["cursor"], "checkpoint": cp["token"]}), tok=other)
    assert status == 409 and reset["error"]["reason"] == "principal_changed"
    assert reset["error"]["resnapshot"] and reset["error"]["preserve_drafts"]
    assert viewer not in json.dumps(bootstrap)


async def test_b02_http_cursor_ahead_and_expired_are_explicit_resets(served):
    d, port = served
    viewer = token(d, "viewer", "observe")
    status, reset = await http(port, "GET", "/api/v1/events?after=1000", tok=viewer)
    assert status == 409 and reset["error"]["reason"] == "cursor_ahead"
    append(d.journal, 1)
    d.journal.db.execute("DELETE FROM api_events")
    status, reset = await http(port, "GET", "/api/v1/events?after=0", tok=viewer)
    assert status == 409 and reset["error"]["reason"] == "cursor_expired"
    status, invalid = await http(port, "GET", "/api/v1/events?after=-1", tok=viewer)
    assert status == 422 and invalid["error"]["code"] == "INVALID_REQUEST"


async def test_b02_sse_delivers_page_checkpoint_then_explicit_reset(served):
    d, port = served
    viewer = token(d, "viewer", "observe")
    _, bootstrap = await ApiV1(d).bootstrap(VIEWER)
    cp = bootstrap["sync"]["checkpoint"]
    seq = append(d.journal, 1)
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    path = "/api/v1/events/stream?" + urlencode({"after": cp["cursor"], "checkpoint": cp["token"]})
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {viewer}\r\n\r\n".encode())
    await writer.drain()
    try:
        assert b"200 OK" in await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        event = await asyncio.wait_for(reader.readuntil(b"\n\n"), 5)
        assert f"id: {seq}\n".encode() in event
        control = await asyncio.wait_for(reader.readuntil(b"\n\n"), 5)
        assert control.startswith(b"event: sync.checkpoint\n")
        sync = json.loads(control.split(b"data: ", 1)[1])
        assert sync["checkpoint"]["cursor"] == seq
        # A later unseen event is pruned while this stream is open.
        append(d.journal, 2)
        d.journal.db.execute("DELETE FROM api_events")
        reset = await asyncio.wait_for(reader.readuntil(b"\n\n"), 5)
        assert reset.startswith(b"event: sync.reset\n")
        assert json.loads(reset.split(b"data: ", 1)[1])["error"]["reason"] == "cursor_expired"
    finally:
        writer.close()
        await writer.wait_closed()
