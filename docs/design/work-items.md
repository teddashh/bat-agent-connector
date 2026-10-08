# 專案與工作項目

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §05（權威來源）、§08（領域模型）、§10（`/projects`、`/work-items`）、§19（專案總覽與工作樹、工作詳情）、§20（Project Hub 重用）與工作包 W05。程式在 `work_items.py`，經 [OperationService](api-v1.md) 執行。

專案與工作項目是 Connector 自己的管理資料，只存在 journal。它們不碰主機、Git 或 GitHub；執行事實（session 是否在跑、PR 是否合併）仍由各自的來源決定，工作項目只連結到它們。

## 兩種紀錄

| 紀錄 | ID | 內容 |
|---|---|---|
| 專案 | `prj_` + 20 hex | 名稱（啟用中的專案不重名）、說明、上層專案、`derived_from`、repositories（`owner/name`）、對應的 Task Service 專案名稱 |
| 工作項目 | `wi_` + 20 hex | 標題、目標、需求原文、驗收條件、步驟（`{text, done}`）、狀態（`todo`／`doing`／`waiting`／`done`）、上層項目（同專案）、`derived_from`（任何專案的項目） |

ID 隨機產生，封存的列保留，所以 ID 不會重用。改名、移動、排序都不改 ID。

## Actions

| Action | Scope | 前置條件 |
|---|---|---|
| `project.create` | manage | — |
| `project.update`（改名、說明、移動、repositories；或只帶 `archived`） | manage | `expected_version` |
| `project.order` | manage | `before`：你看到的兄弟順序 |
| `project.pin` | manage | `before`：你看到時是否已固定 |
| `work_item.create` | manage | — |
| `work_item.update`（內容、步驟、狀態、移動；或只帶 `archived`） | manage | `expected_version` |
| `work_item.order`、`work_item.pin` | manage | 同上 |
| `work_item.approve` | approve | `expected_fingerprint` |
| `work_item.continue` | manage | `expected_fingerprint` |
| `work_item.link`（`remove: true` 移除） | manage | — |

前置條件在保存操作前檢查一次（不符回 409，什麼都不存），執行時在同一個交易裡再檢查一次。兩個依同一版本送出的修改，後執行的那個失敗為 `VERSION_CONFLICT`。

每個修改是一個 SQLite 交易，連同 `management_applied` 的一列（operation ID 與結果）一起寫入。Daemon 在寫入後、記下結果前重啟時，重新執行同一個 operation 會回傳記下的結果，不會再套用一次。

## 完成確認

Agent 把狀態設成 `done` 是「回報完成」，不是完成：項目顯示為待確認（`awaiting_approval`），列在「待處理」。人以 `work_item.approve` 確認時帶上自己讀到的內容指紋（標題、目標、需求原文、驗收條件、步驟的 SHA-256）。標題也算：任何有 `manage` 的人都能改名。

- 確認後內容再被修改（改名也算），指紋不同，項目回到待確認，改內容的人成為新的回報者（`claimed_by`）。
- `work_item.continue`（「還沒完成，繼續」）把 `done` 改回 `doing` 並清掉確認。
- 步驟全部勾完、狀態還不是 `done` 時，也會等人決定；`continue` 記下當時的步驟，同一組步驟不再詢問，加了新步驟並勾完會再問。
- 還有未勾的步驟時不能設成 `done`（`STEPS_OPEN`）。已完成的項目改了步驟後仍有未勾的（取消勾選或新增），狀態回到 `doing`；改名等其他修改不會。
- `approve` 可以從任何狀態直接把項目標為完成（人在 Dashboard 按「標記完成」）。

`approve` 是獨立的 scope：有 `manage` 的 agent 能編輯項目、回報完成，但不能替自己的回報簽核。發 token 給 agent 時不要給它 `approve`。

完成確認只代表人接受了這個項目的內容，不代表測試通過、PR 已合併或已部署（計畫 §05）。

## 樹與順序

`parent_id` 決定在樹上的位置；`derived_from` 只記「從哪裡分出來」。Dashboard 的「分支」會建立一個與來源同一層、`derived_from` 指向來源的項目。

每個上層各存一份順序（`tree_order`：`projects` 或 `items:<project_id>`，最上層是空字串）：

- 固定的項目一定在未固定的上面；排序不能讓固定的項目排到未固定的下面（`PINNED_FIRST`）。
- 排序要帶 `before`，與目前順序不同就回 `ORDER_CHANGED`。
- 從沒排過的分支放在來源後面；其他新項目放在最後。
- 封存的項目保留原本的位置，復原後回到那裡；第一次排序時，已封存的項目也照預設順序保有位置。
- 專案樹與工作項目樹最多 32 層（`TOO_DEEP`）；移動時連同被移動項目底下的層數一起算。

## 封存

- 封存工作項目會連同它底下所有啟用中的項目一起封存，並記下是哪個 operation 封存的。復原只帶回同一個 operation 封存的子項目；在那之前就各自封存的不會一起回來。
- 上層還在封存中時不能復原（`PARENT_ARCHIVED`）。
- 專案還有啟用中的子專案時不能封存（`HAS_CHILDREN`）。專案封存後，它的工作項目不再出現在列表，也不能修改，直到專案復原。

