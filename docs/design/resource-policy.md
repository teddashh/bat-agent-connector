# 資源政策：人工 session 對 API 永久唯讀

日期：2026-10-07。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 D05、D06、§06、§24，工作包 W02（全 mutation 政策、canonical path、manual 保護），驗收 A01、A02。程式在 `src/bat_agent_connector/resource_policy.py`，測試在 `tests/test_resource_policy.py`。

## 保證

每個 BAT 寫入 frame 都要帶一張 `WriteGrant`。`BatClient.invoke` 在送出前核對 grant 的 host、channel 與 `sessionId`，不符就丟 `ResourceReadOnly`，frame 不會離開程序。`append_workspace_terminal`（`workspace:save`）同樣檢查。只有 `resource_policy.py` 會建立 grant，`test_only_the_policy_mints_write_grants` 掃描原始碼確認這點。因此 MCP、`batc`、task service 與舊工具都走同一個檢查，`confirm`、`force`、`discard_uncommitted`、`allow_unmerged`、`all_exhausted`、`approve_pending` 都不能繞過。

人工（`manual`）與來源不明（`unknown`）的 session 永遠不收到 send、continue、answer、interrupt、client-resume、權限變更、批次批准、stop、rehydrate、merge、remove 或 cleanup。

## Session 來源

| 來源 | 證據 |
|---|---|
| `connector_managed` | Connector registry 有這個 session 的建立紀錄（`registry.reserve` 先寫入的 `created_at`，或 task journal 回復時經 BAT 身分核對的 `recovered_from = task_journal`），而且 BAT 已確認啟動（狀態不是 `starting`、`uncertain`、`failed`）。 |
| `manual` | BAT workspace 有這個 tab，但 connector 沒有建立紀錄。永久唯讀，不會轉成 managed。 |
| `unknown` | 其他情況：沒有 tab 也沒有紀錄，或 connector 預留了 ID 但 BAT 沒確認啟動。對帳完成前唯讀。 |

`has_tab`、`orchestrated`、provider、資料夾名稱、UI 認領或口頭確認都不授予寫入。重試啟動留下的同 session 多筆 registry 紀錄，以最新一筆為準。

## 工作目錄歸屬

Session 歸屬與資料夾歸屬分開判斷。Managed session 只有在 connector 擁有它的工作資料夾時才可驅動：

| 歸屬 | 條件 | 隔離程度 |
|---|---|---|
| `managed_root` | 資料夾在主機設定的 `managed_roots` 內（connector 自有 clone）。 | `managed_clone` |
| `connector_worktree` | 紀錄的 `worktree_path` 等於 `cwd`，位於 workspace 資料夾（或其上層 git root）的 `.bat-worktrees/<name>`，而且是 connector 自己建立的；失效接手的 successor 與 reviewer 共享的 worktree，要追溯到同樣條件的 managed session。 | `legacy_shared_clone` |
| 人工 | 主 checkout、BAT GUI 建立的 worktree、共享人工 session 的 worktree。 | 無 |

`legacy_shared_clone` 的 worktree 仍在人工 clone 內，共用它的 refs 與物件庫（見 git-worktree(1)），不是完整隔離。只有 `managed_clone` 符合計畫 §07 的獨立 clone。位於人工資料夾的 connector session 是 §24 說的 legacy boundary：保留觀測與歷史，全部唯讀（包括 stop），由 Ted 在 BAT 處理。

## 寫入前即時核對

Registry 只是 connector 自己的說法。每次寫入前再讀 BAT：

1. `claude:get-session-meta` 的 `cwd` 要等於紀錄的資料夾。
2. Worktree session 的 `worktree:status` 路徑要等於紀錄。
3. `git:getRoot(cwd)` 要等於 worktree 本身（managed root 則要落在 managed root 內）。指回主 checkout 的連結會在這裡被擋下。

不符回 `BINDING_MISMATCH`。送字、回答、權限與 merge 另外要求資料夾存在（`WORKDIR_MISSING`）；stop、interrupt、remove 在資料夾已消失時仍可執行。

`managed_roots` 請填實際路徑（不要經過 symlink），因為 git root 回傳的是解析後的路徑，不一致會被拒絕。

## 目的端

- **新 session**：不能直接在人工 checkout 工作（`use_worktree=false` 只限 managed root）。在人工 clone 內開新 worktree，只有 `shared_clone_worktrees = true`（預設，legacy）時允許。BAT 回傳的 worktree 不在預期位置時中止，且不 rollback（不刪一個位置不明的資料夾）。
- **Merge**：BAT 的 `worktree:merge` 在主 checkout 執行 `git checkout`／`merge`，只有主 checkout 位於 managed root 時才允許，否則回 `DESTINATION_MANUAL`。`session_cleanup` 對準備好合併但目的端是人工 checkout 的工作改判 `ESCALATE`。
- **Task service 的 SSH worktree**：只能是 `<workspace>/.bat-worktrees/batc-task-<12 hex>` 與分支 `batc/task-<12 hex>`。

