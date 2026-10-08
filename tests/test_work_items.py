"""Projects and work items: tree, order, pins, versions, completion approval and links (work_items.py).

The order and completion cases follow Project Hub v4.68.2's own tests (project-order.test.js,
completion.test.js) where the rules were ported.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from bat_agent_connector import api_auth, work_items
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.test_api_v1 import http, token

PERSON = api_auth.Principal("ted-dashboard", frozenset({"observe", "manage", "approve"}))
AGENT = api_auth.Principal("hermes", frozenset({"observe", "manage"}))
VIEWER = api_auth.Principal("viewer", frozenset({"observe"}))


@pytest.fixture
def daemon(mock, tmp_path):
    d = TaskDaemon(make_config(mock, writes=True, orchestrate=True, managed_roots=["/srv"],
                               safety={"write_min_interval_s": 0}), tmp_path / "tasks.db")
    yield d
    d.journal.close()


@pytest.fixture
async def served(daemon):
    server = await asyncio.start_server(daemon._handle, "127.0.0.1", 0)
    worker = asyncio.create_task(daemon.ops.loop(0.05))
    yield daemon, server.sockets[0].getsockname()[1]
    worker.cancel()
    server.close()
    await server.wait_closed()
    await daemon.fleet.close()
    await daemon.inventory.close()


async def act(d, who, action, target=None, params=None, pre=None, *, key=None, ok=True):
    op, _ = d.ops.create(who, action=action, target=target or {}, params=params or {}, preconditions=pre or {},
                         idempotency_key=key or str(uuid.uuid4()))
    await d.ops.drain()
    op = d.ops.get(op["operation_id"])
    if ok:
        assert op["status"] == "succeeded", (op["error_code"], op["status_reason"])
    return op


def refused(d, who, action, target=None, params=None, pre=None) -> OperationError:
    before = d.journal.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    with pytest.raises(OperationError) as e:
        d.ops.create(who, action=action, target=target or {}, params=params or {}, preconditions=pre or {},
                     idempotency_key=str(uuid.uuid4()))
    assert d.journal.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == before  # nothing stored
    return e.value


async def project(d, name="App", **params) -> str:
    return (await act(d, PERSON, "project.create", params={"name": name, **params}))["result"]["project_id"]


async def item(d, pid, title, who=PERSON, **params) -> str:
    op = await act(d, who, "work_item.create", {"project_id": pid}, {"title": title, **params})
    return op["result"]["work_item_id"]


def get(d, wid) -> dict:
    return work_items.work_item_get(d.journal.db, wid)["work_item"]


def ids(tree) -> list[str]:
    return [x.get("work_item_id") or x.get("project_id") for x in tree]


# --------------------------------------------------------------------------- order rules (project-order.js)
def test_sibling_order_follows_the_hub_rules():
    def e(i, derived=None, pinned=False):
        return {"id": i, "derived_from": derived, "pinned": pinned}

    every = [e("a"), e("b"), e("c"), e("fork", "c"), e("fork2", "fork"), e("manual", "c")]
    order = lambda items, saved: [x["id"] for x in work_items.siblings(items, saved, "id")]  # noqa: E731
    # a branch never placed sits right after its source; a placed one keeps its saved slot
    assert order(every, ["manual", "b", "a", "c"]) == ["manual", "b", "a", "c", "fork", "fork2"]
    assert order(every, ["a", "b", "c"]) == ["a", "b", "c", "fork", "fork2", "manual"]
    assert order(every, None) == ["a", "b", "c", "fork", "fork2", "manual"]
    # new entries go to the end (Hub puts new projects first; a work list appends)
    assert order([*every, e("new")], ["manual", "b", "a", "c"])[-1] == "new"
    # pins first, saved order kept within each part
    pinned = [e("a"), e("b", pinned=True), e("c")]
    assert order(pinned, ["c", "a", "b"]) == ["b", "c", "a"]
    # a derived cycle still shows every entry
    assert sorted(order([e("x", "y"), e("y", "x")], None)) == ["x", "y"]


async def test_reorder_needs_the_order_you_saw_keeps_pins_on_top_and_archived_slots(daemon):
    d = daemon
    pid = await project(d)
    a, b, c = [await item(d, pid, t) for t in "ABC"]
    tree = lambda: ids(work_items.project_get(d.journal.db, pid)["work_items"])  # noqa: E731
    assert tree() == [a, b, c]
    await act(d, PERSON, "work_item.order", {"project_id": pid}, {"order": [c, a, b]}, {"before": [a, b, c]})
    assert tree() == [c, a, b]
    # a stale view, a partial order or a duplicate is refused before anything is stored
    for params, pre in (({"order": [a, b, c]}, {"before": [a, b, c]}), ({"order": [a, b]}, {"before": [c, a, b]}),
                        ({"order": [a, a, b]}, {"before": [c, a, b]}), ({"order": [a, b, c]}, {})):
        assert refused(d, PERSON, "work_item.order", {"project_id": pid}, params, pre).code in {
            "ORDER_CHANGED", "INVALID_PARAMS", "PRECONDITION_REQUIRED"}
    # pin b: it moves first; a pinned entry cannot be ordered below an unpinned one
    await act(d, PERSON, "work_item.pin", {"work_item_id": b}, {"pinned": True}, {"before": False})
    assert tree() == [b, c, a]
    assert refused(d, PERSON, "work_item.pin", {"work_item_id": b}, {"pinned": True},
                   {"before": False}).code == "PIN_CHANGED"
    assert refused(d, PERSON, "work_item.order", {"project_id": pid}, {"order": [c, b, a]},
                   {"before": [b, c, a]}).code == "PINNED_FIRST"
    await act(d, PERSON, "work_item.pin", {"work_item_id": b}, {"pinned": False}, {"before": True})
    # an archived entry keeps its slot: archive c, reorder the rest, restore c -> back at the front
    await act(d, PERSON, "work_item.update", {"work_item_id": c}, {"archived": True},
              {"expected_version": get(d, c)["version"]})
    assert tree() == [a, b]
    await act(d, PERSON, "work_item.order", {"project_id": pid}, {"order": [b, a]}, {"before": [a, b]})
    await act(d, PERSON, "work_item.update", {"work_item_id": c}, {"archived": False},
              {"expected_version": get(d, c)["version"]})
    assert tree() == [c, b, a]


async def test_projects_form_a_tree_with_unique_names_and_no_cycles(daemon):
    d = daemon
    root = await project(d, "Root", description="all", repositories=["o/r", "O/R"], task_project="app")
    kid = await project(d, "Kid", parent_id=root)
    grandkid = await project(d, "Grandkid", parent_id=kid)
    listing = work_items.projects_list(d.journal.db)["projects"]
    assert ids(listing) == [root] and ids(listing[0]["children"]) == [kid]
    assert ids(listing[0]["children"][0]["children"]) == [grandkid]
    got = work_items.project_get(d.journal.db, root)
    assert got["project"]["repositories"] == ["o/r"] and got["project"]["task_project"] == "app"
    assert [p["project_id"] for p in got["sub_projects"]] == [kid]
    assert work_items.project_get(d.journal.db, grandkid)["path"] == [
        {"project_id": root, "name": "Root"}, {"project_id": kid, "name": "Kid"}]
    assert refused(d, PERSON, "project.create", params={"name": "Root"}).code == "NAME_TAKEN"
    v = work_items.project_get(d.journal.db, root)["project"]["version"]
    assert refused(d, PERSON, "project.update", {"project_id": root}, {"parent_id": grandkid},
                   {"expected_version": v}).code == "CYCLE"
    for bad in ({"name": ""}, {"name": "two\nlines"}, {"name": "x" * 81}, {"name": "ok", "repositories": ["nope"]},
                {"name": "ok", "parent_id": "prj_" + "0" * 20}, {"name": "ok", "owner": "me"}):
        assert refused(d, PERSON, "project.create", params=bad).code in {
            "INVALID_PARAMS", "PROJECT_NOT_FOUND"}
    # archive needs its sub-projects archived first; restore needs the name to be free again
    assert refused(d, PERSON, "project.update", {"project_id": kid}, {"archived": True},
                   {"expected_version": 1}).code == "HAS_CHILDREN"
    await act(d, PERSON, "project.update", {"project_id": grandkid}, {"archived": True}, {"expected_version": 1})
    await act(d, PERSON, "project.create", params={"name": "Grandkid"})
    assert refused(d, PERSON, "project.update", {"project_id": grandkid}, {"archived": False},
                   {"expected_version": 2}).code == "NAME_TAKEN"
    assert grandkid in [p["project_id"] for p in
                        work_items.projects_list(d.journal.db, include_archived=True)["archived"]]


async def test_a_rename_keeps_ids_and_relations_and_needs_the_version_you_read(daemon):
    d = daemon
    pid = await project(d)
    parent = await item(d, pid, "Parent")
    kid = await item(d, pid, "Kid", parent_id=parent)
    branch = await item(d, pid, "Branch", derived_from=kid, parent_id=parent)
    await act(d, PERSON, "work_item.update", {"work_item_id": parent}, {"title": "Renamed"}, {"expected_version": 1})
    got = work_items.work_item_get(d.journal.db, kid)
    assert got["path"] == [{"work_item_id": parent, "title": "Renamed"}]
    assert [x["work_item_id"] for x in work_items.work_item_get(d.journal.db, kid)["derived"]] == [branch]
    # a second edit based on version 1 is refused up front, and nothing is stored
    e = refused(d, PERSON, "work_item.update", {"work_item_id": parent}, {"title": "Again"}, {"expected_version": 1})
    assert e.code == "VERSION_CONFLICT" and e.status == 409
    assert refused(d, PERSON, "work_item.update", {"work_item_id": parent}, {"title": "x"}).code == \
        "PRECONDITION_REQUIRED"
    # two edits admitted against the same version: the second fails when it runs
    first, _ = d.ops.create(PERSON, action="work_item.update", target={"work_item_id": kid},
                            params={"goal": "one"}, preconditions={"expected_version": 1}, idempotency_key="k1")
    second, _ = d.ops.create(PERSON, action="work_item.update", target={"work_item_id": kid},
                             params={"goal": "two"}, preconditions={"expected_version": 1}, idempotency_key="k2")
    await d.ops.drain()
    ran = sorted(d.ops.get(x["operation_id"])["status"] for x in (first, second))
    assert ran == ["failed", "succeeded"] and get(d, kid)["version"] == 2
    assert {d.ops.get(x["operation_id"])["error_code"] for x in (first, second)} == {None, "VERSION_CONFLICT"}
    # moves stay inside the project and never under the item's own subtree
    other = await item(d, await project(d, "Other"), "Elsewhere")
    assert refused(d, PERSON, "work_item.update", {"work_item_id": kid}, {"parent_id": other},
                   {"expected_version": 2}).code == "WRONG_PROJECT"
    assert refused(d, PERSON, "work_item.update", {"work_item_id": parent}, {"parent_id": kid},
                   {"expected_version": 2}).code == "CYCLE"


# --------------------------------------------------------------------------- completion (completion.js)
async def test_an_agents_done_is_a_claim_that_a_person_approves_for_the_content_they_read(daemon):
    d = daemon
    pid = await project(d)
    wid = await item(d, pid, "Ship it", who=AGENT, goal="g", acceptance="tests pass", steps=["write", "test"])
    assert refused(d, AGENT, "work_item.update", {"work_item_id": wid}, {"state": "done"},
                   {"expected_version": 1}).code == "STEPS_OPEN"
    await act(d, AGENT, "work_item.update", {"work_item_id": wid},
              {"steps": [{"text": "write", "done": True}, {"text": "test", "done": True}], "state": "done"},
              {"expected_version": 1})
    c = get(d, wid)["completion"]
    assert c["display_state"] == "awaiting_approval" and c["pending"] and c["claimed_by"] == "hermes"
    assert work_items.work_items_list(d.journal.db, pending=True)["work_items"][0]["work_item_id"] == wid
    # the agent cannot sign off its own claim
    assert refused(d, AGENT, "work_item.approve", {"work_item_id": wid}, {},
                   {"expected_fingerprint": c["fingerprint"]}).code == "FORBIDDEN"
    # a person approves what they read; a stale read is refused
    assert refused(d, PERSON, "work_item.approve", {"work_item_id": wid}, {},
                   {"expected_fingerprint": "0" * 64}).code == "CONTENT_CHANGED"
    await act(d, PERSON, "work_item.approve", {"work_item_id": wid}, {}, {"expected_fingerprint": c["fingerprint"]})
    c = get(d, wid)["completion"]
    assert c["display_state"] == "done" and c["approved"] and not c["pending"] and c["approved_by"] == "ted-dashboard"
    assert c["claimed_by"] == "hermes"
    # a rename keeps the approval; a content change asks again
    v = get(d, wid)["version"]
    await act(d, AGENT, "work_item.update", {"work_item_id": wid}, {"title": "Ship it now"}, {"expected_version": v})
    assert get(d, wid)["completion"]["approved"]
    await act(d, AGENT, "work_item.update", {"work_item_id": wid}, {"acceptance": "tests and docs"},
              {"expected_version": v + 1})
    c = get(d, wid)["completion"]
    assert c["display_state"] == "awaiting_approval" and c["pending"] and not c["approved"]
    # "keep working" sends it back
    await act(d, PERSON, "work_item.continue", {"work_item_id": wid}, {"note": "docs missing"},
              {"expected_fingerprint": c["fingerprint"]})
    w = get(d, wid)
    assert w["state"] == "doing" and not w["completion"]["pending"]
    assert refused(d, PERSON, "work_item.continue", {"work_item_id": wid}, {},
                   {"expected_fingerprint": w["completion"]["fingerprint"]}).code == "NOTHING_TO_DECIDE"
    kinds = [e["kind"] for e in work_items.work_item_get(d.journal.db, wid)["events"]]
    assert {"work_item.approved", "work_item.continued", "work_item.state"} <= set(kinds)


async def test_checked_steps_ask_for_a_decision_and_keep_working_holds_until_the_steps_change(daemon):
    d = daemon
    pid = await project(d)
    wid = await item(d, pid, "Steps", who=AGENT, steps=["one"])
    await act(d, AGENT, "work_item.update", {"work_item_id": wid}, {"steps": [{"text": "one", "done": True}]},
              {"expected_version": 1})
    c = get(d, wid)["completion"]
    assert c["pending"] and c["display_state"] == "todo"
    await act(d, PERSON, "work_item.continue", {"work_item_id": wid}, {}, {"expected_fingerprint": c["fingerprint"]})
    assert not get(d, wid)["completion"]["pending"]
    # new work, all checked again: it asks again
    await act(d, AGENT, "work_item.update", {"work_item_id": wid},
              {"steps": [{"text": "one", "done": True}, {"text": "two", "done": True}]}, {"expected_version": 3})
    assert get(d, wid)["completion"]["pending"]
    # a person marks it done directly (approve from any state)
    c = get(d, wid)["completion"]
    await act(d, PERSON, "work_item.approve", {"work_item_id": wid}, {}, {"expected_fingerprint": c["fingerprint"]})
    w = get(d, wid)
    assert w["state"] == "done" and w["completion"]["approved"] and w["completion"]["claimed_by"] == "ted-dashboard"
    # approving again is a no-op; unchecking a step reopens it and drops the approval
    again = await act(d, PERSON, "work_item.approve", {"work_item_id": wid}, {},
                      {"expected_fingerprint": w["completion"]["fingerprint"]})
    assert again["result"]["changed"] is False
    await act(d, AGENT, "work_item.update", {"work_item_id": wid},
              {"steps": [{"text": "one", "done": True}, {"text": "two", "done": False}]},
              {"expected_version": w["version"]})
    w = get(d, wid)
    assert w["state"] == "doing" and not w["completion"]["approved"] and w["approved_by"] is None


# --------------------------------------------------------------------------- links, archive, records
async def test_links_point_at_known_resources_and_removal_keeps_history(daemon):
    d = daemon
    pid = await project(d)
    wid = await item(d, pid, "Linked")
    other_op = await act(d, PERSON, "project.create", params={"name": "Other"})
    for kind, ref in (("checkpoint", "cp_" + "0" * 32), ("operation", "op_" + "0" * 32), ("task", "deadbeef"),
                      ("session", "h1/never-seen"), ("session", "nohost/x")):
        assert refused(d, PERSON, "work_item.link", {"work_item_id": wid}, {"kind": kind, "ref": ref}).code in {
            "LINK_TARGET_NOT_FOUND", "INVALID_PARAMS"}
    assert refused(d, PERSON, "work_item.link", {"work_item_id": wid},
                   {"kind": "pull_request", "ref": "o/r#x"}).code == "INVALID_PARAMS"
    task = d.journal.submit(project="p", host="h1", workspace="w", original_words="do", idempotency_key="t1")
    d.journal.db.execute("""INSERT INTO sessions_observed(host,session_id,body,digest,provenance,api_access,
        first_seen_at,last_seen_at) VALUES('h1','s1',?,'d','manual','read_only',1,1)""", (json.dumps({"title": "T"}),))
    links = [("operation", other_op["operation_id"]), ("task", task["task_id"]), ("session", "h1/s1"),
             ("pull_request", "o/r#12")]
    for kind, ref in links:
        await act(d, PERSON, "work_item.link", {"work_item_id": wid}, {"kind": kind, "ref": ref, "note": "why"})
    dup = await act(d, PERSON, "work_item.link", {"work_item_id": wid}, {"kind": "pull_request", "ref": "o/r#12"})
    assert dup["result"]["already"] is True
    got = work_items.work_item_get(d.journal.db, wid)
    assert [(x["kind"], x["ref"]) for x in got["links"]] == links
    targets = {x["kind"]: x["target"] for x in got["links"]}
    assert targets["operation"]["action"] == "project.create" and targets["session"]["title"] == "T"
    assert targets["pull_request"] == {"found": True, "repository": "o/r", "number": 12}
    assert work_items.work_items_for(d.journal.db, "session", "h1/s1")[0]["work_item_id"] == wid
    await act(d, AGENT, "work_item.link", {"work_item_id": wid}, {"kind": "session", "ref": "h1/s1", "remove": True})
    assert refused(d, AGENT, "work_item.link", {"work_item_id": wid},
                   {"kind": "session", "ref": "h1/s1", "remove": True}).code == "NOT_LINKED"
    got = work_items.work_item_get(d.journal.db, wid)
    assert ("session", "h1/s1") not in [(x["kind"], x["ref"]) for x in got["links"]]
    assert got["removed_links"][0]["removed_by"] == "hermes"
    await act(d, PERSON, "work_item.link", {"work_item_id": wid}, {"kind": "session", "ref": "h1/s1"})
    assert work_items.work_items_for(d.journal.db, "session", "h1/s1")


async def test_archive_takes_the_subtree_and_restore_brings_back_only_what_it_took(daemon):
    d = daemon
    pid = await project(d)
    top = await item(d, pid, "Top")
    mid = await item(d, pid, "Mid", parent_id=top)
    leaf = await item(d, pid, "Leaf", parent_id=mid)
    earlier = await item(d, pid, "Earlier", parent_id=mid)
    await act(d, PERSON, "work_item.update", {"work_item_id": earlier}, {"archived": True}, {"expected_version": 1})
    op = await act(d, PERSON, "work_item.update", {"work_item_id": top}, {"archived": True}, {"expected_version": 1})
    assert set(op["result"]["work_item_ids"]) == {top, mid, leaf}
    assert work_items.project_get(d.journal.db, pid)["work_items"] == []
    assert refused(d, PERSON, "work_item.update", {"work_item_id": mid}, {"archived": False},
                   {"expected_version": 2}).code == "PARENT_ARCHIVED"
    assert refused(d, PERSON, "work_item.update", {"work_item_id": leaf}, {"title": "x"},
                   {"expected_version": 2}).code == "WORK_ITEM_ARCHIVED"
    await act(d, PERSON, "work_item.update", {"work_item_id": top}, {"archived": False}, {"expected_version": 2})
    tree = work_items.project_get(d.journal.db, pid)["work_items"]
    assert ids(tree) == [top] and ids(tree[0]["children"]) == [mid] and ids(tree[0]["children"][0]["children"]) == [leaf]
    assert get(d, earlier)["archived"]
    archived = work_items.project_get(d.journal.db, pid, include_archived=True)["archived"]
    assert [x["work_item_id"] for x in archived] == [earlier]


async def test_a_change_is_applied_once_even_if_the_operation_runs_again(daemon):
    d = daemon
    pid = await project(d)
    op = await act(d, PERSON, "work_item.create", {"project_id": pid}, {"title": "Once"}, key="same")
    # the daemon stopped after the change committed but before the operation recorded its result
    d.journal.db.execute("UPDATE operations SET status='running',result=NULL WHERE operation_id=?",
                         (op["operation_id"],))
    await d.ops.drain()
    again = d.ops.get(op["operation_id"])
    assert again["status"] == "succeeded" and again["result"] == op["result"]
    assert d.journal.db.execute("SELECT COUNT(*) FROM work_items").fetchone()[0] == 1
    # the same key returns the same operation; the same key with other content is refused
    replay, created = d.ops.create(PERSON, action="work_item.create", target={"project_id": pid},
                                   params={"title": "Once"}, idempotency_key="same")
    assert not created and replay["operation_id"] == op["operation_id"]
    with pytest.raises(OperationError) as e:
        d.ops.create(PERSON, action="work_item.create", target={"project_id": pid}, params={"title": "Twice"},
                     idempotency_key="same")
    assert e.value.code == "IDEMPOTENCY_CONFLICT"
    events = d.journal.api_events(0, 100, resource_type="work_item")["events"]
    assert [e["kind"] for e in events] == ["work_item.created"]
    assert events[0]["actor"] == "ted-dashboard" and events[0]["body"]["operation_id"] == op["operation_id"]


async def test_scopes_manage_for_changes_and_observe_for_reads(daemon):
    d = daemon
    assert refused(d, VIEWER, "project.create", params={"name": "No"}).code == "FORBIDDEN"
    assert "approve" in api_auth.SCOPES
    pid = await project(d)
    assert refused(d, VIEWER, "work_item.create", {"project_id": pid}, {"title": "No"}).code == "FORBIDDEN"
    actions = {a.name: a.scope for a in work_items.ACTIONS}
    assert actions["work_item.approve"] == "approve"
    assert {s for n, s in actions.items() if n != "work_item.approve"} == {"manage"}


async def test_http_reads_and_one_operation_path(served):
    d, port = served
    person = token(d, "ted-dashboard", "observe", "manage", "approve")
    viewer = token(d, "viewer", "observe")
    status, out = await http(port, "POST", "/api/v1/operations?wait=5", tok=person,
                             body={"action": "project.create", "params": {"name": "Web"}},
                             headers={"Idempotency-Key": "p1"})
    assert status == 202 and out["operation"]["status"] == "succeeded"
    pid = out["operation"]["result"]["project_id"]
    status, out = await http(port, "POST", "/api/v1/operations?wait=5", tok=viewer,
                             body={"action": "work_item.create", "target": {"project_id": pid},
                                   "params": {"title": "No"}}, headers={"Idempotency-Key": "w0"})
    assert status == 403
    status, out = await http(port, "POST", "/api/v1/operations?wait=5", tok=person,
                             body={"action": "work_item.create", "target": {"project_id": pid},
                                   "params": {"title": "Item", "steps": ["a"]}}, headers={"Idempotency-Key": "w1"})
    wid = out["operation"]["result"]["work_item_id"]
    status, out = await http(port, "GET", "/api/v1/projects", tok=viewer)
    assert status == 200 and out["projects"][0]["counts"]["todo"] == 1
    status, out = await http(port, "GET", f"/api/v1/projects/{pid}", tok=viewer)
    assert status == 200 and out["work_items"][0]["work_item_id"] == wid
    status, out = await http(port, "GET", f"/api/v1/work-items/{wid}", tok=viewer)
    assert status == 200 and out["work_item"]["completion"]["display_state"] == "todo"
    status, out = await http(port, "GET", "/api/v1/work-items?pending=true", tok=viewer)
    assert status == 200 and out["work_items"] == []
    status, out = await http(port, "GET", "/api/v1/work-items/wi_" + "0" * 20, tok=viewer)
    assert status == 404 and out["error"]["code"] == "WORK_ITEM_NOT_FOUND"
    status, out = await http(port, "GET", "/api/v1/capabilities", tok=viewer)
    assert out["features"]["work_items"] is True
    assert {a["action"] for a in out["actions"]} >= {"work_item.approve", "project.create"}


def test_cli_reads_the_version_and_fingerprint_it_changes_against(monkeypatch, capsys):
    from bat_agent_connector import cli, task_daemon

    item = {"work_item_id": "wi_" + "1" * 20, "version": 7, "steps": [{"text": "a", "done": False}, {"text": "b", "done": False}],
            "completion": {"fingerprint": "f" * 64}}
    calls = []

    def request(method, **params):
        calls.append((method, params))
        return {"work_item": item} if method == "work_item_get" else {"operation": {"status": "succeeded"}}

    monkeypatch.setattr(task_daemon, "request", request)
    assert cli.main(["item", "update", item["work_item_id"], "--check", "2", "--state", "doing"]) == 0
    method, sent = calls[-1]
    assert method == "op_submit" and sent["action"] == "work_item.update"
    assert sent["preconditions"] == {"expected_version": 7}
    assert sent["params"] == {"state": "doing", "steps": [{"text": "a", "done": False}, {"text": "b", "done": True}]}
    assert cli.main(["item", "approve", item["work_item_id"]]) == 0
    assert calls[-1][1]["preconditions"] == {"expected_fingerprint": "f" * 64}
    assert cli.main(["item", "update", item["work_item_id"], "--check", "3"]) == 1  # no step 3: nothing sent
    assert calls[-1][0] == "work_item_get"
    assert cli.main(["item", "link", item["work_item_id"], "pull_request", "o/r#5", "--remove"]) == 0
    assert calls[-1][1]["params"] == {"kind": "pull_request", "ref": "o/r#5", "remove": True}
    capsys.readouterr()
