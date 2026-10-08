# 統一寫入操作與 Task Service 控制閘門

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §09、§10、§24，W01／W04 剩餘工作，驗收 A01、A05、A07、A08、A09。

本文依 2026-10-08 規格審查決議修訂。Part A 已實作 Task Service authority；Part B 保留第二步合約。交付狀態以本文件、測試與 api-v1/task-service 文件為準。

## 分段交付與審查決議

- **Part A（本次）**：Task Service authority。共用 coordinator gate 先套到現有 ActionDefs 與低階 service/lifecycle 路徑（包括 client-resume、permissions、approve-pending／deferred raise、relay）；task 操作連到原 commands 與同交易回執；canonical owner lock、owner-first 初始化與 A07／A09／task A05 測試。
- **Part B（後續分支）**：舊 session／orchestration MCP／CLI 的 operation 轉接、無 key sentinel 與讀取投影、完整結果與未知布林 null、外部 steps 拆分、A01／A05／A08 全入口測試。本文的舊工具映射、逐工具結果投影、外部步驟拆分與 standalone failover 正面停筆證據保留為第二步。
- Part A 不改 `OperationService.create` 的 admission 順序或 operations schema。policy admission 拒絕仍 403、沒有 operation；執行中才發現的拒絕仍為 failed operation。
- Part B 無 key 呼叫在原 NOT NULL 欄位保存 `batc:nokey:<operation_id>`：只作唯一的儲存值，絕不與另一要求去重。拒絕 client key 使用 `batc:nokey:` 前綴（422）；所有讀取投影 `idempotency_key: null`、`idempotency_enabled: false`。**不 rebuild operations，不需此項 schema migration**。
- 舊 task control 沒有 key 的 RPC 在 Part A 使用每次呼叫獨立的 request key，不提供跨呼叫去重；Part B 才統一 no-key sentinel 與投影。明確給 key 的 task actions 現在即須符合 A05。

## Part A 實作對照

`task_actions.py` 註冊 task.submit／pause／resume／mark_stage／verify／request_ted／command.reconcile；task_send 使用原 session.send 的 `{task_id}` target。`task_control.py` 是 service/lifecycle 的共用 gate，轉交 daemon 原 coordinator；journal 的 current session、start reservation、branch 仍是 ownership 證據。任意 callback 不再跳過 gate。只有既有 command 綁定的 send、原受信 verifier 與 pause 版本的 abort 使用內部 FrameGuard。permissions、relay、批次 approval 與 deferred raises 尚是 legacy 路徑，但 A07 已生效；cleanup 只加 ownership／stop 邊界保護，沒有 Part B step 拆分。

`OpContext.effect` 與原 Journal.tx 的巢狀 savepoint 保存同交易 receipt；沒有 schema migration。task/send linkage 使用 external_refs、command payload 與 operation_steps response，不新增派工資料表。pause local effect 不等待 task lock，abort step 再按 task → session → host → BAT semaphore 順序執行。受信 verifier 在啟動 runner 與保存 evidence 前重查版本；caller 不能以外部 verification 取代它。未知 send 不重送；answer/interrupt 的正面 readback 可交原 coordinator，無法證明的 permissions 保留 uncertain，原 command capability 可作一次性人工對帳。

task.verify／task.request_ted 的 paused／state 規則，以及 task.mark_stage 的 verified done 規則，與 principal／capability／engine 檢查分開。admission 沿用原順序與拒絕碼；執行取得 task lock 後，在第一個 effect／receipt intent 前重查 admission binding，再跑同一 state check。等待鎖時版本改變先回 CONTROL_VERSION_CONFLICT；同版本下 task 完成、暫停或失去 verified done 條件仍以 TASK_PAUSED／TASK_STATE_BLOCKED failed。task、verification／delivery、events 與 commands 不變。已有 succeeded receipt 的 worker replay 先回原 receipt，不因後來的 state／version 改變而重做 effect。task.pause／resume 的本機 effect 前沒有 await，交易內重查版本，原 journal 保留 terminal task；pause abort 的等待只發生在 pause receipt 之後。task.command.reconcile 在 task lock 下重讀 command，原 journal 交易再查 uncertain task／command 與 capability，並在最後提交前重查版本，不套用只供派送的 scoped state 規則。

舊 task 結果只新增 operation_id／operation_status。無 key 舊 controls 為獨立 request identity；task_send 未指定 key 時以 task_id＋原 step_id 保留 retry 身分。舊 work_submit 201–256 字 key 在 adapter 保存原字串並作 SHA-256 operation-key 映射（不改 create 的 200 字限制）；只有 local-admin work_submit 相容入口可寫歷史 task-key bridge receipt，HTTP 一般 actor／新 API admin submission 不追認歷史 key。bridge 與 operation admission 在同一外層 Journal.tx 提交；中途 crash 不會留下可錯建新 task 的孤立 intent，create 的 admission 順序不變。reconcile capability 明文不入 operation；消耗後只能重讀相同 actor/key 的原 operation。

runtime Codex send 保留舊 accepted 欄位，但 ACK 不是 task 的回合證據。沒有 exact echo 時交原 coordinator 的 command readback；證據不足就維持 task／command uncertain，拒絕下一個低階 send。Part B 才改未知效果的 null 投影。

CLI task-reconcile 帶 --key 時，原 admin-only capability issuer 以既有 admin secret 綁定 task／command／key，使重試取得同一 capability 身分。capability 仍只保存 hash、一次性消耗、10 分鐘期限；consumed capability 只能取回自己相同 key 的原 operation。沒有 key 時保留原每次新發 capability。issuer 不執行 reconciliation，也不讓 admin token 代替 command capability。

Part A 的可執行測試在 `tests/test_operations_unification.py`，加上既有 service/task/API tests。A05 包含 actor/key 衝突、所有 task actions、原子 rollback／restart／capability 消耗；A07 包含 legacy/API gate、每種 pending command、晚到版本/owner/frame、client-resume、permission channels、approval/deferred raise/relay、Goose 不自鎖與 pause abort；A09 包含不同 journal、owner metadata 不變、過期 heartbeat 不接管、第二 client 走中央 owner與重啟續用 journal。`tests/test_operations_delivery_seams.py` 另驗證 effect receipt 不被當成 delivery write、巢狀 effect 失敗只 rollback 自己的 savepoint，以及停止的 merge reconcile 保留 request 供後續讀回。A01/A05/A08 的全 legacy 入口驗收仍是 Part B，不能由這批 task 測試宣稱完成。

## 固定來源版本

| 來源 | 固定版本／位置 | 用途 |
|---|---|---|
| Connector | `0.2.4`；`feat/ops-unify` 起點與 `origin/main` 均為 `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b` | 本文入口清單、SQLite schema、coordinator 與 owner 行為均逐項對照此版。 |
| 計畫 | v1.0，2026-10-06，§09、§10、§24、§26、§28 | 合約與驗收依據；不將私人計畫複製進 repository。 |
| BAT 協定筆記 | [PROTOCOL.md](../PROTOCOL.md)：BAT **v3.2.12**、`bat-remote/v2`；上游 `src-tauri/src/remote_server.rs`、`remote_core.rs`、`node-sidecar/src/handlers/*` | 沿用既有 channel，沒有新增任意 RPC／shell 寫入通道。 |
| BAT 對照基準 | 計畫 §03 固定 `b7419892fbc9946799b64cca24c2ec8c7fa15c42`；另見 [next-gen-connector.md](next-gen-connector.md) 記錄的 `5a61d43` 靜態檢查，`node-sidecar/src/handlers/claude-send.mjs`、`src-tauri/src/commands/claude.rs`、`codex_app_server.rs` | 區分 Claude 的 `clientMessageId` echo 與 Codex 的弱游標證據。兩個快照不混稱同版；本次未重新驗證上游或實機部署版本。 |
| 既有設計 | [api-v1.md](api-v1.md)、[task-service.md](task-service.md)、[resource-policy.md](resource-policy.md)、[交接](../handoff/2026-10-08.md) | 沿用 OperationService、TaskCoordinator、journal、WriteGrant 與 owner lease。交接記錄的舊 head 不取代上述起點。 |

## 現有與新增行為差異

| 現況（已核對程式） | Phase 2 行為 |
|---|---|
| `mcp_server.build_server` 的 7 個 write tools、8 個 session orchestration tools，以及 `cli._run` 直接進 `service`／`lifecycle`／`orchestrate`。 | 名稱保留；adapter 只整理輸入、向既有 daemon 提交 action、投影結果。所有實際寫入均先有 operation。 |
| HTTP 已有 `session.send`／`answer`／`interrupt` ActionDef；舊工具未共用。 | 舊 send／continue 共用 `session.send`；answer／interrupt 共用原 ActionDef；補齊其餘能力。 |
| `work_submit`／`pause`／`resume`／`mark_stage` 在 `TaskDaemon.call` 修改 task journal，沒有 operation。`task_scoped_mcp.build` 另有 3 個 mutation tools。 | operation 連到原 task／commands／events；task state 仍由 TaskCoordinator／Journal 決定。 |
| `service._task_send_block` 只查 `tasks.state`：讀不到時 fail closed，`verifying` 時擋 send／answer。interrupt／permissions 沒有此檢查。 | 所有入口使用同一 coordinator gate，檢查 ownership、paused、state、待對帳命令、control version；執行與 frame 邊界再次檢查。 |
| `OperationService.create` 要 key，`operations.idem_key` 為 `NOT NULL`；task key 則是全 journal 唯一。 | 舊入口可省略 key，省略時明確沒有去重保證，不偷偷產生 key。有 key 時以驗證 actor 去重，包含 task 控制。 |
| `TaskDaemon.acquire_owner` 鎖 `<journal.parent>/task-daemon.lock`，鎖失敗只報 `RuntimeError`。 | 沿用同一個 acquire／release 與 flock 機制，固定同 fleet 的鎖定位，衝突回既有 owner 資訊。 |

`lifecycle.main_session` 已排除 task-owned session；`lifecycle._evaluate` 對 task-owned session 已回 `KEEP`。保留這兩項保護。`TaskCoordinator._tick` 目前遇 `quota_limited` 轉 `needs_ted`，不啟用中途 failover；也不恢復已移除的 reviewer／路由流程。

