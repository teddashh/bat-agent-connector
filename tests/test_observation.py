"""計畫 §08/§11/§19, B01/B02/B03: server observation contracts and read-only evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import replace

import pytest

from bat_agent_connector import api_auth, cli, mcp_server, registry
from bat_agent_connector.inventory import Inventory
from bat_agent_connector.observation import (
    Observation,
    bind_worktree,
    dump,
    index,
    remember,
    saved_fact,
    worktree,
)
from bat_agent_connector.operations import OperationError
from bat_agent_connector.resource_ids import worktree_id
from bat_agent_connector.task_journal import Journal
from tests.conftest import adopt, make_config
from tests.test_api_v1 import (  # noqa: F401 - shared fixtures
    MANUAL,
    http,
    token,
    write_frames,
)
from tests.test_api_v1 import (
    daemon as _daemon,
)
from tests.test_api_v1 import (
    served as _served,
)

daemon = _daemon
served = _served


def task(j, key, **kw):
    return j.submit(project="p", host="h1", workspace="w", original_words="private request", idempotency_key=key, **kw)


def bind(j, t, sid, role="lead", reason="start"):
    c, _ = j.command(t["task_id"], "start_" + role, sid, {"agent": "codex"}, t["task_id"] + ":" + role + ":" + sid)
    j.command_status(c["command_id"], "settled")
    j.add_branch(t["task_id"], session_id=sid, provider="codex", role=role, reason=reason)
    return c


async def test_projection_failure_keeps_core_write_and_flags_event(tmp_path, monkeypatch, caplog):
    """B01/B03, §08/§11: a broken read projection cannot fail a task or an operation step."""
    from bat_agent_connector import observation
    from bat_agent_connector.operations import ActionDef, OperationService

    j = Journal(tmp_path / "j.db")
    t = task(j, "projection")
    original = observation.record_event
    failed = []

    def fail(journal, seq, **kwargs):
        original(journal, seq, **kwargs)
        kind = journal.db.execute("SELECT kind FROM api_events WHERE seq=?", (seq,)).fetchone()[0]
        if kind in {"task.state", "operation.step.started"}:
            # Include nested relation events and resource/revision rows in the partial projection.
            observation.relation(journal, t, "partial", "lead", str(seq), seq)
            failed.append(seq)
            raise KeyError("private exception text")

    monkeypatch.setattr(observation, "record_event", fail)
    j.change(t["task_id"], "dispatching")
    assert j.get(t["task_id"])["state"] == "dispatching"
    calls = []

    async def run(ctx):
        async def call():
            calls.append("ran")
            return {"status": "succeeded"}
        return await ctx.step("call", call)

    ops = OperationService(j, actions=[ActionDef("fixture.projection", "observe", "Fixture only", run)])
    principal = api_auth.Principal("agent", frozenset({"observe"}))
    op, _ = ops.create(principal, action="fixture.projection", target={"host": "h1", "session_id": "sid"}, idempotency_key="projection")
    await ops.drain()
    assert calls == ["ran"] and ops.get(op["operation_id"])["status"] == "succeeded"
    assert j.db.execute("SELECT status FROM operation_steps WHERE operation_id=?", (op["operation_id"],)).fetchone()[0] == "succeeded"
    assert len(failed) == 2
    for seq in failed:
        assert j.db.execute("SELECT COUNT(*) FROM api_event_resources WHERE seq=?", (seq,)).fetchone()[0] == 0
        assert j.db.execute("SELECT COUNT(*) FROM relation_revisions WHERE seq=?", (seq,)).fetchone()[0] == 0
    assert j.db.execute("SELECT COUNT(*) FROM observation_relations WHERE session_resource_id='h1/partial'").fetchone()[0] == 0
    assert j.db.execute("SELECT COUNT(*) FROM observation_resources WHERE resource_id='h1/partial'").fetchone()[0] == 0
    events = {e["seq"]: e for e in j.api_events()["events"]}
    obs = Observation(j)
    history = obs.history("execution", t["task_id"])["events"] + obs.history("session", "h1/sid")["events"]
    assert set(failed) <= {e["seq"] for e in history}
    assert all(events[seq]["context"] == {"projection_error": "KeyError"} for seq in failed)
    assert all(e["context"] == {"projection_error": "KeyError"} for e in history if e["seq"] in failed)
    assert "private exception text" not in caplog.text
    assert caplog.text.count("observation projection failed") == 2
    j.close()


def test_b01_warm_reuse_reviewer_followup_and_command_ranges(tmp_path):
    j = Journal(tmp_path / "j.db")
    obs = Observation(j)
    a = task(j, "a")
    first = bind(j, a, "shared")
    bind(j, a, "review", "reviewer")
    j.change(a["task_id"], "failed")
    b = task(j, "b", parent_task_id=a["task_id"], continuation=True)
    second = bind(j, b, "shared", reason="warm_reuse")
    bind(j, b, "replacement", reason="replacement")
    rels = obs.relations("session", "h1/shared")["relations"]
    assert len(rels) == 2 and {r["execution_id"] for r in rels} == {a["task_id"], b["task_id"]}
    assert all(r["status"] == "closed" and r["end_seq"] > r["start_seq"] for r in rels)
    assert rels[0]["start_command_id"] == first["command_id"]
    assert rels[1]["command_ids"] == [second["command_id"]]
    assert rels[1]["follow_up_of_execution_id"] == a["task_id"]
    execution = obs.relations("execution", a["task_id"])["relations"]
    assert {r["role"] for r in execution} == {"lead", "reviewer"}
    assert len({r["relation_id"] for r in execution}) == 2
    j.close()


def test_b01_pending_bind_and_snapshot_relations(tmp_path):
    j = Journal(tmp_path / "j.db")
    t = task(j, "a")
    c, _ = j.command(t["task_id"], "start_lead", None, {}, "start")
    j.command_bind_session(c["command_id"], "sid")
    pending = Observation(j).relations("session", "h1/sid")["relations"][0]
    assert pending["status"] == "pending"
    j.command_status(c["command_id"], "settled")
    bound = Observation(j).relations("session", "h1/sid")["relations"][0]
    assert bound["status"] == "bound" and bound["relation_id"] == pending["relation_id"]
    j.add_branch(t["task_id"], session_id="review", provider="codex", role="reviewer", reason="start")
    page = Observation(j).relations("execution", t["task_id"], limit=1)
    j.change(t["task_id"], "failed")
    tail = Observation(j).relations("execution", t["task_id"], limit=1, cursor=page["next_cursor"])
    assert tail["as_of"] == page["as_of"] and tail["relations"][0]["status"] == "bound"
    j.close()


def relation_pages(obs, wid, first=None):
    page = first or obs.relations("worktree", wid, limit=1)
    rows, as_of = list(page["relations"]), page["as_of"]
    while page["next_cursor"]:
        page = obs.relations("worktree", wid, limit=1, cursor=page["next_cursor"])
        assert page["as_of"] == as_of
        rows.extend(page["relations"])
    assert len(rows) == len({r["relation_id"] for r in rows})
    return rows


def test_b01_worktree_relations_exclude_late_bindings_from_existing_cursor(tmp_path):
    """B01, §08/§10: a binding added after page one cannot change its remaining pages."""
    j = Journal(tmp_path / "j.db")
    with j.tx():
        wid = worktree(j, "h1", "registry", "root@123", "worktree", session_id="early-a")
        bind_worktree(j, "h1/early-b", wid)
    for sid in ("early-a", "early-b", "late"):
        bind(j, task(j, sid), sid)
    obs = Observation(j)
    first = obs.relations("worktree", wid, limit=1)
    assert first["has_more"]
    history = obs.history("worktree", wid, limit=1)
    with j.tx():
        bind_worktree(j, "h1/late", wid)
    assert j.api_head() > first["as_of"]
    old = relation_pages(obs, wid, first)
    assert {r["session_resource_id"] for r in old} == {"h1/early-a", "h1/early-b"}
    assert {r["session_resource_id"] for r in relation_pages(obs, wid)} == {"h1/early-a", "h1/early-b", "h1/late"}
    # Current identity metadata is allowed to change; history membership stays bounded by link seq.
    while history["next_cursor"]:
        history = obs.history("worktree", wid, limit=1, cursor=history["next_cursor"])
        assert all("h1/late" not in e["context"].get("session_resource_ids", []) for e in history["events"])
    j.close()


def test_b01_worktree_moves_preserve_relation_ranges_across_pages(tmp_path):
    """B01/B03, §08/§10: a move clips participation, retaining the old worktree's ranges."""
    j = Journal(tmp_path / "j.db")
    obs = Observation(j)
    with j.tx():
        a = worktree(j, "h1", "registry", "root@123", "worktree", session_id="shared")
        b = worktree(j, "h1", "checkpoint.continue", "new", "worktree")
    previous = []
    for key in ("past-a", "past-b"):
        t = task(j, key)
        c = bind(j, t, "shared")
        previous.append((t, c))
        j.change(t["task_id"], "failed")
    ongoing = task(j, "ongoing")
    before = bind(j, ongoing, "shared")
    j.change(ongoing["task_id"], "dispatching")
    first = obs.relations("worktree", a, limit=1)
    with j.tx():
        bind_worktree(j, "h1/shared", b)
    move_seq = j.api_head()
    after, _ = j.command(ongoing["task_id"], "send", "shared", {}, "after-move")
    j.command_status(after["command_id"], "settled")
    new = task(j, "only-b")
    newest = bind(j, new, "shared")
    old_snapshot = relation_pages(obs, a, first)
    assert old_snapshot[-1]["worktree_ranges"][0]["end_seq"] is None
    assert old_snapshot[-1]["command_ids"] == [before["command_id"]]
    on_a = {r["execution_id"]: r for r in relation_pages(obs, a)}
    on_b = {r["execution_id"]: r for r in relation_pages(obs, b)}
    assert set(on_a) == {t["task_id"] for t, _ in previous} | {ongoing["task_id"]}
    assert set(on_b) == {ongoing["task_id"], new["task_id"]}
    for t, c in previous:
        assert on_a[t["task_id"]]["command_ids"] == [c["command_id"]]
    assert on_a[ongoing["task_id"]]["command_ids"] == [before["command_id"]]
    assert on_a[ongoing["task_id"]]["worktree_ranges"][0]["end_seq"] == move_seq
    assert on_b[ongoing["task_id"]]["command_ids"] == [after["command_id"]]
    assert on_b[ongoing["task_id"]]["worktree_ranges"][0]["start_seq"] == move_seq
    assert on_b[new["task_id"]]["command_ids"] == [newest["command_id"]]
    # A stale creation receipt must not move a session back to the old worktree.
    with j.tx():
        seq = j.api_event("session", "h1/shared", "fixture.receipt", {})
        worktree(j, "h1", "registry", "root@123", "worktree", session_id="shared", seq=seq)
    assert obs.resource("session", "h1/shared")["worktree_id"] == b
    assert all(e["kind"] != "fixture.receipt" for e in obs.history("worktree", a)["events"])
    # Re-entry adds another range to one relation, rather than another copy of that relation.
    with j.tx():
        bind_worktree(j, "h1/shared", a)
    return_seq = j.api_head()
    returned, _ = j.command(ongoing["task_id"], "send", "shared", {}, "return")
    j.command_status(returned["command_id"], "settled")
    returning = next(r for r in relation_pages(obs, a) if r["execution_id"] == ongoing["task_id"])
    assert [r["start_seq"] for r in returning["worktree_ranges"]] == [returning["start_seq"], return_seq]
    assert returning["command_ids"] == [before["command_id"], returned["command_id"]]
    assert Observation(j).relations("execution", ongoing["task_id"])["relations"][0]["command_ids"] == [before["command_id"], after["command_id"], returned["command_id"]]
    j.close()


