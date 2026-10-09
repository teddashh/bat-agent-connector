# GLib 0.18.5 backport

`glib-0.18.5/` is the complete published gtk-rs crate with exactly the two-line
upstream fix for [RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html).
GTK 0.18 / WebKit2GTK 2.0 currently require this GLib series. The app's
`[patch.crates-io]` selects these bytes instead of the affected registry source.
The version remains **0.18.5**; it is not relabelled as an upstream fixed release.

- Archive: <https://static.crates.io/crates/glib/glib-0.18.5.crate>
- Archive SHA-256: `233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5`
- Archive's upstream source commit: `42b9caf98e03ded086362d9653ca58fe94dc8658`
- Fix: [gtk-rs PR #1343](https://github.com/gtk-rs/gtk-rs-core/pull/1343),
  commit [`b5a4071e439bef2b5eea76c3aa25e5ae84839e34`](https://github.com/gtk-rs/gtk-rs-core/commit/b5a4071e439bef2b5eea76c3aa25e5ae84839e34).
- License: upstream MIT, preserved verbatim in `glib-0.18.5/LICENSE`.

`src/variant_iter.rs` changes `let p` to `let mut p` and the C out-argument `&p`
to `&mut p`. `g_variant_get_child` writes the string pointer; an immutable reference
does not permit that write. The rest of the crate is unchanged, including its
manifest, tests and license.

`glib-0.18.5.provenance.json` records every original archive file's SHA-256.
`scripts/check_glib_backport.py` reverses only these two substitutions, checks
all 121 files against that inventory, rejects extra/missing/symlinked files, and
checks Cargo's resolved target graph. This is a reproducibility check against the
reviewed inventory, not an independent attestation of an unreviewed checkout.

From the repository root:

```sh
python3 scripts/check_glib_backport.py --target x86_64-unknown-linux-gnu
python3 scripts/check_glib_backport.py --target x86_64-pc-windows-msvc
cargo test --release --locked --manifest-path desktop/src-tauri/Cargo.toml --test glib_variant_iter
```

The Linux graph must use the local source; the Windows graph must exclude GLib.
The release regression covers `next`, `nth`, `last`, `next_back`, `nth_back`, mixed
iteration, UTF-8 and exhaustion with compiler optimization enabled. CI then runs
the native app tests, packages the Linux app, and starts that release binary in a
private display/session against a loopback fixture.

No advisory ignore or Dependabot dismissal is added. Version-only scanners may
still report 0.18.5; source remediation and advisory status must be reported
separately. Remove this patch only when the actual GTK/WebKit dependency graph
resolves an upstream fixed compatible release, then rerun the same gates.
