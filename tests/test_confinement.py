"""A10: options and evidence are checked without writing to a person's folder; W12 proves enforcement."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import time

import pytest

from bat_agent_connector import confinement, lifecycle, orchestrate, registry, service
from bat_agent_connector.config import parse_config
from bat_agent_connector.errors import ConfigError
from bat_agent_connector.task_journal import Journal
from tests.conftest import adopt

MANAGED = {"managed_roots": ["/srv/demo"], "legacy_shared_worktrees": True}


@pytest.mark.parametrize("agent", ["claude", "codex"])
@pytest.mark.parametrize("policy", ["default", "allow_all", "confined"])
async def test_a10_general_start_preserves_operator_policy_and_records_evidence(fleet_factory, mock, agent, policy):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode=policy,
                      safety={"write_min_interval_s": 0}, **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", agent, confirm=True)
    options = [i["params"]["options"] for i in mock.invokes if i["channel"] == "claude:start-session"][0]
    expected = confinement.policy_options(agent, policy)
    assert {k: options[k] for k in confinement.OPTION_KEYS if k in options} == expected
    assert r["write_scope"] == ("confined" if policy == "confined" else None)
    record = r["confinement"]
    assert record["level"] == ("none" if policy == "allow_all" else
                               "prompt_gated" if agent == "claude" else "os_sandbox")
    assert record["verification"]["status"] == "options_confirmed"
    if agent == "codex" and policy != "allow_all":
        assert record["gap"] == "sandbox_enforcement_unverified"
    read = await service.session_read(f, "h1", r["session_id"])
    assert read["confinement"] == record and read["current_verification"]["status"] == "options_confirmed"
    await f.close()


class AccountRunner:
    def __init__(self, status="verified"):
        self.status, self.scripts = status, []

    def available(self, host):
        return True

    async def run(self, host, script, timeout_s=None):
        self.scripts.append(script)
        return json.dumps({"status": self.status, "reason": "read_only_account_check"})


ACCOUNT = {"host_account": True, "expected_uid": 2001, "protected_roots": ["/srv/personal"]}


async def test_a10_accept_edits_requires_verified_account_and_checks_are_read_only(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, **MANAGED)
    f.confinement_runner = AccountRunner()
    r = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    assert r["confinement"]["options"] == {"permissionMode": "acceptEdits"}
    assert r["confinement"]["level"] == "host_account"
    assert r["confinement"]["verification"]["status"] == "verified"
    script = f.confinement_runner.scripts[0]
    assert "'-xdev'" in script and "'-writable'" in script and "'status'" in script
    assert "sudo" not in script and "write_text" not in script
    await f.close()


@pytest.mark.parametrize("status", ["unknown", "mismatch"])
async def test_a10_declared_unverified_account_blocks_new_start(fleet_factory, mock, status):
    f = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, **MANAGED)
    f.confinement_runner = AccountRunner(status)
    with pytest.raises(confinement.ConfinementRefused, match="HOST_ACCOUNT_UNVERIFIED"):
        await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True)
    assert "claude:start-session" not in mock.channels() and "worktree:create" not in mock.channels()
    await f.close()


async def test_a10_host_account_cache_expires_without_upgrading_creation(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, **MANAGED)
    f.confinement_runner = AccountRunner()
    r = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    original = copy.deepcopy(r["confinement"])
    f._confinement_checks["h1"]["checked_at"] = time.time() - 1000
    read = await service.session_read(f, "h1", r["session_id"])
    assert read["confinement"] == original and read["current_verification"]["status"] == "unknown"
    assert read["current_verification"]["reason"] == "host_account_unverified"
    await f.close()


@pytest.mark.parametrize("force", [False, True])
async def test_a10_raise_and_deferred_raise_are_refused(fleet_factory, mock, force):
    f = fleet_factory(writes=True, default_permission_mode="allow_all", **MANAGED)
    adopt("sess-claude-0001", write_scope="confined", permission_raise_pending="allow_all")
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_RAISE_REFUSED"):
        await lifecycle.session_set_permissions(f, "h1", "sess-claude-0001", confirm=True, force=force)
    dry = await lifecycle._raise_deferred(f, "h1", dry_run=True)
    assert dry[0]["skipped"] == "confined"
    actual = await lifecycle._raise_deferred(f, "h1", dry_run=False)
    assert actual[0]["error_code"] == "CONFINEMENT_RAISE_REFUSED"
    assert registry.get("h1", "sess-claude-0001")["permission_raise_pending"] is None
    assert not mock.perm_calls
    await f.close()


async def test_a10_loaded_legacy_send_works_but_missing_evidence_resume_is_blocked(fleet_factory, mock):
    f = fleet_factory(writes=True, safety={"write_min_interval_s": 0}, **MANAGED)
    adopt("sess-claude-0001", write_scope="confined")
    r = await service.session_send(f, "h1", "sess-claude-0001", "Continue", confirm=True)
    assert r["accepted"]
    mock.metas.pop("sess-claude-0001")
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_EVIDENCE_MISSING"):
        await service.session_send(f, "h1", "sess-claude-0001", "Continue", confirm=True)
    assert "claude:client-resume" not in mock.channels()
    await f.close()


async def test_a10_resume_uses_original_options_not_stale_tab(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, tabs=True, default_permission_mode="allow_all",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    sid = r["session_id"]
    mock.metas.pop(sid)
    for terminal in mock.ws_doc["terminals"]:
        if terminal["id"] == sid:
            terminal["permissionMode"] = "bypassPermissions"
    await service.session_send(f, "h1", sid, "Continue", confirm=True)
    resume = [i for i in mock.invokes if i["channel"] == "claude:client-resume"][-1]
    assert resume["params"]["options"]["permissionMode"] == "default"
    await f.close()


@pytest.mark.parametrize("tool,dont", [("Bash", True), ("ExitPlanMode", False), ("ExitPlanMode", True)])
async def test_a10_persistent_and_exit_plan_approvals_are_refused(fleet_factory, mock, tool, dont):
    f = fleet_factory(writes=True, **MANAGED)
    adopt("sess-claude-0001", write_scope="confined")
    mock.states["sess-claude-0001"]["pendingPermission"] = {"toolUseId": "test", "toolName": tool, "input": {}}
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_RAISE_REFUSED"):
        await service.session_answer(f, "h1", "sess-claude-0001", permission="allow",
                                     dont_ask_again=dont, confirm=True)
    assert "claude:resolve-permission" not in mock.channels()
    await f.close()


async def test_a10_creation_snapshot_survives_runtime_drift_and_send_refuses(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0}, **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    mock.metas[r["session_id"]]["permissionMode"] = "acceptEdits"
    read = await service.session_read(f, "h1", r["session_id"])
    assert read["confinement"] == r["confinement"] and read["current_verification"]["status"] == "mismatch"
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_MISMATCH"):
        await service.session_send(f, "h1", r["session_id"], "Continue", confirm=True)
    await f.close()


async def test_a10_planner_is_read_only_never_and_successor_preserves_limits(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="allow_all", **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True, confinement_role="planner")
    previous = registry.get("h1", r["session_id"])
    opts, scope, record = await confinement.start_decision(f, "h1", "codex", confined=True, predecessor=previous)
    assert r["confinement"]["options"] == opts == {"codexSandboxMode": "read-only", "codexApprovalPolicy": "never"}
    assert scope == "confined" and record["evidence"]["inherited_from"]["session_id"] == r["session_id"]
    await f.close()


async def test_a10_task_service_keeps_engine_policy_and_reports_gap(fleet_factory):
    for policy in ("allow_all", "confined"):
        f = fleet_factory(writes=True, default_permission_mode=policy)
        options, scope, record = await confinement.start_decision(f, "h1", "codex", task=True)
        assert options == confinement.policy_options("codex", "allow_all" if policy == "allow_all" else "default")
        assert scope is None and record["gap"] == "task_recipe_compatibility"
        await f.close()


def test_a10_host_account_configuration_rejects_uncheckable_claims():
    for config in ({"host_account": True}, {**ACCOUNT, "expected_uid": 0},
                   {**ACCOUNT, "protected_roots": ["/srv/demo"]}, {"sandbox_evidence_file": "/tmp/proof"}):
        with pytest.raises(ConfigError):
            parse_config({"hosts": {"h1": {"url": "wss://example.invalid", "fingerprint": "a" * 64, "token_ref": "env:EXAMPLE", "managed_roots": ["/srv/demo"],
                                          "confinement": config}}})


def test_a10_host_evidence_migration_is_idempotent_and_persists(tmp_path):
    journal = Journal(tmp_path / "tasks.db")
    journal.db.execute("INSERT INTO confinement_host_checks VALUES(?,?)", ("h1", '{"status":"unknown"}'))
    journal.close()
    journal = Journal(tmp_path / "tasks.db")
    assert journal.db.execute("SELECT evidence FROM confinement_host_checks").fetchone()[0] == '{"status":"unknown"}'
    assert journal.db.execute("PRAGMA user_version").fetchone()[0] == 2
    journal.close()


@pytest.mark.parametrize("case,expected", [("safe", "verified"), ("writable", "mismatch"),
                                          ("budget", "unknown"), ("identity", "unknown"),
                                          ("capabilities", "mismatch"), ("ancestor", "mismatch"),
                                          ("time", "unknown"), ("process", "unknown"), ("symlink", "unknown")])
def test_a10_linux_read_only_scan_uses_find_and_process_identity(tmp_path, monkeypatch, capsys, case, expected):
    """Use real GNU find on a disposable fixture; simulate /proc, alias and ancestor metadata only."""
    root = tmp_path / "protected"
    root.mkdir()
    (root / "file").write_text("fixture")
    (root / "file").chmod(0o600 if case == "writable" else 0o400)
    if case == "symlink":
        (root / "link").symlink_to(root / "file")
    root.chmod(0o500)
    real_path = pathlib.Path
    uid = os.getuid()
    gid = os.getgid()
    groups = " ".join(str(g) for g in sorted(os.getgroups()))
    def status(parent):
        return (f"PPid:\t{parent}\nUid:\t{uid} {uid} {uid} {uid}\n"
                            f"Gid:\t{gid} {gid} {gid} {gid}\nGroups:\t{groups}\n"
                            f"CapEff:\t{'1' if case == 'capabilities' else '0'}\n")

    class Proc:
        def __init__(self, *parts):
            self.parts = parts
            self.name = parts[-1]
        def __truediv__(self, part):
            return Proc(*self.parts, part)
        def read_text(self):
            if self.name in {"tcp", "tcp6"}:
                return "header\n0: 0100007F:2694 0:0 0A 0 0 0 0 0 101\n"
            return status(1 if self.parts[1] == "2" else 0)
        def read_bytes(self):
            return b"unidentified" if case == "process" else (
                b"bat-server" if self.parts[1] == "1" else b"codex")
        def iterdir(self):
            return [Proc("/proc", "1"), Proc("/proc", "2")] if self.parts == ("/proc",) else [Proc("fd")]

    def path(*parts):
        return Proc(*parts) if str(parts[0]).startswith("/proc") else real_path(*parts)

    monkeypatch.setattr(pathlib, "Path", path)
    monkeypatch.setattr(os, "readlink", lambda _: "socket:[101]")
    monkeypatch.setattr(os, "access", lambda *a, **k: case == "ancestor")
    monkeypatch.setattr('sys.argv', ["check", json.dumps({"uid": uid + 1 if case == "identity" else uid,
                                                        "roots": [str(root)], "entries": 1 if case == "budget" else 10,
                                                        "seconds": .000001 if case == "time" else 5, "port": 9876})])
    with pytest.raises(SystemExit):
        exec(confinement._ACCOUNT_PROGRAM, {})
    assert json.loads(capsys.readouterr().out)["status"] == expected
    root.chmod(0o700)
    (root / "file").chmod(0o600)


@pytest.mark.parametrize("agent,options,level", [
    ("claude", {"permissionMode": "acceptEdits"}, "none"),
    ("claude", {"permissionMode": "bypassPermissions"}, "none"),
    ("claude", {"permissionMode": "default"}, "prompt_gated"),
    ("codex", {"codexSandboxMode": "workspace-write", "codexApprovalPolicy": "on-request"}, "os_sandbox"),
])
def test_a10_level_requires_options_not_cwd(agent, options, level):
    record = confinement.confirm(confinement.snapshot(agent, options), {"cwd": "/same", **options})
    assert record["level"] == level and record["verification"]["status"] != "verified"
    assert confinement.verify(record, {"cwd": "/same"})["status"] == "unknown"


async def test_a10_partial_permission_ack_preserves_creation_and_reports_drift(fleet_factory, mock):
    from bat_agent_connector.errors import InvokeTimeout
    f = fleet_factory(writes=True, orchestrate=True, default_permission_mode="allow_all",
                      safety={"write_min_interval_s": 0}, **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", "codex", confirm=True)
    sid = r["session_id"]
    client = f.client("h1")
    real = client.invoke

    async def lost_second_reply(channel, params=None, **kw):
        result = await real(channel, params, **kw)
        if channel == "claude:set-codex-approval-policy":
            raise InvokeTimeout("lost permission acknowledgement")
        return result

    client.invoke = lost_second_reply
    with pytest.raises(InvokeTimeout):
        await lifecycle.session_set_permissions(f, "h1", sid, "default", confirm=True)
    read = await service.session_read(f, "h1", sid)
    assert read["confinement"] == r["confinement"] and read["current_verification"]["status"] == "mismatch"
    # Retry after a partial/lost reply records the actual current options; it never edits creation evidence.
    client.invoke = real
    await lifecycle.session_set_permissions(f, "h1", sid, "default", confirm=True)
    read = await service.session_read(f, "h1", sid)
    assert read["confinement"] == r["confinement"] and read["current_verification"]["matches_creation"] is False
    await f.close()


async def test_a10_start_mismatch_stays_uncertain_and_never_sends_prompt(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, **MANAGED)
    client = f.client("h1")
    real = client.invoke

    async def changed_before_readback(channel, params=None, **kw):
        result = await real(channel, params, **kw)
        if channel == "claude:start-session":
            mock.metas[params["sessionId"]]["permissionMode"] = "acceptEdits"
        return result

    client.invoke = changed_before_readback
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_MISMATCH"):
        await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True,
                                        write_scope="confined", prompt="Work")
    assert "claude:send-message" not in mock.channels()
    assert registry.list_entries("h1")[0]["status"] == "uncertain"
    await f.close()


async def test_a10_frame_guard_catches_drift_after_first_read(fleet_factory, mock):
    f = fleet_factory(writes=True, orchestrate=True, safety={"write_min_interval_s": 0}, **MANAGED)
    r = await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    sid = r["session_id"]
    def drift():
        mock.metas[sid]["permissionMode"] = "bypassPermissions"
    with pytest.raises(confinement.ConfinementRefused, match="CONFINEMENT_MISMATCH"):
        await service.session_send(f, "h1", sid, "Work", confirm=True, before_invoke=drift)
    assert "claude:send-message" not in mock.channels()
    await f.close()


def test_a10_account_script_quotes_paths_without_shell_expansion():
    roots = ["/srv/space $(touch probe) 'root'"]
    script = confinement.account_script({**ACCOUNT, "protected_roots": roots})
    import shlex
    assert json.loads(shlex.split(script.splitlines()[0])[3])["roots"] == roots


async def test_a10_lost_confined_start_ack_retains_options_and_worktree(fleet_factory, mock):
    from bat_agent_connector.errors import InvokeTimeout
    f = fleet_factory(writes=True, orchestrate=True, **MANAGED)
    client = f.client("h1")
    real = client.invoke

    async def lost(channel, params=None, **kw):
        result = await real(channel, params, **kw)
        if channel == "claude:start-session":
            raise InvokeTimeout("lost start acknowledgement")
        return result

    client.invoke = lost
    with pytest.raises(InvokeTimeout):
        await orchestrate.session_start(f, "h1", "demo-project", "claude", confirm=True, write_scope="confined")
    entry = registry.list_entries("h1")[0]
    assert entry["status"] == "uncertain" and entry["confinement"]["options"] == {"permissionMode": "default"}
    assert "worktree:remove" not in mock.channels()
    await f.close()
