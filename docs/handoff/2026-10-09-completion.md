# Shared product continuation after PR #60

PR #60 merged as `c11dab72651ccf459842b3b39e942b040cfe2c36`. Its reviewed head is
`581e2a75b553c57867192a52f639c2dbed061904`; both have tree `ee21941fa5137cc862f2775ba5d975db154755db`.
This adds organized sessions, native Windows credential enrollment, reviewed bulk approval backend,
managed artifact capture and exact-revision acceptance. It does not complete issue #59 or M1–M3.

- [Python CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37879651946): 3.10–3.13 each 2568 passed/33 skipped, Ruff, generated skills and secret scan passed.
- [Desktop CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37879651932): 179 shared UI, 12 state, 33 Windows/32 Linux Rust; Windows NSIS/Linux deb unsigned packages and central fixtures passed.
- Local frozen backend `9b67ed8`: Python 3.13 2568/33 in 1017.37s, Python 3.10 2568/33 in 993.88s. UI-only descendants are covered by exact candidate CI, not retroactively by those local runs.

The owner wants the same product with a Tauri UI and Project Hub's orderly sessions. Work stays on the
selected BAT host/workspace. Cross-host code synchronization uses explicit GitHub bindings and published
commits; unpublished direct Git-pack transport remains excluded and its experiment stays unmerged.
Manual resources are readonly. Python remains the central authority. See the product decisions, not an
older handoff, for current scope.

Active continuation contracts: `bulk-approval.md` shared UI, new `session-start.md` and task coordinator
cleanup on their feature branches, native files in Rust and existing attachment rows. Integrate only
frozen reviewed commits, preserve all start/cleanup/confinement gates and run required full checks in
sequence. Current root integration branch is `integrate/completion-next`; original runtime checkout stays untouched.

Remaining product work includes B2 UI, other durable orchestration, explicit published-repository sync,
Rust Fleet parity/migration/bootstrap, signing/update and the same-candidate installed/live matrix.
Issue #53 remains the separate Linux GLib release gate. No live BAT/provider effects were performed.
