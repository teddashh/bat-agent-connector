# Windows Fleet and desktop resources

**English** · [繁體中文](windows.zh-TW.md) · [Product overview](../README.md)

Windows Fleet is the product's local connection and startup layer. It is already
integrated into the Tauri client. Python Connector / Task Service remains the
authority for agent work, and BAT executes that work on the chosen host. A Windows
client can use a Linux central service; it does not need a Windows-native central
to manage its existing Fleet connections.

## What runs where

| Layer | Responsibility |
| --- | --- |
| Windows Tauri / Fleet | Selected background connections, SSH tunnel ownership, route/readiness checks, BAT profile launch, login choices, credentials, files and tray. |
| Python Connector / Task Service | Agent identities, authorization, dispatch, task coordination, operations, receipts and history. |
| BAT hosts | Workspaces, human sessions and worktrees, plus separate agent-owned managed resources. Human BAT desktop / mobile access continues. |
| GitHub / configured deployment target | Published commits, integration PRs, merge and deployment evidence through central operations. |

Project organization is one Dashboard view over this system. Project Hub supplies
interaction references; it is not the runtime or data backend.

## Use an existing Windows installation

The candidate source implements the bundled managed runtime and background environment automatically, though it is pending final validation (draft PR #81). The frontend now includes an adjustable tree, unread and model preferences, a skills catalog, direct result links, repair workflows, and instructions presenting honest limits.

For a supervised trial today:

1. Get `desktop-Windows-unsigned` from the [candidate CI build](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml).
   This is the new candidate artifact. No new version number, tag, or release has been invented yet.
   Final validation is pending for root to finalize.
2. Connect the trusted central and native credential using the
   [current desktop setup](getting-started.md#5-connect-the-desktop-client).
3. If Fleet is already deployed, keep its reviewed Kit inventory, BAT profile index
   and SSH configuration. The native adapter reads that same configuration. Use
   [fleet.example.json](../desktop/fleet.example.json) and the
   [installation contract](design/fleet-installation.md) to bind the existing Kit.
   The sample is not a complete installation; no private topology belongs in this repo.
4. In Connection settings, inspect the current backend and choose **connections**,
   **BAT profiles**, and **Dashboard** independently. Preview prerequisite connections
   before applying or launching. Dashboard-only works without a local BAT executable.
5. Read readiness per host. Tunnel, pinned TLS, BAT authentication/workspace and
   central observe access are separate checks. For Tailscale sign-in, open the installed
   Tailscale app from its local panel, sign in there, then refresh status.
6. Review login-picker / saved launch behavior. An omitted `backend` retains
   **PowerShell** for compatibility. Rust is integrated but taking over an existing
   owner requires the explicit migration flow; installing a new Dashboard is not migration.

Closing the Dashboard hides its window and leaves background work running. Explicit
Quit is different: it requests normal shutdown only of the proven owned local Fleet
monitor and refuses uncertain ownership. Neither action ends central tasks or manual
BAT sessions. Configured remote central bootstrap uses a fixed SSH recipe; it does
not install an arbitrary service or silently create another central database.

## Resource index

| Topic | Maintained resource |
| --- | --- |
| Connections, windows and login choices | [Native Fleet integration](design/desktop-fleet-native.md) · [shared UI](../desktop/src/fleet-desktop.js) |
| Rust runtime and PowerShell compatibility | [Fleet core](../desktop/fleet-core/README.md) · [backend routing](../desktop/src-tauri/src/fleet.rs) |
| Tailscale, configured fallback routes and readiness | [Route policy](design/fleet-routes.md) · [Tailscale sign-in](design/tailscale-recovery.md) |
| Startup and owner migration | [Migration](design/fleet-migration.md) · [Windows ownership](design/fleet-windows.md) |
| Selected central service startup | [Fixed bootstrap recipe](design/fleet-bootstrap.md) |
| Credential Manager, tray and native files | [Desktop client](design/desktop.md) · [file operations](design/native-files.md) |
| Validation packages and installed fixtures | [Desktop CI](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml) · [acceptance matrix](product/acceptance-v2.md) |

Windows installation/WebView fixtures, Fleet source tests and a real working day
against the user's SSH / Tailscale / BAT hosts are different evidence. Complete
managed installation, live Fleet acceptance and signed upgrades remain open product
work. Mac Dashboard support does not establish a Mac port of Windows Fleet.
