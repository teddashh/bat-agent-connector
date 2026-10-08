# 整理與復原：回收 managed 資源，保留工作脈絡

日期：2026-10-08。狀態：Phase 1，待審核的實作規格，本文的新增合約尚未實作。
對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §23 全節、§10「整理與復原」、
§19 同名畫面、§26 E01／E02，以及 W06 cleanup。操作沿用 [OperationService](api-v1.md)，
歸屬沿用 [resource policy](resource-policy.md)，關係沿用 [work items](work-items.md)。

整理回收的是執行用的 session／worktree／clone。工作項目、checkpoint、接收回執與查詢歷史永久保留。
收合、完成、封存、停止執行、整理及刪除遠端 branch 是不同動作；本規格不把它們串成隱含副作用。

## 固定來源版本

| 來源 | 固定版本／實際核對位置 |
|---|---|
| Connector | 開始時 `HEAD = origin/main = 5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`；分支 `feat/cleanup`。`pyproject.toml` 版本 0.2.4 |
| 計畫 | v1.0，2026-10-06；只引用節號與驗收編號，不複製私人計畫 |
| 前輪交接 | [2026-10-08.md](../handoff/2026-10-08.md)，待辦 1；其中 main 與測試數字是交接當時的紀錄，不取代上述實作基準 |
| BAT | `b7419892fbc9946799b64cca24c2ec8c7fa15c42`，遠端協定 `bat-remote/v2`。以 commit 固定來源，不推定所有 host 已安裝同版 |

BAT 的 [ClaudeRuntimeRouter::stop_session、claude_stop_session](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/claude.rs)
將停止送到 Claude sidecar 或 Codex runtime；runtime 停止後才解除 session ownership。
它不是刪除工作項目或對話的 API。`getSessionMeta` 的 null 也不能單獨證明某次 start 從未送出。
Connector 現有呼叫在 `lifecycle._stop`，channel 是 `claude:stop-session`。
BAT 的 [remove_worktree_native／force_remove_worktree](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/crates/bat-git/src/worktree.rs)
包含 force remove、檔案刪除後 prune 及可選的 `branch -D`；新整理不用這條路徑。
本規格沒有新 BAT channel，也不修改 BAT。

## 現有與新增行為差異

| 現有程式／資料 | 本包改變 |
|---|---|
| `checkpoints._run_continue` 在 `worktree.prepare` 前寫 `operations.external_refs`；`checkpoint_runs` 在 start／send 後才寫 | 發現資源時合併兩者及 step intent；崩潰的 run 不能漏掉，也不能因沒有 run 列就當成未啟動 |
| `checkpoints.prepare_script` 建自有 clone、`batc-cp-*`、`batc/cp-*`，clone 標 `batc.managed-clone`、`batc.source` | 經來源證據與即時身分檢查後，保留 commit，移除 worktree；可選擇退休整個 clone |
| `integration.Area`、`integration_previews`、`integration_receipts` 留下 bare repo、repair worktree 與 pins | 依已保存的 area／來源／refs，清理已釋放的內容；不呼叫 `integration.preview` 來做 cleanup preview，因為它會建立 repo、fetch 與寫 ref |
| `integration.receipts()` 算 `effective_status`，保留 `location_class`、source SHA、picked mapping、送達 SHA／PR | 整理依接收回執判斷覆蓋範圍，不能以 ancestor、工作項目 done、PR merged 或測試通過替代 |
| `registry.py` 沒有 delete；`sessions_observed` 會標 gone，仍保留列 | 繼續不硬刪 registry；確認整理後標 `cleaned` 與 tombstone 指標。gone 和「已整理」分開 |
| `lifecycle.session_cleanup` 只整理 BAT 建立的 orchestrate worktree；connector-made 回 KEEP／`NOT_A_BAT_WORKTREE` | 保持 connector-made 的 BAT worktree 禁令。舊 cleanup 改為只讀評估；新 mutation 一律走 reviewed operation |
| **已有例外**：`TaskDaemon._tick_task` 的 finally 會呼叫 `BatTaskAdapter.cleanup_external_worktree`，terminal task 可留 `refs/batc/tasks/*` 後移除乾淨 worktree；`Journal.complete_external_cleanup` 清指標、記事件 | 這不是全無整理。新包把這個刪除入口納入 TaskCoordinator 決策與 reviewed cleanup operation，移除 worker 的自動刪除／刪除重試；已存在的 retained 事件可以回查與復原 |
| `work_item_links` 只有 session、checkpoint、operation、task、pull_request；尚無 artifact／materialization 帳本 | 保留所有既有連結並可查 tombstone；不在本包新建附件系統。不透明附件參照只列為保留 |

## 範圍、識別與發現

`cleanup.preview` 的 `target` 必須且只能選一種：

| `kind` | 必要值 | 展開規則 |
|---|---|---|
| `work_item` | `work_item_id`；`include_children=false` 可改 true | 依 `parent_id` 展開，包含封存子項目；沿所有有效及已移除的歷史 links 找 execution／session／checkpoint／integration。`derived_from` 不自動展開 |
| `checkpoint` | `checkpoint_id` | 來源 session 列為觀測；展開該 checkpoint 的 runs、continue operations／steps／external refs、相關整合回執與共用 clone |
| `integration` | `operation_id` | 接受 `integration.preview`／`apply`／`handoff` 的 ID；展開其 preview、來源、receipt、repair session／worktree、pins 與 area |
| `host` | `host` | 該 configured host 的 inventory（含 gone）、registry、checkpoint／integration／task 建立紀錄與已知 retained records。唯讀資源仍顯示；不列舉整個 managed root 或磁碟來猜候選 |

範圍決定選入的資源，**不限制依賴檢查**。同一實體在範圍外的使用者、task、operation、
preview、restore 與保留規則也要查。若 clone／area 有範圍外資源，列出影響與保留原因；
不能把它們偷偷加進刪除計畫。所有來源只接受 journal／registry 中已記錄的路徑，或由可信建立
intent 的固定參數推導；使用者不能傳入任意 filesystem path、shell 或 ref 作為刪除目標。

Session 沿用原 ID `host/session_id`，Task Service 的 task／command、work item、checkpoint、operation
ID 都不重編。Cleanup item 的投影鍵統一為穩定 `cr_<32 hex>`，session 以 alias 保留原 ID，
不是重編 BAT session ID。投影鍵由 host、kind、**原始建立 intent ID**、
該 intent 的 resource slot 算 SHA-256 前 32 hex；clone／area 共用時追到首次可信建立 intent。
Worktree 的 failover、reviewer、warm reuse、後續 continue 都指回同一 creation slot，不按引用次數產生 ID。
Ref 使用 owner repository resource ID 加完整 ref 名稱與建立 intent 的 slot；保留內容另有 `ret_<32 hex>`。
只有 registry reservation 的舊 session，以原 host／session ID／created_at 作該 reservation 的 intent
識別，仍須通過共用 creation evidence／live binding；不能以可修改的 title／task_id 算 ID。

舊資料 migration 以已保存的 intent、`checkpoint_runs`、registry 的 creation evidence、
task branch／事件與 integration rows 建 alias。只讀 preview 對可證實舊資源算同一 ID，不寫入 alias。
同一 host、canonical common git dir／worktree path 指向同一可信 creation slot 才合併；
證據互斥時列 `BINDING_MISMATCH`，不以名稱或 path 字串強行認領。刪除後同一路徑被新 operation
重建是新 generation、新 ID；原 tombstone 永遠不改回 active。

### 資源清單

以下「移除」都受後面的保留、權限與 crash contract 限制。建立證據、path、Git 身分必須同時成立；
`location_class=managed_clone` 或 `batc/` 名稱只提供線索，不單獨授予寫入。

