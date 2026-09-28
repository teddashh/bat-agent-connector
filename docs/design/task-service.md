# 任務服務：第一階段實作與第二階段計畫

日期：2026-09-27。依照 Ted 核准的架構；BAT 原始碼與既有低階 MCP／`batc` 介面不變。

## 現在要解決的事

Ted 只對 Discord 裡的 Hermes 說話。Hermes 只能逐字保存原話、交辦一次、回報結果；絕不能改寫、解讀或拆解要求。若舊呼叫者仍傳 `interpretation`，此欄僅保存為**非權威的外部附註**，不放進 coding prompt。規劃與拆解交給熟悉 repo 的 Codex／Claude lead session，遵守 `relay.py` 原話優先的界線。Hermes 不應在 `session_wait` 裡等 60／90／120 秒。新訊息曾打斷等待，造成找不到 session、重啟被 active wait 擋住、castle1 metadata／handshake timeout，以及 stale reply guard 擋回覆。現在 `orchestrate_register_tabs=false`，自動 session 在遠端 BAT GUI 看不到。任務服務必須自己保存任務和進度，不以 GUI 或 Hermes 記憶當帳本。

## 第一階段：可執行範圍

`batc serve` 是單一長期程序。它擁有 SQLite WAL 任務、命令及事件帳本，提供 loopback HTTP 給本機 MCP 客戶端與 castle1 OpenClaw 的受控轉接。Hermes 的 `work_submit` 只寫帳本並立即回 `task_id`；`work_status`、`work_pause`、`work_resume`、`work_result` 讀／改同一帳本。提交逐字保存 Ted 原話、Discord thread、recipe、驗收條件及 idempotency key；可選的 interpretation 是非權威記錄，不進 prompt。重複 key 回原 task；同 key 不同內容拒絕。預設 rules 引擎。`goose` 是明確 opt-in。

服務每次先記命令 intent，再呼叫 BAT。單一 task 的同一 host/session 只有一個 writer；控制版本與 pause 在送出前重查。送出逾時後標 `uncertain`，**絕不重送同一命令**。Claude→Codex failover 也分成原子預留 successor 與獨立 `send` 命令：handoff prompt 送出前已有 task／command ID、`needs_review` marker 和完整 prompt hash。BAT 接受不等於 Codex 回合歸因；重啟後若只能證實 successor 存在，仍把 handoff send 留在 uncertain。BAT Codex 沒有可靠的 host-side command receipt，無法承諾 exactly once；GUI 或舊低階工具也不受服務鎖約束。新自動化入口須用 task 工具。

Rules 引擎在回合確定完成、尚未達驗收、沒有 blocker／額度／人工接管且未達 recipe 續推上限時，派一次短 `continue`；模糊語意才請 Jev 分類。狀態包括 queued、dispatching、accepted、running、waiting_permission、quota_limited、human_owned、needs_ted、verifying、done、failed、uncertain。Pause 停止新派送，可選擇 abort 當前回合或讓其結束；resume 先對帳再續推。額度 failover 呼叫 PR #1 的原子 successor reservation 路徑，記下新舊 session。開發者自稱完成、測試通過後，starter recipe 預設開**另一個** reviewer session：Claude 額度可用時用 Claude，否則用全新 Codex。Reviewer 依驗收條件回報；拒絕時送回開發者並計數，達 retry cap 即請 Ted 處理。通過後才以 PR #1 的 commit 綁定驗證紀錄進入 VERIFIED_CANDIDATE。`done` 仍需驗證與 review 都通過。代理自稱 MILESTONE 只進 verifying。

Discord 發文者只讀事件。每個 thread 事件以 event id 去重；看板只有一則可編輯的「任務看板」，訊息 id 持久保存。adapter 可用 fake 測試；正式 token、channel id 只由環境／grok-bot-01 設定。Discord API 不提供以本地交易包住網路發文的 exactly once：送出成功但本地記錄前斷線時，先對帳或人工處理，不盲目重貼。第一階段不啟用正式發文，也不移除現有 cron；部署時才用此服務取代 `bat-watch-*` 與 idle keep-pushing。

