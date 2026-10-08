# Sessions 與歷史：觀測、關係與來源證據

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §08、§10、§11、§19「Sessions 與歷史」、§28「02 observation」，工作包 W03 剩餘部分，驗收 B01、B02、B03。

Phase 1 規格已審查。Phase 2 分兩步：Part A（本次）實作伺服器、journal、HTTP/MCP/CLI、skills、文件及伺服器驗收；Part B 在後續分支實作 Dashboard。下列 Dashboard 畫面與瀏覽器 reopen／catch-up／SSE 去重驗收都屬 Part B。共用操作、資源政策、checkpoint 與管理資料分別沿用 [api-v1.md](api-v1.md)、[resource-policy.md](resource-policy.md)、[checkpoints.md](checkpoints.md)、[work-items.md](work-items.md)。

## 固定來源版本

| 來源 | 固定版本與本規格使用處 |
|---|---|
| Connector | `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`，本工作開始時的 `HEAD` 與 `origin/main`；branch 為 `feat/observation`。套件版本仍為 `0.2.4`。本文件中的「現有」均指這個 commit。 |
| 計畫 | v1.0（2026-10-06）；以章節及驗收編號引用，不複製私有計畫。 |
| BAT | `b7419892fbc9946799b64cca24c2ec8c7fa15c42`；不代表每台主機都已安裝此版，實際 `serverVersion` 另存於掃描證據。 |

BAT 協定判讀依據如下；Phase 2 開始時重新比對 main 的來源版本及 orchestrator 配發的資料步驟編號，不追逐上游最新版。

| BAT 原始碼（上述固定 commit） | 確認的邊界 |
|---|---|
| [node-sidecar/src/handlers/claude-session.mjs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/src/handlers/claude-session.mjs) 的 `claude.getSessionMeta`、`claude.getSessionState`、`claude.clientResume`、`claude.stopSession` | Meta 可回 null；Claude state 查詢遇缺少 cwd 的記錄會刪除 runtime map entry。`clientResume` 在 session 不存在時會走 resume。Stop 移除 runtime 記錄，不證明對話／資源永久刪除。 |
| [node-sidecar/src/lib/state.mjs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/src/lib/state.mjs) 的 `buildSessionMeta` | 提供 `sdkSessionId`、cwd、`runtimeStatus`；`isStreaming` 也包含 runtime 啟動中的狀態，不能直接解讀為模型已輸出文字。 |
| [src-tauri/src/commands/workspace.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/workspace.rs) 的 `workspace_load` | Workspace 文件可能不存在；null 不能當成完整而成功的空列舉。Connector 實際傳送 profile 的入口見 `service._workspace`。 |
| [src-tauri/src/commands/git.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/git.rs) 的 `git_get_status_native` | 呼叫一般 `git status --porcelain --untracked-files=all`，失敗回空陣列。觀測不走這條 dirty 查詢；沿用 `checkpoints.source_state_script` 的 `git --no-optional-locks`。 |

## 現有與新增行為差異

| 能力 | 現有程式與限制 | Phase 2 行為 |
|---|---|---|
| 目錄 | `inventory.Inventory` 使用 read-only `Fleet`；`hosts_observed`、`sessions_observed` 保存最新觀測，主機失敗保留舊列。`list_sessions` 有 keyset 分頁。 | 保留這套目錄；補 profile、掃描涵蓋範圍、欄位觀測時間、跨專案篩選及關係摘要。 |
| 發現來源 | `service._host_sessions` 聯集 workspace agent tabs 與 active registry entries。Transcript 查詢只補已知 Claude session 的活動時間，不發現所有歷史或人工無 tab sessions。 | 聯集 journal 已知的 session IDs、既有觀測及上述來源，無 tab／歷史 session 可獨立閱讀；明列未掃範圍。 |
| 歷史 | `api_events.seq` 已是單一持久游標，`Journal._event` 同交易投影 task events。尚無 session／worktree timeline；用 `resource_id` 篩事件只會找到直接以它為主體的事件。 | 加上事件對資源的索引與證據 envelope；每個資源的歷史包含相關 operation、command、checkpoint、run、receipt 及連結。GET 只讀 journal。 |
| 步驟 | `operations.OperationService._step_start/_step_restart/_step_done/_step_status` 更新 `operation_steps`，沒有步驟事件。 | 在這些既有交易中追加步驟事實；不改步驟執行、reconcile 或寫入權限。 |
| 關係 | `branches`、`commands` 保留多個 task 與 session；`tasks.session_id`／`reviewer_session_id` 是當前指標。`registry.claim_warm` 轉移最新 owner，另留 `warm_from_task_id`。 | 提供時間及 command 範圍的歷史關係，當前 owner 與歷史參與分開；不把 registry 的最新 `task_id` 套到舊事件。 |
| 狀態 | 已有 loaded、streaming、has_tab、gone、stale。但 null meta 時 `_host_sessions` 填 `streaming=false`；stale 主要於 `Inventory._session_out`／`_host_stale` 讀取時計算。 | 新增有證據的多軸狀態，未觀測為 null／unknown；主機 freshness 在讀取時推導，只記 session 自身的 stale 轉換。Gone 只表示不再列舉。 |
| 來源 | `operations.actor/entry`、checkpoint actor、work item links actor 已有；task events 的 `api_events.actor` 通常是 null。`command_reconciliations.actor`、`ted_actions` 有 caller 自報證據。 | 每事件回相同 provenance 欄位；驗證主體、觀測者及自報 actor 分開。缺資料明示 unknown。 |
| Dashboard | `viewSessions` 只有 host/access 篩選；`viewSession` 有訊息、`started_from`、工作項目及 checkpoint。`streamEvents` 重連續讀，但不先排除重複 seq；`start` 先取 head，沒有完整 reopen 驗收。 | 加跨專案目錄、關係、timeline 與掃描證據；Part B 補 baseline／catch-up／SSE 交接及重複防護測試。 |

操作統一、delivery、cleanup 是平行工作包。本包不實作 Task Service actions／共用 gate、PR metadata／merge preview／新的 deployment history、tombstone／retained refs／restore。Phase 2 只接讀當時已在 main 的正式 journal 契約；未合併的 branch 不是來源。

## 資源身分與關係模型

### Session 與 worktree

Session 的 `resource_id` 沿用 `host/session_id`，`session_id` 是完整 BAT ID；provider 名稱或 provider native ID 都不是列表 key。HTTP 的既有 `{host}/{id}` 即此 ID 的兩段，接受 URL encoding，不用前綴匹配。保留 `profile_id`、`workspace_id`、provider 及 `provider_native_id`（目前可從 tab／meta 的 `sdkSessionId` 取得；未提供則 null），移動 tab 或改標題不換資源 ID。

現有設定每個 host alias 只有一個 `HostConfig.profile_id`。掃描 scope 固定這個 alias 的 remote binding 與 profile；journal 保存 binding 的非敏感識別及版本。不同 profile 可用不同設定 alias，不能把相同 provider 的列合併。若同一 alias 改指別的 remote binding／profile，停止覆寫舊身分，回 `DISCOVERY_SCOPE_CHANGED`、保留舊觀測並標 stale；使用新 alias 掃新範圍。本包不替 host alias 改綁建立自動合併機制。舊 journal 未記 profile 的歷史標 `profile_id: null`、`identity_evidence: legacy`，不得把現在的設定追認為當年的 profile。