| kind／覆蓋內容 | 發現 | 歸屬證明 | 實際移除 | 保留／復原內容 |
|---|---|---|---|---|
| `session`：checkpoint.continue／integration.handoff 的 headless 或有 tab managed session；同範圍其他已證實 managed session | inventory、registry、run、operation external refs／`session.start` request；handoff 的 deterministic session ID 與 receipt | 共用 `resource_policy.classify`／`authorize_session`；reservation 或可信 task recovery 對上 host、profile／workspace、BAT meta cwd 與 managed workdir | 只在無 writer／pending 時經 `lifecycle._stop` 的既有 stop 路徑停止 runtime；不刪 GUI tab，不刪 BAT 的 provider transcript | 原 session ID、最後觀測、固定 checkpoint excerpt、已保存 transcript 參照、relations、stop receipt。沒有「復活 session」 |
| `worktree`：checkpoint `.bat-worktrees/batc-cp-*` | `checkpoint_runs`、continue external refs 與 `worktree.prepare` request；只在已證實 clone 做 `worktree list --porcelain` 交叉核對 | `check_checkpoint_worktree` 的固定 binding，加 clone markers、real path、common dir、HEAD／branch 與 creation intent | 先 pin HEAD 到 retained ref，停止 idle sessions、處理明確選定的 dirty discard 後，SSH `git worktree remove <exact path>`，**無 force** | HEAD 與起點 refs、source checkpoint、原 branch／path；可建新 managed worktree |
| `worktree`：integration `wt/batc-fix-*` | handoff external refs／`repair.prepare` request、receipt 的 repair 路徑與 resolver IDs | `check_repair_worktree`、`Area.prelude` 身分檢查及原 handoff intent；common dir 必須是該 `repo.git` | 同上；未釐清的衝突／resolver／apply 保留，不 abort merge 來湊成乾淨 | 已 commit 的 resolution、parents、source pins／回執；未提交衝突只有明確 discard 才可放棄，不能宣稱完整可復原 |
| `worktree`：task 外部 worktree；BAT-made connector worktree 的觀測 | tasks.external_worktree_path／external_branch、commands、branches、registry、`external_worktree_retained` 事件 | TaskCoordinator 先准入，共用 `authorize_external_worktree`／`check_external_worktree`；再要求 root 確實在 managed roots。BAT-made 還須原 creation 記錄與 common dir | 只有 managed clone 內、已證實 binding 且 coordinator 准入才經 SSH 非強制移除；不送 BAT rehydrate／remove。無充分 BAT-made 建立證據就保留 | task verified commit、既有 `refs/batc/tasks/*`、branch、task event／command 關係；legacy shared clone 全部唯讀 |
| `local_branch`：`batc/cp-*`、`batc/fix-*`、`batc/task-*`、restore 新分支 | 原始 prepare intent ＋已證實 repo 的 exact `for-each-ref`；不是 glob 刪除 | 名稱、建立 operation／task、repository ID、預覽 SHA、worktree bindings 全部符合 | 已送達且無 checkout／其他需要時，用 `git update-ref -d <exact full ref> <expected old SHA>` CAS；不使用 `branch -D`。選擇 discard 的未送達 branch 保留 | 刪除前 HEAD 已在 retained ref；保留原 ref→SHA 對照，可用新 branch 名復原；不改任何 remote branch |
| `git_pin`：checkpoint `refs/batc/source/*`、integration `refs/batc/pv/*`／`ops/*`、task retained refs | 來源 prepare／preview／compose 的固定 ref、step output、task retained 事件，加 exact ref 讀取 | 原 mutation 的 intent 對上 repo 與 ref／SHA；不因位於 `refs/batc/` 就當 owned | pv／ops pins 只有釘住成果已接收或只是已釋放的 base、且無 resumable consumer 才可 CAS 刪；先建立 retained alias。source mirror pins、`refs/batc/tasks/*`、`refs/batc/retained/*` 預設不刪 | ref→SHA／來源版本全保留；未知 pin 保留。物件庫不 gc，不保證 ref 刪除本身回收容量 |
| `clone`：checkpoint 共用自有 clone | continue external refs／prepare step、runs；`target_clone` 可能沿用已知 clone | 原 clone 建立 intent、`batc.managed-clone=true`、`batc.source`、canonical repository 與 `.git`；不能認領預先存在的 managed root repo | `retire_containers=true` 才安排；所有 worktrees／writers／consumers 已釋放，全部 refs 與必要 objects 已驗證複製到 retained store 後，限定該 container 移除 | retained bare store、完整 ref manifest、checkpoint 起點／結果 objects、tombstone；主 checkout／未知額外檔案有內容便保留 |
| `integration_area`：bare `repo.git` 與 area | `integration_previews.area_path`、preview 的 prepare step request 中 `area`、handoff 及 apply intent；Area 的固定 binding | 現有 `check_integration_area` 與 `Area.prelude` 的 batc host／repository／URL、config allowlist、no links／alternates／replace／grafts 檢查 | `retire_containers=true`，無 writer、repair、valid preview、未完成 apply／push／restore，refs 完整轉存後移除 exact area | retained bare store、全部 pinned source／target／composed／resolved SHA 與 PR receipts |
| `temporary`：clone prepare 的 `*.batc-tmp-<op suffix>`、integration 的 op 暫存／check worktree | 只從各 prepare／check 的 exact intent 推導；容器內核對。正常 integration 腳本已刪自己的暫存 | 原 intent ＋該 temp 自有 markers／確定性 Git binding；半建成、無 marker 的資料夾不能憑名稱認領 | 有 commit 時先保留；已證明沒有成果且 creator 沒有執行中程序／未決 step 才移除 exact temp。已註冊 worktree 走非 force remove | 每項原路徑／最後觀測／移除證據；無內容不提供 restore。marker 不全列 unknown |
| `retained_store`／`retained_ref` | 新 retained rows、既有 task retained event，並讀回實際 Git ref／object | 原 preserve／archive step 的建立 intent、store marker／manifest／digest | 本包無永久刪除；不因 source clone tombstone 就刪 store | 只列實際存在的 commit；可供 restore，離線顯示 unavailable |
| manual／unknown session、worktree、repo、local state；remote branch；opaque artifact 參照 | 同範圍 inventory／links／receipts 的 human_checkout／remote，已知 repo 的 worktree registration，以及 task.context_refs.attachments | 共用政策輸出 manual／unknown；不推定 opaque attachment 字串就是本機路徑 | 永遠不碰；remote branch 刪除另有 GitHub action。本包未實作 artifacts adapter | 顯示原 ID、位置或 opaque ref、保留原因。未來 W05b 的共享 materialization 仍須沿用全域 content-required 關係規則 |

clone／area 是共用的 Git 內容容器，不等於某一個 run。預設 `retire_containers=false`：先回收
runtime／worktree，clone 留作 retained ref 的載體並列 `RETAINED_CONTENT_STORE`。
選擇退休容器時預覽要列 store 目的地、暫存空間需求與所有附帶 refs，不隱含搬移其他 active 工作。
保留 refs 的容量不是「可回收容量」；impact 的 bytes 是估計，無法量測回 null。

### Retained store 與容器退休

store 位於同 host 的 `<managed root>/.batc-retained/<container resource ID>/repo.git`。
首次建立有獨立 preserve intent；延用 integration 的隔離 Git、config／path integrity 檢查，
在共用 `resource_policy.py` 擴充 `role=retained` 與上述精確目的地規則，沒有另一套 ownership 判斷。
bare repo 以 `git init --bare --template=` 建於 operation 專用 temp，marker 包含 resource ID、host、
source repository identity 與 manifest digest；不帶 remote credentials／hooks。

容器退休先枚舉**整個容器**的 refs、HEAD、每個 checkpoint／receipt／reflog 還需要的 SHA。
不認識的 local branch／pin、unreachable object 保留需求、未知檔案、links、submodule／nested repo
或未解釋的 reflog 內容都阻擋退休；不能以「clone 是我的」略過其他內容的保留需求。
複製已審核的完整 refs／required objects，以 SHA fetch 到 store（不用 hardlinks、alternates、
`--shared`、`--mirror` 或 prune），每一個保留 ref 都以 CAS 固定。原 ref→store ref 名稱／SHA 的對照
存進 manifest，包括會隨容器一起消失的 source mirror／原 branch；未送達或 discard branch 必須
在 manifest 標示，不能把整個 container deletion 當作允許刪 branch 的旁路。
在 store `cat-file`／連通性核對全部 required commits／trees／blobs，確認保留庫獨立於來源。

退休前再次對照 manifest、全部 worktree registration、consumer 集合、容器檔案 manifest。
SSH adapter 只處理這個已核對、journal 有建立證據的 exact container；用 no-follow 的限定刪除，
逐項留下移除進度，遇未知檔案／身分變動立即停下。不使用根目錄遞迴掃描、glob rm、
`git worktree prune`、`gc --prune` 或 Git 自動 maintenance。store 驗證完成前不移除來源。
保留 store 的物件庫可能接近原 clone 大小；此選項主要回收 runtime 目錄與工作副本，沒有承諾
保留全部成果同時釋放全部 Git objects。

## 保留判斷與原因代碼

Preview 分別回 `work_state`、`runtime_state`、`delivery_state`、`resource_state`。
沒有 tab、gone、離線、安靜多久、agent 退出、工作封存／done，都不是刪除證據。
每個 item 的 `reasons[]` 包含 code、短說明、阻擋的 resource／consumer／command／receipt ID、
evidence、是否可用 preview choice 排除。多個原因全部顯示，不只第一個。

| code | 何時保留 | preview choice 能否排除 |
|---|---|---|
| `MANUAL_READ_ONLY` | 共用政策確認人工來源 | 永遠不能 |
| `UNKNOWN_READ_ONLY` | 無可信 creation evidence；半建成、互斥或不完整的歸屬 | 永遠不能；只能先以原 start／prepare operation 對帳 |
| `WORKDIR_NOT_MANAGED` | legacy shared clone／人工 checkout，或 root 不在 managed roots | 不能，shared_clone_worktrees 設定不豁免 cleanup |
| `BINDING_MISMATCH` | host／profile／workspace／cwd／common dir／branch／generation 與可信建立紀錄不合 | 不能 |
| `CLONE_NOT_OURS`／`CLONE_CONFIG_TAMPERED` | markers、links、config／Git integrity 不符 | 不能 |
| `OBSERVATION_UNAVAILABLE` | host／BAT／SSH 讀不到、資料過期，或無可靠 runtime／dirty 觀測 | 不能；離線不是 missing／clean |
| `ACTIVE_WRITER` | session streaming、CLI writer、同 worktree 的其他 writer 或處理中 runtime | 不能；另行停止後重新 preview |
| `SESSION_WAITING` | 等使用者回答、permission、queue／turn 尚未結束 | 不能；不代答、不 interrupt 來清理 |
| `COMMAND_UNRESOLVED` | start／stop／send／prepare／push 等 commands 或 operation steps 為 intent／started／accepted 未完成／uncertain | 不能；即使 parent operation cancelled／failed 仍看未決 step |
| `ACTIVE_EXECUTION` | 別的 active／paused／verifying／needs_ted task 或尚未釋放的 execution 需要內容 | 不能；paused 並非完成 |
| `TASK_OWNER_REFUSED` | TaskCoordinator 拒絕，control_version 改變、存在 pending command、warm claim／handoff、或 coordinator 不可用 | 不能 |
| `CONTENT_REQUIRED` | 任一範圍內外 consumer 還要讀此版本／實體；valid integration preview、resumable apply／resolution、restore 或未完成工作需求 | 不能；有效 reservation 也算 |
| `UNCOMMITTED_CHANGES` | tracked／staged／untracked／ignored 的內容，或進行中的 Git merge／index 狀態 | 僅 owned、無其他阻擋時，由具 `cleanup_discard` 的人逐項選 `discard_uncommitted`；nested repo／未知內容不能 |
| `RESULTS_NOT_DELIVERED` | 回執沒有涵蓋全部結果，新增 commit／只 pick 一部分、只有 verification、pending／conflict／composed | 可逐項選 `discard_undelivered`，另需 `cleanup_discard`；HEAD 仍保留，未送達 ref 不 CAS 刪除 |
| `DELIVERY_UNCERTAIN` | `integration.receipts()` 的 effective_status=unknown，或任何未證實 push | 不能；必須先由 delivery owner 對帳 |
| `RETENTION_RULE` | 已配置／既有 task retention 或 restore 要求保存實體內容 | 不能 |
| `SHARED_CONTAINER` | clone／area 的其他資源不在本次計畫或不能移除 | 不能；只清可移除的子資源 |
| `RETAINED_CONTENT_STORE` | retained ref／store，或預設留下的 clone／area 載體 | 本包不永久刪除；容器可明選轉存後退休 |
| `REMOTE_OUT_OF_SCOPE` | remote branch／PR／deployment | 不能；不做任何 remote mutation |
| `RESOURCE_KIND_UNSUPPORTED` | opaque artifacts、未實作的材料化／archive adapter，不能證實版本或歸屬的舊資源 | 不能 |

