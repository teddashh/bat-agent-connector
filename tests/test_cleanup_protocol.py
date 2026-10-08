"""E01/plan §23: the locked proceed gate is the boundary of host uncertainty."""
from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path

import pytest

from bat_agent_connector import cleanup
from bat_agent_connector.checkpoints import GitCommandFailed
from bat_agent_connector.errors import ConnectionLost
from bat_agent_connector.operations import OperationError
from tests.test_cleanup_uncertainty import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    LocalRunner,
    apply,
    assert_reserved,
    close_clients,
    git,
    known_live_terminals,
    read_back,
    setup_work,
)
from tests.test_cleanup_uncertainty import daemon as checkpoint_daemon
from tests.test_cleanup_uncertainty import human as checkpoint_human

daemon = checkpoint_daemon
human = checkpoint_human


@pytest.mark.parametrize("fault", ["process", "timeout", "oserror", "connection", "truncated", "not_json", "empty", "bad_result"])
async def test_e01_post_gate_transport_and_protocol_failures_reconcile(daemon, mock, fault):
    cp, op = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    original = daemon.ops.context["git_runner"]

    class BrokenReply(LocalRunner):
        fired = False

        async def run(self, host, script, timeout_s=None):
            out = await original.run(host, script, timeout_s)
            req = json.loads(base64.b64decode(shlex.split(script)[-1]))
            if req.get("phase") == "remove.worktree" and not self.fired:
                self.fired = True
                if fault == "process":
                    raise GitCommandFailed("host process failed after proceed")
                if fault == "timeout":
                    raise TimeoutError("reply timed out")
                if fault == "oserror":
                    raise OSError("reply lost")
                if fault == "connection":
                    raise ConnectionLost("connection lost")
                return {"truncated": '{"result":', "not_json": "invalid", "empty": "{}",
                        "bad_result": '{"result": {}}'}[fault]
            return out

    daemon.ops.context["git_runner"] = BrokenReply()
    done = await apply(daemon, doc)
    assert done["status"] == "uncertain", done
    row = assert_reserved(daemon, done, item, "remove.worktree")
    assert row["error"]["host_error"] == "CLEANUP_HOST_PROTOCOL_UNCERTAIN"
    assert not Path(op["result"]["worktree_path"]).exists()
    settled = await read_back(daemon, done["operation_id"])
    assert settled["status"] == "succeeded", settled
    assert cleanup.lookup(daemon.journal.db, item["resource_id"])


async def test_e01_eof_during_locked_check_refuses_without_mutation(daemon, mock, monkeypatch):
    cp, _ = await setup_work(daemon, mock)
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    original = cleanup._phase_consumers

    async def disconnected(ctx, current):
        if current["kind"] == "worktree":
            raise ConnectionLost("live consumer read disconnected before proceed")
        await original(ctx, current)

    monkeypatch.setattr(cleanup, "_phase_consumers", disconnected)
    done = await apply(daemon, doc)
    step = next(s for s in done["steps"] if ".preserve." in s["name"])
    assert step["status"] == "failed" and step["error"]["code"] == "CLEANUP_HOST_REFUSED"
    assert Path(item["path"]).exists()
    assert not git(item["repository"], "for-each-ref", "refs/batc/retained/" + item["resource_id"])
    # No worktree content or pin changed; no unresolved host mutation is recorded.
    assert not any(s["status"] == "uncertain" for s in done["steps"])


@pytest.mark.parametrize("phase", sorted(cleanup.MUTATING_PHASES))
async def test_e01_mutating_phase_requires_locked_gate(daemon, phase):
    with pytest.raises(OperationError, match="CLEANUP_GATE_REQUIRED"):
        await cleanup._host_call(daemon.ops, "h1", {"phase": phase})
