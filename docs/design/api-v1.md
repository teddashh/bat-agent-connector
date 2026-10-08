# /api/v1：操作底座、資源目錄與事件

日期：2026-10-07。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §09–§11，工作包 W01（contract、identity、capabilities、OperationService）與 W03（inventory、pagination、事件游標）。人工 session 的唯讀規則見 [resource-policy.md](resource-policy.md)。

## 一個程序、一個 owner

`/api/v1` 由既有的 `batc serve` task daemon 提供，與 `/rpc` 共用同一個 loopback listener、同一個 SQLite journal（`task_journal.py`）與同一把 owner 鎖。沒有第二個程序或第二個帳本。Dashboard、MCP、CLI 都進入同一個 `OperationService`：

- HTTP：`/api/v1/*`（`api_v1.py`）。
- MCP：`operation_submit`、`operation_get`、`operations_list`、`inventory_sessions`、`inventory_hosts`、`events_list`、`capabilities_get`，經 daemon 的 `/rpc`。
- CLI：`batc api-token`、`batc op`。

遠端使用一律經 SSH forward 到 daemon 的 loopback 埠；daemon 不綁非 loopback 位址。

## 身分與權限

| 主體 | 取得方式 | 權限 |
|---|---|---|
| `local-admin` | daemon 的 `task-admin.token`（0600） | 全部 |
| API token | `batc api-token issue --actor ted-dashboard --scope observe --scope operate` | 發行時指定的 scopes |

Scopes：`observe`（讀目錄、操作、事件、政策）、`operate`（驅動 managed session）、`start`（開新的 managed agent session，例如 `checkpoint.continue`）、`manage`（專案、工作項目與連結）、`approve`（確認工作項目完成；與 `manage` 分開，回報完成的 agent 不能自己簽核，見 [work-items.md](work-items.md)）、`merge`、`deploy`、`integrate`（PR metadata 更新與把成果推送到 head 分支；兩個 action 分開，metadata 另需 repo allow_pr_update，見 [delivery.md](delivery.md)／[integration.md](integration.md)）。Journal 只存 token 的 SHA-256。操作的 actor 一律取自 token；request body 或 MCP 參數自報的名字沒有授權效果。冪等鍵的唯一性以 actor 為範圍：同 actor、同 key、同內容回原 operation；同 key 不同內容回 409。

瀏覽器防護：Host 必須是 loopback（擋 DNS rebinding）；有 Origin 時須是 loopback 或 `[api] allowed_origins`；只接受 bearer token，不用 cookie，所以沒有 CSRF 面。只有列在 `allowed_origins` 的 Origin 會收到 CORS 標頭（含 `OPTIONS` preflight）；Dashboard 與 API 同源，不需要它。

MCP 的 `operation_submit`、`operation_cancel`、`operation_resume` 要 `confirm=true`，而且只以 `BATC_API_TOKEN` 的主體執行，不退回本機 admin token：這個 client 能做什麼由它自己的 token scopes 決定，不是由 MCP server 啟動時的主機 tier 決定。讀取工具沒有 token 時仍用 admin token。

## Operation

| 狀態 | 意思 |
|---|---|
| `accepted` | 意圖已持久保存，尚未開始 |
| `running` | 執行中；daemon 重啟後從已保存的步驟接續 |
| `waiting_checks`、`waiting_external` | 等外部條件（checks、queue、workflow），到時間再跑 |
| `uncertain` | 某一步送出後沒有確定結果；以回查判斷，不重送 |
| `needs_attention` | 需要人處理（含回查多次仍無法證明） |
| `succeeded`、`failed`、`cancelled` | 終態 |

每個外部呼叫是一個具名步驟（`operation_steps`）。步驟意圖在呼叫前先 commit。逾時、連線中斷或之後的本機記錄失敗（`OSError`）時步驟記為 `uncertain`，之後由該步驟的 `reconcile` 讀回外部狀態：證明已發生就補記成功，無法證明（包括回查本身連不上）就維持 `uncertain` 並退避重試回查，五次後轉 `needs_attention`。回查次數用自己的計數（`uncertain_tries`），等待 checks／workflow 的輪詢不會用掉它。已完成的步驟在重跑時直接回傳保存的結果。

取消只在下一步之前生效，而且不跳過回查：`uncertain` 的操作收到取消時先立刻回查，證明那一步已發生就照常完成，所以 `cancelled` 不會掩蓋已送出的動作。`needs_attention` 可以取消（原因會註明哪一步從未證明），也可以 `resume`：已完成的步驟不重做，未證明的步驟再回查一次，不重送。操作的 actor、admin，或擁有該 action scope 的主體可以取消或 resume；事件記在實際操作的人名下。

