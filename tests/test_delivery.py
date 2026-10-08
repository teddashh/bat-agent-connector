"""GitHub delivery operations against a fake GitHub (plan acceptance C04-C07, D01-D04)."""

from __future__ import annotations

import asyncio
import json

import pytest

from bat_agent_connector import api_auth
from bat_agent_connector.config import parse_config
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.fakegithub import TOKEN, FakeGitHub

HEAD = "a" * 40
MERGED = "9" * 40
TED = api_auth.Principal("ted-dashboard", frozenset({"observe", "merge", "deploy"}))


@pytest.fixture
def gh():
    fake = FakeGitHub()
    fake.start()
    yield fake
    fake.stop()


def config(mock, gh, *, mode="workflow_dispatch"):
    host = {"url": mock.url, "fingerprint": mock.fingerprint, "token_ref": "env:BATC_TEST_TOKEN"}
    return parse_config({
        "hosts": {"h1": host},
        "github": {"token_ref": "env:FAKE_GH_TOKEN", "api_url": gh.url, "wait_max_s": 600,
                   "repos": [{"repository": "o/r", "merge_methods": ["squash", "merge"]}]},
        "deploy": {"recipes": [
            {"name": "prod", "repository": "o/r", "environment": "production", "mode": mode,
             "workflow": "deploy.yml", "deploy_job": "deploy", "ref": "main",
             "inputs": {"source_sha": "source_sha", "operation_id": "operation_id"},
             "run_name_contains": "operation_id"}]},
    })


@pytest.fixture
def make_daemon(mock, gh, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_GH_TOKEN", TOKEN)
    made = []

    def make(**kw):
        d = TaskDaemon(config(mock, gh, **kw), tmp_path / f"tasks{len(made)}.db")
        made.append(d)
        return d

    yield make
    for d in made:
        d.journal.close()


def merge_op(d, key="m1", sha=HEAD, number=7, principal=TED, action="github.pr.merge", **target):
    return d.ops.create(principal, action=action, target={"repository": "o/r", "pull_number": number, **target},
                        params={"method": "squash"}, preconditions={"expected_head_sha": sha},
                        idempotency_key=key)


async def settle(d, op_id, rounds=10):
    """Run the operation, fast-forwarding its scheduled waits, until it stops changing."""
    for _ in range(rounds):
        d.journal.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op_id,))
        await d.ops.drain()
        op = d.ops.get(op_id)
        if op["status"] in {"succeeded", "failed", "cancelled", "needs_attention"}:
            return op
    return d.ops.get(op_id)