## 唯一寫入路徑、身分與前置條件

HTTP `/api/v1/operations`、MCP、CLI 與相容 `POST /rpc` 都進入同一個 `OperationService`，共用 `ActionDef` 的 schema／scope／admission／handler／result／errors。各 adapter 不選模型、不複製派工狀態機、不直接建 Fleet 寫 BAT。daemon 不可用回 `OWNER_UNAVAILABLE`，不在 client 自動啟動 daemon 或建立另一 journal。

1. 驗證身分、scope、confirm 與輸入格式。MCP fleet mutation 使用 `BATC_API_TOKEN`，沿用 `principal_daemon` 的原則，不退回本機 admin token。CLI 使用明確的 API token；沒有該 token 時，既有本機 0600 admin token 的路徑保留為 `local-admin`。task／command capability 仍由 Journal 驗證。
2. 將語意相同的 alias 正規化成同一 action／params，核對明確的 key。transport、wait 時間、confirm、輸出格式不進 request hash；會改變效果的選項與呼叫者提供的 preconditions 都進 hash。
3. 保留既有 admission 順序：身分、格式、key/replay、資源政策與 coordinator admission 通過後，先持久保存意圖才執行 mutation。admission 拒絕不建立 operation；執行中才發現政策／task 條件改變時，原 operation 記 failed。
4. 執行前做即時 policy；task-owned 再經 coordinator。每個 BAT／Git／provider mutation 都是一個 intent 已提交的具名 step。已完成 step 重讀結果；未知結果只 reconcile。

Policy admission 拒絕保留 HTTP 403 與政策碼，不讓未受理要求增加 journal。replay 已存在 operation 時先檢查身分／scope 與 hash，再回原紀錄，不重新套用 admission 或重做副作用。

host 的 `writes`／`orchestrate`、`read_only`、rate limit、session cap、`default_permission_mode`、confined session 規則均繼續有效。MCP 原本有 confirm 的工具仍須 `confirm=true`；`work_*` 與 task-scoped tools 原本沒有 confirm，保留已授權提交的相容語意。`--read-only` 在 CLI adapter 也須擋所有 daemon mutation，包含目前在 `main` 先分流的子命令。讀取入口與純 dry run 的註冊／結果不變。

## 每一個現有寫入入口的映射

以下表格是起點的完整外部 mutation 盤點，含只改 connector 資料的工具。`—` 表示該 transport 今天沒有專用入口。`OP` 是 **`POST /api/v1/operations`**，body 的 `action` 指向該列；Phase 2 不增設另一組 session／task 寫入路由。所有 RPC methods 都使用現有 **`POST /rpc`**，不是新增 URL。HTTP 的 action 能力以 daemon 註冊的 ActionDef 為準。

Policy 縮寫只描述既有檢查，實作仍呼叫 `resource_policy.py`：

| 記號 | 政策與實際效果 |
|---|---|
| S | `authorize_session`：managed provenance、connector-owned folder、live binding、對應 tier。送字／answer／permissions 要 live folder；interrupt／stop 按既有規則只核對 session binding。每個 channel 都須 WriteGrant。 |
| N | `authorize_new_session`／`check_new_worktree`／`authorize_shared_session`：先預留 ID、核對目的端、managed root／自有 worktree、cap；tab 另經 `authorize_register_tab`。 |
| W | S ＋ BAT worktree 身分；rehydrate／merge／remove 拒絕 SSH 建立的 worktree（`NOT_A_BAT_WORKTREE`）；merge 另核對目的端在 managed root。 |
| T | 只寫既有 task journal，不因 task link 認領任何 session。若實際派送／interrupt／SSH Git，仍走 S／N／`authorize_external_worktree`。 |
| C | checkpoint 來源只讀；continue 的 clone／worktree 按 `check_checkpoint_worktree` 等既有檢查，新 session 按 N。 |
| I | 既有 integration area／push／repair path 政策；人的 repository 只作讀取來源。 |
| L | 只改 connector 管理資料；不授予 BAT／Git grant。既有版本／fingerprint／order 前置條件保留。 |
| D | 既有 GitHub allowlist、merge／deploy recipe、head SHA 與環境 gate；不碰人工 BAT／Git。 |

Coordinator gate：`G`＝下面的 task-owned runtime gate；`TC`＝原 task 控制方法；`R`＝原 command-scoped reconciliation；`F`＝task-owned failover／worktree／cleanup 不由低階工具執行；`—`＝沒有 task runtime 控制，但連結絕不授予控制權。新 action 名稱是本文的實作合約。

### 舊 session／orchestration 工具與 CLI（Part B；Part A 先加共用 gate）

| MCP tool（今天） | CLI command（今天，省略 `batc`） | HTTP（今天 → Phase 2） | Action | Scope | Policy | Coordinator gate |
|---|---|---|---|---|---|---|
| `session_send` | `send` | OP（已有） | `session.send` | operate | S；含 client-resume | G |
| `session_continue` | `continue` | — → OP | `session.send`，預設 text=`continue` | operate | S；含 client-resume | G；queue 不是 task queue |
| `session_answer` | `answer` | OP（已有） | `session.answer` | operate | S | G；鎖定 prompt ID |
| `session_interrupt` | `interrupt` | OP（已有） | `session.interrupt` | operate | S | G；verifying／paused 時改用明確 task 控制 |
| `session_set_permissions` | `permissions` | — → OP | **新增** `session.permissions` | operate | S；confined 不升 allow-all | G；每個 permission channel 都查版本 |
| `approve_pending`（非 dry run） | `approve-pending`（非 `--dry-run`） | — → OP | **新增** `session.approve_pending` | operate | 每項 S；跳過 read-only／confined | 每項 G，含 `_raise_deferred` |
| `session_relay`（非 dry run） | `relay`（非 `--dry-run`） | — → OP | **新增** `session.relay` | operate；實際建新 session 另需 start | S／N；來源只讀 | G；自動挑選仍排除 task-owned |
| `session_start` | `start` | — → OP | **新增** `session.start` | start | N | 不接受 client 自報 task owner；由 task.submit 建 task session |
| `worktree_merge` | `merge` | — → OP | **新增** `worktree.merge` | integrate | W，含目的端 | F |
| `worktree_remove` | `remove-worktree` | — → OP | **新增** `worktree.remove` | operate | W | F |
| `session_failover`（單個／`all_exhausted`，非 dry run） | `failover`（非 `--dry-run`） | — → OP | **新增** `session.failover` | start；handoff 另需 operate | S／N；force 不能取代 policy／停筆證據 | F；task 中途 failover 保持拒絕 |
| `session_cleanup`（`dry_run=false`） | `cleanup --apply` | —；409 `LEGACY_CLEANUP_DISABLED` | 不新增 action；apply 由 cleanup package 封鎖，本包不包裝 | — | apply 不寫 BAT／Git；dry run 保持唯讀 | reviewed cleanup 交 cleanup package 的 `cleanup_preview`／`cleanup_apply`／`cleanup_restore` |
| `session_record_verification` | `record-verification` | — → OP | **新增** `session.record_verification` | operate | 只寫 verification.json；讀乾淨候選，不授權外部 mutation | task-owned 拒絕外部證詞取代受信 verifier |
| `fanout_plan_session` | `fanout-plan` | — → OP | **新增** `fanout.plan` | start | N；新 planner 自有 worktree | 不改來源 task；保持原 planner，不新增規劃機制 |
| `fanout_from_plan`（非 dry run） | `fanout-start`（非 `--dry-run`） | — → OP | **新增** `fanout.start` | start | 來源只讀、逐項 N；不能經 legacy apply 清理 planner | 回報 `LEGACY_CLEANUP_DISABLED`，保留 planner 交 `cleanup_preview`；不插入來源 task commands |
| — | `fanout PLAN --start` | — → OP | `fanout.start`，params 帶檔案讀出的固定 plan | start | 逐項 N | 同上；client 不逐項直接 session_start |

`integrate` 是既有成果整合 scope；在此也用於會改 managed Git 目的端的 worktree merge，與 GitHub `merge` 分開。worktree remove 用 operate 並保留 host orchestrate tier，不新增 scope。reviewed cleanup 的 scopes 與寫入路徑由 cleanup package 定義。組合 action 的額外 scopes 在寫入意圖前檢查；不能先做一部分才發現沒有權限。

### Task Service 與 task 專用 MCP（Part A）

| MCP tool（今天） | CLI（今天） | HTTP／RPC（今天 → Phase 2） | Action | Scope／驗證 | Policy | Coordinator gate |
|---|---|---|---|---|---|---|
| `work_submit`（含 `continuation=true`） | — | `/rpc work_submit` → 同名轉接＋OP | **新增** `task.submit` | start；舊 RPC local-admin | T；後續派送 S／N | TC；原 submit lock、提交／continuation，不改 recipe／engine 決策 |
| `work_pause` | — | `/rpc work_pause` → 同名轉接＋OP | **新增** `task.pause` | operate | T；abort 時 S | TC：`TaskCoordinator.pause`；先持久 pause／control_version |
| `work_resume` | — | `/rpc work_resume` → 同名轉接＋OP | **新增** `task.resume` | operate | T | TC：`Journal.resume`；下次 tick 先 reconcile |
| `work_mark_stage` | — | `/rpc work_mark_stage` → 同名轉接＋OP | **新增** `task.mark_stage` | manage | T；不執行 GitHub／deploy | TC：`Journal.mark_stage`，只對 verified done task |
| task-scoped `task_send` | — | `/rpc task_send` → 同名轉接；OP 僅受限驗證身分 | `session.send`，target={task_id}，實際 session 第一次綁定 | 原 task capability；只限此 task／session | S | G＋coordinator send；保留 step_id 與 command reconcile |
| task-scoped `task_run_verification` | — | `/rpc task_run_verification` → 同名轉接 | **新增** `task.verify` | 原 task capability；不開放一般 scope token 代填測試 | T；受信 runner 的原工作區政策 | TC；鎖定 candidate commit/tree，拒絕 caller 自報 evidence |
| task-scoped `task_request_ted` | — | `/rpc task_request_ted` → 同名轉接 | **新增** `task.request_ted` | 原 task capability | T | TC；原 request_ted event＋合法 state change，同交易回執 |
| — | `task-reconcile` | `/rpc work_reconcile` → 同名轉接 | **新增** `task.command.reconcile` | 原一次性 task／command capability；admin 不能直接代替 | T；next_prompt 寫入另走 S | R：`TaskCoordinator.resolve_command`，不 replay 舊字 |

