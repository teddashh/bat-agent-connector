# Trusted native Fleet installation and executable entries

`installation::Snapshot` reads the fixed local `fleet.json` supplied by native app
configuration. Its bounded, duplicate-rejecting document accepts `kit_root` and the
optional `backend` (`powershell` or `rust`). Existing documents default to PowerShell;
reading a document never starts or migrates a monitor.

`kit_root` is the installation/repository root already used by the desktop adapter.
The actual Kit configuration and monitor scripts are under its validated `client`
directory. Native inventory/discovery therefore receive `client_root()`, preserving
PowerShell's existing inventory/index/SSH paths and configuration fingerprint.
The facade script must remain within that directory. Windows paths must be absolute
and local before and after canonicalization; UNC, device and mapped-network paths
are refused. Normal drive spelling is retained for PowerShell and exact argv proofs.

The snapshot retains original config bytes and declared/resolved paths. It rejects
config leaves that are links/reparse points, missing or oversized inputs, unknown
fields/backend, changed bytes or resolved installation paths. Call `verify_current`
immediately before local effects. This check detects configuration drift; trusted
installation ancestors and executable code remain prerequisites, not attested by a
path hash. No configuration, executable path or credentials enter the WebView.

`Entry::parse` recognizes an ordinary Dashboard launch, or exactly one of these
native executable argument sets:

- `--fleet-supervisor --fleet-config <absolute-local-fleet.json>`
- `--fleet-login --fleet-config <absolute-local-fleet.json>`

Additional flags, arbitrary commands, URLs and relative config paths refuse.
Supervisor parsing happens before Tauri single-instance/WebView initialization so
the window singleton cannot swallow a monitor process. The CLI parser alone grants
no ownership: the launcher and supervisor still require current account/process
evidence, common mutexes and configuration/selection checks. Login startup entries
remain explicit migration-owned changes; no installation/autostart effect occurs here.

Tests use temporary installation trees and synthetic files. Linux tests and isolated
Windows compilation are source evidence only; packaged startup/migration acceptance
requires actual Windows execution.
