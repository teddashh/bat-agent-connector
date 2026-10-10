"""Real mock BAT setup, private staging and journaled configuration recovery."""
from __future__ import annotations

import json
import time

import pytest

from bat_agent_connector import api_auth, dashboard_sync, platform_files
from bat_agent_connector import managed_setup as setup
from bat_agent_connector.channels import GUARDED_CHANNELS, ORCHESTRATE_CHANNELS, WRITE_CHANNELS
from bat_agent_connector.config import parse_config, tomllib
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.operation_helpers import settle_operations


@pytest.fixture
async def installed(tmp_path, monkeypatch):
    root = tmp_path / "managed"
    platform_files.ensure_private_directory(root / "config")
    monkeypatch.setenv("BATC_CONFIG_DIR", str(root / "config"))
    monkeypatch.setenv("BATC_STATE_DIR", str(root / "state"))
    path = root / "config" / "hosts.toml"
    source = {"client": {"label": "Fixture"}, "hosts": {}, "safety": {"write_min_interval_s": 0},
              "operator_extension": {"keep": ["one", "two"], "nested": {"enabled": True}}}
    platform_files.atomic_write(path, setup._encode(source))
    daemon = TaskDaemon(parse_config(source, path), root / "state" / "tasks.sqlite3")
    principal = api_auth.Principal("desktop-fixture", frozenset(api_auth.SCOPES))
    daemon.managed_installation = {"data_dir": root, "actor": principal.actor,
                                  **dashboard_sync.identity(daemon.journal, principal)}
    setup.install(daemon)
    yield daemon, principal, root
    await daemon.ops.drain()
    await daemon.fleet.close()
    await daemon.inventory.close()
    daemon.journal.close()


def host_params(daemon, principal, mock, **extra):
    ref = setup.stage_secret(daemon, principal, {"kind": "bat", "value": mock.token})["secret_ref"]
    return {"url": mock.url, "fingerprint": mock.fingerprint, "profile_id": "default", "secret_ref": ref,
            "writes": True, "orchestrate": True, "managed_roots": ["/srv/owned"], **extra}


def create(installed, action, target, params, *, key="fixture-setup", revision=None):
    daemon, principal, _ = installed
    return daemon.ops.create(principal, action=action, target=target, params=params,
        preconditions={"config_revision": revision or setup.state(daemon, principal)["revision"]},
        idempotency_key=key)[0]


async def settle(installed, operation):
    daemon, _, _ = installed
    await settle_operations(daemon.ops)
    return daemon.ops.get(operation["operation_id"])


async def test_setup_real_bat_preserves_config_and_exposes_no_secrets(installed, mock, monkeypatch):
    daemon, principal, root = installed
    aliases = []
    async def ssh(alias):
        aliases.append(alias)
    monkeypatch.setattr(setup, "_probe_ssh", ssh)
    params = host_params(daemon, principal, mock, ssh_alias="fixture-bat")
    before = setup.state(daemon, principal)["revision"]
    operation = create(installed, "setup.host", {"host": "fixture"}, params, revision=before)
    result = await settle(installed, operation)
    assert result["status"] == "succeeded", result
    assert aliases == ["fixture-bat"]
    assert result["result"]["workspaces"] == [{"workspace_id": "ws-1", "name": "demo-project"},
                                              {"workspace_id": "ws-2", "name": "other"}]
    raw = (root / "config" / "hosts.toml").read_text()
    data = tomllib.loads(raw)
    assert data["operator_extension"] == {"keep": ["one", "two"], "nested": {"enabled": True}}
    assert data["safety"]["write_min_interval_s"] == 0
    assert daemon.fleet.config.host("fixture").orchestrate
    assert daemon.inventory.fleet.config is daemon.fleet.config
    assert daemon.inventory.observation.config is daemon.fleet.config
    assert daemon.adapter.verifier.settings.ssh_hosts == {"fixture": "fixture-bat"}
    assert daemon.ops.context["git_runner"].available("fixture")
    assert daemon.ops.context["artifact_host"].available("fixture")
    assert mock.token not in raw and mock.token not in json.dumps(result)
    assert mock.token not in " ".join(str(tuple(row)) for row in daemon.journal.db.execute("SELECT * FROM operations"))
    assert not [frame for frame in mock.invokes if frame["channel"] in WRITE_CHANNELS | ORCHESTRATE_CHANNELS | GUARDED_CHANNELS]
    assert create(installed, "setup.host", {"host": "fixture"}, params, revision=before)["operation_id"] == operation["operation_id"]


async def test_bad_pin_or_profile_is_never_published(installed, mock):
    daemon, principal, root = installed
    original = (root / "config" / "hosts.toml").read_bytes()
    params = host_params(daemon, principal, mock, fingerprint="00" * 32)
    result = await settle(installed, create(installed, "setup.host", {"host": "fixture"}, params))
    assert result["status"] == "failed" and result["error_code"] == "SETUP_PROBE_FAILED"
    assert not mock.auth_frames  # pin failure happens before the token crosses the wire
    assert (root / "config" / "hosts.toml").read_bytes() == original
    params = host_params(daemon, principal, mock, profile_id="missing")
    result = await settle(installed, create(installed, "setup.host", {"host": "fixture"}, params, key="bad-profile"))
    assert result["status"] == "failed" and result["error_code"] == "PROFILE_NOT_FOUND"
    assert (root / "config" / "hosts.toml").read_bytes() == original


