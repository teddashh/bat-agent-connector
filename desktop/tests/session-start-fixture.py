"""Standalone start UI against real central operations; all host effects use MockBat."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

from bat_agent_connector import api_auth, platform_files, registry
from bat_agent_connector.errors import InvokeTimeout
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config
from tests.mockbat import TOKEN, MockBat

CHANNELS = {'worktree:create', 'claude:start-session', 'claude:send-message', 'worktree:remove', 'workspace:save'}


async def main():
    with tempfile.TemporaryDirectory(prefix='batc-start-ui-') as temporary:
        root = Path(temporary)
        platform_files.ensure_private_directory(root / "state")
        platform_files.ensure_private_directory(root / "config")
        os.environ.update(BATC_CONFIG_DIR=str(root / 'config'), BATC_STATE_DIR=str(root / 'state'), BATC_TEST_TOKEN=TOKEN)
        os.environ.pop('BATC_DEVICE_ID', None)
        mock = MockBat()
        await mock.start()
        mock.handlers['git:log'] = lambda params: [{'hash': 'a' * 40}]
        original_workspace, original_meta = copy.deepcopy(mock.ws_doc), copy.deepcopy(mock.metas)
        config = make_config(mock, writes=True, orchestrate=True, managed_roots=['/srv'], safety={'write_min_interval_s': 0})
        daemon = TaskDaemon(config, root / 'journal.db')
        token = api_auth.issue(daemon.journal.db, 'start-browser', ['observe', 'start'])
        server = await asyncio.start_server(daemon._handle, '127.0.0.1', 0)
        worker = asyncio.create_task(daemon.ops.loop(0.1))
        print(json.dumps({'port': server.sockets[0].getsockname()[1], 'token': token}), flush=True)
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                command = json.loads(line)
                if command['action'] == 'stop':
                    break
                if command['action'] == 'writes':
                    config.host('h1').writes = command['enabled']
                    print(json.dumps({'writes': command['enabled']}), flush=True)
                elif command['action'] == 'lose-send':
                    client = daemon.fleet.client('h1')
                    original = client.invoke
                    async def lose(channel, *args, _original=original, **kwargs):
                        result = await _original(channel, *args, **kwargs)
                        if channel == 'claude:send-message':
                            raise InvokeTimeout('fixture actual send ACK lost')
                        return result
                    client.invoke = lose
                    print(json.dumps({'send_reply_loss': True}), flush=True)
                elif command['action'] == 'verify':
                    operations = daemon.ops.list()['operations']
                    assert len(operations) == command['operations'], operations
                    op = daemon.ops.get(command['operation_id'])
                    assert op['actor'] == 'start-browser' and op['action'] == 'session.start'
                    assert op['target'] == {'host': 'h1', 'workspace': 'ws-1'}
                    assert op['params']['prompt'] == command['prompt']
                    assert op['status'] == command['status'], op
                    sid = op['external_refs']['session_id']
                    assert registry.get('h1', sid)['start_operation_id'] == op['operation_id']
                    frames = [f for f in mock.invokes if f['channel'] in CHANNELS]
                    assert len(frames) == command['frames'], frames
                    assert mock.ws_doc == original_workspace
                    assert all(mock.metas[s] == meta for s, meta in original_meta.items())
                    sends = [f for f in frames if f['channel'] == 'claude:send-message' and f['params']['sessionId'] == sid]
                    assert len(sends) == 1 and sends[0]['params']['prompt'] == command['prompt']
                    if op['status'] == 'uncertain':
                        assert op['external_refs']['start_result']['started'] is True
                        steps = {s['name']: s['status'] for s in op['steps']}
                        assert steps['session.start'] == 'succeeded' and steps['send'] == 'uncertain', steps
                    print(json.dumps({'verified': True}), flush=True)
                else:
                    raise ValueError('Unknown fixture action')
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            server.close()
            await server.wait_closed()
            await daemon.artifact_store.close_reaper()
            await daemon.inventory.close()
            await daemon.fleet.close()
            daemon.journal.close()
            await mock.stop()


if __name__ == '__main__':
    asyncio.run(main())
