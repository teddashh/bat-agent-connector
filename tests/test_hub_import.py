"""B05: offline imports built from pinned Hub files, never from private data or a runtime."""

from __future__ import annotations

import ast
import asyncio
import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bat_agent_connector import hub_import as hub
from bat_agent_connector import work_items as wi
from bat_agent_connector.config import HubImportSource
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.test_work_items import PERSON, get
from tests.test_work_items import act as management_act

FIXTURE = Path(__file__).parent / "fixtures/hub-import/basic"


@pytest.mark.parametrize("version", [1, 8])
def test_b05_import_ddl_preserves_data_step_version_and_is_idempotent(tmp_path, version):
    import sqlite3

    from bat_agent_connector.task_journal import Journal

    path = tmp_path / "journal.db"
    with sqlite3.connect(path) as db:
        db.execute(f"PRAGMA user_version={version}")
    journal = Journal(path)
    db = journal.db
    assert db.execute("PRAGMA user_version").fetchone()[0] == version
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"hub_import_sources", "hub_import_map", "hub_import_previews", "hub_import_receipts",
            "hub_import_groups", "hub_import_source_snapshots"} <= tables
    db.execute("INSERT INTO hub_import_sources(source_id,revision) VALUES('fixture',3)")
    statements = []
    db.set_trace_callback(statements.append)
    journal._migrate_hub_import()
    db.set_trace_callback(None)
    assert not any("user_version" in sql.lower() for sql in statements)
    before = list(db.iterdump())
    journal.close()
    reopened = Journal(path)
    assert reopened.db.execute("PRAGMA user_version").fetchone()[0] == version
    assert list(reopened.db.iterdump()) == before
    reopened.close()


@pytest.fixture
async def daemon(mock, tmp_path):
    src = tmp_path / "hub"
    shutil.copytree(FIXTURE, src)
    cfg = make_config(mock, writes=False, orchestrate=False)
    cfg = replace(cfg, hub_import_sources={"sample": HubImportSource("sample", str(src), True)})
    d = TaskDaemon(cfg, tmp_path / "tasks.db")
    yield d, src
    for task in d.ops._active.values():
        task.cancel()
    await asyncio.gather(*d.ops._active.values(), return_exceptions=True)
    await d.fleet.close()
    await d.inventory.close()
    d.journal.close()


async def act(d, who, action, target=None, params=None, pre=None, *, key=None, ok=True):
    op = await management_act(d, who, action, target, params, pre, key=key, ok=False)
    await d.ops.drain(timeout=60)
    op = d.ops.get(op["operation_id"])
    if ok:
        assert op["status"] == "succeeded", (op["error_code"], op["status_reason"])
    return op


async def preview(d):
    op = await act(d, PERSON, "hub.import.preview", {"source_id": "sample"})
    return hub.get_preview(d.ops, op["result"]["preview"]["preview_id"], PERSON)


async def apply(d, doc, *, ok=True):
    req = hub.apply_request(doc)
    return await act(
        d,
        PERSON,
        req["action"],
        req["target"],
        req["params"],
        req["preconditions"],
        key=req["idempotency_key"],
        ok=ok,
    )


def mapped(d, p, t=""):
    return hub._mapped_id(d.ops.db, "sample", hub.record_key("item" if t else "project", p, t))


async def test_B05_preview_apply_preserves_hub_data_and_four_phases(daemon, mock):
    d, src = daemon
    before = {str(p.relative_to(src)): p.read_bytes() for p in src.rglob("*") if p.is_file()}
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert doc["counts"]["projects"]["create"] == 4
    assert doc["counts"]["work_items"]["create"] == 8
    assert not list(d.ops.db.execute("SELECT * FROM projects"))
    op = await apply(d, doc)
    assert op["result"]["complete"]
    assert [
        r[0]
        for r in d.ops.db.execute(
            "SELECT name FROM operation_steps WHERE operation_id=? ORDER BY seq", (op["operation_id"],)
        )
    ] == ["source.verify", "records", "structure.apply", "baseline.finalize"]
    main = get(d, mapped(d, "alpha", "t"))
    assert main["request"] == hub.parse_doc((src / "Product/alpha/.ai/tasks/t.md").read_text())[1]
    assert main["acceptance"] == "The sample preserves the original request."
    assert main["source"]["snapshot"]["request_history"][0]["text"].startswith("Preserve this additional")
    assert main["operation_id"] == op["operation_id"] and "#" not in main["operation_id"]
    assert len(main["import_record"]) == 32
    assert get(d, mapped(d, "alpha", "child"))["parent_id"] == main["work_item_id"]
    branch = get(d, mapped(d, "alpha", "branch"))
    assert branch["parent_id"] == main["work_item_id"] and branch["derived_from"] == mapped(
        d, "alpha", "child"
    )
    cross = get(d, mapped(d, "delta", "t"))
    assert cross["parent_id"] is None and cross["derived_from"] == mapped(d, "alpha", "child")
    done = get(d, mapped(d, "alpha", "done"))
    assert done["source"]["historical_completion"]["approved"] is True
    assert done["completion"]["approved"] is False and done["completion"]["pending"] is True
    assert get(d, mapped(d, "alpha", "continued"))["completion"]["pending"] is False
    assert {x["ref"] for x in wi.work_item_get(d.ops.db, main["work_item_id"])["links"]} == {
        "https://example.invalid/reference",
        "https://example.invalid/guide",
        "https://example.invalid/history",
    }
    roots = wi.projects_list(d.ops.db)["projects"]
    assert [p["name"] for p in roots] == ["Delta", "Alpha", "Fork"]
    assert [p["name"] for p in roots[1]["children"]] == ["Beta"]
    assert not mock.invokes
    assert not list(d.ops.db.execute("SELECT * FROM tasks"))
    assert before == {str(p.relative_to(src)): p.read_bytes() for p in src.rglob("*") if p.is_file()}


async def test_B05_idempotent_reimport_and_source_update(daemon):
    d, src = daemon
    first = await apply(d, await preview(d))
    before = {
        r["connector_id"]: hub._destination(d.ops.db, r["kind"], r["connector_id"])
        for r in d.ops.db.execute("SELECT * FROM hub_import_map")
    }
    doc = await preview(d)
    assert doc["counts"]["projects"]["unchanged"] == 4
    assert doc["counts"]["work_items"]["unchanged"] == 8
    second = await apply(d, doc)
    assert first["operation_id"] != second["operation_id"]
    assert before == {
        r["connector_id"]: hub._destination(d.ops.db, r["kind"], r["connector_id"])
        for r in d.ops.db.execute("SELECT * FROM hub_import_map")
    }
    path = src / "Product/alpha/.ai/tasks/t.md"
    path.write_text(path.read_text().replace("Main request", "Renamed request"))
    doc = await preview(d)
    assert doc["counts"]["work_items"]["update"] == 1 and doc["can_apply"], doc["blockers"]
    await apply(d, doc)
    assert get(d, mapped(d, "alpha", "t"))["title"] == "Renamed request"
    assert get(d, mapped(d, "alpha", "t"))["operation_id"] == first["operation_id"]
    same, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    assert same["status"] == "succeeded"
    summaries = list(d.ops.db.execute("SELECT * FROM api_events WHERE kind LIKE 'hub_import.%'"))
    assert len(summaries) == 3 and all(r["kind"] == "hub_import.completed" for r in summaries)


