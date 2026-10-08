# 整理與復原：回收 managed 資源，保留工作脈絡

日期：2026-10-08。狀態：Phase 2a Part A 實作與驗證。Part B 在 operations-unification
Part A 合併後另開分支。對應計畫 §23 全節、§10、§19、§26 E01／E02、W06 cleanup。
沿用 [OperationService](api-v1.md)、[resource policy](resource-policy.md) 與 [work items](work-items.md)。

整理只回收已符合條件的 runtime、worktree 與暫存。工作項目、checkpoint、回執、原始 ID 與
歷史永久保留。收合、完成、封存、停止執行、整理、刪除遠端 branch 是不同動作。

## 固定來源版本

| 來源 | 固定版本 |
|---|---|
| Connector | 程式基準 `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`；首版規格 `71640f9`；分支 `feat/cleanup`；套件 0.2.4 |
| 計畫 | v1.0，2026-10-06；只引用節號，不複製私人計畫 |
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
| `fanout_from_plan` 對 planner 呼叫上述 cleanup | caller confirm=true 且全部 planned tasks 啟動成功，才用原 stop 路徑停止 idle planner；其他情況保留 planner 供 retry，worktree 一律保留 |
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
| host | configured host | inventory（含 gone）、registry、已知 checkpoint／integration／task intent；不掃 managed roots 或磁碟 |

Integration apply 先由 `params.preview_id` 找原 preview；handoff 先由 `target.operation_id` 找 apply，
再沿同一條鏈找 preview。把 preview ID 與 preview operation ID 都加入 refs，再展開所有 source IDs。
三種 operation target 取得同一批 source／area／pins／repair／session；work-item links 的 integration
operation 也用同一規則。只使用本次 snapshot 已載入的 operation rows，不逐 item 另查 journal。

範圍外的 active execution／command／有效 integration preview／resumable apply 也檢查依賴。
History link 不是實體需求；未完成工作若有 command／operation 真正需要內容，列 content-required
consumer。所有 consumer 從 authoritative tasks、commands、operations、previews 算出，不另存 consumers 表。
不透明附件參照永遠保留，不能當作 remote path。

原 session ID（host/session_id）、task／command／work item／checkpoint／operation ID 不改。
Worktree 使用共用 `resource_ids.worktree_id`：canonical JSON `["worktree",host,intent_type,intent_id,slot]`
的 SHA-256 前 32 hex 加 `wt_`。Checkpoint 為 checkpoint.continue／operation_id／worktree；repair 為
integration.handoff／operation_id／repair；task external 為 task／task_id／external_worktree；BAT-made
為 registry／session_id@created_at（原 registry 值）／worktree。Warm reuse、reviewer、failover、後續 reuse
追第一個 creation slot，沿用 ID。Observation 使用相同函式，rebase 時共用。
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
| BAT-made connector worktree | 原 registry creation／worktree create 回執、BAT binding、common dir／managed clone | 有充分建立證據才經 SSH 非 force remove；不用 rehydrate／BAT remove | 原 branch／HEAD、來源 session、retained ref |
| task-owned session／worktree／branch | task IDs、branches／commands、registry、external_worktree_path、共享 owner | Part A **永遠 TASK_OWNED**；Task Service 原 terminal cleanup 不變 | 原 task facts；Part B 才投影 TaskDaemon tombstones／refs |
| local_branch | 原 prepare intent＋exact refs/heads/batc/cp-* 或 batc/fix-*，repo／branch／old SHA | 已送達、無 checkout／consumer、retained ref 可讀時 update-ref -d exact-ref expected-old-SHA CAS；無 branch -D | retained HEAD；release_undelivered 的原 branch 保留 |
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
| OBSERVATION_UNAVAILABLE | BAT／SSH／host 讀不到、超時、無可靠 dirty／runtime 資料 | 不能；讀取失敗不是 clean／absent |
| ACTIVE_WRITER／SESSION_WAITING | streaming／writer、pending question／permission、queued turn | 不能；先用原控制路徑處理，再 preview |
| COMMAND_UNRESOLVED | start／stop／send／prepare／push 未完成或 uncertain，即使 parent cancelled／failed | 不能；先由原 owner reconcile |
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
不可量測 bytes=null，不能把留下的 Git objects 算回收。沒有可執行 reclaim item 時 ready=false。

