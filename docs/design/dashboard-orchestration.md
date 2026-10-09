# 共用 Dashboard：明確的中央編排入口

沿用 `orchestration-operations.md`、`session-failover.md` 與 v2 UI 方向；中央
OperationService 仍是唯一寫入權威。頁面 `#/orchestrate/{relay|planner|items|failover}`
使用現有 `/operations` 與受限 native connector_request，沒有新增 RPC 或路徑通道。

- relay：固定 managed host/full SID、原文、queue；`start_if_missing=false`。
- planner：固定中央工作區 ID、原文、1–16 項上限；`fanout.plan` 建立唯讀 Codex 規劃者。
- items：固定工作區、agent、逐項 title/prompt/index；明確檢視後送 `fanout.start`。
  不自動解析規劃者回覆，也不停止原規劃者。
- failover：單一 managed Claude、正面閒置觀測、無已知 task 關聯；固定 tail=12 與
  選填補充原文。中央再檢查 quota、所有 owner／writer、confinement 與最終 frame。
  不提供 force、batch、task-owned 切換、archive-only 或自訂 recipe。

所有入口需要 observe 與各 action scope、正面 allowed capability、host writes；新啟動
另需 orchestrate。來源只用來源明確且新鮮的 managed 紀錄；人工、unknown 不可選。
清單只顯示前 200 筆並明示截斷，完整 session 可從既有明細入口開啟。

HTTP 沒有 dry-run preview。勾選表示檢視這次的輸入，不表示對話／交接已固定。
中央在受理後才產生 durable preparation 與逐項回執。接受初始指示不表示任務完成。

以 bootstrap server/principal namespace 保存原始完整 intent、key、accepted operation ID。
提交前先保存；儲存失敗不 POST。回應須符合 actor/key/full envelope／原 operation ID。
失去回覆只可明確重試原 POST；受理後 reload/event/check 只 GET。普通 4xx 不旋轉 key；
只有 action 已證明在 INSERT 前的 tier/worktree-required/fanout-cap 拒絕可重新準備。
部分／未知結果保留 parent、child、step 回執及連結，不以新 key 代替恢復操作。

## 尚未涵蓋

不新增來源對話預覽、不實作任務接管、不修改中央 task ownership，也不自動執行規劃。
實機安裝、真實主機與 provider 並非這組 UI fixtures 的驗證範圍。
