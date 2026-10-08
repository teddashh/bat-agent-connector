"""A05/A07/A09: operation admission and the single Task Service authority."""

import json

import pytest

from bat_agent_connector import registry, service
from bat_agent_connector.errors import OwnerConflict
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config


def test_a09_same_fleet_different_journals_refuses_second_owner(mock, tmp_path):
    config = make_config(mock, writes=True, orchestrate=True)
    first = TaskDaemon(config, tmp_path / "first" / "tasks.db")
    second = TaskDaemon(config, tmp_path / "second" / "tasks.db")
    first.acquire_owner()
    pointer = registry.registry_path().parent / service.TASK_SERVICE_POINTER
    before = pointer.read_bytes()
    try:
        with pytest.raises(OwnerConflict) as caught:
            second.acquire_owner()
        assert caught.value.code == "OWNER_CONFLICT"
        assert caught.value.owner == json.loads(before)
        assert pointer.read_bytes() == before
        assert not second._db_path.parent.exists()  # no journal/token/provider initialization
        first.journal.db.execute("UPDATE daemon_owner SET heartbeat_at=0")
        with pytest.raises(OwnerConflict):
            second.acquire_owner()  # a stale heartbeat cannot steal a live flock
    finally:
        first.journal.close()
    second.acquire_owner()
    assert json.loads(pointer.read_text())["db_path"] == str(second._db_path.resolve())
    assert json.loads(pointer.read_text())["owner_id"] != json.loads(before)["owner_id"]
    second.journal.close()


def test_a09_restart_releases_lease_and_reuses_journal(mock, tmp_path):
    config = make_config(mock, writes=True, orchestrate=True)
    path = tmp_path / "tasks.db"
    first = TaskDaemon(config, path)
    task = first.journal.submit(project="p", host="h1", workspace="w", original_words="do it",
                                idempotency_key="original")
    first.journal.close()
    second = TaskDaemon(config, path)
    try:
        assert second.journal.get(task["task_id"])["original_words"] == "do it"
        assert second.journal.db.execute("SELECT owner_id FROM daemon_owner").fetchone()[0] == second._owner_id
    finally:
        second.journal.close()


def test_a09_owner_lock_precedes_initialization_and_pointer(mock, tmp_path, monkeypatch):
    config = make_config(mock, writes=True, orchestrate=True)
    first = TaskDaemon(config, tmp_path / "first" / "tasks.db")
    second = TaskDaemon(config, tmp_path / "second" / "tasks.db")
    original = first._initialize

    def initializing():
        assert not (registry.registry_path().parent / service.TASK_SERVICE_POINTER).exists()
        assert not first._db_path.exists()
        with pytest.raises(OwnerConflict) as caught:
            second.acquire_owner()
        assert caught.value.code == "OWNER_CONFLICT"
        assert caught.value.owner["lease_path"] == str(registry.registry_path().parent / "task-daemon.lock")
        assert not second._db_path.parent.exists()
        original()
    monkeypatch.setattr(first, "_initialize", initializing)
    first.acquire_owner()
    first.journal.close()

from bat_agent_connector import api_auth, lifecycle  # noqa: E402
from bat_agent_connector.channels import GUARDED_CHANNELS, ORCHESTRATE_CHANNELS, WRITE_CHANNELS  # noqa: E402
from bat_agent_connector.errors import ConnectionLost, InvokeTimeout, TaskControlRefused  # noqa: E402
from bat_agent_connector.operations import OpContext, OperationError  # noqa: E402
from tests.conftest import adopt  # noqa: E402

SID = "sess-claude-0001"


@pytest.fixture
async def owned(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock, writes=True, orchestrate=True, managed_roots=["/srv"],
                                    default_permission_mode="allow_all", safety={"write_min_interval_s": 0}),
                        tmp_path / "tasks.db")
    task = daemon.journal.submit(project="p", host="h1", workspace="demo-project", original_words="do it",
                                 engine="goose", idempotency_key="fixture")
    daemon.journal.db.execute("UPDATE tasks SET state='accepted',session_id=? WHERE task_id=?", (SID, task["task_id"]))
    adopt(SID, task_id=task["task_id"], role="lead", agent_preset="claude-code")
    yield daemon, task["task_id"]
    await daemon.ops.drain()
    await daemon.fleet.close()
    await daemon.inventory.close()
    daemon.journal.close()


def writes(mock):
    return [r for r in mock.invokes if r["channel"] in WRITE_CHANNELS | ORCHESTRATE_CHANNELS | GUARDED_CHANNELS]


