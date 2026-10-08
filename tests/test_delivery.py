"""GitHub delivery operations against a fake GitHub (plan acceptance C04-C07, D01-D04)."""

from __future__ import annotations

import asyncio
import json

import pytest

from bat_agent_connector import api_auth, delivery, pr_delivery
from bat_agent_connector.config import parse_config
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.fakegithub import TOKEN, FakeGitHub

HEAD = "a" * 40
MERGED = "9" * 40
TED = api_auth.Principal("ted-dashboard", frozenset({"observe", "merge", "deploy", "integrate"}))


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
                   "repos": [{"repository": "o/r", "merge_methods": ["squash", "merge", "rebase"], "allow_pr_update": True}]},
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


async def merge_op(d, key="m1", sha=HEAD, number=7, principal=TED, action="github.pr.merge", **target):
    if (len(sha) != 40 or not principal.allows("merge") or not d.ops.context.get("github")
            or (action == "delivery.merge_and_deploy" and not principal.allows("deploy"))):
        return d.ops.create(principal, action=action, target={"repository": "o/r", "pull_number": number, **target},
                            params={"method": "squash"}, preconditions={"expected_head_sha": sha}, idempotency_key=key)
    preview = (await delivery.pr_preview(d.ops, "o/r", number))["merge_preview"]
    envelope = pr_delivery.merge_envelope(preview, recipe=target.get("recipe"))
    envelope["action"] = action
    envelope["target"].update(target)
    return d.ops.create(principal, **envelope, idempotency_key=key)


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
    op, _ = await merge_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    assert done["result"]["merged_sha"] == MERGED and done["result"]["via"] == "direct"
    put = [b for m, p, b in gh.requests if m == "PUT"]
    assert put == [{"sha": HEAD, "merge_method": "squash", "merge_action": "default"}]
    assert done["external_refs"]["merge_request_uuid"]
    assert TOKEN not in json.dumps(done)


