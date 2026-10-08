"""Reviewed connector resource cleanup (plan §23, E01/E02).

Preview is a pure read. Apply uses the existing operation journal and policy, keeps a ref before removing a
worktree, and leaves permanent receipts and original-ID aliases. Registry guards also protect stdio tools.
"""
from __future__ import annotations

import asyncio
import base64
import contextvars
import hashlib
import hmac
import json
import os
import posixpath
import re
import shlex
import time
import urllib.error
import urllib.request
from importlib import resources
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from . import integration, lifecycle, registry, resource_policy, service
from .api_auth import SCOPES
from .config import state_dir
from .errors import BatError, ResourceReadOnly
from .operations import (
    RERUN,
    ActionDef,
    AmbiguousOutcome,
    Cancelled,
    NeedsAttention,
    OperationError,
    StepFailed,
    Uncertain,
    _canonical,
)
from .resource_ids import worktree_id
from .safety import Audit

VERSION = "cleanup-1"
TTL_S = 900
READ_DEADLINE_S = 20.0
MAX_ITEMS = 500
MAX_TOKEN_BYTES = 16384
_HOST_LOCKS: dict[str, asyncio.Lock] = {}
_REPO_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}
_OWNER = contextvars.ContextVar("cleanup_operation", default=None)
REASONS = {
    "MANUAL_READ_ONLY": "A person created this resource; it is read-only.",
    "UNKNOWN_READ_ONLY": "Creation ownership is not proven.",
    "WORKDIR_NOT_MANAGED": "The workdir is outside the managed roots.",
    "BINDING_MISMATCH": "The resource does not match its creation binding.",
    "CLONE_NOT_OURS": "The repository has no matching connector creation markers.",
    "CLONE_CONFIG_TAMPERED": "Repository config or object storage is unsafe.",
    "OBSERVATION_UNAVAILABLE": "Live observation was unavailable within the host deadline.",
    "ACTIVE_WRITER": "A session is streaming or writing.",
    "SESSION_WAITING": "A session has a pending question, permission or queued turn.",
    "COMMAND_UNRESOLVED": "A command or external step has an unresolved outcome.",
    "ACTIVE_EXECUTION": "Another execution still needs this resource.",
    "CONTENT_REQUIRED": "An active integration preview or execution needs the content.",
    "TASK_OWNED": "The Task Service reclaims this resource; reviewed task cleanup comes later.",
    "UNCOMMITTED_CHANGES": "Uncommitted tracked, staged, untracked or ignored content exists.",
    "RESULTS_NOT_DELIVERED": "Delivery receipts do not cover all result commits.",
    "DELIVERY_UNCERTAIN": "Delivery has an unresolved outcome.",
    "RETENTION_RULE": "An explicit retention rule requires this content.",
    "SHARED_CONTAINER": "This container has shared resources.",
    "RETAINED_CONTENT_STORE": "The repository or pin carries retained content and evidence.",
    "REMOTE_OUT_OF_SCOPE": "Remote branch deletion is a separate action.",
    "RESOURCE_KIND_UNSUPPORTED": "This resource or Git state has no cleanup adapter.",
    "RESOURCE_CLEANED": "This resource generation has a confirmed cleanup tombstone.",
    "CLEANUP_IN_PROGRESS": "A cleanup operation has reserved this resource.",
    "TIER_DISABLED": "Cleanup needs the host write and orchestrate tiers.",
}


