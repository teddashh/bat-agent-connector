"""Journal-only resource history and relations. Projection writes belong to the existing writer's transaction."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from .operations import OperationError
from .redact import redact
from .resource_ids import registry_worktree_intent, worktree_id

MIGRATION_VERSION = 2  # One-time history backfill; data step allocated by the orchestrator.
RESOURCE_TYPES = {"session", "worktree", "execution"}
PRIVATE_FIELDS = {"text", "words", "original_words", "instructions", "excerpt", "prompt", "payload",
                  "token", "authorization", "note", "error", "lines", "messages", "interpretation",
                  "acceptance", "original_request", "requirements", "goal", "reason_text"}

SUMMARY_FIELDS = set("""host profile_id workspace workspace_id title cwd agent_kind agent_preset model loaded streaming
runtime_status pending field_evidence field_observed_at loading activity tab enumeration lifecycle freshness fields_stale worktree_branch orchestrated has_tab provenance api_access read_only_code isolation
provider_native_id first_seen_at last_seen_at observed_at gone_at misses changed_fields reason previous_reason
session_id previous_session_id session_resource_id execution_id task_id relation_id branch_id parent_branch_id parent_relation_id
follow_up_of_execution_id command_id command_ids start_command_id end_command_id kind status action from to
operation_id step step_seq request response refs target entry actor source evidence table id seq ref sha head
path retained_ref channel commit_sha source_sha base_sha integrated_sha resolution_sha delivered_sha pinned_sha commit tree_hash branch
worktree_path clone_path repo_root source_session_id checkpoint_id source_kind source_id source_host
repository repository_id pull_number preview_id mode location_class error_code accepted reconciled external_ref
message_id turn_marker turn_ref marker prompt_sha256 digest hash sha256 start_seq end_seq started_at ended_at
created_at updated_at submitted_at finished_at linked_at removed_at linked_by removed_by link_id link_operation
remove_operation work_item_id project_id needs_review source_table source_key saved_snapshot body backfilled
legacy anchor_id identity_evidence worktree_id intent_type intent_id slot coverage methods authority observer
scan_id binding_version attempted_binding_version last_success_at complete_enumeration errors outside_scan scope verified credential_ref
server_version capabilities enrichment_failures workspace_document workspace_ids registry_entries session_count
archive claude_transcripts session_meta safe_state journal workspace:load resource_id resource_type
runtime end_scope git_author author version verification_commit base_commit verification_tree before after
count n attempt status_reason source_versions result_versions files conflict seq pin commits source_key
""".split())

writer_context = ContextVar("observation_writer_context", default=None)


@contextmanager
def event_context(**fields):
    token = writer_context.set(fields)
    try:
        yield
    finally:
        writer_context.reset(token)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def body(value):
    if isinstance(value, dict):
        return value
    try:
        out = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def summary(value):
    if isinstance(value, dict):
        return {k: summary(v) for k, v in value.items() if k in SUMMARY_FIELDS and k not in PRIVATE_FIELDS
                and not (k in {"request", "response", "body"} and not isinstance(v, dict))}
    if isinstance(value, list):
        return [summary(v) for v in value]
    return redact(value) if isinstance(value, str) else value


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z") if value is not None else None


def install(journal):
    db = journal.db
    # Execute statements individually: executescript would commit the caller's migration transaction.
    statements = [
        """CREATE TABLE IF NOT EXISTS api_event_context(seq INTEGER PRIMARY KEY REFERENCES api_events(seq) ON DELETE CASCADE,
            context TEXT NOT NULL)""",
        """CREATE INDEX IF NOT EXISTS event_projection_errors ON api_event_context(seq)
            WHERE json_extract(context,'$.projection_error') IS NOT NULL""",
        """CREATE TABLE IF NOT EXISTS api_event_resources(seq INTEGER NOT NULL REFERENCES api_events(seq) ON DELETE CASCADE,
            resource_type TEXT NOT NULL,resource_id TEXT NOT NULL,linked_at_seq INTEGER NOT NULL,
            evidence_ref TEXT,PRIMARY KEY(seq,resource_type,resource_id))""",
        "CREATE INDEX IF NOT EXISTS event_resources_lookup ON api_event_resources(resource_type,resource_id,seq)",
        """CREATE TABLE IF NOT EXISTS observation_resources(resource_type TEXT NOT NULL,resource_id TEXT NOT NULL,
            body TEXT NOT NULL,PRIMARY KEY(resource_type,resource_id))""",
        """CREATE TABLE IF NOT EXISTS observation_relations(relation_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,
            session_resource_id TEXT NOT NULL,role TEXT NOT NULL,anchor_id TEXT NOT NULL,body TEXT NOT NULL,
            UNIQUE(execution_id,session_resource_id,role,anchor_id))""",
        """CREATE TABLE IF NOT EXISTS relation_revisions(relation_id TEXT NOT NULL,seq INTEGER NOT NULL,
            body TEXT NOT NULL,PRIMARY KEY(relation_id,seq))""",
        "CREATE INDEX IF NOT EXISTS relation_execution ON observation_relations(execution_id)",
        "CREATE INDEX IF NOT EXISTS relation_session ON observation_relations(session_resource_id)",
        """CREATE TABLE IF NOT EXISTS command_relations(command_id TEXT NOT NULL,relation_id TEXT NOT NULL,linked_at_seq INTEGER NOT NULL,
            PRIMARY KEY(command_id,relation_id))""",
        """CREATE TABLE IF NOT EXISTS discovery_latest(host TEXT NOT NULL,profile_id TEXT NOT NULL,
            binding TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(host,profile_id))""",
        """CREATE TABLE IF NOT EXISTS observation_backfill(source_key TEXT PRIMARY KEY,seq INTEGER NOT NULL)""",
    ]
    with journal.tx():
        for sql in statements:
            db.execute(sql)
        journal._observation_ready = True
        if db.execute("PRAGMA user_version").fetchone()[0] < MIGRATION_VERSION:
            backfill(journal)
            db.execute(f"PRAGMA user_version={MIGRATION_VERSION}")


def remember(db, kind, rid, **fields):
    old = db.execute("SELECT body FROM observation_resources WHERE resource_type=? AND resource_id=?",
                     (kind, rid)).fetchone()
    stored = body(old[0]) if old else {}
    data = {**stored, **{k: v for k, v in fields.items() if v is not None}}
    raw = dump(data)
    if old and raw == dump(stored):
        return
    db.execute("""INSERT INTO observation_resources VALUES(?,?,?) ON CONFLICT(resource_type,resource_id)
        DO UPDATE SET body=excluded.body""", (kind, rid, raw))


def index(db, seq, kind, rid, linked=None, evidence=None):
    if kind not in RESOURCE_TYPES or not rid:
        return
    db.execute("INSERT OR IGNORE INTO api_event_resources VALUES(?,?,?,?,?)",
               (seq, kind, rid, linked or seq, evidence))
    remember(db, kind, rid)


def worktree(db, host, intent_type, intent_id, slot, *, path=None, branch=None, session_id=None, clone=None):
    wid = worktree_id(host, intent_type, str(intent_id), slot)
    remember(db, "worktree", wid, host=host, intent_type=intent_type, intent_id=intent_id, slot=slot,
             worktree_path=path, branch=branch, clone_path=clone, identity_evidence="creation_intent")
    if session_id:
        remember(db, "session", f"{host}/{session_id}", host=host, session_id=session_id, worktree_id=wid)
    return wid


def registry_bindings(journal, host, entries):
    """Capture already-known creation slots, without claiming or modifying the registry."""
    db = journal.db
    by_id = {e["session_id"]: e for e in entries if e.get("session_id")}
    roots = {f"{sid}@{str(e['created_at'])}": e for sid, e in by_id.items() if e.get("created_at") is not None}
    seen = set()
    resolved = {}

    def lead_of(task_id):
        t = db.execute("SELECT session_id FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return t[0] if t else None

    def one(sid):
        if sid in resolved:
            return resolved[sid]
        if sid in seen:
            return None
        seen.add(sid)
        e = by_id[sid]
        intent = registry_worktree_intent(entries, host, sid, lead_of)
        if intent:
            root = roots[intent[1]]
            wid = worktree(db, host, *intent, "worktree", path=root["worktree_path"], branch=root.get("branch"))
        else:
            # Non-BAT creations keep their already-journaled checkpoint/integration/task slot.
            r = db.execute("SELECT body FROM observation_resources WHERE resource_type='session' AND resource_id=?",
                           (f"{host}/{sid}",)).fetchone()
            wid = body(r[0]).get("worktree_id") if r else None
            parent = e.get("failover_of") or e.get("shared_worktree_from") or e.get("lead_session_id")
            if not parent and e.get("role") == "reviewer" and e.get("task_id"):
                parent = lead_of(e["task_id"])
            if not wid and parent in by_id:
                wid = one(parent)
        if wid:
            remember(db, "session", f"{host}/{sid}", host=host, session_id=sid, worktree_id=wid)
        resolved[sid] = wid
        return wid

    with journal.tx():
        for sid in by_id:
            remember(db, "session", f"{host}/{sid}", host=host, session_id=sid, identity_evidence="registry")
            one(sid)


def relation(journal, task, sid, role, anchor, seq, *, confirmed=False, branch=None, legacy=False):
    db = journal.db
    rid = f"{task['host']}/{sid}"
    rows = db.execute("SELECT * FROM observation_relations WHERE execution_id=? AND session_resource_id=? AND role=?",
                      (task["task_id"], rid, role)).fetchall()
    active = next((r for r in reversed(rows) if body(r["body"]).get("end_seq") is None), None)
    relid = active["relation_id"] if active else "rel_" + hashlib.sha256(
        dump([task["task_id"], rid, role, anchor]).encode()).hexdigest()[:32]
    data = body(active["body"]) if active else {
        "relation_id": relid, "execution_id": task["task_id"], "session_resource_id": rid, "role": role,
        "anchor_id": anchor, "start_seq": None if legacy else seq, "end_seq": None,
        "started_at": None if legacy else iso(db.execute("SELECT created_at FROM api_events WHERE seq=?", (seq,)).fetchone()[0]), "ended_at": None,
        "start_command_id": anchor if db.execute("SELECT 1 FROM commands WHERE command_id=?", (anchor,)).fetchone() else None,
        "end_command_id": None, "status": "pending", "branch_id": None, "reason": None,
        "follow_up_of_execution_id": task.get("parent_task_id"), "parent_relation_id": None,
        "evidence": {"legacy": legacy, "anchor_id": anchor}}
    previous = dump(data)
    if confirmed:
        data["status"] = "bound"
    if branch:
        data.update(branch_id=branch["branch_id"], reason=branch["reason"])
        if branch.get("parent_branch_id"):
            parent = db.execute("SELECT relation_id FROM observation_relations WHERE json_extract(body,'$.branch_id')=?", (branch["parent_branch_id"],)).fetchone()
            data["parent_relation_id"] = parent[0] if parent else None
    if active and dump(data) == previous:
        return relid
    db.execute("""INSERT INTO observation_relations VALUES(?,?,?,?,?,?) ON CONFLICT(relation_id)
        DO UPDATE SET body=excluded.body""", (relid, task["task_id"], rid, role, data["anchor_id"], dump(data)))
    event_seq = seq if legacy else journal.api_event("execution", task["task_id"],
        "relation.bound" if confirmed else "relation.opened", data)
    db.execute("INSERT OR REPLACE INTO relation_revisions VALUES(?,?,?)", (relid, event_seq, dump(data)))
    index(db, event_seq, "session", rid)
    return relid


def close_relations(journal, task_id, seq, *, role=None, except_sid=None, legacy=False):
    for row in journal.db.execute("SELECT * FROM observation_relations WHERE execution_id=?", (task_id,)).fetchall():
        data = body(row["body"])
        if data["end_seq"] is not None or (role and data["role"] != role) or data["session_resource_id"] == except_sid:
            continue
        close_seq = seq if legacy else journal.api_event("execution", task_id, "relation.closed",
            {**data, "status": "closed", "end_seq": seq, "ended_at": iso(time.time())})
        command = journal.db.execute("""SELECT cr.command_id FROM command_relations cr JOIN commands c USING(command_id)
            WHERE cr.relation_id=? ORDER BY c.created_at DESC LIMIT 1""", (row["relation_id"],)).fetchone()
        data.update(status="closed", end_seq=seq, ended_at=None if legacy else iso(time.time()), end_command_id=command[0] if command else None)
        journal.db.execute("UPDATE observation_relations SET body=? WHERE relation_id=?", (dump(data), row["relation_id"]))
        journal.db.execute("INSERT OR REPLACE INTO relation_revisions VALUES(?,?,?)", (row["relation_id"], close_seq, dump(data)))
        index(journal.db, close_seq, "session", data["session_resource_id"])


def _refs(db, kind, rid, *, include_runs=False):
    if kind == "session":
        return [("session", rid)]
    if kind == "task":
        return [("session", r[0]) for r in db.execute(
            "SELECT DISTINCT session_resource_id FROM observation_relations WHERE execution_id=?", (rid,))]
    if kind == "checkpoint":
        cp = db.execute("SELECT host,source_session_id FROM checkpoints WHERE checkpoint_id=?", (rid,)).fetchone()
        out = [("session", f"{cp[0]}/{cp[1]}")] if cp else []
        if include_runs:
            out += [("session", f"{r[0]}/{r[1]}") for r in db.execute(
                "SELECT host,session_id FROM checkpoint_runs WHERE checkpoint_id=?", (rid,))]
        return out
    if kind == "checkpoint_run":
        r = db.execute("SELECT host,session_id FROM checkpoint_runs WHERE operation_id=?", (rid,)).fetchone()
        return [("session", f"{r[0]}/{r[1]}")] if r else _refs(db, "operation", rid)
    if kind == "operation":
        return [(r[0], r[1]) for r in db.execute("""SELECT DISTINCT resource_type,resource_id FROM api_event_resources
            WHERE seq IN (SELECT seq FROM api_events WHERE resource_type='operation' AND resource_id=?)""", (rid,))]
    return []


def record_event(journal, seq, *, legacy=False, extra=None):
    db = journal.db
    e = dict(db.execute("SELECT * FROM api_events WHERE seq=?", (seq,)).fetchone())
    b = body(e["body"])
    kind, rid = e["resource_type"], e["resource_id"]
    ctx = {"actor": e["actor"], "actor_basis": "authenticated_principal" if e["actor"] else "unknown",
           "actor_evidence": {"source": "api_events.actor", "principal_ref": e["actor"]} if e["actor"] else None, "claimed_actor": b.get("actor"), "observer": None, "evidence": [],
           "entry_point": None, "operation_entry_point": None, "client": None,
           "operation_id": None, "command_id": b.get("command_id"), "step": b.get("step"),
           "work_item_ids": [], "execution_id": None, "relation_ids": [], "project_ids": [],
           "host": b.get("host"), "profile_id": b.get("profile_id"), "workspace_id": b.get("workspace_id"),
           "session_resource_ids": [], "worktree_ids": [], "source_versions": [], "result_versions": [],
           "occurred_at": iso(e["created_at"]), "recorded_at": iso(e["created_at"]),
           "backfilled": legacy or e["kind"] == "history.backfilled", "unknown_fields": {}}
    refs = []
    if b.get("relation_id"):
        ctx["relation_ids"].append(b["relation_id"])
    if kind in RESOURCE_TYPES:
        refs.append((kind, rid))
    if kind == "session":
        host, _, sid = rid.partition("/")
        ctx.update(host=host, observer="inventory", actor_basis="service" if e["actor"] == "inventory" else ctx["actor_basis"])
        remember(db, "session", rid, host=host, session_id=sid)
    task_id = rid if kind in {"task", "execution"} else b.get("ref") if kind == "work_item" and b.get("kind") == "task" else b.get("execution_id")
    task_row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone() if task_id else None
    if task_row:
        task = dict(task_row)
        ctx.update(execution_id=task_id, host=task["host"], observer="task-service")
        refs.append(("execution", task_id))
        cmd = db.execute("SELECT * FROM commands WHERE command_id=?", (ctx["command_id"],)).fetchone() if ctx["command_id"] else None
        if cmd:
            ctx["command_kind"] = cmd["kind"]
            ctx["command_status"] = e["kind"].removeprefix("task.command_")
            ctx["prompt_sha256"] = body(cmd["payload"]).get("prompt_sha256")
        if cmd and cmd["session_id"]:
            sid = cmd["session_id"]
            payload = body(cmd["payload"])
            role = "reviewer" if cmd["kind"] == "start_reviewer" or str(payload.get("purpose", "")).startswith("reviewer:") else "lead"
            refs.append(("session", f"{task['host']}/{sid}"))
            if legacy and e["kind"] == "task.command_intent":
                ctx["evidence"].append({"table": "commands", "id": cmd["command_id"], "range": "legacy_unproven"})
            if e["kind"] == "task.command_bound" and b.get("previous_session_id"):
                close_relations(journal, task_id, seq, role=role, except_sid=f"{task['host']}/{sid}", legacy=legacy)
                refs.append(("session", f"{task['host']}/{b['previous_session_id']}"))
            if not e["kind"].startswith("relation."):
                rel = relation(journal, task, sid, role, cmd["command_id"], seq,
                               confirmed=e["kind"] == "task.command_settled" and cmd["kind"].startswith("start_"), legacy=legacy)
                db.execute("INSERT OR IGNORE INTO command_relations VALUES(?,?,?)", (cmd["command_id"], rel, seq))
                ctx["relation_ids"].append(rel)
            ctx["evidence"].append({"table": "commands", "id": cmd["command_id"]})
            if payload.get("old_session_id"):
                refs.append(("session", f"{task['host']}/{payload['old_session_id']}"))
        branch = db.execute("SELECT * FROM branches WHERE branch_id=?", (b.get("branch_id"),)).fetchone()
        if branch and branch["session_id"] and not e["kind"].startswith("relation."):
            sid = branch["session_id"]
            close_relations(journal, task_id, seq, role=branch["role"], except_sid=f"{task['host']}/{sid}", legacy=legacy)
            anchor = next((c[0] for c in db.execute("SELECT command_id FROM commands WHERE task_id=? AND session_id=? AND kind=? ORDER BY created_at",
                         (task_id, sid, "start_" + branch["role"]))), branch["branch_id"])
            rel = relation(journal, task, sid, branch["role"], anchor, seq, confirmed=True, branch=dict(branch), legacy=legacy)
            refs.append(("session", f"{task['host']}/{sid}"))
            ctx["relation_ids"].append(rel)
        if branch and branch["parent_branch_id"]:
            parent = db.execute("SELECT relation_id FROM observation_relations WHERE json_extract(body,'$.branch_id')=?", (branch["parent_branch_id"],)).fetchone()
            ctx["parent_relation_id"] = parent[0] if parent else None
        if b.get("session_resource_id"):
            refs.append(("session", b["session_resource_id"]))
        if not cmd and not branch:
            for r in db.execute("SELECT body FROM observation_relations WHERE execution_id=?", (task_id,)):
                rel = body(r[0])
                if rel.get("end_seq") is None or e["kind"] == "relation.closed":
                    refs.append(("session", rel["session_resource_id"]))
                    ctx["relation_ids"].append(rel["relation_id"])
        if e["kind"] == "task.external_worktree_retained" and b.get("path"):
            wid = worktree(db, task["host"], "task", task_id, "external_worktree", path=b["path"], branch=b.get("branch"), session_id=task.get("session_id"))
            refs.append(("worktree", wid))
            if b.get("commit"):
                ctx["result_versions"].append({"kind": "git", "sha": b["commit"], "ref": b.get("retained_ref"), "role": "retained"})
        if not legacy and task.get("external_worktree_path"):
            wid = worktree(db, task["host"], "task", task_id, "external_worktree",
                           path=task["external_worktree_path"], branch=task.get("external_branch"), session_id=task.get("session_id"))
            refs.append(("worktree", wid))
        if not legacy:
            for field, target in (("base_commit", "source_versions"), ("verification_commit", "result_versions")):
                if task.get(field):
                    ctx[target].append({"kind": "git", "sha": task[field], "role": field})
        if b.get("to") in {"done", "failed"}:
            close_relations(journal, task_id, seq, legacy=legacy)
    op_id = rid if kind == "operation" else b.get("operation_id") or (rid if kind == "integration" else None)
    if not op_id and kind == "checkpoint":
        cp_op = db.execute("SELECT operation_id FROM checkpoints WHERE checkpoint_id=?", (rid,)).fetchone()
        op_id = cp_op[0] if cp_op else None
    op = db.execute("SELECT * FROM operations WHERE operation_id=?", (op_id,)).fetchone() if op_id else None
    if op:
        target, ext = body(op["target"]), {} if legacy else body(op["external_refs"])
        ctx.update(operation_id=op_id, operation_entry_point=op["entry"], observer="operation-service", host=ctx["host"] or target.get("host") or ext.get("host"))
        if e["kind"] == "operation.accepted":
            ctx["entry_point"] = op["entry"]
        elif e["kind"] not in {"operation.cancelled", "operation.running"} and not legacy:
            ctx["entry_point"] = "daemon"
        if target.get("host") and target.get("session_id"):
            refs.append(("session", f"{target['host']}/{target['session_id']}"))
        if target.get("checkpoint_id"):
            cp_host = db.execute("SELECT host,commit_sha FROM checkpoints WHERE checkpoint_id=?", (target["checkpoint_id"],)).fetchone()
            ctx["host"] = ctx["host"] or (cp_host[0] if cp_host else None)
            if cp_host:
                ctx["source_versions"].append({"kind": "git", "sha": cp_host[1], "role": "checkpoint", "evidence_ref": "checkpoints:" + target["checkpoint_id"]})
            refs.extend(_refs(db, "checkpoint", target["checkpoint_id"]))
        params = body(op["params"])
        source_specs = params.get("sources") or []
        if params.get("preview_id"):
            preview = db.execute("SELECT sources FROM integration_previews WHERE preview_id=?", (params["preview_id"],)).fetchone()
            if preview:
                source_specs = json.loads(preview[0])
        for source in source_specs:
            refs.extend(_refs(db, source.get("kind"), source.get("id")))
            if source.get("pin"):
                ctx["source_versions"].append({"kind": "git", "sha": source["pin"], "role": "pinned"})
        if target.get("operation_id"):
            refs.extend(_refs(db, "operation", target["operation_id"]))
        ctx["action"] = op["action"]
        ctx["source_versions"] += [{"kind": "git", "sha": value, "role": name} for name, value in body(op["preconditions"]).items() if name in {"expected_head", "expected_commit"} and value]
        host = ctx["host"]
        response = b.get("response") or {}
        if e["kind"] == "operation.succeeded" and not legacy:
            response = {**body(op["result"]), **response}
        request = b.get("request") or {}
        for field in ("head", "sha", "commit", "commit_sha", "base_sha", "source_sha", "delivered_sha", "integrated_sha", "resolution_sha"):
            if isinstance(response.get(field), str) and len(response[field]) == 40:
                ctx["result_versions"].append({"kind": "git", "sha": response[field], "role": field})
        sid = b.get("session_id") or response.get("session_id") or request.get("session_id") or ext.get("session_id")
        path = ext.get("worktree_path") or ext.get("worktree") or response.get("worktree_path")
        if host and sid:
            refs.append(("session", f"{host}/{sid}"))
        if host and path and op["action"] in {"checkpoint.continue", "integration.handoff"}:
            wid = worktree(db, host, op["action"], op_id, "repair" if op["action"] == "integration.handoff" else "worktree",
                           path=path, branch=ext.get("branch"), clone=ext.get("clone_path"), session_id=sid)
            refs.append(("worktree", wid))
        if e["kind"] == "resource.bound":
            for old in db.execute("SELECT seq FROM api_events WHERE resource_type='operation' AND resource_id=? AND seq<?", (op_id, seq)):
                for typ, res in refs:
                    index(db, old[0], typ, res, seq, f"api_events:{seq}")
    if kind == "checkpoint":
        cp = db.execute("SELECT * FROM checkpoints WHERE checkpoint_id=?", (rid,)).fetchone()
        if cp:
            refs.append(("session", f"{cp['host']}/{cp['source_session_id']}"))
        if cp:
            ctx.update(host=cp["host"], observer="checkpoint-service", operation_id=ctx["operation_id"] or cp["operation_id"])
            ctx["source_versions"].append({"kind": "git", "sha": cp["commit_sha"], "role": "checkpoint"})
            ctx["source_versions"].append({"kind": "git", "sha": cp["head_sha"], "role": "captured_head"})
        for run in db.execute("SELECT * FROM checkpoint_runs WHERE checkpoint_id=? AND operation_id=?", (rid, b.get("operation_id"))):
            wid = worktree(db, run["host"], "checkpoint.continue", run["operation_id"], "worktree",
                           path=run["worktree_path"], branch=run["branch"], clone=run["clone_path"], session_id=run["session_id"])
            refs.append(("worktree", wid))
    if kind == "integration":
        ctx["observer"] = "integration-service"
        pv = db.execute("SELECT * FROM integration_previews WHERE preview_id=?", (rid,)).fetchone()
        if pv:
            ctx["host"] = pv["host"]
            for src in json.loads(pv["sources"]):
                refs.extend(_refs(db, src.get("kind"), src.get("id")))
        for rec in db.execute("SELECT * FROM integration_receipts WHERE operation_id=?", (rid,)):
            if b.get("seq") is not None and b["seq"] != rec["seq"]:
                continue
            refs.extend(_refs(db, rec["source_kind"], rec["source_id"]))
            ctx["source_versions"].append({"kind": "git", "sha": rec["pinned_sha"], "role": "pinned"})
            if not legacy:
                for k in ("base_sha", "integrated_sha", "resolution_sha", "delivered_sha"):
                    if rec[k]:
                        ctx["result_versions"].append({"kind": "git", "sha": rec[k], "role": k})
            if rec["resolver_session_id"] and rec["resolver_operation_id"] and not legacy:
                resolver = db.execute("SELECT external_refs FROM operations WHERE operation_id=?", (rec["resolver_operation_id"],)).fetchone()
                resolver_host = body(resolver[0]).get("host") if resolver else None
                if not resolver_host:
                    continue
                refs.append(("session", f"{resolver_host}/{rec['resolver_session_id']}"))
                wid = worktree(db, resolver_host, "integration.handoff", rec["resolver_operation_id"], "repair",
                               path=rec["repair_worktree"], branch=rec["repair_branch"], session_id=rec["resolver_session_id"])
                refs.append(("worktree", wid))
    if kind == "integration" and b.get("operation_id"):
        ctx["operation_id"] = b["operation_id"]
    if kind == "work_item":
        ctx["observer"] = "work-item-service"
        ctx["work_item_ids"].append(rid)
        refs.extend(_refs(db, b.get("kind"), b.get("ref"), include_runs=True))
    refs.extend((typ, res) for typ, res in (extra or {}).get("resources", []))
    for typ, res in list(refs):
        if typ == "session":
            row = db.execute("SELECT body FROM observation_resources WHERE resource_type='session' AND resource_id=?", (res,)).fetchone()
            wid = body(row[0]).get("worktree_id") if row else None
            if wid:
                refs.append(("worktree", wid))
    for typ, res in set(refs):
        if typ == "session":
            h, _, sid = res.partition("/")
            remember(db, typ, res, host=h, session_id=sid)
        index(db, seq, typ, res)
        if typ == "session":
            ctx["session_resource_ids"].append(res)
        if typ == "worktree":
            ctx["worktree_ids"].append(res)
    if not legacy:
        links = [("session", r) for r in ctx["session_resource_ids"]]
        if task_id:
            links.append(("task", task_id))
        if op_id:
            links.append(("operation", op_id))
        if kind == "checkpoint":
            links.append(("checkpoint", rid))
        for lk, ref in links:
            ctx["work_item_ids"] += [r[0] for r in db.execute(
                "SELECT work_item_id FROM work_item_links WHERE kind=? AND ref=? AND removed_at IS NULL", (lk, ref))]
    for wi in set(ctx["work_item_ids"]):
        r = db.execute("SELECT project_id FROM work_items WHERE work_item_id=?", (wi,)).fetchone()
        if r:
            ctx["project_ids"].append(r[0])
    for name in ("work_item_ids", "relation_ids", "project_ids", "session_resource_ids", "worktree_ids"):
        ctx[name] = sorted(set(ctx[name]))
    ctx.update({k: v for k, v in (extra or {}).items() if k != "resources"})
    occurred = ctx["occurred_at"]
    ctx["occurred_at_epoch"] = datetime.fromisoformat(occurred.replace("Z", "+00:00")).timestamp() if occurred else None
    ctx["unknown_fields"] = {k: "not_recorded" for k, v in ctx.items() if v is None}
    db.execute("INSERT OR IGNORE INTO api_event_context VALUES(?,?)", (seq, dump(ctx)))


def backfill(journal):
    db = journal.db
    for e in db.execute("SELECT seq FROM api_events ORDER BY seq").fetchall():
        record_event(journal, e[0], legacy=True)
    # Branches without an event and journal-only sessions still keep their identity.
    for row in db.execute("SELECT * FROM branches WHERE session_id IS NOT NULL").fetchall():
        task = dict(db.execute("SELECT * FROM tasks WHERE task_id=?", (row["task_id"],)).fetchone())
        if not db.execute("SELECT 1 FROM observation_relations WHERE execution_id=? AND session_resource_id=?",
                          (row["task_id"], f"{task['host']}/{row['session_id']}")).fetchone():
            seq = saved_fact(journal, "branches", row["branch_id"], dict(row), [("session", f"{task['host']}/{row['session_id']}"), ("execution", row["task_id"])])
            relation(journal, task, row["session_id"], row["role"], row["branch_id"], seq, confirmed=True, branch=dict(row), legacy=True)
    for task_row in db.execute("SELECT * FROM tasks WHERE external_worktree_path IS NOT NULL ORDER BY submitted_at").fetchall():
        task_data = dict(task_row)
        wid = worktree(db, task_data["host"], "task", task_data["task_id"], "external_worktree",
            path=task_data["external_worktree_path"], branch=task_data["external_branch"], session_id=task_data["session_id"])
        refs = [("execution", task_data["task_id"]), ("worktree", wid)]
        if task_data["session_id"]:
            refs.append(("session", f"{task_data['host']}/{task_data['session_id']}"))
        saved_fact(journal, "tasks.external_worktree", task_data["task_id"],
            {"host": task_data["host"], "task_id": task_data["task_id"], "worktree_path": task_data["external_worktree_path"],
             "branch": task_data["external_branch"], "created_at": None}, refs)
    for table, pk in (("operations", "operation_id"), ("commands", "command_id"), ("operation_steps", None),
                      ("sessions_observed", None), ("checkpoints", "checkpoint_id"), ("checkpoint_runs", "operation_id"),
                      ("integration_receipts", None), ("work_item_links", "link_id")):
        for row in db.execute(f"SELECT * FROM {table}").fetchall():  # noqa: S608 - fixed table names
            data = dict(row)
            key = data[pk] if pk else dump([data.get("host"), data.get("session_id"), data.get("operation_id"), data.get("seq")])
            if table in {"operations", "checkpoints"} and db.execute("SELECT 1 FROM api_events WHERE resource_type=? AND resource_id=?", ("operation" if table == "operations" else "checkpoint", key)).fetchone():
                continue
            if table == "checkpoint_runs" and db.execute("SELECT 1 FROM api_events WHERE kind='checkpoint.continued' AND json_extract(body,'$.operation_id')=?", (key,)).fetchone():
                continue
            if table == "commands" and db.execute("SELECT 1 FROM api_events WHERE json_extract(body,'$.command_id')=?", (key,)).fetchone():
                continue
            if table == "work_item_links" and db.execute("SELECT 1 FROM api_events WHERE resource_type='work_item' AND resource_id=? AND kind='work_item.linked' AND json_extract(body,'$.kind')=? AND json_extract(body,'$.ref')=?", (data["work_item_id"], data["kind"], data["ref"])).fetchone():
                continue
            if table == "integration_receipts" and db.execute("SELECT 1 FROM api_events WHERE resource_type='integration' AND resource_id=? AND json_extract(body,'$.seq')=?", (data["operation_id"], data["seq"])).fetchone():
                continue
            for name in ("body", "request", "response", "result", "external_refs", "params"):
                if isinstance(data.get(name), str):
                    data[name] = summary(body(data[name]))
            refs = []
            if data.get("host") and data.get("session_id"):
                refs.append(("session", f"{data['host']}/{data['session_id']}"))
                remember(db, "session", refs[0][1], host=data["host"], session_id=data["session_id"])
            if table == "commands":
                t = db.execute("SELECT host FROM tasks WHERE task_id=?", (data["task_id"],)).fetchone()
                refs.append(("execution", data["task_id"]))
                if t and data.get("session_id"):
                    refs.append(("session", f"{t[0]}/{data['session_id']}"))
            if table == "checkpoints":
                refs.append(("session", f"{data['host']}/{data['source_session_id']}"))
            if table == "checkpoint_runs":
                wid = worktree(db, data["host"], "checkpoint.continue", data["operation_id"], "worktree",
                    path=data["worktree_path"], branch=data["branch"], session_id=data["session_id"], clone=data["clone_path"])
                refs.append(("worktree", wid))
            if table == "work_item_links":
                refs.extend(_refs(db, data["kind"], data["ref"]))
            if table == "integration_receipts":
                refs.extend(_refs(db, data["source_kind"], data["source_id"]))
            if data.get("operation_id"):
                refs.extend(_refs(db, "operation", data["operation_id"]))
                op = db.execute("SELECT action,target,external_refs FROM operations WHERE operation_id=?", (data["operation_id"],)).fetchone()
                if op:
                    target, ext = body(op["target"]), body(op["external_refs"])
                    cp = db.execute("SELECT host FROM checkpoints WHERE checkpoint_id=?", (target.get("checkpoint_id"),)).fetchone()
                    h = target.get("host") or ext.get("host") or (cp[0] if cp else None)
                    sid = ext.get("session_id") or body(data.get("request")).get("session_id") or body(data.get("response")).get("session_id")
                    if h and sid:
                        refs.append(("session", f"{h}/{sid}"))
                    if h and ext.get("worktree_path") and op["action"] in {"checkpoint.continue", "integration.handoff"}:
                        wid = worktree(db, h, op["action"], data["operation_id"], "repair" if op["action"] == "integration.handoff" else "worktree",
                            path=ext["worktree_path"], branch=ext.get("branch"), session_id=sid)
                        refs.append(("worktree", wid))
            saved_fact(journal, table, key, summary(data), refs)


def saved_fact(journal, table, key, data, refs):
    source_key = f"{table}:{key}"
    old = journal.db.execute("SELECT seq FROM observation_backfill WHERE source_key=?", (source_key,)).fetchone()
    if old:
        return old[0]
    seq = journal.api_event("history", source_key, "history.backfilled", {"source_table": table, "source_key": key,
        "saved_snapshot": summary(data)}, context={"backfilled": True, "resources": refs,
        "occurred_at": iso(data.get("finished_at") or data.get("updated_at") or data.get("captured_at") or data.get("created_at") or data.get("last_seen_at") or data.get("first_seen_at")), "evidence": [{"table": table, "id": key}]})
    journal.db.execute("INSERT INTO observation_backfill VALUES(?,?)", (source_key, seq))
    return seq


def event_out(db, row, *, safe=False):
    e = dict(row)
    ctx = db.execute("SELECT context FROM api_event_context WHERE seq=?", (e["seq"],)).fetchone()
    return {"seq": e["seq"], "event_id": e["seq"], "resource_type": e["resource_type"], "resource_id": e["resource_id"],
            "kind": e["kind"], "body": summary(body(e["body"])) if safe else body(e["body"]),
            "actor": e["actor"], "created_at": e["created_at"], "context": body(ctx[0]) if ctx else {}}


def page_limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise OperationError("INVALID_PARAMS", "limit must be an integer between 1 and 200", 422)
    return limit


def cursor_read(cursor, filters, head):
    fhash = hashlib.sha256(dump(filters).encode()).hexdigest()
    if not cursor:
        return fhash, head, None
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if value["v"] != 1 or value["f"] != fhash or type(value["a"]) is not int or not 0 <= value["a"] <= head:
            raise ValueError
        return fhash, value["a"], value["k"]
    except (TypeError, ValueError, KeyError):
        raise OperationError("INVALID_CURSOR", "cursor does not match this resource and filters", 422) from None


def cursor_out(fhash, as_of, key):
    return base64.urlsafe_b64encode(dump({"v": 1, "f": fhash, "a": as_of, "k": key}).encode()).decode().rstrip("=")


class Observation:
    def __init__(self, journal, config=None):
        self.journal, self.db, self.config = journal, journal.db, config

    def resource(self, resource_type, resource_id):
        if resource_type not in RESOURCE_TYPES or not isinstance(resource_id, str) or not resource_id:
            raise OperationError("INVALID_PARAMS", "resource_type must be session, worktree or execution; full ID required", 422)
        r = self.db.execute("SELECT body FROM observation_resources WHERE resource_type=? AND resource_id=?", (resource_type, resource_id)).fetchone()
        known = r is not None
        if resource_type == "execution":
            known = self.db.execute("SELECT 1 FROM tasks WHERE task_id=?", (resource_id,)).fetchone() is not None
        if resource_type == "session":
            host, sep, sid = resource_id.partition("/")
            if not sep or not sid:
                raise OperationError("INVALID_PARAMS", "session resource_id must be host/full-session-id", 422)
            known |= self.db.execute("SELECT 1 FROM sessions_observed WHERE host=? AND session_id=?", (host, sid)).fetchone() is not None
        if not known:
            raise OperationError("NOT_FOUND", "resource has no journal evidence", 404)
        data = {"resource_type": resource_type, "resource_id": resource_id, **(body(r[0]) if r else {})}
        if resource_type == "session":
            data.update(host=host, session_id=sid)
        if self.config is not None and data.get("host"):
            data["scope_status"] = "current" if data["host"] in self.config.hosts else "outside_current_config"
        return data

    def history(self, resource_type, resource_id, *, cursor=None, limit=50, order="desc", kind=None, since=None, until=None):
        resource = self.resource(resource_type, resource_id)
        page_limit(limit)
        if order not in {"asc", "desc"}:
            raise OperationError("INVALID_PARAMS", "order must be asc or desc", 422)
        kinds = [kind] if isinstance(kind, str) else kind or []
        if not isinstance(kinds, list) or not all(isinstance(k, str) for k in kinds):
            raise OperationError("INVALID_PARAMS", "kind must be a string or a list of strings", 422)
        for v in (since, until):
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)):
                raise OperationError("INVALID_PARAMS", "since/until must be UTC epoch seconds", 422)
        if since is not None and until is not None and since > until:
            raise OperationError("INVALID_PARAMS", "since must not exceed until", 422)
        head = self.journal.api_head()
        f, as_of, last = cursor_read(cursor, [resource_type, resource_id, order, sorted(kinds), since, until], head)
        sql = """SELECT e.* FROM api_events e LEFT JOIN api_event_context c ON c.seq=e.seq
            WHERE e.seq<=? AND e.seq IN (
                SELECT r.seq FROM api_event_resources r WHERE r.resource_type=? AND r.resource_id=? AND r.linked_at_seq<=?
                UNION SELECT gap.seq FROM api_event_context gap
                WHERE json_extract(gap.context,'$.projection_error') IS NOT NULL AND gap.seq<=?
                AND EXISTS(SELECT 1 FROM api_events failed WHERE failed.seq=gap.seq AND (
                    (failed.resource_type=? AND failed.resource_id=?) OR
                    (?='execution' AND failed.resource_type='task' AND failed.resource_id=?) OR
                    EXISTS(SELECT 1 FROM api_events source JOIN api_event_resources known ON known.seq=source.seq
                        WHERE source.resource_type=failed.resource_type AND source.resource_id=failed.resource_id AND source.seq<=failed.seq
                        AND known.resource_type=? AND known.resource_id=? AND known.linked_at_seq<=?))))"""
        args = [as_of, resource_type, resource_id, as_of, as_of, resource_type, resource_id,
                resource_type, resource_id, resource_type, resource_id, as_of]
        if last is not None:
            if type(last) is not int:
                raise OperationError("INVALID_CURSOR", "invalid history key", 422)
            sql += " AND e.seq" + (">?" if order == "asc" else "<?")
            args.append(last)
        if kinds:
            sql += " AND e.kind IN (" + ",".join("?" * len(kinds)) + ")"
            args.extend(kinds)
        for sign, value in ((">=", since), ("<=", until)):
            if value is not None:
                sql += f" AND COALESCE(json_extract(c.context,'$.occurred_at_epoch'),e.created_at) {sign} ?"
                args.append(value)
        sql += " ORDER BY e.seq " + order.upper() + " LIMIT ?"
        rows = self.db.execute(sql, (*args, limit + 1)).fetchall()
        events = [event_out(self.db, r, safe=True) for r in rows[:limit]]
        earliest = self.db.execute("SELECT MIN(e.created_at) FROM api_events e JOIN api_event_resources r ON r.seq=e.seq WHERE r.resource_type=? AND r.resource_id=? AND e.seq<=? AND r.linked_at_seq<=?", (resource_type, resource_id, as_of, as_of)).fetchone()[0]
        return {"resource": resource, "events": events, "count": len(events), "as_of": as_of, "head_cursor": head,
                "next_cursor": cursor_out(f, as_of, events[-1]["seq"]) if len(rows) > limit else None,
                "has_more": len(rows) > limit, "coverage": {"source": "journal", "first_recorded_at": iso(earliest), "legacy_transitions": "may_be_incomplete"}}

    def relations(self, resource_type, resource_id, *, cursor=None, limit=50, execution_id=None, include_closed=True):
        resource = self.resource(resource_type, resource_id)
        page_limit(limit)
        if type(include_closed) is not bool:
            raise OperationError("INVALID_PARAMS", "include_closed must be boolean", 422)
        head = self.journal.api_head()
        f, as_of, last = cursor_read(cursor, [resource_type, resource_id, execution_id, include_closed], head)
        sql = """SELECT v.body FROM relation_revisions v JOIN observation_relations r USING(relation_id)
            WHERE v.seq<=? AND v.seq=(SELECT MAX(v2.seq) FROM relation_revisions v2
            WHERE v2.relation_id=v.relation_id AND v2.seq<=?)"""
        args = [as_of, as_of]
        if resource_type in {"execution", "session"}:
            sql += " AND r." + ("execution_id" if resource_type == "execution" else "session_resource_id") + "=?"
            args.append(resource_id)
        rows = self.db.execute(sql, args).fetchall()
        out = []
        for row in rows:
            r = body(row[0])
            if resource_type == "execution" and r["execution_id"] != resource_id:
                continue
            if resource_type == "session" and r["session_resource_id"] != resource_id:
                continue
            if resource_type == "worktree":
                s = self.db.execute("SELECT body FROM observation_resources WHERE resource_type='session' AND resource_id=?", (r["session_resource_id"],)).fetchone()
                if not s or body(s[0]).get("worktree_id") != resource_id:
                    continue
            if execution_id and r["execution_id"] != execution_id or not include_closed and r["status"] == "closed":
                continue
            key = [r["start_seq"] or 0, r["relation_id"]]
            if last is not None and (not isinstance(last, list) or len(last) != 2 or type(last[0]) is not int or not isinstance(last[1], str)):
                raise OperationError("INVALID_CURSOR", "invalid relation key", 422)
            if last is not None and key <= last:
                continue
            r["command_ids"] = [x[0] for x in self.db.execute("""SELECT cr.command_id FROM command_relations cr WHERE relation_id=? AND cr.linked_at_seq<=? ORDER BY cr.rowid""", (r["relation_id"], as_of))]
            out.append(r)
        out.sort(key=lambda r: (r["start_seq"] or 0, r["relation_id"]))
        page = out[:limit]
        return {"resource": resource, "relations": page, "count": len(page), "as_of": as_of,
                "next_cursor": cursor_out(f, as_of, [page[-1]["start_seq"] or 0, page[-1]["relation_id"]]) if len(out) > limit else None,
                "has_more": len(out) > limit}
