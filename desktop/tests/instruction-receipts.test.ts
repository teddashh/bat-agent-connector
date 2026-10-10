import assert from 'node:assert/strict';
import test from 'node:test';
import {instructionReceiptReader} from '../src/instruction-receipts.js';

const row = index => ({operation_id: 'op_' + index.toString().padStart(32, '0'), host: 'fixture', session_id: 'exact',
  phase: 'accepted', text_excerpt: '<script>data only</script>', queue_position: null, per_message_cancel: false, was_queued: true});
const page = (rows, cursor = null) => ({version: 1, host: 'fixture', session_id: 'exact', live_queue_available: false,
  per_message_cancel: false, instructions: rows, next_cursor: cursor, read_at: 100});

test('refresh keeps previous receipts on network failure and rereads loaded older pages', async () => {
  let offline = false;
  const requests = [];
  const reader = instructionReceiptReader({guard() {}, host: 'fixture', sessionId: 'exact', api: async (_, url) => {
    requests.push(url); if (offline) throw new Error('offline');
    return url.includes('cursor=older') ? page([row(1)]) : page([row(2)], 'older');
  }});
  assert.equal((await reader.load()).instructions.length, 1);
  const history = await reader.load(true);
  assert.equal(history.instructions.length, 2);
  assert.equal(history.instructions[0].was_queued, true);
  offline = true;
  await assert.rejects(reader.load(), /offline/);
  assert.deepEqual(reader.snapshot(), history);
  offline = false; requests.length = 0;
  assert.deepEqual(await reader.load(), history);
  assert.equal(requests.length, 2);
});

test('mismatched session and live queue claims never overwrite known history', async () => {
  let response = page([row(1)]);
  const reader = instructionReceiptReader({guard() {}, host: 'fixture', sessionId: 'exact', api: async () => response});
  const original = await reader.load();
  response = {...response, session_id: 'other'};
  await assert.rejects(reader.load(), /Invalid instruction receipts/);
  assert.deepEqual(reader.snapshot(), original);
  response = page([{...row(1), queue_position: 1}]);
  await assert.rejects(reader.load(), /Invalid instruction identity/);
  assert.deepEqual(reader.snapshot(), original);
});

test('principal transition rejects a pending read before cache updates', async () => {
  let active = true, deliver;
  const reader = instructionReceiptReader({host: 'fixture', sessionId: 'exact', guard() {if (!active) throw new Error('retired');},
    api: () => new Promise(resolve => {deliver = resolve;})});
  const reading = reader.load(); active = false; deliver(page([row(1)]));
  await assert.rejects(reading, /retired/);
  active = true; assert.equal(reader.snapshot(), null);
});
