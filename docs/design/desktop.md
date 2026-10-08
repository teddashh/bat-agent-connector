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

Event acknowledgment now waits for asynchronous and debounced view refreshes, including all sibling reads on a failed batch. A locally displayed refresh error retains the original cursor/checkpoint pair and pauses mutations; polling retries the same page. Open edits defer renders and acknowledgment until they can refresh without discarding input. A pending refresh alone does not disable connected, version-checked form saves; an actual failed read or continuity reset does. Delayed refreshes are bound to the original account and mounted view. This only covers existing subscriptions: R04 still owns pending-control refresh, relations/history presentation, and linked operation/parent-project invalidations; it does not claim all mounted-view data is covered or M1 complete.

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
