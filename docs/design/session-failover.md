# Standalone failover：固定來源與獨立效果收據

依[中央 orchestration](orchestration-operations.md)、[operation／Task Service 合約](operations-unification.md)
及[共用產品澄清](../product/realignment-v2.md)。只處理同一 host 的 standalone managed Claude → Codex；
Task Service 的 mid-task failover 仍拒絕，不引入新 queue、data step 或公開 task authority。

## API 與相容入口

`session.failover` 同時需要 start + operate；target 是 host、session_id 或 workspace（供 all_exhausted 篩選）。
params 為 all_exhausted、model、force、tail_messages (1–40)、instructions（最多 4000）、archive_only。
精確一個 session_id 或 all_exhausted=true；instructions/archive_only 僅單一來源。force 只略過 quota 分類，
不能略過正向 idle、managed／task ownership、shared carrier、confinement 或最終 frame checks。
HTTP 要求顯式 key；MCP session_failover／CLI failover 保留 confirm，optional key。no-key 每次新 operation、
public key=null；內部 UUID 不冒充 caller key。重播先讀已接受操作，再做新 admission；不啟 daemon、不 raw fallback。
dry_run 需要 observe，只讀固定候選與 handoff preview，沒有 operation／reservation／marker。

## 固定計畫與效果

先保存候選完整 SID（batch 上限沿用 safety.max_start_per_call、人工項目不佔名額），再保存逐項固定來源：
registry creation、原 terminal/runtime 的 loaded 與缺值、workspace ID/profile/folder、Git root/branch/HEAD、
原 handoff text/digest、successor UUID/message ID、permissions/confinement。read-only resolve 未完成可重讀；
已有 receipt 絕不改挑新 transcript、SID、分支或新 prompt。原 worktree 不存在或無法證明時拒絕，不能改落
main checkout。Dirty bytes 留在同一 carrier；這不是 dirty snapshot，不宣稱與原 BAT UI 的操作原子化。

每項 reserve、start frame、metadata confirmation、registry projection、handoff frame／projection 都有獨立
intent/receipt；不包成整個 lifecycle helper 的單一步驟。Start 有已送 fence，可用原 reserved SID 的正向
metadata/confinement 查回；handoff 只有明確 true ACK 才完成，Codex metadata／相似文字不證明接受。
Lost/error/unknown handoff 不重送，不派下一項；cancel 保留已送效果、carrier、capacity 與 fence。
Batch 的已完成項目保存；遇未完成或拒絕會保留 partial result，不把新挑選當重試。沒有 implicit old-session
stop/remove：原 tab、branch 與 worktree 留存，reviewed cleanup 才能確認退休；capacity replacement 不是
宣稱舊 runtime 已停止。現有其他 operation 的 successor 只呈現既存 pointer，不採用或重送其 handoff。

## Durable predecessor fence

Reserve 同一 registry flock 比對原 incarnation，將 immutable operation＋predecessor＋successor＋固定 plan
hash 寫入兩個 row，再以原有替代 capacity 規則建立 successor。原 session 的 send/resume/answer/permission
及 Git mutation 透過共用 resource-policy 最後檢查拒絕；read/stop/interrupt 保留。未知／損壞 marker、owner 或
receipt 讀不到時 fail closed。Successor 尚未正向完成 handoff 前，只有驗證原 operation receipt 的私有 frame
context 可寫；task、child、recovery 也走相同共用 gate。沒有公開 force、actor 字串或 raw flag 可取得 bypass。

每個新 frame 重新檢查原 carrier 所有已知 consumers、owner、terminal/runtime 與 Git identity；source 或其他
writer 無正向 idle/unloaded 證據即零 start。async guard_read 之後再同步檢查 task/registry/cleanup/config，避免
await 打開 authority 空窗。只有原 claim＋durable start_sent=false 的正向未送證據可 rollback 自己的 marker／
替代 capacity；送出或无法判斷就保留。已完成收據先於現在變動的 policy，以免把本機收尾誤變成重送。

## 尚未涵蓋

不啟用 Task Service mid-task failover、不搬主機、不傳 unpublished Git、不關閉人工 session、不自動清理
共用 worktree。Native/GUI 的專用 failover chooser 與 installed/live 驗收另列；此切片交付同一中央 API/MCP/CLI。

## 回復與相容限制

已證明未送出的 handoff（例如最後 identity read 斷線或 rate budget 不足）保留原操作為 needs_attention；
resume 只對保存的 start/successor/text 重查 gates。它不重送 start。已消耗 handoff hash 或 on_transport fence
則沒有此途徑，未知 ACK 不能從相符 metadata 推定成功。已取得 handoff ACK 而本機 projection 中斷時，cancel／
restart 僅可完成原 incarnation 的 registry CAS；`OpContext.step(receipt_only=True)` 是內部的本機收尾選項，
不接受公開參數，也不能送 BAT/provider frame。較新 owner／policy 不會被覆盖。

原 scope、confirm、人工保護、Task Service authority 與 audit/hourly budget 保留；初次 handoff 沿用既有
initial-send interval exemption，不把本次 start 當成另一則 prompt。正向 receipt 重播不重算 attempt。
MCP/CLI 現在需要可用的中央 owner 與 caller credential；舊 direct transport fixtures 改用真中央入口。
這是 authority 移轉，不是缺 token 時退回 raw Fleet 的相容例外。

Fence 包含固定 carrier；同 carrier 的其他 managed writer 也拒絕，避免另一 session 在判定 idle 後再送訊息。
新建獨立 worktree 仍走既有 ownership/claim/final gates；它會更新 Git worktree metadata，保留原 carrier
內容，不讓新 session 在原 carrier 工作。不因 origin 被 fenced 就失去獨立開工能力。原 source 或 successor 改身分、receipt owner/ACK 無法讀取時，fence 保留供 reviewed cleanup。