async def test_revision_conflict_rejected_before_journaling_or_network(installed, mock):
    daemon, principal, _ = installed
    params = host_params(daemon, principal, mock)
    with pytest.raises(OperationError) as error:
        create(installed, "setup.host", {"host": "fixture"}, params, revision="0" * 64)
    assert error.value.code == "CONFIGURATION_CHANGED"
    assert daemon.journal.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0
    assert not mock.frames


@pytest.mark.parametrize("change", [{"token_ref": "file:/unrelated/private"}, {"secret_ref": "../outside"},
    {"writes": "yes"}, {"url": "wss://user:credential@fixture:9876"}, {"managed_roots": ["/"]},
    {"ssh_alias": "-oProxyCommand=untrusted"}])
async def test_setup_rejects_unsafe_or_untyped_fields(installed, mock, change):
    daemon, principal, _ = installed
    params = host_params(daemon, principal, mock, **change)
    with pytest.raises(OperationError):
        create(installed, "setup.host", {"host": "fixture"}, params)
    assert not mock.frames


async def test_secret_kind_identity_expiry_and_traversal_are_enforced(installed, mock):
    daemon, principal, root = installed
    stranger = api_auth.Principal("other-person", principal.scopes)
    with pytest.raises(OperationError):
        setup.stage_secret(daemon, stranger, {"kind": "bat", "value": mock.token})
    with pytest.raises(OperationError):
        setup.stage_secret(daemon, principal, {"kind": ["bat"], "value": mock.token})
    ref = setup.stage_secret(daemon, principal, {"kind": "github", "value": mock.token})["secret_ref"]
    params = host_params(daemon, principal, mock, secret_ref=ref)
    with pytest.raises(OperationError):
        create(installed, "setup.host", {"host": "fixture"}, params)
    good = host_params(daemon, principal, mock)
    metadata_path = root / "config" / "setup-secrets" / (good["secret_ref"] + ".json")
    metadata = json.loads(metadata_path.read_text())
    metadata["expires_at"] = time.time() - 1
    platform_files.atomic_write(metadata_path, json.dumps(metadata).encode())
    with pytest.raises(OperationError):
        create(installed, "setup.host", {"host": "fixture"}, good)
    setup.stage_secret(daemon, principal, {"kind": "bat", "value": mock.token})
    assert not metadata_path.exists()  # unreferenced expired staging is cleaned on the next explicit stage


async def test_host_identity_is_not_rebound_and_other_work_blocks_setup(installed, mock):
    daemon, principal, _ = installed
    params = host_params(daemon, principal, mock)
    assert (await settle(installed, create(installed, "setup.host", {"host": "fixture"}, params)))["status"] == "succeeded"
    with pytest.raises(OperationError) as error:
        create(installed, "setup.host", {"host": "fixture"}, {**params, "url": "wss://127.0.0.1:65431/"}, key="rebind")
    assert error.value.code == "HOST_IDENTITY_CHANGED"
    daemon.ops.create(principal, action="project.create", params={"name": "Another operation"}, idempotency_key="project")
    with pytest.raises(OperationError) as error:
        create(installed, "setup.host", {"host": "second"}, params, key="busy")
    assert error.value.code == "SETUP_BUSY"


async def test_post_publish_receipt_loss_recovers_by_digest_without_repeating_probe(installed, mock, monkeypatch):
    daemon, principal, root = installed
    params = host_params(daemon, principal, mock)
    operation = create(installed, "setup.host", {"host": "fixture"}, params)
    original = daemon.ops._step_done
    interrupted = False
    def lose_receipt(ident, name, response, **kwargs):
        nonlocal interrupted
        if name == "managed_configuration" and not interrupted:
            interrupted = True
            raise OSError("fixture receipt lost after durable configuration publication")
        return original(ident, name, response, **kwargs)
    monkeypatch.setattr(daemon.ops, "_step_done", lose_receipt)
    await daemon.ops._execute(operation["operation_id"])
    calls = len(mock.auth_frames)
    assert "fixture" in tomllib.loads((root / "config" / "hosts.toml").read_text())["hosts"]
    monkeypatch.setattr(daemon.ops, "_step_done", original)
    await daemon.ops._execute(operation["operation_id"])
    assert daemon.ops.get(operation["operation_id"])["status"] == "succeeded"
    assert len(mock.auth_frames) == calls