def test_b03_worktree_binding_projection_failure_preserves_core_event(tmp_path, monkeypatch, caplog):
    """B03, §08/§11: a partially projected move rolls back without losing its core event."""
    from bat_agent_connector import observation
    j = Journal(tmp_path / "j.db")
    with j.tx():
        a = worktree(j, "h1", "registry", "root@123", "worktree", session_id="sid")
        b = worktree(j, "h1", "checkpoint.continue", "new", "worktree")
    before = [tuple(r) for r in j.db.execute("SELECT * FROM session_worktree_bindings")]
    original = observation.record_event

    def fail(journal, seq, **kwargs):
        original(journal, seq, **kwargs)
        raise KeyError("private projection text")

    monkeypatch.setattr(observation, "record_event", fail)
    with j.tx():
        bind_worktree(j, "h1/sid", b)
    seq = j.api_head()
    assert before == [tuple(r) for r in j.db.execute("SELECT * FROM session_worktree_bindings")]
    assert Observation(j).resource("session", "h1/sid")["worktree_id"] == a
    assert j.db.execute("SELECT COUNT(*) FROM api_event_resources WHERE seq=?", (seq,)).fetchone()[0] == 0
    assert j.db.execute("SELECT COUNT(*) FROM relation_revisions").fetchone()[0] == 0
    e = Observation(j).history("session", "h1/sid")["events"][0]
    assert e["seq"] == seq and e["context"] == {"projection_error": "KeyError"}
    assert "private projection text" not in caplog.text
    j.close()


