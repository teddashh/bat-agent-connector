"""Background read reconciliation belongs to the same fleet owner as operations."""
import asyncio
from contextlib import suppress

import pytest

from bat_agent_connector import delivery, pr_delivery
from tests import test_delivery as fixtures

gh = fixtures.gh
make_daemon = fixtures.make_daemon


@pytest.mark.parametrize("kind,module", [("metadata", pr_delivery), ("deployments", delivery)])
@pytest.mark.parametrize("owns", [True, False])
async def test_background_reconciliation_does_not_begin_without_fleet_owner(make_daemon, monkeypatch, kind, module, owns):
    daemon = make_daemon()
    monkeypatch.setattr(daemon.journal, "owner_valid", lambda: owns)
    calls = []
    observed = asyncio.Event()

    async def reconcile(ops):
        calls.append(ops)
        observed.set()

    monkeypatch.setattr(module, "reconcile_" + kind, reconcile)
    task = asyncio.create_task(getattr(daemon, "reconcile_" + kind)())
    try:
        if owns:
            await asyncio.wait_for(observed.wait(), 2)
        else:
            await asyncio.sleep(0)  # coroutine reaches its first scheduled wait without provider calls
        assert calls == ([daemon.ops] if owns else [])
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