@pytest.mark.parametrize("change", ["configuration", "operation"])
async def test_probe_cannot_overwrite_concurrent_configuration_or_active_work(installed, mock, monkeypatch, change):
    daemon, principal, root = installed
    path = root / "config" / "hosts.toml"
    expected = path.read_bytes()
    original_probe = setup._probe_host
    async def probe(config, host):
        nonlocal expected
        result = await original_probe(config, host)
        if change == "configuration":
            document = tomllib.loads(path.read_text())
            document["operator_extension"]["added_during_verification"] = True
            expected = setup._encode(document)
            platform_files.atomic_write(path, expected)
        else:
            daemon.ops.create(principal, action="project.create", params={"name": "Concurrent work"}, idempotency_key="concurrent")
        return result
    monkeypatch.setattr(setup, "_probe_host", probe)
    operation = create(installed, "setup.host", {"host": "fixture"}, host_params(daemon, principal, mock))
    await daemon.ops._execute(operation["operation_id"])
    assert daemon.ops.get(operation["operation_id"])["error_code"] == "CONFIGURATION_CHANGED"
    assert path.read_bytes() == expected
    assert not daemon.fleet.config.hosts


async def test_accepted_secret_expiry_does_not_change_durable_original_intent(installed, mock):
    daemon, principal, root = installed
    params = host_params(daemon, principal, mock)
    operation = create(installed, "setup.host", {"host": "fixture"}, params)
    metadata_path = root / "config" / "setup-secrets" / (params["secret_ref"] + ".json")
    metadata = json.loads(metadata_path.read_text())
    metadata["expires_at"] = time.time() - 1
    platform_files.atomic_write(metadata_path, json.dumps(metadata).encode())
    setup.stage_secret(daemon, principal, {"kind": "bat", "value": mock.token})
    assert metadata_path.exists()  # pending original intent keeps its already admitted credential
    result = await settle(installed, operation)
    assert result["status"] == "succeeded", result


async def test_repository_binding_checks_provider_and_exact_workspace(installed, mock, monkeypatch):
    daemon, principal, root = installed
    assert (await settle(installed, create(installed, "setup.host", {"host": "fixture"}, host_params(daemon, principal, mock))))["status"] == "succeeded"
    calls = []
    async def repository(self, name):
        calls.append((self.cfg.api_url, name))
        return 200, {"full_name": "fixture/repository"}
    monkeypatch.setattr(setup.GitHubClient, "repository", repository)
    ref = setup.stage_secret(daemon, principal, {"kind": "github", "value": "synthetic-github-fixture-token"})["secret_ref"]
    params = {"host": "fixture", "workspace_id": "ws-1", "secret_ref": ref,
              "remote_url": "git@github.com:fixture/repository.git", "allow_merge": True, "allow_integrate": True}
    result = await settle(installed, create(installed, "setup.repository", {"repository": "fixture/repository"}, params, key="repo"))
    assert result["status"] == "succeeded", result
    repo = daemon.ops.context["github_config"].repos["fixture/repository"]
    assert repo.sync.bindings == (("fixture", "ws-1"),)
    assert repo.integrate.hosts == ("fixture",)
    assert calls == [("https://api.github.com", "fixture/repository")]
    saved = (root / "config" / "hosts.toml").read_bytes()
    bad = {**params, "workspace_id": "unknown-workspace"}
    with pytest.raises(OperationError) as error:
        create(installed, "setup.repository", {"repository": "fixture/repository"}, bad, key="rebind-integration")
    assert error.value.code == "REPOSITORY_BINDING_CHANGED"
    bad.pop("allow_integrate")
    result = await settle(installed, create(installed, "setup.repository", {"repository": "fixture/repository"}, bad, key="bad-workspace"))
    assert result["error_code"] == "WORKSPACE_NOT_FOUND"
    assert (root / "config" / "hosts.toml").read_bytes() == saved
    assert len(calls) == 1


async def test_profile_import_respects_encryption_and_never_returns_credentials(installed, mock, tmp_path, monkeypatch):
    daemon, principal, _ = installed
    directory = tmp_path / "bat-profiles"
    directory.mkdir()
    from urllib.parse import urlsplit
    endpoint = urlsplit(mock.url)
    (directory / "index.json").write_text(json.dumps({"profiles": [{"id": "remote-1", "name": "Fixture BAT",
        "type": "remote", "remoteHost": endpoint.hostname, "remotePort": endpoint.port,
        "remoteFingerprint": mock.fingerprint}]}))
    (directory / "remote-tokens.enc.json").write_text(json.dumps({"enc": True, "data": "opaque-encrypted"}))
    monkeypatch.setattr(setup, "_profile_directory", lambda _: directory)
    state = setup.state(daemon, principal)
    assert state["profiles"][0]["token_available"] is False
    assert state["profiles"][0]["token_state"] == "encrypted"
    with pytest.raises(OperationError):
        create(installed, "setup.host", {"host": "fixture"}, {"import_profile_id": "remote-1"})
    (directory / "remote-tokens.enc.json").write_text(json.dumps({"enc": False, "data": {"tokens": {"remote-1": mock.token}}}))
    state = setup.state(daemon, principal)
    assert state["profiles"][0]["token_available"]
    assert mock.token not in json.dumps(state)
    result = await settle(installed, create(installed, "setup.host", {"host": "fixture"}, {"import_profile_id": "remote-1"}))
    assert result["status"] == "succeeded"
    assert daemon.fleet.config.host("fixture").token_ref == "bat-profile:remote-1"