@pytest.mark.parametrize("action", ["send", "answer", "interrupt", "permissions"])
@pytest.mark.parametrize("error", [ConnectionLost, InvokeTimeout])
@pytest.mark.parametrize("after_frame", [False, True], ids=["before_frame", "after_frame"])
async def test_a07_failure_before_any_frame_rejects_command_without_uncertain_task(owned, mock, monkeypatch,
                                                                                 action, error, after_frame):
    d, tid = owned
    prior = d.journal.get(tid)
    mock.states[SID]["pendingAskUser"] = {"toolUseId": "ask-1", "questions": [{"question": "Choice?"}]}
    handlers = {"send": (service.session_send, {"text": "one instruction"}),
                "answer": (service.session_answer, {"answers": ["yes"], "tool_use_id": "ask-1"}),
                "interrupt": (service.session_interrupt, {}),
                "permissions": (lifecycle.session_set_permissions, {"mode": "allow_all"})}
    fn, params = handlers[action]
    original_lookup = service._resolve_session
    client = d.fleet.client("h1")
    original_roundtrip = client._roundtrip

    async def fail_lookup(*args, **kwargs):
        # The outer admission lookup succeeds; fail the lower-layer lookup after command intent.
        if d.journal.commands(tid):
            raise error("session lookup failed")
        return await original_lookup(*args, **kwargs)

    async def lose_reply(frame, timeout):
        result = await original_roundtrip(frame, timeout)
        if frame["channel"] in WRITE_CHANNELS | ORCHESTRATE_CHANNELS | GUARDED_CHANNELS:
            raise error("write reply lost")
        return result

    with monkeypatch.context() as patch:
        if after_frame:
            patch.setattr(client, "_roundtrip", lose_reply)
        else:
            patch.setattr(service, "_resolve_session", fail_lookup)
            patch.setattr(lifecycle, "_resolve_session", fail_lookup)
        with pytest.raises(error):
            await fn(d.fleet, "h1", SID, confirm=True, **params)
    command = d.journal.commands(tid)[-1]
    assert command["status"] == ("uncertain" if after_frame else "rejected")
    task = d.journal.get(tid)
    assert task["state"] == ("uncertain" if after_frame else prior["state"])
    assert task["control_version"] == prior["control_version"]
    assert len(writes(mock)) == int(after_frame)
    if after_frame:
        with pytest.raises(TaskControlRefused, match="TASK_COMMAND_PENDING"):
            await service.session_interrupt(d.fleet, "h1", SID, confirm=True)
        assert len(d.journal.commands(tid)) == 1
    else:
        await fn(d.fleet, "h1", SID, confirm=True, **params)
        assert len(d.journal.commands(tid)) == 2
        assert len(writes(mock)) == 1


@pytest.mark.parametrize("action", ["send", "answer", "interrupt", "permissions"])
@pytest.mark.parametrize("condition,code", [("verifying", "TASK_VERIFYING"), ("paused", "TASK_PAUSED"),
                                            ("pending", "TASK_COMMAND_PENDING"), ("uncertain", "TASK_RECONCILIATION_REQUIRED"),
                                            ("done", "TASK_STATE_BLOCKED")])
async def test_a07_task_owned_actions_respect_coordinator_gate(owned, mock, action, condition, code):
    d, tid = owned
    if condition == "paused":
        d.journal.pause(tid)
    elif condition == "pending":
        d.journal.command(tid, "send", SID, {}, "pending")
    else:
        d.journal.db.execute("UPDATE tasks SET state=? WHERE task_id=?", (condition, tid))
    handlers = {"send": (service.session_send, {"text": "outside"}),
                "answer": (service.session_answer, {"permission": "allow"}),
                "interrupt": (service.session_interrupt, {"mode": "hard"}),
                "permissions": (lifecycle.session_set_permissions, {"mode": "allow_all", "force": True})}
    fn, params = handlers[action]
    with pytest.raises(TaskControlRefused) as caught:
        await fn(d.fleet, "h1", SID, confirm=True, **params)
    assert caught.value.code == code
    assert not writes(mock)
    assert not d.journal.commands(tid) if condition != "pending" else len(d.journal.commands(tid)) == 1
    if action != "permissions":
        p = api_auth.Principal("caller", frozenset({"operate"}))
        http_params = {"text": "outside"} if action == "send" else {"mode": "hard"} if action == "interrupt" else {
            "permission": "allow", "tool_use_id": "permission-1"}
        with pytest.raises(OperationError) as refused:
            d.ops.create(p, action="session." + action, target={"host": "h1", "session_id": SID},
                         params=http_params, idempotency_key="gate")
        assert refused.value.code == code
        assert d.journal.db.execute("SELECT count(*) FROM operations").fetchone()[0] == 0


@pytest.mark.parametrize("change,code", [("pause", "TASK_PAUSED"), ("version", "CONTROL_VERSION_CONFLICT"),
                                        ("binding", "TASK_BINDING_MISMATCH"), ("verifying", "TASK_VERIFYING")])
async def test_a07_late_state_version_and_owner_change_blocks_frame(owned, mock, monkeypatch, change, code):
    d, tid = owned
    client = d.fleet.client("h1")
    original = client._invoke_checked

    async def delayed(channel, *args, **kwargs):
        if channel == "claude:send-message":
            if change == "pause":
                # Keep the admitted version to exercise the state check independently.
                d.journal.db.execute("UPDATE tasks SET paused=1 WHERE task_id=?", (tid,))
            elif change == "version":
                d.journal.pause(tid)
                d.journal.resume(tid)
            elif change == "binding":
                registry.update("h1", SID, task_id="replacement-task")
            else:
                d.journal.db.execute("UPDATE tasks SET state='verifying' WHERE task_id=?", (tid,))
        return await original(channel, *args, **kwargs)
    monkeypatch.setattr(client, "_invoke_checked", delayed)
    with pytest.raises(TaskControlRefused) as refused:
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True, before_invoke=lambda: None)
    assert refused.value.code == code
    assert not writes(mock)
    assert d.journal.commands(tid)[0]["status"] == "rejected"


