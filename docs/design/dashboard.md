# Dashboard

日期：2026-10-07。對應《Better Agent Dashboard／Connector 計畫》v1.0 的工作包 W09（Dashboard 首批畫面），介面參考 Project Hub。資料與動作全部來自 [/api/v1](api-v1.md)；合併與部署的語意見 [delivery.md](delivery.md)。

## 形式

`batc serve` 在同一個 loopback 埠提供 `/dashboard/`（`http://127.0.0.1:18796/dashboard/`，`/` 會轉到這裡）。只有四個靜態檔：`index.html`、`app.js`、`i18n.js`、`app.css`，放在套件的 `dashboard/` 目錄，沒有 build step，也沒有第三方套件。其他路徑一律 404。

靜態檔本身不含資料，所以不需要 token；頁面發出的每個 `/api/v1` 請求都要 bearer token。遠端使用同樣經 SSH forward（`ssh -L 18796:127.0.0.1:18796 host`），daemon 不對外綁定。

## 安全

- 回應帶 `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; …; frame-ancestors 'none'`、`X-Frame-Options: DENY`、`nosniff`、`Referrer-Policy: no-referrer`。頁面沒有 inline script 或 inline style，CSP 不需要放寬。
- Session 標題、訊息、PR 標題等外部文字一律以 `textContent` 寫入（`app.js` 的 `h()`），不經 HTML 解析。
- Host 必須是 loopback，與 `/api/v1` 同一條規則（擋 DNS rebinding）。
- Token 預設只存在 `sessionStorage`；勾選「在這台電腦記住」才寫入 `localStorage`。不用 cookie，所以沒有 CSRF。

## 畫面

| 畫面 | 內容 | 讀取 | 動作 |
|---|---|---|---|
| 待處理 | 「需要你處理」：等你確認完成的工作項目、等你回答或等權限的 session、`needs_attention`／`uncertain` 操作、連不上的主機。「待確認」：尚未結束的操作 | `work-items?pending=true`、`sessions?attention=true`、`operations?status=…`、`hosts` | — |
| 專案 | 專案樹與各專案的進度 | `projects` | 新增、改名、子專案、上下移、固定、封存與復原 |
| 專案詳情 | 說明、repositories、子專案、工作項目樹（狀態、步驟進度、等你決定） | `projects/{id}` | 新增項目、子項目、分支；上下移、固定、封存（連同子項目）與復原；編輯專案 |
| 工作項目 | 目標、需求原文、驗收、步驟、完成狀態、連結（附現況）、子項目與分支、紀錄 | `work-items/{id}` | 編輯、勾步驟、改狀態、確認完成或退回、連結與移除、從已連結的 checkpoint 派工（[work-items.md](work-items.md)） |
| Sessions | 依主機與存取方式篩選；每列標出 Connector 管理或 API 唯讀、資料過期原因 | `sessions`（keyset 分頁） | — |
| Session | 基本資料、來源、相關工作項目、最近訊息、checkpoint | `sessions/{host}/{sid}`、`…/messages`、`checkpoints` | Managed：送出（session 執行中預設排隊）、中斷、回答問題或權限。人工建立：唯讀說明。任何 session：記下目前版本，從版本開始 agent 工作（[checkpoints.md](checkpoints.md)） |
| 成果與 GitHub | PR 的 head／base、checks、可合併狀態 | `repositories/{o}/{r}/pulls/{n}` | 合併、合併並部署到各 recipe、已合併時部署合併版本 |
| 操作紀錄／操作 | 狀態、原因、步驟、`external_refs`、結果 | `operations`、`operations/{id}` | 取消；`needs_attention` 時重新執行（resume）；合併並部署失敗時以 `merged_sha` 重試部署 |
| 連線 | 輸入 API token，顯示 actor 與 scopes | `capabilities` | — |

Token 缺少某個 scope（`start`、`integrate`、`manage`、`approve`）時，對應的按鈕停用並說明要用哪個 scope 重新發 token。這只是提示：授權只在後端判斷，送出的請求仍可能回 403。

## 冪等與即時更新

- 每個草稿（例如「對這個 session 送字」「以這個 head 合併這個 PR」）在 `localStorage` 有一把 `Idempotency-Key`。回應遺失後重按，會拿回同一個 operation，不會做第二次。操作結束或請求被拒（4xx，409 除外）後才換新鑰匙。
- 專案與工作項目的修改帶上頁面讀到的版本、指紋、兄弟順序或固定狀態；別人先改了就回 409，畫面說明並重新載入，不覆蓋對方。編輯欄的草稿留在重新載入後的表單裡。說明顯示在頁面上方，不會被重畫掉。
- 開著任何編輯欄、或游標在頁面的輸入框裡時，即時更新先暫停，關閉或離開後再補上；在讀取途中才打開的編輯欄也不會被那次重畫關掉。新增步驟、連結的輸入框在重畫時保留內容。
- 從 checkpoint 派工的表單送出後就不能再送：結果留在表單裡，關閉後頁面列出這次執行。
- 即時更新用 fetch 讀 `GET /api/v1/events/stream`，因為 `EventSource` 不能帶 `Authorization`。斷線後從最後一個 `seq` 續接。事件只觸發重新讀取，畫面內容一律以 API 讀回為準。

## 語言

依瀏覽器語言選 zh-TW 或 en，預設 zh-TW。字串只在 `i18n.js`；程式與 CSS 只用 API 的機器值（`status`、`api_access` 等），不比對顯示文字。

## 整理與永久歷史（Part A）

見 [cleanup.md](cleanup.md)：純讀 preview、signed token、逐項 operations／retained refs／tombstones，原 ID
永久可查。Dashboard #/cleanup 與 work item 的整理入口，兩語預覽／逐項回執／歷史搜尋／實際 retained list；
Part A 無 restore 按鈕。Task-owned 資源由 Task Service 整理，本輪列 TASK_OWNED；原 terminal cleanup 不變。
Restore、reviewed task leftovers／coordinator 准入與 TaskDaemon 歷史投影在 Part B。Clone／area 與 pins 留存。

## 尚未涵蓋

- Worktree、diff、檔案瀏覽，以及 Fleet Kit 的連線選擇（W10）。
- 推播通知。

## 測試

`tests/test_api_v1.py::test_dashboard_serves_only_its_static_files_with_strict_headers` 檢查白名單、轉址、HEAD、方法與 Host 限制及安全標頭。畫面流程以 Playwright 對 MockBat 與 FakeGitHub 手動驗證（zh-TW、en、手機寬度），不在 CI 中執行。
