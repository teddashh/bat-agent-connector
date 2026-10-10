"""Real central reading fixture. Disk-temporary journal and MockBat; no live resources."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

from bat_agent_connector import api_auth, dashboard_sync, platform_files, work_items
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.mockbat import TOKEN, MockBat
from tests.operation_helpers import settle_operations


async def main():
    with tempfile.TemporaryDirectory(prefix="batc-attention-") as temporary:
        root = Path(temporary)
        platform_files.ensure_private_directory(root / "state")
        platform_files.ensure_private_directory(root / "config")
        os.environ.update(BATC_CONFIG_DIR=str(root / "config"), BATC_STATE_DIR=str(root / "state"), BATC_TEST_TOKEN=TOKEN)
        os.environ.pop("BATC_DEVICE_ID", None)
        mock = MockBat()
        await mock.start()
        d = TaskDaemon(make_config(mock, writes=False, orchestrate=False), root / "journal.db")
        editor = api_auth.Principal("fixture-editor", frozenset({"observe", "manage"}))

        async def change(action, target, params, version=None):
            op, _ = d.ops.create(editor, action=action, target=target, params=params,
                preconditions={} if version is None else {"expected_version": version},
                idempotency_key=f"fixture-{action}-{version}")
            await settle_operations(d.ops)
            result = d.ops.get(op["operation_id"])
            assert result["status"] == "succeeded", result
            return result["result"]

        pid = (await change("project.create", {}, {"name": "Shared attention"}))["project_id"]
        wid = (await change("work_item.create", {"project_id": pid}, {"title": "Review shared result"}))["work_item_id"]
        await change("work_item.update", {"work_item_id": wid}, {"state": "done"}, 1)
        token = api_auth.issue(d.journal.db, "shared-reader", ["observe"])
        other = api_auth.issue(d.journal.db, "other-reader", ["observe"])
        reader = api_auth.authenticate(d.journal.db, token, "fixture-admin")
        server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
        worker = asyncio.create_task(d.ops.loop(0.05))
        print(json.dumps({"port": server.sockets[0].getsockname()[1], "token": token, "other": other, "wid": wid}), flush=True)
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                command = json.loads(line)
                if command["action"] == "stop":
                    break
                if command["action"] == "edit":
                    item = work_items.work_item_get(d.journal.db, wid)["work_item"]
                    await change("work_item.update", {"work_item_id": wid}, {"goal": f"New result after version {item['version']}"}, item["version"])
                item = work_items.work_item_get(d.journal.db, wid,
                    principal_id=dashboard_sync.identity(d.journal, reader)["principal_id"])["work_item"]
                assert item["completion"]["pending"] and not item["completion"]["approved"]
                assert not mock.invokes  # Work-item reading never contacts BAT, even for read frames.
                print(json.dumps({"version": item["version"], "reading": item["reading"],
                    "markers": d.journal.db.execute("SELECT COUNT(*) FROM work_item_reads").fetchone()[0],
                    "read_events": d.journal.db.execute("SELECT COUNT(*) FROM api_events WHERE kind='work_item.read'").fetchone()[0]}), flush=True)
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            server.close()
            await server.wait_closed()
            await d.ops.drain()
            await d.artifact_store.close_reaper()
            await d.fleet.close()
            await d.inventory.close()
            d.journal.close()
            await mock.stop()


asyncio.run(main())