async def test_a07_client_resume_and_each_permission_channel_are_gated(owned, mock, monkeypatch):
    d, tid = owned
    client = d.fleet.client("h1")
    original = client._invoke_checked

    async def late_pause(channel, *args, **kwargs):
        if channel in {"claude:client-resume", "claude:set-codex-approval-policy"}:
            d.journal.pause(tid)
        return await original(channel, *args, **kwargs)
    monkeypatch.setattr(client, "_invoke_checked", late_pause)
    mock.metas[SID] = None
    with pytest.raises(TaskControlRefused, match="CONTROL_VERSION_CONFLICT"):
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True)
    assert not writes(mock)
    d.journal.resume(tid)
    codex = "sess-codex-0002"
    adopt(codex, task_id=tid, role="lead", agent_preset="codex-agent")
    d.journal.db.execute("UPDATE tasks SET session_id=? WHERE task_id=?", (codex, tid))
    with pytest.raises(TaskControlRefused, match="CONTROL_VERSION_CONFLICT"):
        await lifecycle.session_set_permissions(d.fleet, "h1", codex, "allow_all", confirm=True)
    assert [r["channel"] for r in writes(mock)] == ["claude:set-codex-sandbox-mode"]


async def test_a05_task_actions_share_actor_keys_and_original_effects(owned):
    d, tid = owned
    payload = {"task_id": tid, "actor": "ted", "source_message_id": "message-1", "idempotency_key": "pause"}
    first = await d.call("work_pause", payload)
    second = await d.call("work_pause", payload)
    assert first == second and first["operation_status"] == "succeeded"
    assert d.journal.get(tid)["control_version"] == 1
    assert d.journal.get(tid)["ted_interventions"] == 1
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_pause", {**payload, "abort_current": True})
    p = api_auth.Principal("second-client", frozenset({"operate"}))
    other = await d.call("work_pause", payload, principal=p)
    assert other["operation_id"] != first["operation_id"]
    resume = await d.call("work_resume", {"task_id": tid, "idempotency_key": "resume"})
    again = await d.call("work_resume", {"task_id": tid, "idempotency_key": "resume"})
    assert resume == again and d.journal.get(tid)["control_version"] == 3


async def test_a05_task_effect_and_receipt_commit_together(owned, monkeypatch):
    d, tid = owned
    p = api_auth.Principal("caller", frozenset({"operate"}))
    op, _ = d.ops.create(p, action="task.pause", target={"task_id": tid}, idempotency_key="crash")
    ctx = OpContext(d.ops, d.ops._row(op["operation_id"]))
    original = d.ops._step_done

    def crash(*args, **kwargs):
        raise RuntimeError("crash before receipt commit")
    monkeypatch.setattr(d.ops, "_step_done", crash)
    with pytest.raises(RuntimeError):
        ctx.effect("task_pause", lambda: d.journal.pause(tid))
    assert d.journal.get(tid)["control_version"] == 0
    assert not d.journal.get(tid)["paused"]
    monkeypatch.setattr(d.ops, "_step_done", original)
    result = ctx.effect("task_pause", lambda: d.journal.pause(tid))
    assert result["control_version"] == 1
    assert ctx.effect("task_pause", lambda: d.journal.pause(tid)) == result
    assert d.journal.get(tid)["control_version"] == 1
    await d.ops.drain()
    assert d.ops.get(op["operation_id"])["status"] == "succeeded"
    assert d.journal.get(tid)["control_version"] == 1


async def test_a07_goose_run_does_not_block_its_own_task_send(owned, mock):
    d, tid = owned
    d.journal.command(tid, "goose_run", SID, {}, "goose")
    first = await d.call("task_send", {"task_id": tid, "text": "one instruction", "step_id": "step-1"})
    second = await d.call("task_send", {"task_id": tid, "text": "one instruction", "step_id": "step-1"})
    assert first == second and first["operation_status"] == "succeeded"
    assert len([r for r in writes(mock) if r["channel"] == "claude:send-message"]) == 1
    assert len([c for c in d.journal.commands(tid) if c["kind"] == "send"]) == 1
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("task_send", {"task_id": tid, "text": "different", "step_id": "step-1"})


async def test_a07_approve_pending_deferred_raise_and_relay_do_not_jump_pause(owned, mock):
    d, tid = owned
    d.journal.pause(tid)
    mock.states[SID]["pendingPermission"] = {"toolUseId": "permission-1", "toolName": "Bash", "input": {}}
    registry.update("h1", SID, permission_raise_pending="allow_all")
    result = await lifecycle.approve_pending(d.fleet, "h1", confirm=True)
    assert not writes(mock)
    assert "TASK_PAUSED" in json.dumps(result)
    with pytest.raises(TaskControlRefused, match="TASK_PAUSED"):
        await lifecycle.session_relay(d.fleet, "h1", "a request", session_id=SID, confirm=True, dry_run=False)
    assert not writes(mock)