### Signed token／fingerprint

TTL **15 分鐘**（integration 是一小時）。Wire format `v1.<base64url(canonical payload)>.<base64url(HMAC)>`。
Canonical JSON 用 operations._canonical；key 為 HMAC-SHA256(admin token bytes,"batc.cleanup.preview.v1")，
signature 覆蓋 v1 與 payload bytes，constant-time compare。Payload 固定 actor／target／choices／fingerprint、
policy/contract/config digest、iat/exp（UTC integer seconds，exp=iat+900）。preview_id 為 actor/target/choices/
fingerprint/iat canonical hash 前 32 hex 加 clpv_。Admin token 輪替使尚未接受的 token 無效；token 不授予 scopes。
已接受的 operation params 有 server-only authorization；key 輪替不撤銷 accepted／resumed plan。
尚未送任何 external step 就過期仍拒絕；已送 steps 先 reconcile，不重授權。

Fingerprint 包含完整 resource 集合（包括 retain）、ownership/generation/path、content／dirty bytes/type、
refs／registration／merge state、writer/pending、commands／global consumers、receipt coverage、retention rules、
choices／steps；排除 heartbeat／抓取時間／讀取次數／顯示語言。
Apply 在首個 mutation 前重新計算**整份** snapshot；之後每 item 的 mutations 前只核對該 item／consumers
（及自身已證實的 planned transitions），不 O(n²) 重讀所有剩餘資源。任何外部變動 PREVIEW_STALE，不能換 plan。

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
Local branch 的 only=resource_id snapshot 若無 repository projection，不重建 branch item，沿用 reviewed
item（actual is None）；不把 worktree 已完成的 planned transition 誤判 stale。Host 在同一 flock 下、
寫 branch retained ref 前核 exact branch SHA，移動即 PREVIEW_STALE、無 ref 寫入；刪除時仍核 checkout 與 CAS。

| 副作用 | 限制 |
|---|---|
| preserve | refs/batc/retained/<resource_id>/<revision slot> CAS create，已等值成功，不同值 RETAINED_REF_MISMATCH；cat-file 可讀才算 retained |
| stop | lifecycle._stop 新 keyword-only cleanup=False；default 保留舊行為，cleanup=True 時 no retry on disconnect、ambiguous 傳給 OpContext。Preview／apply re-check／最後 pre-stop 共用 service.SESSION_WAITING_FIELDS；所有 pending question/permission/approval、queued message/count、input waiting 都再查，任一為真回 SESSION_WAITING、streaming 回 ACTIVE_WRITER，不送 stop；不直接 shell kill |
| discard | preview 完整 tracked/staged/untracked/ignored manifest；tracked git restore 到 pinned HEAD，untracked no-follow exact unlink；不 clean sweep／force remove。複雜 merge/rebase 若無精確 after manifest就保留 |
| remove worktree | HEAD retained、writer/pending/consumer 消失、dirty=0，managed clone/area 中 git worktree remove exact-path，無 force／prune／rm fallback |
| remove branch | 只 delivered batc/cp-*／fix-*、無 checkout/consumer，retained HEAD存在，update-ref -d full-ref expected-old-SHA CAS；release 的 branch保留 |
| remove temporary | exact intent／markers／完整 manifest，先 pin commit，no-follow exact deletion；未知內容不碰 |
| finalize | receipt／tombstone／aliases／retained／api event 一個 SQLite tx；registry 同 flock標 cleaned，可由相同 tombstone ID重播 |

