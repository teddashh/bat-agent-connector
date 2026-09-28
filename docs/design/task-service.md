# 任務服務：第一階段實作與第二階段計畫

日期：2026-09-27。依照 Ted 核准的架構；BAT 原始碼與既有低階 MCP／`batc` 介面不變。

## 現在要解決的事

Ted 只對 Discord 裡的 Hermes 說話。Hermes 只能逐字保存原話、交辦一次、回報結果；絕不能改寫、解讀或拆解要求。若舊呼叫者仍傳 `interpretation`，此欄僅保存為**非權威的外部附註**，不放進 coding prompt。規劃與拆解交給熟悉 repo 的 Codex／Claude lead session，遵守 `relay.py` 原話優先的界線。Hermes 不應在 `session_wait` 裡等 60／90／120 秒。新訊息曾打斷等待，造成找不到 session、重啟被 active wait 擋住、castle1 metadata／handshake timeout，以及 stale reply guard 擋回覆。現在 `orchestrate_register_tabs=false`，自動 session 在遠端 BAT GUI 看不到。任務服務必須自己保存任務和進度，不以 GUI 或 Hermes 記憶當帳本。

## 第一階段：可執行範圍

`batc serve` 是單一長期程序。它擁有 SQLite WAL 任務、命令及事件帳本，提供 loopback HTTP 給本機 MCP 客戶端與 castle1 OpenClaw 的受控轉接。Hermes 的 `work_submit` 只寫帳本並立即回 `task_id`；`work_status`、`work_pause`、`work_resume`、`work_result` 讀／改同一帳本。提交逐字保存 Ted 原話、Discord thread、recipe、驗收條件及 idempotency key；可選的 interpretation 是非權威記錄，不進 prompt。重複 key 回原 task；同 key 不同內容拒絕。預設 rules 引擎。`goose` 是明確 opt-in。

服務每次先記命令 intent，再呼叫 BAT。單一 task 的同一 host/session 只有一個 writer；控制版本與 pause 在送出前重查。送出逾時後標 `uncertain`，**絕不重送同一命令**。重啟後先用 BAT session 讀取與 turn marker／message id 對帳；無法判定是否被接受時保留 uncertain 並請 Ted 處理。BAT Codex 沒有可靠的 host-side command receipt，無法承諾 exactly once；GUI 或舊低階工具也不受服務鎖約束。新自動化入口須用 task 工具。

Rules 引擎在回合確定完成、尚未達驗收、沒有 blocker／額度／人工接管且未達 recipe 續推上限時，派一次短 `continue`；模糊語意才請 Jev 分類。狀態包括 queued、dispatching、accepted、running、waiting_permission、quota_limited、human_owned、needs_ted、verifying、done、failed、uncertain。Pause 停止新派送，可選擇 abort 當前回合或讓其結束；resume 先對帳再續推。額度 failover 呼叫 PR #1 的原子 successor reservation 路徑，記下新舊 session。開發者自稱完成、測試通過後，starter recipe 預設開**另一個** reviewer session：Claude 額度可用時用 Claude，否則用全新 Codex。Reviewer 依驗收條件回報；拒絕時送回開發者並計數，達 retry cap 即請 Ted 處理。通過後才以 PR #1 的 commit 綁定驗證紀錄進入 VERIFIED_CANDIDATE。`done` 仍需驗證與 review 都通過。代理自稱 MILESTONE 只進 verifying。

Discord 發文者只讀事件。每個 thread 事件以 event id 去重；看板只有一則可編輯的「任務看板」，訊息 id 持久保存。adapter 可用 fake 測試；正式 token、channel id 只由環境／grok-bot-01 設定。Discord API 不提供以本地交易包住網路發文的 exactly once：送出成功但本地記錄前斷線時，先對帳或人工處理，不盲目重貼。第一階段不啟用正式發文，也不移除現有 cron；部署時才用此服務取代 `bat-watch-*` 與 idle keep-pushing。

Goose adapter 限用 stock `goose acp`，以 ACP JSON-RPC 操控，任務 recipe YAML 設定指示、工具、參數、驗收和重試上限。服務只給 Goose 該 task 的 `send`、`read`、`record_verification`、`request_ted`，不暴露 `work_submit`，避免遞迴與跨任務寫入。Goose provider 可設定，**預設 Codex 訂閱／Codex CLI provider**，Claude 額度可用時可選 Claude；Gemini 僅供明確 opt-in 的低成本狀態分類，不能預設作 PM。設定應採 Goose 官方訂閱登入或既有本機相容端點；禁止付費 API key。Codex 訂閱額度、Claude 限額、Gemini 便宜但規劃品質的差異須在真實 A/B 量測。第一階段有 fake BAT 的 ACP smoke；真 Goose PM、provider 認證及實機穩定性仍待第二階段驗證。預設保持 rules。

