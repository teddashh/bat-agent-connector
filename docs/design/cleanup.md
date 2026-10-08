# 整理與復原：回收 managed 資源，保留工作脈絡

日期：2026-10-08。狀態：Phase 2a Part A 實作與驗證。Part B 在 operations-unification
Part A 合併後另開分支。對應計畫 §23 全節、§10、§19、§26 E01／E02、W06 cleanup。
本輪 retirement follow-up 依 Tauri 校正計畫 v2.0（2026-10-08）§19／§22 R08／§24 E01／E02，
保留原中央後端與 reviewed cleanup；不含 Hub importer／dependency，也不新增 Tauri 業務後端。
沿用 [OperationService](api-v1.md)、[resource policy](resource-policy.md) 與 [work items](work-items.md)。

整理只回收已符合條件的 runtime、worktree 與暫存。工作項目、checkpoint、回執、原始 ID 與
歷史永久保留。收合、完成、封存、停止執行、整理、刪除遠端 branch 是不同動作。

## 固定來源版本

| 來源 | 固定版本 |
|---|---|
| Connector | 程式基準 `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`；首版規格 `71640f9`；分支 `feat/cleanup`；套件 0.2.4 |
| 計畫 | v1.0，2026-10-06；只引用節號，不複製私人計畫 |
| 本輪校正 | v2.0，2026-10-08；retirement 基底 cad864f，舊 §23 對應新版 §19；Task Service gate 與 retained-content restore 的後續分工依新版 §19／R08 |
| BAT | `b7419892fbc9946799b64cca24c2ec8c7fa15c42`，`bat-remote/v2`；不推定實機版本相同 |

BAT [ClaudeRuntimeRouter::stop_session／claude_stop_session](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/claude.rs)
停止 Claude sidecar 或 Codex runtime；不刪工作歷史。Connector 用 `lifecycle._stop` 的
`claude:stop-session`。BAT [remove_worktree_native／force_remove_worktree](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/crates/bat-git/src/worktree.rs)
含 force、rm fallback、prune、可選 `branch -D`；新整理不用這條路徑，也不加新 BAT channel。

## 現有與新增行為差異

