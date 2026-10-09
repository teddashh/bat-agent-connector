import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { nsisBundleProof } from "./windows-bundle.mjs";

const hash = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
test("NSIS proof permits only the upstream bundle marker and preserves original bytes", () => {
  const original = Buffer.from("MZ\x00fixture\xff__TAURI_BUNDLE_TYPE_VAR_UNK\x00payload");
  const saved = Buffer.from(original);
  const expected = Buffer.from("MZ\x00fixture\xff__TAURI_BUNDLE_TYPE_VAR_NSS\x00payload");
  const proof = nsisBundleProof(original);
  assert.equal(proof.built_sha256, hash(original));
  assert.equal(proof.expected_installed_sha256, hash(expected));
  assert.deepEqual(original, saved);
  assert.notEqual(proof.expected_installed_sha256, hash(original));
  for (const index of [0, expected.length - 1]) {
    const altered = Buffer.from(expected);
    altered[index] ^= 1;
    assert.notEqual(proof.expected_installed_sha256, hash(altered));
  }
  assert.notEqual(proof.expected_installed_sha256, hash(Buffer.concat([expected, Buffer.from("extra")])));
});
test("Missing or already-patched markers require reviewing the build input", () => {
  for (const bytes of [Buffer.from("MZ"), Buffer.from("__TAURI_BUNDLE_TYPE_VAR_NSS")]) {
    assert.throws(() => nsisBundleProof(bytes), /unbundled type marker is missing/);
  }
});
