"""Runtime reads are bounded and credentials stay in the backend (D03, plan §17)."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bat_agent_connector import deployment
from bat_agent_connector.deployment_verifier import fetch
from tests import test_delivery as fixtures
from tests.test_delivery import MERGED, settle
from tests.test_deployments import completed, source_on_main, start

gh = fixtures.gh
make_daemon = fixtures.make_daemon


@pytest.fixture
def verifier_server():
    class Runtime:
        mode = "ok"
        requests = []
        body = {"repository_id": 4242, "environment": "production", "source_sha": MERGED, "healthy": True}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            Runtime.requests.append((self.path, self.headers.get("Authorization")))
            if Runtime.mode == "slow":
                time.sleep(2.5)
            body = b"x" * 1000 if Runtime.mode == "oversized" else json.dumps(Runtime.body).encode()
            self.send_response(302 if Runtime.mode == "redirect" else 200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Location", "/destination")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    Runtime.url = f"http://127.0.0.1:{server.server_port}/version"
    yield Runtime
    server.shutdown()
    server.server_close()
    worker.join()


@pytest.mark.parametrize(
    "case,reason",
    [
        ("redirect", "redirect"),
        ("oversized", "oversized"),
        ("non_https", "unavailable"),
        ("slow", "unavailable"),
    ],
)
async def test_verifier_security_refuses_redirect_oversized_non_https_and_slow(verifier_server, case, reason):
    server = verifier_server
    server.mode = case
    settings = {
        "url": "http://deployment.example/version" if case == "non_https" else server.url,
        "timeout_s": 2,
        "max_bytes": 300,
        "token_ref": None,
    }
    evidence = await fetch(settings)
    assert evidence["waiting"] and evidence["reason"] == reason
    assert len(server.requests) == (0 if case == "non_https" else 1)
    assert "destination" not in str(server.requests)
    assert "raw" not in evidence


async def test_verifier_backend_token_and_raw_body_never_enter_journal_logs_or_events(
    make_daemon, gh, verifier_server, monkeypatch, caplog
):
    d = make_daemon()
    source_on_main(gh)
    secret = "fake-runtime-credential-000000"
    monkeypatch.setenv("FAKE_RUNTIME_TOKEN", secret)
    server = verifier_server
    server.body = {**server.body, "token": secret, "debug": {"secret": secret}, "logs": "RAW_RESPONSE_MARKER"}
    cfg = d.ops.context["github_config"]
    r = cfg.recipes["prod"]
    cfg.recipes["prod"] = replace(
        r, verification=replace(r.verification, url=server.url, token_ref="env:FAKE_RUNTIME_TOKEN")
    )
    d.ops.context.pop("deployment_verifier")
    op = await start(d)
    w = await settle(d, op["operation_id"], rounds=1)
    completed(gh, w["external_refs"]["deploy_run_id"])
    done = await settle(d, op["operation_id"])
    assert done["status"] == "succeeded", done
    assert server.requests == [("/version", "Bearer " + secret)]
    dump = "\n".join(d.journal.db.iterdump())
    assert secret not in dump + caplog.text + json.dumps(done)
    assert "RAW_RESPONSE_MARKER" not in dump
    assert set(done["result"]["evidence"]["runtime"]["observed"]) == {
        "repository_id",
        "environment",
        "source_sha",
        "healthy",
    }
    p = deployment.status(d.ops, done["result"]["deployment_id"])
    assert "FAKE_RUNTIME_TOKEN" not in json.dumps(p)


async def test_verifier_refuses_secret_echo_in_whitelisted_field(verifier_server, monkeypatch):
    monkeypatch.setenv("FAKE_RUNTIME_TOKEN", "fake-verifier-credential")
    server = verifier_server
    server.body = {**server.body, "environment": "fake-verifier-credential", "repository_id": True}
    settings = {"url": server.url, "timeout_s": 2, "max_bytes": 65536, "token_ref": "env:FAKE_RUNTIME_TOKEN"}
    evidence = await fetch(settings)
    assert "environment" not in evidence and "repository_id" not in evidence
    assert "fake-verifier-credential" not in json.dumps(evidence)


async def test_runtime_artifact_mismatch_is_d03_failure(make_daemon, gh):
    d = make_daemon()
    source_on_main(gh)
    from tests.test_deployment_rollback import allow, artifact

    allow(d, artifact=True)
    artifact(gh)
    v = d.ops.context["deployment_verifier"]
    v.response = {
        "repository_id": 4242,
        "environment": "production",
        "source_sha": MERGED,
        "healthy": True,
        "artifact_id": 55,
        "artifact_digest": gh.artifacts[55]["digest"],
    }
    from tests.test_deployments import deployed

    first = await deployed(d, gh)
    op = await start(
        d,
        action="deployment.rollback",
        params={"deployment_id": first["result"]["deployment_id"]},
        key="artifact-mismatch",
    )
    w = await settle(d, op["operation_id"], rounds=1)
    completed(gh, w["external_refs"]["deploy_run_id"])
    v.response["artifact_digest"] = "sha256:" + "a" * 64
    done = await settle(d, op["operation_id"])
    assert done["error_code"] == "DEPLOY_VERSION_MISMATCH"
    assert (
        deployment.environment_status(d.ops, "prod")["current"]["deployment_id"]
        == first["result"]["deployment_id"]
    )


async def test_verification_settings_cannot_be_overridden_by_a_client(make_daemon):
    d = make_daemon()
    from bat_agent_connector.operations import OperationError

    with pytest.raises(OperationError) as e:
        await start(
            d,
            params={
                "source_sha": MERGED,
                "verification": {"url": "https://attacker.example/v", "token": "client"},
            },
        )
    assert e.value.code == "INVALID_PARAMS"
    r = d.ops.context["github_config"].recipes["prod"]
    assert asdict(r.verification)["url"] == "https://deployment.example/status"