def _hash(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def migrate(journal):
    """Add cleanup facts on every open; numbered versions belong to data migrations."""
    db = journal.db
    with journal.tx():
        for ddl in (
            """CREATE TABLE IF NOT EXISTS cleanup_runs (operation_id TEXT PRIMARY KEY REFERENCES operations,
                preview_id TEXT NOT NULL, token_hash TEXT NOT NULL, fingerprint TEXT NOT NULL,
                document TEXT NOT NULL, accepted_actor TEXT NOT NULL, accepted_scopes TEXT NOT NULL,
                accepted_choices TEXT NOT NULL, validated_at REAL NOT NULL, supersedes_operation_id TEXT)""",
            """CREATE TABLE IF NOT EXISTS cleanup_receipts (operation_id TEXT NOT NULL REFERENCES cleanup_runs,
                resource_id TEXT NOT NULL, item_order INTEGER NOT NULL, plan TEXT NOT NULL, status TEXT NOT NULL,
                before_state TEXT NOT NULL, after_state TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                error TEXT, settled_by TEXT, retained_ids TEXT NOT NULL DEFAULT '[]', updated_at REAL NOT NULL,
                PRIMARY KEY(operation_id,resource_id))""",
            """CREATE TABLE IF NOT EXISTS cleanup_retained (retained_id TEXT PRIMARY KEY, resource_id TEXT NOT NULL,
                operation_id TEXT NOT NULL, step TEXT NOT NULL, revision_key TEXT NOT NULL, host TEXT NOT NULL,
                repository TEXT NOT NULL, ref TEXT NOT NULL, commit_sha TEXT NOT NULL, tree_sha TEXT NOT NULL,
                digest TEXT NOT NULL, creation_evidence TEXT NOT NULL, created_at REAL NOT NULL,
                UNIQUE(operation_id,resource_id,revision_key))""",
            """CREATE TABLE IF NOT EXISTS resource_tombstones (resource_id TEXT PRIMARY KEY, generation TEXT NOT NULL,
                host TEXT NOT NULL, kind TEXT NOT NULL, document TEXT NOT NULL, cleaned_at REAL NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS cleanup_aliases (kind TEXT NOT NULL, external_id TEXT NOT NULL,
                host TEXT NOT NULL, resource_id TEXT NOT NULL REFERENCES resource_tombstones,
                PRIMARY KEY(kind,external_id,host,resource_id))""",
            "CREATE INDEX IF NOT EXISTS cleanup_alias_lookup ON cleanup_aliases(external_id,host)",
            "CREATE INDEX IF NOT EXISTS cleanup_history_order ON resource_tombstones(cleaned_at,resource_id)",
        ):
            db.execute(ddl)


def _registry_document():
    path = registry.registry_path()
    try:
        d = json.loads(path.read_text())
    except FileNotFoundError:
        return {"sessions": [], "cleanup_guards": {}}
    except (OSError, ValueError):
        raise ResourceReadOnly("CLEANUP_IN_PROGRESS", "cleanup guard registry is unreadable") from None
    if (not isinstance(d, dict) or not isinstance(d.get("sessions", []), list) or
            not isinstance(d.get("cleanup_guards", {}), dict)):
        raise ResourceReadOnly("CLEANUP_IN_PROGRESS", "cleanup guard registry is invalid")
    return d


def guard(host=None, *, session_id=None, path=None, branch=None):
    """One refusal helper for every process; it never grants ownership and never creates a file."""
    for g in _registry_document().get("cleanup_guards", {}).values():
        if host is not None and g.get("host") != host:
            continue
        # A stopped session and a deleted branch do not retire their carrier worktree/repository.
        kind = g.get("kind")
        matches = session_id and session_id in g.get("session_ids", [])
        if kind == "local_branch":
            matches = matches or (branch and branch == g.get("branch") and path == g.get("path"))
        elif kind != "session":
            matches = matches or (path and path == g.get("path"))
        if not matches:
            continue
        if g["status"] == "cleaned":
            raise ResourceReadOnly("RESOURCE_CLEANED", "resource was cleaned; see /api/v1/cleanup-tombstones")
        if g["operation_id"] != _OWNER.get():
            raise ResourceReadOnly("CLEANUP_IN_PROGRESS", "resource is reserved by " + g["operation_id"])


def _mark(item, op_id, status):
    path = registry.registry_path()
    with registry._locked(path):
        d = _registry_document()
        guards = d.setdefault("cleanup_guards", {})
        old = guards.get(item["resource_id"])
        if old and old["operation_id"] == op_id and old["status"] == status:
            return
        if old and old["operation_id"] != op_id:
            raise ResourceReadOnly("CLEANUP_IN_PROGRESS", "resource has another cleanup owner")
        guard(item["host"], session_id=item.get("session_id"), path=item.get("path"), branch=item.get("branch"))
        guards[item["resource_id"]] = {
            "operation_id": op_id, "status": status, "host": item["host"], "kind": item["kind"], "path": item.get("path"),
            "branch": item.get("branch"), "generation": item["generation"],
            "session_ids": [item["session_id"]] if item.get("session_id") else [],
        }
        for e in d.get("sessions", []):
            if e.get("host") == item["host"] and e.get("session_id") == item.get("session_id"):
                e["cleanup_reservation"] = op_id if status == "reserved" else None
                if status == "cleaned":
                    e.update(status="cleaned", tombstone_resource_id=item["resource_id"])
        registry._write_document(path, d)


def _release(item, op_id):
    path = registry.registry_path()
    with registry._locked(path):
        d = _registry_document()
        old = d.get("cleanup_guards", {}).get(item["resource_id"])
        if old and old.get("status") == "reserved" and old["operation_id"] == op_id:
            del d["cleanup_guards"][item["resource_id"]]
            for e in d.get("sessions", []):
                if e.get("cleanup_reservation") == op_id and e.get("session_id") == item.get("session_id"):
                    e["cleanup_reservation"] = None
            registry._write_document(path, d)


def install(ops, admin_token):
    ops.context["cleanup_key"] = hmac.digest(admin_token.encode(), b"batc.cleanup.preview.v1", "sha256")
    for action in ACTIONS:
        if action.name not in ops.actions:
            ops.register(action)


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def decode_token(ops, token, *, allow_expired=False):
    try:
        version, raw, sig = token.split(".")
        if version != "v1" or len(token) > MAX_TOKEN_BYTES * 2:
            raise ValueError()
        payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if _b64(payload) != raw:
            raise ValueError()
        expected = hmac.digest(ops.context["cleanup_key"], b"v1." + payload, "sha256")
        if not hmac.compare_digest(_b64(expected), sig):
            raise ValueError()
        data = json.loads(payload)
        if _canonical(data).encode() != payload or data["exp"] != data["iat"] + TTL_S:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise OperationError("PREVIEW_TOKEN_INVALID", "invalid cleanup preview token", 409) from None
    if not allow_expired and time.time() >= data["exp"]:
        raise OperationError("PREVIEW_EXPIRED", "cleanup preview expired; preview again", 409)
    return data


def _target(ops, value):
    if not isinstance(value, dict):
        raise OperationError("INVALID_TARGET", "target must be an object", 422)
    kind = value.get("kind")
    key = {"work_item": "work_item_id", "checkpoint": "checkpoint_id", "integration": "operation_id",
           "host": "host"}.get(kind)
    if not key or set(value) - {"kind", key, "include_children"} or not isinstance(value.get(key), str):
        raise OperationError("INVALID_TARGET", "choose work_item, checkpoint, integration or host", 422)
    if "include_children" in value and (kind != "work_item" or not isinstance(value["include_children"], bool)):
        raise OperationError("INVALID_TARGET", "include_children applies only to work_item", 422)
    if kind == "host":
        if value[key] not in ops.context["fleet"].config.hosts:
            raise OperationError("UNKNOWN_HOST", "host is not configured", 404)
    else:
        table = {"work_item": "work_items", "checkpoint": "checkpoints", "integration": "operations"}[kind]
        row = ops.db.execute(f"SELECT * FROM {table} WHERE {key}=?", (value[key],)).fetchone()  # noqa: S608
        if not row or (kind == "integration" and not row["action"].startswith("integration.")):
            raise OperationError("NOT_FOUND", "cleanup target was not found", 404)
    return {"kind": kind, key: value[key], **({"include_children": value.get("include_children", False)}
                                              if kind == "work_item" else {})}


def _choices(value, principal=None):
    value = value or {}
    keys = {"discard_uncommitted", "release_undelivered"}
    if not isinstance(value, dict) or set(value) - keys:
        raise OperationError("INVALID_PARAMS", "unknown cleanup choice", 422)
    out = {}
    for key in sorted(keys):
        ids = value.get(key, [])
        if (not isinstance(ids, list) or len(ids) > MAX_ITEMS or
                not all(isinstance(x, str) and re.fullmatch(r"(?:cr|wt)_[0-9a-f]{32}", x) for x in ids)):
            raise OperationError("INVALID_PARAMS", key + " must contain resource IDs", 422)
        out[key] = sorted(set(ids))
    if out["discard_uncommitted"] and principal and not principal.allows("cleanup_discard"):
        raise OperationError("DISCARD_SCOPE_REQUIRED", "discard_uncommitted needs cleanup_discard", 403)
    return out


def _config(ops):
    cfg = ops.context["fleet"].config
    return _hash({"version": VERSION, "hosts": {k: {"roots": h.managed_roots, "profile": h.profile_id,
        "writes": h.writes, "orchestrate": h.orchestrate} for k, h in cfg.hosts.items()},
        "retention": vars(cfg.cleanup)})


def _resource(host, kind, intent, slot, **fields):
    generation = _hash([host, kind, intent, slot])
    return {"resource_id": "cr_" + generation[:32], "generation": generation, "kind": kind, "host": host,
            "creation_evidence": {"intent": intent, "slot": slot}, "original_ids": [], "relations": [],
            "consumers": [], "reasons": [], "overridden_reasons": [], "steps": [], "dependencies": [],
            **fields}


def _reason(item, code, **evidence):
    fact = {"code": code, "message": REASONS.get(code, code), **evidence}
    if fact not in item["reasons"]:
        item["reasons"].append(fact)


def _all(ops):
    """Project resource identities from authoritative creation facts, not folder-name ownership."""
    db, fleet = ops.db, ops.context["fleet"]
    regs = registry.list_entries()
    op_rows = [ops._decode(r) for r in db.execute("SELECT * FROM operations ORDER BY created_at")]
    cps = {r["checkpoint_id"]: dict(r) for r in db.execute("SELECT * FROM checkpoints")}
    pvs = {r["preview_id"]: dict(r) for r in db.execute("SELECT * FROM integration_previews")}
    items, worktrees, containers = {}, {}, {}

    def add(item):
        old = items.setdefault(item["resource_id"], item)
        for k in ("original_ids", "relations"):
            old[k] = sorted(set(old[k] + item[k]))
        return old

    def alias(item, *ids):
        item["original_ids"] = sorted(set(item["original_ids"] + [s for s in ids if s]))

    def wt(host, repo, path, branch, intent, flavor, base, ids, source=None):
        if not path or not repo or host not in fleet.config.hosts:
            return None
        key = host, path
        if key in worktrees:
            item = worktrees[key]
            alias(item, *ids)
            if (repo, branch) != (item["repository"], item["branch"]):
                _reason(item, "BINDING_MISMATCH")
            return item
        intent_type, slot = {"checkpoint": ("checkpoint.continue", "worktree"),
                             "repair": ("integration.handoff", "repair"),
                             "task": ("task", "external_worktree"), "bat": ("registry", "worktree")}[flavor]
        projected = _resource(host, "worktree", intent, slot, path=path, repository=repo, branch=branch,
                              flavor=flavor, base=base, source=source, proven=True)
        projected["resource_id"] = worktree_id(host, intent_type, intent, slot)
        projected["generation"] = _hash(["worktree", host, intent_type, intent, slot])
        projected["creation_evidence"].update(intent_type=intent_type)
        item = add(projected)
        alias(item, *ids)
        worktrees[key] = item
        ck = host, repo
        if ck not in containers:
            container = add(_resource(host, "integration_area" if flavor == "repair" else "clone", intent,
                                      repo, path=repo, repository=repo, proven=True, source=source))
            containers[ck] = container
        alias(containers[ck], *ids)
        return item

    for r in db.execute("SELECT * FROM checkpoint_runs ORDER BY created_at"):
        cp = cps[r["checkpoint_id"]]
        wt(r["host"], r["clone_path"], r["worktree_path"], r["branch"], r["operation_id"], "checkpoint",
           cp["commit_sha"], [r["checkpoint_id"], r["operation_id"], r["host"] + "/" + r["session_id"]],
           cp["repo_root"])
    for op in op_rows:
        if op["action"] == "checkpoint.continue":
            refs = op.get("external_refs") or {}
            cp = cps.get(op["target"].get("checkpoint_id"))
            prepare = db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='worktree.prepare'",
                                 (op["operation_id"],)).fetchone()
            repo = refs.get("clone_path")
            if cp and repo and prepare:
                temp = repo + ".batc-tmp-" + op["operation_id"][3:15]
                item = add(_resource(cp["host"], "temporary", op["operation_id"], temp,
                    path=temp, repository=repo, source=cp["repo_root"], proven=True,
                    original_ids=[op["operation_id"], cp["checkpoint_id"]]))
                add(_resource(cp["host"], "temporary", "container-lock:" + repo, repo + ".batc-lock",
                    path=repo + ".batc-lock", repository=repo, proven=False,
                    original_ids=[op["operation_id"], cp["checkpoint_id"]]))
    for op in op_rows:
        refs = op.get("external_refs") or {}
        host = refs.get("host") or op["target"].get("host")
        if op["action"] == "checkpoint.continue":
            cp = cps.get(op["target"].get("checkpoint_id"))
            if cp:
                host = cp["host"]
                wt(host, refs.get("clone_path"), refs.get("worktree_path"), refs.get("branch"),
                   op["operation_id"], "checkpoint", cp["commit_sha"],
                   [cp["checkpoint_id"], op["operation_id"], host + "/" + refs["session_id"]
                    if refs.get("session_id") else None], cp["repo_root"])
        if op["action"] == "integration.handoff":
            apply_id = op["target"].get("operation_id")
            ar = db.execute("SELECT * FROM integration_receipts WHERE operation_id=? AND seq=?",
                            (apply_id, refs.get("seq", op["params"].get("seq", 1)))).fetchone()
            pv = pvs.get(ar["preview_id"]) if ar else None
            if pv:
                wt(pv["host"], pv["area_path"], refs.get("worktree_path"), refs.get("branch"),
                   op["operation_id"], "repair", ar["integrated_sha"] or ar["pinned_sha"],
                   [op["operation_id"], apply_id, pv["preview_id"],
                    pv["host"] + "/" + refs["session_id"] if refs.get("session_id") else None],
                   {"host": pv["host"], "repository": pv["repository"], "remote-url": pv["remote_url"]})
        # A failed preview may not have produced integration_previews yet, but its prepare intent is durable.
        if op["action"] == "integration.preview" and host:
            step = db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='prepare'",
                              (op["operation_id"],)).fetchone()
            area = refs.get("area_path") or (json.loads(step[0]).get("area") if step else None)
            if area and (host, area) not in containers:
                repo = fleet.config.github.repos.get(op["target"].get("repository", "").lower())
                source = {"host": host, "repository": repo.repository, "remote-url": repo.integrate.remote_url} if repo else None
                item = add(_resource(host, "integration_area", op["operation_id"], area, path=area,
                                     repository=area, proven=bool(source), source=source))
                containers[host, area] = item
                alias(item, op["operation_id"])
    for pv in pvs.values():
        for source in json.loads(pv["sources"]):
            if source["kind"] == "branch":
                remote = add(_resource(pv["host"], "remote", "remote:" + pv["repository"], source["id"],
                    proven=False, ref=source.get("ref"), original_ids=[source["id"], pv["operation_id"], pv["preview_id"]]))
                remote["remote"] = True
        ck = pv["host"], pv["area_path"]
        if ck not in containers:
            containers[ck] = add(_resource(pv["host"], "integration_area", pv["operation_id"], pv["area_path"],
                path=pv["area_path"], repository=pv["area_path"], proven=True,
                source={"host": pv["host"], "repository": pv["repository"], "remote-url": pv["remote_url"]}))
        containers[ck].setdefault("source", {"host": pv["host"], "repository": pv["repository"], "remote-url": pv["remote_url"]})
        alias(containers[ck], pv["operation_id"], pv["preview_id"])
    for op in op_rows:
        if op["action"] not in {"integration.preview", "integration.apply"}:
            continue
        prepare = db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='prepare'",
                             (op["operation_id"],)).fetchone()
        if not prepare:
            continue
        host = op["target"].get("host")
        pv = pvs.get(op["params"].get("preview_id"))
        area = (pv or {}).get("area_path") or json.loads(prepare[0]).get("area")
        container = containers.get((host, area))
        if container:
            temp = area + "/repo.git.batc-tmp-" + op["operation_id"][3:15]
            add(_resource(host, "temporary", op["operation_id"], temp, path=temp, repository=area,
                source=container.get("source"), proven=bool(container.get("source")),
                original_ids=[op["operation_id"], *(([pv["preview_id"]]) if pv else [])]))
            for step_prefix, name in (("check.", "batc-check-"), ("push.", "batc-push-")):
                if db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name LIKE ?",
                              (op["operation_id"], step_prefix + "%")).fetchone():
                    path = area + "/repo.git/" + name + op["operation_id"][3:15]
                    add(_resource(host, "temporary", op["operation_id"], path, path=path, repository=area,
                                  proven=False, original_ids=[op["operation_id"], *(([pv["preview_id"]]) if pv else [])]))
    for task in db.execute("SELECT * FROM tasks ORDER BY submitted_at"):
        path = task["external_worktree_path"]
        if path:
            w = wt(task["host"], posixpath.dirname(posixpath.dirname(path)), path,
                   task["external_branch"], task["task_id"], "task", task["base_commit"], [task["task_id"]])
            if w:
                w["task_owned"] = True
    for e in regs:
        host, sid = e.get("host"), e.get("session_id")
        if host not in fleet.config.hosts or not sid:
            continue
        creation = f"{sid}@{e.get('created_at')}"
        path = e.get("worktree_path") or e.get("cwd") or e.get("origin_cwd")
        session = add(_resource(host, "session", creation, sid, session_id=sid, path=path, registry=e,
                               proven=bool(e.get("created_at")), task_owned=bool(e.get("task_id"))))
        alias(session, sid, host + "/" + sid, e.get("task_id"))
        if e.get("worktree_path") and (host, e["worktree_path"]) not in worktrees:
            # A successful legacy BAT create/start records its origin root, branch and worktree path together.
            proven = bool(e.get("created_at") and e.get("branch") and e.get("origin_root") and
                          e.get("status") in {"active", "superseded", "removed", "cleaned"} and
                          (host, e.get("origin_root")) in containers and not e.get("failover_of") and
                          e.get("worktree_made_by") != "connector")
            if proven or e.get("task_id"):
                w = wt(host, e.get("origin_root") or e.get("origin_cwd"), e["worktree_path"], e.get("branch"),
                       creation, "bat", e.get("start_commit") or e.get("base_commit"), [host + "/" + sid, e.get("task_id")])
                if w:
                    w["proven"] = proven
        w = worktrees.get((host, path))
        if w:
            alias(w, sid, host + "/" + sid, e.get("task_id"))
            w["task_owned"] = w.get("task_owned", False) or bool(e.get("task_id"))
            session["worktree_id"] = w["resource_id"]
            session["repository"] = w["repository"]
    # Include manual/unknown inventory and task leftovers even when the registry is incomplete.
    for r in db.execute("SELECT host,session_id,body,provenance FROM sessions_observed"):
        body = json.loads(r["body"])
        if any(i.get("session_id") == r["session_id"] and i["host"] == r["host"] for i in items.values()):
            continue
        item = add(_resource(r["host"], "session", "observed:" + r["session_id"], r["session_id"],
                             session_id=r["session_id"], path=body.get("cwd"), proven=False,
                             provenance=r["provenance"]))
        alias(item, r["host"] + "/" + r["session_id"])
    for task in db.execute("SELECT * FROM tasks"):
        host, path = task["host"], task["external_worktree_path"]
        if path and (host, path) not in worktrees:
            repo = posixpath.dirname(posixpath.dirname(path))
            w = wt(host, repo, path, task["external_branch"], task["task_id"], "task", task["base_commit"],
                   [task["task_id"]])
            if w:
                w["task_owned"] = True
        for i in items.values():
            if i["host"] == host and (i.get("path") == path or i.get("session_id") in
                                     {task["session_id"], task["reviewer_session_id"]} - {None}):
                i["task_owned"] = True
                alias(i, task["task_id"])
    links = [dict(r) for r in db.execute("SELECT * FROM work_item_links")]
    for i in items.values():
        i["relations"] = sorted({r["work_item_id"] for r in links if r["ref"] in i["original_ids"]})
    return items, op_rows, pvs, worktrees, containers, links


