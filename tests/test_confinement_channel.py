"""A10 / 計畫 §06, §12: only a declared trusted auditor channel certifies an account."""
from __future__ import annotations

import ast
import copy
import errno
import json
import pathlib
import stat
import sys
import types

import pytest

from bat_agent_connector import confinement, orchestrate
from tests.test_confinement import ACCOUNT, MANAGED, AccountRunner, account_observation
from tests.test_confinement_integrity import integrity_fixture


async def test_a10_same_account_forged_verdict_never_enables_accept_edits(fleet_factory, mock):
    class Forged(AccountRunner):
        async def run_account_check(self, *args, **kwargs):
            self.scripts.append("forged startup output")
            return '{"status":"verified"}'

    account = {k: v for k, v in ACCOUNT.items() if k not in {"check_ssh_alias", "check_uid", "bat_account"}}
    fleet = fleet_factory(writes=True, orchestrate=True, confinement=account, **MANAGED)
    runner = fleet.confinement_runner = Forged()
    try:
        cached = confinement.host_capability(fleet, "h1")["host_account"]
        assert cached["reason"] == "check_channel_untrusted" and cached["start_effect"] == "fallback_default"
        result = await orchestrate.session_start(fleet, "h1", "demo-project", "claude", confirm=True,
                                                write_scope="confined")
        assert result["confinement"]["options"] == {"permissionMode": "default"}
        assert result["confinement"]["evidence"]["host_check"]["status"] == "unknown"
        assert runner.scripts == []  # Never execute the account-controlled login to ask whether it is trusted.
        assert mock.channels().count("claude:start-session") == 1
    finally:
        await fleet.close()


@pytest.mark.parametrize("field,value", [("checked_uid", 2003), ("auditor_uid", 2001),
                                         ("ssh_alias", "wrong-auditor"), ("bat_account", "another-bat"),
                                         ("method", "login_shell"), ("channel", None)])
async def test_a10_verified_channel_facts_must_match_declaration(fleet_factory, field, value):
    observation = account_observation("verified", "read_only_account_check")
    if field in {"checked_uid", "channel"}:
        observation[field] = value
    else:
        observation["channel"][field] = value

    class Runner(AccountRunner):
        async def run_account_check(self, host, script, timeout_s=None, *, ssh_alias):
            assert ssh_alias == ACCOUNT["check_ssh_alias"]
            return json.dumps(observation)

    fleet = fleet_factory(confinement=ACCOUNT)
    fleet.confinement_runner = Runner()
    try:
        result = await confinement.start_account(fleet, "h1")
        assert result["status"] == "unknown" and result["reason"] == "check_channel_untrusted"
        assert confinement.account_start_effect(result) == "fallback_default"
    finally:
        await fleet.close()


@pytest.mark.parametrize("reason", [None, "auditor_identity_mismatch", "auditor_login_environment_writable",
                                    "check_executable_untrusted", "auditor_shell_untrusted", "bootstrap_acl_unproven"])