async def test_moved_head_is_refused_before_any_merge_request(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op, _ = await merge_op(d)
    gh.pulls[7]["head"]["sha"] = "e" * 40
    done = await settle(d, op["operation_id"])
    assert done["status"] == "failed" and done["error_code"] == "TARGET_HEAD_CHANGED"
    assert gh.count("PUT", "merge-async") == 0


async def test_merge_queue_waits_until_github_shows_the_merge(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    op, _ = await merge_op(d)
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
    op, _ = await merge_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded"
    gh.add_pr(8, HEAD)
    gh.merge_mode = "conflict_409_other"
    op, _ = await merge_op(d, key="m2", number=8)
    other = await settle(d, op["operation_id"])
    assert other["status"] == "needs_attention" and other["error_code"] == "EXISTING_MERGE_REQUEST"
    assert gh.pulls[8]["merged"] is False


async def test_lost_merge_reply_is_read_back_not_blindly_resent(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "fail_500_but_merged"  # GitHub merged it, the reply was lost
    op, _ = await merge_op(d)
    first = await settle(d, op["operation_id"], rounds=1)
    assert first["status"] == "uncertain"
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["merged_sha"] == MERGED
    assert gh.count("PUT", "merge-async") == 1
    gh.add_pr(8, HEAD)
    gh.merge_mode = "fail_500"  # nothing happened: the read-back proves it, so asking again is safe
    op, _ = await merge_op(d, key="m2", number=8)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and gh.count("PUT", "pulls/8/merge-async") == 2


async def test_pending_required_checks_wait_without_merging(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD, mergeable_state="blocked")
    gh.check_runs[HEAD] = [{"name": "ci", "status": "in_progress", "conclusion": None}]
    op, _ = await merge_op(d)
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
            await merge_op(d, **kwargs)
        assert e.value.code == code
    with pytest.raises(OperationError) as e:
        d.ops.create(TED, action="github.pr.merge", target={"repository": "x/y", "pull_number": 1},
                     preconditions={"expected_head_sha": HEAD}, idempotency_key="k")
    assert e.value.code == "REPO_NOT_CONFIGURED"
    monkeypatch.delenv("FAKE_GH_TOKEN")
    nogh = make_daemon()
    with pytest.raises(OperationError) as e:
        await merge_op(nogh)
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
    op, _ = await merge_op(d, action="delivery.merge_and_deploy", recipe="prod")
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
    op, _ = await merge_op(d)
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
    gh.add_pr(8, HEAD)
    op, _ = await merge_op(d, number=8)
    gh.pulls.pop(8)  # reviewed preview was admitted; PR is no longer readable before the first write
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


async def preview_op(d, *, method="squash", key="preview-merge", action="github.pr.merge", recipe=None):
    doc = (await delivery.pr_preview(d.ops, "o/r", 7, method))["merge_preview"]
    envelope = pr_delivery.merge_envelope(doc, recipe=recipe)
    envelope["action"] = action
    return doc, d.ops.create(TED, **envelope, idempotency_key=key)[0]


async def test_c05_base_changed_before_submit_has_diff_and_zero_put(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    doc, op = await preview_op(d)
    gh.pulls[7]["base"]["sha"] = "c" * 40
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "TARGET_BASE_CHANGED" and done["status"] == "failed"
    assert done["external_refs"]["scope_difference"] == {
        "field": "base_sha", "reviewed": doc["target"]["base_sha"], "observed": "c" * 40}
    assert gh.count("PUT", "merge-async") == 0


@pytest.mark.parametrize("method", ["squash", "merge"])
async def test_c05_queue_newer_base_verifies_actual_merge(make_daemon, gh, method):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    doc, op = await preview_op(d, method=method)
    waiting = await settle(d, op["operation_id"], 2)
    assert waiting["status"] == "waiting_external"
    newer = "c" * 40
    gh.commits[newer] = {"sha": newer, "parents": [{"sha": "b" * 40}], "commit": {"message": "another PR"}}
    gh.branches["main"] = newer
    gh.merge(7)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    assert done["result"]["merged_sha"] == MERGED and done["result"]["verified"]
    assert done["result"]["merged_onto_base_sha"] == newer and done["result"]["base_moved"]
    assert done["result"]["other_commits_count"] == 1
    assert gh.count("PUT", "merge-async") == 1
    assert pr_delivery.get_preview(d.journal.db, doc["preview_id"]) == doc


async def test_c05_newer_base_combined_deploy_uses_actual_sha(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d, action="delivery.merge_and_deploy", recipe="prod")
    await settle(d, op["operation_id"], 1)
    gh.commits["c" * 40] = {"sha": "c" * 40, "parents": [{"sha": "b" * 40}], "commit": {}}
    gh.branches["main"] = "c" * 40
    gh.merge(7)
    waiting = await settle(d, op["operation_id"], 1)
    assert waiting["external_refs"]["merged_sha"] == MERGED
    payload = [b for m, _, b in gh.requests if m == "POST"]
    assert payload[0]["inputs"]["source_sha"] == MERGED
    assert gh.count("PUT", "merge-async") == 1


@pytest.mark.parametrize("native", [True, False])
async def test_c04_native_stack_and_branch_chain_are_listed_and_refused(make_daemon, gh, native):
    d = make_daemon()
    lower = gh.add_pr(6, "c" * 40, head_ref="lower")
    upper = gh.add_pr(7, HEAD)
    upper["base"].update(ref="lower", sha="c" * 40)
    gh.commits[HEAD]["parents"] = [{"sha": "c" * 40}]
    if native:
        gh.stacks[1] = {"number": 1, "pull_requests": [lower, upper]}
    doc, op = await preview_op(d)
    assert doc["affected_prs"][0]["number"] == 6
    assert doc["affected_prs"][0]["reason"] == ("native_stack" if native else "branch_chain")
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "STACKED_PR_UNSUPPORTED" and done["status"] == "needs_attention"
    assert gh.count("PUT", "merge-async") == 0


async def test_c04_indirect_merge_differs_by_method_and_shared_ancestor(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(6, "c" * 40)
    gh.add_pr(7, HEAD)
    gh.commits[HEAD]["parents"] = [{"sha": "c" * 40}]
    merge = (await delivery.pr_preview(d.ops, "o/r", 7, "merge"))["merge_preview"]
    squash = (await delivery.pr_preview(d.ops, "o/r", 7, "squash"))["merge_preview"]
    assert merge["blocking"][0]["code"] == "MERGE_SCOPE_EXPANDED"
    assert not squash["blocking"] and squash["affected_prs"][0]["would_merge"] is False
    gh.pulls[6]["head"]["sha"] = "b" * 40
    shared = (await delivery.pr_preview(d.ops, "o/r", 7, "merge"))["merge_preview"]
    assert not shared["affected_prs"] and not shared["blocking"]


async def test_c05_swept_downstack_fails_verification_and_never_dispatches(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(6, "c" * 40)
    gh.add_pr(7, HEAD)
    gh.commits[HEAD]["parents"] = [{"sha": "c" * 40}]
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d, action="delivery.merge_and_deploy", recipe="prod")
    await settle(d, op["operation_id"], 1)
    gh.merge(7)
    gh.pulls[6].update(merged=True, state="closed", merge_commit_sha=MERGED)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "MERGE_RESULT_SCOPE_CHANGED"
    assert done["external_refs"]["merged_sha"] == MERGED
    assert gh.count("POST", "dispatches") == 0 and gh.count("PUT", "merge-async") == 1


async def test_c04_complete_compare_pagination_over_250_commits(make_daemon, gh):
    d = make_daemon()
    last = "b" * 40
    for i in range(301):
        sha = f"{i + 1000:040x}"
        gh.commits[sha] = {"sha": sha, "parents": [{"sha": last}], "commit": {"message": str(i)}}
        last = sha
    gh.add_pr(7, last)
    doc = (await delivery.pr_preview(d.ops, "o/r", 7))["merge_preview"]
    assert len(doc["commits"]) == 301 and doc["commits"][-1]["sha"] == last
    assert not doc["blocking"]
    assert gh.count("GET", "compare/.*page=4") == 1


async def test_c04_old_merge_client_requires_saved_preview(make_daemon, gh):
    d = make_daemon()
    with pytest.raises(OperationError) as e:
        d.ops.create(TED, action="github.pr.merge", target={"repository": "o/r", "pull_number": 7},
                     preconditions={"expected_head_sha": HEAD}, idempotency_key="old")
    assert e.value.code == "PRECONDITION_REQUIRED" and "github_pr_preview" in e.value.message
    assert not gh.requests


async def update_op(d, *, params=None, key="metadata", principal=TED, expected=None):
    pr = (await delivery.pr_preview(d.ops, "o/r", 7))
    return d.ops.create(principal, action="github.pr.update", target={"repository": "o/r", "pull_number": 7},
                        params=params or {"title": "Reviewed title"}, idempotency_key=key,
                        preconditions={"expected_metadata_digest": expected or pr["metadata_digest"]})[0]


async def test_metadata_human_only_pr_preserves_body_and_clears_explicitly(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD, body="Human work\n\n[notes](https://example.com)\n")
    op = await update_op(d)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["verified"]
    assert gh.pulls[7]["body"].endswith("\n") and gh.pulls[7]["title"] == "Reviewed title"
    second = await update_op(d, params={"body": ""}, key="clear")
    assert (await settle(d, second["operation_id"]))["status"] == "succeeded"
    assert gh.pulls[7]["body"] == "" and gh.pulls[7]["title"] == "Reviewed title"
    assert [b for m, _, b in gh.requests if m == "PATCH"] == [{"title": "Reviewed title"}, {"body": ""}]
    assert not gh.count("PUT", ".") and not gh.count("POST", ".")
    assert "Human work" not in json.dumps(d.journal.api_events(0, 200))


async def test_metadata_stale_digest_and_last_read_race_send_zero_patch(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op = await update_op(d)
    gh.pulls[7]["body"] = "other person's edit"
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "PR_METADATA_CHANGED" and gh.count("PATCH", ".") == 0
    op = await update_op(d, key="second")
    reads = 0
    def race(method, path, body):
        nonlocal reads
        if method == "GET" and path.endswith("pulls/7"):
            reads += 1
            if reads == 2:
                gh.pulls[7]["title"] = "another edit before PATCH"
    gh.before_request = race
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "PR_METADATA_CHANGED" and gh.count("PATCH", ".") == 0


@pytest.mark.parametrize("lost", [False, True])
async def test_metadata_write_readback_conflict_never_overwrites(make_daemon, gh, lost):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op = await update_op(d)
    gh.patch_after = lambda pr: pr.update(body="concurrent editor")
    gh.patch_mode = "lost_after" if lost else "ok"
    done = await settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "PR_METADATA_CONFLICT"
    assert done["external_refs"]["metadata_difference"]["observed"]["body"] == "concurrent editor"
    assert gh.count("PATCH", ".") == 1
    d.ops.resume(TED, op["operation_id"])
    await settle(d, op["operation_id"])
    assert gh.count("PATCH", ".") == 1 and gh.pulls[7]["body"] == "concurrent editor"


async def test_metadata_lost_reply_restart_and_cancel_never_resend(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.patch_mode = "lost_after"
    op = await update_op(d)
    first = await settle(d, op["operation_id"], 1)
    assert first["status"] == "uncertain"
    # A new service on the same journal really replays saved step intent.
    from bat_agent_connector.operations import OperationService
    fresh = OperationService(d.journal, actions=delivery.ACTIONS)
    fresh.context.update(d.ops.context)
    d.ops = fresh
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["observed_intent"]
    assert gh.count("PATCH", ".") == 1
    gh.patch_mode = "lost_before"
    op = await update_op(d, params={"body": "late patch"}, key="late")
    assert (await settle(d, op["operation_id"], 2))["status"] == "uncertain"
    d.ops.cancel(TED, op["operation_id"])
    with pytest.raises(OperationError) as e:
        await update_op(d, key="cannot-overtake")
    assert e.value.code == "PR_UPDATE_IN_PROGRESS"
    await pr_delivery.reconcile_metadata(d.ops)
    assert gh.count("PATCH", ".") == 2  # before is not proof of no side effect
    gh.pulls[7]["body"] = "late patch"  # positive readback of the cancelled request
    await pr_delivery.reconcile_metadata(d.ops)
    assert d.ops.get(op["operation_id"])["external_refs"]["observed_intent"]
    assert (await settle(d, op["operation_id"]))["status"] == "cancelled"
    assert (await update_op(d, key="after-proof"))["status"] == "accepted"


async def test_c07_metadata_integrate_scope_opt_in_and_fields(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    for principal in [api_auth.Principal("observer", frozenset({"observe"})),
                      api_auth.Principal("merger", frozenset({"merge"}))]:
        with pytest.raises(OperationError) as e:
            await update_op(d, principal=principal)
        assert e.value.code == "FORBIDDEN"
    for params in [{"title": ""}, {"body": None}, {"links": []}, {"base": "other"}]:
        with pytest.raises(OperationError) as e:
            await update_op(d, params=params)
        assert e.value.code == "INVALID_PARAMS"
    from dataclasses import replace
    cfg = d.ops.context["github_config"]
    cfg.repos["o/r"] = replace(cfg.repos["o/r"], allow_pr_update=False)
    with pytest.raises(OperationError) as e:
        await update_op(d)
    assert e.value.code == "PR_UPDATE_DISABLED" and gh.count("PATCH", ".") == 0


async def test_c04_expired_request_uuid_reads_pr_without_resubmit(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.result_status = "pending"
    _, op = await preview_op(d)
    assert (await settle(d, op["operation_id"], 1))["status"] == "waiting_external"
    gh.merge_requests.clear()
    assert (await settle(d, op["operation_id"], 1))["status"] == "waiting_external"
    gh.merge(7)
    assert (await settle(d, op["operation_id"]))["status"] == "succeeded"
    assert gh.count("PUT", "merge-async") == 1


async def test_c05_merge_restart_preserves_actual_sha_without_attribution(make_daemon, gh):
    from bat_agent_connector.operations import OperationService
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "fail_500_but_merged"
    _, op = await preview_op(d)
    assert (await settle(d, op["operation_id"], 1))["status"] == "uncertain"
    fresh = OperationService(d.journal, actions=delivery.ACTIONS)
    fresh.context.update(d.ops.context)
    d.ops = fresh
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["merged_sha"] == MERGED
    assert done["result"]["merged_by_this_operation"] is False
    assert all(s["status"] == "succeeded" for s in done["steps"])
    assert gh.count("PUT", "merge-async") == 1


async def test_c04_native_bottom_lists_upper_rebase_and_refuses(make_daemon, gh):
    d = make_daemon()
    lower = gh.add_pr(7, HEAD)
    upper = gh.add_pr(8, "c" * 40)
    upper["base"].update(ref=lower["head"]["ref"], sha=HEAD)
    gh.stacks[1] = {"number": 1, "pull_requests": [lower, upper]}
    doc, op = await preview_op(d)
    assert doc["affected_prs"][0]["effect"] == "branch_rebase"
    assert doc["affected_prs"][0]["would_merge"] is False
    assert (await settle(d, op["operation_id"]))["error_code"] == "STACKED_PR_UNSUPPORTED"
    assert gh.count("PUT", ".") == 0


@pytest.mark.parametrize("rest_list_shape", [False, True])
async def test_c05_new_stack_during_acceptance_never_dispatches(make_daemon, gh, monkeypatch, rest_list_shape):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d, action="delivery.merge_and_deploy", recipe="prod")
    await settle(d, op["operation_id"], 1)
    gh.merge(7)
    # A newly created downstack PR is no longer in the stack list after it was swept in.
    lower = gh.add_pr(6, HEAD)
    lower.update(merged=True, state="closed", merge_commit_sha=MERGED)
    if rest_list_shape:
        from datetime import datetime, timezone
        client = d.ops.context["github"]
        original = client.pulls
        async def rest_list(*args, **kw):
            status, body = await original(*args, **kw)
            # List pulls has merged_at, not the single-PR response's merged boolean; second precision.
            return status, {"items": [{k: v for k, v in p.items() if k != "merged"} | {
                "merged_at": datetime.fromtimestamp(int(op["created_at"]), timezone.utc).isoformat()}
                for p in body["items"]]}
        monkeypatch.setattr(client, "pulls", rest_list)
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "MERGE_RESULT_SCOPE_CHANGED"
    assert gh.count("POST", ".") == 0 and gh.count("PUT", ".") == 1


async def test_c04_scope_changes_or_missing_pages_never_submit(make_daemon, gh, monkeypatch):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    _, op = await preview_op(d, method="merge")
    gh.add_pr(6, HEAD)
    done = await settle(d, op["operation_id"])
    assert done["error_code"] in {"MERGE_SCOPE_EXPANDED", "MERGE_SCOPE_CHANGED"} and gh.count("PUT", ".") == 0
    gh.pulls.pop(6)
    client = d.ops.context["github"]
    original = client.compare
    async def missing(repo, base, head, *, page=1):
        status, body = await original(repo, base, head, page=page)
        body["total_commits"] = 301
        if page > 1:
            body["commits"] = []
        return status, body
    monkeypatch.setattr(client, "compare", missing)
    doc = (await delivery.pr_preview(d.ops, "o/r", 7))["merge_preview"]
    assert doc["blocking"][0]["code"] == "MERGE_SCOPE_UNPROVEN"
    assert gh.count("PUT", ".") == 0


@pytest.mark.parametrize("status", [403, 404])
async def test_c04_stack_read_errors_are_not_empty_membership(make_daemon, gh, monkeypatch, status):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    async def unavailable(*args, **kw):
        return status, {"message": "cannot read stacks"}
    monkeypatch.setattr(d.ops.context["github"], "stacks", unavailable)
    doc, op = await preview_op(d)
    assert doc["blocking"][0]["code"] == "MERGE_SCOPE_UNPROVEN"
    assert (await settle(d, op["operation_id"]))["error_code"] == "MERGE_SCOPE_UNPROVEN"
    assert gh.count("PUT", ".") == 0


async def test_c05_wrong_merge_parent_keeps_receipt_and_stops_deploy(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d, method="merge", action="delivery.merge_and_deploy", recipe="prod")
    await settle(d, op["operation_id"], 1)
    gh.merge(7)
    gh.commits[MERGED]["parents"][1]["sha"] = "f" * 40
    done = await settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "MERGE_RESULT_UNVERIFIABLE"
    assert done["external_refs"]["merged_sha"] == MERGED and gh.count("POST", ".") == 0


async def test_merge_preview_expiry_only_before_first_submit(make_daemon, gh, monkeypatch):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    doc, op = await preview_op(d)
    monkeypatch.setattr(pr_delivery.time, "time", lambda: doc["expires_at"] + 1)
    assert (await settle(d, op["operation_id"]))["error_code"] == "PREVIEW_EXPIRED"
    assert gh.count("PUT", ".") == 0
    monkeypatch.undo()
    gh.merge_mode = "enqueue"
    doc, op = await preview_op(d, key="queued")
    await settle(d, op["operation_id"], 1)
    gh.merge(7)
    monkeypatch.setattr(pr_delivery.time, "time", lambda: doc["expires_at"] + 1)
    assert (await settle(d, op["operation_id"]))["status"] == "succeeded"
    assert gh.count("PUT", ".") == 1


async def test_metadata_cancelled_unknown_write_stays_blocking_until_proven(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.patch_mode = "lost_before"
    op = await update_op(d)
    unknown = await settle(d, op["operation_id"])
    assert unknown["status"] == "needs_attention" and unknown["error_code"] == "UNCERTAIN_UNRESOLVED"
    assert d.ops.cancel(TED, op["operation_id"])["status"] == "cancelled"
    await pr_delivery.reconcile_metadata(d.ops)
    with pytest.raises(OperationError) as e:
        await update_op(d, key="new")
    assert e.value.code == "PR_UPDATE_IN_PROGRESS"
    gh.pulls[7]["title"] = "Reviewed title"
    await pr_delivery.reconcile_metadata(d.ops)
    assert (await update_op(d, key="after-proof"))["status"] == "accepted"
    assert gh.count("PATCH", ".") == 1


def test_part_a_preview_migration_reopens_without_data_change(tmp_path):
    from bat_agent_connector.task_journal import Journal
    path = tmp_path / "old.db"
    j = Journal(path)
    doc = {"fixed": "scope"}
    j.db.execute("INSERT INTO pr_merge_previews VALUES (?,?,?,?,?,?,?)", ("mpv_" + "0" * 32, "o/r", 7,
                                                                         json.dumps(doc), "digest", 1, 2))
    j.db.execute("PRAGMA user_version=1")
    j.close()
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert pr_delivery.get_preview(j.db, "mpv_" + "0" * 32) == doc
    j.db.execute("PRAGMA user_version=8")  # rebase renumbering preserves both the row and later migrations
    j.close()
    j = Journal(path)
    assert j.db.execute("PRAGMA user_version").fetchone()[0] == 8
    assert pr_delivery.get_preview(j.db, "mpv_" + "0" * 32) == doc
    j.close()


async def tool_text(server, name, args):
    try:
        return str(await server.call_tool(name, args))
    except Exception as exc:  # direct MCP calls raise anticipated tool errors
        return str(exc)


async def test_c07_delivery_transports_share_actions_and_principals(make_daemon, gh, monkeypatch, tmp_path, capsys):
    from bat_agent_connector import cli
    from bat_agent_connector.mcp_server import build_server
    from tests.test_api_v1 import http, token
    d = make_daemon()
    gh.add_pr(7, HEAD)
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    own = token(d, "client", "observe", "integrate", "merge", "deploy")
    viewer = token(d, "viewer", "observe")
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_API_TOKEN", own)
    mcp, fleet = build_server(d.fleet.config)
    try:
        _, body = await http(port, "GET", "/api/v1/repositories/o/r/pulls/7?method=squash", tok=own)
        pr = body["pull_request"]
        doc = pr["merge_preview"]
        _, saved = await http(port, "GET", f"/api/v1/delivery/previews/{doc['preview_id']}", tok=own)
        assert saved["preview"] == doc
        envelope = {"action": "github.pr.update", "target": {"repository": "o/r", "pull_number": 7},
                    "params": {"title": "Across transports", "body": "Markdown\n"},
                    "preconditions": {"expected_metadata_digest": pr["metadata_digest"]}, "idempotency_key": "shared"}
        assert (await http(port, "POST", "/api/v1/operations", tok=viewer, body=envelope))[0] == 403
        _, out = await http(port, "POST", "/api/v1/operations", tok=own, body=envelope)
        op_id = out["operation"]["operation_id"]
        assert (await settle(d, op_id))["status"] == "succeeded"
        response = await tool_text(mcp, "github_pr_update", {"repository": "o/r", "pull_number": 7,
            "expected_metadata_digest": pr["metadata_digest"], "title": "Across transports", "body": "Markdown\n",
            "idempotency_key": "shared", "wait_s": 0, "confirm": True})
        assert op_id in str(response)
        body_file = tmp_path / "body.md"
        body_file.write_text("Markdown\n")
        assert await asyncio.to_thread(cli.main, ["delivery", "update-pr", "o/r", "7", "--metadata-digest",
            pr["metadata_digest"], "--title", "Across transports", "--body-file", str(body_file), "--key", "shared"]) == 0
        assert op_id in capsys.readouterr().out
        assert gh.count("PATCH", ".") == 1
        # New merge preview after the title change, then identical HTTP/MCP/CLI intent.
        _, body = await http(port, "GET", "/api/v1/repositories/o/r/pulls/7", tok=own)
        doc = body["pull_request"]["merge_preview"]
        envelope = {**pr_delivery.merge_envelope(doc), "idempotency_key": "merge-shared"}
        _, out = await http(port, "POST", "/api/v1/operations", tok=own, body=envelope)
        merge_id = out["operation"]["operation_id"]
        assert (await settle(d, merge_id))["status"] == "succeeded"
        response = await tool_text(mcp, "github_pr_merge", {"preview_id": doc["preview_id"],
            "idempotency_key": "merge-shared", "wait_s": 0, "confirm": True})
        assert merge_id in str(response)
        assert await asyncio.to_thread(cli.main, ["delivery", "merge", "--preview", doc["preview_id"], "--key", "merge-shared"]) == 0
        assert merge_id in capsys.readouterr().out
        assert gh.count("PUT", ".") == 1
        assert {o["actor"] for o in d.ops.list()["operations"]} == {"client"}
        assert (await http(port, "GET", f"/api/v1/delivery/previews/{doc['preview_id']}", tok=viewer))[0] == 200
        # An agent token cannot borrow the Dashboard's integrate/merge grants.
        monkeypatch.setenv("BATC_API_TOKEN", viewer)
        response = await tool_text(mcp, "github_pr_merge", {"preview_id": doc["preview_id"], "idempotency_key": "agent", "confirm": True})
        assert "FORBIDDEN" in str(response)
        assert await asyncio.to_thread(cli.main, ["delivery", "merge", "--preview", doc["preview_id"], "--key", "agent"]) == 1
        assert "FORBIDDEN" in capsys.readouterr().err
        _, caps = await http(port, "GET", "/api/v1/capabilities", tok=viewer)
        assert caps["contract_version"] == "2026-10-08"
        assert caps["features"]["merge_scope_preview"] and caps["features"]["metadata_update"]
        merge_only = token(d, "merge-only", "observe", "merge")
        _, caps = await http(port, "GET", "/api/v1/capabilities", tok=merge_only)
        assert not next(a["allowed"] for a in caps["actions"] if a["action"] == "delivery.merge_and_deploy")
    finally:
        await fleet.close()
        server.close()
        await server.wait_closed()


async def test_c07_delivery_wrappers_require_confirmation_and_token(make_daemon, monkeypatch):
    from bat_agent_connector.mcp_server import build_server
    d = make_daemon()
    mcp, fleet = build_server(d.fleet.config)
    monkeypatch.delenv("BATC_API_TOKEN", raising=False)
    try:
        for name, args in [("github_pr_merge", {"preview_id": "mpv_" + "0" * 32, "idempotency_key": "x"}),
                           ("github_pr_update", {"repository": "o/r", "pull_number": 7,
                            "expected_metadata_digest": "0" * 64, "idempotency_key": "x", "title": "title"})]:
            for confirm, message in [(False, "confirm=true"), (True, "BATC_API_TOKEN")]:
                result = await tool_text(mcp, name, {**args, "confirm": confirm})
                assert message in str(result)
        readonly, ro_fleet = build_server(d.fleet.config, read_only=True)
        assert not {"github_pr_merge", "github_pr_update"} & {t.name for t in await readonly.list_tools()}
        await ro_fleet.close()
    finally:
        await fleet.close()


@pytest.mark.parametrize("options", [{"merge_action": "bypass"}, {"merge_method": "default"},
                                    {"expected_head_sha": None}, {"merge_method": "merge"}])
async def test_c04_existing_request_requires_exact_options(make_daemon, gh, monkeypatch, options):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "conflict_409_same"
    doc, op = await preview_op(d)
    client = d.ops.context["github"]
    original = client.merge_async
    async def different(*args):
        status, body = await original(*args)
        body["details"].update(options)
        return status, body
    monkeypatch.setattr(client, "merge_async", different)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "needs_attention" and done["error_code"] == "EXISTING_MERGE_REQUEST"
    assert not gh.pulls[7]["merged"] and gh.count("PUT", ".") == 1
    assert doc["method"] == "squash"


async def test_c05_independently_merged_candidate_on_new_base_is_allowed(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(6, "c" * 40)
    gh.add_pr(7, HEAD)
    gh.commits[HEAD]["parents"] = [{"sha": "c" * 40}]
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d)
    await settle(d, op["operation_id"], 1)
    gh.merge(6, sha="d" * 40)
    gh.merge(7)
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["base_moved"]
    assert done["result"]["affected_prs"][0]["independent"]
    assert gh.count("PUT", ".") == 1


async def test_metadata_cancel_after_acknowledgement_retains_verified_effect(make_daemon, gh, monkeypatch):
    from bat_agent_connector.github import GitHubAmbiguous
    d = make_daemon()
    gh.add_pr(7, HEAD)
    op = await update_op(d)
    client = d.ops.context["github"]
    original = client.pull
    async def unavailable_after_write(*args):
        if gh.count("PATCH", "."):
            raise GitHubAmbiguous("readback unavailable")
        return await original(*args)
    monkeypatch.setattr(client, "pull", unavailable_after_write)
    waiting = await settle(d, op["operation_id"], 1)
    assert waiting["status"] == "uncertain" and waiting["external_refs"]["write_acknowledged"]
    assert waiting["external_refs"]["verification_pending"]
    d.ops.cancel(TED, op["operation_id"])
    monkeypatch.setattr(client, "pull", original)
    await pr_delivery.reconcile_metadata(d.ops)
    assert d.ops.get(op["operation_id"])["external_refs"]["observed_intent"]
    assert gh.count("PATCH", ".") == 1


async def test_c05_rebase_verifies_reviewed_head_and_actual_destination(make_daemon, gh):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    source = "c" * 40
    gh.commits[source] = {"sha": source, "parents": [{"sha": "b" * 40}], "commit": {"message": "source one"}}
    gh.commits[HEAD]["parents"] = [{"sha": source}]
    gh.merge_mode = "enqueue"
    doc, op = await preview_op(d, method="rebase")
    await settle(d, op["operation_id"], 1)
    onto = "d" * 40
    gh.commits[onto] = {"sha": onto, "parents": [{"sha": "b" * 40}], "commit": {"message": "another merge"}}
    gh.branches["main"] = onto
    gh.merge(7)
    done = await settle(d, op["operation_id"])
    assert len(doc["commits"]) == 2
    assert done["status"] == "succeeded" and done["result"]["merged_onto_base_sha"] == onto
    assert done["result"]["base_moved"] and done["result"]["other_commits_count"] == 1
    assert gh.count("PUT", ".") == 1


async def test_c05_merge_verification_intent_precedes_reads_and_resume_is_read_only(make_daemon, gh, monkeypatch):
    d = make_daemon()
    gh.add_pr(7, HEAD)
    gh.merge_mode = "enqueue"
    _, op = await preview_op(d, method="merge")
    await settle(d, op["operation_id"], 1)
    gh.merge(7)
    gh.commits[MERGED]["parents"][1]["sha"] = "f" * 40
    client = d.ops.context["github"]
    original = client.commit
    async def check_intent(repo, sha):
        if sha == MERGED:
            row = d.journal.db.execute("SELECT status FROM operation_steps WHERE operation_id=? "
                                      "AND name LIKE 'merge.verify%' ORDER BY seq DESC LIMIT 1",
                                      (op["operation_id"],)).fetchone()
            assert row and row["status"] == "started"
        return await original(repo, sha)
    monkeypatch.setattr(client, "commit", check_intent)
    assert (await settle(d, op["operation_id"]))["error_code"] == "MERGE_RESULT_UNVERIFIABLE"
    gh.commits[MERGED]["parents"][1]["sha"] = HEAD
    d.ops.resume(TED, op["operation_id"])
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded" and done["result"]["verified"]
    assert any(s["name"].startswith("merge.verify.retry.") for s in done["steps"])
    assert gh.count("PUT", ".") == 1


async def test_c04_paginated_pr_list_finds_late_indirect_candidate(make_daemon, gh):
    d = make_daemon()
    for number in range(1, 110):
        if number != 7:
            gh.add_pr(number, "b" * 40)
    gh.add_pr(7, HEAD)
    gh.add_pr(111, "c" * 40)
    gh.commits[HEAD]["parents"] = [{"sha": "c" * 40}]
    doc = (await delivery.pr_preview(d.ops, "o/r", 7, "merge"))["merge_preview"]
    assert doc["affected_prs"][0]["number"] == 111
    assert doc["blocking"][0]["code"] == "MERGE_SCOPE_EXPANDED"
    assert gh.count("GET", r"pulls\?.*page=2") == 1 and gh.count("PUT", ".") == 0