Goose adapter 限用 stock `goose acp`，以 ACP JSON-RPC 操控，任務 recipe YAML 設定指示、工具、參數、驗收和重試上限。服務只給 Goose 該 task 的 `send`、`read`、`run_verification`、`request_ted`，不暴露 `work_submit`。驗證命令由本機受信設定選定並由服務觀察 exit code、commit/tree；Goose 無法提供自己的 exit code 作證。Goose PM 的**首選預設改為 agy-openai-shim 的 Antigravity Claude**；順序為 `agy-claude → codex → claude`。Codex 使用 ChatGPT 訂閱登入作備援；Claude ACP 須有可用額度。Gemini 只在明確設定時做低成本狀態分類。禁止付費 API key。第一階段有 fake BAT 的 ACP smoke 與 provider adapter／fallback 測試；真 Goose PM、provider 認證、ACP 恢復及實機穩定性仍待第二階段驗證。正式 task 仍預設 rules，daemon 拒絕 live Goose 提交。

每個 PM step 的 model router 先用既有 TypeSafe Jev 分類 `status_relay`、`verification`、`planning`、`review`，記錄校準 confidence 與 stakes。一般狀態／逐字轉述可走 agy Gemini Flash；規劃、查證、review 在低信心或高風險時優先用 agy shim 的 Antigravity Claude，受每日成功使用次數上限與 quota/rate-limit 訊號限制，超限即用 Codex 訂閱。Jev 不可用則直接用 Codex。第一階段只交付決策介面、設定物件、使用量／錯誤及 routing journal，**沒有讓 router 呼叫真實模型**；實際模型提供者切換、每日 cap 的配額對應和信心閾值調校屬第二階段。

Goose 執行檔固定版本 **v1.52.0**，只在 grok-bot-01 的 `/home/box/.local/bin/goose` 安裝；Ted 從官方 `aaif-goose/goose` v1.52.0 Linux x86_64 release 安裝，並核對 archive SHA-256 `4aee1f770b405c44194c0e9407df1fb06bda4c50eee935f0d8fd10731821cc5e`。connector `GooseConfig.expected_version` 及執行前檢查也固定為 `1.52.0`。本 worktree 沒有該 binary；Goose 與 connector 分別版本化，不能修改 Goose bundle。升版須重新跑下方契約門檻。

端點現況：`castleridge-ai1` 上既有 agy-openai-shim 位於其**本機** `127.0.0.1:18795`；公開 `/v1/models` 只列 Gemini ID。Claude 請求失敗，因該 shim 給 Claude 加了不支援的 `--effort medium`。Ted 確認直接 agy 的 `claude-sonnet-4-6` 回應 `AGY_OK`；用只修正 Claude effort 對應的**隔離暫時 shim**，在遠端 loopback `18796`、本地轉送後，Claude model 請求成功，紀錄顯示帳號池 acct1／acct2／acct3。既有 Hermes shim 未更動；正式 shim 修正／model list 合約尚未交付，不能把 18795 當可用 Claude 端點，也不能把轉送埠當永久配置。Goose 的 base URL、model、token 仍須從私有 0600 設定／環境提供，不寫進 repo。沒有讀取或提交金鑰，也未使用付費 API key。

隔離 live smoke 已以 **Goose v1.52.0 + 暫時 Claude-capable shim + PR 的 GooseACP + task-scoped MCP** 跑通；未開 Goose 內建 developer／shell 工具。Goose ACP 回 `end_turn`，fake task/BAT 帳本只有**一次** `task_send`，文字 `SMOKE_TASK_SENT`，provider branch 記為 `agy-claude`。耗時約 41.7 秒；provider log 顯示五次 streamed completions，未提供 token 用量。這證明一條隔離路徑可連通，**不是**真 BAT、正式 daemon、重啟恢復、provider switch 或生產部署證據；live Goose gate 仍關閉。

