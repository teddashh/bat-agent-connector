// Display labels only. Logic and CSS never key on these strings (machine enums come from /api/v1).
const STRINGS = {
  "zh-TW": {
    nav_home: "待處理", nav_sessions: "Sessions", nav_delivery: "成果與 GitHub", nav_operations: "操作紀錄",
    nav_settings: "連線",
    tab_needs_you: "需要你處理", tab_to_confirm: "待確認",
    empty_needs_you: "目前沒有需要你處理的項目。", empty_to_confirm: "沒有等待確認的操作。",
    stale: "資料過期", stale_reason_host_unreachable: "主機連不上", stale_reason_host_not_refreshed: "很久沒更新",
    stale_reason_not_enumerated: "上次列舉沒有出現", stale_reason_gone: "已不存在", stale_reason_never_observed: "尚未觀測",
    read_only: "API 唯讀", managed: "Connector 管理",
    provenance_manual: "人工建立（BAT）", provenance_connector_managed: "Connector 建立", provenance_unknown: "來源不明",
    state_streaming: "執行中", state_loaded: "已載入", state_unloaded: "未載入", pending_ask_user: "等你回答",
    pending_permission: "等待權限",
    host: "主機", workspace: "Workspace", title: "標題", agent: "Agent", state: "狀態", activity: "最後活動",
    observed: "觀測時間", all_hosts: "全部主機", all_access: "全部", only_managed: "只看 Connector 管理",
    only_read_only: "只看唯讀", load_more: "載入更多",
    messages: "對話", send: "送出", send_placeholder: "給這個 managed session 的訊息…", interrupt: "中斷這一輪",
    answer: "回答", allow: "允許", deny: "拒絕", read_only_note:
      "這個 session 由人在 BAT 建立，API 永久唯讀：不送字、不回答、不中斷。要讓 agent 接續，請從它的 commit 另開 managed 工作。",
    continue_from_checkpoint: "從此版本建立 agent 工作", checkpoints: "版本（checkpoint）",
    checkpoint_help: "記下這個 session 目前的 commit 與最近對話（只讀，不改動原 session 或資料夾）。從版本開始的 agent 工作會在 Connector 自己的 clone 裡用新的 branch 與 session 進行。",
    create_checkpoint: "記下目前版本", no_checkpoints: "還沒有記下的版本。", excerpt_count: "{n} 則對話",
    dirty_warning: "記錄時有 {n} 個未提交的修改，不會帶入新工作。", continue_placeholder: "要 agent 接著做什麼…",
    start_agent_work: "開始 agent 工作", open_new_session: "開啟新 session",
    checkpoint_unavailable: "這台主機尚未設定 managed_roots、SSH alias 或 write／orchestrate 權限，不能從版本開工。",
    repository: "Repository", pull_number: "PR 編號", load_pr: "讀取 PR", head: "Head", base: "Base",
    checks: "Checks", checks_summary: "{total} 個，{pending} 個未完成，{failed} 個失敗", mergeable: "可合併狀態",
    merge: "合併 PR", deploy_to: "部署到 {env}", merge_and_deploy_to: "合併並部署到 {env}",
    retry_deploy: "重試部署這個版本", merged_sha: "實際合併版本",
    op_accepted: "已受理", op_running: "執行中", op_waiting_checks: "等待 checks", op_waiting_external: "等待 GitHub／部署",
    op_needs_attention: "需要處理", op_uncertain: "結果不明，回查中", op_succeeded: "完成", op_failed: "失敗",
    op_cancelled: "已取消", cancel: "取消", resume: "重新執行",
    resume_help: "處理完原因後再跑一次：已完成的步驟不重做，未確定的步驟先回查，不會重送。", steps: "步驟", action: "動作", actor: "操作者", created: "建立時間",
    error: "錯誤", reason: "原因",
    token: "API token", token_help: "以 batc api-token issue 發行；只存在這台瀏覽器。", connect: "連線",
    remember: "在這台電腦記住", disconnect: "中斷", connected_as: "已連線：{actor}（{scopes}）",
    need_token: "請先在「連線」輸入 API token。", unreachable_hosts: "主機異常", loading: "載入中…",
    forbidden_scope: "你的 token 沒有這個權限。", queue_behind: "排在目前這一輪之後", no_messages: "還沒有訊息。",
  },
  en: {
    nav_home: "Pending", nav_sessions: "Sessions", nav_delivery: "Delivery", nav_operations: "Operations",
    nav_settings: "Connection",
    tab_needs_you: "Needs you", tab_to_confirm: "To confirm",
    empty_needs_you: "Nothing needs you right now.", empty_to_confirm: "Nothing is waiting.",
    stale: "stale", stale_reason_host_unreachable: "host unreachable", stale_reason_host_not_refreshed: "not refreshed",
    stale_reason_not_enumerated: "missing from last listing", stale_reason_gone: "gone",
    stale_reason_never_observed: "not observed yet",
    read_only: "API read-only", managed: "Connector-managed",
    provenance_manual: "created in BAT", provenance_connector_managed: "created by the connector",
    provenance_unknown: "unknown origin",
    state_streaming: "working", state_loaded: "loaded", state_unloaded: "unloaded", pending_ask_user: "asking you",
    pending_permission: "waiting for permission",
    host: "Host", workspace: "Workspace", title: "Title", agent: "Agent", state: "State", activity: "Last activity",
    observed: "Observed", all_hosts: "All hosts", all_access: "All", only_managed: "Connector-managed only",
    only_read_only: "Read-only only", load_more: "Load more",
    messages: "Messages", send: "Send", send_placeholder: "Message for this managed session…",
    interrupt: "Interrupt turn", answer: "Answer", allow: "Allow", deny: "Deny",
    read_only_note: "A person created this session in BAT, so the API never writes to it. To have an agent " +
      "continue, start a new managed session from its commit.",
    continue_from_checkpoint: "Start agent work from this version", checkpoints: "Checkpoints",
    checkpoint_help: "Records this session's current commit and recent conversation (read-only; the session and " +
      "its folder are not changed). Agent work started from it runs in the connector's own clone on a new branch " +
      "and session.",
    create_checkpoint: "Record current version", no_checkpoints: "No checkpoints yet.", excerpt_count: "{n} messages",
    dirty_warning: "{n} uncommitted change(s) at capture time are not carried over.",
    continue_placeholder: "What should the agent do next…", start_agent_work: "Start agent work",
    open_new_session: "Open the new session",
    checkpoint_unavailable: "This host lacks managed_roots, an SSH alias or the write/orchestrate tiers, so work " +
      "cannot start from a checkpoint here.",
    repository: "Repository", pull_number: "PR number", load_pr: "Load PR", head: "Head", base: "Base",
    checks: "Checks", checks_summary: "{total} total, {pending} pending, {failed} failed", mergeable: "Mergeable",
    merge: "Merge PR", deploy_to: "Deploy to {env}", merge_and_deploy_to: "Merge and deploy to {env}",
    retry_deploy: "Retry deploying this version", merged_sha: "Merged commit",
    op_accepted: "accepted", op_running: "running", op_waiting_checks: "waiting for checks",
    op_waiting_external: "waiting for GitHub/deploy", op_needs_attention: "needs attention",
    op_uncertain: "outcome unknown, reading back", op_succeeded: "done", op_failed: "failed",
    op_cancelled: "cancelled", cancel: "Cancel", resume: "Resume",
    resume_help: "Run it again after fixing the cause: finished steps are not repeated and unproven ones are read " +
      "back, never re-sent.", steps: "Steps", action: "Action", actor: "Actor",
    created: "Created", error: "Error", reason: "Reason",
    token: "API token", token_help: "Issue one with batc api-token issue; it stays in this browser.",
    connect: "Connect", remember: "Remember on this computer", disconnect: "Disconnect",
    connected_as: "Connected as {actor} ({scopes})", need_token: "Enter an API token under Connection first.",
    unreachable_hosts: "Host problems", loading: "Loading…", forbidden_scope: "Your token lacks this scope.",
    queue_behind: "Queue behind the running turn", no_messages: "No messages yet.",
  },
};

const lang = (navigator.language || "zh-TW").toLowerCase().startsWith("zh") ? "zh-TW" : "en";

export function t(key, vars = {}) {
  const text = STRINGS[lang][key] ?? STRINGS["zh-TW"][key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}
