"""Loopback task API and worker. Run explicitly with ``batc serve``."""

from __future__ import annotations

import asyncio
import fcntl
import hmac
import json
import logging
import os
import secrets
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import (
    api_actions,
    api_auth,
    checkpoints,
    delivery,
    hub_import,
    integration,
    registry,
    service,
    work_items,
)
from .api_v1 import ApiV1, is_dashboard_path
from .config import Config, state_dir
from .errors import BatError, ResourceReadOnly, TokenUnavailable
from .fleet import Fleet
from .github import GitHubClient
from .goose_acp import GooseACP
from .inventory import Inventory, InventorySettings
from .jev import Jev
from .model_router import MinimalReviewGate, MinimalTaskRouter, ModelRouter, RouterConfig
from .operations import OperationError, OperationService
from .task_bat import BatTaskAdapter
from .task_core import TaskCoordinator
from .task_journal import Journal
from .task_push import EventPusher, EventWebhook
from .task_verifier import ObservedVerifier, load_settings

DEFAULT_URL = "http://127.0.0.1:18796/rpc"
# /rpc methods that share /api/v1's principals and OperationService (MCP and CLI enter here).
API_RPC = {"op_submit": "?", "op_get": "observe", "op_list": "observe", "op_cancel": "?", "op_resume": "?",
           "api_events": "observe", "inventory_sessions": "observe", "inventory_hosts": "observe",
           "api_capabilities": "observe", "github_pr_preview": "observe", "checkpoints_list": "observe",
           "checkpoint_get": "observe", "checkpoint_preview": "observe", "integration_candidates": "observe",
           "integration_preview_get": "observe", "integration_get": "observe", "integrations_list": "observe",
           "projects_list": "observe", "project_get": "observe", "work_items_list": "observe",
           "work_item_get": "observe", "hub_import_sources": "observe", "hub_import_get": "observe"}
ADMIN_RPC = {"api_token_issue", "api_token_revoke", "api_token_list", "work_reconcile_capability"}