每個 task 保存 `submitted_at`、`delivered_at`、`delivered`、`review_rejections`、`ted_interventions`、`session_replacements`；可計算交付／未交付、review 駁回次數、消失 session 的替代次數及交付秒數。目前 `ted_interventions` 是**呼叫者聲稱 Ted 介入**的次數，來源 ID 去重，但尚未綁定受信 Discord 事件，不能作已驗證的 Ted 實際介入數。事件帶時間戳供稽核，不能把 coding agent 的自述當成 delivered。

### 本 PR 的啟動與限制

`batc serve --host 127.0.0.1 --port 18796` 僅在明確啟動時運行；需要主機 `writes=true`、`orchestrate=true`。既有 `bat-agent-connector-mcp` 新增五個 work 工具，透過 `BATC_TASK_URL`（預設 `http://127.0.0.1:18796/rpc`）連同機 daemon；它本身不擁有第二份帳本。服務尚未部署。Rules 可建立 lead、續推、停派、從不明 BAT 回應對帳、執行**管理員預先設定**的測試命令並將觀察結果連同 commit/tree 寫入 PR #1 驗證紀錄，再啟獨立 reviewer。未設定受信測試命令時停在 verifying。Goose ACP adapter 和 task-scoped MCP 有 fake BAT 與上述隔離 live smoke 證據；goose 選項仍屬 smoke／試驗用途。Discord adapter 可用 fake 測；正式憑證和看板 channel 尚未配置。未關閉既有 Hermes cron，也未修改 BAT／Hermes 設定。

castle1 OpenClaw 應透過到 grok-bot-01 loopback 服務的受控轉接（例如 SSH socket forwarding）呼叫同一 task MCP，不在 castle1 啟第二個 daemon 或 SQLite。HTTP 維持 loopback；不直接向 LAN 開放 BAT token 或 task 控制端點。

## 第二階段：計畫，尚未交付

1. grok-bot-01 已安裝並 pin Goose v1.52.0；接著須驗證 stock ACP resume、持久恢復、provider 選擇與正式 agy shim Claude 相容性。用相同真實任務比較 rules、Goose、Hermes 的完成品質、續推次數、額度、人工介入與恢復時間，再決定預設引擎。
2. 第一階段已有預設 OFF 的 service-only GUI tab 註冊開關；第二階段在 grok-bot-01 小範圍開啟、跑 revision recheck／GUI 競態測試。`workspace:save` 是整份覆寫，與 GUI 同時存檔仍可能互蓋；Ted 已接受文件化風險，但無 BAT host-side 原子 append 就不能保證沒有 race。
3. 配正式 Discord token／thread／看板 channel、持久化 message id、部署 service unit、備份 SQLite、健康檢查與重啟 runbook。確認對帳後停用 Hermes 的 `bat-watch-*`、idle keep-pushing；實測 castle1 OpenClaw 轉接。沒有在本 PR 啟動服務或更動 Hermes／BAT。

參考：[研究 Part 1／2](../research/2026-09-27-review.md)、[先前評估](no-bat-change-evaluation.md)、[下一代設計](next-gen-connector.md)。`chatgpt-full-discussion.md` 僅研究使用，不能提交。

## 可恢復的狀態機與帳本

單一 task ID 永不更換。`branches` 表另記每次 BAT lead／reviewer session 與 PM provider 選擇，包含 `branch_id`、`session_id`、provider、角色、上游 branch ID、原因、時間；`work_status` 回傳完整 branch 歷史。這裡的 branch 是任務執行分支，與 Git branch 名稱不同。`tasks` 保存原話、工作空間、recipe、狀態、pause/control_version、lead/reviewer session、turn marker、commit/tree、review marker、提交／交付時間與指標。`commands` 有唯一 idempotency key、預留 session ID、BAT message ID、kind、送出前游標和狀態。`events`、`routing`、`provider_usage`、`observed_verifications`、`capabilities`、`ted_actions`、Discord `board` 與 owner lease 各自保存可稽核資料。所有網路呼叫前先提交命令意圖；同一 key 不會生第二條命令。

### 2026-09-27 22:51:52–22:51:58 ET shadow task 診斷及恢復界線