Worktree 只有在 journal 或可信 registry 有明確建立 binding 時才建立讀模型。使用共享 `resource_ids.worktree_id(host, intent_type, intent_id, slot)`：將 `["worktree", host, intent_type, intent_id, slot]` 以 `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` 編碼，再回 `wt_` 加 SHA-256 前 32 hex。Cleanup 使用同一個函式，先合併的包提供模組，另一包原樣引用。

BAT-made worktree 的建立根節點由共用純函式 `resource_ids.registry_worktree_intent(entries, host, session_id, lead_of=None)` 解析。依 failover_of／shared_worktree_from／lead_session_id 回溯；reviewer 缺 lead 時可用 journal task lookup。Registry 順序不影響結果；缺 parent 停在最後已知 entry，cycle 為 unknown。根節點屬 connector external worktree、checkpoint、integration 或缺 created_at／path 時不鑄 registry ID；created_at 使用載入 JSON 值的 str()，不重新格式化。Observation／cleanup 共用此解析，其他建立 intent 沿用既有 journal binding。

| 建立來源 | intent_type | intent_id | slot |
|---|---|---|---|
| Checkpoint continue | `checkpoint.continue` | continue operation_id | `worktree` |
| Integration repair | `integration.handoff` | operation_id | `repair` |
| Task external worktree | `task` | task_id | `external_worktree` |
| Connector session 的 BAT-made worktree | `registry` | `session_id@created_at`（created_at 完全沿用 registry 儲存值） | `worktree` |

Warm reuse、reviewer、failover successor 或後續 continue 指回首次建立的 slot，取得相同 ID；同 path 的新 creation intent 取得新 ID。Worktree 身分表保存這個 ID 及 binding/path/branch 證據。只有 cwd／branch 或無法證明建立 slot 時不猜 ID，不發送 rehydrate；這是觀測身分，不是 ownership grant。

未被 inventory 看過但已有 command／checkpoint／run 證據的 session 也可取得詳情、關係及 history：`observation: unknown`、`has_tab: null`，並保留真實 ID。未知完整 ID 回 404；已知而 gone 的 ID 仍回 200。Registry 所知但尚未成功列舉者也保留 journal identity，未觀測的欄位維持 null。人工無 tab session 若從未被 BAT 可讀介面或 journal 記錄過，列入 outside scan，不能宣稱已發現。

### Execution 與 session 的使用區間

Execution 沿用 Task Service `task_id`，API 補 `execution_id = task_id`，不另建 tasks database。既有 `branches.branch_id` 是派工分支識別，不是 Git branch。

| Relation 欄位 | 定義 |
|---|---|
| `relation_id`、`execution_id`、`session_resource_id` | 一段使用關係的穩定 ID、原 task ID、資源 ID。`relation_id` 由 execution/session/role 與起始 command ID 衍生；舊資料沒有 command 才用 branch ID 作 anchor。Pending → bound 保持同 ID，後續取得 branch ID 只補關聯。 |
| `branch_id`、`role`、`reason` | 沿用 lead／reviewer 等真實角色與 `start`、`warm_reuse`、replacement／failover 原因。PM branch 沒有 BAT session 時不製造 session 列。 |
| `follow_up_of_execution_id`、`parent_relation_id` | 只來自明確 `tasks.parent_task_id`／continuation 與 journal replacement 證據。Follow-up 的 lead 仍是 lead，以此欄標示後續工作，不因 provider 相同就推斷接續。 |
| `start_seq`、`end_seq`、`started_at`、`ended_at` | 半開範圍 `[start_seq, end_seq)`；時間為 UTC。未證明終點為 null；不拿 task 的最新 `updated_at` 當終點。 |
| `start_command_id`、`end_command_id`、`command_ids` | 穩定 command IDs；每 command 明確連到 relation。UUID 不作數值大小比較；範圍依 intent／binding 的 journal seq。摘要不冒充完整清單，完整 command 事實由 history 的 task command kinds 分頁閱讀。 |
| `status`、`evidence` | `pending`（意圖）、`bound`（已綁定）、`closed`；含依據表／ID 及不完整邊界說明。關係不是資源寫入授權。 |

`Journal.warm_candidates`、`BatTaskAdapter.find_warm/_warm_identity/start` 與 `TaskCoordinator._start` 已有同 workstream、乾淨且 HEAD 為已驗證版本的 reuse 檢查。`commands.payload.warm_session_id`、新 task 的 `branches.reason=warm_reuse`、`task_capabilities_revoked`、`warm_base_recorded` 均已記錄；舊 task 的 branches／commands 不會被 registry owner 轉移刪掉。但目前沒有明確舊／新 execution 的完整區間及 binding event，`command_bind_session` 也沒有事件。

Phase 2 在既有 journal 寫入點補 `relation.opened`、`relation.closed`、`relation.bound`；同交易保存舊／新 task、role、session、binding command 及來源證據。Start intent 是 pending，只有原流程確認身分後才 bound。Warm claim 與 SQLite 不共用交易：以已持久化的 start command 連接 claim 結果；當中斷時保留 pending／unknown，由既有 Task Service recovery 確認後補記事實。讀 history 不執行 recovery、claim、start 或新派工。

Execution 終態／明確 replacement 可關閉該已確認使用區間；不能由 session idle、host 離線或 registry 最新 owner 推斷終點。Task 結束後又有明確帳本活動時另開區間。舊資料依每 task 的 branches、commands、events 回填，確定的 command 歸屬保留；只有開始下限而沒有結束事實就保留 null。Reviewer 歷史即使當前 `reviewer_session_id` 清掉仍可見。

工作項目的直接 link 沿用 `work_item_links`，unlink 的 actor、時間與 operation 保留。Timeline 對 event 的 work item 歸屬固定在當時的 link 區間；後來 unlink 不抹去舊關係，後來新增 link 不回寫舊事件。目錄的「曾經關聯」可經 task／operation／checkpoint 的明確 link 找到 session，必須標 `via`；單靠同 project／repo 不建立隱含連結。

## 狀態分類

`state` 分軸回傳；舊扁平欄位保留相容，新畫面與工具以 `state` 及其 evidence 為準。Bool 欄位允許 null，不把未觀測填成 false。各軸有 `observed_at`、`source_ref`、`stale`，一次讀 meta 失敗不能刷新上一個 streaming／pending 事實的時間。

