"""Real central scheduler and MockBat frames; checked Git reads use temporary local repositories."""
from __future__ import annotations

import asyncio
import json
import subprocess

import pytest

from bat_agent_connector import api_auth, checkpoints, registry, resource_policy, service
from bat_agent_connector import worktree_merge_host as helper
from bat_agent_connector import worktree_merge_operations as merge
from bat_agent_connector.errors import InvokeTimeout, ResourceReadOnly
from bat_agent_connector.operations import OperationError, OperationService
from bat_agent_connector.task_journal import Journal
from tests import test_api_v1 as api
from tests.conftest import adopt
from tests.operation_helpers import settle_operations

daemon, served = api.daemon, api.served
P = api_auth.Principal('merge-caller', frozenset({'observe', 'integrate'}))
SID = 'merge-managed-0001'


def git(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, check=True).stdout.strip()


class LocalRunner:
    def available(self, host):
        return host == 'h1'

    async def run(self, host, script, timeout_s):
        return await checkpoints._run(('sh', '-c', script), timeout_s)


@pytest.fixture
def carriers(daemon, mock, tmp_path):
    origin, source = tmp_path / 'clone', tmp_path / 'worktree'
    origin.mkdir()
    git(origin, 'init', '-b', 'main')
    git(origin, 'config', 'user.name', 'Fixture')
    git(origin, 'config', 'user.email', 'fixture@example.invalid')
    (origin / 'base').write_text('base')
    git(origin, 'add', '.')
    git(origin, 'commit', '-m', 'base')
    git(origin, 'worktree', 'add', '-b', 'bat/feature', str(source))
    (source / 'feature').write_text('fixed result')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'feature')
    daemon.fleet.config.host('h1').managed_roots = [str(tmp_path)]
    daemon.ops.context['git_runner'] = LocalRunner()
    mock.ws_doc['workspaces'].append({'id': 'ws-merge', 'name': 'merge-fixture', 'folderPath': str(origin)})
    mock.ws_doc['terminals'].append({'id': SID, 'workspaceId': 'ws-merge', 'agentPreset': 'claude-code-worktree',
                                   'cwd': str(source), 'worktreePath': str(source), 'worktreeBranch': 'bat/feature'})
    mock.metas[SID] = {'cwd': str(source), 'isStreaming': False, 'sdkSessionId': 'fixed-runtime'}
    mock.states[SID] = {'isStreaming': False, 'messages': []}
    mock.worktrees[SID] = {'worktreePath': str(source), 'branchName': 'bat/feature', 'sourceBranch': 'main',
                           'mergedKind': 'ahead', 'merged': False}
    mock.handlers['git:getRoot'] = lambda p: git(p['cwd'], 'rev-parse', '--show-toplevel')
    mock.handlers['git:branch'] = lambda p: git(p['cwd'], 'branch', '--show-current')
    mock.handlers['git:log'] = lambda p: [{'hash': git(p['cwd'], 'rev-parse', 'HEAD')}]
    mock.handlers['git:status'] = lambda p: []  # deliberately cannot prove successful Git execution
    def perform(p):
        git(origin, 'merge', '--no-ff', '--no-edit', 'bat/feature')
        return {'success': True, 'strategy': 'merge', 'branchName': 'bat/feature', 'sourceBranch': 'main'}
    mock.handlers['worktree:merge'] = perform
    adopt(SID, cwd=str(source), origin_cwd=str(origin), worktree_path=str(source), branch='bat/feature',
          agent_preset='claude-code-worktree', workspace_id='ws-merge')
    return origin, source


def intent(**kw):
    return {'action': 'worktree.merge', 'target': {'host': 'h1', 'session_id': SID}, 'params': {}, 'idempotency_key': 'merge-key', **kw}


async def create(d, **kw):
    op, _ = d.ops.create(P, **intent(**kw))
    await settle_operations(d.ops)
    return d.ops.get(op['operation_id'])


