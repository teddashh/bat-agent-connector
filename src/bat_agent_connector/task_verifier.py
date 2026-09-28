"""Trusted, observed verification on an isolated worktree.

Only administrator-configured argv is executed. A task caller cannot supply a
command, exit status or candidate hash. Output is kept in a private 0600 log
and never placed in the service journal or Discord messages.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shlex
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import state_dir


def _remote_command(alias: str, cwd: str, argv: tuple[str, ...]) -> tuple[str, ...]:
    """Build one SSH remote-command argument so the login shell preserves quoting."""
    script = "cd -- " + shlex.quote(cwd) + " && " + shlex.join(argv)
    # ssh concatenates all command arguments before handing them to the remote
    # shell.  Passing ``sh``, ``-lc`` and a separately quoted script therefore
    # loses the quote boundaries (and can run from the wrong directory).
    return ("ssh", "-o", "BatchMode=yes", alias, "sh -lc " + shlex.quote(script))

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class VerificationSettings:
    commands: dict[str, tuple[str, ...]] = field(default_factory=dict)
    ssh_hosts: dict[str, str] = field(default_factory=dict)
    timeout_s: int = 600
    register_tabs: bool = False
    artifact_dir: str | None = None
    base_branches: dict[str, str] = field(default_factory=dict)


def load_settings(path: str | None = None) -> VerificationSettings:
    path = path or os.environ.get("BATC_TASK_SETTINGS")
    if not path:
        return VerificationSettings()
    p = Path(path).expanduser()
    if stat.S_IMODE(p.stat().st_mode) & 0o077:
        raise ValueError("task settings must be mode 0600")
    raw = tomllib.loads(p.read_text())
    section = raw.get("verification", {})
    commands = {k: tuple(v) for k, v in section.get("commands", {}).items()}
    if any(not cmd or not all(isinstance(a, str) and a for a in cmd) for cmd in commands.values()):
        raise ValueError("verification commands must be nonempty argv arrays")
    aliases = section.get("ssh_hosts", {})
    if any(not isinstance(v, str) or not v or v.startswith("-") for v in aliases.values()):
        raise ValueError("invalid SSH alias")
    register_tabs = raw.get("task_service", {}).get("register_tabs", False)
    if not isinstance(register_tabs, bool):
        raise ValueError("task_service.register_tabs must be boolean")
    base_branches = raw.get("task_service", {}).get("base_branches", {})
    if not isinstance(base_branches, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v or v.startswith("-")
        for k, v in base_branches.items()
    ):
        raise ValueError("task_service.base_branches must map project names to branch names")
    return VerificationSettings(commands, aliases, int(section.get("timeout_s", 600)), register_tabs,
                                section.get("artifact_dir"), dict(base_branches))


class ObservedVerifier:
    def __init__(self, settings: VerificationSettings):
        self.settings = settings

    async def _run(self, host: str, cwd: str, argv: tuple[str, ...], timeout: int = 30) -> tuple[int, str]:
        alias = self.settings.ssh_hosts.get(host)
        if alias:
            cmd = _remote_command(alias, cwd, argv)
            working_dir = None
        else:
            cmd = argv
            working_dir = cwd
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=working_dir,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except BaseException:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
        if len(stdout) > 4096:
            raise ValueError("verification metadata output too large")
        return proc.returncode, stdout.decode(errors="replace").strip()

    async def identity(self, task: dict, cwd: str) -> dict | None:
        host = task["host"]
        try:
            head_rc, head = await self._run(host, cwd, ("git", "rev-parse", "HEAD"))
            tree_rc, tree = await self._run(host, cwd, ("git", "rev-parse", "HEAD^{tree}"))
            dirty_rc, dirty = await self._run(host, cwd, ("git", "status", "--porcelain"))
        except (OSError, ValueError, asyncio.TimeoutError):
            return None
        if any(rc != 0 for rc in (head_rc, tree_rc, dirty_rc)) or len(head) != 40 or len(tree) != 40:
            return None
        return {"candidate_commit": head, "tree_hash": tree, "clean": not bool(dirty)}

    async def observe(self, task: dict, cwd: str) -> dict | None:
        argv = self.settings.commands.get(task["project"])
        if not argv:
            return None
        before = await self.identity(task, cwd)
        if not before or not before["clean"]:
            return None
        alias = self.settings.ssh_hosts.get(task["host"])
        if alias:
            cmd = _remote_command(alias, cwd, argv)
            working_dir = None
        else:
            cmd = argv
            working_dir = cwd
        artifacts = Path(self.settings.artifact_dir or state_dir() / "task-artifacts")
        artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifacts.chmod(0o700)
        log_path = artifacts / (str(task["task_id"]) + "-" + uuid.uuid4().hex + ".log")
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        digest = hashlib.sha256()
        captured = 0
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=working_dir,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT)
        except BaseException:
            os.close(fd)
            log_path.unlink(missing_ok=True)
            raise

        async def drain():
            nonlocal captured
            assert proc.stdout
            while chunk := await proc.stdout.read(65_536):
                digest.update(chunk)
                if captured < 2_000_000:
                    kept = chunk[:2_000_000 - captured]
                    os.write(fd, kept)
                    captured += len(kept)
        try:
            await asyncio.wait_for(drain(), self.settings.timeout_s)
            await proc.wait()
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            exit_code = 124
        except BaseException:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
        finally:
            os.close(fd)
        after = await self.identity(task, cwd)
        if not after or not after["clean"] or after != before:
            return None
        return {"source": "observed_runner", "candidate_commit": before["candidate_commit"],
                "tree_hash": before["tree_hash"], "command": shlex.join(argv),
                "exit_code": exit_code, "log_ref": str(log_path),
                "output_sha256": digest.hexdigest()}