@pytest.mark.parametrize("edit", ["content", "reverted", "approval", "archive"])
async def test_b05_source_updates_and_local_edits_conflict(daemon, edit):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "waiting")
    row = get(d, wid)
    if edit in ("content", "reverted"):
        await act(
            d,
            PERSON,
            "work_item.update",
            {"work_item_id": wid},
            {"title": "Local decision"},
            {"expected_version": row["version"]},
        )
        if edit == "reverted":
            await act(
                d,
                PERSON,
                "work_item.update",
                {"work_item_id": wid},
                {"title": row["title"]},
                {"expected_version": get(d, wid)["version"]},
            )
    elif edit == "approval":
        await act(
            d,
            PERSON,
            "work_item.approve",
            {"work_item_id": wid},
            {},
            {"expected_fingerprint": row["completion"]["fingerprint"]},
        )
    else:
        await act(
            d,
            PERSON,
            "work_item.update",
            {"work_item_id": wid},
            {"archived": True},
            {"expected_version": row["version"]},
        )
    local = await preview(d)
    assert next(r for r in local["records"] if r["connector_id"] == wid)["classification"] == "local_only"
    path = src / "Product/alpha/.ai/tasks/waiting.md"
    path.write_text(path.read_text().replace("Waiting", "Source decision"))
    conflict = await preview(d)
    assert not conflict["can_apply"]
    assert next(r for r in conflict["records"] if r["connector_id"] == wid)["classification"] == "conflict"
    with pytest.raises(hub.OperationError, match="IMPORT_CONFLICT"):
        d.ops.create(PERSON, **hub.apply_request(conflict))


async def test_b05_metadata_links_source_missing_and_rename(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "t")
    before = get(d, wid)
    path = src / "Product/alpha/.ai/tasks/t.md"
    path.write_text(path.read_text().replace("owner: synthetic-person", "owner: other-synthetic-person"))
    doc = await preview(d)
    assert doc["counts"]["work_items"]["metadata_only"] == 1, [
        (r["key"], r["classification"], r["changed_fields"])
        for r in doc["records"]
        if r["classification"] != "unchanged"
    ]
    await apply(d, doc)
    assert get(d, wid)["version"] == before["version"] and get(d, wid)["updated_at"] == before["updated_at"]
    path.write_text(
        path.read_text().replace("https://example.invalid/reference", "https://example.invalid/replacement")
    )
    await apply(d, await preview(d))
    detail = wi.work_item_get(d.ops.db, wid)
    assert "https://example.invalid/reference" in {x["ref"] for x in detail["removed_links"]}
    assert "https://example.invalid/replacement" in {x["ref"] for x in detail["links"]}
    old = src / "Product/alpha/.ai/tasks/waiting.md"
    text = old.read_text()
    missing_id = mapped(d, "alpha", "waiting")
    old.unlink()
    doc = await preview(d)
    assert doc["counts"]["work_items"]["source_missing"] == 1 and doc["can_apply"]
    await apply(d, doc)
    assert not get(d, missing_id)["archived"]
    old.write_text(text)
    p = src / "Product/alpha/PROJECT.md"
    p.write_text(p.read_text().replace("name: Alpha", "name: Renamed Alpha"))
    beta = src / "Product/beta/PROJECT.md"
    beta.write_text(beta.read_text().replace("parent: Alpha", "parent: alpha"))
    await apply(d, await preview(d))
    assert mapped(d, "alpha", "waiting") == missing_id
    assert wi.project_get(d.ops.db, mapped(d, "alpha"))["project"]["name"] == "Renamed Alpha"


async def test_b05_order_changes_protect_local_siblings(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    await act(d, PERSON, "project.create", {}, {"name": "Local sibling"})
    order = src / "_hub/project-order.json"
    order.write_text('{"groups":{"": ["fork", "delta", "alpha"], "alpha": ["beta"]}}\n')
    doc = await preview(d)
    assert any(x.get("group_key") and x["code"] == "IMPORT_CONFLICT" for x in doc["blockers"])


@pytest.mark.parametrize("mutation", ["source", "collection", "root", "destination", "pin", "link", "order"])
async def test_b05_stale_source_and_destination_stop_apply(daemon, mutation):
    import os

    d, src = daemon
    await apply(d, await preview(d))
    doc = await preview(d)
    wid = mapped(d, "alpha", "waiting")
    if mutation == "source":
        p = src / "Product/alpha/.ai/tasks/waiting.md"
        st = p.stat()
        p.write_text(p.read_text().replace("Waiting", "Changed"))
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    elif mutation == "collection":
        p = src / "Product/alpha/.ai/tasks/new.md"
        p.write_text("---\ntitle: New\n---\n")
    elif mutation == "root":
        src.rename(src.with_name("old-hub"))
        shutil.copytree(src.with_name("old-hub"), src)
    elif mutation == "destination":
        await act(
            d,
            PERSON,
            "work_item.update",
            {"work_item_id": wid},
            {"title": "Local"},
            {"expected_version": get(d, wid)["version"]},
        )
    elif mutation == "pin":
        await act(d, PERSON, "work_item.pin", {"work_item_id": wid}, {"pinned": True}, {"before": False})
    elif mutation == "link":
        await act(
            d,
            PERSON,
            "work_item.link",
            {"work_item_id": wid},
            {"kind": "external_url", "ref": "https://example.invalid/local"},
        )
    else:
        ids = [p["project_id"] for p in wi.projects_list(d.ops.db)["projects"]]
        await act(d, PERSON, "project.order", {}, {"order": [ids[0], *reversed(ids[1:])]}, {"before": ids})
    counts = d.ops.db.execute("SELECT COUNT(*) FROM hub_import_receipts").fetchone()[0]
    op = await apply(d, doc, ok=False)
    assert op["status"] == "needs_attention"
    assert op["error_code"] == (
        "SOURCE_CHANGED" if mutation in ("source", "collection", "root") else "DESTINATION_CHANGED"
    )
    assert d.ops.db.execute("SELECT COUNT(*) FROM hub_import_receipts").fetchone()[0] == counts
    assert not hub.import_get(d.ops, op["operation_id"])["import"]["partial"]


@pytest.mark.parametrize("phase", ["source.verify", "records", "structure.apply", "baseline.finalize"])
@pytest.mark.parametrize("committed_response", [False, True])
async def test_b05_restart_lost_reply_and_partial_recovery(daemon, monkeypatch, phase, committed_response):
    d, src = daemon
    doc = await preview(d)
    real = d.ops._step_done

    def crash(op, name, response, **kw):
        if name == phase:
            if committed_response:
                real(op, name, response, **kw)
            raise asyncio.CancelledError()
        return real(op, name, response, **kw)

    monkeypatch.setattr(d.ops, "_step_done", crash)
    op, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    await d.ops.run_due()
    # Stop after the first simulated daemon death; drain would keep scheduling that same crash.
    stopped = await asyncio.wait_for(
        asyncio.gather(d.ops._active[op["operation_id"]], return_exceptions=True), timeout=60
    )
    assert isinstance(stopped[0], asyncio.CancelledError)
    assert d.ops.get(op["operation_id"])["status"] == "running"
    opid = op["operation_id"]
    receipts = {r["record_key"]: r["connector_id"] for r in d.ops.db.execute("SELECT * FROM hub_import_map")}
    cfg = replace(make_config_for(d), hub_import_sources=d.ops.context["hub_import_sources"])
    path = d.journal.path
    d.journal.close()
    restarted = TaskDaemon(cfg, path)
    d.journal, d.ops = restarted.journal, restarted.ops
    await d.ops.drain(timeout=30)
    final = d.ops.get(opid)
    assert final["status"] == "succeeded", final
    assert all(mapped(d, json.loads(k)[1], json.loads(k)[2]) == cid for k, cid in receipts.items())
    assert len(list(d.ops.db.execute("SELECT * FROM hub_import_map"))) == 12
    assert len(list(d.ops.db.execute("SELECT * FROM api_events WHERE kind='hub_import.completed'"))) == 1
    assert [s["status"] for s in final["steps"]] == ["succeeded"] * 4


def make_config_for(d):
    return d.fleet.config


async def test_b05_sqlite_rollback_is_reconciled_without_duplicate_rows(daemon, monkeypatch):
    import sqlite3

    d, _ = daemon
    doc = await preview(d)
    original = hub._save_receipt
    calls = 0

    def fail(ctx, key, result, after=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("synthetic disk failure before commit")
        return original(ctx, key, result, after)

    monkeypatch.setattr(hub, "_save_receipt", fail)
    op, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "uncertain"
    assert d.ops.db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    monkeypatch.setattr(hub, "_save_receipt", original)
    d.ops.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op["operation_id"],))
    await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "succeeded"
    assert d.ops.db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 4


