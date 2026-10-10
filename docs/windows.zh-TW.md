# Windows Fleet 與桌面資源

[English](windows.md) · **繁體中文** · [產品總覽](../README.zh-TW.md)

Windows Fleet 是本產品的本機連線與啟動層，已整合進 Tauri client。Python Connector／
Task Service 負責 Agent 工作的中央控制，BAT 在選定主機執行工作。Windows client 可以
連接 Linux 中央，不必等 Windows 原生中央完成，才能管理既有 Fleet 連線。

## 每一層負責什麼

| 層次 | 責任 |
| --- | --- |
| Windows Tauri／Fleet | 選定背景連線、SSH tunnel ownership、路由／就緒檢查、BAT profile 啟動、登入選擇、憑證、檔案與系統匣。 |
| Python Connector／Task Service | Agent 身分、權限、派工、task 協調、operations、回執與歷史。 |
| BAT 主機 | Workspaces、人工 sessions／worktrees，以及 Agent 各自的 managed 資源。人的 BAT desktop／mobile 照常使用。 |
| GitHub／已配置的部署目標 | 經中央操作管理已發布 commit、整合 PR、merge 與部署證據。 |

專案管理是這套系統的一個 Dashboard 視角。Project Hub 提供互動參考，並不是本產品的
runtime 或資料後端。

## 使用既有 Windows 環境

以下是**目前已配置環境的試用步驟**。正常安裝器應自動準備 runtime 與背景環境，
完整流程[仍須實作](design/managed-installation.md)。

1. 從成功的 [desktop workflow](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml)
   下載 `desktop-Windows-unsigned`，內含 NSIS `.exe`。核對 commit；artifact 可能到期，
   目前仍不是正式簽章發行／更新通道。
2. 依[目前的桌面連線步驟](getting-started.zh-TW.md#5-接上桌面-client)連接可信中央，
   在原生憑證視窗完成驗證。
3. 已部署 Fleet 時，保留原來已檢視的 Kit inventory、BAT profile index 與 SSH 設定。
   原生 adapter 讀取同一份配置；以 [fleet.example.json](../desktop/fleet.example.json) 與
   [安裝合約](design/fleet-installation.md) 綁定現有 Kit。範例本身不是完整安裝，私人主機
   拓撲也不應複製到這個公開 repo。
4. 在連線設定查看目前 backend，分別選擇**背景連線、BAT profiles、Dashboard**。
   保存或啟動前檢視必要連線；Dashboard-only 不需要本機 BAT executable。
5. 逐台看就緒狀態。Tunnel、TLS pin、BAT 驗證／workspace、中央 observe 存取分開檢查。
   需要 Tailscale 登入時，從本機面板開啟已安裝的 Tailscale 程式，在該程式登入，再刷新狀態。
6. 檢視登入選擇器與已保存啟動選項。未指定 `backend` 時沿用 **PowerShell**；Rust runtime
   已接入，但接手既有 owner 必須經明確遷移，安裝新版 Dashboard 不會自動完成遷移。

關閉 Dashboard 只隱藏視窗，背景工作繼續。明確選擇 Quit 則會要求正常停止已證明由自己
持有的本機 Fleet monitor；ownership 不明時拒絕退出。兩者都不結束中央任務或人工 BAT
sessions。已配置的遠端中央 bootstrap 使用固定 SSH recipe，不是任意遠端安裝，也不會
默默建立另一套中央資料庫。

## 資源索引

| 主題 | 對應資源 |
| --- | --- |
| 連線、視窗與登入選擇 | [原生 Fleet 整合](design/desktop-fleet-native.md) · [共用 UI](../desktop/src/fleet-desktop.js) |
| Rust runtime 與 PowerShell 相容 | [Fleet core](../desktop/fleet-core/README.md) · [backend 路由](../desktop/src-tauri/src/fleet.rs) |
| Tailscale、已配置的備援路由與就緒 | [路由政策](design/fleet-routes.md) · [Tailscale 登入](design/tailscale-recovery.md) |
| 登入啟動與 owner 遷移 | [遷移合約](design/fleet-migration.md) · [Windows ownership](design/fleet-windows.md) |
| 指定中央服務啟動 | [固定 bootstrap recipe](design/fleet-bootstrap.md) |
| Credential Manager、系統匣與原生檔案 | [桌面 client](design/desktop.md) · [檔案操作](design/native-files.md) |
| 驗證安裝包與 installed fixtures | [Desktop CI](https://github.com/teddashh/bat-agent-connector/actions/workflows/desktop.yml) · [驗收矩陣](product/acceptance-v2.md) |

Windows 安裝／WebView fixture、Fleet 原始碼測試，和在使用者真正 SSH／Tailscale／BAT
主機上跑完整工作日，是不同的證據。完整自動安裝、Fleet 實機驗收與正式簽署更新仍須完成；
支援 Mac Dashboard 也不代表 Windows Fleet 已移植到 Mac。