| 軸與機器值 | 顯示／可用證據 | 不可推斷 |
|---|---|---|
| `connection: connected / not_connected / unknown` | 最近一次有效 host 掃描成功／失敗／未掃；不以 inventory idle socket 已關閉當斷線。 | 斷線不等於 session 結束。 |
| `loading: loaded / not_loaded / unknown` | Meta 有有效物件／成功回 null／查詢失敗或未查。Null 只證明這次沒有載入記錄。 | 未 loaded 不等於刪除、可安全重新啟動。 |
| `tab: present / no_tab / unknown` | 成功且完整的設定 profile workspace 文件有／沒有該 ID；或尚未取得文件。 | 無 tab 不等於無 session；無 tab 也不授予管理權。 |
| `activity: streaming / starting / not_streaming / unknown` | 有效 meta 的 streaming 與 runtime status，保留原始機器值；未提供或失敗為 unknown。 | `not_streaming` 不等於工作完成；`starting` 不寫成已開始輸出。 |
| `lifecycle: active / ended / unknown` | Active 需有效 runtime 證據；ended 需明確、可連到此 runtime／資源的終止回執或具有已驗證語意的 provider 終態，附 `end_scope: runtime / resource`。 | Turn 完成、task done、meta null、registry cleaned、gone 都不證明 session 結束或永久資源刪除。 |
| `enumeration: present / missing / gone / unknown` | 沿用連續兩次成功且完整列舉缺席才 gone；失敗／部分掃描不累加 misses。 | Gone 顯示「不再列舉」，不顯示「已刪除」。 |
| `freshness: fresh / stale` | 保留 `stale_reason`：`never_observed`、`host_unreachable`、`host_not_refreshed`、`not_enumerated`、`gone`，新增 scope／partial 原因。 | Stale 不覆寫最後已知狀態、actor 或 identity。 |
| `provenance`、`api_access`、`isolation` | 沿用 `resource_policy`，來源、可寫能力、隔離各自呈現。 | 新 relation、人工 actor 標籤、Git author、history 完整度均不提升寫入能力。 |

目前 main 沒有正式 journal stop 回執；interrupt／abort 是 turn interruption，不是 session 終止。未來 stop 若證明卸載 runtime，仍可能保留 transcript／tab，才可顯示「已證實 runtime 結束（可保留對話）」。目前 main 沒有保證覆蓋所有人工 session 的 resource 終態來源，無證據時 lifecycle 保持 unknown，不能為了填 ended 而呼叫 stop 或 resume。若後續 main 有正式 cleanup tombstone，它證明哪個實體被整理就顯示哪個 scope，不宣稱整段歷史消失。

## Discovery scope 的可見證據

延伸 `Inventory.refresh_host`，同 journal 的 `discovery_latest` 只保存每 `(host, profile_id)` 最近掃描；poll 覆寫 status、times、methods、coverage、outside_scan，不累積每輪 rows。只有 status 或 coverage 改變才追加 `discovery.changed`；`/hosts/{host}/discovery` 回最新 scope 與從事件分頁讀出的近期 transitions。HTTP inventory 讀取不觸發 poll。

| 欄位 | 契約 |
|---|---|
| `scan_id`、`host`、`profile_id`、`binding_version` | 固定掃描範圍；DISCOVERY_SCOPE_CHANGED 時 binding_version 沿用 journal 的 binding 欄位，拒絕改綁後的設定，不呈現為目前已掃範圍。Journal ID 不含 token／真實指紋；API 不暴露 bearer 或 credential path。 |
| `attempted_binding_version` | 僅 DISCOVERY_SCOPE_CHANGED 時出現，記錄被拒絕的設定 digest；其餘成功／失敗不帶此欄位。同 profile 改 URL／fingerprint 後，每次 refresh 都保持拒絕、零 BAT frames，原 binding／身分／歷史保留。 |
| `started_at`、`finished_at`、`last_success_at` | UTC；成功與嘗試時間分開。單 session 另回 `first_seen_at`、`last_seen_at`、`observed_at`，沿用原 timestamp，不把重新讀取時間當觀測時間。 |
| `observer`、`authority` | 已知服務主體 `inventory`、`authority.kind=bat_authenticated_read`、非敏感 credential reference ID／設定版本、BAT 回覆的 protocol／capabilities。只有實際回覆的 authority 才算 verified；scope observe 是讀 Connector，並不證明 BAT token 能掃所有 profiles。 |
| `methods`、`coverage` | 每來源的 attempted／succeeded／failed／skipped、workspace IDs、筆數、activity/pending 是否本輪查過。來源包括 `workspace:load`、meta、安全 state、archive、限定 cwd 的 Claude transcript、registry、journal。 |
| `status`、`complete_enumeration`、`errors` | `succeeded / partial / failed / never_scanned`；redacted 穩定錯誤及欄位失敗。完整列舉只描述本次授權集合，不宣稱掃完整磁碟。 |
| `outside_scan` | 其他 profiles／未配置 hosts、從未列舉或記錄的人工無 tab sessions、任意路徑 transcript、未掃 Codex rollouts、未取得的 Git 狀態、connector 記錄開始之前的歷史，附原因。 |

Cheap poll 沒重讀 archive／pending 時明列 skipped，保留舊值及欄位時間。首次 meta 失敗仍可保存 tab 身分，但 loading/activity 為 unknown；後續失敗沿用舊事實並標欄位 stale。Null／壞 workspace 文件一律不是完整列舉，即使 registry 剛好提供非空 rows 也不增加 missing_count。成功文件僅有部分 enrichment 失敗時，已確認的 tab 列舉仍可成功，相關欄位及來源保持 partial。

Journal／registry 候選在失敗 poll 前已知的身分仍保留；不讀 registry 充當成功 BAT 枚舉。每台 host 的排程與退避沿用 `Inventory.loop`，慢 host 不阻擋其他 hosts。Host 從設定移除時沿用一般列表不列它的行為；journal 歷史保留，已知 ID 的純歷史讀取回 `scope_status: outside_current_config`，不呼叫已移除 host。

Host reachability 沿用 `host.reachable`／`host.unreachable`，host_unreachable／host_not_refreshed／never_observed 的 session freshness 在讀取時由 host row 推導，不為每個 session 寫事件或索引 host flap。只對 session-specific 的 `not_enumerated`、`gone`、scope change 記 `session.stale`／`session.fresh`；相同 reason／觀測版本只記一次，GET 不寫事件。Daemon 停機期間不虛構 poll；host_not_refreshed 在讀取時推導，重啟不補寫每 session 的逾期事件。

## Timeline 的 journal 來源與事件種類

只使用 journal 已保存的事實，不在 GET 時呼叫 BAT、SSH Git、GitHub、registry 或模型，也不由最新 row 拼出過去每一步。保留 `api_events` 為唯一事件序列；新增 `api_event_context`（seq 為 PK，證據 envelope）與 `api_event_resources`（`seq, resource_type, resource_id, linked_at_seq, evidence_ref`，PK 為前三欄，依資源與 seq 建索引）。Relation IDs 在 context 中保存。同一事件可連多個 session／worktree，但某資源的 timeline 用 DISTINCT seq 只回一次。

Operation intent 當下尚不知道新 session／worktree 時，其 context 保持未知；確認 binding 後，在 `resource.bound` 的交易中索引該 operation 先前的事件，`linked_at_seq` 為 binding 事實的 seq。History 同時要求 event seq 及 linked_at_seq 不超過 as_of，已開的 snapshot 不變。`resource.bound` 帶先前事件 refs，提醒 client 重讀該資源的 history，而不是把早期事件重送成新發生；關聯補全不改原 actor／版本／狀態。Task 歷史歸屬依確定的 command／range 處理，不因目前 owner 更換追掛全部 task 事件。

下表「已有」是現有 api event；「補記」是在既有事實寫入交易中加上事件或完整 fields。所有 rows 的順序／分頁鍵均是**全域 `api_events.seq`**，不使用表內 command UUID、step seq 或 timestamp 作次序。Event ID 回 `event_id = seq`，SSE `id` 也用此 seq。

