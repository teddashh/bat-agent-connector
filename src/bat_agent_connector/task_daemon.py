"""Loopback task API and worker. Run explicitly with ``batc serve``."""

from __future__ import annotations

import asyncio
import fcntl
import hmac
import json
import logging
import os
import secrets
import tempfile
import shutil
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import registry
from .config import Config, state_dir
from .fleet import Fleet
from .goose_acp import GooseACP
from .task_bat import BatTaskAdapter
from .task_core import TaskCoordinator
from .task_discord import DiscordHTTP, DiscordPublisher
from .task_journal import Journal
from .task_verifier import ObservedVerifier, load_settings

DEFAULT_URL = "http://127.0.0.1:18796/rpc"


def request(method: str, *, _auth_token: str | None = None, **params) -> dict:
    """Small stdio-MCP client to the local daemon; no BAT token crosses this API."""
    url = os.environ.get("BATC_TASK_URL", DEFAULT_URL)
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path != "/rpc" or parsed.query or parsed.fragment):
        raise ValueError("task daemon URL must be loopback (use SSH forwarding on example-host-1)")
    cap = os.environ.get("BATC_TASK_CAPABILITY")
    token_file = Path(os.environ.get("BATC_TASK_ADMIN_TOKEN_FILE", state_dir() / "task-admin.token"))
    token = _auth_token or cap or token_file.read_text().strip()
    req = urllib.request.Request(  # noqa: S310 - validated loopback URL
        url, method="POST", data=json.dumps({"method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5) as resp:  # noqa: S310 - loopback checked above
        result = json.load(resp)
    if "error" in result:
        raise ValueError(result["error"])
    return result["result"]


class TaskDaemon:
    def __init__(self, config: Config, db_path: str | Path | None = None, *, discord=None):
        self.journal = Journal(db_path or state_dir() / "tasks.sqlite3")
        self.admin_token_path = self.journal.path.parent / "task-admin.token"
        try:
            fd = os.open(self.admin_token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
        if self.admin_token_path.stat().st_mode & 0o077:
            raise ValueError("task admin token file must be mode 0600")
        self._admin_token = self.admin_token_path.read_text().strip()
        if len(self._admin_token) < 32:
            raise ValueError("task admin token is invalid")
        self.fleet = Fleet(config, actor="task-service")
        self.adapter = BatTaskAdapter(self.fleet, ObservedVerifier(load_settings()), self.journal)
        self.coordinator = TaskCoordinator(self.journal, self.adapter)
        # Covers the whole verifying state, including BAT/SSH lookups before
        # and after the subprocess. A restart retains the journal timestamp.
        self.verification_timeout_s = min(300, max(1, self.adapter.verifier.settings.timeout_s))
        self.goose = GooseACP()
        self._active_ticks: dict[str, asyncio.Task] = {}
        self._lease_fd: int | None = None
        self._owner_id = secrets.token_hex(16)
        board = os.environ.get("BATC_DISCORD_BOARD_CHANNEL_ID")
        self.publisher = DiscordPublisher(self.journal, discord or DiscordHTTP(), board) if (
            discord or os.environ.get("BATC_DISCORD_BOT_TOKEN")
        ) else None

    async def call(self, method: str, params: dict, *, auth_token: str | None = None) -> dict:
        if method == "work_delivery_status":
            return {"unresolved_events": self.journal.discord_unresolved(),
                    "board": self.journal.board_get(os.environ.get("BATC_DISCORD_BOARD_CHANNEL_ID", ""))}
        if method == "work_delivery_confirm_absent":
            if params.get("event_id") is not None:
                self.journal.discord_confirm_absent(int(params["event_id"]))
            elif params.get("board_channel_id"):
                self.journal.board_confirm_absent(params["board_channel_id"])
            else:
                raise ValueError("event_id or board_channel_id required")
            return {"confirmed_absent": True}
        if method == "work_delivery_confirm_found":
            if not self.publisher:
                raise ValueError("Discord publisher is not configured")
            return await self.publisher.confirm_found(event_id=params.get("event_id"),
                                                      board_channel_id=params.get("board_channel_id"),
                                                      message_id=params["message_id"])
        if method == "work_submit":
            if params.get("engine", "rules") == "goose":
                raise ValueError("Goose live tasks are disabled until ACP recovery and provider validation")
            if not self.fleet.orchestrate_enabled(params.get("host", "")):
                raise ValueError("task host needs writes=true and orchestrate=true")
            params = dict(params)
            if params.get("base_branch") is None:
                params["base_branch"] = self.adapter.verifier.settings.base_branches.get(params.get("project"))
            task = self.journal.submit(**params)
            return {"task_id": task["task_id"], "state": task["state"], "submitted_at": task["submitted_at"]}
        task_id = params["task_id"]
        if method == "work_reconcile_capability":
            token = self.journal.issue_reconcile_capability(task_id, params["command_id"])
            return {"task_id": task_id, "command_id": params["command_id"], "capability": token,
                    "expires_in_s": 600}
        if method == "work_reconcile":
            if not auth_token:
                raise ValueError("command-scoped reconciliation capability required")
            return await self.coordinator.resolve_command(
                task_id, params["command_id"], token=auth_token, outcome=params["outcome"],
                actor=params["actor"], source=params["source"], evidence=params["evidence"],
                observed_result=params.get("observed_result", "none"), turn_ref=params.get("turn_ref"),
                candidate_commit=params.get("candidate_commit"), tree_hash=params.get("tree_hash"),
                next_prompt=params.get("next_prompt"),
            )
        if method == "work_status":
            task = self.journal.get(task_id)
            return {**task, "commands": self.journal.commands(task_id)[-5:],
                    "events": self.journal.events(task_id)[-10:],
                    "reconciliations": self.journal.reconciliations(task_id)}
        if method == "work_result":
            task = self.journal.get(task_id)
            return {"task_id": task_id, "state": task["state"], "delivered": task["delivered"],
                    "delivered_at": task["delivered_at"], "time_to_deliver_s": task["time_to_deliver_s"],
                    "result": task["result"], "verification_commit": task["verification_commit"],
                    "review_rejections": task["review_rejections"], "ted_interventions": task["ted_interventions"],
                    "session_replacements": task["session_replacements"],
                    "ted_interventions_basis": "caller_reported"}
        if method == "work_pause":
            if params.get("actor", "service") not in {"service", "ted"}:
                raise ValueError("invalid actor")
            if params.get("actor") == "ted" and not params.get("source_message_id"):
                raise ValueError("Ted action requires source_message_id")
            result = await self.coordinator.pause(task_id, abort_current=params.get("abort_current", False))
            if params.get("actor") == "ted":
                self.journal.ted_action(task_id, action="pause", source_message_id=params["source_message_id"])
            return result
        if method == "work_resume":
            if params.get("actor", "service") not in {"service", "ted"}:
                raise ValueError("invalid actor")
            if params.get("actor") == "ted" and not params.get("source_message_id"):
                raise ValueError("Ted action requires source_message_id")
            result = self.journal.resume(task_id)
            if params.get("actor") == "ted":
                self.journal.ted_action(task_id, action="resume", source_message_id=params["source_message_id"])
            return result
        if method.startswith("task_"):
            task = self.journal.get(task_id)
            if task["engine"] != "goose":
                raise ValueError("task-scoped tools require goose engine")
            if method == "task_read":
                return await self.adapter.read(task, task["session_id"], params.get("marker"))
            if method == "task_send":
                if not task["session_id"]:
                    raise ValueError("task has no BAT session")
                if (not isinstance(params.get("text"), str) or not params["text"].strip()
                        or len(params["text"]) > 18_000 or not isinstance(params.get("step_id"), str)
                        or not 0 < len(params["step_id"]) <= 128):
                    raise ValueError("invalid task prompt or step id")
                return await self.coordinator._send(task, task["session_id"], params["text"],
                                                    "goose:" + params["step_id"])
            if method == "task_run_verification":
                if set(params) != {"task_id"}:
                    raise ValueError("caller-supplied verification evidence is forbidden")
                evidence = await self.adapter.run_verification(task)
                if not evidence:
                    raise ValueError("trusted verifier unavailable or candidate changed")
                return self.journal.record_observed_verification(task_id, evidence)
            if method == "task_request_ted":
                self.journal.request_ted(task_id, params["reason"])
                return self.journal.change(task_id, "needs_ted", fields={"result": params["reason"]})
        raise ValueError("unknown task method")

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            peer = writer.get_extra_info("peername")
            if not peer or peer[0] not in {"127.0.0.1", "::1"}:
                raise ValueError("loopback client required")
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
            auth = [line.split(":", 1)[1].strip() for line in lines[1:]
                    if line.lower().startswith("authorization:")]
            token = auth[0][7:] if len(auth) == 1 and auth[0].startswith("Bearer ") else ""
            method = body["method"]
            params = body.get("params") or {}
            admin = hmac.compare_digest(token, self._admin_token)
            scoped = (method.startswith("task_") and bool(params.get("task_id"))
                      and self.journal.authorize_capability(token, params["task_id"]))
            reconcile = (method == "work_reconcile" and bool(params.get("task_id"))
                         and bool(params.get("command_id"))
                         and self.journal.authorize_reconcile_capability(
                             token, params["task_id"], params["command_id"]))
            if method == "work_reconcile" and not reconcile:
                raise ValueError("command-scoped reconciliation capability required")
            if method == "work_reconcile_capability" and not admin:
                raise ValueError("admin authorization required")
            if not (admin or scoped or reconcile):
                raise ValueError("task API authorization failed")
            if scoped and not method.startswith("task_"):
                raise ValueError("capability scope violation")
            result = {"result": await self.call(method, params,
                                                auth_token=token if reconcile else None)}
            status = "200 OK"
        except Exception as exc:  # noqa: BLE001
            # Do not echo task text, tokens, or provider exceptions over RPC.
            result = {"error": type(exc).__name__}
            status = "400 Bad Request"
        raw = json.dumps(result, ensure_ascii=False, default=str).encode()
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode() + raw)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _worker(self):
        while True:
            self.journal.db.execute("UPDATE daemon_owner SET heartbeat_at=? WHERE singleton=1 AND owner_id=?",
                                    (time.time(), self._owner_id))
            for task in self.journal.list_active():
                tid = task["task_id"]
                active = self._active_ticks.get(tid)
                if active is None or active.done():
                    self._active_ticks[tid] = asyncio.create_task(self._tick_task(tid))
            if self.publisher:
                try:
                    await asyncio.wait_for(self.publisher.flush(), timeout=10)
                except Exception as exc:  # noqa: BLE001 - sending remains pending/uncertain for reconciliation
                    logging.warning("Discord event flush needs reconciliation: %s", type(exc).__name__)
            await asyncio.sleep(2)

    async def _tick_task(self, task_id: str):
        verifying = False
        try:
            task = self.journal.get(task_id)
            verifying = task["state"] == "verifying"
            if verifying and not task["paused"]:
                remaining = self.verification_timeout_s - (time.time() - task["updated_at"])
                if remaining <= 0:
                    self.journal.change(task_id, "needs_ted", event="verification_deadline",
                                        fields={"result": "VerificationDeadlineExceeded"})
                    return
            if task["engine"] == "goose" and not self.goose.config.enabled:
                if task["state"] not in {"uncertain", "done", "failed"}:
                    self.journal.change(task_id, "uncertain", event="goose_disabled")
                return
            if task["engine"] != "goose" or task["state"] in {"queued", "verifying", "quota_limited", "uncertain"}:
                if verifying and not task["paused"]:
                    await asyncio.wait_for(self.coordinator.tick(task_id), timeout=remaining)
                else:
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
            goose_cwd = entry["cwd"]
            temporary_cwd = None
            # External BAT worktrees live on the host, while Goose ACP runs in
            # the connector process. Goose still requires an existing cwd for
            # session/new even though this recipe is MCP-only, so give it a
            # disposable local cwd rather than the remote SSH path.
            if not Path(goose_cwd).is_dir():
                temporary_cwd = tempfile.mkdtemp(prefix="batc-goose-")
                goose_cwd = temporary_cwd
            try:
                capability = self.journal.issue_capability(task_id)
                await self.goose.run_task(task, goose_cwd, capability=capability,
                                          journal=self.journal)
            except Exception as exc:  # noqa: BLE001 - reconcile before uncertainty
                logging.warning("Goose ACP task %s failed before settlement: %s", task_id[:8], exc)
                current = self.journal.get(task_id)
                try:
                    identity = await self.adapter.candidate_identity(current)
                    lead = await self.adapter.read(current, current["session_id"], current.get("turn_marker"))
                except Exception:  # noqa: BLE001 - failed readback remains uncertain
                    identity, lead = None, {}
                if (identity and identity.get("clean") and lead.get("streaming") is False
                        and not lead.get("pending")):
                    self.journal.command_status(cmd["command_id"], "settled")
                    self.journal.change(task_id, "verifying", fields={
                        "verification_commit": None, "verification_tree": None,
                        "reviewer_session_id": None, "review_commit": None,
                        "review_tree": None, "review_marker": None, "review_passed": 0,
                    }, event="goose_readback_settled")
                else:
                    self.journal.command_status(cmd["command_id"], "uncertain")
            else:
                self.journal.command_status(cmd["command_id"], "settled")
                if self.journal.get(task_id)["state"] == "running":
                    self.journal.change(task_id, "verifying", fields={
                        "verification_commit": None, "verification_tree": None,
                        "reviewer_session_id": None, "review_commit": None,
                        "review_tree": None, "review_marker": None, "review_passed": 0,
                    }, event="goose_settled")
            finally:
                if temporary_cwd:
                    shutil.rmtree(temporary_cwd, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001 - one task cannot kill worker
            logging.warning("Task %s needs reconciliation after %s", task_id[:8], type(exc).__name__)
            try:
                current = self.journal.get(task_id)
                if verifying and current["state"] == "verifying":
                    kind = "verification_timeout" if isinstance(exc, TimeoutError) else "verification_error"
                    self.journal.change(task_id, "needs_ted", event=kind,
                                        fields={"result": type(exc).__name__})
                elif current["state"] not in {"needs_ted", "done", "failed"}:
                    self.journal.change(task_id, "uncertain")
            except ValueError:
                pass
        finally:
            try:
                current = self.journal.get(task_id)
                if current["state"] in {"done", "failed"} and current.get("external_worktree_path"):
                    await self.adapter.cleanup_external_worktree(current)
                    self.journal.change(task_id, current["state"], fields={
                        "external_worktree_path": None, "external_branch": None})
            except Exception as cleanup_exc:  # noqa: BLE001 - cleanup is retried by operator
                logging.warning("Task %s external worktree cleanup failed: %s",
                                task_id[:8], type(cleanup_exc).__name__)

    async def serve(self, host: str = "127.0.0.1", port: int = 18796):
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("task service only binds loopback")
        self.acquire_owner()
        worker = None
        try:
            server = await asyncio.start_server(self._handle, host, port)
            worker = asyncio.create_task(self._worker())
            async with server:
                await server.serve_forever()
        finally:
            if worker is not None:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
            await self.fleet.close()
            self.journal.close()
            self.release_owner()

    def acquire_owner(self):
        if self._lease_fd is not None:
            return
        path = self.journal.path.parent / "task-daemon.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise RuntimeError("another task daemon owns this journal") from None
        self._lease_fd = fd
        self.journal.db.execute("""INSERT INTO daemon_owner(singleton,owner_id,pid,heartbeat_at)
            VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET owner_id=excluded.owner_id,
            pid=excluded.pid,heartbeat_at=excluded.heartbeat_at""", (self._owner_id, os.getpid(), time.time()))

    def release_owner(self):
        if self._lease_fd is not None:
            fcntl.flock(self._lease_fd, fcntl.LOCK_UN)
            os.close(self._lease_fd)
            self._lease_fd = None
