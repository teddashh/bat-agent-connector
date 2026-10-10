# Public Windows Fleet configuration

[Windows guide](../windows.md) · [繁體中文摘要](#繁體中文設定摘要)

The packaged Windows client contains the Rust Fleet runtime. A new installation can
use the public [configuration example](../../desktop/fleet.example.json) and
[example data directory](../../desktop/fleet.example/) without another repository,
PowerShell Fleet scripts or VBS launchers. Windows OpenSSH and BAT remain separate
installed tools. This is the optional native connection layer; the bundled central
and shared Web Dashboard do not require Fleet configuration.

## New Rust installation

1. Copy `desktop/fleet.example/client` into a new private local directory, for example
   `C:\Tools\ConnectorFleet\client`. Use a directory controlled by your Windows account.
   Do not overwrite an existing Fleet installation or its ownership records.
2. Edit the three example files below for **your** BAT host. The documentation-only
   `192.0.2.10` address, SSH user and fingerprint placeholder cannot connect to a real
   deployment. The placeholder fingerprint intentionally fails profile validation.
3. Make the reviewed aliases available to Windows OpenSSH. The native SSH command uses
   your normal `%USERPROFILE%\.ssh\config`; it does not pass `-F`. Add an explicit
   `Include C:/Tools/ConnectorFleet/client/ssh-config` there, or keep matching literal
   host entries in both files. Preserve existing SSH settings. Verify the server's
   host key and that the alias works noninteractively with your chosen key before
   enabling its Fleet connection. Fleet neither creates keys nor approves host keys.
4. In BAT, configure the matching remote profile and its token using BAT's own trusted
   connection setup. Match the profile ID, tunnel loopback address/port, remote workspace
   profile ID and certificate fingerprint to the example index. Fleet checks the live
   BAT profile against this index; editing only the Fleet index cannot establish trust.
5. Save the example `fleet.json` in `%APPDATA%\io.betteragent.dashboard\fleet.json`,
   beside `central.json`, with the actual local root and explicit `"backend":"rust"`.
   `kit_root` is a compatibility field name for this configuration root; no Kit checkout
   is needed. Keep the `client` subdirectory. Absolute local paths are required; mapped
   network drives, UNC and device paths are refused.
6. Reopen Dashboard and inspect **Connection / Fleet**. Review background connections,
   BAT windows and Dashboard separately before starting. Validate configuration and
   read distinct tunnel, TLS, BAT and central readiness results. Startup is optional:
   preview and apply the Rust login choice through the existing native controls.

The initial example defines one BAT host and disables the external-central route
(`connector.ssh_alias: null`). The bundled central's normal **Open Dashboard** flow is
independent. To use Fleet's external-central connection or Dashboard selection, add
an explicitly trusted SSH alias, set its loopback forwarding endpoints, and configure
its separate observe-only credential as described below. Do not reuse the bundled
central's mutation credential or choose an already occupied local listener.

## Files and schema

All JSON uses UTF-8, exact field names and no duplicate keys, including case variants.
Unknown inventory fields refuse. See the public
[parser](../../desktop/fleet-core/src/inventory.rs) for bounded validation and the
[configuration loader](../../desktop/fleet-core/src/configuration.rs) for byte binding.

| File | Contents and required relationship |
| --- | --- |
| `fleet.json` | `kit_root`: absolute root containing `client`; `backend`: explicit `rust` for a new standalone installation. Omitted backend means legacy PowerShell. |
| `client/fleet-inventory.json` | Version-1 inventory with `fleet_version`, `direct_probe_ms` (1–5000), `cloudflare_access_hosts`, `credentials`, `fingerprints`, nonempty `hosts`, `provisioning_profiles`, and `connector`. |
| `client/bat-profiles/index.json` | `profiles` and `activeProfileIds`. Each selected remote profile has `id`, `type: "remote"`, `remoteHost`, `remotePort`, `remoteProfileId` and a trusted `remoteFingerprint` (64 hex digits or colon-separated SHA-256). IDs and endpoint/pin values must match the inventory and live BAT profile. No token belongs here. |
| `client/ssh-config` | Literal `Host` aliases referenced by inventory routes. This file and the user's SSH config are bound into the configuration snapshot. The validator does not expand `Include` directives. |

Each `hosts` entry has these fields:

| Fields | Meaning |
| --- | --- |
| `name`, `profile`, `label` | Stable logical host ID, BAT profile ID and display label. Host names/profile IDs are unique ignoring case; `connector`/`default` are reserved. |
| `local`, `target` | Client IPv4 loopback `address:port` and the BAT endpoint reached from the SSH server. Each BAT host needs a distinct local loopback address. |
| `probe`, `routes`, `provision_route` | Optional top-level probe (`null` allowed); ordered routes (`direct`, `lan`, `cf`) with a literal SSH `alias`; and one configured route kind. `lan` needs a probe endpoint. `direct` is the Tailscale route, requires a `100.64.0.0/10` IPv4 probe, and must match the top-level probe. `cf` needs `access_host` listed in `cloudflare_access_hosts`; configure its SSH ProxyCommand separately. No fallback route is invented. |
| `bat` | `remote_profile_id`, `credential_ref`, `fingerprint_ref`, `protocol: "bat-remote/v2"`, and `min_version`. Credential/pin references must resolve to the same BAT profile. |
| `workspace_bindings` | Array of `{id, workspace_id, required}` using actual BAT workspace IDs; empty is allowed. |
| `connector_endpoint` | Optional additional BAT endpoint metadata (`null` in the example); when present requires `endpoint`, `remote_profile_id`, `credential_ref`, `fingerprint_ref`. This is separate from the central HTTP connector below. |

`provisioning_profiles` lists every host's profile exactly once. `credentials` maps
logical references to `{kind:"bat-profile-token", profile_id}` or
`{kind:"windows-dpapi", name}`. `fingerprints` maps references to
`{kind:"bat-profile-pin", profile_id}`. No literal token or private key is stored in
these documents.

The `connector` object requires `name:"connector"`, `label`, `local`, `target`,
`ssh_alias` (a configured literal alias or `null`), `dashboard_path`, `credential_ref`,
`supported_api_versions:[1]`, `min_contract_version`, and nonempty `required_features`.
The example's required features are `inventory` and `events_stream` with contract
`2026-10-08`. A configured central credential must reference `windows-dpapi` and its
API identity must have **exactly observe scope**. A running service or listening port
alone does not establish API readiness.

## Credentials and optional bootstrap

Fleet reads the current BAT data directory under `%APPDATA%\BetterAgentTerminal`,
or the legacy `%APPDATA%\org.tonyq.better-agent-terminal` when the former is absent.
It never searches another profile or falls back to a Dashboard credential. BAT tokens
use the existing supported `profiles/remote-tokens.enc.json` format: `enc:false` and
string `data` containing a `tokens` map. An encrypted or unsupported store reports
unavailable; do not overwrite a user's BAT store to bypass that result. The live
`profiles/index.json` remains the independent source for profile drift checks.

For an optional external central, issue a separate observe token on that central:

```sh
batc api-token issue --actor fleet-observer --scope observe
```

Store that token on Windows under the same account that runs Fleet. This public
PowerShell command writes the supported DPAPI CurrentUser format without printing
or putting the token in command history. Set `$fleetData` to the **existing selected**
BAT data directory; do not create a competing data root. For the example credential
name, run:

```powershell
$fleetData = Join-Path $env:APPDATA 'BetterAgentTerminal'
if (-not (Test-Path -LiteralPath $fleetData -PathType Container)) { throw 'Select the existing BAT data directory first' }
$fleetCredentials = Join-Path $fleetData 'fleet-credentials'
New-Item -ItemType Directory -Force -Path $fleetCredentials | Out-Null
$fleetSecret = Read-Host 'Separate central observe token' -AsSecureString
try {
    $fleetProtected = ConvertFrom-SecureString -SecureString $fleetSecret
    [IO.File]::WriteAllText((Join-Path $fleetCredentials 'connector-observe.dpapi'), $fleetProtected, [Text.Encoding]::ASCII)
} finally {
    $fleetSecret.Dispose()
    Remove-Variable fleetSecret, fleetProtected -ErrorAction SilentlyContinue
}
```

Do not use this command to replace an existing credential without reviewing the
selected central and principal. [Credential contract](fleet-credentials.md).

Cold bootstrap is optional and disabled without a local recipe. Its public server
implementation is [fleet_bootstrap.py](../../src/bat_agent_connector/fleet_bootstrap.py)
with [the fixed entry script](../../scripts/bat-connector-bootstrap-v1). Follow the
[bootstrap deployment contract](fleet-bootstrap.md#fixed-linux-server-guard) to
install that module in the fixed interpreter, deploy the helper at the fixed path,
and bind an already initialized systemd user service, journal, lock and protected
recipe. It does not require a private repository. It never creates a replacement
central after a failed probe, and this guide does not imply a helper is installed.

## Existing PowerShell installations

Keep existing configuration and ownership evidence. An omitted `backend` still
selects PowerShell and requires the existing `client/fleet-desktop.ps1` facade.
PowerShell monitor migration additionally requires `bat-connect.ps1`; its login
shortcut requires `Open BAT.vbs`. These are optional externally supplied legacy
components, not files shipped by the standalone Rust example. Use the native
migration flow to change an existing owner; do not hand-edit its backend or delete
its monitor records. Rust-to-PowerShell requests without the required legacy files
fail before configuration/startup publication. Foreign or unprovable shortcuts and
processes remain untouched.

## 繁體中文設定摘要

新的 Windows Rust Fleet 可直接使用本 repo 的公開範例，不需其他 repository、
PowerShell Fleet scripts 或 VBS launcher。這是選用的連線管理層；包內中央與 Web
Dashboard 不需要先設定 Fleet。

1. 將 `desktop/fleet.example/client` 複製到自己控制的本機目錄，例如
   `C:\Tools\ConnectorFleet\client`，不要覆寫既有 Fleet。
2. 在 inventory、profile index 與 SSH 設定填入自己的主機、profile ID、loopback
   位址／port 與可信憑證指紋。`192.0.2.10` 與指紋文字是不能直接使用的範例，
   指紋未替換時驗證會失敗。範例不包含私人主機或任何 token。
3. 在 `%USERPROFILE%\.ssh\config` 加入明確的
   `Include C:/Tools/ConnectorFleet/client/ssh-config`，或保持兩份設定內的實際
   alias 一致。先自行核對 SSH host key 與非互動金鑰登入；Fleet 不建立金鑰或批准信任。
4. 用 BAT 自己的設定建立相符連線 profile 與 token；Fleet 會核對 BAT 實際 index
   與 token store，不能只改 Fleet index 就視為已連線或已信任。
5. 將 `fleet.example.json` 另存於
   `%APPDATA%\io.betteragent.dashboard\fleet.json`，填入實際 `kit_root`，明確保留
   `"backend":"rust"`。`kit_root` 是相容欄位名稱，不表示需要 Kit checkout。
6. 重開 Dashboard，在「連線／Fleet」檢查設定，分別選擇背景連線、BAT 視窗與
   Dashboard，再預覽／啟動。登入啟動也透過原生預覽與套用，不手改既有 owner。

範例的外部中央 SSH alias 是 `null`，不啟用外部中央路由。包內中央的「開啟 Dashboard」
維持獨立。需要 Fleet 連至外部中央時，另配可信 SSH alias、未占用的 loopback port
及**只有 observe 權限**的獨立 token；上面的 PowerShell 範例可保存成目前帳號的 DPAPI
格式，不需私人安裝工具。BAT 加密 token store 不在目前讀取格式內，會如實顯示不可用，
不要覆寫 BAT 的資料來繞過檢查。

已有 PowerShell Fleet 時保留原設定，未指定 backend 仍是 PowerShell。切換須沿用
原生遷移與擁有權檢查。只有選用舊 backend 才需要外部的 PS／VBS 檔案，公開 Rust
範例不附帶它們。自動啟動遠端中央的 helper 與 recipe 另依公開 bootstrap 合約配置；
缺少設定不會偷偷建立新服務或新資料庫。