def test_a10_auditor_program_uses_exact_direct_exec_and_requires_preflight(monkeypatch, capsys, reason):
    uid = ACCOUNT["check_uid"] if reason != "auditor_identity_mismatch" else ACCOUNT["expected_uid"]
    calls = []

    class Path(pathlib.PurePosixPath):
        def resolve(self, strict=False):
            return self

        def lstat(self):
            return types.SimpleNamespace(st_uid=2001 if (reason == 'check_executable_untrusted' and str(self) == '/usr/bin/sudo'
                                                        or reason == 'auditor_shell_untrusted' and str(self) == '/bin/bash') else 0,
                                         st_gid=0, st_mode=stat.S_IFDIR | (
                0o777 if reason == 'auditor_login_environment_writable' and str(self) == '/usr/fixture-auditor/.bashrc' else 0o755))

    def no_acl(*args):
        if reason == 'bootstrap_acl_unproven' and str(args[0]) == '/usr/bin':
            return b'fixture ACL: conservatively unproven'
        raise OSError(errno.ENODATA, "fixture no ACL")

    def run(argv, *, input, **kwargs):
        calls.append(argv)
        # The child receives config on stdin, never as extra sudoers command arguments.
        tree = ast.parse(input.decode())
        payload = json.loads(ast.literal_eval(tree.body[1].value)[1])
        observed = {"status": "verified", "reason": "fixture", "checked_uid": ACCOUNT["expected_uid"],
                    "entries_remaining": 9000, "auditor_integrity": {"home": "/usr/fixture-auditor"},
                    "channel": copy.deepcopy(payload["channel"])}
        if payload["channel_only"] and reason:
            observed.update(status="unknown", reason="check_channel_untrusted", channel_reason=reason,
                            paths=["/usr/fixture-auditor/.bashrc"])
        return types.SimpleNamespace(returncode=0, stderr=b"", stdout=json.dumps(observed).encode())

    config = {"uid": ACCOUNT["expected_uid"], "auditor_uid": ACCOUNT["check_uid"],
              "bat_account": ACCOUNT["bat_account"], "ssh_alias": ACCOUNT["check_ssh_alias"],
              "entries": 10000, "seconds": 10, "roots": ["/srv/personal"], "port": 9876}
    with monkeypatch.context() as imports:
        imports.setitem(sys.modules, "pathlib", types.SimpleNamespace(Path=Path))
        imports.setitem(sys.modules, "os", types.SimpleNamespace(getuid=lambda: uid, geteuid=lambda: uid, getxattr=no_acl,
                                                              getgrouplist=lambda *a: [2001]))
        imports.setitem(sys.modules, "pwd", types.SimpleNamespace(getpwnam=lambda _: types.SimpleNamespace(pw_uid=2001, pw_gid=2001),
                                                               getpwuid=lambda _: types.SimpleNamespace(pw_dir='/usr/fixture-auditor', pw_shell='/bin/bash')))
        imports.setitem(sys.modules, "sys", types.SimpleNamespace(argv=["-", json.dumps(config)],
                                                               platform="linux", executable="/usr/bin/python3"))
        imports.setitem(sys.modules, "sysconfig", types.SimpleNamespace(get_path=lambda _: "/usr/lib/python3.10"))
        imports.setitem(sys.modules, "subprocess", types.SimpleNamespace(run=run, PIPE=-1, TimeoutExpired=TimeoutError))
        try:
            exec(confinement._ACCOUNT_CHANNEL_PROGRAM, {})
        except SystemExit:
            pass
    observed = json.loads(capsys.readouterr().out)
    assert all(argv == ['/usr/bin/sudo', '-n', '-u', ACCOUNT['bat_account'], '--', '/usr/bin/env', '-i',
                        'PATH=/usr/bin:/bin', 'LC_ALL=C', '/usr/bin/python3', '-I', '-S', '-B', '-'] for argv in calls)
    if reason:
        assert observed["status"] == "unknown"
        assert observed["reason"] == ('check_executable_untrusted' if reason in {'check_executable_untrusted', 'auditor_shell_untrusted', 'bootstrap_acl_unproven'}
                                     else 'check_channel_untrusted')
        assert calls == []  # Parent refuses the untrusted channel before any sudo drop.
    else:
        assert len(calls) == 2 and confinement.channel_matches(ACCOUNT, observed)


@pytest.mark.parametrize("path", ["/usr/fixture-auditor", "/usr/fixture-auditor/.ssh/rc",
                                 "/usr/fixture-auditor/.ssh/environment", "/usr/fixture-auditor/.ssh/authorized_keys",
                                 "/usr/fixture-auditor/.bashrc"])
def test_a10_auditor_login_inputs_are_checked_as_bat_uid(path):
    (reason, evidence), calls = integrity_fixture(account_uid=ACCOUNT["check_uid"], writable=[path])
    assert reason == "login_environment_writable" and path in evidence["paths"]
    assert all(call[0] == "/usr/bin/find" for call in calls)
    assert any('-writable' in call and '-uid' in call and str(ACCOUNT['expected_uid']) in call for call in calls)