async def test_a07_waiting_permission_versions_reviewers_and_policy_first(owned, mock):
    d, tid = owned
    d.journal.db.execute("UPDATE tasks SET state='waiting_permission' WHERE task_id=?", (tid,))
    with pytest.raises(TaskControlRefused, match="TASK_STATE_BLOCKED"):
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True)
    with pytest.raises(TaskControlRefused, match="CONTROL_VERSION_CONFLICT"):
        await service.session_interrupt(d.fleet, "h1", SID, confirm=True, control_version=99)
    mock.states[SID]["pendingPermission"] = {"toolUseId": "permission-1", "toolName": "Bash", "input": {}}
    answer = await service.session_answer(d.fleet, "h1", SID, permission="allow", confirm=True, tool_use_id="permission-1")
    assert answer["permission"] == "allow"
    reviewer = "sess-codex-0002"
    adopt(reviewer, task_id=tid, role="reviewer", agent_preset="codex-agent")
    d.journal.db.execute("UPDATE tasks SET reviewer_session_id=? WHERE task_id=?", (reviewer, tid))
    with pytest.raises(TaskControlRefused, match="TASK_STATE_BLOCKED"):
        await service.session_interrupt(d.fleet, "h1", reviewer, confirm=True)
    # Losing creation evidence leaves an unknown resource; policy wins over the task pause.
    registry.update("h1", SID, created_at=None, recovered_from=None)
    d.journal.pause(tid)
    from bat_agent_connector.errors import ResourceReadOnly
    with pytest.raises(ResourceReadOnly):
        await service.session_interrupt(d.fleet, "h1", SID, confirm=True)


async def test_a07_task_pause_abort_is_journaled_control(owned, mock):
    d, tid = owned
    d.journal.db.execute("UPDATE tasks SET state='verifying' WHERE task_id=?", (tid,))
    result = await d.call("work_pause", {"task_id": tid, "abort_current": True, "idempotency_key": "abort"})
    assert result["paused"] and result["operation_status"] == "succeeded"
    op = d.ops.get(result["operation_id"])
    assert [(s["name"], s["status"]) for s in op["steps"]] == [("task_pause", "succeeded"), ("abort_current", "succeeded")]
    assert [r["channel"] for r in writes(mock)] == ["claude:abort-session"]
    assert await d.call("work_pause", {"task_id": tid, "abort_current": True, "idempotency_key": "abort"}) == result
    assert len(writes(mock)) == 1


async def test_a09_second_client_uses_central_owner(owned, mock, fleet_factory, monkeypatch):
    import asyncio
    d, tid = owned
    client = fleet_factory(writes=True, orchestrate=True, managed_roots=["/srv"], safety={"write_min_interval_s": 0})
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    d._endpoint = f"http://127.0.0.1:{port}/rpc"
    d._write_owner_pointer()
    try:
        result = await service.session_send(client, "h1", SID, "through owner", confirm=True)
        assert result["accepted"]
        commands = d.journal.commands(tid)
        assert len(commands) == 1 and commands[0]["kind"] == "send"
        assert len(writes(mock)) == 1
    finally:
        server.close()
        await server.wait_closed()
        await client.close()


async def test_a05_task_submit_actor_scope_continuation_and_upgrade_replay(owned):
    d, tid = owned
    payload = {"project": "p", "host": "h1", "workspace": "demo-project", "original_words": "new task",
               "idempotency_key": "submit"}
    first = await d.call("work_submit", payload)
    assert await d.call("work_submit", payload) == first
    p = api_auth.Principal("another-client", frozenset({"start"}))
    other = await d.call("work_submit", payload, principal=p)
    assert other["task_id"] != first["task_id"]
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_submit", {**payload, "original_words": "different"})
    old = d.journal.submit(project="p", host="h1", workspace="demo-project", original_words="historical",
                           engine="goose", recipe="goose-session", idempotency_key="historical")
    linked = await d.call("work_submit", {**payload, "original_words": "historical", "idempotency_key": "historical"})
    assert linked["task_id"] == old["task_id"]
    separate = await d.call("work_submit", {**payload, "original_words": "historical", "idempotency_key": "historical"}, principal=p)
    assert separate["task_id"] != old["task_id"]
    follow = {**payload, "parent_task_id": tid, "continuation": True, "idempotency_key": "follow"}
    result = await d.call("work_submit", follow)
    assert await d.call("work_submit", follow) == result
    assert d.journal.get(tid)["continuations"] == 1
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_submit", {**follow, "original_words": "different steering"})


