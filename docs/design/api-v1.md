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

Scopes：`observe`（讀目錄、操作、事件、政策）、`operate`（驅動 managed session）、`manage`、`merge`、`deploy`。Journal 只存 token 的 SHA-256。操作的 actor 一律取自 token；request body 或 MCP 參數自報的名字沒有授權效果。冪等鍵的唯一性以 actor 為範圍：同 actor、同 key、同內容回原 operation；同 key 不同內容回 409。

瀏覽器防護：Host 必須是 loopback（擋 DNS rebinding）；有 Origin 時須是 loopback 或 `[api] allowed_origins`；只接受 bearer token，不用 cookie，所以沒有 CSRF 面。

## Operation

| 狀態 | 意思 |
|---|---|
| `accepted` | 意圖已持久保存，尚未開始 |
| `running` | 執行中；daemon 重啟後從已保存的步驟接續 |
| `waiting_checks`、`waiting_external` | 等外部條件（checks、queue、workflow），到時間再跑 |
| `uncertain` | 某一步送出後沒有確定結果；以回查判斷，不重送 |
| `needs_attention` | 需要人處理（含回查多次仍無法證明） |
| `succeeded`、`failed`、`cancelled` | 終態 |

每個外部呼叫是一個具名步驟（`operation_steps`）。步驟意圖在呼叫前先 commit。逾時或連線中斷時步驟記為 `uncertain`，之後由該步驟的 `reconcile` 讀回外部狀態：證明已發生就補記成功，無法證明就維持 `uncertain` 並退避重試回查，五次後轉 `needs_attention`。已完成的步驟在重跑時直接回傳保存的結果。

第一批 action：

| Action | Scope | 外部呼叫 | 回查依據 |
|---|---|---|---|
| `session.send` | operate | `claude:send-message`，`clientMessageId = batc-<operation_id>` | BAT 接受後寫入的 turn 紀錄 |
| `session.answer` | operate | `claude:resolve-ask-user`／`resolve-permission` | 該 tool use 已不在 pending |
| `session.interrupt` | operate | `claude:interrupt-turn`／`abort-session` | session 已不在 streaming |

Session action 在建立時先用 registry 與目錄判斷來源，人工、unknown、未啟用 write tier 的主機直接回 403，不寫入 operation；執行時 `service.py` 再做一次資源政策的即時檢查。新 action 以 `ActionDef` 註冊（`api_actions.py`），之後的 GitHub merge、部署、checkpoint 都用同一套步驟與回查規則。

## 資源目錄

`inventory.py` 用自己的 read-only `Fleet` 輪詢每台主機：client 核心拒絕所有寫入 channel，所以觀測不可能改動 BAT。結果寫入 `hosts_observed` 與 `sessions_observed`。

- 主機連不上時保留最後一次的列，標 `stale: true, stale_reason: host_unreachable`，不刪除。
- 一列要連續兩次成功列舉都沒出現，才標 `gone`。
- `last_activity` 以外的欄位有實質變化時，才寫 `session.added`／`session.updated`／`session.gone` 事件。
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
- `GET /api/v1/events/stream`：SSE，支援 `Last-Event-ID`，15 秒 keepalive，最多 16 條同時連線，單條最長 30 分鐘。瀏覽器 `EventSource` 不能帶 Authorization，Dashboard 以 `fetch` 讀串流。

## 路由

| 方法與路徑 | Scope | 說明 |
|---|---|---|
| `GET /api/v1/version` | 無 | connector、api_version、contract_version |
| `GET /api/v1/capabilities` | observe | actor、scopes、主機 tiers、actions 與是否允許 |
| `GET /api/v1/hosts` | observe | 主機可達性與 stale |
| `GET /api/v1/sessions` | observe | 分頁目錄；`host`、`provenance`、`access`、`attention`、`include_gone`、`order`、`cursor`、`limit` |
| `GET /api/v1/sessions/{host}/{id}` | observe | 一列；`live=true` 另附即時資源政策判定 |
| `GET /api/v1/sessions/{host}/{id}/messages` | observe | 經 read-only fleet 讀對話 |
| `GET /api/v1/policy` | observe | mutation 清單與各主機設定 |
| `GET/POST /api/v1/operations` | observe／依 action | 列表；建立（`Idempotency-Key` 標頭或 `idempotency_key`，`?wait=秒`） |
| `GET /api/v1/operations/{id}`、`POST …/cancel` | observe／actor | 含步驟；取消只在下一步之前生效 |
| `GET /api/v1/events`、`/events/stream` | observe | 事件分頁、SSE |
| `GET /api/v1/tasks/{task_id}` | observe | 既有 `work_status` |

錯誤格式為 `{"error": {"code", "message"}}`：401 未驗證、403 權限或資源唯讀（代碼同 resource-policy）、404、405、409 冪等衝突、422 參數錯誤、502 BAT 錯誤。

## 尚未涵蓋

- Dashboard 畫面（W09）、GitHub merge／部署（W07／W08）、checkpoint 接續（W04）。這些新增 action 與路由，不改這裡的合約。
- 既有 MCP 寫入工具（`session_send` 等）仍直接呼叫 service；它們受同一套資源政策約束，但不留 operation 紀錄。之後改為經 `operation_submit`。
- `task.submit`／`pause`／`resume` 尚未包成 operation。
