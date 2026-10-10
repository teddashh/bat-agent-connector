"""A drag keeps both the displayed sibling order and each displayed version."""
from __future__ import annotations

import pytest

from bat_agent_connector import work_items
from tests import test_work_items as fixtures
from tests.test_work_items import PERSON, act, get, item, project, refused

daemon = fixtures.daemon


@pytest.mark.parametrize("kind", ["project", "work_item"])
async def test_reorder_checks_every_sibling_version_before_and_during_execution(daemon, kind):
    if kind == "project":
        first, second = await project(daemon, "One"), await project(daemon, "Two")
        target, identity = {}, "project_id"
        update = {"name": "Renamed while dragging"}
        def row(key):
            return work_items.project_get(daemon.journal.db, key)["project"]
    else:
        parent = await project(daemon)
        first, second = await item(daemon, parent, "One"), await item(daemon, parent, "Two")
        target, identity = {"project_id": parent}, "work_item_id"
        update = {"title": "Renamed while dragging"}
        def row(key):
            return get(daemon, key)
    versions = {first: row(first)["version"], second: row(second)["version"]}
    params, pre = {"order": [second, first]}, {"before": [first, second], "expected_versions": versions}
    accepted = daemon.ops.create(PERSON, action=f"{kind}.order", target=target,
        params=params, preconditions=pre, idempotency_key="drag-before-edit")[0]
    change = daemon.ops.create(PERSON, action=f"{kind}.update", target={identity: second},
        params=update, preconditions={"expected_version": versions[second]}, idempotency_key="rename")[0]
    await daemon.ops._execute(change["operation_id"])
    await daemon.ops._execute(accepted["operation_id"])
    assert daemon.ops.get(accepted["operation_id"])["error_code"] == "VERSION_CONFLICT"
    assert refused(daemon, PERSON, f"{kind}.order", target, params, pre).code == "VERSION_CONFLICT"
    current = {first: row(first)["version"], second: row(second)["version"]}
    await act(daemon, PERSON, f"{kind}.order", target, params, {**pre, "expected_versions": current})


@pytest.mark.parametrize("versions", [{}, {"bogus": 1}, None])
async def test_invalid_version_map_is_refused_or_legacy_order_remains_supported(daemon, versions):
    parent = await project(daemon)
    first, second = await item(daemon, parent, "One"), await item(daemon, parent, "Two")
    params, pre = {"order": [second, first]}, {"before": [first, second], "expected_versions": versions}
    if versions is None:
        await act(daemon, PERSON, "work_item.order", {"project_id": parent}, params, pre)
    else:
        assert refused(daemon, PERSON, "work_item.order", {"project_id": parent}, params, pre).code == "PRECONDITION_REQUIRED"
