# Dashboard

更新：2026-10-08。既有 W09 畫面依 [Tauri v2 範圍](../product/realignment-v2.md) 納入 R02/R04 共用 frontend；介面參考 Project Hub，不提供 Hub 匯入器。資料與動作全部來自 [/api/v1](api-v1.md)；合併與部署的語意見 [delivery.md](delivery.md)，原生殼與驗收限制見 [desktop.md](desktop.md)。

## 形式

`desktop/src` 是 browser 與 Tauri 唯一共用 UI source，保留原有 JavaScript、CSS、DOM helpers 與表單；transport/state helpers 使用 TypeScript。`cd desktop && npm ci && npm run build:all` 以 Vite 產生 packaged desktop assets 與 Python browser assets。Tauri 正式執行不需要 Vite server。

`batc serve` 仍在同一個 loopback 埠提供 `/dashboard/`（`http://127.0.0.1:18796/dashboard/`，`/` 會轉到這裡）。套件的 `dashboard/` 仍只提供 `index.html`、`app.js`、`i18n.js`、`app.css` 四檔；它們由共用 source 產生，禁止手改。翻譯已 bundle 入 app.js，i18n.js 保留相容 stub。其他路徑一律 404。JavaScript/Cargo lockfiles 固定依賴，CI 重建並檢查 generated drift。

靜態檔本身不含資料，所以不需要 token；頁面發出的每個 `/api/v1` 請求都要 bearer token。遠端使用同樣經 SSH forward（`ssh -L 18796:127.0.0.1:18796 host`），daemon 不對外綁定。

## 安全

- 回應帶 `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; …; frame-ancestors 'none'`、`X-Frame-Options: DENY`、`nosniff`、`Referrer-Policy: no-referrer`。頁面沒有 inline script 或 inline style，CSP 不需要放寬。
- Session 標題、訊息、PR 標題等外部文字一律以 `textContent` 寫入（`desktop/src/app.js` 的 `h()`），不經 HTML 解析。
- Host 必須是 loopback，與 `/api/v1` 同一條規則（擋 DNS rebinding）。
- Browser token 預設只存在 `sessionStorage`；勾選「在這台電腦記住」才寫入 `localStorage`。不用 cookie，所以不依賴 cookie 型 CSRF 防護。
- Tauri 只載入打包的 frontend，透過限縮 native command 連受信配置中的中央服務。Token 留在 Rust memory，不進 WebView storage；目前原生憑證注入使用啟動環境變數，OS 保護儲存 enrollment 尚未提供。中央 actor／API／contract mismatch 拒絕連線，原生 HTTP 不跟隨 redirect。GitHub HTTPS links 由受限 native action 開系統瀏覽器。完整邊界見 [desktop.md](desktop.md)。

## 畫面

| 畫面 | 內容 | 讀取 | 動作 |
|---|---|---|---|
| 待處理 | 「需要你處理」：等你確認完成的工作項目、等你回答或等權限的 session、`needs_attention`／`uncertain` 操作、連不上的主機。「待確認」：尚未結束的操作 | `work-items?pending=true`、`sessions?attention=true`、`operations?status=…`、`hosts` | — |
| 專案 | 專案樹與各專案的進度 | `projects` | 新增、改名、子專案、上下移、固定、封存與復原 |
| 專案詳情 | 說明、repositories、子專案、工作項目樹（狀態、步驟進度、等你決定） | `projects/{id}` | 新增項目、子項目、分支；上下移、固定、封存（連同子項目）與復原；編輯專案 |
| 工作項目 | 目標、需求原文、驗收、步驟、完成狀態、連結（附現況）、子項目與分支、紀錄 | `work-items/{id}` | 編輯、勾步驟、改狀態、確認完成或退回、連結與移除、從已連結的 checkpoint 派工（[work-items.md](work-items.md)） |
| Sessions | 依主機與存取方式篩選；每列標出 Connector 管理或 API 唯讀、資料過期原因 | `sessions`（keyset 分頁） | — |
| Session | 基本資料、來源、相關工作項目、最近訊息、checkpoint | `sessions/{host}/{sid}`、`…/messages`、`checkpoints` | Managed：送出（session 執行中預設排隊）、中斷、回答問題或權限。人工建立：唯讀說明。任何 session：記下目前版本，從版本開始 agent 工作（[checkpoints.md](checkpoints.md)） |
| 成果與 GitHub | 環境的選定／觀測／最後驗證版本、游標分頁部署歷史；PR 的 head／base、checks、可合併狀態 | `deployment-environments`、`deployment-environments/history`、`deployments/{id}`、`repositories/{o}/{r}/pulls/{n}` | 以 `deployments/preview` 固定環境代數與 recipe digest 後回退或重試固定版本；合併、合併並部署、部署已合併版本 |
| 操作紀錄／操作 | 狀態、原因、步驟、`external_refs`、結果 | `operations`、`operations/{id}` | 取消；`needs_attention` 時重新執行（resume）；合併並部署失敗時以 `merged_sha` 重試部署 |
| 連線 | Browser 輸入 API token；Tauri 顯示配置位置、原生憑證狀態；兩者顯示 actor 與 scopes | `capabilities`、`bootstrap` | 連線、斷線 |

