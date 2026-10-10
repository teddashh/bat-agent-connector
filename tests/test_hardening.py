"""Private file validation, bounded output and connection lifecycle checks."""

import asyncio
import gzip
import json
import os
import sys
from types import SimpleNamespace

import pytest

from bat_agent_connector import _private_files, client
from bat_agent_connector._bounded import capture
from bat_agent_connector.checkpoints import _run
from bat_agent_connector.client import GZIP_MAGIC, BatClient, EventSubscription
from bat_agent_connector.config import SafetyConfig, _resolve_token_ref
from bat_agent_connector.errors import ConnectionLost, TokenUnavailable, WriteRefused
from bat_agent_connector.operations import AmbiguousOutcome
from bat_agent_connector.safety import Audit
from bat_agent_connector.task_verifier import ObservedVerifier, VerificationSettings


@pytest.mark.parametrize("kind,limit", [("file", 65536), ("bat-profile", 1048576)])
@pytest.mark.parametrize("condition", ["symlink", "directory", "permissions", "size", "owner"])
def test_validate_token_files(tmp_path, monkeypatch, kind, limit, condition):
    path = tmp_path / ("token" if kind == "file" else "remote-tokens.enc.json")
    path.write_text("fixture-value")
    path.chmod(0o600)
    if condition == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif condition == "directory":
        path.unlink()
        path.mkdir()
    elif condition == "permissions":
        if os.name == "nt":
            pytest.skip("POSIX permissions")
        path.chmod(0o640)
    elif condition == "size":
        with path.open("wb") as stream:
            stream.truncate(limit + 1)
    elif condition == "owner":
        if not hasattr(os, "getuid"):
            pytest.skip("uid unavailable")
        monkeypatch.setattr(_private_files, "os", SimpleNamespace(**{
            **vars(os), "getuid": lambda: os.getuid() + 1,
        }))
    ref = f"file:{path}" if kind == "file" else "bat-profile:fixture"
    with pytest.raises(TokenUnavailable) as exc:
        _resolve_token_ref(ref, str(tmp_path))
    assert "fixture-value" not in str(exc.value)


def test_private_token_normal_size(tmp_path):
    path = tmp_path / "token"
    path.write_text("fixture-value\n")
    path.chmod(0o600)
    assert _resolve_token_ref(f"file:{path}", "") == "fixture-value"


@pytest.mark.parametrize("text", ["token: short-value", "token=short-value", "?token=short-value&x=1",
                                  "&token=short-value", "Authorization: Bearer short-value", "Ab9_" * 10])
def test_redact_audit_preview(tmp_path, text):
    audit = Audit(SafetyConfig(audit_preview_chars=200), tmp_path / "audit")
    audit.record(text=text)
    preview = json.loads(audit.path.read_text())["text_preview"]
    assert "[redacted]" in preview
    assert "short-value" not in preview and "Ab9_" not in preview


@pytest.mark.parametrize("condition", ["symlink", "directory", "permissions", "owner"])
def test_validate_audit_files(tmp_path, monkeypatch, condition):
    path = tmp_path / "audit"
    path.write_text("")
    path.chmod(0o600)
    if condition == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif condition == "directory":
        path.unlink()
        path.mkdir()
    elif condition == "permissions":
        if os.name == "nt":
            pytest.skip("POSIX permissions")
        path.chmod(0o640)
    else:
        if not hasattr(os, "getuid"):
            pytest.skip("uid unavailable")
        monkeypatch.setattr(_private_files, "os", SimpleNamespace(**{
            **vars(os), "getuid": lambda: os.getuid() + 1,
        }))
    audit = Audit(SafetyConfig(), path)
    with pytest.raises(WriteRefused):
        audit.check_rate("fixture", "session")
    with pytest.raises(WriteRefused):
        audit.record(text="fixture")


def test_new_audit_file_permissions(tmp_path):
    audit = Audit(SafetyConfig(), tmp_path / "private" / "audit")
    audit.record(text="ordinary preview")
    if os.name != "nt":
        assert audit.path.stat().st_mode & 0o777 == 0o600
        assert audit.path.parent.stat().st_mode & 0o777 == 0o700


