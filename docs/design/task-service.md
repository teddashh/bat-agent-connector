# 任務服務：第一階段實作與第二階段計畫

日期：2026-09-27。依照 Ted 核准的架構；BAT 原始碼與既有低階 MCP／`batc` 介面不變。

## 現在要解決的事

Ted 只對 Discord 裡的 Hermes 說話。Hermes 只能逐字保存原話、交辦一次、回報結果；絕不能改寫、解讀或拆解要求。若舊呼叫者仍傳 `interpretation`，此欄僅保存為**非權威的外部附註**，不放進 coding prompt。規劃與拆解交給熟悉 repo 的 Codex／Claude lead session，遵守 `relay.py` 原話優先的界線。Hermes 不應在 `session_wait` 裡等 60／90／120 秒。新訊息曾打斷等待，造成找不到 session、重啟被 active wait 擋住、操作者工作站（下稱 `host-a`）的 metadata／handshake timeout，以及 stale reply guard 擋回覆。現在 `orchestrate_register_tabs=false`，自動 session 在遠端 BAT GUI 看不到。任務服務必須自己保存任務和進度，不以 GUI 或 Hermes 記憶當帳本。

## 第一階段：可執行範圍

下方既有 one-line README 本機 A/B 時間是在 Jev review gate 加入前量測；不包含新的 Jev 網路等待，不能當作目前交付時間。

`batc serve` 是單一長期程序。它擁有 SQLite WAL 任務、命令及事件帳本，提供 loopback HTTP 給本機 MCP 客戶端與 `host-a` 上 OpenClaw 的受控轉接。標準路徑的 `work_submit` 只寫帳本並立即回 `task_id`；最小路徑先做一次有界 Jev 判斷再回傳；`work_status`、`work_pause`、`work_resume`、`work_result` 讀／改同一帳本。提交逐字保存 Ted 原話、Discord thread、recipe、驗收條件及 idempotency key；可選的 interpretation 是非權威記錄，不進 prompt。重複 key 回原 task；同 key 不同內容拒絕。預設 rules 引擎。`goose` 是明確 opt-in。

新 `task_path="minimal"` 是獨立、可 A/B 的 opt-in 路徑，預設仍為 `standard`。首次 `work_submit` 只列出**實際可執行**的引擎：Goose live contract gate 關閉時只有 rules，直接採用、不問 Jev（原因 `only_runnable_engine`）。只有兩個引擎都可執行時才問 Jev **一個** typed choice：`rules_engine` 或 `goose`；原文只作分類資料，不由 Hermes 改寫或拆解。Jev 不可用、逾時或 typed 回答無效時選 rules。選擇、信心、`jev_backend`、實際引擎與原因在同一提交交易中寫入 `engine_decision` 事件；重複 idempotency key 不再重新決定。最小路徑不記 PM 每步 routing；`work_status` 仍回報提交時的決策。

最小路徑的 `small-task-with-tests` recipe 是明確的小任務選擇，因提交時的一個 Jev 問題不能同時暗中判斷規模。它仍要求目前乾淨 commit/tree 上由服務觀察到的 trusted test 命令 exit code 0，並確認 lead 已閒置。測試通過後，服務取得完整的小候選 diff 與檔案路徑，把 diff 及 Ted 的 `original_words`（離開主機前遮蔽疑似 credential）交給**一個 typed Jev choice**，同時判斷是否滿足要求、有無明顯風險。沿用 TypeSafe → OpenRouter Decisions `typesafe/jev-1.13` 的同題 fallback；不用 chat/completions、`typesafe/jev-router` 或一般 LLM。只有 PASS 且信心 ≥ 0.50、backend 有效、測試及乾淨 commit/tree 仍吻合，才略過獨立 reviewer。低信心、FAIL、風險／不確定、敏感路徑、diff 超過 3500 字、缺 diff／baseline、Jev 兩端無效或失敗，一律轉現有獨立 reviewer；敏感／過大 diff 不送 Jev。私有 0600 `BATC_PM_PROVIDER_CONFIG` 的 `[router]` 可調 `minimal_review_confidence_threshold`、`minimal_review_max_diff_chars`（最多 4000）和 `minimal_review_sensitive_paths` glob 清單，預設涵蓋 auth、secrets、CI、deploy、migrations、credentials、tokens、Docker、infra。`minimal_review_gates` 先記 candidate commit/tree、完整 diff SHA-256 與 pending，再記 verdict、confidence、backend、原因並寫事件；重啟遇 pending 直接升級 reviewer，不重問 Jev。`work_status.minimal_review_gate` 可查決策；保留事件另記 diff 字數與路徑。`python -m bat_agent_connector.gate_eval --db <journal>` 唯讀列出每個 gate 候選的 Jev 選擇／信心、同 candidate 的獨立 reviewer 結果，以及 0.50、0.45、「PASS＋極小非敏感 diff」三種政策的 false pass／false escalate 次數（不呼叫模型）。門檻仍為 0.50。`work_status`／`work_result` 的 `delivery` 區分 `verified`（受信測試＋reviewer／gate 通過）與 `adopted`、`merged`、`deployed`；後三者只在以 `work_mark_stage` 記錄（附 commit／PR／部署參照）後出現，服務本身不 merge、不部署。`work_submit` 可附 `context_refs`（attachments、previous_message_id、plan、commit），僅保存為資料。通過獨立 reviewer 時仍需同 commit/tree 的結構化 PASS verdict（見〈Release boundary〉）；Jev PASS 本身不代表測試通過。其他 recipe 照舊需要 reviewer。服務只在**同一工作流**的後續任務重用同 project、host、workspace、agent 的**已完成、沒有共享 reviewer session** task 之既有 lead session/branch：新任務的 `parent_task_id` 指向該 task（或同一 parent 的兄弟 task），或 `continuation=true` 且 `discord_thread_id` 相同；並且 worktree 目前 HEAD 必須等於前一 task 的 `verification_commit`。獨立的新請求一律從 base 開新 branch（工具快取照常共用）。移轉前撤銷舊 task-scoped capability，移轉後任何舊 task 工具讀取遇到 registry 所有權變更即拒絕；須驗證 registry 所有權、BAT meta、worktree path/branch、Git root、非 streaming、無 pending、工作樹乾淨且寫入間隔已過，再以 registry lock 原子轉移所有權。任何證據不足即建立新 session/worktree；重新接手仍記新的 task branch，task_id 不變。帶明確 `base_branch` 的 task 不跨任務重用。此路徑仍遵守全域每小時寫入上限與後續 prompt 間隔。