| Event kind | Journal 來源／既有寫入點 | 事件固定 fields 與關聯 | 狀態 |
|---|---|---|---|
| `session.added` | `sessions_observed`；`Inventory._record_success` | resource、scan、first_seen、material snapshot、各欄觀測證據；只表示第一次被 Connector 看見。 | 已有；補 context |
| `session.updated` | 同上 | before/after 或 changed fields、欄位 evidence；額外 field timestamps 保存於最新 observation，timeline context 取當輪已知來源；不因活動 timestamp 更新單獨發事件。 | 已有；補 diff/context |
| `session.gone`、`session.reappeared` | `sessions_observed.missing_count/gone_at`；成功列舉交易 | misses、scan、最後 seen、原身分；重現清除 gone，不重建 ID。現有 reappear 是 `session.updated`，Phase 2 改發專用事件且不雙發。 | gone 已有；reappeared 補記 |
| `session.stale`、`session.fresh` | 保存的 host／session freshness transition | reason、依據 scan/觀測版本、過期與記錄時間。 | 補記；GET 不產生 |
| `host.reachable`、`host.unreachable`、`discovery.changed` | `hosts_observed`、`discovery_latest`；`_record_success/_record_failure` | host/profile、scope、完成度／redacted error；host 層事件不向 sessions fan-out。 | host 已有；scope transition 補記 |
| `operation.accepted/running/waiting_checks/waiting_external/uncertain/needs_attention/succeeded/failed/cancelled` | `operations`；`OperationService.create/_transition` | action、from/to、error code、event actor、entry、target、當時版本與 external refs；結果中有真實 session/worktree 時追加 binding 事實。 | 已有；補 context |
| `operation.step.started/restarted/succeeded/failed/uncertain` | `operation_steps`；既有 `_step_*` | operation ID、step name/seq、保存的 status、摘要或 hash、external ref、reconciled、已知來源／結果 SHA。 | 補記，不變更執行機制 |
| `task.command_intent`、`task.command_accepted/running/settled/uncertain/rejected/cancelled`、`task.command_reconciled`、`task.failover_operator_reconciled` | `commands`、`command_reconciliations`、對應 `events`；`Journal.command/command_status/resolve_send/resolve_failover` | task/command、當時 session/relation、kind/status、message/turn refs、prompt hash；reconciliation 的 caller claim 與可驗證證據分開。 | 已有；補 context |
| `task.command_bound`、`relation.opened/bound/closed` | `branches`、`commands`、關係區間；`add_branch/command_bind_session/change` 與已確認的 reuse/replacement 記錄點 | task、session、role、range、binding command、previous/next execution、reason。 | 補記 |
| `task.task_branch`、`task.state`、`task.paused/resumed`、其他實際存在的 `task.*` | `events` 經 `Journal._event` 同交易投影；`tasks`、`branches`、`observed_verifications`、routing 等作證據 | 原 kind 的結構化摘要、明確 session refs 或當時有效 relation；task 的非 session 里程碑標 execution context，不宣稱每個 session 都做過該動作。 | 已有；完整列出，不受 `work_status` 最近 10 筆限制 |
| `checkpoint.created` | `checkpoints`；`checkpoints._run_create` | checkpoint/operation、source session、擷取版本與當時 HEAD、dirty 三值、excerpt digest、capture actor；不回聊天全文。 | 已有；補 source worktree/context |
| `checkpoint.continued` | `checkpoint_runs`；`checkpoints._run_continue` | checkpoint、operation、新 session/worktree、source session、固定起點、實際 branch；在來源與新資源 timeline 均可見。 | 已有；補 context |
| `resource.bound` | `operations.external_refs`、成功或 uncertain step 中已知的真實 binding | operation、資源、step、checkpoint source、可信度；送字前中斷尚無 `checkpoint_runs` 也能看見預留／已建立資源。 | 補記；intent 不說成啟動成功 |
| `integration.previewed/composed/conflict/resolved/delivered/updated/handoff_started` | `integration_previews`、`integration_receipts`、`api_events`；`integration._receipt_update/_push/_finish` 等 | operation、receipt 的 `(operation_id, seq)`、source kind/id/host、pinned/base/integrated/resolution/delivered SHA、resolver session/worktree、PR 身分；依 checkpoint/run 的明確來源連資源。 | 已有；補當時 fields |
| `work_item.linked`、`work_item.unlinked` | `work_item_links`、`work_items._run_link/_event` | link ID、work item、kind/ref、actor、時間、link/remove operation；間接關係附 via。 | 已有；補 link ID/context |
| `task.external_worktree_retained`、`task.initial_session_vanished` | `events`；`Journal.complete_external_cleanup/mark_initial_session_vanished` | 原 worktree path/branch/ref/commit 或消失的 ID、command evidence；保存原事件語意。 | 已有；不改造成 §23 tombstone |
| `history.backfilled`（預設 live feed 隱藏） | migration 的舊 journal 事實投影 | 原表、PK、可證明的 snapshot、原 timestamp、`backfilled=true`、缺少的歷史；只在沒有對應 api event 時補一筆。 | 補記；不虛構過去 transitions |

以下是**條件式事件種類**；只有對應 writer/schema 已在 Phase 2 開始時的 main 才提供 adapter 及 fixture。表內名稱是 observation 的種類分類，不強迫其他包改名；使用其正式 event kind，無來源就不產生、不宣告 capability。

| 未來事實種類 | 來源及 fields | 本包邊界 |
|---|---|---|
| Task Service operation／step 關聯 | operations unification 的正式 operation-command binding，含 operation、task、command、actor、entry。 | 接讀已合併的契約；本包不建立 task actions 或第二套 gate。 |
| PR metadata、merge preview、後續 deployment history | delivery 正式 journal facts，含 repository/PR、版本、workflow/run/environment、來源／結果版本；只有明確連到 session/worktree 的才入該 timeline。 | 目前 main 的 merge/deploy operation 可按上表顯示；不實作新 provider 行為或猜測關聯。 |
| `cleanup.tombstone`、retained ref、restore | cleanup 正式 tombstone/receipt，含 resource ID、operation、actor、移除範圍、保留 ref/commit、restore 的新實體關係。 | 不掃磁碟補墓碑；不實作 cleanup、refs 寫入、restore；保留歷史身分。 |

### 固定排序與分頁

Timeline 預設新到舊，`ORDER BY seq DESC`；`order=asc` 可逐筆回放。第一頁在 daemon 單一 journal owner 的同步讀取中捕捉 `as_of = api_head()`，查詢只含 `seq <= as_of`。Next cursor 為 versioned opaque token，內容為 `{v, f, a, k}`；f 是 resource/filters/order 的 hash，a 是 as_of，k 是 last_seq。DESC 下一頁 `seq < last_seq`，ASC 下一頁 `seq > last_seq`，一律限制 `seq <= as_of`。預設 limit 50，上限 200，非法值回 422；換 resource／kind／時間／順序不能沿用游標。`next_cursor=null` 表示這個 snapshot 讀完；回 `has_more`、`count`、`head_cursor`。

