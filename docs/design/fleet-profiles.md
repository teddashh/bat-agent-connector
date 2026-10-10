# Native Fleet choices and BAT window launch

This extends [Fleet ownership](fleet-rust.md) and the reviewed Kit
`client/fleet-client.ps1` / `client/bat-launch.ps1`. The launcher chooses local client windows; it has no
authority over remote sessions, tasks, worktrees or manual BAT processes.

The BAT interface was also checked at pinned source
`b7419892fbc9946799b64cca24c2ec8c7fa15c42`: [profile storage](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/crates/bat-app-storage/src/profile.rs),
[window restoration](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/app.rs)
and [renderer startup](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/renderer/src/App.tsx).
`default` is a local profile. BAT supports a single-profile CLI flag, but that path
suppresses active-set restoration, so this adapter retains the Kit's empty-argv flow.

Connections, BAT profile windows and Dashboard remain independent saved choices.
A native-only selection preview retains the exact configuration, original private
selection snapshot and expected monitor epoch. Its safe summary lists requested
choices and added prerequisite connections. Applying commits those exact choices
through the existing shared preference lock and byte/configuration/epoch CAS;
dropping a preview changes nothing. Removing a connection through the existing
connection-only action continues to remove dependent future window choices.

BAT receives no invented profile CLI flags. The reviewed Kit writes
`profiles/index.json` `activeProfileIds` and launches the installed executable with
empty argv. The native adapter follows that interface only while complete process
enumeration proves no BAT process can be using the index. It retains unrelated
root/profile metadata and never repairs profiles, credentials, settings or sessions.
Remote profiles must match the current configured endpoint, remote profile and pin.
The local `default` choice must exist as a local profile. The index and executable
are bound to the preview; changed inputs require a new preview. Dashboard-only or
connections-only choices do not resolve or require a BAT executable.
Required BAT profile field types are checked so the app cannot silently read a
backup/default index instead. Nonempty selected `sshTarget` overrides refuse: BAT
would create a separate tunnel instead of using Fleet's reviewed local endpoint.
Unknown metadata remains intact. BAT may add a local anchor window for an all-remote
set (`bat_may_open_local_window` in the summary), and its own hydrated credentials
determine remote restoration. Neither the summary nor a creation receipt promises
an exact rendered-window count or an authenticated connection.

The Windows adapter borrows the caller's existing `Global\\BatFleetLauncher_<SID>`
guard; it never reacquires it. Executable candidates come only from OS known Program
Files and Local App Data folders with the reviewed BAT suffixes. It never searches
PATH or accepts an executable/path/argv from IPC. Existing BAT processes block index
changes and another launch. Unknown process evidence and another login refuse; no
process is terminated and no manual window is closed.

A fixed account-wide local launch receipt is written before changing the index or
spawning. Each preview has a stable launch ID. A repeated ID reads its receipt;
an unconfirmed spawn never repeats, including after a crash. A new explicit preview
may launch only after the earlier recorded incarnation has positively ended and BAT
enumeration is empty. A birthless uncertain intent remains blocked. Process creation
is reported as started, never proof that selected windows rendered or connected.
The caller owns Dashboard focus, monitor readiness/launch and any user-facing retry
flow. No shell, updater restart, forced BAT recovery or profile-store migration is
part of this adapter.
Older receipts are archived by their fixed native launch IDs before replacement,
so replaying an earlier accepted ID cannot become another launch. A positive unsent
failure retains its code and needs a new explicit preview to retry; original index
bytes are restored only if our proposed bytes remain unchanged and BAT is absent.

## Native integration

- `selection::Choices` carries logical connection/profile IDs and Dashboard choice.
  `Store::preview_choices` returns an opaque `ChoicePreview`; `summary` includes the
  independently saved choices, effective connections and added prerequisites.
  `Store::apply_choices` rechecks original private bytes/configuration/owner epoch.
- `profile_launch::preview(configuration, store, selection, roaming, platform)` binds
  an accepted selection and returns an opaque `Preview`. Its safe `summary` contains
  a stable launch ID, requested IDs and the local-window caveat. No file bytes, paths,
  arguments, login identifiers or credential content are serialized.
- `profile_launch::apply` consumes that fixed intent once and returns `NoBat`,
  `AlreadyRunning` or a durable `Receipt`. `read_receipt(roaming, launch_id, platform)`
  recovers the same result after a lost reply/restart without launching anything.
  `Started` proves only process creation; `Uncertain` never permits a repeat spawn.
- `windows_profiles::WindowsProfiles::new(&LauncherMutex, &installation::Snapshot)`
  borrows the caller's guard. Root app integration owns native handle registration,
  Dashboard focus and supervisor ensure/readiness before calling these methods.

Executable discovery uses the current user's OS known folders via
[SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath);
process candidates use a bounded read-only
[Toolhelp snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot).
Exact executable bytes (up to 512 MiB) and index bytes (up to 1 MiB) are rechecked
before effects. Only fixed OS/shell environment fields are inherited; central/BAT
token and generic proxy environment variables are excluded.

Files are bounded, stage-and-flush replaced with expected-byte rechecks under the
shared launcher guard. This does not claim an atomic filesystem CAS against an
uncooperative editor or a manual BAT start in the final check/create-process window.
Tests use synthetic process identities, temporary files and injected launch effects;
installed Windows window rendering, updater handoff and same/cross-login behavior
remain separate acceptance work.

## Verification at implementation freeze

The 18 new temporary profile/choice cases and nine existing selection cases pass.
The full Linux core attempt passed 117 cases before an existing native-route test
observed a connection to its just-closed ephemeral loopback port. Its unchanged
two-case family passed on serial retry; the 53 cases not reached by that attempt
also passed (171 distinct core cases covered). The original failed run is retained
as validation history; no timing assertion or unrelated route source was changed.
Formatting, all-target Linux Clippy and secret scanning pass.

An isolated `x86_64-pc-windows-msvc` all-target Clippy check includes the exact new
Windows module and profile test bodies. The existing TLS-provider constructor is
compile-stubbed because this Linux environment lacks the Windows `ring` C toolchain.
This establishes Rust/Windows API type checking only, not an application build or
Windows execution. All executable and process effects in these tests are injected;
no installed BAT, manual windows, remote hosts, Startup or real profile index was
read or changed.

Session details also support an [explicit one-profile handoff](session-bat.md).
That preview uses the original private Fleet selection as its authority and does
not rewrite saved connection, window, dashboard or login choices. The existing
profile-index launch effect and receipt protocol apply unchanged. The user must
search within BAT using the complete copied session title or ID; opening a profile
does not prove a particular session was focused.