本機 one-line README 模擬 A/B（fake BAT、Jev network 關閉、可信測試 fake，並非實際 README 修改）：每組 10 個完成任務，標準 `bugfix-with-tests` 中位數 48.44 ms、最小 `small-task-with-tests` 中位數 22.73 ms。數字只衡量本機 journal／coordinator 路徑，沒有 BAT、模型、SSH、真實測試或網路延遲；不能外推真實交付時間。`fix/task-initial-write-spacing` PR 另外修正 start 後首個 `lead:initial`／`reviewer:initial` 被 60 秒同 session 限速誤擋，仍保留每小時 cap 與後續 write spacing；此分支以該修正為基礎，不改 BAT 或 Hermes 部署。

服務每次先記命令 intent，再呼叫 BAT。單一 task 的同一 host/session 只有一個 writer；控制版本與 pause 在送出前重查。送出逾時後標 `uncertain`，**絕不重送同一命令**。Claude→Codex failover 也分成原子預留 successor 與獨立 `send` 命令：handoff prompt 送出前已有 task／command ID、`needs_review` marker 和完整 prompt hash。BAT 接受不等於 Codex 回合歸因；重啟後若只能證實 successor 存在，仍把 handoff send 留在 uncertain。BAT Codex 沒有可靠的 host-side command receipt，無法承諾 exactly once；BAT GUI 不受 connector 鎖約束；舊低階工具現在經原 coordinator 的 task gate。新自動化入口須用 task 工具。

Rules 引擎在回合確定完成、尚未達驗收、沒有 blocker／額度／人工接管且未達 recipe 續推上限時，派一次短 `continue`；模糊語意才請 Jev 分類。狀態包括 queued、dispatching、accepted、running、waiting_permission、quota_limited、human_owned、needs_ted、verifying、done、failed、uncertain。Pause 停止新派送，可選擇 abort 當前回合或讓其結束；resume 先對帳再續推。額度 failover 呼叫 PR #1 的原子 successor reservation 路徑，記下新舊 session。開發者自稱完成、測試通過後，starter recipe 預設開**另一個** reviewer session：Claude 額度可用時用 Claude，否則用全新 Codex。Reviewer 依驗收條件回報；拒絕時送回開發者並計數，達 retry cap 即請 Ted 處理。通過後才以 PR #1 的 commit 綁定驗證紀錄進入 VERIFIED_CANDIDATE。`done` 仍需驗證與 review 都通過。代理自稱 MILESTONE 只進 verifying。

里程碑事件流（2026-09-29 取代 Discord 發文者）：服務不再知道 Discord 存在，也不發任何聊天訊息。唯讀 MCP 工具 `work_events(since_cursor, limit)`（RPC `work_events`、CLI `batc task-events`）只回傳四種里程碑：`started`（首次 accepted/running，或 needs_ted 後恢復）、`needs_ted`（附具體原因）、`done`（附 commit／PR 連結）、`failed`。每筆含單調遞增的 `cursor`（event id）、`task_id`、`project`、`workspace`、`origin_thread_id`（提交時的不透明來源參照，欄位仍名為 `discord_thread_id`）、`kind`、簡短 `summary`。`next_cursor` 會越過非里程碑事件；讀取端（Hermes）發文成功後才保存游標；`limit=0` 只回 `head_cursor`，新讀取端可從「現在」開始、不補發歷史。主要路徑是推播：私有設定 `[task_service.event_webhook]` 的 `url`（僅限 loopback）與 `secret_file`（0600）設定後，每個已提交的里程碑依 cursor 順序以純 JSON POST 出去（HMAC-SHA256 `X-Webhook-Signature-V2`、`X-Webhook-Timestamp`、`X-Request-ID`、`delivered_through`），推播游標首次設定時從「現在」開始、只在 2xx 後前進，失敗以指數退避（上限 300 秒）重試；`work_events` 只作接收端斷線後的補漏。舊帳本開啟時移除 `events.discord_status`、`events.discord_message_id` 與 `board` 表，舊積壓永遠不會被發出。

每一個 task 是一個 Goose session，固定 Opus 5.5。`goose-session` recipe 的 prompt 指示 Goose 在開始時拆一次，再以 Grok 4.7 : Codex : Opus 5.5 = 4:2:1 的比例派工，且不把新工作派給週配額剩餘 15% 或以下的模型；這些是 prompt 裡的指引，服務程式不計算派工比例，也不讀取配額。服務不選模型、不開獨立 reviewer、也不在任務中途 failover。驗證是受信測試；程式失敗回到同一個 session 做有上限的返工，用盡才 `needs_ted`。Ted 之後的指示是同一個 task 的 continuation（不新建 task、不重新規劃）。Jev 不在這條路上；只有 orchestrator 已經拆好並傳入 `executor_model`（grok、codex 或 claude）時才問一次 Jev，並跳過 Opus；問題文字請 Jev 在該模型週配額剩餘 15% 或以下時回 reject，有效的 reject 會拒絕這次提交，服務本身不查配額。Goose 由 `GooseConfig.enabled` 一個開關控制，預設關閉，關閉時 task 停在 queued。見 docs/design/provider-routing.md。

里程碑只有四種：`started`、`needs_ted`、`done`、`failed`。`work_status`／`work_result` 是純讀取，不寫 routing、不呼叫模型。

Goose 執行檔固定版本 **v1.52.0**，只安裝在執行 Hermes 與 `batc serve` 的控制主機（下稱 `control-host`）上，位於執行帳號的 `~/.local/bin/goose`；Ted 從官方 `aaif-goose/goose` v1.52.0 Linux x86_64 release 安裝，並核對 archive SHA-256 `4aee1f770b405c44194c0e9407df1fb06bda4c50eee935f0d8fd10731821cc5e`。connector `GooseConfig.expected_version` 及執行前檢查也固定為 `1.52.0`。本 worktree 沒有該 binary；Goose 與 connector 分別版本化，不能修改 Goose bundle。升版須重新跑下方契約門檻。

