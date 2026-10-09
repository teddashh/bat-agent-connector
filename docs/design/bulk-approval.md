# Bulk approval：固定預覽、逐項 child operations

基底 main `e495d70`，追蹤 #59。沿用[同一產品/Tauri 方向](../product/realignment-v2.md)、
[operations](operations-unification.md)、[permissions](session-permissions.md) 與
[驗收矩陣](../product/acceptance-v2.md) A01/A05/A07/A08；不是另一個 queue 或 authority。

## 公開合約

`POST /api/v1/approval-previews`（observe）：`{host, workspace?}`。只讀固定 BAT workspace/meta/state；
不更新 inventory、registry、不派送 setter、answer、rehydrate 或 deferred flags。
最多 50 個 session、每項完整 prompt 最多 8 KiB、總回覆最多 256 KiB；超量／無法完整展示的項目不可選。
預覽列明 `permission=allow, dont_ask_again=true`（這會授權 BAT 的同類請求，並非一次性 allow），
mode 由 caller 明確選 `null|default|allow_all`。Manual/unknown、confined policy、task pause/version、
未載入／unknown agent、host policy 等拒絕保留 code，不悄悄改成單次 allow。

預覽包含固定 item ID、完整 SID、registry creation/owner/cwd/policy、runtime SDK identity、
原 task incarnation/control_version、toolUseId 與整個 permission prompt fingerprint。
HMAC token 綁 server/原 authenticated credential/actor/scopes，有效 600 秒；嚴格限制輸出及解碼大小。
Token 不儲存 preview 資料列，沒有 retention/reaping 的無上限 observe-write store。

Canonical `session.approve_pending`（operate + observe）target `{host}`，
params `{preview_token, selection:[{item_id, mode:null|default|allow_all}]}`，
preconditions `{expected_fingerprint}`。Selection 必須非空、無重複、全部來自此有效預覽。
Preview 的 blocked 項目不能強制選；mode 不在該 item 支援集合則 admission 拒絕。
Named key 先依原 literal intent/當前 caller 授權 replay；accepted 後不重新過期或選新 prompt。
Legacy MCP/CLI 無 key 每次獨立，並如實回 `idempotency_key:null/idempotency_enabled:false`。

MCP `approve_pending` / CLI `approve-pending --dry-run` 回同一中央 preview。
Apply 必須帶 preview token、fingerprint、明確 selection；缺少則 `BULK_PREVIEW_REQUIRED`，
不自動 preview/all-select。保留 confirm/read-only/tier；需自己的 API token，沒有 daemon autostart/raw fallback。
CLI 以 `--preview-file` 與 `--selection` JSON 送 reviewed intent，`--key` 可選。

## 一個父 operation 與現有 children

父 operation 保存固定 selection/原 actor/受理 scopes。每項 answer 使用原 `session.answer`；
成功且有 literal true ACK 後，才建立可選的 `session.permissions` child。
Child key 由 server 隨機保留，與父 local effect receipt/child linkage 同 journal transaction 提交；
尚未提交的 child 不可能被 worker 派送，重啟只重播原 child ID，不重新建立效果。
這避免 caller 預先佔用可猜測 child key。沒有第二個 ledger/queue/migration step。

Child action 仍走 canonical admission、原 TaskCoordinator command、rate limit/audit、confinement。
額外的 server-only bulk linkage 指向父 receipt；每個尚未派送 frame 都檢查父取消狀態、選中 item、
session creation/runtime、原 owner（包含沒有 owner）、task version、固定 prompt fingerprint。
在 client semaphore 內以 allowlisted guard_read 讀 meta/state，再做同步最後 gate；不重入 semaphore。
新的 RPC/HTTP body 不能自填 linkage 或 callback。

Bulk answer 只把 true ACK 當作同意證據。Pending prompt 消失不證明它獲准，因此 bulk child 不採用
一般 answer 的「prompt 已清除」推論去授權後續 mode change。False/unknown/lost/error ACK 保留未證明
receipt，永不重送。一般 standalone answer 的既有 readback 語意不變。
Permissions 沿用逐 channel ACK；Claude streaming 不 deferred，historical flags 不自動採用。
真 ACK 只證明 BAT 接受設定，不是 SDK/OS enforcement；同 permissions 合約的 pinned BAT 來源。

獨立項目可各自完成或拒絕；任何部分結果保留原 session/prompt/child IDs。
Parent result 的 all_succeeded/counts/items 區分批次已處理與所有項目同意，不能只看 parent succeeded。
未證明 child 仍可 readback／needs_attention；parent 不宣稱全成功。Resume 只接續同一 children，
已失敗項目需要新的 reviewed request，不在原 parent 偷換 key 或 prompt。
Parent 依最早 child 的既有 next_run_at 等待（1–30 秒）；active child 使用 1 秒。
不在 child 等待 30–600 秒時以 0.2 秒重寫父 journal；明確 parent cancel/resume 清除到期時間，立即喚醒。

## 取消與授權

父 cancel 不直接抹除有可能 sent 的 children；先記錄 cancel_requested，交原 worker 停止建立新 child，
沿用各 child 的取消/receipt recovery。全部效果已證明後才 terminal-cancel 父；未知效果保持
needs_attention 及 child/step refs，不釋放 task/registry/cleanup claims。
取消後任何 unsent frame 最後 gate 都拒絕；完整 ACK 的 local receipt completion 仍可進行。

Parent replay/resume/cancel 要求目前 operate+observe 與原 authenticated credential；受理 authority
不因 scheduler wake actor 改變。Linked child 的 controls 需原 actor 與目前 operate+observe，
不能以另一個只有 operate 的 credential 經 child 繞過組合 scope。中央 worker 只依受理的有限
operate/observe authority 管理原 children，不建立 admin principal 或跨 caller fallback。

## 共用 Dashboard

工作階段清單連到獨立且精簡的批次核准頁。Host 必選、workspace 可選，使用上述 observe preview，
逐筆展示完整 prompt、完整 session ID、不可選原因及模式；初次預覽不預選任何項目。每筆明示
`dont_ask_again=true` 的持續授權語意，模式預設不變更，不能把此操作表示為單次 allow。
超過 50 個 session 時顯示只檢查部分的提示，不把已載入數量當總量。

預覽、草稿選擇及受理前固定 request/key 存在既有 endpoint/server/principal namespace。
更換 host/workspace 會使尚未送出的 preview 失效；已送出請求鎖定範圍，回覆遺失只重試原 key，
有 operation ID 只 GET 查回。核對 action、actor、target、完整 params/preconditions、key 與原 ID
才接受回應。結果畫面同時顯示父狀態與逐筆 child receipts，不以父 succeeded 推論全部成功。
只有 terminal readback 或中央確定受理前的 preview/mode 拒絕才允許明確開始另一批；一般 auth、
transport、conflict 保留原意圖。取消/恢復沿用 operation 詳情頁，沒有另一套批次控制流程。
事件等候尚未收到回覆的 POST，再讀原 operation，失敗不推進 cursor。新 prompt 不加入舊選擇。

Native transport 僅增加固定 `/approval-previews` POST，拒絕 query、key、未知欄位與非字串 scope。
沒有新增直接 BAT 權限。Browser/native fixtures 與本機包測試不是真 Windows 或 live 接受證據。

## 尚未涵蓋

不處理 ask-user 自動作答、任意工具規則、批次 deny、跨 host 原子交易、歷史 deferred adoption、
原子 BAT GUI 鎖或新 task recipe。人的 session/worktree 維持唯讀。
Mock/CI/branch 證據不代表 Windows installed/live 或完整產品 46 項驗收。