第一批 action：

| Action | Scope | 外部呼叫 | 回查依據 |
|---|---|---|---|
| `session.send` | operate | `claude:send-message`，`clientMessageId = batc-<operation_id>` | BAT 接受後寫入的 turn 紀錄；沒有紀錄時讀 BAT 的對話，找 id 等於 `clientMessageId` 的 user 訊息。Codex 不保留這個 id，回覆遺失的 Codex 送字無法證明，會停在 `uncertain`／`needs_attention` |
| `session.answer` | operate | `claude:resolve-ask-user`／`resolve-permission`；必須帶 `tool_use_id` | 那個 tool use 已不在 pending |
| `session.interrupt` | operate | `claude:interrupt-turn`／`abort-session` | session 已不在 streaming |

Session action 在建立時先用 registry 與目錄判斷來源，人工、unknown、未啟用 write tier 的主機直接回 403，不寫入 operation；執行時 `service.py` 再做一次資源政策的即時檢查。新 action 以 `ActionDef` 註冊（`api_actions.py`），之後的 GitHub merge、部署、checkpoint 都用同一套步驟與回查規則。

Part A delivery actions 仍由 `POST /api/v1/operations` 受理：`github.pr.update`（integrate，repo opt-in）帶 `params={title?,body?}`、`expected_metadata_digest`；`github.pr.merge` 帶 `params={preview_id,method}`、`preconditions={expected_head_sha,expected_base_sha,preview_digest}`。`delivery.merge_and_deploy` 使用同 merge envelope，加 recipe 與 deploy scope；只部署經驗證的 actual merged SHA。舊 head-only 請求回 PRECONDITION_REQUIRED，點名 preview read。MCP `github_pr_update`／`github_pr_merge` 是 caller-token operation wrappers；`github_merge_preview_get` 為 observe read。新 CLI mutation 也要求 BATC_API_TOKEN。Contract_version 保持 ISO date `2026-10-08`（既有 contract 和本次變更同一天）；capabilities 宣告 metadata_update／merge_scope_preview 與 per-repo allow_pr_update。Part B deployment history／rollback／generation routes 尚未交付。

Metadata uncertain write 從 step.started_at 起滿 600 秒，GET 仍為 before 就在 delivery 表保存 not_applied／PR_METADATA_NOT_APPLIED，釋放同 PR 的 admission lock 並停止背景 GET，永不重 PATCH。Cancelled 保留 cancelled；UNCERTAIN_UNRESOLVED 保留原 needs_attention audit，resume 只讀 settlement 並以 PR_METADATA_NOT_APPLIED failed。新操作仍比較 metadata digest，晚到的舊寫入會在下次寫前被 PR_METADATA_CHANGED 擋下；GitHub 無 CAS 的窗口仍依 [delivery.md](delivery.md) 說明。

未過期且同 repository／PR／method／digest 的 merge_preview 重用 ID，原 expiry 不延長；保存時清除 expired 超過 24 小時、未被非 terminal merge／combined operation 引用的 rows。Files 只回 filename／status／additions／deletions／changes／previous_filename，不回 patch／blob／contents URLs。Dashboard 的事件重載使用 from_event=true，仍讀 PR／checks，同 head／base 的完整 scope 每 60 秒最多一次；手動讀取重新預覽。等待 checks 只核對 head／base，完整 scope 在首次 submit step 前重新核對；暫時 scope read failure 可 resume，不建立 failed submit step。merge.verify 受影響 PR 的 merged_after=true／independent=true 代表它在本次 merge 之後獨立落地，允許通過；最近 PR 列表按 updated desc，只讀到 admission 時間，已保存 candidates 仍全部驗證。

## 資源目錄

`inventory.py` 用自己的 read-only `Fleet` 輪詢每台主機：client 核心拒絕所有寫入 channel，所以觀測不可能改動 BAT。結果寫入 `hosts_observed` 與 `sessions_observed`。

