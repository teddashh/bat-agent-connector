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

Scopes：`observe`（讀目錄、操作、事件、政策）、`operate`（驅動 managed session）、`start`（開新的 managed agent session，例如 `checkpoint.continue`）、`manage`（專案、工作項目與連結）、`approve`（確認工作項目完成；與 `manage` 分開，回報完成的 agent 不能自己簽核，見 [work-items.md](work-items.md)）、`merge`、`deploy`、`integrate`（把成果推送到 PR 的 head 分支，見 [integration.md](integration.md)）、`cleanup`（reviewed resource cleanup／release）、`cleanup_discard`（只丟棄未提交內容；person-controlled，agents 不要求，Hermes／Grokbot tokens 不給）。Journal 只存 token 的 SHA-256。操作的 actor 一律取自 token；request body 或 MCP 參數自報的名字沒有授權效果。冪等鍵的唯一性以 actor 為範圍：同 actor、同 key、同內容回原 operation；同 key 不同內容回 409。

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

## 資源目錄

`inventory.py` 用自己的 read-only `Fleet` 輪詢每台主機：client 核心拒絕所有寫入 channel，所以觀測不可能改動 BAT。結果寫入 `hosts_observed` 與 `sessions_observed`。

- 主機連不上時保留最後一次的列，標 `stale: true, stale_reason: host_unreachable`，不刪除。
- 一列要連續兩次成功列舉都沒出現，才標 `gone`。`workspace:load` 回 null 或格式不對時算失敗，不當成空清單。
- 一次輪詢沒觀測到的欄位沿用上次的值：讀 meta 失敗的 session 保留上一列；這次沒重讀 state（`auto` 只在 session 執行中才讀）時保留上次的 pending；活動時間只會往後。
- 每台主機各自排程輪詢，慢的主機不會拖住其他主機。已從設定移除的主機不出現在列表。
- `last_activity` 以外的欄位有實質變化時，才寫 `session.added`／`session.updated`／`session.gone` 事件。
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

- `GET /api/v1/events?after=N&limit=M` → `{events, next_cursor, head_cursor, has_more}`。
- `GET /api/v1/events/stream`：SSE，支援 `Last-Event-ID`，15 秒 keepalive，最多 16 條同時連線（每個 actor 最多 8 條），單條最長 30 分鐘。串流每 5 秒重新驗一次 token，撤銷或過期後就結束。瀏覽器 `EventSource` 不能帶 Authorization，Dashboard 以 `fetch` 讀串流。

## 路由

| 方法與路徑 | Scope | 說明 |
|---|---|---|
| `GET /api/v1/version` | 無 | connector、api_version、contract_version |
| `GET /api/v1/capabilities` | observe | actor、scopes、主機 tiers、actions 與是否允許 |
| `GET /api/v1/hosts` | observe | 主機可達性與 stale |
| `GET /api/v1/sessions` | observe | 分頁目錄；`host`、`provenance`、`access`、`attention`、`include_gone`、`order`、`cursor`、`limit` |
| `GET /api/v1/sessions/{host}/{id}` | observe | 一列與連到它的工作項目；`live=true` 另附即時資源政策判定 |
| `GET /api/v1/sessions/{host}/{id}/messages` | observe | 經 read-only fleet 讀對話 |
| `GET /api/v1/policy` | observe | mutation 清單與各主機設定 |
| `GET/POST /api/v1/operations` | observe／依 action | 列表；建立（`Idempotency-Key` 標頭或 `idempotency_key`，`?wait=0-60` 秒，格式錯誤時在保存前回 422） |
| `GET /api/v1/operations/{id}`、`POST …/cancel`、`POST …/resume` | observe／actor 或 action scope | 含步驟；取消見上；resume 只用於 `needs_attention` |
| `GET /api/v1/events`、`/events/stream` | observe | 事件分頁、SSE |
| `GET /api/v1/tasks/{task_id}` | observe | 既有 `work_status` |
| `GET /api/v1/integrations/candidates?host=` | observe | 可放進 PR 的 agent 成果與 checkpoint，及送過的 PR |
| `GET /api/v1/integrations/previews/{ipv_id}` | observe | 預覽文件與是否過期 |
| `GET /api/v1/integrations?repository=&pull_number=`、`/integrations/{op_id}` | observe | 一個 PR 的整合紀錄、一次整合與各來源 receipts |
| `POST /api/v1/cleanup-previews` | observe；discard 另需 cleanup_discard | target 四類與 per-item choices，純讀 signed preview；TTL **15 分鐘**（integration 一小時） |
| `POST /api/v1/operations` action=cleanup.apply | cleanup；discard 另需 cleanup_discard | preview_token／preview_id／preview_fingerprint；PREVIEW_MISMATCH／EXPIRED／BLOCKED／STALE 必須重新 preview |
| `GET /api/v1/cleanup-retained` | observe | 實際可讀 refs／objects 與 unavailable；host/resource_id/query/limit/cursor；Part A 無 restore |
| `GET /api/v1/cleanup-tombstones`、`/{resource_id}` | observe | query/original_id/host/work_item_id/kind/limit/cursor；永久原 ID aliases、位置、原因、PR、receipts |
| `GET /api/v1/projects`、`/projects/{prj_id}` | observe | 專案樹與統計；一個專案與它的工作項目樹（[work-items.md](work-items.md)） |
| `GET /api/v1/work-items`、`/work-items/{wi_id}` | observe | 跨專案的工作項目（`pending=true`：等人決定）；一個項目與它的完成狀態、連結、紀錄 |

