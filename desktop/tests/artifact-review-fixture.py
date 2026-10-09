"""Managed capture/review through actual central HTTP, temporary Git and MockBat."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from bat_agent_connector import api_auth, artifacts
from tests.mockbat import TOKEN, MockBat
from tests.test_artifact_capture import daemon as daemon_fixture
from tests.test_artifact_capture import human as human_fixture
from tests.test_artifact_managed import execution as execution_fixture
from tests.test_checkpoints import bat_writes, git, snapshot


def worktree_snapshot(path):
    index = Path(git(path, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    return {"files": {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()},
            "refs": git(path, "for-each-ref"), "head": git(path, "rev-parse", "HEAD"),
            "index": (hashlib.sha256(index.read_bytes()).hexdigest(), index.stat().st_mtime_ns)}


async def main():
    with tempfile.TemporaryDirectory(prefix="batc-artifact-review-ui-") as temporary:
        root = Path(temporary)
        os.environ.update(BATC_CONFIG_DIR=str(root / "config"), BATC_STATE_DIR=str(root / "state"), BATC_TEST_TOKEN=TOKEN)
        os.environ.pop("BATC_DEVICE_ID", None)
        mock = MockBat()
        await mock.start()
        human = human_fixture.__wrapped__(root)
        fixture = daemon_fixture.__wrapped__(mock, human, root)
        daemon = await anext(fixture)
        operation, sid, path = await execution_fixture.__wrapped__(daemon, mock)
        await daemon.inventory.refresh_host("h1")
        contents = (path / "result.bin").read_bytes()
        source_before, human_before, writes_before = worktree_snapshot(path), snapshot(human), len(bat_writes(mock))
        token = api_auth.issue(daemon.journal.db, "artifact-review-browser", ["observe", "manage", "approve"])
        server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
        worker = asyncio.create_task(daemon.ops.loop(0.1))
        print(json.dumps({"port": server.sockets[0].getsockname()[1], "token": token, "session_id": sid,
                          "execution_id": operation["operation_id"], "digest": hashlib.sha256(contents).hexdigest()}), flush=True)
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                command = json.loads(line)
                if command["action"] == "stop":
                    break
                if command["action"] != "verify":
                    raise ValueError("Unknown fixture command")
                capture = daemon.ops.get(command["capture_id"])
                review = daemon.ops.get(command["accept_id"])
                assert capture["action"] == "artifact.capture.managed" and capture["status"] == "succeeded", capture
                assert review["action"] == "artifact.accept" and review["status"] == "succeeded", review
                ref = capture["result"]
                row = artifacts.get(daemon.journal.db, ref["artifact_id"], ref["revision"])
                assert row["source"]["kind"] == "managed_capture"
                assert row["source"]["source"]["lineage"]["execution_operation_id"] == operation["operation_id"]
                assert row["digest"] == hashlib.sha256(contents).hexdigest()
                assert daemon.artifact_store.read_content(ref["artifact_id"], ref["revision"]) == contents
                assert len(row["acceptances"]) == 1 and row["acceptances"][0]["operation_id"] == review["operation_id"]
                for action in ("artifact.capture.managed", "artifact.accept"):
                    assert daemon.journal.db.execute("SELECT COUNT(*) FROM operations WHERE action=?", (action,)).fetchone()[0] == 1
                assert worktree_snapshot(path) == source_before and snapshot(human) == human_before
                assert len(bat_writes(mock)) == writes_before
                assert not daemon.journal.db.execute("SELECT 1 FROM tasks").fetchone()
                assert not daemon.journal.db.execute("SELECT 1 FROM work_items").fetchone()
                print(json.dumps({"verified": True, "bytes": list(contents), "acceptances": 1}), flush=True)
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            server.close()
            await server.wait_closed()
            await fixture.aclose()
            await mock.stop()


if __name__ == "__main__":
    asyncio.run(main())