def _selection(ops, target, items, pvs, links):
    kind = target["kind"]
    if kind == "host":
        return {rid for rid, i in items.items() if i["host"] == target["host"]}, []
    key = target.get("checkpoint_id") or target.get("operation_id") or target.get("work_item_id")
    refs, wi_ids = {key}, []
    if kind == "work_item":
        wi_ids = [key]
        if target["include_children"]:
            todo = [key]
            while todo:
                parent = todo.pop()
                children = [r[0] for r in ops.db.execute("SELECT work_item_id FROM work_items WHERE parent_id=?", (parent,))
                            if r[0] not in wi_ids]
                wi_ids.extend(children)
                todo.extend(children)
        refs.update(r["ref"] for r in links if r["work_item_id"] in wi_ids)
    for pv in pvs.values():
        if pv["operation_id"] in refs or pv["preview_id"] in refs:
            refs.add(pv["preview_id"])
            refs.update(s["id"] for s in json.loads(pv["sources"]))
    selected = {rid for rid, i in items.items() if refs.intersection(i["original_ids"]) or
                set(wi_ids).intersection(i["relations"])}
    # The source of a checkpoint is always listed read-only, even when not in inventory.
    cp_ids = {r for r in refs if r.startswith("cp_")}
    for cp_id in cp_ids:
        cp = ops.db.execute("SELECT * FROM checkpoints WHERE checkpoint_id=?", (cp_id,)).fetchone()
        if cp:
            item = _resource(cp["host"], "source", "manual:" + cp["repo_root"], cp["repo_root"], path=cp["repo_root"], proven=False,
                             provenance="manual", original_ids=[cp_id, cp["host"] + "/" + cp["source_session_id"]])
            old = items.setdefault(item["resource_id"], item)
            old["original_ids"] = sorted(set(old["original_ids"] + item["original_ids"]))
            selected.add(item["resource_id"])
    # Opaque or remote links remain findable; they are never interpreted as paths.
    for r in links:
        if r["work_item_id"] in wi_ids and not any(r["ref"] in i["original_ids"] for i in items.values()):
            item = _resource("", "artifact", "link:" + str(r["link_id"]), r["ref"], proven=False,
                             original_ids=[r["ref"]], relations=[r["work_item_id"]])
            items[item["resource_id"]] = item
            selected.add(item["resource_id"])
    selected.update(i["resource_id"] for i in items.values() if i.get("worktree_id") in selected and i["kind"] == "session")
    return selected, wi_ids


async def _host_call(ops, host, req, timeout=READ_DEADLINE_S):
    runner = ops.context.get("git_runner")
    if not runner or not runner.available(host):
        raise OperationError("GIT_RUNNER_UNAVAILABLE", "no SSH runner for host", 409)
    source = (resources.files(__package__) / "cleanup_host.py").read_text()
    arg = base64.b64encode(_canonical({**req, "deadline_s": timeout}).encode()).decode()
    result = json.loads(await runner.run(host, "python3 -c " + shlex.quote(source) + " " + shlex.quote(arg),
                                        timeout_s=max(0.01, timeout)))
    if "error" in result:
        raise OperationError(result["error"], "host cleanup check refused", 409)
    return result["result"]


async def _runtime(ops, item, deadline):
    fleet = ops.context["inventory"].fleet  # read-only BAT fleet
    client = fleet.client(item["host"])
    async def read():
        meta = await service._meta(client, item["session_id"])
        state = None
        preset = (item.get("registry") or {}).get("agent_preset", "claude")
        kind = "codex" if "codex" in preset else "claude"
        if service._state_safe(kind, meta):
            state = await client.invoke("claude:get-session-state", {"sessionId": item["session_id"]})
        if isinstance(state, dict):
            # Runtime facts only: do not archive raw transcripts or prompt text in cleanup receipts.
            state = {k: (bool(v) if k.startswith("pending") or k in {"queuedMessages", "isWaitingForInput"} else v)
                     for k, v in state.items() if k in {"status", "sessionId", "isStreaming", "pendingAskUser",
                         "pendingPermission", "pendingQuestion", "pendingPermissions", "pendingQuestions",
                         "queuedMessages", "queuedMessageCount", "pendingApproval", "isWaitingForInput"}}
        return {"loaded": meta is not None, "cwd": (meta or {}).get("cwd"),
                "streaming": bool((meta or {}).get("isStreaming")), "state": state}
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise asyncio.TimeoutError()
        return await asyncio.wait_for(read(), remaining)
    except (BatError, OSError, asyncio.TimeoutError):
        return {"error": "OBSERVATION_UNAVAILABLE"}


