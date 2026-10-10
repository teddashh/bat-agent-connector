from __future__ import annotations

import json
from pathlib import Path

import pytest

from bat_agent_connector.errors import InvokeTimeout
from bat_agent_connector.operations import OperationError
from tests.test_artifacts import LocalArtifactHost, action, upload
from tests.test_checkpoints import bat_writes, git, snapshot
from tests.test_repository_sync import STARTER, envelope, preview, settle
from tests.test_repository_sync import world as world  # noqa: F401


@pytest.fixture(autouse=True)
async def close_artifact_store(world):
    yield
    await world['d'].artifact_store.close_reaper()


async def project(w):
    op = await action(w['d'], 'project.create', params={'name': 'Dispatch fixture', 'repositories': ['o/r']})
    return op['result']['project_id']


async def prepared(w, **params):
    pid = await project(w)
    ref = await upload(w['d'], b'fixed input\n')
    w['d'].ops.context['artifact_host'] = LocalArtifactHost()
    request = envelope(await preview(w), artifacts=[ref], project_id=pid, **params)
    request['preconditions']['expected_project_version'] = 1
    return request, ref


@pytest.mark.parametrize('agent', ['claude', 'codex'])
async def test_project_dispatch_materializes_before_start_and_preserves_original(world, mock, agent):
    request, ref = await prepared(world, prompt='  Original words\nKeep them.  ', model='fixture-model', agent=agent)
    before = snapshot(world['human'])
    remote_before = git(world['remote'], 'for-each-ref')
    op, _ = world['d'].ops.create(STARTER, **request)
    op = await settle(world, op)
    assert op['status'] == 'succeeded', (op['error_code'], op['status_reason'], op['steps'])
    path = Path(op['result']['worktree_path'], '.batc-inputs', f"{ref['artifact_id']}-r1", 'notes.txt')
    assert path.read_bytes() == b'fixed input\n'
    start = next(f for f in bat_writes(mock) if f['channel'] == 'claude:start-session')
    assert start['params']['options']['model'] == 'fixture-model'
    names = [s['name'] for s in op['steps']]
    assert next(i for i, s in enumerate(names) if '.readback.' in s) < names.index('session.start')
    send = next(f for f in bat_writes(mock) if f['channel'] == 'claude:send-message')
    assert request['params']['prompt'] in send['params']['prompt']
    assert ref['digest'] in send['params']['prompt'] and str(path.relative_to(path.parents[2])) in send['params']['prompt']
    assert op['external_refs']['project_id'] == request['params']['project_id']
    assert not world['d'].journal.db.execute('SELECT 1 FROM work_items').fetchone()
    assert snapshot(world['human']) == before and git(world['remote'], 'for-each-ref') == remote_before


@pytest.mark.parametrize('change', ['archived', 'repository', 'version'])
async def test_project_changes_before_admission_or_execution_never_dispatch(world, mock, change):
    request, _ = await prepared(world)
    op, _ = world['d'].ops.create(STARTER, **request)
    params = {'archived': True} if change == 'archived' else {'repositories': ['other/repo']} if change == 'repository' else {'name': 'Renamed'}
    # Execute the competing edit before the accepted start gets its first turn.
    from tests.test_artifacts import PERSON
    edit, _ = world['d'].ops.create(PERSON, action='project.update', target={'project_id': request['params']['project_id']},
        params=params, preconditions={'expected_version': 1}, idempotency_key='edit-project')
    await world['d'].ops._execute(edit['operation_id'])
    with pytest.raises(OperationError):
        world['d'].ops.create(STARTER, **{**request, 'idempotency_key': 'new'})
    op = await settle(world, op)
    assert op['status'] == 'failed'
    assert not world['runner'].scripts and not bat_writes(mock)
    assert not world['d'].ops.context['artifact_host'].calls


async def test_repository_outside_project_and_missing_version_are_refused(world):
    request, _ = await prepared(world)
    request['params']['project_id'] = (await action(world['d'], 'project.create', params={'name': 'Other', 'repositories': ['other/repo']}))['result']['project_id']
    with pytest.raises(OperationError, match='does not belong'):
        world['d'].ops.create(STARTER, **request)
    request['preconditions'].pop('expected_project_version')
    with pytest.raises(OperationError):
        world['d'].ops.create(STARTER, **request)


@pytest.mark.parametrize('broken', ['digest', 'missing', 'receiver', 'tampered_before_send'])
async def test_unverified_inputs_block_start_or_first_prompt(world, mock, monkeypatch, broken):
    request, ref = await prepared(world)
    if broken in {'digest', 'missing'}:
        request['params']['artifacts'][0] = {**ref, **({'digest': '0' * 64} if broken == 'digest' else {'revision': 999})}
        with pytest.raises(OperationError):
            world['d'].ops.create(STARTER, **request)
        assert not world['runner'].scripts and not bat_writes(mock)
        return
    adapter = world['d'].ops.context['artifact_host']
    original = adapter.call
    async def call(host, data, content=b''):
        if broken == 'receiver' and data['mode'] == 'receive':
            return {'ok': False, 'code': 'ARTIFACT_DIGEST_MISMATCH'}
        return await original(host, data, content)
    monkeypatch.setattr(adapter, 'call', call)
    if broken == 'tampered_before_send':
        client = world['d'].fleet.client('h1')
        invoke = client.invoke
        async def changed(channel, *args, **kwargs):
            result = await invoke(channel, *args, **kwargs)
            if channel == 'claude:start-session':
                root = next(world['managed'].glob('batc-published-*'))
                path = next(root.glob('.bat-worktrees/*/.batc-inputs/*/notes.txt'))
                path.chmod(0o600)
                path.write_bytes(b'changed')
            return result
        monkeypatch.setattr(client, 'invoke', changed)
    op, _ = world['d'].ops.create(STARTER, **request)
    op = await settle(world, op)
    assert op['status'] in {'failed', 'needs_attention'}, op
    assert 'claude:send-message' not in mock.channels()
    assert mock.channels().count('claude:start-session') == (1 if broken == 'tampered_before_send' else 0)