Token 缺少某個 scope（`start`、`integrate`、`manage`、`approve`）時，對應的按鈕停用並說明要用哪個 scope 重新發 token。這只是提示：授權只在後端判斷，送出的請求仍可能回 403。

## 冪等與即時更新

- 每個草稿（例如「對這個 session 送字」「以這個 head 合併這個 PR」）在身份分區的 `localStorage` 有一把 `Idempotency-Key`；保存原 operation ID 以便查回。回應遺失後重開再重按仍使用相同 key。操作結束或請求被拒（4xx，409 除外）後才換新鑰匙。舊版無身份分區的資料保留原處，不自動指派給另一個 backend／actor；不明舊操作須先對帳。
- 專案與工作項目的修改帶上頁面讀到的版本、指紋、兄弟順序或固定狀態；別人先改了就回 409，畫面說明並重新載入，不覆蓋對方。編輯欄的草稿留在重新載入後的表單裡。說明顯示在頁面上方，不會被重畫掉。
- 既有 projects／work-items／delivery 的 live render 會避開開啟中的編輯欄或正在輸入的欄位，關閉或離開後再補上。新增步驟、連結的輸入框在相應 view 重畫時保留內容；這不代表所有表單都已持久化。Session 送字草稿另存於身份分區，重開仍可回復。
- 從 checkpoint 派工的表單送出後就不能再送：結果留在表單裡，關閉後頁面列出這次執行。
- Browser 與 Tauri 共用有界的 `GET /api/v1/events` polling，追平後每秒讀一次；原生 Rust 不另建 event log。中央 SSE 仍可供其他 clients 使用，但這個版本沒有 native streaming subscription。
- 新中央提供 [bootstrap／checkpoint 合約](dashboard-sync.md)。先取得 cursor/token，再讀需要的畫面資料，畫面 mounted 後續讀事件。Snapshot 與多頁讀取不是原子快照（`atomic:false`）；資料以 stable IDs 及 API 讀回為準。每頁等待所有 async/debounced view refresh 完成後才一起保存 `next_cursor` 與新 checkpoint token，不能先跳到 head。讀回失敗保留原 cursor/token，暫停操作並重讀同一頁；開啟的編輯表單延後 refresh 與 acknowledgment，保留草稿；單純等待不會禁止有版本前置條件的表單儲存，實際讀取失敗或 continuity reset 才暫停操作。此保障限於已訂閱的畫面更新；pending controls、linked resource invalidations 與 history/relations 畫面仍由 R04 完成。Cache／草稿／操作 keys 依 endpoint、server_id、principal_id、actor 分區。
- `EVENT_CURSOR_RESET` 重讀 bootstrap；同身份已開表單保留至使用者離開再刷新，其間不接受 mutation。切換 backend／principal 立即換分區，不把舊表單內容寫入新身份。Poll 失敗也會暫停 operation POST，保留草稿和原 key。舊中央無 bootstrap 時仍可讀目前畫面，但沒有 retention／continuity 保證。