def _coverage(ops, item, observed):
    coverage, prs, covered = [], [], set()
    full_head = False
    results = observed.get("results")
    head = observed.get("head")
    ids = set(item["original_ids"])
    for op_id in {r[0] for r in ops.db.execute("SELECT DISTINCT operation_id FROM integration_receipts")}:
        for r in integration.receipts(ops.db, op_id):
            # A repair result is covered by a delivered resolution receipt as well as source revisions.
            repair_host = ops.db.execute("SELECT host FROM integration_previews WHERE preview_id=?", (r["preview_id"],)).fetchone()
            match = (r["source_kind"] in {"checkpoint_run", "session"} and
                     r["source_host"] == item["host"] and r["location_class"] == "managed_clone" and
                     r["source_id"] in ids) or (r.get("repair_worktree") == item.get("path") and
                                               repair_host and repair_host[0] == item["host"])
            if not match:
                continue
            coverage.append({k: r.get(k) for k in ("operation_id", "seq", "source_kind", "source_id",
                "pinned_sha", "mode", "commits", "picked", "resolution_sha", "delivered_sha", "effective_status")})
            if r["effective_status"] == "unknown":
                _reason(item, "DELIVERY_UNCERTAIN", operation_id=op_id, seq=r["seq"])
            if r["effective_status"] != "delivered" or not r["delivered_sha"]:
                continue
            prs.append({"repository": r["repository"], "pull_number": r["pull_number"],
                        "delivered_sha": r["delivered_sha"]})
            if r["mode"] != "pick" and r["pinned_sha"] == head or r.get("resolution_sha") == head:
                full_head = True
                covered.update(results or [])
                covered.add(head)
            if r["mode"] == "pick":
                picked = r.get("picked") or []
                # Integration records a list of {source, picked}; all listed picks must have exact mappings.
                mapped = {p.get("source") for p in picked if p.get("new") and p.get("source")}
                covered.update(set(r.get("commits") or []) & mapped)
    no_result = results == [] and item.get("base") == head
    delivered = no_result or full_head or (results is not None and bool(results) and set(results) <= covered)
    return {"delivered": delivered, "no_result": no_result, "receipts": coverage,
            "result_commits": results, "covered_commits": sorted(covered), "pull_requests": prs}


def _consumers(ops, item, op_rows, pvs, own_op=None):
    ids = set(item["original_ids"])
    needles = ids | {v for v in (item.get("path") if item["kind"] != "local_branch" else item.get("branch"),) if v}
    for op in op_rows:
        if op["operation_id"] == own_op or op["action"] == "cleanup.apply":
            continue  # reservations below handle concurrent cleanup, without circular self-consumers
        text = _canonical([op["target"], op["params"], op.get("external_refs")])
        related = op["operation_id"] in ids or any(n in text for n in needles)
        if not related:
            continue
        unresolved = [r["name"] for r in ops.db.execute("SELECT name FROM operation_steps WHERE operation_id=? "
                     "AND status IN ('started','uncertain')", (op["operation_id"],))]
        if unresolved:
            _reason(item, "COMMAND_UNRESOLVED", operation_id=op["operation_id"], steps=unresolved)
        if op["status"] not in {"succeeded", "failed", "cancelled"}:
            fact = {"kind": "operation", "id": op["operation_id"], "status": op["status"]}
            item["consumers"].append(fact)
            _reason(item, "ACTIVE_EXECUTION", **fact)
    for command in ops.db.execute("SELECT * FROM commands WHERE status NOT IN ('succeeded','failed','cancelled')"):
        if (command["session_id"] and item["host"] + "/" + command["session_id"] in ids or
                command["task_id"] in ids):
            _reason(item, "COMMAND_UNRESOLVED", command_id=command["command_id"], status=command["status"])
    for pv in pvs.values():
        if pv["expires_at"] <= time.time():
            continue
        if any(s.get("id") in ids for s in json.loads(pv["sources"])):
            fact = {"kind": "integration_preview", "id": pv["preview_id"]}
            item["consumers"].append(fact)
            _reason(item, "CONTENT_REQUIRED", **fact)
    e = item.get("registry") or {}
    if e.get("status") in {"starting", "uncertain"} or e.get("handoff_status") == "pending":
        _reason(item, "COMMAND_UNRESOLVED", session_id=item.get("session_id"), status=e.get("status"))
    if e.get("retain_content") or e.get("retention_rule"):
        _reason(item, "RETENTION_RULE", rule=e.get("retention_rule") or "retain_content")
    try:
        guard(item["host"], session_id=item.get("session_id"), path=item.get("path"), branch=item.get("branch"))
    except ResourceReadOnly as e:
        _reason(item, e.code)


def _plan(ops, item, choices, op_rows, pvs, own_op=None):
    item["reasons"] = [r for r in item["reasons"] if r["code"] == "BINDING_MISMATCH"]
    item["consumers"] = []
    item["steps"] = []
    item["overridden_reasons"] = []
    kind, obs = item["kind"], item.get("observation") or {}
    if not item.get("proven"):
        _reason(item, "MANUAL_READ_ONLY" if item.get("provenance") == "manual" else "UNKNOWN_READ_ONLY")
    if item.get("task_owned"):
        _reason(item, "TASK_OWNED")
    if kind in {"clone", "integration_area", "git_pin", "retained_ref"}:
        _reason(item, "RETAINED_CONTENT_STORE")
    if kind == "remote":
        _reason(item, "REMOTE_OUT_OF_SCOPE")
    if kind in {"artifact", "source"}:
        _reason(item, "RESOURCE_KIND_UNSUPPORTED")
    hc = ops.context["fleet"].config.hosts.get(item["host"])
    if hc and kind in {"session", "worktree", "local_branch", "temporary"} and (not hc.writes or not hc.orchestrate):
        _reason(item, "TIER_DISABLED")
    if hc and not resource_policy.in_managed_root(hc, item.get("path") or item.get("repository")):
        _reason(item, "WORKDIR_NOT_MANAGED")
    if obs.get("error"):
        _reason(item, obs["error"] if obs["error"] in REASONS else "OBSERVATION_UNAVAILABLE")
    if item.get("live_host_unavailable"):
        _reason(item, "OBSERVATION_UNAVAILABLE")
    if item.get("repository_error"):
        code = item["repository_error"]
        _reason(item, code if code in REASONS else "OBSERVATION_UNAVAILABLE")
    if item.get("path_observation", {}).get("error") and obs.get("loaded"):
        _reason(item, item["path_observation"]["error"])
    _consumers(ops, item, op_rows, pvs, own_op)
    if kind == "session":
        if obs.get("streaming") or (isinstance(obs.get("state"), dict) and obs["state"].get("isStreaming")):
            _reason(item, "ACTIVE_WRITER")
        state = obs.get("state") or {}
        if isinstance(state, dict) and any(state.get(k) for k in
                ("pendingPermission", "pendingQuestion", "pendingPermissions", "pendingQuestions", "queuedMessages",
                 "pendingApproval", "pendingAskUser", "queuedMessageCount", "isWaitingForInput")):
            _reason(item, "SESSION_WAITING")
        if obs.get("loaded") and obs.get("cwd") != item.get("path"):
            _reason(item, "BINDING_MISMATCH")
        if obs.get("loaded") and not item["reasons"]:
            item["steps"] = ["stop", "finalize"]
    if kind in {"worktree", "local_branch"}:
        if kind == "worktree" and obs.get("exists"):
            if obs.get("branch") != item.get("branch") or not obs.get("registration"):
                _reason(item, "BINDING_MISMATCH")
            if obs.get("status"):
                _reason(item, "UNCOMMITTED_CHANGES", manifest=obs.get("manifest_digest"))
            if obs.get("complex_state") or any(f.get("type") != "file" for f in obs.get("manifest", [])):
                _reason(item, "RESOURCE_KIND_UNSUPPORTED")
        coverage = _coverage(ops, item, item.get("branch_observation", obs) if obs.get("exists") is False else obs)
        item["delivery"] = coverage
        if not coverage["delivered"]:
            _reason(item, "RESULTS_NOT_DELIVERED", receipts=coverage["receipts"])
        for code, choice in (("UNCOMMITTED_CHANGES", "discard_uncommitted"),
                             ("RESULTS_NOT_DELIVERED", "release_undelivered")):
            if (item["resource_id"] in choices[choice] and kind == "worktree" and
                    item.get("proven") and not item.get("task_owned")):
                matched = [r for r in item["reasons"] if r["code"] == code]
                item["overridden_reasons"].extend(matched)
                item["reasons"] = [r for r in item["reasons"] if r["code"] != code]
        if kind == "worktree" and obs.get("exists") and not item["reasons"]:
            item["steps"] = ["preserve", *(["discard"] if obs.get("status") else []), "remove.worktree", "finalize"]
        if kind == "local_branch" and obs.get("head") and not item["reasons"]:
            item["steps"] = ["preserve", "remove.branch", "finalize"]
    if kind == "temporary":
        if obs.get("exists"):
            if not obs.get("content_available"):
                _reason(item, "CONTENT_REQUIRED")
            if not obs.get("git_only"):
                _reason(item, "UNCOMMITTED_CHANGES")
            if not item["reasons"]:
                commits = sorted(set(obs.get("refs", {}).values()) | ({obs["head"]} if obs.get("head") else set()))
                obs["head"] = obs.get("head") or (commits[0] if commits else None)
                item["steps"] = [*(["preserve"] if commits else []), "remove.temporary", "finalize"]
        elif obs.get("exists") is False and not obs.get("error"):
            item["states"] = {"resource": "absent"}
    item["decision"] = "reclaim" if item["steps"] else "retain"
    item["states"] = {"work": "history", "runtime": "active" if obs.get("loaded") else "absent",
                      "delivery": "delivered" if item.get("delivery", {}).get("delivered") else "not_delivered",
                      "resource": "present" if obs.get("exists", obs.get("loaded", True)) else "absent"}
    if (kind == "session" and obs.get("loaded") is False or kind in {"worktree", "temporary"} and obs.get("exists") is False) and not obs.get("error"):
        item["decision"] = "already_absent" if not item["reasons"] else "retain"
    return item


