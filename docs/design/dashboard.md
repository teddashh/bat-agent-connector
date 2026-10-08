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
| 待處理 | 「需要你處理」：等你回答或等權限的 session、`needs_attention`／`uncertain` 操作、連不上的主機。「待確認」：尚未結束的操作 | `sessions?attention=true`、`operations?status=…`、`hosts` | — |
| Sessions | 依主機與存取方式篩選；每列標出 Connector 管理或 API 唯讀、資料過期原因 | `sessions`（keyset 分頁） | — |
| Session | 基本資料、來源、最近訊息、checkpoint | `sessions/{host}/{sid}`、`…/messages`、`checkpoints` | Managed：送出（session 執行中預設排隊）、中斷、回答問題或權限。人工建立：唯讀說明。任何 session：記下目前版本，從版本開始 agent 工作（[checkpoints.md](checkpoints.md)） |
| 成果與 GitHub | PR 的 head／base、checks、可合併狀態 | `repositories/{o}/{r}/pulls/{n}` | 合併、合併並部署到各 recipe、已合併時部署合併版本 |
| 操作紀錄／操作 | 狀態、原因、步驟、`external_refs`、結果 | `operations`、`operations/{id}` | 取消；`needs_attention` 時重新執行（resume）；合併並部署失敗時以 `merged_sha` 重試部署 |
| 連線 | 輸入 API token，顯示 actor 與 scopes | `capabilities` | — |

按鈕不會因為 scope 不足而隱藏：送出後由 API 回 403，畫面顯示「你的 token 沒有這個權限」。授權只在後端判斷。

## 冪等與即時更新

- 每個草稿（例如「對這個 session 送字」「以這個 head 合併這個 PR」）在 `localStorage` 有一把 `Idempotency-Key`。回應遺失後重按，會拿回同一個 operation，不會做第二次。操作結束或請求被拒（4xx，409 除外）後才換新鑰匙。
- 即時更新用 fetch 讀 `GET /api/v1/events/stream`，因為 `EventSource` 不能帶 `Authorization`。斷線後從最後一個 `seq` 續接。事件只觸發重新讀取，畫面內容一律以 API 讀回為準。

## 語言

依瀏覽器語言選 zh-TW 或 en，預設 zh-TW。字串只在 `i18n.js`；程式與 CSS 只用 API 的機器值（`status`、`api_access` 等），不比對顯示文字。

## 尚未涵蓋

- Worktree、diff、檔案瀏覽，以及 Fleet Kit 的連線選擇（W10）。
- 推播通知。

## 測試

`tests/test_api_v1.py::test_dashboard_serves_only_its_static_files_with_strict_headers` 檢查白名單、轉址、HEAD、方法與 Host 限制及安全標頭。畫面流程以 Playwright 對 MockBat 與 FakeGitHub 手動驗證（zh-TW、en、手機寬度），不在 CI 中執行。
