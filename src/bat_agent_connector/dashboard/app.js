// Generated from desktop/src. Run: cd desktop && npm ci && npm run build:browser. Do not edit.
//#region src/i18n.js
var STRINGS = {
	"zh-TW": {
		"nav_cleanup": "整理與復原",
		"cleanup_target": "選擇整理範圍",
		"cleanup_target_work_item": "工作項目",
		"cleanup_target_checkpoint": "Checkpoint",
		"cleanup_target_integration": "整合操作",
		"cleanup_target_host": "主機",
		"cleanup_id": "主機名稱或原始 ID",
		"cleanup_children": "包含子工作項目",
		"cleanup_intro": "先查看實際資源與保留原因，再回收資源。工作脈絡、回執與原始 ID 永久可查。",
		"cleanup_repreview": "選擇或實際狀態已改變。執行前請重新預覽。",
		"cleanup_retry_same": "未收到明確回覆。請再次執行，使用原預覽與相同 key 查回原操作；不要另建清理。",
		"cleanup_preview": "預覽整理",
		"cleanup_apply": "執行已審閱的整理",
		"cleanup_reviewed": "我已查看這份預覽的資源、保留內容與丟棄選擇。",
		"cleanup_scope": "執行需要 cleanup 權限。",
		"cleanup_counts": "回收 {reclaim} 個資源 · 保留 {retain} 個",
		"cleanup_expires": "預覽到期時間：{time}（15 分鐘）。",
		"cleanup_blocked": "所有資源都保留。請查看每項的原因。",
		"cleanup_commit_kept": "保留 commit",
		"cleanup_not_delivered": "成果尚未送達。釋放後仍保留 commits 與本機 branch。",
		"cleanup_release": "釋放這個 worktree；保留尚未送達的 commits 與 branch",
		"cleanup_discard": "永久丟棄未提交的檔案（需要 cleanup_discard）",
		"cleanup_plan": "執行計畫",
		"cleanup_evidence": "ID、證據與送達涵蓋範圍",
		"cleanup_open_receipts": "查看逐項回執",
		"cleanup_history": "永久整理紀錄",
		"cleanup_retained": "實際保留的內容",
		"cleanup_retained_help": "從主機驗證 refs 與 commit objects。目前只提供保留內容列表；runtime 不會復活。",
		"cleanup_search": "搜尋原始 ID、舊位置或 PR",
		"cleanup_search_button": "搜尋",
		"cleanup_empty_history": "還沒有整理紀錄。",
		"cleanup_empty_retained": "還沒有已記錄的保留內容。",
		"cleanup_unavailable": "無法驗證主機或保留 objects。",
		"cleanup_reason_reviewed": "由審閱後的整理操作移除。",
		"cleanup_choice_UNCOMMITTED_CHANGES": "已選擇永久丟棄未提交內容。",
		"cleanup_choice_RESULTS_NOT_DELIVERED": "已選擇釋放；保留尚未送達的 commits 與 branch。",
		"cleanup_kind_session": "Session",
		"cleanup_kind_worktree": "Worktree",
		"cleanup_kind_local_branch": "本機 branch",
		"cleanup_kind_clone": "Managed clone",
		"cleanup_kind_integration_area": "整合區",
		"cleanup_kind_git_pin": "Git pin",
		"cleanup_kind_source": "原始來源",
		"cleanup_kind_artifact": "附件參照",
		"cleanup_kind_temporary": "暫存",
		"cleanup_kind_retained_ref": "保留 ref",
		"cleanup_decision_retain": "保留",
		"cleanup_decision_reclaim": "回收",
		"cleanup_decision_already_absent": "已不存在",
		"cleanup_step_preserve": "Pin commit",
		"cleanup_step_stop": "停止 session",
		"cleanup_step_discard": "丟棄檔案",
		"cleanup_step_remove.worktree": "移除 worktree",
		"cleanup_step_remove.branch": "刪除已送達 branch",
		"cleanup_step_finalize": "保存回執",
		"cleanup_step_remove.temporary": "移除指定暫存",
		"cleanup_kind_remote": "遠端資源",
		"cleanup_reason_TIER_DISABLED": "主機的 write／orchestrate tier 未啟用。",
		"cleanup_reason_MANUAL_READ_ONLY": "人工建立，永遠唯讀。",
		"cleanup_reason_UNKNOWN_READ_ONLY": "無法證明建立來源。",
		"cleanup_reason_WORKDIR_NOT_MANAGED": "工作目錄不在 managed roots 內。",
		"cleanup_reason_BINDING_MISMATCH": "資源與建立時的綁定不符。",
		"cleanup_reason_CLONE_NOT_OURS": "沒有符合的 Connector 建立標記。",
		"cleanup_reason_CLONE_CONFIG_TAMPERED": "Repository 設定或 object 儲存不安全。",
		"cleanup_reason_OBSERVATION_UNAVAILABLE": "無法在主機讀取期限內觀測。",
		"cleanup_reason_ACTIVE_WRITER": "Session 正在串流或寫入。",
		"cleanup_reason_SESSION_WAITING": "Session 有待回答問題、權限或排隊指令。",
		"cleanup_reason_COMMAND_UNRESOLVED": "指令或外部步驟的結果尚未確認。",
		"cleanup_reason_ACTIVE_EXECUTION": "另一個執行仍需要資源。",
		"cleanup_reason_CONTENT_REQUIRED": "有效整合預覽或執行仍需要內容。",
		"cleanup_reason_TASK_OWNED": "由 Task Service 整理；reviewed task cleanup 在 Part B。",
		"cleanup_reason_UNCOMMITTED_CHANGES": "有未提交、未追蹤或 ignored 內容。",
		"cleanup_reason_RESULTS_NOT_DELIVERED": "送達回執未涵蓋全部結果 commits。",
		"cleanup_reason_DELIVERY_UNCERTAIN": "送達結果尚未確認。",
		"cleanup_reason_RETENTION_RULE": "明確保留規則仍需要內容。",
		"cleanup_reason_SHARED_CONTAINER": "這個載體有共用資源。",
		"cleanup_reason_RETAINED_CONTENT_STORE": "載體或 pin 保留成果與證據。",
		"cleanup_reason_REMOTE_OUT_OF_SCOPE": "遠端 branch 刪除是另一個動作。",
		"cleanup_reason_RESOURCE_KIND_UNSUPPORTED": "這類資源或 Git 狀態沒有整理 adapter。",
		"cleanup_reason_RESOURCE_CLEANED": "這一代資源已有已確認的整理紀錄。",
		"cleanup_reason_CLEANUP_IN_PROGRESS": "整理操作已保留這個資源。",
		"cleanup_receipt_retained": "保留",
		"cleanup_receipt_pending": "等待",
		"cleanup_receipt_running": "執行中",
		"cleanup_receipt_succeeded": "完成",
		"cleanup_receipt_already_absent": "已不存在",
		"cleanup_receipt_failed": "失敗",
		"cleanup_receipt_uncertain": "待確認結果",
		"cleanup_receipt_blocked_stale": "狀態改變",
		"cleanup_receipt_cancelled": "已取消",
		offline_actions_paused: "中央離線，暫停操作",
		sync_waiting: "等待更新，草稿已保留",
		desktop_connection: "桌面中央連線",
		desktop_local: "本機功能",
		desktop_connect_needed: "請連到已配置的中央 Connector。",
		desktop_polling: "已連線 · 每秒更新",
		desktop_config_needed: "尚未配置中央連線。",
		desktop_credential_missing: "本機憑證尚未提供，請依桌面安裝說明設定後重新啟動。",
		desktop_credential_help: "中央位置與身份由本機設定指定；憑證保留在原生程式，不存入此畫面。",
		desktop_dashboard_only: "目前支援 Dashboard，無需安裝 BAT。Fleet 連線管理、開啟 BAT、原生附件、登入自啟與更新尚未提供。關閉視窗會留在系統匣；退出程式不會停止中央工作。",
		merge_scope_reload: "PR 範圍已變更，已保留你選定的預覽。請重新讀取並檢視後再合併。",
		metadata_diff: "內容比較",
		metadata_before: "寫前",
		metadata_intended: "預期",
		metadata_observed: "讀回",
		scope_stack_rebase: "上層分支將重整",
		scope_dependency: "分支相依",
		metadata_edit: "編輯 PR 標題與說明",
		metadata_title: "PR 標題",
		metadata_disabled: "此 repository 尚未啟用 allow_pr_update。",
		metadata_race_limit: "儲存前比較標題與說明，寫後再次讀回。GitHub 沒有原子比對寫入，最後讀取與寫入間仍可能覆蓋同時發生的編輯。",
		metadata_result_help: "操作詳情保留寫前、預期與讀回內容。若有衝突，先重新讀取再編輯；不自動覆蓋或還原。",
		metadata_pending: "PR 已修改，讀回驗證仍待完成。",
		merge_scope: "合併範圍",
		merge_method: "合併方式",
		merge_commit_range: "查看完整 BASE..HEAD：{count} 個 commits",
		merge_preview_fixed: "此預覽固定 head、base 與範圍；更換方式需重新讀取。",
		scope_single_pr: "未發現其他 PR 會被合併。",
		scope_native_stack: "原生 stack",
		scope_branch_chain: "相依分支 chain",
		scope_indirect_merge: "間接合併候選",
		scope_would_merge: "影響其他 PR",
		scope_candidate: "已包含的 commits",
		merged_newer_base: "合併到較新的 base：另有 {count} 個 commits 會一起發布。",
		close: "關閉",
		nav_projects: "專案",
		projects_help: "專案與工作項目是 Connector 自己的紀錄：目標、需求原文、驗收、步驟，以及做這件事的 sessions、版本、操作與 PR。改名不會改 ID；排序與固定只影響顯示。",
		new_project_name: "新專案名稱",
		add_project: "新增",
		show_archived: "顯示已封存",
		no_projects: "還沒有專案。",
		new_sub_project: "子專案名稱",
		rename: "改名",
		archive: "封存",
		restore: "復原",
		more: "更多",
		move_up: "上移",
		move_down: "下移",
		pin: "固定在上方",
		unpin: "取消固定",
		wi_done_of: "完成 {done}/{total}",
		wi_state_todo: "未開始",
		wi_state_doing: "進行中",
		wi_state_waiting: "等待中",
		wi_state_done: "已完成",
		wi_state_awaiting_approval: "待確認完成",
		wi_err_VERSION_CONFLICT: "這筆資料剛被改過，已重新載入最新內容（你在表單裡的修改還在）；確認後再存一次。",
		linked_back: "已連回這個工作項目",
		wi_err_ORDER_CHANGED: "順序剛被改過，已重新載入；請再排一次。",
		wi_err_PIN_CHANGED: "固定狀態剛被改過，已重新載入。",
		wi_err_CONTENT_CHANGED: "內容在你確認時被改過；請看過新的內容再決定。",
		wi_err_NAME_TAKEN: "已有同名的專案。",
		wi_err_HAS_CHILDREN: "請先封存它的子專案。",
		wi_err_PARENT_ARCHIVED: "上層已封存，請先復原上層。",
		wi_err_PINNED_FIRST: "固定的項目一定在未固定的上面；要往下移請先取消固定。",
		wi_err_STEPS_OPEN: "還有沒勾的步驟；勾完（或刪掉不需要的步驟）再標完成。",
		wi_err_CYCLE: "不能移到自己底下。",
		wi_err_LINK_TARGET_NOT_FOUND: "找不到這個連結對象（Connector 沒看過它）。",
		wi_err_NOTHING_TO_DECIDE: "沒有人回報完成，不需要決定。",
		new_item_title: "新工作項目",
		add_item: "新增",
		work_items: "工作項目",
		name: "名稱",
		description: "說明",
		repositories: "Repositories",
		task_project: "Task Service 專案名稱",
		save: "儲存",
		archived: "已封存",
		sub_projects: "子專案",
		new_child_item: "子項目名稱",
		new_branch_item: "分支項目名稱（與它同一層）",
		archive_with_children: "封存（連同子項目）",
		needs_decision: "等你決定",
		no_items: "還沒有工作項目。",
		link_missing: "已找不到",
		needs_manage_scope: "你的 token 沒有 manage 權限，不能修改專案與工作項目；用 --scope manage 重新發 token。",
		needs_approve_scope: "你的 token 沒有 approve 權限，不能確認完成；用 --scope approve 重新發 token。",
		accept_done: "確認完成",
		mark_done: "標記完成",
		keep_working: "還沒完成，繼續",
		approved_by: "{who} 已確認完成（{time}）。內容再被修改時會重新等待確認。",
		claimed_done: "{who} 回報已完成，等你確認。確認的是你現在看到的內容。",
		steps_all_checked: "步驟都勾完了。要標記完成，還是繼續？",
		goal: "目標",
		request: "需求原文",
		acceptance: "驗收條件",
		steps_title: "步驟",
		parent_id: "上層",
		remove: "移除",
		new_step: "新步驟",
		link_session: "Session",
		link_checkpoint: "版本",
		link_operation: "操作",
		link_task: "任務",
		link_pull_request: "PR",
		link_ref_hint: "對象",
		link_ref_session: "host/session_id",
		link_ref_checkpoint: "cp_…",
		link_ref_operation: "op_…",
		link_ref_task: "task ID",
		link_ref_pull_request: "owner/name#123",
		link: "連結",
		links: "相關資源",
		no_links: "還沒有連結。",
		no_steps: "沒有步驟。",
		children: "子項目",
		derived: "從這裡分出的項目",
		history: "紀錄",
		derived_from: "分支自",
		start_from_checkpoint: "從這個版本派工",
		claimed_by: "{who} 回報完成",
		linked_items: "相關工作項目",
		ev_work_item_created: "建立",
		ev_work_item_updated: "修改",
		ev_work_item_state: "狀態",
		ev_work_item_approved: "確認完成",
		ev_work_item_continued: "退回繼續",
		ev_work_item_linked: "加上連結",
		ev_work_item_unlinked: "移除連結",
		ev_work_item_archived: "封存",
		ev_work_item_restored: "復原",
		ev_work_item_pinned: "固定",
		ev_work_item_unpinned: "取消固定",
		nav_home: "待處理",
		nav_sessions: "Sessions",
		nav_delivery: "成果與 GitHub",
		nav_operations: "操作紀錄",
		nav_settings: "連線",
		tab_needs_you: "需要你處理",
		tab_to_confirm: "待確認",
		empty_needs_you: "目前沒有需要你處理的項目。",
		empty_to_confirm: "沒有等待確認的操作。",
		stale: "資料過期",
		stale_reason_host_unreachable: "主機連不上",
		stale_reason_host_not_refreshed: "很久沒更新",
		stale_reason_not_enumerated: "上次列舉沒有出現",
		stale_reason_gone: "已不存在",
		stale_reason_never_observed: "尚未觀測",
		read_only: "API 唯讀",
		managed: "Connector 管理",
		provenance_manual: "人工建立（BAT）",
		provenance_connector_managed: "Connector 建立",
		provenance_unknown: "來源不明",
		state_streaming: "執行中",
		state_loaded: "已載入",
		state_unloaded: "未載入",
		pending_ask_user: "等你回答",
		pending_permission: "等待權限",
		host: "主機",
		workspace: "Workspace",
		title: "標題",
		agent: "Agent",
		state: "狀態",
		activity: "最後活動",
		observed: "觀測時間",
		all_hosts: "全部主機",
		all_access: "全部",
		only_managed: "只看 Connector 管理",
		only_read_only: "只看唯讀",
		load_more: "載入更多",
		messages: "對話",
		send: "送出",
		send_placeholder: "給這個 managed session 的訊息…",
		interrupt: "中斷這一輪",
		answer: "回答",
		allow: "允許",
		deny: "拒絕",
		read_only_note: "這個 session 由人在 BAT 建立，API 永久唯讀：不送字、不回答、不中斷。要讓 agent 接續，請從它的 commit 另開 managed 工作。",
		continue_from_checkpoint: "從此版本建立 agent 工作",
		checkpoints: "版本（checkpoint）",
		checkpoint_help: "記下這個 session 目前的 commit 與最近對話（只讀，不改動原 session 或資料夾）。從版本開始的 agent 工作會在 Connector 自己的 clone 裡用新的 branch 與 session 進行。",
		create_checkpoint: "記下這個版本",
		no_checkpoints: "還沒有記下的版本。",
		excerpt_count: "{n} 則對話",
		commit: "Commit",
		checkpoint_note_placeholder: "接下來要做什麼（原文，會一併記下，選填）…",
		dirty_unknown: "未提交的修改：未觀測（這台主機沒有 SSH alias）；不會帶入新工作。",
		source_advanced: "來源已有更新的 commit；這個版本仍固定在原 commit。要帶入新版本請再記一次。",
		started_from: "這個 session 從版本 {commit} 開出：",
		source_session: "來源 session",
		dirty_warning: "記錄時有 {n} 個未提交的修改，不會帶入新工作。",
		continue_placeholder: "要 agent 接著做什麼…",
		start_agent_work: "開始 agent 工作",
		open_new_session: "開啟新 session",
		checkpoint_unavailable: "這台主機尚未設定 managed_roots、SSH alias 或 write／orchestrate 權限，不能從版本開工。",
		needs_start_scope: "你的 token 沒有 start 權限，不能開新的 agent 工作；用 --scope start 重新發 token。",
		confined_note: "工作目錄本身不提供保護。限制取決於啟動選項及帳號證據；個別批准可能允許外部寫入。",
		confinement_none: "無已證實的執行限制",
		confinement_prompt_gated: "權限詢問控管",
		confinement_host_account: "帳號限制",
		confinement_os_sandbox: "OS sandbox",
		confinement_os_pending: "OS sandbox（尚未實機驗證）",
		confinement_evidence: "限制證據",
		confinement_creation: "建立時限制",
		confinement_current: "目前核對",
		confinement_options: "啟動選項",
		confinement_gap: "尚未涵蓋",
		confinement_status_verified: "已查核",
		confinement_status_options_confirmed: "選項已核對",
		confinement_current_unknown: "目前限制未知",
		confinement_current_mismatch: "目前限制與紀錄不符",
		confinement_status_unknown: "未知",
		confinement_status_mismatch: "與紀錄不符",
		confinement_status_pending: "等待核對",
		confinement_gap_sandbox_enforcement_unverified: "尚未由 W12 實機驗證阻擋效果",
		confinement_gap_prompt_rules_are_not_os_isolation: "既有批准規則及 shell 可能允許外部寫入",
		confinement_gap_task_recipe_compatibility: "保留 Task Service 測試行為；未新增執行限制",
		confinement_gap_execution_restriction_unverified: "尚無執行限制證據",
		confinement_gap_legacy_evidence_missing: "舊 session 缺建立時證據；不自動升級",
		confinement_claude_note: "Claude 使用 default：未預先授權的編輯及 Bash 會詢問。既有批准規則仍適用，沒有 OS 寫入隔離。建議使用 Codex；個別批准可能允許外部寫入。",
		confinement_codex_note: "Codex 使用 workspace-write／on-request。未完成實機阻擋驗證；網路及可寫 roots 無法由 BAT 設定，安裝與 localhost 測試可能受限。個別批准可能越過限制。",
		confinement_account_note: "已查核 BAT 帳號不能寫宣告的私人 roots。Claude 可使用 acceptEdits；限制只涵蓋已查核的 roots，啟動前會重新核對。",
		confinement_account_blocked: "已宣告帳號限制，但查核尚未通過；新 session 會被拒絕。請修正主機配置。原因：{reason}。",
		confinement_account_recheck: "啟動 session 時會重新查核帳號限制。通過後，Claude 可使用 acceptEdits；若僅缺少可降級處理的環境加固條件，Claude 仍可用 default 啟動。其他查核失敗會拒絕啟動。",
		confinement_account_fallback: "帳號查核回報 {reason}。Claude 會使用 default，不啟用 acceptEdits。",
		repository: "Repository",
		pull_number: "PR 編號",
		load_pr: "讀取 PR",
		head: "Head",
		base: "Base",
		checks: "Checks",
		checks_summary: "{total} 個，{pending} 個未完成，{failed} 個失敗",
		mergeable: "可合併狀態",
		merge: "合併 PR",
		deploy_to: "部署到 {env}",
		merge_and_deploy_to: "合併並部署到 {env}",
		retry_deploy: "重試部署這個版本",
		merged_sha: "實際合併版本",
		op_accepted: "已受理",
		op_running: "執行中",
		op_waiting_checks: "等待 checks",
		op_waiting_external: "等待 GitHub／部署",
		op_needs_attention: "需要處理",
		op_uncertain: "結果不明，回查中",
		op_succeeded: "完成",
		op_failed: "失敗",
		op_cancelled: "已取消",
		cancel: "取消",
		resume: "重新執行",
		resume_help: "處理完原因後再跑一次：已完成的步驟不重做，未確定的步驟先回查，不會重送。",
		steps: "步驟",
		action: "動作",
		actor: "操作者",
		created: "建立時間",
		error: "錯誤",
		reason: "原因",
		token: "API token",
		token_help: "以 batc api-token issue 發行；只存在這台瀏覽器。",
		connect: "連線",
		remember: "在這台電腦記住",
		disconnect: "中斷",
		connected_as: "已連線：{actor}（{scopes}）",
		need_token: "請先在「連線」輸入 API token。",
		unreachable_hosts: "主機異常",
		loading: "載入中…",
		forbidden_scope: "你的 token 沒有這個權限。",
		queue_behind: "排在目前這一輪之後",
		no_messages: "還沒有訊息。",
		update_pr_results: "更新 PR 成果",
		update_pr_help: "把選定的成果整合進這個 PR 的 head：一般 push，不會強制覆蓋；不會改動你本機的資料夾。",
		needs_integrate_scope: "需要 integrate 權限：用 --scope integrate 重新發 token。",
		integration_no_host: "這個 repository 的 integrate 主機目前都沒有 SSH alias、managed root 或 write／orchestrate 權限。",
		kind_checkpoint: "你的 checkpoint",
		kind_checkpoint_run: "agent 成果",
		kind_branch: "GitHub 分支",
		previewing: "預覽中…（第一次會建立 managed 整合區，可能需要幾分鐘）",
		start_integration_conflict: "開始整合（第 {n} 項預計衝突，會停下讓你處理）",
		normal_push: "一般 push",
		push_access_ok: "可推送",
		push_access_denied: "這台主機的 git 憑證無法推送（請設定 deploy key 或憑證）",
		push_access_unknown: "推送權限未確認",
		plan_fast_forward: "快轉",
		plan_merge: "合併",
		plan_pick: "挑選",
		plan_already_included: "已在 PR 中",
		plan_conflict: "預計衝突",
		plan_not_predicted: "未檢查",
		plan_unrelated: "沒有共同歷史",
		n_commits: "{n} 個 commit",
		n_files: "{n} 個檔案",
		foreign_commit: "不屬於所選來源",
		overlapping_files: "重疊檔案：",
		preview_expired: "預覽已過期（超過 1 小時或 PR head 已變更）。",
		previewed_at: "預覽於 {time} · 1 小時內有效",
		preview_again: "重新預覽",
		branch_on_github: "GitHub 上的分支名稱",
		add: "加入",
		add_branch: "加入分支",
		delivered_to: "已送進 #{n}",
		agent_results: "agent 成果",
		your_checkpoints: "你的 checkpoint",
		still_working: "執行中",
		done: "已完成",
		none: "沒有",
		selected_in_order: "已選（依序整合）",
		integration_done: "PR 已更新：{old} → {new}，加入 {n} 個 commit。你本機的資料夾不會自動更新；要同步請在 BAT 裡 pull。",
		integration_INTEGRATION_CONFLICT: "有一項衝突。前面的項目已在 Connector 的整合區完成，尚未推送。可以交給 agent 在整合區解衝突，或取消後不含它重新預覽。",
		integration_RESOLUTION_INCOMPLETE: "衝突還沒解完（還沒 commit）。等 agent 完成 `git commit --no-edit` 後按「重新執行」。",
		integration_RESOLUTION_INVALID: "解衝突的結果不符合要求（要剛好一個 merge commit、沒有未提交修改或衝突標記）；修好後按「重新執行」。",
		integration_waiting_resolver: "等 agent 解完衝突（它還在工作）",
		hand_to_agent: "交給 agent 解衝突",
		handoff_started: "已開始解衝突的 session；它 commit 之後按「重新執行」。",
		integration_REMOTE_MOVED: "PR 在整合時有新的推送，沒有覆蓋它，也沒有推送。請取消並以最新版本重新預覽。",
		integration_PUSH_REJECTED: "GitHub 拒絕這次推送（保護規則或簽章要求）。",
		integration_PUSH_AUTH_FAILED: "這台主機的 git 憑證無法推送；修好後按「重新執行」。",
		integration_REMOTE_REWOUND_BEFORE_PUSH: "已推送，但推送前分支被往回改過；請看一下 PR，再按「重新執行」完成。",
		integration_REMOTE_REF_RECREATED: "已推送，但推送前分支被刪除過；請看一下 PR，再按「重新執行」完成。",
		integration_UNCERTAIN_UNRESOLVED: "推送結果還無法確認（讀不到遠端）；Connector 不會重推。",
		integration_uncertain: "推送結果確認中（Connector 會先讀遠端，不會重推）",
		integration_waiting: "已推送，等待 GitHub 顯示新的 head",
		integration_running: "正在更新 PR…",
		cancel_and_preview: "取消並重新預覽",
		receipts: "各來源紀錄",
		receipt_pending: "待處理",
		receipt_composed: "已整合（未推送）",
		receipt_already_included: "已在 PR 中",
		receipt_conflict: "衝突",
		receipt_delivered: "已送達",
		receipt_not_delivered: "未送達",
		receipt_unknown: "不確定（推送結果未證實）",
		receipt_resolved: "已解衝突（未推送）",
		integration_PUSH_UNPROVEN: "PR 分支在舊的 head，但組合後的 commit 已在 GitHub 上：之前的推送可能落地後被改回。不會再推一次；請看一下 PR，再取消並重新預覽。"
	},
	en: {
		"nav_cleanup": "Cleanup and retained work",
		"cleanup_target": "Choose a scope",
		"cleanup_target_work_item": "Work item",
		"cleanup_target_checkpoint": "Checkpoint",
		"cleanup_target_integration": "Integration",
		"cleanup_target_host": "Host",
		"cleanup_id": "Host name or original ID",
		"cleanup_children": "Include child work items",
		"cleanup_intro": "Review the resources before reclaiming them. Work context, receipts and original IDs stay findable forever.",
		"cleanup_repreview": "Choices or live state changed. Preview again before applying.",
		"cleanup_retry_same": "The reply was not confirmed. Apply again with this preview and the same key to recover the original operation.",
		"cleanup_preview": "Preview cleanup",
		"cleanup_apply": "Apply reviewed cleanup",
		"cleanup_reviewed": "I reviewed the resources, retained content and discard choices in this preview.",
		"cleanup_scope": "Applying needs the cleanup scope.",
		"cleanup_counts": "{reclaim} resources to reclaim · {retain} retained",
		"cleanup_expires": "This preview expires at {time} (15 minutes).",
		"cleanup_blocked": "All resources are retained. Review the reasons for each item.",
		"cleanup_commit_kept": "Commit kept",
		"cleanup_not_delivered": "Results were not delivered. Releasing keeps the commits and local branch.",
		"cleanup_release": "Release this worktree; keep its undelivered commits and branch",
		"cleanup_discard": "Discard uncommitted files permanently (requires cleanup_discard)",
		"cleanup_plan": "Plan",
		"cleanup_evidence": "IDs, evidence and delivery coverage",
		"cleanup_open_receipts": "View item receipts",
		"cleanup_history": "Permanent cleanup history",
		"cleanup_retained": "Actual retained content",
		"cleanup_retained_help": "Refs and commit objects verified on their host. Worktree restore is not available yet; a runtime cannot be revived.",
		"cleanup_search": "Search original ID, old location or PR",
		"cleanup_search_button": "Search",
		"cleanup_empty_history": "No cleanup history yet.",
		"cleanup_empty_retained": "No retained content recorded yet.",
		"cleanup_unavailable": "Host or retained objects could not be verified.",
		"cleanup_reason_reviewed": "Removed by a reviewed cleanup operation.",
		"cleanup_choice_UNCOMMITTED_CHANGES": "You chose permanent discard of uncommitted content.",
		"cleanup_choice_RESULTS_NOT_DELIVERED": "You chose release; undelivered commits and branch are kept.",
		"cleanup_kind_session": "Session",
		"cleanup_kind_worktree": "Worktree",
		"cleanup_kind_local_branch": "Local branch",
		"cleanup_kind_clone": "Clone",
		"cleanup_kind_integration_area": "Integration area",
		"cleanup_kind_git_pin": "Git pin",
		"cleanup_kind_source": "Source",
		"cleanup_kind_artifact": "Artifact",
		"cleanup_kind_temporary": "Temporary",
		"cleanup_kind_retained_ref": "Retained ref",
		"cleanup_decision_retain": "Retain",
		"cleanup_decision_reclaim": "Reclaim",
		"cleanup_decision_already_absent": "Already absent",
		"cleanup_step_preserve": "Pin commit",
		"cleanup_step_stop": "Stop session",
		"cleanup_step_discard": "Discard files",
		"cleanup_step_remove.worktree": "Remove worktree",
		"cleanup_step_remove.branch": "Delete delivered branch",
		"cleanup_step_finalize": "Record receipt",
		"cleanup_step_remove.temporary": "Remove exact temporary",
		"cleanup_kind_remote": "Remote resource",
		"cleanup_reason_TIER_DISABLED": "The host write or orchestrate tier is disabled.",
		"cleanup_reason_MANUAL_READ_ONLY": "A person created this resource; it is read-only.",
		"cleanup_reason_UNKNOWN_READ_ONLY": "Creation ownership is not proven.",
		"cleanup_reason_WORKDIR_NOT_MANAGED": "The workdir is outside the managed roots.",
		"cleanup_reason_BINDING_MISMATCH": "The resource does not match its creation binding.",
		"cleanup_reason_CLONE_NOT_OURS": "The repository has no matching connector creation markers.",
		"cleanup_reason_CLONE_CONFIG_TAMPERED": "Repository config or object storage is unsafe.",
		"cleanup_reason_OBSERVATION_UNAVAILABLE": "Live observation was unavailable within the host deadline.",
		"cleanup_reason_ACTIVE_WRITER": "A session is streaming or writing.",
		"cleanup_reason_SESSION_WAITING": "A session has a pending question, permission or queued turn.",
		"cleanup_reason_COMMAND_UNRESOLVED": "A command or external step has an unresolved outcome.",
		"cleanup_reason_ACTIVE_EXECUTION": "Another execution still needs this resource.",
		"cleanup_reason_CONTENT_REQUIRED": "An active integration preview or execution needs the content.",
		"cleanup_reason_TASK_OWNED": "The Task Service reclaims this resource; reviewed task cleanup comes later.",
		"cleanup_reason_UNCOMMITTED_CHANGES": "Uncommitted tracked, staged, untracked or ignored content exists.",
		"cleanup_reason_RESULTS_NOT_DELIVERED": "Delivery receipts do not cover all result commits.",
		"cleanup_reason_DELIVERY_UNCERTAIN": "Delivery has an unresolved outcome.",
		"cleanup_reason_RETENTION_RULE": "An explicit retention rule requires this content.",
		"cleanup_reason_SHARED_CONTAINER": "This container has shared resources.",
		"cleanup_reason_RETAINED_CONTENT_STORE": "The repository or pin carries retained content and evidence.",
		"cleanup_reason_REMOTE_OUT_OF_SCOPE": "Remote branch deletion is a separate action.",
		"cleanup_reason_RESOURCE_KIND_UNSUPPORTED": "This resource or Git state has no cleanup adapter.",
		"cleanup_reason_RESOURCE_CLEANED": "This resource generation has a confirmed cleanup tombstone.",
		"cleanup_reason_CLEANUP_IN_PROGRESS": "A cleanup operation has reserved this resource.",
		"cleanup_receipt_retained": "retained",
		"cleanup_receipt_pending": "pending",
		"cleanup_receipt_running": "running",
		"cleanup_receipt_succeeded": "succeeded",
		"cleanup_receipt_already_absent": "already absent",
		"cleanup_receipt_failed": "failed",
		"cleanup_receipt_uncertain": "uncertain",
		"cleanup_receipt_blocked_stale": "blocked stale",
		"cleanup_receipt_cancelled": "cancelled",
		offline_actions_paused: "Central offline · actions paused",
		sync_waiting: "Waiting to refresh · draft preserved",
		desktop_connection: "Desktop central connection",
		desktop_local: "Local capabilities",
		desktop_connect_needed: "Connect to the configured central Connector.",
		desktop_polling: "connected · updates every second",
		desktop_config_needed: "Central connection is not configured.",
		desktop_credential_missing: "Native credential unavailable. Follow desktop setup and restart the app.",
		desktop_credential_help: "The central address and expected identity come from local configuration. Credentials stay in the native app, outside this page.",
		desktop_dashboard_only: "Dashboard is available without BAT installed. Fleet connections, opening BAT, native attachments, login autostart and updates are not available yet. Closing the window keeps the app in the tray; quitting does not stop central work.",
		merge_scope_reload: "PR scope changed; your selected preview is retained. Load and review it again before merging.",
		metadata_diff: "Content comparison",
		metadata_before: "Before",
		metadata_intended: "Intended",
		metadata_observed: "Observed",
		scope_stack_rebase: "Upper branch rebase",
		scope_dependency: "Branch dependency",
		metadata_edit: "Edit PR title and description",
		metadata_title: "PR title",
		metadata_disabled: "This repository has not enabled allow_pr_update.",
		metadata_race_limit: "Compare title/body before saving and read back after writing. GitHub has no atomic compare-and-write; edits in the final read/write window can still be overwritten.",
		metadata_result_help: "Operation details retain before, intended and observed content. On conflict, reload and edit again; no automatic overwrite or undo.",
		metadata_pending: "PR was modified; readback verification is pending.",
		merge_scope: "Merge scope",
		merge_method: "Merge method",
		merge_commit_range: "Review complete BASE..HEAD: {count} commits",
		merge_preview_fixed: "This preview fixes head, base and scope; changing method reloads it.",
		scope_single_pr: "No other PR was found to be merged.",
		scope_native_stack: "Native stack",
		scope_branch_chain: "Dependent branch chain",
		scope_indirect_merge: "Indirect merge candidate",
		scope_would_merge: "Affects other PRs",
		scope_candidate: "Included commits",
		merged_newer_base: "Merged onto a newer base: {count} other commits will ship too.",
		close: "Close",
		nav_projects: "Projects",
		projects_help: "Projects and work items are the connector's own records: goals, the request verbatim, acceptance, steps, and the sessions, checkpoints, operations and PRs that carried them. A rename never changes an ID; order and pins only change the display.",
		new_project_name: "New project name",
		add_project: "Add",
		show_archived: "Show archived",
		no_projects: "No projects yet.",
		new_sub_project: "Sub-project name",
		rename: "Rename",
		archive: "Archive",
		restore: "Restore",
		more: "More",
		move_up: "Move up",
		move_down: "Move down",
		pin: "Pin to top",
		unpin: "Unpin",
		wi_done_of: "{done}/{total} done",
		wi_state_todo: "to do",
		wi_state_doing: "in progress",
		wi_state_waiting: "waiting",
		wi_state_done: "done",
		wi_state_awaiting_approval: "done? (to confirm)",
		wi_err_VERSION_CONFLICT: "Someone changed this meanwhile; the latest version was loaded (your edits in the form are kept). Check it and save again.",
		linked_back: "linked to this work item",
		wi_err_ORDER_CHANGED: "The order changed meanwhile; it was reloaded. Reorder again.",
		wi_err_PIN_CHANGED: "The pin changed meanwhile; it was reloaded.",
		wi_err_CONTENT_CHANGED: "The content changed while you were reading it; read the new content, then decide.",
		wi_err_NAME_TAKEN: "Another project has this name.",
		wi_err_HAS_CHILDREN: "Archive its sub-projects first.",
		wi_err_PARENT_ARCHIVED: "Its parent is archived; restore the parent first.",
		wi_err_PINNED_FIRST: "Pinned entries stay above the others; unpin it to move it down.",
		wi_err_STEPS_OPEN: "Some steps are not checked; check them (or remove the ones not needed) before marking it done.",
		wi_err_CYCLE: "It cannot move under itself.",
		wi_err_LINK_TARGET_NOT_FOUND: "Nothing to link: the connector has never seen it.",
		wi_err_NOTHING_TO_DECIDE: "Nobody claimed it is done; there is nothing to decide.",
		new_item_title: "New work item",
		add_item: "Add",
		work_items: "Work items",
		name: "Name",
		description: "Description",
		repositories: "Repositories",
		task_project: "Task Service project name",
		save: "Save",
		archived: "archived",
		sub_projects: "Sub-projects",
		new_child_item: "Child item title",
		new_branch_item: "Branch title (same level)",
		archive_with_children: "Archive (with its children)",
		needs_decision: "your decision",
		no_items: "No work items yet.",
		link_missing: "no longer found",
		needs_manage_scope: "Your token lacks the manage scope, so it cannot change projects or work items; issue one with --scope manage.",
		needs_approve_scope: "Your token lacks the approve scope, so it cannot accept work as done; issue one with --scope approve.",
		accept_done: "Accept as done",
		mark_done: "Mark done",
		keep_working: "Not done: keep working",
		approved_by: "{who} accepted it as done ({time}). Editing the content asks again.",
		claimed_done: "{who} says this is done and waits for you. You accept the content shown here.",
		steps_all_checked: "Every step is checked. Mark it done, or keep working?",
		goal: "Goal",
		request: "Request (verbatim)",
		acceptance: "Acceptance",
		steps_title: "Steps",
		parent_id: "Parent",
		remove: "Remove",
		new_step: "New step",
		link_session: "Session",
		link_checkpoint: "Checkpoint",
		link_operation: "Operation",
		link_task: "Task",
		link_pull_request: "PR",
		link_ref_hint: "Target",
		link_ref_session: "host/session_id",
		link_ref_checkpoint: "cp_…",
		link_ref_operation: "op_…",
		link_ref_task: "task ID",
		link_ref_pull_request: "owner/name#123",
		link: "Link",
		links: "Related",
		no_links: "Nothing linked yet.",
		no_steps: "No steps.",
		children: "Children",
		derived: "Branched from here",
		history: "History",
		derived_from: "Branched from",
		start_from_checkpoint: "Start agent work from this checkpoint",
		claimed_by: "{who} says done",
		linked_items: "Work items",
		ev_work_item_created: "Created",
		ev_work_item_updated: "Edited",
		ev_work_item_state: "State",
		ev_work_item_approved: "Accepted as done",
		ev_work_item_continued: "Sent back",
		ev_work_item_linked: "Linked",
		ev_work_item_unlinked: "Unlinked",
		ev_work_item_archived: "Archived",
		ev_work_item_restored: "Restored",
		ev_work_item_pinned: "Pinned",
		ev_work_item_unpinned: "Unpinned",
		nav_home: "Pending",
		nav_sessions: "Sessions",
		nav_delivery: "Delivery",
		nav_operations: "Operations",
		nav_settings: "Connection",
		tab_needs_you: "Needs you",
		tab_to_confirm: "To confirm",
		empty_needs_you: "Nothing needs you right now.",
		empty_to_confirm: "Nothing is waiting.",
		stale: "stale",
		stale_reason_host_unreachable: "host unreachable",
		stale_reason_host_not_refreshed: "not refreshed",
		stale_reason_not_enumerated: "missing from last listing",
		stale_reason_gone: "gone",
		stale_reason_never_observed: "not observed yet",
		read_only: "API read-only",
		managed: "Connector-managed",
		provenance_manual: "created in BAT",
		provenance_connector_managed: "created by the connector",
		provenance_unknown: "unknown origin",
		state_streaming: "working",
		state_loaded: "loaded",
		state_unloaded: "unloaded",
		pending_ask_user: "asking you",
		pending_permission: "waiting for permission",
		host: "Host",
		workspace: "Workspace",
		title: "Title",
		agent: "Agent",
		state: "State",
		activity: "Last activity",
		observed: "Observed",
		all_hosts: "All hosts",
		all_access: "All",
		only_managed: "Connector-managed only",
		only_read_only: "Read-only only",
		load_more: "Load more",
		messages: "Messages",
		send: "Send",
		send_placeholder: "Message for this managed session…",
		interrupt: "Interrupt turn",
		answer: "Answer",
		allow: "Allow",
		deny: "Deny",
		read_only_note: "A person created this session in BAT, so the API never writes to it. To have an agent continue, start a new managed session from its commit.",
		continue_from_checkpoint: "Start agent work from this version",
		checkpoints: "Checkpoints",
		checkpoint_help: "Records this session's current commit and recent conversation (read-only; the session and its folder are not changed). Agent work started from it runs in the connector's own clone on a new branch and session.",
		create_checkpoint: "Record this version",
		no_checkpoints: "No checkpoints yet.",
		excerpt_count: "{n} messages",
		commit: "Commit",
		checkpoint_note_placeholder: "What should happen next (kept verbatim; optional)…",
		dirty_unknown: "Uncommitted changes: not observed (no SSH alias for this host); none are carried over.",
		source_advanced: "The source has newer commits; this checkpoint stays at its commit. Record again to include them.",
		started_from: "This session was started from version {commit}:",
		source_session: "source session",
		dirty_warning: "{n} uncommitted change(s) at capture time are not carried over.",
		continue_placeholder: "What should the agent do next…",
		start_agent_work: "Start agent work",
		open_new_session: "Open the new session",
		checkpoint_unavailable: "This host lacks managed_roots, an SSH alias or the write/orchestrate tiers, so work cannot start from a checkpoint here.",
		needs_start_scope: "Your token lacks the start scope, so it cannot start agent work; issue one with --scope start.",
		confined_note: "The working directory alone offers no protection. Limits come from start options and account evidence; individual approvals may permit outside writes.",
		confinement_none: "No proven execution limit",
		confinement_prompt_gated: "Prompt gated",
		confinement_host_account: "Host account",
		confinement_os_sandbox: "OS sandbox",
		confinement_os_pending: "OS sandbox (live verification pending)",
		confinement_evidence: "Confinement evidence",
		confinement_creation: "Creation limits",
		confinement_current: "Current verification",
		confinement_options: "Start options",
		confinement_gap: "Coverage gap",
		confinement_status_verified: "Verified",
		confinement_status_options_confirmed: "Options confirmed",
		confinement_current_unknown: "Current confinement unknown",
		confinement_current_mismatch: "Confinement mismatch",
		confinement_status_unknown: "Unknown",
		confinement_status_mismatch: "Record mismatch",
		confinement_status_pending: "Pending",
		confinement_gap_sandbox_enforcement_unverified: "W12 live enforcement verification is pending",
		confinement_gap_prompt_rules_are_not_os_isolation: "Existing approvals and shell commands can permit outside writes",
		confinement_gap_task_recipe_compatibility: "Task Service test behavior is preserved; no additional execution restriction",
		confinement_gap_execution_restriction_unverified: "No execution restriction evidence",
		confinement_gap_legacy_evidence_missing: "Legacy creation evidence is missing; no automatic upgrade",
		confinement_claude_note: "Claude uses default: unapproved edits and Bash ask for approval. Existing approval rules still apply; there is no OS write isolation. Consider Codex. Individual approvals may permit outside writes.",
		confinement_codex_note: "Codex uses workspace-write / on-request. Live enforcement is unverified; BAT cannot configure network or writable roots, so installs and localhost tests may be restricted. Individual approvals may escape these limits.",
		confinement_account_note: "The BAT account was checked against declared personal roots. Claude may use acceptEdits; only those roots are covered and the account is checked again before starting.",
		confinement_account_blocked: "A host account boundary is declared but its check has not passed. New sessions will be refused; fix the host configuration. Reason: {reason}.",
		confinement_account_recheck: "The account boundary is checked again when the session starts. If it passes, Claude may use acceptEdits; a supported hardening gap uses plain default. Other check failures refuse the start.",
		confinement_account_fallback: "The account check reports {reason}. Claude uses plain default without acceptEdits.",
		repository: "Repository",
		pull_number: "PR number",
		load_pr: "Load PR",
		head: "Head",
		base: "Base",
		checks: "Checks",
		checks_summary: "{total} total, {pending} pending, {failed} failed",
		mergeable: "Mergeable",
		merge: "Merge PR",
		deploy_to: "Deploy to {env}",
		merge_and_deploy_to: "Merge and deploy to {env}",
		retry_deploy: "Retry deploying this version",
		merged_sha: "Merged commit",
		op_accepted: "accepted",
		op_running: "running",
		op_waiting_checks: "waiting for checks",
		op_waiting_external: "waiting for GitHub/deploy",
		op_needs_attention: "needs attention",
		op_uncertain: "outcome unknown, reading back",
		op_succeeded: "done",
		op_failed: "failed",
		op_cancelled: "cancelled",
		cancel: "Cancel",
		resume: "Resume",
		resume_help: "Run it again after fixing the cause: finished steps are not repeated and unproven ones are read back, never re-sent.",
		steps: "Steps",
		action: "Action",
		actor: "Actor",
		created: "Created",
		error: "Error",
		reason: "Reason",
		token: "API token",
		token_help: "Issue one with batc api-token issue; it stays in this browser.",
		connect: "Connect",
		remember: "Remember on this computer",
		disconnect: "Disconnect",
		connected_as: "Connected as {actor} ({scopes})",
		need_token: "Enter an API token under Connection first.",
		unreachable_hosts: "Host problems",
		loading: "Loading…",
		forbidden_scope: "Your token lacks this scope.",
		queue_behind: "Queue behind the running turn",
		no_messages: "No messages yet.",
		update_pr_results: "Update PR results",
		update_pr_help: "Put the chosen results into this PR's head branch: a normal push, never forced; your local folders are not changed.",
		needs_integrate_scope: "Needs the integrate scope: issue a token with --scope integrate.",
		integration_no_host: "No integrate host of this repository has an SSH alias, a managed root and the write/orchestrate tiers.",
		kind_checkpoint: "your checkpoint",
		kind_checkpoint_run: "agent result",
		kind_branch: "GitHub branch",
		previewing: "Previewing… (the first time builds the managed integration area and can take minutes)",
		start_integration_conflict: "Start integrating (item {n} is expected to conflict; it will stop there)",
		normal_push: "normal push",
		push_access_ok: "can push",
		push_access_denied: "this host's git credentials cannot push (set a deploy key or credential)",
		push_access_unknown: "push access not confirmed",
		plan_fast_forward: "fast-forward",
		plan_merge: "merge",
		plan_pick: "pick",
		plan_already_included: "already in PR",
		plan_conflict: "expected conflict",
		plan_not_predicted: "not checked",
		plan_unrelated: "no shared history",
		n_commits: "{n} commit(s)",
		n_files: "{n} file(s)",
		foreign_commit: "not from the chosen source",
		overlapping_files: "Files touched by more than one:",
		preview_expired: "This preview has expired (over an hour old, or the PR head changed).",
		previewed_at: "Previewed {time} · valid for an hour",
		preview_again: "Preview again",
		branch_on_github: "branch name on GitHub",
		add: "Add",
		add_branch: "Add branch",
		delivered_to: "sent to #{n}",
		agent_results: "Agent results",
		your_checkpoints: "Your checkpoints",
		still_working: "working",
		done: "done",
		none: "None",
		selected_in_order: "Selected (integrated in this order)",
		integration_done: "PR updated: {old} → {new}, {n} commit(s) added. Your local folders are not updated; pull in BAT to sync.",
		integration_INTEGRATION_CONFLICT: "One item conflicts. The items before it are composed in the connector's area and nothing was pushed. Hand it to an agent to resolve there, or cancel and preview again without it.",
		integration_RESOLUTION_INCOMPLETE: "The conflict is not resolved yet (nothing committed). Resume after the agent runs `git commit --no-edit`.",
		integration_RESOLUTION_INVALID: "The resolution does not qualify (exactly one merge commit, no uncommitted changes or conflict markers); fix it, then Resume.",
		integration_waiting_resolver: "Waiting for the agent to finish resolving (it is still working)",
		hand_to_agent: "Ask an agent to resolve",
		handoff_started: "A session is resolving it; Resume after it commits.",
		integration_REMOTE_MOVED: "Someone pushed to the PR meanwhile; nothing was overwritten or pushed. Cancel and preview again at the new head.",
		integration_PUSH_REJECTED: "GitHub refused the push (branch protection or signature rules).",
		integration_PUSH_AUTH_FAILED: "This host's git credentials cannot push; fix them, then Resume.",
		integration_REMOTE_REWOUND_BEFORE_PUSH: "Pushed, but the branch was moved back just before; check the PR, then Resume to finish.",
		integration_REMOTE_REF_RECREATED: "Pushed, but the branch had been deleted just before; check the PR, then Resume to finish.",
		integration_UNCERTAIN_UNRESOLVED: "The push outcome cannot be confirmed yet (the remote is unreadable); the connector never pushes again on a guess.",
		integration_uncertain: "Confirming the push (the remote is read first; nothing is pushed twice)",
		integration_waiting: "Pushed; waiting for GitHub to show the new head",
		integration_running: "Updating the PR…",
		cancel_and_preview: "Cancel and preview again",
		receipts: "Per-source records",
		receipt_pending: "pending",
		receipt_composed: "composed (not pushed)",
		receipt_already_included: "already in PR",
		receipt_conflict: "conflict",
		receipt_delivered: "delivered",
		receipt_not_delivered: "not delivered",
		receipt_unknown: "unknown (the push was never proven)",
		receipt_resolved: "resolved (not pushed)",
		integration_PUSH_UNPROVEN: "The PR branch is at its old head, but the composed commit exists on GitHub: an earlier push may have landed and been set back. Nothing is pushed again; check the PR, then cancel and preview again."
	}
};
var lang = (navigator.language || "zh-TW").toLowerCase().startsWith("zh") ? "zh-TW" : "en";
function t(key, vars = {}) {
	return (STRINGS[lang][key] ?? STRINGS["zh-TW"][key] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}
async function invoke(cmd, args = {}, options) {
	return window.__TAURI_INTERNALS__.invoke(cmd, args, options);
}
function isTauri() {
	return !!(globalThis || window).isTauri;
}
//#endregion
//#region src/transport/index.ts
var nativeDesktop = isTauri();
var nativeStatus = () => invoke("native_status");
var nativeConnect = () => invoke("connector_connect");
var nativeDisconnect = () => invoke("connector_disconnect");
var openExternal = (url) => invoke("open_external", { url });
async function connectorRequest(method, path, body, key, browserToken) {
	if (nativeDesktop) return invoke("connector_request", { input: {
		method,
		path,
		body: body ?? null,
		idempotency_key: key ?? null
	} });
	const headers = { Authorization: `Bearer ${browserToken}` };
	if (body !== void 0) headers["Content-Type"] = "application/json";
	if (key) headers["Idempotency-Key"] = key;
	const res = await fetch(`/api/v1${path}`, {
		method,
		headers,
		body: body === void 0 ? void 0 : JSON.stringify(body)
	});
	return {
		status: res.status,
		data: await res.json().catch(() => ({}))
	};
}
//#endregion
//#region src/state/events.ts
function consumePage(page, cursor, emit) {
	if (page.reset_required || page.reset || page.head_cursor < cursor) {
		emit({
			seq: 0,
			kind: "reset",
			resource_type: "reset"
		});
		cursor = 0;
	}
	for (const event of page.events) {
		if (event.seq <= cursor) continue;
		emit(event);
		cursor = event.seq;
	}
	if (Number.isSafeInteger(page.next_cursor) && page.next_cursor >= cursor && page.next_cursor <= page.head_cursor) cursor = page.next_cursor;
	return cursor;
}
async function consumePageAsync(page, cursor, emit) {
	if (page.reset_required || page.reset || page.head_cursor < cursor) {
		await emit({
			seq: 0,
			kind: "reset",
			resource_type: "reset"
		});
		cursor = 0;
	}
	const pending = [];
	const next = consumePage({
		...page,
		reset: false,
		reset_required: false
	}, cursor, (event) => {
		pending.push(Promise.resolve().then(() => emit(event)));
	});
	await settleRefreshes(pending);
	return next;
}
async function settleRefreshes(pending) {
	const results = await Promise.allSettled(pending);
	for (const result of results) if (result.status === "rejected") throw result.reason;
}
function storageScope(endpoint, actor, server = "legacy", principal = actor) {
	return [
		endpoint,
		server,
		principal,
		actor
	].map(encodeURIComponent).join(":");
}
//#endregion
//#region src/app.js
var TOKEN_KEY = "batc.dashboard.token";
var state = {
	token: null,
	caps: null,
	lastEvent: 0,
	listeners: new Set(),
	namespace: "",
	epoch: 0,
	online: false,
	viewReady: false,
	sync: null,
	endpoint: "",
	connectionError: null,
	refreshCycle: null
};
async function activate(caps, endpoint = location.origin, reset = false) {
	state.epoch++;
	state.connectionError = null;
	state.online = false;
	state.viewReady = false;
	state.caps = caps;
	state.endpoint = endpoint;
	state.sync = null;
	let bootstrap;
	try {
		bootstrap = await api("GET", "/bootstrap");
	} catch (e) {
		if (e.status !== 404) throw e;
	}
	if (bootstrap) {
		const sync = bootstrap.sync;
		if (sync?.version !== 1 || !sync.server_id || !sync.principal_id || !Number.isSafeInteger(sync.checkpoint?.cursor) || sync.checkpoint.cursor < 0 || !sync.checkpoint.token || bootstrap.capabilities?.actor !== caps.actor) throw new Error("Invalid central bootstrap identity");
		state.caps = bootstrap.capabilities;
		state.namespace = storageScope(endpoint, caps.actor, sync.server_id, sync.principal_id);
		state.sync = sync.checkpoint;
		if (!reset) try {
			const saved = JSON.parse(localStorage.getItem(`batc.sync.${state.namespace}`));
			if (Number.isSafeInteger(saved?.cursor) && saved.cursor >= 0 && typeof saved.token === "string" && saved.token) state.sync = saved;
		} catch {}
		state.lastEvent = state.sync.cursor;
	} else {
		state.namespace = storageScope(endpoint, caps.actor);
		state.lastEvent = 0;
	}
	state.online = true;
}
function saveCursor() {
	if (state.sync) try {
		localStorage.setItem(`batc.sync.${state.namespace}`, JSON.stringify(state.sync));
	} catch {}
}
function disconnect() {
	state.epoch++;
	clearToken();
	state.token = null;
	state.caps = null;
	state.lastEvent = 0;
	state.online = false;
	state.viewReady = false;
	state.sync = null;
}
function loadToken() {
	if (nativeDesktop) return null;
	try {
		return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}
function saveToken(token, remember) {
	if (nativeDesktop) return;
	try {
		sessionStorage.setItem(TOKEN_KEY, token);
		if (remember) localStorage.setItem(TOKEN_KEY, token);
		else localStorage.removeItem(TOKEN_KEY);
	} catch {}
}
function clearToken() {
	try {
		sessionStorage.removeItem(TOKEN_KEY);
		localStorage.removeItem(TOKEN_KEY);
	} catch {}
}
function h(tag, attrs = {}, ...children) {
	const el = document.createElement(tag);
	for (const [k, v] of Object.entries(attrs || {})) {
		if (v === null || v === void 0 || v === false) continue;
		if (k === "class") el.className = v;
		else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
		else el.setAttribute(k, v === true ? "" : String(v));
	}
	for (const c of children.flat()) {
		if (c === null || c === void 0 || c === false) continue;
		el.append(c instanceof Node ? c : document.createTextNode(String(c)));
	}
	if (nativeDesktop && tag === "a" && attrs.href && !attrs.href.startsWith("#")) el.addEventListener("click", async (event) => {
		event.preventDefault();
		try {
			await openExternal(attrs.href);
		} catch (error) {
			document.getElementById("main").prepend(errorBox(error));
		}
	});
	return el;
}
var chip = (text, cls = "") => h("span", { class: `chip ${cls}` }, text);
function when(iso) {
	if (!iso) return "";
	const d = new Date(iso);
	return isNaN(d) ? iso : d.toLocaleString();
}
async function draftId(scope, request) {
	const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(request)));
	return `${scope}.${[...new Uint8Array(digest).slice(0, 12)].map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}
var TERMINAL = [
	"succeeded",
	"failed",
	"cancelled"
];
function assertConnection(connection) {
	if (connection.epoch !== state.epoch || connection.namespace !== state.namespace) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed while preparing the operation");
}
async function keyFor(scope, connection) {
	assertConnection(connection);
	const k = `batc.key.${connection.namespace}.${scope}`;
	let saved = null;
	try {
		const raw = localStorage.getItem(k);
		try {
			saved = JSON.parse(raw);
		} catch {
			saved = raw ? { key: raw } : null;
		}
	} catch {
		saved = null;
	}
	if (saved?.key && saved.op) try {
		const op = (await api("GET", `/operations/${saved.op}`)).operation;
		assertConnection(connection);
		if (TERMINAL.includes(op.status)) saved = null;
	} catch (e) {
		if (e.code === "CONNECTION_CHANGED") throw e;
		if (e.status === 404) saved = null;
	}
	assertConnection(connection);
	if (saved?.key) return saved.key;
	const key = crypto.randomUUID();
	try {
		localStorage.setItem(k, JSON.stringify({ key }));
	} catch {}
	return key;
}
function rememberOp(scope, key, op, namespace) {
	try {
		localStorage.setItem(`batc.key.${namespace}.${scope}`, JSON.stringify({
			key,
			op
		}));
	} catch {}
}
function dropKey(scope, namespace) {
	try {
		localStorage.removeItem(`batc.key.${namespace}.${scope}`);
	} catch {}
}
var ApiError = class extends Error {
	constructor(status, code, message) {
		super(message || code);
		this.status = status;
		this.code = code;
	}
};
async function api(method, path, body, key) {
	if (!state.token) throw new ApiError(401, "UNAUTHORIZED", t("need_token"));
	if (method === "POST" && (!state.online || !state.viewReady)) throw new ApiError(0, "CENTRAL_OFFLINE", t("offline_actions_paused"));
	const epoch = state.epoch;
	const { status, data } = await connectorRequest(method, path, body, key, state.token);
	if (epoch !== state.epoch) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed while the request was in flight");
	if (status < 200 || status >= 300) throw new ApiError(status, data.error?.code, data.error?.message);
	return data;
}
function errorBox(e) {
	if (state.refreshCycle) state.refreshCycle.error ||= e;
	return h("p", { class: "error" }, e.status === 403 && e.code === "FORBIDDEN" ? t("forbidden_scope") : `${e.code || ""} ${e.message || e}`);
}
async function submit(action, target, params, preconditions, scope) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace
	};
	const request = {
		action,
		target,
		params,
		preconditions
	};
	scope = await draftId(scope, request);
	assertConnection(connection);
	const key = await keyFor(scope, connection);
	assertConnection(connection);
	try {
		const out = await api("POST", "/operations?wait=3", request, key);
		assertConnection(connection);
		if (TERMINAL.includes(out.operation.status)) dropKey(scope, connection.namespace);
		else rememberOp(scope, key, out.operation.operation_id, connection.namespace);
		return out.operation;
	} catch (e) {
		if (e.status && e.status < 500 && e.status !== 409) dropKey(scope, connection.namespace);
		throw e;
	}
}
function onEvents(fn) {
	state.listeners.add(fn);
	return () => state.listeners.delete(fn);
}
async function streamEvents() {
	const live = document.getElementById("live");
	for (;;) {
		if (!state.token || !state.viewReady) {
			live.className = "live down";
			live.textContent = state.token ? t("sync_waiting") : "";
			await sleep(1e3);
			continue;
		}
		const epoch = state.epoch, view = generation;
		let cycle;
		try {
			const before = state.lastEvent;
			const page = await api("GET", `/events?after=${before}&limit=100${state.sync ? `&checkpoint=${encodeURIComponent(state.sync.token)}` : ""}`);
			if (epoch !== state.epoch || view !== generation || !state.viewReady) continue;
			cycle = { error: null };
			state.refreshCycle = cycle;
			live.className = "live down";
			live.textContent = t("sync_waiting");
			const cursor = await consumePageAsync(page, before, (ev) => {
				return settleRefreshes([...state.listeners].map((fn) => Promise.resolve().then(() => fn(ev))));
			});
			if (epoch !== state.epoch || view !== generation || !state.viewReady) continue;
			if (cycle.error) throw cycle.error;
			if (state.sync) {
				if (page.sync?.checkpoint?.cursor !== cursor || !page.sync?.checkpoint?.token) throw new Error("Invalid central event checkpoint");
				state.sync = page.sync.checkpoint;
			}
			state.lastEvent = cursor;
			saveCursor();
			state.refreshCycle = null;
			state.online = true;
			live.className = "live ok";
			live.textContent = t("desktop_polling");
			if (!page.has_more || cursor <= before) await sleep(1e3);
		} catch (error) {
			if (epoch !== state.epoch || view !== generation) continue;
			if (state.refreshCycle === cycle) state.refreshCycle = null;
			state.online = false;
			live.className = "live down";
			live.textContent = t("offline_actions_paused");
			if (error.code === "EVENT_CURSOR_RESET") {
				const previous = {
					namespace: state.namespace,
					sync: state.sync
				};
				try {
					await activate(state.caps, state.endpoint, true);
					if (state.namespace === previous.namespace && (editing || typing())) idleReload = route;
					else await route();
				} catch {
					state.sync = previous.sync;
					state.viewReady = true;
				}
			}
			await sleep(3e3);
		} finally {
			if (state.refreshCycle === cycle) state.refreshCycle = null;
		}
	}
}
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function debounce(fn, ms) {
	let id;
	return () => {
		clearTimeout(id);
		id = setTimeout(fn, ms);
	};
}
function assertView(connection) {
	assertConnection(connection);
	if (connection.generation !== generation) throw new ApiError(0, "VIEW_CHANGED", "View changed during refresh");
}
function debounceRefresh(fn, ms) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	let id, waiting = [];
	return () => new Promise((resolve, reject) => {
		waiting.push({
			resolve,
			reject
		});
		clearTimeout(id);
		id = setTimeout(async () => {
			const batch = waiting;
			waiting = [];
			try {
				assertView(connection);
				await fn();
				assertView(connection);
				batch.forEach((p) => p.resolve());
			} catch (error) {
				batch.forEach((p) => p.reject(error));
			}
		}, ms);
	});
}
function confinementLabel(s) {
	const level = s.confinement?.level || "none";
	return t(level === "os_sandbox" && s.confinement?.verification?.status !== "verified" ? "confinement_os_pending" : "confinement_" + level);
}
function confinementNote(host, agent) {
	const note = h("p", {
		class: "muted",
		"data-confinement-note": ""
	});
	const update = () => {
		const account = state.caps?.hosts?.find((x) => x.host === host)?.confinement?.host_account;
		const effect = account?.start_effect;
		if (effect === "refused") {
			note.textContent = t("confinement_account_blocked", { reason: account.reason });
			if (agent.value === "codex") note.textContent += " " + t("confinement_codex_note");
		} else if (agent.value === "codex") note.textContent = t("confinement_codex_note");
		else if (effect === "verified") note.textContent = t("confinement_account_note");
		else if (effect === "recheck") note.textContent = t("confinement_account_recheck");
		else note.textContent = (effect === "fallback_default" && account?.declared ? t("confinement_account_fallback", { reason: account.reason }) + " " : "") + t("confinement_claude_note");
	};
	agent.addEventListener("change", update);
	note.setHost = (value) => {
		host = value;
		update();
	};
	update();
	return note;
}
function confinementDetails(s) {
	const record = s.confinement;
	const current = s.current_verification;
	return h("details", {}, h("summary", {}, t("confinement_evidence")), h("p", { class: "muted" }, t("confined_note")), h("dl", { class: "kv" }, h("dt", {}, t("confinement_creation")), h("dd", {}, confinementLabel(s)), h("dt", {}, t("confinement_current")), h("dd", {}, t("confinement_status_" + (current?.status || "unknown"))), h("dt", {}, t("confinement_options")), h("dd", {}, h("code", {}, JSON.stringify(record?.options || {}))), h("dt", {}, t("confinement_evidence")), h("dd", {}, h("code", {}, JSON.stringify(record?.evidence || {}))), h("dt", {}, t("confinement_gap")), h("dd", {}, record?.gap ? t("confinement_gap_" + record.gap) : t("none")), h("dt", {}, t("confinement_current")), h("dd", {}, h("code", {}, JSON.stringify(current || { status: "unknown" })))));
}
function sessionBadges(s) {
	return [
		chip(s.host),
		chip(confinementLabel(s), s.confinement?.level === "none" ? "readonly" : "info"),
		s.confinement?.level && s.confinement.level !== "none" && ["unknown", "mismatch"].includes(s.current_verification?.status) ? chip(t("confinement_current_" + s.current_verification.status), "stale") : null,
		s.api_access === "managed" ? chip(t("managed"), "managed") : chip(t("read_only"), "readonly"),
		s.stale ? chip(`${t("stale")} · ${t("stale_reason_" + s.stale_reason)}`, "stale") : null,
		s.pending ? chip(t("pending_" + s.pending.kind), "stale") : null
	];
}
function light(s) {
	return h("span", {
		class: `light ${s.pending ? "pending" : s.streaming ? "streaming" : s.loaded ? "ok" : ""}`,
		title: s.streaming ? t("state_streaming") : s.loaded ? t("state_loaded") : t("state_unloaded")
	});
}
function sessionRow(s) {
	return h("div", { class: "row" }, light(s), h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/session/${encodeURIComponent(s.host)}/${encodeURIComponent(s.session_id)}`
	}, s.title || s.session_id), h("div", { class: "muted" }, [
		s.workspace,
		s.agent_kind,
		s.worktree_branch
	].filter(Boolean).join(" · "))), h("div", { class: "actions session-badges" }, ...sessionBadges(s)), h("span", { class: "muted" }, when(s.last_activity_at)));
}
var epoch = (x) => x ? new Date(x * 1e3).toISOString() : "";
function opStatus(op) {
	return h("span", { class: `status-${op.status}` }, t("op_" + op.status));
}
function opRow(op) {
	return h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/op/${op.operation_id}`
	}, op.action), h("div", { class: "muted" }, [op.actor, when(epoch(op.created_at))].join(" · ")), op.status_reason ? h("div", { class: "muted" }, op.status_reason) : null), opStatus(op), op.error_code ? chip(op.error_code, "bad") : null);
}
async function viewHome(main) {
	const tab = sessionStorage.getItem("batc.tab") || "needs";
	const panel = h("div", { class: "panel" });
	const tabs = h("div", { class: "tabs" }, h("button", {
		class: tab === "needs" ? "on" : "",
		onclick: () => {
			sessionStorage.setItem("batc.tab", "needs");
			route();
		}
	}, t("tab_needs_you")), h("button", {
		class: tab === "confirm" ? "on" : "",
		onclick: () => {
			sessionStorage.setItem("batc.tab", "confirm");
			route();
		}
	}, t("tab_to_confirm")));
	main.append(h("h1", {}, t("nav_home")), tabs, panel);
	const render = async () => {
		panel.replaceChildren(h("p", { class: "muted" }, t("loading")));
		try {
			if (tab === "needs") {
				const [sessions, ops, hosts, decide] = await Promise.all([
					api("GET", "/sessions?attention=true&limit=50"),
					api("GET", "/operations?status=needs_attention,uncertain&limit=50"),
					api("GET", "/hosts"),
					api("GET", "/work-items?pending=true&limit=50")
				]);
				const rows = [
					...hosts.hosts.filter((x) => x.stale).map((x) => h("div", { class: "row" }, h("span", { class: "light bad" }), h("div", { class: "grow" }, h("div", { class: "title" }, `${t("unreachable_hosts")}: ${x.host}`), h("div", { class: "muted" }, x.error || t("stale_reason_" + x.stale_reason))))),
					...decide.work_items.map(workItemRow),
					...sessions.sessions.map(sessionRow),
					...ops.operations.map(opRow)
				];
				panel.replaceChildren(...rows.length ? rows : [h("p", { class: "muted" }, t("empty_needs_you"))]);
			} else {
				const ops = await api("GET", "/operations?status=accepted,running,waiting_checks,waiting_external&limit=50");
				panel.replaceChildren(...ops.operations.length ? ops.operations.map(opRow) : [h("p", { class: "muted" }, t("empty_to_confirm"))]);
			}
		} catch (e) {
			panel.replaceChildren(errorBox(e));
		}
	};
	await render();
	return onEvents(debounceRefresh(render, 500));
}
async function viewSessions(main) {
	const q = new URLSearchParams(sessionStorage.getItem("batc.sessions") || "");
	const hostSel = h("select", {}, h("option", { value: "" }, t("all_hosts")));
	const accessSel = h("select", {}, h("option", { value: "" }, t("all_access")), h("option", { value: "managed" }, t("only_managed")), h("option", { value: "read_only" }, t("only_read_only")));
	const list = h("div", { class: "panel" });
	const more = h("button", {
		class: "secondary",
		hidden: true
	}, t("load_more"));
	main.append(h("h1", {}, t("nav_sessions")), h("div", { class: "filters" }, hostSel, accessSel), list, more);
	try {
		for (const x of (await api("GET", "/hosts")).hosts) hostSel.append(h("option", { value: x.host }, x.host));
	} catch (e) {
		list.replaceChildren(errorBox(e));
		return;
	}
	hostSel.value = q.get("host") || "";
	accessSel.value = q.get("access") || "";
	let cursor = null;
	const load = async (reset) => {
		const p = new URLSearchParams({ limit: "50" });
		if (hostSel.value) p.set("host", hostSel.value);
		if (accessSel.value) p.set("access", accessSel.value);
		sessionStorage.setItem("batc.sessions", p.toString());
		if (!reset && cursor) p.set("cursor", cursor);
		try {
			const page = await api("GET", `/sessions?${p}`);
			const rows = page.sessions.map(sessionRow);
			if (reset) list.replaceChildren(...rows);
			else list.append(...rows);
			cursor = page.next_cursor;
			more.hidden = !cursor;
		} catch (e) {
			list.replaceChildren(errorBox(e));
		}
	};
	hostSel.onchange = accessSel.onchange = () => load(true);
	more.onclick = () => load(false);
	await load(true);
	const reload = debounceRefresh(() => load(true), 800);
	return onEvents((ev) => {
		if (ev.resource_type === "session" || ev.resource_type === "host") return reload();
	});
}
async function viewSession(main, host, sid) {
	const head = h("div", { class: "panel" });
	const msgs = h("div", { class: "panel" });
	const controls = h("div", { class: "panel" });
	main.append(head, controls, h("h2", {}, t("messages")), msgs);
	let row, from, linked;
	try {
		({session: row, started_from: from, work_items: linked} = await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}`));
	} catch (e) {
		head.replaceChildren(errorBox(e));
		return;
	}
	if (!head.isConnected) return;
	head.replaceChildren(h("h1", {}, row.title || sid), h("div", { class: "actions" }, ...sessionBadges(row)), h("dl", { class: "kv" }, h("dt", {}, t("host")), h("dd", {}, row.host), h("dt", {}, t("workspace")), h("dd", {}, row.workspace || ""), h("dt", {}, "Session"), h("dd", {}, h("code", {}, row.session_id)), h("dt", {}, t("agent")), h("dd", {}, [row.agent_kind, row.model].filter(Boolean).join(" · ")), h("dt", {}, "Provenance"), h("dd", {}, t("provenance_" + row.provenance)), h("dt", {}, t("observed")), h("dd", {}, when(row.observed_at))));
	head.append(confinementDetails(row));
	if (from) head.append(h("p", { class: "note" }, t("started_from", { commit: from.commit_sha.slice(0, 12) }), " ", h("a", { href: `#/session/${encodeURIComponent(from.source_host)}/${encodeURIComponent(from.source_session_id)}` }, t("source_session")), " · ", h("a", { href: `#/op/${from.operation_id}` }, from.operation_id)));
	if (linked?.length) head.append(linkedItems(linked));
	const scope = `send.${host}.${sid}`;
	const draftNamespace = state.namespace;
	const cps = checkpointPanel(host, sid);
	main.insertBefore(cps.box, msgs.previousSibling);
	if (row.api_access !== "managed") controls.replaceChildren(h("p", { class: "note" }, t("read_only_note")));
	else {
		const box = h("textarea", { placeholder: t("send_placeholder") });
		try {
			box.value = localStorage.getItem(`batc.draft.${draftNamespace}.${scope}`) || "";
		} catch {}
		box.oninput = () => {
			try {
				localStorage.setItem(`batc.draft.${draftNamespace}.${scope}`, box.value);
			} catch {}
		};
		const status = h("div", { class: "muted" });
		const queue = h("input", {
			type: "checkbox",
			checked: row.streaming
		});
		const send = h("button", {
			class: "primary",
			onclick: async () => {
				if (!box.value.trim()) return;
				send.disabled = true;
				try {
					const op = await submit("session.send", {
						host,
						session_id: sid
					}, {
						text: box.value,
						queue: queue.checked
					}, {}, scope);
					status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
					if (op.status === "succeeded") {
						box.value = "";
						try {
							localStorage.removeItem(`batc.draft.${draftNamespace}.${scope}`);
						} catch {}
					}
				} catch (e) {
					status.replaceChildren(errorBox(e));
				}
				send.disabled = false;
			}
		}, t("send"));
		const stop = h("button", {
			class: "danger",
			onclick: async () => {
				try {
					const op = await submit("session.interrupt", {
						host,
						session_id: sid
					}, { mode: "soft" }, {}, `interrupt.${host}.${sid}`);
					status.replaceChildren(opStatus(op));
				} catch (e) {
					status.replaceChildren(errorBox(e));
				}
			}
		}, t("interrupt"));
		controls.replaceChildren(box, h("div", { class: "actions" }, send, stop, h("label", { class: "muted" }, queue, " ", t("queue_behind"))), status);
		if (row.pending) {
			const pend = row.pending;
			const answerScope = `answer.${host}.${sid}.${pend.toolUseId || ""}`;
			const answer = async (params) => {
				try {
					status.replaceChildren(opStatus(await submit("session.answer", {
						host,
						session_id: sid
					}, {
						...params,
						tool_use_id: pend.toolUseId
					}, {}, answerScope)));
				} catch (e) {
					status.replaceChildren(errorBox(e));
				}
			};
			const pendingBox = h("div", { class: "panel" }, h("div", { class: "title" }, t("pending_" + pend.kind)));
			if (pend.kind === "permission") pendingBox.append(h("p", {}, h("code", {}, pend.toolName || "")), h("p", { class: "msg" }, pend.input_preview || ""), h("div", { class: "actions" }, h("button", {
				class: "primary",
				onclick: () => answer({ permission: "allow" })
			}, t("allow")), h("button", {
				class: "danger",
				onclick: () => answer({ permission: "deny" })
			}, t("deny"))));
			else {
				const fields = (pend.questions || []).map((q) => {
					const input = h("input", { placeholder: t("answer") });
					const picks = (q.options || []).map((o) => h("button", {
						class: "secondary",
						onclick: () => {
							input.value = o;
						}
					}, o));
					pendingBox.append(h("p", {}, q.header ? h("strong", {}, `${q.header} · `) : null, q.question), picks.length ? h("div", { class: "actions" }, ...picks) : null, h("div", { class: "actions" }, input));
					return input;
				});
				pendingBox.append(h("div", { class: "actions" }, h("button", {
					class: "primary",
					onclick: () => answer({ answers: fields.map((f) => f.value) })
				}, t("answer"))));
			}
			controls.prepend(pendingBox);
		}
	}
	const loadMessages = async () => {
		try {
			const items = (await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}/messages?last_n=30`)).messages.map((m) => h("div", { class: `msg ${m.role === "user" ? "user" : ""}` }, h("span", { class: "who" }, `${m.role || ""} · ${when(m.ts)}`), m.text || ""));
			msgs.replaceChildren(...items.length ? items : [h("p", { class: "muted" }, t("no_messages"))]);
		} catch (e) {
			msgs.replaceChildren(errorBox(e));
		}
	};
	await Promise.all([loadMessages(), cps.load()]);
	const reload = debounceRefresh(loadMessages, 800);
	const reloadCps = debounceRefresh(cps.load, 800);
	return onEvents((ev) => {
		return settleRefreshes([ev.resource_id === `${host}/${sid}` ? reload() : Promise.resolve(), ev.resource_type === "checkpoint" ? reloadCps() : Promise.resolve()]);
	});
}
function checkpointPanel(host, sid) {
	const can = (state.caps?.features?.checkpoints || []).includes(host);
	const mayStart = (state.caps?.scopes || []).includes("start");
	const list = h("div", {});
	const status = h("div", { class: "muted" });
	const rows = new Map();
	let preview = null;
	const row = (cp) => rows.get(cp.checkpoint_id) || rows.set(cp.checkpoint_id, buildRow(cp)).get(cp.checkpoint_id);
	const buildRow = (cp) => {
		const instr = h("textarea", { placeholder: t("continue_placeholder") });
		const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
		const out = h("div", { class: "muted" });
		const go = h("button", {
			class: "primary",
			onclick: async () => {
				if (!instr.value.trim()) return;
				go.disabled = true;
				try {
					const op = await submit("checkpoint.continue", { checkpoint_id: cp.checkpoint_id }, {
						instructions: instr.value,
						agent: agent.value
					}, {}, `continue.${cp.checkpoint_id}`);
					out.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				} catch (e) {
					out.replaceChildren(errorBox(e));
				}
				go.disabled = false;
			}
		}, t("start_agent_work"));
		const form = h("div", { hidden: true }, confinementNote(host, agent), instr, h("div", { class: "actions" }, agent, go), out);
		return h("div", { class: "row" }, h("div", { class: "grow" }, h("div", { class: "title" }, h("code", {}, cp.commit_sha.slice(0, 12)), " ", cp.branch || ""), h("div", { class: "muted" }, [
			when(epoch(cp.captured_at)),
			cp.actor,
			t("excerpt_count", { n: cp.excerpt_messages })
		].join(" · ")), cp.dirty ? h("div", { class: "error" }, t("dirty_warning", { n: cp.dirty })) : cp.dirty === null ? h("div", { class: "muted" }, t("dirty_unknown")) : null, preview && preview.head !== cp.commit_sha ? h("div", { class: "muted" }, t("source_advanced")) : null, form), h("button", {
			class: "secondary",
			disabled: !can || !mayStart,
			title: !can ? t("checkpoint_unavailable") : mayStart ? null : t("needs_start_scope"),
			onclick: () => {
				form.hidden = !form.hidden;
			}
		}, t("continue_from_checkpoint")));
	};
	const load = async () => {
		try {
			const page = await api("GET", `/checkpoints?${new URLSearchParams({
				host,
				session_id: sid,
				limit: "10"
			})}`);
			list.replaceChildren(...page.checkpoints.length ? page.checkpoints.map(row) : [h("p", { class: "muted" }, t("no_checkpoints"))]);
		} catch (e) {
			list.replaceChildren(errorBox(e));
		}
	};
	const pick = h("select", {
		"aria-label": t("commit"),
		hidden: true
	});
	const note = h("textarea", {
		placeholder: t("checkpoint_note_placeholder"),
		hidden: true
	});
	let previewFailed = false;
	const loadPreview = async () => {
		if (!can) return;
		try {
			const selectedCommit = pick.value;
			const current = (await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}/checkpoint-preview`)).preview;
			if (!Array.isArray(current?.commits)) throw new Error("Invalid checkpoint preview");
			preview = current;
			pick.replaceChildren(...preview.commits.map((c) => h("option", { value: c.hash }, `${c.hash.slice(0, 10)} · ${c.message}`)));
			if (preview.commits.some((c) => c.hash === selectedCommit)) pick.value = selectedCommit;
			pick.hidden = note.hidden = false;
			create.disabled = false;
			if (previewFailed) status.replaceChildren();
			previewFailed = false;
			if (preview.dirty) status.replaceChildren(h("span", { class: "error" }, t("dirty_warning", { n: preview.dirty })));
		} catch (error) {
			previewFailed = true;
			create.disabled = true;
			status.replaceChildren(errorBox(error));
		}
	};
	const create = h("button", {
		class: "secondary",
		disabled: !can,
		onclick: async () => {
			create.disabled = true;
			try {
				const params = {
					last_n: 20,
					...preview ? { commit: pick.value } : {},
					...note.value.trim() ? { note: note.value.trim() } : {}
				};
				const op = await submit("checkpoint.create", {
					host,
					session_id: sid
				}, params, {}, `checkpoint.${host}.${sid}`);
				if (op.status === "succeeded") note.value = "";
				status.replaceChildren(...[
					opStatus(op),
					op.error_code ? chip(op.error_code, "bad") : null,
					op.status_reason
				].filter(Boolean).flatMap((x) => [x, " "]));
				await load();
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
			create.disabled = !can || previewFailed;
		}
	}, t("create_checkpoint"));
	return {
		box: h("div", { class: "panel" }, h("h2", {}, t("checkpoints")), h("p", { class: "muted" }, t("checkpoint_help")), can ? null : h("p", { class: "muted" }, t("checkpoint_unavailable")), can && !mayStart ? h("p", { class: "muted" }, t("needs_start_scope")) : null, note, h("div", { class: "actions" }, pick, create), status, list),
		load: async () => {
			await loadPreview();
			await load();
		}
	};
}
async function viewDelivery(main) {
	freshPage();
	const repo = h("input", {
		placeholder: "owner/name",
		value: sessionStorage.getItem("batc.repo") || ""
	});
	const num = h("input", {
		placeholder: "123",
		inputmode: "numeric",
		size: 6,
		value: sessionStorage.getItem("batc.pr") || ""
	});
	const card = h("div", { class: "panel delivery-card" });
	let selectedMethod = "";
	let reviewedPreview = null;
	main.append(h("h1", {}, t("nav_delivery")), h("div", { class: "filters delivery-controls" }, repo, num, h("button", {
		class: "secondary",
		onclick: () => load()
	}, t("load_pr"))), card);
	if (!repo.value && state.caps?.repositories?.length) repo.value = state.caps.repositories[0].repository;
	const load = async (flash = null, fromEvent = false) => {
		const opens = drawerOpens;
		sessionStorage.setItem("batc.repo", repo.value);
		sessionStorage.setItem("batc.pr", num.value);
		if (!repo.value || !/^\d+$/.test(num.value)) return;
		try {
			const query = new URLSearchParams();
			if (selectedMethod) query.set("method", selectedMethod);
			if (fromEvent) query.set("from_event", "true");
			const pr = (await api("GET", `/repositories/${repo.value}/pulls/${num.value}?${query}`)).pull_request;
			if (holdRender(fromEvent, opens)) {
				idleReload = () => load(null, true);
				return;
			}
			freshPage();
			const status = h("div", { "aria-live": "polite" });
			const target = {
				repository: pr.repository,
				pull_number: Number(pr.pull_number)
			};
			if (!fromEvent || !reviewedPreview) reviewedPreview = pr.merge_preview;
			const pv = reviewedPreview;
			const scopeChanged = pr.merge_preview.digest !== pv.digest;
			const pre = {
				expected_head_sha: pv.target.head_sha,
				expected_base_sha: pv.target.base_sha,
				preview_digest: pv.digest
			};
			const params = {
				method: pv.method,
				preview_id: pv.preview_id
			};
			const run = async (action, extra, scope) => {
				try {
					const op = await submit(action, {
						...target,
						...extra.target
					}, extra.params || params, extra.pre ?? pre, scope);
					const receipt = op.result?.merge || op.result || op.external_refs?.merge_receipt;
					fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id), receipt?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: receipt.other_commits_count })) : null);
				} catch (e) {
					fill(status, errorBox(e));
				}
			};
			const blocked = pr.state !== "open" || pr.draft || pr.merged || pv.blocking.length > 0 || scopeChanged;
			const method = h("select", {
				"aria-label": t("merge_method"),
				onchange: () => {
					selectedMethod = method.value;
					load();
				}
			}, ...pr.merge.methods.map((m) => h("option", {
				value: m,
				selected: m === pv.method
			}, m)));
			const buttons = [h("button", {
				class: "primary",
				"data-testid": "merge-submit",
				disabled: blocked || !pr.merge.allowed || !may("merge"),
				onclick: () => run("github.pr.merge", {}, `merge.${pv.preview_id}`)
			}, t("merge"))];
			for (const r of pr.recipes) {
				buttons.push(h("button", {
					class: "secondary",
					disabled: blocked || !pr.merge.allowed || !may("merge") || !may("deploy"),
					onclick: () => run("delivery.merge_and_deploy", { target: { recipe: r.name } }, `merge_deploy.${pv.preview_id}.${r.name}`)
				}, t("merge_and_deploy_to", { env: r.environment })));
				if (pr.merged && pr.merge_commit_sha) buttons.push(h("button", {
					class: "secondary",
					disabled: !may("deploy"),
					onclick: async () => {
						try {
							const op = await submit("deployment.start", { recipe: r.name }, { source_sha: pr.merge_commit_sha }, {}, `deploy.${r.name}.${pr.merge_commit_sha}`);
							fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
						} catch (e) {
							fill(status, errorBox(e));
						}
					}
				}, t("deploy_to", { env: r.environment })));
			}
			const commitList = h("details", { class: "row-details" }, h("summary", {}, t("merge_commit_range", { count: pv.commits.length })), h("ul", {}, ...pv.commits.map((c) => h("li", {}, h("code", {}, c.sha), " ", c.message))));
			const affected = pv.affected_prs.map((p) => h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
				href: p.html_url,
				target: "_blank",
				rel: "noopener"
			}, `#${p.number} ${p.title || ""}`), " · ", t("scope_" + p.reason), h("div", {}, h("code", {}, p.head_sha || ""))), chip(t(p.effect === "branch_rebase" ? "scope_stack_rebase" : p.effect === "dependency" ? "scope_dependency" : p.would_merge ? "scope_would_merge" : "scope_candidate"), p.would_merge ? "warn" : "")));
			fill(card, h("h2", {}, h("a", {
				href: pr.html_url,
				target: "_blank",
				rel: "noopener"
			}, `#${pr.pull_number} ${pr.title || ""}`)), h("dl", { class: "kv" }, h("dt", {}, t("head")), h("dd", {}, h("code", {}, `${pr.head_ref} @ ${pr.head_sha}`)), h("dt", {}, t("base")), h("dd", {}, h("code", {}, `${pr.base_ref} @ ${pr.base_sha}`)), h("dt", {}, t("mergeable")), h("dd", {}, `${pr.state}${pr.draft ? " · draft" : ""} · ${pr.mergeable_state || "?"}`), h("dt", {}, t("checks")), h("dd", {}, t("checks_summary", pr.checks)), pr.merged ? [h("dt", {}, t("merged_sha")), h("dd", {}, h("code", {}, pr.merge_commit_sha))] : null), metadataDrawer(pr, load), scopeChanged ? h("p", { class: "note warn" }, t("merge_scope_reload")) : null, h("h2", {}, t("merge_scope")), h("label", {}, t("merge_method"), " ", method), h("p", { class: "muted" }, t("merge_preview_fixed"), " ", h("code", {}, pv.preview_id)), commitList, affected.length ? h("div", {}, ...affected) : h("p", { class: "muted" }, t("scope_single_pr")), ...pv.blocking.map((b) => h("p", { class: "note warn" }, h("code", {}, b.code), " · ", b.message)), ...pv.warnings.map((w) => h("p", { class: "muted" }, w)), h("div", { class: "actions" }, ...buttons), status, flash instanceof Node ? flash : null, pr.integration?.allowed ? integrationPanel(pr, load) : null);
		} catch (e) {
			if (!holdRender(fromEvent, opens)) fill(card, errorBox(e));
		}
	};
	await load();
	return liveReload(() => load(null, true), ["operation", "integration"]);
}
function metadataDrawer(pr, reload) {
	const title = h("input", {
		value: pr.title || "",
		"data-testid": "metadata-title"
	});
	const body = h("textarea", { "data-testid": "metadata-body" }, pr.body || "");
	const initialBody = body.value;
	const out = h("div", { "aria-live": "polite" });
	let d;
	const save = h("button", {
		class: "primary",
		"data-testid": "metadata-save",
		onclick: async () => {
			const params = {};
			if (title.value !== (pr.title || "")) params.title = title.value;
			if (body.value !== initialBody) params.body = body.value;
			if (!Object.keys(params).length) return;
			save.disabled = true;
			try {
				const op = await submit("github.pr.update", {
					repository: pr.repository,
					pull_number: pr.pull_number
				}, params, { expected_metadata_digest: pr.metadata_digest }, `pr_metadata.${pr.repository}.${pr.pull_number}.${pr.metadata_digest}`);
				const diff = op.external_refs?.metadata_difference;
				const contents = diff ? h("details", {
					class: "row-details",
					open: true
				}, h("summary", {}, t("metadata_diff")), ...[
					["metadata_before", diff.observed ? diff.before : {
						title: pr.title,
						body: pr.body
					}],
					["metadata_intended", diff.after || diff.intended],
					["metadata_observed", diff.observed || diff.before]
				].map(([label, value]) => h("div", {}, h("strong", {}, t(label)), h("pre", { class: "pre" }, JSON.stringify(value, null, 2))))) : null;
				fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id), op.error_code ? chip(op.error_code, "bad") : null, contents, h("p", { class: "muted" }, t("metadata_result_help")));
				idleReload = () => reload();
			} catch (e) {
				fill(out, errorBox(e));
				save.disabled = false;
			}
		}
	}, t("save"));
	const close = h("button", {
		class: "secondary",
		"data-testid": "metadata-close",
		onclick: () => d.close()
	}, t("close"));
	d = drawer(h("label", {}, t("metadata_title"), title), h("label", {}, t("description"), body), h("p", { class: "muted" }, t("metadata_race_limit")), h("div", { class: "actions" }, save, close), out);
	return h("div", {}, h("button", {
		class: "secondary",
		"data-testid": "metadata-edit",
		disabled: !pr.metadata_update.allowed || !may("integrate"),
		title: !may("integrate") ? t("needs_integrate_scope") : !pr.metadata_update.allowed ? t("metadata_disabled") : null,
		onclick: () => d.open()
	}, t("metadata_edit")), d.box);
}
function integrationPanel(pr, reloadCard) {
	const box = h("div", { class: "panel" });
	const may = (state.caps?.scopes || []).includes("integrate");
	const hosts = pr.integration.hosts;
	box.append(h("h2", {}, t("update_pr_results")), h("p", { class: "muted" }, t("update_pr_help")));
	if (!may) {
		box.append(h("p", { class: "note" }, t("needs_integrate_scope")));
		return box;
	}
	if (!hosts.length) {
		box.append(h("p", { class: "note" }, t("integration_no_host")));
		return box;
	}
	const target = {
		host: hosts[0],
		repository: pr.repository,
		pull_number: Number(pr.pull_number)
	};
	const selected = [];
	const pickList = h("div", {});
	const order = h("div", {});
	const previewBox = h("div", {});
	const status = h("div", {});
	let doc = null;
	let generation = 0;
	const rerender = () => {
		order.replaceChildren(...selected.map((s, i) => h("div", { class: "row" }, h("div", { class: "grow" }, `${i + 1}. `, chip(t("kind_" + s.kind)), " ", h("code", {}, s.label)), h("button", {
			class: "secondary",
			disabled: i === 0,
			onclick: () => {
				selected.splice(i - 1, 0, selected.splice(i, 1)[0]);
				changed();
			}
		}, "↑"), h("button", {
			class: "secondary",
			disabled: i === selected.length - 1,
			onclick: () => {
				selected.splice(i + 1, 0, selected.splice(i, 1)[0]);
				changed();
			}
		}, "↓"), h("button", {
			class: "secondary",
			onclick: () => {
				selected.splice(i, 1);
				changed();
			}
		}, "×"))));
	};
	const freshHead = async () => {
		try {
			pr.head_sha = (await api("GET", `/repositories/${pr.repository}/pulls/${pr.pull_number}`)).pull_request.head_sha;
		} catch {}
	};
	const runPreview = async () => {
		const mine = ++generation;
		doc = null;
		if (!selected.length) {
			previewBox.replaceChildren();
			return;
		}
		previewBox.replaceChildren(h("p", { class: "muted" }, t("previewing")));
		try {
			let op = await submit("integration.preview", target, { sources: selected.map(({ kind, id }) => ({
				kind,
				id
			})) }, { expected_head_sha: pr.head_sha }, `preview.${pr.repository}.${pr.pull_number}`);
			while (!TERMINAL.includes(op.status) && op.status !== "needs_attention" && box.isConnected && mine === generation) {
				await sleep(1e3);
				op = (await api("GET", `/operations/${op.operation_id}`)).operation;
			}
			if (mine !== generation || !box.isConnected) return;
			if (op.status !== "succeeded") {
				previewBox.replaceChildren(h("p", { class: "error" }, `${op.error_code || op.status} ${op.status_reason || ""}`));
				return;
			}
			doc = op.result;
			renderPreview();
		} catch (e) {
			if (mine === generation) previewBox.replaceChildren(errorBox(e));
		}
	};
	const changed = debounce(() => {
		rerender();
		runPreview();
	}, 600);
	const add = (kind, id, label) => {
		if (!selected.some((s) => s.kind === kind && s.id === id)) selected.push({
			kind,
			id,
			label
		});
		changed();
	};
	const plain = (w) => h("li", {}, w.text);
	const renderPreview = () => {
		const expired = Date.now() / 1e3 > doc.expires_at || doc.target.head_sha !== pr.head_sha;
		const conflictAt = doc.sources.find((s) => s.predicted === "conflict");
		const go = h("button", {
			class: "primary",
			disabled: !doc.ready || expired,
			onclick: async () => {
				go.disabled = true;
				try {
					const req = {
						action: "integration.apply",
						target,
						params: { preview_id: doc.preview_id },
						preconditions: {
							expected_head_sha: doc.target.head_sha,
							preview_digest: doc.digest
						}
					};
					follow((await api("POST", "/operations?wait=3", req, "integrate." + doc.preview_id)).operation);
				} catch (e) {
					status.replaceChildren(errorBox(e));
					go.disabled = false;
				}
			}
		}, conflictAt ? t("start_integration_conflict", { n: conflictAt.seq }) : t("update_pr_results"));
		previewBox.replaceChildren(...[
			h("p", {}, h("code", {}, `${doc.repository} #${doc.pull_number} · ${doc.target.head_ref} @ ${doc.target.head_sha.slice(0, 12)}`), " → ", t("normal_push"), " · ", t("push_access_" + doc.target.push_access)),
			...doc.sources.map((s) => h("details", { class: "row-details" }, h("summary", {}, `${s.seq}. `, chip(t("plan_" + (s.predicted || "not_predicted")), s.predicted === "conflict" ? "bad" : ""), " ", h("code", {}, s.label), " · ", t("n_commits", { n: s.commits_total }), " · ", t("n_files", { n: s.files_total }), s.conflict_files.length ? h("span", { class: "error" }, " · ", s.conflict_files.join(", ")) : null), h("ul", {}, ...s.commits.map((c) => h("li", {}, h("code", {}, c.sha.slice(0, 10)), ` ${c.subject} — ${c.author}`, c.origin === "foreign" ? h("span", { class: "error" }, " · ", t("foreign_commit")) : null))), s.warnings.length ? h("ul", { class: "muted" }, ...s.warnings.map(plain)) : null)),
			doc.overlaps.length ? h("p", { class: "muted" }, t("overlapping_files"), " ", doc.overlaps.map((o) => `${o.path} (${o.seqs.join(", ")}${o.also_changed_on_pr ? ", PR" : ""})`).join("; ")) : null,
			doc.blocking.length ? h("ul", { class: "error" }, ...doc.blocking.map(plain)) : null,
			doc.warnings.length ? h("ul", { class: "muted" }, ...doc.warnings.map(plain)) : null,
			h("p", { class: "muted" }, expired ? t("preview_expired") : t("previewed_at", { time: when(epoch(doc.observed_at)) }), " ", h("a", {
				href: "#",
				onclick: (ev) => {
					ev.preventDefault();
					runPreview();
				}
			}, t("preview_again"))),
			h("div", { class: "actions" }, go)
		].filter(Boolean));
	};
	const follow = async (op) => {
		for (;;) {
			if (!box.isConnected) return;
			status.replaceChildren(integrationStatus(op, {
				resume: async () => {
					try {
						follow((await api("POST", `/operations/${op.operation_id}/resume`, {})).operation);
					} catch (e) {
						status.append(errorBox(e));
					}
				},
				cancel: async () => {
					await api("POST", `/operations/${op.operation_id}/cancel`, {});
					await freshHead();
					runPreview();
				}
			}));
			if (TERMINAL.includes(op.status) || op.status === "needs_attention") break;
			await sleep(1500);
			op = (await api("GET", `/operations/${op.operation_id}`)).operation;
		}
		if (op.status === "succeeded") reloadCard(integrationStatus(op, {}));
		else if (["TARGET_HEAD_CHANGED", "SOURCE_CHANGED"].includes(op.error_code)) {
			await freshHead();
			runPreview();
		}
	};
	const branch = h("input", { placeholder: t("branch_on_github") });
	(async () => {
		try {
			const c = await api("GET", `/integrations/candidates?host=${encodeURIComponent(target.host)}`);
			const row = (kind, id, label, chips) => h("div", { class: "row" }, h("div", { class: "grow" }, h("code", {}, label), " ", ...chips), h("button", {
				class: "secondary",
				onclick: () => add(kind, id, label)
			}, t("add")));
			const delivered = (x) => x.delivered_to.length ? [chip(t("delivered_to", { n: x.delivered_to[0].pull_number }), "ok")] : [];
			pickList.replaceChildren(h("h3", {}, t("agent_results")), ...c.agent_results.length ? c.agent_results.map((r) => row("checkpoint_run", r.id, r.branch, [r.streaming ? chip(t("still_working"), "warn") : chip(t("done"), "ok"), ...delivered(r)])) : [h("p", { class: "muted" }, t("none"))], h("h3", {}, t("your_checkpoints")), ...c.checkpoints.length ? c.checkpoints.map((r) => row("checkpoint", r.id, `${r.branch || "?"} @ ${r.commit_sha.slice(0, 10)}`, [r.note ? h("span", { class: "muted" }, r.note.slice(0, 60)) : null, ...delivered(r)])) : [h("p", { class: "muted" }, t("none"))], h("div", { class: "actions" }, branch, h("button", {
				class: "secondary",
				onclick: () => {
					if (branch.value.trim()) add("branch", branch.value.trim(), branch.value.trim());
					branch.value = "";
				}
			}, t("add_branch"))));
		} catch (e) {
			pickList.replaceChildren(errorBox(e));
		}
	})();
	box.append(pickList, h("h3", {}, t("selected_in_order")), order, previewBox, status);
	return box;
}
function repairControl(op) {
	const conflict = [
		"INTEGRATION_CONFLICT",
		"RESOLUTION_INCOMPLETE",
		"RESOLUTION_INVALID"
	].includes(op.error_code);
	const out = h("div", {});
	let handoff = null;
	let repair = null;
	if (conflict && (state.caps?.scopes || []).includes("start")) {
		const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
		const go = h("button", {
			class: "secondary",
			onclick: async () => {
				go.disabled = true;
				try {
					const o = await submit("integration.handoff", { operation_id: op.operation_id }, { agent: agent.value }, {}, `handoff.${op.operation_id}`);
					out.append(h("p", {}, opStatus(o), " ", t("handoff_started"), " ", h("a", { href: `#/op/${o.operation_id}` }, o.operation_id)));
				} catch (e) {
					out.append(errorBox(e));
				}
				go.disabled = false;
			}
		}, t("start_agent_work"));
		const d = drawer(confinementNote(op.target?.host || op.external_refs?.host, agent), h("div", { class: "actions" }, agent, go));
		repair = d.box;
		handoff = h("button", {
			class: "secondary",
			onclick: () => d.toggle.click()
		}, t("hand_to_agent"));
	}
	if (handoff) out.append(handoff, repair);
	return out;
}
function integrationStatus(op, act) {
	const code = op.error_code;
	const text = op.status === "succeeded" ? t("integration_done", {
		old: op.result.old_head.slice(0, 7),
		new: op.result.new_head.slice(0, 7),
		n: op.result.added_commits ?? "?"
	}) : op.status === "needs_attention" ? t("integration_" + code) !== "integration_" + code ? t("integration_" + code) : op.status_reason : op.status === "uncertain" ? t("integration_uncertain") : op.status === "waiting_external" ? (op.external_refs || {}).conflict ? t("integration_waiting_resolver") : (op.external_refs || {}).pushed_sha ? t("integration_waiting") : op.status_reason || t("integration_running") : op.status === "failed" ? `${code}: ${op.status_reason || ""}` : t("integration_running");
	const out = h("div", {});
	const handoff = repairControl(op);
	const buttons = op.status === "needs_attention" ? [
		h("button", {
			class: "primary",
			onclick: act.resume
		}, t("resume")),
		handoff,
		h("button", {
			class: "danger",
			onclick: act.cancel
		}, t("cancel_and_preview"))
	].filter(Boolean) : [];
	out.append(h("p", {}, opStatus(op), " ", text, " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)), h("div", { class: "actions" }, ...buttons));
	return out;
}
async function viewOperations(main) {
	const list = h("div", { class: "panel" });
	main.append(h("h1", {}, t("nav_operations")), list);
	const render = async () => {
		try {
			list.replaceChildren(...(await api("GET", "/operations?limit=100")).operations.map(opRow));
		} catch (e) {
			list.replaceChildren(errorBox(e));
		}
	};
	await render();
	const reload = debounceRefresh(render, 500);
	return onEvents((ev) => {
		if (ev.resource_type === "operation") return reload();
	});
}
async function viewOperation(main, id) {
	freshPage();
	const panel = h("div", { class: "panel" });
	main.append(panel);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		try {
			const { operation: op, work_items: linked, cleanup_receipts: cleanupReceipts } = await api("GET", `/operations/${id}`);
			const refs = op.external_refs || {};
			const retry = refs.merged_sha && op.action === "delivery.merge_and_deploy" && op.status === "failed" ? h("button", {
				class: "primary",
				onclick: async () => {
					try {
						const o = await submit("deployment.start", { recipe: op.target.recipe }, { source_sha: refs.merged_sha }, {}, `deploy.${op.target.recipe}.${refs.merged_sha}`);
						location.hash = `#/op/${o.operation_id}`;
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("retry_deploy")) : null;
			const resume = op.status === "needs_attention" ? h("button", {
				class: "primary",
				title: t("resume_help"),
				onclick: async () => {
					try {
						await api("POST", `/operations/${id}/resume`, {});
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("resume")) : null;
			const opened = op.result?.session_id && op.result?.host ? h("a", {
				class: "secondary",
				href: `#/session/${encodeURIComponent(op.result.host)}/${encodeURIComponent(op.result.session_id)}`
			}, t("open_new_session")) : null;
			let receipts = null;
			if (op.action === "integration.apply") {
				const rows = (await api("GET", `/integrations/${id}`)).receipts;
				receipts = [h("h2", {}, t("receipts")), ...rows.map((r) => h("div", { class: "row" }, h("div", { class: "grow" }, `${r.seq}. ${t("kind_" + r.source_kind)} `, h("code", {}, r.source_id.slice(0, 15)), " ", h("code", {}, `${r.pinned_sha.slice(0, 10)} → ${(r.integrated_sha || "").slice(0, 10)}`), r.conflict_files ? h("span", { class: "error" }, " ", r.conflict_files.join(", ")) : null), chip(r.method || "-"), chip(t("receipt_" + r.effective_status), r.effective_status === "delivered" ? "ok" : "")))];
			}
			const cancel = !TERMINAL.includes(op.status) ? h("button", {
				class: "danger",
				onclick: async () => {
					try {
						await api("POST", `/operations/${id}/cancel`, {});
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("cancel")) : null;
			if (!panel.isConnected) return;
			if (holdRender(fromEvent, opens)) {
				idleReload = () => render(true);
				return;
			}
			freshPage();
			fill(panel, h("h1", {}, op.action), h("p", { class: "op-status" }, opStatus(op), " ", op.error_code ? chip(op.error_code, "bad") : null), ...linked?.length ? [linkedItems(linked)] : [], h("dl", { class: "kv" }, h("dt", {}, t("actor")), h("dd", {}, `${op.actor} (${op.entry})`), h("dt", {}, t("created")), h("dd", {}, when(epoch(op.created_at))), op.status_reason ? [h("dt", {}, t("reason")), h("dd", {}, op.status_reason)] : null, h("dt", {}, "Target"), h("dd", {}, h("code", {}, JSON.stringify(op.target))), Object.keys(refs).length ? [h("dt", {}, "Refs"), h("dd", {}, h("code", {}, JSON.stringify(refs)))] : null, op.result ? [h("dt", {}, "Result"), h("dd", {}, h("code", {}, JSON.stringify(op.result)))] : null), ...receipts || [], ...cleanupReceipts?.length ? [h("h2", {}, t("cleanup_open_receipts")), ...cleanupReceipts.map((r) => h("details", { class: "row-details" }, h("summary", {}, r.resource_id, " · ", t("cleanup_receipt_" + r.status)), h("pre", { class: "pre" }, JSON.stringify(r, null, 2))))] : [], ...op.action === "integration.apply" ? [repairControl(op)] : [], (op.result?.merge || op.result || refs.merge_receipt)?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: (op.result?.merge || op.result || refs.merge_receipt).other_commits_count })) : null, refs.write_acknowledged && refs.verification_pending ? h("p", { class: "note warn" }, t("metadata_pending")) : null, h("h2", {}, t("steps")), ...op.steps.map((s) => h("div", { class: "row" }, h("div", { class: "grow" }, s.name), h("span", { class: `status-${s.status}` }, s.status), s.error ? chip(s.error.code || t("error"), "bad") : null)), h("div", { class: "actions" }, opened, resume, retry, cancel));
		} catch (e) {
			fill(panel, errorBox(e));
		}
	};
	await render();
	return liveReload(render, [
		"operation",
		"integration",
		"cleanup"
	]);
}
function viewSettings(main) {
	if (nativeDesktop) return viewNativeSettings(main);
	const input = h("input", {
		type: "password",
		autocomplete: "off",
		size: 40,
		placeholder: "batc_…"
	});
	const remember = h("input", { type: "checkbox" });
	const info = h("p", { class: "muted" });
	if (state.caps) info.textContent = t("connected_as", {
		actor: state.caps.actor,
		scopes: state.caps.scopes.join(", ")
	});
	else if (state.connectionError) info.replaceChildren(errorBox(state.connectionError));
	main.append(h("h1", {}, t("nav_settings")), h("div", { class: "panel" }, h("label", {}, t("token")), h("div", { class: "filters" }, input, h("button", {
		class: "primary",
		onclick: async () => {
			disconnect();
			state.token = input.value.trim();
			try {
				await activate(await api("GET", "/capabilities"));
				saveToken(state.token, remember.checked);
				location.hash = "#/home";
				await route();
			} catch (e) {
				state.token = null;
				info.replaceChildren(errorBox(e));
			}
		}
	}, t("connect")), h("button", {
		class: "secondary",
		onclick: () => {
			disconnect();
			route();
		}
	}, t("disconnect"))), h("label", {}, remember, " ", t("remember")), h("p", { class: "muted" }, t("token_help")), info));
}
async function viewNativeSettings(main) {
	const info = h("p", { class: "muted" });
	const endpoint = h("p", { class: "muted" });
	const connect = h("button", {
		class: "primary",
		onclick: async () => {
			connect.disabled = true;
			try {
				const status = await nativeStatus();
				const caps = await nativeConnect();
				state.token = "native-credential";
				await activate(caps, status.endpoint);
				location.hash = "#/home";
				route();
			} catch (e) {
				disconnect();
				info.replaceChildren(errorBox(e));
			} finally {
				connect.disabled = false;
			}
		}
	}, t("connect"));
	main.append(h("h1", {}, t("nav_settings")), h("div", { class: "panel" }, h("h2", {}, t("desktop_connection")), endpoint, h("p", { class: "muted" }, t("desktop_credential_help")), h("div", { class: "actions" }, connect, h("button", {
		class: "secondary",
		onclick: async () => {
			await nativeDisconnect();
			disconnect();
			route();
		}
	}, t("disconnect"))), info), h("div", { class: "panel" }, h("h2", {}, t("desktop_local")), h("p", { class: "note" }, t("desktop_dashboard_only"))));
	if (state.caps) info.textContent = t("connected_as", {
		actor: state.caps.actor,
		scopes: state.caps.scopes.join(", ")
	});
	try {
		if (!state.caps && state.connectionError) info.replaceChildren(errorBox(state.connectionError));
		const status = await nativeStatus();
		endpoint.textContent = status.endpoint || t("desktop_config_needed");
		if (status.error) info.textContent = status.error;
		else if (!status.credential_available) info.textContent = t("desktop_credential_missing");
		connect.disabled = !!status.error || !status.credential_available;
	} catch (e) {
		info.replaceChildren(errorBox(e));
	}
}
var may = (scope) => (state.caps?.scopes || []).includes(scope);
function fill(el, ...kids) {
	el.replaceChildren(...kids.flat(2).filter((x) => x !== null && x !== void 0 && x !== false));
}
var PROJECT_ERRORS = [
	"VERSION_CONFLICT",
	"ORDER_CHANGED",
	"PIN_CHANGED",
	"CONTENT_CHANGED",
	"NAME_TAKEN",
	"HAS_CHILDREN",
	"PARENT_ARCHIVED",
	"PINNED_FIRST",
	"STEPS_OPEN",
	"CYCLE",
	"LINK_TARGET_NOT_FOUND",
	"NOTHING_TO_DECIDE"
];
function problem(code, message) {
	return h("p", { class: "error" }, PROJECT_ERRORS.includes(code) ? t("wi_err_" + code) : `${code || ""} ${message || ""}`);
}
var STALE = [
	"VERSION_CONFLICT",
	"ORDER_CHANGED",
	"PIN_CHANGED",
	"CONTENT_CHANGED"
];
var lastFailure = null;
async function change(out, action, target, params, pre, scope) {
	lastFailure = null;
	try {
		const op = await submit(action, target, params, pre, scope);
		if (op.status === "succeeded") {
			fill(out);
			return op;
		}
		lastFailure = op.error_code || op.status;
		if (TERMINAL.includes(op.status)) fill(out, problem(op.error_code, op.status_reason));
		else fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
	} catch (e) {
		lastFailure = e.code || "ERROR";
		fill(out, e.status === 403 ? errorBox(e) : problem(e.code, e.message));
	}
	return null;
}
function manageNote() {
	return may("manage") ? null : h("p", { class: "note" }, t("needs_manage_scope"));
}
function indent(el, depth) {
	el.style.setProperty("--depth", String(depth));
	return el;
}
function stateChip(c) {
	const cls = {
		done: "ok",
		awaiting_approval: "warn",
		doing: "info",
		waiting: "warn"
	}[c.display_state] || "";
	return chip(t("wi_state_" + c.display_state), cls);
}
function counts(c) {
	return [
		c.doing ? chip(`${t("wi_state_doing")} ${c.doing}`, "info") : null,
		c.awaiting_approval ? chip(`${t("wi_state_awaiting_approval")} ${c.awaiting_approval}`, "warn") : null,
		chip(t("wi_done_of", {
			done: c.done,
			total: c.total
		}), c.total && c.done === c.total ? "ok" : "")
	];
}
function orderButtons(sibs, i, key, run) {
	const me = sibs[i];
	const swap = (j) => () => {
		const before = sibs.map((x) => x[key]);
		const order = before.slice();
		[order[i], order[j]] = [order[j], order[i]];
		run("order", before, order);
	};
	const can = (j) => j >= 0 && j < sibs.length && sibs[j].pinned === me.pinned;
	return [
		h("button", {
			class: "mini",
			title: t("move_up"),
			"aria-label": t("move_up"),
			disabled: !can(i - 1),
			onclick: swap(i - 1)
		}, "↑"),
		h("button", {
			class: "mini",
			title: t("move_down"),
			"aria-label": t("move_down"),
			disabled: !can(i + 1),
			onclick: swap(i + 1)
		}, "↓"),
		h("button", {
			class: `mini ${me.pinned ? "on" : ""}`,
			title: me.pinned ? t("unpin") : t("pin"),
			"aria-label": me.pinned ? t("unpin") : t("pin"),
			onclick: () => run("pin", me.pinned)
		}, me.pinned ? "★" : "☆")
	];
}
var editing = 0;
var idleReload = null;
var drawerOpens = 0;
function setEditing(n) {
	editing = Math.max(0, n);
	if (!editing && idleReload) {
		const fn = idleReload;
		idleReload = null;
		fn();
	}
}
function drawer(...children) {
	const box = h("div", {
		class: "drawer",
		hidden: true
	}, ...children);
	const toggle = h("button", {
		class: "mini",
		title: t("more"),
		"aria-label": t("more"),
		onclick: () => {
			box.hidden = !box.hidden;
			if (!box.hidden) drawerOpens += 1;
			setEditing(editing + (box.hidden ? -1 : 1));
		}
	}, "…");
	const open = () => {
		if (box.hidden) toggle.click();
	};
	return {
		box,
		toggle,
		open,
		close: () => {
			if (!box.hidden) toggle.click();
		}
	};
}
function freshPage() {
	editing = 0;
	idleReload = null;
}
function typing() {
	const a = document.activeElement;
	return Boolean(a?.closest?.("#main")) && (a.tagName === "TEXTAREA" || a.tagName === "SELECT" || a.tagName === "INPUT" && ![
		"checkbox",
		"radio",
		"button",
		"submit"
	].includes(a.type));
}
function holdRender(fromEvent, opensAtStart) {
	return editing > 0 && (fromEvent || drawerOpens !== opensAtStart) || fromEvent && typing();
}
document.addEventListener("focusout", () => setTimeout(() => {
	if (!editing && !typing() && idleReload) {
		const fn = idleReload;
		idleReload = null;
		fn();
	}
}, 0));
function liveReload(fn, kinds) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const later = debounceRefresh(async () => {
		for (;;) {
			while (editing || typing()) {
				assertView(connection);
				await sleep(100);
			}
			assertView(connection);
			const opened = drawerOpens;
			await fn(true);
			assertView(connection);
			if (!editing && !typing() && drawerOpens === opened) return;
		}
	}, 500);
	return onEvents((ev) => {
		if (kinds.includes(ev.resource_type)) return later();
	});
}
async function viewProjects(main) {
	freshPage();
	const out = h("div", {});
	const tree = h("div", { class: "panel" });
	const archived = h("div", {});
	const name = h("input", {
		placeholder: t("new_project_name"),
		maxlength: 80
	});
	const add = h("button", {
		class: "primary",
		disabled: !may("manage"),
		onclick: async () => {
			if (!name.value.trim()) return;
			add.disabled = true;
			const op = await change(out, "project.create", {}, { name: name.value.trim() }, {}, "project.create");
			add.disabled = false;
			if (op) {
				name.value = "";
				location.hash = `#/project/${op.result.project_id}`;
			}
		}
	}, t("add_project"));
	const showArchived = h("input", { type: "checkbox" });
	main.append(h("h1", {}, t("nav_projects")), h("p", { class: "muted" }, t("projects_help")), manageNote() || "", h("div", { class: "filters" }, name, add), out, tree, h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		try {
			const data = await api("GET", `/projects${showArchived.checked ? "?include_archived=true" : ""}`);
			if (!tree.isConnected) return;
			if (holdRender(fromEvent, opens)) {
				idleReload = () => render(true);
				return;
			}
			freshPage();
			const rows = [];
			const walk = (sibs, depth, parent) => sibs.forEach((p, i) => {
				const msg = out;
				const run = async (what, before, order) => {
					if (what === "order") await change(msg, "project.order", {}, {
						parent_id: parent,
						order
					}, { before }, `project.order.${parent}`);
					else await change(msg, "project.pin", { project_id: p.project_id }, { pinned: !before }, { before }, `project.pin.${p.project_id}`);
					render();
				};
				const rename = h("input", {
					value: p.name,
					maxlength: 80
				});
				const sub = h("input", {
					placeholder: t("new_sub_project"),
					maxlength: 80
				});
				const d = drawer(h("div", { class: "filters" }, rename, h("button", {
					class: "secondary",
					onclick: async () => {
						if (await change(msg, "project.update", { project_id: p.project_id }, { name: rename.value.trim() }, { expected_version: p.version }, `project.rename.${p.project_id}`) || STALE.includes(lastFailure)) render();
					}
				}, t("rename"))), h("div", { class: "filters" }, sub, h("button", {
					class: "secondary",
					onclick: async () => {
						if (!sub.value.trim()) return;
						if (await change(msg, "project.create", {}, {
							name: sub.value.trim(),
							parent_id: p.project_id
						}, {}, `project.create.${p.project_id}`)) {
							d.close();
							render();
						}
					}
				}, t("add_project"))), h("div", { class: "actions" }, h("button", {
					class: "danger",
					onclick: async () => {
						if (await change(msg, "project.update", { project_id: p.project_id }, { archived: true }, { expected_version: p.version }, `project.archive.${p.project_id}`) || STALE.includes(lastFailure)) render();
					}
				}, t("archive"))));
				rows.push(indent(h("div", { class: "row tree" }, h("div", { class: "grow" }, h("a", {
					class: "title",
					href: `#/project/${p.project_id}`
				}, p.name), p.description ? h("div", { class: "muted clamp" }, p.description) : null), ...counts(p.counts), may("manage") ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "project_id", run), d.toggle) : null), depth), d.box);
				walk(p.children, depth + 1, p.project_id);
			});
			walk(data.projects, 0, "");
			fill(tree, ...rows.length ? rows : [h("p", { class: "muted" }, t("no_projects"))]);
			fill(archived, ...(data.archived || []).map((p) => h("div", { class: "row" }, h("div", { class: "grow" }, h("span", { class: "muted" }, p.name)), h("button", {
				class: "secondary",
				disabled: !may("manage"),
				onclick: async () => {
					await change(out, "project.update", { project_id: p.project_id }, { archived: false }, { expected_version: p.version }, `project.restore.${p.project_id}`);
					render();
				}
			}, t("restore")))));
		} catch (e) {
			fill(tree, errorBox(e));
		}
	};
	showArchived.onchange = () => render();
	await render();
	return liveReload(render, ["project", "work_item"]);
}
async function viewProject(main, pid) {
	freshPage();
	let draft = null;
	const head = h("div", { class: "panel" });
	const items = h("div", { class: "panel" });
	const out = h("div", {});
	const archived = h("div", {});
	const showArchived = h("input", { type: "checkbox" });
	const title = h("input", {
		placeholder: t("new_item_title"),
		maxlength: 120
	});
	const add = h("button", {
		class: "primary",
		disabled: !may("manage"),
		onclick: async () => {
			if (!title.value.trim()) return;
			add.disabled = true;
			const op = await change(out, "work_item.create", { project_id: pid }, { title: title.value.trim() }, {}, `wi.create.${pid}`);
			add.disabled = false;
			if (op) {
				title.value = "";
				render();
			}
		}
	}, t("add_item"));
	main.append(manageNote() || "", out, head, h("h2", {}, t("work_items")), h("div", { class: "filters" }, title, add), items, h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		let data;
		try {
			data = await api("GET", `/projects/${pid}${showArchived.checked ? "?include_archived=true" : ""}`);
		} catch (e) {
			fill(head, errorBox(e));
			return;
		}
		if (!head.isConnected) return;
		if (holdRender(fromEvent, opens)) {
			idleReload = () => render(true);
			return;
		}
		freshPage();
		const p = data.project;
		const msg = out;
		const v = draft || {
			name: p.name,
			description: p.description,
			repositories: p.repositories,
			task_project: p.task_project || ""
		};
		const f = {
			name: h("input", {
				value: v.name,
				maxlength: 80
			}),
			description: h("textarea", {}, v.description),
			repositories: h("input", {
				value: v.repositories.join(", "),
				placeholder: "owner/name, owner/name"
			}),
			task_project: h("input", {
				value: v.task_project,
				placeholder: t("task_project")
			})
		};
		const d = drawer(h("label", {}, t("name")), f.name, h("label", {}, t("description")), f.description, h("label", {}, t("repositories")), f.repositories, h("label", {}, t("task_project")), f.task_project, h("div", { class: "actions" }, h("button", {
			class: "primary",
			onclick: async () => {
				const params = {
					name: f.name.value.trim(),
					description: f.description.value,
					repositories: f.repositories.value.split(/[\s,]+/).filter(Boolean),
					task_project: f.task_project.value.trim()
				};
				const ok = await change(msg, "project.update", { project_id: pid }, params, { expected_version: p.version }, `project.edit.${pid}`);
				if (!ok && STALE.includes(lastFailure)) draft = params;
				if (ok || draft) render();
			}
		}, t("save"))));
		fill(head, h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")), ...data.path.flatMap((x) => [" / ", h("a", { href: `#/project/${x.project_id}` }, x.name)])), h("h1", {}, p.name, " ", p.archived ? chip(t("archived"), "warn") : null), p.description ? h("p", { class: "pre" }, p.description) : null, h("div", { class: "actions" }, ...counts(p.counts), ...p.repositories.map((r) => chip(r)), p.task_project ? chip(`Task Service: ${p.task_project}`) : null, may("manage") && !p.archived ? d.toggle : null), d.box, data.sub_projects.length ? h("p", {}, t("sub_projects"), ": ", ...data.sub_projects.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/project/${x.project_id}` }, x.name)])) : null);
		if (draft) {
			draft = null;
			d.open();
		}
		const rows = [];
		const walk = (sibs, depth, parent) => sibs.forEach((w, i) => {
			const rowMsg = out;
			const run = async (what, before, order) => {
				if (what === "order") await change(rowMsg, "work_item.order", { project_id: pid }, {
					parent_id: parent,
					order
				}, { before }, `wi.order.${pid}.${parent}`);
				else await change(rowMsg, "work_item.pin", { work_item_id: w.work_item_id }, { pinned: !before }, { before }, `wi.pin.${w.work_item_id}`);
				render();
			};
			const child = h("input", {
				placeholder: t("new_child_item"),
				maxlength: 120
			});
			const branch = h("input", {
				placeholder: t("new_branch_item"),
				maxlength: 120
			});
			const create = (input, params, scope) => h("button", {
				class: "secondary",
				onclick: async () => {
					if (!input.value.trim()) return;
					if (await change(rowMsg, "work_item.create", { project_id: pid }, {
						title: input.value.trim(),
						...params
					}, {}, scope)) render();
				}
			}, t("add_item"));
			const dr = drawer(h("div", { class: "filters" }, child, create(child, { parent_id: w.work_item_id }, `wi.child.${w.work_item_id}`)), h("div", { class: "filters" }, branch, create(branch, {
				parent_id: parent || null,
				derived_from: w.work_item_id
			}, `wi.branch.${w.work_item_id}`)), h("div", { class: "actions" }, h("button", {
				class: "danger",
				onclick: async () => {
					if (await change(rowMsg, "work_item.update", { work_item_id: w.work_item_id }, { archived: true }, { expected_version: w.version }, `wi.archive.${w.work_item_id}`) || STALE.includes(lastFailure)) render();
				}
			}, t("archive_with_children"))));
			const done = w.steps.filter((s) => s.done).length;
			rows.push(indent(h("div", { class: "row tree" }, stateChip(w.completion), h("div", { class: "grow" }, h("a", {
				class: "title",
				href: `#/item/${w.work_item_id}`
			}, w.title), w.derived_from ? h("span", { class: "muted" }, " ⑂") : null), w.steps.length ? chip(`${done}/${w.steps.length}`) : null, w.completion.pending ? chip(t("needs_decision"), "warn") : null, may("manage") && !p.archived ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "work_item_id", run), dr.toggle) : null), depth), dr.box);
			walk(w.children, depth + 1, w.work_item_id);
		});
		walk(data.work_items, 0, "");
		fill(items, ...rows.length ? rows : [h("p", { class: "muted" }, t("no_items"))]);
		fill(archived, ...(data.archived || []).map((w) => h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
			class: "muted",
			href: `#/item/${w.work_item_id}`
		}, w.title)), h("button", {
			class: "secondary",
			disabled: !may("manage") || p.archived,
			onclick: async () => {
				await change(out, "work_item.update", { work_item_id: w.work_item_id }, { archived: false }, { expected_version: w.version }, `wi.restore.${w.work_item_id}`);
				render();
			}
		}, t("restore")))));
		add.disabled = !may("manage") || p.archived;
	};
	showArchived.onchange = () => render();
	await render();
	return liveReload(render, ["project", "work_item"]);
}
function linkTarget(l) {
	const x = l.target || {};
	if (!x.found) return h("span", { class: "muted" }, l.ref, " · ", t("link_missing"));
	if (l.kind === "session") {
		const [host, ...rest] = l.ref.split("/");
		return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(host)}/${encodeURIComponent(rest.join("/"))}` }, x.title || l.ref), " ", chip(x.api_access === "managed" ? t("managed") : t("read_only"), x.api_access === "managed" ? "managed" : "readonly"), x.gone ? chip(t("stale_reason_gone"), "stale") : null);
	}
	if (l.kind === "operation") return h("span", {}, h("a", { href: `#/op/${l.ref}` }, x.action), " ", h("span", { class: `status-${x.status}` }, t("op_" + x.status)), x.session ? [" · ", h("a", { href: `#/session/${encodeURIComponent(x.session.host)}/${encodeURIComponent(x.session.session_id)}` }, t("open_new_session"))] : null);
	if (l.kind === "checkpoint") return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(x.host)}/${encodeURIComponent(x.source_session_id)}` }, h("code", {}, x.commit_sha.slice(0, 12))), " ", x.branch || "", " · ", x.host);
	if (l.kind === "task") return h("span", {}, h("code", {}, l.ref.slice(0, 12)), " ", x.project, " · ", x.state);
	return h("a", {
		href: `https://github.com/${x.repository}/pull/${x.number}`,
		target: "_blank",
		rel: "noopener"
	}, `${x.repository}#${x.number}`);
}
async function viewWorkItem(main, wid) {
	freshPage();
	const notice = h("div", {});
	const panel = h("div", {});
	let draft = null;
	const newStep = h("input", {
		placeholder: t("new_step"),
		maxlength: 300
	});
	const kind = h("select", {}, ...[
		"session",
		"checkpoint",
		"operation",
		"task",
		"pull_request"
	].map((k) => h("option", { value: k }, t("link_" + k))));
	const ref = h("input", { placeholder: t("link_ref_hint") });
	kind.onchange = () => {
		ref.placeholder = t("link_ref_" + kind.value);
	};
	kind.onchange();
	main.append(manageNote() || "", notice, panel);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		let data;
		try {
			data = await api("GET", `/work-items/${wid}`);
		} catch (e) {
			fill(panel, errorBox(e));
			return;
		}
		if (!panel.isConnected) return;
		if (holdRender(fromEvent, opens)) {
			idleReload = () => render(true);
			return;
		}
		freshPage();
		const w = data.work_item, c = w.completion;
		const live = !w.archived && !data.project.archived;
		const pre = { expected_version: w.version };
		const update = (params, scope) => change(notice, "work_item.update", { work_item_id: wid }, params, pre, scope);
		const decide = async (action, scope) => {
			await change(notice, action, { work_item_id: wid }, {}, { expected_fingerprint: c.fingerprint }, scope);
			render();
		};
		const approve = h("button", {
			class: "primary",
			disabled: !live || !may("approve"),
			title: may("approve") ? null : t("needs_approve_scope"),
			onclick: () => decide("work_item.approve", `wi.approve.${wid}.${c.fingerprint}`)
		}, c.pending ? t("accept_done") : t("mark_done"));
		const keepGoing = h("button", {
			class: "secondary",
			disabled: !live || !may("manage"),
			onclick: () => decide("work_item.continue", `wi.continue.${wid}.${c.fingerprint}`)
		}, t("keep_working"));
		let banner = null;
		if (c.approved) banner = h("p", { class: "note ok" }, t("approved_by", {
			who: c.approved_by,
			time: when(epoch(c.approved_at))
		}));
		else if (c.pending && w.state === "done") banner = h("div", { class: "note warn" }, h("p", {}, t("claimed_done", { who: c.claimed_by || "?" })), h("div", { class: "actions" }, approve, keepGoing), may("approve") ? null : h("p", { class: "muted" }, t("needs_approve_scope")));
		else if (c.pending) banner = h("div", { class: "note warn" }, h("p", {}, t("steps_all_checked")), h("div", { class: "actions" }, approve, keepGoing));
		const stateSel = h("select", { disabled: !live || !may("manage") }, ...[
			"todo",
			"doing",
			"waiting"
		].map((s) => h("option", {
			value: s,
			selected: w.state === s
		}, t("wi_state_" + s))));
		if (w.state === "done") stateSel.prepend(h("option", {
			value: "done",
			selected: true
		}, t("wi_state_" + c.display_state)));
		stateSel.onchange = async () => {
			await update({ state: stateSel.value }, `wi.state.${wid}`);
			render();
		};
		const v = {
			...w,
			...draft || {}
		};
		const f = {
			title: h("input", {
				value: v.title,
				maxlength: 120
			}),
			goal: h("textarea", {}, v.goal),
			request: h("textarea", {}, v.request),
			acceptance: h("textarea", {}, v.acceptance)
		};
		const d = drawer(h("label", {}, t("title")), f.title, h("label", {}, t("goal")), f.goal, h("label", {}, t("request")), f.request, h("label", {}, t("acceptance")), f.acceptance, h("div", { class: "actions" }, h("button", {
			class: "primary",
			onclick: async () => {
				const params = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, k === "title" ? el.value.trim() : el.value]).filter(([k, v]) => v !== w[k]));
				if (!Object.keys(params).length) {
					d.close();
					return;
				}
				const ok = await update(params, `wi.edit.${wid}`);
				if (!ok && STALE.includes(lastFailure)) draft = params;
				if (ok || draft) render();
			}
		}, t("save"))));
		const section = (label, text) => text ? [h("h2", {}, label), h("div", { class: "panel pre" }, text)] : [];
		const setSteps = async (steps, added) => {
			if (await update({ steps }, `wi.steps.${wid}`) && added) newStep.value = "";
			render();
		};
		const stepRows = w.steps.map((s, i) => h("div", { class: "step" }, h("label", {}, h("input", {
			type: "checkbox",
			checked: s.done,
			disabled: !live || !may("manage"),
			onchange: () => setSteps(w.steps.map((x, j) => j === i ? {
				...x,
				done: !x.done
			} : x))
		}), " ", s.text), live && may("manage") ? h("button", {
			class: "mini",
			title: t("remove"),
			"aria-label": t("remove"),
			onclick: () => setSteps(w.steps.filter((_, j) => j !== i))
		}, "×") : null));
		const addStep = h("button", {
			class: "secondary",
			disabled: !live || !may("manage"),
			onclick: () => {
				if (newStep.value.trim()) setSteps([...w.steps, {
					text: newStep.value.trim(),
					done: false
				}], true);
			}
		}, t("add"));
		const link = async (params, scope, typed) => {
			if (await change(notice, "work_item.link", { work_item_id: wid }, params, {}, scope)) {
				if (typed) ref.value = "";
				render();
			}
		};
		const linkRows = data.links.map((l) => h("div", { class: "row" }, chip(t("link_" + l.kind)), h("div", { class: "grow" }, linkTarget(l), l.note ? h("div", { class: "muted" }, l.note) : null, h("div", { class: "muted" }, `${l.linked_by} · ${when(epoch(l.linked_at))}`)), l.kind === "checkpoint" && l.target?.found && live ? continueFrom(w, l.ref, notice) : null, live && may("manage") ? h("button", {
			class: "mini",
			title: t("remove"),
			"aria-label": t("remove"),
			onclick: () => link({
				kind: l.kind,
				ref: l.ref,
				remove: true
			}, `wi.unlink.${wid}.${l.kind}.${l.ref}`)
		}, "×") : null));
		const brief = (x) => h("div", { class: "row" }, chip(t("wi_state_" + x.display_state)), h("a", {
			class: "grow",
			href: `#/item/${x.work_item_id}`
		}, x.title));
		fill(panel, h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")), " / ", h("a", { href: `#/project/${data.project.project_id}` }, data.project.name), ...data.path.flatMap((x) => [" / ", h("a", { href: `#/item/${x.work_item_id}` }, x.title)])), h("h1", {}, w.title, " ", stateChip(c), w.archived ? [" ", chip(t("archived"), "warn")] : null), data.derived_from ? h("p", { class: "muted" }, t("derived_from"), " ", h("a", { href: `#/item/${data.derived_from.work_item_id}` }, data.derived_from.title)) : null, banner, h("div", { class: "actions" }, h("label", {}, t("state"), " ", stateSel), !c.pending && !c.approved && live ? approve : null, live && may("manage") ? d.toggle : null), d.box, ...section(t("goal"), w.goal), ...section(t("request"), w.request), ...section(t("acceptance"), w.acceptance), h("h2", {}, t("steps_title")), h("div", { class: "panel" }, ...stepRows.length ? stepRows : [h("p", { class: "muted" }, t("no_steps"))], live && may("manage") ? h("div", { class: "filters" }, newStep, addStep) : null), h("div", { class: "actions" }, h("a", { href: `#/cleanup/item/${wid}` }, t("nav_cleanup"))), h("h2", {}, t("links")), h("div", { class: "panel" }, ...linkRows.length ? linkRows : [h("p", { class: "muted" }, t("no_links"))], live && may("manage") ? h("div", { class: "filters" }, kind, ref, h("button", {
			class: "secondary",
			onclick: () => {
				if (ref.value.trim()) link({
					kind: kind.value,
					ref: ref.value.trim()
				}, `wi.link.${wid}`, true);
			}
		}, t("link"))) : null), data.children.length ? [h("h2", {}, t("children")), h("div", { class: "panel" }, ...data.children.map(brief))] : null, data.derived.length ? [h("h2", {}, t("derived")), h("div", { class: "panel" }, ...data.derived.map(brief))] : null, h("h2", {}, t("history")), h("div", { class: "panel" }, ...data.events.map((ev) => h("div", { class: "row" }, h("div", { class: "grow" }, t("ev_" + ev.kind.replace(".", "_")), h("div", { class: "muted" }, eventDetail(ev.body))), h("span", { class: "muted" }, `${ev.actor || ""} · ${when(epoch(ev.created_at))}`)))));
		if (draft) {
			draft = null;
			d.open();
		}
	};
	await render();
	return liveReload(render, ["work_item"]);
}
function continueFrom(w, checkpointId, notice) {
	const instr = h("textarea", {}, [
		w.title,
		w.goal,
		w.request && `${t("request")}:\n${w.request}`,
		w.acceptance && `${t("acceptance")}:\n${w.acceptance}`,
		w.steps.length ? `${t("steps_title")}:\n${w.steps.map((s) => `- [${s.done ? "x" : " "}] ${s.text}`).join("\n")}` : ""
	].filter(Boolean).join("\n\n"));
	const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const out = h("div", {});
	const go = h("button", {
		class: "primary",
		onclick: async () => {
			go.disabled = true;
			let op;
			try {
				op = await submit("checkpoint.continue", { checkpoint_id: checkpointId }, {
					instructions: instr.value,
					agent: agent.value
				}, {}, `continue.${checkpointId}`);
			} catch (e) {
				fill(out, errorBox(e));
				go.disabled = false;
				return;
			}
			fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
			if (TERMINAL.includes(op.status) && op.status !== "succeeded") return;
			if (await change(notice, "work_item.link", { work_item_id: w.work_item_id }, {
				kind: "operation",
				ref: op.operation_id
			}, {}, `wi.link.${w.work_item_id}.${op.operation_id}`)) out.append(" · ", t("linked_back"));
		}
	}, t("start_agent_work"));
	const note = confinementNote(w.links?.find((l) => l.ref === checkpointId)?.target?.host, agent);
	api("GET", `/checkpoints/${encodeURIComponent(checkpointId)}`).then((x) => note.setHost(x.checkpoint.host)).catch(() => {});
	const d = drawer(note, instr, h("div", { class: "actions" }, agent, go), out);
	const why = !may("start") ? t("needs_start_scope") : !may("manage") ? t("needs_manage_scope") : null;
	return h("div", { class: "grow" }, h("button", {
		class: "secondary",
		disabled: Boolean(why),
		title: why,
		onclick: () => d.toggle.click()
	}, t("start_from_checkpoint")), d.box);
}
function eventDetail(b) {
	if (b.fields) return b.fields.map((f) => t(f === "steps" ? "steps_title" : f)).join(", ");
	if (b.from && b.to) return `${t("wi_state_" + b.from)} → ${t("wi_state_" + b.to)}${b.note ? ` · ${b.note}` : ""}`;
	if (b.kind && b.ref) return `${t("link_" + b.kind)} ${b.ref}`;
	return b.note || "";
}
function linkedItems(items) {
	return h("p", { class: "muted" }, t("linked_items"), ": ", ...items.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/item/${x.work_item_id}` }, x.title)]));
}
function workItemRow(w) {
	return h("div", { class: "row" }, stateChip(w.completion), h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/item/${w.work_item_id}`
	}, w.title), h("div", { class: "muted" }, [w.project_name, w.completion.claimed_by && t("claimed_by", { who: w.completion.claimed_by })].filter(Boolean).join(" · "))), chip(t("needs_decision"), "warn"));
}
async function viewCleanup(main, section, ident) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const draftKey = `batc.cleanup.draft.${connection.namespace}`;
	const pendingKey = `batc.cleanup.pending.${connection.namespace}`;
	const persist = (key, value) => {
		assertView(connection);
		try {
			if (value === null) sessionStorage.removeItem(key);
			else sessionStorage.setItem(key, JSON.stringify(value));
		} catch (error) {
			if (error.code) throw error;
		}
	};
	const stored = (() => {
		try {
			return JSON.parse(sessionStorage.getItem(draftKey) || "{}");
		} catch {
			return {};
		}
	})();
	const choices = section === "item" && stored.id !== ident ? {
		discard_uncommitted: [],
		release_undelivered: []
	} : stored.choices || {
		discard_uncommitted: [],
		release_undelivered: []
	};
	const pending = (() => {
		try {
			return JSON.parse(sessionStorage.getItem(pendingKey) || "null");
		} catch {
			return null;
		}
	})();
	const kind = h("select", { "aria-label": t("cleanup_target") }, ...[
		"work_item",
		"checkpoint",
		"integration",
		"host"
	].map((k) => h("option", { value: k }, t("cleanup_target_" + k))));
	kind.value = section === "item" ? "work_item" : stored.kind || "host";
	const targetId = h("input", {
		value: section === "item" ? ident : stored.id || "",
		"aria-label": t("cleanup_id"),
		placeholder: t("cleanup_id"),
		class: "cleanup-id"
	});
	const children = h("input", {
		type: "checkbox",
		checked: stored.children || false
	});
	const childrenLabel = h("label", { class: "cleanup-choice" }, children, t("cleanup_children"));
	const previewOut = h("div", { "aria-live": "polite" });
	const status = h("div", { "aria-live": "polite" });
	const historyOut = h("div", { "aria-live": "polite" });
	const retainedOut = h("div", { "aria-live": "polite" });
	let doc = pending, busy = false, pendingRequest = !!pending, previewRevision = 0;
	function changed() {
		assertView(connection);
		previewRevision++;
		doc = null;
		apply.disabled = true;
		reviewed.checked = false;
		persist(draftKey, {
			kind: kind.value,
			id: targetId.value,
			children: children.checked,
			choices
		});
		childrenLabel.hidden = kind.value !== "work_item";
		fill(status, h("p", { class: "muted" }, t("cleanup_repreview")));
	}
	function targetChanged() {
		choices.discard_uncommitted = [];
		choices.release_undelivered = [];
		changed();
	}
	kind.addEventListener("change", targetChanged);
	targetId.addEventListener("input", targetChanged);
	children.addEventListener("change", targetChanged);
	childrenLabel.hidden = kind.value !== "work_item";
	function choice(item, key, label) {
		const input = h("input", {
			type: "checkbox",
			checked: choices[key].includes(item.resource_id),
			disabled: pendingRequest || key === "discard_uncommitted" && !may("cleanup_discard"),
			onchange: () => {
				choices[key] = choices[key].filter((id) => id !== item.resource_id);
				if (input.checked) choices[key].push(item.resource_id);
				changed();
			}
		});
		return h("label", { class: "cleanup-choice" }, input, label);
	}
	function resourceRow(item) {
		const codes = (item.reasons || []).map((r) => r.code);
		const eligible = item.proven && item.kind === "worktree" && !item.task_owned;
		return h("article", { class: "cleanup-resource" }, h("div", { class: "row" }, h("strong", { class: "grow" }, t("cleanup_kind_" + item.kind)), chip(t("cleanup_decision_" + item.decision), item.decision === "reclaim" ? "ok" : "")), h("div", { class: "cleanup-binding" }, item.host || "", " ", item.path || item.ref || item.resource_id), item.observation?.head ? h("p", { class: "muted" }, t("cleanup_commit_kept"), " ", h("code", {}, item.observation.head)) : null, item.delivery && !item.delivery.delivered ? h("p", { class: "note warn" }, t("cleanup_not_delivered")) : null, ...(item.reasons || []).map((r) => h("div", { class: "cleanup-reason" }, h("code", {}, r.code), " · ", t("cleanup_reason_" + r.code))), ...(item.overridden_reasons || []).map((r) => h("p", { class: "muted" }, t("cleanup_choice_" + r.code))), item.steps?.length ? h("p", {}, t("cleanup_plan"), ": ", item.steps.map((x) => t("cleanup_step_" + x)).join(" → ")) : null, eligible && codes.includes("RESULTS_NOT_DELIVERED") ? choice(item, "release_undelivered", t("cleanup_release")) : null, eligible && codes.includes("UNCOMMITTED_CHANGES") ? choice(item, "discard_uncommitted", t("cleanup_discard")) : null, h("details", {}, h("summary", {}, t("cleanup_evidence")), h("pre", { class: "pre" }, JSON.stringify({
			resource_id: item.resource_id,
			original_ids: item.original_ids,
			reasons: item.reasons,
			consumers: item.consumers,
			delivery: item.delivery,
			manifest: item.observation?.manifest
		}, null, 2))));
	}
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => {
			apply.disabled = !doc?.ready || !may("cleanup") || !reviewed.checked;
		}
	});
	const apply = h("button", {
		class: "primary",
		disabled: true,
		onclick: async () => {
			if (busy || !doc || !reviewed.checked) return;
			assertView(connection);
			const reviewedDoc = doc;
			busy = true;
			pendingRequest = true;
			apply.disabled = true;
			previewButton.disabled = true;
			kind.disabled = true;
			targetId.disabled = true;
			children.disabled = true;
			previewOut.querySelectorAll("input").forEach((input) => {
				input.disabled = true;
			});
			persist(pendingKey, reviewedDoc);
			try {
				const op = await submit("cleanup.apply", { preview_id: reviewedDoc.preview_id }, { preview_token: reviewedDoc.preview_token }, { preview_fingerprint: reviewedDoc.fingerprint }, "cleanup.apply");
				assertView(connection);
				fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, t("cleanup_open_receipts")), ...(op.result?.items || []).map((r) => h("p", {}, h("code", {}, r.resource_id), " · ", t("cleanup_receipt_" + r.status))));
				persist(pendingKey, null);
				pendingRequest = false;
				doc = null;
				reviewed.checked = false;
				previewButton.disabled = false;
				kind.disabled = false;
				targetId.disabled = false;
				children.disabled = false;
				await loadHistory();
				await loadRetained();
			} catch (e) {
				if (connection.epoch !== state.epoch || connection.namespace !== state.namespace || connection.generation !== generation) return;
				if (!e.status || e.status >= 500) {
					fill(status, errorBox(e), h("p", {}, t("cleanup_retry_same")));
					apply.disabled = !may("cleanup");
					previewButton.disabled = true;
					kind.disabled = true;
					targetId.disabled = true;
					children.disabled = true;
				} else {
					persist(pendingKey, null);
					pendingRequest = false;
					fill(status, errorBox(e), h("p", {}, t("cleanup_repreview")));
					doc = null;
					previewButton.disabled = false;
					kind.disabled = false;
					targetId.disabled = false;
					children.disabled = false;
				}
			} finally {
				busy = false;
			}
		}
	}, t("cleanup_apply"));
	function renderPreview() {
		fill(previewOut, h("h2", {}, t("cleanup_preview")), h("p", {}, t("cleanup_counts", {
			reclaim: doc.impact.reclaim,
			retain: doc.impact.retain
		})), h("p", { class: "muted" }, t("cleanup_expires", { time: when(doc.expires_at * 1e3) })), ...(doc.items || []).map(resourceRow), !doc.ready ? h("p", { class: "note" }, t("cleanup_blocked")) : null);
	}
	const previewButton = h("button", {
		class: "secondary",
		onclick: async () => {
			assertView(connection);
			const revision = ++previewRevision;
			previewButton.disabled = true;
			doc = null;
			apply.disabled = true;
			reviewed.checked = false;
			const key = {
				work_item: "work_item_id",
				checkpoint: "checkpoint_id",
				integration: "operation_id",
				host: "host"
			}[kind.value];
			const target = {
				kind: kind.value,
				[key]: targetId.value.trim(),
				...kind.value === "work_item" ? { include_children: children.checked } : {}
			};
			try {
				const result = await api("POST", "/cleanup-previews", {
					target,
					choices: structuredClone(choices)
				});
				assertView(connection);
				if (revision !== previewRevision) return;
				doc = result.preview;
				renderPreview();
				fill(status);
			} catch (e) {
				if (revision === previewRevision && connection.epoch === state.epoch) fill(status, errorBox(e));
			} finally {
				previewButton.disabled = false;
			}
		}
	}, t("cleanup_preview"));
	if (pending && section !== "resource") {
		kind.value = pending.target.kind;
		targetId.value = pending.target[{
			work_item: "work_item_id",
			checkpoint: "checkpoint_id",
			integration: "operation_id",
			host: "host"
		}[kind.value]];
		children.checked = !!pending.target.include_children;
		childrenLabel.hidden = kind.value !== "work_item";
		renderPreview();
		reviewed.checked = true;
		apply.disabled = !may("cleanup");
		previewButton.disabled = true;
		kind.disabled = true;
		targetId.disabled = true;
		children.disabled = true;
		fill(status, h("p", { class: "note" }, t("cleanup_retry_same")));
	}
	const search = h("input", {
		class: "cleanup-id",
		"aria-label": t("cleanup_search"),
		placeholder: t("cleanup_search")
	});
	async function loadHistory(cursor = "") {
		try {
			const result = await api("GET", `/cleanup-tombstones?query=${encodeURIComponent(search.value)}&cursor=${encodeURIComponent(cursor)}`);
			assertView(connection);
			const rows = (result.tombstones || []).map((x) => h("article", { class: "cleanup-resource" }, h("a", { href: `#/cleanup/resource/${x.resource_id}` }, t("cleanup_kind_" + x.kind)), h("div", { class: "cleanup-binding" }, x.host, " ", x.path || x.ref || ""), h("p", { class: "muted" }, x.actor, " · ", when(x.cleaned_at * 1e3)), h("p", {}, t("cleanup_reason_reviewed")), ...(x.pull_requests || []).map((pr) => h("p", {}, `${pr.repository} #${pr.pull_number}`))));
			if (cursor) historyOut.append(...rows);
			else fill(historyOut, ...rows, rows.length ? null : h("p", { class: "muted" }, t("cleanup_empty_history")));
			if (result.next_cursor) historyOut.append(h("button", {
				class: "secondary",
				onclick: (e) => {
					e.currentTarget.remove();
					loadHistory(result.next_cursor);
				}
			}, t("more")));
		} catch (e) {
			fill(historyOut, errorBox(e));
		}
	}
	async function loadRetained(cursor = "") {
		try {
			const result = await api("GET", `/cleanup-retained?cursor=${encodeURIComponent(cursor)}`);
			assertView(connection);
			const rows = (result.retained || []).map((x) => h("article", { class: "cleanup-resource" }, h("code", {}, x.commit_sha), h("div", { class: "cleanup-binding" }, x.host, " ", x.repository), h("p", { class: "muted" }, x.ref)));
			const unavailable = (result.unavailable || []).map((x) => h("p", { class: "note warn" }, x.host, " ", x.ref, " · ", t("cleanup_unavailable")));
			if (cursor) retainedOut.append(...rows, ...unavailable);
			else fill(retainedOut, ...rows, ...unavailable, rows.length || unavailable.length ? null : h("p", { class: "muted" }, t("cleanup_empty_retained")));
			if (result.next_cursor) retainedOut.append(h("button", {
				class: "secondary",
				onclick: (e) => {
					e.currentTarget.remove();
					loadRetained(result.next_cursor);
				}
			}, t("more")));
		} catch (e) {
			fill(retainedOut, errorBox(e));
		}
	}
	main.append(h("h1", {}, t("nav_cleanup")), h("p", { class: "muted" }, t("cleanup_intro")));
	if (section === "resource") {
		try {
			const data = await api("GET", `/cleanup-tombstones/${encodeURIComponent(ident)}`);
			main.append(h("a", { href: "#/cleanup" }, t("nav_cleanup")), resourceRow(data.tombstone), h("h2", {}, t("cleanup_open_receipts")), h("pre", { class: "panel pre" }, JSON.stringify(data.receipts, null, 2)));
		} catch (e) {
			main.append(errorBox(e));
		}
		return;
	}
	main.append(h("div", { class: "panel" }, h("h2", {}, t("cleanup_target")), h("div", { class: "filters" }, kind, targetId), childrenLabel, h("div", { class: "actions" }, previewButton)), previewOut, h("div", { class: "panel" }, h("label", { class: "cleanup-choice" }, reviewed, t("cleanup_reviewed")), !may("cleanup") ? h("p", { class: "muted" }, t("cleanup_scope")) : null, h("div", { class: "actions" }, apply), status), h("h2", {}, t("cleanup_history")), h("div", { class: "panel" }, h("form", {
		class: "filters",
		onsubmit: (e) => {
			e.preventDefault();
			loadHistory();
		}
	}, search, h("button", {
		class: "secondary",
		type: "submit"
	}, t("cleanup_search_button"))), historyOut), h("h2", {}, t("cleanup_retained")), h("p", { class: "muted" }, t("cleanup_retained_help")), h("div", { class: "panel" }, retainedOut));
	await loadHistory();
	await loadRetained();
	const refresh = debounceRefresh(() => settleRefreshes([loadHistory(), loadRetained()]), 500);
	return onEvents((ev) => {
		if (["cleanup", "operation"].includes(ev.resource_type)) return refresh();
	});
}
var NAV = [
	["home", "nav_home"],
	["projects", "nav_projects"],
	["sessions", "nav_sessions"],
	["delivery", "nav_delivery"],
	["operations", "nav_operations"],
	["cleanup", "nav_cleanup"],
	["settings", "nav_settings"]
];
var teardown = null;
var generation = 0;
async function route() {
	const mine = ++generation;
	state.viewReady = false;
	if (teardown) {
		teardown();
		teardown = null;
	}
	freshPage();
	const [name, ...rest] = (location.hash.replace(/^#\//, "") || "home").split("/").map(decodeURIComponent);
	document.getElementById("nav").replaceChildren(...NAV.map(([k, label]) => h("a", {
		href: `#/${k}`,
		class: name === k ? "on" : ""
	}, t(label))));
	const main = document.getElementById("main");
	main.replaceChildren();
	if (!state.token && name !== "settings") {
		main.append(h("p", { class: "note" }, t(nativeDesktop ? "desktop_connect_needed" : "need_token")));
		viewSettings(main);
		return;
	}
	const off = await ({
		home: viewHome,
		projects: viewProjects,
		project: viewProject,
		item: viewWorkItem,
		sessions: viewSessions,
		cleanup: viewCleanup,
		delivery: viewDelivery,
		operations: viewOperations,
		session: viewSession,
		op: viewOperation,
		settings: viewSettings
	}[name] || viewHome)(main, ...rest);
	if (mine !== generation) {
		if (off) off();
		return;
	}
	teardown = off || null;
	state.viewReady = true;
}
async function start() {
	if (nativeDesktop) {
		clearToken();
		try {
			const status = await nativeStatus();
			const caps = await nativeConnect();
			state.token = "native-credential";
			await activate(caps, status.endpoint);
		} catch (error) {
			disconnect();
			state.connectionError = error;
		}
	} else {
		state.token = loadToken();
		if (state.token) try {
			await activate(await api("GET", "/capabilities"));
		} catch {
			state.token = null;
		}
	}
	window.addEventListener("hashchange", route);
	await route();
	streamEvents();
}
start();
//#endregion
