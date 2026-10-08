"""A10: synthetic login/executable layouts: no fleet account or home is inspected."""
from __future__ import annotations

import json
import pathlib
import stat
import types

import pytest

from bat_agent_connector import checkpoints, confinement, orchestrate
from tests.test_confinement import ACCOUNT, MANAGED, AccountRunner, account_observation


def integrity_fixture(*, owned=(), writable=(), shell="/bin/bash", missing=(), account_uid=None):
    uid = 2001
    calls = []
    owned, writable, missing = set(owned), set(writable), set(missing)

    class FixturePath(pathlib.PurePosixPath):
        def resolve(self, strict=False):
            return self

        def stat(self):
            return types.SimpleNamespace(st_uid=uid if str(self) in owned else 0, st_mode=stat.S_IFDIR | 0o755)

        lstat = stat

        def exists(self):
            return str(self) not in missing

        def is_symlink(self):
            return False

    def run(args, **kwargs):
        calls.append(args)
        return types.SimpleNamespace(returncode=0, stderr=b"", stdout=b"W" if args[1] in writable else b"")

    class Process:
        def __init__(self, args, **kwargs):
            calls.append(args)
            target = args[1]
            hits = sorted(p for p in owned | writable if p == target or (
                '-maxdepth' not in args and p.startswith(target + '/')))
            self.output = b"E\0" + (("W:" + hits[0]).encode() + b"\0" if hits else b"")
            self.stdout = types.SimpleNamespace(fileno=lambda: 123)
            self.returncode = 0

        def communicate(self, **kwargs):
            return b"", b""

        def poll(self):
            return 0

    current = None

    def popen(*args, **kwargs):
        nonlocal current
        current = Process(*args, **kwargs)
        return current

    def read(*args):
        output, current.output = current.output, b""
        return output

    selector = types.SimpleNamespace(register=lambda *a: None, select=lambda *a: [True], close=lambda: None)
    namespace = {"c": {"uid": uid}, "remaining": 1000, "deadline": 100., "budget": lambda: None,
                 "pwd": types.SimpleNamespace(getpwuid=lambda account: types.SimpleNamespace(
                     pw_dir="/usr/fixture-home" if account == uid else "/usr/fixture-auditor", pw_shell=shell)),
                 "pathlib": types.SimpleNamespace(Path=FixturePath),
                 "sys": types.SimpleNamespace(executable="/usr/bin/python3"),
                 "sysconfig": types.SimpleNamespace(get_path=lambda _: "/usr/lib/python3.10"),
                 "os": types.SimpleNamespace(access=lambda p, *a, **k: str(p) in writable,
                                             W_OK=2, X_OK=1, read=read, fsdecode=lambda s: s.decode()),
                 "stat": stat, "time": types.SimpleNamespace(monotonic=lambda: 0.),
                 "subprocess": types.SimpleNamespace(run=run, Popen=popen, PIPE=-1),
                 "selectors": types.SimpleNamespace(DefaultSelector=lambda: selector, EVENT_READ=1)}
    exec(confinement._ACCOUNT_INTEGRITY_PROGRAM, namespace)
    return namespace["check_integrity"](account_uid), calls