`kind` 為精確種類集合，`since`／`until` 以 UTC occurred_at 篩選，但排序仍按 seq。歷史事件時間可以相同或晚補；晚補的舊事實按新 seq 顯示並標記原發生時間，不重排已讀頁面。GET 不因查詢而新增事件。

Relations 的 key 為 `(start_seq, relation_id)`，預設 ASC；未知開始的 legacy row 用排序值 0，但輸出 start_seq 仍是 null。Cursor 帶 resource/execution、filters、as_of 與 last key。關閉或綁定的新事實按 seq 保存 revision，因此下一頁仍返回 as_of 當時的 relation，重啟不改頁面邊界。

全域 `/events?after=` 與 SSE 沿用向前的 seq，與 history 的 opaque page cursor 不互換。`events_list` 增加明確的 `related_resource_type/id` 篩選，查 `api_event_resources`；原 `resource_type/id` 仍表示直接主體，不偷偷換語意。Filtered feed 固定本頁 head，掃至該 head 並回最後掃描 seq；即使沒有符合事件也能前進游標，避免反覆讀空頁。Client 必須處理完事件才保存 next_cursor；不把較大的 head_cursor 當作已處理游標。

目錄分頁維持既有 keyset，不增加 observation_revisions 或 snapshot rows。`order=id` 的 key 為 `(host, session_id)`，穩定集合每列一次；巡覽期間新加入的列可能出現或不出現，filter membership 改變透過 events 補追。`order=activity` 的 key 是 `(-last_activity_ms, host, session_id)`，保留動態排序可能漏列／重列的限制。as_of 是第一頁的事件補追起點，不是目錄隔離快照。

Backfill 事件只在 resource history 或明確 `kind=history.backfilled` 的 events 查詢顯示，預設 `/events`／SSE 排除；next_cursor 仍跨過隱藏 seq，不反覆掃描或在升級後重播大量舊事實。

## Provenance 與 actor evidence

每個 event 回以下 `context`；鍵必須存在，不知道的單值用 null 並在 `unknown_fields` 列原因，陣列用空陣列。Dashboard 顯示「unknown／來源未證實」與現有證據，不能把 null 默認成 Ted 或 Hermes。事件發生者與看見事件的人分開。

| 欄位 | 來源與規則 |
|---|---|
| `actor`、`actor_basis`、`actor_evidence` | 驗證 token 的 Principal 或可信服務主體；basis 為 `authenticated_principal / service / unknown`。保留既有 event 的 actor，而非用 operation 原始 actor 覆蓋 cancel/resume 的操作者。 |
| `claimed_actor`、`observer`、`evidence` | `ted_actions`、reconciliation、legacy body 的自報人名放 claim；observer 指 inventory／Task Service 等記錄者。證據用表／ID、protocol/version、turn/message/hash／receipt ref；不存 token 或原始 prompt。 |
| `entry_point`、`operation_entry_point`、`client`、`operation_id`、`command_id`、`step` | entry_point 是當次事件的可信 http/mcp/cli／daemon 入口，由 adapter 傳入 writer；operation_entry_point 才是建立操作時的 `operations.entry`。Cancel/resume 沒記當次入口時為 unknown，不借用原入口。Legacy task RPC 若只有 local-admin 驗證，actor 是 local-admin，human identity unknown；不由 body 自報推斷實際人。 |
| `work_item_ids`、`execution_id`、`relation_ids`、`project_ids` | 當時有效的 journal 關係，可多 work items；不以最新 owner 或今天的專案樹回寫舊事件。 |
| `host`、`profile_id`、`workspace_id`、`session_resource_ids`、`worktree_ids` | 實際 binding；跨 host receipt 分 source/destination；沒有明確 binding 就保持未知。 |
| `source_versions`、`result_versions` | `{kind, repository_id, sha/ref/digest, role, evidence_ref}` 的陣列；如 checkpoint commit、task base/verified commit、integration pinned/integrated/delivered SHA。Branch／latest 不是固定版本。Git author 若已有證據，只是版本 metadata，不是 actor。 |
| `occurred_at`、`recorded_at`、`backfilled`、`unknown_fields` | UTC；recorded_at 是 durable 寫入時間。Host timestamp 附來源，不拿時鐘偏差改 seq。回填區分原來源時間與新增投影時間。 |

Operation／checkpoint／work item 新事件在現有交易中寫完整 context；舊 operation 的建立者／原入口／target 可由不可變欄位還原，變動過的 result/version 不拿最新值補舊 status。Step、receipt、command 的每次轉換保存當時 fields，HTTP/MCP/CLI 回同一份 envelope。History 使用明確 allowlist 回結構化摘要、hash 及 reference；舊 task body 裡的需求原文或原始 prompt 不整段複製到 timeline。聊天內容仍用既有 messages 讀取路徑，不擴大 event feed 的敏感內容。

`resource_policy` 是可寫判斷唯一來源。B03 的 unknown actor/provenance 不會產生 grant，不回填 managed creation intent，也不增加配額；觀測 journal 的 relation/index 不能被 mutation admission 當作擁有權證據。

## 輸入／輸出與介面

所有新增讀取須通過既有 `api_auth` 的 observe scope，HTTP／MCP／CLI 經同 daemon、同 journal 的讀服務。沒有新增 mutation action；需要記 checkpoint、link 或派工時仍使用已註冊 `ActionDef`／OperationService，權限保持原契約。

| HTTP 路由（Phase 2） | MCP（RPC 為同一讀服務） | CLI | 輸入與輸出 |
|---|---|---|---|
| `GET /api/v1/sessions`（延伸） | `inventory_sessions` | `batc inventory sessions` | 保留原 host/provenance/access/attention/include_gone/order/cursor/limit，新增 profile_id、project_id（多值 OR）、work_item_id、execution_id、provider、has_tab、loaded、streaming、lifecycle、stale、`relation_scope=current/history`（預設 history）。其他不同 filters 為 AND；回 sessions/count/next_cursor/as_of/hosts，加 relation summary 與 coverage。 |
| `GET /api/v1/sessions/{host}/{id}`（延伸） | `inventory_session`（新增） | `batc inventory session HOST SID` | 回 session、現有 started_from/work_items，新增 state、discovery、relations_summary、history_available；不為 journal-only session 呼叫 host。既有 `live=true` 明確為另外的 host 讀取，history 不支援 live。 |
| `GET /api/v1/sessions/{host}/{id}/history` | `resource_history(resource_type="session", resource_id="host/id")` | `batc history session HOST SID` | cursor/limit/order/kind/since/until；回 resource、events、count、as_of、head_cursor、next_cursor、has_more、coverage。計畫 `/sessions/{id}/history` 的 ID 在現有 API 分成 host/id。 |
| `GET /api/v1/sessions/{host}/{id}/relations` | `resource_relations(resource_type="session", resource_id="host/id")` | `batc relations session HOST SID` | cursor/limit、execution_id、include_closed（預設 true）；回 relations、count、as_of、next_cursor，完整 ranges／evidence。 |
| `GET /api/v1/tasks/{task_id}/sessions`、`…/history`；`GET /tasks/{task_id}` 加摘要 | `resource_relations(resource_type="execution", resource_id=task_id)`；保留 `work_status` | `batc relations execution TASK` | execution_id 就是 task_id；history 同 resource_history(type=execution)，relations 以同 relation 服務分頁列 lead/reviewer/歷史 replacements，附 follow-up 關係與 worktree；不依最後五個 commands 充當完整列表。 |
| `GET /api/v1/worktrees/{worktree_id}`、`…/history`、`…/relations` | `inventory_worktree`、`resource_history`／`resource_relations`（type=worktree） | `batc inventory worktree ID`、`batc history worktree ID`、`batc relations worktree ID` | 只讀 connector 已知 binding；history/relations 分頁與 session 相同。沒有 binding 回 404，不掃主機猜 path。 |
| `GET /api/v1/hosts`（延伸）、`GET /api/v1/hosts/{host}/discovery` | `inventory_hosts(host, discovery=true)` | `batc inventory hosts`、`batc inventory discovery HOST` | hosts 含每 configured profile 最近 scope/status/times；discovery 回最新 scan/outside_scan，近期 transitions 以 seq cursor 分頁。 |
| `GET /api/v1/events`（延伸）；既有 `/events/stream` | `events_list` | `batc inventory events --after N` | 保留原契約；新增 related_resource 篩選與同 context。SSE 沿用全域 feed，不另建 timeline streamer。 |

