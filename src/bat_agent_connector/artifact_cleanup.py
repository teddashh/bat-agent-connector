"""Read-only projection of verified checkpoint input replicas for reviewed cleanup.

Cleanup still proves ownership/consumers and hashes each current host file. This
module supplies exact expected files, never directory or path-based exemptions.
"""

from __future__ import annotations

import json

from . import artifacts
from .errors import ResourceReadOnly
from .operations import OperationError


def replica_evidence(ops, item):
    empty = {"replica_manifest": [], "bookkeeping_names": []}
    creation = item.get("creation_evidence") or {}
    operation_id = creation.get("intent")
    if (item.get("kind") != "worktree" or item.get("flavor") != "checkpoint" or item.get("proven") is not True
            or creation.get("intent_type") != "checkpoint.continue" or creation.get("slot") != "worktree"
            or not isinstance(operation_id, str) or not artifacts.OPERATION_ID.fullmatch(operation_id)
            or ops.context.get("artifact_store") is None):
        return empty
    db = ops.db
    op = db.execute("SELECT action,target,external_refs FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
    prepare = db.execute("SELECT request FROM operation_steps WHERE operation_id=? AND name='worktree.prepare'",
                         (operation_id,)).fetchone()
    if op is None or op["action"] != "checkpoint.continue" or prepare is None:
        return empty
    try:
        target, refs, request = (json.loads(op["target"]), json.loads(op["external_refs"]), json.loads(prepare["request"]))
        cp = db.execute("SELECT host FROM checkpoints WHERE checkpoint_id=?", (target["checkpoint_id"],)).fetchone()
        if cp is None or cp["host"] != item["host"]:
            return empty
        for key, field in (("worktree_path", "path"), ("clone_path", "repository"), ("branch", "branch")):
            if not item.get(field) or refs.get(key) != item[field] or request.get(key) != item[field]:
                return empty
    except (ValueError, TypeError, KeyError, AttributeError):
        return empty
    manifest, books = [], set()
    rows = db.execute("SELECT * FROM artifact_materializations WHERE operation_id=? AND host=? AND state='verified' "
                      "ORDER BY materialization_id", (operation_id, item["host"]))
    for row in rows:
        try:
            ref = {key: row[key] for key in ("artifact_id", "revision", "digest")}
            revision = artifacts.get(db, row["artifact_id"], row["revision"])
            name = artifacts.safe_name(revision["display_name"])
            relative = f".batc-inputs/{row['artifact_id']}-r{row['revision']}/{name}"
            evidence = json.loads(row["evidence"])
            expected = {"worktree": item["path"], "ref": ref, "name": name,
                        "operation_id": operation_id, "size_bytes": revision["size_bytes"]}
            if (revision["state"] != "ready" or revision["digest"] != row["digest"]
                    or row["managed_path"] != item["path"] + "/" + relative
                    or type(row["attempt"]) is not int or row["attempt"] < 1
                    or evidence.get("ok") is not True or artifacts._materialization_error(evidence, expected)):
                continue
            attempts = set()
            # Use actual recorded transfer intents, not a guessed 1..N range.
            prefix = f"artifact.{row['materialization_id']}.transfer."
            for step in db.execute("SELECT name,request FROM operation_steps WHERE operation_id=?", (operation_id,)):
                if not step["name"].startswith(prefix):
                    continue
                transfer = json.loads(step["request"])
                attempt = transfer.get("attempt")
                if (type(attempt) is not int or not 1 <= attempt <= row["attempt"]
                        or step["name"] != prefix + str(attempt) or transfer.get("clone") != item["repository"]
                        or any(transfer.get(key) != value for key, value in expected.items())):
                    raise ValueError("transfer intent does not bind this replica")
                attempts.add(attempt)
            if row["attempt"] not in attempts:
                continue
            # A dispatch receipt alone must not retire the last surviving bytes.
            # This read verifies immutable store content without changing state.
            ops.context["artifact_store"].read_content(row["artifact_id"], row["revision"])
            manifest.append({"path": relative, "bytes": revision["size_bytes"], "digest": row["digest"]})
            books.add(".batc-inputs/.owner")
            directory = f".batc-inputs/.attempts/{row['artifact_id']}-r{row['revision']}"
            for attempt in attempts:
                books.update({f"{directory}/.attempt-{attempt}", f"{directory}/.closed-{attempt}"})
        except (ValueError, TypeError, KeyError, AttributeError, OSError, OperationError, ResourceReadOnly):
            # Missing/corrupt/unproven evidence leaves host content ordinary.
            continue
    return {"replica_manifest": sorted(manifest, key=lambda entry: entry["path"]), "bookkeeping_names": sorted(books)}