`UNCOMMITTED_CHANGES` 與 `RESULTS_NOT_DELIVERED` 在未選 discard 時必須保留。
選擇後仍在 `overridden_reasons` 顯示原原因、授權 actor、精確內容指紋及不可復原部分；
其他原因依然阻擋。確認參數、bulk、work item approve 都不能繞過。

### 成果接收與共享內容

1. 讀原 creation 起點到 preview HEAD 的結果版本／commit 集合、receipt 的 `pinned_sha`、mode、
   `commits`／`picked`／`resolution_sha`、`delivered_sha`、PR repository ID／number。
   只有 `effective_status=delivered` 且 exact source revision 覆蓋此結果集合的回執可以授予正常整理。
   `already_included` 本身不是送達事實；等 push/readback 的 delivered receipt。
2. Merge、pick、外部 squash 的接收都保存原成果→接收版本 mapping。Pick 部分 commits 不覆蓋
   其餘結果；分支在送達後又前進也不覆蓋新內容。Squash 的目的 SHA 不是 source ancestor，
   仍可依可信 exact mapping 整理。任意 PR link、相同 tree、ancestry 或 caller 自報 delivered 不算。
   本包不增加一般 GitHub squash receipt 匯入／人工 attestation API；缺可信回執時保留。
3. `Journal.delivery()` 的 verified、tasks.delivered、work item approve 只證明各自的工作狀態。
   舊 task `stage_adopted` 只有文字 ref，沒有完整 revision coverage；不能直接當 Git 接收證據。
   Task 結果尚無 integration source adapter 時正常列 `RESULTS_NOT_DELIVERED`，或由人明選 discard。
4. 原 prepare 失敗、沒有產生結果時，須 exact 起點等於 HEAD、無變更、無未決命令，且 creation
   owner 證明 no-result，才可 `delivery_state=no_result`；不是「沒 receipt 就當空」。
5. 既有 work item links **全是歷史關聯**，不因 unfinished work item 的一條 link 就鎖住全部資源，
   也不因 link 被移除就忽略 active task。實體需求由 task／commands／未完成 operation／preview
   或明確 retention requirement 提供。確實需要重新讀原 worktree 的未完成工作用
   `content_required` consumer 表示，不能只存模糊 link。歷史 links 在整理後仍解析到 tombstone。
6. 依賴查詢不依 task_id 的最後值：warm-session 與 shared reviewer／successor 要讀 branches、
   commands、registry handoff／shares_worktree_with、operation external refs，保留全部曾使用者。
   一個資源只出現一個 item，`relations[]` 列出每個 work item／execution 使用區段。

## 權限與必要前置條件

提議新增 `cleanup` scope：回收可整理的 managed runtime／worktree／容器、從 retained commit
建立無 runtime 的新 worktree。`start` 是啟動 agent，`manage` 是管理資料；兩者都不隱含資源刪除。
`operate` 也不隱含 cleanup。新增 `cleanup_discard` scope 專管 preview 裡的 dirty／未送達內容放棄，
有它仍必須有 `cleanup`。發 token 仍只能由 local admin；一般 agent token 不預設給 discard，
人要授權此能力必須刻意重發。scope 不辨認 body 自報的「人」，授權以 token Principal 為準。

| 能力 | scopes／條件 |
|---|---|
| preview／retained list／tombstone search | observe；帶 discard choice 的 preview 另需 cleanup_discard，讀取不授予 apply |
| apply | cleanup；有任一 discard choice 另需 cleanup_discard；驗證 token 綁定 actor，不能由不同 actor 偷用別人的選擇 |
| restore managed worktree | cleanup；不啟動 session、不送 prompt。之後從 checkpoint 開新 agent 仍需 start |
| resume／cancel | Cancel 沿用 operation owner／scope 規則。Cleanup Resume 額外必須有 cleanup，有 discard choices 還需 cleanup_discard；原 actor 身分本身不豁免 scope |

現有 `OperationService._may_steer` 允許原 actor 不帶 action scope 操作自己的 operation；
本包只對 cleanup Resume 增加上述 action admission 檢查。Resume 記錄本次授權 actor／scopes，
不能以原操作曾有 discard scope 代替本次授權；Cancel 仍可阻止未送出的 mutations。
Accepted operation 的原始授權固定在意圖上，scope 撤銷不回溯已送出的副作用；需要立即停下時
取消同 operation，未決步驟仍先對帳。這沒有建立新的通用 token 撤銷排程機制。

主機 mutations 要 `writes=true`、`orchestrate=true`、configured canonical `managed_roots`、
`[verification] ssh_hosts` alias、受支援的 BAT capability／identity、可用 Git（沿用 integration 最低 2.38）。
Preview 不因 write tier 關閉而寫入／啟用它，回 read-only plan 與 blocked capability 原因。
所有 SSH mutations 先經擴充的共用 policy；source、destination、retained store、restore worktree
都核對。主機 read／write 使用既有 `SshGitRunner`，沒有可供 agent 任意 shell 的新 API。

Task-owned 資源先向 **同一 TaskCoordinator** 要只讀 eligibility，再在 apply 取得 coordinator
控制版本與 task／session locks 下的持久 cleanup reservation。新增 coordinator 方法是本規格需求，
目前 `TaskCoordinator` 沒有這個准入介面。只有 terminal、commands 都已釐清、全域 consumer 已釋放
且 delivery／discard 符合的資源可准入。Coordinator 擁有 task 停派、warm claim、handoff 與 writer
順序；cleanup 不自改 task state、不 pause／stop active task。Reservation 不轉移 task ownership。
有阻擋時先用原 task 控制路徑處理，再重新 preview。

### 執行前即時政策與競態

預覽採 read-only inventory fleet 的 live BAT 讀取；Git 讀用 `--no-optional-locks`、
`GIT_OPTIONAL_LOCKS=0`，關閉 hooks／fsmonitor／auto maintenance，使用 integration 已有的設定隔離。
不用 BAT `git:status`，不用 fetch／worktree repair／建立 lock file 來做 preview。
只讀 clone 身分檢查重用 `Area.prelude` 的 ident 部分，不跑 create 部分。
BAT state 讀取遵守 `service._state_safe`；沒有 cwd 的 Claude record 不呼叫會移除該 record 的
get-session-state，改列觀測不全與保留。來源不明不能因讀取而改寫分類或 runtime。

Apply 先鎖住精確 resource／repository／task reservation。中央 journal 的 reservation 不設自動過期；
重啟先對帳未決 steps。共享 writer、start、send、warm claim、integration、restore 都在送出前查
同一 reservation，跨 clone 指向同一 common dir 時共用鎖。遠端 Git script 沿用 clone prepare
的 flock 慣例，但 cleanup 必須有 flock（不可像舊 prepare 在缺 flock 時略過）；同一 clone／area
的 prepare、compose、push／repair 與 cleanup 一併使用此鎖，避免 SSH reply 遺失後遠端仍執行。
記錄 operation／step／generation 與仍在執行的程序身分，不用 `pkill` 或以目錄名尋找程序。

鎖內、每個外部呼叫的前一刻，檢查 root、container、worktree、Git dir／commondir 真實路徑、
no symlink／越界、creation markers、ref old SHA、dirty manifest、BAT cwd／writer／pending 及 commands。
拒絕會將寫入導向人工目錄的 `.git`、objects／refs links／alternates／config include／filters／hooks。
checkpoint clone 的 config 檢查需擴充 shared policy 的 allowlist，不能照搬 integration 的 role 標記
而把正常 origin 設定誤認為接管證據。Nested repo／submodule／額外未知內容預設保留。

Connector 的 locks 只能協調 connector writers，不能鎖住 BAT GUI 或同帳號外部程序。
Managed host 的限制若無法排除／確認外部 live writer，列 `ACTIVE_WRITER` 或
`OBSERVATION_UNAVAILABLE`，不承諾消除與未受控寫入的全部競態；非強制 remove 是最後一道保護。
canonical path 必須在 script 內緊接 mutation 重新核對，不能只靠 admission 的字串 prefix。
Git／filesystem script 經 SSH 在已證實的 managed clone／integration area／retained store 執行；
BAT stop 仍經既有 Fleet／host 路由（配置的 SSH tunnel），不用 SSH shell 代殺 runtime。

