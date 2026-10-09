# Configured Connector cold bootstrap

This is a native client contract for R03/T10. It does not create or replace the
central Connector, its journal, its owner lock, or a remote service deployment.
The shared [Fleet contract](fleet-rust.md) and [product decisions](../product/realignment-v2.md)
continue to apply.

## Source and configuration boundary

The reviewed Kit source `2ec4b11bc010bfd669040e942648c741b63d0b7c` has local monitor
bootstrap in `client/fleet-monitor.ps1` (`Start-Monitor`). It has no remote Connector
service recipe or remote query/ensure protocol. The strict Connector inventory
schema has no bootstrap field. This client capability is therefore an explicit new
contract, not an assertion of existing Kit wire parity or an installed recipe.
Unconfigured bootstrap remains unavailable; failed readiness alone grants no effect.
No private deployment name, address, service unit, state path, or credential is
provided by this repository.

A configured recipe must bind the selected inventory Connector and SSH alias to one
pre-existing deployment, service, and durable state identity. It must positively
prove that the service still uses that state before ensure. Plain `systemctl start`
without this proof is insufficient: the configured service could create an empty
journal or start another owner. Unknown state, changed identity, unsupported protocol,
missing journal, another owner, or an activating service cannot authorize ensure.
There is no shell/service/path field in the WebView API and no generic repair tool.

## Durable local behavior

The local request precedes all bootstrap transport. Its literal request identity,
recipe/configuration binding, and bounded progress survive client restart. An ensure
intent is durably recorded before the remote effect. After that boundary, lost reply,
local write failure, timeout, cancellation, or process restart permits queries only;
none permits another ensure. A service already running or activating is never
restarted. Finite query exhaustion becomes needs attention without deleting evidence.
No new key or client restart resets an unresolved ensure fence.

Every effect checks that the Connector is still selected and the native configuration,
recipe, login, and generation still match. Exact receipt settlement may retain evidence
after drift, but may not publish it as a result from the new configuration. Cooperative
clients must share the existing launcher/owner exclusion; journal replacement uses
exact prior bytes. This is not atomic protection against an uncooperative file editor.

A service-running response is only service evidence. It does not prove API readiness,
central operation admission, or work completion. The existing separate observe-only
Connector probe must validate API identity/version/contract and its authenticated
principal; the user's Desktop mutation token is never a bootstrap credential. No
central diagnostics attachment is claimed until such a capability exists.

## Evidence limits

Development uses temporary local receipt files, synthetic protocol/process peers,
and injected observations. No live SSH, service mutation, installed helper, real
journal, or native installed acceptance is exercised. The required remote guard and
its configured deployment must be independently established before this client can
be enabled. Missing proof is a truthful unavailable/needs-attention result.

## Implemented native interface and wire version 1

`bootstrap::Recipe::load(client_root, &Configuration)` reads only the optional
`fleet-connector-bootstrap.json` under the trusted client root. It rejects unknown
fields and binds `schema_version:1`, `allow_ensure:true`, `ssh_alias`, `service_id`,
`state_directory`, `journal_path`, `owner_uid`, and `server_recipe_sha256`. Optional
`auto_ensure` is a strict boolean and defaults to `false`. The alias
must equal the inventory Connector alias; the state/journal paths are fixed native
configuration, never IPC. Absent/disabled recipes do not enable bootstrap. This
separate file does not extend the Kit inventory schema.

`Store::new(native_roaming_dir).advance(recipe, captured_generation, request_id,
platform)` stores `bat-fleet-connector-bootstrap.json`. Request IDs are literal
32-character lower-case hex values chosen once by native code. The store retains
up to 64 historical requests within a 256 KiB cap; it does not silently prune.
Each exchange retains its full fixed request and validated response (or unknown
response), and counts its query before I/O. A request has at most four queries and
one ensure. Each advance has a 20-second transport deadline; a crashed query spends
its recorded attempt. Exhaustion remains needs attention. A new request ID is only
admitted after positive service-running evidence for the previous request, never
as an automatic retry of an unresolved start. A finished replay is historical
service evidence, not a current readiness observation.

`windows_bootstrap::WindowsBootstrap::new(configuration, &LauncherMutex,
verify_selected_generation)` uses the OS System directory's fixed `OpenSSH/ssh.exe`.
The native callback rechecks the selected Connector, installation and exact captured
`ProbeGeneration`; the account launcher guard remains on the same blocking thread
through the entire advance. The adapter rechecks login, recipe/configuration and
executable path. It sends only the fixed remote command
`/usr/local/libexec/bat-connector-bootstrap-v1`, with noninteractive host-key checking,
no agent/X11 forwarding, no local command or inherited remote command, and bounded
stdin/stdout. Only the retained local SSH child is closed on timeout/cancellation;
that is never evidence the remote ensure was not received.

