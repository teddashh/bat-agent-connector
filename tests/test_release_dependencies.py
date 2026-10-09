"""A version label or unused local patch cannot satisfy the GLib release gate."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.check_glib_backport import CHANGED_FILE, REPLACEMENTS, ROOT, check_graph, check_source


@pytest.fixture
def vendor_root(tmp_path):
    shutil.copytree(ROOT / "desktop/vendor", tmp_path / "desktop/vendor")
    return tmp_path


def test_exact_upstream_backport():
    assert check_source(ROOT)["verified_files"] == 121


@pytest.mark.parametrize("which", [0, 1])
def test_either_missing_fix_is_rejected(vendor_root, which):
    path = vendor_root / "desktop/vendor/glib-0.18.5" / CHANGED_FILE
    before, after = REPLACEMENTS[which]
    path.write_bytes(path.read_bytes().replace(after, before))
    with pytest.raises(ValueError, match="mutable out-parameter"):
        check_source(vendor_root)


@pytest.mark.parametrize("change", ["changed", "added", "removed", "symlink"])
def test_unreviewed_vendor_changes_are_rejected(vendor_root, change):
    vendor = vendor_root / "desktop/vendor/glib-0.18.5"
    path = vendor / "Cargo.toml"
    if change == "changed":
        path.write_text(path.read_text() + "\n# unrelated change\n")
    elif change == "added":
        (vendor / "extra.rs").write_text("// unexpected source\n")
    elif change == "removed":
        path.unlink()
    else:
        path.unlink()
        path.symlink_to(ROOT / "desktop/vendor/glib-0.18.5/Cargo.toml")
    with pytest.raises(ValueError):
        check_source(vendor_root)


def _metadata():
    return {
        "packages": [{"id": "glib", "name": "glib", "version": "0.18.5", "source": None,
                      "manifest_path": str(ROOT / "desktop/vendor/glib-0.18.5/Cargo.toml")}],
        "resolve": {"root": "app", "nodes": [
            {"id": "app", "dependencies": ["glib"]}, {"id": "glib", "dependencies": []}
        ]},
    }


def test_linux_requires_reachable_patched_source():
    metadata = _metadata()
    assert check_graph(ROOT, "x86_64-unknown-linux-gnu", metadata)["glib_packages"] == 1
    metadata["resolve"]["nodes"][0]["dependencies"] = []
    with pytest.raises(ValueError, match="exactly the local"):
        check_graph(ROOT, "x86_64-unknown-linux-gnu", metadata)
    assert check_graph(ROOT, "x86_64-pc-windows-msvc", metadata)["glib_packages"] == 0


@pytest.mark.parametrize("field,value", [
    ("version", "0.20.0"), ("source", "registry+https://github.com/rust-lang/crates.io-index"),
    ("manifest_path", str(Path("/another/glib/Cargo.toml"))),
])
def test_relabelled_or_wrong_source_cannot_pass(field, value):
    metadata = _metadata()
    metadata["packages"][0][field] = value
    with pytest.raises(ValueError):
        check_graph(ROOT, "x86_64-unknown-linux-gnu", metadata)


def test_unexpected_windows_glib_is_rejected():
    with pytest.raises(ValueError, match="unexpectedly includes"):
        check_graph(ROOT, "x86_64-pc-windows-msvc", _metadata())


def test_provenance_cannot_relabel_upstream(vendor_root):
    path = vendor_root / "desktop/vendor/glib-0.18.5.provenance.json"
    data = json.loads(path.read_text())
    data["version"] = "0.20.0"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="provenance"):
        check_source(vendor_root)