## Preview／apply／restore 合約

### cleanup.preview：純讀

這是共用 read handler `cleanup.preview()`，不經會保存 intent 的 `OperationService.create`。
新增 mutations 仍註冊 `ActionDef`；不為 read preview 另造 operation 狀態機。
Preview 不寫 journal／registry／events、不更新 inventory，不改 BAT／Git／filesystem。
採兩次 read snapshot，若期間 resource identity／content／dependencies 改變，回 `PREVIEW_UNSTABLE`。
讀取失敗的 item 留在計畫中，decision=retain、帶觀測原因；不能填成 dirty=0。

輸入：`{target, choices}`。`choices` 有 `retire_containers=false`，以及按 stable resource ID 的
`discard_uncommitted[]`、`discard_undelivered[]`（預設空）。不能指定 arbitrary paths、force、
delete_remote_branch 或在 apply 才增加選項。Discard 清單只能指本次範圍中的可證實 managed 資源。

輸出：`{preview_id, preview_token, fingerprint, contract_version, issued_at, expires_at, target, choices,
items, impact, ready, blocking}`。Item 必含：

| 欄位 | 內容 |
|---|---|
| identity | resource_id、generation、kind、host、原始 ID、repo／container、canonical path／ref、creation evidence IDs |
| observation | 四種狀態、fresh／unknown、last observation、HEAD／ref SHA、worktree／Git binding、dirty manifest digest |
| relations | 所有 work items／tasks／sessions／operations／checkpoints；history 與 content_required 分開；scope 外 blockers 也列 |
| delivery | evidence receipt IDs、exact revision coverage、接收 PR URL／repository／number／SHA；未知就標未知 |
| plan | decision=retain／reclaim／already_absent；固定且有順序的 steps、前置條件、依賴 IDs、retained refs／store destination、不可復原的 discard manifest |
| reasons | 保留原因／overridden_reasons，含 evidence；保留項目不收到 mutation |

`impact` 包含不同 kind 的保留／停止／移除／轉存數、受影響工作與範圍外依賴、PR 目的地、
保留 bytes／預估釋放 bytes、dirty discard 的檔案與大小、`runtime_restorable=false`。
有 retain item 不等於整個 preview blocked；有 reclaim item 且 action 所需能力可用才 ready。
所有列都列入 fingerprint，包括保留列，不能只釘住將刪的 subset。

### Preview token 與一致性

Token 是 stateless、HMAC-SHA256 簽名的 compact payload：format version、preview ID、actor、
target／choices、fingerprint、policy／contract version、host binding／設定 digest、issued／expiry。
以 daemon 既有 0600 admin token 導出的 purpose-specific key 簽名（不回傳 admin token），
可跨 daemon restart 驗證；admin token 輪替使舊 preview 無效。Token 是審核內容證據，不是 bearer
權限；每次仍驗證 API token／scopes。無需在純讀 preview 時寫一張 previews 表。
固定 TTL 15 分鐘；首次 apply worker 在到期前必須完成驗證。已驗證、已開始的 operation
依其保存計畫續做，不因 token 到期重新執行已完成副作用。

Wire format 固定為 `v1.<base64url(canonical payload)>.<base64url(HMAC)>`，無 padding。
Canonical JSON 延用 `operations._canonical` 的 sort_keys／compact separators／UTF-8。
Key 是 `HMAC-SHA256(admin_token_bytes, "batc.cleanup.preview.v1")` 的 bytes；signature 覆蓋
版本前綴與 payload bytes，驗證用 constant-time compare。`iat`／`exp` 為 UTC 整數秒，
`exp=iat+900`；preview ID 是 actor／target／choices／fingerprint／iat 的 canonical JSON
SHA-256 前 32 hex 加 `clpv_`，不帶 host credential。對外時間顯示 UTC ISO-8601。

Fingerprint 為 canonical JSON SHA-256：排序後完整 resource 集合、ownership／generation／path、
content SHA／dirty 檔案類型與 bytes digest、Git registration／refs／merge state、session writer／pending
狀態、commands、consumer 集合與版本、receipt coverage、retention rules、choices、預計副作用。
排除抓取時間、heartbeat／讀取次數、純顯示語言；last observation 的實際內容不排除。
只有顯示用的時間改變不算內容改變。尚未實作的 field 不以猜值補滿。

Apply handler 重新讀相同 scope＋choices，計算 fingerprint；與 token／precondition 不符時
`PREVIEW_STALE`，回 changed resource IDs／fields，要求重新 preview。開始前整批驗證，**任何列
變動都不送首個 mutation**；執行中重新核對整個剩餘 snapshot，僅扣除本 operation 已證實的
planned transitions（stop、retained ref、remove）及自身 reservation，不能把外部變動當作自己的。
之後 stale 保留先前回執、停止所有未送出的步驟；不換成新計畫或新增範圍。

不分頁執行半份 preview。最多 500 resources、choices／token payload 最多 16 KiB；超過時
`PREVIEW_TOO_LARGE`，可選更小 work item／checkpoint／integration 範圍。長 manifest 與檔案清單
在 response，token 只攜 digest。Apply body 可維持現有 `api_v1.MAX_BODY=200_000`。
對大型 host 完整預覽的後續 paging／snapshot 支援列為 open question，不能截斷後假裝完整。

### cleanup.apply：執行已審核計畫

註冊 `ActionDef("cleanup.apply", "cleanup", ...)`，共用 admission 驗證 token 簽名／actor／scope／
choices／format；昂貴的 live revalidation 在已持久化意圖後的 handler 完成。
不增加第二張 task database，HTTP／MCP／CLI 都呼叫同一 OperationService。

```json
{
  "action": "cleanup.apply",
  "target": {"preview_id": "clpv_<32 hex>"},
  "params": {"preview_token": "<由 preview 回傳的 signed payload>"},
  "preconditions": {"preview_fingerprint": "<preview.fingerprint>"},
  "idempotency_key": "<client 保留的操作識別>"
}
```

禁止在 apply 帶新的 resource／discard 清單或 force。Token 釘住全部 reclaim items，不能讓 adapter
自行挑選 subset；要改選擇就重新 preview。Admission 記 operation intent；同 actor／key／內容
回原 operation，不因回覆遺失產生另一份清理。
`params` 唯一可選的額外 metadata 是 `supersedes_operation_id`：必須指同 scope 的舊 cleanup.apply，
且原 actor 相同或 caller 是 admin；只連歷史，不繼承舊 token、放寬 plan 或接手未決 step。
驗證匹配後將**重算的完整 document**、原 token hash、source fingerprint 在 journal 固定；
它與人讀過的 document 有相同內容指紋。只此時建 resource aliases／per-item intent rows。
Operation ID、preview ID、原 resource IDs 固定在 `external_refs`，receipt 可在 operation 執行中讀取。

每 item 依固定 DAG 處理：`validate` → `preserve` → `stop`（若列出 idle loaded session）→
`discard`（若有明選）→ `remove.worktree` → `remove.ref`（若 delivered 且列出）→
`archive.container`／`remove.container`（若選退休）→ `finalize`。
Session／branch／container 各是獨立 item，用依賴 ID 相連；step 名稱為
`item.<resource_id>.<phase>.a<attempt>`。Session 已停止才允許依賴它的 worktree remove；
preserve 在任何丟棄／移除前完成，完整 tombstone draft 在第一個 mutation 前存在。

| 實際副作用 | 限制與證據 |
|---|---|
| pin `refs/batc/retained/<resource_id>/<revision slot>` | `git update-ref <ref> <SHA> <zero>`；已等值是成功，不同值 `RETAINED_REF_MISMATCH`；記錄 commit／tree 與 object 可讀證據 |
| stop managed session | 共用政策與 audit／rate limit，沿用 `lifecycle._stop`。擴充它讓 cleanup operation 用 `retry_on_disconnect=false`，傳遞 ambiguous error，不把 timeout 包成「沒有停止」；執行前另檢查 pending、queue、tasks，返回 ACK 後讀回停止證據 |
| explicit dirty discard | preview 有完整 tracked／staged／untracked／ignored manifest，含內容 digest／type／size；只還原／刪除此份 owned manifest。tracked 用隔離的 `git restore --source=<pinned HEAD> --staged --worktree -- <paths>`；untracked 用 no-follow exact unlink。Git merge state 的例外見下；不做未列出的 reset／clean sweep、不能 force worktree remove |
| remove worktree | 保留 HEAD 可讀、所有 sessions 停止／無 writer、dirty 為零，managed clone／bare area 中非強制 `git worktree remove <exact path>`。Git 拒絕就保留，不以 rm fallback |
| remove delivered owned local ref | exact ref 與 expected old SHA CAS；受 branch／pin inventory 規則限制，任何 consumer／checkout 都阻擋 |
| retire container | 先 archive、verify store，再依上述限定檔案刪除。未知 files／ref 不能夾帶刪除；不刪 source repo、remote branch 或整個 managed root |
| finalize | 同一 SQLite transaction 完成 item receipt、tombstone、retained rows、relations 與 api event；registry JSON 用既有 flock 標 cleaned，可對帳重播 |

Dirty discard 不等於 snapshot：保留 HEAD 只能復原已 commit 的內容。
Ignored 檔案也算內容；資料夾過大或無法完整觀測時 `DISCARD_MANIFEST_UNAVAILABLE`，繼續保留。
不透明、manual／unknown 檔案或 nested repo 不可由這個參數丟棄。人看到差異與不可復原部分後
在 preview 選擇；apply 是一次點擊，不加相同意思的第二次確認。