每個 PM step 的 model router 先用既有 TypeSafe Jev 分類 `status_relay`、`verification`、`planning`、`review`，記錄校準 confidence 與 stakes。一般狀態／逐字轉述可走 agy Gemini Flash；規劃、查證、review 在低信心或高風險時優先用 agy shim 的 Antigravity Claude，受每日成功使用次數上限與 quota/rate-limit 訊號限制，超限即用 Codex 訂閱。Jev 不可用則直接用 Codex。第一階段只交付決策介面、設定物件、使用量／錯誤及 routing journal，**沒有讓 router 呼叫真實模型**；實際模型提供者切換、每日 cap 的配額對應和信心閾值調校屬第二階段。

模型端點檢查：本機 `agy-openai-shim` 設定有 `127.0.0.1:18795`，程式提供 OpenAI 相容 `/v1/models` 和 `/v1/chat/completions`；此為檢查到的**本機**設定，未確認 grok-bot-01 相同或 Goose 可成功認證。僅在明確選 Gemini 分類時檢查該端點；Goose PM 預設 Codex 訂閱登入，不配置付費 API key。`goose --version` 在本工作樹環境無可執行檔；正式 smoke 須於部署主機補跑。

每個 task 保存 `submitted_at`、`delivered_at`、`delivered`、`review_rejections`、`ted_interventions`；可計算交付／未交付、review 駁回次數、Ted 介入次數及從提交到交付的秒數。事件帶時間戳供稽核，不能把 coding agent 的自述當成 delivered。

### 本 PR 的啟動與限制

`batc serve --host 127.0.0.1 --port 18796` 僅在明確啟動時運行；需要主機 `writes=true`、`orchestrate=true`。既有 `bat-agent-connector-mcp` 新增四個 work 工具，透過 `BATC_TASK_URL`（預設 `http://127.0.0.1:18796/rpc`）連同機 daemon；它本身不擁有第二份帳本。服務尚未部署。Rules 可建立 lead、續推、停派、從不明 BAT 回應對帳、讀取現有 `batc record-verification` 紀錄並在通過後啟獨立 reviewer。若沒有外部可信測試執行者寫入 PR #1 驗證紀錄，任務停在 verifying，不會假裝已交付。Goose ACP adapter 和 task-scoped MCP 已可用 fake BAT 走通一個 tool call；真 Goose 尚未在此主機安裝，goose 選項屬 smoke／試驗用途。Discord adapter 可用 fake 測；正式憑證和看板 channel 尚未配置。未關閉既有 Hermes cron，也未修改 BAT／Hermes 設定。

castle1 OpenClaw 應透過到 grok-bot-01 loopback 服務的受控轉接（例如 SSH socket forwarding）呼叫同一 task MCP，不在 castle1 啟第二個 daemon 或 SQLite。HTTP 維持 loopback；不直接向 LAN 開放 BAT token 或 task 控制端點。

## 第二階段：計畫，尚未交付

1. 在 grok-bot-01 安裝與 pin Goose 版本，驗證 stock ACP resume、MCP 工具注入與 agy shim 的端到端模型呼叫。用相同真實任務比較 rules、Goose、Hermes 的完成品質、續推次數、額度、人工介入與恢復時間，再決定預設引擎。
2. 讓自動 session 可選擇註冊 BAT 遠端 GUI 頁籤；保留 revision recheck、加競態測試與受控 rollout。`workspace:save` 是整份覆寫，與 GUI 同時存檔仍可能互蓋；Ted 已接受文件化風險，但無 BAT host-side 原子 append 就不能保證沒有 race。
3. 配正式 Discord token／thread／看板 channel、持久化 message id、部署 service unit、備份 SQLite、健康檢查與重啟 runbook。確認對帳後停用 Hermes 的 `bat-watch-*`、idle keep-pushing；實測 castle1 OpenClaw 轉接。沒有在本 PR 啟動服務或更動 Hermes／BAT。

參考：[研究 Part 1／2](../research/2026-09-27-review.md)、[先前評估](no-bat-change-evaluation.md)、[下一代設計](next-gen-connector.md)。`chatgpt-full-discussion.md` 僅研究使用，不能提交。