async def test_b05_retirement_busy_cancel_and_resume(daemon, monkeypatch):
    d, _ = daemon
    source = d.ops.context["hub_import_sources"]["sample"]
    d.ops.context["hub_import_sources"]["sample"] = replace(source, runtime_retired=False)
    doc = await preview(d)
    assert any(b["code"] == "HUB_NOT_RETIRED" for b in doc["blockers"])
    with pytest.raises(hub.OperationError, match="HUB_NOT_RETIRED"):
        d.ops.create(PERSON, **hub.apply_request(doc))
    d.ops.context["hub_import_sources"]["sample"] = source
    doc = await preview(d)
    op, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    req = hub.apply_request(doc)
    req["idempotency_key"] = "another-apply"
    with pytest.raises(hub.OperationError, match="IMPORT_BUSY"):
        d.ops.create(PERSON, **req)
    real = hub._write_record

    def cancel(ctx, row, doc):
        result = real(ctx, row, doc)
        ctx.service.cancel(PERSON, ctx.operation_id)
        return result

    monkeypatch.setattr(hub, "_write_record", cancel)
    await d.ops.drain(timeout=60)
    final = d.ops.get(op["operation_id"])
    assert final["status"] == "cancelled"
    assert hub.import_get(d.ops, final["operation_id"])["import"]["partial"]
    monkeypatch.setattr(hub, "_write_record", real)
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    await apply(d, doc)
    assert d.ops.db.execute("SELECT COUNT(*) FROM hub_import_map").fetchone()[0] == 12


@pytest.mark.parametrize(
    ("file", "text", "code"),
    [
        ("_hub/project-order.json", "{broken", "IMPORT_FORMAT_INVALID"),
        ("_hub/project-pins.json", '["alpha", "alpha"]', "IMPORT_FORMAT_INVALID"),
        ("_hub/completion.json", '{"version":true}', "IMPORT_FORMAT_INVALID"),
        ("Product/alpha/PROJECT.md", "not frontmatter", "IMPORT_FORMAT_INVALID"),
        ("Product/alpha/PROJECT.md", "---\nname: A\nparent: missing\n---\n", "IMPORT_RELATION_INVALID"),
        ("Product/alpha/PROJECT.md", "---\nname: A\nparent: beta\n---\n", "IMPORT_RELATION_INVALID"),
        ("Product/alpha/.ai/tasks/waiting.md", "---\ntitle: A\ntitle: B\n---\n", "IMPORT_FORMAT_INVALID"),
        ("Product/alpha/.ai/tasks/waiting.md", "---\nid: wrong\n---\n", "IMPORT_FORMAT_INVALID"),
        ("Product/alpha/.ai/tasks/waiting.md", "---\nstate: unknown\n---\n", "IMPORT_STATE_UNSUPPORTED"),
        (
            "Product/alpha/.ai/tasks/waiting.md",
            "---\nstate: 完了\n---\n## 手順\n- [ ] Open\n",
            "COMPLETION_STEPS_OPEN",
        ),
        ("Product/alpha/.ai/chat/t.jsonl", '{"role":"user","text":"a","text":"b"}', "IMPORT_FORMAT_INVALID"),
    ],
)
async def test_b05_invalid_and_incomplete_formats_are_reported(daemon, file, text, code):
    d, src = daemon
    (src / file).write_text(text)
    doc = await preview(d)
    assert not doc["can_apply"] and any(b["code"] == code for b in doc["blockers"]), doc["blockers"]
    assert d.ops.db.execute("SELECT COUNT(*) FROM work_items").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["file_symlink", "directory_symlink", "fifo", "utf8", "limit"])
async def test_b05_descriptor_snapshot_refuses_unsafe_sources(daemon, kind, monkeypatch):
    import os

    d, src = daemon
    p = src / "Product/alpha/.ai/tasks/waiting.md"
    if kind == "file_symlink":
        p.unlink()
        p.symlink_to(src / "Product/alpha/.ai/tasks/t.md")
    elif kind == "directory_symlink":
        old = src / "Product/alpha/.ai/tasks"
        old.rename(old.with_name("old"))
        old.symlink_to(old.with_name("old"))
    elif kind == "fifo":
        p.unlink()
        os.mkfifo(p)
    elif kind == "utf8":
        p.write_bytes(b"\xff")
    else:
        monkeypatch.setattr(hub, "FILE_MAX", 5)
    doc = await preview(d)
    code = (
        "IMPORT_FORMAT_INVALID"
        if kind == "utf8"
        else "IMPORT_LIMIT_EXCEEDED"
        if kind == "limit"
        else "IMPORT_SOURCE_UNSAFE"
    )
    assert not doc["can_apply"] and doc["blockers"][0]["code"] == code


@pytest.mark.parametrize("marker", [True, False])
async def test_b05_completion_missing_ledger_never_seeds_approval(daemon, marker):
    d, src = daemon
    (src / "_hub/completion.json").unlink()
    if not marker:
        (src / "_hub/completion.migrated").unlink()
    await apply(d, await preview(d))
    done = get(d, mapped(d, "alpha", "done"))
    assert done["source"]["historical_completion"]["legacy_unverified"] is (not marker)
    assert done["completion"]["pending"] and not done["completion"]["approved"]
    assert not (src / "_hub/completion.json").exists()