Repair worktree 尚有 MERGE_HEAD 時，只有原 integration owner 已取消且無未決 push／resolver、
prepare intent 的兩個 parents、ORIG_HEAD 與 pinned HEAD 全部相符，才可在 discard plan 列
`discard.merge` 的 `git merge --abort`，預先列完整 before／after index／檔案／merge-state manifest。
不能在 apply 第一次遇到衝突才加 abort；無法預測 abort 的精確效果時保留。
其他 rebase／cherry-pick／sequencer 狀態第一版列 `RESOURCE_KIND_UNSUPPORTED`，不以 reset 代清。

Result：`{preview_id, fingerprint, summary, items, tombstones, retained, next_action}`。
Per-item receipt 有 planned steps、actual steps／attempts、status、before／after observation、
retained locations／SHAs、discard authorization／manifest digest、errors、settled_by、關聯及 PR destinations。
Item status：`retained`、`pending`、`running`、`succeeded`、`already_absent`、`failed`、`uncertain`、
`blocked_stale`、`cancelled`。不是刪除的 retained item 也有 receipt，沒有 tombstone 成功假象。

Operation 沿用既有狀態，**不新增 partial 狀態**。全部計畫處理完成為 succeeded；有 definitive
可重試項失敗為 needs_attention，`summary.partial=true` 與成功／剩餘 counts；回覆不明則 uncertain。
確定失敗且不影響其他 item 可繼續獨立 item；uncertain 或 stale 停止後續 mutations。
首次驗證 stale 為 failed、零外部副作用；已部分完成的 stale 為 needs_attention，不能 Resume
換掉 fingerprint，必須新 preview／新 operation，並連 `supersedes_operation_id` 到舊回執。
穩定計畫的暫時失敗可對同 operation Resume；成功 item 不重做。

### cleanup.restore：只復原真正保留的內容

讀取 handler `cleanup.restore_list()` 回 `{retained[], unavailable[], next_cursor}`
（按 scope／resource_id／host／PR／文字、limit／cursor）。只有實際讀回的內容進 `retained[]`，
包含 retained ID、kind、原 resource ID／tombstone、ref／SHA／digest、location、available、
last_verified_at、可用 mode 及不可復原部分。Git 類別要 live `cat-file`／ref 讀回；離線或消失時
原 journal 記錄進 `unavailable[]`、available=false、列原因與最後驗證時間，不能選為可復原項目。
列表 digest 釘住 identity／ref／SHA／tree／manifest，不含本次抓取時間。固定 checkpoint excerpt 可直接唯讀
查看；BAT 的尚未匯入對話只提供原參照，不宣稱有 connector archive。

Mutation 註冊 `ActionDef("cleanup.restore", "cleanup", ...)`：
`target={retained_id}`，`params={mode:"managed_worktree"}`，
`preconditions={expected_retained_digest:<列表版本指紋>}`，必有 idempotency key。
第一版只在 retained 所在 host 復原；不接受 client 給的目的路徑、任意 branch 名、runtime ID 或 prompt。

操作先記 intent，再保留同一 retained ref 的 reservation。目的地是其已證實 bare store（或尚在的
managed clone／integration repo）下固定 `wt/batc-restore-<operation suffix>`、新 branch
`batc/restore-<operation suffix>`；checkpoint clone 可使用 `.bat-worktrees` 的同樣固定 slot。
由共用 policy 新增精確 restore destination 規則。`restore.prepare` 先核對來源 commit 與目的地
no links、managed roots，非強制 `git worktree add -b <new branch> <new path> <exact SHA>`，
`restore.verify` 確認 HEAD／tree／乾淨狀態並 finalize 新資源。
已有同 operation 的新 worktree 只在 binding／commit 全相符時回同一結果；不能重用未知目錄。

Result：`{operation_id, retained_id, restored_resource_id, restored_from_resource_id, host,
worktree_path, branch, commit_sha, tree_sha, runtime_restored:false, context_links}`。
原 tombstone 不改寫、不重用原 session／worktree ID；新 worktree 另記 provenance／creation intent，
沿 relation 指回原工作。保留 ref 不被消耗，restore 的內容需求直到新資源可獨立使用才釋放。
新 runtime 要使用既有 checkpoint／start 路徑，不能 restore 自動啟動。

### 穩定錯誤代碼

HTTP 錯誤格式沿用 `{error:{code,message}}`；operation 已 accepted 後以 `error_code`／item receipt
表示相同錯誤。Policy code 不另改名；表中的 HTTP code 是可在 admission／read 得到的對應值。

| code | HTTP／operation 意義 | 下一步 |
|---|---|---|
| `INVALID_TARGET`／`INVALID_PARAMS`／`INVALID_REQUEST` | 422，範圍或 choices 不合約，apply 加欄位／force | 修正輸入 |
| `NOT_FOUND`／`UNKNOWN_HOST` | 404，scope／retained ID 不存在；有 tombstone 的原 ID 不回 404 | 查原 ID／configured host |
| `FORBIDDEN`／`DISCARD_SCOPE_REQUIRED` | 403，缺 cleanup／discard scope | 由人管理 token；不回退 admin |
| `RESOURCE_CLEANED` | 409，舊 generation 已有 confirmed tombstone，不能由 send／resume 重新啟動 | 從實際 retained 內容建新資源 |
| `PREVIEW_TOKEN_INVALID`／`PREVIEW_ACTOR_MISMATCH` | 409／403，簽名／版本／actor 不符 | 以自己的身分重新 preview |
| `PREVIEW_EXPIRED`／`PREVIEW_STALE`／`PREVIEW_UNSTABLE` | 409，首次已過期／資源變動／讀取不穩定 | 顯示差異，重新 preview；stale 不自動放寬 |
| `PREVIEW_TOO_LARGE` | 413，超出整份安全上限 | 換較小 scope；不截斷執行 |
| `IDEMPOTENCY_CONFLICT`／`IDEMPOTENCY_KEY_REQUIRED` | 409／422，沿用 OperationService | 查原 operation／保留 key |
| `CLEANUP_IN_PROGRESS`／`TASK_OWNER_REFUSED` | 409，資源已被另一 mutation reservation／coordinator 阻擋 | 先查 owner operation／task |
| 共用政策代碼（含 `DESTINATION_MANUAL`／`DESTINATION_UNKNOWN`） | 403／409，人工／unknown／binding／path／config 拒絕 | 只讀保留；不讓 confirm 解除 |
| `TIER_DISABLED`／`NO_MANAGED_ROOT`／`GIT_RUNNER_UNAVAILABLE`／`LOCK_UNAVAILABLE` | 403／409，執行能力不足 | 管理員配置；不建立替代旁路 |
| `DISCARD_MANIFEST_UNAVAILABLE` | 409，無法完整釘住要丟棄的內容 | 保留、由人另處理，再 preview |
| `RETAINED_REF_MISMATCH`／`RETAINED_CONTENT_MISSING`／`ARCHIVE_VERIFY_FAILED` | 409，保留 ref 版本不同、內容遺失或轉存未證實 | 停止移除；檢查 retained evidence |
| `WORKTREE_REMOVE_REFUSED`／`REF_CHANGED`／`CONTAINER_NOT_EMPTY` | 409，Git 非強制拒絕、CAS 不符、發現未列內容 | 保留成功回執；重新 preview |
| `STOP_UNPROVEN`／`EXTERNAL_EFFECT_UNPROVEN` | operation uncertain，含 stop／SSH 回覆遺失 | reconcile 同 step，不重送 |
| `RESTORE_UNAVAILABLE`／`RESTORE_TARGET_CHANGED` | 409，無實際 retained commit、未知目的地或新 worktree 被改 | 保留 tombstone；重新觀測 |
| `LEGACY_CLEANUP_DISABLED` | 409，舊 cleanup apply 不再寫入 | 用新 resource-cleanup preview／apply |
| `UNCERTAIN_UNRESOLVED`／`NOT_RESUMABLE` | 沿用 OperationService | 人查看證據；取消不能宣稱副作用沒發生 |

## Crash／lost reply 恢復

所有外部 mutations 用 `OpContext.step`。每項 tombstone draft、step request、保留／丟棄選擇
先 commit 再呼叫；不在 SQLite transaction 裡等待 SSH／BAT。未決步驟先 reconcile，再看 cancel，
不能因 operation cancelled／failed 忽略不確定的外部效果。