- 主機連不上時保留最後一次的列，標 `stale: true, stale_reason: host_unreachable`，不刪除。
- 一列要連續兩次成功列舉都沒出現，才標 `gone`。`workspace:load` 回 null 或格式不對時算失敗，不當成空清單。
- 一次輪詢沒觀測到的欄位沿用上次的值：讀 meta 失敗的 session 保留上一列；這次沒重讀 state（`auto` 只在 session 執行中才讀）時保留上次的 pending；活動時間只會往後。
- 每台主機各自排程輪詢，慢的主機不會拖住其他主機。已從設定移除的主機不出現在列表。
- Host stale 在讀取時推導，不向 sessions 發送 host flap 事件；只有 session-specific 缺席／gone／scope change 記 stale/fresh。
- 首次觀測寫 `session.added`；值或非時間欄位 freshness 改變寫 `session.updated`，gone 後重現寫 `session.reappeared`。三者的 body 都帶 `fields_stale` 與 `field_evidence`；digest 與 `changed_fields` 包含這兩欄，即使沿用的 loaded／streaming 值相同，meta 失敗及恢復也會通知。`field_observed_at`、`last_activity_ms` 等時間單獨變動不寫 update；連續相同失敗／成功不寫事件。
- 欄位 freshness 與 `session.stale`／`session.fresh` 的單一 specific reason 分開，可同時 stale。成功列舉缺席的 `session.gone` 規則沿用上文。
- `order=activity` 的分頁鍵是活動時間；翻頁期間活動時間變動的列可能重複或漏掉，要完整清單用 `order=id`。
- `GET /api/v1/sessions` 用 keyset 分頁（`order=activity` 或 `id`）。游標綁定篩選條件；第一頁回 `as_of`（當下事件游標），之後以 `/api/v1/events?after=as_of` 追變化，不必反覆重列。

設定：

```toml
[api]
inventory_interval_s = 60   # 每台主機的輪詢間隔；失敗時指數退避到 600 秒
stale_after_s = 180         # 超過這個時間沒成功觀測就標 stale
activity_every = 5          # 每 N 次才查 transcript／archive 的活動時間（最慢的部分）
allowed_origins = []        # 額外允許的瀏覽器 Origin（loopback 已允許）
```

## 事件

`api_events` 是單一、持久、單調的游標，涵蓋 task、operation、session、host。Task 事件在同一個交易中寫入 `events` 與 `api_events`；舊 journal 開啟時以 `PRAGMA user_version` 一次性回填。`work_events`（Hermes 的里程碑 feed）與 webhook 推播仍用原本的 `events.event_id`，不受影響。

- 所有事件增加 provenance context；`history.backfilled` 預設不進 events／SSE，明確 `kind=history.backfilled` 才顯示，next_cursor 仍跨過隱藏 seq。`related_resource_type/id` 查資源索引，原 `resource_type/id` 仍是直接主體。完整契約見 [observation.md](observation.md)。
- `GET /api/v1/events?after=N&limit=M` → `{events, next_cursor, head_cursor, has_more}`。
- `GET /api/v1/events/stream`：SSE，支援 `Last-Event-ID`，15 秒 keepalive，最多 16 條同時連線（每個 actor 最多 8 條），單條最長 30 分鐘。串流每 5 秒重新驗一次 token，撤銷或過期後就結束。瀏覽器 `EventSource` 不能帶 Authorization，Dashboard 以 `fetch` 讀串流。

資源 `…/history` 使用安全的遞迴摘要：reason／previous_reason 只保留已知固定 enum 或 null；caller 的 request_ted／task result／command conflict／operation diagnostic prose 移除，保留原已記錄的機器 reason_code／error_code。所有 title、status_reason、git_author claim、scalar body/request/response/evidence 等 prose 入口排除，含 history.resource 及 saved_snapshot；來源 evidence 只留結構化表／ID／enum／hash。Scalar source 只允許固定來源 enum，ref／external_ref 只允許無空白的 ID/Git ref/URL token；原 journal 與既有 work_events 的文字不改。完整 producer/value/shape 稽核見 [observation.md](observation.md)。

History 的 since／until 是 inclusive UTC epoch seconds，按 occurrence 篩選，排序仍按 seq。Context 缺少 occurred_at_epoch 才以 api_events.created_at fallback；明確 JSON null 是未知發生時間，不符合任何單邊／雙邊界線。無界線仍顯示該 fact 且 occurred_at 為 null。Coverage.unknown_occurrence_times_excluded 在有時間界線時為 true（表示排除規則，非筆數）；無界線為 false。Coverage.first_recorded_at 仍是最早 journal 記錄時間，可為 migration 時間，不能當發生時間。

History／relations 的 opaque cursor 在任何 journal read 前驗證 version、filter hash、as_of 型別與 key；之後才讀 head 驗上界並查資源／結果。History key 為 int，relations key 為恰兩元素的 [int, str]；bool 不是 int，null 不是有效 key 或元素。錯 key 一律 `INVALID_CURSOR`／422，包含資源沒有 rows 或 execution_id／include_closed 篩掉全部 rows 的情況；合法游標的分頁與 as_of 不變。