## 附件與草稿（Part A；計畫 §13，B04）

工作項目編輯與 checkpoint 接續表單提供檔案 picker，選擇即 upload。原 `batc.draft.<scope>` localStorage 草稿擴充為 text／uploaded refs／尚未成功檔名／提交 operation；沒有 server draft 或 IndexedDB。File 只在記憶體，失敗可 Retry；重新載入列檔名並明確顯示「請重新選擇這個檔案。瀏覽器無法在重新載入後開啟本機檔案。」（英文同義）。成功 upload 不清草稿，continue／update succeeded 才清提交 snapshot，期間新編輯留下。

Dashboard 開接續表單時讀 source HEAD 並送 expected_source_head_sha；SOURCE_MOVED 在原 operation 頁明確確認原 commit／attachments，續同 parent。操作页展示各 materialization 的 pending／transferring／uncertain／verified／blocked evidence。prompt 只有 worktree-relative paths 與精確 ref／digest，無 client-local path；download attachment 無 preview。完整合約見 [artifacts.md](artifacts.md)。

## 語言

依瀏覽器語言選 zh-TW 或 en，預設 zh-TW。字串在 `desktop/src/i18n.js`；程式與 CSS 只用 API 的機器值（`status`、`api_access` 等），不比對顯示文字。

## 整理與永久歷史（Part A）

見 [cleanup.md](cleanup.md)：純讀 preview、signed token、逐項 operations／retained refs／tombstones，原 ID
永久可查。Dashboard #/cleanup 與 work item 的整理入口，兩語預覽／逐項回執／歷史搜尋／實際 retained list；
Part A 無 restore 按鈕。Task-owned 資源由 Task Service 整理，本輪列 TASK_OWNED；原 terminal cleanup 不變。
Restore、reviewed task leftovers／coordinator 准入與 TaskDaemon 歷史投影在 Part B。Clone／area 與 pins 留存。
## 執行限制證據（A10）

Session card 依 creation snapshot 顯示 level；OS sandbox 最多 options_confirmed，badge 明示尚未實機驗證。Detail 可展開建立選項、evidence／gap 及獨立 current verification；stale／mismatch 不改原 level。Checkpoint、work item 接續與 repair forms 隨所選 agent 及中央 `host_account.start_effect` 顯示限制：`recheck` 要求 start 時重新查核；`fallback_default` 的 Claude 使用 plain default；`refused` 才顯示阻擋與原因；`verified` 顯示已驗證 account 邊界。Codex 顯示 network／writable roots 不可設定與測試相容風險。所有字串有 en／zh-TW。Cwd 本身不稱為保護；A10 尚待 W12，見 [confinement](confinement.md)。

## 尚未涵蓋

- Worktree、diff、檔案瀏覽。Fleet Kit 的連線選擇已由 Windows [PS adapter](desktop-fleet.md) 與桌面設定頁提供；Rust parity 與實機驗收仍待完成。
- 推播通知。
- #35 history／relations／discovery read models 已有中央合約；其完整 UI 呈現、已開 session 的 pending 控制刷新、linked operation／parent project invalidation 仍屬 R04 待完成範圍。
- Windows 真實 tray、cross-session ownership、native files、Fleet parity、OS credential enrollment 與 signed updates 未因桌面殼可編譯而視為驗收完成。

## 測試

`tests/test_api_v1.py::test_dashboard_serves_only_its_static_files_with_strict_headers` 檢查白名單、轉址、HEAD、方法與 Host 限制及安全標頭。`desktop` workflow 執行共用 frontend build、generated drift、TypeScript event helpers、Rust bridge 與 Chromium Playwright fixture tests；後者涵蓋 390/768/1440 寬度、原生 transport mock、遺失回應重試、reset 草稿與離線拒絕寫入。Linux genuine packaged WebKit fixture 另驗證啟動讀取、關窗隱藏和第二次啟動恢復。這些都是 fixture／native smoke 證據，不代替 Windows 安裝或真實中央與 BAT 的完整驗收。
