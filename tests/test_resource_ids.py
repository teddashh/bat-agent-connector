"""B01, 計畫 §08: observation and cleanup share the same registry creation intent."""

import pytest

from bat_agent_connector.resource_ids import registry_worktree_intent


@pytest.mark.parametrize("case", ["failover", "reviewer", "reviewer_lookup", "warm_reuse", "out_of_order", "missing_parent"])
def test_registry_worktree_intent_creation_root(case):
    root = {"host": "h1", "session_id": "root", "created_at": "123.4560", "worktree_path": "/srv/wt"}
    middle = {"host": "h1", "session_id": "middle", "created_at": 124, "worktree_path": "/srv/wt", "failover_of": "root"}
    successor = {"host": "h1", "session_id": "successor", "created_at": 125, "worktree_path": "/srv/wt", "failover_of": "middle"}
    entries, sid, lead_of = [root, middle, successor], "successor", None
    if case == "reviewer":
        successor = {**successor, "failover_of": None, "role": "reviewer", "lead_session_id": "root"}
        entries = [root, successor]
    elif case == "reviewer_lookup":
        successor = {**successor, "failover_of": None, "role": "reviewer", "task_id": "task"}
        entries = [root, successor]
        def lead_of(task_id):
            return "root" if task_id == "task" else None
    elif case == "warm_reuse":
        root.update(task_id="new-task", warm_from_task_id="old-task")
        successor = {**successor, "failover_of": None, "shared_worktree_from": "root"}
        entries = [root, successor]
        assert registry_worktree_intent(entries, "h1", "root") == ("registry", "root@123.4560")
    elif case == "out_of_order":
        entries = [successor, middle, root]
    elif case == "missing_parent":
        root["failover_of"] = "missing"
    before = [dict(e) for e in entries]
    assert registry_worktree_intent(entries, "h1", sid, lead_of) == ("registry", "root@123.4560")
    assert entries == before


def test_registry_worktree_intent_cycle_is_unknown():
    entries = [{"session_id": "a", "created_at": 1, "worktree_path": "/srv/wt", "failover_of": "b"},
               {"session_id": "b", "created_at": 2, "worktree_path": "/srv/wt", "shared_worktree_from": "a"}]
    assert registry_worktree_intent(entries, "h1", "a") is None
    assert registry_worktree_intent(list(reversed(entries)), "h1", "b") is None


@pytest.mark.parametrize("fields", [{"worktree_made_by": "connector"}, {"checkpoint_id": "cp"},
                                   {"integration_operation_id": "op"}, {"created_at": None}, {"worktree_path": None}])
def test_registry_worktree_intent_excludes_other_creation_slots(fields):
    root = {"session_id": "root", "created_at": 0, "worktree_path": "/srv/wt", **fields}
    successor = {"session_id": "successor", "created_at": 1, "worktree_path": "/srv/wt", "failover_of": "root"}
    assert registry_worktree_intent([successor, root], "h1", "successor") is None


def test_registry_worktree_intent_keeps_hosts_and_loaded_number_format():
    entries = [{"host": "h2", "session_id": "root", "created_at": 1, "worktree_path": "/srv/wt"},
               {"host": "h1", "session_id": "root", "created_at": 2.0, "worktree_path": "/srv/wt"}]
    assert registry_worktree_intent(entries, "h1", "root") == ("registry", "root@2.0")
    assert registry_worktree_intent(entries, "h2", "root") == ("registry", "root@1")
    assert registry_worktree_intent(entries, "h1", "missing") is None