async def test_a05_restart_after_effect_commit_replays_without_increment(mock, tmp_path):
    config = make_config(mock, writes=True, orchestrate=True)
    first = TaskDaemon(config, tmp_path / "restart.db")
    task = first.journal.submit(project="p", host="h1", workspace="w", original_words="do it", idempotency_key="old")
    principal = api_auth.Principal("caller", frozenset({"operate"}))
    op, _ = first.ops.create(principal, action="task.pause", target={"task_id": task["task_id"]},
                              preconditions={"control_version": 0}, idempotency_key="crash")
    ctx = OpContext(first.ops, first.ops._row(op["operation_id"]))
    ctx.effect("task_pause", lambda: first.journal.pause(task["task_id"]))
    first.journal.db.execute("UPDATE operations SET status='running' WHERE operation_id=?", (op["operation_id"],))
    await first.fleet.close()
    first.journal.close()
    second = TaskDaemon(config, tmp_path / "restart.db")
    try:
        await second.ops.drain()
        assert second.ops.get(op["operation_id"])["status"] == "succeeded"
        assert second.journal.get(task["task_id"])["control_version"] == 1
        assert len([e for e in second.journal.events(task["task_id"]) if e["kind"] == "paused"]) == 1
    finally:
        await second.fleet.close()
        second.journal.close()


async def test_a05_verify_request_ted_and_stage_use_original_receipts(owned, monkeypatch):
    d, tid = owned
    calls = []
    evidence = {"candidate_commit": "a" * 40, "tree_hash": "b" * 40, "command": "trusted tests",
                "exit_code": 0, "log_ref": "log-1", "output_sha256": "c" * 64, "source": "observed_runner"}

    async def verify(task):
        calls.append(task["task_id"])
        return evidence
    monkeypatch.setattr(d.adapter, "run_verification", verify)
    result = await d.call("task_run_verification", {"task_id": tid, "idempotency_key": "verify"})
    assert await d.call("task_run_verification", {"task_id": tid, "idempotency_key": "verify"}) == result
    assert calls == [tid]
    assert d.journal.db.execute("SELECT count(*) FROM observed_verifications").fetchone()[0] == 1
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("task_run_verification", {"task_id": tid, "idempotency_key": "verify", "exit_code": 1})
    ask = {"task_id": tid, "idempotency_key": "ted", "reason": "needs a decision"}
    first = await d.call("task_request_ted", ask)
    assert await d.call("task_request_ted", ask) == first
    assert len([e for e in d.journal.events(tid) if e["kind"] == "ted_requested"]) == 1
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("task_request_ted", {**ask, "reason": "different"})
    d.journal.db.execute("UPDATE tasks SET state='done',verification_commit=?,verification_tree=? WHERE task_id=?",
                         ("a" * 40, "b" * 40, tid))
    stage = {"task_id": tid, "idempotency_key": "stage", "stage": "adopted", "ref": "commit-a"}
    first = await d.call("work_mark_stage", stage)
    assert await d.call("work_mark_stage", stage) == first
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_mark_stage", {**stage, "ref": "commit-b"})


async def test_a05_reconcile_capability_consumption_and_receipt_are_atomic(owned, monkeypatch):
    d, tid = owned
    cmd, _ = d.journal.command(tid, "send", SID, {"purpose": "goose:one", "prompt_sha256": "d" * 64}, "uncertain-send")
    d.journal.command_status(cmd["command_id"], "uncertain")
    d.journal.change(tid, "uncertain")
    cap = d.journal.issue_reconcile_capability(tid, cmd["command_id"])
    params = {"task_id": tid, "command_id": cmd["command_id"], "outcome": "not_delivered", "actor": "operator",
              "source": "ticket-1", "evidence": "inspected the exact turn", "idempotency_key": "reconcile"}
    principal = d.capability_principal(cap, "task.command.reconcile", params, "reconcile")
    first = await d.call("work_reconcile", params, principal=principal)
    assert not d.journal.authorize_reconcile_capability(cap, tid, cmd["command_id"])
    assert cap not in json.dumps([dict(r) for r in d.journal.db.execute("SELECT * FROM operations")])
    assert d.capability_principal(cap, "task.command.reconcile", params, "different-key") is None
    assert d.capability_principal(cap, "task.command.reconcile", params, "reconcile") == principal
    assert await d.call("work_reconcile", params, principal=principal) == first
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_reconcile", {**params, "outcome": "delivered"}, principal=principal)
    # Crash after consuming the capability, before the operation result was committed.
    d.journal.db.execute("UPDATE operations SET status='running',result=NULL WHERE operation_id=?", (first["operation_id"],))
    await d.ops.drain()
    assert d.ops.get(first["operation_id"])["status"] == "succeeded"
    assert len(d.journal.reconciliations(tid)) == 1


async def test_a07_task_resume_reconciles_before_dispatch(owned, mock):
    d, tid = owned
    cmd, _ = d.journal.command(tid, "send", SID, {"purpose": "goose:one", "prompt_sha256": "d" * 64, "before": {}}, "pending")
    await d.call("work_pause", {"task_id": tid, "idempotency_key": "pause"})
    await d.call("work_resume", {"task_id": tid, "idempotency_key": "resume"})
    await d.coordinator.tick(tid)
    assert d.journal.command_get(cmd["command_id"])["status"] == "uncertain"
    assert not writes(mock)
    with pytest.raises(TaskControlRefused, match="TASK_COMMAND_PENDING"):
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True)