Task `9a8c8579-b0cc-4e0b-aa69-71d79eabfe0e` 的 BAT start 回 `aec7b468-deb2-4166-b662-3d8f79529e66`，audit 中 `worktree:create` 成功、branch `bat/worktree-e5ed1603`，`claude:start-session` 回成功，但初次送 prompt 被拒，進入 `needs_ted`。唯讀檢查 castle1 的 BAT 現況時，**同一 session ID 的** `claude:get-session-meta` 與 `claude:get-session-state` 都存在、`numTurns=0`；`worktree:status` 有該 branch/path，工作樹目錄仍在；BAT user service 自 19:00:37 ET 運作，沒有 22:51 重啟證據。GUI workspace terminals 沒有這個 headless session，符合 tab registration OFF。castle1 本機 connector registry 也沒有它，所以 `service._resolve_session` 對同 ID 回「session not found」。BAT 的舊 sidecar log 和該時段 user journal 沒有足夠事件細節；grok-bot-01 daemon 的當時 registry/log 未能唯讀取得，故**不能證明** grok 端當次拒絕的唯一原因或宣稱 BAT GC 刪了 session。可確認的是 connector 查找設計存在 registry/GUI 可見性裂縫；BAT meta 本身證明 session ID 沒錯，worktree 並未消失。

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

`pause` 先持久化控制版本，停止新派送；可選擇 interrupt 當前 turn。start 等待期間發生 pause 時，已接受的 session 保存為 `accepted` 但不送初始 prompt。若 pause 在 send 前的 presence lookup 期間發生，服務在 BAT send 呼叫前再次讀 pause，取消尚未送出的命令。`resume` 清除 pause，下一 tick 先查 pending 命令；若無待對帳且 session 尚未收到 prompt，才以新的 control version 送第一次 prompt。每個 host/session 在單 daemon 內有 writer lock；程序間以 0600 lock file 的排他 `flock` 與 owner heartbeat 限制為一個 daemon。外部 BAT GUI／舊低階工具不受此鎖控制，故遇無法歸因的 turn 保留 uncertain。

送 prompt 前先持久記 `needs_review`，包含 message ID、prompt SHA-256 與送出前游標；即使 crash 發生在實際送出前，也按**可能已送出**處理。逾時、斷線或回覆遺失後保持 `uncertain`。Claude `session_read` 的 `correlated`／`correlated_after_prior_turn` 可用於對帳；Codex 的 `timestamp_cursor` **只是時間位置，不能證明回覆屬於本命令**，連同後來出現的 `REVIEW: PASS` 都不能用來結案或自動重送。Codex 只有明確的命令／turn 綁定證據才可自動歸因，否則走下述人工對帳。Reviewer PASS 同時要求獨立 reviewer prompt／turn 歸因、lead 已停筆、乾淨的當前 commit/tree 和受信測試 exit 0。BAT 明確回 busy/rejected 時標 rejected、請 Ted 處理，不假設可安全重送。start 對帳使用預留 session ID 和 BAT meta；lead／reviewer／failover successor start 的 ack 都須回精確預留 session ID。相同 worktree 的 failover 另比對 host worktree path/branch、Git branch 與 registry branch，任何變動都 fail closed。failover 的 registry＋BAT meta **只證實 successor session 存在**，handoff `batc-*` ID、registry `sent` 和後來不相關的回覆都不能證明 prompt 所屬 turn。handoff `send` 維持 uncertain，可用獨立一次性命令 capability 人工對帳；確認 session 閒置後才可送文字不同的新 prompt。遇 candidate commit 或 tree 改變，清除舊 verification/reviewer/PASS，建立新 reviewer session。

