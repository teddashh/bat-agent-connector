# Managed desktop installation and background service

Status: **candidate source implemented; pending final validation**.
Owner clarification: 2026-10-10, following the README / website review. Formal signing, Mac notarization, update channels, Linux persistent vault, and human real host acceptance have been explicitly removed from agent delivery gates. This removed scope is distinct from the newly implemented candidate features.

The candidate source now implements the bundled managed runtime, auto personal identity, and a browser one-use ticket for secure local access. The setup flow includes BAT profiles configuration, explicit GitHub binding, and verification commands. For Windows, actual file locks and private storage are implemented. The shared frontend includes an adjustable tree, unread/model preferences, skills catalog, direct result links, repair workflows, and instructions that reflect honest limits.

*Note: PR #81 (draft) is not merged yet, and final full gates/native fixtures are running. The current installed release assets remain historical client validation unless a new packaging workflow artifact is produced. Do not claim the latest published release automatically bundles the new runtime.*

## User journey

1. Install the Windows or Mac package. It contains the matching runtime; users do
   not install Python, uv or developer tools first.
2. Start the application. It prepares its private data directory, managed Python
   central service and personal identity without hand-written JSON or copied tokens.
3. Connect BAT through an understandable host/profile flow. Import existing
   configuration where available; let the user choose the actual host and workspace.
   Account sign-in, host trust and provider authorization cannot be fabricated.
4. Open Dashboard from the tray / menu bar. A browser entry is sufficient for daily
   access; the Tauri window remains another client of the same shared frontend.
5. Keep Connector and the selected connections running in the background. Closing
   the browser or Dashboard window does not stop work. Show background / login
   startup settings and connection state in ordinary user language.

Joining a deployed central service remains an advanced alternative. Failure to
reach that configured service must never silently create a second database.

## Service and identity ownership

- Python Connector / Task Service remains the sole operation and journal authority.
  Rust owns local installation and service lifecycle, not business state.
- A persistent installation manifest binds the runtime version, data location,
  server identity, principal and owned service. Reopening, rebooting, upgrading or
  starting a second client recovers that installation instead of creating another.
- Use real cross-process ownership on every supported platform. A occupied port,
  stale PID or matching path does not prove ownership of a service.
- Pin runtime artifacts and verify package integrity. Do not download and execute
  an unversioned installation script to simulate a bundled environment.
- Keep bearer credentials out of command arguments, URLs, browser storage and logs.
  One-click browser entry needs an authenticated local handoff design; opening an
  unauthenticated dashboard and asking users to paste an API token is not completion.
- The managed service keeps a stable loopback endpoint or publishes a verified
  endpoint pointer. Preserve Host / Origin / CSRF boundaries and platform private
  storage protections. This does not authorize public unauthenticated hosting.

## Background behavior and recovery

Network recovery may retry connections and reads. It must not resend a possibly
accepted start, prompt, integration, merge or deployment. Recover the original
operation ID / request key and let central reconciliation decide its outcome.

The tray / menu bar should expose Open Dashboard, connection state and service
settings. Closing the visible UI is distinct from explicitly stopping an owned
background service. Stopping or upgrading must respect ongoing effects, locks and
saved receipts. Do not terminate a different installation or another user's BAT.

On login, start only the saved, owned installation and selected connections.
Reconnect with backoff; make unavailable hosts and account expiry visible. Neither
offline operation nor an expired credential permits creating a new owner or
switching to an unrelated service. Existing manual resources remain read-only.

Uninstall / reinstall and upgrade preserve data unless the user explicitly chooses
a reviewed deletion. New software must recover the same IDs and history. A browser
and Tauri connected together must observe one set of operations and permissions.

## Current implementation gap

The current packages include the Tauri client and configured native Fleet support,
but no provisioned Python central runtime. Native initial setup still asks for an
endpoint and actor. Windows central portability needs actual file locking, private
storage / ACL and reparse protection, atomic artifact publication and ownership;
removing `fcntl` imports or disabling security checks is not a port. Mac client
packaging and Keychain fixtures do not prove the complete managed installation.

This is installation engineering still to do, not a user prerequisite to normalize
in the product introduction. Existing manual deployment remains documented as the
development-trial / operator path while the normal installation is completed.

## Exit criteria

On the same fixed candidate, validate Windows, Apple Silicon and Intel Mac from a
clean user profile with no Python / uv, central config or token:

- Install, initialize the owned service and open an authenticated Dashboard without
  entering an actor, editing a config file or copying a long-lived token.
- Select / authorize BAT access and a repository, then dispatch a traceable managed
  session; absence of BAT configuration is a guided state, not a false ready result.
- Close the UI, reopen through the tray and browser, restart the client, and log in
  again: same central identity, data and work, without a second service owner.
- Disconnect the network and restart central mid-operation: recover the original
  work without duplicate starts or effects; retain uncertain evidence.
- Exercise occupied ports, invalid manifests, failed initialization, expired
  credentials and interrupted upgrades without overwriting unrelated installations.
- Preserve credentials, history and saved operation identities through upgrade and
  the documented reinstall path; verify cleanup of test-owned installations.

Packaging, native fixtures and real user-host acceptance remain distinct evidence.
See [the acceptance matrix](../product/acceptance-v2.md) and
[shared frontend lifecycle](shared-frontend.md).
