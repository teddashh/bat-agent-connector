# Project Hub 資料匯入

日期：2026-10-08。本規格已依 Phase 2 審查修訂並實作。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §08（穩定識別）、§09（共用操作與預覽）、§20（Hub 重用）、§24 現有資料遷移第 7 步、§28，以及驗收 B05。

新增本文件，因為來源檔案、安全讀取、重匯衝突與遷移復原需要獨立的合約；[work-items.md](work-items.md) 繼續說明日常管理規則。匯入後，管理資料的權威來源是 Connector journal。

## 固定來源版本

| 來源 | 固定版本／實際查閱位置 |
|---|---|
| Connector | `origin/main`、本工作包起點 `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`；套件版本 0.2.4。`src/bat_agent_connector/work_items.py`、`task_journal.py`、`operations.py`、`task_daemon.py`、`api_v1.py`、`mcp_server.py`、`cli.py` |
| Project Hub | v4.68.2，`kieiken/project-hub@031aedd4bf62ef4bb1e6199c31aa9c4323a116bb`，MIT。以 `/tmp` 的 detached checkout 查閱，不啟動 Hub 或安裝其依賴 |
| BAT | 計畫固定基準 `b7419892fbc9946799b64cca24c2ec8c7fa15c42`；本功能不呼叫 BAT channel，因此沒有新增 BAT 協定假設 |

下文「Hub 格式」指這個 commit 的格式，並非一般 YAML 或推測的匯出 API。主要依據：