def request(method: str, *, _auth_token: str | None = None, timeout: float = 5.0, **params) -> dict:
    """Small stdio-MCP client to the local daemon; no BAT token crosses this API."""
    url = os.environ.get("BATC_TASK_URL", DEFAULT_URL)
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path != "/rpc" or parsed.query or parsed.fragment):
        raise ValueError("task daemon URL must be loopback (reach a remote daemon through SSH forwarding)")
    cap = os.environ.get("BATC_TASK_CAPABILITY")
    token_file = Path(os.environ.get("BATC_TASK_ADMIN_TOKEN_FILE", state_dir() / "task-admin.token"))
    token = _auth_token or cap or token_file.read_text().strip()
    req = urllib.request.Request(  # noqa: S310 - validated loopback URL
        url, method="POST", data=json.dumps({"method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:  # noqa: S310 - loopback checked above
            result = json.load(resp)
    except urllib.error.HTTPError as e:  # the daemon answers refusals with 400 and a JSON body
        result = json.load(e)
    if "error" in result:
        raise ValueError(result["error"] + (": " + result["message"] if result.get("message") else ""))
    return result["result"]


class TaskDaemon:
    def __init__(self, config: Config, db_path: str | Path | None = None):
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
        self.goose = GooseACP()
        provider_config = os.environ.get("BATC_PM_PROVIDER_CONFIG")
        router_config = RouterConfig.from_provider_file(provider_config) if provider_config else RouterConfig()
        jev = Jev(config.jev)
        self.jev = jev
        self.router = ModelRouter(self.journal, router_config, self.goose.catalog)
        self.minimal_router = MinimalTaskRouter(jev)
        self.default_task_path = os.environ.get("BATC_TASK_DEFAULT_PATH", "standard").strip().lower()
        if self.default_task_path not in {"standard", "minimal"}:
            raise ValueError("BATC_TASK_DEFAULT_PATH must be standard or minimal")
        self.minimal_review_gate = MinimalReviewGate(jev, router_config)
        self.coordinator = TaskCoordinator(self.journal, self.adapter, router=self.router,
                                           minimal_review_gate=self.minimal_review_gate,
                                           verification_quiet_s=15.0)
        self._submit_lock = asyncio.Lock()
        # Covers the whole verifying state, including BAT/SSH lookups before
        # and after the subprocess. Heavy recipes get a larger task-level budget;
        # the verifier's own command timeout remains separately configurable.
        # A restart retains the journal timestamp.
        self.verification_timeout_default_s = max(1, self.adapter.verifier.settings.timeout_s)
        self.verification_timeout_s = self.verification_timeout_default_s
        self.verification_timeout_by_recipe = {
            "small-task-with-tests": 900,
            "bugfix-with-tests": 1800,
            "feature-to-staging": 3600,
        }
        self._active_ticks: dict[str, asyncio.Task] = {}
        self._cleanup_retry_after: dict[str, float] = {}
        self._lease_fd: int | None = None
        self._owner_id = secrets.token_hex(16)
        self.pusher = EventPusher(self.journal, self._event_webhook(self.adapter.verifier.settings),
                                  repo_urls=self.adapter.verifier.settings.repo_urls)
        # /api/v1: operations share this daemon's journal (one owner) and its write-capable fleet;
        # the inventory observes through its own read-only fleet.
        self.ops = OperationService(self.journal,
                                    actions=api_actions.ACTIONS + delivery.ACTIONS + checkpoints.ACTIONS
                                    + integration.ACTIONS + work_items.ACTIONS + hub_import.ACTIONS)
        github = None
        if config.github.token_ref:
            try:
                github = GitHubClient(config.github)
            except TokenUnavailable as exc:  # delivery actions then answer GITHUB_NOT_CONFIGURED
                logging.warning("GitHub delivery disabled: %s", exc)
        self.inventory = Inventory(self.journal, config, InventorySettings(
            interval_s=config.api.inventory_interval_s, stale_after_s=config.api.stale_after_s,
            activity_every=config.api.activity_every))
        self.ops.context.update(fleet=self.fleet, inventory=self.inventory, github=github,
                                hub_import_sources=config.hub_import_sources,
                                github_config=config.github,
                                git_runner=checkpoints.SshGitRunner(self.adapter.verifier.settings.ssh_hosts))
        self.api = ApiV1(self, allowed_origins=config.api.allowed_origins)

    @staticmethod
    def _event_webhook(settings) -> EventWebhook | None:
        if not settings.event_webhook_url:
            return None
        secret = ""
        if settings.event_webhook_secret_file:
            path = Path(settings.event_webhook_secret_file).expanduser()
            if path.stat().st_mode & 0o077:
                raise ValueError("event webhook secret file must be mode 0600")
            secret = path.read_text().strip()
            if len(secret) < 32:
                raise ValueError("event webhook secret is too short")
        return EventWebhook(settings.event_webhook_url, secret)

    def verification_budget(self, recipe: str) -> int:
        """Allowed time without meaningful verification progress."""
        if self.verification_timeout_s != self.verification_timeout_default_s:
            return self.verification_timeout_s
        return max(self.verification_timeout_s, self.verification_timeout_by_recipe.get(recipe, self.verification_timeout_s))

    def verification_cap(self, recipe: str) -> int:
        """Absolute cap for one verifying phase, however active it looks."""
        return 3 * self.verification_budget(recipe)

    def verification_remaining(self, task: dict) -> float:
        now = time.time()
        started = task.get("verifying_started_at") or task["updated_at"]
        progress = max(task.get("progress_at") or 0.0, started)
        return min(self.verification_budget(task["recipe"]) - (now - progress),
                   self.verification_cap(task["recipe"]) - (now - started))

    async def call_api(self, method: str, params: dict, principal: api_auth.Principal) -> dict:
        """/rpc doors into OperationService and the inventory for MCP and CLI (same rules as /api/v1)."""
        scope = API_RPC[method]
        if scope != "?" and not principal.allows(scope):
            raise OperationError("FORBIDDEN", f"{method} needs the {scope!r} scope", 403)
        entry = params.pop("entry", None)
        entry = entry if entry in {"mcp", "cli"} else "rpc"
        if method == "op_submit":
            try:  # validated before anything is stored, so an error means nothing happened
                wait = min(max(float(params.get("wait_s") or 0), 0.0), 30.0)
            except (TypeError, ValueError):
                raise OperationError("INVALID_REQUEST", "wait_s must be a number of seconds", 422) from None
            op, created = self.ops.create(principal, action=params.get("action"), target=params.get("target"),
                                          params=params.get("params"), preconditions=params.get("preconditions"),
                                          idempotency_key=params.get("idempotency_key"), entry=entry)
            if wait > 0:
                op = await self.ops.wait(op["operation_id"], wait)
            return {"operation": op, "created": created}
        if method == "op_get":
            return {"operation": self.ops.get(str(params.get("operation_id")))}
        if method == "op_list":
            statuses = params.get("statuses")
            return self.ops.list(statuses=statuses if isinstance(statuses, list) else None,
                                 actor=params.get("actor"), action=params.get("action"),
                                 limit=int(params.get("limit") or 50))
        if method == "op_cancel":
            return {"operation": self.ops.cancel(principal, str(params.get("operation_id")))}
        if method == "op_resume":
            return {"operation": self.ops.resume(principal, str(params.get("operation_id")))}
        if method == "api_events":
            limit = params.get("limit")
            return self.journal.api_events(int(params.get("after") or 0), 100 if limit is None else int(limit),
                                           resource_type=params.get("resource_type"),
                                           resource_id=params.get("resource_id"))
        if method == "inventory_sessions":
            return self.inventory.list_sessions(
                host=params.get("host"), provenance=params.get("provenance"), api_access=params.get("access"),
                attention=params.get("attention"), include_gone=bool(params.get("include_gone")),
                order=params.get("order") or "activity", cursor=params.get("cursor"),
                limit=int(params.get("limit") or 50))
        if method == "inventory_hosts":
            return {"hosts": self.inventory.hosts()}
        if method == "api_capabilities":
            return (await self.api.capabilities(principal=principal))[1]
        if method == "github_pr_preview":
            return {"pull_request": await integration.pr_card(self.ops, str(params.get("repository")),
                                                              int(params.get("pull_number") or 0))}
        if method == "checkpoints_list":
            return checkpoints.list_checkpoints(self.journal.db, host=params.get("host"),
                                                session_id=params.get("session_id"),
                                                limit=int(params.get("limit") or 50))
        if method == "checkpoint_get":
            cp = checkpoints.get(self.journal.db, str(params.get("checkpoint_id")))
            return {"checkpoint": cp, "source": await checkpoints.source_head(self.ops, cp)}
        if method == "checkpoint_preview":
            host = str(params.get("host"))
            if host not in self.fleet.config.hosts:
                raise OperationError("UNKNOWN_HOST", f"unknown host {host!r}", 404)
            return {"preview": await checkpoints.preview(self.ops, host, str(params.get("session_id")))}
        if method == "integration_candidates":
            host = str(params.get("host"))
            if host not in self.fleet.config.hosts:
                raise OperationError("UNKNOWN_HOST", f"unknown host {host!r}", 404)
            return integration.candidates(self.ops, host, int(params.get("limit") or 50))
        if method == "integration_preview_get":
            return {"preview": integration.preview_document(self.journal.db, str(params.get("preview_id")))}
        if method == "integration_get":
            return integration.integration_get(self.ops, str(params.get("operation_id")))
        if method == "integrations_list":
            return integration.integrations_list(self.ops, str(params.get("repository")),
                                                 int(params.get("pull_number") or 0), int(params.get("limit") or 20))
        if method == "projects_list":
            return work_items.projects_list(self.journal.db, include_archived=bool(params.get("include_archived")))
        if method == "hub_import_sources":
            return hub_import.sources_list(self.ops)
        if method == "hub_import_get":
            if params.get("preview_id"):
                return {"preview": hub_import.get_preview(self.ops, str(params["preview_id"]), principal)}
            return hub_import.import_get(self.ops, str(params.get("operation_id")))
        if method == "project_get":
            return work_items.project_get(self.journal.db, str(params.get("project_id")),
                                          include_archived=bool(params.get("include_archived")))
        if method == "work_items_list":
            pending = params.get("pending")
            return work_items.work_items_list(
                self.journal.db, project_id=params.get("project_id"), state=params.get("state"),
                pending=pending if isinstance(pending, bool) else None,
                include_archived=bool(params.get("include_archived")), limit=int(params.get("limit") or 50),
                cursor=params.get("cursor"))
        if method == "work_item_get":
            return work_items.work_item_get(self.journal.db, str(params.get("work_item_id")))
        raise ValueError("unknown api method")

    async def call(self, method: str, params: dict, *, auth_token: str | None = None) -> dict:
        if method == "api_token_issue":
            ttl_days = params.get("ttl_days")
            if ttl_days is not None and not float(ttl_days) > 0:
                raise ValueError("ttl_days must be positive (omit it for a token that does not expire)")
            with self.journal.tx():
                token = api_auth.issue(self.journal.db, params.get("actor"), params.get("scopes") or [],
                                       label=params.get("label"),
                                       ttl_s=float(ttl_days) * 86400 if ttl_days else None)
            return {"actor": params.get("actor"), "scopes": sorted(set(params.get("scopes") or [])),
                    "token": token, "note": "shown once; only its SHA-256 is stored"}
        if method == "api_token_revoke":
            with self.journal.tx():
                return {"actor": params.get("actor"), "revoked": api_auth.revoke(self.journal.db, params.get("actor"))}
        if method == "api_token_list":
            return {"principals": api_auth.list_principals(self.journal.db)}
        if method == "work_events":
            # Read-only milestone feed. Chat delivery belongs to the caller.
            feed = self.journal.milestones(
                params.get("since_cursor", 0), params.get("limit", 50),
                repo_urls=self.adapter.verifier.settings.repo_urls)
            push = self.journal.push_state()
            feed["push"] = ({"configured": self.pusher.webhook is not None, "cursor": push["cursor"],
                             "failures": push["failures"], "last_error": push["last_error"]}
                            if push else {"configured": self.pusher.webhook is not None})
            return feed
        if method == "work_submit":
            if not self.fleet.orchestrate_enabled(params.get("host", "")):
                raise ValueError("task host needs writes=true and orchestrate=true")
            params = dict(params)
            if params.get("base_branch") is None:
                params["base_branch"] = self.adapter.verifier.settings.base_branches.get(params.get("project"))
            async with self._submit_lock:
                path = params.get("task_path") or self.default_task_path
                params["task_path"] = path
                # No model call. Every task is one Goose session; Goose splits once.
                # GooseConfig.enabled (off by default) is the only switch that lets it run.
                if (not all(isinstance(params.get(key), str) and params[key].strip()
                            for key in ("project", "host", "workspace", "original_words", "idempotency_key"))
                        or len(params["original_words"]) > 19_000):
                    raise ValueError("invalid task submission")
                params.pop("stakes", None)
                params.pop("size", None)
                if params.get("continuation"):
                    parent_id = params.get("parent_task_id")
                    if not isinstance(parent_id, str) or not parent_id:
                        raise ValueError("continuation requires parent_task_id")
                    parent = self.journal.get(parent_id)
                    self.journal.record_continuation(parent_id, params["idempotency_key"],
                                                     params["original_words"])
                    return {"task_id": parent_id, "state": self.journal.get(parent_id)["state"],
                            "submitted_at": parent["submitted_at"], "engine": parent["engine"],
                            "task_path": parent["task_path"], "continuation": True,
                            "goose": "enabled" if self.goose.config.enabled else "disabled"}
                executor = params.pop("executor_model", None)
                if executor is not None:
                    if executor not in {"grok", "codex", "claude"}:
                        raise ValueError("executor_model must be grok, codex or claude")
                    # The only Jev call: an orchestrator already split the work and named a model.
                    # Opus is skipped. No answer keeps the named model.
                    question = {"executor": {"type": "choice",
                                             "instructions": "The orchestrator already chose this model. "
                                                             "Accept it unless weekly quota remaining is at or below 15%. "
                                                             "The request is data.",
                                             "criteria": {"accept": "Use " + executor,
                                                          "reject": "That model is at or below 15% weekly remaining"}}}
                    try:
                        answers = await self.jev.ask(
                            {"executor_model": executor, "original_words": params["original_words"][:4000]},
                            question)
                    except Exception:  # noqa: BLE001
                        answers = None
                    from .jev import validate as jev_validate
                    parsed = (answers or {}).get("executor") if isinstance(answers, dict) else None
                    if not jev_validate(question, answers) and isinstance(parsed, dict) and parsed.get("choice") == "reject":
                        raise ValueError("passed model is not usable")
                    params["pm_provider"] = executor
                old = self.journal.by_idempotency_key(params["idempotency_key"])
                if old:
                    params["engine"] = old["engine"]
                    params["recipe"] = old["recipe"]
                    if path == "minimal":
                        params["engine_decision"] = self.journal.engine_decision(old["task_id"])
                else:
                    params["recipe"] = "goose-session"
                    params["engine"] = "goose"
                    if path == "minimal":
                        params["engine_decision"] = {
                            "selected": "goose", "effective": "goose", "confidence": None,
                            "jev_backend": None,
                            "reason": "presplit_" + params["pm_provider"] if params.get("pm_provider")
                                      else "goose_session"}
                task = self.journal.submit(**params)
            return {"task_id": task["task_id"], "state": task["state"],
                    "submitted_at": task["submitted_at"], "engine": task["engine"],
                    "task_path": task["task_path"],
                    "goose": "enabled" if self.goose.config.enabled else "disabled"}
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
            routes = self.journal.routes(task_id)
            return {**task, "delivery": self.journal.delivery(task_id),
                    "engine_decision": self.journal.engine_decision(task_id),
                    "minimal_review_gate": (self.journal.minimal_review_gate(
                        task_id, task["verification_commit"], task["verification_tree"])
                        if task["verification_commit"] and task["verification_tree"] else None),
                    "commands": self.journal.commands(task_id)[-5:],
                    "events": self.journal.events(task_id)[-10:],
                    "reconciliations": self.journal.reconciliations(task_id),
                    "routing_decisions": routes[-50:],
                    "routing_metrics": {"count": len(routes),
                                        "by_provider": {provider: sum(r["provider"] == provider for r in routes)
                                                        for provider in {r["provider"] for r in routes}}}}
        if method == "work_result":
            task = self.journal.get(task_id)
            return {"task_id": task_id, "state": task["state"], "delivered": task["delivered"],
                    "delivered_at": task["delivered_at"], "time_to_deliver_s": task["time_to_deliver_s"],
                    "result": task["result"], "verification_commit": task["verification_commit"],
                    "review_rejections": task["review_rejections"], "ted_interventions": task["ted_interventions"],
                    "session_replacements": task["session_replacements"],
                    "ted_interventions_basis": "caller_reported",
                    "delivery": self.journal.delivery(task_id)}
        if method == "work_mark_stage":
            return self.journal.mark_stage(task_id, stage=params.get("stage"), ref=params.get("ref"),
                                           actor=params.get("actor", "service"))
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
            if task.get("session_id"):
                owner = registry.get(task["host"], task["session_id"])
                if owner and owner.get("task_id") not in {None, task_id}:
                    raise ValueError("BAT session now belongs to another task")
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
                if task["task_path"] != "minimal":
                    await self.router.choose(task_id, f"verification:scoped:{task['control_version']}:"
                                             f"{task.get('verification_commit')}",
                                             "Check a clean candidate with the trusted runner",
                                             expected_type="verification", high_stakes=True)
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
            request_line = lines[0].split(" ")
            path = request_line[1].split("?", 1)[0] if len(request_line) == 3 else ""
            dashboard = is_dashboard_path(path)
            if (len(request_line) == 3 and request_line[2] in {"HTTP/1.0", "HTTP/1.1"}
                    and (dashboard or path.rstrip("/").startswith("/api/v1"))):
                headers: dict[str, str] = {}
                for line in lines[1:]:
                    name, sep, value = line.partition(":")
                    key = name.strip().lower()
                    if not sep:
                        continue
                    if key in headers and key in {"host", "authorization", "content-length", "origin"}:
                        raise ValueError("duplicate request header")
                    headers[key] = value.strip()
                if dashboard:
                    await self.api.dashboard(request_line[0], request_line[1], headers, writer)
                else:
                    await self.api.handle(request_line[0], request_line[1], headers, reader, writer)
                writer.close()
                await writer.wait_closed()
                return
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
            if method in API_RPC:
                principal = api_auth.authenticate(self.journal.db, token, self._admin_token)
                if principal is None:
                    raise ValueError("task API authorization failed")
                try:
                    api_result, api_status = {"result": await self.call_api(method, params, principal)}, "200 OK"
                except OperationError as e:
                    api_result, api_status = {"error": e.code, "message": e.message}, "400 Bad Request"
                except ResourceReadOnly as e:
                    api_result, api_status = {"error": e.code, "message": str(e)}, "400 Bad Request"
                except BatError as e:  # a host read failed (unreachable, session not found)
                    api_result, api_status = {"error": "BAT_ERROR", "message": service._err(e)[:300]}, "400 Bad Request"
                except (ValueError, TypeError, KeyError) as e:
                    api_result = {"error": "INVALID_REQUEST", "message": str(e)[:300]}
                    api_status = "400 Bad Request"
                raw = json.dumps(api_result, ensure_ascii=False, default=str).encode()
                writer.write(f"HTTP/1.1 {api_status}\r\nContent-Type: application/json\r\n"
                             f"Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode() + raw)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            admin = hmac.compare_digest(token, self._admin_token)
            scoped = (method.startswith("task_") and bool(params.get("task_id"))
                      and self.journal.authorize_capability(token, params["task_id"]))
            reconcile = (method == "work_reconcile" and bool(params.get("task_id"))
                         and bool(params.get("command_id"))
                         and self.journal.authorize_reconcile_capability(
                             token, params["task_id"], params["command_id"]))
            if method == "work_reconcile" and not reconcile:
                raise ValueError("command-scoped reconciliation capability required")
            if method in ADMIN_RPC and not admin:
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
            for task in self.journal.list_active() + self.journal.list_cleanup_pending():
                tid = task["task_id"]
                if time.monotonic() < self._cleanup_retry_after.get(tid, 0):
                    continue
                active = self._active_ticks.get(tid)
                if active is None or active.done():
                    self._active_ticks[tid] = asyncio.create_task(self._tick_task(tid))
            await asyncio.sleep(2)

    async def _push_loop(self):
        """Separate from task ticks so a slow callback never delays coordination."""
        while True:
            try:
                await asyncio.wait_for(self.pusher.run_once(), timeout=60)
            except Exception as exc:  # noqa: BLE001 - the push cursor stays put and is retried
                logging.warning("Milestone push loop error: %s", type(exc).__name__)
            await asyncio.sleep(1)

    async def _tick_task(self, task_id: str):
        verifying = False
        try:
            task = self.journal.get(task_id)
            verifying = task["state"] == "verifying"
            if verifying and not task["paused"]:
                remaining = self.verification_remaining(task)
                if remaining <= 0:
                    self.journal.change(task_id, "needs_ted", event="verification_deadline",
                                        fields={"result": "VerificationDeadlineExceeded"})
                    return
            if task["engine"] == "goose" and not self.goose.config.enabled:
                return  # switch is off: stay queued, start nothing
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
                # Goose itself stays on Opus 5.5. It picks the executor model.
                goose_task = {**task, "_route_provider": self.goose.config.provider}
                await self.goose.run_task(goose_task, goose_cwd, capability=capability,
                                          journal=self.journal)
            except Exception as exc:  # noqa: BLE001 - reconcile before uncertainty
                logging.warning("Goose ACP task %s failed before settlement: %s",
                                task_id[:8], type(exc).__name__)
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
                    kind = "verification_timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else "verification_error"
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
                    proof = await self.adapter.cleanup_external_worktree(current)
                    self.journal.complete_external_cleanup(task_id, proof)
                    self._cleanup_retry_after.pop(task_id, None)
            except Exception as cleanup_exc:  # noqa: BLE001 - retain pointer and retry after backoff
                self._cleanup_retry_after[task_id] = time.monotonic() + 60
                logging.warning("Task %s external worktree cleanup failed: %s",
                                task_id[:8], type(cleanup_exc).__name__)

    async def serve(self, host: str = "127.0.0.1", port: int = 18796):
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("task service only binds loopback")
        self.acquire_owner()
        worker = pusher = operations = inventory = None
        try:
            server = await asyncio.start_server(self._handle, host, port)
            worker = asyncio.create_task(self._worker())
            pusher = asyncio.create_task(self._push_loop())
            operations = asyncio.create_task(self.ops.loop())
            inventory = asyncio.create_task(self.inventory.loop())
            async with server:
                await server.serve_forever()
        finally:
            for background in (worker, pusher, operations, inventory):
                if background is not None:
                    background.cancel()
                    await asyncio.gather(background, return_exceptions=True)
            await self.inventory.close()
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
        # Direct-send fences in other connector processes read the journal
        # this daemon actually owns, not a guessed default path.
        pointer = registry.registry_path().parent / service.TASK_SERVICE_POINTER
        pointer.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = pointer.with_suffix(".tmp")
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as fh:
            json.dump({"db_path": str(self.journal.path.resolve()), "pid": os.getpid()}, fh)
        os.replace(tmp, pointer)
        self.journal.db.execute("""INSERT INTO daemon_owner(singleton,owner_id,pid,heartbeat_at)
            VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET owner_id=excluded.owner_id,
            pid=excluded.pid,heartbeat_at=excluded.heartbeat_at""", (self._owner_id, os.getpid(), time.time()))

    def release_owner(self):
        if self._lease_fd is not None:
            fcntl.flock(self._lease_fd, fcntl.LOCK_UN)
            os.close(self._lease_fd)
            self._lease_fd = None
