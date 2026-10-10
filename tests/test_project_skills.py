from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

import pytest

from bat_agent_connector import api_auth, project_skills
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.operation_helpers import settle_operations

PERSON = api_auth.Principal("person", frozenset({"observe", "manage"}))
REF = {"skill_id": "skill_" + "1" * 32, "digest": "2" * 64}


class Host:
    def __init__(self):
        self.rows = [{**REF, "name": "Reviewed helper", "description": "A fixed skill", "scope": "project",
                      "relative_path": "skills/helper", "files": 2, "size_bytes": 100, "agent": "claude",
                      "available": True, "reason": None}]
        self.offline = False
        self.calls = []

    async def scan(self, host, folder):
        self.calls.append((host, folder))
        if self.offline:
            raise OSError("private SSH error")
        return {"ok": True, "version": 1, "skills": copy.deepcopy(self.rows), "complete": True}


@pytest.fixture
async def context(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock), tmp_path / "journal" / "tasks.sqlite3")
    daemon.acquire_owner()
    project_skills.install(daemon.ops)
    operation, _ = daemon.ops.create(PERSON, action="project.create", target={}, params={"name": "project"},
                                     preconditions={}, idempotency_key="project")
    await settle_operations(daemon.ops)
    project = daemon.ops.get(operation["operation_id"])["result"]["project_id"]
    host = Host()
    daemon.ops.context["skill_host"] = host
    document = await project_skills.service._workspace(daemon.fleet.client("h1"))
    workspace = document["workspaces"][0]
    try:
        yield daemon, project, workspace, host
    finally:
        await daemon.artifact_store.close_reaper()
        await daemon.api.session_observation.close()
        await daemon.inventory.close()
        await daemon.fleet.close()
        daemon.journal.close()


async def test_selection_is_fixed_to_host_workspace_and_source_digest(context):
    daemon, project, workspace, host = context
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert host.calls == [("h1", workspace["folderPath"])]
    op, _ = daemon.ops.create(PERSON, action="project.skills.update", target={"project_id": project}, params={
        "host": "h1", "workspace_id": workspace["id"], "selected": [REF]},
        preconditions={"expected_revision": 0, "expected_catalog_digest": value["catalog"]["catalog_digest"]},
        idempotency_key="select")
    await settle_operations(daemon.ops)
    result = daemon.ops.get(op["operation_id"])
    assert result["status"] == "succeeded", result
    assert result["result"]["application"] == "selected_not_applied"
    host.rows = []
    missing = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"], refresh=True)
    assert missing["selection"]["selected"] == [REF]
    assert missing["selection"]["unresolved"] == [REF]
    assert missing["selection"]["revision"] == 1


async def test_changed_catalog_before_operation_effect_prevents_selection(context):
    daemon, project, workspace, host = context
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    op, _ = daemon.ops.create(PERSON, action="project.skills.update", target={"project_id": project}, params={
        "host": "h1", "workspace_id": workspace["id"], "selected": [REF]},
        preconditions={"expected_revision": 0, "expected_catalog_digest": value["catalog"]["catalog_digest"]},
        idempotency_key="changed")
    host.rows[0]["digest"] = "3" * 64
    await settle_operations(daemon.ops)
    assert daemon.ops.get(op["operation_id"])["status"] == "failed"
    assert project_skills.selection(daemon.ops.db, project)["selected"] == []


async def test_unavailable_catalog_does_not_adopt_arbitrary_paths(context):
    daemon, project, workspace, host = context
    host.offline = True
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert value["catalog"]["status"] == "unavailable"
    assert "private SSH error" not in json.dumps(value)
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", "/arbitrary/path")
    assert value["catalog"]["reason"] == "workspace_unavailable"
    assert host.calls == [("h1", workspace["folderPath"])]
    with pytest.raises(OperationError, match="observe"):
        await project_skills.read(daemon.ops, api_auth.Principal("none", frozenset()), project, "h1", workspace["id"])


async def test_skill_cache_and_review_are_invalidated_when_host_binding_changes(context):
    daemon, project, workspace, host = context
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert "_source_binding" not in json.dumps(value)
    daemon.fleet.config.host("h1").profile_id = "new-profile"
    with pytest.raises(OperationError, match="SKILL_CATALOG_CHANGED"):
        daemon.ops.create(PERSON, action="project.skills.update", target={"project_id": project}, params={
            "host": "h1", "workspace_id": workspace["id"], "selected": [REF]},
            preconditions={"expected_revision": 0, "expected_catalog_digest": value["catalog"]["catalog_digest"]},
            idempotency_key="old-host-catalog")
    host.offline = True
    changed = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert changed["catalog"]["status"] == "unavailable" and changed["catalog"]["skills"] == []
    host.offline = False
    refreshed = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert refreshed["catalog"]["catalog_digest"] != value["catalog"]["catalog_digest"]


async def test_skill_host_change_during_scan_does_not_cache_old_source(context, monkeypatch):
    daemon, project, workspace, host = context
    original = host.scan
    async def racing(*args):
        document = await original(*args)
        daemon.fleet.config.host("h1").profile_id = "changed-during-scan"
        return document
    monkeypatch.setattr(host, "scan", racing)
    value = await project_skills.read(daemon.ops, PERSON, project, "h1", workspace["id"])
    assert value["catalog"]["status"] == "unavailable" and value["catalog"]["reason"] == "host_binding_changed"
    assert not daemon.ops.db.execute("SELECT 1 FROM project_skill_catalogs").fetchone()


@pytest.mark.skipif(os.name == "nt", reason="helper runs on the explicitly selected POSIX BAT host")
def test_read_only_helper_binds_supporting_files_and_rejects_links(tmp_path):
    root = tmp_path / "workspace"
    skill = root / ".claude" / "skills" / "helper"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: helper\ndescription: fixed helper\n---\n# Instructions\n")
    (skill / "helper.py").write_text("print('first')")
    def scan():
        completed = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", project_skills.HELPER],  # noqa: S603
            input=json.dumps({"workspace": str(root), "include_global": False}).encode(), capture_output=True, check=True)
        return json.loads(completed.stdout)
    first = scan()
    assert first["ok"] and first["skills"][0]["files"] == 2
    (skill / "helper.py").write_text("print('second')")
    assert scan()["skills"][0]["digest"] != first["skills"][0]["digest"]
    outside = tmp_path / "private"
    outside.write_text("fixture private bytes")
    (skill / "link").symlink_to(outside)
    unsafe = scan()
    assert not unsafe["skills"][0]["available"]
    assert unsafe["skills"][0]["digest"] is None
    assert "fixture private bytes" not in json.dumps(unsafe)
    assert outside.read_text() == "fixture private bytes"