def reopen(d):
    d.journal.close()
    d.journal = Journal(d.journal.path)
    ops = OperationService(d.journal, actions=list(d.ops.actions.values()))
    ops.context.update(d.ops.context)
    d.ops = ops
    d.coordinator.journal = d.adapter.journal = d.journal


async def test_merge_exact_receipts_real_git_and_named_replay(daemon, mock, carriers):
    origin, source = carriers
    original_head = git(origin, 'rev-parse', 'HEAD')
    out = await create(daemon, target={'host': 'h1', 'session_id': 'merge-managed'})
    assert out['status'] == 'succeeded', out
    assert out['result']['merged_now'] is True and out['result']['result']['strategy'] == 'merge'
    assert git(origin, 'rev-parse', 'HEAD') != original_head
    assert (origin / 'feature').read_bytes() == (source / 'feature').read_bytes()
    assert not merge._document().get('carrier_writers')
    assert [s['name'] for s in out['steps']] == ['merge.prepare', 'merge.reserve', 'merge.frame', 'merge.release']
    daemon.fleet.config.host('h1').orchestrate = False
    daemon.ops.context['git_runner'] = None
    replay = await create(daemon, target={'host': 'h1', 'session_id': 'merge-managed'})
    assert replay['operation_id'] == out['operation_id'] and mock.channels().count('worktree:merge') == 1
    with pytest.raises(OperationError, match='TIER_DISABLED'):
        await create(daemon, idempotency_key='new')
    await daemon.fleet.close()


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'dirty', 'root', 'unavailable'])
async def test_failed_positive_git_proof_never_uses_bat_empty_status(daemon, mock, carriers, monkeypatch, failure):
    origin, source = carriers
    if failure == 'dirty':
        (source / 'uncommitted').write_text('do not merge')
    elif failure == 'root':
        git(source, 'config', 'core.worktree', str(origin / 'wrong'))
    elif failure == 'unavailable':
        daemon.ops.context['git_runner'] = None
    else:
        async def failed(*args, **kwargs):
            if failure == 'timeout':
                raise asyncio.TimeoutError()
            return json.dumps({'ok': False, 'code': 'MERGE_GIT_UNAVAILABLE'})
        monkeypatch.setattr(daemon.ops.context['git_runner'], 'run', failed)
    if failure == 'unavailable':
        with pytest.raises(OperationError, match='MERGE_GIT_UNAVAILABLE'):
            await create(daemon)
    else:
        out = await create(daemon)
        assert out['status'] == ('succeeded' if failure == 'dirty' else 'failed'), out
        if failure == 'dirty':
            assert out['result']['merged_now'] is False
    assert not api.write_frames(mock)
    assert not merge._document().get('carrier_writers')
    await daemon.fleet.close()


@pytest.mark.parametrize('change', ['manual', 'task', 'pending', 'streaming', 'unknown_idle', 'neighbor', 'operation'])
async def test_positive_managed_idle_and_all_consumers_required(daemon, mock, carriers, change):
    origin, source = carriers
    if change == 'manual':
        registry.registry_path().unlink()
    elif change == 'task':
        task = daemon.journal.submit(project='p', host='h1', workspace='merge-fixture', original_words='task', idempotency_key='task')
        daemon.journal.db.execute('UPDATE tasks SET session_id=?,paused=1 WHERE task_id=?', (SID, task['task_id']))
    elif change == 'pending':
        mock.states[SID]['pendingPermission'] = {'id': 'pending'}
    elif change == 'streaming':
        mock.metas[SID]['isStreaming'] = True
    elif change == 'unknown_idle':
        mock.metas[SID].pop('isStreaming')
    elif change == 'neighbor':
        mock.ws_doc['terminals'].append({'id': 'manual-neighbor', 'cwd': str(origin), 'agentPreset': 'claude-code'})
    else:
        other, _ = daemon.ops.create(api_auth.Principal('other', frozenset({'operate'})), action='session.send',
                                    target={'host': 'h1', 'session_id': SID}, params={'text': 'pending'}, idempotency_key='pending')
        daemon.ops.db.execute("UPDATE operations SET status='uncertain',next_run_at=99999999999 WHERE operation_id=?", (other['operation_id'],))
    out = await create(daemon)
    assert out['status'] == 'failed', out
    assert not api.write_frames(mock)
    await daemon.fleet.close()