| 步驟／崩潰點 | 讀回與完成條件 | 允許再送的證據 |
|---|---|---|
| preview HTTP reply 遺失 | 再做純讀 preview；舊 token 無副作用 | 只有 read，無 operation 要回收 |
| apply accepted reply 遺失 | 同 actor／key 回原 operation；查 receipts | 不建新 operation |
| validate／reservation 落地後重啟 | 查 journal reservation、原 plan、task control_version／commands、remote lock／step；未開始時仍受 expiry | 純讀可重跑；有可能送出的 step 必須先對帳 |
| preserve ref ACK 遺失／寫後未記 response | exact ref=planned SHA 且 object 可讀即成功；different SHA 拒絕 | ref 缺失、同 identity、前次遠端程序已結束、CAS create 可安全重跑才回 `RERUN` |
| stop ACK 遺失 | 主機 identity／BAT 讀取健康、原 start 已證實完成、同 session／generation 的 runtime 終止正向證據與無 pending writer；單次 meta=null／沒有 tab 不算 | 尚未取得 grant／frame 未送出的持久證據才 RERUN；仍 idle loaded 不證明前次沒 stop 後被重啟，保持 uncertain |
| discard 中途／ACK 遺失 | 每個 manifest entry 核對 before／expected-after digest；已成 after 的檔案不重丟。index／merge state 也核對 | 全部狀態只在預定 before／after 之間、原程序已結束，且 scope／policy 再通過；第三種狀態 stale，不能覆蓋新內容 |
| worktree remove ACK 遺失 | source repo／retained ref identity 正確，exact worktree path 消失且 `worktree list` registration 消失，HEAD／object 仍在 → succeeded／settled_by=readback | 原 path／binding／dirty 全等 preview、原程序已結束，才能非強制重跑。path absent 但 registration 還在維持 uncertain／needs_attention，不 prune／rm repair |
| ref CAS delete ACK 遺失 | exact ref 缺失，且 retained alias=planned old SHA → 已移除；第三種 SHA → stale | 同 ref 仍等 old SHA、無 writer、原程序已結束，CAS 冪等重跑；不無條件 `update-ref -d` |
| archive／move ACK 遺失 | 讀 exact temp／store markers、manifest digest、全部 required objects 與 refs；store 驗證完成才標 preserved | 僅同 operation 的 create／copy／CAS；未知既存路徑不覆蓋。disk full／驗證失敗保留來源 |
| container 刪除中途／ACK 遺失 | store 完整；容器 absent 記成功。部分移除時按 committed manifest／每檔回執核對 remaining，root identity 不符則停止 | 只有未改變的 exact 剩餘 entries；不能把 rm 重試擴成刪除新檔案。parent 空目錄可留下，不影響成功 item |
| finalize commit 前後中斷 | steps 的正向 readback 可重建 receipt／tombstone；receipt、relations、retained、event 在一個 tx，唯一鍵防重複 | journal finalize 可重播；registry update 不刪 row，依 tombstone ID 同值對帳 |
| restore add ACK 遺失 | exact 新 worktree registration／branch／HEAD／tree 等 intent，補記成功；不同 binding／dirty 不接管 | branch／path 不存在且 remote 程序已結束才可 add；已有 branch 只在同 creation intent 下沿用 |
| cancel／部分成功／Resume | 成功 items 永遠保留；未送出的 cancelled。Uncertain 先讀回；取消沒有「還原已清理」副作用 | unchanged plan 的 confirmed-no-effect failure 可由人 Resume 新 attempt；stale 一律新 preview |

現有 `OpContext.step` 會重拋 failed step，不能宣稱 Resume 自動重試它。
Cleanup handler 在 explicit Resume、先證實前 attempt 沒有副作用且 preconditions 未變後，才建
新的 `.a2` step；成功 `.a1` 回應重播，未決 `.a1` 只 reconcile。Step request 固定 plan／manifest
digest、exact path／ref／SHA、generation、parent intent；每個 attempt 有 receipt，不改寫舊失敗。
Stop helper 必須把 InvokeTimeout／ConnectionLost 傳到 OpContext，取消或 rate limit 不得造成
第二次 stop frame。Remote PID 仍在執行時維持 uncertain，不能只因本機 SSH 子程序已退出就重送。

## Journal tables／migration

沿用 `task_journal.Journal` 的 SQLite、WAL、FULL synchronous、foreign keys 與單一 owner。
目前 `PRAGMA user_version=1`；新增 **v2 additive migration**，`BEGIN IMMEDIATE` 一個 transaction
建立下表／indexes、以已保存的可信資料 backfill alias 與舊 task retained event，最後才設 user_version=2。
不刪舊表／列／registry、不為 read preview 保存一列、不在 migration 呼叫 BAT／SSH／Git。
Migration 中途失敗 rollback，重啟重做；既有 events cursor 不重編、不重播舊 task event。

| 表 | 欄位與約束 | 用途 |
|---|---|---|
| `cleanup_resources` | resource_id PK，kind、host、generation、creation_intent_type／id／slot、repository_resource_id、canonical_binding JSON、ownership_evidence JSON、state、last_observation JSON、version、created_at／updated_at；UNIQUE(creation_intent_type,id,slot,host) | 資源的 ID／generation 投影，session 保留原 ID alias；不是第二個 tasks authority，也不因 row 存在授予 ownership |
| `cleanup_resource_aliases` | (kind,external_id,host,resource_id) PK；external_id 為原 session／run／task／path＋generation／ref binding；索引 external_id | 去重與原 ID 搜尋；不以 alias 更新歷史 consumer owner |
| `cleanup_consumers` | resource_id、consumer_kind／id、revision_key、requirement=history／content_required、reason、source_version、released_at；複合 PK | 原關係的投影與明確 retention／restore 需求；每次核對 authoritative commands／operations，不能只信快取 |
| `cleanup_runs` | operation_id PK FK operations，preview_id、token_hash、source_fingerprint、document JSON、validated_at、partial、supersedes_operation_id、required_scopes JSON、resumed_by／resumed_scopes JSON；document 驗證後不可改 | accepted 後固定匹配的 preview，保存計畫與 recover context；required_scopes 從已准入 action／choices 計算；preview ID 索引 |
| `cleanup_receipts` | (operation_id,resource_id) PK；item_order、plan JSON、status、before／after JSON、attempts JSON、retained_ids、error_code、settled_by、started／finished_at | 每個真正資源一列，包括 retained items。attempt 詳情連原 operation_steps，resume 不覆蓋 |
| `cleanup_retained` | retained_id PK、resource_id、revision_key、preserve_operation_id／step、kind、host、repository_resource_id、location／ref、commit／tree／digest、manifest JSON、state、last_verified_at、created_at；UNIQUE(preserve_operation_id,resource_id,revision_key) | 真正 preserved refs／stores；舊 task retained 只 backfill 為 unverified，live 驗證後可復原 |
| `resource_tombstones` | resource_id PK、original_ids JSON、kind、generation、host／profile／workspace／path／ref、creation_evidence、last_observation、reason／choices、relations、delivery_destinations、cleanup_operation_id、receipt keys、retained IDs、cleaned_at | 永久搜尋／詳情。mutation 前先保存同內容 draft 於 receipt；只有外部效果證實後 finalize tombstone |
| `cleanup_reservations` | resource_id PK、operation_id FK、task_id（可空）、control_version、plan_digest、created_at、phase | 與既有 task／session lock 配合，避免其他 connector writer 進入；uncertain 不依時間釋放，證實完成／取消無未決效果才釋放 |

`cleanup_retained` 應另有 index(host,resource_id,created_at,retained_id)，tombstones
index(host,kind,cleaned_at,resource_id) 與 aliases/ref 搜尋索引。JSON 長 manifest 限制大小與 redaction，
不可保存 API／admin token、credentials 或 raw message bodies 作 audit。Signed preview payload 不含
credentials，只作原操作的審核證據；Original context 只引用已保存的 checkpoint excerpt。
未實作 artifact rows 不造假 backfill。舊 task 已清除 path 只從 `external_worktree_retained` event
取原 path／branch／SHA；無 evidence 的外部檔案保持 unknown。

registry 保留 creation fields，在既有 flock 內附 `cleanup_operation_id`、`tombstone_resource_id`、
`cleaned_at`，status=cleaned；reservation／writer 判斷不得因舊 active registry 列誤判，須與
新 confirmed cleanup facts 對帳。也不得因新 cleaned 列跳過 live streaming session。
共用政策對已確認 tombstone 的 generation 拒絕 send／resume／stop／worktree mutation
（`RESOURCE_CLEANED`）；不能讓舊 session_send 的 client-resume 重啟已清理的 session。
同 ID 又出現 live runtime 是 binding conflict，列保留與需要對帳，不修改原 tombstone。
`sessions_observed` 的 body／最後觀測保留，另附 tombstone 查詢結果；gone 不是 delete。
Finalize 產生 `cleanup.item.retained`／`preserved`／`reclaimed`／`failed`／`restored`，
沿 `Journal.api_event` 的同一 cursor；只有實際狀態 transition 記事件，重播不重複。

### 永久查詢

Session 詳情、work item links、checkpoint runs 與 integration 來源讀取先找 active 投影，缺實體時
回同一原 ID 的 tombstone。`work_item.link` 的 session 存在檢查擴為 inventory 或 tombstone，
歷史連結不解除、不改成新 ID。Task external cleanup 只在 coordinator 確認 receipt 後清可寫指標，
原 task event／branch 歷史仍保留。移除 host 設定不抹掉 tombstone；只禁用 live／restore。

新增 cleanup 搜尋可依 query（原 ID／標題／舊 path／PR）、host、work_item_id、resource_id、kind
查詢 tombstones。回原 session 在哪個 host／workspace／path、何時／由誰／為何整理、source checkpoint、
全部 execution 關係、receipt 及結果 PR URL／SHA。原 session URL 永久可開，不因 inventory gone 回 404。
沒有已保存對話時顯示「未保存對話」，仍保留上述 context，不承諾全文 archive。

## Retention 設定

設定在既有 `config.py` 增加 `[cleanup]`（服務啟動時讀取，修改設定需重新 preview）：

```toml
[cleanup]
retained_refs = "keep"             # 唯一支援值；Git成果永久保留
history_retention = "forever"       # 唯一支援值；tombstones／relations／receipts不刪
permanent_delete = false            # 唯一支援值；true啟動時拒絕，不能假裝已有purge
```

不提供自動到期刪除／background housekeeping。Expiry 只使 preview 不可開始，不使內容可刪。
Container 退休由人或有 cleanup scope 的 agent 在這份 preview 明選，保留 refs 移到 managed store；
artifact／對話保留期限屬後續 adapter，第一版不為尚不存在的內容設倒數刪除。
永久刪除將來必須有獨立 spec／authorization／preview，不能悄悄改 keep 的含義。