CLI 今天沒有 task submit／pause／resume 子命令，不能把不存在的命令列成已提供。這些 action 可先由 OP／`operation_submit` 使用；若 Phase 2 提供 `batc task submit|pause|resume`，只是同一 action 的薄轉接，須另列新增命令與契約測試。既有 `task-reconcile` 一定納入，不因今天沒有一般 task CLI 而漏掉。

### 已走 OperationService 的入口（保留，納入全入口契約測試）

以下各 action 今天均可由 `operation_submit`、`/rpc op_submit`、OP 呼叫。除特別註明外沒有專用 MCP tool。表中的 CLI 為現有命令；全部沿用原 ActionDef，不另複製 handler。

| MCP 專用 tool／CLI | HTTP route | Action | Scope | Policy | Coordinator gate |
|---|---|---|---|---|---|
| `checkpoint_create`／`checkpoint create` | OP | `checkpoint.create` | operate | C；來源含 manual／unknown，只讀 | —；不操作來源 runtime |
| `work_continue_from_checkpoint`／`checkpoint continue` | OP | `checkpoint.continue` | start | C／N | 新 standalone session；來源只讀，不觸碰 task owner |
| —／— | OP | `github.pr.merge` | merge | D | — |
| —／— | OP | `deployment.start` | deploy | D | — |
| —／— | OP | `delivery.merge_and_deploy` | merge＋deploy | D | — |
| —／`integrate preview` | OP | `integration.preview` | integrate | I；preview 寫 connector area | — |
| —／`integrate apply` | OP | `integration.apply` | integrate | I；normal push、PR head 前置條件 | — |
| —／`integrate handoff` | OP | `integration.handoff` | integrate＋start | I／N | 新 confined repair session，不接管來源 task |
| —／`project create` | OP | `project.create` | manage | L | — |
| —／`project update`（含 archive／restore） | OP | `project.update` | manage | L；expected_version | — |
| —／— | OP | `project.order` | manage | L；原順序前置條件 | — |
| —／— | OP | `project.pin` | manage | L；原 pin 前置條件 | — |
| —／`item create` | OP | `work_item.create` | manage | L | — |
| —／`item update`（含 check／uncheck、archive／restore、完成聲稱） | OP | `work_item.update` | manage | L；expected_version | — |
| —／— | OP | `work_item.order` | manage | L；原順序前置條件 | — |
| —／— | OP | `work_item.pin` | manage | L；原 pin 前置條件 | — |
| —／`item approve` | OP | `work_item.approve` | approve | L；expected_fingerprint | —；task 結果連結不是替 task 放行 |
| —／`item continue` | OP | `work_item.continue` | manage | L；expected_fingerprint | — |
| —／`item link`（含 `--remove`） | OP | `work_item.link` | manage | L；連結不授權資源 | — |
| `operation_submit`／— | OP；`/rpc op_submit` | 指定的任何已註冊 action | 依 action | 依 action | 依 action |
| `operation_cancel`／`op ID --cancel` | `POST /api/v1/operations/{id}/cancel`；`/rpc op_cancel` | 原 `OperationService.cancel`，不新增 action | 原 actor／admin／目標 action scope | 操作紀錄控制；未證明 step 仍須回查 | 不等於 task.pause；已提交 task 不撤回 |
| `operation_resume`／`op ID --resume` | `POST /api/v1/operations/{id}/resume`；`/rpc op_resume` | 原 `OperationService.resume`，不新增 action | 原 actor／admin／目標 action scope | 操作紀錄控制；只允許 needs_attention | 不等於 task.resume；task gate 不會失效 |

Operation cancel/resume 保留原 endpoints、authorization 與 events；不新增 control operation、key 或 target-dependent ActionDef 授權。它們不等同 task.pause/resume。

### 管理憑證與本機初始化：明列邊界

| 現有入口 | 將使用的 action／邊界 | Scope | Resource policy | TaskCoordinator gate |
|---|---|---|---|---|
| `api-token issue`；`/rpc api_token_issue` | 原短 connector-data RPC；不新增 operation | local-admin 專用，不可發行可冒充 admin 的 scope | 只改 api_principals，不寫 BAT | — |
| `api-token revoke`；`/rpc api_token_revoke` | 原短 connector-data RPC；不新增 operation | local-admin 專用 | 同上 | — |
| `task-reconcile` 的前置 `/rpc work_reconcile_capability` | 原 admin-only capability 發行 RPC；reconcile 本身是 operation | local-admin 專用；一次性 command capability | 只改 capabilities，不放明文 token 入 operation | R；限 uncertain command 與原 10 分鐘期限 |
| `import-bat`（output 為檔案，含 force） | 本機安裝／設定初始化，**沒有 fleet action**；審查已決定保留 | 現有本機操作者 | 現況直接寫指定 config 檔；不能宣稱已有 managed path policy | 不建立 task owner |
| `serve --db` | owner 啟動／schema 初始化，**不是 task action**；不能先要求一個尚未啟動的 OperationService | 本機操作者 | acquire_owner 成功後才開始服務／worker；不得覆寫別人的 owner pointer | 唯一 owner gate，見 A09 |
| `mcp`／MCP server 啟動；讀取連線時的 device-id／token 檔初始化 | transport／身分初始化，**不是 fleet mutation action** | 原本機設定 | 不新增 BAT mutation 能力；保留既有讀取行為 | client 只連既有 owner |

憑證發行／撤銷與一次性 capability 發行是短 connector-data 修改，不觸及 BAT/Git/provider，保留原行為與秘密處理。只存 token hash，明文一次回傳；不新增其 operation 回執。

## 輸入、輸出與相容性

### 共用 action 輸入

既有 OP envelope 保留：`action`、`target`、`params`、`preconditions`、`idempotency_key`。HTTP 新 mutation action 預設仍要求明確的 key；只有經核准的舊入口允許 key 省略。這個相容模式由 transport 內部選定，不接受 client body 的 bypass 旗標。舊工具新增可選 `idempotency_key` 與 `control_version`；舊 CLI 新增 `--key` 與 `--control-version`。Part B 只使用保留前綴＋operation ID 作不去重的儲存 sentinel，不以文字／資源身分推導 client key。

| 能力 | target | params／preconditions 的必要內容 | result／refs |
|---|---|---|---|
| session 控制 | `host`、確切 `session_id`；task-scoped send 另接受 capability 綁定的 `{task_id}` | send：text、queue、可選 message_id；answer：answers 或 permission、固定 tool_use_id、deny_message、dont_ask_again；interrupt：mode；permissions：mode。task-owned 的明確 precondition 為 `control_version`。 | 原工具完整結果；task_id、command_id、dispatch 時 control_version 另記 refs。 |
| start／relay／fanout／failover | host、workspace／來源 session | 原工具欄位全部保存；relay 原話、brief、thread、earlier、fanout 選項分別保存。fanout plan 在第一次選定後持久固定內容與 digest。 | 預留 session IDs、worktree／branch、逐項結果、來源與 successor 關係。 |
| task.submit | host、workspace；project 放 params | 原 work_submit 欄位全部可轉接；original_words 逐字保存。continuation 帶 parent_task_id。不改 daemon 的 default task_path、base_branch 或 engine／recipe 規則。 | task_id、state、submitted_at、engine、task_path、goose、continuation；refs.task_id。 |
| task.pause／resume／mark_stage | task_id | abort_current；caller provenance actor／source_message_id；stage／ref。明確控制版本用 preconditions.control_version。 | 原 task／delivery 結果；控制版本與 effect 回執。 |
| task.verify／request_ted | capability 綁定的 task_id | verify 不接受 caller argv／exit code／evidence；request_ted 帶 reason。 | 原受信 evidence／task 結果、candidate 與 log reference。 |
| task.command.reconcile | task_id、command_id | 原 outcome、source、evidence、observed_result、turn_ref、candidate_commit／tree_hash、新 next_prompt；一次性 capability 走認證，不放 params。 | 原 reconciliation task 結果；原 command 與新 command IDs。 |

舊 host／session 短名解析保留，但在 daemon 唯讀解析成穩定 ID 後即固定，不在 retry／執行時重新挑選另一資源。傳入的字面 target 進 hash；解析結果存在 refs，不因 inventory 更新改寫 intent。task_send 的 `{task_id}` 也在第一次 admission 固定 host／session；重送先查原 operation，不能因 task 換 session 而送到新的 writer。session.send 的共用 schema 明列這兩種 target，不能在 adapter 先查當前 session 再改變 replay 的 request hash。`queue=true` 只描述 BAT 的 standalone streaming guard，不把 task-owned 要求放到另一個 queue。

### 每個舊工具的結果投影（Part B；task 欄位新增 ID/status 為 Part A）

所有相容入口保留原頂層欄位；Part A task 結果新增 `operation_id`、`operation_status`；Part B 另加 `operation_error_code`，不以 operation 的 status 覆蓋 task 的 `state`。HTTP／通用 `operation_submit` 仍回 `{operation, created}`。bounded wait 沿用 RPC 上限 30 秒；逾時回紀錄，不在 adapter 再呼叫 handler。

