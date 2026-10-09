// Generated from desktop/src. Run: cd desktop && npm ci && npm run build:browser. Do not edit.
//#region src/i18n.js
var STRINGS = {
	"zh-TW": {
		bulk_title: "批次核准",
		bulk_choose_host: "選擇主機",
		bulk_workspace: "工作區名稱或 ID（選填）",
		bulk_preview: "預覽待核准請求",
		bulk_scope: "範圍限於所選主機，可再指定工作區。只處理這次明確勾選的請求。",
		bulk_effect: "每筆勾選的請求都會設為允許，並通知 BAT 不再詢問同類請求。這不是單次允許；變更權限模式則需另外選擇。",
		bulk_select: "核准 {id}",
		bulk_mode: "{id} 的後續權限模式",
		bulk_no_mode: "不變更權限模式",
		bulk_apply: "核准已選請求",
		bulk_selected: "已選 {count} 筆",
		bulk_check: "查回批次結果",
		bulk_new: "檢視另一批請求",
		bulk_empty: "這個範圍目前沒有待核准請求。",
		bulk_blocked: "不可納入批次",
		bulk_truncated: "這次只檢查前 50 個工作階段，並非完整清單。請縮小工作區範圍後再預覽。",
		bulk_fixed: "保留原請求、選擇與操作識別。新出現的請求不會自動加入這一批。",
		bulk_expired: "預覽已過期。請重新預覽並勾選。",
		bulk_refused: "這筆請求在受理前被拒絕。可重新檢視另一批請求。",
		bulk_invalid_preview: "預覽回應與所選範圍不符。",
		bulk_invalid_result: "操作回應與原批次請求不符。",
		bulk_all_proven: "每筆核准與所選權限變更都有接受回執；這不代表工作已完成。",
		bulk_partial: "尚未證明全部項目成功。請查看逐筆回執與原操作。",
		bulk_item_complete: "所選操作已接受",
		bulk_item_incomplete: "尚未全部確認",
		bulk_answer: "核准",
		bulk_permissions: "權限",
		bulk_full_prompt: "完整請求與識別資料",
		start_title_page: "開始新工作階段",
		start_intro: "在選定主機與工作區建立獨立的受管理工作階段。",
		start_choose_host: "選擇主機",
		start_workspace: "工作區",
		start_choose_workspace: "選擇工作區",
		start_agent: "Agent",
		start_model: "模型（選填）",
		start_model_default: "使用主機或 agent 的預設模型",
		start_title: "標題（選填）",
		start_prompt: "原始指示（選填）",
		start_reload_workspaces: "重新讀取工作區",
		start_loading_workspaces: "正在讀取中央工作區清單…",
		start_discovery_failed: "工作區清單尚未確認。請重新讀取後再選擇。",
		start_no_workspaces: "此主機目前未傳回工作區。",
		start_truncated: "只顯示前 200 個工作區；此清單不代表所有工作區。",
		start_workspace_help: "使用中央傳回的固定工作區 ID；主機仍會檢查儲存庫與權限。",
		start_isolation: "使用新 worktree。此操作不會接管既有人工或任務工作階段。",
		start_prompt_help: "原文會完整保留。留白只啟動工作階段，不會自動產生指示。",
		start_apply: "開始工作階段",
		start_new: "準備另一個工作階段",
		start_unavailable: "需要 observe 與 start 權限，以及中央允許啟動的主機。",
		start_invalid_result: "操作回應與原啟動請求不符。",
		start_unknown: "提交結果尚未確認；原請求與 key 已保留。",
		start_fixed: "主機、工作區、選項與原文已固定。查回不會重新啟動；結果不明時只能重試同一筆請求。",
		start_refused: "請求在受理前被拒絕。可明確準備另一筆請求。",
		start_started: "已確認啟動：",
		start_without_prompt: "未要求傳送初始指示。",
		start_prompt_accepted: "已確認初始指示被接受。",
		start_prompt_unknown: "已啟動，但初始指示是否被接受尚未確認。請檢視逐步回執；不要另開工作階段重送。",
		sessions_label: "標題",
		sessions_workspace: "工作區",
		sessions_workspace_id: "工作區 ID",
		sessions_id: "工作階段 ID",
		sessions_title: "工作階段",
		sessions_intro: "依主機與工作區整理工作階段，保留人工工作與過往紀錄。",
		sessions_search: "搜尋已載入的工作階段",
		sessions_workspaces: "已載入的工作區",
		sessions_scope_note: "數量只計算已載入的頁面。",
		sessions_all_loaded: "全部已載入",
		sessions_loaded_count: "{count} 筆",
		sessions_projects: "前往專案與工作項目",
		sessions_workspace_unknown: "工作區未記錄",
		sessions_workspace_unverified: "未記錄工作區 ID",
		sessions_scope_missing: "所選工作區目前沒有資料",
		sessions_no_matches: "目前範圍沒有符合的工作階段。",
		sessions_more_hint: "還有頁面尚未載入。可載入更多，或調整搜尋與篩選。",
		sessions_empty_hint: "可調整搜尋、主機或存取方式；未出現在這裡不代表工作已結束。",
		sessions_showing: "顯示 {shown} 筆 · 已載入 {loaded} 筆",
		sessions_page_note: "搜尋與工作區選擇只套用到已載入頁面。",
		sessions_manual: "人工建立",
		sessions_connector: "Connector 建立",
		sessions_origin_unknown: "來源未確認",
		sessions_access_unknown: "存取方式未確認",
		sessions_details: "狀態與紀錄",
		sessions_runtime_stale: "活動與待回覆資訊尚未重新確認。",
		sessions_not_seen: "最近掃描未見",
		sessions_stale: "觀測待更新",
		sessions_activity_unknown: "活動狀態未確認",
		permissions_title: "Session 權限",
		permissions_mode: "要求的模式",
		permissions_default: "一般權限",
		permissions_allow_all: "全部允許",
		permissions_apply: "套用權限",
		permissions_check: "查回原操作",
		permissions_new: "建立另一筆變更",
		permissions_retry: "重試原請求",
		permissions_details: "檢視操作與逐步回執",
		permissions_help: "選擇要套用的權限。這裡不表示目前實際模式；主機政策與隔離限制仍然適用。",
		permissions_default_help: "使用一般核准流程，保留需要確認的操作提示。",
		permissions_allow_help: "略過 agent 的操作核准提示，包括寫入與命令執行。主機仍可拒絕此變更。",
		permissions_unavailable: "需要最新 Session 資料、operate 權限，以及中央明確允許此操作與主機寫入。",
		permissions_unknown: "結果尚未確認。原請求已保留。",
		permissions_fixed: "保留同一筆模式、Session 與操作。部分完成或結果不明時，請先檢視回執。",
		permissions_invalid_result: "操作回應與原權限請求不符。",
		permissions_damaged: "已儲存的請求不完整。請先在操作紀錄確認結果。",
		permissions_accepted: "BAT 已接受要求的設定；尚未獨立查證執行中的 agent 已套用。",
		permissions_next_turn: "Codex 於下一輪使用這個設定。",
		permissions_refused: "這筆請求在受理前被拒絕。可明確建立另一筆變更；原請求不會自動重試。",
		ar_nav: "附件成果",
		ar_title: "附件成果與審閱",
		ar_open: "擷取與審閱這次執行的檔案",
		ar_help: "保存一個管理中來源的固定檔案版本，再明確記錄對該版本的審閱。原工作樹與執行狀態不會因此改變。",
		ar_capture_title: "保存來源檔案",
		ar_review_title: "審閱固定版本",
		ar_execution: "中央執行證據",
		ar_choose_execution: "選擇已接受的執行或指令",
		ar_evidence_kind: "證據類型",
		ar_operation: "執行操作",
		ar_command: "Task Service 指令",
		ar_task_id: "完整任務 ID",
		ar_evidence_id: "完整操作或指令 ID",
		ar_exact_evidence: "輸入較早的完整證據 ID…",
		ar_more_executions: "更多執行紀錄",
		ar_refresh_sources: "重新讀取執行證據",
		ar_source_unavailable: "來源須為目前由 Connector 管理的完整 session；中央仍會查核原始執行證據。",
		ar_receipt: "對此版本的審閱紀錄（最多 2000 字）",
		ar_accept: "記錄此版本的審閱",
		ar_check_accept: "查回原審閱提交",
		ar_accept_help: "請先檢視這份成果，再記錄審閱依據。此回執只對應下列版本，不表示測試通過、任務完成、合併或部署。",
		ar_approve_scope: "記錄審閱需要 approve 權限；查看附件需要 observe 權限。",
		ar_revision: "固定附件版本",
		ar_lineage: "中央來源與執行證據",
		ar_check: "查回原操作",
		ar_new_review: "新增另一筆審閱",
		ar_recorded: "已記錄對此固定版本的審閱。任務與工作項目的完成狀態未改變。",
		ar_catalog: "已保存的管理中來源成果",
		ar_no_artifacts: "這一頁尚無可審閱的管理中來源成果。",
		ar_invalid_result: "回應與原操作、固定版本或中央來源證據不符。原請求與 key 已保留。",
		ar_storage: "無法保存原操作的復原資料。請先允許此應用程式使用本機儲存空間。",
		ar_original_credential: "擷取查回需要原始憑證及 manage、observe 權限。請恢復原憑證；原請求與 key 會繼續保留。",
		ar_original_preview: "原始擷取預覽與來源證據",
		capture_title: "擷取遠端檔案",
		capture_host: "來源主機",
		capture_session: "完整人工 Session ID",
		capture_path: "遠端相對檔案路徑",
		capture_help: "輸入一個相對於所選人工 session 資料夾的檔案路徑。讀取過程不會更動來源。",
		capture_preview: "預覽來源檔案",
		capture_review: "我已檢視此檔案與來源證據",
		capture_save: "保存已檢視的檔案",
		capture_check: "查回原擷取操作",
		capture_new: "擷取另一個檔案",
		capture_attach: "加入目前附件草稿",
		capture_attached: "已加入附件草稿。儲存工作項目或派工後才會套用。",
		capture_name: "檔名",
		capture_bytes: "位元組",
		capture_source: "來源",
		capture_root: "Session 資料夾",
		capture_repository: "儲存庫",
		capture_expiry: "預覽有效期限",
		capture_single_file: "只擷取這一個檔案；不包含其他尚未提交的變更。",
		capture_expired: "預覽已過期。請重新預覽與檢視；尚未提交擷取。",
		capture_fixed: "保留原預覽與操作識別；查回不會改取較新的內容。",
		capture_unknown: "提交結果尚未確認。請查回同一筆擷取；原草稿與操作 key 已保留。",
		capture_saved: "已保存固定附件版本，可在附件選擇中使用：",
		capture_scope_observe: "預覽需要 observe 權限。",
		capture_scope_manage: "保存需要 manage 與 observe 權限及中央擷取能力。",
		capture_manual_only: "來源必須是中央明確觀測為人工建立的完整 session。",
		capture_invalid_preview: "中央預覽與選定來源不符。",
		capture_invalid_result: "無法查證已保存附件的固定版本與擷取來源。",
		obs_unknown: "未知",
		obs_state_evidence: "分項狀態與證據",
		obs_lifecycle_note: "閒置、未載入或沒有分頁都不代表結束；沒有結束證據就保留未知。",
		obs_discovery: "Discovery 涵蓋範圍",
		obs_discovery_note: "這裡顯示中央已記錄的掃描範圍，不會另行掃描主機；沒有看見不代表不存在。",
		obs_scan_status: "最近掃描",
		obs_last_success: "最後成功觀測",
		obs_last_attempt: "最近查詢完成",
		obs_authority: "觀測授權",
		obs_verified: "已驗證",
		obs_unverified: "未驗證",
		obs_scan_coverage: "讀取方式、範圍與失敗",
		obs_outside_scan: "未涵蓋的範圍",
		obs_no_scan: "尚未記錄這台主機的掃描證據。",
		obs_new_facts: "Journal 有新紀錄。已載入的頁面仍保持原快照；可重新讀取此資源。",
		obs_event_kind: "事件 kind（選填）",
		obs_execution_filter: "Execution ID（選填）",
		obs_read_latest: "讀取最新紀錄",
		obs_evidence: "原始 ID 與證據",
		obs_occurred: "發生時間",
		obs_recorded: "記錄時間",
		obs_pending_binding: "尚未綁定 session",
		obs_half_open: "序號區間 [{start}, {end})",
		obs_follow_up: "接續執行",
		obs_empty: "這個範圍沒有已記錄的證據。",
		obs_snapshot: "固定 journal 快照：{seq}。",
		obs_historical_limits: "早期歷程可能不完整；未知時間不會推測。",
		obs_first_recorded: "最早記錄",
		obs_relations: "Execution 與 Session 關係",
		obs_history: "資源歷程",
		obs_include_closed: "包含已關閉關係",
		obs_execution: "Execution",
		obs_worktree: "Worktree",
		obs_known_identity: "顯示中央的已知資源 ID；關係與歷程不授予操作權限。",
		obs_inventory_note: "依穩定 ID 巡覽，保留已載入頁數。列表反映持續變化的觀測，不是隔離快照。",
		obs_axis_connection: "連線",
		obs_axis_loading: "載入",
		obs_axis_tab: "分頁",
		obs_axis_activity: "活動",
		obs_axis_lifecycle: "生命週期",
		obs_axis_enumeration: "列舉",
		obs_axis_freshness: "資料新鮮度",
		obs_value_unknown: "未知",
		obs_value_connected: "已連線",
		obs_value_not_connected: "未連線",
		obs_value_loaded: "已載入",
		obs_value_not_loaded: "未載入",
		obs_value_present: "存在",
		obs_value_no_tab: "沒有分頁",
		obs_value_starting: "啟動中",
		obs_value_streaming: "輸出中",
		obs_value_not_streaming: "未輸出",
		obs_value_active: "運作中",
		obs_value_ended: "已結束",
		obs_value_gone: "已離開列舉",
		obs_value_missing: "本次未列舉",
		obs_value_fresh: "新鮮",
		obs_value_stale: "過期",
		obs_scope_other_profiles_and_hosts: "其他 profile 與主機",
		obs_scope_manual_sessions_without_tabs_or_facts: "沒有分頁或事實的手動 session",
		obs_scope_arbitrary_transcripts: "未綁定的逐字稿",
		obs_scope_codex_rollouts: "Codex rollout 掃描",
		obs_scope_background_git_state: "背景 Git 狀態探測",
		obs_scope_earlier_history: "較早的歷程",
		parent_archived: "這個項目或所屬專案已封存；編輯草稿仍保留。",
		pending_changed: "待回覆的問題已改變；草稿仍保留。請查看目前的要求後重新作答。",
		files_unavailable: "目前連線無法取回原傳輸。從草稿移除不會取消上傳。",
		files_choose: "選擇檔案",
		files_help: "檔案內容會在選取時固定；完成驗證後即可加入附件。",
		files_drop: "啟用拖放",
		files_drop_help: "將檔案拖入視窗，再按「上傳」加入這份草稿。",
		files_upload: "上傳",
		files_progress: "本機傳輸進度",
		files_stop: "停止傳輸",
		files_retry: "重試原傳輸",
		files_check: "查回結果",
		files_cancel: "取消上傳",
		files_discard: "清除本機紀錄",
		files_save: "另存新檔",
		files_preview: "預覽",
		files_selected: "已選取",
		files_checking: "查核原操作",
		files_uploading: "傳送中",
		files_verifying: "驗證中",
		files_downloading: "下載中",
		files_saving: "儲存中",
		files_ready: "已驗證",
		files_saved: "已儲存",
		files_stopped: "已停止，結果保留",
		files_failed: "操作失敗",
		files_cancelled: "已取消",
		files_receipt_mismatch: "傳輸紀錄與原檔案不符，未加入附件。",
		attachment_file_changed: "請重新選擇相同檔案以查回原上傳；不同內容請先移除這一項。",
		attachment_pending: "上傳結果仍待確認。請以相同檔案重試原操作。",
		existing_artifact: "已上傳附件",
		add_attachment: "加入附件",
		attachments: "附件",
		choose_attachments: "選擇附件",
		upload_on_choose: "選擇檔案後立即上傳。成功上傳的版本會隨草稿保存。",
		choose_again: "請重新選擇這個檔案。瀏覽器無法在重新載入後開啟本機檔案。",
		uploading: "正在上傳…",
		retry: "重試",
		attachment_role: "附件用途",
		attachment_input: "輸入",
		attachment_result: "成果",
		attachments_not_ready: "請先完成附件上傳或移除未完成的檔案。",
		source_unavailable: "無法讀取來源 HEAD，保留草稿；恢復連線後再試。",
		confirm_source: "確認保留原版本與附件，繼續同一派工",
		materializations: "附件傳輸",
		material_pending: "待傳輸",
		material_transferring: "傳輸中",
		material_uncertain: "待確認",
		material_verified: "已驗證",
		material_blocked: "受阻",
		"nav_cleanup": "整理與復原",
		"cleanup_target": "選擇整理範圍",
		"cleanup_target_work_item": "工作項目",
		"cleanup_target_task": "執行任務",
		"cleanup_task_preview": "預覽此任務的資源整理",
		"cleanup_check": "查回原整理操作",
		"cleanup_new": "預覽另一筆整理",
		"cleanup_invalid_result": "操作回應與原整理請求不符。",
		"cleanup_task_help": "任務整理使用完整任務 ID，由中央檢查結束狀態、共用資源與未確認指令。未提交的任務內容與分支仍保留；不會刪除任務歷史。",
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
		"cleanup_reason_automatic": "由任務服務自動整理，保留內容與操作回執。",
		"cleanup_reason_historical": "依過往任務整理事件保存的歷史紀錄；並非本次審閱操作。",
		"cleanup_reason_recorded": "已有整理紀錄，詳細來源請見回執。",
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
		"cleanup_reason_TASK_OWNED": "此資源屬於執行任務，須在該任務範圍確認可整理；目前仍保留。",
		"cleanup_reason_RETAINED_COPY": "保留原分支作為內容副本。",
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
		dep_pull_request: "合併請求（PR）",
		dep_desired: "選定部署",
		dep_observed: "目前觀測版本",
		dep_last_verified: "最後驗證版本",
		dep_history: "部署歷史",
		dep_no_history: "尚無部署紀錄。",
		dep_no_version: "尚無版本紀錄。",
		dep_not_observed: "尚未觀測",
		dep_observed_at: "觀測時間：{time}",
		dep_verified_at: "驗證時間：{time}",
		dep_artifact: "產物 {id}",
		dep_not_undone: "回退不會撤銷",
		dep_no_limits: "此部署設定未宣告無法撤銷的副作用。",
		dep_rollback: "回退到此版本",
		dep_retry: "重試部署 · {sha}",
		dep_confirm_rollback: "開始回退",
		dep_confirm_retry: "重試此部署",
		dep_rollback_review: "檢視回退版本",
		dep_retry_review: "檢視重試部署",
		dep_retry_only: "重新部署此固定版本，不會再次合併 PR。",
		dep_retry_unavailable: "此舊紀錄缺少可重試的固定版本，請重新預覽部署。",
		dep_preview_generation: "{env} · 環境第 {generation} 代",
		dep_stale_preview: "環境或部署設定已變更。請檢視下方最新預覽，再決定是否重新送出。不會自動重送。",
		dep_refused: "部署請求未能繼續，請查看操作詳情。",
		dep_open_operation: "查看操作",
		dep_operation_details: "操作詳情",
		dep_run: "服務商執行紀錄",
		dep_attempt: "執行次數",
		dep_error_code: "錯誤代碼",
		dep_needs_scope: "需要 deploy 權限。",
		dep_missing_recipe: "此部署設定已移除。",
		dep_missing_verification: "部署已停用：缺少版本驗證設定。",
		dep_disabled: "目前未開放部署。",
		dep_provider_pending: "服務商的執行結果仍待確認，尚不能重試。",
		dep_attention: "需要處理",
		dep_attention_help: "請比較選定與觀測版本，並先查看操作詳情再決定下一步。",
		dep_drift: "觀測版本與選定部署不同，不會自動啟動部署。",
		dep_superseded: "已被新的選定部署取代。",
		dep_new_desired: "查看新的選定部署",
		dep_provider_run: "原始執行紀錄",
		dep_previous: "上一頁",
		dep_next: "下一頁",
		dep_page: "第 {page} 頁",
		dep_ROLLBACK_UNSUPPORTED: "此部署設定不支援回退。",
		dep_ROLLBACK_TARGET_INVALID: "此版本未經驗證，或屬於不同部署設定／環境。",
		dep_ROLLBACK_ARTIFACT_UNAVAILABLE: "保存的產物無法取得。",
		dep_ROLLBACK_ARTIFACT_EXPIRED: "保存的產物已過期。",
		dep_version_health: "已驗證執行環境版本與健康。",
		dep_version_only: "已驗證執行環境版本；此部署設定不檢查健康。",
		dep_health_only: "健康檢查通過；此部署設定不檢查執行環境版本。",
		dep_state_selected: "已選定",
		dep_state_waiting_order: "等待環境順序",
		dep_state_queued: "已排程",
		dep_state_building: "建置中",
		dep_state_waiting_environment: "等待環境核准",
		dep_state_deploying: "部署中",
		dep_state_verifying: "驗證中",
		dep_state_succeeded: "已驗證",
		dep_state_failed: "失敗",
		dep_state_cancelled: "已取消",
		dep_state_uncertain: "結果未明",
		dep_state_needs_attention: "需要處理",
		dep_state_unverified: "未驗證",
		dep_state_superseded: "已被取代",
		dep_operation: "操作",
		dep_status: "狀態",
		dep_generation: "環境第 {generation} 代",
		offline_actions_paused: "中央離線，暫停操作",
		sync_waiting: "等待更新，草稿已保留",
		desktop_add_credential: "新增憑證",
		desktop_replace_credential: "更換憑證",
		desktop_forget_credential: "移除此電腦儲存的憑證",
		desktop_reload_configuration: "重新載入設定",
		desktop_connecting: "正在處理連線…",
		desktop_endpoint: "中央位置",
		desktop_expected_actor: "預期身分",
		desktop_configuration_file: "設定檔",
		desktop_credential_source: "憑證來源",
		desktop_source_launch_environment: "本次啟動的記憶體憑證",
		desktop_source_windows_credential_manager: "Windows 認證管理員",
		desktop_enrollment_help: "在 Windows 對話框的密碼欄輸入 Connector API token。驗證身分後，才會儲存供此 Windows 帳戶下次使用。",
		desktop_enrollment_unsupported: "此平台尚未支援保護儲存與憑證輸入。可使用啟動時提供的記憶體憑證；不會儲存至磁碟。",
		desktop_forget_help: "只移除此電腦的已儲存憑證並中斷連線；不會撤銷中央 token。草稿與原操作識別仍保留。",
		desktop_forgotten: "已移除本機憑證並中斷連線。",
		desktop_reloaded: "已重新載入設定。請驗證連線；原草稿仍保留。",
		desktop_disconnected: "已中斷連線；中央工作仍繼續。",
		desktop_enrollment_cancelled: "已取消憑證輸入，保留原連線。",
		desktop_connection: "桌面中央連線",
		desktop_local: "本機功能",
		desktop_connect_needed: "請連到已配置的中央 Connector。",
		desktop_polling: "已連線 · 每秒更新",
		desktop_config_needed: "尚未配置中央連線。",
		desktop_credential_missing: "尚未提供可用的本機憑證。",
		desktop_credential_help: "中央位置與身份由本機設定指定；憑證保留在原生程式，不存入此畫面。",
		desktop_dashboard_only: "Dashboard 無需安裝 BAT。本機 Fleet 可使用已配置的 Kit 管理連線。開啟 BAT、原生附件、登入自啟與更新尚未提供。關閉視窗會留在系統匣；退出程式不會停止中央工作或 Fleet。",
		fleet_title: "本機 Fleet 連線",
		fleet_help: "選擇這台電腦需要的連線；連線選擇與實際就緒狀態分開顯示。",
		fleet_apply: "儲存連線選擇",
		fleet_refresh: "重新讀取狀態",
		fleet_use_current: "使用目前選擇",
		fleet_start: "啟動連線監控",
		fleet_quit: "停止本機連線監控",
		fleet_monitor_running: "監控執行中",
		fleet_monitor_stopped: "監控已停止",
		fleet_ready: "就緒",
		fleet_degraded: "部分可用",
		fleet_down: "無法連線",
		fleet_off: "未啟用",
		fleet_fresh: "最新觀測",
		fleet_stale: "觀測已過期",
		fleet_unavailable: "尚無可用觀測",
		fleet_applied: "監控已讀取目前選擇。",
		fleet_waiting: "等待監控讀取目前選擇。",
		fleet_changed: "連線選擇或監控已變更。草稿已保留；請讀取並檢視目前選擇。",
		fleet_other_owner: "目前監控不屬於這個登入工作階段，僅供檢視。",
		fleet_invalid: "Fleet 設定需要處理（{n} 項）。",
		fleet_windows: "Fleet 連線管理需要 Windows。",
		fleet_setup: "尚未配置 Fleet Kit；請依桌面設定文件指定安裝位置。",
		fleet_working: "正在處理連線設定…",
		fleet_saved: "設定已儲存；就緒狀態由監控回報。",
		fleet_quit_requested: "已請求停止監控；正在等候狀態更新。",
		fleet_unknown: "結果尚未確定，草稿已保留。重新讀取狀態後再操作。",
		fleet_read_failed: "無法讀取 Fleet；操作已暫停。",
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
		nav_sessions: "工作階段",
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
		bulk_title: "Batch approvals",
		bulk_choose_host: "Choose a host",
		bulk_workspace: "Workspace name or ID (optional)",
		bulk_preview: "Preview pending requests",
		bulk_scope: "Choose one host and optionally a workspace. Only explicitly selected requests enter this batch.",
		bulk_effect: "Each selected request is allowed with BAT instructed not to ask again for the same kind of request. This is not a one-time allowance. Changing the permission mode is a separate choice.",
		bulk_select: "Approve {id}",
		bulk_mode: "Subsequent permission mode for {id}",
		bulk_no_mode: "Keep permission mode",
		bulk_apply: "Approve selected requests",
		bulk_selected: "{count} selected",
		bulk_check: "Check batch outcome",
		bulk_new: "Review another batch",
		bulk_empty: "No pending approval requests in this scope.",
		bulk_blocked: "Unavailable for this batch",
		bulk_truncated: "Only the first 50 sessions were checked. This is not the complete inventory. Narrow the workspace and preview again.",
		bulk_fixed: "The original requests, selection and operation identity are retained. Newly arriving prompts never join this batch.",
		bulk_expired: "This preview expired. Preview again and select requests.",
		bulk_refused: "This request was refused before admission. You can review another batch.",
		bulk_invalid_preview: "The preview does not match the selected scope.",
		bulk_invalid_result: "The operation response does not match the original batch request.",
		bulk_all_proven: "Each selected approval and mode change has an acceptance receipt. This does not mean the work is complete.",
		bulk_partial: "Not all items are proven successful. Check the individual receipts and original operations.",
		bulk_item_complete: "Selected actions accepted",
		bulk_item_incomplete: "Not fully confirmed",
		bulk_answer: "Approval",
		bulk_permissions: "Permissions",
		bulk_full_prompt: "Full request and identity",
		start_title_page: "Start a new session",
		start_intro: "Create a standalone managed session on the host and workspace you choose.",
		start_choose_host: "Choose a host",
		start_workspace: "Workspace",
		start_choose_workspace: "Choose a workspace",
		start_agent: "Agent",
		start_model: "Model (optional)",
		start_model_default: "Use the host or agent default",
		start_title: "Title (optional)",
		start_prompt: "Original instructions (optional)",
		start_reload_workspaces: "Reload workspaces",
		start_loading_workspaces: "Reading central workspaces…",
		start_discovery_failed: "Workspace discovery is unconfirmed. Reload before selecting.",
		start_no_workspaces: "This host returned no workspaces.",
		start_truncated: "Only the first 200 workspaces are shown; this is not a complete listing.",
		start_workspace_help: "Uses the exact workspace ID returned by central. Host repository and policy checks still apply.",
		start_isolation: "Uses a new worktree. This action does not adopt an existing manual or task session.",
		start_prompt_help: "Your original text is preserved. Leave this empty to start without sending instructions.",
		start_apply: "Start session",
		start_new: "Prepare another session",
		start_unavailable: "Requires observe and start scopes, and a host central permits for starting sessions.",
		start_invalid_result: "The operation response does not match the original start request.",
		start_unknown: "Submission is unconfirmed; the original request and key are preserved.",
		start_fixed: "Host, workspace, options and original text are fixed. Read-back never starts again; an unknown submission can only retry the same request.",
		start_refused: "This request was refused before admission. You can explicitly prepare another request.",
		start_started: "Start confirmed:",
		start_without_prompt: "No initial instructions were requested.",
		start_prompt_accepted: "Initial instructions were accepted.",
		start_prompt_unknown: "Started, but acceptance of the initial instructions is unconfirmed. Check the step receipts; do not resend by starting another session.",
		ar_nav: "Artifacts",
		ar_title: "Artifacts and review",
		ar_open: "Capture and review this execution's file",
		ar_help: "Save one fixed file revision from a managed source, then explicitly record a review of that revision. This does not change the source worktree or execution state.",
		ar_capture_title: "Save source file",
		ar_review_title: "Review fixed revision",
		ar_execution: "Central execution evidence",
		ar_choose_execution: "Choose an accepted execution or command",
		ar_evidence_kind: "Evidence type",
		ar_operation: "Execution operation",
		ar_command: "Task Service command",
		ar_task_id: "Full task ID",
		ar_evidence_id: "Full operation or command ID",
		ar_exact_evidence: "Enter an older exact evidence ID…",
		ar_more_executions: "More executions",
		ar_refresh_sources: "Reload execution evidence",
		ar_source_unavailable: "Choose a current Connector-managed session with its full ID. Central still verifies the original execution evidence.",
		ar_receipt: "Review receipt for this revision (up to 2000 characters)",
		ar_accept: "Record review of this revision",
		ar_check_accept: "Check original review submission",
		ar_accept_help: "Inspect the result before recording your review. This receipt covers only the fixed revision below; it does not prove passing tests, task completion, merge or deployment.",
		ar_approve_scope: "Recording review requires approve; reading artifacts requires observe.",
		ar_revision: "Fixed artifact revision",
		ar_lineage: "Central source and execution evidence",
		ar_check: "Check original operations",
		ar_new_review: "Record another review",
		ar_recorded: "Review of this exact revision was recorded. Task and work-item completion are unchanged.",
		ar_catalog: "Saved results from managed sources",
		ar_no_artifacts: "No reviewable managed-source results on this page.",
		ar_invalid_result: "The response does not match the original operation, fixed revision or central source proof. The original request and key are retained.",
		ar_storage: "The original operation recovery data could not be saved. Enable local storage for this application before submitting.",
		ar_original_credential: "Capture recovery requires the original credential and manage/observe scopes. Restore that credential; the original request and key stay saved.",
		ar_original_preview: "Original capture preview and source evidence",
		sessions_label: "Title",
		sessions_workspace: "Workspace",
		sessions_workspace_id: "Workspace ID",
		sessions_id: "Session ID",
		sessions_title: "Sessions",
		sessions_intro: "Browse sessions by host and workspace, with manual work and earlier records kept in view.",
		sessions_search: "Search loaded sessions",
		sessions_workspaces: "Loaded workspaces",
		sessions_scope_note: "Counts cover loaded pages only.",
		sessions_all_loaded: "All loaded sessions",
		sessions_loaded_count: "{count} loaded",
		sessions_projects: "Projects and work items",
		sessions_workspace_unknown: "Workspace not recorded",
		sessions_workspace_unverified: "No recorded workspace ID",
		sessions_scope_missing: "Selected workspace is not in this view",
		sessions_no_matches: "No matching sessions in this view.",
		sessions_more_hint: "More pages are available. Load more, or adjust your search and filters.",
		sessions_empty_hint: "Adjust your search, host or access filter. Absence from this view does not mean work has ended.",
		sessions_showing: "Showing {shown} · {loaded} loaded",
		sessions_page_note: "Search and workspace selection cover loaded pages only.",
		sessions_manual: "Manual",
		sessions_connector: "Connector created",
		sessions_origin_unknown: "Origin unknown",
		sessions_access_unknown: "Access unknown",
		sessions_details: "Status and records",
		sessions_runtime_stale: "Activity and pending requests have not been rechecked.",
		sessions_not_seen: "Not in latest scan",
		sessions_stale: "Observation needs updating",
		sessions_activity_unknown: "Activity unknown",
		permissions_title: "Session permissions",
		permissions_mode: "Requested mode",
		permissions_default: "Normal permissions",
		permissions_allow_all: "Allow all",
		permissions_apply: "Apply permissions",
		permissions_check: "Check original operation",
		permissions_new: "Start another change",
		permissions_retry: "Retry original request",
		permissions_details: "View operation and step receipts",
		permissions_help: "Choose the permissions to apply. This does not show the current mode; host policy and confinement limits still apply.",
		permissions_default_help: "Use the normal approval flow, keeping prompts for actions that need confirmation.",
		permissions_allow_help: "Bypass the agent's approval prompts, including file writes and command execution. The host may still refuse this change.",
		permissions_unavailable: "Requires current session data, operate scope, and explicit central permission for this action and host writes.",
		permissions_unknown: "The result is not yet confirmed. The original request is retained.",
		permissions_fixed: "The mode, session and operation stay fixed. Check the receipts for partial or unknown results.",
		permissions_invalid_result: "The operation reply does not match the original permission request.",
		permissions_damaged: "The saved request is incomplete. Check operation history before proceeding.",
		permissions_accepted: "BAT accepted the requested configuration; the running agent's settings have not been independently verified.",
		permissions_next_turn: "Codex uses this setting on its next turn.",
		permissions_refused: "This request was refused before admission. You can explicitly start another change; the original request will not retry automatically.",
		capture_title: "Capture a remote file",
		capture_host: "Source host",
		capture_session: "Full manual session ID",
		capture_path: "Remote relative file path",
		capture_help: "Enter one file path relative to the selected manual session folder. The source is read without being changed.",
		capture_preview: "Preview source file",
		capture_review: "I reviewed this file and its source evidence",
		capture_save: "Save reviewed file",
		capture_check: "Check original capture",
		capture_new: "Capture another file",
		capture_attach: "Add to attachment draft",
		capture_attached: "Added to the attachment draft. Save the work item or start the work to apply it.",
		capture_name: "Filename",
		capture_bytes: "Bytes",
		capture_source: "Source",
		capture_root: "Session folder",
		capture_repository: "Repository",
		capture_expiry: "Preview expires",
		capture_single_file: "Only this file is captured; other uncommitted changes are excluded.",
		capture_expired: "Preview expired. Preview and review again; capture has not been submitted.",
		capture_fixed: "The original preview and operation identity are retained. Read-back does not select newer content.",
		capture_unknown: "Submission outcome is unknown. Check the same capture; its draft and operation key are retained.",
		capture_saved: "Saved a fixed attachment revision, available in attachment selection:",
		capture_scope_observe: "Preview requires observe scope.",
		capture_scope_manage: "Saving requires manage and observe scopes and central capture capability.",
		capture_manual_only: "The source must be a full session explicitly observed as manually created.",
		capture_invalid_preview: "Central preview does not match the selected source.",
		capture_invalid_result: "Unable to verify the saved attachment revision and capture source.",
		obs_unknown: "unknown",
		obs_state_evidence: "State and evidence",
		obs_lifecycle_note: "Idle, unloaded and no tab do not mean ended. Lifecycle stays unknown without end evidence.",
		obs_discovery: "Discovery coverage",
		obs_discovery_note: "This shows central recorded discovery; it does not start another host scan. Not observed does not mean absent.",
		obs_scan_status: "Latest scan",
		obs_last_success: "Last successful observation",
		obs_last_attempt: "Latest read completed",
		obs_authority: "Read authority",
		obs_verified: "verified",
		obs_unverified: "unverified",
		obs_scan_coverage: "Read methods, coverage and failures",
		obs_outside_scan: "Outside this scan",
		obs_no_scan: "No discovery evidence has been recorded for this host.",
		obs_new_facts: "New journal facts are available. Loaded pages keep their snapshot; refresh to check this resource.",
		obs_event_kind: "Event kind (optional)",
		obs_execution_filter: "Execution ID (optional)",
		obs_read_latest: "Read latest records",
		obs_evidence: "Original IDs and evidence",
		obs_occurred: "Occurred",
		obs_recorded: "Recorded",
		obs_pending_binding: "session binding pending",
		obs_half_open: "Sequence interval [{start}, {end})",
		obs_follow_up: "Follow-up of",
		obs_empty: "No recorded evidence in this range.",
		obs_snapshot: "Fixed journal snapshot: {seq}.",
		obs_historical_limits: "Earlier history may be incomplete; unknown times are not inferred.",
		obs_first_recorded: "First recorded",
		obs_relations: "Execution and session relations",
		obs_history: "Resource history",
		obs_include_closed: "Include closed relations",
		obs_execution: "Execution",
		obs_worktree: "Worktree",
		obs_known_identity: "Central known resource ID. Relations and history do not grant write authority.",
		obs_inventory_note: "Browse by stable ID while retaining loaded pages. Inventory reflects changing observations, without snapshot isolation.",
		obs_axis_connection: "Connection",
		obs_axis_loading: "Loading",
		obs_axis_tab: "Tab",
		obs_axis_activity: "Activity",
		obs_axis_lifecycle: "Lifecycle",
		obs_axis_enumeration: "Enumeration",
		obs_axis_freshness: "Freshness",
		obs_value_unknown: "unknown",
		obs_value_connected: "connected",
		obs_value_not_connected: "not connected",
		obs_value_loaded: "loaded",
		obs_value_not_loaded: "not loaded",
		obs_value_present: "present",
		obs_value_no_tab: "no tab",
		obs_value_starting: "starting",
		obs_value_streaming: "streaming",
		obs_value_not_streaming: "not streaming",
		obs_value_active: "active",
		obs_value_ended: "ended",
		obs_value_gone: "gone",
		obs_value_missing: "missing",
		obs_value_fresh: "fresh",
		obs_value_stale: "stale",
		obs_scope_other_profiles_and_hosts: "Other profiles and hosts",
		obs_scope_manual_sessions_without_tabs_or_facts: "Manual sessions without tabs or facts",
		obs_scope_arbitrary_transcripts: "Unbound transcripts",
		obs_scope_codex_rollouts: "Codex rollout scans",
		obs_scope_background_git_state: "Background Git probes",
		obs_scope_earlier_history: "Earlier history",
		parent_archived: "This item or its project is archived. Your edit draft is retained.",
		pending_changed: "The pending request changed. Your draft is retained; review the current request before answering.",
		files_unavailable: "The original transfer is unavailable on this connection. Removing it from the draft does not cancel the upload.",
		files_choose: "Choose files",
		files_help: "Selection fixes the file contents. Verified uploads become attachments.",
		files_drop: "Enable file drop",
		files_drop_help: "Drop files into this window, then choose Upload to add them to this draft.",
		files_upload: "Upload",
		files_progress: "Local transfer progress",
		files_stop: "Stop transfer",
		files_retry: "Retry original transfer",
		files_check: "Check result",
		files_cancel: "Cancel upload",
		files_discard: "Clear local receipt",
		files_save: "Save As",
		files_preview: "Preview",
		files_selected: "Selected",
		files_checking: "Checking original operation",
		files_uploading: "Sending",
		files_verifying: "Verifying",
		files_downloading: "Downloading",
		files_saving: "Saving",
		files_ready: "Verified",
		files_saved: "Saved",
		files_stopped: "Stopped; original result retained",
		files_failed: "Operation failed",
		files_cancelled: "Cancelled",
		files_receipt_mismatch: "The transfer receipt does not match the original file. Attachment was not added.",
		attachment_file_changed: "Choose the same file to recover this upload; remove this entry before choosing different content.",
		attachment_pending: "Upload outcome is still pending. Retry the original operation with the same file.",
		existing_artifact: "Uploaded attachment",
		add_attachment: "Add attachment",
		attachments: "Attachments",
		choose_attachments: "Choose attachments",
		upload_on_choose: "Files upload when chosen. Uploaded revisions are saved with your draft.",
		choose_again: "Choose this file again. The browser cannot reopen local files after a reload.",
		uploading: "Uploading…",
		retry: "Retry",
		attachment_role: "Attachment role",
		attachment_input: "Input",
		attachment_result: "Result",
		attachments_not_ready: "Finish uploading or remove the unfinished files first.",
		source_unavailable: "Source HEAD is unavailable. Your draft is kept; retry after reconnecting.",
		confirm_source: "Keep the original commit and attachments; resume this run",
		materializations: "Attachment transfer",
		material_pending: "Pending",
		material_transferring: "Transferring",
		material_uncertain: "Checking",
		material_verified: "Verified",
		material_blocked: "Blocked",
		"nav_cleanup": "Cleanup and retained work",
		"cleanup_target": "Choose a scope",
		"cleanup_target_work_item": "Work item",
		"cleanup_target_task": "Execution task",
		"cleanup_task_preview": "Preview this task's resource cleanup",
		"cleanup_check": "Check original cleanup",
		"cleanup_new": "Preview another cleanup",
		"cleanup_invalid_result": "The operation response does not match the original cleanup request.",
		"cleanup_task_help": "Task cleanup uses the complete task ID. Central checks terminal state, shared resources and unresolved commands. Uncommitted task content, task branches and task history are retained.",
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
		"cleanup_reason_automatic": "Automatically cleaned by the task service, with retained content and operation receipts.",
		"cleanup_reason_historical": "Historical record from an earlier task cleanup event; no current reviewed operation is implied.",
		"cleanup_reason_recorded": "Cleanup was recorded; inspect its receipt for the original source.",
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
		"cleanup_reason_TASK_OWNED": "This resource needs cleanup authority from its owning task. It remains retained in this scope or state.",
		"cleanup_reason_RETAINED_COPY": "The original branch remains as a retained copy.",
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
		dep_pull_request: "Pull request",
		dep_desired: "Selected deployment",
		dep_observed: "Current observed version",
		dep_last_verified: "Last verified version",
		dep_history: "Deployment history",
		dep_no_history: "No deployments yet.",
		dep_no_version: "No version recorded.",
		dep_not_observed: "not observed yet",
		dep_observed_at: "Observed: {time}",
		dep_verified_at: "Verified: {time}",
		dep_artifact: "Artifact {id}",
		dep_not_undone: "Rollback does not undo",
		dep_no_limits: "This recipe declares no excluded side effects.",
		dep_rollback: "Rollback to this version",
		dep_retry: "Retry deploy · {sha}",
		dep_confirm_rollback: "Start rollback",
		dep_confirm_retry: "Retry this deployment",
		dep_rollback_review: "Review rollback",
		dep_retry_review: "Review deploy retry",
		dep_retry_only: "Deploy this saved identity again. The PR is never merged again.",
		dep_retry_unavailable: "This old record has no retryable fixed identity; preview a new deployment.",
		dep_preview_generation: "{env} · environment generation {generation}",
		dep_stale_preview: "The environment or recipe changed. Review the fresh preview below, then submit again if intended. Nothing is re-submitted automatically.",
		dep_refused: "The deployment request could not proceed. See operation details.",
		dep_open_operation: "View operation",
		dep_operation_details: "Operation details",
		dep_run: "Provider run",
		dep_attempt: "Run attempt",
		dep_error_code: "Error code",
		dep_needs_scope: "Requires deploy scope.",
		dep_missing_recipe: "This recipe is no longer configured.",
		dep_missing_verification: "Deploy disabled: add recipe verification.",
		dep_disabled: "Deployment is unavailable under the current capabilities.",
		dep_provider_pending: "The provider outcome is still pending; retry is unavailable.",
		dep_attention: "Needs attention",
		dep_attention_help: "Compare the selected and observed versions. Check the operation details before taking action.",
		dep_drift: "The observed version differs from the selected deployment. No deployment is started automatically.",
		dep_superseded: "Superseded by a newer selection.",
		dep_new_desired: "View new selection",
		dep_provider_run: "Original provider run",
		dep_previous: "Previous",
		dep_next: "Next",
		dep_page: "Page {page}",
		dep_ROLLBACK_UNSUPPORTED: "This recipe does not support rollback.",
		dep_ROLLBACK_TARGET_INVALID: "This version is unverified or belongs to another recipe or environment.",
		dep_ROLLBACK_ARTIFACT_UNAVAILABLE: "The saved artifact is unavailable.",
		dep_ROLLBACK_ARTIFACT_EXPIRED: "The saved artifact has expired.",
		dep_version_health: "Runtime version and health verified.",
		dep_version_only: "Runtime version verified; health is not checked by this recipe.",
		dep_health_only: "Health passed; runtime version is not checked by this recipe.",
		dep_state_selected: "Selected",
		dep_state_waiting_order: "Waiting for environment",
		dep_state_queued: "Queued",
		dep_state_building: "Building",
		dep_state_waiting_environment: "Waiting for approval",
		dep_state_deploying: "Deploying",
		dep_state_verifying: "Verifying",
		dep_state_succeeded: "Verified",
		dep_state_failed: "Failed",
		dep_state_cancelled: "Cancelled",
		dep_state_uncertain: "Outcome unknown",
		dep_state_needs_attention: "Needs attention",
		dep_state_unverified: "Unverified",
		dep_state_superseded: "Superseded",
		dep_operation: "Operation",
		dep_status: "State",
		dep_generation: "Environment generation {generation}",
		offline_actions_paused: "Central offline · actions paused",
		sync_waiting: "Waiting to refresh · draft preserved",
		desktop_add_credential: "Add credential",
		desktop_replace_credential: "Replace credential",
		desktop_forget_credential: "Forget saved credential",
		desktop_reload_configuration: "Reload configuration",
		desktop_connecting: "Connection in progress…",
		desktop_endpoint: "Central address",
		desktop_expected_actor: "Expected identity",
		desktop_configuration_file: "Configuration file",
		desktop_credential_source: "Credential source",
		desktop_source_launch_environment: "Memory-only launch credential",
		desktop_source_windows_credential_manager: "Windows Credential Manager",
		desktop_enrollment_help: "Enter the Connector API token in the Windows dialog’s Password field. After identity verification, it is saved for this Windows account’s next login.",
		desktop_enrollment_unsupported: "Protected storage and credential entry are not available on this platform yet. A launch credential can be used in memory; it is never saved to disk.",
		desktop_forget_help: "Removes this computer’s saved credential and disconnects; it does not revoke the central token. Drafts and original operation IDs stay saved.",
		desktop_forgotten: "Saved credential removed and disconnected.",
		desktop_reloaded: "Configuration reloaded. Verify the connection to continue; existing drafts stay saved.",
		desktop_disconnected: "Disconnected. Central work continues.",
		desktop_enrollment_cancelled: "Credential entry cancelled. The existing connection is unchanged.",
		desktop_connection: "Desktop central connection",
		desktop_local: "Local capabilities",
		desktop_connect_needed: "Connect to the configured central Connector.",
		desktop_polling: "connected · updates every second",
		desktop_config_needed: "Central connection is not configured.",
		desktop_credential_missing: "No native credential is available yet.",
		desktop_credential_help: "The central address and expected identity come from local configuration. Credentials stay in the native app, outside this page.",
		desktop_dashboard_only: "Dashboard is available without BAT installed. Local Fleet connections use your configured Kit. Opening BAT, native attachments, login autostart and updates are not available yet. Closing the window keeps the app in the tray; quitting does not stop central work or Fleet.",
		fleet_title: "Local Fleet connections",
		fleet_help: "Choose connections for this computer. Your selection and observed readiness are shown separately.",
		fleet_apply: "Save connections",
		fleet_refresh: "Read status",
		fleet_use_current: "Use current selection",
		fleet_start: "Start connection monitor",
		fleet_quit: "Stop local connection monitor",
		fleet_monitor_running: "Monitor running",
		fleet_monitor_stopped: "Monitor stopped",
		fleet_ready: "Ready",
		fleet_degraded: "Partly available",
		fleet_down: "Unavailable",
		fleet_off: "Off",
		fleet_fresh: "Recent observation",
		fleet_stale: "Observation stale",
		fleet_unavailable: "No current observation",
		fleet_applied: "The monitor has read the current selection.",
		fleet_waiting: "Waiting for the monitor to read the current selection.",
		fleet_changed: "The selection or monitor changed. Your draft is preserved; read and review the current selection.",
		fleet_other_owner: "This monitor is outside this login session's control; status is read-only.",
		fleet_invalid: "Fleet configuration needs attention ({n} issues).",
		fleet_windows: "Fleet connection management requires Windows.",
		fleet_setup: "Fleet Kit is not configured. Follow desktop setup to select its installation.",
		fleet_working: "Updating connections…",
		fleet_saved: "Selection saved; the monitor reports readiness separately.",
		fleet_quit_requested: "Monitor stop requested; waiting for status.",
		fleet_unknown: "The outcome is unknown; your draft is preserved. Read status before acting again.",
		fleet_read_failed: "Fleet status unavailable; actions are paused.",
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
var nativeFileSupport = false;
async function nativeStatus() {
	const status = await invoke("native_status");
	nativeFileSupport = status.file_transfers === true;
	return status;
}
var nativeFilesStatus = () => invoke("native_files_status");
var nativeFilesPick = (draftId) => invoke("native_files_pick", { draftId });
var nativeFilesUpload = (handleId) => invoke("native_files_upload", { handleId });
var nativeFilesDropTarget = (draftId, enabled) => invoke("native_files_drop_target", {
	draftId,
	enabled
});
var nativeFilesControl = (transferId, action) => invoke("native_files_control", {
	transferId,
	action
});
var nativeFilesSave = (reference) => invoke("native_files_save", { reference });
var nativeFilesPreview = (reference) => invoke("native_files_preview", { reference });
var nativeConnect = () => invoke("connector_connect");
var nativeDisconnect = () => invoke("connector_disconnect");
var nativeEnroll = () => invoke("connector_enroll", { locale: navigator.language.toLowerCase().startsWith("zh") ? "zh-TW" : "en-US" });
var nativeReloadConfiguration = () => invoke("connector_reload_configuration");
var nativeForgetCredential = () => invoke("connector_forget_credential");
var openExternal = (url) => invoke("open_external", { url });
var fleetAvailability = () => invoke("fleet_availability");
var fleetRequest = (input) => invoke("fleet_request", { input });
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
async function connectorUploadArtifact(operationId, bytes, browserToken) {
	if (!/^op_[0-9a-f]{32}$/.test(operationId)) throw new Error("Invalid artifact upload operation ID");
	if (nativeDesktop) {
		if (bytes.byteLength > 16777216) throw new Error("Artifact exceeds the native 16 MiB upload limit");
		return invoke("connector_upload_artifact", bytes, { headers: { "x-batc-upload-operation": operationId } });
	}
	const res = await fetch(`/api/v1/artifacts/uploads/${operationId}/content`, {
		method: "POST",
		redirect: "error",
		headers: {
			Authorization: `Bearer ${browserToken}`,
			"Content-Type": "application/octet-stream"
		},
		body: bytes
	});
	return {
		status: res.status,
		data: await res.json().catch(() => ({}))
	};
}
//#endregion
//#region src/native-files.js
var pending = new Set([
	"checking",
	"uploading",
	"verifying",
	"downloading",
	"saving"
]);
var fixedRef = (ref) => ({
	artifact_id: ref.artifact_id,
	revision: ref.revision,
	digest: ref.digest
});
var sameRef = (a, b) => a && b && a.artifact_id === b.artifact_id && a.revision === b.revision && a.digest === b.digest;
function nativeAttachments({ h, t, guard, canWrite, draftId, onReceipt, onDiscard, onVisibility, attached }) {
	const rows = h("div", { class: "native-transfers" }), notice = h("p", {
		class: "muted",
		role: "status"
	});
	const preview = h("div", {
		class: "file-preview",
		hidden: true
	});
	const box = h("div", { class: "native-files" }, rows, notice, preview);
	const known = new Map(), downloads = new Set();
	let armed = false, refreshing, picking = false, objectUrl = null, stopped = false;
	const live = () => {
		guard();
		if (!box.isConnected) throw new Error("Attachment form changed");
	};
	const failure = (error) => {
		try {
			live();
			notice.textContent = String(error?.message || error);
		} catch {}
	};
	const writable = () => {
		live();
		if (!canWrite()) throw new Error(t("offline_actions_paused"));
	};
	const act = async (receipt, action) => {
		try {
			live();
			if (["retry", "cancel_upload"].includes(action) && receipt.direction === "upload") writable();
			await nativeFilesControl(receipt.transfer_id, action);
			live();
			if (action === "discard_local") onDiscard(receipt.transfer_id);
			await refresh();
		} catch (error) {
			failure(error);
		}
	};
	const render = () => {
		rows.replaceChildren(...[...known.values()].filter((r) => r.direction === "download" || !attached(r.transfer_id)).map((r) => {
			const active = pending.has(r.stage), percent = r.size_bytes ? Math.min(100, Math.floor(r.transferred_bytes / r.size_bytes * 100)) : 0;
			return h("div", { class: "file-transfer" }, h("div", { class: "row" }, h("div", { class: "grow" }, r.display_name, h("div", { class: "muted" }, `${t(`files_${r.stage}`)} · ${r.transferred_bytes} / ${r.size_bytes} B`)), r.operation_id ? h("a", { href: `#/op/${r.operation_id}` }, t("dep_operation_details")) : null), active ? h("progress", {
				max: 100,
				value: percent,
				"aria-label": t("files_progress")
			}) : null, r.error ? h("p", { class: "muted" }, r.error) : null, h("div", { class: "actions" }, active ? h("button", {
				class: "secondary",
				onclick: () => act(r, "stop")
			}, t("files_stop")) : null, !active && ![
				"ready",
				"saved",
				"failed",
				"cancelled"
			].includes(r.stage) ? h("button", {
				class: "secondary",
				disabled: r.direction === "upload" && !canWrite(),
				onclick: () => act(r, "retry")
			}, t(r.stage === "selected" ? "files_upload" : "files_retry")) : null, !active && r.direction === "upload" && r.stage !== "selected" && ![
				"ready",
				"failed",
				"cancelled"
			].includes(r.stage) ? h("button", {
				class: "secondary",
				onclick: () => act(r, "check")
			}, t("files_check")) : null, !active && r.operation_id && ![
				"succeeded",
				"failed",
				"cancelled"
			].includes(r.operation_status) ? h("button", {
				class: "secondary",
				disabled: !canWrite(),
				onclick: () => act(r, "cancel_upload")
			}, t("files_cancel")) : null, !active && (r.direction === "download" || r.stage === "selected" || [
				"ready",
				"failed",
				"cancelled"
			].includes(r.stage)) ? h("button", {
				class: "secondary",
				onclick: async () => {
					await act(r, "discard_local");
				}
			}, t("files_discard")) : null));
		}));
	};
	const adopt = (r) => {
		if (!/^file_[0-9a-f]{32}$/.test(r?.transfer_id) || !/^[0-9a-f]{64}$/.test(r.digest) || !Number.isSafeInteger(r.size_bytes) || r.size_bytes < 0 || r.size_bytes > 16777216 || typeof r.display_name !== "string") throw new Error(t("files_receipt_mismatch"));
		const previous = known.get(r.transfer_id);
		if (previous && [
			"intent_key",
			"direction",
			"draft_id",
			"display_name",
			"size_bytes",
			"digest"
		].some((k) => previous[k] !== r[k])) throw new Error(t("files_receipt_mismatch"));
		if (r.direction === "upload" && r.draft_id !== draftId) return;
		if (r.stage === "ready" && (r.operation_status !== "succeeded" || !r.operation_id || r.artifact?.digest !== r.digest || !/^art_[0-9a-f]{32}$/.test(r.artifact?.artifact_id) || !Number.isSafeInteger(r.artifact?.revision))) throw new Error(t("files_receipt_mismatch"));
		known.set(r.transfer_id, r);
		if (r.direction === "upload" && JSON.stringify(previous) !== JSON.stringify(r)) onReceipt(r);
	};
	const refresh = async () => {
		if (refreshing) return refreshing;
		const task = (async () => {
			live();
			const status = await nativeFilesStatus();
			live();
			const previousKeys = [...known.keys()].join(","), current = new Set();
			for (const receipt of status.transfers) if (receipt.direction === "upload" && receipt.draft_id === draftId || receipt.direction === "download" && (receipt.stage !== "saved" || downloads.has(receipt.transfer_id))) {
				current.add(receipt.transfer_id);
				adopt(receipt);
			}
			for (const id of known.keys()) if (!current.has(id)) known.delete(id);
			if ([...known.keys()].join(",") !== previousKeys) onVisibility();
			if (status.drop_error) notice.textContent = status.drop_error;
			render();
		})();
		refreshing = task;
		try {
			await task;
		} finally {
			if (refreshing === task) refreshing = null;
		}
	};
	const pick = async () => {
		if (picking) return;
		try {
			writable();
			picking = true;
			const receipts = await nativeFilesPick(draftId);
			live();
			for (const receipt of receipts) {
				adopt(receipt);
				writable();
				await nativeFilesUpload(receipt.transfer_id);
				live();
			}
			await refresh();
		} catch (error) {
			failure(error);
			await refresh().catch(failure);
		} finally {
			picking = false;
		}
	};
	const drop = h("button", {
		class: "secondary",
		"aria-pressed": false,
		onclick: async () => {
			try {
				writable();
				armed = !armed;
				await nativeFilesDropTarget(draftId, armed);
				live();
				drop.setAttribute("aria-pressed", String(armed));
				notice.textContent = armed ? t("files_drop_help") : "";
			} catch (error) {
				armed = false;
				failure(error);
			}
		}
	}, t("files_drop"));
	const closePreview = () => {
		preview.replaceChildren();
		preview.hidden = true;
		if (objectUrl) URL.revokeObjectURL(objectUrl);
		objectUrl = null;
	};
	const actions = (ref) => h("span", { class: "actions file-actions" }, h("button", {
		class: "secondary",
		onclick: async () => {
			try {
				live();
				const expected = fixedRef(ref), receipt = await nativeFilesSave(expected);
				live();
				if (!receipt) return;
				if (receipt.direction !== "download" || !sameRef(receipt.artifact, expected)) throw new Error(t("files_receipt_mismatch"));
				downloads.add(receipt.transfer_id);
				adopt(receipt);
				render();
			} catch (error) {
				failure(error);
			}
		}
	}, t("files_save")), h("button", {
		class: "secondary",
		onclick: async () => {
			try {
				live();
				const content = await nativeFilesPreview(fixedRef(ref));
				live();
				closePreview();
				let view;
				if (content.media_type === "text/plain" && typeof content.text === "string" && content.text.length <= 262144) view = h("pre", {}, content.text);
				else if (content.media_type === "image/png" && typeof content.base64 === "string" && content.base64.length <= 28e5) {
					const bytes = Uint8Array.from(atob(content.base64), (c) => c.charCodeAt(0));
					objectUrl = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
					view = h("img", {
						src: objectUrl,
						alt: t("files_preview")
					});
				} else throw new Error(t("files_receipt_mismatch"));
				preview.hidden = false;
				preview.append(h("div", { class: "actions" }, h("strong", {}, t("files_preview")), h("button", {
					class: "secondary",
					onclick: closePreview
				}, t("close"))), view);
			} catch (error) {
				failure(error);
			}
		}
	}, t("files_preview")));
	const tick = async () => {
		try {
			live();
			await refresh();
			if (armed) {
				writable();
				await nativeFilesDropTarget(draftId, box.getClientRects().length > 0 && document.visibilityState === "visible");
			}
		} catch (error) {
			try {
				live();
				failure(error);
			} catch {
				stopped = true;
				closePreview();
				await nativeFilesDropTarget(draftId, false).catch(() => {});
			}
		}
		if (!stopped) setTimeout(tick, 1e3);
	};
	queueMicrotask(tick);
	return {
		box,
		pick,
		drop,
		actions,
		refresh,
		has: (id) => known.has(id)
	};
}
//#endregion
//#region src/fleet.js
async function mountFleet(main, { h, t }) {
	if (!main.isConnected) return () => {};
	const panel = h("section", {
		class: "panel",
		"aria-label": t("fleet_title")
	});
	const content = h("div"), message = h("p", {
		class: "muted",
		role: "status"
	});
	panel.append(h("h2", {}, t("fleet_title")), h("p", { class: "muted" }, t("fleet_help")), content, message);
	main.append(panel);
	let disposed = false, busy = false, readable = false, timer, snapshot, draft, binding;
	const alive = () => !disposed && panel.isConnected;
	const key = () => `batc.desktop.fleet.selection.${binding}`;
	const save = () => {
		try {
			if (draft) sessionStorage.setItem(key(), JSON.stringify(draft));
			else sessionStorage.removeItem(key());
		} catch {}
	};
	const same = (a, b) => a.length === b.length && [...a].sort().every((x, i) => x === [...b].sort()[i]);
	const changed = () => draft && (draft.revision !== snapshot.selection.revision || draft.epoch !== snapshot.monitor.epoch);
	const editable = () => readable && !busy && snapshot?.configuration.valid && (snapshot.monitor.state === "stopped" || snapshot.monitor.controllable);
	const render = () => {
		if (!alive() || !snapshot) return;
		const names = draft?.connections || snapshot.selection.connections;
		const ready = new Map([...snapshot.readiness.hosts || [], snapshot.readiness.connector].filter(Boolean).map((row) => [row.name, row]));
		const focus = document.activeElement?.dataset?.fleetName;
		const rows = snapshot.configuration.connections.map((entry) => {
			const input = h("input", {
				type: "checkbox",
				checked: names.includes(entry.name),
				disabled: !editable() || !!changed(),
				"data-fleet-name": entry.name,
				onchange: () => {
					if (!draft) draft = {
						revision: snapshot.selection.revision,
						epoch: snapshot.monitor.epoch,
						connections: [...snapshot.selection.connections]
					};
					draft.connections = input.checked ? [...new Set([...draft.connections, entry.name])] : draft.connections.filter((x) => x !== entry.name);
					if (same(draft.connections, snapshot.selection.connections)) draft = null;
					save();
					render();
				}
			});
			const observed = ready.get(entry.name);
			return h("div", { class: "row" }, h("label", { class: "grow fleet-choice" }, input, " ", entry.label), h("span", { class: "chip" }, t("fleet_" + (observed?.level || "unavailable"))), observed?.blocking ? h("span", { class: "muted" }, observed.blocking) : null);
		});
		content.replaceChildren(...[
			h("p", {}, t("fleet_monitor_" + snapshot.monitor.state), " · ", t("fleet_" + snapshot.readiness.state)),
			!snapshot.configuration.valid ? h("p", { class: "error" }, t("fleet_invalid", { n: snapshot.configuration.issue_count })) : null,
			snapshot.monitor.state === "running" && !snapshot.monitor.controllable ? h("p", { class: "note" }, t("fleet_other_owner")) : null,
			...rows,
			h("p", { class: "muted" }, t(snapshot.selection.applied_revision === snapshot.selection.revision ? "fleet_applied" : "fleet_waiting")),
			changed() ? h("p", { class: "error" }, t("fleet_changed")) : h("span"),
			h("div", { class: "actions" }, h("button", {
				class: "primary",
				disabled: !editable() || !draft || !!changed(),
				onclick: () => mutate({
					action: "set_connections",
					connections: [...draft.connections],
					expected_selection_revision: draft.revision,
					expected_monitor_epoch: draft.epoch,
					expected_configuration_binding: binding
				})
			}, t("fleet_apply")), h("button", {
				class: "secondary",
				disabled: busy,
				onclick: () => read(true)
			}, t("fleet_refresh")), h("button", {
				class: "secondary",
				disabled: !readable || busy || !draft,
				onclick: () => {
					draft = null;
					save();
					message.textContent = "";
					render();
				}
			}, t("fleet_use_current"))),
			h("div", { class: "actions" }, h("button", {
				class: "secondary",
				disabled: !editable() || !!draft || snapshot.monitor.state !== "stopped",
				onclick: () => mutate({
					action: "ensure_monitor",
					expected_configuration_binding: binding
				})
			}, t("fleet_start")), h("button", {
				class: "danger",
				disabled: !editable() || !!draft || !snapshot.monitor.controllable,
				onclick: () => mutate({
					action: "quit_owned",
					expected_configuration_binding: binding,
					expected_monitor_epoch: snapshot.monitor.epoch
				})
			}, t("fleet_quit")))
		].filter(Boolean));
		if (focus) [...content.querySelectorAll("input")].find((input) => input.dataset.fleetName === focus)?.focus();
	};
	const accept = (value) => {
		if (!value?.configuration?.connections || !value?.monitor || !value?.selection || !value?.readiness) throw new Error(t("fleet_unavailable"));
		if (binding !== value.configuration.binding) {
			binding = value.configuration.binding;
			draft = null;
			try {
				const old = JSON.parse(sessionStorage.getItem(key()) || "null");
				if (old && Array.isArray(old.connections) && old.connections.every((x) => typeof x === "string") && typeof old.revision === "string") draft = old;
			} catch {}
		}
		snapshot = value;
		readable = true;
		if (draft && same(draft.connections, value.selection.connections)) {
			draft = null;
			save();
		}
	};
	const read = async (explicit = false) => {
		if (!alive() || busy) return;
		busy = true;
		render();
		try {
			const value = await fleetRequest({ action: "status" });
			if (!alive()) return;
			accept(value);
			if (explicit) message.textContent = "";
		} catch (error) {
			if (alive()) {
				readable = false;
				message.textContent = `${t("fleet_read_failed")} ${String(error)}`;
			}
		} finally {
			busy = false;
			render();
		}
	};
	const mutate = async (input) => {
		if (!editable() || !alive()) return;
		busy = true;
		readable = false;
		message.textContent = t("fleet_working");
		render();
		try {
			const result = await fleetRequest(input);
			if (!alive()) return;
			if (input.action !== "quit_owned") accept(result);
			message.textContent = t(input.action === "quit_owned" ? "fleet_quit_requested" : "fleet_saved");
		} catch (error) {
			if (alive()) message.textContent = `${t("fleet_unknown")} ${String(error)}`;
		} finally {
			busy = false;
			render();
		}
	};
	try {
		const availability = await fleetAvailability();
		if (!alive()) return () => {
			disposed = true;
		};
		if (!availability.configured || !availability.platform_supported) message.textContent = t(!availability.platform_supported ? "fleet_windows" : "fleet_setup");
		else {
			await read();
			const poll = async () => {
				if (!alive()) return;
				await read();
				if (alive()) timer = setTimeout(poll, 5e3);
			};
			timer = setTimeout(poll, 5e3);
		}
	} catch {
		message.textContent = t("fleet_unavailable");
	}
	return () => {
		disposed = true;
		clearTimeout(timer);
		panel.remove();
	};
}
//#endregion
//#region src/state/sessions.js
var text$1 = (value) => typeof value === "string" ? value : "";
function workspaceGroup(session) {
	const host = text$1(session.host), id = text$1(session.workspace_id), name = text$1(session.workspace);
	return {
		key: JSON.stringify([
			host,
			id ? "id" : name ? "label" : "unknown",
			id || name
		]),
		host,
		id,
		name
	};
}
function groupedSessions(sessions) {
	const groups = new Map();
	for (const session of sessions) {
		const group = workspaceGroup(session);
		if (!groups.has(group.key)) groups.set(group.key, {
			...group,
			sessions: []
		});
		groups.get(group.key).sessions.push(session);
	}
	return [...groups.values()].sort((a, b) => a.host.localeCompare(b.host) || (a.name || a.id).localeCompare(b.name || b.id) || a.key.localeCompare(b.key));
}
function matchesSession(session, query) {
	const haystack = [
		session.title,
		session.session_id,
		session.host,
		session.workspace,
		session.workspace_id,
		session.agent_kind,
		session.model,
		session.worktree_branch
	].map(text$1).join("\n").toLocaleLowerCase();
	return query.trim().toLocaleLowerCase().split(/\s+/).every((word) => haystack.includes(word));
}
function runtimeStale(session) {
	return Boolean(session.stale || session.fields_stale || session.state?.evidence?.activity?.stale);
}
function sessionActivity(session) {
	if (session.pending) return {
		key: "pending_" + session.pending.kind,
		tone: "stale"
	};
	if (session.state?.lifecycle === "ended") return {
		key: "obs_value_ended",
		tone: ""
	};
	if (session.gone_at || ["gone", "missing"].includes(session.state?.enumeration)) return {
		key: "sessions_not_seen",
		tone: "stale"
	};
	if (runtimeStale(session)) return {
		key: "sessions_stale",
		tone: "stale"
	};
	if (session.streaming === true) return {
		key: "obs_value_streaming",
		tone: "info"
	};
	if (session.streaming === false) return {
		key: "obs_value_not_streaming",
		tone: ""
	};
	return {
		key: "sessions_activity_unknown",
		tone: ""
	};
}
//#endregion
//#region src/capture.js
var record$2 = (value) => value && typeof value === "object" && !Array.isArray(value);
var digest$1 = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
var operationId$2 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var previewId = (value) => typeof value === "string" && /^acpv_[0-9a-f]{32}$/.test(value);
var previewToken = (value) => typeof value === "string" && value.length > 0 && value.length <= 24576;
var validPreview$2 = (doc) => record$2(doc) && record$2(doc.source) && record$2(doc.evidence) && [
	doc.relative_path,
	doc.source.host,
	doc.source.session_id,
	doc.source.root,
	doc.source.repository_root,
	doc.evidence.head_sha
].every((value) => typeof value === "string" && value.length > 0) && doc.source.provenance === "manual" && doc.snapshot === false && Number.isFinite(doc.expires_at) && previewId(doc.preview_id) && previewToken(doc.preview_token) && digest$1(doc.fingerprint) && digest$1(doc.evidence.digest) && Number.isSafeInteger(doc.evidence.size_bytes) && doc.evidence.size_bytes >= 0;
function restore$2(value, source) {
	const saved = { input: {
		...source,
		relative_path: ""
	} };
	if (!record$2(value)) return saved;
	if (record$2(value.input)) {
		for (const key of [
			"host",
			"session_id",
			"relative_path"
		]) if (typeof value.input[key] === "string") saved.input[key] = value.input[key];
	}
	if (validPreview$2(value.preview)) saved.preview = value.preview;
	const intent = value.intent, request = intent?.request;
	const usable = request?.action === "artifact.capture" && previewId(request.target?.preview_id) && previewToken(request.params?.preview_token) && digest$1(request.preconditions?.expected_fingerprint) && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200;
	if (usable || operationId$2(intent?.operation_id)) saved.intent = {
		key: usable ? intent.key : null,
		request: usable ? request : null,
		operation_id: operationId$2(intent.operation_id) ? intent.operation_id : null,
		reviewed_digest: digest$1(intent.reviewed_digest) ? intent.reviewed_digest : saved.preview?.evidence.digest
	};
	return saved;
}
function capturePanel({ h, t, api, caps, guard, onEvents, errorBox, storageKey, source = {}, onAttach }) {
	let saved;
	try {
		saved = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	saved = restore$2(saved, source);
	let busy = false, revision = 0, disposed = false, refreshing = null;
	const host = h("select", { "aria-label": t("capture_host") }, h("option", { value: "" }, t("capture_host")), ...(caps()?.hosts || []).map((item) => h("option", { value: item.host }, item.host)));
	const session = h("input", {
		"aria-label": t("capture_session"),
		placeholder: "sess-…",
		maxlength: 256
	});
	const path = h("input", {
		"aria-label": t("capture_path"),
		placeholder: "notes/input.txt"
	});
	host.value = saved.input.host || "";
	session.value = saved.input.session_id || "";
	path.value = saved.input.relative_path || "";
	const notice = h("div", { role: "status" }), evidence = h("div", { "data-capture-evidence": "" });
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => update()
	});
	const review = h("label", { class: "capture-choice" }, reviewed, " ", t("capture_review"));
	const persist = () => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch {}
	};
	const current = () => ({
		host: host.value,
		session_id: session.value.trim(),
		relative_path: path.value
	});
	const scopes = () => caps()?.scopes || [];
	const supported = () => caps()?.artifacts?.capture?.manual_single_file === true;
	const mayPreview = () => supported() && scopes().includes("observe");
	const mayCapture = () => mayPreview() && scopes().includes("manage") && caps()?.actions?.some((item) => item.action === "artifact.capture" && item.allowed === true);
	const expired = () => !saved.preview || saved.preview.expires_at * 1e3 <= Date.now();
	const settled = () => [
		"succeeded",
		"failed",
		"cancelled"
	].includes(saved.operation?.status);
	const active = () => Boolean(saved.intent && (!settled() || saved.operation.status === "succeeded" && !saved.result) && !saved.refused);
	const currentView = () => {
		try {
			guard();
			return !disposed;
		} catch {
			return false;
		}
	};
	const validInput = (input) => input.host && input.session_id.length >= 6 && input.session_id.length <= 256 && !/[\x00-\x1f\x7f-\x9f/\\]/.test(input.session_id) && input.relative_path && new TextEncoder().encode(input.relative_path).length <= 4096 && !/[\\\x00-\x1f\x7f-\x9f]/.test(input.relative_path) && input.relative_path.split("/").every((part) => part && part !== "." && part !== ".." && part.toLowerCase() !== ".git");
	const showError = (error) => {
		if (currentView()) notice.replaceChildren(errorBox(error));
	};
	const preview = h("button", {
		class: "secondary",
		onclick: async () => {
			const input = current();
			guard();
			if (busy || saved.intent || !mayPreview() || !validInput(input)) return;
			const ticket = ++revision;
			busy = true;
			saved.preview = null;
			reviewed.checked = false;
			persist();
			render();
			try {
				const row = (await api("GET", `/sessions/${encodeURIComponent(input.host)}/${encodeURIComponent(input.session_id)}`)).session;
				guard();
				if (ticket !== revision) return;
				if (row?.provenance !== "manual" || row.host !== input.host || row.session_id !== input.session_id) throw new Error(t("capture_manual_only"));
				const response = await api("POST", "/artifact-capture-previews", input);
				guard();
				if (ticket !== revision) return;
				const doc = response.preview;
				if (!validPreview$2(doc) || doc.source.host !== input.host || doc.source.session_id !== input.session_id || doc.relative_path !== input.relative_path) throw new Error(t("capture_invalid_preview"));
				saved.preview = doc;
				persist();
				notice.replaceChildren();
			} catch (error) {
				if (ticket === revision) showError(error);
			} finally {
				busy = false;
				render();
			}
		}
	}, t("capture_preview"));
	const accept = async (operation) => {
		guard();
		const intent = saved.intent;
		if (!intent || !operationId$2(operation?.operation_id) || operation.action !== "artifact.capture" || intent.operation_id && intent.operation_id !== operation.operation_id || intent.request && operation.target?.preview_id !== intent.request.target.preview_id) throw new Error(t("capture_invalid_result"));
		saved.operation = operation;
		saved.intent.operation_id = operation.operation_id;
		persist();
		if (operation.status === "succeeded") {
			const ref = operation.result;
			if (!/^art_[0-9a-f]{32}$/.test(ref?.artifact_id) || !Number.isSafeInteger(ref.revision) || ref.revision < 1 || !digest$1(ref.digest) || ref.digest !== intent.reviewed_digest) throw new Error(t("capture_invalid_result"));
			const { artifact } = await api("GET", `/artifacts/${ref.artifact_id}/revisions/${ref.revision}`);
			guard();
			if (saved.intent !== intent) return;
			if (artifact.artifact_id !== ref.artifact_id || artifact.revision !== ref.revision || artifact.state !== "ready" || artifact.digest !== ref.digest || artifact.source?.kind !== "manual_capture" || artifact.source.operation_id !== operation.operation_id) throw new Error(t("capture_invalid_result"));
			saved.result = {
				artifact_id: ref.artifact_id,
				revision: ref.revision,
				digest: ref.digest
			};
			persist();
		}
		render();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			guard();
			if (busy || !mayCapture() || settled() && (saved.operation.status !== "succeeded" || saved.result) || saved.refused) return;
			if (!saved.intent) {
				if (expired() || !reviewed.checked) return;
				const doc = saved.preview;
				saved.intent = {
					key: crypto.randomUUID(),
					reviewed_digest: doc.evidence.digest,
					request: {
						action: "artifact.capture",
						target: { preview_id: doc.preview_id },
						params: { preview_token: doc.preview_token },
						preconditions: { expected_fingerprint: doc.fingerprint }
					}
				};
				persist();
			}
			busy = true;
			update();
			try {
				const intent = saved.intent;
				const result = intent.operation_id ? await api("GET", `/operations/${intent.operation_id}`) : await api("POST", "/operations?wait=3", intent.request, intent.key);
				guard();
				await accept(result.operation);
				notice.replaceChildren();
			} catch (error) {
				if (!currentView()) return;
				if (!saved.intent.operation_id && [
					"PREVIEW_EXPIRED",
					"PREVIEW_TOKEN_INVALID",
					"PREVIEW_MISMATCH",
					"INVALID_PARAMS"
				].includes(error.code)) saved.refused = true;
				persist();
				showError(error);
			} finally {
				busy = false;
				render();
			}
		}
	}, t("capture_save"));
	const reset = h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (busy || refreshing || active()) return;
			saved = { input: current() };
			reviewed.checked = false;
			revision++;
			persist();
			notice.replaceChildren();
			render();
		}
	}, t("capture_new"));
	const attach = onAttach ? h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (saved.result) {
				onAttach({ ...saved.result }, (saved.preview?.relative_path || saved.input.relative_path).split("/").at(-1));
				notice.textContent = t("capture_attached");
			}
		}
	}, t("capture_attach")) : null;
	const box = h("details", {
		class: "capture",
		"data-capture": "",
		hidden: !supported()
	}, h("summary", {}, t("capture_title")), h("p", { class: "muted" }, t("capture_help")), h("div", { class: "capture-fields" }, h("label", {}, t("capture_host"), host), h("label", {}, t("capture_session"), session), h("label", {}, t("capture_path"), path)), h("div", { class: "actions" }, preview), evidence, review, h("div", { class: "actions" }, apply, attach, reset), notice);
	function update() {
		const frozen = busy || Boolean(saved.intent);
		for (const field of [
			host,
			session,
			path
		]) field.disabled = frozen;
		preview.disabled = busy || Boolean(saved.intent) || !mayPreview() || !validInput(current());
		review.hidden = !saved.preview || Boolean(saved.intent);
		reviewed.disabled = expired();
		apply.hidden = settled() && (saved.operation.status !== "succeeded" || saved.result);
		apply.textContent = saved.intent ? t("capture_check") : t("capture_save");
		apply.disabled = busy || !mayCapture() || Boolean(saved.refused) || !saved.intent && (expired() || !reviewed.checked);
		reset.hidden = !saved.intent;
		reset.disabled = busy || Boolean(refreshing) || active();
		if (attach) {
			attach.hidden = !saved.result;
			attach.disabled = busy;
		}
		const expiry = evidence.querySelector("[data-capture-expiry]");
		if (expiry) expiry.textContent = saved.intent ? t("capture_fixed") : expired() ? t("capture_expired") : t("capture_single_file");
	}
	function render() {
		if (disposed) return;
		evidence.replaceChildren();
		if (!mayPreview()) evidence.append(h("p", { class: "muted" }, t("capture_scope_observe")));
		else if (!mayCapture()) evidence.append(h("p", { class: "muted" }, t("capture_scope_manage")));
		const doc = saved.preview;
		if (doc) {
			const facts = [
				[t("capture_name"), doc.relative_path.split("/").at(-1)],
				[t("capture_bytes"), String(doc.evidence.size_bytes)],
				["SHA-256", doc.evidence.digest],
				[t("capture_source"), `${doc.source.host} / ${doc.source.session_id}`],
				[t("capture_path"), doc.relative_path],
				[t("capture_root"), doc.source.root],
				[t("capture_repository"), doc.source.repository_root],
				["HEAD", doc.evidence.head_sha],
				[t("capture_expiry"), new Date(doc.expires_at * 1e3).toLocaleString()]
			];
			evidence.append(h("dl", { class: "kv" }, ...facts.flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, h("code", {}, value))])), h("p", {
				class: "muted",
				"data-capture-expiry": ""
			}));
		}
		if (saved.intent) evidence.append(h("p", {}, saved.operation ? `${t("op_" + saved.operation.status)} ` : t("capture_unknown"), saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, saved.intent.operation_id) : null, saved.operation?.status_reason ? ` · ${saved.operation.status_reason}` : ""));
		if (saved.result) evidence.append(h("p", { class: "pre" }, t("capture_saved"), " ", `${saved.result.artifact_id} · r${saved.result.revision} · ${saved.result.digest}`));
		update();
	}
	for (const field of [
		host,
		session,
		path
	]) field.addEventListener("input", () => {
		guard();
		if (saved.intent) return;
		revision++;
		saved.input = current();
		saved.preview = null;
		reviewed.checked = false;
		persist();
		render();
	});
	const refresh = async (fresh = false) => {
		if (!saved.intent?.operation_id) return;
		if (refreshing) {
			await refreshing;
			if (!fresh) return;
			guard();
			return refresh(true);
		}
		const id = saved.intent.operation_id;
		refreshing = (async () => {
			while (busy) {
				await new Promise((resolve) => setTimeout(resolve, 25));
				guard();
			}
			const { operation } = await api("GET", `/operations/${id}`);
			guard();
			if (saved.intent?.operation_id === id) await accept(operation);
		})();
		try {
			await refreshing;
		} finally {
			refreshing = null;
		}
	};
	const off = onEvents((event) => {
		if (!box.isConnected) {
			off();
			return;
		}
		if (!currentView()) {
			off();
			return;
		}
		if (event.resource_id === saved.intent?.operation_id || event.resource_id === saved.result?.artifact_id) return refresh(true);
	});
	const timer = setInterval(() => {
		if (!box.isConnected) {
			disposed = true;
			clearInterval(timer);
			off();
			return;
		}
		try {
			guard();
		} catch {
			disposed = true;
			clearInterval(timer);
			off();
			return;
		}
		update();
		if (saved.intent?.operation_id && (active() || saved.operation?.status === "succeeded" && !saved.result)) refresh().catch(showError);
	}, 1e3);
	queueMicrotask(() => {
		if (box.isConnected && saved.intent?.operation_id) refresh().catch(showError);
	});
	render();
	return box;
}
//#endregion
//#region src/permissions.js
var record$1 = (value) => value && typeof value === "object" && !Array.isArray(value);
var modeValue = (value) => ["default", "allow_all"].includes(value);
var operationId$1 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var terminal$3 = (operation) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(operation?.status);
var admissionRefusals$1 = new Set([
	"TASK_PAUSED",
	"CONTROL_VERSION_CONFLICT",
	"PERMISSIONS_HOST_POLICY",
	"CONFINEMENT_RAISE_REFUSED"
]);
function restore$1(value, target) {
	const saved = { mode: modeValue(value?.mode) ? value.mode : "default" };
	if (!record$1(value) || !value.intent) return saved;
	const intent = value.intent, request = intent.request;
	const valid = request?.action === "session.permissions" && request.target?.host === target.host && request.target?.session_id === target.session_id && modeValue(request.params?.mode) && record$1(request.preconditions) && Object.keys(request.preconditions).length === 0 && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200;
	saved.intent = {
		key: valid ? intent.key : null,
		request: valid ? {
			action: "session.permissions",
			target: { ...target },
			params: { mode: request.params.mode },
			preconditions: {}
		} : null,
		operation_id: operationId$1(intent.operation_id) ? intent.operation_id : null
	};
	if (valid && !saved.intent.operation_id && admissionRefusals$1.has(intent.refused)) saved.intent.refused = intent.refused;
	if (valid) saved.mode = request.params.mode;
	return saved;
}
function permissionsPanel({ h, t, api, caps, guard, errorBox, opStatus, storageKey, target, session, ready }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = restore$1(raw, target), operation = null, busy = false, refreshing = null, submission = null, readFailed = false;
	const mode = h("select", { "aria-label": t("permissions_mode") }, ...["default", "allow_all"].map((value) => h("option", { value }, t("permissions_" + value))));
	mode.value = saved.mode;
	const message = h("div", { role: "status" }), result = h("div", { "data-permission-result": "" });
	const explanation = h("p", { class: "muted" }), restriction = h("p", { class: "muted" });
	const persist = () => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch {}
	};
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const writable = () => ready() && session()?.api_access === "managed" && session()?.provenance === "connector_managed" && (caps()?.scopes || []).includes("operate") && caps()?.hosts?.some((host) => host.host === target.host && host.writes === true) && caps()?.actions?.some((action) => action.action === "session.permissions" && action.allowed === true);
	const accept = (candidate) => {
		guard();
		if (!saved.intent || !operationId$1(candidate?.operation_id) || candidate.action !== "session.permissions" || candidate.target?.host !== target.host || candidate.target?.session_id !== target.session_id || !modeValue(candidate.params?.mode) || saved.intent.request && candidate.params.mode !== saved.intent.request.params.mode || saved.intent.key && candidate.idempotency_key !== saved.intent.key || saved.intent.operation_id && candidate.operation_id !== saved.intent.operation_id) throw new Error(t("permissions_invalid_result"));
		operation = candidate;
		saved.intent.operation_id = candidate.operation_id;
		saved.mode = candidate.params.mode;
		mode.value = saved.mode;
		readFailed = false;
		persist();
		message.replaceChildren();
		update();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || readFailed || !writable() || saved.intent?.operation_id || saved.intent && (!saved.intent.request || saved.intent.refused)) return;
			busy = true;
			if (!saved.intent) {
				saved.intent = {
					key: crypto.randomUUID(),
					request: {
						action: "session.permissions",
						target: { ...target },
						params: { mode: saved.mode },
						preconditions: {}
					},
					operation_id: null
				};
				persist();
			}
			const intent = saved.intent;
			update();
			submission = (async () => {
				try {
					const response = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					if (saved.intent === intent) accept(response.operation);
				} catch (error) {
					if (current()) {
						if (error.status >= 400 && error.status < 500 && admissionRefusals$1.has(error.code)) {
							intent.refused = error.code;
							persist();
						}
						message.replaceChildren(errorBox(error));
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("permissions_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(showError)
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$3(operation) || saved.intent?.refused) || !writable()) return;
			saved = { mode: "default" };
			mode.value = saved.mode;
			operation = null;
			persist();
			message.replaceChildren();
			update();
		}
	}, t("permissions_new"));
	const box = h("details", {
		class: "permissions",
		"data-permissions": ""
	}, h("summary", {}, t("permissions_title")), h("p", { class: "muted" }, t("permissions_help")), h("label", { class: "permission-mode" }, t("permissions_mode"), mode), explanation, h("div", { class: "actions" }, apply, check, another), restriction, result, message);
	mode.addEventListener("change", () => {
		if (!current() || saved.intent) {
			mode.value = saved.mode;
			return;
		}
		saved.mode = modeValue(mode.value) ? mode.value : "default";
		persist();
		update();
	});
	function update() {
		const managed = session()?.api_access === "managed" && session()?.provenance === "connector_managed";
		box.hidden = !managed;
		mode.disabled = busy || Boolean(saved.intent);
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.disabled = busy || readFailed || !writable() || Boolean(saved.intent && !saved.intent.request);
		apply.textContent = t(saved.intent ? "permissions_retry" : "permissions_apply");
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$3(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed || !writable();
		explanation.textContent = t(saved.mode === "allow_all" ? "permissions_allow_help" : "permissions_default_help");
		restriction.textContent = writable() ? "" : t("permissions_unavailable");
		result.replaceChildren();
		if (saved.intent) {
			result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "permissions_refused" : "permissions_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null, operation?.status_reason ? ` · ${operation.status_reason}` : ""));
			result.append(h("p", { class: "muted" }, t("permissions_fixed")));
			if (operation?.status === "succeeded") result.append(h("p", { class: "muted" }, t("permissions_accepted"), operation.result?.agent_kind === "codex" ? " " + t("permissions_next_turn") : ""));
			if (!saved.intent.request && !saved.intent.operation_id) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		}
	}
	function showError(error) {
		if (current()) {
			readFailed = true;
			message.replaceChildren(errorBox(error));
			update();
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) return;
		const intent = saved.intent;
		refreshing = (async () => {
			const response = await api("GET", `/operations/${intent.operation_id}`);
			guard();
			if (saved.intent === intent) accept(response.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (error) {
			showError(error);
			throw error;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	update();
	return {
		box,
		update,
		refresh
	};
}
//#endregion
//#region src/approvals.js
var object$1 = (value) => value && typeof value === "object" && !Array.isArray(value);
var opId = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var mode = (value) => value === null || value === "default" || value === "allow_all";
var terminal$2 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var equal$2 = (a, b) => {
	if (a === b) return true;
	if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => equal$2(v, b[i]));
	return object$1(a) && object$1(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$2(a[k], b[k]));
};
var refusedBeforeAdmission = new Set([
	"BULK_PREVIEW_INVALID",
	"BULK_PREVIEW_EXPIRED",
	"BULK_PREVIEW_MISMATCH",
	"BULK_MODE_REFUSED",
	"CONTROL_VERSION_CONFLICT",
	"BULK_BINDING_CHANGED"
]);
function validPreview$1(p) {
	return object$1(p) && typeof p.host === "string" && p.host.length > 0 && (p.workspace === null || typeof p.workspace === "string") && typeof p.preview_token === "string" && p.preview_token.startsWith("bap1.") && p.preview_token.length <= 262144 && /^[0-9a-f]{64}$/.test(p.fingerprint) && Number.isFinite(p.expires_at) && equal$2(p.answer, {
		permission: "allow",
		dont_ask_again: true
	}) && Array.isArray(p.items) && p.items.length <= 50 && new Set(p.items.map((i) => i?.item_id)).size === p.items.length && p.items.every((i) => object$1(i) && /^bapi_[0-9a-f]{24}$/.test(i.item_id) && i.host === p.host && typeof i.session_id === "string" && typeof i.eligible === "boolean" && (!i.eligible || object$1(i.prompt) && typeof i.prompt.toolUseId === "string" && Array.isArray(i.allowed_modes) && i.allowed_modes.includes(null) && i.allowed_modes.every(mode)));
}
function validRequest$1(r) {
	return r?.action === "session.approve_pending" && typeof r.target?.host === "string" && Object.keys(r.target).length === 1 && typeof r.params?.preview_token === "string" && Object.keys(r.params).length === 2 && Array.isArray(r.params.selection) && r.params.selection.length > 0 && r.params.selection.length <= 50 && r.params.selection.every((s) => object$1(s) && Object.keys(s).length === 2 && /^bapi_[0-9a-f]{24}$/.test(s.item_id) && mode(s.mode)) && new Set(r.params.selection.map((s) => s.item_id)).size === r.params.selection.length && object$1(r.preconditions) && Object.keys(r.preconditions).length === 1 && /^[0-9a-f]{64}$/.test(r.preconditions.expected_fingerprint);
}
function approvalsPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = {
		host: typeof raw?.host === "string" ? raw.host : "",
		workspace: typeof raw?.workspace === "string" ? raw.workspace : ""
	};
	if (validPreview$1(raw?.preview) && raw.preview.host === saved.host && (raw.preview.workspace || "") === saved.workspace) saved.preview = raw.preview;
	if (raw?.intent) saved.intent = {
		request: validRequest$1(raw.intent.request) ? raw.intent.request : null,
		key: typeof raw.intent.key === "string" && raw.intent.key.length > 0 && raw.intent.key.length <= 200 ? raw.intent.key : null,
		operation_id: opId(raw.intent.operation_id) ? raw.intent.operation_id : null,
		refused: refusedBeforeAdmission.has(raw.intent.refused) && !raw.intent.operation_id ? raw.intent.refused : null
	};
	let operation = null, busy = false, submission = null, refreshing = null, readFailed = false;
	const selected = new Map(), controls = [];
	if (saved.preview && !saved.intent && Array.isArray(raw?.selection)) {
		for (const s of raw.selection) if (object$1(s) && saved.preview.items.some((i) => i.eligible && i.item_id === s.item_id && i.allowed_modes.includes(s.mode))) selected.set(s.item_id, s.mode);
	}
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = (required = false) => {
		guard();
		saved.selection = [...selected].map(([item_id, mode]) => ({
			item_id,
			mode
		}));
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch (error) {
			if (required) throw error;
		}
	};
	const observable = () => ready() && caps()?.scopes?.includes("observe");
	const writable = () => observable() && caps()?.scopes?.includes("operate") && caps()?.actions?.some((a) => a.action === "session.approve_pending" && a.allowed === true) && caps()?.hosts?.some((host) => host.host === (saved.intent?.request?.target.host || saved.host) && host.writes === true);
	const host = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("bulk_choose_host")), ...(caps()?.hosts || []).map((x) => h("option", { value: x.host }, x.host)));
	host.value = saved.host;
	const workspace = h("input", {
		"aria-label": t("bulk_workspace"),
		placeholder: t("bulk_workspace"),
		value: saved.workspace
	});
	const rows = h("div", { "data-approval-items": "" }), result = h("div", { "data-approval-result": "" }), status = h("div", { role: "status" });
	const summary = h("p", { class: "muted" });
	const previewButton = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || saved.intent || !observable() || !host.value) return;
			saved.host = host.value;
			saved.workspace = workspace.value.trim();
			workspace.value = saved.workspace;
			delete saved.preview;
			selected.clear();
			busy = true;
			persist();
			renderPreview();
			update();
			try {
				const p = await api("POST", "/approval-previews", {
					host: saved.host,
					...saved.workspace ? { workspace: saved.workspace } : {}
				});
				guard();
				if (!validPreview$1(p) || p.host !== saved.host || (p.workspace || "") !== saved.workspace) throw new Error(t("bulk_invalid_preview"));
				saved.preview = p;
				persist();
				status.replaceChildren();
				renderPreview();
			} catch (e) {
				if (current()) status.replaceChildren(errorBox(e));
			} finally {
				busy = false;
				if (current()) update();
			}
		}
	}, t("bulk_preview"));
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !opId(candidate?.operation_id) || !intent.request || !intent.key || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$2({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && candidate.operation_id !== intent.operation_id) throw new Error(t("bulk_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	};
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !writable() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (!saved.preview || saved.preview.expires_at * 1e3 <= Date.now() || !selected.size) {
					update();
					return;
				}
				const selection = saved.preview.items.filter((i) => selected.has(i.item_id)).map((i) => ({
					item_id: i.item_id,
					mode: selected.get(i.item_id)
				}));
				saved.intent = {
					key: crypto.randomUUID(),
					operation_id: null,
					request: {
						action: "session.approve_pending",
						target: { host: saved.preview.host },
						params: {
							preview_token: saved.preview.preview_token,
							selection
						},
						preconditions: { expected_fingerprint: saved.preview.fingerprint }
					}
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist(true);
			} catch (error) {
				status.replaceChildren(errorBox(error));
				update();
				return;
			}
			busy = true;
			const intent = saved.intent;
			update();
			submission = (async () => {
				try {
					const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(data.operation);
				} catch (e) {
					if (current()) {
						if (e.status >= 400 && e.status < 500 && refusedBeforeAdmission.has(e.code)) {
							intent.refused = e.code;
							persist();
						}
						status.replaceChildren(errorBox(e));
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("bulk_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("bulk_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$2(operation) || saved.intent?.refused)) return;
			delete saved.intent;
			delete saved.preview;
			selected.clear();
			operation = null;
			persist();
			status.replaceChildren();
			renderPreview();
			update();
		}
	}, t("bulk_new"));
	const box = h("section", { "data-approvals": "" }, h("div", { class: "panel" }, h("div", { class: "filters" }, host, workspace, previewButton), h("p", { class: "muted" }, t("bulk_scope"))), rows, h("div", { class: "panel" }, h("p", { class: "note" }, t("bulk_effect")), summary, h("div", { class: "actions" }, apply, check, another), result, status));
	host.onchange = workspace.oninput = () => {
		if (!current() || busy || saved.intent) return;
		saved.host = host.value;
		saved.workspace = workspace.value;
		delete saved.preview;
		selected.clear();
		persist();
		renderPreview();
		update();
	};
	function renderPreview() {
		controls.length = 0;
		rows.replaceChildren();
		if (!saved.preview) return;
		if (saved.preview.truncated) rows.append(h("p", { class: "note" }, t("bulk_truncated")));
		if (!saved.preview.items.length) rows.append(h("p", { class: "panel" }, t("bulk_empty")));
		for (const item of saved.preview.items) {
			const choice = h("input", {
				type: "checkbox",
				"aria-label": t("bulk_select", { id: item.session_id })
			});
			const requestMode = saved.intent?.request?.params.selection.find((s) => s.item_id === item.item_id);
			choice.checked = Boolean(requestMode) || selected.has(item.item_id);
			const select = h("select", { "aria-label": t("bulk_mode", { id: item.session_id }) }, ...(item.allowed_modes || [null]).map((value) => h("option", { value: value || "" }, t(value === null ? "bulk_no_mode" : "permissions_" + value))));
			select.value = requestMode?.mode || selected.get(item.item_id) || "";
			choice.onchange = () => {
				if (!current() || saved.intent || busy) return;
				if (choice.checked) selected.set(item.item_id, select.value || null);
				else selected.delete(item.item_id);
				persist();
				update();
			};
			select.onchange = () => {
				if (!current() || saved.intent || busy) return;
				if (selected.has(item.item_id)) selected.set(item.item_id, select.value || null);
				persist();
				update();
			};
			const warning = h("p", { class: "muted" });
			controls.push({
				item,
				choice,
				select,
				warning
			});
			rows.append(h("article", {
				class: "panel bulk-item",
				"data-approval-item": item.item_id
			}, h("div", { class: "row" }, choice, h("div", { class: "grow" }, h("a", {
				class: "title",
				href: `#/session/${encodeURIComponent(item.host)}/${encodeURIComponent(item.session_id)}`
			}, item.session_id), h("div", { class: "muted" }, [item.host, item.agent_kind].filter(Boolean).join(" · ")))), item.eligible ? [
				h("p", { class: "title" }, item.prompt.toolName || t("bulk_answer")),
				h("pre", { class: "pre bulk-prompt" }, typeof item.prompt.input === "string" ? item.prompt.input : Object.keys(item.prompt.input || {}).length === 1 && typeof item.prompt.input?.command === "string" ? item.prompt.input.command : JSON.stringify(item.prompt.input ?? item.prompt, null, 2)),
				h("details", { class: "bulk-evidence" }, h("summary", {}, t("bulk_full_prompt")), h("pre", { class: "pre bulk-prompt" }, JSON.stringify(item.prompt, null, 2))),
				select,
				warning
			] : h("p", { class: "muted" }, t("bulk_blocked"), " · ", item.code || t("obs_unknown"))));
		}
	}
	function update() {
		const fixed = Boolean(saved.intent), expired = saved.preview && saved.preview.expires_at * 1e3 <= Date.now();
		host.disabled = workspace.disabled = busy || fixed;
		previewButton.disabled = busy || fixed || !observable() || !host.value;
		for (const c of controls) {
			c.choice.disabled = busy || fixed || !c.item.eligible || !writable() || expired;
			c.select.disabled = c.choice.disabled || !c.choice.checked;
			c.warning.textContent = c.select.value === "allow_all" ? t("permissions_allow_help") : "";
		}
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "bulk_apply");
		apply.disabled = busy || readFailed || !writable() || (fixed ? !saved.intent.request || !saved.intent.key : !selected.size || expired);
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$2(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed;
		summary.textContent = fixed ? t(saved.intent.refused ? "bulk_refused" : "bulk_fixed") : expired ? t("bulk_expired") : t("bulk_selected", { count: selected.size });
		result.replaceChildren();
		if (!fixed) return;
		result.append(h("p", {}, operation ? opStatus(operation) : t("permissions_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null));
		if (!saved.intent.request || !saved.intent.key) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		if (!operation) return;
		const items = operation.result?.items || operation.external_refs?.bulk_items || [];
		result.append(h("p", { class: "muted" }, t(operation.result?.all_succeeded === true ? "bulk_all_proven" : "bulk_partial")));
		for (const item of items) result.append(h("div", { class: "row bulk-receipt" }, h("div", { class: "grow" }, item.session_id, h("div", { class: "muted" }, t(item.complete === true ? "bulk_item_complete" : "bulk_item_incomplete"))), ...["answer", "permissions"].filter((phase) => item[phase]).map((phase) => h("span", {}, t("bulk_" + phase), ": ", opId(item[phase].operation_id) ? h("a", { href: `#/op/${item[phase].operation_id}` }, item[phase].status || t("obs_unknown")) : item[phase].status || t("obs_unknown"), item[phase].code ? ` · ${item[phase].code}` : ""))));
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) {
			update();
			return;
		}
		refreshing = (async () => {
			const data = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(data.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			if (current()) {
				readFailed = true;
				status.replaceChildren(errorBox(e));
				update();
			}
			throw e;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	renderPreview();
	update();
	return {
		box,
		update,
		refresh
	};
}
//#endregion
//#region src/session-start.js
var object = (v) => v && typeof v === "object" && !Array.isArray(v);
var operationId = (v) => typeof v === "string" && /^op_[0-9a-f]{32}$/.test(v);
var terminal$1 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var equal$1 = (a, b) => a === b || object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$1(a[k], b[k]));
var text = (v, max) => typeof v === "string" && v.trim().length > 0 && v.length <= max;
var fields = [
	"host",
	"workspace",
	"agent",
	"model",
	"title",
	"prompt"
];
var admissionRefusals = new Set(["TIER_DISABLED", "START_WORKTREE_REQUIRED"]);
function validRequest(r) {
	return r?.action === "session.start" && object(r.target) && Object.keys(r.target).length === 2 && text(r.target.host, 256) && text(r.target.workspace, 256) && object(r.params) && Object.keys(r.params).every((k) => [
		"agent",
		"model",
		"title",
		"prompt",
		"use_worktree"
	].includes(k)) && ["claude", "codex"].includes(r.params.agent) && r.params.use_worktree === true && [
		"model",
		"title",
		"prompt"
	].every((k) => !(k in r.params) || text(r.params[k], k === "prompt" ? 2e4 : 256)) && object(r.preconditions) && Object.keys(r.preconditions).length === 0;
}
function sessionStartPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = Object.fromEntries(fields.map((k) => [k, typeof raw?.[k] === "string" ? raw[k] : k === "agent" ? "claude" : ""]));
	if (!["claude", "codex"].includes(saved.agent)) saved.agent = "claude";
	if (raw?.intent) {
		const valid = validRequest(raw.intent.request) && text(raw.intent.key, 200);
		saved.intent = {
			request: valid ? raw.intent.request : null,
			key: valid ? raw.intent.key : null,
			operation_id: operationId(raw.intent.operation_id) ? raw.intent.operation_id : null,
			refused: !raw.intent.operation_id && admissionRefusals.has(raw.intent.refused) ? raw.intent.refused : null
		};
		if (valid) Object.assign(saved, raw.intent.request.target, {
			model: "",
			title: "",
			prompt: ""
		}, raw.intent.request.params);
	}
	let operation = null, busy = false, submission = null, refreshing = null, readFailed = false;
	let workspaces = [], discovery = 0, discovering = false, discoveredHost = "";
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const observe = () => caps()?.scopes?.includes("observe");
	const allowed = () => observe() && caps()?.scopes?.includes("start") && caps()?.actions?.some((a) => a.action === "session.start" && a.allowed === true);
	const hostAllowed = () => caps()?.hosts?.some((x) => x.host === saved.host && x.writes === true && x.orchestrate === true);
	const status = h("div", { role: "status" }), result = h("div", { "data-start-result": "" }), discoveryStatus = h("p", {
		class: "muted",
		role: "status"
	});
	const host = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("start_choose_host")), ...(caps()?.hosts || []).map((x) => h("option", { value: x.host }, x.host)));
	if (saved.host && ![...host.options].some((o) => o.value === saved.host)) host.append(h("option", { value: saved.host }, saved.host));
	const workspace = h("select", { "aria-label": t("start_workspace") });
	const agent = h("select", { "aria-label": t("start_agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const model = h("input", {
		"aria-label": t("start_model"),
		maxlength: 256,
		placeholder: t("start_model_default")
	});
	const title = h("input", {
		"aria-label": t("start_title"),
		maxlength: 256
	});
	const prompt = h("textarea", {
		"aria-label": t("start_prompt"),
		maxlength: 2e4,
		rows: 6
	});
	const inputs = {
		host,
		workspace,
		agent,
		model,
		title,
		prompt
	};
	const fill = () => {
		for (const [k, el] of Object.entries(inputs)) el.value = saved[k];
	};
	const showError = (e) => {
		if (current()) status.replaceChildren(errorBox(e));
	};
	function renderWorkspaces() {
		workspace.replaceChildren(h("option", { value: "" }, t("start_choose_workspace")), ...workspaces.map((w) => h("option", { value: w.workspace_id }, `${w.name || w.workspace_id} · ${w.workspace_id}`)));
		if (saved.workspace && ![...workspace.options].some((o) => o.value === saved.workspace)) workspace.append(h("option", { value: saved.workspace }, saved.workspace));
		workspace.value = saved.workspace;
	}
	async function discover() {
		if (!current() || saved.intent || !observe() || !saved.host) return;
		const expected = ++discovery, selectedHost = saved.host;
		discovering = true;
		discoveredHost = "";
		workspaces = [];
		renderWorkspaces();
		update();
		discoveryStatus.textContent = t("start_loading_workspaces");
		try {
			const doc = await api("GET", `/workspaces?host=${encodeURIComponent(selectedHost)}&limit=200`);
			guard();
			if (expected !== discovery || saved.host !== selectedHost || saved.intent) return;
			if (!Array.isArray(doc.workspaces) || doc.workspaces.length > 200 || typeof doc.has_more !== "boolean" || !object(doc.errors) || Object.keys(doc.errors).length || doc.workspaces.some((w) => !object(w) || w.host !== selectedHost || !text(w.workspace_id, 256) || typeof w.folder !== "string") || new Set(doc.workspaces.map((w) => w.workspace_id)).size !== doc.workspaces.length) throw new Error(t("start_discovery_failed"));
			workspaces = doc.workspaces;
			discoveredHost = selectedHost;
			renderWorkspaces();
			discoveryStatus.textContent = t(doc.has_more ? "start_truncated" : !workspaces.length ? "start_no_workspaces" : "start_workspace_help");
		} catch (e) {
			if (current() && expected === discovery) {
				discoveryStatus.textContent = t("start_discovery_failed");
				showError(e);
			}
		} finally {
			if (expected === discovery && current()) {
				discovering = false;
				update();
			}
		}
	}
	const reload = h("button", {
		class: "secondary",
		onclick: discover
	}, t("start_reload_workspaces"));
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !intent.request || !intent.key || !operationId(candidate?.operation_id) || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$1({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && intent.operation_id !== candidate.operation_id) throw new Error(t("start_invalid_result"));
		for (const proof of [candidate.result, candidate.external_refs?.start_result]) if (proof?.started === true && (proof.host !== intent.request.target.host || !text(proof.session_id, 256) || proof.session_id !== candidate.external_refs?.session_id)) throw new Error(t("start_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	};
	function request() {
		const params = {
			agent: saved.agent,
			use_worktree: true
		};
		for (const key of [
			"model",
			"title",
			"prompt"
		]) if (saved[key] !== "") params[key] = saved[key];
		return {
			action: "session.start",
			target: {
				host: saved.host,
				workspace: saved.workspace
			},
			params,
			preconditions: {}
		};
	}
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !ready() || !allowed() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (!hostAllowed() || discoveredHost !== saved.host || !workspaces.some((w) => w.workspace_id === saved.workspace) || !validRequest(request())) return;
				saved.intent = {
					request: request(),
					key: crypto.randomUUID(),
					operation_id: null
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist();
			} catch (e) {
				showError(e);
				update();
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(data.operation);
				} catch (e) {
					if (current()) {
						if (e.status >= 400 && e.status < 500 && admissionRefusals.has(e.code)) {
							intent.refused = e.code;
							try {
								persist();
							} catch {}
						}
						showError(e);
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("start_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$1(operation) || saved.intent?.refused)) return;
			const previous = saved;
			saved = {
				host: saved.host,
				workspace: "",
				agent: "claude",
				model: "",
				title: "",
				prompt: ""
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				showError(e);
				return;
			}
			operation = null;
			status.replaceChildren();
			fill();
			renderWorkspaces();
			update();
			await discover();
		}
	}, t("start_new"));
	for (const [key, el] of Object.entries(inputs)) el.addEventListener(key === "host" || key === "workspace" || key === "agent" ? "change" : "input", () => {
		if (!current() || saved.intent || busy) {
			fill();
			return;
		}
		saved[key] = el.value;
		if (key === "host") {
			saved.workspace = "";
			discoveredHost = "";
			workspaces = [];
			discovery++;
			renderWorkspaces();
		}
		try {
			persist();
		} catch (e) {
			showError(e);
		}
		update();
		if (key === "host") discover();
	});
	const label = (name, control) => h("label", {}, t(name), control);
	const box = h("section", {
		class: "session-start",
		"data-session-start": ""
	}, h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("host", host), label("start_workspace", workspace)), h("div", { class: "actions" }, reload), discoveryStatus, h("p", { class: "muted" }, t("start_isolation"))), h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("start_agent", agent), label("start_model", model), label("start_title", title)), label("start_prompt", prompt), h("p", { class: "muted" }, t("start_prompt_help"))), h("div", { class: "actions" }, apply, check, another), result, status);
	function update() {
		const fixed = Boolean(saved.intent);
		for (const el of Object.values(inputs)) el.disabled = busy || fixed;
		workspace.disabled ||= discovering || !saved.host;
		reload.hidden = fixed;
		reload.disabled = discovering || !observe() || !saved.host;
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "start_apply");
		apply.disabled = busy || readFailed || !ready() || !allowed() || (fixed ? !saved.intent.request || !saved.intent.key : !hostAllowed() || discoveredHost !== saved.host || !workspaces.some((w) => w.workspace_id === saved.workspace) || !validRequest(request()));
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$1(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed;
		result.replaceChildren();
		if (!allowed()) result.append(h("p", { class: "muted" }, t("start_unavailable")));
		if (!fixed) return;
		result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "start_refused" : "start_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null, operation?.status_reason ? ` · ${operation.status_reason}` : ""));
		result.append(h("p", { class: "muted" }, t("start_fixed")));
		if (!saved.intent.request || !saved.intent.key) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		const proof = operation?.result?.started === true ? operation.result : operation?.external_refs?.start_result;
		if (proof?.started === true) {
			result.append(h("p", {}, t("start_started"), " ", h("a", { href: `#/session/${encodeURIComponent(proof.host)}/${encodeURIComponent(proof.session_id)}` }, proof.session_id)));
			const sent = operation?.result?.prompt_sent;
			result.append(h("p", { class: "muted" }, t(!saved.intent.request?.params.prompt ? "start_without_prompt" : sent === true ? "start_prompt_accepted" : "start_prompt_unknown")));
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) {
			update();
			return;
		}
		refreshing = (async () => {
			const doc = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(doc.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			if (current()) {
				readFailed = true;
				showError(e);
				update();
			}
			throw e;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	renderWorkspaces();
	fill();
	update();
	return {
		box,
		update,
		refresh,
		init: async () => {
			if (saved.intent) await refresh();
			else await discover();
		}
	};
}
//#endregion
//#region src/artifact-review.js
var record = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
var ordered = (value) => record(value) ? Object.fromEntries(Object.keys(value).sort().map((k) => [k, ordered(value[k])])) : Array.isArray(value) ? value.map(ordered) : value;
var stable = (value) => JSON.stringify(ordered(value));
var equal = (a, b) => stable(a ?? null) === stable(b ?? null);
var digest = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
var oid = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var aid = (value) => typeof value === "string" && /^art_[0-9a-f]{32}$/.test(value);
var tid = (value) => typeof value === "string" && /^[0-9a-f-]{8,64}$/.test(value);
var commandId = (value) => typeof value === "string" && value.length > 0 && value.length <= 256 && !/[\x00-\x1f\x7f-\x9f]/.test(value);
var terminal = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var executions = [
	"checkpoint.continue",
	"integration.handoff",
	"session.send",
	"session.start"
];
var managedCaptureExecution = (op) => oid(op?.operation_id) && op.status === "succeeded" && executions.includes(op.action) && (op.action !== "session.start" || op.result?.started === true && op.result.prompt_sent === true && op.result.message_id === `batc-${op.operation_id}`);
var safePath = (path) => typeof path === "string" && path && new TextEncoder().encode(path).length <= 4096 && !/[\\\x00-\x1f\x7f-\x9f]/.test(path) && path.split("/").every((p) => p && p !== "." && p !== ".." && p.toLowerCase() !== ".git");
var selectorValid = (s) => record(s) && (equal(Object.keys(s).sort(), ["execution_operation_id"]) && oid(s.execution_operation_id) || equal(Object.keys(s).sort(), ["command_id", "task_id"]) && tid(s.task_id) && commandId(s.command_id));
var validRef = (ref) => aid(ref?.artifact_id) && Number.isSafeInteger(ref.revision) && ref.revision > 0 && ref.revision <= 999999999 && digest(ref.digest);
var refOf = (value) => ({
	artifact_id: value.artifact_id,
	revision: value.revision,
	digest: value.digest
});
var sourceFromOperation = (op) => op.action === "session.send" ? op.external_refs?.resolved_target || op.target : op.result;
function validPreview(doc, input) {
	return record(doc) && /^acpv_[0-9a-f]{32}$/.test(doc.preview_id) && typeof doc.preview_token === "string" && doc.preview_token.length > 0 && doc.preview_token.length <= 24576 && digest(doc.fingerprint) && doc.snapshot === false && Number.isFinite(doc.expires_at) && doc.source?.provenance === "connector_managed" && doc.source.host === input.host && doc.source.session_id === input.session_id && equal(doc.source.selector, input.selector) && doc.relative_path === input.relative_path && typeof doc.source.root === "string" && typeof doc.source.repository_root === "string" && record(doc.source.lineage) && digest(doc.evidence?.digest) && /^[0-9a-f]{40}$/.test(doc.evidence.head_sha) && Number.isSafeInteger(doc.evidence.size_bytes) && doc.evidence.size_bytes >= 0;
}
function validArtifact(row, expected) {
	const proof = row?.source;
	return validRef(row) && row.state === "ready" && record(proof) && proof.kind === "managed_capture" && oid(proof.operation_id) && row.operation_id === proof.operation_id && digest(proof.fingerprint) && proof.source?.provenance === "connector_managed" && record(proof.source.lineage) && selectorValid(proof.source.selector) && safePath(proof.relative_path) && proof.evidence?.digest === row.digest && proof.evidence.size_bytes === row.size_bytes && /^[0-9a-f]{40}$/.test(proof.evidence.head_sha) && (!expected || equal(refOf(row), expected));
}
function restore(raw) {
	const saved = {
		relative_path: "",
		selector: null,
		reviewText: ""
	};
	if (!record(raw)) return saved;
	if (typeof raw.relative_path === "string") saved.relative_path = raw.relative_path;
	if (selectorValid(raw.selector)) saved.selector = raw.selector;
	if (typeof raw.reviewText === "string") saved.reviewText = raw.reviewText;
	if (record(raw.preview)) saved.preview = raw.preview;
	for (const kind of ["capture", "accept"]) if (raw[kind]) {
		const intent = raw[kind];
		const usable = record(intent.request) && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200 && typeof intent.actor === "string" && record(intent.request.target) && record(intent.request.params) && record(intent.request.preconditions) && intent.request.action === (kind === "capture" ? "artifact.capture.managed" : "artifact.accept");
		saved[kind] = {
			request: usable ? intent.request : null,
			key: usable ? intent.key : null,
			actor: intent.actor,
			operation_id: oid(intent.operation_id) ? intent.operation_id : null,
			expected: intent.expected,
			refused: usable && [
				"PREVIEW_EXPIRED",
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_MISMATCH",
				"INVALID_PARAMS",
				"ARTIFACT_REVISION_MISMATCH",
				"ARTIFACT_LINEAGE_UNPROVEN"
			].includes(intent.refused) ? intent.refused : null
		};
	}
	return saved;
}
async function mountArtifactReview({ main, h, t, api, caps, guard, onEvents, errorBox, opStatus, storageKey, context }) {
	const container = h("div", { class: "artifact-review" });
	main.append(container);
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = restore(raw), source = null, artifact = null, busy = false, readFailed = false, disposed = false;
	let refreshing = null, submission = null, revision = 0, catalogCursor = null;
	const operations = {
		capture: null,
		accept: null
	}, candidates = new Map(), pages = new Map();
	const notice = h("div", { role: "status" }), sourceBox = h("div"), evidence = h("div"), outcome = h("div");
	const catalog = h("div"), reviewFacts = h("div"), catalogNotice = h("div");
	const path = h("input", {
		"aria-label": t("capture_path"),
		value: saved.relative_path,
		placeholder: "results/report.md"
	});
	const choice = h("select", { "aria-label": t("ar_execution") }, h("option", { value: "" }, t("ar_choose_execution")));
	const customType = h("select", { "aria-label": t("ar_evidence_kind") }, h("option", { value: "operation" }, t("ar_operation")), h("option", { value: "command" }, t("ar_command")));
	const customTask = h("input", {
		"aria-label": t("ar_task_id"),
		maxlength: 64
	});
	const customId = h("input", {
		"aria-label": t("ar_evidence_id"),
		maxlength: 256
	});
	const custom = h("div", {
		class: "capture-fields",
		hidden: true
	}, h("label", {}, t("ar_evidence_kind"), customType), h("label", {}, t("ar_task_id"), customTask), h("label", {}, t("ar_evidence_id"), customId));
	const receipt = h("textarea", {
		"aria-label": t("ar_receipt"),
		maxlength: 2e3,
		value: saved.reviewText
	});
	receipt.value = saved.reviewText;
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => update()
	});
	const currentView = () => {
		try {
			guard();
			return !disposed;
		} catch {
			return false;
		}
	};
	const persist = (required = false) => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
			return true;
		} catch {
			if (required) throw new Error(t("ar_storage"));
			return false;
		}
	};
	const showError = (error) => {
		if (currentView()) notice.replaceChildren(errorBox(error));
	};
	const supported = () => caps()?.artifacts?.capture?.managed_single_file === true;
	const scope = (name) => caps()?.scopes?.includes(name);
	const allowed = (name) => caps()?.actions?.some((a) => a.action === name && a.allowed === true);
	const mayCapture = () => supported() && scope("observe") && scope("manage") && allowed("artifact.capture.managed");
	const mayAccept = () => scope("observe") && scope("approve") && allowed("artifact.accept");
	const active = (kind) => saved[kind] && !saved[kind].refused && (!terminal(operations[kind]) || kind === "capture" && operations.capture?.status === "succeeded" && !artifact);
	const frozen = () => Boolean(saved.capture || saved.accept);
	const input = () => ({
		host: source?.host,
		session_id: source?.session_id,
		relative_path: path.value,
		selector: saved.selector
	});
	const facts = (rows) => h("dl", { class: "kv" }, ...rows.flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, h("code", {}, value ?? ""))]));
	const proofFacts = (proof) => facts([
		[t("capture_source"), `${proof.source.host} / ${proof.source.session_id}`],
		[t("capture_path"), proof.relative_path],
		[t("capture_root"), proof.source.root],
		["HEAD", proof.evidence.head_sha],
		[t("capture_bytes"), String(proof.evidence.size_bytes)],
		["SHA-256", proof.evidence.digest]
	]);
	function renderChoice() {
		choice.replaceChildren(h("option", { value: "" }, t("ar_choose_execution")), ...[...candidates].map(([key, entry]) => h("option", { value: key }, entry.label)), h("option", { value: "custom" }, t("ar_exact_evidence")));
		if (saved.selector) {
			const key = stable(saved.selector);
			if (frozen() && !candidates.has(key)) choice.append(h("option", { value: key }, saved.selector.execution_operation_id ? `${t("ar_operation")} · ${saved.selector.execution_operation_id}` : `${t("ar_command")} · ${saved.selector.task_id} · ${saved.selector.command_id}`));
			if (candidates.has(key) || frozen()) choice.value = key;
			else {
				choice.value = "custom";
				customType.value = saved.selector.task_id ? "command" : "operation";
				customTask.value = saved.selector.task_id || context.task_id || "";
				customId.value = saved.selector.command_id || saved.selector.execution_operation_id;
			}
		}
		custom.hidden = choice.value !== "custom";
		customTask.disabled = customType.value !== "command" || frozen() || busy;
	}
	function changed() {
		if (!currentView() || frozen()) return;
		revision++;
		saved.relative_path = path.value;
		saved.preview = null;
		reviewed.checked = false;
		saved.selector = choice.value === "custom" ? customType.value === "command" ? {
			task_id: customTask.value.trim(),
			command_id: customId.value.trim()
		} : { execution_operation_id: customId.value.trim() } : candidates.get(choice.value)?.selector || null;
		custom.hidden = choice.value !== "custom";
		persist();
		render();
	}
	for (const field of [
		path,
		choice,
		customType,
		customTask,
		customId
	]) field.addEventListener("input", changed);
	receipt.addEventListener("input", () => {
		if (!currentView() || saved.accept) return;
		saved.reviewText = receipt.value;
		persist();
		update();
	});
	async function captureArtifact(op) {
		const intent = saved.capture, ref = op.result;
		if (!validRef(ref) || ref.digest !== intent.expected?.digest) throw new Error(t("ar_invalid_result"));
		const { artifact: row } = await api("GET", `/artifacts/${ref.artifact_id}/revisions/${ref.revision}`);
		guard();
		const proof = row?.source;
		if (!validArtifact(row, refOf(ref)) || proof.operation_id !== op.operation_id || proof.fingerprint !== intent.request.preconditions.expected_fingerprint || !equal(proof.source, intent.expected.source) || !equal(proof.evidence, intent.expected.evidence) || proof.relative_path !== intent.expected.relative_path) throw new Error(t("ar_invalid_result"));
		artifact = row;
	}
	async function adopt(kind, op) {
		guard();
		const intent = saved[kind];
		if (!intent?.request || !oid(op?.operation_id) || op.actor !== intent.actor || op.actor !== caps().actor || op.idempotency_key !== intent.key || op.action !== intent.request.action || !equal(op.target, intent.request.target) || !equal(op.params, intent.request.params) || !equal(op.preconditions, intent.request.preconditions) || intent.operation_id && intent.operation_id !== op.operation_id) throw new Error(t("ar_invalid_result"));
		intent.operation_id = op.operation_id;
		persist();
		if (kind === "capture" && op.status === "succeeded") await captureArtifact(op);
		if (kind === "accept" && op.status === "succeeded") {
			const result = op.result, request = intent.request;
			if (!result || result.operation_id !== op.operation_id || result.actor !== intent.actor || result.meaning !== "artifact_revision_review" || !equal(refOf(result), {
				...request.target,
				digest: request.params.digest
			}) || result.source_fingerprint !== request.params.source_fingerprint || result.receipt !== request.params.receipt || result.capture_operation_id !== intent.expected?.capture_operation_id || result.source_commit !== intent.expected?.source_commit || !equal(result.lineage, intent.expected?.lineage)) throw new Error(t("ar_invalid_result"));
		}
		operations[kind] = op;
		readFailed = false;
		render();
	}
	async function submit(kind) {
		if (busy || refreshing || readFailed || !saved[kind]?.request) return;
		guard();
		busy = true;
		update();
		let finish;
		submission = new Promise((resolve) => {
			finish = resolve;
		});
		try {
			persist(true);
			const intent = saved[kind];
			const result = intent.operation_id ? await api("GET", `/operations/${intent.operation_id}`) : await api("POST", "/operations?wait=3", intent.request, intent.key);
			guard();
			await adopt(kind, result.operation);
			notice.replaceChildren();
		} catch (error) {
			if (!currentView()) return;
			const safe = kind === "capture" ? [
				"PREVIEW_EXPIRED",
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_MISMATCH",
				"INVALID_PARAMS"
			] : [
				"INVALID_PARAMS",
				"ARTIFACT_REVISION_MISMATCH",
				"ARTIFACT_LINEAGE_UNPROVEN"
			];
			if (!saved[kind].operation_id && error.status >= 400 && error.status < 500 && safe.includes(error.code)) saved[kind].refused = error.code;
			persist();
			showError(error);
			if (kind === "capture" && error.status === 403) notice.append(h("p", { class: "muted" }, t("ar_original_credential")));
		} finally {
			busy = false;
			finish();
			submission = null;
			if (currentView()) render();
		}
	}
	const preview = h("button", {
		class: "secondary",
		onclick: async () => {
			if (busy || frozen() || !source || !scope("observe") || !supported() || !safePath(path.value) || !selectorValid(saved.selector)) return;
			guard();
			const ticket = ++revision, fixed = structuredClone(input());
			busy = true;
			saved.preview = null;
			reviewed.checked = false;
			update();
			try {
				const { selector, ...fields } = fixed;
				const { preview: doc } = await api("POST", "/artifact-managed-capture-previews", {
					...fields,
					...selector
				});
				guard();
				if (ticket !== revision) return;
				if (!validPreview(doc, fixed)) throw new Error(t("capture_invalid_preview"));
				saved.preview = doc;
				readFailed = false;
				persist();
				notice.replaceChildren();
			} catch (error) {
				if (ticket === revision) showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("capture_preview"));
	const capture = h("button", {
		class: "primary",
		onclick: () => {
			if (busy || refreshing || readFailed || !mayCapture() || saved.capture?.operation_id || saved.capture?.refused) return;
			guard();
			if (!saved.capture) {
				const doc = saved.preview;
				if (!doc || !reviewed.checked || doc.expires_at * 1e3 <= Date.now() || !validPreview(doc, input())) return;
				saved.capture = {
					key: crypto.randomUUID(),
					actor: caps().actor,
					request: {
						action: "artifact.capture.managed",
						target: { preview_id: doc.preview_id },
						params: { preview_token: doc.preview_token },
						preconditions: { expected_fingerprint: doc.fingerprint }
					},
					expected: {
						digest: doc.evidence.digest,
						evidence: doc.evidence,
						source: doc.source,
						relative_path: doc.relative_path
					}
				};
			}
			submit("capture");
		}
	}, t("capture_save"));
	const accept = h("button", {
		class: "primary",
		onclick: () => {
			if (busy || refreshing || readFailed || !artifact || !mayAccept() || saved.accept?.operation_id || saved.accept?.refused || !receipt.value.trim() || [...receipt.value].length > 2e3) return;
			guard();
			if (!saved.accept) saved.accept = {
				key: crypto.randomUUID(),
				actor: caps().actor,
				request: {
					action: "artifact.accept",
					target: {
						artifact_id: artifact.artifact_id,
						revision: artifact.revision
					},
					params: {
						digest: artifact.digest,
						source_fingerprint: artifact.source.fingerprint,
						receipt: receipt.value
					},
					preconditions: {}
				},
				expected: {
					capture_operation_id: artifact.source.operation_id,
					source_commit: artifact.source.evidence.head_sha,
					lineage: artifact.source.source.lineage
				}
			};
			submit("accept");
		}
	}, t("ar_accept"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(showError)
	}, t("ar_check"));
	const reload = h("button", {
		class: "secondary",
		onclick: async () => {
			if (busy || refreshing || frozen()) return;
			busy = true;
			update();
			try {
				await loadSource();
				guard();
				readFailed = false;
				notice.replaceChildren();
			} catch (error) {
				showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("ar_refresh_sources"));
	const reset = h("button", {
		class: "secondary",
		onclick: async () => {
			guard();
			if (busy || refreshing || readFailed || active("capture") || active("accept")) return;
			saved = {
				relative_path: path.value,
				selector: null,
				reviewText: ""
			};
			artifact = source = null;
			candidates.clear();
			pages.clear();
			operations.capture = operations.accept = null;
			reviewed.checked = false;
			receipt.value = "";
			revision++;
			persist();
			notice.replaceChildren();
			renderChoice();
			busy = true;
			render();
			try {
				await loadSource();
			} catch (error) {
				showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("capture_new"));
	const newReview = h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (busy || refreshing || readFailed || active("accept")) return;
			saved.accept = null;
			operations.accept = null;
			persist();
			render();
		}
	}, t("ar_new_review"));
	const moreExecutions = h("button", {
		class: "secondary",
		onclick: () => loadExecutions(true).catch(showError)
	}, t("ar_more_executions"));
	const reviewPanel = h("section", {
		class: "panel",
		"data-artifact-accept": ""
	}, h("h2", {}, t("ar_review_title")), reviewFacts, h("p", { class: "muted" }, t("ar_accept_help")), h("label", {}, t("ar_receipt"), receipt), h("p", { class: "muted" }, t("ar_approve_scope")), h("div", { class: "actions" }, accept, newReview));
	const capturePanel = h("section", {
		class: "panel",
		"data-managed-capture": ""
	}, h("h2", {}, t("ar_capture_title")), sourceBox, h("div", { class: "capture-fields" }, h("label", {}, t("ar_execution"), choice), h("label", {}, t("capture_path"), path)), custom, h("div", { class: "actions" }, reload, moreExecutions, preview), evidence, h("label", { class: "capture-choice" }, reviewed, t("capture_review")), h("div", { class: "actions" }, capture, reset));
	const moreArtifacts = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => loadCatalog(true).catch((e) => catalogNotice.replaceChildren(errorBox(e)))
	}, t("more"));
	const catalogPanel = h("section", { class: "panel" }, h("h2", {}, t("ar_catalog")), catalog, catalogNotice, h("div", { class: "actions" }, moreArtifacts));
	container.append(h("h1", {}, t("ar_title")), h("p", { class: "muted" }, t("ar_help")), capturePanel, reviewPanel, h("div", { class: "actions" }, check), outcome, notice, catalogPanel);
	function update() {
		const fixed = busy || frozen();
		for (const field of [
			path,
			choice,
			customType,
			customId
		]) field.disabled = fixed;
		customTask.disabled = fixed || customType.value !== "command";
		preview.disabled = busy || frozen() || !source || !scope("observe") || !supported() || !safePath(path.value) || !selectorValid(saved.selector);
		reviewed.disabled = busy || Boolean(saved.capture) || !saved.preview || saved.preview.expires_at * 1e3 <= Date.now();
		reviewed.closest("label").hidden = Boolean(saved.capture) || !saved.preview;
		capture.hidden = Boolean(saved.capture?.operation_id || saved.capture?.refused);
		capture.textContent = saved.capture ? t("capture_check") : t("capture_save");
		capture.disabled = busy || Boolean(refreshing) || readFailed || !mayCapture() || !source || Boolean(saved.capture && !saved.capture.request) || !saved.capture && (!saved.preview || !reviewed.checked || saved.preview.expires_at * 1e3 <= Date.now());
		receipt.disabled = busy || Boolean(saved.accept) || !artifact;
		accept.hidden = Boolean(saved.accept?.operation_id || saved.accept?.refused);
		accept.textContent = saved.accept ? t("ar_check_accept") : t("ar_accept");
		accept.disabled = busy || Boolean(refreshing) || readFailed || !artifact || !mayAccept() || !receipt.value.trim() || [...receipt.value].length > 2e3 || Boolean(saved.accept && !saved.accept.request);
		check.hidden = !saved.capture?.operation_id && !saved.accept?.operation_id && context.kind !== "artifact";
		check.disabled = busy || Boolean(refreshing);
		reset.hidden = !saved.capture;
		reset.disabled = busy || Boolean(refreshing) || readFailed || Boolean(active("capture") || active("accept"));
		newReview.hidden = !saved.accept;
		newReview.disabled = busy || Boolean(refreshing) || readFailed || Boolean(active("accept"));
		moreExecutions.disabled = busy || frozen();
		reload.disabled = busy || frozen();
		moreExecutions.hidden = ![...pages.values()].some((value) => value !== null);
	}
	function render() {
		if (!currentView()) return;
		capturePanel.hidden = ![
			"session",
			"task",
			"operation"
		].includes(context.kind);
		evidence.replaceChildren();
		if (!mayCapture()) evidence.append(h("p", { class: "muted" }, t("capture_scope_manage")));
		if (saved.preview && validPreview(saved.preview, input())) {
			const description = [proofFacts(saved.preview), h("p", { class: "muted" }, saved.capture ? t("capture_fixed") : saved.preview.expires_at * 1e3 <= Date.now() ? t("capture_expired") : t("capture_single_file"))];
			evidence.append(...artifact ? [h("details", {}, h("summary", {}, t("ar_original_preview")), ...description)] : description);
		}
		reviewPanel.hidden = !artifact && context.kind !== "artifact" && !saved.accept;
		reviewFacts.replaceChildren();
		if (artifact) reviewFacts.append(facts([[t("ar_revision"), `${artifact.artifact_id} · r${artifact.revision}`]]), proofFacts(artifact.source), h("details", {}, h("summary", {}, t("ar_lineage")), h("pre", { class: "pre" }, JSON.stringify(artifact.source.source.lineage, null, 2))));
		outcome.replaceChildren();
		for (const kind of ["capture", "accept"]) if (saved[kind]) {
			const intent = saved[kind], op = operations[kind];
			outcome.append(h("p", {}, t(kind === "capture" ? "ar_capture_title" : "ar_review_title"), ": ", op ? opStatus(op) : t("capture_unknown"), " ", intent.operation_id ? h("a", { href: `#/op/${intent.operation_id}` }, intent.operation_id) : null));
			if (intent.refused) outcome.append(h("p", { class: "muted" }, intent.refused));
		}
		if (artifact) outcome.append(h("p", { "data-artifact-ready": "" }, t("capture_saved"), " ", `${artifact.artifact_id} · r${artifact.revision}`));
		if (operations.accept?.status === "succeeded") outcome.append(h("p", { "data-artifact-accepted": "" }, t("ar_recorded")));
		update();
	}
	async function loadExecutions(more = false) {
		if (!source || frozen()) return;
		const results = await Promise.all(executions.map(async (action) => {
			if (more && pages.get(action) === null) return;
			const before = more ? pages.get(action) : null;
			return {
				action,
				data: await api("GET", `/operations?status=succeeded&action=${action}&limit=50${before ? `&before=${before}` : ""}`)
			};
		}));
		guard();
		if (frozen()) return;
		for (const result of results.filter(Boolean)) {
			pages.set(result.action, result.data.next_before ?? null);
			for (const op of result.data.operations || []) {
				const bound = sourceFromOperation(op);
				if (managedCaptureExecution(op) && bound?.host === source.host && bound.session_id === source.session_id) {
					const selector = { execution_operation_id: op.operation_id };
					candidates.set(stable(selector), {
						selector,
						label: `${op.action} · ${op.operation_id}`
					});
				}
			}
		}
		renderChoice();
		update();
	}
	async function loadSource() {
		let task, data, bound;
		if (context.kind === "task") {
			task = (await api("GET", `/tasks/${encodeURIComponent(context.task_id)}`)).task;
			if (task?.task_id !== context.task_id) throw new Error(t("ar_source_unavailable"));
			bound = {
				host: task.host,
				session_id: task.session_id
			};
			customTask.value = task.task_id;
		} else if (context.kind === "operation") {
			const op = (await api("GET", `/operations/${context.operation_id}`)).operation;
			if (op?.operation_id !== context.operation_id || !managedCaptureExecution(op)) throw new Error(t("ar_source_unavailable"));
			bound = sourceFromOperation(op);
			if (!saved.selector) saved.selector = { execution_operation_id: context.operation_id };
		} else if (context.kind === "session") bound = context;
		else return;
		guard();
		if (!bound?.host || !bound?.session_id) throw new Error(t("ar_source_unavailable"));
		data = await api("GET", `/sessions/${encodeURIComponent(bound.host)}/${encodeURIComponent(bound.session_id)}`);
		guard();
		const row = data.session;
		if (row?.host !== bound.host || row.session_id !== bound.session_id || row.provenance !== "connector_managed" || row.api_access !== "managed") throw new Error(t("ar_source_unavailable"));
		source = {
			host: row.host,
			session_id: row.session_id
		};
		sourceBox.replaceChildren(facts([[t("capture_source"), `${row.host} / ${row.session_id}`]]));
		if (!saved.capture) {
			const taskIds = task ? [task.task_id] : [...new Set((data.relations_summary || []).filter((r) => r.status !== "closed").map((r) => r.execution_id))].filter(tid);
			const tasks = task ? [task] : await Promise.all(taskIds.slice(0, 20).map(async (id) => (await api("GET", `/tasks/${id}`)).task));
			guard();
			for (const current of tasks) if (current?.host === source.host && current.session_id === source.session_id) {
				for (const cmd of current.commands || []) if (cmd.task_id === current.task_id && cmd.session_id === source.session_id && cmd.kind === "send" && ["accepted", "settled"].includes(cmd.status) && commandId(cmd.command_id)) {
					const selector = {
						task_id: current.task_id,
						command_id: cmd.command_id
					};
					candidates.set(stable(selector), {
						selector,
						label: `${t("ar_command")} · ${current.task_id} · ${cmd.command_id}`
					});
				}
			}
			await loadExecutions();
		}
		renderChoice();
		render();
	}
	async function loadExactArtifact() {
		const expected = context.kind === "artifact" ? {
			artifact_id: context.artifact_id,
			revision: context.revision
		} : null;
		if (!expected) return;
		if (!aid(expected.artifact_id) || !Number.isSafeInteger(expected.revision) || expected.revision < 1 || expected.revision > 999999999) throw new Error(t("ar_invalid_result"));
		const { artifact: row } = await api("GET", `/artifacts/${expected.artifact_id}/revisions/${expected.revision}`);
		guard();
		if (!validArtifact(row) || row.artifact_id !== expected.artifact_id || row.revision !== expected.revision) throw new Error(t("ar_invalid_result"));
		artifact = row;
		render();
	}
	async function loadCatalog(more = false) {
		const data = await api("GET", `/artifacts?limit=30${more && catalogCursor ? `&cursor=${encodeURIComponent(catalogCursor)}` : ""}`);
		guard();
		const rows = (data.artifacts || []).map((a) => a.revision).filter((row) => validArtifact(row));
		if (!more) catalog.replaceChildren();
		for (const row of rows) catalog.append(h("div", { class: "row" }, h("a", {
			class: "title",
			href: `#/artifact-review/artifact/${row.artifact_id}/${row.revision}`
		}, `${row.display_name || row.artifact_id} · r${row.revision}`), h("code", {}, row.digest)));
		catalogCursor = data.next_cursor;
		moreArtifacts.hidden = !catalogCursor;
		if (!catalog.children.length) catalog.append(h("p", { class: "muted" }, t("ar_no_artifacts")));
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		refreshing = (async () => {
			const reads = [];
			if (saved.capture?.operation_id) reads.push(api("GET", `/operations/${saved.capture.operation_id}`).then((data) => adopt("capture", data.operation)));
			else if (context.kind === "artifact") reads.push(loadExactArtifact());
			if (saved.accept?.operation_id) reads.push(api("GET", `/operations/${saved.accept.operation_id}`).then((data) => adopt("accept", data.operation)));
			const outcomes = await Promise.allSettled(reads);
			for (const result of outcomes) if (result.status === "rejected") throw result.reason;
			guard();
			readFailed = false;
			render();
		})();
		update();
		try {
			await refreshing;
		} catch (error) {
			if (currentView()) {
				readFailed = true;
				showError(error);
			}
			throw error;
		} finally {
			refreshing = null;
			if (currentView()) update();
		}
	}
	const off = onEvents((event) => {
		if (!currentView()) return;
		if (event.resource_id === saved.capture?.operation_id || event.resource_id === saved.accept?.operation_id || event.resource_id === artifact?.artifact_id) return refresh(true);
	});
	if (saved.capture?.expected?.source) source = {
		host: saved.capture.expected.source.host,
		session_id: saved.capture.expected.source.session_id
	};
	renderChoice();
	render();
	const initial = [];
	if (!saved.capture) initial.push(loadSource());
	if (saved.capture?.operation_id || saved.accept?.operation_id || context.kind === "artifact") initial.push(refresh());
	initial.push(loadCatalog().catch((error) => {
		if (currentView()) catalogNotice.replaceChildren(errorBox(error));
	}));
	const results = await Promise.allSettled(initial);
	for (const result of results) if (result.status === "rejected") {
		readFailed = true;
		showError(result.reason);
	}
	if (!source && saved.capture?.expected?.source) {
		source = {
			host: saved.capture.expected.source.host,
			session_id: saved.capture.expected.source.session_id
		};
		renderChoice();
	}
	render();
	const timer = setInterval(() => {
		if (!currentView()) return;
		update();
		if (saved.capture?.operation_id && active("capture") || saved.accept?.operation_id && active("accept")) refresh().catch(showError);
	}, 1e3);
	return () => {
		disposed = true;
		clearInterval(timer);
		off();
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
	nativeBusy: false,
	nativeAttempt: 0,
	connectionNotice: null,
	refreshCycle: null
};
async function activate(caps, endpoint = location.origin, reset = false) {
	state.epoch++;
	state.observations = new Map();
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
		if (nativeDesktop || e.status !== 404) throw e;
	}
	if (bootstrap) {
		const sync = bootstrap.sync;
		if (sync?.version !== 1 || !sync.server_id || !sync.principal_id || !Number.isSafeInteger(sync.checkpoint?.cursor) || sync.checkpoint.cursor < 0 || !sync.checkpoint.token || bootstrap.capabilities?.actor !== caps.actor || caps.desktop_identity && (caps.desktop_identity.server_id !== sync.server_id || caps.desktop_identity.principal_id !== sync.principal_id)) throw new Error("Invalid central bootstrap identity");
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
	if (method === "POST" && (state.nativeBusy || !state.online || !state.viewReady)) throw new ApiError(0, "CENTRAL_OFFLINE", t("offline_actions_paused"));
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
function manualCapture(scope, source = {}, onAttach) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	return capturePanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		onEvents,
		errorBox,
		storageKey: `batc.capture.${connection.namespace}.${scope}`,
		source,
		onAttach
	});
}
function attachmentDraft(scope, text, initial = [], roles = false) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const key = `batc.draft.${connection.namespace}.${scope}`;
	let saved;
	try {
		saved = JSON.parse(localStorage.getItem(key));
	} catch {}
	saved = saved && typeof saved === "object" ? saved : {
		text: text.value,
		attachments: initial.map((ref) => ({
			name: ref.artifact_id,
			ref: { ...ref }
		}))
	};
	if (!Array.isArray(saved.attachments)) saved.attachments = [];
	saved.attachments = saved.attachments.filter((a) => a && typeof a === "object");
	for (const a of saved.attachments) delete a.busy;
	if (typeof saved.text === "string") text.value = saved.text;
	const files = new Map(), rows = h("div", { class: "attachment-list" });
	const status = h("p", {
		class: "muted",
		role: "status"
	});
	const supported = Boolean(state.caps?.artifacts), nativeFiles = nativeDesktop && nativeFileSupport;
	const nativeUploadAllowed = state.caps?.actions?.some((a) => a.action === "artifact.upload" && a.allowed === true);
	let native;
	const choose = nativeFiles ? h("button", {
		class: "secondary",
		disabled: !supported || !may("manage") || !nativeUploadAllowed,
		onclick: () => native.pick()
	}, t("files_choose")) : h("input", {
		type: "file",
		multiple: true,
		disabled: !supported || !may("manage"),
		"aria-label": t("choose_attachments")
	});
	const box = h("div", {
		class: "attachments",
		hidden: !supported
	}, nativeFiles ? h("div", { class: "actions" }, h("strong", {}, t("attachments")), choose) : h("label", {}, t("attachments"), choose), h("p", { class: "muted" }, t(nativeFiles ? "files_help" : "upload_on_choose")), rows, status);
	const guard = (mounted = false) => {
		assertView(connection);
		if (mounted && !box.isConnected) throw new ApiError(0, "VIEW_CHANGED", "Attachment form changed during the request");
	};
	const persist = () => {
		guard();
		saved.text = text.value;
		try {
			localStorage.setItem(key, JSON.stringify(saved));
		} catch {}
	};
	const removeStored = () => {
		guard();
		try {
			localStorage.removeItem(key);
		} catch {}
	};
	text.addEventListener("input", persist);
	const refs = () => saved.attachments.filter((a) => a.ref).map((a) => roles ? {
		...a.ref,
		role: a.ref.role || "input"
	} : {
		artifact_id: a.ref.artifact_id,
		revision: a.ref.revision,
		digest: a.ref.digest
	});
	const snapshot = () => JSON.stringify({
		text: text.value,
		attachments: refs(),
		fields: saved.fields
	});
	const ready = () => saved.attachments.every((a) => a.ref);
	const render = () => fill(rows, ...saved.attachments.filter((a) => !nativeFiles || !a.native_handle || a.ref || !native?.has(a.native_handle)).map((a) => h("div", { class: "row" }, h("div", { class: "grow" }, a.name, a.ref ? h("div", { class: "muted" }, `${a.ref.artifact_id} · r${a.ref.revision} · ${a.ref.digest.slice(0, 12)}`) : h("div", { class: "muted" }, a.error || (a.native_handle ? t("files_unavailable") : files.has(a) ? t("uploading") : t("choose_again")))), a.ref && roles ? h("select", {
		"aria-label": t("attachment_role"),
		onchange: (e) => {
			guard();
			a.ref.role = e.target.value;
			persist();
		}
	}, ...["input", "result"].map((role) => h("option", {
		value: role,
		selected: (a.ref.role || "input") === role
	}, t(`attachment_${role}`)))) : null, a.ref && native ? native.actions(a.ref) : null, !a.ref && files.has(a) && !a.busy ? h("button", {
		class: "secondary",
		onclick: () => upload(a)
	}, t("retry")) : null, h("button", {
		class: "secondary",
		disabled: a.busy,
		onclick: () => {
			guard();
			if (a.native_handle) {
				saved.native_ignored ||= [];
				saved.native_ignored.push(a.native_handle);
			}
			saved.attachments = saved.attachments.filter((x) => x !== a);
			files.delete(a);
			persist();
			render();
		}
	}, t("remove")))));
	if (nativeFiles) {
		if (!Array.isArray(saved.native_ignored)) saved.native_ignored = [];
		saved.native_ignored = saved.native_ignored.filter((id) => typeof id === "string" && /^file_[0-9a-f]{32}$/.test(id));
		if (typeof saved.native_draft !== "string" || !/^[0-9a-f-]{36}$/.test(saved.native_draft)) saved.native_draft = saved.attachments.find((a) => typeof a.native_receipt?.draft_id === "string" && /^[0-9a-f-]{36}$/.test(a.native_receipt.draft_id))?.native_receipt.draft_id || crypto.randomUUID();
		native = nativeAttachments({
			h,
			t,
			guard: () => guard(true),
			canWrite: () => state.online && state.viewReady && may("manage") && nativeUploadAllowed,
			draftId: saved.native_draft,
			onVisibility: render,
			onDiscard: (id) => {
				guard(true);
				saved.attachments = saved.attachments.filter((a) => a.native_handle !== id || a.ref);
				persist();
				render();
			},
			attached: (id) => saved.attachments.some((a) => a.native_handle === id && a.ref) || saved.native_ignored?.includes(id),
			onReceipt: (receipt) => {
				guard(true);
				if (saved.native_ignored?.includes(receipt.transfer_id)) return;
				let a = saved.attachments.find((a) => a.native_handle === receipt.transfer_id);
				if (a?.native_receipt && [
					"intent_key",
					"display_name",
					"size_bytes",
					"digest"
				].some((field) => a.native_receipt[field] !== receipt[field])) throw new Error(t("files_receipt_mismatch"));
				if (a && JSON.stringify(a.native_receipt) === JSON.stringify(receipt)) return;
				if (!a) {
					a = {
						name: receipt.display_name,
						native_handle: receipt.transfer_id
					};
					saved.attachments.push(a);
				}
				a.native_receipt = receipt;
				if (receipt.stage === "ready") a.ref = {
					...receipt.artifact,
					...roles ? { role: a.ref?.role || "input" } : {}
				};
				persist();
				render();
			}
		});
		choose.after(native.drop);
		box.insertBefore(native.box, rows);
		persist();
	}
	const acceptUpload = (a, op) => {
		if (op.status !== "succeeded") return;
		a.ref = {
			artifact_id: op.result.artifact_id,
			revision: op.result.revision,
			digest: op.result.digest,
			...roles ? { role: "input" } : {}
		};
		delete a.operation_id;
		delete a.key;
		delete a.error;
		delete a.request;
		files.delete(a);
		persist();
		render();
	};
	const upload = async (a) => {
		if (a.busy) return;
		guard();
		a.busy = true;
		delete a.error;
		render();
		try {
			const file = files.get(a), limit = Math.min(state.caps.artifacts.limits.max_file_bytes, nativeDesktop ? 16777216 : Number.MAX_SAFE_INTEGER);
			if (file.size > limit) throw new Error(`ARTIFACT_TOO_LARGE (${limit})`);
			const bytes = await file.arrayBuffer();
			guard(true);
			const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((x) => x.toString(16).padStart(2, "0")).join("");
			guard(true);
			const request = {
				action: "artifact.upload",
				target: {},
				params: {
					display_name: file.name,
					media_type: file.type || "application/octet-stream",
					size_bytes: file.size,
					expected_digest: digest
				},
				preconditions: {}
			};
			if (a.request && JSON.stringify(a.request) !== JSON.stringify(request)) throw new Error(t("attachment_file_changed"));
			a.request ||= request;
			a.key ||= crypto.randomUUID();
			persist();
			let op = a.operation_id ? (await api("GET", `/operations/${a.operation_id}`)).operation : null;
			guard(true);
			if (op && ["failed", "cancelled"].includes(op.status)) {
				op = null;
				a.key = crypto.randomUUID();
				delete a.operation_id;
				persist();
			}
			if (!op) op = (await api("POST", "/operations?wait=3", a.request, a.key)).operation;
			guard(true);
			a.operation_id = op.operation_id;
			persist();
			const deadline = Date.now() + 6e4;
			const readNext = async () => {
				if (Date.now() > deadline) throw new Error(t("attachment_pending"));
				await sleep(400);
				guard(true);
				const next = (await api("GET", `/operations/${op.operation_id}`)).operation;
				guard(true);
				return next;
			};
			while (["accepted", "running"].includes(op.status)) op = await readNext();
			if (op.status === "waiting_external") {
				if (!state.online || !state.viewReady) throw new ApiError(0, "CENTRAL_OFFLINE", t("offline_actions_paused"));
				const epoch = state.epoch;
				const response = await connectorUploadArtifact(op.operation_id, bytes, state.token);
				guard(true);
				if (epoch !== state.epoch) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed during upload");
				if (response.status < 200 || response.status >= 300) throw new ApiError(response.status, response.data.error?.code, response.data.error?.message);
				do
					op = await readNext();
				while ([
					"accepted",
					"running",
					"waiting_external"
				].includes(op.status));
			}
			if (op.status !== "succeeded") throw new Error(`${op.error_code || op.status}: ${op.status_reason || ""}`);
			acceptUpload(a, op);
		} catch (e) {
			if (connection.epoch !== state.epoch || connection.generation !== generation || !box.isConnected) return;
			a.error = e.message;
		} finally {
			delete a.busy;
			if (connection.epoch === state.epoch && connection.generation === generation && box.isConnected) {
				persist();
				render();
			}
		}
	};
	if (!nativeFiles) choose.onchange = () => {
		guard();
		for (const file of choose.files) {
			let a = saved.attachments.find((x) => !x.ref && !files.has(x) && x.name === file.name);
			if (!a) {
				a = { name: file.name };
				saved.attachments.push(a);
			}
			files.set(a, file);
			upload(a);
		}
		choose.value = "";
		persist();
		render();
	};
	const existing = h("select", { "aria-label": t("existing_artifact") }, h("option", { value: "" }, t("existing_artifact")));
	box.append(h("div", { class: "actions" }, existing, h("button", {
		class: "secondary",
		onclick: async () => {
			if (!existing.value) return;
			const [artifactId, revision] = existing.value.split(":");
			try {
				guard();
				const { artifact } = await api("GET", `/artifacts/${artifactId}/revisions/${revision}`);
				guard(true);
				if (artifact.state !== "ready") throw new Error(t("attachments_not_ready"));
				if (!saved.attachments.some((a) => a.ref?.artifact_id === artifactId && a.ref?.revision === Number(revision))) saved.attachments.push({
					name: artifact.display_name,
					ref: {
						artifact_id: artifactId,
						revision: Number(revision),
						digest: artifact.digest,
						...roles ? { role: "input" } : {}
					}
				});
				persist();
				render();
			} catch (e) {
				if (connection.epoch === state.epoch) fill(status, errorBox(e));
			}
		}
	}, t("add_attachment"))));
	let catalogCursor = null;
	const more = h("button", {
		class: "secondary",
		hidden: true,
		onclick: async () => {
			more.disabled = true;
			try {
				await loadCatalog(catalogCursor);
			} catch (e) {
				if (box.isConnected) fill(status, errorBox(e));
			} finally {
				more.disabled = false;
			}
		}
	}, t("more"));
	box.append(more);
	if (state.caps?.artifacts?.capture?.manual_single_file) box.append(manualCapture(scope, {}, (ref, name) => {
		guard(true);
		if (!saved.attachments.some((a) => a.ref?.artifact_id === ref.artifact_id && a.ref?.revision === ref.revision)) saved.attachments.push({
			name,
			ref: {
				...ref,
				...roles ? { role: "input" } : {}
			}
		});
		persist();
		render();
	}));
	const loadCatalog = async (cursor = "") => {
		const page = await api("GET", `/artifacts?limit=200${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
		guard(true);
		const selected = existing.value, selectedOption = existing.selectedOptions[0];
		if (!cursor) existing.replaceChildren(h("option", { value: "" }, t("existing_artifact")));
		for (const { revision: r } of page.artifacts) if (r?.state === "ready" && ![...existing.options].some((o) => o.value === `${r.artifact_id}:${r.revision}`)) existing.append(h("option", { value: `${r.artifact_id}:${r.revision}` }, `${r.display_name} · r${r.revision} · ${r.artifact_id.slice(-8)}`));
		if (selected && ![...existing.options].some((o) => o.value === selected)) existing.append(selectedOption);
		existing.value = selected;
		catalogCursor = page.next_cursor;
		more.hidden = !catalogCursor;
	};
	const settleSubmission = (op) => {
		guard(true);
		if (!saved.submission || !TERMINAL.includes(op.status)) return;
		const unchanged = saved.submission.snapshot === snapshot();
		delete saved.submission;
		if (op.status === "succeeded" && unchanged) {
			text.value = "";
			saved.attachments = [];
			saved.fields = void 0;
			removeStored();
			render();
		} else persist();
	};
	const perform = async (action, target, params, preconditions, requestScope) => {
		guard(true);
		const request = {
			action,
			target,
			params,
			preconditions
		};
		if (saved.submission?.refused && JSON.stringify(saved.submission.request) !== JSON.stringify(request)) delete saved.submission;
		if (!saved.submission) {
			saved.submission = {
				request: structuredClone({
					action,
					target,
					params,
					preconditions
				}),
				key: crypto.randomUUID(),
				snapshot: snapshot(),
				scope: requestScope
			};
			persist();
		}
		const intent = saved.submission;
		try {
			const op = intent.operation_id ? (await api("GET", `/operations/${intent.operation_id}`)).operation : (await api("POST", "/operations?wait=3", intent.request, intent.key)).operation;
			guard(true);
			intent.operation_id = op.operation_id;
			persist();
			settleSubmission(op);
			return op;
		} catch (error) {
			if (connection.epoch === state.epoch && connection.generation === generation && error.status >= 400 && error.status < 500 && error.code !== "IDEMPOTENCY_CONFLICT") {
				intent.refused = true;
				persist();
			}
			throw error;
		}
	};
	const refresh = async () => {
		guard(true);
		const pending = saved.attachments.filter((a) => !a.ref && a.operation_id);
		await settleRefreshes([
			...native ? [native.refresh()] : [],
			...pending.map(async (a) => {
				const { operation } = await api("GET", `/operations/${a.operation_id}`);
				guard(true);
				acceptUpload(a, operation);
			}),
			...saved.submission?.operation_id ? [(async () => {
				const { operation } = await api("GET", `/operations/${saved.submission.operation_id}`);
				guard(true);
				settleSubmission(operation);
			})()] : []
		]);
	};
	if (supported) {
		const unsub = onEvents((ev) => {
			if (!box.isConnected || connection.epoch !== state.epoch) {
				unsub();
				return;
			}
			if (ev.resource_type === "artifact") return settleRefreshes([refresh(), loadCatalog()]);
			if (ev.resource_id === saved.submission?.operation_id || saved.attachments.some((a) => a.operation_id === ev.resource_id)) return refresh();
		});
		queueMicrotask(() => settleRefreshes([loadCatalog(), refresh()]).catch((e) => {
			if (box.isConnected && connection.epoch === state.epoch) fill(status, errorBox(e));
		}));
	}
	const bindFields = (fields) => {
		for (const [name, field] of Object.entries(fields)) {
			if (typeof saved.fields?.[name] === "string") field.value = saved.fields[name];
			field.addEventListener("input", () => {
				guard();
				saved.fields = Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.value]));
				persist();
			});
		}
	};
	render();
	return {
		box,
		refs,
		ready,
		perform,
		bindFields,
		pending: () => Boolean(saved.submission)
	};
}
function onEvents(fn) {
	state.listeners.add(fn);
	return () => state.listeners.delete(fn);
}
async function streamEvents() {
	const live = document.getElementById("live");
	for (;;) {
		if (state.nativeBusy || !state.token || !state.viewReady) {
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
function rememberObservation(type, id, value, dependencies = []) {
	state.observations ||= new Map();
	state.observations.set(`${type}:${id}`, {
		value,
		dependencies: new Set(dependencies)
	});
}
function observationAffected(type, id, event) {
	const key = `${event.resource_type}:${event.resource_id}`;
	return key === `${type}:${id}` || state.observations?.get(`${type}:${id}`)?.dependencies.has(key);
}
function itemDependencies(data) {
	return [
		`project:${data.project.project_id}`,
		...[
			...data.path || [],
			...data.children || [],
			...data.derived || []
		].map((item) => `work_item:${item.work_item_id}`),
		...(data.links || []).flatMap((link) => {
			const related = [`${link.kind}:${link.ref}`];
			if (link.kind === "task") related.push(`execution:${link.ref}`);
			if (link.target?.session) related.push(`session:${link.target.session.host}/${link.target.session.session_id}`);
			return related;
		})
	];
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
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const storageKey = `batc.sessions.${connection.namespace}`;
	const q = new URLSearchParams(sessionStorage.getItem(storageKey) || "");
	const hostSel = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("all_hosts")));
	const accessSel = h("select", { "aria-label": t("all_access") }, h("option", { value: "" }, t("all_access")), h("option", { value: "managed" }, t("only_managed")), h("option", { value: "read_only" }, t("only_read_only")));
	const search = h("input", {
		type: "search",
		"aria-label": t("sessions_search"),
		placeholder: t("sessions_search")
	});
	search.value = q.get("search") || "";
	let selected = q.get("workspace") || "", cursor = null, pages = 1, serial = Promise.resolve(), revision = 0;
	const rows = new Map(), expanded = new Set();
	const list = h("div", { class: "session-inventory" }), status = h("div", {}), count = h("p", {
		class: "muted",
		"aria-live": "polite"
	});
	const more = h("button", {
		class: "secondary",
		hidden: true
	}, t("load_more"));
	const navigation = h("nav", {
		"aria-label": t("sessions_workspaces"),
		class: "session-workspaces"
	});
	const scope = h("details", {
		class: "panel session-scope",
		open: matchMedia("(min-width: 901px)").matches
	}, h("summary", {}, t("sessions_workspaces")), h("p", { class: "muted" }, t("sessions_scope_note")), navigation, h("a", {
		class: "session-project-link",
		href: "#/projects"
	}, t("sessions_projects")));
	main.append(h("div", { class: "session-heading" }, h("h1", {}, t("sessions_title")), state.caps?.actions?.some((a) => a.action === "session.start") ? h("a", { href: "#/start" }, t("start_title_page")) : null), h("p", { class: "muted" }, t("sessions_intro")), h("div", { class: "filters session-filters" }, search, hostSel, accessSel, state.caps?.actions?.some((a) => a.action === "session.approve_pending") ? h("a", { href: "#/approvals" }, t("bulk_title")) : null), status, h("div", { class: "session-layout" }, scope, h("section", {
		"aria-label": t("sessions_title"),
		class: "session-results"
	}, count, list, h("div", { class: "session-pagination" }, more, h("span", { class: "muted" }, t("sessions_page_note"))))));
	try {
		const hosts = (await api("GET", "/hosts")).hosts;
		assertView(connection);
		for (const x of hosts) hostSel.append(h("option", { value: x.host }, x.host));
	} catch (e) {
		status.replaceChildren(errorBox(e));
		return;
	}
	hostSel.value = q.get("host") || "";
	accessSel.value = q.get("access") || "";
	const save = () => {
		assertView(connection);
		const values = new URLSearchParams({
			host: hostSel.value,
			access: accessSel.value,
			search: search.value,
			workspace: selected
		});
		sessionStorage.setItem(storageKey, values.toString());
	};
	const row = (session) => {
		const id = `${session.host}/${session.session_id}`, activity = sessionActivity(session);
		const origin = session.provenance === "manual" ? "sessions_manual" : session.provenance === "connector_managed" ? "sessions_connector" : "sessions_origin_unknown";
		const access = session.api_access === "managed" ? "managed" : session.api_access === "read_only" ? "read_only" : "sessions_access_unknown";
		const evidence = () => [
			h("dl", { class: "kv" }, h("dt", {}, t("sessions_label")), h("dd", {}, session.title || session.session_id), h("dt", {}, t("sessions_workspace")), h("dd", {}, session.workspace || t("sessions_workspace_unknown")), h("dt", {}, t("sessions_workspace_id")), h("dd", {}, h("code", {}, session.workspace_id || t("obs_unknown"))), h("dt", {}, t("sessions_id")), h("dd", {}, h("code", {}, session.session_id)), h("dt", {}, t("activity")), h("dd", {}, observationTime(session.last_activity_at)), h("dt", {}, t("observed")), h("dd", {}, observationTime(session.observed_at))),
			h("p", { class: "muted" }, confinementLabel(session)),
			confinementDetails(session),
			observationState(session)
		];
		const details = h("details", {
			class: "session-row-details",
			open: expanded.has(id)
		}, h("summary", {}, t("sessions_details")));
		let mounted = false;
		const mountEvidence = () => {
			if (!mounted) {
				details.append(...evidence());
				mounted = true;
			}
		};
		if (expanded.has(id)) mountEvidence();
		details.addEventListener("toggle", () => {
			if (!details.isConnected) return;
			if (details.open) {
				expanded.add(id);
				mountEvidence();
			} else expanded.delete(id);
		});
		return h("article", {
			class: "session-entry",
			"data-resource-id": id
		}, h("div", { class: "session-entry-heading" }, h("a", {
			class: "title",
			title: session.title || session.session_id,
			href: `#/session/${encodeURIComponent(session.host)}/${encodeURIComponent(session.session_id)}`
		}, session.title || session.session_id), chip(t(activity.key), activity.tone)), h("div", { class: "session-entry-meta" }, h("span", { class: session.api_access === "managed" ? "" : "session-readonly" }, session.provenance === "connector_managed" && session.api_access === "managed" ? t(access) : `${t(origin)} · ${t(access)}`), h("span", {}, [session.agent_kind, session.worktree_branch].filter(Boolean).join(" · "))), runtimeStale(session) ? h("p", { class: "session-stale muted" }, t("sessions_stale"), " · ", session.stale_reason === "gone" ? t("sessions_not_seen") : session.stale_reason ? t("stale_reason_" + session.stale_reason) : t("sessions_runtime_stale")) : null, details);
	};
	const render = () => {
		assertView(connection);
		const groups = groupedSessions([...rows.values()]);
		const choose = (key) => {
			selected = key;
			save();
			render();
		};
		const workspaceName = (group) => group.name || group.id || t("sessions_workspace_unknown");
		const navButton = (label, key, n) => h("button", {
			class: "session-scope-button",
			"aria-pressed": String(selected === key),
			"data-workspace-key": key,
			title: label,
			onclick: () => choose(key)
		}, h("span", {}, label), h("span", { class: "muted" }, t("sessions_loaded_count", { count: n })));
		const links = [navButton(t("sessions_all_loaded"), "", rows.size)];
		const labels = new Map();
		const labelKey = (group) => JSON.stringify([group.host, workspaceName(group)]);
		for (const group of groups) labels.set(labelKey(group), (labels.get(labelKey(group)) || 0) + 1);
		let lastHost;
		for (const group of groups) {
			if (group.host !== lastHost) {
				links.push(h("a", {
					class: "session-host-link",
					href: `#/host/${encodeURIComponent(group.host)}`,
					title: t("obs_discovery")
				}, group.host));
				lastHost = group.host;
			}
			const sameName = labels.get(labelKey(group)) > 1;
			links.push(navButton(workspaceName(group) + (sameName && group.id ? ` · ${group.id}` : ""), group.key, group.sessions.length));
		}
		if (selected && !groups.some((group) => group.key === selected)) links.push(navButton(t("sessions_scope_missing"), selected, 0));
		const focusedKey = navigation.contains(document.activeElement) ? document.activeElement.dataset.workspaceKey : void 0;
		navigation.replaceChildren(...links);
		if (focusedKey !== void 0) [...navigation.querySelectorAll("button")].find((button) => button.dataset.workspaceKey === focusedKey)?.focus({ preventScroll: true });
		let visible = 0;
		const sections = groups.filter((group) => !selected || selected === group.key).flatMap((group) => {
			const sessions = group.sessions.filter((session) => matchesSession(session, search.value));
			if (!sessions.length) return [];
			visible += sessions.length;
			return [h("section", { class: "panel session-group" }, h("header", { class: "session-group-heading" }, h("h2", { title: workspaceName(group) }, workspaceName(group)), h("span", { class: "muted" }, group.host), group.name && group.id && labels.get(labelKey(group)) > 1 ? h("code", { class: "muted" }, group.id) : null, group.name && !group.id ? h("span", { class: "muted" }, t("sessions_workspace_unverified")) : null), ...sessions.map(row))];
		});
		list.replaceChildren(...sections.length ? sections : [h("div", { class: "panel" }, h("p", {}, t("sessions_no_matches")), h("p", { class: "muted" }, cursor ? t("sessions_more_hint") : t("sessions_empty_hint")))]);
		count.textContent = t("sessions_showing", {
			shown: visible,
			loaded: rows.size
		});
	};
	const read = async (mode, expectedRevision) => {
		if (expectedRevision !== revision) return;
		const p = new URLSearchParams({
			limit: "50",
			order: "id",
			include_gone: "true"
		});
		if (hostSel.value) p.set("host", hostSel.value);
		if (accessSel.value) p.set("access", accessSel.value);
		save();
		more.disabled = true;
		try {
			assertView(connection);
			const before = scrollY, anchor = [...list.querySelectorAll("[data-resource-id]")].find((node) => node.getBoundingClientRect().bottom > 110);
			const anchorID = anchor?.dataset.resourceId, offset = anchor?.getBoundingClientRect().top;
			const observed = new Map(mode === "more" ? rows : []);
			let next = mode === "more" ? cursor : null;
			const total = mode === "refresh" ? pages : 1;
			let readPages = 0;
			for (let page = 0; page < total; page++) {
				const query = new URLSearchParams(p);
				if (next) query.set("cursor", next);
				const result = await api("GET", `/sessions?${query}`);
				assertView(connection);
				if (expectedRevision !== revision) return;
				for (const session of result.sessions) observed.set(`${session.host}/${session.session_id}`, session);
				readPages++;
				if (result.next_cursor && result.next_cursor === next) throw new Error("Inventory cursor did not advance");
				next = result.next_cursor;
				if (!next) break;
			}
			rows.clear();
			for (const [id, session] of observed) {
				rows.set(id, session);
				rememberObservation("session", id, { session }, [`host:${session.host}`]);
			}
			cursor = next;
			more.hidden = !cursor;
			pages = mode === "more" ? pages + readPages : readPages;
			const focused = document.activeElement;
			const focusedID = list.contains(focused) ? focused.closest("[data-resource-id]")?.dataset.resourceId : null;
			const focusedPart = focused?.tagName === "SUMMARY" ? "summary" : focused?.classList.contains("title") ? "a.title" : null;
			render();
			status.replaceChildren();
			if (focusedID && focusedPart && document.activeElement === document.body) [...list.querySelectorAll("[data-resource-id]")].find((node) => node.dataset.resourceId === focusedID)?.querySelector(focusedPart)?.focus({ preventScroll: true });
			const current = [...list.querySelectorAll("[data-resource-id]")].find((node) => node.dataset.resourceId === anchorID);
			if (mode === "refresh" && current && Math.abs(scrollY - before) < 1) scrollBy(0, current.getBoundingClientRect().top - offset);
		} catch (e) {
			status.replaceChildren(errorBox(e));
		} finally {
			more.disabled = false;
		}
	};
	const load = async (mode) => {
		const expected = revision;
		serial = serial.then(() => read(mode, expected));
		let pending;
		do {
			pending = serial;
			await pending;
		} while (pending !== serial);
	};
	hostSel.onchange = accessSel.onchange = () => {
		revision++;
		selected = "";
		save();
		return load("reset");
	};
	search.oninput = () => {
		save();
		render();
	};
	more.onclick = () => load("more");
	await load("reset");
	const reload = debounceRefresh(() => load("refresh"), 500);
	return onEvents((ev) => {
		if ([
			"session",
			"host",
			"execution",
			"task"
		].includes(ev.resource_type)) return reload();
	});
}
var observationTime = (value) => value === null || value === void 0 || value === "" ? t("obs_unknown") : when(typeof value === "number" ? new Date(value * 1e3).toISOString() : value);
function observationLink(type, id) {
	if (!id) return null;
	let href;
	if (type === "session") {
		const [host, ...sid] = id.split("/");
		if (host && sid.length) href = `#/session/${encodeURIComponent(host)}/${encodeURIComponent(sid.join("/"))}`;
	} else if (type === "execution" || type === "task") href = `#/task/${encodeURIComponent(id)}`;
	else if (type === "worktree") href = `#/worktree/${encodeURIComponent(id)}`;
	else if (type === "operation") href = `#/op/${encodeURIComponent(id)}`;
	return href ? h("a", { href }, id) : h("code", {}, id);
}
function observationState(row) {
	return h("details", { class: "observation-evidence" }, h("summary", {}, t("obs_state_evidence")), h("p", { class: "muted" }, t("obs_lifecycle_note")), h("dl", { class: "kv" }, ...[
		"connection",
		"loading",
		"tab",
		"activity",
		"lifecycle",
		"enumeration",
		"freshness"
	].flatMap((axis) => {
		const evidence = row.state?.evidence?.[axis];
		return [h("dt", {}, t("obs_axis_" + axis)), h("dd", {}, t("obs_value_" + (row.state?.[axis] || "unknown")), evidence?.stale ? [" · ", chip(t("stale"), "stale")] : null, h("div", { class: "muted" }, observationTime(evidence?.observed_at), " · ", evidence?.source_ref || t("obs_unknown")))];
	})));
}
function discoveryEvidence(scopes) {
	return h("div", {}, ...scopes?.length ? scopes.map((scope) => h("section", { class: "observation-evidence" }, h("h3", {}, scope.profile_id || t("obs_unknown")), h("dl", { class: "kv" }, h("dt", {}, t("obs_scan_status")), h("dd", {}, scope.status || t("obs_unknown")), h("dt", {}, t("obs_last_success")), h("dd", {}, observationTime(scope.last_success_at)), h("dt", {}, t("obs_last_attempt")), h("dd", {}, observationTime(scope.finished_at)), h("dt", {}, t("obs_authority")), h("dd", {}, scope.authority?.kind || t("obs_unknown"), " · ", t(scope.authority?.verified ? "obs_verified" : "obs_unverified"))), scope.error_code ? h("p", { class: "error" }, scope.error_code) : null, h("details", {}, h("summary", {}, t("obs_scan_coverage")), h("pre", { class: "pre" }, JSON.stringify({
		coverage: scope.coverage || {},
		methods: scope.methods || {},
		errors: scope.errors || []
	}, null, 2))), h("h3", {}, t("obs_outside_scan")), h("ul", {}, ...(scope.outside_scan || []).map((x) => h("li", {}, t("obs_scope_" + x.scope), " · ", h("code", {}, x.reason)))))) : [h("p", { class: "muted" }, t("obs_no_scan"))]);
}
function observationPanels(type, id, path) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const section = (mode) => {
		const relations = mode === "relations";
		const list = h("div", {}), status = h("div", {}), evidence = h("p", { class: "muted" });
		const notice = h("p", {
			class: "note",
			hidden: true
		}, t("obs_new_facts"));
		const kind = h("input", {
			placeholder: t("obs_event_kind"),
			"aria-label": t("obs_event_kind")
		});
		const execution = h("input", {
			placeholder: t("obs_execution_filter"),
			"aria-label": t("obs_execution_filter")
		});
		const closed = h("input", {
			type: "checkbox",
			checked: true
		});
		let cursor = null, asOf = null, busy = false, parameters = "", loaded = false, latestSeen = state.lastEvent;
		const seen = new Set();
		const more = h("button", {
			class: "secondary",
			hidden: true,
			onclick: () => load(false)
		}, t("load_more"));
		const refresh = h("button", {
			class: "secondary",
			onclick: () => load(true)
		}, t("obs_read_latest"));
		const eventRow = (event) => {
			const context = event.context || {};
			const occurred = Object.hasOwn(context, "occurred_at") ? context.occurred_at : event.created_at;
			const details = h("details", {}, h("summary", {}, t("obs_evidence")), h("pre", { class: "pre" }, JSON.stringify({
				body: event.body || {},
				context
			}, null, 2)));
			const refs = [];
			for (const [field, resource] of [
				["execution_id", "execution"],
				["session_resource_id", "session"],
				["worktree_id", "worktree"],
				["operation_id", "operation"]
			]) {
				const value = event.body?.[field] || context[field];
				if (value) refs.push(observationLink(resource, value));
			}
			return h("article", {
				class: "observation-record",
				"data-history-seq": event.seq
			}, h("div", { class: "actions" }, h("strong", {}, event.kind), chip(`#${event.seq}`), observationLink(event.resource_type, event.resource_id)), h("p", { class: "muted" }, t("obs_occurred"), ": ", observationTime(occurred), " · ", t("obs_recorded"), ": ", observationTime(context.recorded_at ?? event.created_at), " · ", event.actor || t("obs_unknown")), refs.length ? h("div", { class: "actions" }, ...refs) : null, details);
		};
		const relationRow = (relation) => h("article", {
			class: "observation-record",
			"data-relation-id": relation.relation_id
		}, h("div", { class: "actions" }, observationLink("execution", relation.execution_id), relation.session_resource_id ? observationLink("session", relation.session_resource_id) : chip(t("obs_pending_binding"), "warn")), h("p", {}, relation.role || t("obs_unknown"), " · ", relation.status || t("obs_unknown"), " · ", relation.reason || t("obs_unknown")), h("p", { class: "muted" }, t("obs_half_open", {
			start: relation.start_seq ?? "?",
			end: relation.end_seq ?? "∞"
		}), " · ", observationTime(relation.started_at), " → ", observationTime(relation.ended_at)), relation.follow_up_of_execution_id ? h("p", {}, t("obs_follow_up"), " ", observationLink("execution", relation.follow_up_of_execution_id)) : null, h("details", {}, h("summary", {}, t("obs_evidence")), h("pre", { class: "pre" }, JSON.stringify({
			relation_id: relation.relation_id,
			branch_id: relation.branch_id,
			parent_relation_id: relation.parent_relation_id,
			command_ids: relation.command_ids || [],
			worktree_ranges: relation.worktree_ranges,
			evidence: relation.evidence
		}, null, 2))));
		async function load(reset) {
			if (busy) return;
			busy = true;
			refresh.disabled = more.disabled = true;
			try {
				assertView(connection);
				const params = reset ? new URLSearchParams({ limit: "20" }) : new URLSearchParams(parameters);
				if (reset && relations) {
					params.set("include_closed", String(closed.checked));
					if (execution.value.trim()) params.set("execution_id", execution.value.trim());
				} else if (reset) {
					params.set("order", "desc");
					if (kind.value.trim()) params.set("kind", kind.value.trim());
				}
				const filters = params.toString();
				if (!reset && cursor) params.set("cursor", cursor);
				const result = await api("GET", `${path}/${relations && type === "execution" ? "sessions" : mode}?${params}`);
				assertView(connection);
				if (!Number.isSafeInteger(result.as_of) || !reset && result.as_of !== asOf) throw new Error("Observation cursor changed its as_of");
				const items = result[relations ? "relations" : "events"];
				if (!Array.isArray(items)) throw new Error("Invalid observation page");
				if (reset) {
					seen.clear();
					list.replaceChildren();
					parameters = filters;
					asOf = result.as_of;
					notice.hidden = true;
				}
				for (const item of items) {
					const key = relations ? item.relation_id : item.seq;
					if (!seen.has(key)) {
						seen.add(key);
						list.append(relations ? relationRow(item) : eventRow(item));
					}
				}
				if (!seen.size) list.replaceChildren(h("p", { class: "muted" }, t("obs_empty")));
				cursor = result.next_cursor;
				more.hidden = !cursor;
				loaded = true;
				notice.hidden = latestSeen <= asOf;
				evidence.replaceChildren(...[
					t("obs_snapshot", { seq: asOf }),
					" ",
					t("obs_historical_limits"),
					!relations ? [
						" ",
						t("obs_first_recorded"),
						": ",
						observationTime(result.coverage?.first_recorded_at)
					] : ""
				].flat());
				status.replaceChildren();
			} catch (error) {
				status.replaceChildren(errorBox(error));
			} finally {
				busy = false;
				refresh.disabled = more.disabled = false;
			}
		}
		const box = h("details", {
			class: "panel observation-panel",
			"data-observation": mode,
			ontoggle: () => {
				if (box.open && !loaded) load(true);
			}
		}, h("summary", {}, t(relations ? "obs_relations" : "obs_history")), h("div", { class: "filters" }, relations ? execution : kind, relations ? h("label", {}, closed, " ", t("obs_include_closed")) : null, refresh), notice, evidence, status, list, more);
		return {
			box,
			changed: (event) => {
				latestSeen = Math.max(latestSeen, event.seq);
				if (loaded && latestSeen > asOf) notice.hidden = false;
			}
		};
	};
	const history = section("history"), relations = section("relations");
	return {
		box: h("div", {}, history.box, relations.box),
		changed: (event) => {
			history.changed(event);
			relations.changed(event);
		}
	};
}
async function viewObservedResource(main, type, id) {
	const path = type === "execution" ? `/tasks/${encodeURIComponent(id)}` : `/worktrees/${encodeURIComponent(id)}`;
	const head = h("div", { class: "panel" });
	const panels = observationPanels(type, id, path);
	main.append(head, panels.box);
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const load = async () => {
		try {
			const data = await api("GET", path);
			assertView(connection);
			const resource = data[type === "execution" ? "task" : "worktree"];
			head.replaceChildren(h("h1", {}, t(type === "execution" ? "obs_execution" : "obs_worktree")), h("code", {}, id), h("p", { class: "muted" }, t("obs_known_identity")), type === "execution" && state.caps?.features?.cleanup_task === true ? h("p", {}, h("a", { href: `#/cleanup/task/${encodeURIComponent(id)}` }, t("cleanup_task_preview"))) : null, type === "execution" && state.caps?.artifacts?.capture?.managed_single_file === true ? h("p", {}, h("a", { href: `#/artifact-review/task/${encodeURIComponent(id)}` }, t("ar_open"))) : null, h("pre", { class: "pre" }, JSON.stringify(resource, null, 2)));
		} catch (error) {
			head.append(errorBox(error));
		}
	};
	await load();
	const reload = debounceRefresh(load, 500);
	return onEvents((event) => {
		panels.changed(event);
		if ([
			type,
			"task",
			"operation",
			"session"
		].includes(event.resource_type)) return reload();
	});
}
async function viewHostDiscovery(main, host) {
	const head = h("div", { class: "panel" });
	main.append(h("h1", {}, host, " · ", t("obs_discovery")), h("p", { class: "note" }, t("obs_discovery_note")), head);
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const load = async () => {
		try {
			const data = await api("GET", `/hosts/${encodeURIComponent(host)}/discovery`);
			assertView(connection);
			head.replaceChildren(discoveryEvidence(data.scopes));
		} catch (error) {
			head.append(errorBox(error));
		}
	};
	await load();
	const reload = debounceRefresh(load, 500);
	return onEvents((event) => {
		if (event.resource_type === "host" && event.resource_id === host) return reload();
	});
}
async function viewSession(main, host, sid) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const path = `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}`;
	const head = h("div", { class: "panel" }), msgs = h("div", { class: "panel" });
	const pending = h("div", { "data-pending-controls": "" }), status = h("div", { class: "muted" });
	const scope = `send.${host}.${sid}`, draftKey = `batc.draft.${connection.namespace}.${scope}`;
	const box = h("textarea", { placeholder: t("send_placeholder") });
	try {
		box.value = localStorage.getItem(draftKey) || "";
	} catch {}
	box.oninput = () => {
		try {
			localStorage.setItem(draftKey, box.value);
		} catch {}
	};
	const queue = h("input", { type: "checkbox" });
	let row, pendingIdentity, sending = false, readReady = false, refreshInFlight = null, readError = null;
	const allowed = (action) => readReady && row?.api_access === "managed" && may("operate") && state.caps?.hosts?.find((item) => item.host === host)?.writes !== false && state.caps?.actions?.find((item) => item.action === action)?.allowed !== false;
	const identity = (pend) => pend ? JSON.stringify({
		kind: pend.kind,
		toolUseId: pend.toolUseId,
		toolName: pend.toolName,
		input_preview: pend.input_preview,
		questions: pend.questions
	}) : "";
	const send = h("button", {
		class: "primary",
		disabled: true,
		onclick: async () => {
			if (!box.value.trim()) return;
			const submitted = box.value;
			sending = true;
			send.disabled = true;
			try {
				assertView(connection);
				const op = await submit("session.send", {
					host,
					session_id: sid
				}, {
					text: submitted,
					queue: queue.checked
				}, {}, scope);
				assertView(connection);
				status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				if (op.status === "succeeded" && box.value === submitted) {
					box.value = "";
					try {
						localStorage.removeItem(draftKey);
					} catch {}
				}
			} catch (e) {
				status.replaceChildren(errorBox(e));
			} finally {
				sending = false;
				send.disabled = !allowed("session.send");
			}
		}
	}, t("send"));
	const stop = h("button", {
		class: "danger",
		disabled: true,
		onclick: async () => {
			try {
				assertView(connection);
				const op = await submit("session.interrupt", {
					host,
					session_id: sid
				}, { mode: "soft" }, {}, `interrupt.${host}.${sid}`);
				assertView(connection);
				status.replaceChildren(opStatus(op));
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
		}
	}, t("interrupt"));
	const composer = h("div", { hidden: true }, box, h("div", { class: "actions" }, send, stop, h("label", { class: "muted" }, queue, " ", t("queue_behind"))));
	const readonly = h("p", { class: "note" }, t("read_only_note"));
	let capture, permissions;
	const captureSlot = h("div"), permissionsSlot = h("div");
	const controls = h("div", { class: "panel" }, pending, readonly, composer, permissionsSlot, captureSlot, status);
	const cps = checkpointPanel(host, sid);
	const observations = observationPanels("session", `${host}/${sid}`, path);
	main.append(head, controls, cps.box, h("h2", {}, t("messages")), msgs, observations.box);
	const renderPending = () => {
		const pend = row.api_access === "managed" ? row.pending : null;
		const current = identity(pend);
		if (current === pendingIdentity) return;
		pendingIdentity = current;
		pending.replaceChildren();
		if (!pend) return;
		const answerScope = `answer.${host}.${sid}.${pend.toolUseId || ""}`;
		const key = `batc.draft.${connection.namespace}.${answerScope}`;
		let saved;
		try {
			saved = JSON.parse(localStorage.getItem(key));
		} catch {}
		const answer = async (params) => {
			try {
				assertView(connection);
				const latest = await api("GET", path);
				assertView(connection);
				applyObservation(latest);
				if (latest.session.api_access !== "managed" || identity(latest.session.pending) !== current || !pend.toolUseId) throw new ApiError(409, "PENDING_CHANGED", t("pending_changed"));
				const op = await submit("session.answer", {
					host,
					session_id: sid
				}, {
					...params,
					tool_use_id: pend.toolUseId
				}, {}, answerScope);
				assertView(connection);
				status.replaceChildren(opStatus(op));
				if (op.status === "succeeded") await loadObservation();
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
		};
		const card = h("div", { class: "panel" }, h("div", { class: "title" }, t("pending_" + pend.kind)));
		if (pend.kind === "permission") card.append(h("p", {}, h("code", {}, pend.toolName || "")), h("p", { class: "msg" }, pend.input_preview || ""), h("div", { class: "actions" }, h("button", {
			class: "primary",
			"data-answer-action": "",
			disabled: !pend.toolUseId || !allowed("session.answer"),
			onclick: () => answer({ permission: "allow" })
		}, t("allow")), h("button", {
			class: "danger",
			"data-answer-action": "",
			disabled: !pend.toolUseId || !allowed("session.answer"),
			onclick: () => answer({ permission: "deny" })
		}, t("deny"))));
		else if (pend.kind === "ask_user") {
			const fields = [];
			const save = () => {
				try {
					localStorage.setItem(key, JSON.stringify({
						identity: current,
						answers: fields.map((f) => f.value)
					}));
				} catch {}
			};
			for (const [index, q] of (pend.questions || []).entries()) {
				const input = h("input", {
					placeholder: t("answer"),
					"aria-label": q.question || t("answer"),
					value: saved?.identity === current ? saved.answers?.[index] || "" : "",
					oninput: save
				});
				fields.push(input);
				const picks = (q.options || []).map((o) => h("button", {
					class: "secondary",
					onclick: () => {
						input.value = o;
						save();
					}
				}, o));
				card.append(h("p", {}, q.header ? h("strong", {}, `${q.header} · `) : null, q.question), picks.length ? h("div", { class: "actions" }, ...picks) : null, h("div", { class: "actions" }, input));
			}
			card.append(h("div", { class: "actions" }, h("button", {
				class: "primary",
				"data-answer-action": "",
				disabled: !pend.toolUseId || !allowed("session.answer"),
				onclick: () => answer({ answers: fields.map((f) => f.value) })
			}, t("answer"))));
		}
		pending.append(card);
	};
	const updateControls = () => {
		permissions?.update();
		send.disabled = !allowed("session.send") || sending;
		stop.disabled = !allowed("session.interrupt");
		for (const button of pending.querySelectorAll("[data-answer-action]")) button.disabled = !row?.pending?.toolUseId || !allowed("session.answer");
	};
	const applyObservation = (data) => {
		const first = !row;
		row = data.session;
		rememberObservation("session", `${host}/${sid}`, data, [
			`host:${host}`,
			...(data.work_items || []).map((item) => `work_item:${item.work_item_id}`),
			...(data.relations_summary || []).flatMap((relation) => [`execution:${relation.execution_id}`, `task:${relation.execution_id}`]),
			...data.started_from?.operation_id ? [`operation:${data.started_from.operation_id}`] : []
		]);
		if (first) queue.checked = Boolean(row.streaming);
		head.replaceChildren(h("h1", {}, row.title || sid), h("div", { class: "actions" }, ...sessionBadges(row)), h("dl", { class: "kv" }, h("dt", {}, t("host")), h("dd", {}, h("a", { href: `#/host/${encodeURIComponent(host)}` }, row.host)), h("dt", {}, t("workspace")), h("dd", {}, row.workspace || ""), h("dt", {}, "Session"), h("dd", {}, h("code", {}, row.session_id)), h("dt", {}, t("agent")), h("dd", {}, [row.agent_kind, row.model].filter(Boolean).join(" · ")), h("dt", {}, "Provenance"), h("dd", {}, t("provenance_" + row.provenance)), h("dt", {}, t("observed")), h("dd", {}, observationTime(row.observed_at))), observationState(row), confinementDetails(row));
		if (data.started_from) {
			const from = data.started_from;
			head.append(h("p", { class: "note" }, t("started_from", { commit: from.commit_sha.slice(0, 12) }), " ", h("a", { href: `#/session/${encodeURIComponent(from.source_host)}/${encodeURIComponent(from.source_session_id)}` }, t("source_session")), " · ", h("a", { href: `#/op/${from.operation_id}` }, from.operation_id)));
		}
		if (data.work_items?.length) head.append(linkedItems(data.work_items));
		if (data.discovery?.length) head.append(h("details", {}, h("summary", {}, t("obs_discovery")), discoveryEvidence(data.discovery)));
		const managed = row.api_access === "managed";
		if (managed && row.provenance === "connector_managed" && state.caps?.artifacts?.capture?.managed_single_file) head.append(h("p", {}, h("a", { href: `#/artifact-review/session/${encodeURIComponent(host)}/${encodeURIComponent(sid)}` }, t("ar_open"))));
		if (managed && row.provenance === "connector_managed" && !permissions) {
			permissions = permissionsPanel({
				h,
				t,
				api,
				caps: () => state.caps,
				guard: () => assertView(connection),
				errorBox,
				opStatus,
				storageKey: `batc.permissions.${connection.namespace}.${JSON.stringify([host, sid])}`,
				target: {
					host,
					session_id: sid
				},
				session: () => row,
				ready: () => readReady
			});
			permissionsSlot.append(permissions.box);
		}
		const manualSource = row.provenance === "manual" && state.caps?.artifacts?.capture?.manual_single_file;
		if (manualSource && !capture) {
			capture = manualCapture(`session.${JSON.stringify([host, sid])}`, {
				host,
				session_id: sid
			});
			captureSlot.append(capture);
		}
		if (capture) capture.hidden = !manualSource;
		composer.hidden = !managed;
		readonly.hidden = managed;
		renderPending();
		updateControls();
	};
	const loadObservation = async () => {
		const data = await api("GET", path);
		assertView(connection);
		applyObservation(data);
	};
	const loadMessages = async () => {
		const read = await api("GET", `${path}/messages?last_n=30`);
		assertView(connection);
		const items = read.messages.map((m) => h("div", { class: `msg ${m.role === "user" ? "user" : ""}` }, h("span", { class: "who" }, `${m.role || ""} · ${when(m.ts)}`), m.text || ""));
		msgs.replaceChildren(...items.length ? items : [h("p", { class: "muted" }, t("no_messages"))]);
	};
	const refresh = async (fromEvent = false) => {
		if (refreshInFlight) {
			await refreshInFlight;
			if (fromEvent) return refresh(true);
			return;
		}
		refreshInFlight = (async () => {
			try {
				await settleRefreshes([loadObservation(), loadMessages()]);
				await permissions?.refresh(fromEvent);
				readReady = true;
				updateControls();
				readError?.remove();
				readError = null;
			} catch (error) {
				readReady = false;
				updateControls();
				readError = errorBox(error);
				status.replaceChildren(readError);
				throw error;
			}
		})();
		try {
			await refreshInFlight;
		} finally {
			refreshInFlight = null;
		}
	};
	try {
		await settleRefreshes([refresh(), cps.load()]);
	} catch {}
	const retry = setInterval(() => {
		if (!readReady && !refreshInFlight) refresh().catch(() => {});
	}, 1e3);
	const reload = debounceRefresh(() => refresh(true), 500), reloadCps = debounceRefresh(cps.load, 500);
	const off = onEvents((ev) => {
		observations.changed(ev);
		return settleRefreshes([
			observationAffected("session", `${host}/${sid}`, ev) || ev.resource_type === "work_item" ? reload() : Promise.resolve(),
			ev.resource_type === "checkpoint" ? reloadCps() : Promise.resolve(),
			ev.resource_type === "operation" ? permissions?.refresh(true) : Promise.resolve()
		]);
	});
	return () => {
		clearInterval(retry);
		off();
	};
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
		const draft = attachmentDraft(`continue.${cp.checkpoint_id}`, instr, cp.artifacts || []);
		draft.bindFields({ agent });
		let expectedHead = null;
		const go = h("button", {
			class: "primary",
			onclick: async () => {
				if (!instr.value.trim()) return;
				go.disabled = true;
				try {
					if (!draft.ready() && !draft.pending()) throw new Error(t("attachments_not_ready"));
					if (state.caps?.artifacts && !expectedHead && !draft.pending()) throw new Error(t("source_unavailable"));
					const op = await draft.perform("checkpoint.continue", { checkpoint_id: cp.checkpoint_id }, {
						instructions: instr.value,
						agent: agent.value,
						...state.caps?.artifacts ? { artifacts: draft.refs() } : {}
					}, state.caps?.artifacts ? { expected_source_head_sha: expectedHead } : {}, `continue.${cp.checkpoint_id}`);
					out.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				} catch (e) {
					out.replaceChildren(errorBox(e));
				}
				go.disabled = false;
			}
		}, t("start_agent_work"));
		const form = h("div", { hidden: true }, confinementNote(host, agent), instr, draft.box, h("div", { class: "actions" }, agent, go), out);
		return h("div", { class: "row" }, h("div", { class: "grow" }, h("div", { class: "title" }, h("code", {}, cp.commit_sha.slice(0, 12)), " ", cp.branch || ""), h("div", { class: "muted" }, [
			when(epoch(cp.captured_at)),
			cp.actor,
			t("excerpt_count", { n: cp.excerpt_messages })
		].join(" · ")), cp.dirty ? h("div", { class: "error" }, t("dirty_warning", { n: cp.dirty })) : cp.dirty === null ? h("div", { class: "muted" }, t("dirty_unknown")) : null, preview && preview.head !== cp.commit_sha ? h("div", { class: "muted" }, t("source_advanced")) : null, form), h("button", {
			class: "secondary",
			disabled: !can || !mayStart,
			title: !can ? t("checkpoint_unavailable") : mayStart ? null : t("needs_start_scope"),
			onclick: async () => {
				form.hidden = !form.hidden;
				if (state.caps?.artifacts && !form.hidden && !expectedHead) try {
					expectedHead = (await api("GET", `/checkpoints/${cp.checkpoint_id}?live=true`)).source.head;
					if (!expectedHead) fill(out, h("p", { class: "error" }, t("source_unavailable")));
				} catch (e) {
					fill(out, errorBox(e));
				}
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
	const groups = new Map();
	for (const r of state.caps?.deploy_recipes || []) {
		const key = JSON.stringify([r.repository.toLowerCase(), r.environment]);
		if (!groups.has(key)) groups.set(key, []);
		groups.get(key).push(r);
	}
	const environments = [...groups.values()].map(environmentCard);
	main.append(h("h1", {}, t("nav_delivery")), ...environments.map((e) => e.card));
	let selectedMethod = "";
	let reviewedPreview = null;
	main.append(h("h2", {}, t("dep_pull_request")), h("div", { class: "filters delivery-controls" }, repo, num, h("button", {
		class: "secondary",
		onclick: () => load()
	}, t("load_pr"))), card);
	if (!repo.value && state.caps?.repositories?.length) repo.value = state.caps.repositories[0].repository;
	const load = async (flash = null, fromEvent = false) => {
		const opens = drawerOpens;
		const holdCard = () => card.querySelector(".drawer:not([hidden])") || fromEvent && holdRender(true, opens);
		sessionStorage.setItem("batc.repo", repo.value);
		sessionStorage.setItem("batc.pr", num.value);
		if (!repo.value || !/^\d+$/.test(num.value)) return;
		try {
			const query = new URLSearchParams();
			if (selectedMethod) query.set("method", selectedMethod);
			if (fromEvent) query.set("from_event", "true");
			const pr = (await api("GET", `/repositories/${repo.value}/pulls/${num.value}?${query}`)).pull_request;
			if (holdCard()) {
				idleReload = () => load(null, true);
				return;
			}
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
					disabled: blocked || !pr.merge.allowed || !may("merge") || !may("deploy") || !state.caps?.deploy_recipes?.find((c) => c.name === r.name)?.readiness?.ready,
					onclick: async () => {
						try {
							const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
							await run("delivery.merge_and_deploy", {
								target: { recipe: r.name },
								pre: {
									...pre,
									...deploymentPreview.preconditions
								}
							}, `merge_deploy.${pv.preview_id}.${r.name}`);
						} catch (e) {
							fill(status, errorBox(e));
						}
					}
				}, t("merge_and_deploy_to", { env: r.environment })));
				if (pr.merged && pr.merge_commit_sha) buttons.push(h("button", {
					class: "secondary",
					disabled: !may("deploy") || !state.caps?.deploy_recipes?.find((c) => c.name === r.name)?.readiness?.ready,
					onclick: async () => {
						try {
							const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
							const op = await submit("deployment.start", { recipe: r.name }, { source_sha: pr.merge_commit_sha }, deploymentPreview.preconditions, `deploy.${r.name}.${pr.merge_commit_sha}`);
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
			if (!holdCard()) fill(card, errorBox(e));
		}
	};
	const reload = async (fromEvent = true) => {
		await settleRefreshes([...environments.map((e) => e.load(fromEvent)), load(null, fromEvent)]);
	};
	await reload(false);
	return liveReload(reload, [
		"operation",
		"integration",
		"deployment",
		"deployment_environment"
	]);
}
function deploymentIdentity(identity, empty = "dep_no_version") {
	if (!identity?.source_sha && !identity?.artifact_id) return h("p", { class: "muted" }, t(empty));
	return h("div", { class: "deployment-identity" }, identity.source_sha ? h("code", {}, identity.source_sha) : null, identity.artifact_id ? h("p", {}, t("dep_artifact", { id: identity.artifact_id }), identity.artifact_digest ? [" · ", h("code", {}, identity.artifact_digest)] : null) : null);
}
function deploymentState(value) {
	return chip(t(`dep_state_${value || "unverified"}`), [
		"failed",
		"needs_attention",
		"uncertain"
	].includes(value) ? "bad" : value === "succeeded" ? "ok" : "warn");
}
function deploymentTime(value) {
	return value ? when(Number(value) * 1e3) : t("dep_not_observed");
}
function heldDetails(title, children, onOpen) {
	let counted = false;
	const details = h("details", {
		class: "row-details",
		ontoggle: () => {
			if (details.open !== counted) {
				counted = details.open;
				if (counted) {
					drawerOpens += 1;
					if (onOpen) onOpen();
				}
				setEditing(editing + (counted ? 1 : -1));
			}
		}
	}, h("summary", {}, title), ...children);
	details.closeHeld = () => {
		if (counted) {
			counted = false;
			setEditing(editing - 1);
		}
		details.open = false;
	};
	return details;
}
function deploymentReceipt(dep) {
	const body = h("div", {});
	let read = false;
	return heldDetails(t("dep_operation_details"), [body], async () => {
		if (read) return;
		read = true;
		try {
			const op = (await api("GET", `/operations/${dep.operation_id}`)).operation;
			const saved = op.external_refs?.deployment_id && op.external_refs.deployment_id !== dep.deployment_id ? (await api("GET", `/deployments/${op.external_refs.deployment_id}`)).deployment : dep;
			const values = [
				[t("dep_operation"), h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)],
				[t("dep_status"), opStatus(op)],
				[t("dep_run"), saved.run_id],
				[t("dep_attempt"), saved.run_attempt],
				[t("dep_error_code"), op.error_code || saved.error_code || saved.reconciliation_error]
			];
			fill(body, h("dl", { class: "kv" }, ...values.filter(([, v]) => v !== null && v !== void 0 && v !== "").flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, value)])), op.status_reason ? h("p", {}, op.status_reason) : null, ...(op.steps || []).map((s) => h("div", { class: "row" }, h("code", {}, s.name), h("code", {}, s.status))));
		} catch (e) {
			fill(body, errorBox(e));
			read = false;
		}
	});
}
function deploymentLimits(limits) {
	return h("div", { class: "deployment-limits" }, h("span", { class: "muted" }, t("dep_not_undone")), limits?.length ? h("ul", {}, ...limits.map((value) => h("li", {}, value))) : h("p", { class: "muted" }, t("dep_no_limits")));
}
function deploymentPreviewSummary(preview) {
	return h("p", {
		class: "muted",
		"data-testid": "deployment-preview-generation"
	}, t("dep_preview_generation", {
		env: preview.environment,
		generation: preview.environment_generation
	}));
}
function deploymentIntent(dep, kind, reload) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace
	};
	const out = h("div", { "aria-live": "polite" });
	const d = drawer();
	let busy = false, accepted = false, preview = null;
	const scope = `deployment.${kind}.${dep.deployment_id}`;
	const confirm = h("button", {
		class: kind === "rollback" ? "danger" : "primary",
		disabled: true,
		"data-testid": `deployment-${kind}-confirm`,
		onclick: async () => {
			if (busy || accepted || !preview) return;
			busy = true;
			confirm.disabled = true;
			try {
				assertConnection(connection);
				const action = kind === "rollback" ? "deployment.rollback" : "deployment.start";
				const params = kind === "rollback" ? { deployment_id: dep.deployment_id } : {
					source_sha: dep.identity.source_sha,
					retry_of: dep.deployment_id
				};
				let op = await submit(action, { recipe: dep.recipe }, params, preview.preconditions, scope);
				while (["accepted", "running"].includes(op.status) && d.box.isConnected && !d.box.hidden) {
					await sleep(1e3);
					assertConnection(connection);
					if (!d.box.isConnected || d.box.hidden) break;
					op = (await api("GET", `/operations/${op.operation_id}`)).operation;
				}
				if ([
					"DEPLOY_PREVIEW_REQUIRED",
					"ENVIRONMENT_CHANGED",
					"RECIPE_CHANGED"
				].includes(op.error_code)) {
					fill(out, h("p", { class: "note warn" }, t("dep_stale_preview")), deploymentReceipt({ operation_id: op.operation_id }));
					await refreshPreview();
				} else {
					accepted = true;
					fill(out, h("p", {}, opStatus(op), " · ", h("a", { href: `#/op/${op.operation_id}` }, t("dep_open_operation"))), deploymentReceipt({ operation_id: op.operation_id }));
				}
			} catch (e) {
				fill(out, h("p", { class: "error" }, t("dep_refused")), heldDetails(t("dep_operation_details"), [errorBox(e)]));
				if ([
					"DEPLOY_PREVIEW_REQUIRED",
					"ENVIRONMENT_CHANGED",
					"RECIPE_CHANGED"
				].includes(e.code)) {
					out.prepend(h("p", { class: "note warn" }, t("dep_stale_preview")));
					await refreshPreview();
				}
			} finally {
				busy = false;
				confirm.disabled = accepted || !preview?.readiness?.ready;
			}
		}
	}, t(kind === "rollback" ? "dep_confirm_rollback" : "dep_confirm_retry"));
	const previewBox = h("div", {});
	async function refreshPreview() {
		preview = null;
		confirm.disabled = true;
		try {
			assertConnection(connection);
			preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(dep.recipe)}`)).preview;
			fill(previewBox, deploymentPreviewSummary(preview), preview.readiness?.ready ? null : h("p", { class: "note warn" }, t("dep_missing_verification")));
			confirm.disabled = busy || accepted || !preview.readiness?.ready;
		} catch (e) {
			fill(previewBox, errorBox(e));
		}
	}
	fill(d.box, h("h3", {}, t(kind === "rollback" ? "dep_rollback_review" : "dep_retry_review")), deploymentIdentity(dep.identity), h("p", {}, `${dep.repository} · ${dep.environment}`), kind === "rollback" ? deploymentLimits(dep.rollback?.not_undone) : h("p", { class: "muted" }, t("dep_retry_only")), previewBox, out, h("div", { class: "actions" }, confirm, h("button", {
		class: "secondary",
		onclick: () => {
			d.box.querySelectorAll("details[open]").forEach((el) => el.closeHeld?.());
			d.close();
			reload();
		}
	}, t("close"))));
	return {
		button: h("button", {
			class: "secondary",
			"data-testid": `deployment-${kind}`,
			onclick: () => {
				if (!d.box.hidden) return;
				d.open();
				refreshPreview();
			}
		}, t(kind === "rollback" ? "dep_rollback" : "dep_retry", { sha: (dep.identity?.source_sha || "").slice(0, 8) })),
		box: d.box
	};
}
function deploymentRecord(dep, env, reload, compact = false) {
	if (!dep) return h("p", { class: "muted" }, t("dep_no_version"));
	const r = (state.caps?.deploy_recipes || []).find((r) => r.name === dep.recipe);
	dep = {
		...dep,
		repository: dep.repository || r?.repository || "",
		environment: dep.environment || r?.environment || env.environment || t("dep_no_version")
	};
	const canDeploy = Boolean(state.caps?.features?.deploy && r?.readiness?.ready && (state.caps?.actions || []).some((a) => a.action === "deployment.start" && a.allowed) && may("deploy"));
	const disabledReason = !may("deploy") ? "dep_needs_scope" : !r ? "dep_missing_recipe" : !r.readiness?.ready ? "dep_missing_verification" : "dep_disabled";
	const actions = [], drawers = [];
	if (!compact && dep.rollback_eligible && !dep.is_current) {
		const intent = deploymentIntent(dep, "rollback", reload);
		intent.button.disabled = !canDeploy || !(state.caps?.actions || []).some((a) => a.action === "deployment.rollback" && a.allowed);
		actions.push(intent.button);
		drawers.push(intent.box);
		if (intent.button.disabled) actions.push(h("span", { class: "muted" }, t(disabledReason)));
	}
	if (!compact && dep.state === "failed") {
		if (dep.provider_terminal && !dep.legacy && dep.identity?.source_sha) {
			const intent = deploymentIntent(dep, "retry", reload);
			intent.button.disabled = !canDeploy;
			actions.push(intent.button);
			drawers.push(intent.box);
			if (!canDeploy) actions.push(h("span", { class: "muted" }, t(disabledReason)));
		} else actions.push(h("span", { class: "muted" }, t(dep.provider_terminal ? "dep_retry_unavailable" : "dep_provider_pending")));
	}
	let rollbackReason = dep.rollback_reason;
	let providerUrl = null;
	try {
		const url = new URL(dep.provider_url);
		if (url.protocol === "https:") providerUrl = url.href;
	} catch {}
	if (rollbackReason === "ROLLBACK_ARTIFACT_UNAVAILABLE" && dep.identity?.artifact_expires_at && Date.parse(dep.identity.artifact_expires_at) <= Date.now()) rollbackReason = "ROLLBACK_ARTIFACT_EXPIRED";
	return h("div", {
		class: "deployment-record",
		"data-deployment": dep.deployment_id
	}, h("div", { class: "deployment-record-heading" }, deploymentState(dep.state), h("span", { class: "muted" }, dep.recipe)), deploymentIdentity(dep.identity), compact ? h("p", {}, h("a", { href: `#/op/${dep.operation_id}` }, t("dep_open_operation"))) : h("p", { class: "muted" }, `${dep.environment} · ${deploymentTime(dep.created_at)}`), dep.state === "superseded" ? h("p", {}, t("dep_superseded"), " ", env.desired ? h("a", { href: `#/op/${env.desired.operation_id}` }, t("dep_new_desired")) : null, " · ", providerUrl ? h("a", {
		href: providerUrl,
		target: "_blank",
		rel: "noopener"
	}, t("dep_provider_run")) : null) : null, dep.state === "needs_attention" || dep.reconciliation_error ? h("p", { class: "note warn" }, t("dep_attention")) : null, !compact && rollbackReason ? h("p", { class: "muted" }, t(`dep_${rollbackReason}`)) : null, !compact && dep.rollback_eligible && !dep.is_current ? deploymentLimits(dep.rollback?.not_undone) : null, actions.length ? h("div", { class: "actions" }, ...actions) : null, deploymentReceipt(dep), ...drawers);
}
function environmentCard(group) {
	const card = h("section", {
		class: "panel delivery-card environment-card",
		"data-environment": group[0].environment
	});
	const cursors = [null];
	let page = 0, next = null, loading = false, inFlight = null;
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	async function load(fromEvent = false) {
		if (inFlight) {
			await inFlight;
			if (fromEvent) return load(true);
			return;
		}
		const opens = drawerOpens;
		if (editing || fromEvent && typing()) {
			idleReload = () => load(true);
			return;
		}
		loading = true;
		inFlight = (async () => {
			try {
				assertView(connection);
				const query = new URLSearchParams({
					recipe: group[0].name,
					limit: "5"
				});
				if (cursors[page]) query.set("cursor", cursors[page]);
				const reads = await Promise.allSettled([api("GET", `/deployment-environments?recipe=${encodeURIComponent(group[0].name)}`), api("GET", `/deployment-environments/history?${query}`)]);
				assertView(connection);
				for (const read of reads) if (read.status === "rejected") throw read.reason;
				const [environment, history] = reads.map((read) => read.value);
				if (holdRender(fromEvent, opens) || editing) {
					idleReload = () => load(true);
					return;
				}
				const env = environment.environment;
				next = history.next_cursor;
				const observed = env.observed || env.current?.evidence?.runtime?.observed;
				const needs = env.attention || env.desired?.state === "needs_attention" || env.desired?.reconciliation_error || env.current?.state === "needs_attention" || env.current?.reconciliation_error;
				const previous = h("button", {
					class: "secondary",
					disabled: page === 0,
					"data-testid": "history-previous",
					onclick: () => {
						if (loading) return;
						previous.disabled = more.disabled = true;
						page -= 1;
						load();
					}
				}, t("dep_previous"));
				const more = h("button", {
					class: "secondary",
					disabled: !next,
					"data-testid": "history-next",
					onclick: () => {
						if (loading) return;
						previous.disabled = more.disabled = true;
						cursors[++page] = next;
						load();
					}
				}, t("dep_next"));
				const verified = env.last_verified;
				fill(card, h("div", { class: "deployment-card-heading" }, h("h2", {}, group[0].environment), needs ? chip(t("dep_attention"), "warn") : null), h("p", { class: "muted" }, group[0].repository, " · ", t("dep_generation", { generation: env.desired_generation })), needs ? h("p", { class: "note warn" }, t(env.attention === "ENVIRONMENT_VERSION_DRIFT" ? "dep_drift" : "dep_attention_help")) : null, h("div", { class: "deployment-versions" }, h("div", {}, h("h3", {}, t("dep_desired")), deploymentRecord(env.desired, env, load, true)), h("div", {}, h("h3", {}, t("dep_observed")), deploymentIdentity(observed), h("p", { class: "muted" }, t("dep_observed_at", { time: deploymentTime(observed?.observed_at || env.current?.evidence?.runtime?.checked_at) })), env.current?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(env.current.evidence.runtime)) : null)), h("div", { class: "deployment-last-verified" }, h("h3", {}, t("dep_last_verified")), deploymentIdentity(verified?.identity), h("p", { class: "muted" }, t("dep_verified_at", { time: deploymentTime(verified?.evidence?.runtime?.checked_at) })), verified?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(verified.evidence.runtime)) : null, verified ? deploymentReceipt(verified) : null), h("h3", {}, t("dep_history")), h("div", { "data-testid": "deployment-history" }, ...history.items.length ? history.items.map((dep) => deploymentRecord(dep, env, load)) : [h("p", { class: "muted" }, t("dep_no_history"))]), !history.items.length && group.every((r) => !r.rollback?.supported) ? h("p", { class: "muted" }, t("dep_ROLLBACK_UNSUPPORTED")) : null, h("div", { class: "actions deployment-pagination" }, previous, h("span", { class: "muted" }, t("dep_page", { page: page + 1 })), more));
			} catch (e) {
				if (["CONNECTION_CHANGED", "VIEW_CHANGED"].includes(e.code)) return;
				const failure = errorBox(e);
				if (!holdRender(fromEvent, opens) && !editing) fill(card, failure);
			}
		})();
		try {
			await inFlight;
		} finally {
			loading = false;
			inFlight = null;
		}
	}
	return {
		card,
		load
	};
}
function runtimeSummary(evidence) {
	return t(evidence.version_checked ? evidence.health_checked ? "dep_version_health" : "dep_version_only" : "dep_health_only");
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
						const preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(op.target.recipe)}`)).preview;
						const o = await submit("deployment.start", { recipe: op.target.recipe }, { source_sha: refs.merged_sha }, preview.preconditions, `deploy.${op.target.recipe}.${refs.merged_sha}`);
						location.hash = `#/op/${o.operation_id}`;
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("retry_deploy")) : null;
			const needsConfirm = op.action === "checkpoint.continue" && ["SOURCE_MOVED", "SOURCE_UNAVAILABLE"].includes(op.error_code);
			const resume = op.status === "needs_attention" && !needsConfirm ? h("button", {
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
			const confirmSource = op.status === "needs_attention" && needsConfirm ? h("button", {
				class: "primary",
				onclick: async () => {
					const connection = {
						epoch: state.epoch,
						namespace: state.namespace,
						generation
					};
					try {
						const seen = (await api("GET", `/checkpoints/${op.target.checkpoint_id}?live=true`)).source.head;
						assertView(connection);
						if (!seen) throw new Error(t("source_unavailable"));
						await submit("checkpoint.continue.revalidate", { operation_id: id }, { observed_source_head_sha: seen }, { expected_input_manifest_digest: refs.input_manifest_digest }, `revalidate.${id}.${seen}`);
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("confirm_source")) : null;
			const materialized = refs.materializations || op.result?.materializations || [];
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
			fill(panel, h("h1", {}, op.action), h("p", { class: "op-status" }, opStatus(op), " ", op.error_code ? chip(op.error_code, "bad") : null), ...linked?.length ? [linkedItems(linked)] : [], h("dl", { class: "kv" }, h("dt", {}, t("actor")), h("dd", {}, `${op.actor} (${op.entry})`), h("dt", {}, t("created")), h("dd", {}, when(epoch(op.created_at))), op.status_reason ? [h("dt", {}, t("reason")), h("dd", {}, op.status_reason)] : null, h("dt", {}, "Target"), h("dd", {}, h("code", {}, JSON.stringify(op.target))), Object.keys(refs).length ? [h("dt", {}, "Refs"), h("dd", {}, h("code", {}, JSON.stringify(refs)))] : null, op.result ? [h("dt", {}, "Result"), h("dd", {}, h("code", {}, JSON.stringify(op.result)))] : null), ...receipts || [], ...materialized.length ? [h("h2", {}, t("materializations")), ...materialized.map((m) => h("div", { class: "row" }, h("div", { class: "grow" }, `${m.artifact_id} · r${m.revision}`, h("div", { class: "muted" }, m.managed_path)), chip(t(`material_${m.state}`), m.state === "verified" ? "ok" : "")))] : [], ...cleanupReceipts?.length ? [h("h2", {}, t("cleanup_open_receipts")), ...cleanupReceipts.map((r) => h("details", { class: "row-details" }, h("summary", {}, r.resource_id, " · ", t("cleanup_receipt_" + r.status)), h("pre", { class: "pre" }, JSON.stringify(r, null, 2))))] : [], ...op.action === "integration.apply" ? [repairControl(op)] : [], (op.result?.merge || op.result || refs.merge_receipt)?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: (op.result?.merge || op.result || refs.merge_receipt).other_commits_count })) : null, refs.write_acknowledged && refs.verification_pending ? h("p", { class: "note warn" }, t("metadata_pending")) : null, h("h2", {}, t("steps")), ...op.steps.map((s) => h("div", { class: "row" }, h("div", { class: "grow" }, s.name), h("span", { class: `status-${s.status}` }, s.status), s.error ? chip(s.error.code || t("error"), "bad") : null)), h("div", { class: "actions" }, opened, ["artifact.capture.managed", "artifact.accept"].includes(op.action) && op.status === "succeeded" && /^art_[0-9a-f]{32}$/.test(op.result?.artifact_id) && Number.isSafeInteger(op.result?.revision) && op.result.revision > 0 ? h("a", { href: `#/artifact-review/artifact/${op.result.artifact_id}/${op.result.revision}` }, t("ar_review_title")) : null, state.caps?.artifacts?.capture?.managed_single_file && managedCaptureExecution(op) ? h("a", { href: `#/artifact-review/operation/${op.operation_id}` }, t("ar_open")) : null, confirmSource, resume, retry, cancel));
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
async function nativeTransition(kind) {
	if (state.nativeBusy && kind !== "disconnect") return;
	const attempt = ++state.nativeAttempt;
	const previousOnline = state.online;
	const previousToken = state.token;
	state.nativeBusy = true;
	state.epoch++;
	state.online = false;
	state.connectionError = null;
	state.connectionNotice = null;
	try {
		if (kind === "disconnect" || kind === "reload" || kind === "forget") {
			disconnect();
			if (kind === "disconnect") await nativeDisconnect();
			else if (kind === "reload") await nativeReloadConfiguration();
			else await nativeForgetCredential();
			if (attempt === state.nativeAttempt) state.connectionNotice = t(kind === "forget" ? "desktop_forgotten" : kind === "reload" ? "desktop_reloaded" : "desktop_disconnected");
		} else {
			const status = await nativeStatus();
			if (attempt !== state.nativeAttempt) return;
			const caps = kind === "enroll" ? await nativeEnroll() : await nativeConnect();
			if (attempt !== state.nativeAttempt) return;
			if (!caps) {
				state.online = previousOnline;
				state.connectionNotice = t("desktop_enrollment_cancelled");
			} else {
				state.token = "native-credential";
				try {
					await activate(caps, status.endpoint);
				} catch (error) {
					if (attempt === state.nativeAttempt) {
						await nativeDisconnect();
						disconnect();
					}
					throw error;
				}
				if (kind === "connect" && attempt === state.nativeAttempt) location.hash = "#/home";
			}
		}
	} catch (error) {
		if (attempt !== state.nativeAttempt) return;
		state.connectionError = error;
		if (state.token === previousToken) state.online = previousOnline;
	} finally {
		if (attempt === state.nativeAttempt) {
			state.nativeBusy = false;
			await route();
		}
	}
}
async function viewNativeSettings(main) {
	const mine = generation;
	const info = h("div", { "aria-live": "polite" });
	const details = h("dl", { class: "kv" });
	const help = h("p", { class: "muted" }, t("desktop_credential_help"));
	const platform = h("p", { class: "muted" });
	const fleetRoot = h("div");
	const controls = [];
	const action = (kind, label, cls = "secondary") => {
		const button = h("button", {
			class: cls,
			disabled: true,
			onclick: () => {
				for (const control of controls) control.disabled = true;
				if (kind === "connect" || kind === "enroll") leave.disabled = false;
				info.textContent = t("desktop_connecting");
				return nativeTransition(kind);
			}
		}, t(label));
		controls.push(button);
		return button;
	};
	const connect = action("connect", "connect", "primary");
	const enroll = action("enroll", "desktop_add_credential");
	const reload = action("reload", "desktop_reload_configuration");
	const forget = action("forget", "desktop_forget_credential");
	const leave = action("disconnect", "disconnect");
	const actions = h("div", { class: "actions" }, connect, enroll, reload, leave);
	const saved = h("div", {}, h("p", { class: "muted" }, t("desktop_forget_help")), forget);
	main.append(h("h1", {}, t("nav_settings")), h("section", {
		class: "panel native-connection",
		"aria-label": t("desktop_connection")
	}, h("h2", {}, t("desktop_connection")), details, help, platform, actions, info, saved), h("div", { class: "panel" }, h("h2", {}, t("desktop_local")), h("p", { class: "note" }, t("desktop_dashboard_only"))), fleetRoot);
	const showInfo = () => {
		info.replaceChildren();
		if (state.caps) info.append(h("p", {}, t("connected_as", {
			actor: state.caps.actor,
			scopes: state.caps.scopes.join(", ")
		})));
		if (state.connectionNotice) info.append(h("p", {}, state.connectionNotice));
		if (state.connectionError) info.append(errorBox(state.connectionError));
		if (state.nativeBusy) info.append(h("p", {}, t("desktop_connecting")));
	};
	showInfo();
	try {
		const status = await nativeStatus();
		if (mine !== generation || !main.contains(details)) return;
		const row = (label, value) => {
			if (value) details.append(h("dt", {}, t(label)), h("dd", {}, value));
		};
		row("desktop_endpoint", status.endpoint || t("desktop_config_needed"));
		row("desktop_expected_actor", status.expected_actor);
		row("desktop_configuration_file", status.configuration_file);
		if (status.credential_source) row("desktop_credential_source", t("desktop_source_" + status.credential_source));
		if (status.error) info.append(errorBox(new Error(status.error)));
		else if (!status.credential_available) info.append(h("p", {}, t("desktop_credential_missing")));
		platform.textContent = status.enrollment_supported === true ? t("desktop_enrollment_help") : status.enrollment_supported === false ? t("desktop_enrollment_unsupported") : "";
		connect.disabled = state.nativeBusy || !!status.error || !status.credential_available;
		enroll.hidden = status.enrollment_supported !== true;
		enroll.textContent = t(status.credential_saved ? "desktop_replace_credential" : "desktop_add_credential");
		enroll.disabled = state.nativeBusy || !status.endpoint || !status.expected_actor;
		enroll.className = status.credential_available ? "secondary" : "primary";
		if (!status.credential_available) connect.className = "secondary";
		reload.hidden = !status.configuration_reload;
		reload.disabled = state.nativeBusy || !status.configuration_reload;
		leave.disabled = !state.token && !state.nativeBusy;
		saved.hidden = !status.credential_saved;
		forget.disabled = state.nativeBusy || !status.credential_saved;
	} catch (error) {
		if (mine === generation) info.append(errorBox(error));
	}
	if (mine !== generation) return;
	return mountFleet(fleetRoot, {
		h,
		t
	});
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
function liveReload(fn, kinds, prepare = null) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const later = debounceRefresh(async () => {
		let preparedAt = 0;
		const prepareNow = async () => {
			if (prepare) {
				await prepare();
				preparedAt = Date.now();
			}
		};
		await prepareNow();
		for (;;) {
			while (editing || typing()) {
				assertView(connection);
				await sleep(100);
				if (prepare && Date.now() - preparedAt >= 1e3) await prepareNow();
			}
			assertView(connection);
			const opened = drawerOpens;
			await fn(true);
			assertView(connection);
			if (!editing && !typing() && drawerOpens === opened) return;
		}
	}, 500);
	return onEvents((ev) => {
		if (typeof kinds === "function" ? kinds(ev) : kinds.includes(ev.resource_type)) return later();
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
	if (l.kind === "task") return h("span", {}, observationLink("execution", l.ref), " ", x.project, " · ", x.state);
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
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	let mutable = true;
	const archiveLocks = new Map();
	const blocked = h("p", {
		class: "note warn",
		hidden: true
	}, t("parent_archived"));
	main.append(blocked);
	const requireMutable = () => {
		assertView(connection);
		if (!mutable) throw new ApiError(409, "ITEM_ARCHIVED", t("parent_archived"));
	};
	const refreshSafety = async () => {
		try {
			const data = await api("GET", `/work-items/${wid}`);
			assertView(connection);
			rememberObservation("work_item", wid, data, itemDependencies(data));
			mutable = !data.work_item.archived && !data.project.archived;
			blocked.hidden = mutable;
			if (!mutable) {
				for (const button of panel.querySelectorAll("button")) if (button.getAttribute("aria-label") !== t("more")) {
					if (!archiveLocks.has(button)) archiveLocks.set(button, button.disabled);
					button.disabled = true;
				}
				for (const control of panel.querySelectorAll("select,input[type=checkbox]")) {
					if (!archiveLocks.has(control)) archiveLocks.set(control, control.disabled);
					control.disabled = true;
				}
			} else {
				for (const [control, disabled] of archiveLocks) control.disabled = disabled;
				archiveLocks.clear();
			}
		} catch (error) {
			fill(notice, errorBox(error));
			throw error;
		}
	};
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
		rememberObservation("work_item", wid, data, itemDependencies(data));
		if (holdRender(fromEvent, opens)) {
			idleReload = () => render(true);
			return;
		}
		freshPage();
		const w = data.work_item, c = w.completion;
		const live = mutable = !w.archived && !data.project.archived;
		blocked.hidden = live;
		const pre = { expected_version: w.version };
		const update = (params, scope) => {
			requireMutable();
			return change(notice, "work_item.update", { work_item_id: wid }, params, pre, scope);
		};
		const decide = async (action, scope) => {
			requireMutable();
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
		const attachment = attachmentDraft(`wi.edit.${wid}`, f.request, v.attachments || [], true);
		attachment.bindFields(f);
		const d = drawer(h("label", {}, t("title")), f.title, h("label", {}, t("goal")), f.goal, h("label", {}, t("request")), f.request, h("label", {}, t("acceptance")), f.acceptance, attachment.box, h("div", { class: "actions" }, h("button", {
			class: "primary",
			onclick: async () => {
				const params = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, k === "title" ? el.value.trim() : el.value]).filter(([k, v]) => v !== w[k]));
				if (!attachment.ready()) {
					fill(notice, h("p", { class: "error" }, t("attachments_not_ready")));
					return;
				}
				if (JSON.stringify(attachment.refs()) !== JSON.stringify(w.attachments || [])) params.attachments = attachment.refs();
				if (!Object.keys(params).length && !attachment.pending()) {
					d.close();
					return;
				}
				let op;
				try {
					requireMutable();
					op = await attachment.perform("work_item.update", { work_item_id: wid }, params, pre, `wi.edit.${wid}`);
				} catch (e) {
					fill(notice, errorBox(e));
					if (STALE.includes(e.code)) {
						draft = params;
						render();
					}
					return;
				}
				const ok = op.status === "succeeded";
				if (!ok) fill(notice, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
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
			requireMutable();
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
	return liveReload(render, (event) => observationAffected("work_item", wid, event), refreshSafety);
}
function continueFrom(w, checkpointId, notice) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const instr = h("textarea", {}, [
		w.title,
		w.goal,
		w.request && `${t("request")}:\n${w.request}`,
		w.acceptance && `${t("acceptance")}:\n${w.acceptance}`,
		w.steps.length ? `${t("steps_title")}:\n${w.steps.map((s) => `- [${s.done ? "x" : " "}] ${s.text}`).join("\n")}` : ""
	].filter(Boolean).join("\n\n"));
	const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const out = h("div", {});
	const draft = attachmentDraft(`continue.${checkpointId}.${w.work_item_id}`, instr, (w.attachments || []).filter((x) => x.role === "input"));
	draft.bindFields({ agent });
	let expectedHead = null;
	const go = h("button", {
		class: "primary",
		onclick: async () => {
			go.disabled = true;
			let op;
			try {
				if (!draft.ready() && !draft.pending()) throw new Error(t("attachments_not_ready"));
				if (state.caps?.artifacts && !expectedHead && !draft.pending()) throw new Error(t("source_unavailable"));
				op = await draft.perform("checkpoint.continue", { checkpoint_id: checkpointId }, {
					instructions: instr.value,
					agent: agent.value,
					...state.caps?.artifacts ? {
						artifacts: draft.refs(),
						work_item_id: w.work_item_id
					} : {}
				}, state.caps?.artifacts ? {
					expected_source_head_sha: expectedHead,
					expected_work_item_fingerprint: w.completion.fingerprint
				} : {}, `continue.${checkpointId}`);
			} catch (e) {
				fill(out, errorBox(e));
				go.disabled = false;
				return;
			}
			assertView(connection);
			fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
			if (TERMINAL.includes(op.status) && op.status !== "succeeded") return;
			if (!state.caps?.artifacts) {
				if (await change(notice, "work_item.link", { work_item_id: w.work_item_id }, {
					kind: "operation",
					ref: op.operation_id
				}, {}, `wi.link.${w.work_item_id}.${op.operation_id}`)) out.append(" · ", t("linked_back"));
			} else out.append(" · ", t("linked_back"));
		}
	}, t("start_agent_work"));
	const note = confinementNote(w.links?.find((l) => l.ref === checkpointId)?.target?.host, agent);
	api("GET", `/checkpoints/${encodeURIComponent(checkpointId)}`).then((x) => note.setHost(x.checkpoint.host)).catch(() => {});
	const d = drawer(note, instr, draft.box, h("div", { class: "actions" }, agent, go), out);
	const why = !may("start") ? t("needs_start_scope") : !may("manage") ? t("needs_manage_scope") : null;
	return h("div", { class: "grow" }, h("button", {
		class: "secondary",
		disabled: Boolean(why),
		title: why,
		onclick: async () => {
			d.toggle.click();
			if (state.caps?.artifacts && !expectedHead) try {
				expectedHead = (await api("GET", `/checkpoints/${checkpointId}?live=true`)).source.head;
			} catch (e) {
				fill(out, errorBox(e));
			}
		}
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
	const intentKey = `batc.cleanup.intent.${connection.namespace}`;
	const readStored = (key) => {
		try {
			return JSON.parse(localStorage.getItem(key) || sessionStorage.getItem(key) || "null");
		} catch {
			return null;
		}
	};
	const persist = (key, value) => {
		assertView(connection);
		try {
			for (const storage of [localStorage, sessionStorage]) if (value === null) storage.removeItem(key);
			else storage.setItem(key, JSON.stringify(value));
		} catch (error) {
			if (error.code) throw error;
		}
	};
	const stored = readStored(draftKey) || {};
	const choices = ["item", "task"].includes(section) && stored.id !== ident ? {
		discard_uncommitted: [],
		release_undelivered: []
	} : stored.choices || {
		discard_uncommitted: [],
		release_undelivered: []
	};
	const pending = readStored(pendingKey);
	let intent = readStored(intentKey);
	if (intent) {
		const request = intent.request;
		const valid = request?.action === "cleanup.apply" && request.target?.preview_id === pending?.preview_id && request.params?.preview_token === pending?.preview_token && request.preconditions?.preview_fingerprint === pending?.fingerprint && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200 && pending;
		intent = {
			key: valid ? intent.key : null,
			request: valid ? {
				action: "cleanup.apply",
				target: { preview_id: pending.preview_id },
				params: { preview_token: pending.preview_token },
				preconditions: { preview_fingerprint: pending.fingerprint }
			} : null,
			operation_id: typeof intent.operation_id === "string" && /^op_[0-9a-f]{32}$/.test(intent.operation_id) ? intent.operation_id : null,
			refused: valid && [
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_EXPIRED",
				"PREVIEW_MISMATCH",
				"PREVIEW_BLOCKED"
			].includes(intent.refused) ? intent.refused : null
		};
	}
	let operation = null, operationRead = null, submission = null, readFailed = false;
	const supportsTask = state.caps?.features?.cleanup_task === true;
	const kind = h("select", { "aria-label": t("cleanup_target") }, ...[
		"work_item",
		"checkpoint",
		"integration",
		"host",
		...supportsTask || pending?.target?.kind === "task" ? ["task"] : []
	].map((k) => h("option", { value: k }, t("cleanup_target_" + k))));
	kind.value = section === "item" ? "work_item" : section === "task" && supportsTask ? "task" : stored.kind || "host";
	const targetId = h("input", {
		value: ["item", "task"].includes(section) ? ident : stored.id || "",
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
		const eligible = item.proven && item.kind === "worktree" && (!item.task_owned || item.task_cleanup?.eligible === true);
		return h("article", { class: "cleanup-resource" }, h("div", { class: "row" }, h("strong", { class: "grow" }, t("cleanup_kind_" + item.kind)), chip(t("cleanup_decision_" + item.decision), item.decision === "reclaim" ? "ok" : "")), h("div", { class: "cleanup-binding" }, item.host || "", " ", item.path || item.ref || item.resource_id), item.observation?.head ? h("p", { class: "muted" }, t("cleanup_commit_kept"), " ", h("code", {}, item.observation.head)) : null, item.delivery && !item.delivery.delivered ? h("p", { class: "note warn" }, t("cleanup_not_delivered")) : null, ...(item.reasons || []).map((r) => h("div", { class: "cleanup-reason" }, h("code", {}, r.code), " · ", t("cleanup_reason_" + r.code))), ...(item.overridden_reasons || []).map((r) => h("p", { class: "muted" }, t("cleanup_choice_" + r.code))), item.steps?.length ? h("p", {}, t("cleanup_plan"), ": ", item.steps.map((x) => t("cleanup_step_" + x)).join(" → ")) : null, eligible && codes.includes("RESULTS_NOT_DELIVERED") ? choice(item, "release_undelivered", t("cleanup_release")) : null, eligible && !item.task_owned && codes.includes("UNCOMMITTED_CHANGES") ? choice(item, "discard_uncommitted", t("cleanup_discard")) : null, h("details", {}, h("summary", {}, t("cleanup_evidence")), h("pre", { class: "pre" }, JSON.stringify({
			resource_id: item.resource_id,
			original_ids: item.original_ids,
			reasons: item.reasons,
			consumers: item.consumers,
			task_cleanup: item.task_cleanup,
			delivery: item.delivery,
			manifest: item.observation?.manifest
		}, null, 2))));
	}
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => {
			apply.disabled = busy || readFailed || Boolean(intent?.operation_id) || !doc?.ready || !may("cleanup") || !reviewed.checked;
		}
	});
	function acceptCleanup(op) {
		assertView(connection);
		if (!intent || !/^op_[0-9a-f]{32}$/.test(op?.operation_id) || op.action !== "cleanup.apply" || op.actor !== state.caps.actor || op.idempotency_key !== intent.key || !intent.request || op.target?.preview_id !== intent.request.target.preview_id || op.params?.preview_token !== intent.request.params.preview_token || op.preconditions?.preview_fingerprint !== intent.request.preconditions.preview_fingerprint || intent.operation_id && intent.operation_id !== op.operation_id) throw new Error(t("cleanup_invalid_result"));
		operation = op;
		intent.operation_id = op.operation_id;
		persist(intentKey, intent);
		readFailed = false;
		fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, t("cleanup_open_receipts")), ...(op.result?.items || []).map((r) => h("p", {}, h("code", {}, r.resource_id), " · ", t("cleanup_receipt_" + r.status))));
		cleanupControls();
	}
	function cleanupControls() {
		const fixed = Boolean(intent || pendingRequest);
		kind.disabled = targetId.disabled = children.disabled = busy || fixed;
		previewButton.disabled = busy || fixed || section === "task" && !supportsTask;
		apply.hidden = Boolean(intent?.operation_id || intent?.refused);
		apply.disabled = busy || readFailed || Boolean(intent && !intent.request) || !doc?.ready || !reviewed.checked || !may("cleanup");
		check.hidden = !intent?.operation_id;
		check.disabled = busy || Boolean(operationRead);
		another.hidden = !(TERMINAL.includes(operation?.status) || intent?.refused);
		another.disabled = busy || readFailed || Boolean(operationRead);
	}
	async function refreshCleanup(fresh = false) {
		if (submission) {
			await submission;
			assertView(connection);
		}
		if (operationRead) {
			await operationRead;
			if (fresh) return refreshCleanup(true);
			return;
		}
		if (!intent?.operation_id) return;
		operationRead = (async () => {
			acceptCleanup((await api("GET", `/operations/${intent.operation_id}`)).operation);
		})();
		cleanupControls();
		try {
			await operationRead;
		} catch (e) {
			assertView(connection);
			readFailed = true;
			fill(status, errorBox(e), h("a", { href: `#/op/${intent.operation_id}` }, t("cleanup_open_receipts")));
			throw e;
		} finally {
			operationRead = null;
			cleanupControls();
		}
	}
	const check = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => refreshCleanup(true).catch(() => {})
	}, t("cleanup_check"));
	const another = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => {
			assertView(connection);
			if (busy || readFailed || operationRead || !(TERMINAL.includes(operation?.status) || intent?.refused)) return;
			intent = operation = doc = null;
			pendingRequest = false;
			persist(intentKey, null);
			persist(pendingKey, null);
			reviewed.checked = false;
			previewOut.replaceChildren();
			status.replaceChildren();
			cleanupControls();
		}
	}, t("cleanup_new"));
	const apply = h("button", {
		class: "primary",
		disabled: true,
		onclick: async () => {
			if (busy || readFailed || !doc || !reviewed.checked || intent?.operation_id || intent?.refused || intent && !intent.request) return;
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
			let finish;
			submission = new Promise((resolve) => {
				finish = resolve;
			});
			try {
				if (!intent) {
					const request = {
						action: "cleanup.apply",
						target: { preview_id: reviewedDoc.preview_id },
						params: { preview_token: reviewedDoc.preview_token },
						preconditions: { preview_fingerprint: reviewedDoc.fingerprint }
					};
					intent = {
						request,
						key: await keyFor(await draftId("cleanup.apply", request), connection),
						operation_id: null
					};
					persist(intentKey, intent);
				}
				const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
				assertView(connection);
				acceptCleanup(data.operation);
				await loadHistory();
				await loadRetained();
			} catch (e) {
				if (connection.epoch !== state.epoch || connection.namespace !== state.namespace || connection.generation !== generation) return;
				if (intent && !intent.operation_id && e.status >= 400 && e.status < 500 && [
					"PREVIEW_TOKEN_INVALID",
					"PREVIEW_EXPIRED",
					"PREVIEW_MISMATCH",
					"PREVIEW_BLOCKED"
				].includes(e.code)) {
					intent.refused = e.code;
					persist(intentKey, intent);
				}
				fill(status, errorBox(e), h("p", {}, t(intent?.refused ? "cleanup_repreview" : "cleanup_retry_same")));
			} finally {
				busy = false;
				finish();
				submission = null;
				if (connection.epoch === state.epoch && connection.generation === generation) cleanupControls();
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
				host: "host",
				task: "task_id"
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
			host: "host",
			task: "task_id"
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
			const rows = (result.tombstones || []).map((x) => h("article", { class: "cleanup-resource" }, h("a", { href: `#/cleanup/resource/${x.resource_id}` }, t("cleanup_kind_" + x.kind)), h("div", { class: "cleanup-binding" }, x.host, " ", x.path || x.ref || ""), h("p", { class: "muted" }, x.actor, " · ", when(x.cleaned_at * 1e3)), h("p", {}, t({
				reviewed_cleanup: "cleanup_reason_reviewed",
				task_lifecycle: "cleanup_reason_automatic",
				historical_task_cleanup: "cleanup_reason_historical"
			}[x.reason] || "cleanup_reason_recorded")), ...(x.pull_requests || []).map((pr) => h("p", {}, `${pr.repository} #${pr.pull_number}`))));
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
	main.append(h("h1", {}, t("nav_cleanup")), h("p", { class: "muted" }, t("cleanup_intro")), section === "task" || supportsTask ? h("p", { class: "muted" }, t("cleanup_task_help")) : null);
	if (section === "resource") {
		try {
			const data = await api("GET", `/cleanup-tombstones/${encodeURIComponent(ident)}`);
			main.append(h("a", { href: "#/cleanup" }, t("nav_cleanup")), resourceRow(data.tombstone), h("h2", {}, t("cleanup_open_receipts")), h("pre", { class: "panel pre" }, JSON.stringify(data.receipts, null, 2)));
		} catch (e) {
			main.append(errorBox(e));
		}
		return;
	}
	main.append(h("div", { class: "panel" }, h("h2", {}, t("cleanup_target")), h("div", { class: "filters" }, kind, targetId), childrenLabel, h("div", { class: "actions" }, previewButton)), previewOut, h("div", { class: "panel" }, h("label", { class: "cleanup-choice" }, reviewed, t("cleanup_reviewed")), !may("cleanup") ? h("p", { class: "muted" }, t("cleanup_scope")) : null, h("div", { class: "actions" }, apply, check, another), status), h("h2", {}, t("cleanup_history")), h("div", { class: "panel" }, h("form", {
		class: "filters",
		onsubmit: (e) => {
			e.preventDefault();
			loadHistory();
		}
	}, search, h("button", {
		class: "secondary",
		type: "submit"
	}, t("cleanup_search_button"))), historyOut), h("h2", {}, t("cleanup_retained")), h("p", { class: "muted" }, t("cleanup_retained_help")), h("div", { class: "panel" }, retainedOut));
	cleanupControls();
	await loadHistory();
	await loadRetained();
	try {
		await refreshCleanup();
	} catch {}
	const refresh = debounceRefresh(() => settleRefreshes([
		loadHistory(),
		loadRetained(),
		refreshCleanup(true)
	]), 500);
	return onEvents((ev) => {
		if (["cleanup", "operation"].includes(ev.resource_type)) return refresh();
	});
}
async function viewApprovals(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = approvalsPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		storageKey: `batc.approvals.${connection.namespace}`
	});
	main.append(h("a", { href: "#/sessions" }, t("sessions_title")), h("h1", {}, t("bulk_title")), panel.box);
	try {
		await panel.refresh();
	} catch {}
	return onEvents((event) => event.resource_type === "operation" ? panel.refresh(true) : panel.update());
}
async function viewStart(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = sessionStartPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		storageKey: `batc.start.${connection.namespace}`
	});
	main.append(h("a", { href: "#/sessions" }, t("nav_sessions")), h("h1", {}, t("start_title_page")), h("p", { class: "muted" }, t("start_intro")), panel.box);
	try {
		await panel.init();
	} catch {}
	assertView(connection);
	return onEvents((ev) => {
		if ([
			"operation",
			"host",
			"session"
		].includes(ev.resource_type)) return panel.refresh(true);
	});
}
async function viewArtifactReview(main, kind, first, second) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const context = kind === "session" ? {
		kind,
		host: first,
		session_id: second
	} : kind === "task" ? {
		kind,
		task_id: first
	} : kind === "operation" ? {
		kind,
		operation_id: first
	} : kind === "artifact" ? {
		kind,
		artifact_id: first,
		revision: Number(second)
	} : { kind: "catalog" };
	return mountArtifactReview({
		main,
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		onEvents,
		errorBox,
		opStatus,
		context,
		storageKey: `batc.artifact-review.${connection.namespace}.${JSON.stringify(context)}`
	});
}
var NAV = [
	["home", "nav_home"],
	["projects", "nav_projects"],
	["sessions", "nav_sessions"],
	["artifact-review", "ar_nav"],
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
		approvals: viewApprovals,
		delivery: viewDelivery,
		operations: viewOperations,
		session: viewSession,
		start: viewStart,
		op: viewOperation,
		settings: viewSettings,
		"artifact-review": viewArtifactReview,
		host: viewHostDiscovery,
		task: (main, id) => viewObservedResource(main, "execution", id),
		worktree: (main, id) => viewObservedResource(main, "worktree", id)
	}[name] || viewHome)(main, ...rest);
	if (mine !== generation) {
		if (off) off();
		return;
	}
	teardown = off || null;
	state.viewReady = true;
}
async function start() {
	window.addEventListener("hashchange", route);
	if (nativeDesktop) {
		clearToken();
		const attempt = ++state.nativeAttempt;
		try {
			const status = await nativeStatus();
			if (!status.error && status.credential_available) {
				state.nativeBusy = true;
				route().catch(() => {});
				const caps = await nativeConnect();
				if (attempt === state.nativeAttempt) {
					state.token = "native-credential";
					await activate(caps, status.endpoint);
				}
			}
		} catch (error) {
			if (attempt === state.nativeAttempt) {
				disconnect();
				state.connectionError = error;
				await nativeDisconnect().catch(() => {});
			}
		} finally {
			if (attempt === state.nativeAttempt) state.nativeBusy = false;
		}
	} else {
		state.token = loadToken();
		if (state.token) try {
			await activate(await api("GET", "/capabilities"));
		} catch {
			state.token = null;
		}
	}
	await route();
	streamEvents();
}
start();
//#endregion