| 現況 | Part A |
|---|---|
| `checkpoints._run_continue` 先寫 external refs，最後才寫 checkpoint_runs | 合併 run、operation、step intent；崩潰的 start 不漏列、不猜未啟動 |
| checkpoint clone／worktree／branch、integration bare area／repair／pins 無 reviewed cleanup | 新純讀 preview、signed token、cleanup.apply；clone／area／全部 refs/batc/* 留存 |
| `integration.receipts()` 的 effective_status 含送達與 unknown | 依 exact revision coverage 判斷，不能看 ancestor／PR link／done／verified |
| registry 沒有 delete；inventory gone 仍保留 | 不刪 registry；確認 cleanup 後標 cleaned，保存 tombstone、aliases、receipt |
| `lifecycle.session_cleanup` 在 auto_cleanup 下 merge／remove／stop | 只讀評估；apply 回 LEGACY_CLEANUP_DISABLED。auto_cleanup 繼續解析但 deprecated |
| `fanout_from_plan` 對 planner 呼叫上述 cleanup | caller confirm=true 且全部 planned tasks 啟動成功才 stop；ACK ok=true 與健康 meta read-back 不 loaded 才確認 stopped；matching active row 才釋放 cap，bookkeeping refusal 不否認 stop；worktree 一律保留 |
| `TaskDaemon._tick_task` finally 清 terminal external worktree，留下 refs/batc/tasks/* | **保持原行為**。它是 task owner；本輪所有 task-owned 資源列 TASK_OWNED，不問 coordinator、不獨立回收 |
| 詳情資料可能引用已移除資源 | 自有 tombstone routes 永久查詢；其他詳情最多一個 lookup 附加 cleanup context，不接管 observation 的 sessions/history |

## 分期與修改邊界

Part A：四種 preview scope、全部資源列舉／保留原因、signed token、非 task managed session stop、
checkpoint／repair／有證據的 BAT-made managed worktree 整理、已送達 local branches CAS 刪除、
exact temporaries、discard_uncommitted、release_undelivered、receipts／tombstones／aliases／retained list、
migration、HTTP／MCP／CLI／Dashboard、legacy 與共享 guard、文件／兩份 skills／測試。

Part B：TaskCoordinator eligibility／reservation、reviewed task leftovers、TaskDaemon 清理透過共用 finalize
寫 tombstone／retained，以及過去 external_worktree_retained 事件 backfill；cleanup.restore 與其 mutation
MCP／CLI／Dashboard。Part A 不改 `task_core.py`、`task_daemon.py`、`task_bat.py`、OperationService 的
create／_may_steer／resume／cancel 或 operations table。Actions 可在 ApiV1 初始化時註冊到原 ops；
read adapters 使用同 daemon 的 HTTP，不為新工具修改 task RPC dispatcher。

## Scope、識別與發現

| target.kind | 必要輸入 | 展開 |
|---|---|---|
| work_item | work_item_id，include_children=false | parent_id 子樹（可含封存），有效／已移除歷史 links；derived_from 不自動展開 |
| checkpoint | checkpoint_id | 原來源、所有 runs／continue operations／external refs／steps、共用 clone、相關 receipts |
| integration | operation_id（preview／apply／handoff） | preview、source、receipts、repair、session、pins、area；崩潰 preview 的 prepare request 也有 area |
| host | configured host，或有 creation／observation history 的原 host | inventory（含 gone）、registry、已知 checkpoint／integration／task intent；不掃 managed roots 或磁碟 |

Integration apply 先由 `params.preview_id` 找原 preview；handoff 先由 `target.operation_id` 找 apply，
再沿同一條鏈找 preview。把 preview ID 與 preview operation ID 都加入 refs，再展開所有 source IDs。
三種 operation target 取得同一批 source／area／pins／repair／session；work-item links 的 integration
operation 也用同一規則。只使用本次 snapshot 已載入的 operation rows，不逐 item 另查 journal。

Work-item、checkpoint、integration 及 host target 可包含已從 config 移除的 host。所有 identity 都先由
creation facts 投影：checkpoint runs／continue intents、task external worktrees、repair handoff、registry
sessions／BAT-made carriers，以及各自的 local branch／clone／area。Host 是否 configured 不影響 ID，
branch ID 不等待 live HEAD 才存在；sessions_observed／links／tombstones 也不消失。
snapshot（含 only=item）只觀測目前 configured hosts，其他選中資源仍列出，observation 標
host_configured=false，read-only／retain，沿用 OBSERVATION_UNAVAILABLE，不以 missing host 當 absent。
依賴這些內容的 item 同樣保留；apply 不送 retained item 的任何 host call。同 preview 的 configured-host
items 正常規劃。Host target 只有 config 與既有 resource history 都找不到時才回 UNKNOWN_HOST。
歷史 host 判定同樣使用 _all 的 creation projection；integration.preview 的 prepare 已持久化但尚未寫出
integration_previews 時，仍由該 intent 找回 area／temporary，不要求另一個成功 operation 或 registry row。
Audit：_all 的 wt／registry loop 不再用 host 設定篩 identity；registry BAT ownership 的 HostConfig 查詢
只決定目前能否證明 managed roots，不能隱藏 worktree／branch／carrier。Host 移除時不猜原 roots 或 live
binding，仍列 OBSERVATION_UNAVAILABLE；selection 沒有 configured-host filter。
Audit：_terminal_observations／_runtime 在 inventory Fleet.client 前查目前設定；_host_call 在 runner lookup 前
拒絕 unconfigured host；_phase_consumers／_execute_item／stop callback／retained read 使用同一 _host_config。
Snapshot roots 用該輪 HostConfig，後續 adapter 仍再查 host 是否存在，config 移除不拋 ConfigError。
guard／mark／release 只讀寫 flock 下 registry，不開 Fleet client；host 移除不解除 reservation／tombstone。

範圍外的 active execution／command／有效 integration preview／resumable apply 也檢查依賴。
History link 不是實體需求；未完成工作若有 command／operation 真正需要內容，列 content-required
consumer。所有 consumer 從 authoritative tasks、commands、operations、previews 算出，不另存 consumers 表。
Session 的 task ownership 使用共用 `task_control.owner_task`：registry task tag、current lead／reviewer、
歷史 start command／branch 都沿用 Task Service 的來源。缺 registry tag 不會把 task carrier 變成
standalone；preview、host flock 內的 phase gate 與 capacity retirement 都重查，仍以 TASK_OWNED 保留。
Task external worktree 的 creation facts 只用來列舉該 task 自己的 carrier，不另推定 session owner。
不透明附件參照永遠保留，不能當作 remote path。

原 session ID（host/session_id）、task／command／work item／checkpoint／operation ID 不改。
Worktree 使用共用 `resource_ids.worktree_id`：canonical JSON `["worktree",host,intent_type,intent_id,slot]`
的 SHA-256 前 32 hex 加 `wt_`。Checkpoint 為 checkpoint.continue／operation_id／worktree；repair 為
integration.handoff／operation_id／repair；task external 為 task／task_id／external_worktree；BAT-made
為 registry／session_id@created_at（原 registry 值）／worktree。Warm reuse、reviewer、failover、後續 reuse
追第一個 creation slot，沿用 ID。Observation 與 cleanup 共用
`registry_worktree_intent`／`registry_worktree_root`；registry 列的順序不影響 creation slot，
connector-made 與舊 `batc/` branch 不能被誤列為 BAT-made。Session 詳情的中央 read model
一併帶出 cleanup tombstones；原 host 移除且 inventory row 不存在時，HTTP／MCP／CLI 仍可查詢。
其他 projection ID 為 `cr_<32 hex>`：host、kind、creation intent、slot 的 canonical hash。
同 canonical path／common dir 且 creation 相同才去重；證據矛盾列 BINDING_MISMATCH。
重建同路徑是新 generation；原 tombstone 不改回 active。Retained ID 為 `ret_<32 hex>`。

### 資源 inventory

每種 mutation 都先通過共用 policy；path／名稱／registry row／location_class 單獨不能授予 ownership。

| kind | 發現與 ownership 證明 | 移除 | 實際保留 |
|---|---|---|---|
| session | registry reservation／task recovery、runs／start step、BAT host/profile/workspace/meta cwd，resource_policy.classify／authorize_session | 無 writer／pending、非 task、managed root 內時經原 stop；不刪 tab／transcript | 原 ID、最後觀測、固定 excerpt、relations、stop receipt、PR 去向 |
| checkpoint worktree | checkpoint_runs／continue external refs／prepare request，check_checkpoint_worktree、clone markers、canonical common dir、HEAD／branch | 先 pin HEAD，再非 force git worktree remove | 起點／HEAD、原 branch／path、source checkpoint、retained ref |
| integration repair worktree | handoff external refs／repair.prepare、resolver receipt，check_repair_worktree、Area identity | unresolved apply／resolver 保留；釋放後同上 | resolution commit、source pins、parents、receipts |
| BAT-made connector worktree | 原 registry creation／worktree create 回執直接投影 origin_root 載體，不需 checkpoint／integration／task；BAT binding、common dir／managed clone | 有充分建立證據才經 SSH 非 force remove；不用 rehydrate／BAT remove | 原 branch／HEAD、來源 session、retained ref |
| task-owned session／worktree／branch | task IDs、branches／commands、registry、external_worktree_path、共享 owner | Part A **永遠 TASK_OWNED**；Task Service 原 terminal cleanup 不變 | 原 task facts；Part B 才投影 TaskDaemon tombstones／refs |
| local_branch | 原 prepare intent＋exact refs/heads/batc/cp-* 或 batc/fix-*，或 BAT creation registry 的 exact bat/*；repo／branch／old SHA | 已送達、無 checkout／consumer、retained ref 可讀時 update-ref -d exact-ref expected-old-SHA CAS；無 branch -D | retained HEAD；release_undelivered 的原 branch 保留 |
| git_pin | 已知 clone/area 的 exact refs/batc/source/*、pv/*、ops/*、tasks/*、retained/*；intent／receipt／SHA | **本包全部保留**，不刪 pins、不 gc | 原 refs 與 evidence；未知 pin 不認領 |
| clone／integration_area | prepare intent／runs／preview area／Area identity，batc markers／canonical path／config integrity | **本包不退休** | RETAINED_CONTENT_STORE，作 retained refs 的載體 |
| exact temporary | 原 prepare／check intent 的 exact temp path＋batc marker／Git binding；半建成無 marker 是 unknown | 無 writer／未決 step、無其他內容需求時 no-follow exact deletion；Git worktree 仍用非 force remove | 有 commit 先 pin；空 temp 只保留 observation／receipt，不能宣稱可 restore |
| retained_ref | preserve intent＋實際 ref／cat-file | 永不刪 | exact commit/tree；Part A 只讀列表，Part B 可新建 worktree |
| manual／unknown／remote／opaque artifact | inventory／links／human_checkout／remote receipt、已知 repo 中的未知 registration | 永不碰；remote branch 另有 GitHub action | 原 ID、位置、全部保留原因；artifact adapter 未完成不假裝可刪 |

Temporary adapter 明列兩種可移除資源：continue prepare 的 exact clone init temp，以及 integration
prepare 的 exact bare init temp。兩者需原intent、相符markers、完整Git-only manifest；所有ref commits
在載體可讀時先一併pin。空bare temp不產生retained row，不宣稱可restore。載體未完成／內容不在載體就保留。
`.batc-lock`、check intent的`repo.git/batc-check-<op>`與push intent的`batc-push-<op>`也按exact intent列出；
舊writer未留下resource marker，不補認ownership、不unlink鎖，列UNKNOWN_READ_ONLY；未決writer另列COMMAND_UNRESOLVED。

Checkpoint clone 檢查 batc.managed-clone／batc.source 與 creation intent，不能接管 managed root 中預先存在的 repo。
Standalone BAT worktree 由 registry 的 created_at／branch／origin_root／worktree_path 建立記錄投影 clone，
status 必須為 active／starting／uncertain／superseded／removed／cleaned／stopped／absent_at_cleanup，且非 failover_of、非 worktree_made_by=connector。
Starting／uncertain 的建立事實仍投影 carrier，但未結清 start 永遠不准回收。
只有 origin_root 在 managed roots、worktree_path 符合該 origin 的 in_bat_worktrees layout，才有 ownership 證據。
相同 SSH read／flock 內重核 batc.managed-clone、canonical common dir／config integrity、Git registration 與 recorded branch；
carrier common dir 或 branch 不符列 BINDING_MISMATCH，不能只憑目錄形狀移除。Origin 在 managed roots 外仍列出
worktree，但不認領，保留 WORKDIR_NOT_MANAGED；clone 一律留作 RETAINED_CONTENT_STORE。
Integration 沿用 Area.prelude 的 host/repository/URL markers、config allowlist、no links／alternates／replace／grafts。
目的地、Git dir／commondir／objects／refs 都要在 managed roots。SSH adapter 可用 host Python 3 的
no-follow 檔案檢查／刪除（能力不足即保留），不能提供 raw shell API。Git 關閉 optional locks、hooks、
fsmonitor、auto maintenance；危險 config／nested repo／symlink 越界均拒絕。不能 fallback prune／rm worktree。

## 保留模型

work_state、runtime_state、delivery_state、resource_state 分開。沒有 tab、gone、離線、安靜多久、
退出、done／approve／archive 不是刪除依據。Reasons[] 全部列出 code、說明、resource／consumer／
command／receipt ID 與 evidence；不能只回第一個。Choices 只排除表中明列的原因。

| code | 原因 | 能否選擇釋放 |
|---|---|---|
| MANUAL_READ_ONLY／UNKNOWN_READ_ONLY | 人工／無可信 creation evidence | 永遠不能 |
| WORKDIR_NOT_MANAGED | legacy shared clone／人工主 checkout | 不能；shared_clone_worktrees 不豁免 cleanup |
| BINDING_MISMATCH／CLONE_NOT_OURS／CLONE_CONFIG_TAMPERED | host／cwd／common dir／generation／markers／config／links 不符 | 不能 |
| OBSERVATION_UNAVAILABLE | host 已不在 config，或 BAT／SSH 讀不到、超時、無可靠 dirty／runtime 資料 | 不能；讀取失敗／host 移除不是 clean／absent |
| ACTIVE_WRITER／SESSION_WAITING | streaming／writer、pending question／permission、queued turn | 不能；先用原控制路徑處理，再 preview |
| COMMAND_UNRESOLVED | start／stop／send／prepare／push 未完成或 uncertain，即使 parent cancelled／failed；registry starting／uncertain 即使 meta=null 也不是已結束 | 不能；session 與 carrier 都保留，先由原 owner reconcile |
| ACTIVE_EXECUTION／CONTENT_REQUIRED | 範圍內外 task／operation／有效 integration preview／resumable apply 真正需要內容 | 不能；paused 不是完成，history link 不算需求 |
| TASK_OWNED | Part A 交由 Task Service 整理，未詢問 coordinator | 不能；Part B 才加入 coordinator 准入 |
| UNCOMMITTED_CHANGES | tracked／staged／untracked／ignored 內容或 merge state | owned、無其他阻擋時可選 discard_uncommitted，另需 cleanup_discard |
| RESULTS_NOT_DELIVERED | exact receipts 未涵蓋全部結果／新 commit／部分 pick／只有 verification | 可選 release_undelivered，需 cleanup；HEAD／branch **全部保留**，顯示未送達 |
| DELIVERY_UNCERTAIN | effective_status=unknown、任何未證實 push | 不能；release 不能豁免未決 command |
| RETENTION_RULE | 已有明確內容保留需求 | 不能 |
| SHARED_CONTAINER／RETAINED_CONTENT_STORE | 共用 clone／area 或所有 refs/batc/* | 本包保留，不退休載體 |
| REMOTE_OUT_OF_SCOPE／RESOURCE_KIND_UNSUPPORTED | remote branch、未實作 artifact／複雜 Git state | 不能 |

discard_uncommitted 是唯一摧毀內容的 choice；overridden_reasons 顯示 manifest、actor、不可復原部分。
release_undelivered 不是 discard，只有保留 commit／branch 後釋放 runtime／worktree；正常 agent 可用 cleanup
scope 做明確 per-item release。兩者不能越過 manual／unknown／writer／command／task／其他 content consumer。

每個 host 的全部 workspace terminals（含已註冊 terminals）都讀 live metadata.cwd；registry cwd／
worktree_path 只能提供歷史 binding，不能取代 live read。Live cwd 等於 worktree path 或在其下
（path components／commonpath 比較，不用字串 prefix）即為 consumer，無論 recorded cwd 在哪。
讀取失敗、超時、meta 缺失或沒有 absolute cwd 都是 unknown consumer，回 OBSERVATION_UNAVAILABLE；
同 host 的選中 worktrees／sessions 保留，不把 unknown 當 unused。範圍外 live consumer 回 ACTIVE_EXECUTION，
相連的選中 idle session 也保留，不能先 stop 再發現 worktree 被其他 session 使用。

Checkpoint worktree 的 common info/exclude 排除 `.batc-inputs/`，但忽略目錄不等於內容已驗證。
Connector 每個 worktree 傳 `replica_manifest=[{path,bytes,digest}]`（digest 為 SHA-256）與
`bookkeeping_names`：exact `.batc-inputs/.owner`、`.batc-inputs/.attempts/<art>-r<rev>/.attempt-N`／
`.closed-N`。Host 只豁免未 tracked、regular、single-link 且 path／size／SHA-256 完全匹配的 replica，
以及明列且 regular／single-link 的 helper names；必需的父目錄只是載體。所有豁免事實也納入 fingerprint。
已編輯／新增／缺少的 replica、symlink／hardlink、其他內容或非預期目錄，都列入 preview manifest，
按 UNCOMMITTED_CHANGES 保留；要丟棄必須明選 discard_uncommitted 且有 cleanup_discard。
Discard 用 no-follow exact names unlink／empty-directory rmdir；缺少或本步明選移除的 replica 名稱，
只在成功 discard receipt 後（或 exact after-state reconcile）確認接受其缺失，不豁免其他新缺失。
Artifacts package 後續從 artifact_materializations 提供 materialization evidence，接入
`cleanup._replica_evidence` 的純讀投影；本包預設 manifest／helper names 都為空，任何 `.batc-inputs/`
內容都是一般內容。非 force worktree remove 同時移除已驗證 replicas；artifact store 保留 originals，
只有實際豁免 replica 時 tombstone 才註記去向。Tracked 或非 checkpoint 同名內容仍按一般規則判斷。

### Receipt coverage（E02）

只有 effective_status=delivered 且 exact source revision／commit 集合被 receipt 覆蓋才算接收。
核對 source_kind/id/host/location_class、pinned_sha、mode、commits／picked／resolution_sha、delivered_sha 與 PR。
Pick 部分 commits 不覆蓋其餘結果；送達後分支前進不覆蓋新 HEAD。Squash 可依可信 exact mapping 清理，
source 不必是 destination ancestor；反過來 ancestor 沒有 receipt 也不能清。
Already_included、PR link／merged、work item approve／done、tasks.delivered、Journal.delivery 的 verified
都不是 Git 接收證據。外部 squash receipt 匯入與 task integration adapter 不在本包；缺證據保留或明選 release。
原 prepare 沒產生結果，須 exact HEAD=creation 起點、乾淨、無未決命令才可記 no_result。

## 權限、共用 guard 與並發

新增 scopes：cleanup（整理／release／Part B restore），cleanup_discard（**只** discard_uncommitted）。
Start／manage／operate 不隱含 cleanup。一般 Hermes／Grokbot tokens 不給 cleanup_discard，skills 不要求它。
Preview／history／retained 需 observe；帶 discard choice 的 preview 與 apply 需 cleanup_discard。
Apply 需 cleanup；release 只需 cleanup＋明選 choice。Actor 從 Principal，不接受 body 自報。

不改 OperationService._may_steer／resume／cancel。Accepted plan 保存 actor、當時 scopes、discard／release
choices；Resume 不重新授權。從 operation.running 的 api_events 記錄 resumed_by 作 receipt audit，不作 gate。
Cancel 阻止未送出的 mutations；已送出的 uncertain steps 必須先 reconcile。Authorization 由 action admission
固定於 server-only accepted metadata，再保存 cleanup_runs；不改 operations table。
Admission 必須在 OperationService hash 公開 request 之後、persist params 之前寫入 `_accepted_authorization`
（actor／scopes／choices）。Client 傳入這個欄位回 422 INVALID_PARAMS；同 key／同公開 request retry 必須
回同 operation，不讓 server metadata 改變 request hash。測試固定此界面，operations-unification rebase 時保留。

共享 `cleanup.guard()` 從原 registry JSON 的 cleanup_guards 讀 reservations／confirmed tombstones。
Guard marker 在 registry._locked 同一 flock 下寫，原 registry._write 保留這些額外欄位；另在 session row
附 cleanup_reservation／cleaned／tombstone_resource_id。每個 CLI／stdio MCP process 都讀同 state_dir 的
registry，**不開 daemon Journal**。JSON atomic replace，guard 只讀不建立檔案；讀不到／格式毀損時 mutation
fail closed。Mutation 前持久保存 operation/item intent，再寫 guard marker，再送外部 call。
Session marker 只鎖該 session ID；local branch marker 只鎖該 repository 的 exact branch，不能把載體當 cleaned。
同 cleanup operation 的 ContextVar 只讓本 handler 通過自己的 reservation；第三方不能 body 自報 operation ID。
未決 guard 不按時間解鎖；restart 先 reconcile。Confirmed cleaned generation 回 RESOURCE_CLEANED，
reservation 回 CLEANUP_IN_PROGRESS；舊 send/client-resume／merge/remove 也會拒絕。

與 confinement 的 start claim 共用上述 registry flock。Cleanup 寫 reservation 前，對該 session
（worktree 則含同 path 的已登記 sessions）用新的 descriptor 嘗試既有 `start-claims/<sha256>.lock`；
活躍 start 先取得 claim 時，cleanup 回 START_IN_PROGRESS，registry 不變。Cleanup 先寫 guard 時，
reserve／claim_unsent／ensure_existing 在同 flock 下先回 CLEANUP_IN_PROGRESS（已 cleaned 則
RESOURCE_CLEANED），不能取得 claim 或改 session row。Probe 只 close 自己的 descriptor，不 unlink
lock inode；不靠 token 或 timeout 猜 owner 是否消失。所有 cleanup registry 讀寫與 retirement
都核對 `(host, session_id)` 唯一性，重複 row 回 REGISTRY_DUPLICATE_SESSION 且不寫檔；release
同時匹配 host 與 session ID，不解除另一個 host 的 reservation。

`resource_policy.authorize_session` 及 check_checkpoint_worktree／check_repair_worktree／check_integration_area／
check_external_worktree 各加一個 shared guard hook。service.py／orchestrate.py 不新增 caller checks。
實際 ownership 仍由共用 policy；guard 只禁止使用 reserved／cleaned 資源，不授予 ownership。
同 host repo 的 cleanup mutation 互斥；Git script 鎖內即時核對 canonical paths／refs／dirty／bindings。
Apply 每個 stop／Git phase 都先由 SSH helper 取得 managed repository 的 directory flock；standalone
managed session 使用其 canonical workdir。Helper 在鎖內發 locked notification，Connector 才在共享
per-host read lock／deadline 下重讀全部 terminals 的 live cwd／session state／consumers。只有全部檢查
通過才用 stdin 明確許可 Git phase；stop 在 callback 中經既有 BAT stop path 執行，完成才釋放 host flock。
拒絕／斷線／EOF／deadline 不許可後續 mutation，不寫新 lockfile。Lost reply 沿用既有 uncertain／reconcile
規則，不能因 handshake 遺失重 stop。自己的已接受 idle stop items 可先後停止，worktree 仍依賴全數 stop 成功。
拒絕／timeout 的 transport 明確關閉 stdin；Python 3.10 的 communicate(input=None) 不會自行關閉，
不能讓 host helper 留到 deadline 才 abort。
Connector locks 不能保證同帳號外部 writer；觀測不足即保留，非 force remove 最後拒絕 dirty race。

### Session retirement／cap 稽核

Cap 只計 registry 的 active／starting。新增 stopped 與 absent_at_cleanup，表示 runtime 使用權已退休，
不是 worktree removed／cleaned；created_at、原 ID、origin_root、path、branch、creation evidence 全部不改。
registry.retire 在原 flock 下只改同一 created_at、沒有 task_id 的 **active** row，記 retired_at／
retirement={actor,reason,operation_id,carrier_resource_id}；planner 另記 stopped_at／stopped_by。
Starting 仍計 cap，但 start 未結清，不能以 absence 退休。所有其他 status／missing row／generation mismatch
都不寫 registry。同 retirement 的 retired row 可重播，回原 capacity fact，不改 timestamp／retirement。

Capacity 是本機 bookkeeping，不是 cleanup effect。Session after_state 記 capacity_released、registry_status、
capacity_reason；success／同值 replay 的 reason=null。Registry refusal／OSError 被 session caller 捕捉並記
capacity_error={code}，registry_status=null 表示未知。它們不拋出 run，不影響 worktree succeeded receipt、
tombstone／cleaned guard，不轉 uncertain／CLEANUP_PARTIAL_STATE。Registry read 不以 I/O failure 猜 missing row。
已移除 resource 的 ownership／consumer／後續 host phases 仍按原 preconditions，不能因 bookkeeping 放寬。

| capacity_reason | capacity_released=false 的原因 |
|---|---|
| not_counted | superseded／removed／cleaned／failed／uncertain／unknown／不同 retirement 的 retired row；原 row 完全不改 |
| generation_changed | created_at 不符或 row 已不存在；不改新 generation |
| task_owned | row 有 task_id，交給 Task Service |
| start_unsettled | row=starting，start claim 可能仍在執行，保留 cap |
| carrier_retained | absent session 的 carrier 未在此 run 成功回收或證實 absent；保留原 slot |
| registry_refused | registry helper 拒絕／資料格式無法讀取，capacity_error 記原 code |
| registry_io_failed | registry I/O 不可用，capacity_error.code=REGISTRY_IO_FAILED；可能已 atomic replace，resume 讀回同 retirement 才確認 |

| Connector 不再 live 的途徑 | 最終 registry status／是否算 cap |
|---|---|
| fanout planner confirmed stop | active 可改 stopped／否；只在全部 starts 成功、caller confirm、stop ACK ok=true 且健康 meta read-back=null 才改。Capacity refusal 不否定已確認 stop：stopped=true、capacity_released=false、capacity_reason／capacity_error。Stop ACK／read-back 未確認才 stopped=false，row 不改 |
| reviewed cleanup session succeeded | cleaned／否，原 finalize／tombstone 規則不變 |
| reviewed cleanup already_absent session，carrier 本次 succeeded／already_absent | matching active row 改 absent_at_cleanup／否，retirement 記 operation_id 與 carrier ID；其他 row 留原 status，after 記 false／reason。不送 stop、不建 session tombstone／aliases、不標 cleaned |
| reviewed cleanup already_absent session，無自己的 worktree | matching active row 改 absent_at_cleanup／否，carrier ID=null；其他 row 完全不改。managed root／clone 本身不移除 |
| registry starting／uncertain，觀測不 loaded | retain／COMMAND_UNRESOLVED，carrier 也保留；starting／是、uncertain／主線既有否。不是 already_absent，絕不退休 |
| already_absent session 的 worktree retained／未完成 | 原 active／是；沒有退休 runtime 使用權，person 仍可 resume 此 work context。無 automatic re-reservation，故保留原 slot；若已因 planner stop 退休則維持既有非 counted status |
| failover 同 worktree supersede | superseded／否；與 successor starting 的 reserve 同 flock，配對計一次；已存在主線行為不改 |
| explicit worktree_remove 成功 | 原 active row 改 removed／否；已退休 row 保持 stopped／absent_at_cleanup，另記 worktree_removed。失敗也不把退休 row 改 active，避免復活舊 ID |
| start definitive failure | failed／否；start 不確定則 uncertain，主線既有計數問題另列於尚未涵蓋，不能把未知 start 當本包 confirmed retirement |
| explicit stop（主線其他 stop action／legacy _stop 單獨使用） | 仍 active／是；既有主線缺少 retirement。本包不改平行 operations 的 stop action，自己的 reviewed carrier cleanup 可釋放此 row |
| BAT 自行 exit／外部 unload | 仍 active／是，保留 resume slot；既有主線不自動回寫。reviewed cleanup 成功／carrier absent 才退休，不能把單次 meta=null 當自動 housekeeping |

已退休的 ID 不能透過 Connector send／client-resume／answer／permissions／interrupt 再啟動，shared policy
回 SESSION_RETIRED；same-ID start／registry recovery 亦在原 registry flock 拒絕。人可用**新 ID**走原
session_start／reserve cap。原 worktree 的 Git cleanup 仍可執行；新 ID 共用 retained carrier 時仍經原 cap／policy。
Absence retirement 是 operation／carrier facts 的本機 projection，可由 cleanup run 重播；不是新增外部
phase。即使稍後 cancel／expiry，也不把已無 carrier 的 session 重新塞回 cap，不假稱 cleanup 停止它。
Finalize 先 durable 成功回執／tombstone／cleaned guard，再退休；中間 crash 時 resume 由 succeeded carrier
receipt 重播 retirement。成功寫入後再 crash，同值 retirement no-op，不能重寫 status 或退休第二次。

| Registry status reader | stopped／absent_at_cleanup 的處理 |
|---|---|
| reserve、list_entries(active_only)、claim_warm／handoff | cap 仍只有 active／starting，active_only 不列退休 row；warm／handoff 原 active gate 不認領退休 ID |
| service live list／successor、triage／worktree_status | headless active list 不含退休 row；原完整 registry／ID lookup 仍在，workspace tab 仍可只讀觀測，successor 不當 active |
| lifecycle failover／_evaluate／session_cleanup | 新 successor 用新 ID 並 reserve；不替退休 ID送訊息。read-only legacy candidates 加入退休 statuses，仍可評估原 worktree；status 不改已記錄的 supersede／removed 含義 |
| resource_policy._UNCONFIRMED／classification | 新 statuses 不屬 failed／starting／uncertain，creation proof 仍是 connector_managed；只在 runtime mutation decision 拒絕 SESSION_RETIRED，Git worktree actions 仍依原 ownership |
| cleanup BAT-made carrier projection | 明列兩個退休 statuses；同 birth slot／worktree ID、原 creation／layout／live carrier proof 不變 |
| guard_new_start／observation registry_bindings（平行套件） | 此固定基準尚無這兩個 helper；reserve／ensure_existing 已拒絕 retired same-ID，rebase 保留此 gate。Observation 要沿原 creation fields 判 ownership，兩 status 不進 _UNCONFIRMED；不修改平行工作樹 |
| Dashboard | live runtime status 與 registry status 分開；現有 receipt／result 用 JSON.stringify 原樣顯示新字串，沒有 registry enum 的翻譯／CSS 假設 |

## Preview／apply 合約（Part A）

### cleanup.preview

共用 read handler，不呼叫 OperationService.create，不寫 journal／registry／events／inventory，不建立
repo／lockfile，不 fetch／write ref。使用 read-only Fleet；遵守 service._state_safe，避免無 cwd Claude
record 的 get-session-state 副作用。不呼叫會寫整合區的 integration.preview。

Input `{target, choices}`。Choices：discard_uncommitted[]、release_undelivered[]，預設空，皆為 resource ID；
不能傳任意 path／ref／force。每 host serialize preview，一次一個，**包括排隊時間的共享 deadline**；
每 repository/container 一個 batched SSH read script，一次枚舉 worktrees／refs／dirty manifests，不逐 ref SSH。
每 host 另用一個 batch 解析所有選中 managed session 的 canonical workdirs；stop call 前再核該 path。
全部 terminal 的 live cwd 及 registered session state 讀取也共用同一 host lock／deadline，不略過 registry entries。
單一 snapshot；沒有 double snapshot／PREVIEW_UNSTABLE。Deadline 未讀完的項目 OBSERVATION_UNAVAILABLE，
不以缺失當乾淨。最多 500 resources、token payload 16 KiB；整份過大回 PREVIEW_TOO_LARGE，不截斷 apply。

Output `{preview_id,preview_token,fingerprint,contract_version,issued_at,expires_at,target,choices,items,impact,
ready,blocking}`。每 item：resource_id／generation／kind／host／original_ids／canonical binding／creation evidence、
四狀態／HEAD／ref SHA／dirty manifest digest／last observation、完整 relations／consumers／receipt coverage／
PR destinations、decision=retain/reclaim/already_absent、固定 steps 與 dependency IDs、全部 reasons／overridden_reasons。
Impact 列 reclaim／retain 數與 undelivered_commits_kept；items.steps、work_items、manifest 列具體停止／移除／丟棄影響。
不可量測 bytes=null，不能把留下的 Git objects 算回收。沒有可執行 reclaim item 時，若有已證實 absent、
仍占 cap 的 active 非 task session，且沒有自己的 worktree 或 carrier 同樣 already_absent，仍 ready=true。
這類 apply 經相同 signed preview／scope／fingerprint 重核，只寫 retirement 與 absence receipt，不送 host
mutation、不新增外部 step 或 tombstone。Retained carrier、未決 start、已退休／非 counted rows 不能單獨
啟用 apply；其餘沒有可執行工作的 preview 為 ready=false。Preview 本身不釋放 cap。

### Signed token／fingerprint

TTL **15 分鐘**（integration 是一小時）。Wire format `v1.<base64url(canonical payload)>.<base64url(HMAC)>`。
Canonical JSON 用 operations._canonical；key 為 HMAC-SHA256(admin token bytes,"batc.cleanup.preview.v1")，
signature 覆蓋 v1 與 payload bytes，constant-time compare。Payload 固定 actor／target／choices／fingerprint、
policy/contract/config digest、iat/exp（UTC integer seconds，exp=iat+900）。preview_id 為 actor/target/choices/
fingerprint/iat canonical hash 前 32 hex 加 clpv_。Admin token 輪替使尚未接受的 token 無效；token 不授予 scopes。
已接受的 operation params 有 server-only authorization；key 輪替不撤銷 accepted／resumed plan。
尚未送任何 external step 就過期仍拒絕；已送 steps 先 reconcile，不重授權。
恢復固定 plan 時若 PREVIEW_EXPIRED、PREVIEW_MISMATCH 或其他 early refusal，且此 operation **完全沒有
operation_steps row**，先以 registry flock 釋放此 operation 的全部 reserved guards 與 session
cleanup_reservation，再把所有 pending／running 回執改為 failed、error.code=該 refusal code，記
guard_released=true，才交回 OperationService。這沿用 cancel 的未送出規則：外部 mutation 必須先有
durable step，完全無 row 即證明沒有 pending／completed phase，釋放安全。僅因只讀觀測失敗留下的
uncertain 回執也按同一無 step 證明結清，不殘留假未決效果。即使原 document 無法解碼，仍按
operation_id 釋放，不依賴 item loop；他人的 guard 與 confirmed cleaned marks 不動。中斷可同值重播。
這是 refusal 的 release，不是逾時自動解鎖。只要已有任一 step（含 failed），就不走此全 operation
release；原 reconcile／partial 規則不變。Resume mismatch 指 accepted token hash 與 journal 不符，
不是同 key／同 public request retry；後者仍回同一 operation。

Fingerprint 包含完整 resource 集合（包括 retain）、ownership/generation/path、content／dirty bytes/type、
refs／registration／merge state、writer/pending、commands／global consumers、receipt coverage、retention rules、
choices／steps；排除 heartbeat／抓取時間／讀取次數／顯示語言。
Apply 在首個 mutation 前重新計算**整份** snapshot；之後每 item 的 mutations 前只核對該 item／consumers
（及自身已證實的 planned transitions）。`snapshot(only=resource_id)` 只觀測該 item 的 host，仍讀該 host
全部 terminals／consumers；local_branch 由 creation slot 投影 ID／host，並用同一 repository read 取得 live
branch SHA，即使 worktree 已移除也仍重核。沒有逐 item 額外 journal 查詢。初始 preview 與 apply 首次驗證
仍觀測所有選中 configured hosts。其他 host
逾時不會在每個 healthy item 上重付 deadline；其資源仍保留 OBSERVATION_UNAVAILABLE。
不 O(n²) 重讀所有剩餘資源。任何外部變動 PREVIEW_STALE，不能換 plan。

### cleanup.apply

ActionDef("cleanup.apply","cleanup",...)。Input：target={preview_id}、params={preview_token}、
preconditions={preview_fingerprint}、idempotency_key。可選 params.supersedes_operation_id 只连同 scope 的舊回執。
Admission 核簽名／actor／target／choices／fingerprint／scope／ready；handler 在持久 intent 後 live revalidate。
Apply 不能增減 resource／discard／release／force。相同 actor/key/content 回原 operation。
Validation 成功後保存同 fingerprint 的完整 document、accepted authorization、per-item intent、tombstone draft；
再安裝 reservation。Response 遺失查同 operation，不重建。

每個 item 的 DAG：validate → preserve → stop（若列出 idle loaded session）→ discard（明選才有）→
remove.worktree／remove.temporary → remove.branch（只有 delivered）→ finalize。Session、worktree、branch
各有 item ID；worktree 依賴對應 session 已停止。steps 命名 item.<id>.<phase>.a<attempt>。
Phase 分類：preserve 是 additive；stop 是 runtime；discard、remove.worktree、remove.temporary、remove.branch
是 destructive。其他 phase：validate 是 read-only，lock.session 是 coordination（其 locked_action 執行 stop），
verify.retained／canonical_paths／observation 是 read-only，finalize 是 journal／registry metadata，不改 Git／runtime。
Operations 合併後保留 cleanup 原有 transaction 邊界：cleanup_runs／初始 receipts 同一 journal tx；
finalize 的 tombstone／aliases／receipt／event 同一 tx。這些 local writes 不加 `ctx.effect` 的 step，
因為「尚無 external step」是 expiry／early refusal 釋放 reservation 的既有判定，不能被 local receipt
改變。Registry guard／retirement 是獨立 filesystem effect，以 flock、generation 與既有 receipt 重播；
不能包進 SQLite 的 effect tx。Stop／Git mutation 繼續使用 `ctx.step` 與 read-back；測試以
`settle_operations` 等待持久結果，不以 best-effort drain 期限代替 settlement。
Local branch 的 only=resource_id snapshot 保留 creation identity，重新觀測 branch；只允許 dependencies
刪去本 operation 已有 succeeded worktree receipt 的 IDs。增加 dependency、刪去未成功 prerequisite 或任何
其他欄位改變仍是 PREVIEW_STALE。若無 repository projection，原 actual is None fallback 仍沿用 reviewed
item，host CAS 與 consumer gate 仍重核。Host 在同一 flock 下、
寫 branch retained ref 前核 exact branch SHA，移動即 PREVIEW_STALE、無 ref 寫入；刪除時仍核 checkout 與 CAS。

| 副作用 | 限制 |
|---|---|
| preserve | refs/batc/retained/<resource_id>/<revision slot> CAS create，已等值成功，不同值 RETAINED_REF_MISMATCH；cat-file 可讀才算 retained |
| stop | lifecycle._stop 新 keyword-only cleanup=False；default 保留舊行為，cleanup=True 時 no retry on disconnect、ambiguous 傳給 OpContext。Preview／apply re-check／最後 pre-stop 共用 service.SESSION_WAITING_FIELDS；所有 pending question/permission/approval、queued message/count、input waiting 都再查，任一為真回 SESSION_WAITING、streaming 回 ACTIVE_WRITER，不送 stop；不直接 shell kill |
| discard | preview 完整 tracked/staged/untracked/ignored manifest；tracked git restore 到 pinned HEAD，untracked no-follow exact unlink；不 clean sweep／force remove。複雜 merge/rebase 若無精確 after manifest就保留 |
| remove worktree | HEAD retained、writer/pending/consumer 消失、dirty=0，managed clone/area 中 git worktree remove exact-path，無 force／prune／rm fallback |
| remove branch | 只 delivered batc/cp-*／fix-* 或有 BAT creation 證據的 exact bat/*、無 checkout/consumer，retained HEAD存在，update-ref -d full-ref expected-old-SHA CAS；release 的 branch保留 |
| remove temporary | exact intent／markers／完整 manifest，先 pin commit，no-follow exact deletion；未知內容不碰 |
| finalize | receipt／tombstone／aliases／retained／api event 一個 SQLite tx；registry 同 flock標 cleaned，可由相同 tombstone ID重播 |

Result `{preview_id,fingerprint,summary,items,tombstones,next_action}`；retained IDs 在逐項 receipts，實物另由 retained read 核對。Receipts 包含 planned/actual steps、
attempts、before/after、retained SHA/location、discard/release choices／authorization、error、settled_by、relations、PR。
回執另有 completed_phases=[{resource_id,phase,effect,step,result}]、refused_phases（同欄位但 error）、
cancel_requested。兩個 phases 欄位每次從 authoritative operation_steps 重建，含 approved DAG 的遞迴
prerequisites：worktree 的 session stop、branch 的 worktree removal 都帶原 resource_id。不加重複的 journal
欄位；step success 已 commit 後即使 receipt／finalize crash，成功 evidence 仍在，tombstone 也保存同一 projection。

| Item status | 回執／副作用 |
|---|---|
| retained | 明列 retention reasons，不執行 |
| pending／running | reclaim intent 已保存／已 reserved，尚未完成 |
| succeeded | 實際 stop／remove 經 read-back 確認；finalize 寫 tombstone／aliases、registry cleaned |
| already_absent | preview 與首輪全 plan 驗證證實 session 不 loaded 或 worktree／temporary 不存在，且無 retention reason；保存同名 definitive receipt／原 observation／IDs，不送 per-item host call、不新增 tombstone／aliases／registry cleaned。Session carrier 已移除／absent 或無自己的 worktree時另標 absent_at_cleanup、回執 after_state 記 capacity_released／registry_status／carrier_resource_id／stopped_by_cleanup=false；carrier retained 時原 slot 留著 |
| failed／blocked_stale | definitive refusal／item precondition 變動；已完成 effects 仍投影，runtime／destructive partial 不用這兩個 status |
| uncertain | 未決效果或已完成 runtime／destructive 的 partial，reservation 保留 |
| cancelled | 未送出或 additive-only 已結清，回執仍列已完成 pins；不包含 partial runtime／destructive |

result.items 與 summary 分別計數 succeeded／retained／already_absent；already_absent 不算 retained 或 partial。
原 absence 回執永久可由 operation read 查詢；cleanup-tombstones 不為沒有 cleanup mutation 的 item 建假 history。
Dependency satisfaction 接受 succeeded 或 already_absent。現有 planner 只把 loaded 的 reclaim session 加入
worktree dependencies、只把 reclaim worktree 加入 branch dependencies，通常不產生 absent edge；若已接受
DAG 有此 edge，absence 回執也已滿足 prerequisite。Cancel 保持 already_absent status。
Operation 沿用原狀態；summary.partial=true，不新增 partial state。獨立 item確定失敗可繼續其他項；
uncertain／stale 停後續。首輪 stale=failed、零 mutation；部分成功後 stale=needs_attention、須新 preview。
Definitive refusal 只證明**該次 phase**沒有未決效果，不代表 item／DAG 之前沒有更動。
此前已有 runtime／destructive success 時，receipt=uncertain、error=CLEANUP_PARTIAL_STATE，保存
completed_phases、refused_phase／refused_code；guard 保留，operation=needs_attention。只有 additive pins
完成且無未知 phase 時可釋放 guard，receipt 仍列出 pins，不能宣稱零效果或內容全保留。
Resume 不重做 success，對 definitive failed Git phase 先以 probe 證明程序結束、carrier identity、exact content
一致，再建立 .aN+1，gate 重新查 consumer／policy。Definitive pre-stop refusal 也用新 attempt，
readonly gate 再核同一 runtime／cwd／policy。多個 session prerequisite 只有部分 stop 完成時，
worktree 的 dependencies refusal 也是 partial／guard 保留。Blocker 仍在則再拒絕且不重複 discard／stop／remove。
Discard 的完整 after observation 在 host flock 下存入 succeeded step；後續 phase 與 retry 使用此 snapshot，
不以 resume 當下的內容重新定義 post-discard precondition。舊 step 無此證據時留 needs_attention，不猜 after。
新的內容／ref 移動仍 PREVIEW_STALE（partial receipt 的 refused_code），先查看原 evidence，不能擅自再 discard。

Cancel 不 rollback。已有 runtime／destructive success 的未完成 item（含 prerequisites）保留 uncertain receipt、
CLEANUP_PARTIAL_STATE、completed_phases 與 reservation；cancel_requested 由原 operation 讀出。
取消 needs_attention 時 OperationService 可直接終止 parent，不改其規則，原 partial receipt／guard 仍保留。
Operation cancelled 不代表內容保留或 runtime 還在；這些保留的 partial reservations 需人工檢視，
本包不提供強制解除／takeover，不能 resume 已 cancelled operation。只有未送出或純 additive、全部已結清
的 item 才 cancelled 並釋放 reservation，pins 仍列出。未知 phase 先 reconcile，cancel 不跳過證明。

### Reserved 後退出路徑稽核

| 路徑 | Guard／回執規則 |
|---|---|
| admission、initial expiry／整份 fingerprint revalidation | reservation 尚未建立，無釋放需求；admission 不寫 cleanup guards／receipts |
| resumed token hash／expiry／document decode、set_refs 的 early refusal | 完全無 step row 時走上述 operation-wide release，pending／running 全改 failed；有 step 不釋放，由既有 durable evidence 保持 reservation |
| mark／receipt running 到第一個 step 間、validate／policy／canonical／readonly precheck 的 OperationError／ResourceReadOnly | mark 與 receipt running 在同一 per-item try；無 pending／runtime／destructive 時 failed 或 blocked_stale 並釋放 own guard。若因此停止且整個 operation 無 step，外層同時釋放其他 crash 留下的 own reservations、結清 pending／running |
| dependency refusal | 無未決 call／irreversible effect 時 failed 並釋放該 item；未決 step 或已完成 prerequisite stop／remove 時 uncertain、保留 guard、needs_attention |
| host mutation／lost reply、runtime／destructive 完成後的後續 refusal | 依 step reconcile／CLEANUP_PARTIAL_STATE 保存已完成效果；不能因後續 refusal 釋放 |
| local／read-only OSError、Uncertain | 不把未知觀測當可繼續；保留 guard 與 uncertain 回執，OperationService 再回查，不是 definitive release |
| finalize／registry cleaned replay | tombstone 與 step 成功保留；同一 ID 補 mark，不解除 confirmed cleaned guard |
| cancel | 未送出／additive-only 且已結清才釋放，partial／unknown 保留；already_absent／retained／succeeded 不改 status |
| 其他 local handler exception | 完全無 step 時仍按 operation_id 結清／釋放，回執沿用 code，無 code 為 INTERNAL；任何 step 已存在都不走此 release |

Host helper 在第一個 mutating call（update-ref、exact unlink／rmdir、git restore、git worktree remove）開始前
設 marker。之前的拒絕仍是 `{error:code}`，沿用 definitive code；之後任一 ValueError／OSError／SubprocessError
回 `{error:code,mutated:true,effects:[{action,target,completed}]}`。mutated 表示 call 已開始、可能有部分效果，
不宣稱該 call 成功；completed 只表示該 call 已返回成功，Git 失敗仍可能有部分更動。
`_host_call` 將此形狀轉 MutationUncertain（AmbiguousOutcome），step／item 保持 uncertain、guard 不釋放；
receipt 保存 host_error／phase／effects。Resume 的 live read-back 只有四種結果：完整 after 補成功；
完整 before 且 flock 證明程序結束時可重跑；preserve 的等值 pins 可 CAS 補齊；可證明的 temporary subset
才完成原 exact removal；其餘 partial state 轉 needs_attention／CLEANUP_PARTIAL_STATE，step 仍 uncertain。

Temporary partial recovery 不要求已部分刪掉的 Git metadata 仍可開 repo：先 canonical／no-follow 讀完整剩餘
manifest／directories。剩餘每個 entry 的 path／type／bytes／digest／mode 必須等於原 preview，directories
只能是原集合的子集；任何新增／改變／link／不完整 observation 都不能刪。原 temp 需 git-only／content_available
證據；在 carrier flock 內再核 identity、subset 與**全部** retained refs／commit 可讀，才 unlink 剩餘 exact entries。
原 step intent 授權同一 manifest，receipt 先記 recovery evidence，成功的 step response 保存此證據；cancel 不開始續刪。
Discard 的 tracked／staged after-state 未完整成立時，不猜哪些 restore 已完成，保留 needs_attention。
Partial evidence 列 removed／changed（before/after facts）／added／remaining、directories、refs 與 repository identity。
讀不到時維持 unknown／uncertain，不以空集合假裝已刪；partial 未被解釋前，不因之後的 refusal 釋放 guard。

所有可能寫入的 host phase：lock.session（gate 內呼叫既有 BAT stop）、preserve、discard、remove.worktree、
remove.temporary、remove.branch，必須提供 locked_check；_host_call 與 cleanup_host.mutate 都拒絕缺 gate。
Stop 的 readonly locked_check 與 runtime locked_action 分開：checked=true 在前置核對完成後、BAT stop
之前設定；BAT reply lost 也走 gate 後 uncertainty。明確 pre-stop SESSION_WAITING／ACTIVE_WRITER refusal
仍 definitive，沒有送 stop；不把這種已知 refusal 當 transport failure。
若 BAT stop ACK 已收到，但 lock.session helper 之後拒絕或回覆遺失，整個 step 仍 uncertain／guard 保留，
receipt.error.effects 保存 completed stop ACK；helper 的 no-Git-effect refusal 不能宣稱 BAT 沒有停止。
Helper 的 mutate 在 flock／identity 核對後輸出 locked，並以 select／readline 等待明確 `{proceed:true}`；
EOF／refusal／deadline 不進入任何 mutation。checkpoints._run_locked 在 check 拒絕或 exchange 失敗時關閉 stdin，
cleanup_host.mutate 的 proceed 分支保證此界線前失敗沒有寫入。
Gate 通過（checked=true）後，runner process／transport／timeout／decode／reply schema 失敗都轉
MutationUncertain，synthetic host_error=CLEANUP_HOST_PROTOCOL_UNCERTAIN；缺 result／error、錯誤型別或
phase completion 欄位不足都不能當成功。合法 `{error:code}` 仍可表示 helper 尚未寫入的 definitive refusal；
`mutated:true` 的合法 error 仍 uncertain。Gate 前 exchange 失敗是 CLEANUP_HOST_REFUSED，不重送寫入，
step definitive failed；canonical_paths／observation／verify.retained 是 read-only，沿用原錯誤處理。

### 錯誤代碼

| code | HTTP／下一步 |
|---|---|
| INVALID_TARGET／INVALID_PARAMS／INVALID_REQUEST | 422，修正輸入 |
| NOT_FOUND／UNKNOWN_HOST | 404；host 既不在 config 也無 resource history，才是 UNKNOWN_HOST；原 ID有tombstone仍可查 |
| FORBIDDEN／DISCARD_SCOPE_REQUIRED | 403；discard admission缺cleanup_discard，不用於resume |
| PREVIEW_TOKEN_INVALID | 409，格式／signature／rotated key不符，重preview |
| PREVIEW_MISMATCH | 409，actor／target／choices／precondition與token不符或 resumed accepted token hash 不符；完全無 step 的 run 先釋放 own guards、pending／running 改 failed，再重preview |
| PREVIEW_EXPIRED／PREVIEW_BLOCKED | 409，過期／ready=false；resumed run 完全無 step 時 expiry 先釋放 own guards、pending／running 改 failed；已有 step 沿原 reconcile 規則 |
| PREVIEW_STALE | 409或operation error，live state changed；首輪回fingerprint已變，item階段回resource已變；重preview比較原預覽 |
| PREVIEW_TOO_LARGE | 413，改較小scope，不截斷執行 |
| RESOURCE_CLEANED／CLEANUP_IN_PROGRESS | 409／policy refusal，原generation已清理／reserved |
| SESSION_RETIRED | 409／policy refusal，退休的 session ID 已不占 cap，不能 drive／resume／same-ID start；以新 ID reserve，原 history／worktree 不改 |
| REGISTRY_IO_FAILED／REGISTRY_READ_FAILED | capacity_error 的 bookkeeping evidence，非 operation error；capacity_released=false、保留 registry／成功 cleanup outcome，resume 可重播 |
| 共用ownership／destination／TIER_DISABLED／NO_MANAGED_ROOT／GIT_RUNNER_UNAVAILABLE | 沿用原code，保留不越界 |
| OBSERVATION_UNAVAILABLE | retained reason；歷史 host 不在 config 時保留所有 creation identities／branches／carriers，preview 仍成功，無 live call；直接 adapter／mutation call 回 409，未決 phase 仍保留 guard |
| DISCARD_MANIFEST_UNAVAILABLE／RETAINED_REF_MISMATCH／RETAINED_CONTENT_MISSING | 409，無完整discard／保留證據，停止移除 |
| WORKTREE_REMOVE_REFUSED／REF_CHANGED | 409，非force Git拒絕／CAS不符，保留回執重preview |
| STOP_UNPROVEN／EXTERNAL_EFFECT_UNPROVEN／UNCERTAIN_UNRESOLVED | uncertain／needs_attention，讀回不重送 |
| CLEANUP_MUTATION_UNCERTAIN | per-item uncertain，host 回 mutated=true；保存 host code／effects、保留 guard，讀回核對原 intent |
| CLEANUP_HOST_PROTOCOL_UNCERTAIN | gate 已通過但 transport／process／decode／schema 無可靠回覆；同 uncertain／guard／reconcile 路徑 |
| CLEANUP_HOST_REFUSED／CLEANUP_GATE_REQUIRED | 409，gate 前 exchange 失敗／mutation 缺 gate；helper 未獲 proceed，不會寫入 |
| CLEANUP_PARTIAL_STATE | operation needs_attention、item uncertain；未決 step uncertain，definitive refused step failed。保存 completed_phases、refused_phase／refused_code 或 removed／changed／remaining；guard 保留。cancel 仍保存 effects／reservation，不能把 partial 當 success／kept |
| LEGACY_CLEANUP_DISABLED | 409，改用batc resource-cleanup |
| INTERNAL | OperationService 原 handler error；完全無 step 的 local／journal decode failure 仍先結清 pending／running、釋放 own reserved guards，不做 host call |
| IDEMPOTENCY_CONFLICT／IDEMPOTENCY_KEY_REQUIRED／NOT_RESUMABLE | 沿用OperationService |

## Crash／lost-reply（Part A；restore列為Part B）

所有外部call用OpContext.step，step intent commit後才送。未決step先reconcile再看cancel；不能因
parent cancelled/failed把它當成沒發生。遠端程序仍在／身份不明時不能因本機SSH退出重送。

| 步驟 | 讀回／可否重送 |
|---|---|
| preview reply lost | 純讀重取；沒有preview row要刪 |
| accepted reply lost | 同key查同operation |
| validate／guard後crash | 查固定plan／registry marker；完全無 step 時 expiry／mismatch／early refusal 先按 operation_id 釋放全部 own reserved guards／session markers、pending／running 回執改 failed；無外部 mutation 可安全釋放，新 preview／apply 可再回收。有step不採此 release，先reconcile |
| preserve ACK lost／部分 pins 後錯誤 | 全部 exact ref=planned SHA且object可讀補成功；content unchanged、flock 證明原程序結束才 CAS 補 missing pins；不同SHA轉 CLEANUP_PARTIAL_STATE、guard 保留 |
| stop ACK lost | 已證實start、host健康、相同generation的終止證據才成功；單次meta=null／無tab不足；unknown不重stop |
| discard partial／lost | 完整 dirty=0／HEAD／retained 證據補成功；同 before 且原程序結束可重跑；extras 已刪但 tracked／staged 未完整 restore 時 CLEANUP_PARTIAL_STATE，逐 entry 證據保留且不再 remove worktree |
| worktree remove lost | retained仍在，path與registration都消失即成功；只有path消失不prune；仍原binding/clean且前程序结束才非force重送 |
| branch CAS lost | ref absent且retained old SHA在即成功；still old且無writer可CAS retry；第三種SHA stale |
| temporary partial／lost | 全部消失且pins仍在補成功；完整 before 可重跑；原 exact manifest／directories 的 unchanged subset、carrier identity 與全部 pins 重新核實才續刪。新增／改變內容或 missing pins 轉 CLEANUP_PARTIAL_STATE，保存證據，不掃剩餘檔案 |
| finalize crash | steps讀回可補finalize；同tx／unique keys防重複event／aliases；registry同值對帳 |
| runtime／destructive success 後別的 phase 拒絕 | succeeded steps／prerequisite effects 永久列於 receipt；failed phase 已知無效果，item partial=uncertain、guard 保留、needs_attention。post-discard 原 after 一致且 gate 再通過才 .aN+1，success 不重做 |
| cancel／Resume | 成功item留存；未送出或 additive-only、全部已結清才釋放 guard。runtime／destructive partial 或未知 phase 不解鎖，receipt 列 completed_phases、cancel_requested；parent cancelled 不是內容保留證據。Resume 只重試證明 no-effect 的 failed phase，新 .aN+1 核原 post-state |
| Part B restore add lost | exact新worktree/branch/HEAD/tree對上intent才補成功，未知目的地不認領；不重建runtime |

## Journal／migration

原Journal、WAL/FULL、single owner。新增idempotent DDL，每次open都以BEGIN IMMEDIATE一個tx建表/index；
不讀、不寫user_version，中斷rollback可重跑。版本號只供 orchestrator 跨package分配的一次性data steps使用，
本包不假設其他package的版號。DDL若相對遞增版本會跳過其他package的data steps；
Part A只有建表/index，不占版本號。
目前 data steps 為 1 event copy、2 observation history；deployment history 的 3 另行整合。
Cleanup DDL 單獨執行時保留原 version；完整 Journal open 仍依已整合的 migration 升級。
不改operations table，不host calls、不刪舊rows／registry／events，不重編cursor。

| 表 | 固定事實／鍵 |
|---|---|
| cleanup_runs | operation_id PK/FK、preview_id、token_hash、fingerprint、immutable document、accepted_actor/scopes/choices、validated_at、supersedes_operation_id；validated snapshot是新事實；authorization沿用operation params接受時的固定metadata |
| cleanup_receipts | (operation_id,resource_id) PK，item_order、plan、status、before/after、attempts、error、settled_by、retained IDs／timestamps；resumed_by 從原 api_events 附加；completed_phases／refused_phases 從 durable steps（含 DAG prerequisites）投影，cancel_requested 從 operation 投影，不加重複欄位 |
| cleanup_retained | retained_id PK、resource_id、preserve operation/step、revision_key、host/repository/ref/commit/tree/digest、creation evidence、created_at；每次read即時核實，不寫last_verified；unique preserve op/resource/revision |
| resource_tombstones | resource_id PK、generation、original_ids、host/profile/workspace/path/ref、creation evidence、last observation、reason/choices、relations、receipt keys、retained IDs、PR destinations、cleaned_at |
| cleanup_aliases | (kind,external_id,host,resource_id) PK；原session/run/task/checkpoint/op與generation path/ref的永久解引用 |

Consumers在讀取時計算；reservations的唯一跨process authority是registry guard，不複製task狀態。
Part A不backfillTaskDaemon舊清理；Part B才把可信external_worktree_retained事件投影到共用finalize。
不保存API/admin tokens／credentials／raw transcript audit；只保留已遮蔽的固定context與references。
Tombstone自有routes可查原ID、舊位置、清理原因、誰做的、哪個PR接收，不依livehost。
其他session/work-item/checkpoint/integration詳情最多一個cleanup.lookup call，在實體gone時附context。

## 保留設定

[cleanup] retained_refs="keep"、history_retention="forever"、permanent_delete=false。
唯一支援這三個值，其他啟動拒絕；preview TTL不刪內容。clone／area與所有refs/batc/*永遠留存。
沒有container retirement／retained store／time-based deletion／disk-wide sweep／background housekeeping。

## Surfaces（Part A）

| 入口 | 合約 |
|---|---|
| POST /api/v1/cleanup-previews | observe，body target/choices，200純讀snapshot／token；discard另查scope |
| POST /api/v1/operations | cleanup.apply，原key／202/200／get/cancel/resume；唯一mutation action |
| GET /api/v1/cleanup-retained | observe，target filters／host/resource_id/query、limit50(max200)/cursor；retained[]只含ref/object真實可讀，unavailable[]含離線／失蹤紀錄與原因 |
| GET /api/v1/cleanup-tombstones、/{resource_id} | observe，query/host/work_item_id/kind、keyset(cleaned_at,resource_id)、cursor；另以original_id alias lookup |
| MCP cleanup_preview／cleanup_apply | 同schema，apply需confirm、BATC_API_TOKEN，不fallbackadmin；previewtoken綁callingPrincipal |
| MCP cleanup_retained／cleanup_tombstones | 都是read工具；Part A無cleanup_restore |
| CLI batc resource-cleanup preview | --item/--checkpoint/--integration/--host擇一、--include-children、--discard-uncommitted ID、--release-undelivered ID、--json |
| CLI batc resource-cleanup apply | --preview-token／--fingerprint／--key／--confirm；可讀previewJSONfile，不選新resources |
| CLI batc resource-cleanup retained／history | 同read routes；續做用batc op ID --resume |

Capabilities列cleanup/read/apply/discard、host能力／reason／limits／15分鐘TTL／retention；restore=false。
api-token issue help、api-v1.md、README兩語、兩份skills都列新scopes；agent不要求cleanup_discard。
Legacy batc cleanup／session_cleanup名稱保留只讀，不alias新的host-wide語意；apply立即409並指出新流程。
Legacy evaluation 只讀 worktree status；BAT 忘記 worktree 時不取得 mutation grant、不發
worktree:rehydrate，即使 confirm=true 也不重登記；缺狀態回 ESCALATE，registry 不變。
auto_cleanup只保留config解析，deprecated且不啟用writes；worktree_merge/remove仍是explicit動作，只共享guard。
Fanout planner 只有 caller `confirm=true` 且每一個 planned task 都成功啟動，才經原 stop 路徑停止。
Stop ACK ok=true 且健康 meta read-back 不 loaded 才標 stopped（含 operator），離開 cap；未確認保留原 counted row。
Stop 已確認、capacity 拒絕／I/O failure 時仍回 stopped=true；另外列 capacity_released=false 與原因，不能謊稱未 stop。
未確認、任一 start failed 或 loop 提早停止，都保留 loaded planner／原 plan 供 retry；不能因 starts
回傳 error 或只是部分成功就 stop。回 `planner_cleanup={stopped:false,reason,worktree_kept:true,
next_action:"batc resource-cleanup"}`，reason 區分 confirmation／start failed／incomplete loop。
成功 fan-out 的 stop 仍核 tier／policy／streaming，stop refused／error 也保留原因與 next_action。
任何情況都不 merge／remove planner worktree；idle planner 可另經 reviewed cleanup 回收。

Dashboard #/cleanup、#/cleanup/resource/ID：scope／子工作、真resource與all reasons／plan、保留commits與
未送達標記、discard不可復原內容、一次apply、逐itemreceipt、tombstone搜尋、實際retained列表。
工作detail有預填work_item的整理entry；沒有restorebutton。Stale顯示拒絕原因、留choices草稿、重preview以比較差異；
lostreply保留reviewed document與key，reload後用同token/key查回原op；未知回覆時不能另開preview。Reuse原tokens/components、兩語i18n、fill()、CSP、focus/live-updatehold；390px驗證。

## Part B：reviewed task cleanup與restore（第二步，尚未實作）

TaskCoordinator在task state/control_version／pending commands／warm claim／writer lock下先決定eligibility，
允許terminal且全部content需求釋放後才准reviewed leftovers。TaskDaemon原terminalcleanup不取消，
而是把原proof透過sharedfinalize寫同receipt/tombstone/retained；舊事件only可信evidencebackfill。
TASK_OWNED在這階段才改為實際coordinator verdict，不在Part A假稱問過owner。

cleanup.restore註冊獨立ActionDef，需cleanup，target retained_id、mode managed_worktree、expected_retained_digest、key。
只從實際ref/objects與exactSHA，在同host managed clone/area固定新wt/batc-restore-<op>/batc/restore-<op>
建新worktree；來源／目的都sharedpolicy，reservation先記intent。verifyHEAD/tree/clean後finalize新resource，
原tombstone與IDs不改。Result含restored_resource_id/restored_from/commit/tree/runtime_restored=false。
不送start/send/tab，不承諾runtime復活；新agent仍走checkpoint/start且需startscope。
MCP cleanup_restore**只有mutation**，read保持cleanup_retained；CLI新增restore、Dashboard實際可復原項才顯示button。

## 預計修改檔案

Part A：新cleanup.py、cleanup_host.py、resource_ids.py；task_journal.py（migration）、registry.py（guard metadata）、resource_policy.py（單一hooks
及cleanupSSHpolicy）、config.py/api_auth.py；api_v1.py（registration/routes/one-calllookup）、mcp_server.py/cli.py；
lifecycle.py（legacy／stop option／planner）；dashboard/app.js/app.css/i18n.js；README兩語/CHANGELOG/兩份skills；
api-v1/resource-policy/checkpoints/integration/work-items/dashboard設計的已完成／尚未涵蓋；tests/test_cleanup.py及必要回歸。
Part B才改task_core/task_daemon/task_bat與restore相關surfaces。本包不改OperationService或operations schema。

## 測試對應

新tests/test_cleanup.py用MockBat/FakeGitHub/LocalRunner/RealGitLog/temp Git，無實機寫入；manual refs/index/mtime/
config/HEAD/BATframes做snapshot。所有faultintent／replay／stale／scope／policy都驗證，不靠skip。

| 計畫§23／驗收 | 測試名稱／證據 |
|---|---|
| 四狀態／inactive不足；E01 | test_e01_pending_start_stop_and_waiting_sessions_are_retained |
| preview 到 stop 間任何 waiting field 改變都不 stop／remove；E01 | test_e01_every_waiting_field_racing_with_stop_keeps_session_and_worktree（共用 set 全部九個 fields）、test_e01_preview_recheck_and_stop_share_waiting_fields |
| registered live cwd／unknown consumer 阻止 stop 與 remove；E01/E02 | test_e01_registered_terminal_live_cwd_or_unknown_blocks_preview_and_apply（inside／missing cwd／missing meta／failed read）、test_e01_live_cwd_uses_path_components_not_string_prefix |
| host flock 內、每個 phase 前再查全部 live consumers；E01 | test_e01_live_cwd_is_rechecked_under_host_flock_before_stop_and_removal（lock.session／preserve／remove.worktree，各測 live cwd race／read failure，實際驗證 flock 被持有） |
| refused callback 的 EOF 立即結束 host helper；E01 | test_e01_refused_locked_check_closes_host_input_without_waiting_for_deadline（含 Python 3.10） |
| 父子樹、manual/unknown/active/completed與exactplan；E01 | test_e01_tree_preview_apply_matches_and_read_only_resources_survive |
| sharedID／全域consumer、history不擋；E02 | test_e02_shared_worktree_is_one_item_and_checks_out_of_scope_consumers、test_e01_tree_preview_apply_matches_and_read_only_resources_survive |
| receipt而非ancestor，partialpick/newtip/uncertain；E02 | test_e02_squash_and_pick_use_exact_delivery_receipt_coverage |
| release保留內容只需cleanup／discard需scope；E01 | test_e01_release_keeps_commits_with_cleanup_scope、test_e01_discard_requires_cleanup_discard |
| purepreview/token/stale/expiry；E01 | test_e01_preview_is_pure_and_signed_plan_cannot_be_changed、test_e01_stale_any_item_stops_before_mutation_and_reports_changes |
| guard 到第一個 step 間 crash／early refusal、同資源可再回收；E01／§23 failures | test_e01_resumed_unstarted_refusal_releases_all_reservations（expiry／mismatch／journal decode error、全部 guards／session markers 清除、回執 definitive、新 preview／apply 成功）、test_e01_refusal_before_first_step_releases_guard（validate／reservation／set_refs）、test_e01_expiry_after_read_only_failure_settles_unstarted_uncertainty |
| 有 step 的 resume 不採 unstarted release；E01 | test_e01_resumed_expired_run_with_steps_keeps_reservations_and_finishes、test_e01_resumed_mismatch_with_steps_never_releases_guard、test_e01_dependency_refusal_keeps_unresolved_call_reserved |
| observed absence 不假稱 retained／cleaned；E01/E02／§23 receipts | test_e01_already_absent_receipt_and_satisfied_dependency（mixed reclaim、HTTP operation receipt／summary、自有 tombstones 不建 absence row、無 per-item execution／stop／registry cleaned、accepted absent dependency 可繼續） |
| canonical/policy/preserve/nonforce/CAS；E01 | test_e01_every_mutation_rechecks_policy_and_canonical_destination、test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs |
| standalone BAT creation 的 host／work-item scope、preserve／remove／branch CAS；E01/E02 | test_e01_standalone_bat_worktree_and_branch_are_reclaimed（兩種 target、session delivery receipt、兩 item succeeded、載體保留）、test_e01_standalone_bat_release_keeps_undelivered_branch |
| standalone live carrier／branch 矛盾、managed roots 外不能回收；E01 | test_e01_standalone_bat_worktree_live_binding_mismatch_is_retained、test_e01_standalone_bat_worktree_outside_managed_roots_is_listed_and_retained |
| 同 apply 的 worktree／branch 回執均成功；移除後 branch 移動先拒絕；E01 | test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs（live branch snapshot，只正規化 succeeded worktree dependency）、test_e01_branch_moved_after_worktree_removal_is_stale（PREVIEW_STALE、所有 refs 不變） |
| integration 三種 target 同 scope／handoff 完整鏈；E01/E02 | test_e01_integration_preview_apply_and_handoff_expand_to_same_resources（source／area／pins／repair／session 的所有 item fields 相等） |
| crashedcheckpoint/handoff／未決start-stop；E01 | test_e01_crashed_continue_and_handoff_intents_are_discovered_without_adoption、test_e01_pending_start_stop_and_waiting_sessions_are_retained |
| partsuccess/restart/lostreply；E01 | test_e01_partial_cleanup_resumes_only_unfinished_unchanged_items、test_e01_lost_replies_reconcile_each_cleanup_phase、test_e01_cancel_reconciles_sent_steps_and_releases_only_confirmed_reservations |
| post-mutation error 保持 uncertain／guard；partial reconcile；E01 | test_e01_temporary_post_mutation_failure_keeps_guard_and_reconciles（第二次 unlink／root rmdir failure，原 subset 安全續刪）、test_e01_discard_restore_failure_after_unlink_reports_partial_evidence（needs_attention、removed／remaining）、test_e01_preserve_failure_after_a_pin_completes_missing_pins |
| locked gate 後 process／protocol failure；E01／§23 lost-reply | test_e01_post_gate_transport_and_protocol_failures_reconcile（GitCommandFailed／timeout／OSError／disconnect／truncated／not JSON／{}／malformed result／error）、test_e01_eof_during_locked_check_refuses_without_mutation、test_e01_mutating_phase_requires_locked_gate、test_e01_stop_protocol_failure_after_gate_reads_back_without_repeat（stop ACK 後 process／{}／helper refusal；保存 ACK evidence） |
| 已完成 destructive／runtime 後 refusal、無重複效果；E01/E02／§23 partial success | test_e01_completed_discard_survives_refusal_and_new_attempt、test_e01_completed_worktree_removal_survives_branch_refusal、test_e01_completed_stop_survives_first_git_refusal、test_e01_retry_uses_recorded_post_discard_state |
| 共用 worktree 的 stops 只完成一部分；E02／§23 DAG receipts | test_e02_shared_worktree_partial_stop_dependency_stays_reserved（dependencies refusal 仍列已 stop、保留 guard；清 blocker 後 stop.a2，已成功 stop 不重做） |
| cancel partial 保留證據／guard，additive-only 可釋放；E01／§23 receipts | test_e01_cancel_partial_keeps_completed_phases_and_guard（active cancel／needs_attention cancel、live API receipt）、test_e01_additive_only_refusal_lists_pins_and_releases_guard、test_e01_additive_only_cancel_records_pins_and_releases_guard；原 cancel 回歸測試也驗證已 stop 的 prerequisites |
| mutation 前 refusal 仍 definitive；E01 | test_e01_refusal_before_host_mutation_stays_definitive（無 stop dependency，PREVIEW_STALE、failed step、零 ref write、guard 釋放） |
| partial temporary 的新內容／missing pin 不能續刪；E01/E02 | test_e01_partial_temporary_unreviewed_changes_or_missing_pins_need_attention（exact removed／changed／added／remaining、缺 retained 證據、不再改檔、guard 保留） |
| 原ID/位置/原因/relations/PR與真retained；E01/E02 | test_e01_original_ids_remain_searchable_with_location_reason_and_pr（同測試移除實際ref，確認列為unavailable） |
| TASK_OWNED／原TaskDaemon不變 | test_e01_task_owned_resources_are_retained；原test_external_cleanup_retains_unmerged_commit_and_recovers_after_restart／test_terminal_cleanup_requires_proof_before_journal_path_is_cleared |
| legacy只讀、config解析、planner只stop、跨processguard | test_e01_legacy_apply_is_disabled_and_auto_cleanup_still_loads、test_e01_fanout_stops_planner_and_keeps_worktree、test_e01_guard_refuses_legacy_writes_on_reserved_and_cleaned_resources |
| planner stop 需確認與全數 tasks 啟動；失敗保留 plan 供 retry；E01 | test_e01_fanout_without_confirmation_keeps_planner_loaded、test_e01_fanout_failed_start_keeps_planner_for_retry（第一個／最後一個 start 失敗）、test_e01_fanout_stops_planner_and_keeps_worktree（stop frame 恰一次） |
| retirement／cap／managed carrier 不遺失；E01/E02／§23 | test_e01_confirmed_planner_stop_frees_capacity_and_worktree_stays_reclaimable（cap=3、next start、reviewed worktree cleanup）、test_e01_unconfirmed_planner_stop_stays_counted（ACK／still loaded／read failed）、test_e01_absent_session_capacity_follows_carrier_receipt（reclaim／already absent／retained）、test_e01_absent_session_without_worktree_leaves_cap、test_e01_retired_session_refuses_send_resume_and_same_id_start（兩 statuses／generation mismatch／registry recovery）、test_e01_legacy_worktree_remove_keeps_runtime_retired（Git remove 成功／拒絕都不復活退休 runtime） |
| 全部 runtime absent 仍可 reviewed 釋放 cap；E01/E02／§23 | test_e01_all_absent_host_releases_capacity_without_external_mutation（main checkout／carrier 與 branch 皆 absent、cap=1、preview 純讀、零 host mutation／step／tombstone、next start 可行）、test_e01_absent_runtime_with_retained_carrier_cannot_enable_bookkeeping_apply |
| capacity 只作 bookkeeping，舊 registry／start claims 不退化 run；E01/E02／§23 | test_e01_host_cleanup_old_rows_never_fail_capacity_projection（cleaned／failed／superseded／removed／uncertain／starting／unknown，只有 active 退休；不計數 row 原樣保留，pending carrier retain）、test_e01_capacity_retirement_only_changes_counted_set（task／starting／全部不計數 statuses，registry byte-identical） |
| capacity race／failure／crash，不改成功 cleanup effect；E01／§23 recovery | test_e01_capacity_changes_after_validation_do_not_degrade_reclaimed_worktree（generation／missing／task／starting；branch 明確保留、WT succeeded／tombstone／cleaned，不 uncertain）、test_e01_capacity_registry_failure_never_fails_a_cleanup_run（run 開頭／finalize，refusal／I/O）、test_e01_capacity_retirement_replays_once_after_finalize_crash（before／after retirement、resume 只寫一次）、test_e01_confirmed_planner_stop_reports_capacity_refusal_honestly（confirmed stop 仍 true，capacity false 與 reason） |
| retirement read／write 不可用仍保持成功 cleanup；E01／新版 §19 recovery | test_e01_capacity_registry_io_failure_records_bookkeeping_without_changing_outcome（helper 真正 read／write failure，沒有全域 Path patch、不抹除 WT tombstone／receipt） |
| legacy confirmation／read-only audit；E01 | test_e01_legacy_mutations_require_confirmation_before_writes（planner／relay／merge／remove／failover／permissions／approve／verification）、test_e01_legacy_cleanup_disabled_apply_never_writes_with_auto_cleanup、test_e01_legacy_cleanup_evaluation_never_rehydrates_worktrees（confirm=false／true 都不寫） |
| boundedread／serialization／deadline | test_e01_previews_serialize_per_host_and_share_read_deadline |
| multi-host apply 每 item 只讀自己的 host；E01/E02 | test_e01_multi_host_apply_observes_only_each_items_host（另一 host terminal read 永不回覆；healthy session／worktree／branch 均成功，unavailable 資源保留；只有初始 preview／全 plan 驗證付該 host deadline） |
| removed host 的歷史仍可 preview／read，無 live call；E01/E02 | test_e01_removed_host_history_is_retained_without_live_calls（work-item initial／only snapshot、configured items apply 正常；SSH／terminal／runtime／guard audit；實際 retained rows 在 host 移除後列 unavailable） |
| removed host 不漏 creation identities／branch／carrier；E01/E02／§23 inventory | test_e01_removed_host_keeps_every_creation_identity_and_apply_is_read_only（checkpoint／task／repair／registry 四種來源，work-item／checkpoint／integration／historical host targets，移除前後 ID 相同；每 item snapshot 與混合 host apply 無 removed-host client／SSH call，全部 retained；healthy session／worktree／branch 成功） |
| 僅有失敗 prepare 的 removed host 仍可讀；E01/E02／§23 inventory | test_e01_removed_host_known_only_by_failed_prepare_remains_inspectable（真 Git area create 後中斷，無其他 history rows；host／integration target IDs 一致、全部 retain、零 BAT／SSH call，真正未知 host 仍 UNKNOWN_HOST） |
| attachmentreplicas只豁免exact manifest／exacttemps | test_e01_attachment_replicas_are_removed_without_discard_scope、test_e01_edited_or_extra_replica_content_counts_as_uncommitted、test_e01_replicas_without_manifest_are_ordinary_content、test_e01_replica_anomalies_require_reviewed_discard（missing/link/hardlink/directory）、test_e01_replica_edit_after_preview_is_stale、test_e01_lost_replies_reconcile_each_cleanup_phase（discard.replica）、test_e01_exact_temporary_requires_creation_markers_and_never_sweeps、test_e01_empty_integration_temporary_has_exact_intent_and_no_restore_promise |
| acceptedauthority由server記錄／public request retry／載體不被guard退休 | test_e01_accepted_authorization_is_server_recorded（HTTP 422、persisted actor/scopes/choices、同key retry）、test_e01_accepted_authority_survives_key_rotation_and_carrier_stays_usable |
| migration原histories／DDL不占user_version／keep無sweep | test_cleanup_migration_is_atomic_additive_and_preserves_history（version 1與3、第二次open不變）、test_e01_keep_defaults_reject_purge_and_never_sweep_by_name |
| §10三入口／§19Dashboard | test_e01_cleanup_adapters_share_the_action_contract；Playwright（含lostreply/reload同key） en/zh-TW/390px #/cleanup與workitementry／無restore／無null/undefined/[object文字 |
| Part B延期 | taskcoordinator/reservation、TaskDaemonbackfill、restore/lostadd新tests；**container不屬Part B**另規格 |

Rewrite舊legacyapplytests，不skip；保留mutation-table、connector-made BAT worktree禁令、unprovenpush回歸。
報告uv run ruff check .／全uv run pytest -q的exactsummary；app.js用.mjs做node --check；Playwright兩語390px。

## 尚未涵蓋

- **主線既有 capacity 邊界**：本包不改平行 explicit stop action 的 registry 回寫、BAT exit 的自動投影，或 uncertain start 未占 cap 的舊規則；本包新增 retirement 只依 confirmed stop／reviewed carrier facts。Task stop／cleanup 的狀態與 TaskCoordinator 改動仍由 owner 套件處理。
- **Stuck starting claim 回收**：本包保留 session／carrier 與 counted slot，不以 meta=null 釋放。#37 的 start-claim eligibility／reconcile 在 rebase round 銜接，不在這輪另建 takeover。

- **Part B**：coordinator准入／reviewed taskleftovers、TaskDaemon共用finalize與舊事件backfill、restore action/tool/CLI/button。
- **Container退休／retained store**：不屬A或B。Clone／area全刪風險較高，§23本包只回收session/worktree/temporary；另spec。
- **refs/batc/*刪除／GC／永久刪除／保留期限**：pins是evidence，無GC刪pins不回收容量。本包keep/forever/false。
- **Cancelled partial reservation 的強制解除／takeover**：cancel 不抹除已 stop／discard／remove 的效果；本包保留 guard 與 evidence，需人工檢視，未提供強制解除 action。
- **Artifacts/fulltranscript archive、taskintegration／外部squashreceipt匯入**：缺adapter就retain，不自造acceptance。
- **大型host immutablepaging、跨hostrestore、remotebranch刪除**：另contract；本包不截斷preview、不掃磁碟。
- **實機能力**：BAT終止證據、canonicalroots、SSH/Python/no-follow、外部writer隔離仍需部署驗證；測試不向實機write。
