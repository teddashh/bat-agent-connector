# Native Fleet backend and login-startup migration

This implements the local transition contract in the Tauri plan §§08/09/21 and
[fleet-rust.md](fleet-rust.md). It does not change central tasks, inventory, profile
selection or credentials, and is not installed Windows parity evidence.

Reviewed Kit `2ec4b11` installs only the current-user Startup `Open BAT.lnk`:
`client/install-autostart.ps1` targets system `wscript.exe`, exactly the quoted
`client/Open BAT.vbs`, with the client directory as working directory. No registry
Run value or scheduled task belongs to this Kit. Migration touches only this fixed
slot. Foreign or ambiguous links refuse; other entries remain untouched. Entry presence is configured login startup, not proof that
Windows policy or Task Manager permits execution; those OS settings are not overwritten. Native
startup targets the trusted installed Dashboard with `--fleet-login --fleet-config`
and the trusted absolute config path. The same slot prevents adding a second Fleet
login entry. The config's `kit_root` is the installation root; PS scripts are under
its `client` child. Config validation comes from the installation snapshot adapter.

An opaque native preview binds exact source bytes, paths, backend and owner; the adapter
checks the UI's reviewed fingerprint before admission. A reviewed intent saves exact
original/proposed config and shortcut bytes, caller
login, original monitor identity and fixed direction before effects. Each intent has
one local journal. Original bytes remain available after completion and are used by
an explicit reverse intent; there is no blind automatic rollback. Journal/config/link
writes use bounded regular files, expected-original comparison, staged write and
replacement. Uncooperative editors can still race the final check/rename; stop such
editors during migration. This is not a multi-file atomic transaction.

One caller holds the shared `Global\\BatFleetLauncher_<SID>` coordination across
transition effects. The core requests normal quit only for the exact current-login
recorded owner with a valid epoch. Other-login, unrecorded legacy and unknown evidence
refuse. It never force-kills a monitor, BAT, SSH, Tailscale or another app. A quit
receipt is not proof of exit: a later discovery must prove no owner, and the caller
must acquire the common Monitor mutex and recheck absence before writing settings.
The monitor mutex stays held through config/startup replacement. It is released only
for launch while launcher coordination remains held.

Recovery recognizes each slot only as its original or requested bytes. A third value
refuses without overwriting it. A write whose receipt was lost can be read back and
settled. A durable launch-intent precedes the launch hook; after a crash/unknown hook
result, recovery may accept a freshly proven matching current-login backend, but
never automatically launches again. No owner after that intent means attention is
required. Explicit reverse migration first stops any proven current owner and uses
the same exclusion and byte checks. Launchers must refuse an unfinished migration
journal, including when one slot already changed.

The Windows adapter uses COM ShellLink persistence in memory: it does not resolve or
execute an inspected link. It checks exact target, arguments, working directory and
unsupported link flags, creates only fixed known invocations, and retains all source
bytes. Tests use synthetic files/links/process observations and temporary directories;
no real Startup, registry, monitor, account credential or live tunnel is changed.

## Interfaces and integration requirements

- `Store::new(fleet_json, startup_directory)` accepts only trusted native absolute paths;
  the config basename and startup filename are fixed. `preview(platform, from)` returns
  a native `Preview` with safe `fingerprint`, `backend`, `autostart_entry_present` accessors.
- `begin(platform, id, &preview, to, exact_next_config, autostart)` saves an immutable
  reviewed request. IDs are 32 lowercase hex characters and cannot change their request.
  `advance(platform, id)` performs bounded transitions; the adapter owns finite polling
  deadlines. `pending()` blocks ordinary launchers while a transition is unfinished.
- `restore(platform, source_id, new_id)` retains both journals and requests exact original
  bytes. A lost pointer-publication reply resumes the same prepared reverse intent.
- `Platform` supplies current discovery/login, installation validation for both exact
  payloads, normal exact-owner quit, shortcut codec, launcher/common-monitor guards and
  bounded low-level launch. Launch must not reacquire the already held launcher mutex.
  Configuration and process observations are revalidated before every local effect;
  unknown outcomes are errors, never a false `None` owner.
- `windows_launcher::LauncherMutex` is shared with native ensure/start. Keep it on one
  native blocking thread, including readback; it is neither recursive nor tunnel authority.
  `windows_startup::Codec` reads/renders in-memory ShellLink bytes. Only the separate native
  `startup_directory()` queries the OS folder; tests never call it or write installed entries.

Windows fixture bodies include COM round trips and an actual system PowerShell/WScript.Shell
creation oracle, all targeting temporary synthetic files. Local Linux tests and Windows
cross-compilation are separate from execution of those Windows fixtures and installed
login/migration acceptance. Unsupported link flags or invocation forms refuse safely.