async def snapshot(ops, target, choices, *, only=None, own_op=None):
    items, op_rows, pvs, worktrees, containers, links = _all(ops)
    selected, wi_ids = _selection(ops, target, items, pvs, links)
    hosts = sorted({items[r]["host"] for r in selected if items[r]["host"]})
    if len(selected) > MAX_ITEMS:
        raise OperationError("PREVIEW_TOO_LARGE", "preview exceeds 500 resources", 413)
    for host in hosts:
        deadline = time.monotonic() + READ_DEADLINE_S
        host_items = [i for i in items.values() if i["host"] == host]
        lock = _HOST_LOCKS.setdefault(host, asyncio.Lock())
        acquired = False
        try:
            await asyncio.wait_for(lock.acquire(), max(.001, deadline - time.monotonic()))
            acquired = True
            try:
                workspace = await asyncio.wait_for(service._workspace(ops.context["inventory"].fleet.client(host)),
                                                   max(.001, deadline - time.monotonic()))
                for t in workspace.get("terminals", []):
                    sid = t.get("id")
                    if not sid or any(i.get("session_id") == sid for i in host_items):
                        continue
                    meta = await asyncio.wait_for(service._meta(ops.context["inventory"].fleet.client(host), sid),
                                                  max(.001, deadline - time.monotonic()))
                    path = (meta or {}).get("cwd") or t.get("cwd")
                    w = worktrees.get((host, path))
                    i = _resource(host, "session", "observed:" + sid, sid, session_id=sid, path=path,
                        proven=False, provenance="manual" if sid not in {r.get("session_id") for r in registry.list_entries(host)} else "unknown",
                        original_ids=[sid, host + "/" + sid])
                    if w:
                        i.update(repository=w["repository"], worktree_id=w["resource_id"])
                    items[i["resource_id"]] = i
                    host_items.append(i)
                    if target["kind"] == "host" or w and w["resource_id"] in selected:
                        selected.add(i["resource_id"])
            except (BatError, OSError, asyncio.TimeoutError):
                for i in host_items:
                    if i["resource_id"] in selected:
                        i["live_host_unavailable"] = True
            # Observe all sessions in selected containers, including consumers outside the requested work item.
            repos = {i.get("repository") for i in host_items if i["resource_id"] in selected and i.get("repository")}
            if only:
                repos = {i.get("repository") for i in host_items if i["resource_id"] == only and i.get("repository")}
            for repo in sorted(repos):
                related = [i for i in host_items if i.get("repository") == repo]
                req = {"repository": repo, "roots": list(ops.context["fleet"].config.host(host).managed_roots),
                       "paths_only": bool(only),
                       "worktrees": [i["path"] for i in related if i["kind"] == "worktree" and
                           (not only or i["resource_id"] == only or i.get("branch_id") == only)],
                       "branches": {i["branch"]: i.get("base") for i in related if i["kind"] == "worktree" and i.get("branch")},
                       "replica_paths": [i["path"] for i in related if i.get("flavor") == "checkpoint"],
                       "temporaries": [i["path"] for i in related if i["kind"] == "temporary"],
                       "bases": {i["path"]: i["base"] for i in related if i["kind"] == "worktree" and i.get("base")}}
                try:
                    if time.monotonic() >= deadline:
                        raise asyncio.TimeoutError()
                    read = await asyncio.wait_for(_host_call(ops, host, req, deadline - time.monotonic()),
                                                  max(.001, deadline - time.monotonic()))
                except (BatError, OperationError, OSError, asyncio.TimeoutError, AmbiguousOutcome, ValueError) as e:
                    if getattr(e, "code", None) == "PREVIEW_TOO_LARGE":
                        raise OperationError("PREVIEW_TOO_LARGE", "repository observation exceeds cleanup limits", 413) from None
                    read = {"error": getattr(e, "code", "OBSERVATION_UNAVAILABLE")}
                carrier_source = (containers.get((host, repo)) or {}).get("source")
                markers = read.get("markers", {})
                if carrier_source and (isinstance(carrier_source, str) and markers.get("batc.source") != carrier_source or
                        isinstance(carrier_source, dict) and any(markers.get("batc." + k) != v for k,v in carrier_source.items())):
                    read["error"] = "CLONE_NOT_OURS"
                for i in related:
                    i["repository_identity"] = {k: read.get(k) for k in ("common_dir", "markers", "config_digest")}
                    i["repository_error"] = read.get("error")
                    if i["kind"] == "temporary":
                        i["observation"] = read.get("temporaries", {}).get(i["path"], {"error": "OBSERVATION_UNAVAILABLE"})
                        temp_markers = i["observation"].get("identity", {}).get("markers", {})
                        src = i.get("source")
                        if i["observation"].get("exists") and (isinstance(src, str) and temp_markers.get("batc.source") != src or
                                isinstance(src, dict) and any(temp_markers.get("batc." + k) != v for k,v in src.items())):
                            i["repository_error"] = "CLONE_NOT_OURS"
                    if i["kind"] == "worktree":
                        i["branch_observation"] = read.get("branches", {}).get(i.get("branch"), {})
                        i["observation"] = read.get("worktrees", {}).get(i["path"], {"error": read.get("error") or
                                                                                  "OBSERVATION_UNAVAILABLE"})
                        # Markers must also match original creation, not just the directory shape.
                        markers = read.get("markers", {})
                        src = i.get("source")
                        if src and isinstance(src, str) and markers.get("batc.source") != src:
                            i["repository_error"] = "CLONE_NOT_OURS"
                        if src and isinstance(src, dict) and (markers.get("batc.role") != "integration" or any(markers.get("batc." + k) != v for k, v in src.items())):
                            i["repository_error"] = "CLONE_NOT_OURS"
                container = containers.get((host, repo))
                for ref, sha in read.get("refs", {}).items():
                    if ref.startswith("refs/batc/"):
                        i = _resource(host, "git_pin", container["creation_evidence"]["intent"] if container else repo,
                                      ref, repository=repo, ref=ref, path=repo, proven=False,
                                      original_ids=(container or {}).get("original_ids", []),
                                      relations=(container or {}).get("relations", []), observation={"head": sha})
                        items[i["resource_id"]] = i
                        if container and container["resource_id"] in selected:
                            selected.add(i["resource_id"])
                for path, observed in read.get("worktrees", {}).items():
                    if (host, path) not in worktrees and path not in {repo, repo + "/repo.git"}:
                        i = _resource(host, "worktree", "unproven:" + repo, path, path=path, repository=repo,
                                      proven=False, observation=observed,
                                      original_ids=(container or {}).get("original_ids", []))
                        items[i["resource_id"]] = i
                        if container and container["resource_id"] in selected:
                            selected.add(i["resource_id"])
            for i in host_items:
                if i["kind"] == "session" and (i["resource_id"] in selected or i.get("repository") in repos):
                    if only and i["resource_id"] != only and i.get("repository") not in repos:
                        continue
                    i["observation"] = await _runtime(ops, i, deadline)
            sessions = [i for i in host_items if i["kind"] == "session" and i.get("proven") and i.get("path") and
                        i["resource_id"] in selected and (not only or i["resource_id"] == only)]
            if sessions:
                try:
                    paths = await asyncio.wait_for(_host_call(ops, host, {"canonical_paths": sorted({i["path"] for i in sessions}),
                        "roots": list(ops.context["fleet"].config.host(host).managed_roots)}, max(.01, deadline - time.monotonic())),
                        max(.001, deadline - time.monotonic()))
                except (BatError, OperationError, OSError, asyncio.TimeoutError, AmbiguousOutcome, ValueError):
                    paths = {}
                for i in sessions:
                    i["path_observation"] = paths.get(i["path"], {"error": "OBSERVATION_UNAVAILABLE"})
        except asyncio.TimeoutError:
            for i in host_items:
                if i["resource_id"] in selected:
                    i["observation"] = {"error": "OBSERVATION_UNAVAILABLE"}
        finally:
            if acquired:
                lock.release()
    for i in list(items.values()):
        if i["kind"] != "worktree" or i["resource_id"] not in selected or not i.get("proven"):
            continue
        obs = i.get("observation", {})
        branch_obs = i.get("branch_observation") or {"head": obs.get("head"), "results": obs.get("results")}
        if not branch_obs.get("head"):
            continue
        b = _resource(i["host"], "local_branch", i["creation_evidence"]["intent"], i.get("branch"),
                      path=i["repository"], repository=i["repository"], branch=i.get("branch"), proven=True,
                      flavor=i.get("flavor"), base=i.get("base"), observation=branch_obs, original_ids=i["original_ids"], relations=i["relations"],
                      task_owned=i.get("task_owned", False), worktree_id=i["resource_id"],
                      repository_identity=i.get("repository_identity"), repository_error=i.get("repository_error"))
        i["branch_id"] = b["resource_id"]
        items[b["resource_id"]] = b
        selected.add(b["resource_id"])
    for i in items.values():
        if i["resource_id"] in selected or i["kind"] == "session":
            _plan(ops, i, choices, op_rows, pvs, own_op)
    for rid in sorted(selected, key=lambda r: {"worktree": 0, "local_branch": 1}.get(items[r]["kind"], 2)):
        i = items[rid]
        if i["kind"] == "worktree":
            for s in items.values():
                if s["kind"] != "session" or s["host"] != i["host"] or s.get("path") != i.get("path"):
                    continue
                for reason in s["reasons"]:
                    if reason["code"] in {"ACTIVE_WRITER", "SESSION_WAITING", "COMMAND_UNRESOLVED", "TASK_OWNED",
                                          "OBSERVATION_UNAVAILABLE", "BINDING_MISMATCH", "CLEANUP_IN_PROGRESS"}:
                        _reason(i, reason["code"], session_id=s["session_id"])
                if s.get("observation", {}).get("loaded"):
                    if s["resource_id"] not in selected or s["decision"] != "reclaim":
                        _reason(i, "ACTIVE_EXECUTION", session_id=s["session_id"])
                    else:
                        i["dependencies"].append(s["resource_id"])
            if i["reasons"]:
                i.update(steps=[], decision="retain")
        if i["kind"] == "local_branch":
            w = items[i["worktree_id"]]
            absent_cleaned = w.get("observation", {}).get("exists") is False and all(
                r["code"] == "RESOURCE_CLEANED" for r in w["reasons"])
            if (w["decision"] in {"reclaim", "already_absent"} or absent_cleaned) and i.get("flavor") in {"checkpoint", "repair"}:
                i["dependencies"] = [w["resource_id"]] if w["decision"] == "reclaim" else []
            else:
                _reason(i, "CONTENT_REQUIRED", resource_id=w["resource_id"])
            if i.get("flavor") not in {"checkpoint", "repair"}:
                _reason(i, "RESOURCE_KIND_UNSUPPORTED")
            if i["reasons"]:
                i.update(steps=[], decision="retain")
    if len(selected) > MAX_ITEMS:
        raise OperationError("PREVIEW_TOO_LARGE", "preview exceeds 500 resources; narrow the target", 413)
    if set(choices["discard_uncommitted"] + choices["release_undelivered"]) - selected:
        raise OperationError("INVALID_PARAMS", "choice names a resource outside this target", 422)
    ordered = sorted((items[r] for r in selected), key=lambda i: ({"session": 0, "worktree": 1,
                     "local_branch": 2}.get(i["kind"], 3), i["host"], i["resource_id"]))
    # Registry volatile timestamps and self reservations must not change the content fingerprint.
    for i in ordered:
        if "registry" in i:
            i["registry"] = {k: v for k, v in i["registry"].items() if k not in
                             {"updated_at", "cleanup_reservation"}}
    return {"target": target, "choices": choices, "items": ordered, "work_items": wi_ids,
            "config_digest": _config(ops), "contract_version": VERSION}


