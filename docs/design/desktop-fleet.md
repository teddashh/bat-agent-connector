# Desktop Fleet adapter (R03, PowerShell stage)

The Rust client calls the installed Fleet Kit's fixed `client/fleet-desktop.ps1`
entry point. That Kit remains the only owner of monitors and tunnels. This slice
adds native transport commands; the settings UI, Rust ownership parity and actual
Windows acceptance are separate work.

Place `fleet.json` beside `central.json` in the app configuration directory, using
[`desktop/fleet.example.json`](../../desktop/fleet.example.json). `kit_root` is the
absolute local root of a reviewed Kit installation containing the desktop facade.
It is startup configuration, never a WebView parameter. The adapter reuses that
Kit's validated default inventory/profile pair and preference store; it creates
no duplicate host inventory. Missing configuration leaves central Dashboard use
available. Fleet control is Windows-only.

`fleet_availability` returns configuration/platform availability without paths.
`fleet_request` accepts only contract, status, configuration validation, selection,
ensure-monitor and quit-owned actions. Selection supplies a complete logical-ID
list, the observed selection revision and monitor epoch. Quit supplies the observed
epoch; it accepts no PID. The Kit performs the actual ownership and CAS checks.
Ensuring a monitor does not open BAT, launch a browser or run Kit self-update.

Each call first verifies the fixed `desktop-facade-v1` contract. Rust chooses
Windows PowerShell using the OS system-directory API, invokes a fixed `-File`
argument, and sends one UTF-8 JSON request over stdin. No arbitrary executable,
script, arguments, filesystem path, URL, headers or credentials cross IPC.
The child inherits only selected Windows identity paths; central tokens and proxy
credentials are not inherited. Only the packaged main window has command access,
with the same native origin checks as the central transport.

Requests are at most 64 KiB; stdout is at most 256 KiB; stderr is discarded.
Contract checks have a ten-second deadline; actions have a 35-second deadline.
Only one call runs at a time. On timeout Rust terminates its own facade process,
never a monitor/tunnel or an arbitrary PID. An interrupted action may already have
changed preferences or started a monitor: the client must read status and retain
its reviewed intent before retrying. The bridge does not automatically retry.
Closing or quitting the Dashboard sends no Fleet quit request.

Responses must match the request ID/schema and process outcome. Rust constructs
the returned fields explicitly. Configuration errors expose a count rather than
raw diagnostic details; readiness exposes logical names, labels, bounded status,
observation time and recognized layers. Process identities, raw errors, tokens
and paths are excluded. Freshness and selection application remain separate:
`selection.revision` is desired state, `applied_revision` is the monitor's observed
state, and missing/stale readiness is not readiness success.

Synthetic JSON fixtures originate from the Fleet Kit facade tests developed
against upstream `4ca47d0749113d2b930f360995977e425226ef1f` and are copied explicitly
for the native contract tests. They contain no live configuration. Unit tests cover
forbidden IPC inputs, contract/reply mismatch, installation containment, output
filtering, subprocess EOF/bounds, uncertain exits and cancellation. Linux process
fixtures validate transport behavior; they do not prove Windows ownership or
PowerShell startup behavior. The Kit Windows matrix and actual same/cross-login
session acceptance are required before claiming the R03/T04/T05 gates complete.
