"""Loopback task API and worker. Run explicitly with ``batc serve``."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import registry
from .config import Config, state_dir
from .fleet import Fleet
from .goose_acp import GooseACP
from .redact import redact
from .task_bat import BatTaskAdapter
from .task_core import TaskCoordinator
from .task_discord import DiscordHTTP, DiscordPublisher
from .task_journal import Journal

DEFAULT_URL = "http://127.0.0.1:18796/rpc"


def request(method: str, **params) -> dict:
    """Small stdio-MCP client to the local daemon; no BAT token crosses this API."""
    url = os.environ.get("BATC_TASK_URL", DEFAULT_URL)
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path != "/rpc" or parsed.query or parsed.fragment):
        raise ValueError("task daemon URL must be loopback (use SSH forwarding on example-host-1)")
    req = urllib.request.Request(  # noqa: S310 - validated loopback URL
        url, method="POST", data=json.dumps({"method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - loopback checked above
        result = json.load(resp)
    if "error" in result:
        raise ValueError(result["error"])
    return result["result"]


class TaskDaemon:
    def __init__(self, config: Config, db_path: str | Path | None = None, *, discord=None):
        self.journal = Journal(db_path or state_dir() / "tasks.sqlite3")
        self.fleet = Fleet(config, actor="task-service")
        self.adapter = BatTaskAdapter(self.fleet)
        self.coordinator = TaskCoordinator(self.journal, self.adapter)
        self.goose = GooseACP()
        self._active_ticks: dict[str, asyncio.Task] = {}
        board = os.environ.get("BATC_DISCORD_BOARD_CHANNEL_ID")
        self.publisher = DiscordPublisher(self.journal, discord or DiscordHTTP(), board) if (
            discord or os.environ.get("BATC_DISCORD_BOT_TOKEN")
        ) else None

    async def call(self, method: str, params: dict) -> dict:
        if method == "work_submit":
            if not self.fleet.orchestrate_enabled(params.get("host", "")):
                raise ValueError("task host needs writes=true and orchestrate=true")
            task = self.journal.submit(**params)
            return {"task_id": task["task_id"], "state": task["state"], "submitted_at": task["submitted_at"]}
        task_id = params["task_id"]
        if method == "work_status":
            task = self.journal.get(task_id)
            return {**task, "commands": self.journal.commands(task_id)[-5:],
                    "events": self.journal.events(task_id)[-10:]}
        if method == "work_result":
            task = self.journal.get(task_id)
            return {"task_id": task_id, "state": task["state"], "delivered": task["delivered"],
                    "delivered_at": task["delivered_at"], "time_to_deliver_s": task["time_to_deliver_s"],
                    "result": task["result"], "verification_commit": task["verification_commit"],
                    "review_rejections": task["review_rejections"], "ted_interventions": task["ted_interventions"]}
        if method == "work_pause":
            return await self.coordinator.pause(task_id, abort_current=params.get("abort_current", False))
        if method == "work_resume":
            return self.journal.resume(task_id)
        if method.startswith("task_"):
            task = self.journal.get(task_id)
            if task["engine"] != "goose":
                raise ValueError("task-scoped tools require goose engine")
            if method == "task_read":
                return await self.adapter.read(task, task["session_id"], params.get("marker"))
            if method == "task_send":
                if not task["session_id"]:
                    raise ValueError("task has no BAT session")
                return await self.coordinator._send(task, task["session_id"], params["text"],
                                                    "goose:" + params["step_id"])
            if method == "task_record_verification":
                return await self.adapter.record_verification(task, **{k: params[k] for k in (
                    "candidate_commit", "command", "exit_code", "environment", "log_ref")})
            if method == "task_request_ted":
                self.journal.intervention(task_id)
                return self.journal.change(task_id, "needs_ted", fields={"result": params["reason"]})
        raise ValueError("unknown task method")

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            if len(head) > 16_384:
                raise ValueError("request headers too large")
            lines = head.decode("ascii").split("\r\n")
            if lines[0] != "POST /rpc HTTP/1.1":
                raise ValueError("POST /rpc required")
            lengths = [int(line.split(":", 1)[1].strip()) for line in lines[1:] if line.lower().startswith("content-length:")]
            if len(lengths) != 1 or not 0 < lengths[0] <= 100_000:
                raise ValueError("invalid body length")
            body = json.loads(await asyncio.wait_for(reader.readexactly(lengths[0]), 5))
            result = {"result": await self.call(body["method"], body.get("params") or {})}
            status = "200 OK"
        except Exception as exc:  # noqa: BLE001
            result = {"error": redact(f"{type(exc).__name__}: {exc}")}
            status = "400 Bad Request"
        raw = json.dumps(result, ensure_ascii=False, default=str).encode()
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode() + raw)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _worker(self):
        while True:
            for task in self.journal.list_active():
                tid = task["task_id"]
                active = self._active_ticks.get(tid)
                if active is None or active.done():
                    self._active_ticks[tid] = asyncio.create_task(self._tick_task(tid))
            if self.publisher:
                try:
                    await self.publisher.flush()
                except Exception as exc:  # noqa: BLE001 - sending remains pending/uncertain for reconciliation
                    logging.warning("Discord event flush needs reconciliation: %s", type(exc).__name__)
            await asyncio.sleep(2)

    async def _tick_task(self, task_id: str):
        try:
            task = self.journal.get(task_id)
            if task["engine"] != "goose" or task["state"] in {"queued", "verifying", "quota_limited", "uncertain"}:
                await self.coordinator.tick(task_id)
                return
            if task["paused"] or task["state"] in {"needs_ted", "human_owned", "failed", "done"}:
                return
            if any(c["kind"] == "goose_run" for c in self.journal.commands(task_id)):
                return
            entry = registry.get(task["host"], task["session_id"])
            if not entry or not entry.get("cwd"):
                self.journal.change(task_id, "uncertain")
                return
            cmd, _ = self.journal.command(task_id, "goose_run", task["session_id"], {},
                                          f"{task_id}:goose:run")
            try:
                await self.goose.run_task(task, entry["cwd"])
            except Exception:  # noqa: BLE001 - record uncertainty; no blind ACP rerun
                self.journal.command_status(cmd["command_id"], "uncertain")
                self.journal.change(task_id, "uncertain")
                return
            self.journal.command_status(cmd["command_id"], "settled")
            if self.journal.get(task_id)["state"] == "running":
                self.journal.change(task_id, "needs_ted")
        except Exception as exc:  # noqa: BLE001 - one task cannot kill worker
            logging.warning("Task %s needs reconciliation after %s", task_id[:8], type(exc).__name__)
            try:
                self.journal.change(task_id, "uncertain")
            except ValueError:
                pass

    async def serve(self, host: str = "127.0.0.1", port: int = 18796):
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("task service only binds loopback")
        server = await asyncio.start_server(self._handle, host, port)
        worker = asyncio.create_task(self._worker())
        try:
            async with server:
                await server.serve_forever()
        finally:
            worker.cancel()
            await self.fleet.close()
            self.journal.close()
