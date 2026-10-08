# Desktop foundation (R02)

This first slice packages the existing Dashboard in Tauri 2. It reads and operates the existing central Connector; it does not start a Python daemon, own tunnels, or maintain a task journal. The original colors, CSS, DOM helpers, forms, checkpoint flow, delivery flow and operation envelopes are reused from the Dashboard at `2568520`.

## One frontend

Edit `desktop/src`, never the generated Python static assets. The existing JavaScript UI remains JavaScript; its transport and event helpers use TypeScript. React/Vue are not introduced.

```sh
cd desktop
npm ci
npm run build:all
npm test
npm run test:ui
cargo test --locked --manifest-path src-tauri/Cargo.toml
# After `uv sync --locked --extra dev` at repository root:
npm run test:central
```

`npm run build` generates packaged assets in `desktop/dist`. `npm run build:browser` generates the original four permitted `/dashboard/` files, including a compatibility `i18n.js` stub; translations are bundled from `desktop/src/i18n.js`. The Python server keeps its same-origin authorization, file allowlist and CSP. CI rebuilds browser assets and rejects drift. `package-lock.json` and `src-tauri/Cargo.lock` pin dependency resolution; the initial build uses Node 24.21.0 and Rust 1.98.1, Tauri 2.12.1, Vite 8.3.4, TypeScript 7.0.2.

## Configure the native client

The client loads `central.json` from the platform app configuration directory:

| Platform | Configuration file |
| --- | --- |
| Windows | `%APPDATA%\io.betteragent.dashboard\central.json` |
| Linux | `$XDG_CONFIG_HOME/io.betteragent.dashboard/central.json`, normally `~/.config/io.betteragent.dashboard/central.json` |
| macOS | `~/Library/Application Support/io.betteragent.dashboard/central.json` (not validated on macOS) |

Copy `desktop/central.example.json` there and set the actual expected API actor. Endpoint selection is native startup configuration, never a WebView-supplied URL. This configuration is client-local and is not another fleet host inventory. The endpoint must be an HTTPS origin or a literal loopback HTTP origin for an already authenticated SSH tunnel. The app neither creates that tunnel nor authenticates its ownership. Preserve the existing tunnel's host verification; an arbitrary loopback listener is not proof of central identity.

For this slice, supply `BATC_DESKTOP_TOKEN` in the launching process environment. Rust reads and removes it before constructing the runtime, retains it in zeroizing native memory, and never returns it to JavaScript. Do not put it in the JSON file, a URL, command arguments, or frontend storage. This is an explicit provisional native-memory credential adapter. Windows Credential Manager/DPAPI enrollment and other OS protected-storage adapters remain required; this is not an unattended-login setup.

The first connection reads `/capabilities` and requires the configured actor, API version `1`, contract version `2026-10-08`, and `observe` scope. It displays the central actor/scopes, without claiming a distinct cryptographic server identity. HTTPS certificates or the configured tunnel provide transport identity. Contract or actor mismatches leave operations blocked.

The app works without BAT installed. Connection settings explicitly list Fleet, opening BAT, native attachments, autostart and updates as unavailable. Missing configuration and credentials remain visible in the app.

## Native boundary

Only the bundled `main` window receives generated application command permissions. Rust checks its label and local origin again. Navigation cannot replace it with an external site. The development origin is accepted only in debug builds. Native CSP allows IPC, without giving frontend `fetch` access to the central network.

`connector_request` accepts a method, a relative allowlisted API path, an optional JSON body and an idempotency key. It cannot accept an endpoint, filesystem path, shell command, arbitrary headers or credentials. Defined GET reads and central operation POSTs share the existing backend authorization/policy. Create operations require an idempotency key. Paths are checked before URL normalization; encoded path segments and traversal are refused. Malformed/control-character queries and unknown query keys are refused. Requests/responses and timeouts are bounded; redirects and environment HTTP proxies are disabled. Request errors never expose native credentials.

The initial allowlist accepts ASCII host/session identifiers; encoded/non-ASCII path identifiers are a remaining compatibility limit, not a reason to bypass validation. New central API routes require an explicit allowlist update and review.