Request JSON echoes the configured service/state/UID/server-recipe digest, protocol
`1`, request ID, generation digest, query attempt and `query`/`ensure` action. A
response must match every field exactly. Its added fields are `state`, `owner` and
`ensure_accepted`. `running` requires `owner:service`; `stopped` requires
`owner:absent`. `ensure_accepted` means only the fixed service manager accepted the
start request, not that Connector is online. Raw helper failures, environment,
private paths and commands never enter public status. No token is sent by this
protocol. Existing Fleet observe-only readiness still determines API readiness;
there is no mutation-token fallback or diagnostics-upload claim.

## Desktop runtime and settings

The fixed native `fleet_bootstrap` command accepts exactly four request shapes:

| Action | Input | Behavior |
| --- | --- | --- |
| `overview` | none | Read configured/missing status, automatic opt-in, eligibility and latest sanitized receipt |
| `prepare` | `recipe_binding` | Save a native-generated 32-hex request ID without remote I/O; reuse the unresolved original |
| `advance` | `recipe_binding`, `request_id` | Run the original bounded query/at-most-one-ensure protocol |
| `receipt` | `request_id` | Read the original local receipt, even if its recipe is now missing or changed |

The WebView cannot supply a service, SSH alias, executable, path, PID, command or
credential. The controller captures the lifecycle Ticket at IPC entry and verifies
that same Ticket after acquiring the shared Launcher guard and at each core
transport boundary. Quit/update invalidates queued work permanently. Each request
captures the monitor epoch, configuration and private selection bytes, with a
bootstrap-local generation counter of zero; it does not borrow the supervisor's
separate per-host probe counter. Those exact native identities are rechecked under
Launcher before effects. A recovered original request can query under a new proven
monitor generation, without clearing its ensure fence.

Admission additionally requires a current-login recorded monitor matching the
configured backend, a positively observed Connector SSH child with its exact
configured tunnel arguments, owner PID/incarnation and epoch, and fresh selected
Connector-unavailable readiness. Both recorded owner directories are checked;
conflicting evidence refuses. An open local port is insufficient. Unknown, stale,
future, authentication, credential or API-contract failures do not authorize
bootstrap. A healthy central result suppresses remote bootstrap. If it becomes
healthy while a request is in flight, an unconfirmed local result may remain
historical/unknown; the normal central connection remains independently usable.

An independent native worker checks the optional `auto_ensure:true` recipe every
five seconds. It uses the same prerequisites, original local journal and finite
query budget. It never allocates a replacement automatic request after success or
exhaustion, including across app restart; a later outage requires explicit review.
An invalidated lifecycle Ticket stops that worker for the process lifetime. Normal
central connection and supervisor readiness workers do not wait for its SSH budget.
Bootstrap does not start a local monitor or create a second central daemon.

The shared settings module displays configured/missing/blocked state and separate
service evidence. Prepare, ensure/reconcile and read-original are explicit controls.
Reopening or polling the page only reads local receipts. The native journal is the
source of request identity; browser session storage is an optional index, so losing
it cannot mint another ensure. Wrong-ID/binding or unreadable receipts keep effects
disabled. No recipe editor or automatic mutation is implemented in the WebView.

Focused evidence covers real temporary receipt bytes, injected process identities,
route/readiness policy, finite automatic-request selection, native IPC validation,
and browser-hosted native transport doubles for loss/reload/layout behavior. Windows
module compilation is compile-only evidence; real Windows SSH/installed service
and startup acceptance remain outstanding.

## Fixed Linux server guard

The new standalone module is `bat_agent_connector.fleet_bootstrap`; the supplied
`scripts/bat-connector-bootstrap-v1` entry uses `/usr/bin/python3 -I`. An operator
must separately install that reviewed module in that interpreter's environment,
place the entry at the fixed remote path, and prepare protected
`/etc/bat-agent-connector/bootstrap-v1.json`. This change performs none of those
steps and does not expose the helper through Connector HTTP/MCP/CLI. A missing
helper or incompatible existing service is unavailable, not a shell fallback.

The server recipe has exact version-1 fields: `service_id`, `unit`, `unit_path`,
`unit_sha256`, `uid`, `executable`, `config_path`, `state_directory`, `journal_path`,
`journal_identity:[device,inode]`, `lock_identity:[device,inode]`, and `port`.
The client pins the SHA-256 of those exact server recipe bytes. The helper requires
the same real/effective UID and a pre-existing **systemd user service**. System
services, sudo, launchd, Windows services and arbitrary wrappers are unsupported.
It only accepts literal absolute ASCII paths (no expansion/specifiers), a simple
unit with no automatic restart, and direct argv:

```
<fixed executable> --config <fixed config> serve --host 127.0.0.1 --port <fixed port> --db <fixed journal>
```

The actual Connector source uses `BATC_STATE_DIR` for both the registry and
`task-daemon.lock`; global `--config` and serve `--db` are existing CLI arguments.
The unit must explicitly set `BATC_STATE_DIR` and `BATC_CONFIG` to the recipe paths.
The guard pins protected unit bytes and compares loaded effective argv/environment,
fragment path, reload state, service type and restart behavior. Drop-ins,
EnvironmentFiles, Pass/UnsetEnvironment, extra pre/post commands, root remapping,
unknown properties, multiple commands and unsupported unit directives refuse.
The `systemctl show` text contract follows
[systemd v257 `systemctl-show.c`](https://github.com/systemd/systemd/blob/v257/src/systemctl/systemctl-show.c):
fixed ExecStart record formatting and an empty Job property for no pending job.
Queries use `--all`; only the formatter's omitted empty `EnvironmentFiles` and
`ExecStartPre`/`ExecStartPost`/`ExecCondition` arrays are normalized to empty. Missing
other fields refuse. The pinned unit parser independently forbids those directives.
The per-field evidence is deliberately narrow:

| Loaded properties | Evidence / admission meaning |
| --- | --- |
| `Id`, `LoadState`, `FragmentPath`, `NeedDaemonReload` | Exact pinned unit identity, loaded source path, no pending reload; strings must be present |
| `Type`, `Restart`, `User`, `DynamicUser` | Simple/no-restart/current configured UID; present empty `User` is the user-manager default, not a different user |
| `Environment`, `EnvironmentFiles`, `PassEnvironment`, `UnsetEnvironment` | Exactly the two explicit BATC bindings; no additional environment source. `EnvironmentFiles` is the reviewed omitted-empty array exception; the others must be present |
| `ExecStart`, `ExecStartPre`, `ExecStartPost`, `ExecCondition` | Exactly one literal configured command; the three optional command arrays may be omitted only as empty. The `ExecStart` formatter records path, argv and ignore-errors before runtime status |
| `DropInPaths`, `RootDirectory`, `RootImage` | Present empty values only; no extra unit/root mapping |
| `ActiveState`, `SubState`, `MainPID`, `Job` | Inactive/dead, PID `0`, empty `Job` are required for ensure. The formatter emits `Job=` for no job; a numeric job is a transition, never absence |

Tests feed the formatter's omitted-empty shape through the real `Systemd.query`
parser, then independently exercise loaded-field mismatches. These fixtures are
source-based compatibility evidence, not an installed systemd user-service test.

Only an inactive/dead unit, zero main PID, no job and a positively free **existing**
owner flock can proceed. The guard opens no lock with create flags and releases
that flock **before** `/usr/bin/systemctl --user --no-pager start --no-block -- <unit>`;
the existing Connector flock arbitrates a competing owner normally. It never calls
restart, reset-failed, enable, daemon-reload, or a daemon constructor. A held lock
never authorizes start. Positive already-running evidence additionally matches the
unit PID, kernel flock owner, `/proc` UID/command/incarnation and existing pointer;
a stale pointer/heartbeat alone cannot prove ownership.

For inactive state proof, bounded protected DB and WAL bytes are copied into a
private disposable scratch directory while the owner flock is free/held by the
checker. SQLite opens the **copy** with `mode=ro`; WAL is included rather than
ignored by `immutable=1`. Required initialized tables and quick-check must pass;
source metadata is rechecked, and no source SHM/journal is created. A hot rollback
journal, changed inode, symlink/reparse equivalent, unsafe ownership/mode, malformed
or oversized bytes refuse. Limits are 256 MiB DB, 64 MiB WAL, 16 KiB recipe/wire/unit,
3 seconds per systemctl invocation, 2 seconds SQLite progress budget, and a
15-second helper process alarm. Output is bounded and no service environment is
logged. Existing helper/service environment and filesystem reads may still block
inside OS calls; the client deadline remains an unknown-result fence, not proof
of remote cancellation.

There is an unavoidable check/start interval against an uncooperative administrator
changing unit/state files or unlinking a journal after proof. This does not claim
an atomic systemd/filesystem transaction; deployment changes require the service
and bootstrap users stopped. Missing/changed state observed by the guard never
creates a replacement journal. Server deployment review must establish the actual
unit, data paths, permission model, package/helper versions, and observe credential
before enabling this optional recipe.
