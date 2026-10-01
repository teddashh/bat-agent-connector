# BAT 不改版時，Hermes 要怎麼穩定交辦程式工作

日期：2026-09-27；依 Ted 後續提供的完整逐回合討論與「自動 session 在 GUI 完全不可見」事實修訂。本文只評估，不修改 BAT 或連接器程式。PR [#1](https://github.com/teddashh/bat-agent-connector/pull/1) 已修正部分連接器問題，但 BAT 沒有替外部控制器記錄任務或鎖住工作目錄。

**資料範圍。** 先前所說的「兩篇」是同一份[研究文字](../research/2026-09-27-review.md)的 Part 1（連接器與 Goose）及 Part 2（Buzz），不是 Tony 的文章。這次另逐回合讀完 Ted 提供的 1,570 行 `docs/research/chatgpt-full-discussion.md`，並核對工作樹的 `docs/current-workflow.md`、`docs/hermes-bat-log-excerpts.txt`、本庫[遠端協定筆記](../PROTOCOL.md)、[上一版設計](next-gen-connector.md)、PR #1 和原始碼。三份 Ted 新提供的本地檔案是研究輸入，未隨本文提交；完整討論引述另一個 BAT×Goose 計畫及另一個分享頁，但本文沒有拿到那些原文，不能把 ChatGPT 對它們的描述當作 Ted 已確認的規格。BAT `5a61d43`、Goose `04ed836`、Buzz `b0d6fb8` 是唯讀參考快照；未驗證五台主機是否部署相同版本。沒有搜尋 Tony 文章。

## 我的判斷

**新的關鍵事實：Ted 現在完全看不到連接器建立的 session。** `orchestrate_register_tabs=false`，這些 session 沒有 BAT GUI 頁籤；Ted 實際只在 Discord 看 Hermes 報告。完整討論早期把「在 BAT 看同一段 session 並接手」當作現況或目標，但現在只能當願景，不能拿來支持選 BAT 當自動化主引擎。

目標架構應是**一個持久任務服務 + 對 Hermes 的任務級 MCP + Discord 回報 + 可看證據的 Dashboard／CLI + 可替換執行器**。近期沿用 BAT 連接器作為現有工作的相容執行路徑，先修「送出後誰追、斷線後怎麼對帳、報告會不會重貼」。新無人值守任務的預設目標則應評估主機上的 Codex CLI／`codex exec` 或 Claude Code 無介面 runner：它直接掌握程序、日誌、取消與驗證，不再為一個 Ted 看不到的 BAT 面板承受 Codex 回合關聯與頁籤成本。**這是目標選擇，並非已驗證的直接替換**；先用相同任務比較品質、訂閱／認證、額度、成本及恢復能力，再切主力。

Dashboard 現在是**必要的任務觀察面**，不能再假設「詳細內容回 BAT 看」；第一版至少能看正在做什麼、最後新事件、輸出摘錄、卡點、worktree／commit、測試證據及原始日誌位置。BAT 仍保留給 Ted 手動開發或看 repo；若未來要在 BAT 原生面板接手**同一個**自動 session，現有無頁籤與 BAT 端無 ownership gate 的限制仍在，需先停派並用人工交接，不能承諾無競態。

## 現況與 BAT 的設計邊界

Ted 在 TED-H AI Discord 從手機下令；控制主機（下稱 `control-host`）上的 Hermes（Gemini 經 agy-login／agy-openai-shim）解讀與轉交。Hermes 透過 MCP／`batc` 的 `bat-remote/v2` 連五台 BAT 主機（下稱 `host-a` 至 `host-e`，其中 `host-a` 是操作者的工作站）；本機代理各自可連本機 BAT，`host-a` 的 OpenClaw 也能連五台。它在專案 workspace 與 `.bat-worktrees/<id>` 建立或重用 Claude／Codex session，等待回合，把進度送到 Discord thread；15 分鐘的 `bat-watch` 與 5 分鐘派票 cron 另行運作。Claude 額度不足時轉 Codex，額度優先順序為 Google、Codex、Claude。Ted 有自己的 BAT 開發空間；但**連接器建立的自動化 session 在其遠端 GUI 不可見，沒有正在觀看或直接接手這些 session**。Hermes 的基礎 prompt 約 45k 至 48k tokens，120k 才壓縮；讓它反覆等待每張票既耗配額，也增加 thread 狀態漂移的機會。

BAT [README](https://github.com/tony1223/better-agent-terminal/blob/5a61d43/README.md)描述的是多工作區的終端與內建 Claude／Codex 面板；遠端 WebSocket 主要供另一個 BAT 或行動裝置操作主機，也可用無 GUI 的 `bat-server`。本庫以相同遠端 API 延伸成 MCP／CLI 是合理的，但 API 的基本單位仍是 session、workspace、事件，不是耐重啟的「Discord 任務」。`claude:get-session-meta/state` 可輪詢狀態，`agent:*` 串流事件在斷線期間會遺失；`workspace:save` 覆寫整份 workspace 文件。BAT 遠端 token 的權限很大，跨機的控制面必須自行控管。

目前不註冊 GUI 頁籤的 headless session 只存在連接器本機的 `orchestrated.json`；[registry.py](../../src/bat_agent_connector/registry.py) 使用本機 `flock`，`control-host` 與 `host-a` 的 OpenClaw 並不共享這份記錄。若啟用 `orchestrate_register_tabs`，連接器以 `workspace:save` 寫整份文件，和 GUI 同時存檔仍會遺失更新。**不改 BAT 時，不能同時保證「自動建立 BAT 可見頁籤」和「GUI 編輯絕不被覆蓋」。** 可以讓 Ted 手動打開獨立工作目錄／session，或接受經測量的風險；不應把選項寫成已解決。

## 完整討論中的目標、介面與可行性

Ted 在逐回合稿的第 1、32、51、62、95 回合，明確描述了遠端操控、少監督、Discord 看報告、多 VM／worktree、想把自寫 MCP 變成有 Dashboard＋CLI 的服務，以及不想一直加技術棧。其餘許多具體介面名稱和架構圖是 ChatGPT 的**提案**，不是 Ted 已核准的成品規格。下表把明示需求和合理延伸一起列出，並標明不改 BAT 的邊界。此處「可」指可在連接器／協調器／主機 runner 完成，不表示現在已實作。

| 目標／介面 | 不改 BAT？ | 做法、現況與界線 |
| --- | --- | --- |
| **手機 Discord → Hermes**：一句話下令、回同一 thread、原文不被改寫 | **可** | Hermes 只收指示、標示自己的解讀並提交 task；保存 Discord 訊息／thread ID，`relay.py` 的原文與解讀分開。新訊息打斷等待不應取消已接受的 task |
| **Hermes 任務級 MCP**：提交、查狀態、等事件、補充要求、暫停／取消、取成果 | **可，需新增** | `task_submit/status/events/answer/pause/cancel/result` 是提議介面；回穩定 task ID，底層 BAT session／CLI 程序可更換。維持既有 session MCP 名稱供舊客戶端使用，但自動寫入須歸一個服務 |
| **任務服務／持久帳本**：跨 Discord、cron、OpenClaw、CLI 共用狀態 | **可，需新增** | 單一 daemon＋SQLite WAL 先保存 task、command、owner、事件、候選版與驗證；五台主機的控制器都向它讀寫，不能各有 `orchestrated.json` 當真相 |
| **命令去重／斷線恢復**：不因逾時重送兩次、重啟能繼續追 | **可部分保證** | 先記 intent／idempotency key 再派送，`uncertain` 時對帳。對 BAT Codex 無主機端命令收據，不能證明恰好一次；headless runner 可藉程序 ID、持久日誌及本機佇列提高可恢復性 |
| **現有 `batc` 與低階 MCP** | **可** | 保留命令、參數與讀取用途；新增 task 入口或讓自動化寫入轉同一服務。CLI 不得繞開服務另啟獨立控制者 |
| **Dashboard**：任務、里程碑、時間線、卡點、owner、主機、分支、額度、測試 | **可，現在更必要** | 讀同一帳本，顯示輸出摘錄、工具／程序日誌與證據連結；可分頁讀詳細紀錄。因 BAT 自動 session 在 Ted GUI 看不到，不能再把「看詳情」推回 BAT。第一版唯讀，控制功能先經有授權的 CLI／Discord |
| **Discord watcher 與派票 cron**：15 分鐘進度、5 分鐘社群票 | **可** | 對 task event 做排程及發文 ID 去重，只有狀態變化才回報；由服務原子領票。不要讓每個 `bat-watch-<session>` 長輪詢或由 Grok Bot 逐票催工 |
| **Coding agent 內層循環**：修改、測試、修正到交付點，少叫 Hermes | **可** | 給 Claude／Codex 一份明確任務、工作範圍、測試與停止條件；服務處理確定性等待與重試，Hermes 只管跨任務依賴和例外。Goose 不是必要條件 |
| **Repo-aware 計畫／fan-out** | **可** | 保留 coding agent 在 repo 內產生 fan-out 計畫；每個子任務分別入帳、分配 worktree 和 owner，不能只靠 Hermes 的長上下文記住 |
| **Worktree 隔離**：平行任務不互踩、必要時交接同一分支 | **可** | 每個並行改碼任務獨立 worktree／branch；測試埠、資料庫、暫存也要隔離。切換 writer 前先停止舊程序／session；`git worktree lock` 不能管誰能改檔 |
| **BAT 原生 Claude／Codex 執行** | **可，已有** | 既有 connector 經 `bat-remote/v2` 呼叫 `claude:*`。早期逐回合稿用 `agent:*` 作概括名稱；本庫實際通道與欄位以[協定筆記](../PROTOCOL.md)和原始碼為準。保留過渡／比較用途 |
| **直接 Codex CLI／Claude Code headless** | **可，需主機 runner** | 每台執行主機可啟程序、收退出碼／日誌／rollout，工作與 BAT GUI 解耦；要實測認證、額度、權限、品質、長任務與恢復，不假設它和 BAT app-server 完全等價 |
| **額度路由與 Claude→Codex failover** | **可部分實現** | 讀配額／限額訊號，選 Google、Codex、Claude 策略；PR #1 在單狀態目錄內做原子 successor reservation。跨機須用服務交易，舊 writer 與新 writer 不得同時改同一工作樹；認證與訂閱耗用要實測 |
| **任務預算、期限與有限重試** | **可** | 可信任務設定指定時間、回合／費用上限及最多幾次恢復；程式在達限時停派，按狀態對帳。額度耗盡與暫時連線錯誤採不同處理，不讓 Hermes 或 Goose 無限「繼續」 |
| **權限提示與 allow-all** | **可，但需明確界線** | 現況 Hermes 自動批准 BAT 提示；服務可對已授權的開發工作樹套固定權限政策、記錄批准，對新主機、正式環境、機密與破壞性動作另行升級。若走 headless runner，對應權限在 runner 啟動設定處理，不靠模型讀取提示後隨意放行 |
| **權限與控制權／Ted 停止或接手** | **服務內可，BAT GUI 強制鎖不可** | owner＋`control_version` 拒絕經服務的舊命令；停止派送、取消 runner／中止 BAT turn、對帳後交還工作樹。Ted 直接在 BAT GUI 寫入不經此鎖；目前自動 session 連頁籤都沒有。接手現實做法是先停自動化，再在 Ted 自己的 BAT session／新 checkout 繼續 |
| **BAT GUI 看同一個自動 session 的完整對話** | **目前不可用；安全自動化不可保證** | `orchestrate_register_tabs=false` 無頁籤；改成 true 會遇到整份 `workspace:save` 與 GUI 存檔競態。可以手動建立可見 BAT session 或另看 Dashboard 紀錄；不把前者說成已達成的現況 |
| **候選版驗證、採用／合併、清理** | **可，仍需可信執行器** | PR #1 已分開回合結束、代理宣稱、候選版驗證與合併准許；驗證綁 commit／乾淨樹、指令、exit、環境與 log。`session_record_verification` 目前仍可由呼叫者自述；下一步讓 runner／CI 真正產生證據。變更後重驗；保留未合併 branch／未提交工作，別因「暫時沒動」就刪掉 |
| **低成本判斷／Jev Decision Gateway** | **可選** | 程式先判斷 PID、狀態、exit、hash、owner；Jev 只處理窄範圍語意分類，不代替測試或每步都呼叫。不要再加一層必經的完整 transcript 推理 |
| **Goose 作局部派工者**：服務以 ACP 控制 Goose，Goose 用 MCP 操作任務 | **可選，需整合** | Goose 需自己的模型／供應商，僅拿該 task 的工具、session 與預算；Hermes 和 watcher 不再對同一 task 直接續推。其 ACP resume 要在實際版本驗證，Goose 的 session 鎖不會鎖 BAT／Git |
| **Goose 把 BAT MCP「直接當 ACP」／BAT ACP provider** | **前者不可；後者理論可但不宜先做** | MCP 是工具，ACP 是 agent session 契約；要另寫 prompt、事件、取消、權限、resume 映射的 adapter。沒有 BAT 修改也可做轉接，但無法補 BAT Codex 命令 ID，且多一層故障面 |
| **Buzz 概念或整套產品** | **借概念可；全面採用非必要** | 借一次性任務、期限、取消、可信啟動設定與結構化結果；`taskId` 不是去重帳本。完整 Buzz 會與 Discord／自建 Dashboard 重疊，違反 Ted 少加技術棧的偏好，除非真要替換既有協作面 |
| **Grok Bot／VM 管家**：版本、磁碟、登入、skills、訂閱、正式服務 | **可，屬獨立運維域** | 讓 Grok Bot 只看五台主機的健康與例外；用實際版本、skill hash、登入狀態、服務 health 證明「已套用」，避免八個升級包送到卻沒安裝的假完成。正式環境服務只在明確授權範圍變更；不把 VM 維護塞進 coding task 引擎 |
| **減少 Ted 監督與喚醒** | **可** | 正常進度由 Dashboard／Discord 增量報告，卡關先按預設策略有限次恢復；金錢、機密、公開、破壞性或不可逆才叫 Ted。停止／接手是確定性控制，不交給模型猜 |
| **安全存取五台主機** | **可，需認證設計** | BAT 仍用 TLS 指紋釘選與 token；新服務先綁 loopback。跨主機 Dashboard／MCP 需要身分驗證、task／主機授權、稽核及傳輸保護，不能只開 `0.0.0.0` |
| **衡量是否真的更有效率** | **可** | 比較現況、加任務服務、換 headless runner、再可選 Goose／Jev；同一批 repo／候選版／驗收，量通過任務數、人工分鐘、重工、恢復、成本與額度。不能把控制層收益算給 Goose |

介面關係可簡化為：`Ted → Discord/Hermes → 任務服務 → {BAT connector、headless runner、可選 Goose ACP} → 驗證器`。Dashboard、CLI、watcher 都讀同一任務服務；Grok Bot 只處理 VM 健康和少數例外。若 Goose 用 MCP 呼叫 BAT，它只是**其中一條執行路徑**，不能再讓它用相同高階 `task_submit` 反覆建立自己的任務。

## 日誌能證明什麼、還不能證明什麼

以下時間來自 Ted 複製的 `control-host` grep 摘錄（工作樹 `docs/hermes-bat-log-excerpts.txt`），是選過的行，不含完整工具參數、回傳內容或同時的 BAT 主機日誌。

| 觀察 | 可以下的結論 | 仍需查明 |
| --- | --- | --- |
| 9/26 至 9/27 大量 `mcp__bat__session_wait` 約 60／90／120 秒才回，偶有 200 秒以上，結果常只有 176／177 bytes | Hermes 的工作單元長時間被等待占住，值得把監看移出對話回合；小結果長度本身不代表 BAT 沒進度 | 逐次回傳的 `status`、`after`、`turn_phase`、BAT `numTurns`、是否同一任務重複輪詢 |
| 9/26 22:35:10 等待因 Ted 新訊息中斷 | 使用者插話確實會取消 MCP 等待；如果後續只靠短暫事件，會漏看回合 | 取消後是否重新讀取該 task／session，或意外重送 prompt |
| 9/27 12:22:32 `gateway.mirror` 回報 Discord thread「no session found」 | 有獨立於 BAT 的 Discord 對話映射問題 | 該 thread、Hermes session、BAT session 的持久映射是否仍在，以及當時是否重啟 |
| 9/27 14:23 至 14:24 重啟等待一個仍在 `session_wait` 的工作單元，之後 Discord 斷線；多次重啟後 MCP 工具重新註冊 | 長等待會拖住重啟；重啟與連線生命週期確實介入了作業 | 當時 host 是否仍在跑、事件／Discord 發文是否重播 |
| 9/27 18:10 `claude:get-session-meta` 15 秒逾時；18:13 `host-a` WebSocket 握手逾時 | 至少有主機／連線層的實際故障，不能全歸咎於模型忘記 | `host-a` BAT 負載、連線與 sidecar 日誌、其後是否成功對帳 |
| 9/27 19:27 `bat-freshturn-guard` 擋住相似度 0.07 的舊回覆；另有 `tools.override` capability 被拒紀錄 | 舊報告重貼的風險是實際觀察，不只是推測；外掛防線也不能假定每次都啟用 | 被擋內容的來源、外掛授權狀態，以及其他未被擋的 Discord 發文 |

所以「Hermes 掉 session」至少可能包含三種不同故障：BAT 回合歸屬不明、Hermes／Discord 的 thread 映射或對話中斷、主機／WebSocket 暫時不可用。PR #1 解決舊 Claude UUID 標記解析錯誤及部分舊回合誤認，**但日誌摘錄沒有該次工具參數與回傳，不能宣稱這就是已觀察案例的唯一根因**。優先補上 `discord_thread_id → task_id → command_id → host/session_id → message_id` 的低敏感度追蹤；記錄送出、接受、輪詢、斷線、對帳及 Discord 發文 ID，不記密鑰和完整 prompt。對同一個錯誤取 Hermes、連接器 audit、BAT sidecar／Codex、主機資源四方時間線，才可定因。

## BAT 不變時的可行控制規則

### 一個持久任務帳本，Hermes 只做指揮

在 `control-host` 或另一台固定的控制主機跑**單一寫入協調器**；Hermes、cron、`batc`、`host-a` 的 OpenClaw 都透過它查詢或派工。先用 SQLite WAL 加單服務實例即可，若以後多實例才換共享資料庫。每個任務固定 `task_id`、原始 Discord 訊息與 thread、Ted 原文、標示清楚的 Hermes 解讀、專案／worktree、執行器與目前 owner。`relay.py` 保留原文和解讀分開、讓 coding session 產出 fan-out 計畫，這點研究說得對；需要修正的是 fan-out 後仍由協調器記錄每個子任務，不能靠 Hermes 記憶。

每次變更先在交易中寫 `command_id`、idempotency key、owner 與 `control_version`，再呼叫 BAT 或本機執行器。階段至少有 `reserved → dispatching → accepted → running → terminal`，另有 `uncertain`。同一 Discord 訊息／票號、同一邏輯動作不得再造第二張票；15 分鐘 watcher 只讀 task event 並以 `(task_id, event_id, Discord thread)` 去重發文。5 分鐘派票 cron 要搶同一筆原子 reservation，不能與其他控制者各自啟動。Grok Bot 管 VM 健康、額度及例外，不進逐票催工；Hermes 管新指示與跨任務協調；等待、權限狀態、定期進度、重試與完成檢查交給服務。停止／接手是確定性的控制命令，先由程式處理，不能把「請停」丟給另一個模型猜。

連線逾時時保持 `uncertain`，先查 session 狀態、echo、rollout／程序日誌與工作樹，再決定是否重試。Claude 在同一 BAT sidecar 的 `clientMessageId` 可去重，但重啟後其記憶不能當永久收據；BAT Codex 根本不沿用這個 ID。**絕不可因 `session_wait` 逾時就重送新的 Codex prompt 或再建 failover。** 無法證明未被接受時，標記待對帳並提醒負責監看的 agent，不把模糊狀態報成失敗或成功。所有既有 MCP／`batc` 名稱可當相容入口，但必須共用同一帳本，否則多個本機鎖只是局部保護。

### 若仍用 BAT 原生代理執行

PR #1 在 [service.py](../../src/bat_agent_connector/service.py) 對 Claude 用精確 `clientMessageId` 對 echo，把訊息 ID 與時間游標分開；排隊回合在不能確定邊界時保守標 `queued_unconfirmed`。這修正 Part 1 Finding 1 的主要錯誤，卻不會讓舊回合最後輸出自動帶新命令 ID。BAT Codex 的 [Rust 路由](https://github.com/tony1223/better-agent-terminal/blob/5a61d43/src-tauri/src/commands/claude.rs) 丟掉 `clientMessageId`，其 user echo 自建 `user-<time>`；目前 timestamp fallback 是弱證據，而且若 session 正在跑，新送入的 Codex prompt 可能**中斷並取代**原 turn，不應當作 Claude 式佇列。

不改 host 的 Codex 對帳可以把下列線索合用，但都不能單獨作成「恰好一次」保證：

1. **送前／送後狀態輪詢。** 記下 `sdkSessionId`、`numTurns`、`isStreaming`、最新訊息 ID／時間，再在同一 session 空閒時送出，確認新增 user echo 與 turn 計數。僅在一個協調器且無 GUI 同時送話時，時間差才有意義；斷線或被他人送話時降級成 `uncertain`。
2. **內容雜湊。** 對協調器實際送出的完整 bytes 計 hash，和新增 user echo 的內容比對。可把短命、無權限的命令 nonce 放入提示作輔助，但 BAT 可能改顯示文字、重複 prompt 也會同 hash，且 hash 不能證明主機接受後是否跑完。不要把 nonce 寫進 Ted 原文段落。
3. **Codex rollout。** 若主機有唯讀檔案存取，可用 `sdkSessionId` 定位 `~/.codex/sessions/` 的 JSONL，核對 user 訊息、turn／工具事件、mtime／offset；讀取要處理延遲寫入、輪替、重啟、隱私與版型變動。BAT 的 `claude:list-sessions(agentKind=codex)` 會掃所有 rollout，可能很慢，不宜每次 wait 都調用；遠端 API 也不能保證直接讀取 rollout 檔案。用主機端唯讀 helper 比持續全量掃描合理。
4. **工作樹與輸出。** git diff、HEAD、狀態及代理回覆能證明有工作發生，不能單獨證明是哪一個送話觸發。若兩個指令內容相似、GUI 插手或事件缺失，維持不確定狀態。

因此 BAT 路線要一個 automation-only session／worktree 只容一個 writer，`queue=false` 為預設；新命令等前一回合明確終止後再送。Ted 若要接手**這份工作**，協調器先停止新派工、升級 `control_version`、要求目前回合停止並輪詢到 idle，記下 HEAD／未提交變動與最後訊息，再讓 Ted 在他可見的 BAT 工作空間開啟該 repo／worktree 繼續。這是**工作交接，不是同一個自動 session 的 GUI 接管**。若未來 Ted 手動打開同一個 BAT session 並輸入，協調器只能偵測意外 user echo／turn 數或檔案變化後暫停；**無 BAT host-side ownership gate，就無法阻止檢查與送話之間的競態**。人接手後不自動恢復；需明確歸還權限與重新對帳。自動 session 維持不註冊頁籤，避免 GUI 存檔競態；詳細內容由 Dashboard 顯示。

### 候選版本、測試和清理

把 `TURN_FINISHED`、代理宣稱完成、`VERIFIED_CANDIDATE`、准許合併分開。[verification.py](../../src/bat_agent_connector/verification.py) 與 PR #1 已要求候選 HEAD／乾淨工作樹、測試命令、exit code、環境和日誌參照；新 commit 或髒工作樹使舊證據失效。下一步應由受控 runner 真正執行測試、存不可隨口杜撰的 log，再把 hash／結果寫帳本；目前 `session_record_verification` 仍是**呼叫者提供的聲明**，不是 BAT 自行驗證。`BAT-STATUS: MILESTONE` 只表達代理說到一個里程碑，Jev 只協助分流，兩者都不能替代執行證據。若測試後又改檔，重做驗證。對一個 clean、已驗證且政策允許的候選，可自動執行可回復的本地清理／合併；push、公開發佈、機密、金錢、破壞性或不可逆操作依 Ted 的授權界線處理。不要把頻繁的例行「完成了嗎」交給 Grok Bot 詢問。

## 三種架構的取捨

| 路線 | 在這五台主機上的實際作法 | 優點 | 缺點與適用條件 |
| --- | --- | --- | --- |
| **A. 協調器 + BAT 原生 Claude／Codex** | Hermes 與 crons 只用 task MCP；協調器轉給現有 connector，session／worktree 隔離，交接工作前停派 | 沿用既有 relay、額度切換、BAT 原生 runtime 與程式投資，適合遷移期或實測更佳的任務 | **目前 Ted 看不到這些 session。** Codex 無可靠命令 ID；BAT 事件不持久；自動頁籤有整份覆寫競態。不能再拿「Ted 可從 GUI 看同一 session」當採用理由 |
| **B. 協調器 + 主機 Codex CLI／Claude Code headless（目標預設，待實測）** | 在 `host-a` 至 `host-e` 等執行主機跑受控程序與獨立 worktree；程序輸出／rollout／exit 存到 task journal；Dashboard／Discord 看結果 | 一次性任務有明確程序生命週期、退出狀態、日誌和取消；不經 BAT 的 Codex 回合猜測與 workspace 頁籤存檔 | 需實作可信 runner、額度／身分設定和日誌留存；須驗證與 BAT runtime 的品質及訂閱差異。Ted 接手時先停程序、保留 worktree，再用自己可見的 BAT session 開啟，對話脈絡靠交接摘要與檔案 |
| **C. Goose／其他 harness 作可選執行器** | 協調器只讓指定任務使用 Goose ACP，Goose 讀 task-scoped MCP 工具；或評估它直接執行 coding | 可選一致的 agent 工作流程、工具限制與局部判斷 | 另需模型供應商、授權、恢復與成本；Goose `ActiveRunRegistry` 只保護 Goose session，不鎖 BAT／Git；不會自動解決 Discord 去重與驗證。僅在實測比 B 或 A 少監督時加入 |

路線 B 下 BAT 是 Ted 的**手動開發工具**，不是自動任務的觀察來源；若他開了相同 repo 的 workspace，也可看檔案、Git 或終端日誌。Codex CLI 的 `apply_patch` 不會神奇變成 BAT Codex 面板內容。既然 A 的自動 session 也不可見，Dashboard 必須提供可追查的輸出與執行紀錄，不能只顯示一個綠點再叫 Ted 回 BAT。只在本機 loopback 開 HTTP；要從其他主機或手機直連，先有明確身分驗證、授權、傳輸保護與操作稽核。對五台主機的現有 BAT token，不要再開放一個未授權的網路寫入 API。

## 對兩部分研究與 PR #1 的評價

| 研究主張 | 評價 |
| --- | --- |
| Part 1：連接器為基礎，Goose ACP 可選；不要讓 Goose 代替確定性的狀態查詢 | **同意前半，修正「最佳預設」。** 現有 connector 是 BAT 路線最省力的相容入口，Goose 也適合選擇性解讀；但自動 session 根本不在 Ted GUI、BAT 又不可改，沒有理由只為 GUI 保留 BAT 作自動化核心。先比較直接 headless runner |
| Part 1 Findings 1 至 5 | **1、3、5 核實且 PR #1 有連接器修正；2、4 只能部分緩解。** 1 的 Claude UUID echo 精確對應已修；Codex 仍用弱游標。3 的 `flock` 原子 failover 只保護同一狀態目錄。5 的驗證紀錄綁候選版，但來源仍須可信。2 的本機鎖不管其他程序或 GUI；4 的整份 workspace 存檔競態不可由重試消除 |
| Part 1：共享協調器、所有人共用 task ID／journal／owner | **同意，而且比增加模型層更急。** 目前 `control-host`、`host-a` 的 OpenClaw、cron 的控制面分散；Ted GUI 不在自動 session 內，這個特定競態比研究假設低，但 `control_version` 仍只能拒絕經協調器的舊命令。先只做一個服務、少量 task MCP 與可看證據的唯讀頁，避免一開始建龐大平台 |
| Part 1：Goose ACP resume／MCP | **有條件同意。** 已檢查的 Goose 原碼有 ACP resume 與每個 Goose session 的 active-run 限制；仍需在實際版本、供應商及斷線情境測試。Goose 不是 BAT owner，不能修復 GUI 搶寫或 Discord thread 映射 |
| Part 2：借 Buzz 單任務邊界、期限、取消與結構化結果，不搬整套平台 | **同意。** `run_task.rs` 與 `isolated_execution.rs` 提供清楚的一次性執行合約。要再補一個耐重啟去重帳本和測試驗證器；Buzz 的 `taskId` 是關聯 ID，非永久去重收據。Buzz 完整 relay／Postgres／Redis／MinIO 對現有 Discord 流程成本過高 |

上一版[設計](next-gen-connector.md)提出 BAT 上游 `workspace:add-terminal`、Codex `clientMessageId` 與 host ownership gate，這些在長期研究上合理，**但本評估的任何可行方案都不依賴它們，也不把上游 PR 當待辦前提**。PR #1 是已發生的連接器改善，不能把其保守 `turn_phase` 解讀成 BAT 提供了通用 transaction ID。

## 有順序的建置計畫

**第一個小里程碑：一台主機、一個 repo、一張任務。** 先選 `host-a` 的非正式服務 repo，沿用現有 BAT connector 當執行器，新增最小 task journal、`task_submit/status/events`、Discord thread 映射與簡單唯讀 task 頁／`batc task status`。Hermes 送出後即取得 task ID 並結束長等待；背景 worker 短輪詢 BAT、持久保存狀態變化、以 event ID 去重發文。這一階段**不做 Goose、不換執行器、不自動合併、不註冊 BAT 頁籤**。驗收：Hermes 重啟或 Ted 在等待中插話後仍可用同一 task ID 找回進度；重送同一 Discord 指示不產生第二個 BAT prompt；同一進度不重貼 Staging 舊報告；頁面看得到最後事件、工作樹、卡點和原始日誌參照。若 BAT 接受與否無法確認，畫面明示 `uncertain`。

第二步，讓 `control-host`、`host-a` 的 OpenClaw、5 分鐘派票及 15 分鐘 watcher 全部改走同一帳本，導入既有 connector registry；舊 `batc` 命令維持相容，禁止另一份隱形 owner。同時核對 `bat-freshturn-guard` 的能力授權，但去重與追蹤由服務本身保證。Dashboard 補上時間線、輸出分頁、failover 關係、候選 commit、測試與成本；不要把未追蹤的完整 transcript 都塞回 Hermes 的 45k 至 48k 基礎 prompt。

第三步，在一台開發主機加入**受控 headless runner 試點**，先跑容易驗收的 Codex／Claude 任務；可信設定決定 executable、cwd、工具權限與期限，任務文字不決定這些能力。保存程序 ID、標準輸出、rollout、exit code、取消結果及 log；由獨立 verifier 對候選 commit／tree 執行測試，生成不可由 agent 自填的證據。比較同一批任務的 BAT A 與 headless B：已驗證交付數、人工介入分鐘、重工、斷線恢復、實際額度與成本。**只有 B 達到品質和認證／額度需求，才把它升為新任務預設**；既有 BAT session 可繼續完成。

第四步，才擴到五台主機的 owner／控制版本、配額切換、確定性停止與工作交接、風險分級清理。合併前重查 HEAD 與 dirty tree；測試通過後改碼必須失效，`MILESTONE`、Jev 或 watcher 文案不得放行。正式環境服務的變更要按 Ted 授權界線另立操作政策，不能沿用開發 repo 的自動清理規則。Grok Bot 的磁碟、版本、登入、skills 與訂閱盤點可讀同一證據理念，但不必強迫進 coding task schema。

第五步，只有 Hermes 仍需反覆閱讀底層輸出作局部續推，才以**有限任務**評估 Goose ACP＋task-scoped MCP；Jev 只在不確定分類上做試驗。Goose 的模型／provider、resume 與取消傳遞要實測，不能因 ACP 介面存在就假定恢復可用。Buzz 借用執行契約即可；若不取代 Discord 或 Dashboard，不部署整套平台。

驗收案例至少包含 BAT 真實 `batc-<uuid>` Claude echo、排隊送話後舊回合輸出、Codex 重複 prompt／rollout 比對、兩個控制器同時 failover、GUI 存檔撞上頁籤註冊、主機接受後立即斷線、Discord 等待遭新訊息中斷、Hermes 重啟後重貼防護、headless runner 取消後程序仍存活，以及測試成功後再修改程式。預期可達成的是「任務持久可見、狀態不確定時不亂重送、可停止並對帳」；在 BAT 不改版時，**不能承諾所有 BAT Codex 命令恰好執行一次，或完全無競態的同 session GUI 接手**。
