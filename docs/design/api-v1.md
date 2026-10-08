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

Part A delivery actions 仍由 `POST /api/v1/operations` 受理：`github.pr.update`（integrate，repo opt-in）帶 `params={title?,body?}`、`expected_metadata_digest`；`github.pr.merge` 帶 `params={preview_id,method}`、`preconditions={expected_head_sha,expected_base_sha,preview_digest}`。`delivery.merge_and_deploy` 使用同 merge envelope，加 recipe 與 deploy scope；只部署經驗證的 actual merged SHA。舊 head-only 請求回 PRECONDITION_REQUIRED，點名 preview read。MCP `github_pr_update`／`github_pr_merge` 是 caller-token operation wrappers；`github_merge_preview_get` 為 observe read。新 CLI mutation 也要求 BATC_API_TOKEN。Contract_version 保持 ISO date `2026-10-08`（既有 contract 和本次變更同一天）；capabilities 宣告 metadata_update／merge_scope_preview 與 per-repo allow_pr_update。Part B 宣告 deployment_history／environment_generation／runtime_check／rollback_readiness；缺 verification 的 recipe readiness 點名缺少設定，deploy feature=false（history 仍可讀）。


Part B 的 `deployment.start` 帶 `{source_sha, retry_of?}`（40 hex、optional retry_of 只取 saved identity 且 SHA 相符）；`deployment.rollback` 帶 `{deployment_id}`。兩者及 combined 都需 `{expected_environment_generation, expected_recipe_digest}`，先讀 `deployment_preview`（`GET /api/v1/deployments/preview?recipe=NAME`）。舊 start 缺這兩欄回 DEPLOY_PREVIEW_REQUIRED，message 點名該 read。Generation CAS 在第一個 local deploy.select step，同交易保存 deployment／desired／event，stale operation 異步 failed／ENVIRONMENT_CHANGED；不改 core admission。Combined preview.base_ref 與 recipe.ref 不同為 DEPLOY_SOURCE_NOT_ON_REF（422、zero PUT／POST）；start／retry／SHA rollback 在 dispatch 前以 ref...sha identical／behind 證明可達，否則同 code、zero POST。

MCP `deployment_start`／`deployment_retry`／`deployment_rollback` 為 caller-token operation wrappers，confirm=true、BATC_API_TOKEN 必填，read-only server 不註冊。Retry 從 `deployment_status` 的 saved identity 建新的 deployment.start，只換新 key／generation／digest，不重新 merge 或換 latest。讀取工具 `deployment_preview`／`deployment_status`／`deployments_list`／`deployment_environment_get` 需 observe。CLI `delivery preview NAME`、`history NAME --cursor CURSOR --limit 50`、`show DEP_ID` 讀同一 journal；`deploy NAME --sha SHA`、`rollback NAME DEP_ID`、`retry NAME DEP_ID` mutation 另必填 `--generation N --recipe-digest DIGEST --key KEY`。`delivery merge --recipe NAME`／MCP github_pr_merge 的 combined 也傳同一對 preconditions，不隱式代選最新。

Deployment success 必須原固定 run attempt＋指定 job completed/success＋目標 environment 無 pending＋recipe runtime 的版本及／或健康證據（至少一種）。API 明示 version_checked／health_checked；job success 不替代 readback。Verifier 只存白名單 response fields；HTTPS（loopback HTTP 僅測試）、無 redirect、timeout／max_bytes 有界，Bearer 只用後端 token_ref。Dispatch 429 是 refusal：依 Retry-After 在 wait_max_s 內等待，每次再送前精確查 token，找到即採用；lost write 查不到仍 uncertain，不重新 POST。

Cancel 不取消 provider run／queue：provider 未終態時仍持有環境 slot 與 recipe deploy lock，包含 cancelled combined merge、dispatch 與尚待定位的 on_merge。Combined on_merge 取消後若 merge 才落地，核對 reviewed head／實際 merge SHA 可達 recipe ref，再追 exact push run 至終態；legacy 未終態亦占用 repository（不分大小寫）／environment 的跨 recipe slot。Settled history 不再回查 provider／runtime；current run／runtime 與 unresolved locate 依 `[github] deployment_reconcile_interval_s`（預設 300、範圍 60–86400 秒）節流，cadence 跨 restart，相同證據不增 row version。只讀 reconcile_deployments 以原 snapshot 查 provider facts，終態才釋放，不 dispatch／resume／改 cancelled operation。晚到舊代不升 current，記 superseded；runtime 舊版使 current=null、ENVIRONMENT_VERSION_DRIFT，保留 last_verified，無自動重派。Rollback 是同 recipe/environment saved verified SHA／artifact 的新 generation／operation／run；API 列 not_undone，刪／inactive record 不回退。