Result `{preview_id,fingerprint,summary,items,tombstones,next_action}`；retained IDs 在逐項 receipts，實物另由 retained read 核對。Receipts 包含 planned/actual steps、
attempts、before/after、retained SHA/location、discard/release choices／authorization、error、settled_by、relations、PR。
Item status：retained/pending/running/succeeded/already_absent/failed/uncertain/blocked_stale/cancelled。
Operation 沿用原狀態；summary.partial=true，不新增 partial state。獨立 item確定失敗可繼續其他項；
uncertain／stale 停後續。首輪 stale=failed、零 mutation；部分成功後 stale=needs_attention、須新 preview。
暫時失敗且 unchanged plan可 Resume，新 .a2 只在 .a1 confirmed-no-effect 後執行；成功不重做。

### 錯誤代碼

| code | HTTP／下一步 |
|---|---|
| INVALID_TARGET／INVALID_PARAMS／INVALID_REQUEST | 422，修正輸入 |
| NOT_FOUND／UNKNOWN_HOST | 404；原 ID有tombstone仍可查 |
| FORBIDDEN／DISCARD_SCOPE_REQUIRED | 403；discard admission缺cleanup_discard，不用於resume |
| PREVIEW_TOKEN_INVALID | 409，格式／signature／rotated key不符，重preview |
| PREVIEW_MISMATCH | 409，actor／target／choices／precondition與token不符，重preview |
| PREVIEW_EXPIRED／PREVIEW_BLOCKED | 409，過期／ready=false |
| PREVIEW_STALE | 409或operation error，live state changed；首輪回fingerprint已變，item階段回resource已變；重preview比較原預覽 |
| PREVIEW_TOO_LARGE | 413，改較小scope，不截斷執行 |
| RESOURCE_CLEANED／CLEANUP_IN_PROGRESS | 409／policy refusal，原generation已清理／reserved |
| 共用ownership／destination／TIER_DISABLED／NO_MANAGED_ROOT／GIT_RUNNER_UNAVAILABLE | 沿用原code，保留不越界 |
| DISCARD_MANIFEST_UNAVAILABLE／RETAINED_REF_MISMATCH／RETAINED_CONTENT_MISSING | 409，無完整discard／保留證據，停止移除 |
| WORKTREE_REMOVE_REFUSED／REF_CHANGED | 409，非force Git拒絕／CAS不符，保留回執重preview |
| STOP_UNPROVEN／EXTERNAL_EFFECT_UNPROVEN／UNCERTAIN_UNRESOLVED | uncertain／needs_attention，讀回不重送 |
| LEGACY_CLEANUP_DISABLED | 409，改用batc resource-cleanup |
| IDEMPOTENCY_CONFLICT／IDEMPOTENCY_KEY_REQUIRED／NOT_RESUMABLE | 沿用OperationService |

## Crash／lost-reply（Part A；restore列為Part B）

所有外部call用OpContext.step，step intent commit後才送。未決step先reconcile再看cancel；不能因
parent cancelled/failed把它當成沒發生。遠端程序仍在／身份不明時不能因本機SSH退出重送。