async def preview(ops, principal, target, choices=None):
    if not principal.allows("observe"):
        raise OperationError("FORBIDDEN", "preview needs observe", 403)
    target, choices = _target(ops, target), _choices(choices, principal)
    doc = await snapshot(ops, target, choices)
    fingerprint = _hash(doc)
    now = int(time.time())
    payload = {"actor": principal.actor, "target": target, "choices": choices, "fingerprint": fingerprint,
               "config_digest": doc["config_digest"], "contract_version": VERSION, "iat": now, "exp": now + TTL_S,
               "ready": any(i["decision"] == "reclaim" for i in doc["items"])}
    raw = _canonical(payload).encode()
    if len(raw) > MAX_TOKEN_BYTES:
        raise OperationError("PREVIEW_TOO_LARGE", "preview token is too large", 413)
    token = "v1." + _b64(raw) + "." + _b64(hmac.digest(ops.context["cleanup_key"], b"v1." + raw, "sha256"))
    preview_id = "clpv_" + _hash(payload)[:32]
    return {**doc, "preview_id": preview_id, "preview_token": token, "fingerprint": fingerprint,
            "issued_at": now, "expires_at": now + TTL_S, "ready": payload["ready"],
            "blocking": [] if payload["ready"] else ["NO_RECLAIMABLE_RESOURCES"],
            "impact": {"reclaim": sum(i["decision"] == "reclaim" for i in doc["items"]),
                       "retain": sum(i["decision"] == "retain" for i in doc["items"]), "estimated_bytes": None,
                       "undelivered_commits_kept": [i["resource_id"] for i in doc["items"]
                           if any(r["code"] == "RESULTS_NOT_DELIVERED" for r in i["overridden_reasons"])]}}


def _admit(ops, principal, target, params, pre):
    if set(target) != {"preview_id"} or set(params) - {"preview_token", "supersedes_operation_id"} or set(pre) != {"preview_fingerprint"}:
        raise OperationError("INVALID_PARAMS", "apply accepts only the reviewed token and fingerprint", 422)
    payload = decode_token(ops, params.get("preview_token"))
    if (payload["actor"] != principal.actor or target["preview_id"] != "clpv_" + _hash(payload)[:32] or
            pre["preview_fingerprint"] != payload["fingerprint"]):
        raise OperationError("PREVIEW_MISMATCH", "actor, preview ID or fingerprint differs", 409)
    _choices(payload["choices"], principal)
    if not payload["ready"]:
        raise OperationError("PREVIEW_BLOCKED", "preview has no reclaimable resources", 409)
    # Admission runs after OperationService hashes the public request and before it persists params.
    # This server-only field records acceptance authority without changing OperationService or its table.
    params["_accepted_authorization"] = {"actor": principal.actor,
        "scopes": sorted(SCOPES if principal.admin else principal.scopes), "choices": payload["choices"]}


def apply_request(doc, key):
    return {"action": "cleanup.apply", "target": {"preview_id": doc["preview_id"]},
            "params": {"preview_token": doc["preview_token"]},
            "preconditions": {"preview_fingerprint": doc["fingerprint"]}, "idempotency_key": key}


def _receipt(ctx, item, status, **extra):
    ctx.service.db.execute("UPDATE cleanup_receipts SET status=?,updated_at=?,after_state=COALESCE(?,after_state),"
        "error=?,settled_by=COALESCE(?,settled_by) WHERE operation_id=? AND resource_id=?",
        (status, time.time(), _canonical(extra.get("after")) if extra.get("after") is not None else None,
         _canonical(extra.get("error")) if extra.get("error") else None, extra.get("settled_by"),
         ctx.operation_id, item["resource_id"]))


def _resumed_by(ctx):
    return [r["actor"] for r in ctx.service.db.execute("SELECT actor,body FROM api_events WHERE resource_id=? "
        "AND kind='operation.running' ORDER BY seq", (ctx.operation_id,)) if
        json.loads(r["body"]).get("from") == "needs_attention"]


def receipts(ops, op_id):
    out = []
    for r in ops.db.execute("SELECT * FROM cleanup_receipts WHERE operation_id=? ORDER BY item_order", (op_id,)):
        d = dict(r)
        for k in ("plan", "before_state", "after_state", "error", "retained_ids"):
            d[k] = json.loads(d[k]) if d[k] else None
        d["resumed_by"] = [r["actor"] for r in ops.db.execute("SELECT actor,body FROM api_events WHERE resource_id=? "
            "AND kind='operation.running' ORDER BY seq", (op_id,)) if json.loads(r["body"]).get("from") == "needs_attention"]
        out.append(d)
    return out


def _finalize(ctx, item, after):
    db, rid = ctx.service.db, item["resource_id"]
    retained_ids = [r[0] for r in db.execute("SELECT retained_id FROM cleanup_retained WHERE operation_id=? "
                                          "AND resource_id=?", (ctx.operation_id, rid))]
    doc = {**item, "operation_id": ctx.operation_id, "actor": ctx.actor, "reason": "reviewed_cleanup",
           "accepted_authorization": ctx.params["_accepted_authorization"], "last_observation": item.get("observation"),
           "after": after, "retained_ids": retained_ids, "receipt": {"operation_id": ctx.operation_id,
           "resource_id": rid}, "resumed_by": _resumed_by(ctx), "cleaned_at": time.time(),
           "pull_requests": item.get("delivery", {}).get("pull_requests", []),
           "attachment_replicas": "removed with worktree; originals in artifact store" if item.get("flavor") == "checkpoint" else None}
    with ctx.service.journal.tx():
        existing = db.execute("SELECT 1 FROM resource_tombstones WHERE resource_id=?", (rid,)).fetchone()
        if not existing:
            db.execute("INSERT INTO resource_tombstones VALUES(?,?,?,?,?,?)",
                       (rid, item["generation"], item["host"], item["kind"], _canonical(doc), doc["cleaned_at"]))
            aliases = [("original", x) for x in item["original_ids"] + item["relations"]]
            aliases += [("path", item["path"])] if item.get("path") else []
            aliases += [("ref", item["branch"])] if item.get("branch") else []
            for kind, external in aliases:
                db.execute("INSERT OR IGNORE INTO cleanup_aliases VALUES(?,?,?,?)", (kind, external, item["host"], rid))
            ctx.service.journal.api_event("cleanup", rid, "cleanup.cleaned", {"operation_id": ctx.operation_id,
                                         "kind": item["kind"], "retained_ids": retained_ids}, actor=ctx.actor)
        _receipt(ctx, item, "succeeded", after=after, settled_by="read_back")
        db.execute("UPDATE cleanup_receipts SET retained_ids=? WHERE operation_id=? AND resource_id=?",
                   (_canonical(retained_ids), ctx.operation_id, rid))
    _mark(item, ctx.operation_id, "cleaned")


def _progress(ctx):
    result = receipts(ctx.service, ctx.operation_id)
    summary = {"succeeded": sum(r["status"] == "succeeded" for r in result),
               "retained": sum(r["status"] == "retained" for r in result),
               "partial": any(r["status"] in {"failed", "blocked_stale", "uncertain", "running", "pending", "cancelled"} for r in result)}
    ctx.service._transition(ctx.operation_id, "running", result={"preview_id": ctx.target["preview_id"],
        "items": result, "summary": summary, "next_action": "inspect receipts; resume or preview again"})


async def _phase_consumers(ctx, item):
    ops = ctx.service
    probe = {**item, "reasons": [], "consumers": []}
    _consumers(ops, probe, [ops._decode(r) for r in ops.db.execute("SELECT * FROM operations")],
               {r["preview_id"]: dict(r) for r in ops.db.execute("SELECT * FROM integration_previews")}, ctx.operation_id)
    if probe["reasons"]:
        raise OperationError("PREVIEW_STALE", "new content consumer before mutation", 409)
    entries = registry.list_entries(item["host"])
    workspace = await service._workspace(ops.context["inventory"].fleet.client(item["host"]))
    for t in workspace.get("terminals", []):
        if t.get("id") and t.get("id") not in {e.get("session_id") for e in entries}:
            meta = await service._meta(ops.context["inventory"].fleet.client(item["host"]), t["id"])
            if (meta or {}).get("cwd") == item.get("path"):
                raise OperationError("PREVIEW_STALE", "a manual session uses this worktree", 409)
    for e in entries:
        if (e.get("worktree_path") or e.get("cwd")) != item.get("path"):
            continue
        if e.get("task_id") or e.get("status") in {"starting", "uncertain"} or e.get("handoff_status") == "pending":
            raise OperationError("PREVIEW_STALE", "a task or unresolved start needs this worktree", 409)
        runtime = await _runtime(ops, {"host": item["host"], "session_id": e["session_id"], "registry": e},
                                 time.monotonic() + READ_DEADLINE_S)
        if runtime.get("error") or runtime.get("loaded"):
            raise OperationError("PREVIEW_STALE", "a session still uses this worktree", 409)