async def test_a07_pause_abort_late_resume_cannot_abort_new_control_version(owned, mock, monkeypatch):
    d, tid = owned
    original = d.fleet.client("h1")._invoke_checked

    async def resume_at_boundary(channel, *args, **kwargs):
        if channel == "claude:abort-session":
            d.journal.resume(tid)
        return await original(channel, *args, **kwargs)
    monkeypatch.setattr(d.fleet.client("h1"), "_invoke_checked", resume_at_boundary)
    with pytest.raises(OperationError, match="CONTROL_VERSION_CONFLICT"):
        await d.call("work_pause", {"task_id": tid, "abort_current": True, "idempotency_key": "abort"})
    assert not writes(mock)
    op = d.ops.list()["operations"][0]
    assert op["status"] == "failed" and op["error_code"] == "CONTROL_VERSION_CONFLICT"
    assert d.journal.get(tid)["control_version"] == 2


async def test_a05_rpc_http_and_mcp_share_task_action_keys(owned, monkeypatch):
    import asyncio

    from bat_agent_connector.mcp_server import build_server
    from tests.test_api_v1 import http

    d, tid = owned
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_TASK_ADMIN_TOKEN_FILE", str(d.admin_token_path))
    mcp, mcp_fleet = build_server(d.fleet.config)
    try:
        first = await mcp.call_tool("work_pause", {"task_id": tid, "idempotency_key": "shared"})
        text = json.dumps(first.model_dump(), default=str)
        op = d.ops.list()["operations"][0]
        assert op["operation_id"] in text
        status, result = await http(port, "POST", "/api/v1/operations?wait=2", tok=d._admin_token,
                                    body={"action": "task.pause", "target": {"task_id": tid},
                                          "params": {"abort_current": False, "actor": "service", "source_message_id": None},
                                          "idempotency_key": "shared"})
        assert status == 200 and result["operation"]["operation_id"] == op["operation_id"]
        assert d.journal.get(tid)["control_version"] == 1
    finally:
        await mcp_fleet.close()
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("kind", ["send", "failover", "start_lead", "answer", "interrupt", "permissions"])
async def test_a07_every_unresolved_runtime_kind_blocks_controls(owned, mock, kind):
    d, tid = owned
    d.journal.command(tid, kind, SID, {}, "pending-kind")
    with pytest.raises(TaskControlRefused, match="TASK_COMMAND_PENDING"):
        await service.session_interrupt(d.fleet, "h1", SID, confirm=True)
    assert not writes(mock)


async def test_a05_long_legacy_task_key_keeps_its_original_payload(owned):
    d, _ = owned
    params = {"project": "p", "host": "h1", "workspace": "demo-project", "original_words": "long key",
              "idempotency_key": "k" * 256}
    first = await d.call("work_submit", params)
    assert await d.call("work_submit", params) == first
    op = d.ops.get(first["operation_id"])
    assert op["params"]["legacy_idempotency_key"] == params["idempotency_key"]
    assert len(op["idem_key"]) <= 200
    with pytest.raises(OperationError, match="IDEMPOTENCY_CONFLICT"):
        await d.call("work_submit", {**params, "original_words": "changed"})


async def test_a07_scoped_operation_observes_late_control_version(owned, mock):
    d, tid = owned
    principal = api_auth.Principal("local-admin", frozenset(), admin=True)
    op, _ = d.ops.create(principal, action="session.send", target={"task_id": tid},
                         params={"text": "instruction", "step_id": "step"},
                         preconditions={"control_version": 0}, idempotency_key="late")
    d.journal.pause(tid)
    d.journal.resume(tid)
    await d.ops.drain()
    assert d.ops.get(op["operation_id"])["error_code"] == "CONTROL_VERSION_CONFLICT"
    assert not writes(mock)


async def test_a07_uncertain_task_send_reads_back_after_restart_without_resending(owned, mock, monkeypatch):
    from bat_agent_connector.errors import InvokeTimeout
    d, tid = owned

    async def lost(*args):
        raise InvokeTimeout("lost send reply")
    monkeypatch.setattr(d.adapter, "send", lost)
    params = {"task_id": tid, "text": "instruction", "step_id": "one", "idempotency_key": "lost"}
    first = await d.call("task_send", params)
    assert first["operation_status"] == "uncertain"
    command = next(c for c in d.journal.commands(tid) if c["kind"] == "send")
    assert command["status"] == "uncertain"
    # Restarted worker has no successful operation result. Missing proof must not dispatch again.
    d.journal.db.execute("UPDATE operations SET status='running',next_run_at=0 WHERE operation_id=?", (first["operation_id"],))
    await d.ops.drain()
    assert not writes(mock)
    assert d.ops.get(first["operation_id"])["status"] == "uncertain"
    assert len([c for c in d.journal.commands(tid) if c["kind"] == "send"]) == 1