| 步驟 | 讀回／可否重送 |
|---|---|
| preview reply lost | 純讀重取；沒有preview row要刪 |
| accepted reply lost | 同key查同operation |
| validate／guard後crash | 查固定plan／registry marker，未送出steps仍受initial expiry；有step先reconcile |
| preserve ACK lost | exact ref=planned SHA且object可讀補成功；ref缺且原程序已结束才CAS RERUN；不同SHA拒絕 |
| stop ACK lost | 已證實start、host健康、相同generation的終止證據才成功；單次meta=null／無tab不足；unknown不重stop |
| discard partial／lost | 每entry核before／expected-after digest；已after不重丟，第三種state stale；同manifest且原程序结束才續 |
| worktree remove lost | retained仍在，path與registration都消失即成功；只有path消失不prune；仍原binding/clean且前程序结束才非force重送 |
| branch CAS lost | ref absent且retained old SHA在即成功；still old且無writer可CAS retry；第三種SHA stale |
| temporary partial／lost | 全部消失且pins仍在即補成功；仍完整before且原程序結束才續。部分刪除／marker損壞留uncertain，不猜測或掃剩餘檔案 |
| finalize crash | steps讀回可補finalize；同tx／unique keys防重複event／aliases；registry同值對帳 |
| cancel／Resume | 成功item留存，未送出cancel；uncertain先讀回。Confirmed未送出的reservation釋放，未知outcome不解鎖。OpContext.failed不自動retry；confirmed-no-effect才另建.a2 |
| Part B restore add lost | exact新worktree/branch/HEAD/tree對上intent才補成功，未知目的地不認領；不重建runtime |

## Journal／migration

原Journal、WAL/FULL、single owner。新增idempotent DDL，每次open都以BEGIN IMMEDIATE一個tx建表/index；
不讀、不寫user_version，中斷rollback可重跑。版本號只供跨package分配的一次性data steps使用：
main為1、delivery為2–3、observation為4。DDL若相對遞增版本會跳過其他package的data steps；
Part A只有建表/index，不占版本號。
不改operations table，不host calls、不刪舊rows／registry／events，不重編cursor。

