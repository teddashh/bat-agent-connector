"""/api/v1: the Dashboard's HTTP API, served by the task daemon on its existing loopback listener.

Every route needs a bearer token (the admin token or an API token from ``batc api-token issue``); the actor is taken
from the token. Reads come from the persisted inventory, the operation records and the event log; every change goes
through ``OperationService.create`` like MCP and CLI. Browsers are kept honest with a loopback Host check (DNS
rebinding), an Origin allowlist and bearer-only auth (no cookies, so no CSRF). Design: docs/design/api-v1.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from importlib import resources
from urllib.parse import parse_qs, unquote, urlsplit

from . import (
    __version__,
    api_auth,
    checkpoints,
    integration,
    pr_delivery,
    resource_policy,
    service,
    work_items,
)
from .errors import BatError, ResourceReadOnly
from .operations import STATES, OperationError

API_VERSION = 1
CONTRACT_VERSION = "2026-10-08"  # delivery Part A shares this contract change date; keep an ISO date
MAX_BODY = 200_000
MAX_STREAMS = 16
MAX_STREAMS_PER_ACTOR = 8  # several Dashboard tabs per person; reloads briefly overlap
REAUTH_S = 5.0  # an open event stream re-checks its token this often (revoked or expired tokens stop it)
STREAM_MAX_S = 1800.0
KEEPALIVE_S = 15.0
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
# The Dashboard is four static files; nothing else under /dashboard/ is served.
DASHBOARD_FILES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                   "i18n.js": "text/javascript; charset=utf-8", "app.css": "text/css; charset=utf-8"}
DASHBOARD_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; "
                 "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
_REASONS = {200: "OK", 202: "Accepted", 204: "No Content", 302: "Found", 400: "Bad Request", 401: "Unauthorized",
            403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large",
            422: "Unprocessable Entity", 429: "Too Many Requests", 500: "Internal Server Error",
            502: "Bad Gateway", 503: "Service Unavailable"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def _host_is_loopback(value: str) -> bool:
    host = value.strip()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.lower() in _LOOPBACK_HOSTS or re.fullmatch(r"127(\.\d{1,3}){3}", host) is not None


def _origin_ok(origin: str, allowed: tuple[str, ...]) -> bool:
    if origin in allowed:
        return True
    parts = urlsplit(origin)
    return parts.scheme in {"http", "https"} and _host_is_loopback(parts.netloc)


def is_dashboard_path(path: str) -> bool:
    return path in {"/", "/dashboard"} or path.startswith("/dashboard/")


def parse_wait(value) -> float:
    if value in (None, ""):
        return 0.0
    try:
        wait = float(value)
    except (TypeError, ValueError):
        raise ApiError(422, "INVALID_REQUEST", "wait must be a number of seconds") from None
    if not 0 <= wait <= 60:
        raise ApiError(422, "INVALID_REQUEST", "wait must be 0-60 seconds")
    return wait


class ApiV1:
    def __init__(self, daemon, *, allowed_origins: tuple[str, ...] = ()) -> None:
        self.daemon = daemon
        self.allowed_origins = allowed_origins
        self._streams = 0
        self._streams_by_actor: dict[str, int] = {}
        self.routes = [
            ("GET", r"/api/v1/version", self.version, None),
            ("GET", r"/api/v1/capabilities", self.capabilities, "observe"),
            ("GET", r"/api/v1/hosts", self.hosts, "observe"),
            ("GET", r"/api/v1/sessions", self.sessions, "observe"),
            ("GET", r"/api/v1/sessions/(?P<host>[^/]+)/(?P<sid>[^/]+)", self.session, "observe"),
            ("GET", r"/api/v1/sessions/(?P<host>[^/]+)/(?P<sid>[^/]+)/messages", self.messages, "observe"),
            ("GET", r"/api/v1/policy", self.policy, "observe"),
            ("GET", r"/api/v1/operations", self.operations, "observe"),
            ("POST", r"/api/v1/operations", self.create_operation, None),
            ("GET", r"/api/v1/operations/(?P<op>op_[0-9a-f]{32})", self.operation, "observe"),
            ("POST", r"/api/v1/operations/(?P<op>op_[0-9a-f]{32})/cancel", self.cancel_operation, None),
            ("POST", r"/api/v1/operations/(?P<op>op_[0-9a-f]{32})/resume", self.resume_operation, None),
            ("GET", r"/api/v1/events", self.events, "observe"),
            ("GET", r"/api/v1/tasks/(?P<task>[0-9a-f-]{8,64})", self.task, "observe"),
            ("GET", r"/api/v1/checkpoints", self.checkpoints, "observe"),
            ("GET", r"/api/v1/sessions/(?P<host>[^/]+)/(?P<sid>[^/]+)/checkpoint-preview", self.checkpoint_preview,
             "observe"),
            ("GET", r"/api/v1/checkpoints/(?P<cp>cp_[0-9a-f]{32})", self.checkpoint, "observe"),
            ("GET", r"/api/v1/repositories/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/pulls/(?P<number>\d{1,9})",
             self.pull_preview, "observe"),
            ("GET", r"/api/v1/delivery/previews/(?P<pv>mpv_[0-9a-f]{32})", self.merge_preview, "observe"),
            ("GET", r"/api/v1/integrations/candidates", self.integration_candidates, "observe"),
            ("GET", r"/api/v1/integrations/previews/(?P<pv>ipv_[0-9a-f]{32})", self.integration_preview, "observe"),
            ("GET", r"/api/v1/integrations", self.integrations, "observe"),
            ("GET", r"/api/v1/integrations/(?P<op>op_[0-9a-f]{32})", self.integration, "observe"),
            ("GET", r"/api/v1/projects", self.projects, "observe"),
            ("GET", r"/api/v1/projects/(?P<prj>prj_[0-9a-f]{20})", self.project, "observe"),
            ("GET", r"/api/v1/work-items", self.work_items, "observe"),
            ("GET", r"/api/v1/work-items/(?P<wi>wi_[0-9a-f]{20})", self.work_item, "observe"),
        ]

    # ------------------------------------------------------------------ plumbing
    def _cors(self, headers: dict[str, str]) -> str:
        """CORS headers only for an origin listed in [api] allowed_origins (the Dashboard itself is same-origin)."""
        origin = headers.get("origin")
        if not origin or origin not in self.allowed_origins:
            return ""
        return f"Access-Control-Allow-Origin: {origin}\r\nVary: Origin\r\n"

    async def handle(self, method: str, target: str, headers: dict[str, str], reader, writer) -> None:
        cors = ""
        try:
            if not _host_is_loopback(headers.get("host", "")):
                raise ApiError(400, "BAD_HOST", "Host must be a loopback address")
            origin = headers.get("origin")
            if origin and not _origin_ok(origin, self.allowed_origins):
                raise ApiError(403, "BAD_ORIGIN", "origin is not allowed")
            cors = self._cors(headers)
            if method == "OPTIONS":  # preflight: no token is sent, so nothing is decided here but CORS
                if not cors:
                    raise ApiError(403, "BAD_ORIGIN", "cross-origin requests need [api] allowed_origins")
                writer.write((
                    "HTTP/1.1 204 No Content\r\n" + cors
                    + "Access-Control-Allow-Methods: GET, POST\r\n"
                    "Access-Control-Allow-Headers: Authorization, Content-Type, Idempotency-Key, Last-Event-ID\r\n"
                    "Access-Control-Max-Age: 600\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").encode())
                with contextlib.suppress(Exception):
                    await writer.drain()
                return
            parts = urlsplit(target)
            path, query = parts.path.rstrip("/") or "/", parse_qs(parts.query)
            body = await self._read_body(method, headers, reader)
            token = self._bearer(headers)
            principal = api_auth.authenticate(self.daemon.journal.db, token, self.daemon._admin_token)
            if principal is None and method == "POST" and path == "/api/v1/operations":
                principal = self.daemon.capability_principal(
                    token, body.get("action"), body.get("target") or {},
                    headers.get("idempotency-key") or body.get("idempotency_key"))
            if path == "/api/v1/events/stream" and method == "GET":
                if principal is None:
                    raise ApiError(401, "UNAUTHORIZED", "a valid bearer token is required")
                if not principal.allows("observe"):
                    raise ApiError(403, "FORBIDDEN", "this route needs the 'observe' scope")
                await self._stream(query, headers, reader, writer, token=token, principal=principal, cors=cors)
                return
            fn, kwargs, scope = self._route(method, path)
            if fn != self.version:
                if principal is None:
                    raise ApiError(401, "UNAUTHORIZED", "a valid bearer token is required")
                if scope and not principal.allows(scope):
                    raise ApiError(403, "FORBIDDEN", f"this route needs the {scope!r} scope")
            status, payload = await fn(principal=principal, query=query, body=body, headers=headers, **kwargs)
        except ApiError as e:
            status, payload = e.status, {"error": {"code": e.code, "message": e.message}}
        except OperationError as e:
            status, payload = e.status, {"error": {"code": e.code, "message": e.message}}
        except ResourceReadOnly as e:
            status, payload = 403, {"error": {"code": e.code, "message": str(e)}}
        except (ValueError, TypeError) as e:
            status, payload = 422, {"error": {"code": "INVALID_REQUEST", "message": str(e)[:300]}}
        except KeyError:
            status, payload = 404, {"error": {"code": "NOT_FOUND", "message": "not found"}}
        except BatError as e:
            status, payload = 502, {"error": {"code": "BAT_ERROR", "message": service._err(e)[:300]}}
        except Exception as e:  # noqa: BLE001 - never echo internals
            status, payload = 500, {"error": {"code": "INTERNAL", "message": type(e).__name__}}
        await self._send_json(writer, status, payload, cors)

    async def dashboard(self, method: str, target: str, headers: dict[str, str], writer) -> None:
        """Static Dashboard files. They hold no data and need no token; the API calls they make do."""
        path = urlsplit(target).path
        extra = ""
        body = b""
        if not _host_is_loopback(headers.get("host", "")):
            status, ctype, body = 400, "text/plain; charset=utf-8", b"Host must be a loopback address\n"
        elif method not in {"GET", "HEAD"}:
            status, ctype, extra = 405, "text/plain; charset=utf-8", "Allow: GET, HEAD\r\n"
        elif path in {"/", "/dashboard"}:
            status, ctype, extra = 302, "text/plain; charset=utf-8", "Location: /dashboard/\r\n"
        else:
            name = path[len("/dashboard/"):] or "index.html"
            if name in DASHBOARD_FILES:
                status, ctype = 200, DASHBOARD_FILES[name]
                body = (resources.files(__package__) / "dashboard" / name).read_bytes()
            else:
                status, ctype, body = 404, "text/plain; charset=utf-8", b"not found\n"
        head = (f"HTTP/1.1 {status} {_REASONS[status]}\r\n"
                f"Content-Type: {ctype}\r\nContent-Length: {len(body)}\r\n{extra}"
                f"Cache-Control: no-cache\r\nContent-Security-Policy: {DASHBOARD_CSP}\r\n"
                "X-Frame-Options: DENY\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n"
                "Cross-Origin-Opener-Policy: same-origin\r\nConnection: close\r\n\r\n")
        writer.write(head.encode() + (b"" if method == "HEAD" else body))
        with contextlib.suppress(Exception):
            await writer.drain()

    @staticmethod
    def _bearer(headers: dict[str, str]) -> str:
        auth = headers.get("authorization", "")
        return auth[7:].strip() if auth.startswith("Bearer ") else ""

    @staticmethod
    async def _read_body(method: str, headers: dict[str, str], reader) -> dict:
        if method != "POST":
            return {}
        raw_length = headers.get("content-length", "0").strip()
        if not raw_length.isdigit():
            raise ApiError(400, "BAD_LENGTH", "invalid Content-Length")
        length = int(raw_length)
        if length > MAX_BODY:
            raise ApiError(413, "TOO_LARGE", "request body is too large")
        if length == 0:
            return {}
        try:
            raw = await asyncio.wait_for(reader.readexactly(length), 10)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            raise ApiError(400, "BAD_LENGTH", "the body is shorter than its Content-Length") from None
        try:
            body = json.loads(raw)
        except ValueError:
            raise ApiError(400, "BAD_JSON", "request body must be JSON") from None
        if not isinstance(body, dict):
            raise ApiError(422, "INVALID_REQUEST", "request body must be a JSON object")
        return body

    def _route(self, method: str, path: str):
        allowed = False
        for m, pattern, fn, scope in self.routes:
            match = re.fullmatch(pattern, path)
            if match:
                if m == method:
                    return fn, {k: unquote(v) for k, v in match.groupdict().items()}, scope
                allowed = True
        if allowed:
            raise ApiError(405, "METHOD_NOT_ALLOWED", "method not allowed")
        raise ApiError(404, "NOT_FOUND", "no such route")

    @staticmethod
    async def _send_json(writer, status: int, payload: dict, cors: str = "") -> None:
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode()
        head = (f"HTTP/1.1 {status} {_REASONS.get(status, 'Error')}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(raw)}\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
                f"{cors}Connection: close\r\n\r\n")
        writer.write(head.encode() + raw)
        with contextlib.suppress(Exception):
            await writer.drain()

    @staticmethod
    def _q(query: dict, name: str, default=None):
        values = query.get(name)
        return values[-1] if values else default

    def _int(self, query: dict, name: str, default: int) -> int:
        try:
            return int(self._q(query, name, default))
        except (TypeError, ValueError):
            raise ApiError(422, "INVALID_REQUEST", f"{name} must be an integer") from None

    def _bool(self, query: dict, name: str):
        value = self._q(query, name)
        if value is None:
            return None
        if value.lower() in {"1", "true", "yes"}:
            return True
        if value.lower() in {"0", "false", "no"}:
            return False
        raise ApiError(422, "INVALID_REQUEST", f"{name} must be true or false")

    # ------------------------------------------------------------------ routes
    async def version(self, **_):
        return 200, {"connector": __version__, "api_version": API_VERSION, "contract_version": CONTRACT_VERSION}

    async def capabilities(self, principal, **_):
        fleet = self.daemon.fleet
        gh_cfg = self.daemon.ops.context["github_config"]
        actions = [{"action": a.name, "scope": a.scope, "summary": a.summary, "allowed": principal.allows(a.scope)
                               and (a.name != "delivery.merge_and_deploy" or principal.allows("deploy"))}
                   for a in self.daemon.ops.actions.values()]
        hosts = [{"host": h, "observe": True, "writes": fleet.writes_enabled(h),
                  "orchestrate": fleet.orchestrate_enabled(h),
                  "managed_roots": list(fleet.config.host(h).managed_roots),
                  "shared_clone_worktrees": fleet.config.host(h).shared_clone_worktrees}
                 for h in fleet.config.hosts]
        return 200, {"actor": principal.actor, "scopes": sorted(principal.scopes), "api_version": API_VERSION,
                     "contract_version": CONTRACT_VERSION, "connector": __version__, "hosts": hosts,
                     "actions": actions, "operation_statuses": list(STATES),
                     "features": {"inventory": True, "events_stream": True, "operations": True, "work_items": True,
                                  "github": self.daemon.ops.context.get("github") is not None,
                                  "deploy": bool(gh_cfg.recipes),
                                  "metadata_update": self.daemon.ops.context.get("github") is not None,
                                  "merge_scope_preview": self.daemon.ops.context.get("github") is not None,
                                  "checkpoints": [h for h in fleet.config.hosts if self._can_continue(h)],
                                  "integration": [{"repository": r.repository,
                                                   "hosts": integration.usable_hosts(self.daemon.ops, r)}
                                                  for r in gh_cfg.repos.values() if r.integrate]},
                     "repositories": [{"repository": r.repository, "allow_merge": r.allow_merge, "allow_pr_update": r.allow_pr_update,
                                       "merge_methods": list(r.merge_methods)} for r in gh_cfg.repos.values()],
                     "deploy_recipes": [{"name": r.name, "repository": r.repository, "environment": r.environment,
                                         "mode": r.mode} for r in gh_cfg.recipes.values()]}

    def _can_continue(self, host: str) -> bool:
        runner = self.daemon.ops.context.get("git_runner")
        fleet = self.daemon.fleet
        return bool(runner and runner.available(host) and fleet.writes_enabled(host)
                    and fleet.orchestrate_enabled(host) and fleet.config.host(host).managed_roots)

    async def hosts(self, **_):
        return 200, {"hosts": self.daemon.inventory.hosts()}

    async def sessions(self, query, **_):
        return 200, self.daemon.inventory.list_sessions(
            host=self._q(query, "host"), provenance=self._q(query, "provenance"),
            api_access=self._q(query, "access"), attention=self._bool(query, "attention"),
            include_gone=bool(self._bool(query, "include_gone")), order=self._q(query, "order", "activity"),
            cursor=self._q(query, "cursor"), limit=self._int(query, "limit", 50))

    def _known_host(self, host: str) -> None:
        if host not in self.daemon.fleet.config.hosts:
            raise ApiError(404, "UNKNOWN_HOST", f"unknown host {host!r}")

    async def session(self, query, host, sid, **_):
        self._known_host(host)
        row = self.daemon.inventory.get_session(host, sid)
        db = self.daemon.journal.db
        out = {"session": row, "started_from": checkpoints.started_from(db, host, sid),
               "work_items": work_items.work_items_for(db, "session", f"{host}/{sid}")}
        if self._bool(query, "live"):
            out["policy"] = await resource_policy.session_policy(self.daemon.fleet, host, sid)
        elif row is None:
            raise ApiError(404, "NOT_FOUND", "session is not in the inventory (pass live=true to ask the host)")
        return 200, out

    async def messages(self, query, host, sid, **_):
        self._known_host(host)
        read = await service.session_read(
            self.daemon.inventory.fleet, host, sid, last_n=self._int(query, "last_n", 20),
            offset=self._int(query, "offset", 0), include_tools=bool(self._bool(query, "include_tools")),
            max_chars=self._int(query, "max_chars", 12_000), after=self._q(query, "after"))
        return 200, read

    async def policy(self, query, **_):
        host = self._q(query, "host")
        if host:
            self._known_host(host)
        names = [host] if host else list(self.daemon.fleet.config.hosts)
        return 200, {"hosts": [await resource_policy.session_policy(self.daemon.fleet, h) for h in names]}

    async def operations(self, query, **_):
        statuses = [s for s in (self._q(query, "status") or "").split(",") if s]
        before = self._q(query, "before")
        return 200, self.daemon.ops.list(statuses=statuses or None, actor=self._q(query, "actor"),
                                         action=self._q(query, "action"),
                                         before=float(before) if before else None,
                                         limit=self._int(query, "limit", 50))

    async def create_operation(self, principal, query, body, headers, **_):
        key = headers.get("idempotency-key") or body.get("idempotency_key")
        wait = parse_wait(self._q(query, "wait"))  # before anything is stored: a 422 must mean nothing happened
        op, created = self.daemon.ops.create(
            principal, action=body.get("action"), target=body.get("target"), params=body.get("params"),
            preconditions=body.get("preconditions"), idempotency_key=key, entry="http")
        if wait > 0:
            op = await self.daemon.ops.wait(op["operation_id"], wait)
        return (202 if created else 200), {"operation": op, "created": created}

    async def operation(self, op, **_):
        return 200, {"operation": self.daemon.ops.get(op),
                     "work_items": work_items.work_items_for(self.daemon.journal.db, "operation", op)}

    async def cancel_operation(self, principal, op, **_):
        return 200, {"operation": self.daemon.ops.cancel(principal, op)}

    async def resume_operation(self, principal, op, **_):
        return 200, {"operation": self.daemon.ops.resume(principal, op)}

    async def events(self, query, **_):
        return 200, self.daemon.journal.api_events(
            self._int(query, "after", 0), self._int(query, "limit", 100),
            resource_type=self._q(query, "resource_type"), resource_id=self._q(query, "resource_id"))

    async def pull_preview(self, owner, repo, number, query, **_):
        return 200, {"pull_request": await integration.pr_card(
            self.daemon.ops, f"{owner}/{repo}", int(number), self._q(query, "method"),
            from_event=self._q(query, "from_event") == "true")}

    async def merge_preview(self, pv, **_):
        return 200, {"preview": pr_delivery.get_preview(self.daemon.journal.db, pv)}

    async def integration_candidates(self, query, **_):
        host = self._q(query, "host")
        self._known_host(host or "")
        return 200, integration.candidates(self.daemon.ops, host, self._int(query, "limit", 50))

    async def integration_preview(self, pv, **_):
        return 200, {"preview": integration.preview_document(self.daemon.journal.db, pv)}

    async def integrations(self, query, **_):
        number = self._int(query, "pull_number", 0)
        if not self._q(query, "repository") or number <= 0:
            raise ApiError(422, "INVALID_REQUEST", "repository and pull_number are required")
        return 200, integration.integrations_list(self.daemon.ops, self._q(query, "repository"), number,
                                                  self._int(query, "limit", 20))

    async def integration(self, op, **_):
        return 200, integration.integration_get(self.daemon.ops, op)

    async def checkpoints(self, query, **_):
        return 200, checkpoints.list_checkpoints(self.daemon.journal.db, host=self._q(query, "host"),
                                                 session_id=self._q(query, "session_id"),
                                                 limit=self._int(query, "limit", 50))

    async def checkpoint(self, query, cp, **_):
        record = checkpoints.get(self.daemon.journal.db, cp)
        out = {"checkpoint": record}
        if self._bool(query, "live"):  # has the source moved on since? (the checkpoint itself never changes)
            out["source"] = await checkpoints.source_head(self.daemon.ops, record)
        return 200, out

    async def checkpoint_preview(self, host, sid, **_):
        self._known_host(host)
        return 200, {"preview": await checkpoints.preview(self.daemon.ops, host, sid)}

    async def projects(self, query, **_):
        return 200, work_items.projects_list(self.daemon.journal.db,
                                             include_archived=bool(self._bool(query, "include_archived")))

    async def project(self, query, prj, **_):
        return 200, work_items.project_get(self.daemon.journal.db, prj,
                                           include_archived=bool(self._bool(query, "include_archived")))

    async def work_items(self, query, **_):
        return 200, work_items.work_items_list(
            self.daemon.journal.db, project_id=self._q(query, "project_id"), state=self._q(query, "state"),
            pending=self._bool(query, "pending"), include_archived=bool(self._bool(query, "include_archived")),
            limit=self._int(query, "limit", 50), cursor=self._q(query, "cursor"))

    async def work_item(self, wi, **_):
        return 200, work_items.work_item_get(self.daemon.journal.db, wi)

    async def task(self, task, **_):
        return 200, {"task": await self.daemon.call("work_status", {"task_id": task})}

    # ------------------------------------------------------------------ SSE
    async def _stream(self, query: dict, headers: dict[str, str], reader, writer, *, token: str,
                      principal, cors: str = "") -> None:
        actor = principal.actor
        if self._streams >= MAX_STREAMS:
            raise ApiError(429, "TOO_MANY_STREAMS", "too many event streams are open")
        if self._streams_by_actor.get(actor, 0) >= MAX_STREAMS_PER_ACTOR:
            raise ApiError(429, "TOO_MANY_STREAMS", f"{actor} already has {MAX_STREAMS_PER_ACTOR} event streams open")
        try:
            after = int(headers.get("last-event-id") or self._q(query, "after", 0) or 0)
        except ValueError:
            raise ApiError(422, "INVALID_REQUEST", "after must be an integer") from None
        self._streams += 1
        self._streams_by_actor[actor] = self._streams_by_actor.get(actor, 0) + 1
        hangup = asyncio.ensure_future(reader.read(1))  # a client never sends after the request: EOF = gone
        try:
            writer.write(("HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\n"
                          f"X-Content-Type-Options: nosniff\r\n{cors}Connection: close\r\n\r\n").encode())
            await asyncio.wait_for(writer.drain(), 10)
            started = last_write = last_auth = time.monotonic()
            while time.monotonic() - started < STREAM_MAX_S:
                if time.monotonic() - last_auth >= REAUTH_S:
                    current = api_auth.authenticate(self.daemon.journal.db, token, self.daemon._admin_token)
                    if current is None or not current.allows("observe"):
                        return  # revoked or expired: stop sending; the client sees the stream end
                    last_auth = time.monotonic()
                page = self.daemon.journal.api_events(after, 100)
                for ev in page["events"]:
                    data = json.dumps(ev, ensure_ascii=False, default=str)
                    writer.write(f"id: {ev['seq']}\nevent: {ev['kind']}\ndata: {data}\n\n".encode())
                    after = ev["seq"]
                if page["events"]:
                    await asyncio.wait_for(writer.drain(), 10)
                    last_write = time.monotonic()
                    if page["has_more"]:
                        continue
                elif time.monotonic() - last_write > KEEPALIVE_S:
                    writer.write(b": keepalive\n\n")
                    await asyncio.wait_for(writer.drain(), 10)
                    last_write = time.monotonic()
                if writer.is_closing() or hangup.done():
                    return
                await asyncio.wait({hangup}, timeout=0.5)
        except (ConnectionError, asyncio.TimeoutError):
            return
        finally:
            hangup.cancel()
            self._streams -= 1
            self._streams_by_actor[actor] -= 1
            if not self._streams_by_actor[actor]:
                del self._streams_by_actor[actor]