## 全 mutation 清單

權威來源是 `resource_policy.MUTATIONS`；`batc policy HOST` 與 MCP `session_policy(host)` 輸出同一份表，`test_mutation_table_classifies_every_bat_write_channel` 確認每個寫入 channel 都有歸類。

| 動作 | 入口 | 規則 |
|---|---|---|
| `session.send` | `session_send`、`session_continue`、`session_relay`、task service send | managed session ＋ connector 擁有的資料夾 |
| `session.answer` | `session_answer`、`approve_pending` | 同上 |
| `session.permissions` | `session_set_permissions`、`approve_pending` | 同上 |
| `session.interrupt` | `session_interrupt`、task interrupt／`work_pause(abort_current)` | 同上 |
| `session.stop` | `session_cleanup` | 同上 |
| `worktree.rehydrate`、`worktree.remove` | `worktree_merge`、`worktree_remove`、`session_cleanup` | 同上 |
| `worktree.merge` | `worktree_merge`、`session_cleanup` | 同上，且目的端在 managed root |
| `session.create` | `session_start`、`session_failover`、`session_relay(start_if_missing)`、fan-out、task lead／reviewer 啟動 | 先在 registry 預留 ID；資料夾是 managed root、connector 新建的 worktree，或共享 connector 擁有的 worktree |
| `workspace.register_tab` | `session_start`、task reviewer 啟動 | 只為剛啟動的 managed session 追加 tab，其他 tab 必須保持不變 |
| `task.external_worktree` | task service 的 `base_branch` 啟動與整理（SSH git） | 固定命名的 connector worktree |

只寫 connector 自己資料的動作（`session_record_verification`、`work_*` 帳本）不碰 BAT 或 Git，不需要 grant。

## 拒絕代碼

| 代碼 | 意思 |
|---|---|
| `MANUAL_READ_ONLY` | 在 BAT 建立的 session。 |
| `UNKNOWN_READ_ONLY` | 來源無法證明，或啟動尚未確認。 |
| `WORKDIR_NOT_MANAGED` | Managed session 但資料夾是人工的（legacy boundary）。 |
| `BINDING_MISMATCH` | BAT 的實際狀態和 connector 紀錄不符。 |
| `WORKDIR_MISSING` | 需要資料夾的動作，但資料夾讀不到。 |
| `DESTINATION_MANUAL` | 新 session 或 merge 的目的端是人工 checkout。 |
| `DESTINATION_UNKNOWN` | 目的路徑不是絕對路徑，或 BAT 建在預期外的位置。 |
| `TIER_DISABLED` | 只出現在 `session_policy`：主機沒開對應層級。 |
| `GRANT_REQUIRED`、`GRANT_MISMATCH` | 程式缺陷：某段程式沒經過政策就要送寫入 frame。 |

## 升級後的行為差異

- `session_relay` 不再寫入人工主 session。預設目標改為同 workspace 最近的可寫 managed session；沒有可寫目標時回 `no_session` 或 `read_only`，`start_if_missing=true` 在新 worktree 開 Codex session。
- `session_failover` 只接續 managed session。人工 session 的後續工作應從其 commit 另開 managed worktree（計畫 §12，checkpoint 流程屬 P2）。
- `fanout_plan_session` 的 planner 在自己的 worktree，不在主 checkout。
- `approve_pending` 跳過唯讀 session（`skipped: read_only`）。
- `session_cleanup` 對人工與 legacy session 一律 `KEEP`，不 stop、不 merge。
- `sessions_list`、`sessions_triage`、`worktree_status` 每列多了 `provenance` 與 `api_access`。

## 尚未涵蓋

- **A10 執行環境限制**：本政策只管 connector 自己送出的 frame。BAT 上的 agent 仍可依對話中的絕對路徑寫入人工目錄；這需要 host 帳號權限、sandbox 或 ACL，屬 P2 managed clone 工作。在那之前，不能把 `legacy_shared_clone` 描述為完整隔離。
- **Managed clone 的建立與 checkpoint 接續**（P2）。目前 `managed_roots` 只描述已存在的 clone。
- **`workspace:save` 與 GUI 同時存檔的 race**（既有，見 SECURITY.md）。
- **HTTP API**：目前只有 MCP 與 CLI，兩者呼叫同一組 service 函式；之後的 HTTP 層也要走同一組函式。

## 設定

```toml
[hosts.buildbox]
managed_roots = ["/srv/batc-managed"]   # connector 自有 clone；可合併到其主 checkout
shared_clone_worktrees = true           # false：只允許在 managed root 內開新 worktree
```
