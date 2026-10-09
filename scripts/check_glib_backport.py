"""Check the complete backport bytes and the app's actual target dependency graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = "233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5"
FIX_COMMIT = "b5a4071e439bef2b5eea76c3aa25e5ae84839e34"
CHANGED_FILE = "src/variant_iter.rs"
REPLACEMENTS = (
    (b"let p: *mut libc::c_char = std::ptr::null_mut();", b"let mut p: *mut libc::c_char = std::ptr::null_mut();"),
    (b"                &p,\n", b"                &mut p,\n"),
)


def check_source(root: Path) -> dict:
    vendor = root / "desktop/vendor/glib-0.18.5"
    provenance = json.loads((vendor.parent / "glib-0.18.5.provenance.json").read_text())
    if (provenance["archive_sha256"], provenance["fix_commit"], provenance["version"]) != (
        ARCHIVE_SHA256, FIX_COMMIT, "0.18.5"
    ):
        raise ValueError("GLib provenance does not match the reviewed upstream source/fix")
    files = {p.relative_to(vendor).as_posix(): p for p in vendor.rglob("*") if p.is_file()}
    if any(p.is_symlink() for p in vendor.rglob("*")) or vendor.is_symlink():
        raise ValueError("GLib vendor source contains a symlink")
    if files.keys() != provenance["upstream_files"].keys():
        raise ValueError("GLib vendor file inventory differs from the published crate")
    for name, path in files.items():
        data = path.read_bytes()
        if name == CHANGED_FILE:
            for before, after in REPLACEMENTS:
                if data.count(after) != 1 or before in data:
                    raise ValueError("GLib iterator is missing the exact upstream mutable out-parameter fix")
                data = data.replace(after, before, 1)
        if hashlib.sha256(data).hexdigest() != provenance["upstream_files"][name]:
            raise ValueError(f"GLib source differs from published crate plus the two-line fix: {name}")
    return {"version": "0.18.5", "upstream_archive_sha256": ARCHIVE_SHA256,
            "fix_commit": FIX_COMMIT, "verified_files": len(files),
            "patched_file_sha256": hashlib.sha256(files[CHANGED_FILE].read_bytes()).hexdigest()}


def check_graph(root: Path, target: str, metadata: dict) -> dict:
    graph = metadata["resolve"]
    nodes = {node["id"]: node for node in graph["nodes"]}
    pending = [graph["root"]]
    reachable = set()
    while pending:
        package = pending.pop()
        if package not in reachable:
            reachable.add(package)
            pending.extend(nodes[package]["dependencies"])
    glib = [p for p in metadata["packages"] if p["id"] in reachable and p["name"] == "glib"]
    if "linux" in target:
        expected = (root / "desktop/vendor/glib-0.18.5/Cargo.toml").resolve()
        if len(glib) != 1 or glib[0]["version"] != "0.18.5" or glib[0]["source"] is not None:
            raise ValueError("Linux app must resolve exactly the local GLib backport")
        if Path(glib[0]["manifest_path"]).resolve() != expected:
            raise ValueError("Linux app resolved a different GLib source directory")
    elif "windows" in target:
        if glib:
            raise ValueError("The Windows dependency graph unexpectedly includes GLib")
    else:
        raise ValueError("Backport gate supports the Linux and Windows release targets only")
    return {"target": target, "glib_packages": len(glib),
            "source": "vendored upstream backport" if glib else "absent"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    source = check_source(ROOT)
    cargo = shutil.which("cargo")
    if cargo is None:
        raise RuntimeError("cargo is required to verify the compiled dependency graph")
    # Fixed commands and manifest; the target is an argv value, never shell input.
    result = subprocess.run(  # noqa: S603
        [cargo, "metadata", "--locked", "--format-version", "1", "--filter-platform", args.target,
         "--manifest-path", str(ROOT / "desktop/src-tauri/Cargo.toml")],
        check=True, capture_output=True, text=True, timeout=180,
    )
    print(json.dumps({"source": source, "graph": check_graph(ROOT, args.target, json.loads(result.stdout))}, indent=2))


if __name__ == "__main__":
    main()
