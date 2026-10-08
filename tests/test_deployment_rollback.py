"""Rollback is a new deployment, never a journal edit (D06)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from bat_agent_connector import delivery, deployment
from bat_agent_connector import deployment_store as store
from bat_agent_connector.operations import OperationError, OperationService
from tests import test_delivery as fixtures
from tests.test_delivery import MERGED, TED, settle
from tests.test_deployments import NEW, completed, deployed, source_on_main, start

gh = fixtures.gh
make_daemon = fixtures.make_daemon


def allow(d, *, artifact=False):
    cfg = d.ops.context["github_config"]
    r = cfg.recipes["prod"]
    cfg.recipes["prod"] = replace(
        r,
        inputs=r.inputs
        + ((("artifact_id", "artifact_id"), ("artifact_digest", "artifact_digest")) if artifact else ()),
        rollback=replace(
            r.rollback,
            supported=True,
            identity="artifact" if artifact else "source_sha",
            not_undone=("database migrations",),
        ),
    )


def artifact(gh):
    gh.artifacts[55] = {
        "id": 55,
        "digest": "sha256:" + "f" * 64,
        "expired": False,
        "expires_at": "2099-01-01T00:00:00Z",
        "workflow_run": {"id": 8000, "repository_id": 4242},
    }


@pytest.mark.parametrize("identity", ["source_sha", "artifact"])
async def test_d06_rollback_redeploys_saved_identity_through_same_recipe(make_daemon, gh, identity):
    d = make_daemon()
    source_on_main(gh)
    allow(d, artifact=identity == "artifact")
    if identity == "artifact":
        artifact(gh)
        d.ops.context["deployment_verifier"].response = {
            "repository_id": 4242,
            "environment": "production",
            "source_sha": MERGED,
            "healthy": True,
            "artifact_id": 55,
            "artifact_digest": gh.artifacts[55]["digest"],
        }
    first = await deployed(d, gh)
    old = deployment.status(d.ops, first["result"]["deployment_id"])
    op = await start(
        d, action="deployment.rollback", params={"deployment_id": old["deployment_id"]}, key="rollback"
    )
    w = await settle(d, op["operation_id"], rounds=1)
    new = deployment.status(d.ops, w["external_refs"]["deployment_id"])
    assert new["generation"] == old["generation"] + 1 and new["rollback_of"] == old["deployment_id"]
    assert new["identity"] == old["identity"] and new["run_id"] != old["run_id"]
    sent = [b for m, p, b in gh.requests if m == "POST"][-1]["inputs"]
    assert sent["source_sha"] == MERGED
    if identity == "artifact":
        assert sent["artifact_id"] == "55" and sent["artifact_digest"] == old["identity"]["artifact_digest"]
        assert new["identity"]["artifact_run_id"] == 8000 != new["run_id"]
    completed(gh, new["run_id"])
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded", json.dumps(done)
    assert deployment.status(d.ops, old["deployment_id"])["identity"] == old["identity"]
    assert not deployment.status(d.ops, old["deployment_id"])["is_current"]
    assert deployment.status(d.ops, new["deployment_id"])["is_current"]
    assert deployment.status(d.ops, new["deployment_id"])["rollback"]["not_undone"] == ["database migrations"]
    assert gh.count("POST", "dispatches") == 2 and gh.count("PUT", ".") == 0


@pytest.mark.parametrize(
    "invalid,code",
    [
        ("unverified", "ROLLBACK_TARGET_INVALID"),
        ("other_environment", "ROLLBACK_TARGET_INVALID"),
        ("expired", "ROLLBACK_ARTIFACT_UNAVAILABLE"),
        ("unavailable", "ROLLBACK_ARTIFACT_UNAVAILABLE"),
        ("digest", "ROLLBACK_ARTIFACT_UNAVAILABLE"),
        ("other_repo", "ROLLBACK_ARTIFACT_UNAVAILABLE"),
        ("other_run", "ROLLBACK_ARTIFACT_UNAVAILABLE"),
    ],
)
async def test_d06_rollback_refuses_unverified_expired_or_other_environment(make_daemon, gh, invalid, code):
    d = make_daemon()
    source_on_main(gh)
    allow(d, artifact=True)
    artifact(gh)
    d.ops.context["deployment_verifier"].response = {
        "repository_id": 4242,
        "environment": "production",
        "source_sha": MERGED,
        "healthy": True,
        "artifact_id": 55,
        "artifact_digest": gh.artifacts[55]["digest"],
    }
    first = await deployed(d, gh)
    dep_id = first["result"]["deployment_id"]
    if invalid == "unverified":
        store.update(d.journal, dep_id, facts={"verified": False})
    elif invalid == "other_environment":
        s = deployment.get(d.ops, dep_id)["recipe_snapshot"]
        store.update(d.journal, dep_id, recipe_snapshot={**s, "environment": "other"})
    elif invalid == "expired":
        gh.artifacts[55]["expired"] = True
    elif invalid == "unavailable":
        gh.artifacts.clear()
    elif invalid == "digest":
        gh.artifacts[55]["digest"] = "sha256:" + "e" * 64
    elif invalid == "other_repo":
        gh.artifacts[55]["workflow_run"]["repository_id"] = 111
    elif invalid == "other_run":
        gh.artifacts[55]["workflow_run"]["id"] = 999
    try:
        op = await start(
            d, action="deployment.rollback", params={"deployment_id": dep_id}, key="bad-rollback"
        )
    except OperationError as e:
        assert e.code == code
    else:
        done = await settle(d, op["operation_id"])
        assert done["error_code"] == code, done
    assert gh.count("POST", "dispatches") == 1


async def test_d06_rollback_lost_reply_restart_never_dispatches_twice(make_daemon, gh):
    d = make_daemon()
    source_on_main(gh)
    allow(d)
    first = await deployed(d, gh)
    gh.dispatch_mode = "fail_500_but_started"
    op = await start(
        d,
        action="deployment.rollback",
        params={"deployment_id": first["result"]["deployment_id"]},
        key="lost",
    )
    assert (await settle(d, op["operation_id"], rounds=1))["status"] == "uncertain"
    fresh = OperationService(d.journal, actions=delivery.ACTIONS)
    fresh.context.update(d.ops.context)
    d.ops = fresh
    w = await settle(d, op["operation_id"], rounds=1)
    completed(gh, w["external_refs"]["deploy_run_id"])
    assert (await settle(d, op["operation_id"]))["status"] == "succeeded"
    assert gh.count("POST", "dispatches") == 2 and len(gh.runs) == 2


async def test_d06_record_inactive_or_deleted_is_not_runtime_rollback(make_daemon, gh):
    d = make_daemon()
    source_on_main(gh)
    allow(d)
    done = await deployed(d, gh)
    dep_id = done["result"]["deployment_id"]
    store.update(d.journal, dep_id, facts={"inactive": True})
    d.journal.db.execute("DELETE FROM deployments WHERE deployment_id=?", (dep_id,))
    assert deployment.history(d.ops, "prod")["items"] == []
    assert deployment.environment_status(d.ops, "prod")["desired_generation"] == 1
    assert gh.deployed_source == MERGED and gh.count("POST", "dispatches") == 1


async def test_d04_retry_keeps_saved_identity_and_never_merges_again(make_daemon, gh):
    d = make_daemon()
    source_on_main(gh)
    old = await deployed(d, gh)
    gh.commits[NEW] = {"sha": NEW, "parents": [{"sha": MERGED}]}
    gh.branches["main"] = NEW
    saved = deployment.status(d.ops, old["result"]["deployment_id"])
    p = await deployment.preview(d.ops, "prod")
    e = deployment.retry_envelope(saved, p["preconditions"])
    op = d.ops.create(TED, **e, idempotency_key="retry")[0]
    w = await settle(d, op["operation_id"], rounds=1)
    completed(gh, w["external_refs"]["deploy_run_id"])
    assert (await settle(d, op["operation_id"]))["result"]["source_sha"] == MERGED
    assert gh.count("PUT", ".") == 0 and gh.count("POST", "dispatches") == 2


async def test_history_keyset_is_stable_offline_and_rollback_disabled_for_missing_config(make_daemon, gh):
    d = make_daemon()
    source_on_main(gh)
    first = await deployed(d, gh)
    await deployed(d, gh, key="second")
    p = deployment.history(d.ops, "prod", limit=1)
    assert p["next_cursor"] and len(p["items"]) == 1
    cfg = d.ops.context["github_config"]
    cfg.recipes.clear()
    d.ops.context["github"] = None
    second = deployment.history(d.ops, "prod", cursor=p["next_cursor"], limit=1)
    assert second["items"][0]["deployment_id"] == first["result"]["deployment_id"]
    assert second["next_cursor"] is None and not second["items"][0]["rollback_eligible"]
    assert deployment.environment_status(d.ops, "prod")["current"]
    for cursor in ["bad", "eyJtYWxpY2lvdXMiOiJpbnB1dCJ9"]:
        with pytest.raises(OperationError):
            deployment.history(d.ops, "prod", cursor=cursor)