端點現況：`host-a` 上既有 agy-openai-shim 位於其**本機** `127.0.0.1:18795`；公開 `/v1/models` 只列 Gemini ID。Claude 請求失敗，因 agy model resolver 給 Claude 加了不支援的 `--effort medium`。舊版 Sonnet smoke 僅屬歷史證據，**不能證明目前 Opus-thinking 設定**。本輪只在暫時的 loopback `18796` 複製 shim 程式及修正 Claude effort resolver；既有 Hermes shim 程式、服務及設定均未更動。正式 shim 仍須加入 Opus model list 與 Claude effort 修正，並以合約測試證明；不能把 18795 當可用 Claude 端點，也不能把暫時埠當永久配置。Goose 的 base URL、model、token 仍須從私有 0600 設定／環境提供，不寫進 repo。沒有讀取或提交金鑰，也未使用付費 API key。

先前隔離 Goose v1.52.0 ACP smoke 使用 Sonnet，只保留為歷史連通性證據。2026-09-28 本輪從官方 release 暫時下載 Goose v1.52.0，archive SHA-256 再次符合上列 pin；以**隔離 18796 shim + `claude-opus-4-6-thinking`** 發送一則 `OPUS_OK` 小測試，回 HTTP 200 並含指定 marker。隨後同一 Opus-thinking endpoint 跑 PR 的 GooseACP、task-scoped MCP 與 fake task HTTP：ACP 回 `end_turn`，fake endpoint 收到**恰好一次** `task_send`，文字為 `SMOKE_TASK_SENT`。第一次只改 server 參數而未修 model resolver 時回 502；在暫時複本修正 Claude `--effort` 對應後才成功，故正式 shim 仍需相同相容性修正。這只證明現在的 **AGY Opus 4.6 備援**在隔離環境可通，沒有對 Opus 5.5 發 live request。所有 smoke 都是 fake task/BAT，不是真 BAT、正式 daemon、重啟恢復、provider switch 或生產部署證據；live Goose gate 仍關閉。

每個 task 保存 `submitted_at`、`delivered_at`、`delivered`、`review_rejections`、`ted_interventions`、`session_replacements`；可計算交付／未交付、review 駁回次數、消失 session 的替代次數及交付秒數。目前 `ted_interventions` 是**呼叫者聲稱 Ted 介入**的次數，來源 ID 去重，但尚未綁定受信 Discord 事件，不能作已驗證的 Ted 實際介入數。事件帶時間戳供稽核，不能把 coding agent 的自述當成 delivered。

### 本 PR 的啟動與限制

`batc serve --host 127.0.0.1 --port 18796` 僅在明確啟動時運行；需要主機 `writes=true`、`orchestrate=true`。既有 `bat-agent-connector-mcp` 新增五個 work 工具，透過 `BATC_TASK_URL`（預設 `http://127.0.0.1:18796/rpc`）連同機 daemon；它本身不擁有第二份帳本。服務尚未部署。Rules 可建立 lead、續推、停派、從不明 BAT 回應對帳、執行**管理員預先設定**的測試命令並將觀察結果連同 commit/tree 寫入 PR #1 驗證紀錄，再啟獨立 reviewer。未設定受信測試命令時停在 verifying。Goose ACP adapter 和 task-scoped MCP 有 fake BAT 與上述隔離 live smoke 證據；goose 選項仍屬 smoke／試驗用途。Discord adapter 可用 fake 測；正式憑證和看板 channel 尚未配置。未關閉既有 Hermes cron，也未修改 BAT／Hermes 設定。

`host-a` 的 OpenClaw 應透過到 `control-host` loopback 服務的受控轉接（例如 SSH socket forwarding）呼叫同一 task MCP，不在 `host-a` 啟第二個 daemon 或 SQLite。HTTP 維持 loopback；不直接向 LAN 開放 BAT token 或 task 控制端點。

### Shadow send 與 verification 卡住的修正界線

Shadow task `11a41bf2` 暴露 send 已在 BAT 接受／完成，但 transport 回覆遺失使 connector 誤標 `uncertain`。新 send intent 除 prompt SHA-256 外，也保存送出前最後一筆 BAT message ID，或空 session 證據。回覆不明時，服務只在**同一 session** 唯讀查最多 100 筆、最多兩次且總共五秒；須見到 fence 之後**恰一筆**完整 user prompt，其 SHA-256 等於 journal 命令，且有 BAT user message ID，才標 `accepted` 並記 `send_reconciled_delivered`。這只證明 prompt 送達，不代表測試、review 或 task 完成。缺 fence、訊息被分頁排除、文字不符、只有後來不相關的 `REVIEW: PASS` 都保持 `uncertain`；從不重送。重啟後對有新 fence 的 command 可做同樣唯讀對帳；舊 command 缺 fence 則仍須人工處理。

Shadow task `d87868ac` 停在 `verifying` 超過八分鐘，顯示先前只有測試 subprocess 的逾時計時，BAT／SSH lookup、候選檢查、review 等整個 worker tick 和連續多次無進展 tick 都沒有截止。現在 `verifying` 自最近一次 task 狀態更新起有明確截止時間：預設最多 300 秒，若私有驗證設定的 `timeout_s` 更短則使用較短值；pause 不耗費計時，resume 重設時間。單次 verifying tick 也受剩餘時間約束；超時記 `verification_timeout` 或 `verification_deadline`，其他例外記 `verification_error`，只寫例外**類型**而不寫可能含私密資訊的錯誤全文，轉 `needs_ted`。不自動重跑測試、不重送 prompt，也不跳過 commit/tree 或 reviewer 證據門檻。Discord flush 另有十秒上限，避免卡住 worker 排程。此工作樹無法解析 `control-host` 的 SSH 名稱，未取得該兩項 real shadow task 的遠端 journal；根因依 connector 的可重現控制流程和 fake/MockBAT 測試界定，既有 shadow daemon/task 未被碰觸。

同一 exact read-back 也用於 BAT 回 `accepted`、但 Codex 只附 `timestamp_cursor` 的情況；這正是 real shadow 初次 send 走到的分支。只有找到 fence 後逐字相同的 user turn 才把該 ACK 升為可歸因的 `accepted`，否則仍為 `uncertain`。單靠 ACK、時間戳或後續 assistant/review 文字都不算證明。

## 第二階段：計畫，尚未交付