Failover 預設把 task ledger 摘要交給 successor：Ted **完整逐字**原話、狀態、候選 commit、近期命令／事件，避免以可能極長或過時的聊天全文作權威。原話可在 handoff 內完整容納時直接寫入，**不再截到 2,200 字**。超過 3,000 字就先把完整原話寫入 0700 私有目錄中的 0600 archive，以 SHA-256 驗證，再由明確配置的 `BATC_TASK_ARCHIVE_VERIFY_SSH_HOST` 以 BAT successor 身分執行唯讀 hash 檢查；`BATC_TASK_LOCAL_HOST_ALIAS` 必須等於 task host。handoff 僅送 archive 路徑、字數、hash 與先讀原話的指示，不能稱縮寫摘要會覆蓋 Ted scope；實際 BAT handoff prompt 在送出前再次檢查路徑／hash 或完整內文仍在。archive 無法被 successor 驗證時 fail closed，不送 prompt。提交原話上限 19,000 字，超過時明確拒絕，避免初始 BAT prompt 靜默截斷；18,000–19,000 字的 failover 一律用完整 archive。若 ledger 摘要失敗，且本機路徑共享條件成立，服務才讀 BAT history 並建立同機 0600 archive／excerpt，**同時保留上述權威原話或原話 archive**；遠端無法共享路徑時 failover 保持 uncertain。超過 200,000 字時 excerpt 保留前 12,000＋後 148,000 字並標明中段省略。archive 絕不能放進 Git。

Failover 恢復只接受帳本預留的**同一個 successor session ID**。`failover` intent 要指向同 task 的獨立 handoff `send` command；兩者的 session ID、原 lead ID、handoff message ID／command ID 必須與 registry 完全相同。BAT 必須明確回 successor metadata 的工作目錄、舊 lead 與 successor 各自的 `worktree:status` path／branch、以及唯讀 Git root，並與原 lead registry worktree 一致。null 是未知；實際值不同或先前 successor 搶占是衝突，持久記為 `operator_only`，重啟後也不自動採用。衝突時不改 command session、task session 或 branch 歷史，不重送 handoff；管理員可用 task／command-scoped `work_reconcile` 記錄證據並交人工接管，但不能憑它把未驗證的 successor 自動變成新 lead。低階 failover 遇已存在的 successor，也必須與 caller 預留 ID、handoff message／command ID 一致。Reviewer 借用 lead worktree，只是讀取者，不擁有自動 cleanup／merge 權限。

Failover handoff 在舊 Claude 狀態查詢、新 Codex session start、BAT 連線等等待之間可能遇到 pause。服務在 handoff intent／prompt hash 已入帳後，送出前重查 task `paused`、`control_version`、原 lead／預留 successor 與 handoff command；BAT client 在真正寫入 `claude:send-message` frame 前再做一次相同檢查。若 pause 已提交，handoff `send` 留在 uncertain、failover 標 `operator_only`，恢復派工也不會重送，須由有權操作者對帳。

BAT 確認預留 successor start ID 後，**handoff 送出前**先查 successor metadata `cwd`、舊／新 session 的 worktree path／branch、Git root，與 task 舊 lead registry、預留 ID 和 handoff command 綁定；任何具體不符都不送 handoff，轉 `operator_only`。BAT client 在提交實際 handoff frame 前計算該 frame 的 prompt SHA-256，與 journal intent **逐字 hash 相等**才寫入 frame，並將該 frame hash 記入私有 registry。正常回覆與重啟恢復都要求 registry frame hash 等於 journal prompt hash；只有 64 位 hash 的外形並不足夠。null host 身分仍是 uncertain，不用猜測或重送。

Successor 身分在 handoff 前查過後，BAT 連線等待仍可能改變 registry 或 host 狀態；所以連線後再查一次 successor `cwd`、舊／新 worktree path／branch 和 Git root。實際 frame 邊界以同一個 registry 檔鎖原子比對 task ID、預留 successor ID、`failover_of` 原 lead、共享 worktree、path／branch、handoff command／message ID 與 pending 狀態，並寫入實際 frame hash；在送 frame 前再檢查 pause／control version。若 owner link、Git root 或其他具體身分在兩次查詢間變動，零 handoff frame，命令維持 uncertain／operator-only。這是 connector 自身送出界線；BAT 外部行為仍須獨立實機驗證。

## 權限、設定與操作恢復