## HTTP／MCP／CLI／Dashboard

### 薄 adapters

| Surface | 合約／權限 |
|---|---|
| HTTP `POST /api/v1/cleanup-previews` | body={target,choices}，200 純讀 preview；observe，discard choices 另查 scope。POST 是複雜查詢，不建立 operation／preview row |
| HTTP `POST /api/v1/operations` | cleanup.apply／cleanup.restore，沿用 Idempotency-Key、202／200 與查詢／cancel／resume；全部 mutations 只有此入口 |
| HTTP `GET /api/v1/cleanup-retained` | observe，scope_kind 加對應 work_item_id／checkpoint_id／operation_id，或 host／resource_id、query、limit=50（最大 200）、cursor；回真實 retained 與 unavailable records；keyset 為 (created_at,retained_id)，cursor 綁全部 filters |
| HTTP `GET /api/v1/cleanup-tombstones`、`/{resource_id}` | observe，query／host／work_item_id／kind、limit／cursor；keyset 以(cleaned_at,resource_id)；詳情查原 ID aliases |
| HTTP 原 sessions／work-items／checkpoints／integrations／operations 詳情 | 附 tombstone、cleanup receipts／retained 與原 relations；不重查已刪 worktree 來冒充 active |
| MCP `cleanup_preview(target,choices)` | 同純讀 handler；observe；用呼叫者 API principal 綁 token，不默認 admin 簽成 agent 可 apply |
| MCP `cleanup_apply(preview_token,preview_fingerprint,idempotency_key,confirm)` | confirm=true，BATC_API_TOKEN、cleanup／discard scopes；由 signed payload 取 preview ID，呼叫 operation_submit 同 action |
| MCP `cleanup_restore(mode="list",target?,limit?,cursor?)` | mode=list 純讀同 retained list；mode=managed_worktree 需 retained_id、expected_retained_digest、key、confirm=true，呼叫同 restore action |
| MCP `cleanup_tombstones(query?,host?,work_item_id?,limit?,cursor?)` | 搜尋永久 context；observe；operation_get／resume／cancel 沿用 |
| CLI `batc resource-cleanup preview` | 四 scope flags 擇一：--item／--checkpoint／--integration／--host；--include-children 只用 item；--retire-containers、--discard-uncommitted ID／--discard-undelivered ID 可重複；--json 輸出 token／fingerprint 與完整 plan |
| CLI `batc resource-cleanup apply --preview-token … --fingerprint … --key … --confirm` | 同 operation；可從 preview JSON 檔讀取 token／fingerprint（client 讀檔不授予遠端 path）；不重新選資源 |
| CLI `batc resource-cleanup restore list`／`restore worktree <retained_id> --digest … --key … --confirm` | 同 restore 讀取／operation，已完成顯示新 worktree／branch 與原 tombstone |
| CLI `batc resource-cleanup history --query …`；`batc op <id> --resume` | 原 ID 搜尋／同 operation 續做；stale 明示要新 preview |

MCP mutation wrappers 須列入既有 `OPERATION_TOOLS`，不依 write tier 退回舊 lifecycle 方法或 admin。
新 read wrappers 也需透過 daemon 同 Principal；有 API token 就不降級 admin。
Capabilities 增加 `features.cleanup`：contract version、read／apply／discard／restore、每 host 的能力與
原因、retention 設定、limits。舊 client 不支援就回明確原因，不猜 tool 或原始 RPC 旁路。
契約測試比對三入口的 target／choices／fingerprint／ActionDef／result schema。

### Legacy 決策

保留 `batc cleanup HOST [SESSION]`／MCP `session_cleanup` **名稱與只讀評估**，不作 alias。
它的 Jev merge／verify gates 與新「已接收、預覽釘住」語意不同，改 alias 會讓舊 script 悄悄獲得
host-wide 整理語意。舊 `--apply`／dry_run=false 統一拒絕 `LEGACY_CLEANUP_DISABLED`，
說明新 resource-cleanup 流程；connector-made 仍 KEEP，`NOT_A_BAT_WORKTREE` 不解除。
`fanout_from_plan` 的隱含 planner cleanup 改為只留下候選／歷史，不繞新 scope 自动刪。
舊 TaskDaemon terminal 外部 worktree 刪除／cleanup retry 也停用，改由 coordinator 核准的本 operation。
已在舊版送出的 cleanup 不能視為未發生：升級先讀既有 task retained event／ref 及 worktree 狀態，
未決 binding／指標保留並由原 owner 對帳，不啟動 cleanup 掃描補刪。

舊直接 `remove-worktree` 不接手 connector-made，也不能作新 cleanup 的 fallback；
只保留它既有 BAT 資源邊界。若原 BAT-made worktree 被新 cleanup reservation 鎖住，
該舊入口也要拒絕；新包不擴大其 delete_branch 能力。遠端 branch 永遠另有明確 GitHub action。

### Dashboard「整理與復原」

新增 `#/cleanup`、`#/cleanup/resource/<resource_id>`。沿用現有頁面／tokens／CSS hierarchy：
scope 選擇、候選表（真 resource、所在位置、狀態、所有引用、plan）、保留原因、影響摘要、
逐項 receipts、可復原內容與 history 搜尋。工作詳情增加「整理資源」entry point，預填 work_item_id，
include_children 由人選；封存／完成按鈕不順帶 cleanup。

主按鈕依完整 preview 啟用，顯示確切停止／移除／保留數；dirty／未送達 discard 在原 item 明選，
改選就重新 preview。沒有 cleanup_discard 時不提供可執行 discard 選項並說明 scope。
Apply 失敗／stale 顯示 changed 資源與已成功回執，保留使用者 choices 草稿但要求新 preview，
不沿用舊 token 自動重送。Response 遺失保留同 Idempotency-Key 並查原 operation。
Restore 顯示「重新建立 managed worktree」，列實際 commit 與新 branch，明示 runtime 不會原樣復活。

Session 已 cleaned 的詳情顯示 tombstone／PR 去向；搜尋含 gone 與 tombstone，不能只取預設 active
inventory 列表。History 連結永久可開。兩語言字串都寫 `i18n.js`，不在產品畫面曝露 SSH script 細節。
CSP 不放寬；可空 children 經 `fill()`，style 用 `el.style.setProperty`。SSE 只標記 preview 可能過期，
焦點／開啟的編輯欄保持既有 hold 規則，不在勾選 discard 或讀取 plan 時重畫掉草稿。

## 預計修改檔案（Phase 2）

