import {test} from 'node:test';
import assert from 'node:assert/strict';
import {groupedSessions, workspaceGroup, matchesSession, runtimeStale, sessionActivity} from '../src/state/sessions.js';

test('workspace groups keep host and recorded workspace identity distinct', () => {
  const rows = [{host: 'a', workspace: 'same', workspace_id: 'one'}, {host: 'a', workspace: 'same', workspace_id: 'two'},
    {host: 'b', workspace: 'same', workspace_id: 'one'}, {host: 'a', workspace: 'same'}, {host: 'a'}];
  assert.equal(groupedSessions(rows).length, 5);
  assert.equal(workspaceGroup({...rows[0], workspace: 'renamed'}).key, workspaceGroup(rows[0]).key);
  assert.notEqual(workspaceGroup(rows[0]).key, workspaceGroup(rows[3]).key);
});
test('loaded search matches factual fields and all query words without project inference', () => {
  const row = {host: 'node-a', workspace: 'Research', session_id: 'sid-exact', worktree_branch: 'fix/42', title: 'Repair parser'};
  assert.equal(matchesSession(row, ' NODE-a repair '), true);
  assert.equal(matchesSession(row, 'sid-exact fix/42'), true);
  assert.equal(matchesSession(row, 'project-research'), false);
});
test('idle, unknown and missing sessions are never inferred completed', () => {
  assert.equal(sessionActivity({loaded: false, streaming: false}).key, 'obs_value_not_streaming');
  assert.equal(sessionActivity({}).key, 'sessions_activity_unknown');
  assert.equal(sessionActivity({streaming: true, stale: true}).key, 'sessions_stale');
  assert.equal(sessionActivity({streaming: false, state: {enumeration: 'gone'}}).key, 'sessions_not_seen');
  assert.equal(sessionActivity({state: {lifecycle: 'ended'}}).key, 'obs_value_ended');
  assert.equal(sessionActivity({pending: {kind: 'ask_user'}, streaming: false}).key, 'pending_ask_user');
});

test('fresh enumeration does not freshen stale runtime or pending evidence', () => {
  const row = {stale: false, streaming: true, fields_stale: true, state: {enumeration: 'present'}};
  assert.equal(sessionActivity(row).key, 'sessions_stale');
  assert.equal(sessionActivity({...row, pending: {kind: 'ask_user'}}).key, 'pending_ask_user');
  assert.equal(runtimeStale({...row, pending: {kind: 'ask_user'}}), true);
  assert.equal(sessionActivity({streaming: true, state: {evidence: {activity: {stale: true}}}}).key, 'sessions_stale');
});
