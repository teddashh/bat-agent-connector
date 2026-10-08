import { test } from "node:test";
import assert from "node:assert/strict";
import { consumePage, consumePageAsync, storageScope } from "../src/state/events.ts";

test("a full page commits its processed cursor, never the remote head", () => {
  const seen: number[] = [];
  const cursor = consumePage({ events: [{seq: 4, kind: "session.updated"}, {seq: 5, kind: "operation.updated"}],
    head_cursor: 900, has_more: true }, 4, event => seen.push(event.seq));
  assert.equal(cursor, 5);
  assert.deepEqual(seen, [5]);
});
test("a reset invalidates views before consuming replacement events", () => {
  const seen: string[] = [];
  assert.equal(consumePage({events: [{seq: 2, kind: "session.updated"}], head_cursor: 2, has_more: false},
    500, event => seen.push(event.kind)), 2);
  assert.deepEqual(seen, ["reset", "session.updated"]);
});
test("handler failure does not acknowledge an unprocessed page", () => {
  assert.throws(() => consumePage({ events: [{seq: 5, kind: "session.updated"}], head_cursor: 5, has_more: false },
    4, () => { throw new Error("failed refresh"); }));
});
test("identities and endpoints cannot share operation and draft storage", () => {
  assert.notEqual(storageScope("https://central.example", "alice"), storageScope("https://central.example", "bob"));
  assert.notEqual(storageScope("https://central.example", "alice"), storageScope("https://other.example", "alice"));
  assert.notEqual(storageScope("https://central.example", "alice", "server-a", "principal-a"),
    storageScope("https://central.example", "alice", "server-b", "principal-a"));
  assert.notEqual(storageScope("https://central.example", "alice", "server-a", "principal-a"),
    storageScope("https://central.example", "alice", "server-a", "principal-b"));
});
test("documented next cursor advances across filtered migration events after handling visible events", () => {
  assert.equal(consumePage({events: [{seq: 5, kind: "session.updated"}], next_cursor: 8, head_cursor: 9, has_more: true},
    4, () => {}), 8);
});

test("asynchronous refreshes finish before the complete page cursor is returned", async () => {
  let release!: () => void, committed = false;
  const refresh = new Promise<void>(resolve => { release = resolve; });
  const seen: number[] = [];
  const result = consumePageAsync({events: [{seq: 5, kind: "changed"}, {seq: 6, kind: "changed"}],
    head_cursor: 100, next_cursor: 8, has_more: true}, 4, event => { seen.push(event.seq); return refresh; })
    .then(cursor => { committed = true; return cursor; });
  await Promise.resolve();
  assert.deepEqual(seen, [5, 6]);
  assert.equal(committed, false);
  release();
  assert.equal(await result, 8);
});

test("an asynchronous view failure refuses the page acknowledgment", async () => {
  await assert.rejects(consumePageAsync({events: [{seq: 5, kind: "changed"}],
    head_cursor: 5, next_cursor: 5, has_more: false}, 4,
  async () => { throw new Error("refresh unavailable"); }), /refresh unavailable/);
});

test("a failed refresh waits for sibling reads before retry can begin", async () => {
  let release!: () => void, rejected = false;
  const sibling = new Promise<void>(resolve => { release = resolve; });
  const result = consumePageAsync({events: [{seq: 5, kind: "failed"}, {seq: 6, kind: "slow"}],
    head_cursor: 6, next_cursor: 6, has_more: false}, 4,
  event => event.kind === "failed" ? Promise.reject(new Error("failed refresh")) : sibling)
    .catch(error => { rejected = true; return error.message; });
  await Promise.resolve(); await Promise.resolve();
  assert.equal(rejected, false);
  release();
  assert.equal(await result, "failed refresh");
});