| 表 | 固定事實／鍵 |
|---|---|
| cleanup_runs | operation_id PK/FK、preview_id、token_hash、fingerprint、immutable document、accepted_actor/scopes/choices、validated_at、supersedes_operation_id；validated snapshot是新事實；authorization沿用operation params接受時的固定metadata |
| cleanup_receipts | (operation_id,resource_id) PK，item_order、plan、status、before/after、attempts、error、settled_by、retained IDs／timestamps；resumed_by從原api_events附加 |
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
auto_cleanup只保留config解析，deprecated且不啟用writes；worktree_merge/remove仍是explicit動作，只共享guard。
Fanout planner 只有 caller `confirm=true` 且每一個 planned task 都成功啟動，才經原 stop 路徑停止。
未確認、任一 start failed 或 loop 提早停止，都保留 loaded planner／原 plan 供 retry；不能因 starts
回傳 error 或只是部分成功就 stop。回 `planner_cleanup={stopped:false,reason,worktree_kept:true,
next_action:"batc resource-cleanup"}`，reason 區分 confirmation／start failed／incomplete loop。
成功 fan-out 的 stop 仍核 tier／policy／streaming，stop refused／error 也保留 reason 與 next_action。
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
| canonical/policy/preserve/nonforce/CAS；E01 | test_e01_every_mutation_rechecks_policy_and_canonical_destination、test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs |
| 同 apply 的 worktree／branch 回執均成功；移除後 branch 移動先拒絕；E01 | test_e01_preserve_precedes_nonforced_remove_and_cas_checks_delivered_refs（branch snapshot actual is None）、test_e01_branch_moved_after_worktree_removal_is_stale（PREVIEW_STALE、所有 refs 不變） |
| integration 三種 target 同 scope／handoff 完整鏈；E01/E02 | test_e01_integration_preview_apply_and_handoff_expand_to_same_resources（source／area／pins／repair／session 的所有 item fields 相等） |
| crashedcheckpoint/handoff／未決start-stop；E01 | test_e01_crashed_continue_and_handoff_intents_are_discovered_without_adoption、test_e01_pending_start_stop_and_waiting_sessions_are_retained |
| partsuccess/restart/lostreply；E01 | test_e01_partial_cleanup_resumes_only_unfinished_unchanged_items、test_e01_lost_replies_reconcile_each_cleanup_phase、test_e01_cancel_reconciles_sent_steps_and_releases_only_confirmed_reservations |
| 原ID/位置/原因/relations/PR與真retained；E01/E02 | test_e01_original_ids_remain_searchable_with_location_reason_and_pr（同測試移除實際ref，確認列為unavailable） |
| TASK_OWNED／原TaskDaemon不變 | test_e01_task_owned_resources_are_retained；原test_external_cleanup_retains_unmerged_commit_and_recovers_after_restart／test_terminal_cleanup_requires_proof_before_journal_path_is_cleared |
| legacy只讀、config解析、planner只stop、跨processguard | test_e01_legacy_apply_is_disabled_and_auto_cleanup_still_loads、test_e01_fanout_stops_planner_and_keeps_worktree、test_e01_guard_refuses_legacy_writes_on_reserved_and_cleaned_resources |
| planner stop 需確認與全數 tasks 啟動；失敗保留 plan 供 retry；E01 | test_e01_fanout_without_confirmation_keeps_planner_loaded、test_e01_fanout_failed_start_keeps_planner_for_retry（第一個／最後一個 start 失敗）、test_e01_fanout_stops_planner_and_keeps_worktree（stop frame 恰一次） |
| boundedread／serialization／deadline | test_e01_previews_serialize_per_host_and_share_read_deadline |
| attachmentreplicas只豁免exact manifest／exacttemps | test_e01_attachment_replicas_are_removed_without_discard_scope、test_e01_edited_or_extra_replica_content_counts_as_uncommitted、test_e01_replicas_without_manifest_are_ordinary_content、test_e01_replica_anomalies_require_reviewed_discard（missing/link/hardlink/directory）、test_e01_replica_edit_after_preview_is_stale、test_e01_lost_replies_reconcile_each_cleanup_phase（discard.replica）、test_e01_exact_temporary_requires_creation_markers_and_never_sweeps、test_e01_empty_integration_temporary_has_exact_intent_and_no_restore_promise |
| acceptedauthority由server記錄／public request retry／載體不被guard退休 | test_e01_accepted_authorization_is_server_recorded（HTTP 422、persisted actor/scopes/choices、同key retry）、test_e01_accepted_authority_survives_key_rotation_and_carrier_stays_usable |
| migration原histories／DDL不占user_version／keep無sweep | test_cleanup_migration_is_atomic_additive_and_preserves_history（version 1與3、第二次open不變）、test_e01_keep_defaults_reject_purge_and_never_sweep_by_name |
| §10三入口／§19Dashboard | test_e01_cleanup_adapters_share_the_action_contract；Playwright（含lostreply/reload同key） en/zh-TW/390px #/cleanup與workitementry／無restore／無null/undefined/[object文字 |
| Part B延期 | taskcoordinator/reservation、TaskDaemonbackfill、restore/lostadd新tests；**container不屬Part B**另規格 |

Rewrite舊legacyapplytests，不skip；保留mutation-table、connector-made BAT worktree禁令、unprovenpush回歸。
報告uv run ruff check .／全uv run pytest -q的exactsummary；app.js用.mjs做node --check；Playwright兩語390px。

## 尚未涵蓋

- **Part B**：coordinator准入／reviewed taskleftovers、TaskDaemon共用finalize與舊事件backfill、restore action/tool/CLI/button。
- **Container退休／retained store**：不屬A或B。Clone／area全刪風險較高，§23本包只回收session/worktree/temporary；另spec。
- **refs/batc/*刪除／GC／永久刪除／保留期限**：pins是evidence，無GC刪pins不回收容量。本包keep/forever/false。
- **Artifacts/fulltranscript archive、taskintegration／外部squashreceipt匯入**：缺adapter就retain，不自造acceptance。
- **大型host immutablepaging、跨hostrestore、remotebranch刪除**：另contract；本包不截斷preview、不掃磁碟。
- **實機能力**：BAT終止證據、canonicalroots、SSH/Python/no-follow、外部writer隔離仍需部署驗證；測試不向實機write。