def test_bounded_gzip_frames():
    c = BatClient(SimpleNamespace(writes=False, orchestrate=False), device_id="fixture", max_frame=32)
    assert c._decode(GZIP_MAGIC + gzip.compress(b'{"ok": true}')) == {"ok": True}
    assert c._decode(GZIP_MAGIC + gzip.compress(b"x" * 100000)) is None
    assert c._decode(GZIP_MAGIC + gzip.compress(b'{"ok":') + gzip.compress(b'true}')) == {"ok": True}
    assert c._decode(GZIP_MAGIC + gzip.compress(b"x" * 20) * 2) is None
    assert c._decode(GZIP_MAGIC + gzip.compress(b"{}")[:-1]) is None


@pytest.mark.asyncio
async def test_subscription_reports_closed():
    sub = EventSubscription()
    waiter = asyncio.create_task(sub.get())
    await asyncio.sleep(0)
    sub.close(ConnectionLost("connection closed"))
    with pytest.raises(ConnectionLost):
        await asyncio.wait_for(waiter, 1)
    with pytest.raises(ConnectionLost):
        await sub.get(timeout=1)


@pytest.mark.asyncio
async def test_reader_reports_closed():
    class ClosedSocket:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    c = BatClient(SimpleNamespace(name="fixture", writes=False, orchestrate=False), device_id="fixture")
    sub = c.subscribe()
    await c._read_loop(ClosedSocket())
    with pytest.raises(ConnectionLost):
        await sub.get()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
async def test_bounded_capture(stream):
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c",
        f"import sys; sys.{stream}.write('x' * 1000000)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    with pytest.raises(ValueError, match="capture limit"):
        await asyncio.wait_for(capture(proc, 4096), 3)
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_capture_timeout():
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(10)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(capture(proc), 0.05)
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_checkpoint_capture_normal_and_bounded():
    assert await _run((sys.executable, "-c", "print('ordinary')")) == "ordinary"
    with pytest.raises(AmbiguousOutcome, match="capture limit"):
        await _run((sys.executable, "-c", "print('x' * 2000000)"))


@pytest.mark.asyncio
async def test_verifier_capture_bounded(tmp_path):
    verifier = ObservedVerifier(VerificationSettings({}, {}))
    assert await verifier._run("fixture", str(tmp_path), (sys.executable, "-c", "print('ordinary')")) == (0, "ordinary")
    with pytest.raises(ValueError):
        await verifier._run("fixture", str(tmp_path), (sys.executable, "-c", "print('x' * 1000000)"))


@pytest.mark.asyncio
async def test_read_retry_jitter(monkeypatch):
    bounds = []
    delays = []
    c = BatClient(SimpleNamespace(name="fixture", writes=False, orchestrate=False), device_id="fixture")

    async def disconnected():
        raise ConnectionLost("closed")

    async def closed():
        pass

    async def sleep(delay):
        delays.append(delay)

    def uniform(low, high):
        bounds.append((low, high))
        return high / 2

    monkeypatch.setattr(c, "connect", disconnected)
    monkeypatch.setattr(c, "close", closed)
    monkeypatch.setattr(client, "random", SimpleNamespace(uniform=uniform))
    monkeypatch.setattr(client, "asyncio", SimpleNamespace(sleep=sleep))
    with pytest.raises(ConnectionLost):
        await c._invoke_checked("workspace:load", {}, None)
    assert bounds == [(0, 0.5), (0, 1.0)]
    assert delays == [0.25, 0.5]


