"""Malformed JSON references refuse at HTTP admission, before durable or host effects."""

import asyncio
import hashlib
import json

import pytest

from bat_agent_connector import api_auth
from tests.test_artifacts import PERSON, action, upload
from tests.test_artifacts import daemon as daemon  # noqa: F401 - shared isolated fixtures
from tests.test_artifacts import human as human  # noqa: F401


async def post(daemon, path, body):
    with daemon.journal.tx():
        token = api_auth.issue(daemon.journal.db, PERSON.actor, list(PERSON.scopes))
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
        payload = json.dumps(body).encode()
        writer.write((f"POST {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\n"
                      f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
                      "Idempotency-Key: malformed-artifact\r\nConnection: close\r\n\r\n").encode() + payload)
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 5)
        headers, raw = response.split(b"\r\n\r\n", 1)
        return int(headers.split(b" ", 2)[1]), json.loads(raw)
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()
        server.close()
        await server.wait_closed()


def saved_state(daemon, mock):
    tables = ("operations", "operation_steps", "artifacts", "artifact_revisions", "artifact_uploads",
              "artifact_references", "work_items", "api_events")
    return ({table: [tuple(row) for row in daemon.journal.db.execute("SELECT * FROM " + table)]
             for table in tables}, list(mock.invokes), daemon.artifact_store.used_bytes())


@pytest.mark.parametrize("role", [[], {}])
@pytest.mark.parametrize("kind", ["create", "update"])
async def test_http_attachment_role_containers_refuse_without_effects(daemon, mock, role, kind):
    ref = await upload(daemon)
    project = await action(daemon, "project.create", params={"name": "Admission fixture"})
    target = {"project_id": project["result"]["project_id"]}
    params, pre = {"title": "Attachment fixture"}, {}
    if kind == "update":
        item = await action(daemon, "work_item.create", target, params)
        target = {"work_item_id": item["result"]["work_item_id"]}
        params, pre = {}, {"expected_version": item["result"]["version"]}
    params["attachments"] = [{**ref, "role": role}]
    before = saved_state(daemon, mock)
    status, body = await post(daemon, "/api/v1/operations", {
        "action": "work_item." + kind, "target": target, "params": params, "preconditions": pre})
    assert status == 422 and body["error"]["code"] == "INVALID_ARTIFACT_REF", body
    assert saved_state(daemon, mock) == before


@pytest.mark.parametrize("artifact_id", [None, "", "not-an-artifact", [], ["x"], {}, {"id": "x"}, True, 3])
@pytest.mark.parametrize("path", ["/api/v1/operations", "/api/v1/artifacts"])
async def test_http_upload_target_must_be_an_artifact_id_before_reservation(daemon, mock, artifact_id, path):
    before = saved_state(daemon, mock)
    status, body = await post(daemon, path, {"action": "artifact.upload", "target": {"artifact_id": artifact_id},
        "params": {"display_name": "fixture.txt", "size_bytes": 0, "expected_digest": hashlib.sha256(b"").hexdigest()}})
    assert status == 422 and body["error"]["code"] == "INVALID_ARTIFACT_REF", body
    assert saved_state(daemon, mock) == before
