"""Connector-only labels. Exact journal identities; no BAT, Git or ownership effects."""
from __future__ import annotations

import json
import time
import unicodedata

from .operations import ActionDef, OpContext, OperationError

MAX_LABELS = 8
MAX_LENGTH = 40


def schema(journal):
    with journal.tx():
        journal.db.execute("""CREATE TABLE IF NOT EXISTS session_metadata (
            host TEXT NOT NULL, session_id TEXT NOT NULL, labels TEXT NOT NULL,
            version INTEGER NOT NULL, updated_by TEXT NOT NULL, updated_at REAL NOT NULL,
            PRIMARY KEY(host, session_id))""")


def labels(value):
    if not isinstance(value, list) or len(value) > MAX_LABELS:
        raise OperationError("INVALID_PARAMS", "labels must be a list of at most 8 labels", 422)
    result = []
    for item in value:
        if not isinstance(item, str):
            raise OperationError("INVALID_PARAMS", "each label must be text", 422)
        # Reject control/format/surrogate characters before trimming; never hide a newline.
        if any(unicodedata.category(c).startswith("C") or c in "\u2028\u2029" for c in item):
            raise OperationError("INVALID_PARAMS", "labels must be single-line plain text", 422)
        item = item.strip()
        if not 1 <= len(item) <= MAX_LENGTH or item in result:
            raise OperationError("INVALID_PARAMS", "labels must be unique, nonempty and at most 40 characters", 422)
        result.append(item)
    return result


def read(db, host, session_id):
    row = db.execute("SELECT * FROM session_metadata WHERE host=? AND session_id=?", (host, session_id)).fetchone()
    if row is None:
        return {"labels": [], "version": 0, "updated_by": None, "updated_at": None}
    try:
        stored = json.loads(row["labels"])
        if labels(stored) != stored or type(row["version"]) is not int or row["version"] < 1:
            raise ValueError("invalid saved metadata")
    except (ValueError, TypeError, OperationError):
        raise OperationError("METADATA_UNREADABLE", "saved session metadata could not be read", 500) from None
    return {"labels": stored, "version": row["version"], "updated_by": row["updated_by"], "updated_at": row["updated_at"]}


def _check(ops, target, params, pre):
    if set(target) != {"host", "session_id"} or any(
        not isinstance(v, str) or not v or len(v) > 512 or "/" in v or any(unicodedata.category(c).startswith("C") for c in v)
        for v in target.values()
    ):
        raise OperationError("INVALID_TARGET", "target must name an exact host and full session_id", 422)
    if set(params) != {"labels"}:
        raise OperationError("INVALID_PARAMS", "params must contain only labels", 422)
    values = labels(params["labels"])
    if set(pre) != {"expected_version"} or type(pre.get("expected_version")) is not int or pre["expected_version"] < 0:
        raise OperationError("PRECONDITION_REQUIRED", "expected_version must be the metadata version you read", 422)
    host, sid = target["host"], target["session_id"]
    rid = f"{host}/{sid}"
    # All checks are SQLite reads. Removed hosts and manual/unknown resources remain eligible.
    known = ops.db.execute("SELECT 1 FROM sessions_observed WHERE host=? AND session_id=?", (host, sid)).fetchone()
    known = known or ops.db.execute("SELECT 1 FROM observation_resources WHERE resource_type='session' AND resource_id=?", (rid,)).fetchone()
    known = known or ops.db.execute("""SELECT 1 FROM resource_tombstones t LEFT JOIN cleanup_aliases a USING(resource_id)
        WHERE t.host=? AND t.kind='session' AND (t.resource_id=? OR (a.kind='original' AND a.external_id=? AND a.host=?))""",
        (host, rid, rid, host)).fetchone()
    if not known:
        raise OperationError("NOT_FOUND", "session has no exact journal identity", 404)
    before = read(ops.db, host, sid)
    if pre["expected_version"] != before["version"]:
        raise OperationError("METADATA_VERSION_CONFLICT", "labels changed since you read them; review the current labels", 409)
    return before, values


def _admit(ops, principal, target, params, pre):
    _check(ops, target, params, pre)


async def _run(ctx: OpContext):
    def change():
        before, values = _check(ctx.service, ctx.target, ctx.params, ctx.preconditions)
        host, sid = ctx.target["host"], ctx.target["session_id"]
        after = {"labels": values, "version": before["version"] + 1,
                 "updated_by": ctx.op["actor"], "updated_at": time.time()}
        ctx.service.db.execute("""INSERT INTO session_metadata VALUES(?,?,?,?,?,?)
            ON CONFLICT(host,session_id) DO UPDATE SET labels=excluded.labels,version=excluded.version,
                updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (host, sid, json.dumps(values, ensure_ascii=False), after["version"], after["updated_by"], after["updated_at"]))
        # Prose stays in the exact operation result, not the redacted observation summary.
        ctx.service.journal.api_event("session", f"{host}/{sid}", "session.labels_updated",
            {"host": host, "session_id": sid, "version": after["version"], "changed_fields": ["labels"],
             "operation_id": ctx.operation_id}, actor=ctx.op["actor"])
        return {"host": host, "session_id": sid, "connector_metadata": after, "previous": before}
    return ctx.effect("session_labels", change, request={"expected_version": ctx.preconditions["expected_version"]})


ACTIONS = [ActionDef("session.labels.set", "manage", "Set Connector-only labels for a journal-known session",
                     _run, _admit, target_keys=("host", "session_id"))]
