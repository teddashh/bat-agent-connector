"""HTTP/MCP/CLI share deployment actions and the caller's principal (§09/§10, C07)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from bat_agent_connector import cli, deployment
from bat_agent_connector.mcp_server import build_server
from tests import test_delivery as fixtures
from tests.test_api_v1 import http, token
from tests.test_delivery import MERGED, settle, tool_text
from tests.test_deployment_rollback import allow
from tests.test_deployments import completed, source_on_main

gh = fixtures.gh
make_daemon = fixtures.make_daemon


async def test_deployment_transports_share_fixed_identity_generation_and_principal(
    make_daemon, gh, monkeypatch, capsys
):
    d = make_daemon()
    source_on_main(gh)
    allow(d)
    server = await asyncio.start_server(d._handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    own = token(d, "deployment-client", "observe", "deploy")
    viewer = token(d, "observer", "observe")
    no_observe = token(d, "deployer-only", "deploy")
    monkeypatch.setenv("BATC_TASK_URL", f"http://127.0.0.1:{port}/rpc")
    monkeypatch.setenv("BATC_API_TOKEN", own)
    mcp, fleet = build_server(d.fleet.config)
    try:
        for path in (
            "/api/v1/deployments/preview?recipe=prod",
            "/api/v1/deployments?recipe=prod",
            "/api/v1/deployment-environments?recipe=prod",
        ):
            assert (await http(port, "GET", path, tok=viewer))[0] == 200
            assert (await http(port, "GET", path, tok=no_observe))[0] == 403
        _, out = await http(port, "GET", "/api/v1/deployments/preview?recipe=prod", tok=own)
        p = out["preview"]
        pre = p["preconditions"]
        body = {
            "action": "deployment.start",
            "target": {"recipe": "prod"},
            "params": {"source_sha": MERGED},
            "preconditions": pre,
            "idempotency_key": "shared-deploy",
        }
        assert (await http(port, "POST", "/api/v1/operations", tok=viewer, body=body))[0] == 403
        _, out = await http(port, "POST", "/api/v1/operations", tok=own, body=body)
        op_id = out["operation"]["operation_id"]
        w = await settle(d, op_id, rounds=1)
        rid = w["external_refs"]["deploy_run_id"]
        completed(gh, rid)
        done = await settle(d, op_id)
        dep_id = done["result"]["deployment_id"]
        args = {
            "recipe": "prod",
            "source_sha": MERGED,
            **pre,
            "idempotency_key": "shared-deploy",
            "wait_s": 0,
            "confirm": True,
        }
        assert op_id in await tool_text(mcp, "deployment_start", args)
        flags = [
            "--generation",
            str(pre["expected_environment_generation"]),
            "--recipe-digest",
            pre["expected_recipe_digest"],
            "--key",
            "shared-deploy",
        ]
        assert await asyncio.to_thread(cli.main, ["delivery", "deploy", "prod", "--sha", MERGED, *flags]) == 0
        assert op_id in capsys.readouterr().out
        for tool, args in [
            ("deployment_preview", {"recipe": "prod"}),
            ("deployment_environment_get", {"recipe": "prod"}),
            ("deployment_status", {"deployment_id": dep_id}),
            ("deployments_list", {"recipe": "prod", "limit": 1}),
        ]:
            assert dep_id in await tool_text(mcp, tool, args)
        for argv in (["preview", "prod"], ["history", "prod", "--limit", "1"], ["show", dep_id]):
            assert await asyncio.to_thread(cli.main, ["delivery", *argv]) == 0
            assert dep_id in capsys.readouterr().out
        assert (await http(port, "GET", f"/api/v1/deployments/{dep_id}", tok=viewer))[1]["deployment"][
            "identity"
        ] == {"source_sha": MERGED}
        assert (await http(port, "GET", f"/api/v1/deployments/{dep_id}", tok=no_observe))[0] == 403
        for kind in ("retry", "rollback"):
            p = (await deployment.preview(d.ops, "prod"))["preconditions"]
            saved = deployment.status(d.ops, dep_id)
            envelope = (
                deployment.retry_envelope(saved, p)
                if kind == "retry"
                else {
                    "action": "deployment.rollback",
                    "target": {"recipe": "prod"},
                    "params": {"deployment_id": dep_id},
                    "preconditions": p,
                }
            )
            _, out = await http(
                port, "POST", "/api/v1/operations", tok=own, body={**envelope, "idempotency_key": kind}
            )
            op = out["operation"]
            w = await settle(d, op["operation_id"], rounds=1)
            completed(gh, w["external_refs"]["deploy_run_id"])
            assert (await settle(d, op["operation_id"]))["status"] == "succeeded"
            args = {"deployment_id": dep_id, **p, "idempotency_key": kind, "wait_s": 0, "confirm": True}
            if kind == "rollback":
                args["recipe"] = "prod"
            assert op["operation_id"] in await tool_text(mcp, "deployment_" + kind, args)
            flags = [
                "--generation",
                str(p["expected_environment_generation"]),
                "--recipe-digest",
                p["expected_recipe_digest"],
                "--key",
                kind,
            ]
            assert await asyncio.to_thread(cli.main, ["delivery", kind, "prod", dep_id, *flags]) == 0
            assert op["operation_id"] in capsys.readouterr().out
        assert {op["actor"] for op in d.ops.list()["operations"]} == {"deployment-client"}
        assert gh.count("POST", "dispatches") == 3 and gh.count("PUT", ".") == 0
        monkeypatch.setenv("BATC_API_TOKEN", viewer)
        assert "FORBIDDEN" in await tool_text(
            mcp,
            "deployment_rollback",
            {
                "recipe": "prod",
                "deployment_id": dep_id,
                **p,
                "idempotency_key": "viewer-write",
                "confirm": True,
            },
        )
        _, caps = await http(port, "GET", "/api/v1/capabilities", tok=viewer)
        assert caps["contract_version"] == "2026-10-08"
        assert all(
            caps["features"][name]
            for name in (
                "deployment_history",
                "environment_generation",
                "runtime_check",
                "rollback_readiness",
            )
        )
        assert caps["deploy_recipes"][0]["rollback"]["not_undone"] == ["database migrations"]
        assert "token_ref" not in json.dumps(caps)
    finally:
        await fleet.close()
        server.close()
        await server.wait_closed()


async def test_deployment_wrappers_require_confirmation_token_and_are_hidden_read_only(
    make_daemon, monkeypatch
):
    d = make_daemon()
    mcp, fleet = build_server(d.fleet.config)
    readonly, ro_fleet = build_server(d.fleet.config, read_only=True)
    try:
        names = {t.name for t in await readonly.list_tools()}
        assert {
            "deployment_preview",
            "deployment_status",
            "deployments_list",
            "deployment_environment_get",
        } <= names
        assert not {"deployment_start", "deployment_retry", "deployment_rollback"} & names
        monkeypatch.delenv("BATC_API_TOKEN", raising=False)
        for tool in ("deployment_start", "deployment_retry", "deployment_rollback"):
            args = {
                "expected_environment_generation": 0,
                "expected_recipe_digest": "0" * 64,
                "idempotency_key": "guard",
            }
            if tool == "deployment_start":
                args.update(recipe="prod", source_sha=MERGED)
            else:
                args.update(deployment_id="dep_" + "0" * 32)
            if tool == "deployment_rollback":
                args["recipe"] = "prod"
            assert "confirm=true" in await tool_text(mcp, tool, args)
            assert "BATC_API_TOKEN" in await tool_text(mcp, tool, {**args, "confirm": True})
    finally:
        await fleet.close()
        await ro_fleet.close()


async def test_capabilities_missing_runtime_verification_disables_deploys(make_daemon):
    d = make_daemon()
    cfg = d.ops.context["github_config"]
    cfg.recipes["prod"] = replace(cfg.recipes["prod"], verification=None)
    from tests.test_delivery import TED

    _, caps = await d.api.capabilities(principal=TED)
    assert not caps["features"]["deploy"]
    assert caps["features"]["deployment_history"]
    assert caps["deploy_recipes"][0]["readiness"]["missing"] == ["verification"]
