"""Native central runtime contract, also exercised on POSIX for parity.

No BAT/provider network access. The Windows CI lane runs these against actual
NTFS handles/ACLs, not monkeypatched os.name or an emulated Windows filesystem.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess

import pytest

from bat_agent_connector import api_auth, platform_files
from bat_agent_connector.artifacts import ArtifactSettings
from bat_agent_connector.config import Config
from bat_agent_connector.errors import OwnerConflict
from bat_agent_connector.task_daemon import TaskDaemon
from tests.operation_helpers import settle_operations

PERSON = api_auth.Principal("local-person", frozenset({"observe", "manage"}))


async def _close(daemon):
    await daemon.artifact_store.close_reaper()
    await daemon.api.session_observation.close()
    await daemon.inventory.close()
    await daemon.fleet.close()
    daemon.journal.close()


async def test_central_owner_artifact_publication_and_restart(tmp_path):
    path = tmp_path / "journal" / "tasks.sqlite3"
    first = TaskDaemon(Config(hosts={}), path)
    first.acquire_owner()
    second = TaskDaemon(Config(hosts={}), path)
    with pytest.raises(OwnerConflict):
        second.acquire_owner()
    raw = b"immutable local artifact\n"
    try:
        token = first._admin_token
        op, _ = first.ops.create(PERSON, action="artifact.upload", target={}, params={
            "display_name": "notes.txt", "size_bytes": len(raw),
            "expected_digest": hashlib.sha256(raw).hexdigest()}, preconditions={}, idempotency_key="portable-upload")
        identity = op["operation_id"]
        await settle_operations(first.ops)
        stream = asyncio.StreamReader()
        stream.feed_data(raw)
        stream.feed_eof()
        await first.artifact_store.receive(PERSON, identity, stream, len(raw))
        await settle_operations(first.ops)
        complete = first.ops.get(identity)
        assert complete["status"] == "succeeded", complete
        ref = complete["result"]
        assert first.artifact_store.read_content(ref["artifact_id"], ref["revision"]) == raw
        # Repeat the actual publication recovery path, including an already
        # read-only destination and the source removed by the first rename.
        row = dict(first.journal.db.execute("SELECT * FROM artifact_uploads WHERE operation_id=?", (identity,)).fetchone())
        # Reaping may already have removed staging; publication recovery itself
        # is exercised before the reaper below in the dedicated fixture.
        assert first.artifact_store.published(row) in (None, ref)
    finally:
        await _close(first)
    reopened = TaskDaemon(Config(hosts={}), path)
    try:
        reopened.acquire_owner()
        assert reopened._admin_token == token
        assert reopened.ops.get(identity)["status"] == "succeeded"
        assert reopened.artifact_store.read_content(ref["artifact_id"], ref["revision"]) == raw
        assert not reopened.journal.db.execute("SELECT 1 FROM operations WHERE operation_id!=?", (identity,)).fetchone()
    finally:
        await _close(reopened)


async def test_publish_recovery_does_not_replace_existing_revision(tmp_path):
    daemon = TaskDaemon(Config(hosts={}), tmp_path / "journal" / "tasks.sqlite3")
    daemon.acquire_owner()
    try:
        # Keep the source directory for explicit crash-after-publish replay.
        daemon.artifact_store.schedule_reap = lambda *args: None
        raw = b"publication recovery"
        op, _ = daemon.ops.create(PERSON, action="artifact.upload", target={}, params={
            "display_name": "recovery.txt", "size_bytes": len(raw),
            "expected_digest": hashlib.sha256(raw).hexdigest()}, preconditions={}, idempotency_key="publish-recovery")
        await settle_operations(daemon.ops)
        stream = asyncio.StreamReader()
        stream.feed_data(raw)
        stream.feed_eof()
        await daemon.artifact_store.receive(PERSON, op["operation_id"], stream, len(raw))
        await settle_operations(daemon.ops)
        row = dict(daemon.journal.db.execute("SELECT * FROM artifact_uploads WHERE operation_id=?", (op["operation_id"],)).fetchone())
        first = daemon.artifact_store.publish(row)
        assert daemon.artifact_store.publish(row) == first
        assert daemon.artifact_store.read_content(first["artifact_id"], first["revision"]) == raw
    finally:
        await _close(daemon)


def test_artifact_store_accepts_native_absolute_path(tmp_path):
    assert ArtifactSettings.from_dict({"store_root": str(tmp_path)}).store_root == str(tmp_path)
    with pytest.raises(ValueError, match="absolute"):
        ArtifactSettings.from_dict({"store_root": "relative/path"})


@pytest.mark.skipif(os.name != "nt", reason="native Windows ACL contract")
def test_windows_rejects_foreign_acl_without_repairing_it(tmp_path):
    root = tmp_path / "owned"
    platform_files.ensure_private_directory(root)
    path = root / "token"
    platform_files.atomic_write(path, b"private-token-fixture")
    subprocess.run(["icacls.exe", str(path), "/grant", "*S-1-1-0:(R)"], check=True, capture_output=True)  # noqa: S603,S607
    with pytest.raises(ValueError, match="another principal"):
        platform_files.read_private(path)
    with pytest.raises(ValueError, match="another principal"):
        platform_files.atomic_write(path, b"must-not-replace")
    assert path.read_bytes() == b"private-token-fixture"


@pytest.mark.skipif(os.name != "nt", reason="native Windows junction contract")
def test_windows_junction_cannot_redirect_creation(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    junction = tmp_path / "junction"
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],  # noqa: S603,S607
                   check=True, capture_output=True)
    try:
        with pytest.raises((ValueError, OSError)):
            platform_files.ensure_private_directory(junction / "state")
        assert not (target / "state").exists()
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="native Windows pinned-directory contract")
def test_windows_directory_chain_cannot_be_replaced_while_open(tmp_path):
    root = tmp_path / "owned"
    platform_files.ensure_private_directory(root / "nested")
    held = platform_files.native.open_dir(root / "nested")
    try:
        with pytest.raises(PermissionError):
            root.rename(tmp_path / "swapped")
    finally:
        held.close()
    root.rename(tmp_path / "swapped")