1. `control-host` 已安裝並 pin Goose v1.52.0；接著須驗證 stock ACP resume、持久恢復、provider 選擇與正式 agy shim Claude 相容性。用相同真實任務比較 rules、Goose、Hermes 的完成品質、續推次數、額度、人工介入與恢復時間，再決定預設引擎。
2. 第一階段已有預設 OFF 的 service-only GUI tab 註冊開關；第二階段在 `control-host` 小範圍開啟、跑 revision recheck／GUI 競態測試。`workspace:save` 是整份覆寫，與 GUI 同時存檔仍可能互蓋；Ted 已接受文件化風險，但無 BAT host-side 原子 append 就不能保證沒有 race。
3. 配正式 Discord token／thread／看板 channel、持久化 message id、部署 service unit、備份 SQLite、健康檢查與重啟 runbook。確認對帳後停用 Hermes 的 `bat-watch-*`、idle keep-pushing；實測 `host-a` 的 OpenClaw 轉接。沒有在本 PR 啟動服務或更動 Hermes／BAT。

參考：[研究 Part 1／2](../research/2026-09-27-review.md)、[本輪全庫審查與 Opus smoke](../research/2026-09-28-whole-repo-review.md)、[先前評估](no-bat-change-evaluation.md)、[下一代設計](next-gen-connector.md)。`chatgpt-full-discussion.md` 僅研究使用，不能提交。

## 可恢復的狀態機與帳本

單一 task ID 永不更換。`branches` 表另記每次 BAT lead／reviewer session 與 PM provider 選擇，包含 `branch_id`、`session_id`、provider、角色、上游 branch ID、原因、時間；`work_status` 回傳完整 branch 歷史。這裡的 branch 是任務執行分支，與 Git branch 名稱不同。`tasks` 保存原話、工作空間、recipe、狀態、pause/control_version、lead/reviewer session、turn marker、commit/tree、review marker、提交／交付時間與指標。`commands` 有唯一 idempotency key、預留 session ID、BAT message ID、kind、送出前游標和狀態。`events`、`routing`、`provider_usage`、`observed_verifications`、`capabilities`、`ted_actions` 與 owner lease 各自保存可稽核資料。所有網路呼叫前先提交命令意圖；同一 key 不會生第二條命令。

### 2026-09-27 22:51:52 至 22:51:58 ET shadow task 診斷及恢復界線

Task `9a8c8579-b0cc-4e0b-aa69-71d79eabfe0e` 的 BAT start 回 `aec7b468-deb2-4166-b662-3d8f79529e66`，audit 中 `worktree:create` 成功、branch `bat/worktree-e5ed1603`，`claude:start-session` 回成功，但初次送 prompt 被拒，進入 `needs_ted`。唯讀檢查 `host-a` 的 BAT 現況時，**同一 session ID 的** `claude:get-session-meta` 與 `claude:get-session-state` 都存在、`numTurns=0`；`worktree:status` 有該 branch/path，工作樹目錄仍在；BAT user service 自 19:00:37 ET 運作，沒有 22:51 重啟證據。GUI workspace terminals 沒有這個 headless session，符合 tab registration OFF。`host-a` 本機 connector registry 也沒有它，所以 `service._resolve_session` 對同 ID 回「session not found」。BAT 的舊 sidecar log 和該時段 user journal 沒有足夠事件細節；`control-host` daemon 的當時 registry/log 未能唯讀取得，故**不能證明** `control-host` 端當次拒絕的唯一原因或宣稱 BAT GC 刪了 session。可確認的是 connector 查找設計存在 registry/GUI 可見性裂縫；BAT meta 本身證明 session ID 沒錯，worktree 並未消失。

修正後，每次初始 lead **和 reviewer** prompt 前，以該 task 的 durable branch／start intent、BAT 精確 session ID metadata、workspace/worktree path 和唯讀 Git root 核對；既有 registry row 也要比對，不再因 row 存在就略過驗證。**Lead 的 `worktree:status` 必須明確回 path 和 branch，且與 registry／Git root 相符；即使 session metadata 有值、舊 registry 有 path/branch、磁碟 Git root 存在，BAT worktree status 為 null 仍屬未知，不能送初始 prompt。** Headless reviewer 的**自身** BAT `worktree:status` 常為 null，因 reviewer 沿用 lead worktree；此時 lead 的 BAT worktree status 仍須明確回 path/branch，並與 journal 的 lead session、reviewer metadata `cwd` 精確相等，才能恢復 reviewer lookup。BAT lead/reviewer start 回覆都必須含與預留 ID 相同的 `sessionId`，缺失或不同都不能視為成功。若 BAT session 存在但本地 registry 遺失，就以受驗證資料補回 headless lookup，**不新建 BAT session**。

**null 不是消失證據。** BAT protocol 說 `claude:get-session-meta` 可在重啟後、session 尚未 resume 時回 null；`worktree:status` 也可在 host 記憶狀態消失但磁碟 worktree 仍在時回 null。三次 meta 都為 null 時，BAT adapter 只回 `uncertain`，不標 `vanished`、不釋放原 registry 名額、不建替代分支；就算 worktree status 也為 null，結論仍然相同。若尚未建立 send intent，下一 worker tick 可重新驗證身分；若已建立 intent，仍須按命令對帳，不能重播。現有 `session_replacements`／最多一次 branch 機制只供日後有**明確、強於 null 的 host absence proof** 的 adapter 使用；真 BAT 目前沒有這種證據，故自動替代保持停用。原 shadow 送出拒絕的精確原因仍未證明。無 GUI tab 不代表 BAT session 消失。

Pause 在任何等待的 presence lookup 後重查；`service.session_send` 的 session/meta/state 等待結束後、BAT send invoke 前，以及 BAT client 建連後送出 WebSocket frame 前，再以 journal task control version、pause、session ID、command ID/status 和 prompt hash 作同步檢查。已寫但確定尚未送 BAT frame 的 intent 標 `cancelled`，resume 用新 control version 建新的 send command。對已送 frame 的不明回覆仍維持 `uncertain`，不能因 pause／resume 自動重送。這些檢查在 task/session writer lock 內執行；pause 可以先持久化控制版本，晚於 frame 送出時則屬已開始的回合。

| 原狀態 | 可自動進入 | 條件 |
| --- | --- | --- |
| `queued` | `dispatching` | 預留 lead session ID、寫 start intent 後啟動 |
| `dispatching` | `accepted`／`verifying`／`uncertain` | BAT start 明確成功／reviewer start 成功／回覆不明 |
| `accepted` | `running`／`uncertain`／`queued`／`needs_ted` | 已先記 `needs_review` 送出標記；BAT 回覆可歸因／不明；`queued` 替代只供日後有明確 host absence proof 的 adapter，BAT null 訊號不能啟用 |
| `running` | `accepted`／`verifying`／`waiting_permission`／`quota_limited`／`needs_ted` | 回合結束續推／里程碑／權限／額度／人為阻塞 |
| `quota_limited` | `uncertain`／`needs_ted` | Claude→Codex 原子預留 successor 與獨立 handoff send；Codex 送出後等命令證據或人工對帳 |
| `verifying` | `done`／`accepted`／`needs_ted` | 乾淨候選 commit/tree 的觀察測試與 fresh reviewer PASS／REJECT／測試失敗 |
| `uncertain` | `accepted`／`running`／`verifying`／`human_owned`／`done`／`needs_ted` | 可歸因的 BAT 證據或有權操作者針對特定命令明確處理；絕不自動重送 |