def test_b03_worktree_binding_backfill_matches_live_and_reopens_without_writes(tmp_path, monkeypatch):
    """B01/B03, §08/§11: step 2 seeds proven binding seqs, preserving live command participation."""
    from bat_agent_connector import observation
    from bat_agent_connector.operations import ActionDef, OperationService

    async def never_run(ctx):
        raise AssertionError("read-model fixture must not execute operations")

    def populate(j):
        ops = OperationService(j, actions=[ActionDef("checkpoint.continue", "observe", "Fixture only", never_run)])
        principal = api_auth.Principal("fixture", frozenset({"observe"}))
        op, _ = ops.create(principal, action="checkpoint.continue", target={"host": "h1"}, idempotency_key="creation")
        ops._merge_refs(op["operation_id"], {"host": "h1", "session_id": "shared", "worktree_path": "/srv/wt"})
        binding_seq = j.api_head()
        t = task(j, "past")
        bind(j, t, "shared")
        j.change(t["task_id"], "failed")
        bind(j, task(j, "current"), "shared")
        return worktree_id("h1", "checkpoint.continue", op["operation_id"], "worktree"), binding_seq

    def participation(j, wid):
        return [(j.get(r["execution_id"])["idem_key"], r["status"],
                 [j.command_get(cid)["kind"] for cid in r["command_ids"]]) for r in relation_pages(Observation(j), wid)]

    live = Journal(tmp_path / "live.db")
    live_wid, live_seq = populate(live)
    assert live.db.execute("SELECT start_seq FROM session_worktree_bindings").fetchone()[0] == live_seq
    expected = participation(live, live_wid)
    path = tmp_path / "legacy.db"
    with monkeypatch.context() as legacy:
        legacy.setattr(observation, "install", lambda journal: None)
        j = Journal(path)
    wid, seq = populate(j)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 1
    j.close()
    original = observation.backfill
    calls = []

    def capture(journal):
        calls.append(True)
        original(journal)

    monkeypatch.setattr(observation, "backfill", capture)
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    binding = j.db.execute("SELECT * FROM session_worktree_bindings").fetchone()
    assert binding["start_seq"] == binding["linked_at_seq"] == seq
    assert binding["evidence_ref"] == f"api_events:{seq}"
    assert participation(j, wid) == expected
    # Command ownership is proven; an old relation's exact start still stays unknown.
    assert all(r["start_seq"] is None for r in relation_pages(Observation(j), wid))
    tables = ("session_worktree_bindings", "relation_revisions", "api_event_resources", "observation_backfill")
    saved = {table: [tuple(r) for r in j.db.execute(f"SELECT * FROM {table}")] for table in tables}
    head = j.api_head()
    j.close()
    j = Journal(path)
    assert calls == [True] and j.api_head() == head and j.db.total_changes == 0
    assert saved == {table: [tuple(r) for r in j.db.execute(f"SELECT * FROM {table}")] for table in tables}
    assert participation(j, wid) == expected
    j.close()
    live.close()


def test_b03_saved_worktree_binding_uses_backfill_link_seq_without_inventing_earlier_range(tmp_path):
    """B03, §08: a saved current pointer alone does not prove an earlier worktree assignment."""
    path = tmp_path / "j.db"
    j = Journal(path)
    past = task(j, "past")
    bind(j, past, "sid")
    j.change(past["task_id"], "failed")
    current = task(j, "current")
    bind(j, current, "sid")
    with j.tx():
        wid = worktree(j, "h1", "registry", "root@123", "worktree")
        remember(j.db, "session", "h1/sid", worktree_id=wid)
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    binding = j.db.execute("SELECT * FROM session_worktree_bindings").fetchone()
    seed = j.db.execute("SELECT seq FROM observation_backfill WHERE source_key='session_worktree_bindings:h1/sid'").fetchone()[0]
    assert binding["start_seq"] == binding["linked_at_seq"] == seed
    assert j.db.execute("SELECT linked_at_seq FROM api_event_resources WHERE seq=? AND resource_type='session'", (seed,)).fetchone()[0] == seed
    rows = relation_pages(Observation(j), wid)
    assert [r["execution_id"] for r in rows] == [current["task_id"]]
    assert rows[0]["command_ids"] == []  # Their earlier commands have no proven worktree binding.
    assert rows[0]["worktree_ranges"][0]["start_seq"] == seed
    assert {e["seq"] for e in Observation(j).history("worktree", wid)["events"]} == {seed}
    head = j.api_head()
    j.close()
    j = Journal(path)
    assert j.api_head() == head and j.db.total_changes == 0
    j.close()