async def _run(ctx):
    ops, db = ctx.service, ctx.service.db
    existing = db.execute("SELECT * FROM cleanup_runs WHERE operation_id=?", (ctx.operation_id,)).fetchone()
    if existing:
        # Acceptance is durable. A signing-key rotation cannot revoke an already accepted operation on resume.
        if existing["token_hash"] != _hash(ctx.params["preview_token"]):
            raise OperationError("PREVIEW_MISMATCH", "accepted token differs from journal", 409)
        raw = ctx.params["preview_token"].split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        doc = json.loads(existing["document"])
        if time.time() >= payload["exp"] and not db.execute("SELECT 1 FROM operation_steps WHERE operation_id=?", (ctx.operation_id,)).fetchone():
            raise OperationError("PREVIEW_EXPIRED", "preview expired before any external step", 409)
    else:
        # Admission already verified this token and durably recorded its authority in the operation params.
        # Key rotation after acceptance cannot revoke queued work; expiry before execution still applies.
        raw = ctx.params["preview_token"].split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if time.time() >= payload["exp"]:
            raise OperationError("PREVIEW_EXPIRED", "preview expired before execution", 409)
        doc = await snapshot(ops, payload["target"], payload["choices"], own_op=ctx.operation_id)
        if _hash(doc) != payload["fingerprint"]:
            raise OperationError("PREVIEW_STALE", "live resources or consumers changed; preview again", 409)
        with ops.journal.tx():
            auth = ctx.params["_accepted_authorization"]
            db.execute("INSERT INTO cleanup_runs VALUES(?,?,?,?,?,?,?,?,?,?)", (ctx.operation_id,
                ctx.target["preview_id"], _hash(ctx.params["preview_token"]), payload["fingerprint"], _canonical(doc),
                auth["actor"], _canonical(auth["scopes"]), _canonical(auth["choices"]), time.time(),
                ctx.params.get("supersedes_operation_id")))
            for order, item in enumerate(doc["items"]):
                db.execute("INSERT INTO cleanup_receipts(operation_id,resource_id,item_order,plan,status,before_state,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)", (ctx.operation_id, item["resource_id"], order, _canonical(item),
                    "pending" if item["decision"] == "reclaim" else "retained", _canonical(item.get("observation", {})), time.time()))
    ctx.set_refs(preview_id=ctx.target["preview_id"], fingerprint=payload["fingerprint"])
    owner = _OWNER.set(ctx.operation_id)
    try:
        for item in doc["items"]:
            if item["decision"] != "reclaim":
                continue
            row = db.execute("SELECT status FROM cleanup_receipts WHERE operation_id=? AND resource_id=?",
                             (ctx.operation_id, item["resource_id"])).fetchone()
            if row[0] == "succeeded":
                _mark(item, ctx.operation_id, "cleaned")
                continue
            unresolved = db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name LIKE ? "
                                    "AND status IN ('started','uncertain')", (ctx.operation_id, "item." + item["resource_id"] + ".%" )).fetchone()
            if not unresolved:
                ctx.check_cancel()
            if any(db.execute("SELECT status FROM cleanup_receipts WHERE operation_id=? AND resource_id=?",
                              (ctx.operation_id, dep)).fetchone()[0] != "succeeded" for dep in item["dependencies"]):
                _receipt(ctx, item, "failed", error={"code": "DEPENDENCY_FAILED"})
                continue
            lock = _REPO_LOCKS.setdefault((item["host"], item.get("repository") or item.get("path")), asyncio.Lock())
            async with lock:
                _mark(item, ctx.operation_id, "reserved")
                _receipt(ctx, item, "running")
                try:
                    await _execute_item(ctx, item, payload)
                except Uncertain:
                    _receipt(ctx, item, "uncertain")
                    _progress(ctx)
                    raise
                except (OperationError, ResourceReadOnly, StepFailed) as e:
                    code = getattr(e, "code", "CLEANUP_FAILED")
                    _receipt(ctx, item, "blocked_stale" if code == "PREVIEW_STALE" else "failed",
                             error={"code": code, "message": str(e)[:300]})
                    # A definitive refusal made no pending external call; keep its content and release the guard.
                    _release(item, ctx.operation_id)
                    _progress(ctx)
                    if code == "PREVIEW_STALE":
                        raise NeedsAttention(code, "item changed; keep receipts and preview again") from None
        result = receipts(ops, ctx.operation_id)
        if any(r["status"] == "failed" for r in result):
            _progress(ctx)
            raise NeedsAttention("CLEANUP_PARTIAL", "some items failed; inspect receipts before resuming")
        return {"preview_id": ctx.target["preview_id"], "fingerprint": payload["fingerprint"], "items": result,
                "summary": {"succeeded": sum(r["status"] == "succeeded" for r in result),
                            "retained": sum(r["status"] == "retained" for r in result), "partial": False},
                "tombstones": [r["resource_id"] for r in result if r["status"] == "succeeded"],
                "next_action": "cleanup_retained"}
    except Cancelled:
        # Cancel cannot abandon an unknown external outcome. Confirmed or unstarted items release their guards.
        for item in doc["items"]:
            row = db.execute("SELECT status FROM cleanup_receipts WHERE operation_id=? AND resource_id=?",
                             (ctx.operation_id, item["resource_id"])).fetchone()
            if row[0] in {"succeeded", "retained"}:
                continue
            unresolved = db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name LIKE ? "
                                    "AND status IN ('started','uncertain')", (ctx.operation_id, "item." + item["resource_id"] + ".%" )).fetchone()
            _receipt(ctx, item, "uncertain" if unresolved else "cancelled")
            if not unresolved:
                _release(item, ctx.operation_id)
        _progress(ctx)
        raise
    finally:
        _OWNER.reset(owner)