async def test_lost_send_reconciles_without_retransferring_or_rereading_changed_inputs(world, mock, monkeypatch):
    request, _ = await prepared(world)
    client = world['d'].fleet.client('h1')
    original = client.invoke
    async def lose(channel, *args, **kwargs):
        result = await original(channel, *args, **kwargs)
        if channel == 'claude:send-message':
            raise InvokeTimeout('lost input prompt reply')
        return result
    monkeypatch.setattr(client, 'invoke', lose)
    op, _ = world['d'].ops.create(STARTER, **request)
    op = await settle(world, op)
    assert op['status'] == 'uncertain', op
    count = len(world['d'].ops.context['artifact_host'].calls)
    world['d'].ops.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (op['operation_id'],))
    op = await settle(world, op)
    assert op['status'] == 'succeeded', op
    assert len(world['d'].ops.context['artifact_host'].calls) == count
    assert mock.channels().count('claude:start-session') == mock.channels().count('claude:send-message') == 1


@pytest.mark.parametrize('change', ['binding', 'operation', 'head', 'missing_kind'])
async def test_artifact_helper_refuses_a_different_published_carrier(world, mock, monkeypatch, change):
    request, _ = await prepared(world)
    adapter = world['d'].ops.context['artifact_host']
    original = adapter.call
    async def call(host, data, content=b''):
        if data['mode'] == 'receive':
            data = {**data, 'published_binding': dict(data['published_binding'])}
            if change == 'binding':
                data['published_binding']['binding_digest'] = '0' * 64
            elif change == 'operation':
                git(data['clone'], 'config', 'batc.operation', 'op_' + '0' * 32)
            elif change == 'head':
                data['published_binding']['source_sha'] = '0' * 40
            else:
                data.pop('published_binding')
        return await original(host, data, content)
    monkeypatch.setattr(adapter, 'call', call)
    op, _ = world['d'].ops.create(STARTER, **request)
    op = await settle(world, op)
    assert op['status'] == 'needs_attention', op
    assert not bat_writes(mock)
    assert not list(world['managed'].glob('**/.batc-inputs'))


async def test_project_change_after_materialization_blocks_the_first_frame(world, mock, monkeypatch):
    request, _ = await prepared(world)
    adapter = world['d'].ops.context['artifact_host']
    original = adapter.call
    async def call(host, data, content=b''):
        result = await original(host, data, content)
        if data['mode'] == 'receive':
            world['d'].ops.db.execute('UPDATE projects SET version=version+1 WHERE project_id=?', (request['params']['project_id'],))
        return result
    monkeypatch.setattr(adapter, 'call', call)
    op, _ = world['d'].ops.create(STARTER, **request)
    op = await settle(world, op)
    assert op['status'] in {'failed', 'needs_attention'}, op
    assert not bat_writes(mock)


async def test_cli_and_mcp_forward_the_same_project_input_contract(world, monkeypatch):
    from bat_agent_connector import cli, task_daemon
    from bat_agent_connector.mcp_server import build_server
    from tests.operation_helpers import settle_operations
    from tests.test_api_v1 import token
    from tests.test_mcp_principal import call

    request, ref = await prepared(world, model='chosen-model')
    p, pre = request['params'], request['preconditions']
    seen = []
    def capture(method, **kw):
        seen.append((method, kw))
        return {'operation': {'status': 'accepted'}}
    with monkeypatch.context() as patch:
        patch.setattr(task_daemon, 'request', capture)
        args = cli.build_parser().parse_args(['repository', 'continue', 'o/r', 'h1', 'ws-1', '--ref', p['source_ref'],
            '--sha', p['source_sha'], '--repository-id', str(pre['repository_id']), '--binding-digest', pre['binding_digest'],
            '--prompt', p['prompt'], '--model', p['model'], '--artifact', json.dumps(ref), '--project-id', p['project_id'],
            '--project-version', '1', '--key', 'from-cli', '--confirm'])
        assert cli.cmd_repository(args) == 0
    assert seen[0][1]['params'] == {**p, 'agent': 'claude'} and seen[0][1]['preconditions'] == pre
    monkeypatch.setenv('BATC_TASK_URL', f"http://127.0.0.1:{world['port']}/rpc")
    monkeypatch.setenv('BATC_API_TOKEN', token(world['d'], 'project-starter', 'start'))
    mcp, fleet = build_server(world['d'].fleet.config, principal_only=True)
    try:
        out = await call(mcp, 'work_continue_from_repository', {**request['target'], **p, **pre,
            'idempotency_key': 'from-mcp', 'confirm': True, 'wait_s': 0})
        assert 'accepted' in out, out
        await settle_operations(world['d'].ops)
        op = next(x for x in world['d'].ops.list()['operations'] if x['action'] == 'repository.continue')
        assert op['status'] == 'succeeded', op
        assert op['params'] == {**p, 'agent': 'claude'} and op['preconditions'] == pre
    finally:
        await fleet.close()
