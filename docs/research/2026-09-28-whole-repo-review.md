# Task-service PR #2：全庫程式審查與模型探針

日期：2026-09-28。範圍是 connector 全庫，不只 PR diff；沒有修改 BAT、Hermes 或正式 agy shim，也沒有部署。`docs/research/chatgpt-full-discussion.md` 維持未追蹤。

## 方法與可用性

依便宜先行的順序：讀 README／設計及 task、lifecycle、MCP、BAT、verifier、Goose、provider 原始碼與測試；用 `rg` 搜尋 shell 執行、token／錯誤輸出、跨 task 操作、舊 watcher／relay 重疊；跑 Ruff、`git diff --check`、focused 與全庫 pytest。指定的 Jev 程式審查 skill（`jev-code-review/SKILL.md`）在這台開發主機（`host-a`，操作者的工作站）不存在，已搜尋本機可用 skill；也沒有可呼叫的 user-jev MCP，`TYPESAFE_API_KEY` 不在本機環境，故本輪未聲稱執行 TypeSafe Jev 的線上審查。這不影響 service 中 Jev fail-open 的 fake／contract 測試。BAT Codex reviewer 的讀取結果另記於下方；獨立 release sign-off 仍由 Ted 指定的 reviewer 處理。

後續 executor 對 `f59e359` 依既定 Jev 全庫流程完成第一輪：32 檔、47 次呼叫，結論 `request_changes`。唯一項目是 `task_handoff.py` 的 `original_words_archive`／`ledger_summary` 缺直接測試（testGap、嚴重度 2.03、機制信心低）。人工檢查未找到執行時缺陷；下表與新回歸測試記錄這項測試缺口的處理，沒有重跑模型探針。

## 發現

| 嚴重度／狀態 | 位置與證據 | 處理 |
|---|---|---|
| High，已修 | `src/bat_agent_connector/lifecycle.py:987`：舊 `session_cleanup` 原可把 task-service 擁有的 session 當閒置 worktree 清理；`lifecycle.py:1379` 的 `main_session` 原可選 headless task lead 做舊 relay。 | registry 帶 `task_id` 的 session 排除 cleanup 與 main relay；`tests/test_lifecycle.py` 覆蓋兩路。 |
| High，已修（獨立 BAT 審查） | `src/bat_agent_connector/orchestrate.py:259`、`task_bat.py:143`：task lead 原在 BAT start 完成後才補 `task_id`；若 start 後、初次 send 前 pause，舊 cleanup／main relay 可把它當一般 session。 | `session_start` 在原子的 registry reservation 時即寫入 `task_id`／lead 角色；真 MockBAT start→pause 回歸測試執行 cleanup 和 main-session 選擇，均排除該 lead。 |
| High，已修（獨立 BAT 審查） | `src/bat_agent_connector/task_bat.py:78`、`task_daemon.py:360`：終態外部 worktree 原以 force remove 與 `git branch -D` 刪除，且忽略失敗，未合併 commit 可能失去可達 ref。 | 僅清潔且 HEAD／branch 一致時移除 worktree；先保存 `refs/batc/tasks/<task-id-prefix>`，同時保留原 branch。成功或重啟對帳均需 Git ref／commit 證據才清 journal 指標並記事件；失敗保留路徑，以 60 秒退避重試。真 Git 測試驗證未合併 commit、dirty 拒絕、錯誤 done hash 拒絕、刪除後重啟對帳。 |
| Low，測試缺口已補（Jev） | `src/bat_agent_connector/task_handoff.py:1`：Jev 指出 `original_words_archive`／`ledger_summary` 缺直接測試，人工檢查未見執行時缺陷。 | `tests/test_task_handoff.py` 直接驗證完整 UTF-8 內容、SHA-256、0700／0600、檔案與目錄 fsync、UUID 碰撞不覆寫、長原話須用 archive，以及摘要超界時保留權威 archive 指標。 |
| Medium，已修 | `src/bat_agent_connector/task_verifier.py:174`：管理員設定的驗證 argv 原本逐字進 journal／status，若參數含 credential 就會外洩。 | journal 只存完整 argv 的 SHA-256；0600 私有設定供管理員對照；測試用假私有參數確認 evidence 不含原值。 |
| Medium，已修 | `src/bat_agent_connector/task_bat.py:61`：外部 worktree 建立命令把 BAT workspace 路徑直接插入單引號 grep 表達式；名稱含 `'` 時 shell 語法破裂；`$ref` 也未加雙引號。 | 使用 `shlex.quote` 處理整行 `worktree <path>`，並引用 `"$ref"`；以含 apostrophe 的 root 做 shell syntax 回歸測試。 |
| Medium，已修 | `src/bat_agent_connector/task_daemon.py:316`：Goose 例外全文可能含 provider prompt／token，原先寫入服務 log。 | 只記例外類型；測試檢查假私密錯誤文字不出現在 log。 |
| Medium，已修 | `src/bat_agent_connector/task_core.py:143`：新 Jev routing 在 BAT start 前 await，pause 可在分類期間提交；若不重讀控制狀態，start 會越過 pause。 | route 回來後重新讀 task／paused，send 與 verification route 也同樣重查；阻塞分類的回歸測試要求零 BAT start／send。 |
| Medium，已修 | `src/bat_agent_connector/task_daemon.py:310`：把 router 選擇直接寫成 task `pm_provider` 會遮蔽 recipe 明確指定的 provider，journal 也可能與實際選擇不符。 | task／recipe override 先傳給 router 記錄，Goose 依 task → recipe → routed choice → 預設的順序執行；contract test 驗證優先順序。 |
| Medium，保留 | `src/bat_agent_connector/goose_acp.py:120` 的 ACP adapter 是短煙測路徑，缺重啟後持久恢復與完整 pinned UI／provider contract；`task_daemon.py:108` 已禁止 live Goose task。 | 維持 gate 關閉；M2 合約清單見設計文件，不能用本輪 isolated smoke 代替。 |
| Low，保留 | `src/bat_agent_connector/mcp_server.py:69` 的舊 `session_wait` 與 lifecycle 仍公開作相容介面；若舊 Hermes workflow 主動呼叫，仍可能等待。 | 正式 Hermes cutover／watcher 停用屬 M2 部署；本 PR 不更動 Hermes。 |

