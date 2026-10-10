"""Real isolated service ownership, credential recovery and safe failure boundaries."""
import json
import os
import socket
import time

import pytest

from bat_agent_connector import managed_runtime as runtime


@pytest.fixture
def installation(tmp_path, monkeypatch):
    root = tmp_path / "installed"
    children = []
    original = runtime._spawn

    def spawn(path):
        child = original(path)
        children.append(child)
        return child

    monkeypatch.setattr(runtime, "_spawn", spawn)
    yield root, children
    for child in children:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except Exception:
                child.kill()
                child.wait(timeout=10)


def test_installed_runtime_reuses_identity_and_recovers_after_restart(installation):
    root, children = installation
    first = runtime.ensure(root, timeout=15)
    second = runtime.ensure(root, timeout=5)
    assert first == second and len(children) == 1
    assert first["token"].startswith("batc_")
    assert first["actor"].startswith("desktop-")
    # Service continues independently of launcher/client; its ordinary API is authoritative.
    bootstrap = runtime._request(first["endpoint"], "/api/v1/bootstrap", token=first["token"])
    assert bootstrap["sync"]["server_id"] == first["server_id"]
    assert bootstrap["sync"]["principal_id"] == first["principal_id"]
    stopped = runtime._request(first["endpoint"], "/api/v1/managed/stop", token=first["token"], body={})
    assert stopped == {"protocol": 1, "stopped": True}
    children[0].wait(timeout=10)
    third = runtime.ensure(root, timeout=15)
    assert {k: third[k] for k in ("actor", "token", "server_id", "principal_id")} == {
        k: first[k] for k in ("actor", "token", "server_id", "principal_id")}


def test_invalid_manifest_and_existing_unclaimed_data_never_spawn(installation):
    root, children = installation
    root.mkdir(mode=0o700)
    (root / "state").mkdir()
    with pytest.raises(ValueError, match="unclaimed"):
        runtime.ensure(root)
    assert not children and not (root / runtime.MANIFEST).exists()
    (root / "state").rmdir()
    runtime._write(root / runtime.MANIFEST, {"protocol": 1, "data_dir": str(root)})
    with pytest.raises(ValueError, match="manifest"):
        runtime.ensure(root)
    assert not children


def test_revoked_identity_never_gets_replaced(installation):
    root, children = installation
    first = runtime.ensure(root, timeout=15)
    runtime._request(first["endpoint"], "/api/v1/managed/stop", token=first["token"], body={})
    children[0].wait(timeout=10)
    import sqlite3
    with sqlite3.connect(root / "state" / "tasks.sqlite3") as db:
        db.execute("UPDATE api_principals SET revoked_at=?", (time.time(),))
    with pytest.raises(ValueError, match="initialization failed"):
        runtime.ensure(root, timeout=10)
    assert (root / "identity.token").read_text() == first["token"]
    assert json.loads((root / runtime.MANIFEST).read_text())["server_id"] == first["server_id"]


def test_occupied_default_port_is_not_adopted(installation):
    root, _ = installation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        first = runtime.ensure(root, timeout=15)
        assert first["endpoint"] != f"http://127.0.0.1:{listener.getsockname()[1]}"


@pytest.mark.skipif(os.name == "nt", reason="native reparse coverage lives in Windows platform fixtures")
def test_symlinked_installation_is_not_adopted(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "alias"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        runtime.ensure(link)
    assert not list(target.iterdir())
