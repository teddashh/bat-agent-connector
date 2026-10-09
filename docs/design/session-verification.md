# 外部驗證證詞的中央 operation

`session.record_verification` 使用 `operate` scope，target 只有 `host`、完整
`session_id`；params 保留 `candidate_commit`、`command`、整數 `exit_code`、
`environment`、`log_ref`。它只讀 BAT 的固定來源與乾淨 HEAD，寫 Connector
`verification.json`；不執行 command、不讀 log_ref、不授予 BAT/Git grant。
人工來源仍可記錄 metadata，但不因此變成 managed。Task-owned 來源拒絕外部
證詞；原 internal FrameGuard／ObservedVerifier 路徑不變。

HTTP 使用既有 operations route；RPC/MCP `session_record_verification` 與 CLI
`record-verification` 是薄轉接。MCP 使用自己的 BATC_API_TOKEN，CLI 沿用明確
token／local-admin 的既有中央 request 語意，不建立第二個 daemon 或 raw fallback。
相容入口保留 confirm、host writes/orchestrate、CLI read-only；新增 optional key。
同一 literal key 先 replay，再做 selector／tier／來源讀取；省 key 為獨立要求。

`verification.observe` 固定 exact SID、tab/workspace/cwd、registry incarnation
（包含原本不存在）、乾淨候選與 principal actor。`verification.record` 在最後來源
讀取後，再核對 task absence、registry binding、owner lease 與取消狀態才寫入。
外部 BAT GUI 仍可能在最後快照後改動來源；本證詞不是對 GUI 的原子鎖或持續有效保證。

JSON 保留原 `records` latest-per-session 格式，新增 `operation_receipts`，以
operation ID 保存不可變完整 row 與 payload digest。兩者在同一 flock／atomic
replace 寫入；internal writer 必須保留所有 operation receipts。Malformed、duplicate
keys、過大或不可讀既有檔案拒絕覆寫。Stored row/receipt 不能自報 trusted verifier。

JSON replace 後、SQLite step receipt 前 crash：回查原 operation receipt，不重新
檢查已改動來源、不覆寫後來的 latest row、不改原 timestamp。Started record step
沒有可證明的 JSON receipt 保持 uncertain，不重送或重建。完成 receipt 可在後來
pause／binding/tier 變更後重讀；新的寫入仍需當下政策。

輸出保留完整 testimony 與 `verified_candidate`，另附 operation ID/status/error/key
欄位。`verified_candidate=true` 只表示 caller 的 exit_code=0 證詞綁定了當時乾淨
候選；不建立 Task Service `observed_verifications`、不 accept artifact、不完成
work item，不宣稱已 merge/deploy。測試只用 MockBat、暫存 JSON／SQLite。

上游 BAT `b7419892fbc9946799b64cca24c2ec8c7fa15c42` 的
`src-tauri/src/commands/git.rs::git_get_status_native` 將 Git 執行失敗／timeout
也轉為 `[]`。這裡保留既有 HEAD 與 BAT 回報空 status 的相容檢查，拒絕 malformed
status，但不能由此證明 Git 子程序成功或沒有未追蹤內容。它不是 trusted verifier
或 artifact acceptance 的來源；其他實際 mutation 不能借用這份證詞當 authority。