`pause` 先持久化控制版本，停止新派送；可選擇 interrupt 當前 turn。start 等待期間發生 pause 時，已接受的 session 保存為 `accepted` 但不送初始 prompt。若 pause 在 send 前的 presence lookup 期間發生，服務在 BAT send 呼叫前再次讀 pause，取消尚未送出的命令。`resume` 清除 pause，下一 tick 先查 pending 命令；若無待對帳且 session 尚未收到 prompt，才以新的 control version 送第一次 prompt。每個 host/session 在單 daemon 內有 writer lock；程序間以 0600 lock file 的排他 `flock` 與 owner heartbeat 限制為一個 daemon。外部 BAT GUI 不受此鎖控制；connector 舊低階工具也先走 task gate。遇無法歸因的 turn 仍保留 uncertain。

送 prompt 前先持久記 `needs_review`，包含 message ID、prompt SHA-256 與送出前游標；即使 crash 發生在實際送出前，也按**可能已送出**處理。逾時、斷線或回覆遺失後保持 `uncertain`。Claude `session_read` 的 `correlated`／`correlated_after_prior_turn` 可用於對帳；Codex 的 `timestamp_cursor` **只是時間位置，不能證明回覆屬於本命令**，連同後來出現的 `REVIEW: PASS` 都不能用來結案或自動重送。Codex 只有明確的命令／turn 綁定證據才可自動歸因，否則走下述人工對帳。Reviewer PASS 同時要求獨立 reviewer prompt／turn 歸因、lead 已停筆、乾淨的當前 commit/tree 和受信測試 exit 0。BAT 明確回 busy/rejected 時標 rejected、請 Ted 處理，不假設可安全重送。start 對帳使用預留 session ID 和 BAT meta；lead／reviewer／failover successor start 的 ack 都須回精確預留 session ID。相同 worktree 的 failover 另比對 host worktree path/branch、Git branch 與 registry branch，任何變動都 fail closed。failover 的 registry＋BAT meta **只證實 successor session 存在**，handoff `batc-*` ID、registry `sent` 和後來不相關的回覆都不能證明 prompt 所屬 turn。handoff `send` 維持 uncertain，可用獨立一次性命令 capability 人工對帳；確認 session 閒置後才可送文字不同的新 prompt。遇 candidate commit 或 tree 改變，清除舊 verification/reviewer/PASS，建立新 reviewer session。

Failover 預設把 task ledger 摘要交給 successor：Ted **完整逐字**原話、狀態、候選 commit、近期命令／事件，避免以可能極長或過時的聊天全文作權威。原話可在 handoff 內完整容納時直接寫入，**不再截到 2,200 字**。超過 3,000 字就先把完整原話寫入 0700 私有目錄中的 0600 archive，以 SHA-256 驗證，再由明確配置的 `BATC_TASK_ARCHIVE_VERIFY_SSH_HOST` 以 BAT successor 身分執行唯讀 hash 檢查；`BATC_TASK_LOCAL_HOST_ALIAS` 必須等於 task host。handoff 僅送 archive 路徑、字數、hash 與先讀原話的指示，不能稱縮寫摘要會覆蓋 Ted scope；實際 BAT handoff prompt 在送出前再次檢查路徑／hash 或完整內文仍在。archive 無法被 successor 驗證時 fail closed，不送 prompt。提交原話上限 19,000 字，超過時明確拒絕，避免初始 BAT prompt 靜默截斷；18,000 至 19,000 字的 failover 一律用完整 archive。若 ledger 摘要失敗，且本機路徑共享條件成立，服務才讀 BAT history 並建立同機 0600 archive／excerpt，**同時保留上述權威原話或原話 archive**；遠端無法共享路徑時 failover 保持 uncertain。超過 200,000 字時 excerpt 保留前 12,000＋後 148,000 字並標明中段省略。archive 絕不能放進 Git。

Failover 恢復只接受帳本預留的**同一個 successor session ID**。`failover` intent 要指向同 task 的獨立 handoff `send` command；兩者的 session ID、原 lead ID、handoff message ID／command ID 必須與 registry 完全相同。BAT 必須明確回 successor metadata 的工作目錄、舊 lead 與 successor 各自的 `worktree:status` path／branch、以及唯讀 Git root，並與原 lead registry worktree 一致。null 是未知；實際值不同或先前 successor 搶占是衝突，持久記為 `operator_only`，重啟後也不自動採用。衝突時不改 command session、task session 或 branch 歷史，不重送 handoff；管理員可用 task／command-scoped `work_reconcile` 記錄證據並交人工接管，但不能憑它把未驗證的 successor 自動變成新 lead。低階 failover 遇已存在的 successor，也必須與 caller 預留 ID、handoff message／command ID 一致。Reviewer 借用 lead worktree，只是讀取者，不擁有自動 cleanup／merge 權限。

Failover handoff 在舊 Claude 狀態查詢、新 Codex session start、BAT 連線等等待之間可能遇到 pause。服務在 handoff intent／prompt hash 已入帳後，送出前重查 task `paused`、`control_version`、原 lead／預留 successor 與 handoff command；BAT client 在真正寫入 `claude:send-message` frame 前再做一次相同檢查。若 pause 已提交，handoff `send` 留在 uncertain、failover 標 `operator_only`，恢復派工也不會重送，須由有權操作者對帳。

BAT 確認預留 successor start ID 後，**handoff 送出前**先查 successor metadata `cwd`、舊／新 session 的 worktree path／branch、Git root，與 task 舊 lead registry、預留 ID 和 handoff command 綁定；任何具體不符都不送 handoff，轉 `operator_only`。BAT client 在提交實際 handoff frame 前計算該 frame 的 prompt SHA-256，與 journal intent **逐字 hash 相等**才寫入 frame，並將該 frame hash 記入私有 registry。正常回覆與重啟恢復都要求 registry frame hash 等於 journal prompt hash；只有 64 位 hash 的外形並不足夠。null host 身分仍是 uncertain，不用猜測或重送。