async def test_a09_live_owner_lease_loss_blocks_a_waiting_frame(owned, mock, monkeypatch):
    d, _ = owned
    original = d.fleet.client("h1")._invoke_checked

    async def lose_owner(channel, *args, **kwargs):
        if channel == "claude:send-message":
            d.release_owner()
        return await original(channel, *args, **kwargs)
    monkeypatch.setattr(d.fleet.client("h1"), "_invoke_checked", lose_owner)
    with pytest.raises(TaskControlRefused, match="TASK_OWNER_UNAVAILABLE"):
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True)
    assert not writes(mock)


async def test_a07_missing_registry_owner_does_not_downgrade_a_reserved_task_session(owned, mock):
    d, _ = owned
    registry.update("h1", SID, task_id=None)
    with pytest.raises(TaskControlRefused, match="TASK_BINDING_MISMATCH"):
        await service.session_send(d.fleet, "h1", SID, "outside", confirm=True)
    assert not writes(mock)


async def test_a07_task_scoped_send_preserves_late_gate_code(owned, mock, monkeypatch):
    d, tid = owned
    original = d.fleet.client("h1")._invoke_checked

    async def pause_at_frame(channel, *args, **kwargs):
        if channel == "claude:send-message":
            d.journal.pause(tid)
        return await original(channel, *args, **kwargs)
    monkeypatch.setattr(d.fleet.client("h1"), "_invoke_checked", pause_at_frame)
    with pytest.raises(OperationError, match="CONTROL_VERSION_CONFLICT"):
        await d.call("task_send", {"task_id": tid, "text": "instruction", "step_id": "one"})
    assert not writes(mock)
    assert d.journal.commands(tid)[0]["status"] == "rejected"


async def test_a07_verifying_refusal_does_not_wait_for_coordinator_lock(owned):
    import asyncio
    d, tid = owned
    lock = d.coordinator._task_locks.setdefault(tid, asyncio.Lock())
    d.journal.db.execute("UPDATE tasks SET state='verifying' WHERE task_id=?", (tid,))
    async with lock:
        with pytest.raises(TaskControlRefused, match="TASK_VERIFYING"):
            await asyncio.wait_for(service.session_interrupt(d.fleet, "h1", SID, confirm=True), 1)


async def test_a05_historical_bridge_and_operation_intent_are_atomic(owned, monkeypatch):
    d, _ = owned
    old = d.journal.submit(project="p", host="h1", workspace="demo-project", original_words="historical",
                           engine="goose", recipe="goose-session", idempotency_key="pre-upgrade")
    original = d.ops._step_done
    monkeypatch.setattr(d.ops, "kick", lambda: None)

    def crash(*args, **kwargs):
        raise RuntimeError("crash before bridge commit")
    monkeypatch.setattr(d.ops, "_step_done", crash)
    params = {"project": "p", "host": "h1", "workspace": "demo-project", "original_words": "historical",
              "idempotency_key": "pre-upgrade"}
    with pytest.raises(RuntimeError, match="bridge commit"):
        await d.call("work_submit", params)
    assert d.journal.db.execute("SELECT count(*) FROM operations").fetchone()[0] == 0
    monkeypatch.setattr(d.ops, "_step_done", original)
    result = await d.call("work_submit", params)
    assert result["task_id"] == old["task_id"]


async def test_a05_historical_bridge_survives_restart_before_task_effect(mock, tmp_path, monkeypatch):
    config = make_config(mock, writes=True, orchestrate=True)
    path = tmp_path / "upgrade.db"
    first = TaskDaemon(config, path)
    old = first.journal.submit(project="p", host="h1", workspace="w", original_words="historical",
                               engine="goose", recipe="goose-session", idempotency_key="pre-upgrade")
    monkeypatch.setattr(first.ops, "kick", lambda: None)

    async def crash():
        raise RuntimeError("crash after admission commit")
    monkeypatch.setattr(first.ops, "run_due", crash)
    with pytest.raises(RuntimeError, match="admission commit"):
        await first.call("work_submit", {"project": "p", "host": "h1", "workspace": "w", "original_words": "historical",
                                         "idempotency_key": "pre-upgrade"})
    op_id = first.journal.db.execute("SELECT operation_id FROM operations").fetchone()[0]
    await first.fleet.close()
    first.journal.close()
    second = TaskDaemon(config, path)
    try:
        await second.ops.drain()
        assert second.ops.get(op_id)["result"]["task_id"] == old["task_id"]
        assert second.journal.db.execute("SELECT count(*) FROM tasks").fetchone()[0] == 1
    finally:
        await second.fleet.close()
        second.journal.close()


async def test_a07_runtime_codex_ack_requires_original_command_readback(owned, mock, monkeypatch):
    d, tid = owned
    sid = "sess-codex-0002"
    adopt(sid, task_id=tid, role="lead", agent_preset="codex-agent")
    mock.metas[sid]["isStreaming"] = False
    d.journal.db.execute("UPDATE tasks SET session_id=? WHERE task_id=?", (sid, tid))

    async def unknown(*args, **kwargs):
        return None
    monkeypatch.setattr(d.adapter, "reconcile_send", unknown)
    result = await service.session_send(d.fleet, "h1", sid, "runtime instruction", confirm=True)
    assert result["accepted"] is True  # the old result projection is retained in Part A
    assert d.journal.get(tid)["state"] == "uncertain"
    assert d.journal.commands(tid)[-1]["status"] == "uncertain"
    with pytest.raises(TaskControlRefused, match="TASK_COMMAND_PENDING"):
        await service.session_send(d.fleet, "h1", sid, "another instruction", confirm=True)
    assert len([r for r in writes(mock) if r["channel"] == "claude:send-message"]) == 1