HTTP 僅聽 loopback 並檢查 peer。一般 work RPC 需本機 0600 admin bearer token；Goose 只取得 1 小時的 task-scoped capability，不能呼叫 `work_submit`、操作另一 task 或直接提供測試 exit code。對不明一般 send 或 failover handoff send，管理員用 `work_reconcile_capability` 為**一個 task／command** 發 10 分鐘一次性 capability，再用該 token 呼叫 `work_reconcile`，提供 `delivered`／`not_delivered`／`superseded`、操作者、來源和證據。admin token 本身不能直接解決命令。`batc task-reconcile` 在本機完成這兩步；若要接續，必須提交**不同文字**的新 prompt，先記新 intent，並確認 BAT session 閒置；新 prompt 不重播舊命令。人工聲稱 review PASS 還要提供當前 commit/tree、exact turn reference，服務重查乾淨候選、reviewer 已停筆及當前觀察測試。無證據的 resolve 留在 `human_owned`，`work_resume` 不會偷偷續推。這是有權操作者的可稽核證詞，並非 BAT 自動證明。狀態目錄 0700；SQLite、token、lock、私有 handoff archive 0600。不要將 token、shim 金鑰、原始聊天或 provider 錯誤全文寫入日志。castle1 OpenClaw 需透過受控 SSH loopback forward 加 admin bearer 呼叫同一 grok-bot-01 daemon；若要允許 castle1 寫入，應配置限定權限的轉接身分，不能把 loopback HTTP 直接開到 LAN。此轉接與主機授權尚未部署。

私有 `BATC_TASK_SETTINGS` TOML 必須 0600，例如 `[verification.commands]` 的 `project = ["uv", "run", "pytest", "-q"]`；remote host 可用 `[verification.ssh_hosts]` 指定既有 SSH alias。測試 stdout/stderr 只存本機 `task-artifacts` 的 0600 檔案（至多保留前 2 MB，另存完整輸出 SHA-256）；可在 `[verification]` 設 `artifact_dir` 到私有路徑。`[task_service] register_tabs = true` 是額外的 service-only 顯式開關，預設 false；主機既有 `orchestrate_register_tabs=true` 也必須同時成立。lead 和 reviewer tab 都用 connector 的 append/revision recheck；不改 BAT。Ted 很少開 GUI，仍需知道 `workspace:save` 整份覆寫的 race。

Discord thread 發文含固定 `BATC-EVENT:<event_id>` marker，發文前 claim；若 crash，重啟先找最近 100 則的 marker／message ID，找到即標 sent。超過這個範圍時需管理員查完整 Discord history；若找到了舊訊息，可用 `batc task-delivery --confirm-found-event <id> --message-id <discord-id>`，服務再用 Discord GET 驗證 bot 作者和 marker 後標 sent；確認不存在才用 `--confirm-absent-event` 明確重試。看板 `BATC-BOARD:<channel>` 只有一則：已知 message ID 時重試 edit 安全；未知 ID 的 create 同樣須尋找或人工確認，可用 `--confirm-found-board`／`--message-id`。Fake adapter 覆蓋重啟及 found-ID；真 Discord token 和 channel ID 只從環境注入。`work_delivery_status` 與 `batc task-delivery` 可查看未解事件。尚未取代 Hermes cron。

若 failover 身分有明確衝突，管理員也可對 `failover` command 取得一次性 capability 並對帳；此動作同時結清它綁定的 handoff command、留下 actor／source／evidence，task 進入 `human_owned`，**不**把未知 successor 變成 lead，也不能在同一次對帳送新 prompt。若 handoff command 本身的帳本綁定已損壞，必須先由管理員修復帳本，服務拒絕自動採用或猜測。

## PM provider 設定與限額

私有 `BATC_PM_PROVIDER_CONFIG` TOML (0600) 有多個 `[[providers]]`：`id`、`kind`（`agy-shim`、`openai-compatible`、`codex-acp`、`claude-acp`、`gemini`）、`base_url`、`model`、`daily_cap`；頂層 `fallback_order = ["agy-claude", "codex", "claude"]`。`base_url` 僅允許無 credential 的 loopback HTTP；`BATC_AGY_SHIM_TOKEN` 從環境供本機 agy shim adapter 使用，不能提交設定或使用付費 API key。每 task 可給 `pm_provider`，recipe 可給預設；未給則首選 agy Claude。新 provider 只需一個小 adapter class、設定 entry 及自己的 fake endpoint／ACP contract test。設定日上限按 UTC 日計成功使用次數；`quota_error`、`rate_limited`、`auth_error` 只能在**確認未送 prompt**時切換至下一 provider，寫 `provider_usage` 與新的 task PM branch。已送、`needs_review` 或 uncertain prompt 必須先對帳，禁止切換時重播同一內容。錯誤以結構化 HTTP status/code 分類，不以可能含敏感內容的錯誤字串猜測。

