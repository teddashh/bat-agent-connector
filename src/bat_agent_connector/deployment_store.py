"""Deployment facts in the shared journal; schema has no data-step version."""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import nullcontext


def tx(journal):
    """Local helpers join their caller's transaction; no OperationService dependency."""
    return nullcontext() if journal.db.in_transaction else journal.tx()


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


def environment_key(origin: str, repository_id: int, environment: str) -> str:
    return digest([origin, repository_id, environment])


def schema(journal) -> None:
    with tx(journal):
        journal.db.execute("""CREATE TABLE IF NOT EXISTS deployment_environments (
            environment_key TEXT PRIMARY KEY, provider_origin TEXT NOT NULL, repository_id INTEGER NOT NULL,
            repository TEXT NOT NULL, environment TEXT NOT NULL, desired_generation INTEGER NOT NULL DEFAULT 0,
            desired_deployment_id TEXT, current_deployment_id TEXT, last_verified_deployment_id TEXT,
            slot_deployment_id TEXT, observed TEXT, attention TEXT, version INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL
        )""")
        journal.db.execute("""CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE, recipe TEXT NOT NULL,
            environment_key TEXT NOT NULL, generation INTEGER, identity TEXT NOT NULL,
            recipe_snapshot TEXT NOT NULL, recipe_digest TEXT NOT NULL, state TEXT NOT NULL,
            provider_terminal INTEGER NOT NULL DEFAULT 0, run_id INTEGER, run_attempt INTEGER,
            document TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL,
            updated_at REAL NOT NULL, UNIQUE(environment_key,generation)
        )""")
        journal.db.execute("""CREATE INDEX IF NOT EXISTS deployments_history
            ON deployments(recipe,created_at DESC,deployment_id DESC)""")
        journal.db.execute("""CREATE INDEX IF NOT EXISTS deployments_provider
            ON deployments(provider_terminal,updated_at)""")


def deployment(db, *, deployment_id=None, operation_id=None) -> dict | None:
    row = (db.execute("SELECT * FROM deployments WHERE deployment_id=?", (deployment_id,)).fetchone()
           if deployment_id else db.execute("SELECT * FROM deployments WHERE operation_id=?", (operation_id,)).fetchone())
    if row is None:
        return None
    result = {**json.loads(row["document"]), **dict(row)}
    for field in ("identity", "recipe_snapshot"):
        result[field] = json.loads(result[field])
    result.pop("document")
    result["provider_terminal"] = bool(result["provider_terminal"])
    return result


def environment(db, key: str) -> dict | None:
    row = db.execute("SELECT * FROM deployment_environments WHERE environment_key=?", (key,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["observed"] = json.loads(result["observed"]) if result["observed"] else None
    return result


def update(journal, deployment_id: str, *, facts=None, expected_version=None, **columns) -> bool:
    allowed = {"identity", "state", "provider_terminal", "run_id", "run_attempt", "recipe_snapshot"}
    if set(columns) - allowed:
        raise ValueError("unsupported deployment columns")
    with tx(journal):
        row = journal.db.execute("SELECT * FROM deployments WHERE deployment_id=?", (deployment_id,)).fetchone()
        if not row or (expected_version is not None and row["version"] != expected_version):
            return False
        document = {**json.loads(row["document"]), **(facts or {})}
        columns = {k: encode(v) if k in {"identity", "recipe_snapshot"} else v for k, v in columns.items()}
        if document == json.loads(row["document"]) and all(row[k] == v for k, v in columns.items()):
            return True
        setters = ",".join(k + "=?" for k in columns)
        journal.db.execute(f"UPDATE deployments SET {setters + ',' if setters else ''}document=?,"  # noqa: S608
                           "version=version+1,updated_at=? WHERE deployment_id=? AND version=?",
                           (*columns.values(), encode(document), time.time(), deployment_id, row["version"]))
        return True


def backfill(journal) -> None:
    """Allocated data step 3. Observation owns step 2; never perform or impersonate it here."""
    if journal.db.execute("PRAGMA user_version").fetchone()[0] != 2:
        return
    with journal.tx():
        rows = journal.db.execute("SELECT * FROM operations WHERE action IN "
                                  "('deployment.start','delivery.merge_and_deploy') ORDER BY created_at").fetchall()
        for row in rows:
            _legacy_deployment(journal, row)
        journal.db.execute("PRAGMA user_version=3")


def _legacy_deployment(journal, row) -> None:
    target, params = json.loads(row["target"]), json.loads(row["params"])
    result, refs = json.loads(row["result"] or "{}"), json.loads(row["external_refs"] or "{}")
    result = result.get("deploy") or result
    step = journal.db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='deploy.dispatch'",
                              (row["operation_id"],)).fetchone()
    merge_sent = journal.db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name='merge.submit'",
                                    (row["operation_id"],)).fetchone() is not None
    recipe = target.get("recipe", "")
    repository = result.get("repository") or target.get("repository") or ""
    env = result.get("environment")
    key = environment_key("legacy", 0, recipe)
    identity = {"source_sha": result.get("source_sha") or params.get("source_sha") or refs.get("merged_sha")}
    run_id = result.get("run_id") or refs.get("deploy_run_id")
    sent = bool(step or run_id or merge_sent)
    outcome = row["status"]
    terminal = (not sent or outcome == "succeeded"
                or (outcome == "failed" and row["error_code"] in {"DEPLOY_FAILED", "DEPLOY_NOT_RUN"}))
    state = {"succeeded": "unverified", "failed": "failed", "cancelled": "cancelled"}.get(
        outcome, "uncertain" if sent else "failed")
    dep_id = "dep_" + row["operation_id"].removeprefix("op_")
    snapshot = {"name": recipe, "repository": repository, "environment": env,
                "workflow": result.get("workflow"), "mode": result.get("mode"),
                "legacy": True}
    document = {"legacy": True, "dispatch_sent": bool(step), "merge_sent": merge_sent,
                "provider_kind": "run" if step or run_id else "merge" if merge_sent else "none",
                "html_url": result.get("html_url") or refs.get("deploy_run_url"),
                "evidence": None, "verified": False, "rollback_of": None,
                "legacy_operation_status": outcome, "error_code": row["error_code"] or
                ("DEPLOY_PREVIEW_REQUIRED" if not sent and outcome not in {"succeeded", "failed", "cancelled"} else None),
                "legacy_binding_sources": {"environment": "result" if env else "unknown",
                                           "mode": "result" if result.get("mode") else "unknown"}}
    journal.db.execute("""INSERT OR IGNORE INTO deployment_environments
        (environment_key,provider_origin,repository_id,repository,environment,slot_deployment_id,updated_at)
        VALUES(?,'legacy',0,?,?,?,?)""", (key, repository, env or "", dep_id if sent and not terminal else None, row["updated_at"]))
    if sent and not terminal:
        journal.db.execute("UPDATE deployment_environments SET slot_deployment_id=? WHERE environment_key=? "
                           "AND slot_deployment_id IS NULL", (dep_id, key))
    journal.db.execute("""INSERT OR IGNORE INTO deployments
        (deployment_id,operation_id,recipe,environment_key,generation,identity,recipe_snapshot,recipe_digest,
         state,provider_terminal,run_id,run_attempt,document,created_at,updated_at)
        VALUES(?,?,?,?,NULL,?,?,?, ?,?,?,?,?,?,?)""",
        (dep_id, row["operation_id"], recipe, key, encode(identity), encode(snapshot), "legacy",
         state, terminal, run_id,
         result.get("run_attempt"), encode(document), row["created_at"], row["updated_at"]))