錯誤格式為 `{"error": {"code", "message"}}`：401 未驗證、403 權限或資源唯讀（代碼同 resource-policy）、404、405、409 冪等衝突、422 參數錯誤、502 BAT 錯誤。

## 整理合約（Part A）

見 [cleanup.md](cleanup.md)：preview 只讀、一份 snapshot、每 host 序列化並限制讀取時間，500 resources 上限。
Host target 接受 configured host 或有 resource history 的原 host。Host 移除後，各來源的 session／worktree／
branch／carrier ID 保持不變，全部 retained／OBSERVATION_UNAVAILABLE，不送 BAT／SSH；同 preview 的其他 host 正常 apply。
Apply 只執行同一 reviewed fingerprint；16 KiB signed token，15 分鐘到期。release_undelivered 保留 commits 與
branch，不需 cleanup_discard；只有 discard_uncommitted 摧毀內容。Accepted actor/scopes/choices 固定，resume
沿用原 OperationService 規則，不再檢查 discard scope；回執記錄 resumer。保留設定 keep/forever/false。
Resumed run 在沒有任何 operation_steps row 時若 expiry／mismatch／early refusal，先釋放全部 own reserved
guards／session markers、pending／running 回執改 failed 並保存 refusal code；已有 step 不走此 release。
完全無 step、只因 read-only failure 留下的 uncertain 回執也在 refusal 時結清為 failed。
Item status=already_absent 是獨立 definitive receipt，result.items 與 summary.already_absent 分別列出，
不算 retained。它只保存經全 plan 驗證的 absence／original IDs，沒有 per-item host call、tombstone／aliases
或 registry cleaned mark；不是 cleanup 移除的證據。Dependencies 接受 succeeded 或 already_absent。
沒有 reclaim item 但有可釋放 cap 的 already_absent active 非 task session（無自己的 worktree 或 carrier
同樣 already_absent）時，preview.ready=true；同一 cleanup.apply 只結算本機 retirement／receipt。
Preview 本身不改 registry；retained carrier、未決或已退休 row 不會單獨開啟 apply。
Confirmed planner stop 的 registry status=stopped，已不占 host cap；ACK／read-back 未確認時不改。
Already-absent session 的 worktree 本次 succeeded／already_absent，或沒有自己的 worktree時，status 改為
absent_at_cleanup，retirement 記 actor／operation_id／carrier_resource_id。回執 after_state 有
capacity_released=true、registry_status、carrier_resource_id、stopped_by_cleanup=false；不建 session tombstone。
Worktree retained 時 absent session 的 active slot 留著供 resume。已退休的 ID 的 drive／client-resume／
same-ID start／registry recovery 回 SESSION_RETIRED (409)；人可用新 ID 經原 cap reserve，ownership 仍 connector_managed。
GET /operations/{id} 的 cleanup_receipts／tombstone 回執包含 completed_phases=[{resource_id,phase,effect,step,result}]、
refused_phases（同形但 error）及 cancel_requested。它們投影 durable steps／operation，含 approved DAG 的
prerequisites，不因後續失敗消失。result.items 是最後一次 progress snapshot；cancel 後以 live cleanup_receipts
或 operation.cancel_requested 判斷取消，不以舊 result.items 的 flag 判斷。effect=additive（preserve）／runtime（stop）／destructive（discard、remove.*）。
Gate 通過後的 process／transport／decode／schema failure 是 uncertain，保留 reservation、只回查。
已完成 runtime／destructive phase 後 refusal，item=uncertain、error.code=CLEANUP_PARTIAL_STATE，
另記 refused_phase／refused_code，operation=needs_attention；解除 blocker 後 resume 以新的 .aN attempt
重核原 preconditions，完成步驟不重做。Discard after snapshot 存在 succeeded step，resume 不採納新內容。
Cancel 已有 runtime／destructive partial 的 item 仍 uncertain、cancel_requested=true、reservation 保留；
cancelled parent 不表示內容保留，也不能 resume。需人工檢視，本包無強制解鎖／takeover。只有未送出或
pure additive、全部已結清的 item 可 cancelled／釋放 guard，回執仍列已建立的 pins。
Legacy batc cleanup／session_cleanup 只評估，apply 回 LEGACY_CLEANUP_DISABLED (409)，指向 resource-cleanup；
auto_cleanup deprecated，只保留解析，不啟用任何 writes。Fanout planner 只 stop，worktree 留給 reviewed cleanup。
Restore、reviewed task cleanup、TaskDaemon tombstone backfill 在 Part B；clones/areas 退休與 refs/batc/* 刪除不在本包。

## 尚未涵蓋

- Dashboard 畫面（W09）、GitHub merge／部署（W07／W08）、checkpoint 接續（W04）。這些新增 action 與路由，不改這裡的合約。
- 既有 MCP 寫入工具（`session_send` 等）仍直接呼叫 service；它們受同一套資源政策約束，但不留 operation 紀錄。之後改為經 `operation_submit`。
- `task.submit`／`pause`／`resume` 尚未包成 operation。
