"""Deployment history rejects invalid scalars before SQL and retains numeric ordering."""

import asyncio
import base64
import json
from urllib.parse import urlencode

import pytest

from bat_agent_connector import deployment_store
from tests import test_delivery as fixtures
from tests.test_api_v1 import http, token
from tests.test_deployment_config import legacy_operations

gh = fixtures.gh
make_daemon = fixtures.make_daemon
ROUTES = ("/api/v1/deployments", "/api/v1/deployment-environments/history")


def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


def populate(d):
    legacy_operations(d.journal)
    d.journal.db.execute("PRAGMA user_version=2")
    deployment_store.backfill(d.journal)


@pytest.fixture
async def served(make_daemon):
    d = make_daemon()
    viewer = token(d, "history-viewer", "observe")
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    try:
        yield d, server.sockets[0].getsockname()[1], viewer
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("stamp", [
    pytest.param(2**63, id="overflow"), pytest.param(-(2**63) - 1, id="underflow"),
    pytest.param(10**400, id="huge-positive"), pytest.param(-(10**400), id="huge-negative"),
    pytest.param(float("nan"), id="nan"), pytest.param(float("inf"), id="infinity"),
    pytest.param(float("-inf"), id="negative-infinity"), pytest.param(True, id="bool"),
    pytest.param(None, id="null"), pytest.param("1", id="string"),
    pytest.param([], id="list"), pytest.param({}, id="object"),
])
async def test_invalid_timestamp_http_rpc_empty_and_populated(served, gh, mock, stamp):
    d, port, viewer = served
    cursor = encode([stamp, "dep_" + "a" * 32])
    for populated in (False, True):
        if populated:
            populate(d)
        before = d.journal.api_head(), d.ops.list(), list(gh.requests), list(mock.invokes)
        queries = []
        d.journal.db.set_trace_callback(queries.append)
        params = {"recipe": "prod", "cursor": cursor}
        try:
            for route in ROUTES:
                status, result = await http(port, "GET", route + "?" + urlencode(params), tok=viewer)
                assert status == 422 and result["error"]["code"] == "INVALID_PARAMS", result
            status, result = await http(port, "POST", "/rpc", tok=viewer,
                                        body={"method": "deployments_list", "params": params})
            assert status == 400 and result["error"] == "INVALID_PARAMS", result
        finally:
            d.journal.db.set_trace_callback(None)
        assert not any("SELECT deployment_id,created_at FROM deployments" in query for query in queries)
        assert (d.journal.api_head(), d.ops.list(), gh.requests, mock.invokes) == before


@pytest.mark.parametrize("cursor", [False, 0, [], {}, encode(None), encode({"stamp": 1, "id": "dep_a"}),
                                   encode([1]), encode([1, "dep_a", "extra"])])
async def test_invalid_cursor_shape_rpc(served, cursor):
    _, port, viewer = served
    status, result = await http(port, "POST", "/rpc", tok=viewer,
                                body={"method": "deployments_list", "params": {"recipe": "prod", "cursor": cursor}})
    assert status == 400 and result["error"] == "INVALID_PARAMS", result


async def test_valid_cursor_integer_precision_boundaries_and_saved_pages(served, gh):
    d, port, viewer = served
    populate(d)
    ids = [row[0] for row in d.journal.db.execute("SELECT deployment_id FROM deployments ORDER BY deployment_id")]
    for index, dep_id in enumerate(ids):
        d.journal.db.execute("UPDATE deployments SET created_at=? WHERE deployment_id=?", (2**53 + index * 2, dep_id))
    # The midpoint must remain an integer: float conversion rounds it down and loses the lower row.
    samples = [(2**53 + 1, [ids[0]]), (-(2**63), []), (2**63 - 1, list(reversed(ids))),
               (-1e308, []), (1e308, list(reversed(ids)))]
    for stamp, expected in samples:
        params = {"recipe": "prod", "cursor": encode([stamp, "dep_0"])}
        for route in ROUTES:
            status, result = await http(port, "GET", route + "?" + urlencode(params), tok=viewer)
            assert status == 200 and [row["deployment_id"] for row in result["items"]] == expected, result
        status, result = await http(port, "POST", "/rpc", tok=viewer,
                                    body={"method": "deployments_list", "params": params})
        assert status == 200 and [row["deployment_id"] for row in result["result"]["items"]] == expected
    for route in ROUTES:
        status, first = await http(port, "GET", route + "?recipe=prod&limit=1", tok=viewer)
        assert status == 200 and first["items"][0]["deployment_id"] == ids[1] and first["next_cursor"]
        status, second = await http(port, "GET", route + "?" + urlencode(
            {"recipe": "prod", "limit": 1, "cursor": first["next_cursor"]}), tok=viewer)
        assert status == 200 and second["items"][0]["deployment_id"] == ids[0] and second["next_cursor"] is None
    assert gh.requests == []