def test_b05_frontmatter_dialect_and_crlf_hash():
    doc, body = hub.parse_doc(
        '---\r\nname: "中文 # keep" # comment\r\nnumber: 12\r\nflags: [true, false]\r\nfolders:\r\n  notes: local/file\r\nchats:\r\n  - {title: "a,b", url: https://example.invalid/a}\r\n---\r\n完整文字\r\n'
    )
    assert doc == {
        "name": "中文 # keep",
        "number": "12",
        "flags": [True, False],
        "folders": {"notes": "local/file"},
        "chats": [{"title": "a,b", "url": "https://example.invalid/a"}],
    }
    assert body == "完整文字\r\n"
    assert hub.hub_hash("完整文字\r\n") == hub.hub_hash("完整文字\n")


async def test_b05_daemon_source_boundary_and_scopes(daemon):
    from bat_agent_connector import api_auth

    d, src = daemon
    observer = api_auth.Principal("observer", frozenset({"observe"}))
    before = d.ops.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    for who, target, params, code in (
        (observer, {"source_id": "sample"}, {}, "FORBIDDEN"),
        (PERSON, {"source_id": "sample", "path": str(src)}, {}, "INVALID_PARAMS"),
        (PERSON, {"source_id": "sample"}, {"path": str(src)}, "INVALID_PARAMS"),
        (PERSON, {"source_id": ["sample"]}, {}, "INVALID_TARGET"),
        (PERSON, {"source_id": "unknown"}, {}, "IMPORT_SOURCE_NOT_CONFIGURED"),
    ):
        with pytest.raises(hub.OperationError) as exc:
            d.ops.create(
                who, action="hub.import.preview", target=target, params=params, idempotency_key="refused"
            )
        assert exc.value.code == code
    assert before == d.ops.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    doc = await preview(d)
    other = api_auth.Principal("another-person", frozenset({"observe", "manage"}))
    with pytest.raises(hub.OperationError, match="FORBIDDEN"):
        hub.get_preview(d.ops, doc["preview_id"], other)
    with pytest.raises(hub.OperationError, match="FORBIDDEN"):
        d.ops.create(other, **hub.apply_request(doc))
    req = hub.apply_request(doc)
    req["preconditions"]["preview_digest"] = "bad-digest"
    with pytest.raises(hub.OperationError, match="PREVIEW_MISMATCH"):
        d.ops.create(PERSON, **req)
    d.ops.db.execute("UPDATE hub_import_previews SET expires_at=0 WHERE preview_id=?", (doc["preview_id"],))
    with pytest.raises(hub.OperationError, match="PREVIEW_EXPIRED"):
        d.ops.create(PERSON, **hub.apply_request(doc))
    assert str(src) not in json.dumps(hub.sources_list(d.ops))


@pytest.mark.parametrize(
    "row",
    [
        {"id": "good", "path": "relative"},
        {"id": "bad/id", "path": "/synthetic"},
        {"id": "good", "path": "/synthetic/../escape"},
        {"id": "good", "path": "/synthetic", "runtime_retired": "true"},
        {"id": "good", "path": "/synthetic", "url": "https://example.invalid"},
    ],
)
def test_b05_config_source_allowlist_is_strict(row):
    from bat_agent_connector.config import parse_config
    from bat_agent_connector.errors import ConfigError

    with pytest.raises(ConfigError):
        parse_config({"hub_import": {"sources": [row]}})


async def test_b05_http_rpc_and_mcp_share_the_same_actions(daemon, monkeypatch):
    from bat_agent_connector import mcp_server
    from tests.test_api_v1 import http, token

    d, _ = daemon
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    tok = token(d, PERSON.actor, "observe", "manage")
    try:
        status, sources = await http(port, "GET", "/api/v1/hub-import/sources", tok=tok)
        assert status == 200 and sources == await d.call_api("hub_import_sources", {}, PERSON)
        status, out = await http(
            port,
            "POST",
            "/api/v1/operations",
            tok=tok,
            headers={"Idempotency-Key": "http-preview"},
            body={"action": "hub.import.preview", "target": {"source_id": "sample"}},
        )
        assert status == 202
        await d.ops.drain(timeout=60)
        op = d.ops.get(out["operation"]["operation_id"])
        assert (
            "records" not in op["result"]["preview"]
        )  # actor-bound source text is not in generic operation reads
        pv = op["result"]["preview"]["preview_id"]
        status, result = await http(port, "GET", "/api/v1/hub-import/previews/" + pv, tok=tok)
        assert status == 200 and result["preview"]["can_apply"]
        req = hub.apply_request(result["preview"])
        out = await d.call_api("op_submit", {**req, "entry": "mcp"}, PERSON)
        await d.ops.drain(timeout=60)
        opid = out["operation"]["operation_id"]
        status, result = await http(port, "GET", "/api/v1/hub-import/imports/" + opid, tok=tok)
        assert status == 200 and result["import"]["complete"]
        same = await d.call_api("op_submit", {**req, "entry": "cli"}, PERSON)
        assert not same["created"] and same["operation"]["operation_id"] == opid

        def fake_rpc(method, **kwargs):
            assert method == "hub_import_sources"
            return sources

        monkeypatch.setattr(mcp_server, "task_request", fake_rpc)
        mcp, fleet = mcp_server.build_server(d.fleet.config)
        tools = {x.name: x for x in await mcp.list_tools()}
        assert tools["hub_import_sources"].annotations.read_only_hint
        assert "hub_import_get" in tools and "operation_submit" in tools
        response = await mcp.call_tool("hub_import_sources", {})
        assert "sample" in json.dumps(
            response.model_dump() if hasattr(response, "model_dump") else response, default=str
        )
        await fleet.close()
    finally:
        server.close()
        await server.wait_closed()


def test_b05_cli_submits_preview_then_its_fixed_apply_key(monkeypatch, capsys):
    from bat_agent_connector import cli, task_daemon

    doc = {
        "source_id": "sample",
        "preview_id": "hip_" + "1" * 32,
        "digest": "fixture-digest",
        "can_apply": True,
    }
    calls = []

    def fake_request(method, **kw):
        calls.append((method, kw))
        if method == "hub_import_get":
            return {"preview": doc}
        if method == "hub_import_sources":
            return {"sources": []}
        return {"operation": {"status": "succeeded", "result": {"preview": doc}}}

    monkeypatch.setattr(task_daemon, "request", fake_request)
    assert cli.main(["hub", "import", "--source", "sample", "--preview"]) == 0
    assert calls[0][1]["action"] == "hub.import.preview"
    calls.clear()
    assert (
        cli.main(["hub", "import", "--source", "sample", "--apply", "--preview-id", doc["preview_id"]]) == 0
    )
    assert calls[-1][1]["action"] == "hub.import.apply"
    assert calls[-1][1]["idempotency_key"] == "hub.import.apply." + doc["preview_id"]
    assert cli.main(["hub", "show"]) == 0
    assert cli.main(["hub", "import", "--source", "sample", "--apply"]) != 0
    capsys.readouterr()