## 連結

`work_item.link` 把項目連到它的執行與成果：

| kind | ref | 檢查 |
|---|---|---|
| `session` | `host/session_id` | 設定裡的主機，且 inventory 看過這個 session |
| `checkpoint` | `cp_…` | journal 有這個 checkpoint |
| `operation` | `op_…` | journal 有這個 operation（例如 `checkpoint.continue`、`integration.apply`、`github.pr.merge`） |
| `task` | Task Service 的 task ID | journal 有這個 task |
| `pull_request` | `owner/name#123` | 格式 |

讀取時每個連結附上它現在的狀態（session 標題與存取方式、operation 狀態與開出的 session、checkpoint 的 commit），全部來自 journal 與 inventory，不問主機。移除連結只標記移除者與時間，紀錄留在 `removed_links`。Session 與 operation 的讀取另附連到它的工作項目（`work_items`）。

Dashboard 的工作詳情可以從已連結的 checkpoint 直接派工：指示預先填入項目的標題、目標、需求原文、驗收與步驟，開出的 `checkpoint.continue` operation 會自動連回這個項目。

## 讀取

| 入口 | 內容 |
|---|---|
| `GET /api/v1/projects`（`include_archived`） | 專案樹（顯示順序）與各專案的項目統計 |
| `GET /api/v1/projects/{prj}` | 一個專案、它的路徑、子專案與工作項目樹 |
| `GET /api/v1/work-items`（`project_id`、`state`、`pending`、`include_archived`、`limit`、`cursor`） | 跨專案，最近修改的在前；`pending=true` 是等人決定的項目。下一頁帶上回應的 `next_cursor`（修改時間加 ID：整棵封存或復原的項目時間相同） |
| `GET /api/v1/work-items/{wi}` | 一個項目、完成狀態（`completion`）、路徑、子項目、分支、連結與最近 50 筆紀錄 |
| MCP | `projects_list`、`project_get`、`work_items_list`、`work_item_get`；修改用 `operation_submit` |
| CLI | `batc project list|show|create|update`、`batc item list|show|create|update|approve|continue|link`。`batc item approve` 要帶 `--fingerprint`（`batc item show` 的 `completion.fingerprint`），確認的是你讀過的內容；`--archive`／`--restore` 不能和其他修改一起用 |

事件：`project.*` 與 `work_item.*`（`created`、`updated`、`state`、`approved`、`continued`、`linked`、`unlinked`、`archived`、`restored`、`pinned`、`unpinned`、`ordered`），帶 actor 與 `operation_id`。

## 與 Project Hub 的對照

規則移植自 Project Hub v4.68.2（kieiken/project-hub@031aedd4，MIT；聲明見 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)）。

| Hub 檔案 | 這裡 | 不同之處 |
|---|---|---|
| `hub/lib/hierarchy.js` | 改名與關係 | 關係只存 ID，所以改名不用改寫其他紀錄；以版本號取代內容雜湊 |
| `hub/lib/project-order.js`、`hub/public/project-order.js` | `siblings()`、`_save_order()` | 新項目放最後（Hub 放最前）；固定也適用於工作項目；分支的位置由 `parent_id` 決定，不跟著來源移動 |
| `hub/lib/completion.js` | `completion()`、`approve`／`continue` | 指紋含標題（Hub 的改名由人操作；這裡 agent 也能改名）；確認需要 `approve` scope |
| `hub/lib/task-ids.js` | 隨機 ID、封存保留 | 不需要依日期編號與預約檔 |

## Hub 匯入的來源與連結

[hub-import.md](hub-import.md) 已實作 B05 的離線匯入：`hub.import.preview`／`hub.import.apply` 都需 manage。四個 phase steps 共用一個 apply operation，每列用 `_once(..., key=creation_reference)` 作 SQLite 交易與回執去重，沒有子 operation。原有 projects／work_items 的 NOT NULL UNIQUE operation_id 保留；匯入新列用 `<apply operation_id>#<record id>` creation reference。`split_creation_reference()` 在每個讀取投影真正的 operation_id 與 import_record，composite 不當作 operation ID 連結。

列表與詳情附 source 標記，詳情保留原文、歷史完成、原始 parent／derivedFrom 與 shared snapshot reference。來源的完成簽核只作歷史事實，仍須現有 approve 流程。Hub parent 不寫 Task Service continuation；execution branch ID 不當 Git branch 名稱。

`work_item.link` 新增 external_url：只接受最多 300 字的 HTTP(S) URL，拒絕 userinfo、控制字元／空白與非法 authority。連結仍用 work_item_links 與 removed_links，讀取不連網或猜 PR 身分；project 來源連結則留 source snapshot。S0／S1／D0／D1 比對保護人修改的內容、簽核、pins、order、links 與 archive；source_missing 不刪除或復原目的項目。

## 尚未涵蓋

- 工作項目的附件（W05b）尚未實作。Hub 新版／壓縮匯出／衝突後 adopt-baseline 等仍見 hub-import.md 的尚未涵蓋。
- 專案的階段與專案層級的完成確認。
- 在專案之間移動工作項目。
- `work_submit` 與 checkpoint 派工以外的入口自動建立連結。
