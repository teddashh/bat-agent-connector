import assert from 'node:assert/strict';
import test from 'node:test';
import {repairDispatchSeed, repairIntent, repairRequest} from '../src/repair-intent.js';

const doc = {version: 1, project_id: 'prj_' + '1'.repeat(20), source: {kind: 'discovery', host: 'fixture', profile_id: 'default'},
  evidence_digest: 'a'.repeat(64), expected_project_version: 2};
const storage = () => {const values = new Map(); return {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)};};

test('lost reply and reload keep the exact original request and key', async () => {
  const disk = storage(), calls = [];
  let lost = true;
  const api = async (method, path, body, key) => {
    calls.push({method, path, body, key});
    if (lost) {lost = false; throw new Error('reply lost');}
    return {operation: {...body, operation_id: 'op_' + '1'.repeat(32), actor: 'person', idempotency_key: key, status: 'succeeded'}};
  };
  const args = {api, storage: disk, storageKey: 'principal-namespace:repair', guard() {}, actor: () => 'person', allowed: () => true, newKey: () => 'fixed-key'};
  const original = repairIntent(args);
  await assert.rejects(original.create(doc), /reply lost/);
  const restored = repairIntent(args);
  await assert.rejects(restored.create({...doc, evidence_digest: 'b'.repeat(64)}), /original repair intent/);
  const op = await restored.check();
  assert.equal(op.operation_id, 'op_' + '1'.repeat(32));
  assert.deepEqual(calls[0], calls[1]);
  assert.equal(restored.snapshot().intent.key, 'fixed-key');
  assert.throws(() => repairIntent({...args, actor: () => 'another-person'}), /unavailable/);
});

test('retired view cannot accept a pending reply or launch from stale repair evidence', async () => {
  let active = true, deliver;
  const disk = storage();
  const intent = repairIntent({api: async () => new Promise(resolve => {deliver = resolve;}), storage: disk,
    storageKey: 'principal-namespace:repair', guard() {if (!active) throw new Error('retired');},
    actor: () => 'person', allowed: () => true, newKey: () => 'fixed-key'});
  const wait = intent.create(doc);
  active = false;
  deliver({operation: {...repairRequest(doc), operation_id: 'op_' + '1'.repeat(32), actor: 'person', idempotency_key: 'fixed-key'}});
  await assert.rejects(wait, /retired/);
  assert.equal(JSON.parse(disk.getItem('principal-namespace:repair')).operation_id, null);
  const record = {version: 1, project_id: doc.project_id, work_item_id: 'wi_' + '2'.repeat(20),
    evidence_digest: doc.evidence_digest, expected_work_item_fingerprint: 'b'.repeat(64), request: 'fixed server evidence',
    dispatchable: true, dispatch_operation_id: null};
  assert.equal(repairDispatchSeed(record).prompt, record.request);
  assert.throws(() => repairDispatchSeed({...record, dispatch_operation_id: 'op_' + '1'.repeat(32)}), /current server evidence/);
  assert.throws(() => repairDispatchSeed({...record, dispatchable: false}), /current server evidence/);
});

test('failed intent persistence prevents any send', async () => {
  let calls = 0;
  const intent = repairIntent({api: async () => {calls++;}, storage: {getItem: () => null, setItem: () => {throw new Error('disk failed');}},
    storageKey: 'principal-namespace:repair', guard() {}, actor: () => 'person', allowed: () => true, newKey: () => 'fixed'});
  await assert.rejects(intent.create(doc), /disk failed/);
  assert.equal(calls, 0);
});