async def test_a07_frame_guard_binds_prompt_before_client_resume(owned, mock):
    import hashlib

    from bat_agent_connector.task_control import FrameGuard
    d, tid = owned
    prompt_hash = hashlib.sha256(b"intended prompt").hexdigest()
    command, _ = d.journal.command(tid, "send", SID, {"prompt_sha256": prompt_hash}, "bound")
    guard = FrameGuard(d.journal, tid, "h1", SID, 0, command["command_id"], prompt_sha256=prompt_hash)
    with pytest.raises(TaskControlRefused, match="TASK_BINDING_MISMATCH"):
        await service.session_send(d.fleet, "h1", SID, "different prompt", confirm=True, _task_guard=guard)
    assert writes(mock) == []


async def test_a05_cli_reconcile_retries_keep_command_capability_identity(owned, monkeypatch, capsys):
    import asyncio

    from bat_agent_connector import cli
    d, tid = owned
    cmd, _ = d.journal.command(tid, "send", SID, {"purpose": "goose:one", "prompt_sha256": "d" * 64}, "old-send")
    d.journal.command_status(cmd["command_id"], "uncertain")
    d.journal.change(tid, "uncertain")
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_TASK_ADMIN_TOKEN_FILE", str(d.admin_token_path))
    argv = ["--json", "task-reconcile", "--task-id", tid, "--command-id", cmd["command_id"],
            "--key", "reconcile", "--outcome", "not_delivered", "--actor", "operator", "--source", "ticket-1", "--evidence", "checked exact turn"]
    try:
        assert await asyncio.to_thread(cli.main, argv) == 0
        first = json.loads(capsys.readouterr().out)
        assert await asyncio.to_thread(cli.main, argv) == 0
        assert json.loads(capsys.readouterr().out) == first
        assert len(d.journal.reconciliations(tid)) == 1
        changed = ["delivered" if arg == "not_delivered" else arg for arg in argv]
        assert await asyncio.to_thread(cli.main, changed) == 1
        assert "IDEMPOTENCY_CONFLICT" in capsys.readouterr().err
        assert d.journal.db.execute("SELECT count(*) FROM operations").fetchone()[0] == 1
    finally:
        server.close()
        await server.wait_closed()


async def test_a07_reconcile_rechecks_control_version_before_effect(owned, mock, monkeypatch):
    d, tid = owned
    cmd, _ = d.journal.command(tid, "send", SID, {"purpose": "goose:one", "prompt_sha256": "d" * 64}, "old-send")
    d.journal.command_status(cmd["command_id"], "uncertain")
    d.journal.change(tid, "uncertain")
    cap = d.journal.issue_reconcile_capability(tid, cmd["command_id"])

    async def idle(*args, **kwargs):
        return {"streaming": False, "pending": None}

    async def late_pause(*args, **kwargs):
        d.journal.pause(tid)
        return {"agent_kind": "claude", "before_was_empty": True}
    monkeypatch.setattr(d.adapter, "read", idle)
    monkeypatch.setattr(d.adapter, "prepare_send", late_pause)
    params = {"task_id": tid, "command_id": cmd["command_id"], "outcome": "not_delivered", "actor": "operator",
              "source": "ticket-1", "evidence": "checked exact turn", "next_prompt": "new instruction",
              "idempotency_key": "reconcile", "control_version": 0}
    principal = d.capability_principal(cap, "task.command.reconcile", params, "reconcile")
    with pytest.raises(OperationError, match="CONTROL_VERSION_CONFLICT"):
        await d.call("work_reconcile", params, principal=principal)
    assert d.journal.authorize_reconcile_capability(cap, tid, cmd["command_id"])
    assert d.journal.command_get(cmd["command_id"])["status"] == "uncertain"
    assert d.journal.reconciliations(tid) == []
    assert not writes(mock)


@pytest.mark.parametrize("action,params", [("session.send", {"text": "one instruction", "step_id": "one"}),
                                         ("task.verify", {}), ("task.request_ted", {"reason": "decision"})])
async def test_a07_api_actor_name_cannot_impersonate_task_capability(owned, mock, action, params):
    d, tid = owned
    actor = "task:" + tid + ":pretend"
    token = api_auth.issue(d.journal.db, actor, ["operate"])
    principal = api_auth.authenticate(d.journal.db, token, d._admin_token)
    with pytest.raises(OperationError, match="FORBIDDEN"):
        d.ops.create(principal, action=action, target={"task_id": tid}, params=params, idempotency_key="attempt")
    assert d.journal.db.execute("SELECT count(*) FROM operations").fetchone()[0] == 0
    assert not writes(mock)
