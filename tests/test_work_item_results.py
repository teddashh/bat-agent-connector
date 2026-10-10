from __future__ import annotations

import pytest

from bat_agent_connector import api_auth, work_item_results
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.test_artifacts import upload
from tests.test_work_items import PERSON, act, item, project


@pytest.fixture
async def daemon(mock, tmp_path):
    daemon = TaskDaemon(make_config(mock), tmp_path / "journal" / "tasks.sqlite3")
    daemon.acquire_owner()
    try:
        yield daemon
    finally:
        await daemon.artifact_store.close_reaper()
        await daemon.api.session_observation.close()
        await daemon.inventory.close()
        await daemon.fleet.close()
        daemon.journal.close()


async def test_sources_follow_exact_child_links_and_fixed_result_revisions(daemon):
    d = daemon
    pid = await project(d)
    parent = await item(d, pid, "same title")
    child = await item(d, pid, "same title", parent_id=parent)
    unrelated = await item(d, pid, "same title")
    ref = await upload(d)
    await act(d, PERSON, "work_item.update", {"work_item_id": child},
              {"attachments": [{**ref, "role": "result"}]}, {"expected_version": 1})
    op = await act(d, PERSON, "project.create", params={"name": "another"})
    for wid in (child, unrelated):
        await act(d, PERSON, "work_item.link", {"work_item_id": wid},
                  {"kind": "operation", "ref": op["operation_id"]})
    # Only a durable delivered receipt establishes delivery, not succeeded op state.
    receipt = dict(operation_id="op_" + "a" * 20, seq=1, preview_id="preview", repository="o/r", pull_number=4,
                   head_ref="review", source_kind="execution", source_id=op["operation_id"], source_host="h1",
                   location_class="managed", pinned_sha="a" * 40, mode="merge", source_key="exact-source",
                   status="delivered", delivered_sha="b" * 40, delivered_at=123, actor="fixture", created_at=123,
                   updated_at=123)
    d.ops.db.execute("INSERT INTO integration_receipts(" + ",".join(receipt) + ") VALUES("
                     + ",".join("?" for _ in receipt) + ")", tuple(receipt.values()))
    summary = work_item_results.read(d.ops, PERSON, parent)
    assert [row["work_item_id"] for row in summary["children"]] == [child]
    result = summary["children"][0]
    assert summary["item"]["completion"]["display_state"] == result["completion"]["display_state"] == "todo"
    assert result["links"][0]["target"]["status"] == "succeeded"
    assert result["links"][0]["delivered_to"][0]["pinned_sha"] == "a" * 40
    artifact = result["result_artifacts"][0]
    assert {key: artifact[key] for key in ref} == ref
    assert artifact["available"] and artifact["source"]["kind"] == "upload"
    assert artifact["recorded_consumers"] == [{"owner_kind": "work_item", "owner_id": child, "role": "result"}]
    assert artifact["live_consumers"] == "unknown"
    assert work_item_results.read(d.ops, PERSON, child)["parent"]["work_item_id"] == parent
    d.ops.db.execute("UPDATE artifact_revisions SET state='unavailable' WHERE artifact_id=?", (ref["artifact_id"],))
    missing = work_item_results.read(d.ops, PERSON, child)["item"]["result_artifacts"][0]
    assert not missing["available"] and missing["digest"] == ref["digest"] and missing["content_url"] is None


async def test_child_pages_derivation_and_removed_links_do_not_infer_results(daemon):
    d = daemon
    pid = await project(d)
    parent = await item(d, pid, "parent")
    children = [await item(d, pid, str(n), parent_id=parent) for n in range(3)]
    derived = await item(d, pid, "derived", derived_from=parent)
    await act(d, PERSON, "work_item.link", {"work_item_id": parent}, {"kind": "pull_request", "ref": "o/r#1"})
    await act(d, PERSON, "work_item.link", {"work_item_id": parent},
              {"kind": "pull_request", "ref": "o/r#1", "remove": True})
    first = work_item_results.read(d.ops, PERSON, parent, limit=2)
    second = work_item_results.read(d.ops, PERSON, parent, limit=2, after=first["children_next_cursor"])
    assert sorted(row["work_item_id"] for row in first["children"] + second["children"]) == sorted(children)
    assert second["children_next_cursor"] is None and first["item"]["links"] == []
    assert work_item_results.read(d.ops, PERSON, derived)["derived_from"]["work_item_id"] == parent
    with pytest.raises(OperationError, match="observe"):
        work_item_results.read(d.ops, api_auth.Principal("none", frozenset()), parent)
    with pytest.raises(OperationError, match="limit"):
        work_item_results.read(d.ops, PERSON, parent, limit=True)
