"""Checkpoint continuation (plan §12): read a person's session, then start managed work at its commit.

Git runs for real in temp repositories (a local runner stands in for SSH); BAT is the mock.
"""

from __future__ import annotations

import asyncio
import json
import subprocess

import pytest

from bat_agent_connector import api_auth, checkpoints, resource_policy
from bat_agent_connector.channels import GUARDED_CHANNELS, ORCHESTRATE_CHANNELS, WRITE_CHANNELS
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config

MANUAL = "sess-claude-0001"
TED = api_auth.Principal("ted-dashboard", frozenset({"observe", "operate"}))
ORIGIN = "https://github.example/o/r.git"


def git(cwd, *args) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class LocalRunner:
    """Runs the host git script locally (tests only); the production runner wraps it in ``ssh alias``."""

    def __init__(self) -> None:
        self.scripts: list[str] = []

    def available(self, host: str) -> bool:
        return True

    async def run(self, host: str, script: str) -> str:
        self.scripts.append(script)
        return await checkpoints._run(("sh", "-c", script))


class RealGitLog(dict):
    """mock BAT ``git:log`` answers from real repositories (BAT runs ``git log --pretty=%H``)."""

    def __contains__(self, cwd) -> bool:
        return subprocess.run(["git", "-C", str(cwd), "rev-parse"], capture_output=True).returncode == 0

    def __getitem__(self, cwd):
        out = git(cwd, "log", "--pretty=format:%H||%s", "-n", "200")
        return [{"hash": h, "message": m} for h, _, m in (line.partition("||") for line in out.splitlines())]


def snapshot(repo) -> dict:
    return {"refs": git(repo, "for-each-ref"), "worktrees": git(repo, "worktree", "list", "--porcelain"),
            "status": git(repo, "status", "--porcelain"), "config": git(repo, "config", "--local", "--list"),
            "head": git(repo, "rev-parse", "HEAD")}


@pytest.fixture
def human(tmp_path):
    repo = tmp_path / "human" / "app"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "dev@example.invalid")
    git(repo, "config", "user.name", "dev")
    git(repo, "remote", "add", "origin", ORIGIN)
    for i in (1, 2):
        (repo / "notes.txt").write_text(f"v{i}\n")
        git(repo, "add", "notes.txt")
        git(repo, "commit", "-q", "-m", f"step {i}")
    return repo


@pytest.fixture
def daemon(mock, human, tmp_path):
    mock.metas[MANUAL] = {"cwd": str(human), "isStreaming": False}
    mock.git_logs = RealGitLog()
    d = TaskDaemon(make_config(mock, writes=True, orchestrate=True, managed_roots=[str(tmp_path / "managed")],
                               safety={"write_min_interval_s": 0}), tmp_path / "tasks.db")
    d.ops.context["git_runner"] = LocalRunner()
    yield d
    d.journal.close()


def bat_writes(mock, sid=None):
    writes = WRITE_CHANNELS | ORCHESTRATE_CHANNELS | GUARDED_CHANNELS
    return [i for i in mock.invokes if i["channel"] in writes
            and (sid is None or (i.get("params") or {}).get("sessionId") == sid)]


async def run(d, action, target, params=None, key=None):
    op, _ = d.ops.create(TED, action=action, target=target, params=params or {},
                         idempotency_key=key or f"{action}-{json.dumps(target, sort_keys=True)}-{params}")
    await d.ops.drain(timeout=60)
    return d.ops.get(op["operation_id"])


async def make_checkpoint(d, **params):
    await d.inventory.refresh_host("h1")
    op = await run(d, "checkpoint.create", {"host": "h1", "session_id": MANUAL}, {"last_n": 5, **params})
    assert op["status"] == "succeeded", op
    return checkpoints.get(d.journal.db, op["result"]["checkpoint_id"])


