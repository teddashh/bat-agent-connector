# Task Service reviewed cleanup 與共用 finalization

本片依 [產品決策](../product/realignment-v2.md)、[E01/E02 驗收](../product/acceptance-v2.md)、
Tauri 校正計畫 §19/R08 與 [cleanup Part B](cleanup.md) 實作。兩份計畫是同一產品；
本片不加入 restore 或未發布 Git objects 的跨主機傳輸。

## 公開介面與邊界

既有 cleanup preview 新增 `target: {kind: "task", task_id: "完整 ID"}`。
HTTP `/api/v1/cleanup-previews`、MCP `cleanup_preview` 與 CLI `resource-cleanup preview --task ID` 使用同一 target；
apply 繼續使用 `cleanup.apply`、signed preview token、fingerprint、明確 key 與 `cleanup` scope。
Preview 需要 `observe`，不得寫入 DB、registry、Git 或 BAT。
capabilities 的 `features.cleanup_task: true` 表示支援此 target。UI 可由 task detail 連到既有整理頁；
其他 target 保留原 `TASK_OWNED` 行為。
Preview 的 `task_cleanup` 是解釋與 immutable binding，並非可轉交的權限 token。

只有具 creation evidence 的 session／worktree 可獲准。TaskCoordinator 必須列出資源的所有
current／historical task owners（含 commands、branches、registry 與共用 successor worktree），
確認全部 terminal `done|failed`、固定 control_version／session／resource identity、原 owner lease、
無 unresolved command 或仍需內容的 execution。terminal task 的殘留 paused flag 可透過 explicit reviewed cleanup 回收，但 flag／version 仍固定於 binding；
automatic cleanup 遇到 paused owner 仍保留。一般 runtime gate 與裸 task ID 不能授予 cleanup。
settled／rejected／cancelled command 與 operation 的 succeeded／failed 並非同一狀態集合；
accepted send 必須有原 marker、terminal task 與另外的 live idle／content 檢查；這只證明 dispatch 已知，
不宣稱 delivery。其他 accepted／running 或 intent／needs_review／uncertain command 一律保留。
未知效果、pending prompt、active writer、manual／unknown consumer、live read unavailable、
integration reference、retention 與唯一 artifact original 仍保留，不能用 choices 覆蓋。

本片保留 task branch、retained refs 與不支援的 carrier；dirty task worktree 不提供 discard。
reviewed `release_undelivered` 只允許已獲 coordinator eligibility 的 clean worktree，保留 exact commits
及 branch，不把 task done／verification／PR link 當成 delivery。未核准的 choice 不可影響其他資源。

## 保留、最後一個 effect 與復原

沿用 `cleanup_runs`／`cleanup_receipts`／operation steps／registry cleanup guards，不另建 queue。
Coordinator 在原 task／writer locks 下簽發內部 capability，綁定原 operation、resource generation、
完整 owner set 與 versions。Registry reservation 在既有 flock 內再次驗證 binding；warm claim 在
同一 flock 檢查 cleanup guard，不能把已保留資源交給 successor。
每次新的 stop／preserve／remove 前重新檢查 consumers、owner lease、版本與資源身分；
BAT 最後 frame 使用 coordinator capability，普通 stop 的 `refuse_owned` 不變。
已成功 steps 優先使用 durable receipt；unknown effect 只走既有 readback，不能重新選資源或盲目重送。
local finalization 可補齊自己的完成紀錄，但不得修改新 incarnation／successor 的 registry 或 task。

## 原 automatic external-worktree cleanup

TaskDaemon 保持原 terminal cleanup 排程，改由中央建立 server-origin 的固定 cleanup plan，
使用同一 `cleanup.apply` operation 與 resource reservation；不新增 scheduler、公開 force 參數或
自動 stop runtime。Automatic plan 只處理原 external worktree，clean content 與 retained commit
證據仍必要；有 live／未知 consumer 就保留。operation external_refs 與 task cleanup_accepted event 保存 task／operation IDs，供未完成時直接查回。
固定 carrier key 查回原 operation，partial／unknown
不建立新 attempt，需由既有 operation reconciliation／reviewed cleanup 處理。
Automatic receipt 明記 `task_lifecycle`，不冒充 user-reviewed scope acceptance。

共用 finalize 保存原 resource ID／task ID／path／branch／retained ref／exact SHA、tombstone 與 aliases，
再以原 task/resource binding 清除 external pointer。新 shared retained refs 使用既有
`refs/batc/retained/...`；歷史 `refs/batc/tasks/...` 永不刪除。歷史
`external_worktree_retained` 事件只 backfill 可信的 historical evidence；不能假稱當年有 reviewed
operation，也不能只憑事件宣稱現在仍可讀回 objects。重複 backfill 必須冪等。

## 驗證與尚未涵蓋

使用 temporary Git／MockBat：scope 與 malformed target、preview 純讀、terminal command disposition、
所有 owner／warm successor race、late version／binding／writer、unknown stop/remove 不重送、
automatic/reviewed 互斥、crash 前後共用 finalization、historical ID/ref 可尋與 unavailable retention。
HTTP/MCP/CLI 使用既有 action；UI target 選項由整合者接入。
尚未涵蓋 restore、新增 task branch deletion、manual carrier、dirty task discard、安裝與 live host 驗收。
