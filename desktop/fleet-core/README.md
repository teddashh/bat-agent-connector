# Native Fleet core

Internal Rust library for the existing Fleet inventory, profile pairing, independent local selections,
bounded configuration snapshots, process identity decisions and bounded recovery. It performs no process or network effects and is not
yet connected to the desktop Fleet adapter. This source slice does not establish Rust Fleet parity.

Port basis: Fleet Kit `2ec4b11bc010bfd669040e942648c741b63d0b7c`, `client/fleet-core.ps1` and
`client/fleet-client.ps1`. Reviewed main `4744507354466b1424b8ea369a00a94f1ca3a933` has no intervening
client/tests changes. `tests/fixtures` copies only the Kit's synthetic inventory/index/SSH fixtures;
private configuration, real host identities, credentials and pins are excluded.

Malformed existing preferences fail closed instead of silently enabling every connection. JSON field
spelling is exact and decoded keys must be unique ignoring case. Profile IDs are also unique ignoring
case. These stricter ambiguity rules are deliberate; ordinary reviewed fixtures remain compatible.
Native adapters must use the shared preference file lock/CAS and revalidate configuration before effects.
`ProcessEvidence::matches` is a necessary identity check, not permission to kill by PID. Hold the process
handle before final identity verification, require current login ownership and prove the originating
monitor ended before orphan recovery. Full Windows mutex/process/probe/migration tests are still required.

Run `cargo test --locked --manifest-path desktop/fleet-core/Cargo.toml` from the repository root.
The parser uses Serde's [Visitor](https://docs.rs/serde/1.0.229/serde/de/trait.Visitor.html) interface.

`Configuration` reads bounded UTF-8 (optional BOM) Kit inventory/index/SSH files and retains the exact
bytes used for validation. The default four-input binding matches the PowerShell facade, including
UTF-16 path lengths; an alternate profile index also binds the trusted canonical schema/pin source.
Read failures or byte changes invalidate old evidence. This is a local snapshot check, not an atomic
transaction with external editors. SSH Include expansion is not added by this loader.
`data_directory` rechecks both BAT directory names on every call and creates neither.

`selection_io::Store` holds the shared preference lock while comparing the retained primary/legacy
bytes, current configuration and freshly proven owner epoch. It writes a flushed create-new temporary
file and atomically replaces only `fleet-client.json`. Unknown ownership and directory migration refuse.
The public preference revision remains the PowerShell primary-byte digest; callers must retain the
private Snapshot too, so changes to legacy choices cannot hide behind an absent primary file.
Windows uses `windows::PreferenceLock` from the companion OS adapter; Unix fixtures use File locking.
