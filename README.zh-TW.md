# bat-agent-connector

[English](README.md) · **繁體中文**

**讓 AI agent 操作 [Better Agent Terminal（BAT）](https://github.com/tony1223/better-agent-terminal) session 的非官方連接器。**

**專案介紹頁：** https://teddashh.github.io/bat-agent-connector/?lang=zh-TW

**開發方向：** [Tauri v2 產品決策](docs/product/realignment-v2.md)與
[實作狀態](docs/product/implementation-status.md)。桌面版共用 Dashboard frontend 與既有 Python 後端。
v2 不提供 Project Hub 匯入；保留既有專案與工作項目管理。

BAT（作者 [TonyQ / tony1223](https://github.com/tony1223)）是一套終端機 app，在你自己的機器上執行 Claude Code 與 Codex 的 agent session，並依工作區（workspace）分組。它有一套遠端協定 `bat-remote/v2`，BAT 自己的桌面介面和手機客戶端都走這套協定。本專案實作同一套協定，讓「其他」agent（Claude Code、Codex、Cursor、Hermes 或任何 MCP 客戶端）以及 shell 腳本可以：

* 看到有哪些 agent session、哪些正在跑或卡在問題上，以及它們最近說了什麼；
* 等某個 session 跑完這一輪；
* （選擇性開啟）推動 session：送訊息、叫它「continue」、中斷它、回答它的問題；
* （選擇性開啟，獨立的一層）分派工作：在新的 git worktree 開 session、檢查它們的 diff、merge 乾淨的分支；
* 找出碰到 Claude 用量額度上限的 session，在同一個 worktree 改由 Codex 接手（failover）；
* 在確定性的關卡後面，自動核准權限請求，並清理已完成的 session。

> 本專案與 BAT 作者**沒有任何關係，也未經其背書**。協定是從 BAT 以 MIT 授權公開的原始碼（v3.2.12）讀出來的，BAT 改版時可能跟著變。BAT 的功勞屬於 TonyQ 與其貢獻者。

內容包含四個部分：

| 元件 | 名稱 |
|---|---|
| Python 套件 | `bat-agent-connector`（Python 3.10+，相依套件：`websockets`、`mcp`） |
| MCP 伺服器（stdio，或只綁 localhost 的 streamable HTTP） | `bat-agent-connector-mcp`（也可以用 `batc mcp`） |
| CLI | `batc` |
| Agent skill | [`skills/bat-agent-connector/SKILL.md`](skills/bat-agent-connector/SKILL.md) |

`batc inventory`、`batc history`、`batc relations` 與對應 HTTP/MCP 讀取提供持久觀測。Session 歷史只讀 journal 事實；warm reuse 保留每個 task 的關係區間，discovery 顯示最近 host/profile 掃描範圍及未掃項目。未知 actor／狀態保持 unknown，讀取不啟動 session、不背景探測 Git。詳見 [observation](docs/design/observation.md)。Dashboard 的歷史與 scope 畫面屬後續 Part B。

## 為什麼要做

同時跑好幾個長時間執行的 coding agent，就得一直切分頁檢查：哪個做完了、哪個卡在問題上、哪個只差一句「continue」。透過 BAT 的協定讀這些狀態很可靠（不抓畫面、不模擬 GUI 操作），也能讓一個負責監看的 agent 替你檢查，而任何會寫入的動作都還是由你掌控。

## 安裝

```bash
# 從 git 網址安裝（在上架 PyPI 之前）
uv tool install git+https://github.com/teddashh/bat-agent-connector
# 或
pipx install git+https://github.com/teddashh/bat-agent-connector
# 或不安裝，直接執行
uvx --from git+https://github.com/teddashh/bat-agent-connector batc hosts
```

## 設定

每台主機，連接器需要三樣東西：該主機 `bat-server` 的 `wss://` 網址、伺服器 TLS 憑證的 SHA-256 指紋（固定比對；BAT 使用自簽憑證），以及遠端 token 的**參照**。如果你已經在用 BAT 桌面客戶端，可以直接從它匯入：

```bash
batc import-bat                      # 寫出 ~/.config/bat-agent-connector/hosts.toml（寫入功能關閉）
batc import-bat --rename my-profile-id=box1 --output -   # 換成好記的名字，先預覽
batc hosts                           # 測試連線：每台主機的版本與 ping
```

Token 參照（token 值本身永遠不會存進設定檔、寫進記錄，或由任何工具回傳）：

| `token_ref` | 意思 |
|---|---|
| `env:NAME` | 環境變數 |
| `file:/path` | 只放 token 的檔案（權限請維持 `chmod 600`） |
| `bat-profile:<id>` | BAT 客戶端的 token 儲存檔（`profiles/remote-tokens.enc.json`，只支援未加密的版本） |

所有選項請見 [`examples/hosts.example.toml`](examples/hosts.example.toml)。連接器會把固定的 `deviceId` 存在 `~/.config/bat-agent-connector/device-id`，所以主機不會在每次重新連線時，都跳出一則新的「remote client connected」通知。

## 權限層級

| 層級 | 開啟方式 | 工具 |
|---|---|---|
| read（永遠開啟） | - | `hosts_list`、`host_status`、`workspaces_list`、`sessions_list`、`session_read`、`session_wait`、`worktree_status`、`session_worktree_status`、`sessions_triage`、`quota_sessions`、`session_policy`、`work_status`、`work_result`、`work_events` |
| write | 每台主機設 `writes = true` | `session_send`、`session_continue`、`session_interrupt`、`session_answer`、`session_set_permissions`、`approve_pending`、`session_relay` |
| orchestrate | 每台主機設 `writes = true` **且** `orchestrate = true` | `session_start`、`worktree_merge`、`worktree_remove`、`session_failover`、`session_record_verification`、`session_cleanup`、`fanout_plan_session`、`fanout_from_plan`、`work_submit`、`work_pause`、`work_resume`、`work_mark_stage` |

write 與 orchestrate 的工具沒開啟時根本不會註冊；開啟後每次呼叫都要帶 `confirm=true`，有速率限制，並附加寫進稽核記錄（`~/.local/state/bat-agent-connector/audit.jsonl`；訊息內容只記雜湊值與長度，除非你選擇保留一小段預覽）。MCP 伺服器或 CLI 加上 `--read-only`，不管設定檔怎麼寫，這兩層都會關閉。通道白名單在客戶端核心裡強制執行，位於 MCP 層之下：reset、kill、fork、PTY 寫入、檔案操作、設定、工作區編輯（只能附加的分頁登記 helper 除外）、安裝、更新與帳號變更，一律不會送出。

## MCP 設定

### 任務服務里程碑（選用）

`batc serve` 會在 `127.0.0.1:18796` 啟動以 SQLite WAL 為基礎的任務協調服務。原本的 MCP 伺服器因此多了 `work_submit`、`work_status`、`work_pause`、`work_resume`、`work_result`，以及唯讀的 `work_events` 事件流；它的 stdio 行程透過 `BATC_TASK_URL`（預設 `http://127.0.0.1:18796/rpc`）呼叫這個常駐服務。`work_submit` 在 `original_words` 收下 Ted 的**原話**，再加上一個冪等鍵（例如 Discord 訊息 ID），不等 BAT 就直接回傳 `task_id`。Hermes 不可以重新詮釋或拆分這個請求。規劃由跑在 Opus 5.5 上的 Goose 在 repo 裡進行。任務的寫入動作要求主機原本就設好 `writes=true` 與 `orchestrate=true`。原有的低階工具與 `batc` 指令照常可用。

每個任務就是一個跑在 Opus 5.5 上的 Goose session。`goose-session` recipe 的 prompt 會指示 Goose 一開始拆一次工作，以 Grok 4.7 : Codex : Opus 5.5 = 4:2:1 的比例為目標分配執行者，而且不把新工作交給每週額度剩餘在 15% 以下（含）的模型。這些是寫在 prompt 裡的指示，不是服務會強制執行的規則：服務不會統計分派次數，也不會讀取額度。這個服務本身不做路由、不做審查，也不做 failover。驗證結果以可信任的測試為準；程式碼沒過，就退回同一個 session 在有限次數內重做，預算用完則標為 `needs_ted`。Ted 之後補充的指示，會接在同一個任務上繼續（同一個 session，不重新規劃，也不開新任務）。這條路徑不經過 Jev。只有當調度者送出已經拆好的任務，並指定 `executor_model`（`grok`、`codex` 或 `claude`）而跳過 Opus 規劃時，才會用到 Jev。Goose 本身有一個開關，預設關閉（`GooseConfig.enabled`）；關閉期間，任務會一直排隊，不會啟動任何東西。

可信任的測試指令必須在本機設定好；服務會在乾淨的候選 commit 上觀察它的結束代碼。服務永遠不會自己在聊天室發訊息。`work_events(since_cursor, limit)`（CLI 為 `batc task-events --since N`）只回傳里程碑（`started`、附原因的 `needs_ted`、附 commit／PR 連結的 `done`、`failed`），每一筆都帶單調遞增的 `cursor`、`task_id`、`project`、`workspace`、送出時傳入的不透明 `origin_thread_id`、`kind`，以及一段簡短的 `summary`。主要的傳遞方式是推送：在私有設定裡設好 `[task_service.event_webhook] url`（只限 loopback）與 `secret_file`（權限 0600）後，每個已提交的里程碑都會依 cursor 順序以純 JSON POST 出去（`type="task.milestone"`、`delivered_through`、`X-Request-ID`，以及對 `<X-Webhook-Timestamp>.<body>` 計算的 HMAC-SHA256 `X-Webhook-Signature-V2`）。推送的 cursor 在第一次設定時從「現在」開始，只有收到 2xx 才會前進；失敗時以有上限的指數退避重試（最長 300 秒）。接收端斷線之後，用 `work_events` 補抓；`limit=0` 會回傳 `head_cursor`。選用的 `[task_service] repo_urls` 會多加上 `commit_url`。任務 API 需要本機管理 token 或限定範圍的 capability，而且只綁定 loopback。狀態、復原、私有設定與上線步驟，請見[任務服務設計文件](docs/design/task-service.md)。`work_status` 與 `work_result` 只是單純讀取 journal，回傳的 `delivery` 區塊會把 `verified` 與 `adopted`、`merged`、`deployed` 分開（後三者只來自 `work_mark_stage`）。`context_refs` 保存隨 Ted 的原話一起送來的附件、previous_message_id、計畫與 commit。`work_submit` 可以另外帶 `task_path`（`standard` 或 `minimal`）；沒有帶時，常駐服務使用 `standard`，若啟動時設了 `BATC_TASK_DEFAULT_PATH=minimal` 則改用 `minimal`。只有走 minimal 路徑，而且後續請求的 HEAD 仍是上一個已驗證的 commit，才會沿用已經暖機的主導 session。

較早之前（加入精簡版 Jev 審查關卡之前），曾用一個一行的 README 修改請求做 A/B 測試，使用本機的假 BAT，並關閉 Jev 的網路連線。每條路徑各完成 10 個任務，standard `bugfix-with-tests` 的中位數是 **48.44 ms**，minimal `small-task-with-tests` 的中位數是 **22.73 ms**。這只量到本機協調的時間，不含真正的 BAT、模型、測試執行與網路時間，也不能拿來預估實際交付時間。Codex 的時間戳 cursor 無法證明指令是誰送的。無法確定是否送達的指令會一直停住，直到操作者針對那一個指令做一次性的核對（`batc task-reconcile`）；絕不會自動重送。Claude 轉 Codex 的 failover，會把交接記成另一筆無法確定是否送達的指令。很長的原始請求會使用一份完整的私有封存，派送前先確認接手的主機讀得到；如果無法證明讀得到，服務就直接拒絕執行（fail closed）。不需要任何付費的 API key。

伺服器名稱是 `bat`。以下是範例（想確保唯讀，就加上 `--read-only`）：

**Claude Code**
```bash
claude mcp add bat -- bat-agent-connector-mcp --read-only
```

**Codex**（`~/.codex/config.toml`）
```toml
[mcp_servers.bat]
command = "bat-agent-connector-mcp"
args = ["--read-only"]
```

**Cursor**（`~/.cursor/mcp.json`）
```json
{ "mcpServers": { "bat": { "command": "bat-agent-connector-mcp", "args": ["--read-only"] } } }
```

**Hermes Agent**（`~/.hermes/config.yaml`）
```yaml
mcp_servers:
  bat:
    command: /home/you/.local/bin/bat-agent-connector-mcp
    args: [--read-only]
    connect_timeout: 60.0
    enabled: true
```

**任何透過 HTTP 連線的 MCP 客戶端**（只綁 loopback）：
```bash
bat-agent-connector-mcp --http --port 8765     # http://127.0.0.1:8765/mcp
```

### Dashboard 與 `/api/v1`（選用）

`batc serve` 也在同一個 loopback 埠提供 `/api/v1` 與瀏覽器 Dashboard（`http://127.0.0.1:18796/dashboard/`）：需要你處理的項目、所有 session 與其來源（人在 BAT 建立的 session 一律唯讀）、managed session 的操作、PR 合併與部署按鈕，以及操作紀錄。以 `batc api-token issue --actor ted-dashboard --scope observe --scope operate --scope start --scope integrate --scope manage --scope approve --scope merge --scope deploy`（`merge`、`deploy` 給合併與部署按鈕）發行 token 後在 Dashboard 的「連線」輸入。專案與工作項目記下在做什麼、為什麼：需求原文、驗收、步驟，以及做這件事的 sessions、checkpoint、操作與 PR。有 `manage` 的 agent 可以回報完成；只有帶 `approve` 的 token 能確認完成，而且確認的是它讀到的內容，之後內容再改會重新等待確認。排序、固定、改名與封存沿用 Project Hub 的規則。要接續人的工作而不碰它的 session，先記下 checkpoint（`checkpoint.create`：commit 與最近對話，只讀），再從它開始 managed 工作（`checkpoint.continue`：在 Connector 自有的 clone、worktree、分支與 session 從那個 commit 開始）。需要 `managed_roots` 與主機的 SSH alias。要把成果放進既有 PR，先預覽（`integration.preview`：列出以 SHA 釘住、會進 PR 的每個 commit 與檔案），再套用預覽（`integration.apply`：以主機的 git 憑證，一般 push 組合後的 commit 到 PR 的 head 分支；不強推，也不改你的資料夾），需要在 repository 的 `[[github.repos]]` 設定 `integrate = {hosts, remote_url}`。設計見 [docs/design/api-v1.md](docs/design/api-v1.md)、[docs/design/delivery.md](docs/design/delivery.md)、[docs/design/dashboard.md](docs/design/dashboard.md)、[docs/design/checkpoints.md](docs/design/checkpoints.md)、[docs/design/integration.md](docs/design/integration.md)、[docs/design/work-items.md](docs/design/work-items.md)。

PR metadata 使用獨立 action `github.pr.update`：既有 integrate scope，加 repository `allow_pr_update = true`（預設 false），不需要重新發 token。先以 `github_pr_preview`／`batc delivery pr` 讀 title/body digest 與保存的 merge scope；metadata 寫前比較、寫後讀回，但 GitHub 最後讀寫窗口仍有競爭限制。合併前檢視完整 commits／受影響 PR，再以 `github_pr_merge`／`batc delivery merge --preview mpv_... --key KEY` 送出；舊 head-only 請求會拒絕。提交前 base 變動停止，queue 受理後可合併到較新 base 並列出其他 commits；驗證 actual merged SHA，拒絕不支援的 stack／間接合併。MCP／CLI 寫入需要 caller 自己的 BATC_API_TOKEN。詳見 [交付設計](docs/design/delivery.md)。部署 history、environment generations、runtime verification 與 rollback 留待 Part B。

未知 metadata 寫入滿 10 分鐘後讀回仍未變，會結案為 not_applied、釋放 PR，不重送 PATCH；新編輯仍須讀取新 digest。相同 merge preview 重用 ID；事件重載的完整 scope 讀取以 60 秒節流，head／base 變動立即刷新，送出合併前仍完整核對。

## 工具一覽

| 工具 | 用途 |
|---|---|
| `hosts_list(probe=true)` | 已設定的主機；加上 probe 時，顯示是否連得到、伺服器版本與 ping。 |
| `host_status(host)` | 版本、協定、連線／認證／ping 延遲，以及工作區、終端機、agent session、已載入與串流中 session 的數量。 |
| `workspaces_list(host?)` | 工作區，附資料夾與 session 數量。 |
| `sessions_list(host?, workspace?, agent?, only_loaded?, active_within_hours?, check_pending=auto, limit=50)` | agent session，最近有活動的排在前面：工作區、標題、cwd、agent 種類、模型、是否已載入、是否串流中、待回答的問題、最後活動時間（與來源）、worktree 分支、是否受調度（orchestrated）。 |
| `session_read(host, session_id, last_n=20, offset=0, include_tools=false, max_chars=12000, after=null)` | 以精簡文字分頁讀取最新訊息（`next_offset`），有大小上限；也附上待回答的問題與串流中的尾段。`session_id` 可以用唯一的前綴。對 Claude，`after=<turn_marker>` 會比對 BAT 回傳的確切 echo ID，並隱藏尚未確認的排隊輸出。 |
| `session_wait(host, session_id, until=attention, timeout_s=120, require_new=false, after=null)` | 等到這一輪結束、出現問題或權限請求，或發生錯誤。`after=<turn_marker>`（來自 `session_send`／`session_relay`）會對應 Claude 的 echo，回報 accepted／running／terminal 階段；過時的閒置狀態不算數。BAT 的 Codex 不會回傳 `clientMessageId`，所以改用較弱的時間戳備援。 |
| `worktree_status(host, workspace?)` | worktree session：分支、來源分支、merge 狀態、diff 統計。 |
| `session_worktree_status(host, session_id, include_diff?)` | 單一 session 的同樣資訊，另加尚未提交的檔案與主要 checkout 的狀態。 |
| `session_send(host, session_id, text, confirm, message_id?, queue?)` | 送出訊息；session 尚未載入時，會先由客戶端恢復它；以 `message_id` 保證冪等。 |
| `session_continue(host, session_id, confirm, text="continue")` | 推一下。 |
| `session_interrupt(host, session_id, mode=soft\|hard, confirm)` | soft 是 Claude 的 interrupt-turn，hard 是 abort（Codex 一律 hard）。session 會保留。 |
| `session_answer(host, session_id, confirm, answers? \| permission?)` | 回答待處理的 ask-user 問題或權限請求。 |
| `session_start(host, workspace, agent, confirm, prompt?, model?, use_worktree=true)` | 啟動 session（預設開在新的 worktree；分支由 BAT 命名為 `bat/worktree-<id>`）。每台主機有數量上限。 |
| `worktree_merge(host, session_id, confirm)` | 只 merge 到位於 managed root 內的主 checkout，而且要能證明沒有衝突、乾淨；否則回報原因。 |
| `worktree_remove(host, session_id, confirm, delete_branch=false, ...)` | 移除 worktree 資料夾；預設保留分支；遇到未提交或未 merge 的工作會拒絕，除非明確指示。 |
| `sessions_triage(host?, workspace?, agent?, states?, use_jev=auto, include_unloaded=true)` | 把每個 session 分類為 `quota_exhausted`、`rate_limited_transient`、`waiting_permission`、`waiting_question`、`working`、`done_idle`、`error_other`、`unknown`，並附上 `source`（pattern／jev）、信心值、判斷依據的那一行，以及額度重置時間。 |
| `quota_sessions(host?)` | 捷徑：因用量額度而停下的 Claude session。 |
| `session_set_permissions(host, session_id, mode, confirm)` | `allow_all`（主機必須允許）或 `default`。Claude session 只在閒置時切換（這一輪進行中切換會讓這一輪結束）；Codex 從下一輪開始套用。 |
| `approve_pending(host, confirm, dry_run?)` | 以「不再詢問」核准所有待處理的權限請求（不含問題），並把 session 提升為 allow-all。只能用在 `default_permission_mode = "allow_all"` 的主機。 |
| `session_failover(host, session_id? \| all_exhausted, confirm, dry_run?, model?, force?, instructions?, archive_only?)` | 啟動一個 Codex session，接續因額度停下、由 connector 建立的 Claude session：有 worktree 時沿用同一個 worktree，交接 prompt 帶著原始任務、最新指示、最近的輸出與 git 狀態（憑證已遮蔽）。具冪等性。`model` 預設為主機的 `codex_model`。`instructions` 會取代預設的「繼續完成任務」步驟（例如「只 commit 進行中的工作」）；`archive_only` 讓清理時保留該分支、不 merge。 |
| `session_relay(host, message, confirm, workspace? \| session_id?, brief?, earlier?, channel?, thread?, request_fanout=0, dry_run?, start_if_missing?)` | 把人的訊息原封不動轉給工作區最近一個由 connector 建立的 session（或指定的 session；在 BAT 建立的 session 一律不寫入，`start_if_missing` 改在新 worktree 開 session），可附一段標明是轉達者詮釋的摘要，以及 BAT-STATUS 結尾說明。`request_fanout=N` 會請 session 產出 `bat-fanout` 計畫。回傳組好的文字。 |
| `fanout_plan_session(host, workspace, message, confirm, max_items=4, brief?)` | 在獨立 worktree 啟動一個 Codex 規劃 session（適用於沒有 managed session 可規劃時），由它回覆一份 `bat-fanout` 計畫。 |
| `session_policy(host, session_id?)` | 唯讀。主機的 mutation 清單與 managed roots，或單一 session 的來源（`manual`、`connector_managed`、`unknown`）、資料夾歸屬與每個寫入動作的判定與拒絕代碼。 |
| `fanout_from_plan(host, session_id, confirm, dry_run?, agent="codex", model?, max_items=4)` | 依該 session 最後一個 `bat-fanout` 區塊，每個任務各開一個 worktree session，prompt 原封不動，接著清掉規劃 session。 |
| `session_cleanup(host, confirm, dry_run=true, session_id?)` | 在硬性關卡後面，為每個受調度的 session 決定 MERGE_AND_CLEAN／CLEAN_ONLY／KEEP／ESCALATE，然後執行（需要 `auto_cleanup = true`）。詳見 docs/ORCHESTRATE.md。 |
| `session_record_verification(host, session_id, candidate_commit, command, exit_code, environment, log_ref, confirm)` | 為主機目前乾淨的 commit 記錄一筆在外部執行的驗證；自動清理在 merge 前會再檢查一次。CLI：`batc record-verification`。 |

## CLI

```bash
batc hosts
batc status box1
batc sessions --active-within 24
batc --json sessions box1 --workspace api
batc read box1 1a2b3c4d -n 30
batc wait box1 1a2b3c4d --timeout 600
batc worktrees box1
# write 層（主機需設 writes = true）
batc send box1 1a2b3c4d "Please run the tests and fix failures" --confirm
batc continue box1 1a2b3c4d --confirm
batc interrupt box1 1a2b3c4d --mode soft --confirm
batc answer box1 1a2b3c4d --answer "Which database?=postgres" --confirm
# orchestrate 層
batc fanout PLAN.md                                   # dry run：拆成各個任務的 prompt
batc fanout PLAN.md --start --host box1 --workspace api --confirm
batc merge box1 1a2b3c4d --confirm
batc remove-worktree box1 1a2b3c4d --confirm
# 生命週期
batc triage box1 --state quota_exhausted --state waiting_permission
batc quota                                            # 所有主機上因額度停下的 Claude session
batc approve-pending box1 --dry-run                   # 確認後改用 --confirm
batc permissions box1 1a2b3c4d --mode allow_all --confirm
batc failover box1 --all-exhausted --dry-run          # 確認後改用 --confirm
batc cleanup box1                                     # dry run 表格；要執行請加 --apply --confirm
```

每個指令都能用全域的 `--json` 旗標，但要放在指令前面：`batc --json hosts`。

## 轉達、分派與狀態標記

替人轉達指令的助理（例如從聊天室轉過來）不應該改寫或自己規劃這些指令。`session_relay` 會原封不動送出訊息，可附一段標明身分的摘要；由握有 repo 脈絡的 coding session 來詮釋，把不清楚的要求補齊，並用一行說明它的理解。需要平行處理時，由該 session（或一個唯讀的規劃 session）寫出 `bat-fanout` 區塊：

```bat-fanout
[{"title": "short title", "prompt": "self-contained task prompt", "area": "files/modules touched"}]
```

`fanout_from_plan` 就只啟動這幾個任務。每次停下來都以一行結尾：`BAT-STATUS: MILESTONE <name>`、`BAT-STATUS: CONTINUE <next step>` 或 `BAT-STATUS: NEED-<HUMAN> <reason>`；triage 會把它當成「已完成」的聲明。它不能取代自動清理需要的、綁定 commit 的驗證紀錄。

## 安全模型（精簡版）

* 預設唯讀；寫入與調度要逐台主機開啟，需要 `confirm=true`，有速率限制，並留有稽核記錄。
* 人在 BAT 建立的 session 對所有工具永久唯讀。寫入只會送到 connector 自己建立、且位於它擁有之資料夾的 session；client 核心拒絕任何沒有資源政策 grant 的寫入 frame（見 [docs/design/resource-policy.md](docs/design/resource-policy.md)）。
* TLS 憑證指紋比對是強制的；不符時會在送出 token 之前中止。只接受 `bat-remote/v2`。
* Token 在連線時才從參照解析出來，並從所有錯誤訊息中遮蔽。
* 客戶端會一直把 socket 讀空（BAT 會斷掉累積 256 個待送 frame 的客戶端），事件佇列也有上限。
* Session 裡的文字是不可信任的輸入：agent 不應該照著裡面的指示做。
* 選用的 Jev 判斷層會先試 TypeSafe，再試 OpenRouter Decisions 的 `typesafe/jev-1.13`，使用環境變數裡的 `OPENROUTER_API_KEY`。幾秒後就逾時，兩者都失敗時保留確定性的判斷結果。它只拿到簡短的摘錄，疑似憑證的字串都會先遮蔽。這裡不存放任何 key。

細節：[SECURITY.md](SECURITY.md)、[docs/PROTOCOL.md](docs/PROTOCOL.md)、[docs/ORCHESTRATE.md](docs/ORCHESTRATE.md)。

## 開發

```bash
uv sync --extra dev
uv run ruff check . && uv run pytest            # 單元測試使用模擬的 TLS WebSocket 伺服器
BATC_LIVE=1 uv run pytest tests/test_live.py    # 選用：對你設定好的主機跑唯讀測試
```

## 授權

MIT，見 [LICENSE](LICENSE)。BAT 本身由 TonyQ 以 MIT 授權釋出。
