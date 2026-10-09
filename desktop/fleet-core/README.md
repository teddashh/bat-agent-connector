# Native Fleet core

Internal Rust library for the existing Fleet inventory, profile pairing, independent local selections,
bounded configuration snapshots, locked selection updates, process identity decisions and bounded recovery.
The Windows OS adapter stops only explicitly verified local processes through retained handles.
The probe module performs bounded, read-only loopback TLS/BAT and Connector capabilities requests.
The route module probes configured TCP endpoints and a fixed trusted local Tailscale
`status --json` command under deadlines, and keeps route/recovery decisions native-only.
These effects are not connected to the desktop Fleet adapter or automatic startup. This source slice does not
establish Rust Fleet parity.

Port basis: Fleet Kit `2ec4b11bc010bfd669040e942648c741b63d0b7c`, `client/fleet-core.ps1` and
`client/fleet-client.ps1`. Reviewed main `4744507354466b1424b8ea369a00a94f1ca3a933` has no intervening
client/tests changes. `tests/fixtures` copies only the Kit's synthetic inventory/index/SSH fixtures;
private configuration, real host identities, credentials and pins are excluded.

The native-only credential reader resolves the selected inventory's BAT profile token or Fleet
observe DPAPI reference from fixed, bounded files. It never falls back to a desktop mutation token,
another profile, another data directory or an environment variable. See the
[format and evidence contract](../../docs/design/fleet-credentials.md); Windows DPAPI runtime
compatibility remains a Windows-runner gate.

Malformed existing preferences fail closed instead of silently enabling every connection. JSON field
spelling is exact and decoded keys must be unique ignoring case. Profile IDs are also unique ignoring
case. These stricter ambiguity rules are deliberate; ordinary reviewed fixtures remain compatible.
Native adapters must use the shared preference file lock/CAS and revalidate configuration before effects.
`ProcessEvidence::matches` is a necessary identity check, not permission to kill by PID. Hold the process
handle before final identity verification, require current login ownership and prove the originating
monitor ended before orphan recovery. Probe results retain their captured configuration/selection/epoch
generation and expire after 60 seconds; callers must revalidate configuration before publication.
The observe credential is separate from the desktop mutation credential. Synthetic loopback peers cover
pinning, TLS signatures, BAT auth/version/profile/workspace, strict observe capabilities, fragmented
UTF-8/ping, total deadlines and size limits. Installed Windows process/probe/migration evidence is still
required; loopback fixtures do not establish live Fleet acceptance.

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

Windows boundaries are in `windows` and tested independently from the platform-neutral
`process_adapter` decisions. `MonitorMutex::try_acquire()` uses the PowerShell account mutex and
must stay on one supervisor thread. `PreferenceLock::{try_acquire,acquire}` opens the same `.lock`
sidecar with zero sharing; keep the guard alive through the entire preference CAS/publication.
Process arguments and paths remain native-only evidence, never frontend status. See
[the Windows adapter contract](../../docs/design/fleet-windows.md) for the exact interfaces,
legacy creation-time format, NT command-line limitations and pending Windows execution evidence.

`route::SelectionRequest` lets independent background workers probe an immutable snapshot.
A result's alias is available only after current generation/policy validation; the supervisor
still revalidates configuration before launch. Selection updates preserve an owned Run and
recovery history, while source changes require a fresh policy after owned stop. See
[route policy and intentional Kit corrections](../../docs/design/fleet-routes.md).

`migration` records explicit backend/autostart transitions with exact original bytes and
normal-owner exit proof; it never retries an uncertain launch. The fixed Windows startup
codec reads/writes only the reviewed Open BAT shortcut via the caller's local journal
flow. These modules require the native facade's guarded hooks and are not wired into
automatic startup by this library. See [migration contract](../../docs/design/fleet-migration.md).