| 工具／命令 | 必須保留的結果與特別相容規則 |
|---|---|
| send、continue | host、session_id、message_id、accepted、queued、turn_phase、turn_attribution、resumed、turn_marker、after_ms、after、marker_source、note。`api_actions._send` 現在丟掉部分欄位，Phase 2 改保存完整結果。明確的 message_id 保留 BAT correlation 用途，不變成 operation key；未提供時用固定 operation／command ID。 |
| answer | host、session_id、channel、tool_use_id、result、questions／answered／permission；保留 dont_ask_again。原工具可省 tool_use_id：由共用 handler 先讀 pending prompt，寫入綁定 step，再只回答該 ID；retry 不選下一個問題。通用 action 仍要求明確 ID。 |
| interrupt | host、session_id、mode、channel、result、note；Claude soft／hard、Codex hard 語意不變。 |
| permissions | host、session_id、agent_kind、mode、calls、note。Codex sandbox／approval 兩個 call 分開留 step；先成功一個不能報成全部成功。 |
| approve-pending | host、dry_run、sessions、count、deferred_raises；原 skipped=read_only／confined 保留；新增每項 code、operation／step reference、task 拒絕理由。延後 raise 仍可回 deferred，但此工作要留在原 operation，不靠 registry 旗標成為無主寫入。 |
| relay | host、session_id、workspace、text、request_fanout、max_items、sent、started、read_only、read_only_code、no_session、quota_stopped、busy、replaced、next、result 與 turn 欄位按原分支保留。首次選定目標即固定；task gate 拒絕不能用 start_if_missing 偷換成另一個 task writer。 |
| start | started、session_id、agent_preset、workspace、worktree_path、branch、source_branch、base_branch、base_commit、tab、prompt_sent、message_id、permissions、isolation、note 與原失敗結果。start 成功但 prompt 不明時保留 started=true，prompt_sent 不宣稱 true。 |
| merge | 原 `_summ` report、merged_now、result、main_checkout_clean_after、reason、worktree_dirty_files；不得把 refusal 報成 merged_now=true。 |
| remove-worktree | 原 report、removed、branch_deleted、rehydrated、note／reason／dirty files；delete_branch／allow_unmerged／discard_uncommitted 均保存，仍須原個別授權與安全 gate。 |
| failover | 單項 old_session_id／new_session_id、cwd、branch、same_worktree、prompt_sent、message_id、error、skipped 等原欄位；bulk 的 failovers、count、exhausted_found、skipped_read_only、truncated_by_max_start_per_call。原 session-level「already failed over」檢查保留，但不能用它代替 operation 參數衝突檢查。 |
| cleanup（只限 dry run） | host、dry_run、jev、decisions、counts、escalation_summary、push；保留唯讀的 MERGE_AND_CLEAN／CLEAN_ONLY／KEEP／ESCALATE 決策預覽。apply 維持 409 `LEGACY_CLEANUP_DISABLED`，沒有本包的 operation／effect 投影。 |
| record-verification | verification.record 的完整證詞、verified_candidate；operation actor 取驗證身分。這是外部證詞，不能變成 Task Service 的 observed_verification。 |
| fanout-plan | 原 start 結果＋role、max_items、next；保存 role=planner。 |
| fanout-start | host、source_session、workspace、plan、started、planner_cleanup；原逐項 task/title/session/branch/error 保留。planner_cleanup 回報 legacy apply 拒絕，保留 planner session 供 `cleanup_preview`，不啟動第二個 cleanup writer。 |
| fanout --start | started、count；保留 task index／title 和原 start 結果。plan 的讀檔與純解析仍在 CLI；每項實際派送都在 daemon。 |
| work_submit | task_id、state、submitted_at、engine、task_path、goose、continuation（適用時）；立即持久寫 task 的路徑保留。 |
| work_pause／resume | 原 Journal.get 全部 task 欄位；paused、control_version、state 各自保留，不把 operation succeeded 解釋成 task done。 |
| work_mark_stage | 原 delivery 結果；adopted／merged／deployed 都是證詞，不觸發外部操作。 |
| task_send／run_verification／request_ted | 原 task／evidence 結果；task_send step_id 保留，新增 operation reference。 |
| task-reconcile | 原 task／reconciliation 結果與 `_next_command_id`（適用時）；不增加自動重送或自動採用 successor。 |
| op --cancel／--resume 與 MCP steering | 原 `{operation: target_operation}`、授權與事件完全保留；不新增 control operation。 |
| 已有 checkpoint／integrate／project／item CLI | 原 `{operation, created}` 與 note／next 保留；現有隨機預設 key 改為「未提供就是無 client key」，新增／統一 `--key`，明確顯示去重是否啟用。 |

尚未得到外部 ACK 時，舊布林效果欄位使用 `null` 表示未知（例如 accepted、sent、prompt_sent、merged_now、removed），附 operation_status；不用 false 表示確定沒發生。已證明的前段結果照常回傳。這是 bounded wait／uncertain 新增的結果情況，README 與兩份 skill 必須說明；成功結果保持原型別。CLI 非同步受理退出碼為 0，確定拒絕／failed 為 1；uncertain 顯示 ID 與回查方式。

dry_run=true、cleanup 預設預覽、fanout 不帶 --start 都不執行 mutation，不需要 operation/key。純 preview 不執行 `_raise_deferred`、rehydrate、stop 或 registry effect；既有 `integration.preview` 會寫 connector area，仍是 operation，不能以名字 preview 判斷唯讀。

## A07：從實際 coordinator 導出的規則

### 起點已有的控制機制

- `TaskCoordinator.tick` 以 `_task_locks[task_id]` 串行同 task；`_send` 以 `_lock(host, sid)` 串行同 session。
- `_tick` 先擋 `paused` 與 `done`／`failed`／`human_owned`／`needs_ted`；先查 failover 的 intent／uncertain，再查最新 intent／needs_review／uncertain。未證明 intent 先轉 uncertain，再 `_reconcile_command`，不重送。
- `Journal.command` 拒絕 paused、terminal、human_owned、uncertain、needs_ted；send 只允許 accepted／running／verifying／dispatching。它查未完成的 send／failover／start_% 命令（intent／needs_review／uncertain），但不把所有 accepted 回合當作待對帳。
- `BatTaskAdapter.send.before_invoke` 在準備呼叫與 `BatClient` 送出前核對 paused、control_version、lead/reviewer binding、needs_review command、prompt hash。coordinator 的 reviewer／verification rework 可以合法在 verifying 派送，這不是外部低階工具的權限。
- `Journal.pause`／`resume` 各增 control_version；paused 是 bool，**不是一個 task state**。resume 不直接派送、不清 uncertain；verifying 的 resume 會重設驗證時鐘。
- `TaskCoordinator.pause(abort_current=true)` 先寫 pause，再取得 session lock interrupt；目前這個 interrupt 沒有獨立 command/operation 回執，需補上。不能為了共用鎖讓 pause 等整個長時間 verifier 才持久化。

### 共用外部 gate（新增）

OperationService 的 context 注入 daemon **同一個 coordinator**。不可在 action handler 另建 TaskCoordinator、另讀預設 DB 當 authority。registry 的 task_id、Journal 的 task.session_id／reviewer_session_id、尚在 start command 的預留 ID 與 branch 歷史都要核對；有任何 task ownership 證據就不能當 standalone。task row／owner pointer 不可讀，或來源證據不一致，fail closed。

| 條件（按順序） | 低階 send／answer／interrupt／permissions 結果 | 控制與版本處理 |
|---|---|---|
| manual／unknown／人工 cwd／binding mismatch | 原 resource-policy 拒絕碼 | 零 BAT／Git mutation；task link 不會改分類。 |
| task-owned，但中央 owner／row 不可讀 | `TASK_OWNER_UNAVAILABLE` | 不降級為 standalone，也不另外建帳本。 |
| registry／task／預留 command 指向不同 owner、host 或 session | `TASK_BINDING_MISMATCH` | 不改任何一方的 ownership。 |
| 明確 control_version 或 operation 的 admission binding 與目前不符 | `CONTROL_VERSION_CONFLICT` | 不自動更新 client precondition／admission binding。 |
| `paused=true`（任何 state） | `TASK_PAUSED` | send 的 queue／permission force／批次工具都不插隊。 |
| state=verifying | `TASK_VERIFYING` | 即使 lead 看似 idle 也拒絕，避免改掉候選或 reviewer turn。 |
| unresolved runtime command：send／failover／start_% 或本包新增的 answer／permissions／interrupt，status 為 intent／needs_review／uncertain | `TASK_COMMAND_PENDING` | 回傳非秘密 task_id／command_id／status，交原 coordinator reconcile。 |
| state=uncertain，即使找不到 unresolved command | `TASK_RECONCILIATION_REQUIRED` | absence probe／舊資料可能仍不明，不能視為安全。 |
| dispatching／queued／quota_limited／human_owned／needs_ted／done／failed，或來源為 reviewer／已替換 branch session | `TASK_STATE_BLOCKED` | 不透過低階 action 變更 task state 或接手 role。 |
| accepted／running 的 current lead，無以上阻擋 | send／interrupt 可交 coordinator；answer／permissions 還查當前 pending／streaming 規則 | 持久化 command 意圖、固定 dispatch control_version，再做即時 policy 與 frame guard。 |
| waiting_permission 的 current lead，無以上阻擋 | answer／permissions／interrupt 可交 coordinator；send 為 `TASK_STATE_BLOCKED` | answer 只針對固定 prompt；不能用「continue」跨過等待。 |
| 沒有任何 task owner 的 managed session | 由 OperationService 執行 | 保留 BAT streaming／queue、policy／rate gates，不創建 task。 |

pending command 指待確認派送的命令，不等同 BAT pendingPermission／pendingAskUser。accepted／running command 是已接受的回合，仍按 streaming／turn attribution 判斷；不一律擋掉其正常回答。`goose_run` 是整個 orchestrator 執行的 envelope，不能把其活躍 intent 當成所有 task_send 的阻擋條件。這與 `Journal.command` 的 runtime unresolved 查詢一致；新 runtime command kinds 明確加入同一查詢。

選擇 **拒絕、不新增 queue**。`G` 允許的 action 由 coordinator 的公共控制方法取得原 task/session 鎖、固定版本、透過原 commands 留意圖；send 延用 `_send`／prepare_send／reconcile_send，answer／interrupt／permissions 只增加必要 command kind／回查，不增加另一種 task state。外部不能把它包成 reviewer:initial 或 initial_task_send 以繞 gate。

operation 沒傳 control_version 時，admission 仍固定當時的 task incarnation。版本與 session 在 operation row 同交易保存，不能等執行時才改綁新版本／新 session。執行在第一個 effect／command 前核對：版本變動為 `CONTROL_VERSION_CONFLICT`（409）；同版本但 journal 的 bound role host／session 改變為 `TASK_BINDING_MISMATCH`（409）。零 BAT frame／新 command／task write，原 key 重讀同一 failed operation。task state 改成 verifying 時即使 control_version 未增加，也仍跑原 state gate。registry／resource ownership 保留於原 admission／共用 runtime gate／FrameGuard；本機 command reconciliation 不新增 registry 前置條件。