## 路由

| 方法與路徑 | Scope | 說明 |
|---|---|---|
| `POST /api/v1/artifacts` | manage | artifact.upload intent；body 為 target／params／preconditions，Idempotency-Key，?wait |
| `POST /api/v1/artifacts/uploads/{op_id}/content` | manage＋同 actor 或 admin | body 前驗證 action／state／Content-Length；只收 application/octet-stream，拒絕 chunked；operation 自己的 staging |
| `GET /api/v1/artifacts?limit=&cursor=` | observe | 分頁 ID 與 latest ready 的展示 metadata；輸入選擇仍須精確 ref |
| `GET /api/v1/artifacts/{art_id}/revisions/{revision}` | observe | immutable metadata 與 materialization evidence |
| `GET /api/v1/artifacts/{art_id}/revisions/{revision}/content` | observe | attachment download，nosniff／no-store；無 inline preview |
| `GET /api/v1/version` | 無 | connector、api_version、contract_version |
| `GET /api/v1/capabilities` | observe | actor、scopes、主機 tiers、actions 與是否允許 |
| `GET /api/v1/hosts` | observe | 主機可達性、stale、最近 discovery；host/discovery/after/limit 可讀 scope |
| `GET /api/v1/hosts/{host}/discovery` | observe | 每 profile 最新 scope、authority、outside_scan 及 discovery.changed 事件分頁 |
| `GET /api/v1/sessions` | observe | Keyset；host/provenance/access/attention/include_gone/order/cursor/limit，加 profile_id/project_id（可多值）/work_item_id/execution_id/provider/has_tab/loaded/streaming/lifecycle/stale/relation_scope（current/history） |
| `GET /api/v1/sessions/{host}/{id}` | observe | 一列與連到它的工作項目；`live=true` 另附即時資源政策判定 |
| `GET /api/v1/sessions/{host}/{id}/history`、`…/relations` | observe | Journal-only 分頁 timeline／使用區間；history 固定 as_of、actor evidence、版本 |
| `GET /api/v1/worktrees/{wt_id}`、`…/history`、`…/relations` | observe | 只讀已知 creation intent 身分；不掃主機／Git，沒有 ownership grant |
| `GET /api/v1/tasks/{task_id}/sessions`、`…/history` | observe | Execution 的 lead/reviewer/follow-up 關係分頁；不以最新 session pointer 取代歷史 |
| `GET /api/v1/sessions/{host}/{id}/messages` | observe | 經 read-only fleet 讀對話 |
| `GET /api/v1/policy` | observe | mutation 清單與各主機設定 |
| `GET/POST /api/v1/operations` | observe／依 action | 列表；建立（`Idempotency-Key` 標頭或 `idempotency_key`，`?wait=0-60` 秒，格式錯誤時在保存前回 422） |
| `GET /api/v1/operations/{id}`、`POST …/cancel`、`POST …/resume` | observe／actor 或 action scope | 含步驟；取消見上；resume 只用於 `needs_attention` |
| `GET /api/v1/events`、`/events/stream` | observe | 事件分頁、SSE |
| `GET /api/v1/tasks/{task_id}` | observe | 既有 `work_status` |
| `GET /api/v1/repositories/{owner}/{repo}/pulls/{number}?method=&from_event=true` | observe | PR title/body 與 metadata_digest；重用／保存 immutable mpv merge_preview（完整 commits、檔案摘要、stacks／chains／indirect PRs、blocking）；事件 reload 60 秒 scope 節流，SHA 變立即刷新，省略 from_event 為手動預覽 |
| `GET /api/v1/delivery/previews/{mpv_id}` | observe | 讀保存的 merge scope／digest／expiry，不刷新來源 |
| `GET /api/v1/integrations/candidates?host=` | observe | 可放進 PR 的 agent 成果與 checkpoint，及送過的 PR |
| `GET /api/v1/integrations/previews/{ipv_id}` | observe | 預覽文件與是否過期 |
| `GET /api/v1/integrations?repository=&pull_number=`、`/integrations/{op_id}` | observe | 一個 PR 的整合紀錄、一次整合與各來源 receipts |
| `GET /api/v1/projects`、`/projects/{prj_id}` | observe | 專案樹與統計；一個專案與它的工作項目樹（[work-items.md](work-items.md)） |
| `GET /api/v1/work-items`、`/work-items/{wi_id}` | observe | 跨專案的工作項目（`pending=true`：等人決定）；一個項目與它的完成狀態、連結、紀錄 |