- [hub/lib/store.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/store.js)：`Store.projectDir()`、`taskFile()`、`readProject()`、`readTask()`、`createTask()`、`sections()`、`readSteps()`。
- [hub/lib/frontmatter.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/frontmatter.js)：`parseDoc()`、`parseYaml()`、`parseValue()`，Hub 自己的有限 frontmatter 語法。
- [hub/lib/hierarchy.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/hierarchy.js)：`Hierarchy.resolve()`、`rename()`，ID／唯一顯示名稱的解析，以及改名保留目錄與檔名。
- [hub/lib/task-ids.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/task-ids.js)：`reserveTaskId()`，日期序號與刪除後不重用的來源紀錄。
- [hub/lib/completion.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/completion.js)：`hash()`、`Completion.task()`、`approveTask()`、`continueTask()`、`project()`。
- [hub/lib/project-order.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/project-order.js) 與 [hub/public/project-order.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/public/project-order.js)：`read()`、`readPins()`、`displayParent()`、`taskItems()`、`siblings()`、`nearSources()`。
- [hub/public/app.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/public/app.js)：`treeTasks()`、`taskTree()`，task 的實際顯示階層與兄弟順序；只查閱純顯示規則。
- [hub/lib/chat.js](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/hub/lib/chat.js)：`files()`、`append()`，原始需求可能只存在逐行 JSON 的 user 紀錄；不採用 `ChatRunner`。
- [PROJECT.md 範本](https://github.com/kieiken/project-hub/blob/031aedd4bf62ef4bb1e6199c31aa9c4323a116bb/docs/project-hub/templates/project/PROJECT.md)：`folders`、`related`、`chats: [{title, url}]`、`issues`。

## 現有與新增行為差異

起點的 `work_items.py` 已有 `prj_`／`wi_`、樹、順序、固定、封存、完成確認及資源連結。`_once()` 把修改與 `management_applied` 同交易保存。起點的 `task_journal.py` 尚無 Hub mapping 表；當時 `THIRD_PARTY_NOTICES.md` 的表是規則移植對照，不是使用者資料的 ID mapping。

新增的是離線資料匯入、來源標記、預覽、逐項回執與重匯比對。沿用 `OperationService`、`ActionDef`、`api_auth`、同一 journal 與現有 work item 驗證。匯入不建立 execution、Task Service task、session、worktree、Git branch 或派工命令。Hub 的 `owner`、`model`、`role`、`workdir`、queue 與 provider session ID 不會變成執行設定或管理權證據。

## 真正的磁碟格式

來源根目錄是 Hub 的 `HUB_ROOT`，不是 Hub 程式碼目錄；`hub/server.js` 用它建立 `Store`。以下路徑都相對於該根目錄：

| 檔案 | 身分／內容 | 匯入處理 |
|---|---|---|
| `Product/<project>/PROJECT.md` | `<project>` 是 project ID；frontmatter 的 `name` 是可改的顯示名稱。沒有另一個全域 UUID | 必須有合法 frontmatter；讀 description、parent、derivedFrom、正文與其他欄位 |
| `Product/<project>/.ai/tasks/<task>.md` | 檔名去掉 `.md` 是 task ID；新檔有 `id`，但 `readTask()` 實際用檔名。新 ID 為 `YYYYMMDD-NN`，序號可超過兩位 | 接受 Hub 可讀的舊檔名，例如上游測試的 `t.md`；不要求所有舊 task 都符合日期正則。若有 `id` 且與檔名不同，列為錯誤 |
| `_hub/project-order.json` | `{ "groups": { "": ["p", "q"], "p": ["child"] } }`；空字串代表頂層 | 讀每個 parent 的完整 saved order；包括已不在來源中的 ID 槽位 |
| `_hub/project-pins.json` | project ID 字串陣列 | 只對應專案固定；Hub 此版沒有 task pins 檔 |
| `_hub/completion.json` | `version: 1`、`tasks`、`projects`、`continued`；task key 是 `<project>/<task>` | 保留原紀錄並計算歷史完成事實 |
| `_hub/completion.migrated` | Hub 的首次遷移 marker | 保留是否存在及內容；不得因讀取而建立或更新 |
| `Product/<project>/.ai/chat/<task>.jsonl` | 有 `at`、`role`、`text` 等欄位的逐行 JSON | 選取 `role == "user"` 的文字及來源行號，保留為需求歷史。不是匯入對話 runtime |

列舉規則跟 `Store.listProjects()`／`readProject()` 相同：略過 `.`／`_` 開頭的 project 目錄與 task 檔名。不只檢查最上層：候選若包含 symlink、特殊檔案或不可讀檔案，必須回報，不能把讀取失敗當成沒有資料。來源有 project 目錄卻沒有 `PROJECT.md` 時，在預覽列出略過原因；已有 mapping 的 project 突然失去該檔則是 `SOURCE_MISSING`。

frontmatter 採與上游有限語法相容的 Python parser，支援 scalar、inline list／map、縮排 list／map、Hub 的註解與引號處理。不引入完整 YAML 的 tag、alias 或物件建構。無法解讀的結構、重複 key、非法 UTF-8、JSON duplicate key 等列為 `IMPORT_FORMAT_INVALID`，不仿照 Hub 的 catch-and-default 丟掉資料。正文與未知欄位另保留完整來源，不由 parser 重寫。

此版未發現獨立的可往返資料匯出格式。第一版的「export」是保留上述目錄布局的離線快照目錄；同一 parser 讀它。任意 API `/api/state` 的 JSON、zip／tar、單獨 `Product` 目錄或單張 PROJECT.md 都不當作完整匯出。缺少可選的 order／pins／completion／chat 檔可以匯入，但預覽明列事實缺失；格式損壞則阻擋，不能視為可選檔未存在。

## 必要前置條件與來源唯讀

人先在 daemon 的主機準備來源，並修改 daemon 設定。以下設定由人加入 daemon 設定檔；重新啟動 daemon 後可用：

```toml
[[hub_import.sources]]
id = "hub-fixture"
path = "/srv/import-fixtures/hub-snapshot"
runtime_retired = true
```

- `id` 是這一份舊帳本的固定 namespace，格式 `[a-z][a-z0-9_-]{0,63}`。換快照或搬家沿用它；不同舊帳本即使 task ID 相同也用不同 namespace。同一 canonical path 不得登記兩次。複製的帳本是否同一 lineage 由人指定，Hub 沒有可自動證明的全域 ID。
- `path` 是 daemon 本機的絕對目錄，由設定提供白名單。CLI 的 `--source`、MCP 與 HTTP 都只傳此 `id`；瀏覽器不能提交絕對路徑、`file://`、上傳來源路徑或任意 URL。SSH forward 不會把 client 的檔案變成 daemon 的檔案。
- daemon 用目錄 descriptor 逐層開啟，拒絕 symlink／`..`／越界；在開啟與讀完時驗證 regular file、device／inode。根目錄重綁、檔案被替換、檔案集合改變都使預覽過期。只以 realpath 的字串前綴比較不足以防止換檔競態。
- 只讀已列的來源檔；不追隨 `folders`、`workdir`、Markdown 本機連結、Git alternates 或來源中的其他指向。不得執行來源的 scripts、hooks、CLI、PTY、動態 module 或 HTTP endpoint。一般外部 URL 也不發網路請求。
- 一次上限：5,000 projects、50,000 tasks，單個文字檔 8 MiB，所選來源檔合計 256 MiB。讀取時累計檢查，不信任 stat 的 size；超過是 `IMPORT_LIMIT_EXCEEDED`，不截斷。管理欄位還要符合 `work_items.py` 的名稱、文字、步驟及深度上限。
- 來源可為 manual／unknown 本機資料，永久唯讀；唯一目的地是 Connector 自有 journal。此操作沒有 BAT／Git mutation，不新增另一套 ownership 判斷。若後續加附件 materialization，另經共用 resource policy，不納入本規格。
- `runtime_retired` 是人的持久切換聲明，並非 Connector 查明所有 Hub 程序已停止的證據。false 時仍可 preview，但 apply 被阻擋；一張靜止快照不能證明另一處 Hub 已退役。

快照以相對路徑、存在／缺失標記、檔案 bytes SHA-256、檔案身分組成 manifest。讀完再次列舉並雜湊；不同則 `SOURCE_CHANGED`。以讀到的 bytes 計算，不沿用 Hub 的 mtime／size parse cache。這是變動偵測，沒有宣稱能對活動 writer 取得跨檔案一致快照；人須先停寫再備份。

## 穩定 mapping 與來源資料

在同一 journal 作 versioned、additive migration（起點 `PRAGMA user_version = 1`，本包取下一個空位 2；rebase 時若平行 migration 已使用它，改取下一個空位。DDL 為 idempotent）。以下是新增資料表的邏輯欄位；不另建 tasks database。

| 紀錄 | 主鍵／必要欄位 |
|---|---|
| `hub_import_sources` | `source_id`；最後成功的 actor／operation、manifest 與來源 revision；固定 Hub commit 由 parser/read model 定義，首次 actor／operation 仍可由 receipts 查回。路徑取 daemon 設定，不是 identity |
| `hub_import_map` | 實體主鍵 `(source_id, record_key)`，record_key 編碼 kind／Hub project ID／task ID；`kind = project/item`；project 的 task key 為空字串；`connector_id`、最近成功的 source digest／snapshot、destination baseline、import operation；未完成批次另有 pending snapshot／receipt reference。`connector_id` 不得被另一個 mapping 使用 |
| `hub_import_previews` | `preview_id = hip_` + 32 hex；actor、source_id、parser version、manifest、normalized records、計畫與依賴、destination preconditions、digest、created_at、expires_at |
| `hub_import_receipts` | `(apply_operation_id, record_key)`；結果中的 operation_id／import_record 可還原 creation reference；connector ID、after destination／mapping digest。before 留在綁定的 preview，錯誤留 operation／phase；另有 structure／finalize receipts，不是派工狀態 |
| `hub_import_groups` | `(source_id, group_key)`；group_key 編碼 kind／Hub project／parent record key。保存來源順序及 pins digest、destination baseline 與事件游標；實際 tree_order scope 沿用 `projects`／`items:<prj_id>` |
| `hub_import_source_snapshots` | `apply operation_id`；完整 shared order／pins／completion／marker 文字與 manifest，交易內存一次，避免每個 task 複製 ledger。完成後由 imports read 回查 |

`record_key` 是 canonical JSON 的 kind／Hub project ID／Hub task ID，不能用容易混淆的字串拼接。對照如下：

| Hub identity | Connector identity | 保留規則 |
|---|---|---|
| `(hub-fixture, project, p, "")` | 隨機 `prj_` + 20 hex | 第一次 apply 建立時寫 mapping；preview 不分配正式 ID |
| `(hub-fixture, item, p, 20261001-01)` | 隨機 `wi_` + 20 hex | 同 task ID 在另一個 project 可存在；不能只以 task ID 當 key |
| Hub 顯示名稱改變 | 原 `prj_`／`wi_` | 以目錄／檔名 identity 找舊列，不按 title 猜 mapping |
| Hub 來源消失、Connector 封存、來源搬家 | 原 mapping 保留 | 不刪 mapping、不回收 ID、不自動 archive／restore |
| Hub 目錄或 task 檔名改變 | 新來源 identity | 不能猜成改名；舊列是 source_missing，新列是 create，預覽讓人看見 |

每列 source snapshot 保留原 PROJECT.md／task.md bytes、解析的未知欄位、需求歷史，以及所用 completion／order／pins 的來源證據與相對位置。project 共用檔案只保存一次；不把完整 `_hub/completion.json` 複製到每個 task。資料放 journal 的來源紀錄，未成為第二份可派工的狀態。

project／work item 的讀取附 `source`：`kind: project_hub`、source_id、hub_project_id、hub_task_id、Hub commit、source_digest、import_operation_id、imported_at、import_state（complete／incomplete）、historical_completion 與原始關係。列表也有來源標記；詳情可讀來源文字、缺失與歷史確認。無法證實 actor 的歷史紀錄只標 Hub，不把 `owner` 或 Git author 當 Connector actor。

## 欄位映射

| Hub 欄位／來源 | Connector | 規則 |
|---|---|---|
| PROJECT.md `name`／目錄 ID | project.name | name 缺失用 ID；不按同名合併既有專案。啟用專案名稱碰撞回 `NAME_TAKEN`，不自動加後綴 |
| `description` | project.description | 保留文字；完整 PROJECT.md 正文與 phases／issues 等留 source snapshot |
| project `parent`／`derivedFrom` | project.parent_id／derived_from | 先以 project ID 解析，找不到才用唯一 name；歧義或孤立關係阻擋。parent 採 Hub `displayParent()` 的顯示位置，raw parent 另留來源 |
| task `title`／檔名 ID | work_item.title | title 缺失用 ID；不由需求自動摘要 |
| task 正文 `## 次にやること` | goal | 採 `store.js` 的次步區塊；同名／重複相關區塊有歧義時阻擋，不取最後一份蓋掉前文 |
| task Markdown 正文 | request | 完整保存正文，換行依 `_text()` 正規化；無正文是空字串。包含手順、報告、需求與自訂段落，不能用 `next` 取代原文 |
| task `.ai/chat/<task>.jsonl` 的 user rows | source.request_history | 按檔案行序保留 text、at、request（若有）與行號；不把後續 user 訊息猜成新的 goal 或驗收，也不 replay。缺檔提示需求可能只有 Markdown 中的部分 |
| 正文的驗收區塊 | acceptance | Hub 沒有原生 acceptance 欄位。本 adapter 僅識別完整二級標題 `驗收條件`、`受け入れ条件`、`受入条件`、`Acceptance`；按出現順序保留各區塊文字。沒有就是空字串；其他表述仍完整保存在 request／需求歷史，不用模型推測 |
| `## 手順` 中 `- [ ]`／`- [x]`／`* [X]` | steps `{text, done}` | 跟 `readSteps()` 相容，只讀手順區塊；空白／comment／其他段落不能誤作步驟。超出 50 步或單步 300 字阻擋，不截斷 |
| task `parent` | parent_id | main task 是同 project 的父 task；絕不寫 `tasks.parent_task_id` 或 continuation |
| `kind: derived`、`derivedFrom` | derived_from ＋ parent_id | 支援同 project 的 task ID 或 `<project>/<task>`。保留來源 work item；顯示 parent 依 Hub `taskItems()` 的來源鏈算，同 project 取來源的顯示 parent；跨 project 派生在自己的 project 頂層，原 parent 另留來源。不是 execution branch |
| `_hub/project-order.json`、`project-pins.json` | `tree_order`、project.pinned | 見下一節；新匯入 task.pinned = false。重匯不把 Connector 自己的 task pin 清掉 |
| project `chats: [{title,url}]`、文字中的 HTTP(S) 連結 | source.external_links；task 另可連 `external_url` | project 本來沒有 links 表，來源連結由 project 詳情提供。新增 work item `external_url` kind，沿用 `work_item_links` 與移除歷史；不假造 task/session/checkpoint ref |
| project `related` | source.related_projects | 每個 raw ref 以 Hub project ID／唯一 name 解析並附 mapping 後的 prj ID；非階層的孤立／歧義 ref 保留原文並警告，不丟掉也不建立空專案 |
| `folders`、本機／相對路徑、非 HTTP(S) link | source.references | 原文與位置完整保留、預覽列未 materialize；不開啟、不下載、不認領資源 |
| `updated`、owner、role、phase、via、workdir、workspaceMode 等 | source 原欄位 | Hub 的本機無時區日期不猜成 UTC；Connector created_at／updated_at 是匯入時間。沒有 repo provider identity 就不填 repositories／task_project |

驗收標題白名單是本 adapter 的新規則，不宣稱它存在於 Hub。Markdown 文字與原檔都保留，擷取欄位不能造成原文遺失。URI 字面值與 label 保留原樣；task 的安全 HTTP(S) URL 去重後加入 `external_url`。禁止控制字元與 URL userinfo；其他 scheme 留 source references 並提示不能開啟。不以 substring／正則猜 PR 身分；此版不自動轉 `pull_request`。

連結抽取支援 Markdown inline link、reference link、autolink、裸 HTTP(S) URL，忽略 code fence／inline code；重複 URL 保留各來源位置，但只建一個 active link。刪改匯入的 URL，僅移除 importer 建立且 baseline 未變的 link，沿用 removed_links 歷史。使用者另外建立的 links 一律保留。

### 階層、順序與固定

先讀完全部 identity，再解析關係。有效來源的 Hub 顯示階層、來源鏈與順序都要保留；原始 parent／derivedFrom 也留 source。Hub 會把某些孤立／循環關係退回頂層，匯入器改為在預覽列 blocker，不默默改造壞資料。檢查 project parent、project derivedFrom、task parent、task derivedFrom 的循環、跨 project 非派生 parent、缺失與最終 32 層上限。

project 預覽順序依 `Store.listProjects()` 的 updated 降序、`ProjectOrder.siblings()` 的 saved group／未配置派生位置與 pins-first 算。task 順序依 `Store.readProject()` 的 updated 降序，再套 `taskItems()`、`displayParent()` 與 `taskTree()` 的 `nearSources()` 顯示規則；此版沒有持久 task order／pins，不能虛構來源檔。updated 相同時，以來源 ID 的 UTF-8 byte order 作穩定 tie-break，預覽註明此處 Hub 沒有固定順序。

apply 把實際順序存 `tree_order`，所以 Connector「新項目放最後」的預設不會改掉首次匯入的排列。既有 Connector siblings 保持原相對順序；首次匯入的 siblings 追加到各自 pinned／unpinned 分區尾端。重匯只重排這個 source 的既有槽位，新來源項目追加到該 source 分區尾端；其他來源／本機項目與 archived 槽位留原處。任何順序、固定、parent 變更都在預覽列出實際 affected group。

來源 order 中不存在且從未匯入的 ID 只保留為 Hub 的原始槽位，不憑空建立空專案。若已有 mapping 卻來源消失，列 `source_missing`，不從目的 order 移除；復原來源後仍是原 ID。Connector 已封存的來源項目若需要修改，列衝突，不藉重匯復原它。

### 狀態與完成事實

| Hub raw state | 匯入狀態 | 歷史事實 |
|---|---|---|
| 缺失／`未着手` | todo | 原值保留 |
| `実行中` | doing | 只代表匯入的管理狀態；沒有活動 execution |
| `返事待ち`、`上限で停止`、`停止` | waiting | question 與原停止原因留 source；沒有 pending BAT 問題或 Hub queue |
| `完了`，沒有未勾步驟 | done、awaiting_approval | done_by 為 `project_hub:<source_id>`，done_at 為匯入時間；歷史完成日期另保存，不猜 actor |
| `完了`，仍有未勾步驟 | 不套用 | blocker `COMPLETION_STEPS_OPEN`，需人修正來源後重新預覽；不偷偷勾步驟或直接簽核 |
| 其他 state | 不套用 | `IMPORT_STATE_UNSUPPORTED`，不猜成 todo |

`Completion.hash()` 是 SHA-256，對**整份 task Markdown**把 CRLF 換成 LF 後計算，不是 Connector `fingerprint()`。source.historical_completion 保存 raw_state、task record 的 hash／at、hash 是否匹配、continued steps hash，以及 Hub 當時的 approved／pending 推導結果。continued 的 hash 依上游 `JSON.stringify(steps)` 的 compact、欄位順序與 UTF-8 計算，不用 Connector 的 JSON sort_keys 替代。

completion ledger 缺失但 marker 存在：歷史確認 unknown，完了仍待確認；兩者都缺失：記 `legacy_unverified`，**不執行** Hub seed、也不把 migrated approval 當作新 Connector approval。ledger 的 `at: "migrated"` 保留字面值。ledger hash 不合是 Hub 的未確認完成。project status／phase approvals／continued 同樣保留為歷史來源資料；Connector 尚未有 project 完成欄位，不以 archive 假裝完成。

若 raw state 不是完了、且 Hub continued hash 與目前 steps 相符，將這個「還要繼續」的歷史決定轉為 Connector `continued_steps = steps_hash(mapped_steps)`，保留同組全勾步驟不再詢問的事實。hash 不符就不抑制 pending；raw 完了也不能用 continued 繞過待確認。此欄是 work item 的完成提示決定，與 Task Service 的 continuation 完全不同。

所有匯入只要 `manage`。`approved_fingerprint`／`approved_by`／`approved_at` 不由 importer 寫成已批准；人讀到匯入內容後，以現有 `work_item.approve`、`approve` scope 與 fingerprint 確認。若上次匯入後已有 Connector approval，後續來源內容變動屬目的端編輯，列衝突。歷史 Hub approval 與目前 Connector approval 同時可讀，不把其中一個冒充另一個（計畫 §05）。

## 重匯與衝突規則

以來源 identity 比較，使用三份資料：最近**成功套用**的 source snapshot（S0）、目前來源（S1）、最近匯入寫下的 destination baseline（D0）與目前目的地（D1）。來源 digest 包含原檔 bytes、需求歷史及該列相關的 completion／pins／關係；order group 有獨立 digest。改了未知欄位或 updated 也算來源變更，必須報告，不能只比 title。

D0 包含 row version、所有可變欄位、完成欄位、archive、pin、active／removed link 摘要與相關 `api_events.seq` 游標；group baseline 包含完整 sibling ID 順序、pins、parent 與對應 ordered／移動事件。只用 row.version 不夠：現有 pin、order、link 不一定增加它。只用內容 hash 也不夠：先改再改回的編輯仍由版本／事件辨識。現有不在 journal 的直接 SQLite 手改不屬支援入口，但 digest 仍能查出當下差異。

| 比對 | 預覽分類 | apply 行為 |
|---|---|---|
| 沒有 mapping | create | 建新 ID；不認領同名本機列 |
| S1 = S0，D1 = D0 | unchanged | 不 UPDATE row／mapping，不改 version、updated_at、link、order 或項目事件 |
| S1 = S0，D1 曾被本機改 | local_only | 顯示差異並保持本機內容；不把 D0 移到新位置以掩蓋編輯 |
| S1 ≠ S0，D1 = D0 | update／metadata_only | 列 Hub 差異；只修改真的改變的目的欄位。只有 source metadata 變時不 bump work item 的版本 |
| S1 ≠ S0，D1 曾被本機改 | conflict | `IMPORT_CONFLICT`；不做逐欄位自動合併，即使兩邊改不同欄位或最後內容相同 |
| mapping 的來源不見 | source_missing | 提示、保留 Connector 與 mapping，不封存／刪除 |
| mapping 的目的不見、已封存而需要改動、name collision、無效關係 | conflict／blocker | 不重建 ID、不復原、不改名；回具體錯誤 |

關係移動／順序變更也要檢查舊與新 group baseline。來源 group 沒變時，不重排本機順序；來源 group 改了而目的 group 自上次匯入後有編輯時，列 group conflict，包括新增本機 sibling。不得用本機 `local_only` 項目作為來源結構改動的可寫捷徑。

任何初始 conflict／blocker 都使整張 preview 的 `can_apply = false`，不提供 skip-conflicts 或 force-import。人可直接採 Connector 的內容為正式資料，保留衝突來源作歷史；若確實要人工合併，讀 preview 差異，以既有帶 expected_version 的管理 actions 手動修改。這不自動重設 import baseline；來源仍衝突時會繼續顯示，直到另行設計明確的 adopt-baseline 操作。單純重匯不能抹掉本機編輯。

## Preview／apply 合約與入口

兩個 actions 為 `hub.import.preview`、`hub.import.apply`，scope 都是 `manage`，以 `ActionDef` 註冊。target 固定 `{source_id}`；拒絕額外欄位：

| action | params | preconditions |
|---|---|---|
| hub.import.preview | `{}` | `{}` |
| hub.import.apply | `{preview_id: "hip_…"}` | `{preview_digest: "<sha256>"}`；其他來源／目的版本全部由 preview 帶入，不接受 client 改寫 |

preview 持久保存 operation 意圖，讀取、驗證與產生計畫後保存 preview，**不寫 projects／work_items／mapping／links／tree_order**。不建立 ID 預約檔，也不修改來源。preview TTL 24 小時；parser version、設定來源 path identity 或 runtime_retired 聲明改變也過期。apply admission 檢查預覽存在、actor 相同、source 相同、digest、期限、can_apply；執行前再次檢查來源 manifest 及計畫涉及的完整目的狀態。

preview 結果的必要內容：

```json
{
  "preview_id": "hip_<32 hex>",
  "source_id": "hub-fixture",
  "digest": "<sha256>",
  "can_apply": false,
  "counts": {
    "projects": {"create": 1, "update": 0, "metadata_only": 0, "unchanged": 0, "local_only": 0, "source_missing": 0, "conflict": 0},
    "work_items": {"create": 2, "update": 1, "metadata_only": 0, "unchanged": 3, "local_only": 1, "source_missing": 0, "conflict": 1},
    "links": {"add": 2, "remove": 0},
    "order_groups": {"change": 1, "conflict": 0},
    "blockers": 1, "warnings": 0
  },
  "records": [],
  "groups": [],
  "blockers": [],
  "warnings": []
}
```

counts 的各 entity 分類互斥，總和等於這次來源與舊 mapping 的聯集；blockers 為診斷數，不再算成 entity。records 含 source identity、現有 connector ID（新項目為 null）、classification、changed_fields、S0／S1／D1 差異、預計完成狀態、依賴與來源位置。groups 列實際排序／固定／parent 差異。完整長文由 actor-bound preview 詳情提供；operation.result.preview 只含 preview_id／source_id／digest／counts／can_apply／expires_at，避免一般 operation read 繞過 actor 綁定。一般事件不帶需求正文。

apply 結果含 preview_id、source_id、實際 counts、每列 connector ID／import_record／結果、groups 回執與 `partial`。逐項結果為 created／updated／metadata_only／unchanged／local_only／source_missing／pending；不把前面成功項目因後面失敗變成 failed。

| Surface | 合約 |
|---|---|
| CLI，先做 | `batc hub import --source hub-fixture --preview [--key KEY]`；顯示 counts／conflicts 與 preview ID。`batc hub import --source hub-fixture --apply --preview-id hip_…`；adapter 核對 source_id 並讀預覽取得 digest，apply 固定使用 `hub.import.apply.<preview_id>` key；不用 client local path |
| CLI 回查 | `batc hub show hip_…` 讀預覽；`batc op op_…` 看結果／逐項回執；已有需注意操作用 `batc op op_… --resume` |
| HTTP mutation | `POST /api/v1/operations`，action = hub.import.preview／hub.import.apply，沿用 Idempotency-Key、wait 與標準 operation response。沒有直接寫檔 endpoint |
| HTTP read | 新增 `GET /api/v1/hub-import/sources`、`/previews/{hip_id}`、`/imports/{op_id}`；sources 列 source_id、可預覽／可 apply 與原因，不公開本機絕對 path |
| MCP | `operation_submit(action="hub.import.preview" 或 "hub.import.apply", …, confirm=true)`；新增 `hub_import_sources`、`hub_import_get(preview_id 或 operation_id)`，與 HTTP 同 read model |
| Dashboard | Projects 頁的小型「匯入 Project Hub」入口：只選已登記 source，載入 preview 並列 counts／差異／conflicts。can_apply 時一個「匯入」按鈕提交同 action；不再疊 confirm modal。沒有已登記來源時顯示 daemon 設定方式 |

read routes／MCP 工具需要 `observe`；preview 長文只有 preview actor 或 local-admin 可讀，不能讓僅 observe 的其他 actor 以 preview 讀取 daemon 尚未正式匯入的本機內容。匯入後的 project／work item 來源資料循現有 observe 合約。CLI pending／uncertain／needs_attention 回 operation ID 及非成功 exit code；只有已成功 apply 回 0。preview 有 conflict 時仍完整列結果並回非成功 code，不用 transport error 丟掉診斷。

apply 的預設冪等鍵為 `hub.import.apply.<preview_id>`，只在同 actor 範圍使用；重送取得原 operation。同 key 不同內容仍依現有 `IDEMPOTENCY_CONFLICT` 回 409。preview 預設新 key，重用 key 得到原預覽。CLI 的兩個命令是先讀後寫；Dashboard 已載入預覽時只需按一次 apply（計畫 §09）。過期回差異、停用舊按鈕，更新預覽後再由人決定。

## 實際副作用與失敗恢復

來源永遠零寫入。preview 的副作用限於 operations／steps、預覽及事件。apply 的副作用限於 journal 中的管理資料、mapping／source snapshot、links／移除歷史、tree_order、receipts、management_applied 與事件；不接觸 registry、Task Service continuation、BAT、Git 或 GitHub。

既有兩表的 `operation_id NOT NULL UNIQUE` 不重建、不移除約束。匯入建立列保存 **creation reference**：`<apply operation_id>#<record id>`；record id 是 canonical record key 的 SHA-256 前 32 hex。以共用 helper 分解；所有讀取只投影真實 apply `operation_id` 加 `import_record`，不把 composite 當可連結的 operation ID。一般建立列仍是原 operation ID。

apply 直接寫管理資料，沒有子 operation、每列 step 或等待排程。泛化既有 `work_items._once(ctx, change, key=...)`，以 composite 去重；同一筆 SQLite 交易保存 row、mapping、pending snapshot、receipt、management_applied 與必要的正常管理事件。只有真實資料變更才發 project／work_item 事件。

四個 phase steps：

1. `source.verify`：驗原 manifest、退役聲明、所有目的 preconditions 與最終樹。handler 每次進入（包括 resume）都重新驗 source；不能以已完成 step 跳過。
2. `records`：先 projects 後 items，一列一交易；resume 跳過已有 receipt 的列，但仍檢查已提交列未被外部編輯。新列先不連 parent／derived_from，source.import_state 為 incomplete；既有列的結構暫不改。沒有每列 step。
3. `structure.apply`：ID 已存在後，一個 management 交易套用 parent／derived_from／pins／order groups，驗最終樹，保留本機 siblings、archived 槽位。避免合法父子互換在中間狀態形成循環。
4. `baseline.finalize`：同交易保存成功 baseline、source revision、complete 標記與 finalize receipt；unchanged／local_only 不更新 baseline。summary 另由 `_once()` 去重，避免 finalize 回覆遺失造成重複事件。

phase 用固定 management receipt key 去重，泛化同一 `_once()`；events 始終引用真實 apply op。`records` 的 reconcile 讀 receipts，若未全提交，證明是本機交易後回 RERUN 接續剩餘列。structure／finalize 以 management_applied 回查。來源與目的變動以 needs_attention 明確停止；不把未知的新內容納入原計畫。

| 失敗位置 | 恢復與結果 |
|---|---|
| admission／首次 verify | admission 回 409／422；首次 verify 停在 needs_attention，零管理寫入，重新 preview |
| 某列 commit 前停止／SQLite 錯誤 | row、mapping、snapshot、receipt 一起 rollback；resume 驗原 manifest 與剩餘目的 preconditions，再以相同 creation reference 接續 |
| 某列 commit 後、records phase 回覆遺失 | 查 receipt／management_applied；已提交列跳過，IDs 不重建；phase uncertain 的 reconcile 接續剩餘本機交易 |
| 已套用幾列後來源／目的變動 | partial = true、needs_attention；保留 applied／pending、incomplete。不宣稱整批原子提交 |
| structure commit 後、finalize 前停止 | 查 phase receipt；不再次移動／排序，驗未被外部編輯後 finalize |
| finalize commit 後、operation 結果未存 | 查 finalize receipt 完成原 op 與 phase；不增加 revision、不重發項目事件 |
| cancel | 在下一筆交易／phase 前停止，已提交列與 receipt 保留；uncertain phase 先回查，不刪列回滾 |

imports read model 由 receipts 推導 partial／pending；錯誤或 cancel 的標準 operation result 即使為空，逐項結果仍能回查。執行過的 apply 在成功或第一次停止需人處理／取消時記 summary：成功為 `hub_import.completed`，否則 `hub_import.incomplete`。一個 apply 最多一個 summary；needs_attention 後恢復成功仍保留先前 incomplete 歷史，最新完整狀態由 imports read 查回。SQLite／回覆遺失先沿用 OperationService 的 uncertain 重試；超出既有 read-back 次數時記 incomplete。執行前已取消的 intent 沿用 operation.cancelled，沒有管理寫入。不發 per-record hub_import 事件，metadata-only 只留 receipt；原文不進一般 audit event／log。

只有原 manifest 與目的 preconditions 仍成立，resume 才能續做。SOURCE_CHANGED／DESTINATION_CHANGED 須取消停住的 apply，重新 preview。incomplete mapping 以 pending snapshot 與 receipt 的實際 after 狀態作恢復基準；外部編輯仍 conflict。incomplete 不分類 unchanged，列剩餘 structure／finalize 工作。此基準不抹掉人的修改。

同 source 同時只准一個非終態 apply，否則 IMPORT_BUSY；admission 與第一個管理交易再次檢查。使用同 journal／單一 daemon owner，沒有子操作生命週期或第二 scheduler。

### 穩定錯誤

| Code | 意思／下一步 |
|---|---|
| `IMPORT_SOURCE_NOT_CONFIGURED` | source_id 未登記；在 daemon 設定來源 |
| `IMPORT_SOURCE_UNSAFE` | symlink、特殊檔案、越界或 root 身分不符；人準備安全的快照 |
| `IMPORT_SOURCE_UNREADABLE` | 讀取失敗；保留舊 mapping，不當刪除 |
| `IMPORT_FORMAT_INVALID`／`IMPORT_STATE_UNSUPPORTED` | 檔案／欄位不支援；提供相對路徑與位置，修正後 preview |
| `IMPORT_LIMIT_EXCEEDED` | 超出檔案／資料／管理欄位上限；不截斷 |
| `IMPORT_RELATION_INVALID` | missing、ambiguous、cycle、跨 project parent 或過深；列出相關 IDs |
| `COMPLETION_STEPS_OPEN` | Hub 完成與步驟矛盾；修正或由人明確處理 |
| `HUB_NOT_RETIRED` | 未有退役聲明；preview 可讀，apply 禁止 |
| `PREVIEW_EXPIRED`／`PREVIEW_MISMATCH` | 過期、actor／source／digest 不符；重新 preview |
| `SOURCE_CHANGED` | manifest 與預覽不同；不帶新內容續跑 |
| `DESTINATION_CHANGED` | 預覽後目的資料或 group 變動；顯示差異 |
| `IMPORT_CONFLICT` | 最近匯入後兩側都改；人工合併，不 force |
| `IMPORT_BUSY` | 此 source 已有未終止 apply；回原 operation |
| `IMPORT_TARGET_MISSING` | mapping 指向已不在 journal 的 ID；先查帳本，不分配新 ID |

沿用既有 scope、冪等鍵、`NAME_TAKEN`、archive 等錯誤。格式問題為 422，stale／衝突／busy 為 409，來源未設定為 404，未授權為 403。preview 將檔案錯誤聚合進 blockers；apply 才拒絕。執行後的錯誤存 operation／receipts，不把 partial 批次變成單一空 HTTP error。

## 人如何退役舊 Hub

1. 在原 Hub／作業終端由人結束或等待活動 AI，取消待派送的 queue；停用開機、自動重啟與 background Hub。移除 agents／瀏覽器的 Hub delegate／MCP 寫入入口，改用 Connector。不由 importer 執行 stop／kill。
2. 由人備份 `HUB_ROOT`，包含 Product、completion、order、pins 與需求文字。保留需要的 Work／attachments／歷史原件，但 importer 不認領、不整理它們。另備份 Connector journal、設定與 schema version，記錄 owner。
3. 把來源快照放到 daemon 可讀的登記目錄；讓舊 Hub 使用的正式資料不再被任何舊 runtime／agent 修改。人設 `runtime_retired = true`，並先 preview。單純設定 `HUB_DRY_RUN` 不算退役，Store 的讀取仍可能寫 completion ledger。
4. 一次 apply 後檢查 mapping、階層、順序、完成歷史與外部連結。之後由 Connector 管理；要保留 Markdown 供查閱，可保存凍結快照或後端匯出。重匯是人明確選的離線資料更新，不設 watcher 或雙向同步。

沒有第二份自行派工的 Hub 狀態是 B05 的必要條件。Importer 不以沒有觀測到 Hub 程序就宣稱退役成功；也不重新啟動 Hub 讀取資料。execution branch ID 留來源紀錄，不能當 Git branch 名稱或授權 Git 操作。

## 修改檔案

Phase 1 僅提交規格，審查修訂先獨立提交；Phase 2 實作如下：

| 檔案 | 修改 |
|---|---|
| `src/bat_agent_connector/hub_import.py`（新增） | 純 parser／normalize、唯讀 snapshot、mapping、三方比對、ActionDefs、preview／apply 與 receipts |
| `task_journal.py`、`work_items.py` | additive／versioned tables；共用管理 helper；external_url 驗證與 source read model，不移除原 UNIQUE 約束 |
| `config.py`、`task_daemon.py` | sources 設定、註冊 actions 與 read RPC、共用 OperationService；無 Hub 程序依賴 |
| `api_v1.py`、`mcp_server.py`、`cli.py` | 同合約的 thin adapters、來源與預覽回查、batc hub 命令 |
| `dashboard/app.js`、`app.css`、`i18n.js` | 小型 Projects 入口、來源與 incomplete 標記、en／zh-TW；沿用 fill()、CSP 與 live-update hold 規則 |
| `tests/test_hub_import.py`、`tests/fixtures/hub-import/` | 真格式合成 fixtures、B05 契約與故障注入 |
| `docs/design/work-items.md`、`api-v1.md` | 實作完成後更新尚未涵蓋、actions／routes 與 source／external_url 規則 |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md` | CLI／遷移及設計連結；Next release 引計畫 §08、§09、§20、§24 第 7 步與 B05 |
| `THIRD_PARTY_NOTICES.md` | parser／顯示階層／順序／completion 規則若移植，補固定 commit、上游檔案與 Python 位置，保留既有 MIT 聲明 |
| 兩份 `skills/*/bat-agent-connector/SKILL.md` | 未修改：此包是人主導的一次遷移，未新增 agent 常態匯入流程；MCP action 說明要求人的授權，不替人宣告退役 |

## B05 測試計畫

`tests/fixtures/hub-import/` 是合成資料，來源檔案與刻意差異見其 README；basic 有四個 projects、八個 tasks，date-id 另涵蓋日期序號。損壞、競態、深樹與大量項目都在臨時副本產生，不執行上游 Store。

| 已實作測試（`tests/test_hub_import.py`） | B05／計畫與證據 |
|---|---|
| `test_B05_preview_apply_preserves_hub_data_and_four_phases` | §08／§20／§24 第 7 步：真格式、完整需求／驗收／links／user 歷史、name-ref／derived／跨 project 階層、pins-first、歷史完成與 continued；來源 bytes 不變、沒有 BAT 呼叫或 Task Service task，只有四個 phase steps |
| `test_B05_idempotent_reimport_and_source_update` | §09：unchanged 的 row／mapping、version／updated_at／links／項目事件不變；source-only 更新、固定 creation reference、相同 apply key 回同 operation；一個 summary |
| `test_b05_metadata_links_source_missing_and_rename` | §08／§09：metadata-only 不 bump 版本；URL 修改有 removed_links；來源消失不 archive，恢復／顯示改名仍用原 ID |
| `test_b05_cross_source_mapping_and_snapshot_move`、`test_b05_date_id_and_depth` | §08：同 task ID 在不同 project／source 不衝突，搬快照不換 ID，日期／舊 ID；超過 32 層阻擋 |
| `test_b05_source_updates_and_local_edits_conflict`、`test_b05_order_changes_protect_local_siblings`、`test_b05_archived_destination_is_not_used_for_new_items` | §09：內容／改回原值／pin／link／approval／archive 保護；本機 sibling 使來源重排衝突；不向封存專案加入新項目 |
| `test_b05_stale_source_and_destination_stop_apply`、`test_b05_snapshot_race_and_destination_missing` | §09：bytes 改但 size／mtime 相同、集合／根身分、目的版本／pin／link／order 變；兩次 descriptor 掃描競態、目的消失；首次驗證沒有新增 receipt |
| `test_b05_restart_lost_reply_and_partial_recovery` | §09／§24：四個 phase 的回覆提交前／後重啟，共八種；receipts 去重、沿用 ID、每個 phase 最終成功且 summary 不重複 |
| `test_b05_sqlite_rollback_is_reconciled_without_duplicate_rows`、`test_b05_record_commit_reply_loss_and_mid_import_source_change`、`test_b05_uncertain_budget_has_one_incomplete_summary_and_can_resume` | §09／§24：逐筆 rollback、commit 後回覆遺失、途中來源變動／partial／新 preview、重試耗盡後 resume，沒有重建或重複事件 |
| `test_b05_retirement_busy_cancel_and_resume` | §24 第 7 步：人的退役聲明、busy、cancel 保留已提交列，下一張 preview 安全接續 incomplete |
| `test_b05_invalid_and_incomplete_formats_are_reported`、`test_b05_descriptor_snapshot_refuses_unsafe_sources`、`test_b05_ambiguous_names_are_blocked_and_parser_reports_nested_blocks` | §06／§20：JSON／UTF-8／重複 key、id mismatch／missing／ambiguous／cycles、非法 state／open steps；symlink／FIFO／超限／不支援巢狀語法明列 blocker |
| `test_b05_completion_missing_ledger_never_seeds_approval`、`test_b05_frontmatter_dialect_and_crlf_hash` | §05／§20：缺 ledger／marker 不寫 seed，不授權 Connector approval；CRLF、Unicode、引號、comments、list／map 與原始文字 |
| `test_b05_daemon_source_boundary_and_scopes`、`test_b05_config_source_allowlist_is_strict` | §06／§09：observe 不能變更、browser path／unknown source／非字串／額外參數拒絕；actor／digest／TTL 綁定；sources 不洩漏絕對 path |
| `test_b05_http_rpc_and_mcp_share_the_same_actions`、`test_b05_cli_submits_preview_then_its_fixed_apply_key` | §09：CLI／HTTP／MCP 同 OperationService、reads 與 action、actor-bound preview 不由 generic operation read 洩漏 |
| `test_b05_many_records_use_constant_steps_and_no_children` | §09／§24：1,008 work items 仍只有兩個 operations（preview／apply）、四個 phase steps、一個 shared snapshot／summary；沒有 child operations 或 per-record Hub events |

必跑 `uv run ruff check .`、完整 `uv run pytest -q`；Dashboard 另做 `.mjs` 的 node check 與 en／zh-TW、390／768／1440 px 的 Playwright 預覽、套用雙擊去重、console／overflow／錯誤 DOM 文字檢查。

## 尚未涵蓋

- 任意新版 Hub、壓縮匯出、自訂 YAML 全語法、刪除／trash 紀錄的復原、附件 bytes／Git 成果／完整 assistant 對話遷移。需求文字和原始連結保留，但不 materialize 其指向內容。
- 自動改名 identity、認領同名 Connector 列、雙向同步、watcher、Hub runtime 接管、重送 queue／delegate。第一版皆不做。
- 衝突後明確 adopt-baseline／逐欄位人工合併操作尚未設計；第一版衝突持續可見，管理 actions 可人工處理正式內容，匯入器不自動重設 baseline。
- project 完成／phase 的正式管理功能仍由 work-items.md 列為未涵蓋；本包只保存 Hub 的歷史事實。
