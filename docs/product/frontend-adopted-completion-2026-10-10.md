# 已採納前端對照的實作證據

本表對應 [Project Hub 前端對照](project-hub-frontend-audit-2026-10-09.md) 的已採納／改接範圍。
不把暫緩、拒絕項目或真人實機驗收算成新增產品要求；正式簽章、公證、更新通道與 Linux
憑證持久儲存不在這次代理收尾範圍。模型、Skill、閱讀紀錄與來源證據仍以中央為權威。

| 對照 | 共用 Web／Tauri 實作與限制 |
| --- | --- |
| A04、A05 | `tree-interactions.js` 只允許同一 namespace、父節點與 pinned 區段的同層拖曳；送完整 siblings 順序及 expected versions。上下鍵替代、右鍵、Shift+F10 與 More 使用同一操作 drawer；不重新歸屬。 |
| A08、C14 | Project description、work-item goal/request/acceptance 使用短摘要與可展開原文；checkpoint 接續草稿仍包含原始文字、固定附件與來源 SHA/fingerprint，摘要不代替驗收。 |
| B02、F02、F03 | `model-preferences.js` 使用指定 BAT host 的實際候選目錄；初始與上次選擇分開，隱藏／排序／重設只改個人偏好。失效 ID 保留並說明，不改既有工作的模型。當前值完整保存在輸入、title 與可讀 label，窄螢幕顯示可截短，API ID 不變。 |
| C03、C05 | `summarize.py` 只保留原訊息提供的 agent/model/duration 與時間；舊 BAT 訊息通常沒有逐則模型，不以目前 session 模型補造。工具輸入摘要和結果有長度上限，completed 細節預設折疊，錯誤／執行／拒絕／延後／未知展開且狀態永遠可見。 |
| C06 | `composer-shortcut.js` 在對話、新 session、repository/project 工作提供 Button only、Enter、Ctrl/⌘+Enter；Shift+Enter 換行，composition、229、compositionend 邊界及 repeat 不誤送。使用原本受權限／readiness 限制的送出按鈕。 |
| B10、D06 | `result-sources.js` 從中央明確關聯提供父／子工作、原 session、固定 artifact revision/digest、來源操作與 delivery receipt 入口；未驗收子工作在父工作 checkpoint 接續前提示。已記錄 references 與 live consumers unknown 分開，不把未知說成沒有消費者，不放寬 coordinator gate。 |
| D07 | 既有 integration candidate 勾選與順序控制仍決定固定 preview 的 sources；取消勾選不刪工作、內容、pins 或 references，不表示完成。新增父子來源入口可回到既有 delivery/operation 收據。 |
| F04、F07 | 個人設定顯示 BAT host 回報的 provider account、訂閱窗口比例、reset／fetched 時間、來源、stale 與取得失敗。這不是目前 session 所選帳號證據，也不把 subscription 利用率混作 token/context/cost，不讀 client provider secrets。 |
| H06 | `project-skills.js` 從中央 discovery 選實際 host/workspace ID，再讀該來源的 Skill catalog。保存明確 skill ID + 全來源 digest，保留遺失／改版的舊選取，顯示相容性及不完整／過期來源；改來源與丟棄草稿都是明確操作。`selected_not_applied` 一直可見；沒有宣稱 runtime 啟用或自動放入 prompt。 |
| 跨入口閱讀 | `session_reading.py` 保存 effective-principal 的訊息 revision receipts 與位置；相同 session 從專案／work-item／session 入口共用。只有明確點擊可見完整訊息才標記，工具、未載入歷史、event ACK 與捲動都不標記。工具頁碼與文字 unread 分開，並行不同 filter 不借用錯誤 offset。 |

設定與 Skill 草稿按中央 server/effective principal 隔離；提交前保存固定 intent，失去回覆後使用
同一 request/key 重試，中央 expected revision/catalog digest 保護共享狀態。來源列表保留失敗前
觀察並明示過期；事件刷新失敗不得推進 event checkpoint。父子成果分頁與來源截斷都顯示範圍。

針對性測試包含 `tree-interactions.spec.ts`、`composer-shortcut.spec.ts`、`model-preferences.spec.ts`、
`project-skills.spec.ts`、`result-sources.spec.ts`、`message-metadata.spec.ts`、
`conversation-reading.spec.ts`，以及 `test_tree_order_versions.py`、`test_message_metadata.py`、
`test_session_reading.py`。完整整合測試與最後 issue 對照由整合分支統一記錄。