Existing GitHub links call the narrow `open_external` action. Rust accepts credential-free `https://github.com` URLs without queries and sends them to the system browser. No raw opener, filesystem, shell or HTTP plugin permissions are granted to the WebView.

## Events, drafts and retries

Both builds use bounded one-second polling of the same central `/events` journal. Native streaming subscriptions are not implemented; the central SSE endpoint remains available to other clients.

When `/bootstrap` is available, the client takes its checkpoint before mounting views, isolates state by endpoint/server ID/principal ID/actor, then replays pages with the original checkpoint token and cursor. It persists the returned paired checkpoint only after every visible event's asynchronous view refresh has finished successfully, including legitimate `next_cursor` advancement over filtered migration facts. It never jumps to `head_cursor` on a bounded page and backs off if `has_more` makes no progress. Navigation pauses consumption until the new view is mounted.

`EVENT_CURSOR_RESET` reboots observation reads. Open edits defer the refresh until the user leaves/closes them; operations remain blocked during that interval. A changed backend/principal switches namespaces immediately so an old form cannot write drafts into the new identity. The initial bootstrap snapshot is not a separate authoritative UI cache: views read central data after the captured checkpoint. Older servers returning 404 for bootstrap use current views and polling without continuity guarantees; R04 must be deployed for reset/retention semantics.

Session text drafts, original operation keys/IDs and checkpoint state stay in browser storage under the identity namespace. Poll failures block operation POSTs while preserving the draft and retry key. A reconnect never starts another session or changes the operation envelope. A lost reply can be retried after reopening with the same key; a 409 retains that key. Existing unscoped browser storage is left untouched and is not automatically assigned to a newly identified backend. Migration of ambiguous pre-desktop drafts/unknown operations needs explicit reconciliation before replay.

Event acknowledgment now waits for asynchronous and debounced view refreshes, including all sibling reads on a failed batch. A locally displayed refresh error retains the original cursor/checkpoint pair and pauses mutations; polling retries the same page. Open edits defer renders and acknowledgment until they can refresh without discarding input. A pending refresh alone does not disable connected, version-checked form saves; an actual failed read or continuity reset does. Delayed refreshes are bound to the original account and mounted view. Mounted session events now refresh the observation header, pending questions/permissions and messages without replacing the composer or checkpoint forms. Pending answers are stored per identity and pending ID. Before answering, the client rereads the persisted pending observation and refuses a changed/missing ID; central still validates the live BAT frame because inventory reads are not write authority. Work-item pages refresh for linked operation/session/execution/checkpoint and parent-project events. Parent archive restrictions update immediately while an open edit remains intact; full rerender and acknowledgment wait until editing ends. Resource history/relations and discovery presentation are described below; complete M1 acceptance remains pending.

## Shared delivery controls

Delivery's environment cards, paginated history, rollback/retry confirmations and English/Traditional Chinese
labels now live in the same canonical `desktop/src` files. Browser assets are generated; the delivery backend
retains operation ownership. Deployment and deployment-environment journal events invalidate these cards through
the shared polling reader. Open confirmations keep their fixed identity and preview; a stale generation requires
a refreshed preview and another explicit click. Stable identity-scoped intent keys survive a lost reply and reload.
These cards have the same documented asynchronous view-refresh limitations as other views.

The native bridge explicitly allows the delivery preview, record, environment and history GET routes and `recipe`
query parameter. Deployment writes still go through `/operations` with the same envelope and idempotency key.
The restricted native GitHub opener is unchanged; arbitrary provider/enterprise origins are not supported by it.

`npm run test:delivery` runs the real daemon's delivery fixture with fake GitHub/BAT/runtime providers and serves
this worktree's generated assets. It requires the delivery backend and its dev dependencies; while the changes
are on separate branches, set `BATC_DELIVERY_ROOT` to that backend worktree. It covers both languages at
390/768/1440px, cursor paging, readiness/scope refusals, fixed confirmations during polling, stale previews,
double clicks, deploy-only retries, provider URL filtering, and lost-reply keys across reopening/reloading.
Only a legacy backend's expected `/bootstrap` 404 is excluded from console-error checks; this does not claim
checkpoint support for that backend. The CI UI fixtures separately exercise paired checkpoint polling through
browser HTTP and mocked native IPC. Neither fixture is a live deployment or Windows WebView acceptance test.