### Admission binding 儲存與 action 盤點（Part A）

`ActionDef.admit` 可回傳 binding；`OperationService.create` 將它保存於既有 `external_refs.admission_binding`，與 operation INSERT／accepted event 同交易提交。沒有 schema migration、沒有先建立 binding step。binding 至少含 `task_id`／`control_version`；session target 另含 `host`／`session_id`／`role`。API 將此欄標為 **admission binding**，不是 caller precondition。`preconditions` 原樣保存；request hash 只使用 caller 原 action／target／params／preconditions，binding 不進 hash。replay 仍在 admission 前比原 hash，所以 task 改變後相同 actor／key／原 request 仍回原 operation；把省略版本改成明確版本是不同 request。

| 已核對入口／action | 保存的 binding | 首次 effect 前核對位置 |
|---|---|---|
| task-owned `session.send`（host/session target）／`session.answer`／`session.interrupt` | task version＋current lead host/session/role；answer 的 permission 分支同樣綁定 | ActionDef step callback、`session_control` 取得鎖後／command 前、原 FrameGuard |
| `session.send`（`{task_id}`；`task_send`） | task version＋current lead host/session/role | task lock 下 `task_binding` effect 前；原 session lock／frame gate |
| `task.verify`（`task_run_verification`） | task version＋current lead host/session/role | task lock 下、trusted runner callback |
| `task.request_ted`（`task_request_ted`）／`task.mark_stage`（`work_mark_stage`） | task version | task lock 下，local effect／receipt intent 前 |
| `task.pause`／`task.resume`（`work_pause`／`work_resume`） | task version；abort_current 的 pause 另綁 lead host/session/role | local effect 的交易內；abort 仍使用 pause 後自己的 bound version |
| `task.command.reconcile`（`work_reconcile`／`task-reconcile`） | task version＋原 command 的 current lead/reviewer role host/session | task lock 下與 reconciliation local effect 的交易內；command_id 仍是原固定 target |
| `task.submit` continuation（`work_submit`） | parent task version | submit lock 下，在 submission_defaults／continuation effect 前；新 task submission 沒有既存 incarnation 可綁 |
| legacy permissions／relay target／continue（含 client-resume）／approve-pending／deferred raises | Part A 尚沒有 operation admission；共用 `session_control` 在第一次 gate 固定版本，owner RPC 轉送同一版本 | 原 task/session lock 與每個 permission／resume frame；Part B 包成 action 時須回傳相同 session admission binding，不能建立第二 writer |

上述 RPC／MCP／CLI task doors 都進 `ops.create`，因此得到相同持久 binding。standalone managed session 沒有 task binding。升級前已受理、沒有 `external_refs.admission_binding` 的 operation 保留原 execution-time binding，不回填、不重算 hash。已成功 effect 的 receipt 或外部 uncertain step 的正面 readback 仍按原證據恢復；此檢查只擋新的 effect，不能以較新版本否定已發生的效果或重送未知 frame。

只在 admission 查版本不夠。answer、兩個 Codex permission calls、interrupt、client-resume 都要使用 journal-bound 的內部 guard；public params 不提供 skip_gate／before_invoke／task_id 認領旗標。callback 存在本身不能作為 bypass 證據。所有 runtime writer 共享 coordinator 鎖的取得次序（task → session → host write lock → BAT semaphore），避免低階工具持有 host lock 再等 coordinator。

task.pause 是明確控制例外：先提交 pause、增版本，令未送 command 取消；abort step 只操作被綁定的 current session，即使 task 原先 verifying／pending 也能走 coordinator 停止目前回合。記下該 pause 的版本，若等待鎖期間 task 已 resume／換 session，拒絕遲到 interrupt。task.resume 只清 paused，不證明 writer 已停止；pending 命令仍先 reconcile。

pause／resume 也遵守 admission version：已受理的 resume 不能清掉後來的新 pause；已受理的 pause 不能暫停後來 resume 的 incarnation。兩者在自己的 local effect 前以 CONTROL_VERSION_CONFLICT 拒絕，task 不變。pause 不等待其他 task lock 的既有語意保留；「先提交的 pause 阻止舊 send」不表示排隊中的 stale pause 可永遠覆寫新控制。取得有效 incarnation、通過 gate 並開始 `_send` 後才輸給 pause 的既有 send race，仍沿用下面的 TASK_PAUSED 規則。

task-scoped `session.send` 已通過 admission 後，pause 仍可在等待 session lock、`_route`、presence probe 或 `prepare_send` 時先提交。若 pause 在 command／frame 前勝出，send 以 `TASK_PAUSED`（409）明確拒絕，`task_send_refusal` step 與 operation 都是 failed，沒有 command／BAT write frame，task 保持 pause 留下的內容。相同 key 永遠重讀此拒絕；resume 後要用新 key 才是新派送。原 coordinator 自己的 `_send`（沒有 operation）仍回傳 paused task，paused tick 不派送。

task send operation 的成功必要條件是：這個 operation 已保存 `task_send_command` 回執，連結的同 task／session send command 為 accepted 或 settled。原 readback 可證明 command 後成功；未解 command 保持 uncertain、不重送。沒有此回執的提早回傳不能算成功：沿用 task gate 的拒絕碼，無其他阻擋時為 `TASK_SEND_NOT_DISPATCHED`（409）；BAT 明確不接受則為 `NOT_ACCEPTED`。refusal intent 保存固定 code／message，只執行本機拒絕；started／failed refusal step 在 operation terminal status 尚未保存時遇到 crash，重啟仍先重讀拒絕，不因 task 已 resume 而派送。

bulk approve、deferred raise、明確 relay target 與 implicit client-resume 都使用同一 gate。bulk 被擋的項目保留 skipped/code，不阻擋其他獨立 standalone 項目；不得把 refused task 項目帶到新 session 繼續。task-owned worktree merge/remove/failover 由 F 拒絕 `TASK_OWNED_CONTROL_REQUIRED`；legacy cleanup dry run 繼續 KEEP，apply 由 cleanup package 封鎖。Task Service 自己的 external_worktree cleanup 保留原命名／證據與 coordinator 生命週期，不交另一個 cleanup owner。

## Task operations 與 A05

`task.submit` 的 operation succeeded 表示「原 task 意圖已受理」，不是 coding／verification 已完成。它的 refs.task_id 永遠指向原 task，後續查 work_status／GET tasks／events。pause／resume 表示控制變更已持久；abort 則另有已證明／uncertain 的 interrupt step。operation.cancel 不會撤銷已提交 task；要停派送使用 task.pause。不能用 operation.resume 重送 task prompt。

Local task mutation 與 operation 的 effect receipt 要在 **同一 Journal.tx** commit，沿用 `work_items._once`「effect＋回執同交易」的做法，不只用 `ctx.step` 把整個 `work_*` 函式包住。可用既有 operation_steps 的 response 作本地回執，讓 Journal 的既有方法加入共用交易 helper；不另建 task database 或派工狀態表。意圖先提交，再於短交易同時寫 task/event/control_version、command linkage 與 step success。crash 發生在 effect 後、operation 終態前時，只讀回執，不能再增 control_version、continuations 或 ted_interventions。

Task scope command 外部派送仍由 coordinator 擁有。operation refs 記 task_id／command_ids，task command payload 另記 operation_id；command 的 message_id、before cursor、prompt hash、狀態與 reconciliation 仍使用原機制。不能同時讓 OpContext 與 TaskCoordinator 各自送一份 prompt。answer／permissions／interrupt 的新 command kinds 也由 coordinator reconcile；operation 反映命令證據，不自行改 task state。

| A05 情境 | 固定規則 |
|---|---|
| 同驗證 actor、同 key、同 canonical action/target/params/preconditions | 回同 operation_id；不重跑 admission、模型判斷、task.submit、control 或任何外部 step。 |
| 省略 control_version 的 task-bound operation | admission 版本／session 保存在 external_refs，不改 caller request hash；版本／role 改變後尚未執行的要求 failed，原 key 重讀拒絕。已 succeeded 的要求仍回原成功。 |
| 同 actor/key，但文字、模式、task、source、prompt ID、plan、force、控制版本等有效參數不同 | `IDEMPOTENCY_CONFLICT`，HTTP 409；沒有新的 task／command／session。 |
| 不同 actor 使用同 key | 不同 operation；tasks 原全域 key 不能碰撞。task submit 的內部 journal key 以固定 operation_id 對應，不把 client key 直接當 tasks.idem_key。 |
| 同 key 從 continue 與 text=continue 的 send 重送 | 正規化後相同；transport entry 不造成衝突。原 relay 是另一能力，不因最後組出的 text 相同而合併。 |
| 省略 key（Part B） | 存保留前綴＋operation ID 的唯一 sentinel，每次受理要求新 operation；讀取為 idempotency_key=null、idempotency_enabled=false。遇 timeout 使用已得到的 operation_id；若連 ID 都未收到，不能承諾重送去重。 |
| task_send 的舊 step_id | 這是 caller 已提供的重送識別，明列映射為 key，principal 限同 task；不是由文字推導。改 text 或明確版本要衝突，不能被 Journal.command 的既有舊列遮住。 |
| work_submit continuation | 原 record_continuation 只按 key 去重、未比 words；operation hash 先補齊不同 words 的衝突，同 receipt 保護 continuations 計數。 |
| replay 前置的結果後記失敗／重啟 | 讀既有 task effect／command／step 回執；不補一套 dispatch。 |
| reconciliation capability 已消耗 | 同 key 的原 operation replay 僅在原 capability 有效期限內，以原 token hash／task／command binding 與回執讀回原結果，不允許新的 resolve 或派送；明文 token 不入 journal。CLI 的原 local-admin 身分可查自己的既有 reconciliation operation，取得回執後不再發 capability。 |

