"""Artifacts Part A (plan §08/12/13, B04): real local bytes/Git, mocked BAT; no real host writes."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from bat_agent_connector import api_auth, artifacts, checkpoints, registry, resource_policy, service
from bat_agent_connector.artifact_host import HELPER, ArtifactHost
from bat_agent_connector.artifacts import ArtifactStore
from bat_agent_connector.errors import InvokeTimeout, ResourceReadOnly
from bat_agent_connector.operations import AmbiguousOutcome, OperationError
from bat_agent_connector.task_journal import Journal
from tests.test_checkpoints import MANUAL, git
from tests.test_checkpoints import daemon as checkpoint_daemon
from tests.test_checkpoints import human as checkpoint_human

PERSON = api_auth.Principal("artifact-person", frozenset({"observe", "manage", "start", "operate", "approve"}))


@pytest.fixture
def human(tmp_path):
    return checkpoint_human.__wrapped__(tmp_path)


@pytest.fixture
def daemon(mock, human, tmp_path):
    yield from checkpoint_daemon.__wrapped__(mock, human, tmp_path)


class LocalArtifactHost(ArtifactHost):
    def __init__(self):
        super().__init__({"h1": "local-test"}, 10)
        self.calls = []

    def argv(self, host):
        return (sys.executable, "-c", HELPER)

    async def call(self, host, request, content=b""):
        self.calls.append(dict(request))
        return await super().call(host, request, content)


async def action(d, name, target=None, params=None, pre=None, key=None):
    op, _ = d.ops.create(PERSON, action=name, target=target or {}, params=params or {},
                         preconditions=pre or {}, idempotency_key=key or "test." + os.urandom(8).hex())
    await d.ops.drain(30)
    return d.ops.get(op["operation_id"])


async def reserve(d, data=b"immutable input", key="upload-one", target=None, pre=None, name="notes.txt"):
    return await action(d, "artifact.upload", target, {"display_name": name, "size_bytes": len(data),
                        "expected_digest": hashlib.sha256(data).hexdigest(), "media_type": "text/plain"}, pre, key)


def reader(data):
    stream = asyncio.StreamReader()
    stream.feed_data(data)
    stream.feed_eof()
    return stream


async def upload(d, data=b"immutable input", **kw):
    op = await reserve(d, data, **kw)
    if op["status"] == "waiting_external":
        await d.artifact_store.receive(PERSON, op["operation_id"], reader(data), len(data))
        await d.ops.drain(30)
        await asyncio.sleep(0)
        op = d.ops.get(op["operation_id"])
    assert op["status"] == "succeeded", op
    return {k: op["result"][k] for k in ("artifact_id", "revision", "digest")}


async def continuation(d, cp, refs, key="continue-one", **params):
    d.ops.context.setdefault("artifact_host", LocalArtifactHost())
    return await action(d, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]},
                        {"instructions": "Read the attached input and continue.", "artifacts": refs, **params},
                        {"expected_source_head_sha": cp["head_sha"], **params.pop("pre", {})}, key)


async def make_checkpoint(d, **params):
    await d.inventory.refresh_host("h1")
    op = await action(d, "checkpoint.create", {"host": "h1", "session_id": MANUAL}, {"last_n": 5, **params})
    assert op["status"] == "succeeded", op
    return checkpoints.get(d.journal.db, op["result"]["checkpoint_id"])


def sends(mock):
    return [x for x in mock.invokes if x["channel"] == "claude:send-message"]


async def test_artifact_upload_is_immutable_and_idempotent(daemon):
    ref = await upload(daemon)
    assert await upload(daemon) == ref
    assert daemon.artifact_store.read_content(ref["artifact_id"], 1) == b"immutable input"
    with pytest.raises(OperationError) as conflict:
        await reserve(daemon, b"different", key="upload-one")
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    ref2 = await upload(daemon, b"new", key="upload-two", target={"artifact_id": ref["artifact_id"]},
                        pre={"expected_latest_revision": 1})
    assert ref2["revision"] == 2 and ref2["artifact_id"] == ref["artifact_id"]
    assert daemon.artifact_store.read_content(ref["artifact_id"], 1) == b"immutable input"
    with pytest.raises(OperationError) as exc:
        await reserve(daemon, b"newer", key="upload-three", target={"artifact_id": ref["artifact_id"]}, pre={"expected_latest_revision": 1})
    assert exc.value.code == "REVISION_CONFLICT"
    assert len(list(daemon.artifact_store.root.glob("revisions/*/*/content"))) == 2


async def test_artifact_limits_include_partial_and_concurrent_reservations(daemon):
    daemon.artifact_store.settings = replace(daemon.artifact_store.settings, max_file_bytes=6, max_store_bytes=10)
    op = await reserve(daemon, b"abcdef")
    with pytest.raises(OperationError) as exc:
        await reserve(daemon, b"ghijkl", key="concurrent")
    assert exc.value.code == "ARTIFACT_STORE_FULL"
    with pytest.raises(OperationError, match="retry"):
        await daemon.artifact_store.receive(PERSON, op["operation_id"], reader(b"abcde"), 6)
    with pytest.raises(OperationError) as exc:
        await daemon.artifact_store.receive(PERSON, op["operation_id"], reader(b"abcdef"), 6)
    assert exc.value.code == "ARTIFACT_STORE_FULL"  # 6 reserved + 5 partial
    with pytest.raises(OperationError) as exc:
        await reserve(daemon, b"1234567", key="too-big")
    assert exc.value.code == "ARTIFACT_TOO_LARGE"


async def test_upload_publish_lost_reply_and_restart_read_back(daemon, monkeypatch):
    real = daemon.artifact_store.publish
    def lost(row):
        real(row)
        raise AmbiguousOutcome("publish ACK lost")
    monkeypatch.setattr(daemon.artifact_store, "publish", lost)
    op = await reserve(daemon)
    await daemon.artifact_store.receive(PERSON, op["operation_id"], reader(b"immutable input"), 15)
    await daemon.ops.drain(30)
    assert daemon.ops.get(op["operation_id"])["status"] == "uncertain"
    # A fresh store reopens the same durable intent, not a new upload.
    reopened = ArtifactStore(daemon.ops, daemon.artifact_store.settings)
    daemon.ops.context["artifact_store"] = reopened
    daemon.journal.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op["operation_id"],))
    await daemon.ops.drain(30)
    done = daemon.ops.get(op["operation_id"])
    assert done["status"] == "succeeded", json.dumps(done, indent=2)
    assert len(list(reopened.root.glob("revisions/*/*/content"))) == 1
    assert not (reopened.root / "staging" / op["operation_id"]).exists()


async def test_attachment_change_invalidates_work_item_approval(daemon):
    project = await action(daemon, "project.create", params={"name": "Attachments"})
    item = await action(daemon, "work_item.create", {"project_id": project["result"]["project_id"]}, {"title": "Review"})
    from bat_agent_connector import work_items
    wid = item["result"]["work_item_id"]
    old = work_items.work_item_get(daemon.journal.db, wid)["work_item"]
    approved = await action(daemon, "work_item.approve", {"work_item_id": wid}, pre={"expected_fingerprint": old["completion"]["fingerprint"]})
    assert approved["status"] == "succeeded"
    ref = await upload(daemon)
    updated = await action(daemon, "work_item.update", {"work_item_id": wid}, {"attachments": [{**ref, "role": "input"}]}, {"expected_version": work_items.work_item_get(daemon.journal.db, wid)["work_item"]["version"]})
    assert updated["status"] == "succeeded", updated
    current = work_items.work_item_get(daemon.journal.db, wid)["work_item"]
    assert current["completion"]["fingerprint"] != old["completion"]["fingerprint"] and not current["completion"]["approved"]
    assert daemon.journal.db.execute("SELECT owner_kind FROM artifact_references").fetchone()[0] == "work_item"


def test_artifact_migration_preserves_existing_journal_and_empty_manifests(tmp_path):
    path = tmp_path / "legacy.db"
    j = Journal(path)
    task = j.submit(project="p", host="h1", workspace="w", original_words="keep", idempotency_key="legacy")
    before = j.api_events(0, 10)
    j.db.execute("ALTER TABLE checkpoints DROP COLUMN attachments")
    j.db.execute("ALTER TABLE work_items DROP COLUMN attachments")
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    assert j.get(task["task_id"])["original_words"] == "keep"
    assert j.api_events(0, 10) == before
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    for table in ("checkpoints", "work_items"):
        assert next(x for x in j.db.execute(f"PRAGMA table_info({table})") if x[1] == "attachments")[4] == "'[]'"
    j.close()
    Journal(path).close()  # idempotent second open


class Writer:
    def __init__(self):
        self.data = bytearray()
    def write(self, data):
        self.data.extend(data)
    async def drain(self):
        pass


async def test_artifact_http_mcp_cli_contract_and_scopes(daemon, monkeypatch, tmp_path):
    from bat_agent_connector import cli, mcp_server
    with daemon.journal.tx():
        token = api_auth.issue(daemon.journal.db, PERSON.actor, list(PERSON.scopes))
        other = api_auth.issue(daemon.journal.db, "other", ["observe", "manage"])
    op = await reserve(daemon)
    class NoRead:
        async def read(self, _):
            raise AssertionError("body read before admission")
    base = {"host": "127.0.0.1", "content-type": "application/octet-stream", "content-length": "15"}
    path = op["external_refs"]["content_url"]
    for headers, status in ((base, 401), ({**base, "authorization": "Bearer " + other}, 403),
                            ({**base, "authorization": "Bearer " + token, "transfer-encoding": "chunked"}, 422),
                            ({**base, "authorization": "Bearer " + token, "content-length": "16"}, 422)):
        writer = Writer()
        await daemon.api.handle("POST", path, headers, NoRead(), writer)
        assert writer.data.startswith(f"HTTP/1.1 {status}".encode()), writer.data
    loop = asyncio.create_task(daemon.ops.loop())
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_API_TOKEN", token)
    try:
        args = cli.build_parser().parse_args(["artifact", "upload", str(tmp_path / "local.txt"), "--key", "cli", "--confirm"])
        (tmp_path / "local.txt").write_bytes(b"CLI content")
        assert await asyncio.to_thread(cli.cmd_artifact, args) == 0
        await daemon.ops.drain(30)
        mcp, fleet = mcp_server.build_server(daemon.fleet.config)
        tools = await mcp.list_tools()
        names = {x.name for x in tools}
        assert {"artifact_upload", "artifact_get", "artifacts_list"} <= names
        assert "artifact_materialize" not in names
        # The tool uses the same HTTP adapter after scoped OperationService intent.
        result = await mcp.call_tool("artifact_upload", {"display_name": "model.txt", "content_base64": "bW9kZWw=",
                                    "idempotency_key": "mcp", "confirm": True})
        assert result is not None
        await daemon.ops.drain(30)
        await fleet.close()
        refs = artifacts.list_artifacts(daemon.journal.db)["artifacts"]
        assert len(refs) == 3  # includes the pending HTTP admission reservation
        ready = next(x["revision"] for x in refs if x["revision"] and x["revision"]["state"] == "ready")
        writer = Writer()
        await daemon.api.handle("GET", ready["content_url"], {"host": "localhost", "authorization": "Bearer " + token}, NoRead(), writer)
        assert b"Content-Disposition: attachment" in writer.data and b"nosniff" in writer.data and b"no-store" in writer.data
    finally:
        server.close()
        await server.wait_closed()
        loop.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop


async def test_upload_window_expires_and_removes_only_its_own_staging(daemon):
    kept = await upload(daemon)
    expired = await reserve(daemon, b"partial data", key="expires")
    with pytest.raises(OperationError):
        await daemon.artifact_store.receive(PERSON, expired["operation_id"], reader(b"part"), 12)
    active = await reserve(daemon, b"active", key="active")
    daemon.journal.db.execute("UPDATE artifact_uploads SET deadline=0 WHERE operation_id=?", (expired["operation_id"],))
    daemon.ops.wake(expired["operation_id"])
    await daemon.ops.drain(30)
    await asyncio.sleep(0)
    failed = daemon.ops.get(expired["operation_id"])
    assert failed["status"] == "failed" and failed["error_code"] == "UPLOAD_EXPIRED"
    assert not (daemon.artifact_store.root / "staging" / expired["operation_id"]).exists()
    assert daemon.ops.get(active["operation_id"])["status"] == "waiting_external"
    assert daemon.artifact_store.read_content(kept["artifact_id"], 1) == b"immutable input"


async def test_operation_wake_only_moves_waiting_external(daemon):
    op = await reserve(daemon)
    db = daemon.journal.db
    for state in ("needs_attention", "uncertain", "accepted", "running", "failed", "succeeded", "cancelled"):
        db.execute("UPDATE operations SET status=?,next_run_at=12345 WHERE operation_id=?", (state, op["operation_id"]))
        daemon.ops.wake(op["operation_id"])
        assert db.execute("SELECT status,next_run_at FROM operations WHERE operation_id=?", (op["operation_id"],)).fetchone()[1] == 12345
    db.execute("UPDATE operations SET status='waiting_external',next_run_at=12345 WHERE operation_id=?", (op["operation_id"],))
    daemon.ops.wake(op["operation_id"])
    assert db.execute("SELECT next_run_at FROM operations WHERE operation_id=?", (op["operation_id"],)).fetchone()[0] == 0
    # No new state-transition event was written by wake itself.


async def test_materialized_inputs_are_git_excluded_and_inside_the_worktree(daemon, mock, human):
    daemon.ops.context["artifact_host"] = LocalArtifactHost()
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon, artifacts=[ref])
    done = await continuation(daemon, cp, [ref])
    assert done["status"] == "succeeded", done
    wt = done["result"]["worktree_path"]
    mat = done["result"]["materializations"][0]
    assert Path(mat["managed_path"]).is_relative_to(wt)
    assert Path(mat["managed_path"]).read_bytes() == b"immutable input"
    assert git(wt, "--no-optional-locks", "status", "--porcelain") == ""
    common = Path(git(wt, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    assert (common / "info/exclude").read_text().count("/.batc-inputs/") == 1
    prompt = sends(mock)[0]["params"]["prompt"]
    assert ".batc-inputs/" in prompt and ref["digest"] in prompt
    assert str(human) not in prompt
    assert cp["artifacts"] == [ref]


async def test_artifact_policy_refuses_escape_before_any_host_write(daemon, mock):
    hc = daemon.fleet.config.host("h1")
    root = hc.managed_roots[0] + "/clones/checkpoint-example"
    op = "op_" + "a" * 32
    wt = root + "/.bat-worktrees/batc-cp-" + op[3:15]
    for relative in ("../escape", ".batc-inputs/../../outside", ".batc-inputs/art_" + "a" * 32 + "-r1/../bad", ".batc-inputs/art_" + "a" * 32 + "-r1/.git"):
        with pytest.raises(ResourceReadOnly):
            resource_policy.check_artifact_destination(hc, root, wt, "batc-cp-" + op[3:15], relative)
    assert not sends(mock)


async def test_B04_transfer_interrupted_before_dispatch(daemon, mock):
    adapter = LocalArtifactHost()
    daemon.ops.context["artifact_host"] = adapter
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon)
    real = adapter.call
    async def interrupted(host, request, content=b""):
        if request["mode"] == "receive" and request["attempt"] == 1:
            return await real(host, request, content[:3])
        return await real(host, request, content)
    adapter.call = interrupted
    op = await continuation(daemon, cp, [ref])
    assert op["status"] == "needs_attention" and op["error_code"] == "ARTIFACT_SIZE_MISMATCH", op
    assert not sends(mock) and not registry.list_entries("h1")
    daemon.ops.resume(PERSON, op["operation_id"])
    await daemon.ops.drain(30)
    done = daemon.ops.get(op["operation_id"])
    assert done["status"] == "succeeded" and len(sends(mock)) == 1, done
    assert done["result"]["materializations"][0]["attempt"] == 2


@pytest.mark.parametrize("changed,code", [("digest", "ARTIFACT_DIGEST_MISMATCH"), ("size_bytes", "ARTIFACT_SIZE_MISMATCH"), ("path", "BINDING_MISMATCH")])
async def test_B04_digest_size_or_path_mismatch_blocks_first_command(daemon, mock, changed, code):
    adapter = LocalArtifactHost()
    daemon.ops.context["artifact_host"] = adapter
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon)
    real = adapter.call
    async def mismatch(host, request, content=b""):
        result = await real(host, request, content)
        if request["mode"] == "verify":
            result[changed] = 999 if changed == "size_bytes" else "wrong"
        return result
    adapter.call = mismatch
    op = await continuation(daemon, cp, [ref])
    assert op["status"] == "needs_attention" and op["error_code"] == code, op
    assert not sends(mock)
    assert op["external_refs"]["materializations"][0]["state"] == "blocked"


async def test_B04_source_advanced_after_preview_keeps_selection(daemon, mock, human):
    adapter = LocalArtifactHost()
    daemon.ops.context["artifact_host"] = adapter
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon)
    git(human, "commit", "-q", "--allow-empty", "-m", "source advanced")
    op = await continuation(daemon, cp, [ref])
    assert op["status"] == "needs_attention" and op["error_code"] == "SOURCE_MOVED", op
    assert not sends(mock) and not adapter.calls
    confirmed = await action(daemon, "checkpoint.continue.revalidate", {"operation_id": op["operation_id"]},
                             {"observed_source_head_sha": git(human, "rev-parse", "HEAD")},
                             {"expected_input_manifest_digest": op["external_refs"]["input_manifest_digest"]})
    assert confirmed["status"] == "succeeded", confirmed
    await daemon.ops.drain(30)
    done = daemon.ops.get(op["operation_id"])
    assert done["status"] == "succeeded" and done["params"]["artifacts"] == [ref]
    assert done["result"]["base_commit"] == cp["commit_sha"] and len(sends(mock)) == 1


@pytest.mark.parametrize("lost_step", ["start", "send"])
async def test_B04_resume_after_start_or_send_ack_loss_never_duplicates_execution(daemon, mock, monkeypatch, lost_step):
    from bat_agent_connector import orchestrate
    adapter = LocalArtifactHost()
    daemon.ops.context["artifact_host"] = adapter
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon)
    module, name = (orchestrate, "session_start") if lost_step == "start" else (service, "session_send")
    real = getattr(module, name)
    async def lost(*args, **kwargs):
        await real(*args, **kwargs)
        raise InvokeTimeout("accepted, reply lost")
    monkeypatch.setattr(module, name, lost)
    op = await continuation(daemon, cp, [ref])
    assert op["status"] == "uncertain", op
    monkeypatch.setattr(module, name, real)
    daemon.journal.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op["operation_id"],))
    await daemon.ops.drain(30)
    done = daemon.ops.get(op["operation_id"])
    assert done["status"] == "succeeded", done
    assert len([x for x in mock.invokes if x["channel"] == "claude:start-session"]) == 1
    assert len(sends(mock)) == 1


async def test_B04_inputs_changed_after_start_keep_session_and_block_send(daemon, mock, monkeypatch):
    from bat_agent_connector import orchestrate
    adapter = LocalArtifactHost()
    daemon.ops.context["artifact_host"] = adapter
    ref = await upload(daemon)
    cp = await make_checkpoint(daemon)
    real = orchestrate.session_start
    async def tamper(*args, **kw):
        result = await real(*args, **kw)
        path = next(Path(kw["cwd_override"]).glob(".batc-inputs/*/notes.txt"))
        path.write_bytes(b"changed input")
        return result
    monkeypatch.setattr(orchestrate, "session_start", tamper)
    op = await continuation(daemon, cp, [ref])
    assert op["status"] == "needs_attention" and op["error_code"] == "ARTIFACT_SIZE_MISMATCH", op
    assert not sends(mock) and len(registry.list_entries("h1")) == 1
    Path(op["external_refs"]["materializations"][0]["managed_path"]).write_bytes(b"immutable input")
    daemon.ops.resume(PERSON, op["operation_id"])
    await daemon.ops.drain(30)
    done = daemon.ops.get(op["operation_id"])
    assert done["status"] == "succeeded", done
    assert len([x for x in mock.invokes if x["channel"] == "claude:start-session"]) == 1 and len(sends(mock)) == 1
