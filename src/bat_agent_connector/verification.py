"""Explicit, commit-bound execution evidence for cleanup decisions.

This store retains external testimony and the existing internal verifier's local
projection. It never establishes Task Service observed-verifier authority.
Public admission reads exact HEAD and BAT-reported status; BAT can collapse a
Git status failure to an empty list, so that read is not proof of verifier success.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

from .config import state_dir
from .errors import WriteRefused
from .redact import redact, redact_secrets
from .registry import _locked

SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


def path() -> Path:
    return state_dir() / "verification.json"


MAX_BYTES = 16 * 1024 * 1024
FIELDS = {"candidate_commit", "command", "exit_code", "environment", "log_ref"}
ROW_FIELDS = FIELDS | {"host", "session_id", "actor", "recorded_at"}


def validate(candidate_commit, command, exit_code, environment, log_ref):
    if not isinstance(candidate_commit, str) or not SHA.fullmatch(candidate_commit):
        raise WriteRefused("candidate_commit must be a Git commit hash")
    for name, value, bound in (("command", command, 4000), ("environment", environment, 4000),
                                ("log_ref", log_ref, 2000)):
        if not isinstance(value, str) or not value.strip() or len(value) > bound:
            raise WriteRefused(f"{name} must be nonempty text of at most {bound} characters")
        if redact_secrets(redact(value)) != value:
            raise WriteRefused("verification metadata must not contain credentials; provide sanitized metadata")
    if type(exit_code) is not int:
        raise WriteRefused("exit_code must be an integer")


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _row_valid(row):
    if not isinstance(row, dict) or set(row) != ROW_FIELDS:
        raise ValueError("invalid verification row")
    validate(**{k: row[k] for k in FIELDS})
    if (any(not isinstance(row[k], str) or not row[k] for k in ("host", "session_id", "actor"))
            or type(row["recorded_at"]) not in (int, float) or not math.isfinite(row["recorded_at"])
            or row["recorded_at"] < 0):
        raise ValueError("invalid verification identity")


def _digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _document(p: Path):
    try:
        with p.open("rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return {"records": [], "operation_receipts": {}}
    except OSError as exc:
        raise WriteRefused("verification store is unreadable; preserve it for recovery") from exc
    try:
        if len(raw) > MAX_BYTES:
            raise ValueError("too large")
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        if (not isinstance(doc, dict) or set(doc) - {"records", "operation_receipts"}
                or not isinstance(doc.get("records"), list)
                or not isinstance(doc.get("operation_receipts", {}), dict)):
            raise ValueError("invalid document")
        latest = set()
        for row in doc["records"]:
            _row_valid(row)
            identity = row["host"], row["session_id"]
            if identity in latest:
                raise ValueError("duplicate latest record")
            latest.add(identity)
        for key, receipt in doc.setdefault("operation_receipts", {}).items():
            if (not re.fullmatch(r"op_[0-9a-f]{32}", key) or not isinstance(receipt, dict)
                    or set(receipt) != {"digest", "record"}):
                raise ValueError("invalid operation receipt")
            _row_valid(receipt["record"])
            if receipt["digest"] != _digest(receipt["record"]):
                raise ValueError("receipt digest mismatch")
        return doc
    except (ValueError, TypeError, UnicodeError, WriteRefused, OverflowError, RecursionError) as exc:
        raise WriteRefused("verification store is invalid; preserve it for recovery") from exc


def _read(p: Path) -> list[dict]:
    return _document(p)["records"]


def operation_record(operation_id: str, expected: dict) -> dict | None:
    receipt = _document(path())["operation_receipts"].get(operation_id)
    if receipt is None:
        return None
    if receipt["record"] != expected or receipt["digest"] != _digest(expected):
        raise WriteRefused("verification operation receipt does not match the original intent")
    return receipt["record"]


def _write(p, doc):
    raw = json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=1).encode()
    if len(raw) > MAX_BYTES:
        raise WriteRefused("verification store is full; preserve existing evidence")
    fd, name = tempfile.mkstemp(prefix=".verification-", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(name, p)
        directory = os.open(p.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def get(host: str, session_id: str) -> dict | None:
    return next(
        (r for r in reversed(_read(path())) if r.get("host") == host and r.get("session_id") == session_id),
        None,
    )


def record(
    host: str,
    session_id: str,
    *,
    candidate_commit: str,
    command: str,
    exit_code: int,
    environment: str,
    log_ref: str,
    actor: str,
    operation_id: str | None = None,
    recorded_at: float | None = None,
) -> dict:
    validate(candidate_commit, command, exit_code, environment, log_ref)
    row = {
        "host": host,
        "session_id": session_id,
        "candidate_commit": candidate_commit.lower(),
        "command": command,
        "exit_code": exit_code,
        "environment": environment,
        "log_ref": log_ref,
        "actor": actor,
        "recorded_at": time.time() if recorded_at is None else recorded_at,
    }
    _row_valid(row)
    if operation_id is not None and not re.fullmatch(r"op_[0-9a-f]{32}", operation_id):
        raise WriteRefused("invalid verification operation identity")
    p = path()
    with _locked(p):
        doc = _document(p)
        if operation_id is not None:
            existing = doc["operation_receipts"].get(operation_id)
            if existing is not None:
                if existing["record"] != row:
                    raise WriteRefused("verification operation receipt conflicts with its original intent")
                return existing["record"]
            doc["operation_receipts"][operation_id] = {"record": row, "digest": _digest(row)}
        doc["records"] = [r for r in doc["records"] if (r["host"], r["session_id"]) != (host, session_id)]
        doc["records"].append(row)
        _write(p, doc)
    return row


def matches(record: dict | None, head: str | None) -> bool:
    return bool(
        record
        and head
        and record.get("exit_code") == 0
        and record.get("candidate_commit") == head.lower()
        and record.get("command")
        and record.get("environment")
        and record.get("log_ref")
    )
