# Standalone Rust Fleet example

Follow the [public setup guide](../../docs/design/fleet-configuration.md) before use.
Copy this directory's `client` files into your own private configuration root:

- [Inventory](client/fleet-inventory.json)
- [BAT profile index](client/bat-profiles/index.json)
- [SSH aliases](client/ssh-config)

Use [fleet.example.json](../fleet.example.json) for the native app configuration.
Replace the documentation address, SSH user and fingerprint placeholder with your own
reviewed values. The placeholder deliberately fails trust validation. No credentials
or live deployment settings are included; legacy PowerShell/VBS scripts are not required.
