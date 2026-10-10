# 工作更新的已讀狀態

2026-10-09。Web 與 Tauri 共用中央 journal 的個人工作項目閱讀標記。
這是工作項目版本的未讀更新，不是聊天訊息總數，也不是完成確認。

- `work_item_reads` 以 effective principal（沿用 bootstrap 的 actor/scopes/admin digest）
  與 work_item_id 為鍵。Journal 本身隔離 server；client 仍依 endpoint/server/principal 分區。
  同一身分的兩個入口共享標記，其他身分互不影響；token 輪替不改 effective principal。
- `GET /work-items`、`GET /work-items/{id}`、bootstrap 的 work_items，以及同形 RPC
  回傳 `reading={read_version,current_version,unread,read_at}`。列表可用 `unread=true|false`，
  先篩選再分頁，保留既有 next_cursor，不回傳推算的完整總數。CLI `item list --unread`
  與 MCP `work_items_list(unread=true)` 走同一中央讀取。
- `work_item.read` action 使用 observe scope、exact work_item_id 與
  `preconditions.expected_version`。使用者在詳情明確點「標記此版本已讀」，才提交 durable operation。
  單純載入頁面、捲動或處理事件不寫標記。
- Admission 固定 server/principal；同 actor 不同 scopes 的 replay/cancel/resume 不可借用另一
  身分的 marker。執行使用保存的 binding，marker 與 effect receipt 同一交易，原 key 可查回。
- 只推進已讀版本，不倒退。畫面過期仍可標記當時讀到的較舊版本，較新的版本繼續未讀；
  超前於中央的版本拒絕。新操作重複標記相同版本不製造另一個 read event。
- Mark read 不改 work_items.version/updated_at、completion fingerprint、pending、步驟、
  approval、session 或來源檔案。所有 work-item 版本變更（包含管理資料）都可能產生未讀更新；
  它不代表有新的 agent 回覆或工作已完成。
- 新表是冪等 DDL，不分配 user_version、不搬動自有 IDs／歷史。升級後沒有 marker 的既有項目
  顯示未讀，介面明示這代表尚未標記。事件 `work_item.read` 只用來刷新中央讀取，不用 event
  checkpoint 當 marker。

首頁「需要你處理」分為待回覆／權限、完成確認、需處理操作與主機連線；「執行中操作」取代
原本誤導的「待確認」分頁。獨立「未讀工作更新」依 capability 顯示，可與完成確認同時存在。
每組只報已載入數量，有 next_cursor 時可繼續載入；失敗保留上次資料並標示未更新，不能冒稱為零。
Detail 的標記結果一律重新讀取 reading，不能用 operation accepted/succeeded 推論最新版本已讀。
若正在編輯，讀回只更新閱讀提示並保留草稿與畫面版本，關閉編輯後再刷新內容；不能替尚未顯示的
中央新版標記已讀。詳情刷新依序完成，舊回應不能覆蓋後來的版本。

尚未提供完整聊天訊息的未讀數與跨入口閱讀位置：現有 messages 是有大小限制的局部摘要，
不能靠最後活動時間、idle、畫面已捲到底或 ACK 推算完整閱讀證據。
