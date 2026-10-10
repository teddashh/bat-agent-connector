"""External testimony through the real owner, transports and temporary JSON bytes."""
from __future__ import annotations

import asyncio
import json

import pytest

from bat_agent_connector import api_auth, cli, platform_files, registry, service, verification
from bat_agent_connector import verification_operations as subject
from bat_agent_connector.errors import WriteRefused
from bat_agent_connector.mcp_server import build_server
from bat_agent_connector.operations import NO_KEY_PREFIX, OperationError, OperationService
from tests import test_api_v1 as api
from tests.conftest import adopt
from tests.operation_helpers import settle_operations
from tests.test_interrupt_operations import mcp_result, rpc
from tests.test_mcp_principal import call as call_tool

daemon, served = api.daemon, api.served
SID = api.MANUAL
PERSON = api_auth.Principal("test-witness", frozenset({"operate", "observe"}))
PARAMS = {"candidate_commit": "abc1234", "command": "uv run pytest -q", "exit_code": 0,
          "environment": "temporary mock host", "log_ref": "artifacts/test-run.log"}


def intent(**extra):
    return {"action": subject.ACTION, "target": {"host": "h1", "session_id": SID},
            "params": dict(PARAMS), "idempotency_key": "verification-key", **extra}


async def submit(d, **extra):
    op, _ = d.ops.create(PERSON, **intent(**extra))
    await settle_operations(d.ops)
    return d.ops.get(op["operation_id"])


@pytest.mark.parametrize("managed", [False, True])
async def test_testimony_preserves_actor_without_runtime_or_trusted_effect(daemon, mock, managed):
    if managed:
        adopt(SID)
    before = registry.get("h1", SID)
    out = await submit(daemon)
    assert out["status"] == "succeeded", out
    assert out["result"]["actor"] == PERSON.actor and out["result"]["verified_candidate"] is True
    assert verification.get("h1", SID) == {k: v for k, v in out["result"].items() if k != "verified_candidate"}
    assert registry.get("h1", SID) == before and not api.write_frames(mock)
    assert not daemon.journal.db.execute("SELECT 1 FROM observed_verifications").fetchone()
    assert not daemon.journal.db.execute("SELECT 1 FROM commands").fetchone()
    saved = verification.path().read_bytes()
    reads = list(mock.invokes)
    again = await submit(daemon)
    assert again == out and verification.path().read_bytes() == saved and mock.invokes == reads
    await daemon.fleet.close()


@pytest.mark.parametrize("first", ["http", "rpc", "mcp", "cli"])
async def test_all_transports_share_exact_key_actor_and_complete_testimony(served, mock, monkeypatch, capsys, first):
    d, port = served
    tok = api.token(d, PERSON.actor, "operate", "observe")
    monkeypatch.setenv("BATC_API_TOKEN", tok)
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setattr(cli, "load_config", lambda _: d.fleet.config)
    server, fleet = build_server(d.fleet.config, principal_only=True)
    request = {"host": "h1", "session_id": SID, **PARAMS, "confirm": True, "idempotency_key": "verification-key"}

    async def through(door):
        if door == "http":
            code, out = await api.http(port, "POST", "/api/v1/operations", tok=tok, body=intent())
            assert code in {200, 202}, out
            await settle_operations(d.ops)
            return out["operation"]["operation_id"]
        if door == "rpc":
            code, body = await rpc(port, tok, "session_record_verification", request)
            assert code == 200, body
            out = body["result"]
        elif door == "mcp":
            out = await mcp_result(server, "session_record_verification", request)
        else:
            args = ["--json", "record-verification", "h1", SID, "--commit", PARAMS["candidate_commit"],
                    "--command", PARAMS["command"], "--exit-code", "0", "--environment", PARAMS["environment"],
                    "--log-ref", PARAMS["log_ref"], "--confirm", "--key", "verification-key"]
            assert await asyncio.to_thread(cli.main, args) == 0
            out = json.loads(capsys.readouterr().out)
        assert out["operation_status"] == "succeeded" and out["actor"] == PERSON.actor
        assert out["verified_candidate"] is True and out["command"] == PARAMS["command"]
        return out["operation_id"]

    try:
        oid = await through(first)
        saved = verification.path().read_bytes()
        d.fleet.config.host("h1").orchestrate = False
        for door in ("http", "rpc", "mcp", "cli"):
            assert await through(door) == oid
        assert saved == verification.path().read_bytes() and not api.write_frames(mock)
    finally:
        await fleet.close()