## Packaging and lifecycle

```sh
# Windows, from a configured Visual Studio/Rust environment
npm run tauri -- build --bundles nsis

# Linux, with WebKitGTK 4.1 and AppIndicator development packages
npm run tauri -- build --bundles deb

# Local native fixture smoke after a debug package build (Linux + Pillow/xdotool/Xvfb)
npm run tauri -- build --debug --bundles deb
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- node tests/native-smoke.mjs
```

The app bundles frontend assets and does not require Vite in production. Closing the main window hides it; the tray offers Open Dashboard and Quit Dashboard. Quitting does not stop central tasks. The single-instance plugin focuses the existing window in the current desktop session. This plugin is not the Fleet cross-Windows-session ownership protocol; another interactive Windows session is not yet fenced. Because this slice starts no supervisor, it cannot start a second tunnel owner.

The desktop workflow packages unsigned Windows NSIS and Linux deb artifacts for validation. Signing, updater channels, macOS packages and release publishing are not configured.

## Evidence and remaining acceptance

On the Linux development host: both frontend builds, Rust compilation/tests/clippy, existing Python static allowlist/CSP test, and Chromium browser/IPC-mock tests passed. The separate `test:central` integration uses the real Python HTTP API and journal with MockBat: signed checkpoint replay, actual retention reset, and draft recovery passed through the generated browser UI. Browser screenshots at 390/768/1440 preserve the original dashboard layout. A debug deb was built. The genuine packaged Linux WebKit view read a loopback fixture's capabilities/bootstrap/data/events without Vite; a window-manager close event hid it while retaining the process, and a second app invocation exited and restored the same window. This verifies close handling and instance handoff, but not a physical tray interaction. These are fixture results, not live BAT/central service acceptance.

Windows installation, actual Windows tray behavior, cross-session fencing, production credentials, native files, Fleet parity, autostart, signed updates, and end-to-end work against real central/BAT hosts remain unvalidated or unimplemented. This commit is an R02 foundation and does not claim M1 or product v1 completion.