async def test_checkpoint_reads_a_person_session_and_writes_nothing(daemon, mock, human):
    before = snapshot(human)
    cp = await make_checkpoint(daemon)
    assert cp["source_provenance"] == "manual" and cp["commit_sha"] == before["head"]
    assert cp["branch"] == "main" and cp["dirty"] is False and cp["repo_root"] == str(human)
    assert len(cp["excerpt"]) == 5 and all(m["text"] for m in cp["excerpt"])
    assert bat_writes(mock) == []
    assert snapshot(human) == before
    events = daemon.journal.api_events(0, 100, resource_type="checkpoint")["events"]
    assert [e["kind"] for e in events] == ["checkpoint.created"]


async def test_checkpoint_refuses_a_commit_the_source_does_not_have(daemon, mock):
    await daemon.inventory.refresh_host("h1")
    op = await run(daemon, "checkpoint.create", {"host": "h1", "session_id": MANUAL}, {"commit": "e" * 40})
    assert op["status"] == "failed" and op["error_code"] == "COMMIT_NOT_FOUND"
    with pytest.raises(OperationError) as e:
        daemon.ops.create(TED, action="checkpoint.create", target={"host": "h1", "session_id": "nope"},
                          idempotency_key="k-missing")
    assert e.value.code == "NOT_FOUND"


async def test_continue_starts_managed_work_at_the_checkpoint_and_leaves_the_source_alone(daemon, mock, human):
    first = git(human, "rev-list", "--max-parents=0", "HEAD")
    cp = await make_checkpoint(daemon, commit=first)
    mock.git_status[str(human)] = [{"path": "notes.txt", "status": "M"}]  # the person keeps working meanwhile
    before = snapshot(human)
    op = await run(daemon, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]},
                   {"instructions": "Add a changelog entry", "agent": "claude"})
    assert op["status"] == "succeeded", op
    r = op["result"]
    wt, sid = r["worktree_path"], r["session_id"]
    assert git(wt, "rev-parse", "HEAD") == first and git(wt, "status", "--porcelain") == ""
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == r["branch"] == "batc/cp-" + op["operation_id"][3:15]
    clone = op["external_refs"]["clone_path"]
    assert git(clone, "config", "--get", "remote.origin.url") == ORIGIN  # pushes go to GitHub, not the person
    assert git(clone, "config", "--get", "batc.managed-clone") == "true"
    assert snapshot(human) == before

    starts = [i for i in mock.invokes if i["channel"] == "claude:start-session"]
    assert len(starts) == 1 and starts[0]["params"]["options"]["cwd"] == wt
    sends = [i for i in mock.invokes if i["channel"] == "claude:send-message"]
    assert len(sends) == 1 and sends[0]["params"]["sessionId"] == sid
    prompt = sends[0]["params"]["prompt"]
    assert "Add a changelog entry" in prompt and first in prompt and "[assistant]" in prompt
    assert bat_writes(mock, MANUAL) == []  # nothing was sent to the person's session

    hc = daemon.fleet.config.host("h1")
    entries = resource_policy._entries("h1")
    assert resource_policy.classify_row_for_read(hc, sid, has_tab=False, entries=entries)["api_access"] == "managed"
    follow = await run(daemon, "session.send", {"host": "h1", "session_id": sid}, {"text": "and a test"})
    assert follow["status"] == "succeeded", follow

    # A second continuation reuses the connector clone and gets its own worktree and branch.
    again = await run(daemon, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]},
                      {"instructions": "Try another approach"}, key="second")
    assert again["status"] == "succeeded", again
    assert again["external_refs"]["clone_path"] == clone and again["result"]["worktree_path"] != wt
    runs = checkpoints.get(daemon.journal.db, cp["checkpoint_id"])["runs"]
    assert [x["session_id"] for x in runs] == [sid, again["result"]["session_id"]]
    assert snapshot(human) == before


