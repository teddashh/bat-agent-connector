"""Published project dispatch stays linked through exact Git delivery; no live providers."""
import json

from bat_agent_connector import api_auth, cleanup, execution_sources, integration, work_items
from bat_agent_connector.config import parse_config
from tests import test_repository_sync as published
from tests.test_artifacts import action
from tests.test_checkpoints import git, snapshot
from tests.test_integration import hermetic_git  # noqa: F401

world = published.world
INTEGRATOR = api_auth.Principal('integrator', frozenset({'integrate', 'observe'}))


async def test_project_published_work_links_session_worktree_and_fixed_pr_receipt(world):
    w, d = world, world['d']
    created = await action(d, 'project.create', params={'name': 'Daily trial', 'repositories': ['o/r']})
    pid = created['result']['project_id']
    pv = await published.preview(w)
    req = published.envelope(pv, project_id=pid)
    req['preconditions']['expected_project_version'] = 1
    op, _ = d.ops.create(published.STARTER, **req)
    before = work_items.project_get(d.journal.db, pid, ops=d.ops)['work']
    assert len(before) == 1 and before[0]['id'] == op['operation_id'] and not before[0]['eligible']
    op = await published.settle(w, op)
    assert op['status'] == 'succeeded', op
    unchanged = snapshot(w['human'])
    record = work_items.project_get(d.journal.db, pid, ops=d.ops)['work'][0]
    assert record['project_ids'] == [pid] and record['eligible'], record
    assert record['session_id'] == op['result']['session_id'] and record['worktree_id'].startswith('wt_')
    resource = d.inventory.observation.resource('worktree', record['worktree_id'])
    facts = execution_sources.for_worktree(d.ops, resource)
    assert facts['known_sessions'][0]['session_id'] == record['session_id']
    assert facts['work'][0]['id'] == op['operation_id']
    path = op['result']['worktree_path']
    git(path, 'config', 'user.email', 'agent@example.invalid')
    git(path, 'config', 'user.name', 'Agent')
    from pathlib import Path
    (Path(path) / 'result.txt').write_text('Project result\n')
    git(path, 'add', 'result.txt')
    git(path, 'commit', '-qm', 'Project result')
    result_sha = git(path, 'rev-parse', 'HEAD')
    git(w['remote'], 'update-ref', 'refs/heads/project-pr', w['sha'])
    git(w['remote'], 'update-ref', 'refs/pull/1/head', w['sha'])
    w['gh'].add_pr(1, w['sha'], head_ref='project-pr')
    w['gh'].track_remote(1, str(w['remote']))
    w['raw']['github']['repos'][0]['integrate'] = {'hosts': ['h1'], 'remote_url': str(w['remote'])}
    d.ops.context['github_config'] = parse_config(w['raw']).github
    selected = integration.candidates(d.ops, 'h1', source_kind='execution', source_id=op['operation_id'])['selected']
    assert selected['id'] == record['id'] and selected['eligible']
    preview_op, _ = d.ops.create(INTEGRATOR, action='integration.preview',
        target={'host': 'h1', 'repository': 'o/r', 'pull_number': 1},
        params={'sources': [{'kind': 'execution', 'id': op['operation_id']}]}, idempotency_key='project-preview')
    preview_op = await published.settle(w, preview_op)
    assert preview_op['status'] == 'succeeded', preview_op
    doc = preview_op['result']
    assert doc['ready'] and doc['sources'][0]['pinned_sha'] == result_sha, doc
    applied, _ = d.ops.create(INTEGRATOR, **integration.apply_request(doc))
    applied = await published.settle(w, applied)
    assert applied['status'] == 'succeeded', applied
    record = work_items.project_get(d.journal.db, pid, ops=d.ops)['work'][0]
    assert record['delivered_to'][0]['repository'] == 'o/r'
    assert record['delivered_to'][0]['pinned_sha'] == result_sha
    assert record['result']['status'] == 'unverified'  # integration does not approve the task
    items, operations, previews, *_ = cleanup._all(d.ops)
    item = items[record['worktree_id']]
    observed = {'head': result_sha, 'results': [result_sha]}
    assert cleanup._coverage(d.ops, item, observed)['delivered']
    cleanup._consumers(d.ops, item, operations, previews)
    assert 'CONTENT_REQUIRED' in {reason['code'] for reason in item['reasons']}
    # A path or branch match alone cannot give another creation slot delivery credit.
    assert not cleanup._coverage(d.ops, {**item, 'resource_id': 'wt_'+'0'*32}, observed)['delivered']
    branch = next(value for value in items.values() if value.get('worktree_id') == record['worktree_id'] and value['kind'] == 'local_branch')
    assert cleanup._coverage(d.ops, branch, observed)['delivered']
    assert snapshot(w['human']) == unchanged
    assert not d.journal.db.execute('SELECT 1 FROM tasks').fetchone()
    # The project binding is explicit. Renaming a project cannot assign another project's work.
    other = await action(d, 'project.create', params={'name': 'Same repository', 'repositories': ['o/r']})
    assert not work_items.project_get(d.journal.db, other['result']['project_id'], ops=d.ops)['work']
    assert json.loads(d.journal.db.execute('SELECT sources FROM integration_previews WHERE preview_id=?',
                                          (doc['preview_id'],)).fetchone()[0])[0]['lineage']['action'] == 'repository.continue'
