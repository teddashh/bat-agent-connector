"""Bundled central launcher. Stdout is a private native IPC pipe, never a log.

The native client owns packaging/login startup; this process owns the ordinary
Python central. A durable manifest and kernel lease recover one installation.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__, api_auth, dashboard_sync
from .platform_files import (
    atomic_write,
    ensure_private_directory,
    lock,
    open_private_file,
    read_private,
    unlock,
)

PROTOCOL = 1
MANIFEST = "installation.json"


def _json(path):
    return json.loads(read_private(path))


def _write(path, value):
    atomic_write(path, (json.dumps(value, sort_keys=True) + "\n").encode())


@contextlib.contextmanager
def _locked(path, *, blocking=True):
    fd = open_private_file(path, os.O_RDWR | os.O_CREAT)
    try:
        lock(fd, blocking=blocking)
        try:
            yield
        finally:
            unlock(fd)
    finally:
        os.close(fd)


def _root(raw):
    path = Path(raw).expanduser().absolute()
    # Never follow an existing alias and then bless its target as this installation.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("managed data location must not contain symbolic links")
    ensure_private_directory(path)
    return path


def _manifest(root):
    doc = _json(root / MANIFEST)
    if (doc.get("protocol") != PROTOCOL or doc.get("data_dir") != str(root)
            or not re.fullmatch(r"[0-9a-f]{32}", doc.get("installation_id", ""))
            or doc.get("actor") != "desktop-" + doc["installation_id"]
            or doc.get("state") not in {"initializing", "ready"}):
        raise ValueError("installation manifest is invalid; preserve its data for recovery")
    if doc["state"] == "ready" and (not doc.get("server_id") or not doc.get("principal_id")):
        raise ValueError("installation identity is incomplete")
    return doc


def _prepare(root):
    path = root / MANIFEST
    if path.exists():
        return _manifest(root)
    # A directory with existing service data but no manifest is never a new installation.
    if any((root / name).exists() for name in ("state", "config", "identity.token", "installation.key")):
        raise ValueError("unclaimed installation data exists; automatic replacement is refused")
    ident = secrets.token_hex(16)
    doc = {"protocol": PROTOCOL, "installation_id": ident, "actor": "desktop-" + ident,
           "data_dir": str(root), "runtime_version": __version__, "state": "initializing"}
    _write(path, doc)
    return doc


def _endpoint(root):
    pointer = _json(root / "state" / "task-service.json")
    if pointer.get("db_path") != str(root / "state" / "tasks.sqlite3"):
        raise ValueError("service pointer belongs to another database")
    value = pointer.get("endpoint", "")
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port
            or parsed.path != "/rpc" or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("invalid owned service endpoint")
    return value.removesuffix("/rpc")


def _request(endpoint, path, *, token=None, body=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(endpoint + path,  # noqa: S310 - fixed loopback owned endpoint
        data=json.dumps(body).encode() if body is not None else None, headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            raise ValueError("managed service redirects are refused")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=2) as response:  # noqa: S310 - no proxies or redirects
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("managed service response exceeds its bound")
    return json.loads(raw)


def _proof(key, challenge, endpoint, server_id):
    data = json.dumps([PROTOCOL, challenge, endpoint, server_id], separators=(",", ":")).encode()
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def _verify(root, doc):
    endpoint = _endpoint(root)
    challenge = secrets.token_hex(32)
    result = _request(endpoint, "/api/v1/managed/identity?challenge=" + challenge)
    expected = _proof(read_private(root / "installation.key"), challenge, endpoint, doc.get("server_id"))
    if not hmac.compare_digest(str(result.get("proof", "")), expected):
        raise ValueError("owned service identity could not be verified")
    token = read_private(root / "identity.token").decode().strip()
    caps = _request(endpoint, "/api/v1/capabilities", token=token)
    if (caps.get("actor") != doc["actor"] or caps.get("desktop_identity") !=
            {"server_id": doc["server_id"], "principal_id": doc["principal_id"]}):
        raise ValueError("owned service personal identity changed; automatic replacement is refused")
    return {"protocol": PROTOCOL, "endpoint": endpoint, "actor": doc["actor"],
            "server_id": doc["server_id"], "principal_id": doc["principal_id"],
            "runtime_version": result.get("runtime_version", doc["runtime_version"]), "token": token}


def _service_command(root):
    prefix = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "bat_agent_connector.managed_runtime"]
    return [*prefix, "serve", "--data-dir", str(root)]


def _spawn(root):
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
               "close_fds": True, "cwd": str(root)}
    if getattr(sys, "frozen", False):
        options["env"] = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    with os.fdopen(open_private_file(root / "service.log", os.O_WRONLY | os.O_CREAT | os.O_TRUNC), "wb") as log:
        options["stderr"] = log
        return subprocess.Popen(_service_command(root), **options)  # noqa: S603 - fixed bundled self executable


def ensure(raw, *, timeout=45):
    root = _root(raw)
    with _locked(root / "launcher.lock"):
        doc = _prepare(root)
        ensure_private_directory(root / "state")
        # A locked service lease is evidence of an owner, not proof of its endpoint.
        try:
            with _locked(root / "state" / "task-daemon.lock", blocking=False):
                running = False
        except BlockingIOError:
            running = True
        child = None if running else _spawn(root)
        until = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < until:
            try:
                doc = _manifest(root)
                if doc["state"] == "ready":
                    return _verify(root, doc)
            except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
                last_error = type(error).__name__
            if child and child.poll() is not None:
                raise ValueError("managed service initialization failed; existing data was preserved")
            time.sleep(0.1)
        # Never kill a PID read from a pointer or create a second database after a failure.
        raise ValueError("managed service unavailable; retry this installation" +
                         (f" ({last_error})" if last_error else ""))


async def serve(raw):
    root = _root(raw)
    doc = _manifest(root)
    ensure_private_directory(root / "config")
    ensure_private_directory(root / "state")
    os.environ["BATC_STATE_DIR"] = str(root / "state")
    os.environ["BATC_CONFIG_DIR"] = str(root / "config")
    os.environ["BATC_CONFIG"] = str(root / "config" / "hosts.toml")
    # A packaged private installation must not accidentally adopt operator env recipes.
    for key in ("BATC_TASK_SETTINGS", "BATC_TASK_ADMIN_TOKEN_FILE", "BATC_TASK_CAPABILITY", "BATC_TASK_URL",
                "BATC_PM_PROVIDER_CONFIG", "BATC_DEVICE_ID"):
        os.environ.pop(key, None)
    from .config import load_config
    from .task_daemon import TaskDaemon
    config_path = root / "config" / "hosts.toml"
    if not config_path.exists():
        if doc["state"] != "initializing":
            raise ValueError("installation configuration is missing; automatic replacement is refused")
        atomic_write(config_path, b'[client]\nlabel = "Better Agent Dashboard"\n[hosts]\n')
    daemon = TaskDaemon(load_config(config_path), root / "state" / "tasks.sqlite3")
    daemon.acquire_owner()
    try:
        token_path = root / "identity.token"
        if not token_path.exists():
            if doc["state"] != "initializing":
                raise ValueError("personal credential is missing; automatic replacement is refused")
            with daemon.journal.tx():
                api_auth.revoke(daemon.journal.db, doc["actor"])
                token = api_auth.issue(daemon.journal.db, doc["actor"], api_auth.SCOPES, label="Managed desktop")
            atomic_write(token_path, token.encode())
        token = read_private(token_path).decode().strip()
        principal = api_auth.authenticate(daemon.journal.db, token, daemon._admin_token)
        if principal is None or principal.actor != doc["actor"]:
            raise ValueError("personal credential expired or revoked; automatic identity replacement is refused")
        identity = dashboard_sync.identity(daemon.journal, principal)
        if doc["state"] == "ready" and any(doc[k] != identity[k] for k in identity):
            raise ValueError("installation journal identity changed")
        key_path = root / "installation.key"
        if not key_path.exists():
            if doc["state"] != "initializing":
                raise ValueError("installation proof key is missing")
            atomic_write(key_path, secrets.token_bytes(32))
        key = read_private(key_path)
        doc.update(identity, state="ready", runtime_version=__version__)
        _write(root / MANIFEST, doc)
        daemon.managed_installation = {**doc, "data_dir": root}
        from . import managed_setup
        managed_setup.install(daemon)
        from .browser_sessions import BrowserSessions
        daemon.api.browser_sessions = BrowserSessions(daemon, root, doc["installation_id"])

        def prove(challenge, host):
            endpoint = daemon._endpoint.removesuffix("/rpc")
            if not re.fullmatch(r"[0-9a-f]{64}", challenge) or host != urlsplit(endpoint).netloc:
                raise ValueError("invalid managed identity challenge")
            return {"protocol": PROTOCOL, "runtime_version": __version__,
                    "proof": _proof(key, challenge, endpoint, doc["server_id"])}
        daemon.managed_proof = prove
        stopping = asyncio.Event()
        daemon.managed_stop = stopping
        # Port zero is published through the owned pointer and verified before any bearer is sent.
        service_task = asyncio.create_task(daemon.serve(port=0))
        stop_task = asyncio.create_task(stopping.wait())
        try:
            await asyncio.wait((service_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
            if service_task.done():
                await service_task
        finally:
            service_task.cancel()
            stop_task.cancel()
            await asyncio.gather(service_task, stop_task, return_exceptions=True)
    finally:
        if daemon._lease_fd is not None:
            daemon.journal.close()
            daemon.release_owner()


def main():
    parser = argparse.ArgumentParser(description="Managed desktop central runtime")
    parser.add_argument("command", choices=("ensure", "serve", "browser", "stop"))
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            asyncio.run(serve(args.data_dir))
            return
        if args.command == "stop":
            root = _root(args.data_dir)
            _manifest(root)
            with _locked(root / "launcher.lock"):
                try:
                    with _locked(root / "state" / "task-daemon.lock", blocking=False):
                        print(json.dumps({"protocol": 1, "stopped": True}), flush=True)
                        return
                except BlockingIOError:
                    pass
            result = _verify(root, _manifest(root))
            result = _request(result["endpoint"], "/api/v1/managed/stop", token=result["token"], body={})
            until = time.monotonic() + 30
            while True:
                try:
                    with _locked(root / "state" / "task-daemon.lock", blocking=False):
                        break
                except BlockingIOError:
                    if time.monotonic() >= until:
                        raise ValueError("owned service is still stopping") from None
                    time.sleep(0.1)
            print(json.dumps(result), flush=True)
            return
        result = ensure(args.data_dir)
        if args.command == "browser":
            result = _request(result["endpoint"], "/api/v1/managed/browser-file", token=result["token"], body={})
        print(json.dumps(result), flush=True)
    except Exception as error:  # no secrets, paths or arbitrary provider output on the native protocol
        failure = {"protocol": PROTOCOL, "error": "MANAGED_RUNTIME_UNAVAILABLE",
                   "message": type(error).__name__ + ": managed installation needs recovery",
                   "errno": getattr(error, "errno", None), "winerror": getattr(error, "winerror", None)}
        print(json.dumps(failure), file=sys.stderr if args.command == "serve" else sys.stdout, flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
