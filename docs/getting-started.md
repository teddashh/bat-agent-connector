# Installation and first use

[Product overview](../README.md) · **English** · [繁體中文](getting-started.zh-TW.md)

## The intended installation experience

The desktop package should prepare the runtime, data, personal identity and background Connector for you. After guided BAT / GitHub authorization, open Dashboard from the tray or menu bar. Keep the service connected while the window is closed. You should not need to install Python, edit JSON or enter an API actor.

**That managed installation is not complete in the current validation packages.** The instructions below are the interim development-trial / operator path, not the intended onboarding for every user. Joining an already operated central service remains a supported advanced choice. [Managed installation contract](design/managed-installation.md).

## Choose a trial path

| Your situation | Start here |
| --- | --- |
| Your environment already has a central service | Get its trusted Dashboard address and your own API credential from the operator. Open Web, or follow [desktop connection](#5-connect-the-desktop-client). |
| You operate the first environment | Set up a Linux central host using the steps below. |
| You only want to observe BAT through an agent | Use a configured central identity and the read-only MCP path under [CLI and agent access](#cli-and-agent-access). |
| You expect an installer with no engineering setup | That is the required product experience, but it is not yet available. Follow the [implementation record](product/implementation-status.md) and [Releases](https://github.com/teddashh/bat-agent-connector/releases). |

## 1. Prepare a central host

For the documented setup, use Linux and Python 3.10–3.13. The central host needs access to your BAT server. For managed Git work it also needs the configured SSH / Git access, a Connector-owned managed root and an explicitly bound repository. Windows and Mac desktop support does not imply Windows / Mac central acceptance.

The two credentials serve different purposes:

| Credential | Used by | Purpose |
| --- | --- | --- |
| BAT remote token | Connector to a BAT host | Access BAT's remote protocol, with its certificate fingerprint pinned. |
| Connector API token | Dashboard or MCP client to central | Identify the caller and authorize central actions. Issue one per client / actor. |

Do not use a BAT remote token in the Dashboard API login field.

## 2. Install Connector

Install with `uv` on the central host. Until a formal release is selected, pin a reviewed commit instead of silently following changing `main`. This example uses the documented product baseline:

```bash
uv tool install 'git+https://github.com/teddashh/bat-agent-connector@15b2048de5c2ec3a31e0845ce76a79b612d1c32e'
batc --help
```

A development checkout can instead use `uv sync --locked --extra dev`, with `uv run batc` for the commands below. Keep the desktop and central contract versions compatible; the desktop refuses incompatible identity / contracts.

## 3. Configure BAT access

If this host has the BAT desktop client's profiles:

```bash
batc import-bat
batc hosts
```

Import writes `~/.config/bat-agent-connector/hosts.toml` with writes disabled. It stores the endpoint, pinned TLS fingerprint and a **token reference**, not the token value. `batc hosts` probes configured hosts; a successful probe does not prove Git access or deployment readiness.

For a different profile location, use `batc import-bat --profiles-dir /path/to/profiles`. Preview generated configuration with `--output -`. Do not add `--force` merely to bypass an existing configuration.

Without local BAT profiles, configure [hosts.example.toml](../examples/hosts.example.toml) with the actual BAT endpoint, trusted fingerprint and an appropriate `token_ref`:

- `env:NAME`: resolve from the service's private environment.
- `file:/path`: resolve from a private token file.
- `bat-profile:ID`: resolve from the supported BAT client token store.

A default profile path is not a cross-platform discovery guarantee. Preserve the original BAT configuration and keep credentials out of source control.

## 4. Start central and open Web

Run the service in one terminal on the central host:

```bash
batc serve
```

The default is `127.0.0.1:18796`. The process must keep running; this command does not install an autostart service. An already owned service may report `OWNER_CONFLICT`: use that owner instead of creating another database.

In a second terminal on the same host, issue an observation identity:

```bash
batc api-token issue --actor personal-dashboard --scope observe
```

The token is printed once. Keep it private. Open `http://127.0.0.1:18796/dashboard/` on that host and use the Connection screen to sign in. Pending, Projects and Sessions should become available. This initial identity intentionally cannot dispatch or edit work.

If the central host is remote, use an existing verified tunnel. An example with a previously configured and trusted SSH alias is:

```bash
ssh -N -L 18796:127.0.0.1:18796 central-alias
```

Then open the same loopback Dashboard address on the client machine. Keep that tunnel running. Do not expose the service by changing its bind address or disabling Host / Origin checks. The service does not currently provide a general public-hosting ingress.

## 5. Connect the desktop client

Windows also includes native Fleet connectivity, BAT profile launch and login
controls. Keep the [Windows usage and resource guide](windows.md) alongside this
central setup guide; these are complementary parts of the product.

Download the correct validation artifact from a successful [desktop workflow](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml):

| Platform | Artifact | Package |
| --- | --- | --- |
| Windows x64 | `desktop-Windows-unsigned` | NSIS `.exe` |
| Mac Apple Silicon | `desktop-macOS-arm64-validation` | `.dmg` |
| Mac Intel | `desktop-macOS-x64-validation` | `.dmg` |
| Linux | `desktop-Linux-unsigned` | `.deb` |

Artifacts may expire and can require GitHub sign-in. Windows packages are unsigned and Mac validation bundles are ad-hoc signed; this is not the formal public distribution or update channel. Review the source and run receipts. If platform policy prevents installation, use Web for the trial rather than weakening system-wide checks.

On Windows / Mac:

1. Install and launch the package for your platform.
2. Enter the trusted central address and the expected actor used when issuing the API token (for example, `personal-dashboard`).
3. Review the native connection confirmation. Only confirmation creates the first `central.json`; existing invalid configuration is not silently overwritten.
4. Choose **Add credential** and provide the Connector API token in the native secure prompt. It is verified before saving to Windows Credential Manager or macOS Keychain.
5. Connect and confirm the expected identity and central data. Web can remain open at the same time.

These steps describe today's interim connection flow. The normal managed installer must eliminate steps requiring manual endpoint / actor / token setup for a new local environment.

Linux native credentials currently use the deliberate memory-only `BATC_DESKTOP_TOKEN` adapter; persistent enrollment is not implemented. See [the native credential contract](design/desktop.md#configure-the-native-client). Web is the simpler Linux trial entry.

Native configuration locations and recovery are in [desktop.md](design/desktop.md). **Forget saved credential** only removes that local record; it does not revoke the API token on central. Replace credentials through Connection, never through a pasted token URL.

## 6. Enable useful work deliberately

Observation working is the first checkpoint. For actual dispatch, the operator configures:

1. The selected host's `writes` and `orchestrate` gates, owned managed root, Git / SSH runner and confinement policy.
2. An explicit repository-to-host/workspace binding under the existing `github.repos` configuration. A project name, workspace path or Git remote alone is not that binding.
3. The client's scopes for the intended action. A typical project-dispatch identity needs `observe`, `manage` and `start`; session interaction uses `operate`. Integration, acceptance, merge, deployment and cleanup have separate scopes.

Example binding (replace every demonstration value with the reviewed destination):

```toml
[[github.repos]]
repository = "example/project"
sync = { remote_url = "git@github.com:example/project.git", bindings = [{ host = "worker", workspace_id = "exact-workspace-id" }] }
```

This snippet is not the complete host / GitHub configuration and does not grant integration push or deployment permission. Follow [repository setup](design/repository-sync.md) and the [configuration example](../examples/hosts.example.toml).

In Dashboard, create a project and explicitly choose its configured repository. Open project dispatch, choose the destination and branch, review its fixed commit, add original instructions and optional attachments / model, then submit. Return to the project to follow the work and its delivery entry.

Read the integration preview before adding results to a PR. Merge and deployment require their own configuration and scopes; deployment additionally needs a recipe with actual source-version / health verification. [Delivery setup](design/delivery.md).

## CLI and agent access

The CLI offers the same observation and operation records:

```bash
batc hosts
batc inventory
batc history --help
batc relations --help
batc op --help
batc repository --help
batc delivery --help
batc resource-cleanup --help
```

Register `bat-agent-connector-mcp` in the MCP client's supported configuration. A common read-only JSON form is:

```json
{
  "mcpServers": {
    "bat": {
      "command": "bat-agent-connector-mcp",
      "args": ["--principal-only", "--read-only"]
    }
  }
}
```

Run the configured central service and give this MCP process its own scoped `BATC_API_TOKEN` through private environment configuration, including `observe` for reads. Ensure it can find the executable and intended configuration. `--principal-only` keeps the agent on its authenticated central identity; retain it when enabling writes. Remove only `--read-only` when the client is meant to act; host gates and scopes still apply. Set `BATC_TASK_URL` privately if central uses a different RPC endpoint.

The operator compatibility mode without `--principal-only` includes local-admin read fallback and direct Fleet tools. It is not a scope-isolated agent endpoint. A trusted local operator can use `bat-agent-connector-mcp --read-only` for direct BAT observation without the central workflow, but this is not the default for a shared agent integration.

The optional loopback MCP HTTP transport is a separate adapter:

```bash
bat-agent-connector-mcp --principal-only --read-only --http --port 8765
```

This serves MCP at `http://127.0.0.1:8765/mcp`; it is not the Web Dashboard address. Use the [canonical skill](../skills/bat-agent-connector/SKILL.md) and [matching agent adapters](agent-skills.md) for durable work and recovery. Task Service recipes have additional settings; a queued task with the planner disabled does not prove dispatch failure. [Task Service](design/task-service.md).

## First-connection and workflow troubleshooting

| What you see | What to check / do |
| --- | --- |
| First desktop screen asks for central / actor | This is the current client-only installer gap. Use the configured trial path above; it is not the desired permanent onboarding. |
| No Dashboard response | Is `batc serve` still running? Is the trusted tunnel open? Verify the configured address; do not start a second owner blindly. |
| Credential rejected | Use a Connector API token, not a BAT token. Check expected actor, `observe` scope, expiry, API contract and the intended central identity. |
| Connected, but no hosts / sessions | Verify `hosts.toml`, BAT remote access and token references. Retain offline / stale evidence; an empty read does not prove work stopped. |
| No repository in project dispatch | Configure the explicit `github.repos[].sync` binding and associate that repository with the project. |
| An action is disabled | Check client scopes, host gates, ownership, destination configuration and the reason shown beside the action. |
| Start accepted, then connection lost | Keep the original operation ID and request key. Read its receipt; do not submit a new job to guess the result. |
| An agent stops outputting | Check pending input, permissions and observed activity. Idle is not completion, and completion is not deployment. |
| Cleanup is refused | Read the retention reasons. Do not clear reservations or remove a worktree that may still have a writer. |
| Desktop closes but work keeps running | Central and the UI have separate lifecycles. Close-to-tray / Dock behavior also differs from explicit Quit. |
| Fleet does not start | Fleet needs its own configured installation. A missing `backend` retains the PowerShell compatibility default; installing Dashboard does not automatically migrate ownership to Rust. |

## What counts as a successful trial?

Use one small real project, with a known commit and destination. Confirm: manual work stays unchanged; managed work has traceable ownership; its result reaches the intended PR; any deployment reports the actual version; disconnect / reopen finds the same work; cleanup preserves history. Keep supervision while the [full acceptance matrix](product/acceptance-v2.md) and managed installation are unfinished.