## AGY 模型與 Goose 證據

現有 18795 shim 的 `/v1/models` 原始設定只列 `gemini-3.8-flash`、其 low／medium／high 變體及 `gemini-3.1-pro`；這只是發布清單，沒有在本輪向 Hermes 18795 發請求，也沒有驗證 Gemini prompt。後端 agy model resolver 原始碼列出確切 `claude-opus-4-6-thinking` ID，並會把預設 `--effort medium` 加到 Claude。只在暫時複本修正 Claude effort 並在 loopback 18796 發起極小測試：`claude-opus-4-6-thinking` 回 HTTP 200，內容含 `OPUS_OK`。第一次只修改 model list、未修 resolver，回 HTTP 502；因此正式 shim 需要相容性修改與重新驗證。這是帳號池的一次成功，沒有個別 acct1／acct2／acct3 額度或成功率結論。沒有編輯或重啟正式 18795 服務。

Goose v1.52.0 官方 archive 的 SHA-256 再驗為 `4aee1f770b405c44194c0e9407df1fb06bda4c50eee935f0d8fd10731821cc5e`。本機暫時解壓 binary 回報 `1.52.0`。同一隔離 Opus-thinking shim 下，PR 的 GooseACP 以 task-scoped MCP 指向 fake HTTP task endpoint；ACP `stopReason=end_turn`，fake endpoint 僅收到一次 `task_send`，文字 `SMOKE_TASK_SENT`。此證據不涉及真 BAT，也沒有通過 live Goose restart／UI／approval gate。

## 檢查結果

`fe56575` 的全庫 pytest 在 Python 3.10.20、3.11.15、3.12.13、3.13.13 各為 **232 passed、1 skipped**；`f59e359` 的兩項 High 修復後各為 **235 passed、1 skipped**。Jev test-gap 補測後，四個 Python 版本各為 **237 passed、1 skipped**，`ruff check .` 與 `git diff --check` 通過。舊驗證 deadline 測試曾用 50 ms 人工期限而在併行排程壓力下提前截止；調整成 1 秒並以 2 秒舊時間戳測試後，四版本全庫重跑通過。