async def test_b05_cross_source_mapping_and_snapshot_move(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    alpha = mapped(d, "alpha")
    old = mapped(d, "alpha", "t")
    moved = src.with_name("moved")
    src.rename(moved)
    d.ops.context["hub_import_sources"]["sample"] = HubImportSource("sample", str(moved), True)
    doc = await preview(d)
    assert doc["can_apply"] and doc["counts"]["work_items"]["unchanged"] == 8
    await apply(d, doc)
    assert old == mapped(d, "alpha", "t")
    d.ops.context["hub_import_sources"]["second"] = HubImportSource("second", str(src), True)
    shutil.copytree(moved, src)
    for p in (src / "Product").iterdir():
        path = p / "PROJECT.md"
        path.write_text(
            path.read_text().replace("name: ", "name: Second ").replace("parent: Alpha", "parent: alpha")
        )
    op = await act(d, PERSON, "hub.import.preview", {"source_id": "second"})
    doc = hub.get_preview(d.ops, op["result"]["preview"]["preview_id"], PERSON)
    assert doc["can_apply"], doc["blockers"]
    await apply(d, doc)
    assert hub._mapped_id(d.ops.db, "second", hub.record_key("project", "alpha")) != alpha
    assert hub._mapped_id(d.ops.db, "second", hub.record_key("item", "alpha", "t")) != old


async def test_b05_archived_destination_is_not_used_for_new_items(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    pid = mapped(d, "delta")
    project = wi.project_get(d.ops.db, pid)["project"]
    await act(
        d,
        PERSON,
        "project.update",
        {"project_id": pid},
        {"archived": True},
        {"expected_version": project["version"]},
    )
    path = src / "Product/delta/.ai/tasks/new.md"
    path.write_text("---\ntitle: New in archived project\n---\n")
    doc = await preview(d)
    assert not doc["can_apply"] and any(b["code"] == "ARCHIVED" for b in doc["blockers"])


async def test_b05_record_commit_reply_loss_and_mid_import_source_change(daemon, monkeypatch):
    d, src = daemon
    doc = await preview(d)
    real = hub._write_record
    calls = 0

    def lost(ctx, row, doc):
        nonlocal calls
        calls += 1
        result = real(ctx, row, doc)
        if calls == 1:
            raise OSError("synthetic lost receipt reply after commit")
        return result

    monkeypatch.setattr(hub, "_write_record", lost)
    op, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "uncertain"
    cid = mapped(d, "alpha")
    monkeypatch.setattr(hub, "_write_record", real)
    d.ops.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op["operation_id"],))
    await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "succeeded" and mapped(d, "alpha") == cid
    path = src / "Product/alpha/.ai/tasks/waiting.md"
    path.write_text(path.read_text().replace("Waiting", "Updated waiting"))
    doc = await preview(d)

    def changed(ctx, row, doc):
        result = real(ctx, row, doc)
        path.write_text(path.read_text() + "More source text\n")
        return result

    monkeypatch.setattr(hub, "_write_record", changed)
    op = await apply(d, doc, ok=False)
    assert op["status"] == "needs_attention" and op["error_code"] == "SOURCE_CHANGED"
    assert hub.import_get(d.ops, op["operation_id"])["import"]["partial"]
    assert get(d, mapped(d, "alpha", "waiting"))["source"]["import_state"] == "incomplete"
    d.ops.cancel(PERSON, op["operation_id"])
    monkeypatch.setattr(hub, "_write_record", real)
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    await apply(d, doc)


async def test_b05_many_records_use_constant_steps_and_no_children(daemon):
    d, src = daemon
    for i in range(1000):
        (src / "Product/alpha/.ai/tasks" / f"bulk-{i:04d}.md").write_text(
            f"---\ntitle: Synthetic bulk {i}\n---\n"
        )
    doc = await preview(d)
    op, _ = d.ops.create(PERSON, **hub.apply_request(doc))
    # A thousand individual commits can exceed a minute on the shared test filesystem.
    await d.ops.drain(timeout=180)
    op = d.ops.get(op["operation_id"])
    assert op["status"] == "succeeded", (op["status"], op["error_code"])
    assert len(op["steps"]) == 4
    assert d.ops.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 2
    assert (
        d.ops.db.execute("SELECT COUNT(*) FROM api_events WHERE kind LIKE 'hub_import.%'").fetchone()[0] == 1
    )
    assert d.ops.db.execute("SELECT COUNT(*) FROM hub_import_source_snapshots").fetchone()[0] == 1
    assert d.ops.db.execute("SELECT COUNT(*) FROM work_items").fetchone()[0] == 1008


async def test_b05_date_id_and_depth(daemon):
    d, src = daemon
    shutil.rmtree(src)
    shutil.copytree(FIXTURE.parent / "date-id", src)
    doc = await preview(d)
    assert doc["can_apply"]
    await apply(d, doc)
    assert mapped(d, "dated", "20261001-01")
    tasks = src / "Product/dated/.ai/tasks"
    for i in range(33):
        (tasks / f"depth-{i}.md").write_text(
            "---\ntitle: Deep\n" + (f"parent: depth-{i - 1}\n" if i else "") + "---\n"
        )
    doc = await preview(d)
    assert any(b["code"] == "IMPORT_RELATION_INVALID" for b in doc["blockers"])


async def test_b05_snapshot_race_and_destination_missing(daemon, monkeypatch):
    d, src = daemon
    original = hub._Reader.read
    changed = False

    def raced(reader, relative, **kw):
        nonlocal changed
        result = original(reader, relative, **kw)
        if relative.endswith("waiting.md") and not changed:
            changed = True
            p = src / relative
            p.write_text(p.read_text() + "Raced\n")
        return result

    monkeypatch.setattr(hub._Reader, "read", raced)
    doc = await preview(d)
    assert doc["blockers"][0]["code"] == "SOURCE_CHANGED"
    monkeypatch.setattr(hub._Reader, "read", original)
    await apply(d, await preview(d))
    d.ops.db.execute("DELETE FROM work_items WHERE work_item_id=?", (mapped(d, "alpha", "waiting"),))
    doc = await preview(d)
    assert any(b["code"] == "IMPORT_TARGET_MISSING" for b in doc["blockers"])


async def test_b05_uncertain_budget_has_one_incomplete_summary_and_can_resume(daemon, monkeypatch):
    d, _ = daemon
    real = hub._write_record

    def unavailable(*args):
        raise OSError("synthetic temporarily unavailable transaction")

    monkeypatch.setattr(hub, "_write_record", unavailable)
    op, _ = d.ops.create(PERSON, **hub.apply_request(await preview(d)))
    for _ in range(len(hub.UNCERTAIN_RETRY_S) + 1):
        d.ops.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op["operation_id"],))
        await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "needs_attention"
    assert (
        d.ops.db.execute("SELECT COUNT(*) FROM api_events WHERE kind='hub_import.incomplete'").fetchone()[0]
        == 1
    )
    monkeypatch.setattr(hub, "_write_record", real)
    d.ops.resume(PERSON, op["operation_id"])
    await d.ops.drain(timeout=60)
    assert d.ops.get(op["operation_id"])["status"] == "succeeded"
    assert (
        d.ops.db.execute("SELECT COUNT(*) FROM api_events WHERE kind LIKE 'hub_import.%'").fetchone()[0] == 1
    )


