# 安裝與首次使用

[產品介紹](../README.zh-TW.md) · [English](getting-started.md) · **繁體中文**

## 正常安裝應該是什麼樣子？

桌面安裝包應替你準備 runtime、資料、個人身分與背景 Connector。引導完成 BAT／GitHub 授權後，從系統匣或選單列點一下開 Dashboard；關視窗時背景服務繼續維持連線。不應要求你先裝 Python、手改 JSON 或輸入 API actor。

**目前驗證包還沒完成這套 managed 安裝。**下面是過渡期的開發試用／操作者設定，不是每個一般使用者都應承擔的 onboarding。加入別人已維護的中央環境仍是進階選項。[安裝合約](design/managed-installation.md)。

## 選擇目前的試用方式

| 你的情況 | 從這裡開始 |
| --- | --- |
| 已有維護中的中央服務 | 向維護者取得可信 Dashboard 網址和自己的 API 身分，開 Web 或接上桌面 client。 |
| 由你建立第一套環境 | 依下列步驟建立 Linux 中央。 |
| 只想讓 Agent 觀察 BAT | 準備已配置中央的個別身分，使用下方唯讀 MCP 設定。 |
| 想下載後直接開始，不做工程設定 | 這就是正式產品要求，但現有包尚未達成。可查看[實作紀錄](product/implementation-status.md)及 [Releases](https://github.com/teddashh/bat-agent-connector/releases)。 |

## 1. 準備中央主機

本文使用 Linux 與 Python 3.10–3.13。中央必須能存取 BAT server；若要 managed Git 工作，另需已配置的 SSH／Git、Connector 自有 managed root 及 repository 明確綁定。Windows／Mac 桌面支援不等於相同平台的中央已驗收。

兩種 token 用途不同：

| 憑證 | 誰使用 | 用途 |
| --- | --- | --- |
| BAT remote token | Connector 連 BAT 主機 | 使用 BAT 遠端協定，搭配固定 TLS 指紋。 |
| Connector API token | Dashboard／MCP 連中央 | 識別呼叫者並授權中央操作；每個 client／actor 分別簽發。 |

Dashboard 登入欄位不能填 BAT remote token。

## 2. 安裝 Connector

在中央主機使用 `uv` 安裝。正式版本選定前，固定一個已檢視 commit，避免不知情跟著 `main` 變動。以下使用本文件產品基準：

```bash
uv tool install 'git+https://github.com/teddashh/bat-agent-connector@15b2048de5c2ec3a31e0845ce76a79b612d1c32e'
batc --help
```

開發 checkout 可改用 `uv sync --locked --extra dev`，以下指令以 `uv run batc` 執行。桌面與中央須維持 contract 相容；桌面會拒絕不相容的合約或身分。

## 3. 配置 BAT 存取

這台主機已有 BAT desktop profiles 時：

```bash
batc import-bat
batc hosts
```

匯入會寫出 `~/.config/bat-agent-connector/hosts.toml`，預設關閉 writes；保存 endpoint、固定 TLS 指紋及 **token 參照**，不複製 token 值。`batc hosts` 會探測已配置主機，成功不代表 Git／部署也就緒。

Profile 位於別處可用 `batc import-bat --profiles-dir /path/to/profiles`；加 `--output -` 預覽。不要只為跳過既有設定而加 `--force`。

中央沒有本機 BAT profiles 時，依 [hosts.example.toml](../examples/hosts.example.toml) 配置實際 endpoint、可信指紋與 `token_ref`：

- `env:NAME`：從服務的私人環境讀取。
- `file:/path`：從私人 token 檔案讀取。
- `bat-profile:ID`：從支援的 BAT client token store 讀取。

預設 profile 路徑不代表完整跨平台自動發現。保留 BAT 原設定，憑證不要提交至 repo。

## 4. 啟動中央並開啟 Web

在中央的一個終端機執行：

```bash
batc serve
```

預設為 `127.0.0.1:18796`，process 須持續運行；這條命令不會安裝登入自啟服務。出現 `OWNER_CONFLICT` 時，先使用已存在的 owner，不要另建一份資料庫。

在同一台主機的另一個終端機簽發唯讀身分：

```bash
batc api-token issue --actor personal-dashboard --scope observe
```

Token 只印一次，請私下保存。開啟 `http://127.0.0.1:18796/dashboard/`，在連線畫面登入；應能進入待處理、專案與工作階段。這個初始身分刻意沒有派工或編輯權限。

中央在遠端時，沿用已驗證 tunnel。例如已配置且可信的 SSH alias：

```bash
ssh -N -L 18796:127.0.0.1:18796 central-alias
```

保持 tunnel，再在 client 開同一個 loopback 網址。不要靠改 bind address 或關閉 Host／Origin 檢查來公開服務；目前沒有通用的公開 hosting 入口。

## 5. 接上桌面 client

在成功的 [desktop workflow](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml) 下載對應 artifact：

| 平台 | Artifact | 格式 |
| --- | --- | --- |
| Windows x64 | `desktop-Windows-unsigned` | NSIS `.exe` |
| Mac Apple Silicon | `desktop-macOS-arm64-validation` | `.dmg` |
| Mac Intel | `desktop-macOS-x64-validation` | `.dmg` |
| Linux | `desktop-Linux-unsigned` | `.deb` |

Artifact 可能到期或要求 GitHub 登入。Windows 未簽署、Mac 驗證包是 ad-hoc 簽署，尚非正式公開發行／更新通道。核對來源與測試回執；若系統政策擋下安裝，可先用 Web 試用，不必削弱整台電腦的安全設定。

Windows／Mac 現行步驟：

1. 安裝並啟動相符平台的包。
2. 輸入可信中央位址與簽發 API token 時的 actor，例如 `personal-dashboard`。
3. 檢視原生確認；確認後才建立第一份 `central.json`，不默默覆寫已存在的錯誤設定。
4. 選擇「新增憑證」，在原生安全輸入框提供 Connector API token；驗證後才保存於 Credential Manager／Keychain。
5. 連線後核對身分與中央資料，Web 可以同時開著。

這是現有過渡流程。正式 managed 安裝對新本機環境必須消除手動 endpoint／actor／token 設定。

Linux 原生目前使用明確提供的記憶體來源 `BATC_DESKTOP_TOKEN`，尚無持久憑證登錄；詳見[原生憑證合約](design/desktop.md#configure-the-native-client)。Linux 試用可先用 Web。

各平台設定位置與恢復見 [desktop.md](design/desktop.md)。「忘記已保存憑證」只移除本機記錄，不撤銷中央 token。更換身分走連線頁，不把 token 貼進 URL。

## 6. 啟用實際工作

先確認觀察功能正常，再由操作者配置：

1. 目的 host 的 `writes`／`orchestrate`、自有 managed root、Git／SSH runner 與 confinement。
2. 在既有 `github.repos` 明確綁定 repository、host、workspace；專案名、路徑或 Git remote 不是綁定證據。
3. 所需 scopes。專案派工通常需要 `observe`、`manage`、`start`；操作 session 使用 `operate`。整合、接受、merge、部署、整理各有權限。

綁定範例，須把展示值換成已檢視的實際目的地：

```toml
[[github.repos]]
repository = "example/project"
sync = { remote_url = "git@github.com:example/project.git", bindings = [{ host = "worker", workspace_id = "exact-workspace-id" }] }
```

這不是完整 host／GitHub 設定，也不授予 integration push 或部署權限。請搭配 [repository 設定](design/repository-sync.md)與[設定範例](../examples/hosts.example.toml)。

在 Dashboard 建立專案並明確選 repository，再開專案派工：選目的地、分支、檢視固定 commit，加入原始指示與選用附件／模型後送出。回原專案追蹤工作與成果入口。

成果進 PR 前先看整合預覽。Merge／部署另需設定與 scopes；部署 recipe 還要有真實版本／健康驗證。[交付設定](design/delivery.md)。

## CLI 與 Agent 存取

CLI 可讀取相同觀測與操作紀錄：

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

在 MCP client 支援的設定位置註冊 `bat-agent-connector-mcp`。常見唯讀 JSON 格式：

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

先啟動已配置中央，透過私人環境給此 MCP process 專屬的 `BATC_API_TOKEN`，讀取也須包含 `observe`。確認執行檔與設定可用；`--principal-only` 讓 Agent 固定使用自己的中央身分，開啟寫入時仍應保留。確實需要操作才移除 `--read-only`，host 開關與 scopes 仍會檢查。中央 RPC 位址不同時，另私下設定 `BATC_TASK_URL`。

沒有 `--principal-only` 的操作者相容模式，包含 local-admin 讀取備援與直接 Fleet 工具，不是依 scope 隔離的 Agent 入口。可信本機操作者可使用 `bat-agent-connector-mcp --read-only` 直接觀察 BAT，不必走中央工作流程；但共用 Agent 整合不以此為預設。

選用的 loopback MCP HTTP 是另一個 adapter：

```bash
bat-agent-connector-mcp --principal-only --read-only --http --port 8765
```

MCP 位址是 `http://127.0.0.1:8765/mcp`，不是 Dashboard 網址。Durable 工作及復原請使用[共用 skill](../skills/bat-agent-connector/SKILL.md)與[同版 Agent 配接](agent-skills.md)。Task Service recipes 另有設定；planner 關閉時 task 排隊，不代表派工出錯。[Task Service](design/task-service.md)。

## 首次連線與工作流程排錯

| 畫面情況 | 檢查與處理 |
| --- | --- |
| 桌面一開始要求 central／actor | 這是現有 client-only 安裝器缺口；先按上述試用流程配置，不是永久正常 onboarding。 |
| 網頁沒有回應 | 確認 `batc serve` 與可信 tunnel 仍在跑；核對設定地址，不盲目啟第二個 owner。 |
| 憑證被拒絕 | 使用 Connector API token，不是 BAT token；核對 actor、`observe`、到期、contract 及中央身分。 |
| 已連線但沒有 hosts／sessions | 核對 `hosts.toml`、BAT 遠端存取及 token 參照；離線／過期不代表工作停止。 |
| 派工沒有 repository 可選 | 配置 `github.repos[].sync` 的明確綁定，並把該 repository 加入專案。 |
| 按鈕不可按 | 看旁邊原因，檢查 scopes、host 開關、ownership 與目的地設定。 |
| 啟動受理後斷線 | 保留原 operation ID／key，查回回執；不要為猜結果再派一份。 |
| Agent 沒繼續輸出 | 看待回答、權限與活動；閒置不是完成，完成也不是部署。 |
| 整理被拒絕 | 看保留原因；不要清 reservation 或刪可能還有 writer 的 worktree。 |
| 桌面關閉但工作還在跑 | 中央與 UI 生命週期分開；關窗留背景也不同於明確 Quit。 |
| Fleet 沒啟動 | Fleet 另需配置；沒寫 `backend` 沿用 PowerShell 相容預設，安裝 Dashboard 不等於自動遷移 Rust owner。 |

## 什麼才算一次成功試用？

挑一個小型真實專案，固定 commit 與目的地。確認人工工作不變、managed 工作可追溯、成果到正確 PR、部署顯示實際版本、斷線重開查回同一份工作、整理後歷史仍在。[完整驗收](product/acceptance-v2.md)與 managed 安裝完成前，維持有人監督。