async def test_continue_refusals_happen_before_anything_is_recorded(daemon, mock, human):
    cp = await make_checkpoint(daemon)
    target = {"checkpoint_id": cp["checkpoint_id"]}
    for params, code in [({"instructions": " "}, "INVALID_PARAMS"),
                         ({"instructions": "x", "agent": "gpt"}, "INVALID_PARAMS")]:
        with pytest.raises(OperationError) as e:
            daemon.ops.create(TED, action="checkpoint.continue", target=target, params=params,
                              idempotency_key=f"bad-{params}")
        assert e.value.code == code
    with pytest.raises(OperationError) as e:
        daemon.ops.create(TED, action="checkpoint.continue", target={"checkpoint_id": "cp_" + "0" * 32},
                          params={"instructions": "x"}, idempotency_key="k-none")
    assert e.value.status == 404
    daemon.ops.context["git_runner"] = None
    with pytest.raises(OperationError) as e:
        daemon.ops.create(TED, action="checkpoint.continue", target=target, params={"instructions": "x"},
                          idempotency_key="k-runner")
    assert e.value.code == "GIT_RUNNER_UNAVAILABLE"
    viewer = api_auth.Principal("viewer", frozenset({"observe"}))
    with pytest.raises(OperationError) as e:
        daemon.ops.create(viewer, action="checkpoint.create", target={"host": "h1", "session_id": MANUAL},
                          idempotency_key="k-viewer")
    assert e.value.code == "FORBIDDEN"


async def test_continue_never_adopts_a_folder_it_did_not_create(daemon, mock, human, tmp_path):
    cp = await make_checkpoint(daemon)
    clone = checkpoints.clone_path(str(tmp_path / "managed"), "h1", str(human))
    subprocess.run(["git", "init", "-q", clone], check=True)  # someone else's repo at the clone path
    op = await run(daemon, "checkpoint.continue", {"checkpoint_id": cp["checkpoint_id"]}, {"instructions": "x"})
    assert op["status"] == "failed" and op["error_code"] == "GIT_FAILED"
    assert "not a connector clone" in op["status_reason"]
    assert not any(i["channel"] == "claude:start-session" for i in mock.invokes)


async def test_prepare_script_is_idempotent(human, tmp_path):
    runner = LocalRunner()
    head = git(human, "rev-parse", "HEAD")
    dest = str(tmp_path / "managed" / "app-1")
    args = (str(human), dest, dest + "/.bat-worktrees/w1", "batc/cp-w1", head, dest + ".tmp")
    first = await runner.run("h1", checkpoints.prepare_script(*args))
    second = await runner.run("h1", checkpoints.prepare_script(*args))
    assert first == second == f"{head}\n0"
    assert git(dest, "worktree", "list", "--porcelain").count("worktree ") == 2


def test_first_prompt_keeps_the_newest_excerpt_within_the_limit():
    cp = {"repo_root": "/r/app", "branch": "main", "commit_sha": "a" * 40, "dirty": 2,
          "excerpt": [{"role": "user", "text": f"message {i} " + "x" * 3000} for i in range(20)]}
    text = checkpoints.first_prompt(cp, worktree="/m/app/.bat-worktrees/w", branch="batc/cp-1",
                                    instructions="Ship it")
    assert len(text) <= 20_000 and text.endswith("Task:\nShip it")
    assert "message 19 " in text and "message 0 " not in text and "2 uncommitted" in text


async def test_http_lists_checkpoints_and_reports_where_they_can_continue(daemon, mock):
    cp = await make_checkpoint(daemon)
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    with daemon.journal.tx():
        tok = api_auth.issue(daemon.journal.db, "viewer", ["observe"])

    async def get(path):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer {tok}\r\n\r\n".encode())
        await writer.drain()
        raw = await reader.read()
        writer.close()
        return json.loads(raw.partition(b"\r\n\r\n")[2])

    try:
        listed = await get(f"/api/v1/checkpoints?session_id={MANUAL}")
        assert [c["checkpoint_id"] for c in listed["checkpoints"]] == [cp["checkpoint_id"]]
        assert listed["checkpoints"][0]["excerpt_messages"] == 5
        one = await get(f"/api/v1/checkpoints/{cp['checkpoint_id']}")
        assert one["checkpoint"]["commit_sha"] == cp["commit_sha"] and one["checkpoint"]["runs"] == []
        caps = await get("/api/v1/capabilities")
        assert caps["features"]["checkpoints"] == ["h1"]
    finally:
        server.close()
        await server.wait_closed()
        await daemon.fleet.close()
        await daemon.inventory.close()
