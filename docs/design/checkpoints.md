# Checkpoint：從人的版本另開 agent 工作

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §12（Checkpoint 接續與獨立執行）與工作包 W04。程式在 `checkpoints.py`，經 [OperationService](api-v1.md) 執行；資源規則見 [resource-policy.md](resource-policy.md)。

## 兩個 action

| Action | Scope | 做什麼 | 寫入 |
|---|---|---|---|
| `checkpoint.create` | operate | 讀來源 session 的資料夾、git root、分支、commit、未提交修改數，與最近 `last_n`（0–50）則對話 | 只寫 Connector 自己的 journal（`checkpoints`）；BAT 只用讀取 channel |
| `checkpoint.continue` | operate | 在 Connector 自有 clone 的新 worktree 與分支上，從 checkpoint 的 commit 開新 BAT session，確認起點後才送第一個指令 | 只在 managed root 內寫 |

來源可以是任何 session，包括人在 BAT 建立、API 永久唯讀的 session。來源 session 與它的資料夾不會被送字、stash、commit、checkout 或鎖住。

## checkpoint.create

1. 經 inventory 的唯讀 fleet（client 核心拒絕所有寫入 channel）：`claude:get-session-meta` 取資料夾（沒有就用目錄裡的 `cwd`），`git:getRoot`、`git:branch`、`git:log`。
2. 指定 `commit`（完整 40 hex）時，必須在來源分支最近 200 個 commit 內，否則 `COMMIT_NOT_FOUND`。沒指定就用 HEAD。
3. 未提交修改數（`dirty`）經主機的 SSH alias 以 `git --no-optional-locks status --porcelain` 讀取；沒有 alias 時記為 `null`（未觀測）。不用 BAT 的 `git:status`：BAT 執行一般的 `git status`（`git_get_status_native`），工作檔的 stat 資料過期時會刷新並改寫人的 `.git/index`；失敗時它回 `[]`，看起來像「乾淨」。第一版只帶已提交的 commit，未提交內容不會進新工作（`preview.snapshot.supported = false`）。
4. 讀對話摘錄，經 secret 遮蔽後存成固定內容與 SHA-256。
5. 再讀一次 HEAD（SSH 讀到的 HEAD 也要一致）；沒指定 commit 而 HEAD 變了，回 `SOURCE_MOVED`，請使用者重做（計畫 §12「前後指紋」）。

Checkpoint ID 由 operation ID 衍生（`cp_<32 hex>`），所以重跑同一個 operation 不會產生第二個 checkpoint。之後來源分支前進，不會改變已選定的 checkpoint。

## checkpoint.continue

BAT 的 `worktree:create` 不能指定起點 commit，所以 clone 與 worktree 由 Connector 經主機的 SSH alias 以 git 建立（與 verification 共用 `[verification] ssh_hosts`）：

1. `worktree.prepare`：在主機第一個 `managed_roots` 下的 `<repo>-<8 hex>`（同一主機、同一來源 repository 共用一個）準備 clone，再加 worktree `<clone>/.bat-worktrees/batc-cp-<12 hex>` 與分支 `batc/cp-<12 hex>`，起點是 checkpoint 的 commit。腳本可重跑：已存在的 clone 與 worktree 直接沿用。
   - `git clone` 與 `git fetch` 只讀人的 repository。clone 的 `origin` 改成來源自己的 origin URL（沒有就移除），所以從 clone push 不會進到人的 repository。
   - Clone 先建在暫存目錄，標上 `batc.managed-clone` 與 `batc.source` 後才搬到正式位置。目標路徑已存在但不是 Connector 的 clone（或屬於別的來源）時中止（`GIT_FAILED: not a connector clone`），不接管別人的資料夾。
2. 腳本回報的 HEAD 必須等於 checkpoint commit 且乾淨，否則 `START_MISMATCH`。
3. `session.start`：`session_start` 以 `cwd_override` 在 worktree 開新 session，session ID 由 operation ID 衍生；資源政策確認目的地在 managed root 內（`managed_clone`），並用 `git:getRoot` 確認沒有連結到 managed root 外。
4. 送第一個指令前，BAT 自己的 `git:log` 必須在新 session 的資料夾看到 checkpoint commit（計畫 §12 第 5 步）。
5. `send`：第一個指令的第一行是 `[batc checkpoint <checkpoint_id> · <operation_id>]`，接著是 repository、來源分支與 commit、新分支與資料夾、未提交修改的提醒、對話摘錄（超過長度時保留最新的），最後是使用者的指示原文。
6. 記入 `checkpoint_runs`，並立刻更新該主機的目錄，讓新 session 馬上出現在 Dashboard。

每一步都是 operation step，回應遺失時以讀回判斷，不重送：

| 步驟 | 讀回 |
|---|---|
| `worktree.prepare` | 腳本可重跑，直接重跑 |
| `session.start` | Registry 沒有預留紀錄：start frame 從未送出，可以重跑。BAT 的 session meta 顯示該 ID 在這個 worktree：補記成功。其他情況（包括 meta 是 null；BAT 可能還在啟動）：維持 `uncertain` 稍後再讀，不再啟動第二次 |
| `send` | Claude：BAT 接受該 `clientMessageId` 後寫入的 turn 紀錄。Codex：新 session 對話中開頭是上述第一行的 user 訊息 |

新 session 的 registry 列與 `checkpoint_runs` 都記下來源；`GET /api/v1/sessions/{host}/{id}` 回 `started_from`。

## 讀取

- `GET /api/v1/checkpoints?host=&session_id=&limit=`：列表（不含摘錄，只有則數）。
- `GET /api/v1/checkpoints/{id}`：含摘錄與從它開出的 sessions（`runs`）；`live=true` 另回 `source.advanced`（來源分支是否已前進，計畫 §12「來源已有新版本」）。
- `GET /api/v1/sessions/{host}/{id}/checkpoint-preview`：記錄前的預覽（只讀）：branch、HEAD、最近 20 個 commit、`dirty`。
- MCP：`checkpoints_list`、`checkpoint_preview`、`checkpoint_create`、`work_continue_from_checkpoint`（後兩個與 `operation_submit` 同樣以 `BATC_API_TOKEN` 的身分執行，需要 `confirm=true`）。CLI：`batc checkpoint create|continue|list|show`。
- `capabilities.features.checkpoints` 列出能接續的主機（有 SSH alias、managed root、write 與 orchestrate tier）。

Dashboard 的 session 頁有「版本（checkpoint）」區塊：從最近的 commit 中選一個、寫下需求原文後記下版本；列出 checkpoint（來源已有更新的 commit 時會標示），展開後輸入指示即可開始。完成的操作頁有「開啟新 session」，新 session 頁標出它從哪個版本開出。

## 設定

```toml
[hosts.workstation]
writes = true
orchestrate = true
managed_roots = ["/srv/batc-managed"]   # 第一個是 Connector clone 的位置；請填實際路徑
```

```toml
# BATC_TASK_SETTINGS 指向的設定（0600）
[verification]
ssh_hosts = { workstation = "workstation-alias" }   # ~/.ssh/config 的 alias，BatchMode
```

## 尚未涵蓋

- 未提交內容的唯讀 snapshot（計畫 §12「未提交修改」）：目前只顯示 `dirty` 提醒。
- 跨主機接續：新工作固定在 checkpoint 所在的主機。
- 附件與 artifact revisions、work item 關聯（W05）。
- Managed clone 的清理：worktree 與分支保留，由之後的整理工作處理。