@pytest.mark.parametrize("options,reason,path", [
    ({"owned": ["/usr/fixture-home"]}, "login_environment_writable", "/usr/fixture-home"),
    ({"writable": ["/usr/fixture-home/.ssh/rc"]}, "login_environment_writable", "/usr/fixture-home/.ssh/rc"),
    ({"writable": ["/usr/fixture-home/.bashrc"]}, "login_environment_writable", "/usr/fixture-home/.bashrc"),
    ({"writable": ["/usr/bin"]}, "check_executable_untrusted", "/usr/bin"),
    ({"owned": ["/usr/bin/find"]}, "check_executable_untrusted", "/usr/bin/find"),
    ({"shell": "/bin/fish"}, "login_shell_unsupported", None),
    ({"missing": ["/usr/fixture-home/.bashrc"], "writable": ["/usr/fixture-home"]},
     "login_environment_writable", "/usr/fixture-home"),
])
def test_account_integrity_rejects_account_controlled_check_inputs(options, reason, path):
    (observed, evidence), calls = integrity_fixture(**options)
    assert observed == reason
    if path:
        assert path in evidence["paths"]
    assert all(call[0] == "/usr/bin/find" for call in calls)


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/dash", "/bin/bash", "/usr/bin/zsh"])
def test_account_integrity_accepts_root_owned_nonwritable_layout(shell):
    (reason, evidence), calls = integrity_fixture(shell=shell, missing=["/usr/fixture-home/.pam_environment"])
    assert reason is None and evidence["home"] == "/usr/fixture-home"
    assert "/usr/bin/python3" in evidence["trusted_paths"] and "/usr/bin/find" in evidence["trusted_paths"]
    assert all(call[0] == "/usr/bin/find" for call in calls)
    assert any('-writable' in call and '-uid' in call for call in calls)


async def test_account_check_remote_command_is_isolated_and_git_runner_unchanged(monkeypatch):
    calls = []

    async def run(argv, timeout_s=None):
        calls.append(argv)
        return '{}'

    monkeypatch.setattr(checkpoints, "_run", run)
    runner = checkpoints.SshGitRunner({"fixture": "synthetic-alias"})
    command = confinement.account_script(ACCOUNT)
    await runner.run_account_check("fixture", command, ssh_alias=ACCOUNT["check_ssh_alias"])
    assert calls[0] == ("ssh", "-o", "BatchMode=yes", ACCOUNT["check_ssh_alias"], command)
    assert command.startswith("cd / && exec /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C /usr/bin/python3 -I -S -B - ")
    assert "sh -l" not in command and "-lc" not in command
    assert "['find'" not in command and "['/usr/bin/find'" in command
    await runner.run("fixture", "git status")
    assert calls[1][-1] == "sh -lc 'git status'"


@pytest.mark.parametrize("reason", sorted(confinement.ACCOUNT_HARDENING_GAPS))
async def test_account_integrity_unknown_uses_plain_default_never_accept_edits(fleet_factory, mock, reason):
    class Unhardened(AccountRunner):
        async def run_account_check(self, *args, **kwargs):
            return json.dumps({"status": "unknown", "reason": reason, "paths": ["/usr/fixture-home"]})

    fleet = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, **MANAGED)
    fleet.confinement_runner = Unhardened()
    try:
        result = await orchestrate.session_start(fleet, "h1", "demo-project", "claude", confirm=True,
                                                write_scope="confined")
        starts = [i for i in mock.invokes if i["channel"] == "claude:start-session"]
        assert starts[0]["params"]["options"]["permissionMode"] == "default"
        record = result["confinement"]
        assert record["level"] == "prompt_gated" and record["protected_roots"] == []
        assert record["evidence"]["host_check"]["status"] == "unknown"
        assert record["evidence"]["host_check"]["reason"] == reason
    finally:
        await fleet.close()


async def test_account_integrity_gap_at_frame_never_sends_prepared_accept_edits(fleet_factory, mock):
    class Changed(AccountRunner):
        async def run_account_check(self, *args, **kwargs):
            self.scripts.append(args[1])
            return json.dumps(account_observation("verified" if len(self.scripts) == 1 else "unknown",
                                                  "login_environment_writable"))

    fleet = fleet_factory(writes=True, orchestrate=True, confinement=ACCOUNT, **MANAGED)
    fleet.confinement_runner = Changed()
    try:
        with pytest.raises(confinement.ConfinementRefused, match="HOST_ACCOUNT_UNVERIFIED"):
            await orchestrate.session_start(fleet, "h1", "demo-project", "claude", confirm=True,
                                            write_scope="confined")
        assert "claude:start-session" not in mock.channels()
    finally:
        await fleet.close()