async def test_b05_ambiguous_names_are_blocked_and_parser_reports_nested_blocks(daemon):
    d, src = daemon
    p = src / "Product/collision"
    p.mkdir()
    (p / "PROJECT.md").write_text("---\nname: Alpha\n---\n")
    doc = await preview(d)
    assert any(
        b["code"] == "IMPORT_RELATION_INVALID" and "ambiguous" in b["message"] for b in doc["blockers"]
    )
    with pytest.raises(ValueError, match="nested"):
        hub.parse_doc("---\nfield:\n  nested:\n    child: unsupported\n---\n")
    assert hub.parse_doc("---\nname : Value\n---\n")[0] == {"name": "Value"}


@pytest.mark.parametrize("mode", ["preview", "apply"])
@pytest.mark.parametrize("status", ["accepted", "running", "waiting_checks", "waiting_external", "uncertain",
                                   "needs_attention", "failed", "cancelled", "succeeded"])
def test_b05_cli_import_exit_code_requires_success(monkeypatch, capsys, mode, status):
    from bat_agent_connector import cli, task_daemon

    doc = {"source_id": "sample", "preview_id": "hip_" + "2" * 32,
           "digest": "fixture-digest", "can_apply": True}
    opid = "op_" + "2" * 32

    def request(method, **kw):
        if method == "hub_import_get":
            return {"preview": doc}
        return {"operation": {"operation_id": opid, "status": status, "result": {"preview": doc}}}

    monkeypatch.setattr(task_daemon, "request", request)
    args = ["hub", "import", "--source", "sample", "--" + mode]
    if mode == "apply":
        args += ["--preview-id", doc["preview_id"]]
    assert cli.main(args) == (0 if status == "succeeded" else 1)
    assert opid in capsys.readouterr().out


def test_b05_cli_successful_preview_with_blockers_is_nonzero(monkeypatch, capsys):
    from bat_agent_connector import cli, task_daemon

    doc = {"source_id": "sample", "preview_id": "hip_" + "3" * 32, "can_apply": False}
    opid = "op_" + "3" * 32
    monkeypatch.setattr(task_daemon, "request", lambda method, **kw: {"preview": doc} if method == "hub_import_get"
                        else {"operation": {"operation_id": opid, "status": "succeeded", "result": {"preview": doc}}})
    assert cli.main(["hub", "import", "--source", "sample", "--preview"]) == 1
    assert opid in capsys.readouterr().out


async def clean_reapply(d):
    """B05 invariant: a successful apply leaves source/destination baselines aligned."""
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert all(row["classification"] == "unchanged" for row in doc["records"]), [
        (row["key"], row["classification"]) for row in doc["records"]
    ]
    op = await apply(d, doc)
    assert op["error_code"] != "DESTINATION_CHANGED"
    return doc