@pytest.mark.parametrize("field,value", [("command", []), ("environment", {}), ("log_ref", None),
    ("candidate_commit", True), ("exit_code", False), ("exit_code", 1.5), ("command", " "),
    ("command", "a" * 4001)])
async def test_http_malformed_admission_has_no_record_operation_or_bat_read(served, mock, field, value):
    d, port = served
    tok = api.token(d, "caller", "operate")
    code, out = await api.http(port, "POST", "/api/v1/operations", tok=tok,
                              body=intent(params={**PARAMS, field: value}))
    assert code == 422 and out["error"]["code"] == "INVALID_PARAMS", out
    assert not d.ops.list()["operations"] and not verification.path().exists() and not mock.invokes


async def test_no_key_independent_reserved_prefix_and_conflict(daemon, mock):
    req = {"host": "h1", "session_id": SID, **PARAMS, "confirm": True}
    first = await subject.legacy(daemon.ops, PERSON, req, entry="rpc")
    second = await subject.legacy(daemon.ops, PERSON, req, entry="rpc")
    assert first["operation_id"] != second["operation_id"]
    assert first["idempotency_key"] is None and not first["idempotency_enabled"]
    assert NO_KEY_PREFIX not in json.dumps(first)
    with pytest.raises(OperationError, match="INVALID_IDEMPOTENCY_KEY"):
        await subject.legacy(daemon.ops, PERSON, {**req, "idempotency_key": NO_KEY_PREFIX + "forged"}, entry="rpc")
    await submit(daemon)
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await submit(daemon, params={**PARAMS, "exit_code": 1})
    await daemon.fleet.close()


@pytest.mark.parametrize("change", ["head", "dirty", "task", "registry", "cwd", "lease"])
async def test_final_observation_change_prevents_local_record(daemon, mock, monkeypatch, change):
    original = subject._source
    calls = 0
    async def altered(ctx):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "head":
                mock.git_logs = {"/srv/demo": [{"hash": "b" * 40}]}
            elif change == "dirty":
                mock.git_status["/srv/demo"] = [{"status": "M", "file": "result.txt"}]
            elif change == "task":
                adopt(SID, task_id="task-new")
            elif change == "registry":
                adopt(SID)
            elif change == "cwd":
                mock.ws_doc["terminals"][0]["cwd"] = "/srv/another"
            else:
                daemon.journal.owner_valid = lambda: False
        return await original(ctx)
    monkeypatch.setattr(subject, "_source", altered)
    out = await submit(daemon)
    assert out["status"] == "failed", out
    assert not verification.path().exists() and not api.write_frames(mock)
    await daemon.fleet.close()


async def test_external_task_record_refuses_before_admission_even_without_registry_mark(daemon, mock):
    task = daemon.journal.submit(project="demo", host="h1", workspace="ws-1",
                                 original_words="owned", idempotency_key="owned")
    daemon.journal.db.execute("UPDATE tasks SET session_id=? WHERE task_id=?", (SID, task["task_id"]))
    with pytest.raises(Exception, match="TASK_OWNED_CONTROL_REQUIRED"):
        await submit(daemon)
    assert not daemon.ops.list()["operations"] and not verification.path().exists() and not mock.invokes
    await daemon.fleet.close()