Task lead 的 `task_id` 在 `session_start` 的 registry 預留交易當下寫入，早於 worktree 建立和 BAT start。即使 BAT start 已完成而 task 在初次 prompt 前被 pause，舊 `session_cleanup`／`main_session` 也必須排除它。外部 task worktree 到 `done`／`failed` 時，只在乾淨、HEAD 與 branch 相等，且 `done` 的 HEAD 等於已驗證 commit 時移除工作樹。移除前建立 `refs/batc/tasks/<task-id-prefix>` 指向完整 commit，保留原 branch；**不執行 force remove 或 branch -D**。journal 只有收到路徑、branch、保留 ref、commit 的明確證據才清除工作樹指標並記事件。Git 移除後若程序中斷，重啟依仍在的兩個 ref 對帳；失敗則保留指標並退避重試，不以忽略錯誤當作清理成功。

Successor 身分在 handoff 前查過後，BAT 連線等待仍可能改變 registry 或 host 狀態；所以連線後再查一次 successor `cwd`、舊／新 worktree path／branch 和 Git root。實際 frame 邊界以同一個 registry 檔鎖原子比對 task ID、預留 successor ID、`failover_of` 原 lead、共享 worktree、path／branch、handoff command／message ID 與 pending 狀態，並寫入實際 frame hash；在送 frame 前再檢查 pause／control version。若 owner link、Git root 或其他具體身分在兩次查詢間變動，零 handoff frame，命令維持 uncertain／operator-only。這是 connector 自身送出界線；BAT 外部行為仍須獨立實機驗證。

BAT client 的最後一輪 host 身分查詢現在在**取得送出 semaphore 之後**執行；這三種查詢只允許 `claude:get-session-meta`、`worktree:status`、`git:getRoot`，直接使用已連線的唯讀 roundtrip，不再次取得同一 semaphore。查詢完成後同步執行 task pause／control-version、journal prompt hash 與 registry 原子 owner/link 檢查，緊接著提交 handoff frame；等待 semaphore 期間改變 Git root、worktree branch 或 `failover_of` 都必須是零 handoff frame 並留下 uncertain／operator-only。這仍不是 BAT 提供的跨系統原子交易；外部直接修改 BAT session 的競爭需真機契約測試界定。

## 權限、設定與操作恢復

HTTP 僅聽 loopback 並檢查 peer。一般 work RPC 需本機 0600 admin bearer token；Goose 只取得 1 小時的 task-scoped capability，不能呼叫 `work_submit`、操作另一 task 或直接提供測試 exit code。對不明一般 send 或 failover handoff send，管理員用 `work_reconcile_capability` 為**一個 task／command** 發 10 分鐘一次性 capability，再用該 token 呼叫 `work_reconcile`，提供 `delivered`／`not_delivered`／`superseded`、操作者、來源和證據。admin token 本身不能直接解決命令。`batc task-reconcile` 在本機完成這兩步；若要接續，必須提交**不同文字**的新 prompt，先記新 intent，並確認 BAT session 閒置；新 prompt 不重播舊命令。人工聲稱 review PASS 還要提供當前 commit/tree、exact turn reference，服務重查乾淨候選、reviewer 已停筆及當前觀察測試。無證據的 resolve 留在 `human_owned`，`work_resume` 不會偷偷續推。這是有權操作者的可稽核證詞，並非 BAT 自動證明。狀態目錄 0700；SQLite、token、lock、私有 handoff archive 0600。不要將 token、shim 金鑰、原始聊天或 provider 錯誤全文寫入日誌。`host-a` 的 OpenClaw 需透過受控 SSH loopback forward 加 admin bearer 呼叫同一 `control-host` daemon；若要允許 `host-a` 寫入，應配置限定權限的轉接身分，不能把 loopback HTTP 直接開到 LAN。此轉接與主機授權尚未部署。

私有 `BATC_TASK_SETTINGS` TOML 必須 0600，例如 `[verification.commands]` 的 `project = ["uv", "run", "pytest", "-q"]`；remote host 可用 `[verification.ssh_hosts]` 指定既有 SSH alias。測試 stdout/stderr 只存本機 `task-artifacts` 的 0600 檔案（至多保留前 2 MB，另存完整輸出 SHA-256）；可在 `[verification]` 設 `artifact_dir` 到私有路徑。`[task_service] register_tabs = true` 是額外的 service-only 顯式開關，預設 false；主機既有 `orchestrate_register_tabs=true` 也必須同時成立。lead 和 reviewer tab 都用 connector 的 append/revision recheck；不改 BAT。Ted 很少開 GUI，仍需知道 `workspace:save` 整份覆寫的 race。

（已移除）舊的 `BATC-EVENT`／`BATC-BOARD` 發文、`batc task-delivery` 與 `work_delivery_*` 對帳流程已刪除；聊天投遞由擁有 Discord 的 Hermes 依 `work_events` 游標負責。

若 failover 身分有明確衝突，管理員也可對 `failover` command 取得一次性 capability 並對帳；此動作同時結清它綁定的 handoff command、留下 actor／source／evidence，task 進入 `human_owned`，**不**把未知 successor 變成 lead，也不能在同一次對帳送新 prompt。若 handoff command 本身的帳本綁定已損壞，必須先由管理員修復帳本，服務拒絕自動採用或猜測。

## PM provider 設定與限額