CLI 保留現有 `batc sessions/read/hosts` 的直接 BAT 行為，新增 `inventory/history/relations` 清楚表示中央持久讀模型。新命令 `--json` 結果與 MCP/HTTP 等價，不因 daemon 未啟動而退回實機 scan；回確切連線錯誤。MCP `inventory_sessions` 補現有 HTTP 的 order 參數，完整巡覽用 order=id。分頁 params／返回 keys 以契約測試比對，避免同名參數各入口不同意思。

`capabilities.features` 增 `session_history`、`resource_relations`、`discovery_scope`，`worktree_history` 說明只限已知 binding；附支援 kinds、history 起始／backfill 限制及 optional providers。能力須反映已在 main 的實作；缺少 optional writer 回 unsupported/未取得原因，不造空的成功資料。

| 錯誤 | HTTP | 恢復 |
|---|---|---|
| `UNAUTHORIZED`、`FORBIDDEN` | 401／403 | 沿用既有驗證與代碼；讀工具不升權。 |
| `NOT_FOUND` | 404 | Journal 從未有該 ID／worktree binding；不隱含 live scan。 |
| `INVALID_PARAMS`、`INVALID_CURSOR` | 422 | 無效型別、範圍、順序、時間或游標與 filters 不合；保留 filters，重新第一頁。 |
| `HISTORY_CURSOR_UNAVAILABLE` | 409 | Cursor 的 snapshot／schema 版本不可讀；重取 baseline 再 catch-up，不能默默跳 head。 |
| `DISCOVERY_SCOPE_CHANGED` | 掃描結果的 error code | 舊 alias 的 binding/profile 變動；保留舊資料並標 outside/stale，配置新 alias。History 仍可讀。 |
| `SOURCE_UNAVAILABLE` | 資料的 reason，GET 仍 200 | Host/field/optional source 沒取得；回舊觀測、證據時間與 scan error，不把失敗當空 inventory。 |

### Part B（第二步）：Dashboard「Sessions 與歷史」

列表預設跨專案，加入多專案、工作項目、execution、host/profile、provider、來源、各狀態及「包含不再列舉的歷史」篩選；最後者在此畫面預設開。清楚列資源 ID、API 唯讀、各時間與 scan scope。選過的 filters 保存在既有 sessionStorage；無關聯資源可單獨篩出，不因沒有工作項目而消失。

Session 詳情加分頁 timeline 與 relations；工作項目、execution、operation、checkpoint、已知 worktree 皆可跳轉。Timeline 每列顯示時間、kind、actor 或 unknown、來源／結果版本、狀態及證據；較長技術 ID 收在可展開細節。Execution 顯示 lead、reviewer、follow-up 的 ranges；worktree 讀頁只呈現同一模型的資訊。Scope 卡顯示「掃了哪個 profile、何時、依何 authority、未掃哪些」，離線仍可讀舊 timeline。

重開與即時更新流程：

1. 從 journal 讀第一頁 baseline，保留 `as_of`；以 order=id 讀所需頁面，以 resource ID 合併 rows，不把跨頁排序變動當新資源。首次載入不使用先查 head 再載 view 的方式聲稱已補漏。
2. 向前分頁讀 `/events?after=as_of` 補到一次捕捉的 head；同時到達的 SSE 暫存，處理完補漏後接續。只按 seq 遞增套用，已處理的 seq 直接忽略；同一事件同時關聯多個資源，也只消費一次全域游標。
3. SSE 斷線後由最後已處理 seq 重連；frame 被截斷不前進 cursor。重複 frame、跨 chunk、多筆積壓、catch-up／SSE 重疊均不重複 timeline 卡片。沒有有效目錄 baseline cache 的 reopen 重取 baseline；不能只恢復游標而留下空畫面。
4. Token／daemon 身分改變時丟棄舊 cache/cursor。現有 journal 不 prune api_events；若未來有 retention 或 cursor 超過當前 head，明示 gap 並重建 baseline，不靜默略過。
5. History 第一頁 as_of 固定；新事件用 seq map 加到頂端，舊頁 cursor 繼續讀原 snapshot。Filters 改變重開 snapshot。渲染沿用 `fill()`、`liveReload` 與 typing／編輯抽屜 hold，保存載入過的頁面及草稿，不在打字下方重畫。

兩種語言在 `i18n.js` 同步，390 px 可讀。CSP 禁止 inline style attributes；需要動態樣式用既有 class 或 `el.style.setProperty`。本包不增加 managed 控制動作；既有控制按鈕仍依 backend capability 及資源政策。

## 必要前置條件、實際副作用與唯讀邊界

Daemon 必須持有既有 owner lock，journal migration 完成；API observe 主體及 host 的 BAT credential 由既有配置提供。沒有 SSH alias 的 host 仍可讀 inventory/history，Git dirty 等欄位標未取得，不能為觀測要求開 write/orchestrate tier。

讀 HTTP/MCP/CLI 只作 journal 的 SELECT，不寫 registry、不取得 host mutation lock、managed worktree flock 或 Git index lock。Background observation 的實際副作用只在 Connector 自己的 journal 覆寫 latest discovery、最新觀測、關係投影與事件；read-only Fleet 會連線／驗證 BAT 並讀 workspace/meta/安全 state/archive。它不送 start、resume、client-resume、rehydrate、workspace save，也不執行 TaskCoordinator.tick 或 write grant。

沿用 `service._state_safe`：Claude meta 沒有 cwd 就不讀 state；不以完整度要求繞過。不新增任何背景 Git 探測。Git 欄位只取 journal 已存的 checkpoint、step、receipt 或既有 on-demand reads；後者沿用 `checkpoints.source_state_script` 的 `git --no-optional-locks`。Outside scan 明列未背景掃描 Git 狀態；禁用 BAT `git:status` 及未驗證會刷新 index 的 worktree status 路徑。不能為補資料 stash、fetch 到人工 repo、checkout、commit、prune 或 rehydrate。讀取不到只回 unknown 與原因。

