import { test } from "node:test";
import assert from "node:assert/strict";
import { consumePage, storageScope } from "../src/state/events.ts";

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
