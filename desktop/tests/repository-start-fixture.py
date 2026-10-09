"""Published-version UI with actual central receipts and temporary Git; no live provider."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from bat_agent_connector import api_auth, registry
from bat_agent_connector.config import parse_config
from bat_agent_connector.errors import InvokeTimeout
from bat_agent_connector.task_daemon import TaskDaemon
from tests.fakegithub import TOKEN as GH_TOKEN
from tests.fakegithub import FakeGitHub
from tests.mockbat import TOKEN, MockBat
from tests.test_checkpoints import RealGitLog, bat_writes, git, snapshot
from tests.test_repository_sync import Runner


async def main():
    with tempfile.TemporaryDirectory(prefix='batc-published-ui-') as temporary:
        root = Path(temporary)
        os.environ.update(BATC_CONFIG_DIR=str(root / 'config'), BATC_STATE_DIR=str(root / 'state'),
                          BATC_TEST_TOKEN=TOKEN, REPO_FAKE_TOKEN=GH_TOKEN)
        os.environ.pop('BATC_DEVICE_ID', None)
        human, remote, managed = root / 'human', root / 'remote.git', root / 'managed'
        human.mkdir()
        managed.mkdir()
        git(human, 'init', '-q', '-b', 'main')
        git(human, 'config', 'user.name', 'fixture')
        git(human, 'config', 'user.email', 'fixture@example.invalid')
        (human / 'hello.txt').write_text('published bytes\n')
        git(human, 'add', '.')
        git(human, 'commit', '-qm', 'published')
        sha = git(human, 'rev-parse', 'HEAD')
        git(root, 'clone', '--bare', '--no-hardlinks', str(human), str(remote))
        (human / 'hello.txt').write_text('unpublished human edit\n')
        before, remote_before = snapshot(human), git(remote, 'for-each-ref')
        mock, gh = MockBat(), FakeGitHub()
        await mock.start()
        gh.start()
        def provide(method, path, _):
            if method == 'GET' and path == '/repos/o/r/git/ref/heads/main':
                gh.script.append(('GET', re.escape(path) + '$', 200, {},
                                  {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': sha}}))
        gh.before_request = provide
        raw = {'hosts': {'h1': {'url': mock.url, 'fingerprint': mock.fingerprint, 'token_ref': 'env:BATC_TEST_TOKEN',
               'writes': True, 'orchestrate': True, 'orchestrate_register_tabs': False, 'orchestrate_max_sessions': 4,
               'managed_roots': [str(managed)]}}, 'safety': {'write_min_interval_s': 0},
               'github': {'token_ref': 'env:REPO_FAKE_TOKEN', 'api_url': gh.url, 'repos': [{'repository': 'o/r',
               'sync': {'remote_url': str(remote), 'bindings': [{'host': 'h1', 'workspace_id': 'ws-1'}]}}]}}
        mock.ws_doc['workspaces'][0]['folderPath'] = str(human)
        mock.git_logs = RealGitLog()
        mock.handlers['git:branch'] = lambda p: git(p['cwd'], 'branch', '--show-current')
        mock.echo_sends = True
        original_workspace = copy.deepcopy(mock.ws_doc)
        daemon = TaskDaemon(parse_config(raw), root / 'journal.db')
        daemon.ops.context['git_runner'] = Runner()
        token = api_auth.issue(daemon.journal.db, 'published-browser', ['observe', 'start'])
        server = await asyncio.start_server(daemon._handle, '127.0.0.1', 0)
        worker = asyncio.create_task(daemon.ops.loop(0.1))
        print(json.dumps({'port': server.sockets[0].getsockname()[1], 'token': token, 'sha': sha}), flush=True)
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                command = json.loads(line)
                if command['action'] == 'stop':
                    break
                if command['action'] == 'writes':
                    daemon.fleet.config.host('h1').writes = command['enabled']
                elif command['action'] == 'lose-send':
                    mock.echo_sends = False
                    client, original = daemon.fleet.client('h1'), daemon.fleet.client('h1').invoke
                    async def lose(channel, *args, _original=original, **kwargs):
                        result = await _original(channel, *args, **kwargs)
                        if channel == 'claude:send-message':
                            raise InvokeTimeout('fixture actual send ACK lost')
                        return result
                    client.invoke = lose
                elif command['action'] == 'verify':
                    op = daemon.ops.get(command['operation_id'])
                    assert op['actor'] == 'published-browser' and op['action'] == 'repository.continue'
                    assert op['params']['source_sha'] == sha and op['params']['prompt'] == command['prompt']
                    assert op['status'] == command['status'], op
                    assert len(daemon.ops.list()['operations']) == command['operations']
                    sid = op['external_refs']['session_id']
                    assert registry.get('h1', sid)['start_operation_id'] == op['operation_id']
                    assert git(op['external_refs']['worktree_path'], 'rev-parse', 'HEAD') == sha
                    assert Path(op['external_refs']['worktree_path'], 'hello.txt').read_text() == 'published bytes\n'
                    frames = bat_writes(mock)
                    assert len(frames) == command['frames'], frames
                    assert snapshot(human) == before and git(remote, 'for-each-ref') == remote_before
                    assert mock.ws_doc == original_workspace
                    assert all(method == 'GET' for method, _, _ in gh.requests), gh.requests
                else:
                    raise ValueError('Unknown fixture action')
                print(json.dumps({'ok': True}), flush=True)
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
            gh.stop()


if __name__ == '__main__':
    asyncio.run(main())