錯誤格式為 `{"error": {"code", "message"}}`：401 未驗證、403 權限或資源唯讀（代碼同 resource-policy）、404、405、409 冪等衝突、422 參數錯誤、502 BAT 錯誤。

## 附件（Part A）

`capabilities.artifacts` 公開 file／selection／store／MCP／upload window limits，以及 host helper 配置與已觀測 readiness。MCP 只有 artifact_upload、artifacts_list、artifact_get；confirmation 經 operation_submit 的 checkpoint.continue.revalidate。沒有 materialize action、store delete 或新 BAT channel。完整參數與錯誤見 [artifacts.md](artifacts.md)。

觀測 Part A 使用同 journal 的讀服務：MCP 只新增 inventory_session、inventory_worktree、resource_history、resource_relations 四個 tools；discovery 是 inventory_hosts 的參數。CLI 為 batc inventory/history/relations。History、relations、scope 的 GET 不呼叫 host、不寫入 journal；inventory 只保存 latest rows，沒有每 poll revisions。Dashboard 的跨專案歷史、scope 卡及 reopen/SSE 去重是 [observation.md](observation.md) 的 Part B。

## Task Service operations（2026-10-08，Part A）

依[統一操作規格](operations-unification.md)的 Part A，以下能力經既有 `POST /api/v1/operations`／`/rpc op_submit`，不新增 task 寫入 URL。舊 RPC／MCP 保留原結果，增加 `operation_id`、`operation_status`；operation succeeded 只表示該次控制完成，不表示 task done。

| Action | target | params | Scope／身分 | 舊入口 |
|---|---|---|---|---|
| `task.submit` | host、workspace | project、original_words 與原 work_submit 選項 | start | work_submit |
| `task.pause` | task_id | abort_current、actor、source_message_id | operate | work_pause |
| `task.resume` | task_id | actor、source_message_id | operate | work_resume |
| `task.mark_stage` | task_id | stage、ref、actor | manage；verified done task | work_mark_stage |
| `session.send` | task_id | text、step_id | 原 task capability／本機 admin 相容路徑；不授予一般 operate token task-scoped 權限 | task_send |
| `task.verify` | task_id | 空物件；不能自填 argv、exit code 或 evidence | 原 task capability／本機 admin 相容路徑 | task_run_verification |
| `task.request_ted` | task_id | reason | 同上 | task_request_ted |
| `task.command.reconcile` | task_id、command_id | 原 outcome、actor、source、evidence、observed_result、turn_ref、candidate／tree、next_prompt | 原一次性 command capability；admin 不能代替 | work_reconcile、task-reconcile |

`preconditions.control_version` 可要求目前版本。舊 task tools 新增可選 `idempotency_key`／`control_version`，CLI `task-reconcile` 新增 `--key`／`--control-version` 並遵守 `--read-only`。key 以驗證 actor 為範圍；相同 key／params 回原 operation，不同內容 409 `IDEMPOTENCY_CONFLICT`。Goose 的原 `step_id` 在未指定 key 時仍是 task send 的重試身分。其他無 key 的舊 task controls 每次使用獨立 request identity，不跨次去重；no-key sentinel／null 投影留在 Part B。舊 work_submit 的 201–256 字 key 由相容 adapter 保存原字串、以 SHA-256 映射到既有 200 字 operation key 上限；通用 HTTP 上限不變。

Task-bound operation 受理時固定 task `control_version`；session target 另固定 host／session／role，存於 `external_refs.admission_binding`（server admission binding，不是 caller precondition）。省略 `preconditions.control_version` 也不能跨 pause／resume 或換 session 執行：第一個 effect 前以 `CONTROL_VERSION_CONFLICT`／`TASK_BINDING_MISMATCH` failed，零 frame／command／task write。request hash 與 caller preconditions 不變；同 key 仍重讀原成功或拒絕。pause／resume 不覆寫較新 incarnation；已成功 receipt／未知 frame readback 沿用原恢復。升級前無 binding 的 operation 保留原 execution-time binding。詳見[盤點與儲存規則](operations-unification.md)。