Implementation references: [Tauri capabilities and application commands](https://v2.tauri.app/security/capabilities/), [tray](https://v2.tauri.app/learn/system-tray/), [single instance](https://v2.tauri.app/plugin/single-instance/), [system opener](https://v2.tauri.app/plugin/opener/), [Windows installers](https://v2.tauri.app/distribute/windows-installer/).


The shared confinement and cleanup slice displays persisted creation claims separately from current verification, including the unverified Codex/BAT gap. Checkpoint continuation and integration repair keep the chosen agent. It ports the existing central cleanup preview, explicit reviewed apply, retained-content list, tombstones, and operation item receipts; restoration remains unavailable.

Cleanup drafts and uncertain apply requests use the captured backend/account namespace. An uncertain reply keeps the exact signed preview, fingerprint, and operation key on reload; switching accounts cannot reuse them. A target/choice edit invalidates an in-flight preview, and cleanup events await history and retained-content refresh without rebuilding the reviewed form. Native cleanup preview IPC accepts only typed central IDs, booleans, and at most 500 resource IDs per choice; exact cleanup read routes have their own query allowlists. Apply still uses the existing central operation journal.

`npm run test:cleanup` runs generated shared assets against real cleanup HTTP endpoints, temporary real Git repositories and MockBat. Set `BATC_CLEANUP_ROOT` to an independently integrated backend checkout while this portable UI branch is stacked before cleanup backend integration. This check covers signed preview, reviewed apply, actual temporary worktree reclamation and per-item receipts. Browser/native IPC fixtures also cover lost replies, identity separation, deferred events and both languages at 390/768/1440 widths. These tests do not prove live OS confinement or complete M1 acceptance.


The attachment slice reuses central immutable artifact revisions. Work-item input/result references and checkpoint-continuation inputs live in the same canonical form code. File objects remain in WebView memory; only text, references and exact operation intents are stored under endpoint/server/principal namespaces. An uncertain continuation reply retains its original source-head precondition, input manifest references and idempotency key after reopening. Changing accounts or leaving the form aborts delayed file reads/hashes before upload. Confirmed operation outcomes reconcile draft state without clearing newer edits.

Metadata upload admission is the existing `artifact.upload` operation. Binary content always targets `/api/v1/artifacts/uploads/op_<32hex>/content`; a backend `content_url` is never followed. Browser uploads use this same-origin route with redirects refused. Desktop sends an ArrayBuffer through raw Tauri IPC and only an operation ID as metadata; Rust validates the ID and a 16 MiB maximum before copying bytes to the fixed configured origin with its native credential. IPC headers are not forwarded. The UI uses the smaller of the advertised server file limit and the native limit. This avoids JSON/base64 overhead and adds no filesystem path or shell capability. Artifact reads are the exact list/revision routes; the existing-revision selector pages by the central cursor.

`BATC_ARTIFACT_ROOT=/path/to/integrated/backend npm run test:artifacts` uses generated assets against real central HTTP upload/operation endpoints and a local fixture artifact helper. Binary bytes were verified in a temporary managed worktree; MockBat is the only runtime. Browser/native IPC fixtures cover binary byte preservation, lost replies, source-head changes on reopening, account changes during a delayed file read, and both languages at three widths. Rust tests separately verify fixed routes, credential handling, binary bytes, size limits and refused redirects. The chooser is the WebView file input: a native filesystem picker, upload streaming/progress/cancellation, OS credential enrollment, direct attachment downloads, and full live R05/T08 acceptance remain pending.


## Observation UI (R04)

Session pages expose central connection, loading, tab, activity, lifecycle, enumeration and freshness separately, with each field's observation time, source and stale flag. Unloaded/no-tab/idle never imply an ended lifecycle. Host discovery shows recorded profiles, last successful observation, latest failure, read authority, methods, coverage and explicitly unscanned scopes; the desktop starts no additional scanner.

Session, known worktree and execution pages consume the existing history and relations endpoints. Each independently paged section retains its own server `as_of` and filters. New journal facts display a notice without replacing loaded pages. Explicit refresh starts a new snapshot; unknown occurrence times stay unknown and are distinct from recording times. Relations show stable IDs, roles, half-open sequence intervals, commands and evidence; only proven worktree IDs become links. History/relations grant no write authority.

Connection-scoped resource records are indexed by stable ID with explicit parent/linked-resource dependencies. Inventory walks `order=id` with gone records included, preserves loaded page count and filter selection, and keeps the visible scroll anchor on refresh. This is a refreshed inventory walk, not snapshot isolation. History pages remain mounted during session updates. During an open work-item edit, safety reads continue once per second while an event acknowledgment waits, so a later parent archive still disables actions without destroying the draft. General detail renders wait until the editor closes.

`npm run test:observation` checks the generated shared UI against actual central HTTP, the journal and MockBat: a newly observed pending question, fixed history pagination, execution/worktree relations and discovery. `BATC_OBSERVATION_PYTHON` can select an already prepared Python environment; the fixture always imports this checkout. Chromium browser/native IPC fixtures cover failed reads, stale pending refusal, linked completion, later parent archive, stable-ID inventory pages, and English/zh-TW layouts at 390/768/1440. These are fixtures, not live host acceptance. Native route permissions already cover these read-only endpoints.

Remaining R04 limits: history exposes kind and relation execution/closed filters but no time-range picker, event-type catalog or saved multi-resource queries. Inventory refreshes the loaded window rather than maintaining a persistent offline resource database; selected history state is retained while mounted, not across route changes. General project tree refreshes still defer under open drawers; central version/policy guards remain authoritative. Principal/backend switches and continuity resets continue to preserve only drafts in their own namespace. Pending preflight reads the latest persisted observation; central must still reject a changed live BAT tool-use ID. Native event streaming and full M1/T07 live acceptance remain unclaimed.