@pytest.mark.parametrize('change', ['task', 'registry', 'new_neighbor', 'head', 'dirty'])
async def test_final_awaited_reads_followed_by_synchronous_owner_gate(daemon, mock, carriers, monkeypatch, change):
    origin, source = carriers
    original = merge.proof
    count = 0
    async def alter(*args, **kwargs):
        nonlocal count
        p = await original(*args, **kwargs)
        count += 1
        if count == 3:  # final frame's last asynchronous proof
            if change == 'task':
                t = daemon.journal.submit(project='p', host='h1', workspace='merge-fixture', original_words='new', idempotency_key='new-task')
                daemon.journal.db.execute('UPDATE tasks SET session_id=?,paused=1 WHERE task_id=?', (SID, t['task_id']))
            elif change == 'registry':
                registry.update('h1', SID, role='reviewer')
            elif change == 'new_neighbor':
                # Simulate another existing process's newly durable consumer after observation.
                path = registry.registry_path()
                doc = json.loads(path.read_text())
                doc['sessions'].append({**registry.get('h1', SID), 'session_id': 'new-consumer'})
                registry._write_document(path, doc)
            elif change == 'head':
                p['source']['head'] = 'b' * 40
            else:
                p['destination']['clean'] = False
        return p
    monkeypatch.setattr(merge, 'proof', alter)
    out = await create(daemon)
    assert out['status'] in {'failed', 'needs_attention'}, out
    assert not api.write_frames(mock)
    await daemon.fleet.close()


@pytest.mark.parametrize('lost', ['merge', 'rehydrate'])
async def test_lost_ack_cancel_reopen_retains_both_carriers_without_resend(daemon, mock, carriers, monkeypatch, lost):
    origin, source = carriers
    if lost == 'rehydrate':
        status = mock.worktrees.pop(SID)
        mock.handlers['claude:get-worktree-status'] = lambda p: status
        def rehydrate(p):
            mock.worktrees[SID] = status
            return {'success': True}
        mock.handlers['worktree:rehydrate'] = rehydrate
    client = daemon.fleet.client('h1')
    real = client.invoke
    async def lose(channel, *args, **kw):
        r = await real(channel, *args, **kw)
        if channel == 'worktree:' + lost:
            raise InvokeTimeout('fixture lost positive reply')
        return r
    monkeypatch.setattr(client, 'invoke', lose)
    out = await create(daemon)
    assert out['status'] == 'uncertain', out
    assert out['external_refs']['merge_result']['merged_now'] is None
    for path in (origin, source, origin / 'new-subdir'):
        with pytest.raises(ResourceReadOnly, match='MERGE_RESERVED'):
            merge.check_writer('h1', 'new-session', workdir=str(path))
    with pytest.raises(ResourceReadOnly, match='MERGE_RESERVED'):
        registry.reserve('h1', {'session_id': 'new-session', 'cwd': str(origin)}, 10)
    with pytest.raises(ResourceReadOnly, match='MERGE_RESERVED'):
        await service.session_send(daemon.fleet, 'h1', SID, 'later', confirm=True)
    tab = next(t for t in mock.ws_doc['terminals'] if t.get('id') == SID)
    stop = await resource_policy.authorize_session(daemon.fleet, 'h1', 'session.stop', tab)
    resource_policy.check_grant(stop, 'h1', 'claude:stop-session', {'sessionId': SID})
    writes = list(api.write_frames(mock))
    reopen(daemon)
    daemon.ops.db.execute("UPDATE operations SET status='needs_attention' WHERE operation_id=?", (out['operation_id'],))
    daemon.ops.cancel(P, out['operation_id'])
    await settle_operations(daemon.ops)
    assert daemon.ops.get(out['operation_id'])['status'] == 'uncertain'
    assert api.write_frames(mock) == writes and merge._document()['carrier_writers']
    await daemon.fleet.close()


