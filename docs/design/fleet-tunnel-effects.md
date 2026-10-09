# Native Fleet tunnel launch effects

This extends [the Fleet port contract](fleet-rust.md). It is a native-only effect component,
not a Tauri command, an activated supervisor or installed Windows acceptance.

`tunnel::Plan` derives a fixed SSH argument vector from validated inventory, the original
private selection snapshot, the configured route alias and a monitor epoch. It cannot add an
unselected connection or accept a command/forward supplied by the WebView. A newer selection
cannot authorize an older plan, including changes to legacy preferences while the primary
file is absent. Readiness and route eligibility remain separate requirements of the supervisor.

`tunnel::launch` rechecks configuration bytes, the data directory, complete selection snapshot,
current monitor identity and listener absence before spawning. Its `Platform` implementation
must hold the account monitor mutex, prove its own recorded incarnation and exact epoch, use
the OS-resolved system SSH executable, and retain the launch's process handle. An unknown
listener or owner refuses launch. The platform interface exposes no arbitrary shell command.

The fixed local `fleet-tunnel-intents/<name>.json` is saved before the process effect. Unknown
spawn/exit leaves this intent in place and blocks a second launch. A positively refused spawn
may remove only its unchanged intent. The successful child must have the exact executable,
argv, epoch, login and two equal held-handle observations. Both child and parent identity are
saved in the existing `fleet-tunnel-owners/<name>.json` format before returning ownership.

Publication stages and flushes a new file, then creates its final hard link without replacing
an existing path. Unsupported filesystems refuse. A leftover intent after completed owner
publication is conservative; recovery must read the owner record first. A failed publication
may stop only the retained newly launched handle. Unconfirmed exit or an existing owner file
retains the original intent; neither authorizes a repeat launch or killing another PID.
Owned files are compared before removal. This is not an atomic transaction against an
uncooperative local editor replacing ancestor paths or files during the final comparison.

Temporary-directory tests cover unchanged owner publication, occupied/foreign resources,
positive and uncertain spawn failures, selection/configuration changes, held-child rollback,
unknown exit, data-directory mismatch and an old plan presented with a fresh disconnected
selection.

The concrete Windows adapter in `windows_tunnel` holds the existing monitor mutex and
rediscovers the exact current native process/epoch before effects. It obtains the system
SSH image through [GetSystemDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemdirectoryw),
uses ordinary argument-vector escaping with `CREATE_NO_WINDOW`, and inherits the trusted
native environment needed by configured SSH routes. No PATH-based SSH lookup, shell,
raw command string or remote diagnostic text is exposed to the WebView.

A retained launch-handle duplication failure attempts a bounded rollback through the
original Child handle; only a positively ended child releases its intent. Local listener
checks require both connection refusal and a successful temporary bind. `ExitOnForwardFailure`
handles a listener appearing after the check; this is not a transaction with unrelated apps.
Native fixtures operate only a temporary loopback listener and the test's own bounded child.
Linux Clippy and an isolated MSVC exact-module/test-source compile pass; the harness excludes
network dependencies whose Windows C toolchain is unavailable locally. It is not Windows
execution evidence. Lifecycle stop/recovery, route worker integration and the desktop
supervisor remain required before runtime activation.