原 task／continuation／pause／resume／stage／observed verification／request-Ted／reconcile 的 local effect 與 operation step receipt 同交易提交，不另建 task 狀態表。pause 先保存 paused／control_version，abort 再記獨立 step；等待 task lock 或 verifier 不延後 pause 的持久化。RPC 最多等 30 秒；未完成時以 operation ID 回查，pause 可回已保存的 task snapshot。reconcile capability 只存 hash，消耗與回執原子提交；已消耗的 capability 只能用原 key 重讀自己的 operation，不能建立新控制。

task command receipt succeeded 時，`external_refs.task_id`／`command_id`／`control_version` 已與 receipt 同交易保存，版本來自 command 的 dispatch binding；prepared operator command 也適用。舊缺 refs 的 receipt 在 operation 恢復／讀回前修復 link，不重跑 effect 或派送 frame；standalone operation 不寫 task refs。

CLI `task-reconcile --key` 把 key 同時交原 admin-only capability issuer，依既有 admin secret 綁定 task／command／key，使跨次重試保留 actor。沒有 key 時維持原新發一次性 capability；發行本身只是 connector credential data，不執行 task command，也不授予一般 token 對帳權限。

task-owned session 的 send／answer／interrupt／permissions 都先經 resource policy，再進 daemon 原 coordinator；舊直接 service tools 也經相同 gate。鎖順序為 task → session → host write lock → BAT semaphore；client-resume、answer、abort 與每個 permission channel 在 frame 前重查 journal 的版本與 ownership。任意 before_invoke callback 不授予插隊權限。standalone managed session 沿用原行為。

背景 trusted verification 期間的 pause／版本改變為控制取消：task 保留 verifying／paused，取消的 run 不寫 evidence，不升級 needs_ted／uncertain。resume 後下一個 tick 從頭跑，包括 dependency retry；paused task 不計 verification_deadline。lease lost／binding mismatch 保留目前 state，交既有 owner／修復 binding 後再 resume；真正 verifier error 仍是 verification_error／needs_ted。沒有新增 event 或錯誤碼。

| 409 task code | 處理 |
|---|---|
| `TASK_OWNER_UNAVAILABLE` | pointer／journal／row／owner lease 不可用；連既有 owner，不啟動第二個 daemon |
| `TASK_BINDING_MISMATCH` | registry 與 task ownership 不一致；停止並查 work_status |
| `CONTROL_VERSION_CONFLICT` | 控制版本已改；讀狀態，不自動換成新版重試 |
| `TASK_PAUSED`／`TASK_VERIFYING` | task 暫停／驗證中；不可用 queue、force、continue、approve-pending 或 relay 插隊 |
| `TASK_SEND_NOT_DISPATCHED`／`NOT_ACCEPTED`（task send） | operation 沒有已接受／settled 的原 send command；failed 結果沿用原 key，新的派送用新 key |
| `TASK_COMMAND_PENDING`／`TASK_RECONCILIATION_REQUIRED` | 原 command 結果未證明；由 coordinator 回查／command capability 對帳，不重送 |
| `TASK_STATE_BLOCKED` | current lead／task state 不允許該控制；waiting_permission 不接受 send |
| `TASK_OWNED_CONTROL_REQUIRED` | 低階 failover／worktree／外部 verification 不管理 task-owned session；cleanup 保持 KEEP |

policy admission 仍 403、無 operation row；執行期拒絕保留 failed operation 與原 code。`OWNER_CONFLICT` 是 `batc serve` 啟動拒絕，附既有 owner_id、db_path、pid、endpoint、lease_path；不同 `--db` 也不能建立第二個 fleet authority。

## 尚未涵蓋

- Artifact 的 manual／managed capture 與 accept（Part B）、跨主機接續（Part C），見 [artifacts.md](artifacts.md)。Dashboard、GitHub 與 checkpoint 已有各自設計。

- GitHub 部署 history／rollback／environment generation／runtime check 為 delivery Part B（第二步），尚未加入路由。Dashboard、merge、metadata、checkpoint 與 integration 入口已交付。
- 既有 MCP 寫入工具（`session_send` 等）仍直接呼叫 service；它們受同一套資源政策約束，但不留 operation 紀錄。之後改為經 `operation_submit`。
- Part B：其餘 legacy writes 的 operations、no-key sentinel／讀取投影、完整結果與外部 steps 拆分。Task controls 與 A07 共用 gate 已在 Part A 完成。
- `import-bat --output PATH --force` 是 owner 啟動前的本機 config 安裝指令，僅寫指定設定檔，保留現有路徑。
- operation cancel/resume 已授權且 evented，不新增其 control operations；api-token issue/revoke 只改 connector 資料、不觸及 BAT/Git/provider，也不新增 operation。