async def test_json_replace_before_step_receipt_reconciles_original_without_overwriting_newer(daemon, mock, monkeypatch):
    original = daemon.ops._step_done
    class ProcessCrash(BaseException):
        pass
    def lose(oid, name, result, **kwargs):
        if name == "verification.record":
            raise ProcessCrash("fixture process exit after JSON atomic replace")
        return original(oid, name, result, **kwargs)
    monkeypatch.setattr(daemon.ops, "_step_done", lose)
    monkeypatch.setattr(daemon.ops, "kick", lambda: None)
    op, _ = daemon.ops.create(PERSON, **intent())
    with pytest.raises(ProcessCrash):
        await daemon.ops._execute(op["operation_id"])
    old = verification.get("h1", SID)
    assert old and daemon.ops.get(op["operation_id"])["status"] == "running"
    # Recreate the worker from its persisted journal, with no old active task/memory.
    resumed = OperationService(daemon.journal, actions=list(daemon.ops.actions.values()))
    resumed.context.update(daemon.ops.context)
    daemon.ops = resumed
    newer = verification.record("h1", SID, **{**PARAMS, "exit_code": 1}, actor="new-witness")
    saved = verification.path().read_bytes()
    daemon.fleet.config.host("h1").orchestrate = False
    async def no_source(*args):
        pytest.fail("receipt recovery must precede changed-source reads")
    monkeypatch.setattr(service, "_resolve_session", no_source)
    await settle_operations(daemon.ops)
    result = daemon.ops.get(op["operation_id"])
    assert result["status"] == "succeeded", result
    assert result["result"] == {**old, "verified_candidate": True}
    assert verification.get("h1", SID) == newer and verification.path().read_bytes() == saved
    assert not api.write_frames(mock)
    await daemon.fleet.close()


async def test_started_step_without_json_receipt_remains_unknown_without_rewrite(daemon, mock):
    out = await submit(daemon)
    saved = json.loads(verification.path().read_text())
    saved["operation_receipts"].clear()
    verification.path().write_text(json.dumps(saved))
    before = verification.path().read_bytes()
    daemon.ops.db.execute("UPDATE operation_steps SET status='started',response=NULL WHERE operation_id=? AND name='verification.record'", (out["operation_id"],))
    daemon.ops.db.execute("UPDATE operations SET status='running',result=NULL,next_run_at=0 WHERE operation_id=?", (out["operation_id"],))
    await settle_operations(daemon.ops)
    assert daemon.ops.get(out["operation_id"])["status"] == "uncertain"
    assert verification.path().read_bytes() == before and not api.write_frames(mock)
    await daemon.fleet.close()


@pytest.mark.parametrize("raw", ["null", "[]", "{}", '{"records":[],"records":[]}',
    '{"records":[{}]}', '{"records":[],"operation_receipts":{"op_bad":{}}}', '{"records":[] ,"unexpected":1}'])
def test_invalid_store_never_overwrites_original_bytes(raw):
    p = verification.path()
    platform_files.atomic_write(p, raw.encode())
    with pytest.raises(WriteRefused, match="invalid"):
        verification.record("h1", SID, **PARAMS, actor="witness")
    assert p.read_text() == raw


@pytest.mark.parametrize("status", [None, {}, [None], ["bad"], [{"unexpected": True}]])
async def test_nonempty_or_malformed_bat_status_is_not_a_clean_report(daemon, mock, status):
    mock.git_status["/srv/demo"] = status
    out = await submit(daemon)
    assert out["status"] == "failed" and out["error_code"] == "VERIFICATION_NOT_CLEAN"
    assert not verification.path().exists() and not api.write_frames(mock)
    await daemon.fleet.close()


@pytest.mark.parametrize("credentials", ["missing", "observe"])
async def test_principal_mcp_cannot_borrow_operator_or_admin_authority(served, mock, monkeypatch, credentials):
    d, port = served
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_TASK_ADMIN_TOKEN_FILE", str(d.admin_token_path))
    if credentials == "missing":
        monkeypatch.delenv("BATC_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BATC_API_TOKEN", api.token(d, "reader", "observe"))
    server, fleet = build_server(d.fleet.config, principal_only=True)
    try:
        out = await call_tool(server, "session_record_verification", {
            "host": "h1", "session_id": SID, **PARAMS, "confirm": True})
        assert ("own API token" if credentials == "missing" else "FORBIDDEN") in out
        assert not d.ops.list()["operations"] and not mock.invokes and not verification.path().exists()
    finally:
        await fleet.close()


def cli_args():
    return ["record-verification", "h1", SID, "--commit", PARAMS["candidate_commit"],
            "--command", PARAMS["command"], "--exit-code", "0", "--environment", PARAMS["environment"],
            "--log-ref", PARAMS["log_ref"], "--confirm", "--key", "cli-key"]