work_submit 原已要求 key，保留其最大 256 字相容長度；一般 operation 既有上限 200 字保留。validation 由該 action 的 key constraint 決定，避免把合法舊 task key 截短或 rehash 成另一個 client key。舊 task global key 的升級重送另見資料遷移。

## 實際副作用、步驟與失敗恢復（task 為 Part A，其餘拆分為 Part B）

不能只以 `ctx.step("legacy", legacy_function)` 包整個 lifecycle 函式。那些函式內有多次 BAT mutation，有些會吞例外或 rollback。Phase 2 做最小拆分／注入 step 執行介面，使原判斷與 policy 保留，每次 mutation 都有 commit 在先的 intent。原 helper 只供共用 action／coordinator 使用；transport 不直接呼叫它。

| 能力 | 必須分開保存的 step／固定身分 | 遺失 ACK／重啟回查 |
|---|---|---|
| send／continue／relay | target 選定、必要 `client_resume`、send；固定 message ID／prompt hash | resume 核對 meta 與 binding；send 用既有 registry turn／BAT exact echo。Codex 的一般 action 只有 timestamp 時維持 uncertain，不重送。 |
| answer／approve-pending | pending prompt binding、每個 prompt answer、每個 permission 設定 | prompt ID 不再 pending 才能證明清除；不代表所有後續工作成功。失敗讀取不是「沒有 pending」。 |
| permissions | Claude mode；Codex sandbox 與 approval 各一步 | 讀同 session meta 的實際 mode；證據不足時維持 uncertain。deferred raise 保存固定目標／版本；task gate 改變時拒絕，不盲目掃全 registry。 |
| interrupt／pause abort | interrupt／abort 各一步；固定 task/session/version | 證明相同 session 不 streaming；查不到或 binding 不符不能算完成。已 pause 的意圖保留，不因 abort 不明而退回未 paused。 |
| task-owned session.send／answer／interrupt | operation_id 連原 task command；保留原 payload／control_version | operation 讀回先結清自己的 step；下次 coordinator.tick 在 task lock 下以原 `_reconcile_command` 的證據結清 command（send 為 accepted，其餘為 settled），將 lead task 恢復 running。operation 的證據不代替 task 回執；command 未解仍擋控制，回查不明維持 uncertain、不重送。 |
| task-scoped session.send 的 terminal command | `task_send_command` 回執、原 command status／payload、`task_dispatch` failure | command status 已提交，但 result／refusal 未提交即 crash：cancelled／rejected 沿用下表的本機結果，不進 uncertain、不建立新 command／BAT frame；舊 coordinator send 與 tick 共用這項處理。 |
| start／relay 新建／fanout 項目 | reserve IDs、worktree.create、start-session、選配 tab append、第一個 prompt | 核對預留 ID、creation evidence、cwd、branch。已存在只補回執；不能重新 random ID、刪已可能成功的 worktree，或回退人工 cwd。tab 整份 workspace save 的既有 race 不在此聲稱修好。 |
| failover | 固定 source/successor、writer proof、start、獨立 handoff send | successor 存在不代表 handoff 成功；舊 writer 不明時不建第二 writer。registry starting／uncertain 不作「可再開」依據。 |
| worktree merge／remove | 可選 rehydrate、merge、remove、選配 branch delete、stop、registry effect，每項分開 | 保存來源／目的 commit 與 path；merge 以目的 Git 證據核對，remove 以 exact worktree 身分／存在性核對。不能因資料夾不存在就順手刪別的 branch。無法唯一歸因就 uncertain。 |
| fanout | 固定 plan digest、每項預留 ID／steps；planner cleanup 僅回報 legacy apply 拒絕 | per-item 已完成結果不重做；未證明項目維持 uncertain，不啟動更多可能重複的 writer。保留 planner session 交 `cleanup_preview`，不經 legacy apply 清理。partial items 與原 cap 行為保留。 |
| task submit／控制／證詞 | 原 task effect＋同交易 step response；command IDs 連結 | 本地 commit 回執即完成證據；沒有回執代表交易未完成，可以重新做本地交易，不能重播已存在 external command。 |
| task.verify | 固定 candidate、原 runner invocation、output artifact、observed verification receipt | runner 失聯／重啟後無完成證據就 needs_attention／既有 task 恢復規則，不把 invocation 再當普通本地寫入重跑，不接受 caller 填 exit code。 |

task send command 的恢復規則：

| command／durable step | 恢復結果 |
|---|---|
| cancelled | task 仍 paused：TASK_PAUSED；已 resume／control_version 改變：以 command payload 的綁定版本交原 `task_control.check`，回 CONTROL_VERSION_CONFLICT（binding 改變則沿用 gate 的 code）；其他取消固定為 TASK_SEND_NOT_DISPATCHED。只拒絕，task 完全不變。 |
| rejected，task_dispatch 已 failed | 重拋保存的 StepFailed code／message，與原失敗路徑相同；不改 task，不回查 send、不派送。 |
| rejected，沒有 failed dispatch | 保留已記錄的 needs_ted／vanished 結果或較新的 task control／send command（即使 control_version 相同）。仍是同版本、同 session 的原派送狀態時，恢復 needs_ted；initial lead 可由新的 presence 正面證明 vanished，交原 `mark_initial_session_vanished`（最多一次 replacement）。presence await 後重讀 task，期間有改變就保留新狀態。operation 回 NOT_ACCEPTED。 |
| intent／needs_review／uncertain | 保留原 `_reconcile_command` 的證據與未知結果規則；不能重送。 |
| accepted／settled | 保留 task_send_result 的成功回執。 |

舊 command status 沒保存當時的 presence 理由；rejected 本身也不能證明 initial session 已 vanished。若恢復時 presence 不明、讀取失敗或 session 已恢復存在，就選 needs_ted：確定沒有已接受的 send，不需要人工對帳，且不會自動重送或憑空建立 replacement。已提交的本機結果不再寫一次。coordinator 自己的 cancelled send 保留原 task 回傳；non-operation rejected send 在重用 command key、或 tick 要觀測回合前恢復同一本機結果（只處理同版本的 coordinator command，不套用到 runtime control 的拒絕）。沒有新增 command settlement 的證據規則。operation 一旦保存 refusal intent／terminal failure，同 key 永遠重讀原 code。

沿用 operation 的 accepted／running／waiting_external／uncertain／needs_attention／succeeded／failed／cancelled。回查退避與 uncertain_tries 上限沿用 `operations.py`；不新增 task state。多項 operation result 保存每項 code、已完成 steps、effect、尚未證明的部分；每項失敗不能消去其他項已完成的 mutation。

A08 特別要求 standalone failover 取得 **正面的舊 writer 停筆證據**，包含讀取成功、streaming=false、沒有 pending write／uncertain start、同 worktree 的其他活躍 writer 與未完成 operation。`_failover_one` 現在以 snapshot 的 streaming 判斷；meta 不可讀不等同 idle，force 只略過 quota 分類。同 host/worktree 的候選與尚在建立的 successor 要共用 daemon 的現有鎖／reservation，兩個不同 key 也不能同時建 writer。source 已 superseded 或 handoff 未證明時，同一 worktree 上的 send／client-resume 也要拒絕，不能靠復活舊 session 產生第二 writer。

人工接續只用既有 checkpoint.create → checkpoint.continue 的新 managed clone／session；legacy failover 仍不寫、不 stop、不 supersede 人工來源。A08 的人工接續不靠「同 worktree failover」達成。task-owned failover 目前停用，保留停用，不以 operations 引入新 takeover。

## 穩定錯誤碼

| 代碼 | HTTP／相容入口 | 恢復方式 |
|---|---|---|
| 原 resource-policy codes | 403，admission 不建 operation；執行拒絕才 failed；bulk 每項 code | 不改 force／confirm 繞過；改用合法新 managed 工作。 |
| `IDEMPOTENCY_CONFLICT` | 409 | 回原 key 的 operation；新的意圖用明確的新 key。 |
| `CONTROL_VERSION_CONFLICT` | 409 | 讀同 owner 的 task，重新決定動作；不自動換版本重送。 |
| `TASK_PAUSED`、`TASK_VERIFYING` | 409 | 查 task；有授權才用 task.resume／task.pause，不插隊。 |
| `TASK_SEND_NOT_DISPATCHED`、`NOT_ACCEPTED`（task send） | 409，operation failed | 沒有這個 operation 的 accepted／settled command；查原 operation／task，新的派送使用新 key。 |
| `TASK_COMMAND_PENDING`、`TASK_RECONCILIATION_REQUIRED` | 409 | 原 coordinator 回查／command-scoped reconcile。 |
| `TASK_STATE_BLOCKED`、`TASK_OWNED_CONTROL_REQUIRED` | 409 | 使用既有 task 控制；不以 standalone 工具接管。 |
| `TASK_OWNER_UNAVAILABLE`、`OWNER_UNAVAILABLE` | 503 | 恢復既有中央 owner 的連線／可讀 journal。 |
| `TASK_BINDING_MISMATCH` | 409 | 由 owner 核對既有 ownership，不認領或改連結來放行。 |
| `WRITER_UNCERTAIN`、`WRITER_ACTIVE` | 409；若已有外部 step 不明則 uncertain | 留原 ID 回查；不建第二 writer。 |
| `OWNER_CONFLICT` | `serve` 非零退出；client 顯示結構化 owner 資訊 | 使用既有 endpoint；不以 heartbeat 過期自動 takeover。 |
| `UNCERTAIN`／既有 `UNCERTAIN_UNRESOLVED` | operation status＋step evidence | 查原 operation；needs_attention 才用 resume 重新回查。 |

MCP 的 `_wrap` 與 CLI 錯誤 renderer 保留原可讀錯誤／非零行為，新增穩定 code 與 operation_id。`/rpc` 今天將一般 task 例外壓成 class 名、API RPC 一律 400；Phase 2 保留其 envelope 相容性，補 code/message／ID，HTTP `/api/v1` 使用上表狀態。不得把 token／原聊天／provider 錯誤全文回傳。

## A09：既有 owner 與第二個 client／daemon