新增 journal writes 在原 writer 的短交易內，外部呼叫仍在 commit 之後。API 只讀不因觀察人工資源建立 managed registry entry，不改配額、不恢復未知 ownership。直接 messages/live 讀取是另有 host I/O 的既有能力，與純 journal history 分開。

Registry identity 合併結果以 canonical JSON 比較，未變更不執行 upsert。相同 BAT／registry 的第二輪 poll 不改 observation identity／relation／event tables；latest discovery 仍更新本輪掃描時間。

## Migration 與失敗恢復

沿用 `task_journal.Journal`；新增 tables、columns、indexes 採 idempotent DDL，每次開啟都執行，不讀寫 `PRAGMA user_version`，也不占資料步驟編號。新增事件 context/resource 索引、discovery latest、已知 worktree identity、relation segments 及欄位 evidence；既有 tasks、commands、events、work_item_links、checkpoint IDs 不改編。Relation segments 唯一鍵為 `(execution_id, session_resource_id, role, anchor_id)`，command-relation mapping 以 `(command_id, relation_id)` 為 key，保存 linked_at_seq；rebinding 保留舊 link，使 as_of 的 command_ids 不受最新 binding 影響；各 revision 留 seq，只有 SQLite 原 writer 寫入。

回填在 daemon owner 內、背景 loops 開始前完成，是 orchestrator 配發的一次性資料步驟 2；backfill 與 `user_version=2` 在同一交易提交。版本 1 的 journal 執行一次，版本已為 2 時不再執行；新 journal 也以 2 結束。DDL 使用 IF NOT EXISTS，位於資料步驟的版本 gate 之外。來源 key（表名／PK／事實類型）唯一，重啟重做不重複。已經有 api event 的 task／checkpoint／link／receipt 只補資源索引與可信 context，不追加同一件事的第二個 event。當舊 mutable step／receipt 只剩最後快照時，`history.backfilled` 記錄「目前保存的結果」及原 timestamp，不捏造 started → uncertain → succeeded 全序列；`history_coverage` 明列開始時間、缺少的 transitions。舊 profile／actor／range 不明保持 unknown。

已確認綁定的 operation 可能在 runs 表入帳之前中斷；讀 `external_refs`、已持久 step 及 commands 保留其身分與 uncertainty，不執行啟動補償。Context／index 在原交易內用獨立 savepoint 寫入；投影例外只回滾該投影，核心事實照常提交，context 留 `projection_error` 的例外類名並記 log，不保存訊息。History 由原寫入資源或此前已證實的資源連結顯示該事件及缺口；不留下部分 index／relation rows，也不對外宣告 journal 未提交的事件。Poll 失敗保存 failed scan，舊欄位及其他 hosts 不受影響；meta 失敗只影響該 session 的相關欄位。

Reconcile 所補的是新證據與新 seq，先前 uncertain 事件留著；重新讀 timeline 不重送任何命令。讀到未知未來 kind 仍回原 kind、摘要及 evidence，Dashboard 用一般事件列呈現，不因版本差把歷史丟掉。

## 預計修改檔案

Phase 2 的新增 `observation.py` 與共用 `resource_ids.py`；前者只集中純 journal history／relations／event-context 查詢與投影，不取代 inventory 或 OperationService。