| 檔案 | 修改目的 |
|---|---|
| 新 `src/bat_agent_connector/cleanup.py` | resource 發現／依賴／delivery coverage、純讀 preview、簽名 token、apply／restore actions、step reconcile／receipts；重用既有 Git runner 與 policy |
| `resource_policy.py`、`api_auth.py` | 全 mutation 表新增 cleanup ref／discard／container／restore 的 SSH path checks；共用 markers／canonical／destination 檢查；cleanup／cleanup_discard scopes；reservation 檢查 |
| `task_journal.py`、`operations.py` | additive v2 schema／indexes／backfill；沿用 OpContext.step，不另造 step engine；resume／cancel 的 scope 與 cleanup reservation 守門及 partial 讀取 |
| `task_core.py`、`task_bat.py`、`task_daemon.py` | coordinator eligibility／reservation／terminal task receipts；共享寫入鎖；停止自動 external cleanup，ActionDef 與 read RPC registration |
| `checkpoints.py`、`integration.py`、`orchestrate.py`、`service.py`、`lifecycle.py` | creation resource IDs／bindings 與 existing consumer 投影；creation／send／Git mutation 查 reservation、共用 remote locks；stop 保留 ambiguous outcome；legacy cleanup restrict；原歷史查 tombstone |
| `registry.py`、`inventory.py`、`work_items.py` | 保留原 rows／last observation；cleaned 指標／alias、全部共享歷史與 tombstone link 解引用；read preview 不寫快取 |
| `config.py`、`api_v1.py`、`mcp_server.py`、`cli.py` | retention 設定／validation、thin routes／tools／命令、capabilities／contract version；不增加 raw shell 入口 |
| `dashboard/app.js`、`app.css`、`i18n.js` | 整理與復原、工作詳情 entry point、tombstone 搜尋／receipts／新 worktree、en／zh-TW |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md` | 短段落與本文 link；Next release (unreleased)寫計畫§10／§19／§23 及 E01／E02；指出新 scopes、legacy 限制、無 runtime 復活 |
| `skills/bat-agent-connector/SKILL.md`、`skills/hermes/bat-agent-connector/SKILL.md` | 同步 preview→apply→查 operation／reconcile→restore；token／scope、receipt delivery、不得 discard 未授權成果，不走舊 cleanup |
| `docs/design/api-v1.md`、`checkpoints.md`、`integration.md`、`resource-policy.md`、`task-service.md`、`work-items.md`、`dashboard.md` | 補 routes／scopes／resource history；更新真正完成的「尚未涵蓋」項目及 task／legacy 語意，不把未實作內容標完成 |
| 新 `tests/test_cleanup.py`；既有 policy／API／MCP／config／task／checkpoint／integration／work item／lifecycle tests | 下面的 acceptance／failure plan；原 fixture 與 mock，禁止真 host write |

Phase 1 **只提交本文**，不更動上述 product／README／skills／其他 design 的完成狀態。
Phase 2 經審核才實作，不在本文件 commit 裡宣稱 E01／E02 已通過。

## 驗收與測試計畫

以下測試名稱是 Phase 2 要建立的證據，**不是已存在或已執行的 cleanup 測試**。
使用 `tests/mockbat.py`、`tests/fakegithub.py`、`tests/test_checkpoints.py` 的 LocalRunner／RealGitLog
與 temp Git repos；測試 source manual repo 的 refs、index bytes／mtime、status、config、HEAD 與所有
BAT write frames 都不變。禁用 Jev／provider network，無實機 write。

| 計畫§23 句意／驗收 | 預計測試（`tests/test_cleanup.py`，另註者除外） | 必須證明 |
|---|---|---|
| 首段：回收 runtime，脈絡留存；無 tab／離線／安靜／退出不足；E01 | `test_e01_runtime_work_delivery_retention_are_separate` | matrix 涵蓋 tab／headless、離線、gone、exit／idle；不能從一個訊號升級可刪 |
| 使用者動作表：收合／完成／封存／停止／整理／remote 刪除不同 | `test_e01_archive_and_completion_never_cleanup_or_delete_remote` | work item archive／approve 不送 stop／Git mutation；cleanup scripts 無 remote push／delete |
| 父項含子項、真資源、manual／unknown 保留；E01 | `test_e01_tree_preview_apply_matches_and_read_only_resources_survive` | 三層樹含 manual／unknown／streaming／waiting／finished managed，單項與含 children 都列真位置；plan 與 receipts 完全對應；manual／unknown 無寫入 |
| 多 execution 資源 ID 去重；其他使用者／command／retention；E02 | `test_e02_shared_worktree_is_one_item_and_checks_out_of_scope_consumers` | reviewer、successor、warm reuse、兩個 work items 與範圍外 execution 共用；只一 item，任何 content consumer 擋刪 |
| 純歷史不阻擋；共享 artifact；E02 | `test_e02_history_links_resolve_tombstones_and_artifact_refs_are_retained` | 未完成 work item 的 history link 不單獨阻擋；仍需內容的 requirement 會擋；opaque attachment 共享參照不當 path 刪；未來 materialization fixture 用同 consumer 守門 |
| 可信建立、canonical managed、writer／未決 start-stop；E01 | `test_e01_every_mutation_rechecks_policy_and_canonical_destination`、`test_e01_pending_start_stop_and_waiting_sessions_are_retained` | 各 step 前換 symlink／commondir／objects／config／BAT cwd；force、confirm、discard 無法繞過；未決／cancelled step 仍保留 |
| TaskCoordinator 先決定，不能獨立 housekeeping | `test_e01_task_owner_reservation_blocks_cleanup_and_warm_claim`；更新 task tests 的 terminal cleanup 情境 | coordinator control_version 競態、pending command、paused／verifying 都拒絕；worker 無自動刪除；terminal reviewed operation 才能 cleanup，保留舊 task 事件／refs |
| 尚未接收／保留需求；receipt 而非 ancestor；E02 | `test_e02_squash_and_pick_use_exact_delivery_receipt_coverage` | source 不是 squash／pick 目的 ancestor 仍可清；ancestor 但無 receipt 仍保留；pick 部分／新增 tip／verified-only 不算送達；push uncertain 即使 cancel 也保留 |
| 未整合保留或人 preview 明選 discard，不越 manual／writer | `test_e01_discard_is_pinned_scoped_and_never_overrides_read_only_or_writer` | cleanup 不足以 discard；apply 不能加 choices；dirty 含 staged／binary／untracked／ignored；manifest 變動 stale、partial discard 重啟不覆蓋新內容；HEAD 保留且不說 dirty 可復原 |
| E01：preview／execution 一致，stale 需重預覽 | `test_e01_preview_is_pure_and_signed_plan_cannot_be_changed`、`test_e01_stale_any_item_stops_before_mutation_and_reports_changes` | preview 無 journal／event／lockfile／refs／BAT writes；token 改寫／actor 換人／expiry／rotation 拒絕；保留 item／dependency／receipt 改變也 stale；heartbeat 不誤判 |
| 精確 inventory；crashed checkpoint 只在 operation | `test_e01_crashed_continue_and_handoff_intents_are_discovered_without_adoption` | 逐個 crash 點：refs 寫後、prepare 後、start 後、send 前後；無 run／receipt 也找到且 unresolved 保留；半建成 tmp／相同名稱 manual 不認領 |
| 逐項 intent、retained ref 後非 force 移除；E01 | `test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs` | real Git 事件次序；dirty／locked worktree 拒絕，不 force／prune／rm fallback；不刪未知或未送達 local refs；keep refs 無 gc |
| container／refs 整理、永久保留 | `test_e01_container_retirement_verifies_independent_retained_store_first` | default container 保留；opt-in 先存完整 manifest／objects 再刪；disk full／store 不完整／unknown refs／extra files／active preview 擋；source repo 不變 |
| operation 部分成功可續；E01／E02 | `test_e01_partial_cleanup_resumes_only_unfinished_unchanged_items` | 第一項成功第二項確定失敗，Resume 新 attempt、第一項不重做；scope 撤銷拒絕 discard；partial stale 只准新 preview；cancel 保留所有已完成 effects |
| 各步 lost reply／restart；E01 | `test_e01_lost_replies_reconcile_each_cleanup_and_restore_phase`（參數化上表全部階段） | intent 後／host 已執行但 response 未記／finalize 前後 crash；remote PID 仍在不重送；stop null 不足、removed registration 不全不 prune；cancel 不掩蓋 uncertain |
| tombstone 原 ID／最後觀測／關係／PR、Dashboard 搜尋；E01／E02 | `test_e01_original_ids_remain_searchable_with_location_reason_and_pr` | inventory gone／host 移除設定／registry 重播後 session 原 URL、link、checkpoint／integration 詳情與搜尋還在；PR delivery URLs／SHA 與所有關係不丟 |
| restore 只列真保留；refs／archive、runtime 不能原樣復活 | `test_e01_restore_lists_verified_retention_and_creates_new_managed_worktree` | ref／objects 缺失／host 離線不宣稱 available；restore exact SHA 新 ID／branch、原 tombstone 不變；無 start/send/tab writes；lost add 回同 resource |
| retention 設定明確，無掃磁碟／按名稱 prune | `test_e01_keep_defaults_reject_purge_and_never_sweep_by_name` | config 只 keep／forever／false；無時間刪除、unknown folder 不碰、過大 preview 不截斷 apply |
| §10 三入口、scope，§19 畫面；E01 | API／MCP／CLI 增加 `test_e01_cleanup_adapters_share_the_action_contract`；Dashboard fixture smoke | 同 token／fingerprint／key 回同 operation 與 receipts，discard 無 admin fallback；legacy apply disabled；新畫面／work item entry、en／zh-TW 與 390 px、草稿／hold／stale／partial／restore／搜尋都可用 |

回歸保留既有 `test_mutation_table_classifies_every_bat_write_channel`、
`test_bat_worktree_actions_never_touch_a_worktree_the_connector_made`、
`test_c03_a_cancelled_apply_with_an_unproven_push_reports_unknown`、
`test_c03_a_resolution_that_is_not_a_merge_of_both_sides_is_refused` 的安全含義。
舊 lifecycle／terminal task 的「自動 apply」測試須依新的 restrict 語意改寫，不能直接 skip 成綠燈。
Migration 另加 `test_cleanup_v2_migration_is_atomic_additive_and_preserves_history` 與
`test_cleanup_v2_backfill_never_claims_unknown_or_mutates_hosts`，含 fresh DB、v1 DB、重跑、transaction
中斷、同 path 不同 generation、warm／shared alias 及舊 task retained event。

Phase 1 與 Phase 2 報告都跑 `uv run ruff check .`、`uv run pytest -q` 並報實際 summary；Phase 1 的
baseline 成功只證明未破壞現有程式。Phase 2 再將 `app.js` 複製成 `.mjs` 做 `node --check`，
Playwright 檢查兩語言與 390px、無 `null`／`undefined`／`[object` 文字、CSP 及永久搜尋流程。
E01／E02 只有上述新 behaviour 與故障注入證據通過後才宣稱完成。

## 尚未涵蓋

- **待審核的產品決策**：新增 cleanup 與 cleanup_discard 兩個 scope、legacy cleanup 只讀、停止舊 task
  terminal 自動刪除、default 留 container／opt-in 轉存退休。本文提出明確合約；Phase 2 前需確認這些
  相容性變更，沒有把既有 agent token 自動升權。
- **大型 host 範圍**：第一版整份 preview 上限 500 resources。若實際 host 超過，需要審核 immutable
  paged preview／整份 fingerprint 的合約，或接受先用較小 work item／checkpoint／integration scope。
- **Artifact／完整對話 archive**：W05b 尚未有 revision／materialization 帳本，先列 opaque 參照保留。
  本包不實作 upload、materialize、全文 archive 或其永久刪除；只有已保存 excerpt 可讀。
- **Task Git 成果接收與外部 squash evidence**：Task integration sources 與可信外部 receipt 匯入尚未有
  adapter，文字 stage／PR link 不足。缺回執就保留；要擴充需由 delivery owner 提供 exact revision mapping，
  不能在 cleanup 發明 acceptance／attestation 旁路。E02 用可信 receipt fixture 驗證判斷，不代表已能
  匯入任意外部 squash 結果。
- **實機接入**：各 host 的 BAT stop／terminal 證據、managed roots、flock、filesystem no-follow 能力及
  排除外部 writer 條件需在部署前驗證；本包測試不向真 host 寫入。仍需確認哪些舊 clone 有足夠 creation
  evidence 可升級；不能證實的保留 unknown，由原 owner 對帳。
- **永久刪除、保留期限、自動 GC、跨 host restore、遠端 branch 刪除**：全部另立 spec／action；本包無
  disk-wide sweep、資料夾名 prune 或新 background housekeeping loop，不承諾 runtime 原樣復活。