`TaskDaemon` 已有 `_lease_fd`、`_owner_id`、`acquire_owner`／`release_owner`、排他 flock、`daemon_owner` 單列與 `_worker` heartbeat。pointer `task-service.json` 寫在 registry 旁，現在只含實際 db_path／pid。`test_daemon_lock_and_rpc_task_scope` 證明同 DB 不能兩個 daemon；`test_daemon_records_actual_journal_for_send_fence` 證明自訂 DB pointer。兩者**還沒有證明同 fleet、不同 DB 父目錄**不會變成兩個 authority。

Phase 2 擴充原 owner 機制，沒有第二份 owner database／另一套 lease：

1. 同一中央 fleet 的 registry／控制 state directory 是既有 ownership domain。把原 task-daemon.lock 固定在此 domain 的 canonical 路徑；`--db` 只選 journal，不能選出另一把 fleet 鎖。兩個程序同時以不同 DB 路徑啟動、pointer 尚不存在時，也要爭同一把 flock。
2. 先取得這把鎖，才更新 pointer／daemon_owner、執行 schema migration、建立 listener 或 worker。現有建構函式會先開 Journal；需把會改正式資料的初始化排到 owner 成功後，避免第二 daemon 在鎖失敗前修改候選 DB／token。
3. pointer 增 owner_id、journal 參照、實際 loopback endpoint 與 lease path；寫入維持 0600＋atomic replace。衝突者讀此資訊回 `OWNER_CONFLICT`，不能覆蓋 pointer、替換 admin token、觸發 BAT／Git。只有 owner 啟動取得 flock 才可更新 singleton。
4. heartbeat 僅提供觀測。時鐘跳動／heartbeat 過期／pointer PID 不存在都不是強制接管理由；flock 仍持有就拒絕。process 死亡後 OS 釋放鎖，重啟使用既有 journal IDs／steps 回查。
5. 第二個 client 只走 task_daemon.request 的 loopback／SSH forward 與配置 endpoint；不同 actor 共用同 owner、同 journal／events。endpoint 不可用不自動 `serve --db`。client 傳入的 owner_id／actor／journal 路徑不能更換權威。

升級時先停舊 owner，再以同 journal 啟動新版本；舊版 lock 在 DB 父目錄，不可與新版 canonical lock 混跑。回退需保留此 owner／policy 限制，不能啟動未理解新版 schema 的舊 daemon。另一部主機擅自另設 state directory 不在本地 flock 的保證內；正式 client 只有既有中央 endpoint，不新增分散式發現／接管功能。

## 現有資料與 schema 遷移

不搬移、不重編 task／command／session／worktree／branch／checkpoint IDs，不重送歷史命令，不補造「以前執行過」的 operations。registry、tasks.sqlite3、verification 證詞與既有管理／delivery 資料保留。**沒有業務資料搬遷或歷史回填**；NOT NULL 與唯一索引保留，no-key sentinel 不需 schema change。 admission binding 只存於新 operation 的既有 external_refs；舊無 binding rows 保留原行為。

- 不重建 operations、不改其 NOT NULL／FK／唯一索引。Part B 採保留前綴 sentinel；舊有 keys/hashes/steps 原樣保留。Part A 未新增 schema。之後若需額外欄位，以 guarded column add／idempotent DDL 每次開 journal 時執行，不讀寫 `PRAGMA user_version`；只有一次性資料搬移才使用 orchestrator 分配的版本。
- task-operation linkage 使用現有 `external_refs`／command payload／operation_steps response；沒有第二個 task 狀態表，也沒有資料搬移。檢查 row count、operation_steps FK 與原 key 去重結果；初始化失敗 rollback，不先啟動 worker。
- 原 `tasks.idem_key` 全域唯一保留。新版提交使用 operation 固定的內部 journal identity；這是已存在的 task receipt linkage，不是替未提供的 client key 提供去重。對原 work_submit key 的第一次升級重送，僅 local-admin 舊相容入口可按原 `Journal.submit` 的 payload_hash 核對並連到原 task，再寫新的 operation link；內容不同拒絕。無法證明原 actor 的歷史 key 不讓新的 API actor 認領。
- 現有 continuation events／stage events／verification records 不追認為新的 action 回執。新的相同 key 只依新 operation hash 去重；不得因舊 stage 已存在就忽略 ref 不同的衝突。原一次性 reconcile capability 的期限與消耗規則保留。
- 升級前由部署者備份中央 journal（含 WAL 一致性）、registry、設定、schema 版本與 owner pointer。spec 階段不接觸部署資料。舊 permission_raise_pending 尚無 operation：只有下一次明確 approve-pending 要求才把選定項目納入有意圖的 deferred steps，不啟動自動回填 writer。

## 預計修改檔案

