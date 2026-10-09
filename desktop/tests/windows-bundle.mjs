import assert from "node:assert/strict";
import { createHash } from "node:crypto";

// Pinned CLI 2.12.1 writes this marker before NSIS packaging, then restores the
// original target/release binary. Account for exactly that upstream transform.
// https://github.com/tauri-apps/tauri/blob/tauri-cli-v2.12.1/crates/tauri-bundler/src/bundle.rs
export function nsisBundleProof(original) {
  const before = Buffer.from("__TAURI_BUNDLE_TYPE_VAR_UNK");
  const after = Buffer.from("__TAURI_BUNDLE_TYPE_VAR_NSS");
  const offset = original.indexOf(before);
  assert(offset >= 0, "Tauri's unbundled type marker is missing; review the packaging transform");
  const expected = Buffer.from(original);
  after.copy(expected, offset);
  const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
  return { transform: "tauri-nsis-bundle-marker", marker_offset: offset,
    built_sha256: sha256(original), expected_installed_sha256: sha256(expected) };
}