def test_validate_opened_file_metadata(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_text("fixture-value")
    path.chmod(0o600)
    real_fstat = os.fstat

    def changed_metadata(fd):
        info = real_fstat(fd)
        return SimpleNamespace(st_mode=info.st_mode | 0o040, st_uid=info.st_uid,
                               st_size=info.st_size, st_dev=info.st_dev, st_ino=info.st_ino)

    if os.name == "nt":
        pytest.skip("POSIX permissions")
    monkeypatch.setattr(_private_files, "os", SimpleNamespace(**{**vars(os), "fstat": changed_metadata}))
    with pytest.raises(TokenUnavailable):
        _resolve_token_ref(f"file:{path}", "")


def test_owner_check_optional(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_text("fixture-value")
    path.chmod(0o600)
    monkeypatch.setattr(_private_files, "os", SimpleNamespace(**{
        key: value for key, value in vars(os).items() if key != "getuid"
    }))
    assert _resolve_token_ref(f"file:{path}", "") == "fixture-value"


def test_redaction_precedes_truncation(tmp_path):
    audit = Audit(SafetyConfig(audit_preview_chars=24), tmp_path / "audit")
    audit.record(text="token='short-value' ordinary")
    assert json.loads(audit.path.read_text())["text_preview"] == "token='[redacted]' ordin"


@pytest.mark.asyncio
async def test_locked_checkpoint_capture(tmp_path):
    from bat_agent_connector.checkpoints import _run_locked

    calls = []

    async def check():
        calls.append(True)

    script = "import sys; print('{\"locked\": true}', flush=True); sys.stdin.readline(); print('ordinary')"
    assert await _run_locked((sys.executable, "-c", script), check, 3) == "ordinary"
    assert calls == [True]
    with pytest.raises(AmbiguousOutcome, match="capture limit"):
        await _run_locked((sys.executable, "-c", script.replace("print('ordinary')", "print('x' * 2000000)")), check, 3)
    with pytest.raises(AmbiguousOutcome, match="timed out"):
        await _run_locked((sys.executable, "-c", "import time; time.sleep(10)"), check, 0.05)


@pytest.mark.asyncio
async def test_session_wait_reconnects_and_rechecks(monkeypatch):
    from bat_agent_connector import service

    sub = EventSubscription()
    sub.close(ConnectionLost("closed"))
    calls = []
    c = SimpleNamespace(connected=False, subscribe=lambda *args, **kwargs: sub,
                        unsubscribe=lambda value: calls.append("unsubscribe"))

    async def connect():
        calls.append("connect")
        c.connected = True
        sub._closed = None

    async def resolve(*args):
        return {"id": "fixture-session"}, None

    async def meta(*args):
        calls.append("meta")
        return {"isStreaming": not c.connected}

    c.connect = connect
    monkeypatch.setattr(service, "_resolve_session", resolve)
    monkeypatch.setattr(service, "_meta", meta)
    result = await service.session_wait(SimpleNamespace(client=lambda host: c), "fixture", "fixture-session",
                                        require_new=True)
    assert result["status"] == "idle"
    assert calls == ["meta", "connect", "meta", "unsubscribe"]


def test_gzip_decompression_uses_output_cap(monkeypatch):
    limits = []
    zlib_module = client.zlib

    class Decoder:
        def __init__(self, wbits):
            self.decoder = zlib_module.decompressobj(wbits)

        def decompress(self, data, max_length):
            limits.append(max_length)
            return self.decoder.decompress(data, max_length)

        @property
        def eof(self):
            return self.decoder.eof

        @property
        def unused_data(self):
            return self.decoder.unused_data

    monkeypatch.setattr(client, "zlib", SimpleNamespace(decompressobj=Decoder,
                        MAX_WBITS=zlib_module.MAX_WBITS, error=zlib_module.error))
    c = BatClient(SimpleNamespace(writes=False, orchestrate=False), device_id="fixture", max_frame=32)
    assert c._decode(GZIP_MAGIC + gzip.compress(b"x" * 100000)) is None
    assert limits == [33]


@pytest.mark.asyncio
async def test_capture_preserves_both_streams():
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c",
        "import sys; sys.stdout.write('ordinary output'); sys.stderr.write('ordinary error')",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    assert await capture(proc, 4096) == (b"ordinary output", b"ordinary error")