def test_b01_id_paging_complete_and_filter_changes_via_events(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    rows = [{"session_id": f"sid-{n:03}", "agent_kind": "codex", "has_tab": n % 2 == 0,
             "provenance": "unknown", "api_access": "read_only"} for n in range(205)]
    inv._record_success("h1", time.time(), rows, "v-test")
    cursor, ids = None, []
    while True:
        page = inv.list_sessions(order="id", limit=13, cursor=cursor)
        ids += [s["resource_id"] for s in page["sessions"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(ids) == 205 == len(set(ids)) and ids == sorted(ids)
    first = inv.list_sessions(order="id", has_tab=False, limit=1)
    rows[0]["has_tab"] = False
    inv._record_success("h1", time.time(), rows, "v-test")
    changes = j.api_events(first["as_of"])["events"]
    assert any(e["kind"] == "session.updated" and e["resource_id"] == "h1/sid-000" for e in changes)
    with pytest.raises(ValueError):
        inv.list_sessions(order="id", cursor=first["next_cursor"], has_tab=True)
    tables = {r[0] for r in j.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "observation_revisions" not in tables and "discovery_scans" not in tables
    j.close()


def test_b01_history_as_of_late_binding_and_invalid_cursors(tmp_path):
    j = Journal(tmp_path / "j.db")
    with j.tx():
        a = j.api_event("session", "h1/sid", "session.added", {})
        old = j.api_event("operation", "old", "operation.accepted", {})
        j.api_event("session", "h1/sid", "session.updated", {})
    obs = Observation(j)
    page = obs.history("session", "h1/sid", limit=1)
    with j.tx():
        bound = j.api_event("session", "h1/sid", "resource.bound", {})
        index(j.db, old, "session", "h1/sid", bound)
    tail = obs.history("session", "h1/sid", limit=1, cursor=page["next_cursor"])
    assert [e["seq"] for e in tail["events"]] == [a]
    assert old in [e["seq"] for e in obs.history("session", "h1/sid")["events"]]
    for kw in ({"cursor": "bad"}, {"limit": 0}, {"limit": True}, {"order": "time"}, {"since": float("nan")},
               {"cursor": page["next_cursor"], "order": "asc"}):
        with pytest.raises(OperationError):
            obs.history("session", "h1/sid", **kw)
    j.close()


def test_b01_worktree_shared_creation_identity_and_reuse(mock, tmp_path):
    from bat_agent_connector.observation import registry_bindings
    j = Journal(tmp_path / "j.db")
    raw = json.dumps(["worktree", "h1", "task", "t", "external_worktree"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert worktree_id("h1", "task", "t", "external_worktree") == "wt_" + hashlib.sha256(raw.encode()).hexdigest()[:32]
    entries = [{"session_id": "original", "created_at": 123.456, "worktree_path": "/srv/wt"},
               {"session_id": "review", "created_at": 124.0, "worktree_path": "/srv/wt", "lead_session_id": "original"},
               {"session_id": "successor", "created_at": 125.0, "worktree_path": "/srv/wt", "failover_of": "original"}]
    registry_bindings(j, "h1", entries)
    ids = {Observation(j).resource("session", f"h1/{e['session_id']}")["worktree_id"] for e in entries}
    assert ids == {worktree_id("h1", "registry", "original@123.456", "worktree")}
    entries[0]["task_id"] = "new-task"
    registry_bindings(j, "h1", list(reversed(entries)))
    assert Observation(j).resource("session", "h1/original")["worktree_id"] in ids
    with j.tx():
        newer = worktree(j, "h1", "checkpoint.continue", "another", "worktree", path="/srv/wt")
    assert newer not in ids
    j.close()


def test_b01_relation_scope_and_cross_project_link_history(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    t = task(j, "a")
    bind(j, t, "sid")
    # Use the existing work-item operation writer, with no provider call.
    from bat_agent_connector import work_items
    from bat_agent_connector.operations import OperationService
    ops = OperationService(j, actions=work_items.ACTIONS)
    ops.context["fleet"] = inv.fleet
    principal = api_auth.Principal("agent", frozenset({"observe", "manage"}))
    async def create():
        p, _ = ops.create(principal, action="project.create", params={"name": "P"}, idempotency_key="p")
        await ops.drain()
        pid = ops.get(p["operation_id"])["result"]["project_id"]
        w, _ = ops.create(principal, action="work_item.create", target={"project_id": pid}, params={"title": "W", "request": "private", "acceptance": "checked"}, idempotency_key="w")
        await ops.drain()
        wid = ops.get(w["operation_id"])["result"]["work_item_id"]
        link, _ = ops.create(principal, action="work_item.link", target={"work_item_id": wid}, params={"kind": "task", "ref": t["task_id"]}, idempotency_key="l")
        await ops.drain()
        assert ops.get(link["operation_id"])["status"] == "succeeded"
        unlink, _ = ops.create(principal, action="work_item.link", target={"work_item_id": wid}, params={"kind": "task", "ref": t["task_id"], "remove": True}, idempotency_key="u")
        await ops.drain()
        assert ops.get(unlink["operation_id"])["status"] == "succeeded"
        return pid, wid
    pid, wid = asyncio.run(create())
    assert inv.list_sessions(order="id", project_id=[pid], work_item_id=wid)["count"] == 1
    assert inv.list_sessions(order="id", project_id=[pid], relation_scope="current")["count"] == 0
    history = Observation(j).history("session", "h1/sid")["events"]
    links = [e for e in history if e["kind"] in {"work_item.linked", "work_item.unlinked"}]
    assert len(links) == 2 and all(e["body"]["link_id"] and e["context"]["work_item_ids"] == [wid] for e in links)
    assert links[0]["context"]["actor"] == "agent"
    assert "private" not in dump(history)
    j.close()


async def test_b02_discovery_latest_no_poll_rows_and_no_host_fanout(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    await inv.refresh_host("h1")
    before = j.api_head()
    for _ in range(7):
        await inv.refresh_host("h1")
    assert j.api_head() == before
    assert j.db.execute("SELECT COUNT(*) FROM discovery_latest").fetchone()[0] == 1
    scope = inv.discovery("h1")["scopes"][0]
    assert scope["authority"]["verified"] and scope["complete_enumeration"]
    assert any(x["scope"] == "background_git_state" for x in scope["outside_scan"])
    inv._record_failure("h1", time.time(), RuntimeError("offline"))
    kinds = [e["kind"] for e in j.api_events(before)["events"]]
    assert kinds == ["host.unreachable", "discovery.changed"]
    assert inv.get_session("h1", MANUAL)["state"]["connection"] == "not_connected"
    assert all(s["stale"] for s in inv.list_sessions()["sessions"])
    await inv.close()
    j.close()


async def test_b02_unchanged_poll_does_not_rewrite_observation_identities(mock, tmp_path, monkeypatch):
    from bat_agent_connector import inventory
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    adopt("registry-only", worktree_path="/srv/wt", worktree_made_by="bat")
    changes = []
    original = inventory.registry_bindings

    def capture(journal, host, entries):
        before = journal.db.total_changes
        original(journal, host, entries)
        changes.append(journal.db.total_changes - before)

    monkeypatch.setattr(inventory, "registry_bindings", capture)
    await inv.refresh_host("h1")
    tables = ("observation_resources", "session_worktree_bindings", "observation_relations", "relation_revisions", "command_relations",
              "api_event_context", "api_event_resources", "observation_backfill")
    before = {table: [tuple(r) for r in j.db.execute(f"SELECT * FROM {table}")] for table in tables}
    await inv.refresh_host("h1")
    assert changes[0] > 0 and changes[1] == 0
    assert before == {table: [tuple(r) for r in j.db.execute(f"SELECT * FROM {table}")] for table in tables}
    await inv.close()
    j.close()


async def test_b02_two_hosts_one_offline_and_scope_change(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    cfg = make_config(mock)
    cfg.hosts["h2"] = replace(cfg.host("h1"), name="h2", url="wss://127.0.0.1:1/")
    inv = Inventory(j, cfg)
    inv._record_success("h2", time.time(), [{"session_id": "old", "loaded": True}], "v-test")
    results = await inv.refresh_all()
    assert {r["host"]: r["reachable"] for r in results} == {"h1": True, "h2": False}
    assert inv.list_sessions(order="id")["count"] == 4
    assert inv.get_session("h2", "old")["loaded"] is True
    cfg.hosts["h1"] = replace(cfg.host("h1"), profile_id="another-profile")
    frames = len(mock.invokes)
    result = await inv.refresh_host("h1")
    assert "DISCOVERY_SCOPE_CHANGED" in result["error"] and len(mock.invokes) == frames
    assert inv.get_session("h1", MANUAL)["stale_reason"] == "scope_changed"
    assert inv.get_session("h1", MANUAL)["profile_id"] == "default"
    cfg.hosts.pop("h1")
    assert inv.get_session("h1", MANUAL)["scope_status"] == "outside_current_config"
    assert Observation(j).history("session", "h1/" + MANUAL)["events"]
    await inv.close()
    j.close()


@pytest.mark.parametrize("changed_field", ["url", "fingerprint"])
async def test_b02_scope_change_stays_blocked_on_later_refreshes(mock, tmp_path, changed_field):
    """B02, §11: the refused scope never replaces the stored scope or starts later BAT reads."""
    j = Journal(tmp_path / "j.db")
    cfg = make_config(mock)
    inv = Inventory(j, cfg)
    await inv.refresh_host("h1")
    original = cfg.host("h1")
    stored_binding = inv._binding("h1")
    ids = {s["resource_id"] for s in inv.list_sessions(order="id")["sessions"]}
    obs = Observation(j)
    histories = {rid: {e["seq"]: e for e in obs.history("session", rid)["events"]} for rid in ids}
    assert "attempted_binding_version" not in inv.discovery("h1")["scopes"][0]
    fields = {changed_field: original.url + "?scope=changed" if changed_field == "url" else "0" * 64}
    cfg.hosts["h1"] = replace(original, **fields)
    assert cfg.host("h1").profile_id == original.profile_id
    attempted = inv._binding("h1")
    assert attempted != stored_binding
    first_head = None
    for _ in range(2):
        frames = list(mock.frames)
        result = await inv.refresh_host("h1")
        assert not result["reachable"] and "DISCOVERY_SCOPE_CHANGED" in result["error"]
        assert mock.frames == frames
        row = j.db.execute("SELECT binding,body FROM discovery_latest WHERE host=? AND profile_id=?", ("h1", original.profile_id)).fetchone()
        scope = json.loads(row["body"])
        assert row["binding"] == scope["binding_version"] == stored_binding
        assert scope["attempted_binding_version"] == attempted
        assert inv.discovery("h1")["scopes"][0] == scope
        assert {s["resource_id"] for s in inv.list_sessions(order="id")["sessions"]} == ids
        for rid, history in histories.items():
            current = {e["seq"]: e for e in obs.history("session", rid)["events"]}
            assert all(current[seq] == event for seq, event in history.items())
        if first_head is None:
            first_head = j.api_head()
        else:
            assert j.api_head() == first_head
    cfg.hosts["h1"] = original
    inv._record_failure("h1", time.time(), RuntimeError("offline"))
    assert "attempted_binding_version" not in inv.discovery("h1")["scopes"][0]
    await inv.close()
    j.close()


async def test_b02_null_workspace_preserves_missing_counts_even_with_registry(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    adopt("registry-only")
    await inv.refresh_host("h1")
    mock.handlers["workspace:load"] = lambda p: None
    for _ in range(3):
        assert not (await inv.refresh_host("h1"))["reachable"]
    assert all(r[0] == 0 for r in j.db.execute("SELECT missing_count FROM sessions_observed"))
    assert inv.get_session("h1", "registry-only")["has_tab"] is False
    await inv.close()
    j.close()


async def test_b02_session_specific_stale_gone_fresh_and_get_no_writes(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    await inv.refresh_host("h1")
    original = mock.ws_doc["terminals"]
    mock.ws_doc["terminals"] = []
    start = j.api_head()
    await inv.refresh_host("h1")
    assert inv.get_session("h1", MANUAL)["state"]["enumeration"] == "missing"
    assert inv.get_session("h1", MANUAL)["state"]["tab"] == "no_tab"
    assert not inv.get_session("h1", MANUAL)["state"]["evidence"]["connection"]["stale"]
    await inv.refresh_host("h1")
    assert inv.get_session("h1", MANUAL)["state"]["enumeration"] == "gone"
    await inv.refresh_host("h1")
    kinds = [e["kind"] for e in j.api_events(start, resource_id="h1/" + MANUAL)["events"]]
    assert kinds == ["session.stale", "session.gone", "session.stale"]
    mock.ws_doc["terminals"] = original
    await inv.refresh_host("h1")
    tail = j.api_events(start, resource_id="h1/" + MANUAL)["events"]
    assert [e["kind"] for e in tail][-2:] == ["session.reappeared", "session.fresh"]
    before = j.db.total_changes
    for _ in range(3):
        inv.get_session("h1", MANUAL)
        inv.list_sessions(stale=True)
        inv.discovery("h1")
    assert j.db.total_changes == before
    await inv.close()
    j.close()


async def test_b03_states_unknown_no_tab_and_field_times(mock, tmp_path):
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    bind(j, task(j, "known"), "unobserved")
    unknown = inv.get_session("h1", "unobserved")
    assert unknown["loaded"] is unknown["has_tab"] is unknown["streaming"] is None
    assert unknown["state"]["lifecycle"] == "unknown" and unknown["api_access"] == "read_only"
    adopt("no-tab")
    await inv.refresh_host("h1")
    unloaded = inv.get_session("h1", "sess-unload-0003")
    assert unloaded["state"]["loading"] == "not_loaded" and unloaded["state"]["activity"] == "unknown"
    assert inv.get_session("h1", "no-tab")["state"]["tab"] == "no_tab"
    old = inv.get_session("h1", MANUAL)
    mock.handlers["claude:get-session-meta"] = lambda p: (_ for _ in ()).throw(RuntimeError("unavailable"))
    await inv.refresh_host("h1")
    new = inv.get_session("h1", MANUAL)
    assert new["state"]["loading"] == "loaded"
    assert new["state"]["evidence"]["activity"]["observed_at"] == old["state"]["evidence"]["activity"]["observed_at"]
    assert new["state"]["evidence"]["activity"]["stale"]
    await inv.close()
    j.close()


def test_b03_unknown_human_claim_is_not_api_actor_or_git_author(tmp_path):
    j = Journal(tmp_path / "j.db")
    t = task(j, "a")
    bind(j, t, "sid")
    j.note(t["task_id"], "manual_evidence", {"actor": "ted", "git_author": "Some Author", "words": "private prompt"})
    e = next(e for e in Observation(j).history("session", "h1/sid")["events"] if e["kind"] == "task.manual_evidence")
    assert e["context"]["actor"] is None and e["context"]["actor_basis"] == "unknown"
    assert e["context"]["claimed_actor"] == "ted" and "actor" in e["context"]["unknown_fields"]
    assert "private prompt" not in dump(e)
    j.close()


def test_b03_backfill_hidden_idempotent_and_unknown_boundaries(tmp_path):
    path = tmp_path / "j.db"
    j = Journal(path)
    t = task(j, "a")
    bind(j, t, "sid")
    j.db.execute("DELETE FROM api_event_context")
    j.db.execute("DELETE FROM api_event_resources")
    j.db.execute("DELETE FROM command_relations")
    j.db.execute("DELETE FROM relation_revisions")
    j.db.execute("DELETE FROM observation_relations")
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    assert all(r["start_seq"] is None for r in Observation(j).relations("session", "h1/sid")["relations"])
    with j.tx():
        saved_fact(j, "commands", "orphan", {"request": {"text": "private"}, "created_at": 123}, [("session", "h1/sid")])
    head = j.api_head()
    assert all(e["kind"] != "history.backfilled" for e in j.api_events()["events"])
    assert j.api_events()["next_cursor"] == head
    assert j.api_events(kind="history.backfilled")["events"]
    h = Observation(j).history("session", "h1/sid")["events"]
    assert any(e["kind"] == "history.backfilled" and e["context"]["backfilled"] for e in h)
    assert "private" not in dump(h)
    j.close()
    j = Journal(path)
    assert j.api_head() == head
    j.close()


async def test_b02_cursor_catchup_sse_resume_and_hidden_backfill(served):
    d, port = served
    viewer = token(d, "viewer", "observe")
    with d.journal.tx():
        baseline = d.journal.api_event("session", "h1/sid", "session.added", {})
        for n in range(5):
            saved_fact(d.journal, "legacy", str(n), {}, [("session", "h1/sid")])
        for n in range(6):
            d.journal.api_event("session", "h1/sid", "session.updated", {"n": n})
    cursor, ids = baseline, []
    while True:
        status, page = await http(port, "GET", f"/api/v1/events?after={cursor}&limit=2", tok=viewer)
        assert status == 200
        ids += [e["seq"] for e in page["events"]]
        cursor = page["next_cursor"]
        if not page["has_more"]:
            break
    assert len(ids) == len(set(ids)) == 6 and cursor == d.journal.api_head()
    with d.journal.tx():
        latest = d.journal.api_event("session", "h1/sid", "session.updated", {"n": 7})
    async def stream(after):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write((f"GET /api/v1/events/stream HTTP/1.1\r\nHost: localhost:{port}\r\nAuthorization: Bearer {viewer}\r\nLast-Event-ID: {after}\r\n\r\n").encode())
        await writer.drain()
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        frame = await asyncio.wait_for(reader.readuntil(b"\n\n"), 5)
        writer.close()
        await writer.wait_closed()
        return frame
    frame = await stream(cursor)
    assert f"id: {latest}\n".encode() in frame and b"history.backfilled" not in frame
    with d.journal.tx():
        newest = d.journal.api_event("session", "h1/sid", "session.updated", {"n": 8})
    frame2 = await stream(latest)
    assert f"id: {newest}\n".encode() in frame2 and f"id: {latest}\n".encode() not in frame2
    assert (await http(port, "GET", f"/api/v1/events/stream?after={newest+100}", tok=viewer))[0] == 422


async def test_b01_b02_b03_http_mcp_cli_contract_parity(served, mock, monkeypatch, capsys):
    d, port = served
    viewer = token(d, "viewer", "observe")
    monkeypatch.setenv("BATC_API_TOKEN", viewer)
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    await d.inventory.refresh_host("h1")
    t = task(d.journal, "a")
    bind(d.journal, t, MANUAL)
    with d.journal.tx():
        wid = worktree(d.journal, "h1", "task", t["task_id"], "external_worktree", path="/srv/wt", session_id=MANUAL)
        d.journal.api_event("session", "h1/" + MANUAL, "resource.bound", {})
    server, fleet = mcp_server.build_server(d.fleet.config, read_only=True)
    cases = [
        ("/api/v1/sessions?order=id&limit=1&provider=claude", "inventory_sessions", {"order": "id", "limit": 1, "provider": "claude"}, ["inventory", "sessions", "--order", "id", "--limit", "1", "--provider", "claude"]),
        ("/api/v1/sessions/h1/" + MANUAL, "inventory_session", {"host": "h1", "session_id": MANUAL}, ["inventory", "session", "h1", MANUAL]),
        ("/api/v1/sessions/h1/" + MANUAL + "/history?limit=2&order=asc", "resource_history", {"resource_type": "session", "resource_id": "h1/" + MANUAL, "limit": 2, "order": "asc"}, ["history", "session", "h1", MANUAL, "--limit", "2", "--order", "asc"]),
        ("/api/v1/sessions/h1/" + MANUAL + "/relations", "resource_relations", {"resource_type": "session", "resource_id": "h1/" + MANUAL}, ["relations", "session", "h1", MANUAL]),
        ("/api/v1/tasks/" + t["task_id"] + "/sessions", "resource_relations", {"resource_type": "execution", "resource_id": t["task_id"]}, ["relations", "execution", t["task_id"]]),
        ("/api/v1/worktrees/" + wid, "inventory_worktree", {"worktree_id": wid}, ["inventory", "worktree", wid]),
        ("/api/v1/worktrees/" + wid + "/history", "resource_history", {"resource_type": "worktree", "resource_id": wid}, ["history", "worktree", wid]),
        ("/api/v1/worktrees/" + wid + "/relations", "resource_relations", {"resource_type": "worktree", "resource_id": wid}, ["relations", "worktree", wid]),
        ("/api/v1/hosts/h1/discovery", "inventory_hosts", {"host": "h1", "discovery": True}, ["inventory", "discovery", "h1"]),
    ]
    for path, tool, params, command in cases:
        status, expected = await http(port, "GET", path, tok=viewer)
        assert status == 200, expected
        result = await server.call_tool(tool, params)
        if isinstance(result, tuple):
            content, structured = result
            actual = structured if structured is not None else json.loads(content[0].text)
        else:
            content = result.content if hasattr(result, "content") else result
            actual = json.loads(content[0].text)
        assert actual == expected, (tool, actual, expected)
        assert await asyncio.to_thread(cli.main, ["--json", *command]) == 0
        assert json.loads(capsys.readouterr().out) == expected
    assert len({"inventory_session", "inventory_worktree", "resource_history", "resource_relations"} & set(mcp_server.READ_TOOLS)) == 4
    assert (await http(port, "GET", "/api/v1/worktrees/wt_" + "0" * 32, tok=viewer))[0] == 404
    assert (await http(port, "GET", "/api/v1/sessions/h1/" + MANUAL + "/history?cursor=bad", tok=viewer))[0] == 422
    assert (await http(port, "GET", "/api/v1/sessions/h1/" + MANUAL + "/history"))[0] == 401
    cannot_read = token(d, "writer", "manage")
    assert (await http(port, "GET", "/api/v1/sessions/h1/" + MANUAL + "/relations", tok=cannot_read))[0] == 403
    assert write_frames(mock) == []
    await fleet.close()


async def test_b03_observation_never_starts_resumes_rehydrates_or_locks_git(mock, tmp_path, monkeypatch):
    from bat_agent_connector import checkpoints, service
    from tests.test_checkpoints import LocalRunner, git, snapshot
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "dev@example.invalid")
    git(repo, "config", "user.name", "dev")
    (repo / "file.txt").write_text("one\n")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-qm", "one")
    (repo / "file.txt").write_text("two\n")
    before = snapshot(repo)
    j = Journal(tmp_path / "j.db")
    inv = Inventory(j, make_config(mock))
    def refuse(*args, **kw):
        raise AssertionError("observation crossed a write or lock boundary")
    for name in ("claim_warm", "reserve", "update"):
        monkeypatch.setattr(registry, name, refuse)
    mock.metas[MANUAL] = {"cwd": str(repo), "isStreaming": False}
    # Claude without cwd is unsafe for get-session-state; retain the existing Codex-safe path.
    mock.metas["sess-unload-0003"] = {"isStreaming": True}
    mock.handlers["git:status"] = refuse
    await inv.refresh_host("h1")
    state_ids = {f["params"]["sessionId"] for f in mock.invokes if f["channel"] == "claude:get-session-state"}
    assert "sess-unload-0003" not in state_ids
    assert write_frames(mock) == []
    assert not any(f["channel"] == "git:status" for f in mock.invokes)
    # The existing explicit on-demand source probe remains lock-free.
    runner = LocalRunner()
    await runner.run("h1", checkpoints.source_state_script(str(repo)))
    assert "git --no-optional-locks" in runner.scripts[0]
    assert snapshot(repo) == before and not list((repo / ".git").glob("*.lock"))
    async def refuse_async(*args, **kw):
        refuse()
    monkeypatch.setattr(service, "_host_sessions", refuse_async)
    monkeypatch.setattr(registry, "list_entries", refuse)
    changes = j.db.total_changes
    inv.session_document("h1", MANUAL)
    inv.observation.history("session", "h1/" + MANUAL)
    inv.observation.relations("session", "h1/" + MANUAL)
    assert j.db.total_changes == changes and snapshot(repo) == before
    await inv.close()
    j.close()


def test_b01_warm_binding_closes_reserved_intent_without_overwriting(tmp_path):
    j = Journal(tmp_path / "j.db")
    t = task(j, "a")
    cmd, _ = j.command(t["task_id"], "start_lead", "reserved", {"warm_session_id": "reused"}, "warm")
    # A cursor captured before the bind must still list the command's old pending relation.
    j.add_branch(t["task_id"], session_id="earlier", provider="codex", role="reviewer", reason="start")
    obs = Observation(j)
    baseline = obs.relations("execution", t["task_id"], limit=1)
    j.command_bind_session(cmd["command_id"], "reused")
    j.command_status(cmd["command_id"], "settled")
    obs = Observation(j)
    assert obs.relations("session", "h1/reserved")["relations"][0]["status"] == "closed"
    assert obs.relations("session", "h1/reused")["relations"][0]["status"] == "bound"
    original = obs.relations("session", "h1/reserved")["relations"][0]
    assert original["command_ids"] == [cmd["command_id"]]
    tail = obs.relations("execution", t["task_id"], limit=1, cursor=baseline["next_cursor"])
    assert tail["as_of"] == baseline["as_of"]
    assert baseline["relations"][0]["command_ids"] == [cmd["command_id"]]
    j.close()


def test_b03_migration_failure_rolls_back_and_restart_recovers(tmp_path, monkeypatch):
    from bat_agent_connector import observation
    path = tmp_path / "j.db"
    j = Journal(path)
    task(j, "a")
    before = j.api_head()
    j.db.execute("PRAGMA user_version=1")
    j.close()
    original = observation.backfill
    def fail(journal):
        journal.api_event("session", "h1/sid", "session.added", {})
        raise RuntimeError("migration interrupted")
    monkeypatch.setattr(observation, "backfill", fail)
    with pytest.raises(RuntimeError, match="migration interrupted"):
        Journal(path)
    monkeypatch.setattr(observation, "backfill", original)
    j = Journal(path)
    assert j.api_head() == before
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == observation.MIGRATION_VERSION
    assert j.db.execute("SELECT COUNT(*) FROM observation_resources WHERE resource_id='h1/sid'").fetchone()[0] == 0
    j.close()


def test_b03_version_one_journal_runs_observation_backfill_once(tmp_path, monkeypatch):
    """B03, §08/§11: data step 2 runs once; idempotent DDL runs independently on every open."""
    from bat_agent_connector import observation
    path = tmp_path / "j.db"
    with monkeypatch.context() as legacy:
        legacy.setattr(observation, "install", lambda journal: None)
        j = Journal(path)
    t = task(j, "legacy")
    bind(j, t, "sid")
    j.db.execute("""INSERT INTO sessions_observed(host,session_id,body,digest,provenance,api_access,first_seen_at,last_seen_at)
        VALUES('h1','saved','{}','legacy','unknown','read_only',123,124)""")
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 1
    original = observation.backfill
    calls = []

    def capture(journal):
        assert journal.db.execute("PRAGMA user_version").fetchone()[0] == 1
        calls.append("backfill")
        original(journal)

    monkeypatch.setattr(observation, "backfill", capture)
    j.close()
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == observation.MIGRATION_VERSION == 2
    assert calls == ["backfill"]
    saved = Observation(j).history("session", "h1/saved")["events"]
    assert len(saved) == 1 and saved[0]["kind"] == "history.backfilled"
    assert Observation(j).relations("session", "h1/sid")["relations"]
    head = j.api_head()
    snapshot = [tuple(r) for r in j.db.execute("SELECT * FROM observation_backfill")]
    j.close()
    for _ in range(2):
        j = Journal(path)
        assert j.api_head() == head
        assert snapshot == [tuple(r) for r in j.db.execute("SELECT * FROM observation_backfill")]
        j.close()
    assert calls == ["backfill"]

    # DDL must still install on a version-2 journal without invoking its completed data step.
    already_path = tmp_path / "already.db"
    with monkeypatch.context() as legacy:
        legacy.setattr(observation, "install", lambda journal: None)
        j = Journal(already_path)
    task(j, "already")
    head = j.api_head()
    j.db.execute("PRAGMA user_version=2")
    j.close()
    j = Journal(already_path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert j.api_head() == head and calls == ["backfill"]
    assert j.db.execute("SELECT COUNT(*) FROM observation_backfill").fetchone()[0] == 0
    assert j.db.execute("SELECT COUNT(*) FROM api_event_context").fetchone()[0] == 0
    j.close()

    fresh_path = tmp_path / "fresh.db"
    j = Journal(fresh_path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert calls == ["backfill", "backfill"]
    assert j.api_head() == 0 and j.db.execute("SELECT COUNT(*) FROM observation_backfill").fetchone()[0] == 0
    j.close()
    j = Journal(fresh_path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert j.api_head() == 0 and calls == ["backfill", "backfill"]
    assert j.db.execute("SELECT COUNT(*) FROM observation_backfill").fetchone()[0] == 0
    j.close()


async def test_b03_rpc_admin_identity_is_not_claimed_human(served, monkeypatch):
    from bat_agent_connector.task_daemon import request
    d, port = served
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    t = task(d.journal, "a")
    bind(d.journal, t, "sid")
    await asyncio.to_thread(request, "work_pause", _auth_token=d._admin_token, task_id=t["task_id"], actor="ted", source_message_id="claimed-human-message")
    events = Observation(d.journal).history("execution", t["task_id"])["events"]
    paused = next(e for e in events if e["kind"] == "task.paused")
    assert paused["actor"] == "local-admin" and paused["context"]["actor"] == "local-admin"
    assert paused["context"]["entry_point"] == "rpc"
    assert paused["context"]["actor_evidence"]["source"] == "rpc_admin_token"
    assert all(e["context"]["actor"] != "ted" for e in events)


def test_b03_backfilled_occurrence_time_filters_are_not_migration_time(tmp_path):
    j = Journal(tmp_path / "j.db")
    with j.tx():
        seq = saved_fact(j, "legacy", "old", {"created_at": 123.5}, [("session", "h1/sid")])
    obs = Observation(j)
    assert [e["seq"] for e in obs.history("session", "h1/sid", since=123, until=124)["events"]] == [seq]
    assert obs.history("session", "h1/sid", since=124)["count"] == 0
    j.close()


def test_b01_legacy_task_external_creation_keeps_shared_identity(mock, tmp_path):
    path = tmp_path / "j.db"
    j = Journal(path)
    t = task(j, "external")
    bind(j, t, "sid")
    j.db.execute("UPDATE tasks SET session_id='sid',external_worktree_path='/srv/ext',external_branch='batc/task-fixture' WHERE task_id=?", (t["task_id"],))
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    wid = worktree_id("h1", "task", t["task_id"], "external_worktree")
    assert Observation(j).resource("session", "h1/sid")["worktree_id"] == wid
    assert Observation(j).history("worktree", wid)["events"][0]["kind"] == "history.backfilled"
    assert all(e["kind"] != "history.backfilled" for e in j.api_events()["events"])
    j.close()