| 檔案 | Phase 2 修改 |
|---|---|
| `src/bat_agent_connector/api_actions.py` | 原 3 個 action 完整結果、共用 action schema／admission、task ownership gate；註冊新增 session／composite actions。可按既有 delivery/checkpoints 慣例分模組，避免重複定義。 |
| `operations.py` | Part A 不改 create admission/schema；task 使用原子 effect receipt。Part B 補 no-key sentinel／投影；原 steering 與 uncertain/reconcile loop 保留。 |
| `task_daemon.py`、`api_auth.py` | coordinator 注入 ops.context、task／舊 RPC 薄轉接、capability 到受限 principal 的原驗證映射、canonical owner lock／metadata、初始化順序、穩定錯誤。 |
| `task_core.py`、`task_bat.py` | 公共 task-owned action gate、原鎖／commands／版本 guard、answer／permissions／interrupt 回查、pause abort 回執；不改 engine／recipe／模型政策。 |
| `task_journal.py` | 版本化 schema 調整、原子 task effect／step receipt、commands 的新 runtime kinds／operation linkage；原 tasks／events authority 保留。 |
| `service.py`、`lifecycle.py`、`orchestrate.py` | 最小拆分多個 mutation，持久 steps／固定 IDs；移除以 callback 存在就繞 task gate 的路徑；deferred raises、failover 正面停筆證據與 source resume gate。 |
| `mcp_server.py`、`task_scoped_mcp.py`、`cli.py` | 保留工具／命令，新增可選 key/version，統一 principal、confirm/read-only、结果投影／async 結果；不直接寫 Fleet。 |
| `resource_policy.py` | 更新 entry_points 清單、保留所有 WriteGrant／目的端檢查；local 證詞不授予外部寫入。 |
| `tests/test_api_v1.py`、`test_mcp_and_config.py`、`test_resource_policy.py`、`test_task_service.py`、新增 `test_operations_unification.py` | 下列全入口契約、gates、故障注入、schema／owner 測試；只用 mock BAT／fake GitHub／temp Git。 |
| `docs/design/api-v1.md` | 新 actions／scopes／key／結果／錯誤、舊入口 operation admission；完成後移除尚未涵蓋中的舊工具與 task operations 項目。 |
| `docs/design/task-service.md`、`resource-policy.md` | 描述 operation→原 commands、A07／版本／owner 範圍；修正「舊低階工具不受服務鎖控制」與過時 HTTP 尚未涵蓋，保留 BAT GUI／workspace save 的實際限制。 |
| `skills/bat-agent-connector/SKILL.md`、`skills/hermes/bat-agent-connector/SKILL.md` | 同步描述保留 key／operation ID、拒絕碼／回查、work_* 原語意、暫停／驗證不插隊、unknown writer 不 failover，不讓 agent 要求 approve scope。 |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md` | 指向本 spec，說明 daemon/token 前置條件、相容欄位／未知結果、scope 與無 key 重送限制；unreleased 記計畫 §09／§10／§24 與 A01／A05／A07／A08／A09。 |

規格修訂先獨立 commit。Part A 更新 task／API 文件、兩份 skill、README x2 與 CHANGELOG，只描述本段交付；Part B 文件隨其實作同步，不提前把規劃能力寫成已可用。Dashboard 本包沒有新畫面需求，繼續使用同 operation／events／task read API。

## 測試計畫與驗收對照

下表保留完整分段測試計畫；Part A 已加入上節對應的可執行測試。Part B 的全入口名稱仍是預定名稱，不代表全入口驗收已達成。測試名或 docstring 標 acceptance ID，參數化使用上面每一列（含 admin／RPC／task-scoped、dry run 與內部隱式 mutation）；靜態入口清單也要與 MCP 註冊／CLI parser／HTTP route／ActionDef 清單比對，避免只測 HTTP。

| 驗收／計畫 | 既有可執行證據 | Phase 2 新增／延伸測試與必須斷言 |
|---|---|---|
| A01；§09／§10／§24 | `test_session_writes_refused_before_any_frame`、`test_bulk_and_relay_paths_skip_bat_sessions`、`test_mcp_tools_refuse_bat_sessions`、`test_cli_refuses_bat_sessions`（resource_policy）；`test_operation_idempotency_scope_and_bat_sessions`（api_v1） | `test_a01_all_write_adapters_share_policy`：manual／unknown／legacy cwd，各 transport、force/bulk/隱式 resume/deferred raise；所有 BAT write channels／SSH Git spy 為零、來源 files/HEAD/index/refs 未改；admission 拒絕沒有 op，執行拒絕保留 failed op。`test_all_write_entry_points_have_one_action`／`test_read_only_adapters_never_submit_mutations`。 |
| A05；§09 | `test_operation_idempotency_scope_and_bat_sessions`、`test_send_operation_runs_once_and_records_steps_and_events`、`test_restart_replays_finished_steps_and_reconciles_unfinished_ones`、`test_rpc_doors_share_the_operation_service`（api_v1）；`test_journal_idempotency_restart_and_metrics`（task_service） | `test_a05_all_actions_actor_scoped_idempotency`：每個 mutation、跨 adapter replay、same key changed params/preconditions 409、不同 actor 不撞 task key。`test_a05_legacy_no_key_creates_distinct_operations`、`test_a05_task_effect_and_receipt_commit_together`（pause/resume/continuation/stage/reconcile 交易邊界 crash）、`test_a05_task_submit_upgrade_replay`、`test_no_key_sentinel_never_deduplicates_and_is_projected_as_null`（Part B）。 |
| A07；§10 | `test_pause_during_final_presence_check_cancels_unsent_command`、`test_pause_during_late_session_send_lookup_blocks_bat_frame`、`test_daemon_records_actual_journal_for_send_fence`、`test_task_reservation_excludes_paused_lead_from_legacy_cleanup`（task_service） | `test_a07_task_owned_actions_respect_coordinator_gate`：各允許/拒絕 state、paused bool、各 unresolved kind/status、lead/reviewer/預留與舊 session；send/answer/interrupt/permissions、relay、approve/deferred、client-resume 全入口。`test_a07_late_state_version_and_owner_change_blocks_frame`：lookup、session/host lock、BAT semaphore 等待期間 pause/resume/version/verification/binding 改變，零新 frame。`test_a07_task_pause_abort_is_journaled_control`、`test_a07_goose_run_does_not_block_its_own_task_send`、`test_a07_task_resume_reconciles_before_dispatch`。 |
| A08；§09／§10／§24 | `test_continue_starts_managed_work_at_the_checkpoint_and_leaves_the_source_alone`、`test_a_lost_start_reply_is_read_back_not_started_again`（checkpoints）；`test_vanished_after_uncertain_initial_send_never_replaced`、`test_goose_uncertain_prompt_does_not_switch`（task_service） | `test_a08_failover_requires_positive_previous_writer_proof`：meta/offline/null、未確認 streaming、pending send/start/operation、force/bulk；零 successor write。`test_a08_failover_concurrent_keys_reserve_one_writer`、`test_a08_failover_restart_reconciles_successor_and_handoff_separately`、`test_a08_superseded_source_cannot_resume_a_second_writer`、`test_a08_manual_continuation_preserves_source`；證明 distinct 新 session/clone、不改來源、未知 Codex handoff 不重送。 |
| A09；§24 | `test_daemon_lock_and_rpc_task_scope`、`test_daemon_records_actual_journal_for_send_fence`（task_service） | 延伸同名 owner test；`test_a09_same_fleet_different_journals_refuses_second_owner`：含不同父目錄、同時啟動、尚無 pointer。`test_a09_conflict_reports_owner_and_preserves_pointer`、`test_a09_second_client_uses_central_owner`、`test_a09_stale_heartbeat_never_steals_live_lock`、`test_a09_restart_releases_lease_and_reuses_journal`；斷言相同權威、可讀 owner/endpoint、無第二 worker/BAT frames、衝突前不改 DB/token。 |
| 失敗恢復；A05／A07／A08 | `test_ambiguous_send_becomes_uncertain_and_settles_by_read_back`、`test_a_failed_read_back_keeps_the_operation_uncertain`、`test_needs_attention_can_be_cancelled_or_resumed`（api_v1） | `test_each_external_mutation_has_committed_intent`、`test_composite_partial_results_survive_lost_ack_and_restart`、既有 operation steering 不派送 task 的 regression；覆蓋 resume/start/tab/answer/兩個 permissions/merge/remove/stop/deferred 與本地記錄失敗，reconcile 無證據不發送。 |
| A07；§09／§10（Part A pause 競態） | `test_a07_pause_while_send_waits_for_session_lock_refuses_operation`、`test_a07_pause_during_send_preparation_refuses_operation`、`test_a07_task_send_requires_its_accepted_command_receipt` | 等待 session lock、route／presence／prepare_send 時 pause 勝出：operation／step failed、TASK_PAUSED，零 command／frame，task snapshot 不變；同 key 重讀拒絕，resume＋新 key 恰一 frame。paused tick 不派送；缺少回執／rejected／cancelled 不能成功，未解 command 維持 uncertain。 |
| A07；§10（Part A 其他控制） | `test_a07_other_controls_refuse_pause_while_waiting_for_session_lock` | answer／interrupt operations、legacy permissions／relay／deferred raise 等鎖時 pause：鎖後 gate 拒絕，零 command／frame；bulk deferred 項目 raised=false 與明確 code，不能回報成功。 |
| A05；§09（Part A 拒絕恢復） | `test_a05_paused_send_refusal_survives_restart_before_operation_settlement` | refusal step 在 started／failed、operation terminal status 尚未提交即 crash；task resume 後重啟仍重讀 TASK_PAUSED，不建立 command 或補送。 |
| A05／A07；§09／§10（Part A terminal send crash） | `test_a05_a07_cancelled_send_command_survives_restart_without_uncertain_task`、`test_a05_a07_rejected_send_command_survives_restart_without_uncertain_task`、`test_a07_rejected_send_recovery_preserves_a_later_accepted_command`、`test_a07_legacy_send_reuses_terminal_command_without_uncertain_task` | 最後 paused check／initial presence 後 cancelled status 提交即停止；新 daemon 恢復 TASK_PAUSED，task snapshot 不變、零 frame／新 command，resume＋新 key 恰一 frame。版本改變沿用 gate code；其他取消固定拒絕。rejected 的 local refusal／accepted=false／vanished／presence 不明，涵蓋 status 後及本機結果後 crash，保持 failed code、不進 uncertain、不重寫既有結果或較晚 accepted command 的 task。舊 send／tick 的相同 crash 也不製造 uncertain。 |
| A05／A07；§09／§10（Part A task action 鎖後檢查） | `test_a05_locked_task_action_refuses_task_completed_by_tick`、`test_a05_mark_stage_rechecks_verified_done_after_task_lock`、`test_a05_scoped_task_action_rechecks_pause_after_task_lock` | request_ted／verify 已受理但等待驗證 tick 的 task lock；tick 完成後 TASK_STATE_BLOCKED，done／verification／delivery 不變。mark_stage 等鎖後失去 done／verification_commit 時拒絕；scoped actions 等鎖時 pause 增版本，以 CONTROL_VERSION_CONFLICT 拒絕；同版本的 state 規則不變。零 effect／receipt intent、同 key 重讀拒絕。 |
| A05／A07；§09／§10（Part A admission binding） | `test_a07_session_operation_keeps_admission_incarnation`、`test_a07_send_refuses_replaced_admission_session`、`test_a07_task_actions_keep_admission_version` | send／answer／interrupt／permission answer，省略或明確版本：pause＋resume 後拒絕 CONTROL_VERSION_CONFLICT，無競態恰一 frame。task target send session 被換後 TASK_BINDING_MISMATCH，零 frame／command／task write。verify／request_ted／stage／pause／resume／reconcile／continuation 逐 action 綁定版本；stale pause／resume 不覆寫較新控制。原 request hash、refusal replay 與 success replay 不變；明確 stale 版本仍在 admission 拒絕。 |
| A05／A07；§09／§10（binding 持久化與相容） | `test_a05_admission_binding_is_atomic_with_operation_row`、`test_a07_admission_incarnation_survives_restart`、`test_a07_task_session_actions_refuse_replaced_admission_role`、`test_a07_preupgrade_operation_without_admission_binding_keeps_old_behavior`、`test_a05_legacy_task_door_records_admission_binding`、`test_a07_readback_of_old_incarnation_does_not_dispatch_again` | admission event 前 crash rollback 整個 row；restart 保留原 binding／拒絕，新 key 恰送一次。verify／abort pause／reviewer reconcile 不可換 session；舊無 binding rows 保留原行為。RPC／MCP／CLI 相同保存；已送 frame 在新版 incarnation 仍可 readback＋coordinator tick，不重送。 |
| A05；§09（Part A receipt replay 與控制） | `test_a05_locked_task_action_replays_receipt_after_state_change`、`test_a05_task_controls_do_not_wait_for_task_lock_or_change_terminal_task`、`test_a05_reconcile_refuses_command_settled_while_waiting_for_task_lock`、`test_a05_verify_request_ted_and_stage_use_original_receipts` | succeeded receipt 優先於新 state／version；未競態要求仍成功。pause／resume 本機 effect 不等 task lock、保留 terminal task；原 command 在等鎖時已被 tick 接受，reconcile 不消耗 capability／不寫對帳回執。 |

故障注入只用 `tests/mockbat.py`、`tests/fakegithub.py`、[test_checkpoints.py](../../tests/test_checkpoints.py) 的 LocalRunner／RealGitLog 與 temp Git repos。驗證 policy 時比較所有寫 channel 與目的端，不能只數 send-message。停用中的 `pytest.mark.skip` task 測試不算 A07／A08 證據；舊 engine／mid-task failover 的 skip 不因本包自動啟用。

Phase 1 與 Phase 2 報告都跑 `uv run ruff check .`、`uv run pytest -q`；只有 Phase 2 新行為測試通過後才聲稱驗收完成。spec commit 只證明盤點與可審查合約完成。

## 已決事項

歷史 task global key 仍沒有 actor 證據：只有 local-admin compatibility path 可依原 payload_hash 連回原 task；其他 API actor 不認領。無 key sentinel、policy admission、不納入離線 import／operation steering／token operations 的決議見分段交付。

## 尚未涵蓋

- **Part B 尚未交付**：舊 session/orchestration tools 成為 operations、no-key sentinel/投影、未知布林 null、外部 step 拆分與完整 A01/A05/A08 全入口驗收。Part A 只聲稱 task A05、A07、A09。
- `import-bat --output PATH --force` 保留 install-time local command；它在 owner 存在前執行、只寫本機 config，不是 fleet action，本包不改。
- operation cancel/resume 自身的 control operations，以及 api-token issue/revoke operations 不在本包；原 endpoints/RPC 已授權、留事件或立即完成短 connector-data 修改，不觸及 BAT/Git/provider。
- 不新增 task planner、recipe/model 政策、第二個 task database、分散式 owner lease 或人工資源接管；不恢復已停用的 task 中途 failover。
- 計畫 §23 的 reviewed cleanup 由 cleanup package 的 `cleanup_preview`／`cleanup_apply`／`cleanup_restore` 負責。它以 409 `LEGACY_CLEANUP_DISABLED` 停用 legacy `session_cleanup` apply；本包不包裝該 apply，也不建立另一個 cleanup writer。
- BAT GUI 可直接改自己的 session，connector 的鎖不能約束它；不宣稱 BAT 提供跨系統原子控制或 Codex exactly-once receipt。workspace:save race、host sandbox/ACL 與完整 A10 仍按原設計界定。
- 不變更遠端部署、Fleet Kit、live Goose gate、人工 snapshot／附件與整合來源擴充；正式 owner 升級與備份由部署者另行執行。