Deployment tables 是每次 open 的冪等 DDL，不佔 user_version。Reviewer 分配 history data step 3：僅 version=2 時一交易回填舊 operations results／refs、設 3；crash rollback、重開 no-op。Old successes 為 unverified，never current／rollback；舊非終態已 dispatch 僅查原 run，未 dispatch 停 DEPLOY_PREVIEW_REQUIRED。Observation step 2 由 #35 提供，本包不代做。

Metadata uncertain write 從 step.started_at 起滿 600 秒，GET 仍為 before 就在 delivery 表保存 not_applied／PR_METADATA_NOT_APPLIED，釋放同 PR 的 admission lock 並停止背景 GET，永不重 PATCH。Cancelled 保留 cancelled；UNCERTAIN_UNRESOLVED 保留原 needs_attention audit，resume 只讀 settlement 並以 PR_METADATA_NOT_APPLIED failed。新操作仍比較 metadata digest，晚到的舊寫入會在下次寫前被 PR_METADATA_CHANGED 擋下；GitHub 無 CAS 的窗口仍依 [delivery.md](delivery.md) 說明。

未過期且同 repository／PR／method／digest 的 merge_preview 重用 ID，原 expiry 不延長；保存時清除 expired 超過 24 小時、未被非 terminal merge／combined operation 引用的 rows。Files 只回 filename／status／additions／deletions／changes／previous_filename，不回 patch／blob／contents URLs。Dashboard 的事件重載使用 from_event=true，仍讀 PR／checks，同 head／base 的完整 scope 每 60 秒最多一次；手動讀取重新預覽。等待 checks 只核對 head／base，完整 scope 在首次 submit step 前重新核對；暫時 scope read failure 可 resume，不建立 failed submit step。merge.verify 受影響 PR 的 merged_after=true／independent=true 代表它在本次 merge 之後獨立落地，允許通過；最近 PR 列表按 updated desc，只讀到 admission 時間，已保存 candidates 仍全部驗證。

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
| `GET /api/v1/repositories/{owner}/{repo}/pulls/{number}?method=&from_event=true` | observe | PR title/body 與 metadata_digest；重用／保存 immutable mpv merge_preview（完整 commits、檔案摘要、stacks／chains／indirect PRs、blocking）；事件 reload 60 秒 scope 節流，SHA 變立即刷新，省略 from_event 為手動預覽 |
| `GET /api/v1/delivery/previews/{mpv_id}` | observe | 讀保存的 merge scope／digest／expiry，不刷新來源 |
| `GET /api/v1/deployments/preview?recipe=NAME` | observe | repository ID、recipe digest／readiness、generation、desired／current／last_verified／observed、ordering／rollback limits |
| `GET /api/v1/deployments?recipe=NAME&cursor=&limit=` | observe | keyset history（created_at／dep ID，預設 50、上限 200），offline 可讀，identity／evidence／rollback eligibility |
| `GET /api/v1/deployments/{dep_id}` | observe | fixed identity、run／attempt、operation／provider URLs、state／is_current／evidence；missing DEPLOYMENT_NOT_FOUND |
| `GET /api/v1/deployment-environments?recipe=NAME` | observe | desired generation／current／last_verified／observed_at／slot／attention；已移除 recipe 仍可讀保存資料 |
| `GET /api/v1/integrations/candidates?host=` | observe | 可放進 PR 的 agent 成果與 checkpoint，及送過的 PR |
| `GET /api/v1/integrations/previews/{ipv_id}` | observe | 預覽文件與是否過期 |
| `GET /api/v1/integrations?repository=&pull_number=`、`/integrations/{op_id}` | observe | 一個 PR 的整合紀錄、一次整合與各來源 receipts |
| `GET /api/v1/projects`、`/projects/{prj_id}` | observe | 專案樹與統計；一個專案與它的工作項目樹（[work-items.md](work-items.md)） |
| `GET /api/v1/work-items`、`/work-items/{wi_id}` | observe | 跨專案的工作項目（`pending=true`：等人決定）；一個項目與它的完成狀態、連結、紀錄 |

錯誤格式為 `{"error": {"code", "message"}}`：401 未驗證、403 權限或資源唯讀（代碼同 resource-policy）、404、405、409 冪等衝突、422 參數錯誤、502 BAT 錯誤。

## 尚未涵蓋

- GitHub 部署 history／rollback／environment generation／runtime check 為 delivery Part B（第二步），尚未加入路由。Dashboard、merge、metadata、checkpoint 與 integration 入口已交付。
- 既有 MCP 寫入工具（`session_send` 等）仍直接呼叫 service；它們受同一套資源政策約束，但不留 operation 紀錄。之後改為經 `operation_submit`。
- `task.submit`／`pause`／`resume` 尚未包成 operation。