def test_cli_read_only_refuses_before_loading_configuration(monkeypatch, capsys):
    def forbidden(*args):
        pytest.fail("read-only must refuse before configuration or central calls")
    monkeypatch.setattr(cli, "load_config", forbidden)
    assert cli.main(["--read-only", *cli_args()]) == 1
    assert "read-only" in capsys.readouterr().err


async def test_cli_reports_terminal_failure_and_same_key_preserves_it(served, mock, monkeypatch, capsys):
    d, port = served
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_API_TOKEN", api.token(d, "operator", "operate"))
    monkeypatch.setattr(cli, "load_config", lambda _: d.fleet.config)
    mock.git_status["/srv/demo"] = [{"status": "M", "file": "result.txt"}]
    assert await asyncio.to_thread(cli.main, ["--json", *cli_args()]) == 1
    first = json.loads(capsys.readouterr().out)
    assert first["operation_status"] == "failed" and first["operation_error_code"] == "VERIFICATION_NOT_CLEAN"
    mock.git_status["/srv/demo"] = []
    assert await asyncio.to_thread(cli.main, ["--json", *cli_args()]) == 1
    assert json.loads(capsys.readouterr().out) == first
    assert not verification.path().exists() and not api.write_frames(mock)


async def test_selector_is_fixed_after_original_intent_replay(daemon, mock, monkeypatch):
    request = {"host": "h1", "session_id": "sess-claude", **PARAMS,
               "confirm": True, "idempotency_key": "fixed-selector"}
    first = await subject.legacy(daemon.ops, PERSON, request, entry="rpc")
    assert first["session_id"] == SID and first["operation_status"] == "succeeded"
    op = daemon.ops.get(first["operation_id"])
    assert op["target"]["session_id"] == "sess-claude"
    assert op["external_refs"]["resolved_target"]["session_id"] == SID
    async def changed(*args):
        pytest.fail("keyed replay must not resolve a later selector")
    monkeypatch.setattr(service, "_resolve_session", changed)
    assert await subject.legacy(daemon.ops, PERSON, request, entry="rpc") == first
    await daemon.fleet.close()


def test_receipt_digest_and_original_time_are_immutable_and_internal_records_preserve_it():
    oid = "op_" + "a" * 32
    row = verification.record("h1", SID, **PARAMS, actor="first", operation_id=oid, recorded_at=10.0)
    second = verification.record("h1", SID, **{**PARAMS, "exit_code": 1}, actor="internal")
    before = verification.path().read_bytes()
    assert verification.record(**row, operation_id=oid) == row
    assert verification.get("h1", SID) == second and verification.path().read_bytes() == before
    with pytest.raises(WriteRefused, match="conflicts"):
        verification.record(**{**row, "recorded_at": 11.0}, operation_id=oid)
    doc = json.loads(before)
    doc["operation_receipts"][oid]["record"]["exit_code"] = 1
    verification.path().write_text(json.dumps(doc))
    corrupt = verification.path().read_bytes()
    with pytest.raises(WriteRefused, match="invalid"):
        verification.record("h1", SID, **PARAMS, actor="third")
    assert verification.path().read_bytes() == corrupt


def test_oversized_existing_store_is_not_truncated(monkeypatch):
    verification.record("h1", SID, **PARAMS, actor="first")
    before = verification.path().read_bytes()
    monkeypatch.setattr(verification, "MAX_BYTES", len(before) - 1)
    with pytest.raises(WriteRefused, match="invalid"):
        verification.record("h1", SID, **PARAMS, actor="second")
    assert verification.path().read_bytes() == before


async def test_original_actor_without_current_operate_cannot_replay_or_control(daemon, mock):
    out = await submit(daemon)
    reader = api_auth.Principal(PERSON.actor, frozenset({"observe"}))
    with pytest.raises(OperationError, match="FORBIDDEN"):
        daemon.ops.create(reader, **intent())
    with pytest.raises(OperationError, match="FORBIDDEN"):
        daemon.ops.cancel(reader, out["operation_id"])
    assert not api.write_frames(mock)
    await daemon.fleet.close()