# --------------------------------------------------------------------------- merge
async def test_merge_records_the_real_merged_sha(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = merge_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    assert done["result"]["merged_sha"] == MERGED and done["result"]["via"] == "direct"
    put = [b for m, p, b in gh.requests if m == "PUT"]
    assert put == [{"sha": HEAD, "merge_method": "squash", "merge_action": "default"}]
    assert done["external_refs"]["merge_request_uuid"]
    assert TOKEN not in json.dumps(done)


async def test_moved_head_is_refused_before_any_merge_request(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, "e" * 40)
    op, _ = merge_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "failed" and done["error_code"] == "TARGET_HEAD_CHANGED"
    assert gh.count("PUT", "merge-async") == 0


async def test_merge_queue_waits_until_github_shows_the_merge(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    op, _ = merge_op(d)
    waiting = await settle(d, op["operation_id"], rounds=2)
    assert waiting["status"] == "waiting_external" and "merge queue" in waiting["status_reason"]
    assert waiting["external_refs"]["merge_queue"] is True
    gh.merge(7)  # the queue merges it later
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["via"] == "merge_queue"
    assert gh.count("PUT", "merge-async") == 1  # enqueued is never re-submitted


async def test_existing_merge_request_is_adopted_only_when_it_matches(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "conflict_409_same"
    op, _ = merge_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded"
    gh.add_pr(8, HEAD)
    gh.merge_mode = "conflict_409_other"
    op, _ = merge_op(d, key="m2", number=8)
    other = await settle(d, op["operation_id"])
    assert other["status"] == "needs_attention" and other["error_code"] == "EXISTING_MERGE_REQUEST"
    assert gh.pulls[8]["merged"] is False


async def test_lost_merge_reply_is_read_back_not_blindly_resent(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "fail_500_but_merged"  # GitHub merged it, the reply was lost
    op, _ = merge_op(d)
    first = await settle(d, op["operation_id"], rounds=1)
    assert first["status"] == "uncertain"
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["merged_sha"] == MERGED
    assert gh.count("PUT", "merge-async") == 1
    gh.add_pr(8, HEAD)
    gh.merge_mode = "fail_500"  # nothing happened: the read-back proves it, so asking again is safe
    op, _ = merge_op(d, key="m2", number=8)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and gh.count("PUT", "pulls/8/merge-async") == 2


async def test_pending_required_checks_wait_without_merging(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD, mergeable_state="blocked")
    gh.check_runs[HEAD] = [{"name": "ci", "status": "in_progress", "conclusion": None}]
    op, _ = merge_op(d)
    waiting = await settle(d, op["operation_id"], rounds=2)
    assert waiting["status"] == "waiting_checks" and gh.count("PUT", "merge-async") == 0
    gh.check_runs[HEAD] = [{"name": "ci", "status": "completed", "conclusion": "success"}]
    gh.result_status = "failed"  # rules are evaluated when the merge runs
    done = await settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "MERGE_FAILED"


async def test_merge_admission(make_daemon, gh, monkeypatch):
    d = make_daemon()
    for kwargs, code in (({"sha": "short"}, "PRECONDITION_REQUIRED"),
                         ({"principal": api_auth.Principal("bot", frozenset({"operate"}))}, "FORBIDDEN"),
                         ({"action": "delivery.merge_and_deploy", "recipe": "prod",
                           "principal": api_auth.Principal("bot", frozenset({"merge"}))}, "FORBIDDEN")):
        with pytest.raises(OperationError) as e:
            merge_op(d, **kwargs)
        assert e.value.code == code
    with pytest.raises(OperationError) as e:
        d.ops.create(TED, action="github.pr.merge", target={"repository": "x/y", "pull_number": 1},
                     preconditions={"expected_head_sha": HEAD}, idempotency_key="k")
    assert e.value.code == "REPO_NOT_CONFIGURED"
    monkeypatch.delenv("FAKE_GH_TOKEN")
    nogh = make_daemon()
    with pytest.raises(OperationError) as e:
        merge_op(nogh)
    assert e.value.status == 503


# --------------------------------------------------------------------------- deploy
def deploy_op(d, sha=MERGED, key="d1"):
    return d.ops.create(TED, action="deployment.start", target={"recipe": "prod"}, params={"source_sha": sha},
                        idempotency_key=key)


async def test_dispatch_deploy_succeeds_only_when_the_deploy_job_succeeds(make_daemon, gh):
    d = make_daemon()
    op, _ = deploy_op(d)
    waiting = await settle(d, op["operation_id"], rounds=2)
    assert waiting["status"] == "waiting_external"
    dispatched = [b for m, p, b in gh.requests if m == "POST"]
    assert dispatched == [{"ref": "main", "inputs": {"operation_id": op["operation_id"], "source_sha": MERGED}}]
    run_id = waiting["external_refs"]["deploy_run_id"]
    gh.runs[run_id].update(status="completed", conclusion="success")
    gh.jobs[run_id][1]["conclusion"] = "skipped"
    skipped = await settle(d, op["operation_id"])
    assert skipped["status"] == "failed" and skipped["error_code"] == "DEPLOY_NOT_RUN"
    op, _ = deploy_op(d, key="d2")
    await settle(d, op["operation_id"], rounds=2)
    run_id = d.ops.get(op["operation_id"])["external_refs"]["deploy_run_id"]
    gh.runs[run_id].update(status="completed", conclusion="success")
    gh.jobs[run_id][1]["conclusion"] = "success"
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["environment"] == "production"
    assert done["result"]["source_sha"] == MERGED and done["result"]["run_id"] == run_id


async def test_lost_dispatch_reply_is_matched_by_run_name_not_redispatched(make_daemon, gh):
    d = make_daemon()
    gh.dispatch_mode = "fail_500_but_started"
    op, _ = deploy_op(d)
    first = await settle(d, op["operation_id"], rounds=1)
    assert first["status"] == "uncertain"
    found = await settle(d, op["operation_id"], rounds=2)
    assert found["status"] == "waiting_external" and found["external_refs"]["deploy_run_id"]
    assert gh.count("POST", "dispatches") == 1


async def test_on_merge_recipe_tracks_the_existing_run_and_serializes_the_environment(make_daemon, gh):
    d = make_daemon(mode="on_merge")
    op, _ = deploy_op(d)
    waiting = await settle(d, op["operation_id"], rounds=2)
    assert waiting["status"] == "waiting_external" and "start" in waiting["status_reason"]
    with pytest.raises(OperationError) as e:
        deploy_op(d, key="d2")  # one deploy per environment at a time
    assert e.value.status == 409
    gh.add_run(head_sha=MERGED, event="push", status="completed", conclusion="success", job_conclusion="success")
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and gh.count("POST", "dispatches") == 0


async def test_merge_and_deploy_keeps_the_merge_when_the_deploy_fails(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = merge_op(d, action="delivery.merge_and_deploy", recipe="prod")
    waiting = await settle(d, op["operation_id"], rounds=3)
    assert waiting["status"] == "waiting_external" and waiting["external_refs"]["merged_sha"] == MERGED
    run_id = waiting["external_refs"]["deploy_run_id"]
    assert [b for m, p, b in gh.requests if m == "POST"][0]["inputs"]["source_sha"] == MERGED
    gh.runs[run_id].update(status="completed", conclusion="failure")
    failed = await settle(d, op["operation_id"])
    assert failed["status"] == "failed" and failed["error_code"] == "DEPLOY_FAILED"
    # Retry deploys the same merged version; nothing is merged again.
    retry, _ = deploy_op(d, sha=failed["external_refs"]["merged_sha"], key="retry")
    await settle(d, retry["operation_id"], rounds=2)
    rid = d.ops.get(retry["operation_id"])["external_refs"]["deploy_run_id"]
    gh.runs[rid].update(status="completed", conclusion="success")
    gh.jobs[rid][1]["conclusion"] = "success"
    assert (await settle(d, retry["operation_id"]))["status"] == "succeeded"
    assert gh.count("PUT", "merge-async") == 1


# --------------------------------------------------------------------------- GitHub answers that are not outcomes
async def test_token_is_read_per_request_and_a_refused_read_after_the_merge_request_waits(make_daemon, gh,
                                                                                          monkeypatch):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    op, _ = merge_op(d)
    assert (await settle(d, op["operation_id"], rounds=2))["status"] == "waiting_external"
    gh.token = "rotated-token-1"
    monkeypatch.setenv("FAKE_GH_TOKEN", gh.token)  # a refresher rewrote the token; the daemon did not restart
    assert (await settle(d, op["operation_id"], rounds=2))["status"] == "waiting_external"
    gh.token = "rotated-token-2"  # this time nothing refreshed the connector's copy
    held = await settle(d, op["operation_id"])
    assert held["status"] == "needs_attention" and held["error_code"] == "GITHUB_401", held
    monkeypatch.setenv("FAKE_GH_TOKEN", gh.token)
    gh.merge(7)  # the queue merged it meanwhile
    d.ops.resume(TED, op["operation_id"])
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["via"] == "merge_queue"
    assert gh.count("PUT", "merge-async") == 1


async def test_a_token_missing_mid_rotation_still_sends_the_dispatch_with_the_last_good_one(make_daemon, gh,
                                                                                            monkeypatch):
    d = make_daemon()
    monkeypatch.delenv("FAKE_GH_TOKEN")  # the refresher is rewriting it
    op, _ = deploy_op(d)
    sent = await settle(d, op["operation_id"], rounds=1)
    assert sent["status"] == "waiting_external" and sent["external_refs"]["deploy_run_id"], sent
    assert gh.count("POST", "dispatches") == 1


async def test_a_refused_read_before_any_write_still_fails_fast(make_daemon, gh):
    d = make_daemon()
    op, _ = merge_op(d, number=8)  # no such PR
    done = await settle(d, op["operation_id"])
    assert done["status"] == "failed" and done["error_code"] == "GITHUB_404"
    assert gh.count("PUT", "merge-async") == 0


async def test_a_rate_limited_poll_keeps_the_deploy_running_and_the_environment_locked(make_daemon, gh):
    d = make_daemon()
    op, _ = deploy_op(d)
    run_id = (await settle(d, op["operation_id"], rounds=2))["external_refs"]["deploy_run_id"]
    gh.script.append(("GET", rf"/actions/runs/{run_id}$", 403, {"x-ratelimit-remaining": "0"},
                      {"message": "API rate limit exceeded for installation"}))
    limited = await settle(d, op["operation_id"], rounds=1)
    assert limited["status"] == "waiting_external" and "did not answer" in limited["status_reason"], limited
    with pytest.raises(OperationError) as e:
        deploy_op(d, key="d2")
    assert e.value.code == "DEPLOY_IN_PROGRESS"
    gh.runs[run_id].update(status="completed", conclusion="success")
    gh.jobs[run_id][1]["conclusion"] = "success"
    assert (await settle(d, op["operation_id"]))["status"] == "succeeded"


async def test_an_unanswered_run_lookup_after_a_204_dispatch_keeps_looking(make_daemon, gh):
    d = make_daemon()
    gh.dispatch_mode = "no_content"
    gh.script.append(("GET", r"/workflows/deploy\.yml/runs$", 502, {}, {"message": "Bad Gateway"}))
    op, _ = deploy_op(d)
    first = await settle(d, op["operation_id"], rounds=1)
    assert first["status"] == "waiting_external", first
    found = await settle(d, op["operation_id"], rounds=1)
    assert found["status"] == "waiting_external" and found["external_refs"]["deploy_run_id"]
    assert gh.count("POST", "dispatches") == 1


async def test_a_dispatch_reply_cut_short_is_read_back_not_failed(make_daemon, gh):
    d = make_daemon()
    gh.truncate.append(("POST", r"/dispatches$"))
    op, _ = deploy_op(d)
    first = await settle(d, op["operation_id"], rounds=1)
    assert first["status"] == "uncertain", first
    found = await settle(d, op["operation_id"], rounds=2)
    assert found["status"] == "waiting_external" and found["external_refs"]["deploy_run_id"]
    assert gh.count("POST", "dispatches") == 1


async def test_pr_preview_route(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.check_runs[HEAD] = [{"name": "ci", "status": "completed", "conclusion": "success"},
                           {"name": "lint", "status": "queued", "conclusion": None}]
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    with d.journal.tx():
        viewer = api_auth.issue(d.journal.db, "viewer", ["observe"])
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write((f"GET /api/v1/repositories/o/r/pulls/7 HTTP/1.1\r\nHost: localhost\r\n"
                  f"Authorization: Bearer {viewer}\r\n\r\n").encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    body = json.loads(raw.split(b"\r\n\r\n", 1)[1])
    pr = body["pull_request"]
    assert pr["head_sha"] == HEAD and pr["checks"] == {"total": 2, "pending": 1, "failed": 0}
    assert pr["recipes"] == [{"name": "prod", "environment": "production", "mode": "workflow_dispatch"}]
    server.close()
    await server.wait_closed()
