import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile, readdir, readlink } from "node:fs/promises";
import { join, resolve, sep } from "node:path";

export const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");

// Compare packaged app bytes, executable modes and symlinks, including CodeResources.
// Never compare the raw Rust executable: Tauri patches and signs the app bundle.
export async function bundleManifest(directory) {
  const root = resolve(directory);
  const entries = [];
  async function walk(relative) {
    const path = join(root, relative);
    const info = await lstat(path);
    if (info.isSymbolicLink()) {
      const target = await readlink(path);
      const resolved = resolve(path, "..", target);
      assert(resolved.startsWith(`${root}${sep}`), "Bundle symlink escapes app");
      entries.push({ path: relative, link: target });
    } else if (info.isDirectory()) {
      for (const child of (await readdir(path)).sort()) await walk(join(relative, child));
    } else {
      assert(info.isFile(), "Unexpected bundle entry");
      entries.push({ path: relative, executable: info.mode & 0o111, sha256: sha256(await readFile(path)) });
    }
  }
  await walk("");
  return entries;
}
