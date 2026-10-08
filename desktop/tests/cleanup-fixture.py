"""Real cleanup API and Git worktrees; MockBat and local test Git runner only."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

from tests.test_cleanup import setup_work

from bat_agent_connector import api_auth
from tests.mockbat import TOKEN, MockBat
from tests.test_checkpoints import daemon as daemon_fixture
from tests.test_checkpoints import human as human_fixture


async def main():
    with tempfile.TemporaryDirectory(prefix="batc-cleanup-ui-") as temporary:
        root = Path(temporary)
        os.environ.update(BATC_CONFIG_DIR=str(root / "config"), BATC_STATE_DIR=str(root / "state"), BATC_TEST_TOKEN=TOKEN)
        os.environ.pop("BATC_DEVICE_ID", None)
        mock = MockBat()
        await mock.start()
        for terminal in mock.ws_doc["terminals"]:
            if mock.metas.get(terminal["id"]) is None:
                mock.metas[terminal["id"]] = {"cwd": terminal["cwd"], "isStreaming": False}
        human = human_fixture.__wrapped__(root)
        fixture = daemon_fixture.__wrapped__(mock, human, root)
        daemon = next(fixture)
        cp, operation = await setup_work(daemon, mock)
        token = api_auth.issue(daemon.journal.db, "cleanup-browser", ["observe", "cleanup", "cleanup_discard"])
        server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
        worker = asyncio.create_task(daemon.ops.loop(0.1))
        print(json.dumps({"port": server.sockets[0].getsockname()[1], "token": token,
                          "checkpoint_id": cp["checkpoint_id"], "session_id": operation["result"]["session_id"]}), flush=True)
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                if json.loads(line)["action"] == "stop":
                    break
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            server.close()
            await server.wait_closed()
            await daemon.inventory.close()
            with contextlib.suppress(StopIteration):
                next(fixture)
            await mock.stop()


if __name__ == "__main__":
    asyncio.run(main())