async def test_b05_moved_hub_child_keeps_order_slot_and_reapplies(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    child, old_parent = mapped(d, "alpha", "child"), mapped(d, "alpha", "t")
    path = src / "Product/alpha/.ai/tasks/child.md"
    path.write_text(path.read_text().replace("parent: t", "parent: continued"))
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    await apply(d, doc)
    assert get(d, child)["parent_id"] == mapped(d, "alpha", "continued")
    assert child in wi._saved_order(d.ops.db, "items:" + mapped(d, "alpha"), old_parent)
    await clean_reapply(d)
    await clean_reapply(d)


async def test_b05_first_import_preserves_moved_local_project_slot(daemon):
    d, _ = daemon
    a = (await act(d, PERSON, "project.create", {}, {"name": "Local A"}))["result"]["project_id"]
    b = (await act(d, PERSON, "project.create", {}, {"name": "Local B"}))["result"]["project_id"]
    before = [x["project_id"] for x in wi.projects_list(d.ops.db)["projects"]]
    await act(d, PERSON, "project.order", {}, {"order": list(reversed(before))}, {"before": before})
    await act(d, PERSON, "project.update", {"project_id": b}, {"parent_id": a},
              {"expected_version": wi.project_get(d.ops.db, b)["project"]["version"]})
    assert b in wi._saved_order(d.ops.db, "projects", "")
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    await apply(d, doc)
    assert b in wi._saved_order(d.ops.db, "projects", "")
    await clean_reapply(d)


async def test_b05_import_order_events_do_not_poison_project_baseline(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    alpha = mapped(d, "alpha")
    (src / "Product/alpha/.ai/tasks/new.md").write_text("---\ntitle: New\n---\n")
    doc = await preview(d)
    assert next(r for r in doc["records"] if r["connector_id"] == alpha)["classification"] == "unchanged"
    await apply(d, doc)
    await clean_reapply(d)
    path = src / "Product/alpha/PROJECT.md"
    path.write_text(path.read_text().replace("Synthetic migration project", "Source description"))
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert next(r for r in doc["records"] if r["connector_id"] == alpha)["classification"] == "update"
    await apply(d, doc)
    await clean_reapply(d)


async def test_b05_local_task_reorder_is_group_state_not_a_project_edit(daemon):
    d, _ = daemon
    await apply(d, await preview(d))
    alpha = mapped(d, "alpha")
    before = [x["work_item_id"] for x in wi.project_get(d.ops.db, alpha)["work_items"]]
    await act(d, PERSON, "work_item.order", {"project_id": alpha}, {"order": list(reversed(before))},
              {"before": before})
    await clean_reapply(d)
    after = [x["work_item_id"] for x in wi.project_get(d.ops.db, alpha)["work_items"]]
    assert after == list(reversed(before))


async def test_b05_local_description_still_conflicts_after_group_only_import(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    alpha = mapped(d, "alpha")
    await act(d, PERSON, "project.update", {"project_id": alpha}, {"description": "Local description"},
              {"expected_version": wi.project_get(d.ops.db, alpha)["project"]["version"]})
    (src / "Product/alpha/.ai/tasks/new.md").write_text("---\ntitle: New\n---\n")
    await apply(d, await preview(d))
    path = src / "Product/alpha/PROJECT.md"
    path.write_text(path.read_text().replace("Synthetic migration project", "Source description"))
    doc = await preview(d)
    assert not doc["can_apply"]
    assert next(r for r in doc["records"] if r["connector_id"] == alpha)["classification"] == "conflict"


async def test_b05_local_session_and_pr_links_survive_source_update(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "t")
    d.ops.db.execute("""INSERT INTO sessions_observed(host,session_id,body,digest,provenance,api_access,
        first_seen_at,last_seen_at) VALUES('h1','s1',?,'d','manual','read_only',1,1)""",
                     (json.dumps({"title": "Synthetic session"}),))
    local_links = [("session", "h1/s1"), ("pull_request", "fixture/repository#17"),
                   ("external_url", "https://example.invalid/local")]
    for kind, ref in local_links:
        await act(d, PERSON, "work_item.link", {"work_item_id": wid}, {"kind": kind, "ref": ref})
    await act(d, PERSON, "work_item.link", {"work_item_id": wid},
              {"kind": "session", "ref": "h1/s1", "remove": True})
    before = wi.work_item_get(d.ops.db, wid)
    await clean_reapply(d)
    path = src / "Product/alpha/.ai/tasks/t.md"
    path.write_text(path.read_text().replace("Main request", "Source update"))
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert next(r for r in doc["records"] if r["connector_id"] == wid)["classification"] == "update"
    await apply(d, doc)
    after = wi.work_item_get(d.ops.db, wid)
    assert after["links"] == before["links"] and after["removed_links"] == before["removed_links"]
    assert get(d, wid)["title"] == "Source update"
    await clean_reapply(d)


async def test_b05_local_item_pin_is_group_state_and_survives_source_update(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "waiting")
    await act(d, PERSON, "work_item.pin", {"work_item_id": wid}, {"pinned": True}, {"before": False})
    await clean_reapply(d)
    path = src / "Product/alpha/.ai/tasks/waiting.md"
    path.write_text(path.read_text().replace("Waiting", "Source update"))
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert next(r for r in doc["records"] if r["connector_id"] == wid)["classification"] == "update"
    await apply(d, doc)
    assert get(d, wid)["pinned"] and get(d, wid)["title"] == "Source update"
    await clean_reapply(d)


async def test_b05_local_removal_of_source_url_still_conflicts(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "t")
    await act(d, PERSON, "work_item.link", {"work_item_id": wid},
              {"kind": "external_url", "ref": "https://example.invalid/reference", "remove": True})
    path = src / "Product/alpha/.ai/tasks/t.md"
    path.write_text(path.read_text().replace("Main request", "Source update"))
    doc = await preview(d)
    assert not doc["can_apply"]
    assert {x["code"] for x in doc["blockers"]} == {"IMPORT_CONFLICT"}
    assert next(r for r in doc["records"] if r["connector_id"] == wid)["classification"] == "conflict"


async def test_b05_legacy_link_event_baseline_does_not_block_reimport(daemon):
    d, src = daemon
    await apply(d, await preview(d))
    wid = mapped(d, "alpha", "t")
    mapping = d.ops.db.execute("SELECT baseline FROM hub_import_map WHERE connector_id=?", (wid,)).fetchone()
    baseline = json.loads(mapping[0])
    # Previous releases counted the import's link events after its created event.
    old_cursor = d.ops.db.execute("""SELECT MAX(seq) FROM api_events
        WHERE resource_type='work_item' AND resource_id=?""", (wid,)).fetchone()[0]
    assert old_cursor > baseline["event_seq"]
    baseline["event_seq"] = old_cursor
    d.ops.db.execute("UPDATE hub_import_map SET baseline=? WHERE connector_id=?", (json.dumps(baseline), wid))
    await clean_reapply(d)
    path = src / "Product/alpha/.ai/tasks/t.md"
    path.write_text(path.read_text().replace("Main request", "Source update"))
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert next(r for r in doc["records"] if r["connector_id"] == wid)["classification"] == "update"
    await apply(d, doc)
    await clean_reapply(d)


def test_b05_every_emitted_row_event_kind_is_explicitly_classified(tmp_path):
    from bat_agent_connector.task_journal import Journal

    emitted = set()
    for module in (wi, hub):
        for call in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if not isinstance(call, ast.Call):
                continue
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)
            if name == "_event":
                emitted.update(node.value for node in ast.walk(call.args[3])
                               if isinstance(node, ast.Constant) and isinstance(node.value, str)
                               and node.value.startswith(("project.", "work_item.")))
    classified = set().union(*hub.ROW_EDIT_EVENTS.values(), *hub.ROW_IGNORED_EVENTS.values())
    assert emitted and emitted <= classified, f"unclassified events: {emitted - classified}"
    # Item ordering is recorded on the project; both resource assignments ignore it.
    assert "work_item.ordered" in hub.ROW_IGNORED_EVENTS["project"]
    journal = Journal(tmp_path / "events.db")
    try:
        for resource in ("project", "work_item"):
            counted, ignored = hub.ROW_EDIT_EVENTS[resource], hub.ROW_IGNORED_EVENTS[resource]
            assert not counted & ignored
            for kind in counted | ignored:
                rid = "fixture-" + kind
                seq = journal.api_event(resource, rid, kind,
                                        {"operation_id": "other", "fields": ["name", "title"]})
                assert hub._event_seq(journal.db, resource, rid) == (seq if kind in counted else 0)
                assert hub._event_seq(journal.db, resource, rid, exclude="other") == 0
    finally:
        journal.close()


@pytest.mark.parametrize("resource", ["project", "work_item"])
@pytest.mark.parametrize("suffix", ["unknown", "future.ordered", "future.updated"])
def test_b05_unknown_row_event_kinds_fail_closed(tmp_path, resource, suffix):
    from bat_agent_connector.task_journal import Journal

    journal = Journal(tmp_path / "events.db")
    try:
        seq = journal.api_event(resource, "fixture", resource + "." + suffix, {"operation_id": "other"})
        assert hub._event_seq(journal.db, resource, "fixture") == seq
        assert hub._event_seq(journal.db, resource, "fixture", exclude="own") == seq
        assert hub._event_seq(journal.db, resource, "fixture", exclude="other") == 0
    finally:
        journal.close()


@pytest.mark.parametrize("resource", ["project", "work_item"])
def test_b05_row_marker_filters_in_sql_and_stops_at_newest_edit(tmp_path, monkeypatch, resource):
    from bat_agent_connector.task_journal import Journal

    journal = Journal(tmp_path / "events.db")
    db = journal.db
    mapped_field = "name" if resource == "project" else "title"
    ignored_kind = "project.ordered" if resource == "project" else "work_item.linked"
    counted_kind = "project.pinned" if resource == "project" else "work_item.state"
    journal.api_event(resource, "fixture", resource + ".created", {"operation_id": "older"})
    mapped_seq = journal.api_event(resource, "fixture", resource + ".updated",
                                  {"operation_id": "other", "fields": [mapped_field]})
    journal.api_event(resource, "fixture", resource + ".updated",
                      {"operation_id": "other", "fields": ["unmapped"]})
    own_seq = journal.api_event(resource, "fixture", counted_kind, {"operation_id": "own"})
    ignored_seq = journal.api_event(resource, "fixture", ignored_kind)
    db.execute("UPDATE api_events SET body='not JSON' WHERE seq=?", (ignored_seq,))
    parsed, visited, statements = [], [], []
    original_factory = db.row_factory

    def loads(body):
        parsed.append(body)
        return json.loads(body)

    def row_factory(cursor, row):
        visited.append(row[0])
        return original_factory(cursor, row)

    # Patch only this module's JSON binding; no global stdlib mutation.
    monkeypatch.setattr(hub, "json", SimpleNamespace(loads=loads))
    db.row_factory = row_factory
    db.set_trace_callback(statements.append)
    try:
        assert hub._event_seq(db, resource, "fixture") == own_seq
        assert visited == [own_seq] and not parsed
        visited.clear()
        assert hub._event_seq(db, resource, "fixture", exclude="own") == mapped_seq
        assert visited == [own_seq, mapped_seq + 1, mapped_seq] and len(parsed) == 3
        assert all("kind NOT IN" in sql and "ORDER BY seq DESC" in sql for sql in statements)
    finally:
        db.set_trace_callback(None)
        db.row_factory = original_factory
        journal.close()


@pytest.mark.parametrize("target", ["alpha", "fork", "rename"])
async def test_b05_project_name_clash_is_rechecked_inside_record_transaction(daemon, target):
    d, src = daemon
    if target == "rename":
        await apply(d, await preview(d))
        path = src / "Product/alpha/PROJECT.md"
        path.write_text(path.read_text().replace("name: Alpha", "name: Renamed"))
        for project in (src / "Product").glob("*/PROJECT.md"):
            project.write_text(project.read_text().replace("parent: Alpha", "parent: alpha")
                               .replace("derivedFrom: Alpha", "derivedFrom: alpha"))
    local = (await act(d, PERSON, "project.create", {}, {"name": "Local"}))["result"]["project_id"]
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    name = {"alpha": "Alpha", "fork": "Fork", "rename": "Renamed"}[target]
    await act(d, PERSON, "project.create", {}, {"name": name, "parent_id": local})
    op = await apply(d, doc, ok=False)
    assert (op["status"], op["error_code"]) == ("needs_attention", "NAME_TAKEN")
    assert d.ops.db.execute("SELECT COUNT(*) FROM projects WHERE name=? AND archived_at IS NULL", (name,)).fetchone()[0] == 1
    if target == "fork":
        assert len(hub.import_get(d.ops, op["operation_id"])["import"]["records"]) == 12
        assert d.ops.db.execute("SELECT COUNT(*) FROM hub_import_receipts WHERE operation_id=?", (op["operation_id"],)).fetchone()[0] == 3


async def test_b05_group_order_query_uses_the_event_resource_index(daemon):
    d, _ = daemon
    await apply(d, await preview(d))
    statements = []
    d.ops.db.set_trace_callback(statements.append)
    hub._group_state(d.ops.db, "sample", hub.record_key("item", "alpha"))
    d.ops.db.set_trace_callback(None)
    query = next(sql for sql in statements if sql.startswith("SELECT seq,body FROM api_events"))
    plan = [r[3] for r in d.ops.db.execute("EXPLAIN QUERY PLAN " + query)]
    assert any("SEARCH api_events USING INDEX" in detail for detail in plan), plan
    assert not any("SCAN api_events" in detail for detail in plan), plan


@pytest.mark.parametrize("kind", ["project", "task"])
async def test_b05_blank_display_names_fall_back_to_hub_ids(daemon, kind):
    d, src = daemon
    if kind == "project":
        shutil.rmtree(src)
        shutil.copytree(FIXTURE.parent / "date-id", src)
        path = src / "Product/dated/PROJECT.md"
        path.write_text(path.read_text().replace("name: Dated sample", "name:"))
        key, field, expected = hub.record_key("project", "dated"), "name", "dated"
    else:
        path = src / "Product/alpha/.ai/tasks/waiting.md"
        path.write_text(path.read_text().replace("title: Waiting", "title:"))
        key, field, expected = hub.record_key("item", "alpha", "waiting"), "title", "waiting"
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    assert next(r for r in doc["records"] if r["key"] == key)["record"]["values"][field] == expected
    await apply(d, doc)
    await clean_reapply(d)


@pytest.mark.parametrize("bad", ["Bad\tName", "Bad\u2028Name", "x" * 121])
async def test_b05_all_bad_records_are_reported_with_correct_format_or_limit_code(daemon, bad):
    d, src = daemon
    paths = ["Product/alpha/.ai/tasks/waiting.md", "Product/delta/.ai/tasks/t.md"]
    for relative in paths:
        (src / relative).write_text('---\ntitle: "' + bad + '"\n---\n')
    doc = await preview(d)
    code = "IMPORT_LIMIT_EXCEEDED" if len(bad) > 120 else "IMPORT_FORMAT_INVALID"
    assert not doc["can_apply"]
    assert {b["path"] for b in doc["blockers"] if b["code"] == code} == set(paths), doc["blockers"]
    if len(bad) <= 120:
        assert not any(b["code"] == "IMPORT_LIMIT_EXCEEDED" for b in doc["blockers"])
    assert d.ops.db.execute("SELECT COUNT(*) FROM hub_import_map").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["file", "symlink", "fifo"])
async def test_b05_product_stray_files_are_skipped_but_unsafe_entries_are_refused(daemon, kind):
    import os

    d, src = daemon
    path = src / "Product/notes.txt"
    if kind == "file":
        path.write_text("Synthetic note outside project records.\n")
    elif kind == "symlink":
        path.symlink_to(src / "Product/alpha")
    else:
        os.mkfifo(path)
    doc = await preview(d)
    if kind == "file":
        assert doc["can_apply"], doc["blockers"]
        assert {"code": "PROJECT_SKIPPED", "path": "Product/notes.txt"} in doc["warnings"]
        assert len(doc["records"]) == 12
        await apply(d, doc)
    else:
        assert not doc["can_apply"]
        assert any(b["code"] == "IMPORT_SOURCE_UNSAFE" for b in doc["blockers"])


async def test_b05_section_comments_are_filtered_and_raw_request_is_preserved(daemon):
    d, src = daemon
    body = "\n## 次にやること\n<!-- template guidance -->\n\nShip a fixture.\n\n## Acceptance\n  <!-- hidden guidance -->\nOne condition.\n\nAnother condition.\n"
    text = "---\ntitle: Waiting\n---\n" + body
    (src / "Product/alpha/.ai/tasks/waiting.md").write_text(text)
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    row = next(r for r in doc["records"] if r["key"] == hub.record_key("item", "alpha", "waiting"))
    assert row["record"]["values"]["goal"] == "Ship a fixture."
    assert row["record"]["values"]["acceptance"] == "One condition.\nAnother condition."
    assert row["record"]["values"]["request"] == body
    assert row["record"]["snapshot"]["text"] == text
    await apply(d, doc)
    item = get(d, mapped(d, "alpha", "waiting"))
    assert item["goal"] == "Ship a fixture."
    assert item["request"] == body and item["source"]["snapshot"]["text"] == text


@pytest.mark.parametrize("change", ["none", "request", "parent", "add_task", "project_description", "project_pin", "project_order"])
async def test_b05_unchanged_applicable_preview_never_fails_destination_preconditions(daemon, change):
    d, src = daemon
    await apply(d, await preview(d))
    if change == "request":
        path = src / "Product/alpha/.ai/tasks/t.md"
        path.write_text(path.read_text() + "\nAdditional synthetic request.\n")
    elif change == "parent":
        path = src / "Product/alpha/.ai/tasks/child.md"
        path.write_text(path.read_text().replace("parent: t", "parent: continued"))
    elif change == "add_task":
        (src / "Product/alpha/.ai/tasks/new.md").write_text("---\ntitle: New\n---\n")
    elif change == "project_description":
        path = src / "Product/alpha/PROJECT.md"
        path.write_text(path.read_text().replace("Synthetic migration project", "Updated source description"))
    elif change == "project_pin":
        (src / "_hub/project-pins.json").write_text('["delta", "alpha"]')
    elif change == "project_order":
        (src / "_hub/project-order.json").write_text('{"groups":{"": ["fork", "alpha", "delta"],"alpha":["beta"]}}')
    doc = await preview(d)
    assert doc["can_apply"], doc["blockers"]
    op = await apply(d, doc)
    assert op["error_code"] != "DESTINATION_CHANGED"
    await clean_reapply(d)