| 檔案 | 修改 |
|---|---|
| `src/bat_agent_connector/task_journal.py`、新增 `observation.py` | Additive migration、事件 envelope／資源索引、回填、ranges、分頁與讀模型。 |
| `inventory.py`、`service.py`、必要的 `config.py` | Scope/scan/field evidence、安全候選聯集、三值狀態、stale 排程；不擴大可寫 channel。 |
| `operations.py`、`task_core.py`、`task_bat.py` | 在既有 journal 寫入點補 step/binding/relation 事實；不實作 operations-unification 的 action/gate。 |
| `checkpoints.py`、`integration.py`、`work_items.py` | 同交易保存當時 versions／多資源來源及 link ID；沿用已有 writer。 |
| `api_v1.py`、`task_daemon.py`、`mcp_server.py`、`cli.py` | Observe 路由/RPC/tools/命令、params 契約、feature capabilities。 |
| `dashboard/app.js`、`app.css`、`i18n.js`（Part B） | Sessions/歷史/relations/scope、filters、baseline/SSE、兩語言及手機。 |
| `tests/test_observation.py`（新增）、`test_api_v1.py`、`test_task_service.py`、`test_mcp_and_config.py`、`test_work_items.py`、`test_checkpoints.py` | 下節驗收；沿用 MockBat、LocalRunner/RealGitLog、temp git repos，必要時 FakeGitHub。新增可重跑 Dashboard harness／測試，不只依手動截圖。 |
| `skills/bat-agent-connector/SKILL.md`、`skills/hermes/bat-agent-connector/SKILL.md` | 同步教 agent 用持久 inventory 的完整分頁、session/worktree history、relation range、unknown evidence、events 游標；區分訊息分頁與 journal 歷史，禁止因斷線而重開工作。 |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md`、`docs/design/api-v1.md` | 各 README 加短說明與本文件連結；Next release 引用計畫章節、B01–B03；路由表／MCP/CLI/能力同步。 |
| 本文件與相關 design 的 `尚未涵蓋` | Phase 2 完成後才改為實際結果；`api-v1.md` 更新 observation 路由及限制；`dashboard.md` 的畫面待辦留給 Part B，diff/檔案仍待辦。 |

## 測試計畫與驗收對照

下表為 Phase 2 測試計畫；標 Part B 的瀏覽器驗收不在本次 Part A。每個測試名稱或 docstring 引用 B01/B02/B03；現有測試只證明其已涵蓋的部分，不能把 skipped 舊 reviewer 測試算作驗收。

| 驗收／計畫 | 新測試名稱與必要斷言 |
|---|---|
| B01；§08、§11、§19 | `test_b01_id_paging_complete_and_filter_changes_via_events`、`test_b01_relation_scope_and_cross_project_link_history`：205 筆 ID keyset 完整巡覽；filter changes 經 events；跨 project/work item 的 current/history 及 via 證據。 |
| B01；§08 | `test_b01_warm_reuse_reviewer_followup_and_command_ranges`、`test_b01_pending_bind_and_snapshot_relations`、`test_b01_warm_binding_closes_reserved_intent_without_overwriting`：兩 task 共用 session 的 ranges、舊 reviewer/replacement、follow-up、pending/bound/closed、固定 revision 分頁；原 reserved intent 正確關閉。 |
| B01；§08、§10 | `test_b01_worktree_shared_creation_identity_and_reuse`、`test_b01_legacy_task_external_creation_keeps_shared_identity`：共享 registry 建立 slot、reviewer/failover/reuse 同 ID、同 path 新 intent 不合併；使用 cleanup 共用 hash 函式。 |
| B01；§08 | `tests/test_resource_ids.py`：共用 root resolver 的 failover chain、reviewer lookup、warm reuse、逆序 registry、缺 parent、cycle、其他建立 intent 及原 JSON created_at 格式。 |
| B01、B03；§08、§11 | `test_b01_b03_checkpoint_source_run_steps_and_worktree_history`、`test_b01_b03_receipt_versions_are_fixed_at_the_writer_transition`：真實 temp Git checkpoint/run 及 steps 的多資源 timeline 去重；receipt 在既有 writer 轉換時保存各版本，不以新結果改舊事件。 |
| B01、B02；§10、§11 | `test_b01_history_as_of_late_binding_and_invalid_cursors`：history as_of 同時限制 event/linked_at；晚 binding 不進已開 snapshot，kind/order/resource/time 游標契約。 |
| B02；§11 | `test_b02_two_hosts_one_offline_and_scope_change`、`test_b02_null_workspace_preserves_missing_counts_even_with_registry`：另一 host 持續成功、離線保留舊值；scope 改綁不再 host I/O；移除 host 仍可讀 history；壞 workspace 不算完整列舉。 |
| B02；§11 | `test_b02_scope_change_stays_blocked_on_later_refreshes`：同 profile 改 URL／fingerprint，連續兩輪零 BAT frames；binding 與 binding_version 固定原值，attempted_binding_version 記被拒絕值；原身分及 history 不變。 |
| B02；§11 | `test_b02_discovery_latest_no_poll_rows_and_no_host_fanout`、`test_b02_session_specific_stale_gone_fresh_and_get_no_writes`：每 profile 一筆 latest、相同 poll 不寫事件；host flap 不 fan-out；missing/gone/reappear/fresh 與 GET 零 writes。 |
| B02；§11 | `test_b02_unchanged_poll_does_not_rewrite_observation_identities`：第二輪 registry 投影的 total_changes 不變；相同 BAT／registry 不重寫 observation tables。 |
| B02；§10、§11 | `test_b02_cursor_catchup_sse_resume_and_hidden_backfill`：分頁 gap catch-up、Last-Event-ID resume 不重複、backfill 不進 live feed、超前 cursor 422。 |
| B02；§11、§19（Part B） | `test_b02_dashboard_reopen_and_sse_gap_without_duplicates`（待第二步）：瀏覽器 baseline/reopen、frame 碎片/重疊/去重、token 更換、filters/草稿及 typing hold；Playwright 驗證。 |
| B03；§08、§11 | `test_b03_unknown_human_claim_is_not_api_actor_or_git_author`、`test_b03_rpc_admin_identity_is_not_claimed_human`：自報 Ted 保持 claim，RPC admin 是 local-admin；Git author 不升為 API actor。 |
| B02、B03；§11 | `test_b03_states_unknown_no_tab_and_field_times`：meta null／失敗、無 tab、journal-only null、離線與 gone 分軸；失敗不刷新上一個 activity 時間。Main 沒有可證明 session 終止的正式 journal source，因此 lifecycle 保持 unknown，不用 gone／turn abort 推論 ended。 |
| B03；§08、§11 | `test_b03_backfill_hidden_idempotent_and_unknown_boundaries`、`test_b03_migration_failure_rolls_back_and_restart_recovers`、`test_b03_backfilled_occurrence_time_filters_are_not_migration_time`：舊 journal 回填、全交易失敗回滾、重啟不重複、未知 range 邊界、原發生時間與隱藏 cursor。 |
| B03；§08、§11 | `test_b03_version_one_journal_runs_observation_backfill_once`：版本 1 → 2 回填一次；重開及已為 2 的 journal 不執行；新 journal 為 2，不重複回填。 |
| B01、B03；§08、§11 | `test_projection_failure_keeps_core_write_and_flags_event`：task state 與 operation step 的投影例外只回滾 savepoint，核心寫入及外部 step 成功；history 顯示 projection_error，無部分 resource／relation rows。 |
| B01–B03；§10、§11 | `test_b01_b02_b03_http_mcp_cli_contract_parity`：HTTP/實際 MCP server/CLI 經同 daemon；params、keys、cursor、context 一致；observe、404、422 契約及四個新 tools。 |
| B03；§06、§11 | `test_b03_observation_never_starts_resumes_rehydrates_or_locks_git`：MockBat 零 write/git:status；unsafe Claude state 不呼叫，journal 讀取不讀 Fleet/registry、不寫 DB；temp repo HEAD/index/refs/files 不變且無 locks，既有 on-demand Git probe 使用 no-optional-locks。 |

現有基線證據：

- `tests/test_api_v1.py::test_inventory_observes_read_only_and_pages_every_row_once`、`test_inventory_keeps_offline_hosts_stale_and_marks_gone_after_two_misses`、`test_inventory_keeps_what_one_refresh_did_not_observe`：讀取限制、部分 B01/B02 的 inventory 與欄位保留。
- 同檔 `test_task_events_project_into_the_api_cursor_and_old_journals_backfill`、`test_sse_stream_resumes_from_last_event_id`：持久 seq／SSE 從指定 ID 補讀；未涵蓋完整 Dashboard reopen／gap 去重。
- `tests/test_task_service.py::test_minimal_prefers_warm_session_id_and_goose_provider_order`、`test_warm_start_mismatched_ack_remains_uncertain`、`test_bat_warm_reuse_claims_only_clean_completed_service_session`、`test_warm_candidates_are_limited_to_the_same_workstream`：現有 warm reuse 行為；未證明分頁歷史 relations。
- `tests/test_work_items.py::test_links_point_at_known_resources_and_removal_keeps_history`、`test_http_reads_and_one_operation_path`：既有 link/unlink 保留與 session reads；未證明全 timeline 的 actor/context。

Part A 必須跑 `uv run ruff check .`、`uv run pytest -q` 全套，記精確摘要。Part B 修改 Dashboard 時，JS 複製成 `.mjs` 做 `node --check`，Playwright 對 zh-TW/en/390 px 驗證沒有 null/undefined/[object 文字及上述 reopen/SSE 情境。Fixtures 不含真實 host/token/session/workspace/email，不向真 host 寫入。

## 尚未涵蓋

- Part B：Dashboard 跨專案 filters、timeline、relations、scope 卡、reopen／catch-up／SSE 去重及 Playwright 驗證，下一個分支才實作。Part A 不修改 Dashboard。
- 不提供 inventory snapshot isolation，不保存每 poll 的 session revisions 或 scans；完整巡覽使用 order=id 加 events。
- 背景 Git/SSH status 探測不在本包範圍，成本與寫鎖風險不為補欄位而擴大。
- 未授權／未配置 profiles、從未觀測的人工無 tab 資源與任意歷史 transcript 的全面搜尋；本包承諾已授權掃描及 journal 所知範圍，顯示 outside scan。
- 固定 BAT 沒有全域、不可恢復的 session resource 終止證據。若 main 新 writer 尚未提供，resource-ended 仍 unknown；開放問題是未來 provider 應以哪個正式回執證明該終態，不以 idle/gone 補推。
- Host alias 的改綁合併及 profile 切換遷移；本版偵測 scope change 並保留舊身分，新範圍需獨立 alias。舊 profile 缺證據不追認。
- Operation unification／Task Service 共用 gate、delivery 剩餘 provider 功能、§23 tombstone／retained refs／restore；是否已在 main 是 Phase 2 的條件式 adapter 清單，未落地的 facts 仍待各包提供。
- Worktree diff／檔案瀏覽、附件/B04、Hub 匯入/B05、歷史保留／pruning 政策、原生 BAT deep link。既有資料讀取與人工唯讀邊界不因這些待辦改變。