async def _execute_item(ctx, item, payload):
    """Validate once per item; named phases reconcile their own exact effects after a restart."""
    ops, rid = ctx.service, item["resource_id"]
    begun = ops.db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name LIKE ?",
                           (ctx.operation_id, "item." + rid + ".%" )).fetchone()
    if not begun:
        current = await snapshot(ops, payload["target"], payload["choices"], only=rid, own_op=ctx.operation_id)
        actual = next((i for i in current["items"] if i["resource_id"] == rid), None)
        # Earlier planned session stops / worktree removals change dependencies, never the item's content.
        if item["kind"] == "local_branch" and actual is None:
            actual = item  # ref is still checked by the host CAS below; consumers checked separately below
        if item["kind"] == "worktree" and actual:
            actual["dependencies"] = item["dependencies"]
        if actual != item:
            raise OperationError("PREVIEW_STALE", "resource or its consumers changed", 409)
    if item["kind"] == "session":
        async def stop():
            now = await _runtime(ops, item, time.monotonic() + READ_DEADLINE_S)
            if now != item["observation"]:
                raise OperationError("PREVIEW_STALE", "session changed before stop", 409)
            path = await _host_call(ops, item["host"], {"canonical_paths": [item["path"]],
                "roots": list(ops.context["fleet"].config.host(item["host"]).managed_roots)})
            if path.get(item["path"]) != item.get("path_observation") or path[item["path"]].get("error"):
                raise OperationError("PREVIEW_STALE", "session workdir changed before stop", 409)
            result = await lifecycle._stop(ops.context["fleet"], item["host"], item["session_id"],
                                          Audit(ops.context["fleet"].config.safety), cleanup=True)
            if not result.get("stopped"):
                raise OperationError("STOP_UNPROVEN", result.get("reason", "stop was not confirmed"), 409)
            if isinstance(result.get("result"), dict) and result["result"].get("ok") is False:
                raise AmbiguousOutcome("stop acknowledgment did not confirm termination")
            return result

        async def reconcile_stop(_):
            # Missing meta alone is not proof of stop. A healthy BAT explicit terminal state is required.
            now = await _runtime(ops, item, time.monotonic() + READ_DEADLINE_S)
            state = now.get("state") or {}
            if isinstance(state, dict) and state.get("status") in {"stopped", "exited"} and state.get("sessionId") == item["session_id"]:
                return {"stopped": True, "termination_evidence": state}
            return None
        await ctx.step("item." + rid + ".stop.a1", stop, request={"session_id": item["session_id"],
                       "before": item["observation"]}, reconcile=reconcile_stop)
        _finalize(ctx, item, {"stopped": True, "runtime_restored": False})
        return
    hc = ops.context["fleet"].config.host(item["host"])
    resource_policy.check_cleanup_worktree(hc, item["repository"], item["path"] if item["kind"] == "worktree" else None,
                                            item.get("branch") or "batc/temporary")
    if item["kind"] == "worktree":
        if item["flavor"] == "checkpoint":
            resource_policy.check_checkpoint_worktree(hc, item["repository"], item["path"], item["branch"])
        elif item["flavor"] == "repair":
            resource_policy.check_repair_worktree(hc, item["repository"], item["path"], item["branch"])
        else:
            resource_policy.check_cleanup_worktree(hc, item["repository"], item["path"], item["branch"])
    elif item["kind"] == "local_branch":
        resource_policy.check_cleanup_worktree(hc, item["repository"], None, item["branch"])
    sha = item["observation"].get("head")
    retained_ref = "refs/batc/retained/" + rid + "/" + sha if sha else None
    req = {"repository": item["repository"], "roots": list(hc.managed_roots), "identity": item["repository_identity"],
           "path": item["path"] if item["kind"] in {"worktree", "temporary"} else None, "kind": item["kind"],
           "temporaries": [item["path"]] if item["kind"] == "temporary" else [], "branch": item.get("branch"), "sha": sha,
           "retained_ref": retained_ref, "delivered": item.get("delivery", {}).get("delivered", False),
           "worktrees": [item["path"]] if item["kind"] == "worktree" else [],
           "paths_only": True, "replica_paths": [item["path"]] if item.get("flavor") == "checkpoint" else [],
           "bases": {item["path"]: item["base"]} if item.get("base") and item["kind"] == "worktree" else {}}
    before = item["observation"] if item["kind"] in {"worktree", "temporary"} else None

    async def read(*, probe=False):
        return await _host_call(ops, item["host"], {**{k: v for k, v in req.items() if k != "phase"}, "probe": probe})

    for phase in item["steps"]:
        if phase == "finalize":
            continue
        request = {**req, "phase": phase, "before": before}
        name = "item." + rid + "." + phase + ".a1"

        async def execute(request=request):
            ctx.check_cancel()
            await _phase_consumers(ctx, item)
            return await _host_call(ops, item["host"], request)

        async def reconcile(_, phase=phase, request=request):
            observed = await read(probe=True)
            pinned = observed.get("refs", {}).get(retained_ref) == sha
            if phase == "preserve" and pinned:
                commits = sorted(set(item["observation"].get("refs", {}).values()) | {sha}) if item["kind"] == "temporary" else [sha]
                result = await _host_call(ops, item["host"], {**req, "phase": "verify.retained",
                    "retained": [{"ref": retained_ref.rsplit("/", 1)[0] + "/" + commit, "commit_sha": commit} for commit in commits]})
                if all(p["available"] for p in result):
                    return {"ref": retained_ref, "sha": sha,
                            "tree": next(p["tree_sha"] for p in result if p["commit_sha"] == sha),
                            "pins": [{"ref": p["ref"], "sha": p["commit_sha"], "tree": p["tree_sha"]} for p in result]}
            if phase == "remove.worktree" and pinned:
                wt = observed.get("worktrees", {}).get(item["path"], {})
                if wt.get("exists") is False and wt.get("registration") is None:
                    return {"removed": True}
            if phase == "remove.temporary" and (pinned or sha is None) and observed.get("temporaries", {}).get(item["path"], {}).get("exists") is False:
                return {"removed": True}
            if phase == "remove.branch" and pinned and "refs/heads/" + item["branch"] not in observed.get("refs", {}):
                return {"deleted": True, "sha": sha}
            if phase == "discard" and pinned:
                wt = observed.get("worktrees", {}).get(item["path"], {})
                if wt.get("head") == sha and wt.get("status") == "" and not wt.get("complex_state"):
                    return {"discarded": True}
            if observed.get("process_ended") and observed.get("common_dir") == req["identity"]["common_dir"]:
                current = observed.get("worktrees", {}).get(item["path"])
                if phase in {"preserve", "remove.worktree", "discard"} and current == request["before"]:
                    return RERUN  # repository flock proves the earlier single-phase process ended without effect
                if phase == "remove.temporary" and pinned and observed.get("temporaries", {}).get(item["path"]) == request["before"]:
                    return RERUN
                if phase == "preserve" and item["kind"] == "temporary" and observed.get("temporaries", {}).get(item["path"]) == request["before"]:
                    return RERUN
                if phase == "remove.branch" and pinned and observed.get("refs", {}).get("refs/heads/" + item["branch"]) == sha:
                    return RERUN
            return None  # never retry when the remote process's outcome is unproven
        previous = ops.db.execute("SELECT name,status,error FROM operation_steps WHERE operation_id=? AND name LIKE ? ORDER BY seq DESC LIMIT 1",
                                  (ctx.operation_id, "item." + rid + "." + phase + ".a%" )).fetchone()
        if previous and previous["status"] == "failed" and json.loads(previous["error"] or "{}").get("code") == "WORKTREE_REMOVE_REFUSED":
            observed = await read(probe=True)
            if observed.get("worktrees", {}).get(item["path"]) != request["before"]:
                raise OperationError("PREVIEW_STALE", "failed removal no longer has its original binding", 409)
            n = int(previous["name"].rsplit(".a", 1)[1]) + 1
            name = "item." + rid + "." + phase + ".a" + str(n)
        elif previous:
            name = previous["name"]
        result = await ctx.step(name, execute, request=request, reconcile=reconcile)
        if phase == "preserve":
            for pin in result.get("pins", [result]):
                commit = pin["sha"]
                ret_id = "ret_" + _hash([rid, commit, item["repository"]])[:32]
                fact = {"host": item["host"], "repository": item["repository"], "ref": pin["ref"],
                        "commit": commit, "tree": pin["tree"]}
                ops.db.execute("INSERT OR IGNORE INTO cleanup_retained VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ret_id, rid, ctx.operation_id, name, commit, item["host"], item["repository"], pin["ref"], commit,
                     pin["tree"], _hash(fact), _canonical(item["creation_evidence"]), time.time()))
        if phase == "discard":
            observed = await read()
            before = observed["worktrees"][item["path"]]
    after = await read()
    if item["kind"] == "temporary":
        if after.get("temporaries", {}).get(item["path"], {}).get("exists") is not False:
            raise AmbiguousOutcome("temporary removal not confirmed")
    elif item["kind"] == "worktree":
        wt = after.get("worktrees", {}).get(item["path"], {})
        if wt.get("exists") or wt.get("registration"):
            raise AmbiguousOutcome("worktree removal not confirmed")
    elif "refs/heads/" + item["branch"] in after.get("refs", {}):
        raise AmbiguousOutcome("branch removal not confirmed")
    _finalize(ctx, item, {"removed": True, "retained_ref": retained_ref, "head": sha})


def lookup(db, original_id, host=None):
    rows = db.execute("SELECT DISTINCT t.document FROM resource_tombstones t LEFT JOIN cleanup_aliases a USING(resource_id) "
                      "WHERE (t.resource_id=? OR a.external_id=?) AND (? IS NULL OR t.host=?) ORDER BY t.cleaned_at DESC",
                      (original_id, original_id, host, host)).fetchall()
    return [json.loads(r[0]) for r in rows]


def tombstones(ops, *, query=None, host=None, original_id=None, work_item_id=None, kind=None, limit=50, cursor=None):
    limit = max(1, min(200, int(limit)))
    args, where = [], []
    for col, val in (("host", host), ("kind", kind)):
        if val:
            where.append(col + "=?")
            args.append(val)
    if cursor:
        try:
            stamp, rid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            where.append("(cleaned_at,resource_id)<(?,?)")
            args.extend([stamp, rid])
        except (ValueError, TypeError):
            raise OperationError("INVALID_PARAMS", "invalid history cursor", 422) from None
    search = original_id or work_item_id
    if search:
        where.append("resource_id IN (SELECT resource_id FROM cleanup_aliases WHERE external_id=?)")
        args.append(search)
    if query:
        where.append("document LIKE ? ESCAPE '\\'")
        args.append("%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    sql = "SELECT * FROM resource_tombstones" + (" WHERE " + " AND ".join(where) if where else "")  # noqa: S608 - fixed predicates, bound values
    rows = ops.db.execute(sql + " ORDER BY cleaned_at DESC,resource_id DESC LIMIT ?", (*args, limit + 1)).fetchall()
    page = rows[:limit]
    return {"tombstones": [json.loads(r["document"]) for r in page], "next_cursor":
            _b64(_canonical([page[-1]["cleaned_at"], page[-1]["resource_id"]]).encode()) if len(rows) > limit else None}


async def retained(ops, *, host=None, resource_id=None, query=None, limit=50, cursor=None):
    limit = max(1, min(200, int(limit)))
    rows = [dict(r) for r in ops.db.execute("SELECT * FROM cleanup_retained ORDER BY retained_id")]
    rows = [r for r in rows if (not host or r["host"] == host) and (not resource_id or r["resource_id"] == resource_id)
            and (not query or query.casefold() in _canonical(r).casefold()) and (not cursor or r["retained_id"] > cursor)]
    page = rows[:limit]
    available, unavailable = [], []
    groups = {}
    for r in page:
        groups.setdefault((r["host"], r["repository"]), []).append(r)
    for (h, repo), rs in groups.items():
        try:
            read = await _host_call(ops, h, {"phase": "verify.retained", "repository": repo,
                "roots": list(ops.context["fleet"].config.host(h).managed_roots), "retained": rs})
            for row in read:
                row["runtime_restored"] = False
                if not row["available"]:
                    row["reason"] = "RETAINED_CONTENT_MISSING"
                (available if row.pop("available") else unavailable).append(row)
        except (OperationError, BatError, OSError, AmbiguousOutcome, ValueError):
            unavailable.extend({**r, "reason": "OBSERVATION_UNAVAILABLE"} for r in rs)
    return {"retained": available, "unavailable": unavailable, "next_cursor": page[-1]["retained_id"] if len(rows) > limit else None,
            "retention": {"retained_refs": "keep", "history_retention": "forever", "permanent_delete": False}, "restore_available": False}


def http_request(path, *, body=None, token=None, key=None, timeout=40):
    """Thin loopback HTTP adapter for CLI/MCP, avoiding changes to the task RPC dispatcher."""
    parsed = urlsplit(os.environ.get("BATC_TASK_URL", "http://127.0.0.1:18796/rpc"))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError("task daemon URL must be loopback")
    auth = token or os.environ.get("BATC_API_TOKEN")
    if not auth:
        auth = Path(os.environ.get("BATC_TASK_ADMIN_TOKEN_FILE", state_dir() / "task-admin.token")).read_text().strip()
    headers = {"Authorization": "Bearer " + auth, "Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    req = urllib.request.Request(  # noqa: S310 - validated loopback HTTP
        parsed._replace(path=path.split("?", 1)[0], query=path.partition("?")[2], fragment="").geturl(),
        method="POST" if body is not None else "GET", data=_canonical(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as response:  # noqa: S310 - loopback
            out = json.load(response)
            status = response.status
    except urllib.error.HTTPError as e:
        out = json.load(e)
        status = e.code
    if "error" in out:
        raise OperationError(out["error"]["code"], out["error"]["message"], status)
    return out


def read_path(name, **filters):
    return "/api/v1/cleanup-" + name + "?" + urlencode({k: v for k, v in filters.items() if v is not None})


ACTIONS = [ActionDef("cleanup.apply", "cleanup", "Apply exactly a reviewed cleanup preview", _run,
                     admit=_admit, target_keys=("preview_id",))]