私有 `BATC_PM_PROVIDER_CONFIG` TOML (0600) 有多個 `[[providers]]`：`id`、`kind`（`agy-shim`、`openai-compatible`、`codex-acp`、`claude-acp`、`gemini`）、`base_url`、`model`、`daily_cap`；預設頂層 `fallback_order = ["claude", "agy-claude", "codex"]`。`claude` entry 為 `kind = "claude-acp"`、`model = "claude-opus-5-5"`；`agy-claude` 為 `kind = "agy-shim"`、`model = "claude-opus-4-6-thinking"`。前者在 Goose 子程序用 `GOOSE_PROVIDER=claude-acp`、`GOOSE_MODEL=claude-opus-5-5`；後者用 `GOOSE_PROVIDER=openai`、`GOOSE_MODEL=claude-opus-4-6-thinking`、`OPENAI_BASE_URL` 與從環境讀取的 `BATC_AGY_SHIM_TOKEN`。Anthropic [官方模型文件](https://platform.claude.com/docs/en/models/opus-5-5/overview) 確認 5.5 的完整 ID；[Goose v1.52.0 Claude ACP source](https://github.com/aaif-goose/goose/blob/v1.52.0/crates/goose/src/providers/claude_acp.rs) 使用 provider 名 `claude-acp` 並轉送 session model config option。這是程式與 fake ACP 契約證據，**尚未在已安裝 Goose／Claude ACP 驗證 5.5 可用性或實際消耗 Claude 額度**；live gate 仍關閉。`base_url` 僅允許無 credential 的 loopback HTTP；不能提交設定或使用付費 API key。每 task 可給 `pm_provider`，recipe 可給預設；未給則首選 Claude ACP。新 provider 只需一個小 adapter class、設定 entry 及自己的 fake endpoint／ACP contract test。設定日上限按 UTC 日計成功使用次數；`quota_error`、`rate_limited`、`auth_error` 只能在**確認未送 prompt**時切換至下一 provider，寫 `provider_usage` 與新的 task PM branch。已送、`needs_review` 或 uncertain prompt 必須先對帳，禁止切換時重播同一內容。錯誤以結構化 HTTP status/code 分類，不以可能含敏感內容的錯誤字串猜測。

`agy-claude` 的唯一允許 model 是 `claude-opus-4-6-thinking`；預設 `claude` 只允許 `claude-opus-5-5`，所以不能因省略 model 意外用到 Sonnet。`[router]` 可設定（舊 `confidence_threshold` 仍接受但不使用）`agy_claude_daily_cap`（預設每日 10 次已記成功使用）、`status_provider`（`agy-gemini-flash`）、`scarce_provider`（`claude`）、`secondary_provider`（`agy-claude`）、`fallback_provider`（`codex`）、`allow_gemini_status`（true）；沒有 Gemini endpoint/model 時不會選它。Task 明確指定 provider 優先於 recipe，recipe 優先於 router，所有 override 以原因記錄。ModelRouter 的使用量與 provider 錯誤來自本服務帳本；只做路由決策的 rules 步驟不算 API 使用。受信驗證命令 argv 可能含私有值，因此 journal 僅保存 argv SHA-256，不複製原始參數；受信私有設定與 0600 artifact log 可供管理員核對。

Jev 共用客戶端先用 TypeSafe `/v1/systemone`；主端逾時、錯誤或回傳不符合 typed `choice`／`noul` 機率契約時，以環境變數 `OPENROUTER_API_KEY` 呼叫固定 `https://openrouter.ai/api/alpha/decisions`、固定 model `typesafe/jev-1.13`（[OpenRouter Decisions 模型頁](https://openrouter.ai/typesafe/jev-1.13)）；送出的 JSON 只包含 `model`、`state`、`questions`，回應須有通過同一 typed validator 的 `answers`。沒有 key 就跳過；兩端都失敗時沿用原確定性路徑：minimal 引擎選 rules、候選審查轉完整 reviewer、triage 保留 pattern、cleanup 不因 Jev 缺席而 merge。不使用 chat completions、一般大模型或未經 Decisions 契約驗證的 alias 作備援。任何 key 只讀環境、不寫 TOML／journal／log。引擎選擇與 minimal 候選審查記錄回答者 `typesafe`／`openrouter_jev`，未回答則 null。模型呼叫已用 fake transport 測試；本 `host-a` 工作樹沒有 OpenRouter key，executor box 的真端點 smoke 由 Ted 另行執行，不能把它算作本機通過。PM 步驟 provider 以明確規則選擇（見上），不呼叫 Jev。規則引擎仍是 deterministic，routing 記錄的 provider 就是實際啟動的 BAT agent；Goose live gate 仍關閉。額度 cap 是服務的保守計數，不代表第三方真實剩餘額度。OpenAI 相容 adapter 的探針要求 `/v1/models` 含**確切**設定 model ID；ACP/provider 的完整驗證仍需 pinned Goose contract test。真 provider 執行、成本與品質 A/B 屬 M2。

## Pinned Goose 啟用門檻（M2 contract-test checklist）

此清單取自 Ted 提供的 `/workspace/goose-acp-handoff/docs/UPGRADES.md` 概念文字；本環境沒有該 clone，未複製其 Node/MIT 程式碼。目前 pin **Goose v1.52.0**；`goose --version` 必須符合此版，archive checksum 依上文核對。Goose 與 connector 分開 pin 版本，不改簽署的 Goose bundle；私有 integration config 與 handoff state 先備份，不能提交。每次升版在**隔離 synthetic session** 完成下列檢查後才可能開 live Goose：

1. 跑 connector repo tests／syntax，對安裝的 Goose 驗證 `initialize`、`load/new`、`configOptions`、`session/set_config_option` 的真實 schema 與回覆。
2. 檢查 host UI 真的顯示 handoff 與 target-model 選擇；target setup 必須驗證回覆的 provider choice 與 approval-mode setup。wrapper 對 protocol version 非 1 必須拒絕。這些檢查仍非完整相容性保證，未知 protocol/UI 變更可能破壞流程。
3. 切換 provider、記 synthetic marker、reload 後確認 history 與 identity；強制 provider 失敗，確認原 session／內容保留。工具 approval 要保留為 approval，不能自動變成 granted permission。
4. 失敗時保持 handoff 停用，保留舊 session／私有 state，把 adapter/config 回退至 last known good。略過 wrapper 只會回原 agent，不會合併 target branch messages。
5. 替換 relay 之前要讓 in-flight prompt 結束或明確取消，不能為安裝功能殺掉 active writer。

目前 ACP adapter 的 fake smoke 使用 protocol 1，遇非 1 或沒有 session ID 即拒絕；上述 `load/new`、`configOptions`、`session/set_config_option`、真 provider choice／approval UI、故障保留、rollback 及 active-writer 項目尚**不是可執行 gate**。此外還要證明 task-scoped MCP capability、subprocess env/process 隔離、ACP session 在 daemon 重啟後可恢復、provider auth/quota 分類、no-resend 及 pinned 版本在 `control-host` 的實機行為。現有 BAT adapter contract tests 使用 mock host，涵蓋 start／recover／Codex send／reviewer 唯讀；真 BAT timeout、busy、failover、reload 和 tab revision race 仍未實機驗證。**live Goose 保持停用，也不得進入真實 shadow trial。**獨立 reviewer 對本 PR 的 P1/P2 修正重新 sign-off 後，才討論 smoke 範圍及後續實機 gate；本 PR 不部署。

## Release boundary（2026-09-29 hardening）

Reviewer 只以**最後一則 agent 訊息**中的 JSON verdict 決定：`{"verdict":"pass|reject","candidate_commit","tree_hash","findings":[]}`。缺少、格式無效、同一訊息內互相矛盾（含舊式 `REVIEW: PASS`／`REVIEW: REJECT` 文字與 JSON 不一致）、commit/tree 與 review candidate 不符、訊息被讀取截斷、或 PASS 但含 high／critical finding（含 PR #8 的未標記 `High:` 行），一律視為 reject，走有上限的 rework（`review_verdict_rejected` 事件記原因），超過 recipe 上限才 `needs_ted`。Lead 的 `BAT-STATUS` 也只取最後一則 agent 訊息的最後一個 marker；前面引用的 marker 不會推動狀態。Task adapter 讀取時每則訊息上限提高到 20k 字，避免尾端 marker 被預設 2k 截斷。

直接 send／answer／interrupt／permissions 的共用 gate 讀既有 owner 的 `task-service.json` 與 journal，然後轉交**同一個** coordinator。pointer／DB／row／lease 不可用時 `TASK_OWNER_UNAVAILABLE`，registry／task／預留 start／branch ownership 不一致時拒絕，不能降級為 standalone。`paused`、`verifying`、未對帳命令與不允許的 task state 都阻擋低階操作；queue／force／approve-pending／deferred raise／relay 不會插隊。send、client-resume、answer、interrupt、兩個 Codex permission channels 都在 frame 前重查 control_version。只有原 journal command 綁定的內部 send／受信 verification，以及該 pause 版本的 abort，能使用 coordinator 內部權限。

## Verification lifecycle（2026-09-29 hardening）

受信測試的啟動、輸出讀取與程序結束共用**一個 deadline**。命令在自己的 session／process group 執行；逾時或取消時整個 group 被 SIGKILL，確認沒有非 zombie 成員才算結束。SSH 主機上以 `setsid -w` 執行並把 pgid 寫入遠端 `$HOME/.batc-verify-<marker>.pid`；逾時先殺本地 ssh，再以另一條 ssh 對該 pgid `pkill -KILL -g` 並輪詢直到空，輸出 `gone` 才算確認。無法確認即 `VerificationProcessStuck`，task 進 `needs_ted`（fail closed）。超過 2MB 的輸出保留開頭與真正的結尾。

驗證期有兩個時鐘：`progress_at`（候選 commit/tree 變動、lead 或 reviewer 仍在 streaming、測試結果寫入）延長等待，上限為 recipe 的閒置預算（900/1800/3600 秒）；`verifying_started_at` 從進入新一輪 verifying 起算，絕對上限為閒置預算的三倍。Reviewer 啟動（經 dispatching）與 uncertain 回復不會重置；`updated_at` 心跳不再延長驗證。Ted resume 會重置兩個時鐘。

受信測試失敗不再直接 `needs_ted`（stuck handler）：以 log 尾端做決定性分類。缺依賴時，每個候選 commit 只跑一次 repo 追蹤中的 lockfile 安裝（pnpm／yarn／npm ci／uv sync／cargo fetch），工作樹須保持乾淨，再重測；安裝後仍缺即視為程式問題。程式／測試失敗時把遮蔽後的輸出尾端（≤2500 字）送回 lead 做有上限的 rework（`verification_failures`；small 1 次、其他 2 次），再驗證新 commit；超過上限才 `needs_ted`。逾時、權限、登入、網路、磁碟等環境問題直接 `needs_ted`。



## Operations 與唯一 owner（2026-10-08，Part A）

[統一操作規格](operations-unification.md) Part A 已把 task.submit／pause／resume／mark_stage、task_send（session.send 的 task target）、task.verify、task.request_ted、task.command.reconcile 包成 OperationService actions。HTTP、原 MCP／RPC 和 CLI task-reconcile 共用原 Journal／TaskCoordinator；原結果增加 operation_id／operation_status。新增 scope 對照與拒絕碼見 [api-v1.md](api-v1.md)。有 key 時依驗證 actor 去重；無 key 的舊 controls 每次是獨立要求。Goose step_id 仍可重試。一般 session runtime actions 即使走 legacy service，也先提交原 task command，未知結果不重送。

`OpContext.effect` 以同一 journal transaction 保存原 task effect 與 operation_steps receipt。restart 讀到 receipt 就重用結果；只剩 started 意圖表示 effect transaction 沒提交，可安全重做本機 journal method。pause 的 local effect（含 Ted action 去重）先提交，abort_current 為獨立 intent／readback step，resume 後舊版本的 abort 無法送出。reconcile 的一次性 capability 消耗、原 command resolution、新 next_prompt command 與 receipt 同交易提交；跟進 prompt 仍走原 _send，未知結果只回查。

task send 在等待 session lock／派送準備時被 pause 擋住，operation／refusal step 為 failed、code 為 `TASK_PAUSED`，不是成功或 uncertain；command／frame 尚未建立時也不改 pause 的 task snapshot。成功必須有該 operation 的 send command 回執與 accepted／settled 狀態；其他提早回傳明確拒絕。相同 key 重讀拒絕，resume 後新的派送使用新 key。

owner lock 固定在 registry/state directory 的 `task-daemon.lock`，不同 --db 仍爭同一把 flock。TaskDaemon 在取得 owner 後才初始化 Journal、0600 admin token、providers、listener 與 worker。第二個 daemon 回 OWNER_CONFLICT 與既有 pointer metadata，不修改候選 journal／token／pointer。heartbeat 是觀測，不能用過期時間奪取 live lock；OS 釋放後才可重啟並沿用 journal。升級需先停舊版（舊版鎖在 DB 父目錄），不得混跑。

Part A 沒有 schema migration、業務資料搬移或歷史 operations 回填。僅 local-admin work_submit 相容入口可按原 payload hash 連到既有 task；其 bridge receipt 與 operation intent 同交易提交，crash 不會造成重啟錯建 task。新提交使用 operation identity 作 task key，其他 actor 不認領歷史 key。

## 尚未涵蓋

Part B 尚未涵蓋其餘 legacy tools 的 operations、no-key sentinel／null 結果投影、外部 step 拆分及全入口 A01/A05/A08；live BAT／Goose gate 保持原限制。BAT GUI 的外部派送與沒有明確 turn 證據的 Codex 回覆仍不能由 connector 保證歸因。
