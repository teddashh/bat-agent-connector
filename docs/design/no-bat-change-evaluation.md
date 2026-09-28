# BAT 不改版時，Hermes 要怎麼穩定交辦程式工作

日期：2026-09-27。本文只評估，不修改 BAT 或連接器程式。PR [#1](https://github.com/teddashh/bat-agent-connector/pull/1) 已修正部分連接器問題，但不能把 BAT 當成會替外部控制器記錄任務、鎖住工作目錄的排程器。

**資料範圍。** Ted 所說的「兩篇」其實是同一份[研究文字](../research/2026-09-27-review.md)的 Part 1（連接器與 Goose）和 Part 2（Buzz），不是 Tony 的文章；沒有使用或搜尋 Tony 文章。本文另核對 Ted 放在工作樹的 `docs/current-workflow.md` 與 `docs/hermes-bat-log-excerpts.txt`、本庫的[遠端協定筆記](../PROTOCOL.md)、[上一版設計](next-gen-connector.md)及原始碼。前兩份是本次提供的本地證據，未隨評估文件提交。BAT `5a61d43`、Goose `04ed836`、Buzz `b0d6fb8` 是唯讀參考快照。這些快照能說明當時的程式行為，不保證所有五台主機已部署同版。

## 我的判斷

若目標是讓手機 Discord 指令可靠地完成工作，**預設應採「一個持久協調器 + 主機上的 Codex CLI／`codex exec` 或 Claude Code 無介面執行器」**。協調器負責任務、去重、停止、驗證和 Discord 回報；BAT 用於 Ted 查看工作目錄、Git、終端及手動工作。這條路讓執行器直接回報程序狀態與日誌，避開 BAT Codex 回合辨識、GUI 搶寫及無法原子新增頁籤的限制。代價是 BAT 不能保證顯示該無介面代理的**同一段即時對話**；可在 BAT 看檔案、Git、驗證日誌或另開終端看日誌，但不能宣稱是原生 BAT 代理面板。

**若「Ted 必須在 BAT 原生代理面板看見並接手同一段即時對話」是硬需求，則保留連接器 + 協調器 + 隔離的 BAT 自動化工作階段。** 這是現有限制下的最佳折衷，不是完整的強一致控制。自動化時不讓 GUI 同時寫同一 session／worktree；接手須先停派、確認舊回合停下，再由 Ted 打開。沒有 BAT 端鎖，GUI 仍可能繞過協調器，因此不能承諾零競態或 Codex 恰好執行一次。兩條路都應先用少量真實任務測量可靠度，再決定是否增加 Goose。

## 現況與 BAT 的設計邊界

Ted 在 TED-H AI Discord 從手機下令；grok-bot-01 上的 Hermes（Gemini 經 agy-login／agy-openai-shim）解讀與轉交。Hermes 透過 MCP／`batc` 的 `bat-remote/v2` 連 castle1、peach1 及 oracle1/2/3；本機代理各自可連本機 BAT，castle1 的 OpenClaw 也能連五台。它在專案 workspace 與 `.bat-worktrees/<id>` 建立或重用 Claude／Codex session，等待回合，把進度送到 Discord thread；15 分鐘的 `bat-watch` 與 5 分鐘派票 cron 另行運作。Claude 額度不足時轉 Codex，額度優先順序為 Google、Codex、Claude。Ted 偶爾在 GUI 直接接手同一個 session。Hermes 的基礎 prompt 約 45–48k tokens，120k 才壓縮；讓它反覆等待每張票既耗配額，也增加 thread 狀態漂移的機會。

BAT [README](https://github.com/tony1223/better-agent-terminal/blob/5a61d43/README.md)描述的是多工作區的終端與內建 Claude／Codex 面板；遠端 WebSocket 主要供另一個 BAT 或行動裝置操作主機，也可用無 GUI 的 `bat-server`。本庫以相同遠端 API 延伸成 MCP／CLI 是合理的，但 API 的基本單位仍是 session、workspace、事件，不是耐重啟的「Discord 任務」。`claude:get-session-meta/state` 可輪詢狀態，`agent:*` 串流事件在斷線期間會遺失；`workspace:save` 覆寫整份 workspace 文件。BAT 遠端 token 的權限很大，跨機的控制面必須自行控管。

目前不註冊 GUI 頁籤的 headless session 只存在連接器本機的 `orchestrated.json`；[registry.py](../../src/bat_agent_connector/registry.py) 使用本機 `flock`，grok-bot-01 與 castle1 的 OpenClaw 並不共享這份記錄。若啟用 `orchestrate_register_tabs`，連接器以 `workspace:save` 寫整份文件，和 GUI 同時存檔仍會遺失更新。**不改 BAT 時，不能同時保證「自動建立 BAT 可見頁籤」和「GUI 編輯絕不被覆蓋」。** 可以讓 Ted 手動打開獨立工作目錄／session，或接受經測量的風險；不應把選項寫成已解決。

## 日誌能證明什麼、還不能證明什麼

以下時間來自 Ted 複製的 grok-bot-01 grep 摘錄（工作樹 `docs/hermes-bat-log-excerpts.txt`），是選過的行，不含完整工具參數、回傳內容或同時的 BAT 主機日誌。

| 觀察 | 可以下的結論 | 仍需查明 |
| --- | --- | --- |
| 9/26 至 9/27 大量 `mcp__bat__session_wait` 約 60／90／120 秒才回，偶有 200 秒以上，結果常只有 176／177 bytes | Hermes 的工作單元長時間被等待占住，值得把監看移出對話回合；小結果長度本身不代表 BAT 沒進度 | 逐次回傳的 `status`、`after`、`turn_phase`、BAT `numTurns`、是否同一任務重複輪詢 |
| 9/26 22:35:10 等待因 Ted 新訊息中斷 | 使用者插話確實會取消 MCP 等待；如果後續只靠短暫事件，會漏看回合 | 取消後是否重新讀取該 task／session，或意外重送 prompt |
| 9/27 12:22:32 `gateway.mirror` 回報 Discord thread「no session found」 | 有獨立於 BAT 的 Discord 對話映射問題 | 該 thread、Hermes session、BAT session 的持久映射是否仍在，以及當時是否重啟 |
| 9/27 14:23–14:24 重啟等待一個仍在 `session_wait` 的工作單元，之後 Discord 斷線；多次重啟後 MCP 工具重新註冊 | 長等待會拖住重啟；重啟與連線生命週期確實介入了作業 | 當時 host 是否仍在跑、事件／Discord 發文是否重播 |
| 9/27 18:10 `claude:get-session-meta` 15 秒逾時；18:13 castle1 WebSocket 握手逾時 | 至少有主機／連線層的實際故障，不能全歸咎於模型忘記 | castle1 BAT 負載、連線與 sidecar 日誌、其後是否成功對帳 |
| 9/27 19:27 `bat-freshturn-guard` 擋住相似度 0.07 的舊回覆；另有 `tools.override` capability 被拒紀錄 | 舊報告重貼的風險是實際觀察，不只是推測；外掛防線也不能假定每次都啟用 | 被擋內容的來源、外掛授權狀態，以及其他未被擋的 Discord 發文 |

所以「Hermes 掉 session」至少可能包含三種不同故障：BAT 回合歸屬不明、Hermes／Discord 的 thread 映射或對話中斷、主機／WebSocket 暫時不可用。PR #1 解決舊 Claude UUID 標記解析錯誤及部分舊回合誤認，**但日誌摘錄沒有該次工具參數與回傳，不能宣稱這就是已觀察案例的唯一根因**。優先補上 `discord_thread_id → task_id → command_id → host/session_id → message_id` 的低敏感度追蹤；記錄送出、接受、輪詢、斷線、對帳及 Discord 發文 ID，不記密鑰和完整 prompt。對同一個錯誤取 Hermes、連接器 audit、BAT sidecar／Codex、主機資源四方時間線，才可定因。

## BAT 不變時的可行控制規則

### 一個持久任務帳本，Hermes 只做指揮

在 grok-bot-01 或一個固定控制主機跑**單一寫入協調器**；Hermes、cron、`batc`、castle1 OpenClaw 都透過它查詢或派工。先用 SQLite WAL 加單服務實例即可，若以後多實例才換共享資料庫。每個任務固定 `task_id`、原始 Discord 訊息與 thread、Ted 原文、標示清楚的 Hermes 解讀、專案／worktree、執行器與目前 owner。`relay.py` 保留原文和解讀分開、讓 coding session 產出 fan-out 計畫，這點研究說得對；需要修正的是 fan-out 後仍由協調器記錄每個子任務，不能靠 Hermes 記憶。

每次變更先在交易中寫 `command_id`、idempotency key、owner 與 `control_version`，再呼叫 BAT 或本機執行器。階段至少有 `reserved → dispatching → accepted → running → terminal`，另有 `uncertain`。同一 Discord 訊息／票號、同一邏輯動作不得再造第二張票；15 分鐘 watcher 只讀 task event 並以 `(task_id, event_id, Discord thread)` 去重發文。5 分鐘派票 cron 要搶同一筆原子 reservation，不能與 Grok Bot conductor 各自啟動。Grok Bot 只處理新指示、摘要及真正需要 Ted 的事項；等待、權限狀態、定期進度、重試與完成檢查交給服務。停止／接手是確定性的控制命令，先由程式處理，不能把「請停」丟給另一個模型猜。

連線逾時時保持 `uncertain`，先查 session 狀態、echo、rollout／程序日誌與工作樹，再決定是否重試。Claude 在同一 BAT sidecar 的 `clientMessageId` 可去重，但重啟後其記憶不能當永久收據；BAT Codex 根本不沿用這個 ID。**絕不可因 `session_wait` 逾時就重送新的 Codex prompt 或再建 failover。** 無法證明未被接受時，標記待對帳並提醒負責監看的 agent，不把模糊狀態報成失敗或成功。所有既有 MCP／`batc` 名稱可當相容入口，但必須共用同一帳本，否則多個本機鎖只是局部保護。

### 若仍用 BAT 原生代理執行

PR #1 在 [service.py](../../src/bat_agent_connector/service.py) 對 Claude 用精確 `clientMessageId` 對 echo，把訊息 ID 與時間游標分開；排隊回合在不能確定邊界時保守標 `queued_unconfirmed`。這修正 Part 1 Finding 1 的主要錯誤，卻不會讓舊回合最後輸出自動帶新命令 ID。BAT Codex 的 [Rust 路由](https://github.com/tony1223/better-agent-terminal/blob/5a61d43/src-tauri/src/commands/claude.rs) 丟掉 `clientMessageId`，其 user echo 自建 `user-<time>`；目前 timestamp fallback 是弱證據，而且若 session 正在跑，新送入的 Codex prompt 可能**中斷並取代**原 turn，不應當作 Claude 式佇列。

不改 host 的 Codex 對帳可以把下列線索合用，但都不能單獨作成「恰好一次」保證：

1. **送前／送後狀態輪詢。** 記下 `sdkSessionId`、`numTurns`、`isStreaming`、最新訊息 ID／時間，再在同一 session 空閒時送出，確認新增 user echo 與 turn 計數。僅在一個協調器且無 GUI 同時送話時，時間差才有意義；斷線或被他人送話時降級成 `uncertain`。
2. **內容雜湊。** 對協調器實際送出的完整 bytes 計 hash，和新增 user echo 的內容比對。可把短命、無權限的命令 nonce 放入提示作輔助，但 BAT 可能改顯示文字、重複 prompt 也會同 hash，且 hash 不能證明主機接受後是否跑完。不要把 nonce 寫進 Ted 原文段落。
3. **Codex rollout。** 若主機有唯讀檔案存取，可用 `sdkSessionId` 定位 `~/.codex/sessions/` 的 JSONL，核對 user 訊息、turn／工具事件、mtime／offset；讀取要處理延遲寫入、輪替、重啟、隱私與版型變動。BAT 的 `claude:list-sessions(agentKind=codex)` 會掃所有 rollout，可能很慢，不宜每次 wait 都調用；遠端 API 也不能保證直接讀取 rollout 檔案。用主機端唯讀 helper 比持續全量掃描合理。
4. **工作樹與輸出。** git diff、HEAD、狀態及代理回覆能證明有工作發生，不能單獨證明是哪一個送話觸發。若兩個指令內容相似、GUI 插手或事件缺失，維持不確定狀態。

因此 BAT 路線要一個 automation-only session／worktree 只容一個 writer，`queue=false` 為預設；新命令等前一回合明確終止後再送。Ted 要接手時，協調器先停止新派工、升級 `control_version`、要求目前回合停止並輪詢到 idle，記下 HEAD／未提交變動與最後訊息，再把控制權交給 Ted。若 Ted 已經直接在 GUI 輸入，協調器只能偵測意外 user echo／turn 數或檔案變化後暫停；**無 BAT host-side ownership gate，就無法阻止檢查與送話之間的競態**。人接手後不自動恢復；需明確歸還權限與重新對帳。為避開 GUI 存檔競態，自動 session 不註冊頁籤；Ted 若需要原生面板，必須接受手動建立／打開與可見性限制，不能讓程式暗中全量改寫 workspace。

### 候選版本、測試和清理

把 `TURN_FINISHED`、代理宣稱完成、`VERIFIED_CANDIDATE`、准許合併分開。[verification.py](../../src/bat_agent_connector/verification.py) 與 PR #1 已要求候選 HEAD／乾淨工作樹、測試命令、exit code、環境和日誌參照；新 commit 或髒工作樹使舊證據失效。下一步應由受控 runner 真正執行測試、存不可隨口杜撰的 log，再把 hash／結果寫帳本；目前 `session_record_verification` 仍是**呼叫者提供的聲明**，不是 BAT 自行驗證。`BAT-STATUS: MILESTONE` 只表達代理說到一個里程碑，Jev 只協助分流，兩者都不能替代執行證據。若測試後又改檔，重做驗證。對一個 clean、已驗證且政策允許的候選，可自動執行可回復的本地清理／合併；push、公開發佈、機密、金錢、破壞性或不可逆操作依 Ted 的授權界線處理。不要把頻繁的例行「完成了嗎」交給 Grok Bot 詢問。

## 三種架構的取捨

| 路線 | 在這五台主機上的實際作法 | 優點 | 缺點與適用條件 |
| --- | --- | --- | --- |
| **A. 協調器 + BAT 原生 Claude／Codex** | Hermes 與 crons 只用 task MCP；協調器轉給現有 connector，session／worktree 隔離，GUI 接手前停派 | 沿用 BAT 原生面板、現有 relay、額度切換與投資；Ted 可沿同一 BAT session 看工作 | Codex 無可靠命令 ID；BAT 事件不持久；GUI 不能硬鎖；自動頁籤有整份覆寫競態。只有「同一原生面板」不可退讓時選這條 |
| **B. 協調器 + 主機 Codex CLI／Claude Code headless（建議預設）** | 在 castle1／peach1／oracle 主機跑受控程序與獨立 worktree；程序輸出／rollout／exit 存到 task journal；BAT 看檔案、Git 與日誌 | 一次性任務有明確程序生命週期、退出狀態、日誌和取消；不經 BAT 的 Codex 回合猜測與 workspace 頁籤存檔 | 需實作可信 runner、額度／身分設定和日誌留存；BAT 不會原生顯示同一段 headless 對話。Ted 若要直接接手，須停止程序、保留 worktree，再開新的 BAT session，對話脈絡靠交接摘要與檔案 |
| **C. Goose／其他 harness 取代 BAT 作自動化** | 協調器把任務送給 Goose ACP 或單次任務 harness；BAT 仍可看 repo，或不再參與自動化 | 可選一致的 agent 執行介面、會話管理與工具限制 | 換模型供應商與新的狀態／授權／故障面；Goose `ActiveRunRegistry` 只保護 Goose session，不鎖 BAT／Git；不會自動解決 Discord 去重與驗證。僅在實測明顯優於 B、且功能真的需要時採用 |

路線 B 的「BAT 只供人看」要說清楚：BAT 可以看 workspace 檔案、Git 檢視或終端 tail 日誌；Codex CLI 的 `apply_patch` 視覺化可能和現況一樣不完整，也不會神奇變成 BAT Codex 面板內容。若 Ted 在意完整即時對話，提供協調器唯讀事件頁或日誌連結，比假裝 BAT 能導入外部會話更誠實。只在本機 loopback 開 HTTP；要從其他主機或手機直連，先有明確身分驗證、授權、傳輸保護與操作稽核。對五台主機的現有 BAT token，不要再開放一個未授權的網路寫入 API。

## 對兩部分研究與 PR #1 的評價

| 研究主張 | 評價 |
| --- | --- |
| Part 1：連接器為基礎，Goose ACP 可選；不要讓 Goose 代替確定性的狀態查詢 | **同意前半，修正「最佳預設」。** 現有 connector 是 BAT 路線最省力的入口，Goose 也適合選擇性解讀；但在 BAT 不可改、GUI 偶爾接手、Codex 占主要額度時，不能先假定 BAT 應是自動化執行核心。先比較直接 headless runner |
| Part 1 Findings 1–5 | **1、3、5 核實且 PR #1 有連接器修正；2、4 只能部分緩解。** 1 的 Claude UUID echo 精確對應已修；Codex 仍用弱游標。3 的 `flock` 原子 failover 只保護同一狀態目錄。5 的驗證紀錄綁候選版，但來源仍須可信。2 的本機鎖不管其他程序或 GUI；4 的整份 workspace 存檔競態不可由重試消除 |
| Part 1：共享協調器、所有人共用 task ID／journal／owner | **同意，而且比增加模型層更急。** 目前 grok-bot-01、castle1 OpenClaw、cron 和 BAT GUI 的控制面分散；但 `control_version` 只能拒絕經協調器的舊命令，不能給 BAT GUI 加鎖。先只做一個服務、少量 task MCP 與唯讀狀態頁，避免一開始建龐大平台 |
| Part 1：Goose ACP resume／MCP | **有條件同意。** 已檢查的 Goose 原碼有 ACP resume 與每個 Goose session 的 active-run 限制；仍需在實際版本、供應商及斷線情境測試。Goose 不是 BAT owner，不能修復 GUI 搶寫或 Discord thread 映射 |
| Part 2：借 Buzz 單任務邊界、期限、取消與結構化結果，不搬整套平台 | **同意。** `run_task.rs` 與 `isolated_execution.rs` 提供清楚的一次性執行合約。要再補一個耐重啟去重帳本和測試驗證器；Buzz 的 `taskId` 是關聯 ID，非永久去重收據。Buzz 完整 relay／Postgres／Redis／MinIO 對現有 Discord 流程成本過高 |

上一版[設計](next-gen-connector.md)提出 BAT 上游 `workspace:add-terminal`、Codex `clientMessageId` 與 host ownership gate，這些在長期研究上合理，**但本評估的任何可行方案都不依賴它們，也不把上游 PR 當待辦前提**。PR #1 是已發生的連接器改善，不能把其保守 `turn_phase` 解讀成 BAT 提供了通用 transaction ID。

## 落地順序與驗收

1. **先止住重貼與漏追。** 持久保存 Discord thread／原訊息 ID 到 task 的映射，watcher 只讀增量 event；把 `session_wait` 改成短、可取消的服務端輪詢，Hermes 回覆 Ted 後退出等待。每個 Discord 發文記 event ID，重啟後不能再貼同一份 Staging 報告。檢查 `bat-freshturn-guard` 的授權狀態，但不讓外掛當唯一防線。
2. **建最小單協調器。** 讓 grok-bot-01、castle1 OpenClaw、5 分鐘派票及 15 分鐘 watcher 使用同一 task／command 帳本；導入既有 connector registry，避免既有任務被當新任務。第一版可繼續跑 BAT Claude，並以隔離 session 驗證 BAT Codex；新增任務優先試 B 的 headless runner。保留 Ted 原文與 Hermes 解讀的分開標示。
3. **量化 A 與 B。** 同類 ticket 各跑一小批：送出後斷線、重啟、使用者插話、Claude 額度耗盡、同時 failover、GUI 提前打開、測試後又改碼。記錄重複執行／漏回報／人工接手耗時／錯誤合併數，以及 Gemini、Codex、Claude 用量。只有 B 的 BAT 可見性不足以接受時才把 A 作主路；只有 Goose 在可靠度或成本有實證收益時才接入。
4. **驗證與清理分開交付。** runner 保存指令、exit code、環境、完整日誌參照和候選 commit/tree；合併前重查 HEAD 與 dirty tree。測試通過後改碼必須失效，舊 `MILESTONE`、Jev 或 watcher 文案不得放行。停止／接手後停派與撤銷舊 owner 版本；無法確認 BAT GUI 是否已動手時保守暫停自動清理。

驗收測試至少包含 BAT 真實 `batc-<uuid>` Claude echo、排隊送話後舊回合輸出、Codex 重複 prompt／rollout 比對、兩個控制器同時 failover、GUI 存檔撞上頁籤註冊、主機接受後立即斷線、Discord 等待遭新訊息中斷、Hermes 重啟後重貼防護，以及測試成功後再修改程式。預期可達成的是「持久知道任務是否確定、可安全停止並對帳」；在 BAT 不改版且允許 GUI 直接寫同一 session 的條件下，**不能承諾所有 BAT Codex 命令恰好執行一次，或完全無競態的同 session 接手**。