Jev router 仍可按每個 PM step 分類 `status_relay`／`verification`／`planning`／`review`，每次記 confidence、stakes、選擇與原因；Jev 不可用時 fail open 選 Codex。Routine status 可明確選 agy Gemini Flash；高風險／低信心規劃、查證、review 優先 scarce agy Claude，額度不足選 Codex。**M1 只有 router 決策／帳本介面；daemon 還未讓 router 驅動 live PM 步驟。**規則引擎是 deterministic，不會偷偷呼叫模型；Goose live gate 仍關閉。它與 Goose provider switcher 是兩層：Jev 決定一步適合誰，switcher 只處理該 provider 在未送 prompt 前的故障。額度 cap 是服務的保守計數，不代表第三方真實剩餘額度。OpenAI 相容 adapter 的探針現在要求 `/v1/models` 含設定的 model ID；各種 ACP/provider 的實際模型驗證仍需 pinned Goose contract test。真 provider 執行、成本與品質 A/B 屬 M2。

## Pinned Goose 啟用門檻（M2 contract-test checklist）

此清單取自 Ted 提供的 `/workspace/goose-acp-handoff/docs/UPGRADES.md` 概念文字；本環境沒有該 clone，未複製其 Node/MIT 程式碼。目前 pin **Goose v1.52.0**；`goose --version` 必須符合此版，archive checksum 依上文核對。Goose 與 connector 分開 pin 版本，不改簽署的 Goose bundle；私有 integration config 與 handoff state 先備份，不能提交。每次升版在**隔離 synthetic session** 完成下列檢查後才可能開 live Goose：

1. 跑 connector repo tests／syntax，對安裝的 Goose 驗證 `initialize`、`load/new`、`configOptions`、`session/set_config_option` 的真實 schema 與回覆。
2. 檢查 host UI 真的顯示 handoff 與 target-model 選擇；target setup 必須驗證回覆的 provider choice 與 approval-mode setup。wrapper 對 protocol version 非 1 必須拒絕。這些檢查仍非完整相容性保證，未知 protocol/UI 變更可能破壞流程。
3. 切換 provider、記 synthetic marker、reload 後確認 history 與 identity；強制 provider 失敗，確認原 session／內容保留。工具 approval 要保留為 approval，不能自動變成 granted permission。
4. 失敗時保持 handoff 停用，保留舊 session／私有 state，把 adapter/config 回退至 last known good。略過 wrapper 只會回原 agent，不會合併 target branch messages。
5. 替換 relay 之前要讓 in-flight prompt 結束或明確取消，不能為安裝功能殺掉 active writer。

目前 ACP adapter 的 fake smoke 使用 protocol 1，遇非 1 或沒有 session ID 即拒絕；上述 `load/new`、`configOptions`、`session/set_config_option`、真 provider choice／approval UI、故障保留、rollback 及 active-writer 項目尚**不是可執行 gate**。此外還要證明 task-scoped MCP capability、subprocess env/process 隔離、ACP session 在 daemon 重啟後可恢復、provider auth/quota 分類、no-resend 及 pinned 版本在 grok-bot-01 的實機行為。現有 BAT adapter contract tests 使用 mock host，涵蓋 start／recover／Codex send／reviewer 唯讀；真 BAT timeout、busy、failover、reload 和 tab revision race 仍未實機驗證。**live Goose 保持停用，也不得進入真實 shadow trial。**獨立 reviewer 對本 PR 的 P1/P2 修正重新 sign-off 後，才討論 smoke 範圍及後續實機 gate；本 PR 不部署。