async def test_rehydrate_and_merge_are_separate_frames_max_inflight_one(daemon, mock, carriers):
    status = mock.worktrees.pop(SID)
    mock.handlers['claude:get-worktree-status'] = lambda p: status
    def rehydrate(p):
        mock.worktrees[SID] = status
        return {'success': True}
    mock.handlers['worktree:rehydrate'] = rehydrate
    daemon.fleet.client('h1')._sem = asyncio.Semaphore(1)
    out = await create(daemon)
    assert out['status'] == 'succeeded', out
    assert out['result']['rehydrated'] is True
    assert [f['channel'] for f in api.write_frames(mock)] == ['worktree:rehydrate', 'worktree:merge']
    assert {s['name'] for s in out['steps']} >= set(merge.REMOTE)
    await daemon.fleet.close()


async def test_all_ack_cancel_restart_only_releases_original_marker(daemon, mock, carriers, monkeypatch):
    original = merge.release
    def fail(*a, **kw):
        raise OSError('local registry write unavailable')
    monkeypatch.setattr(merge, 'release', fail)
    out = await create(daemon)
    assert out['status'] == 'uncertain', out
    writes = list(api.write_frames(mock))
    monkeypatch.setattr(merge, 'release', original)
    daemon.fleet.config.host('h1').orchestrate = False
    reopen(daemon)
    daemon.ops.db.execute("UPDATE operations SET status='needs_attention' WHERE operation_id=?", (out['operation_id'],))
    daemon.ops.cancel(P, out['operation_id'])
    await settle_operations(daemon.ops)
    assert daemon.ops.get(out['operation_id'])['status'] == 'succeeded'
    assert api.write_frames(mock) == writes and not merge._document()['carrier_writers']
    await daemon.fleet.close()


@pytest.mark.parametrize('params', [{'force': True}, {'strategy': 'cherry-pick'}])
async def test_http_scope_and_malformed_inputs_before_frames(served, mock, carriers, params):
    d, port = served
    token = api.token(d, P.actor, 'observe', 'integrate')
    status, body = await api.http(port, 'POST', '/api/v1/operations', tok=token, body=intent(params=params))
    assert status == 422 and body['error']['code'] == 'INVALID_PARAMS'
    status, _ = await api.http(port, 'POST', '/api/v1/operations', tok=api.token(d, 'observe-only', 'observe'), body=intent())
    assert status == 403 and not api.write_frames(mock)
    assert d.ops.db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] == 0


def test_helper_checks_status_process_failure_and_timeout(tmp_path, monkeypatch):
    # Stub only this helper's subprocess dependency, never global subprocess/Popen.
    class Failing:
        returncode = 1
        def poll(self):
            return 1
        def wait(self):
            return 1
    class ProcessModule:
        @staticmethod
        def Popen(*args, **kwargs):
            return Failing()
    monkeypatch.setattr(helper, 'subprocess', ProcessModule)
    with pytest.raises(ValueError, match='MERGE_GIT_UNAVAILABLE'):
        helper.git(str(tmp_path), 'status', '--porcelain=v1')
    class Hanging(Failing):
        def poll(self):
            return None
        def kill(self):
            self.killed = True
    process = Hanging()
    ProcessModule.Popen = lambda *a, **kw: process
    monkeypatch.setattr(helper, 'DEADLINE', 0)
    with pytest.raises(ValueError, match='MERGE_GIT_UNAVAILABLE'):
        helper.git(str(tmp_path), 'status', '--porcelain=v1')
    assert process.killed
