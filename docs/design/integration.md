# Integration：把成果放進既有 PR（更新 PR 成果）

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §14（Git 成果整合）、驗收 C01–C03 與工作包 W06。程式在 `integration.py`，經 [OperationService](api-v1.md) 執行；資源規則見 [resource-policy.md](resource-policy.md)；成果來源見 [checkpoints.md](checkpoints.md)。

## 三個 action

| Action | Scope | 做什麼 | 寫入 |
|---|---|---|---|
| `integration.preview` | integrate | 釘住 PR head 與每個來源的 SHA，列出會進 PR 的每個 commit 與檔案、重疊、依賴，預測結果與衝突，並以 `push --dry-run` 確認主機能推送 | 只寫整合區（物件與 `refs/batc/pv/…`） |
| `integration.apply`（更新 PR 成果） | integrate | 依預覽的來源與順序組合，檢查只多了預覽列出的 commit，一般 push 一個確切 SHA 到 PR 的 head 分支，再讀遠端確認 | 整合區，加上遠端的一個分支 |
| `integration.handoff`（交給 agent 解衝突） | integrate，另需 start | 在整合區為停在衝突的 apply 建一個 repair worktree，開一個受限的 managed session 解衝突 | 整合區的 `wt/batc-fix-<12 hex>` 與分支 `batc/fix-<12 hex>`，加上一個新 session |

`integrate` 是獨立的 scope：`merge` token 不能推送，`integrate` token 不能合併（計畫 §15、C07）。Agent 的 token 只有刻意發行時才有它。

Apply 只接受 `params.preview_id`，並要求 `preconditions.expected_head_sha` 與 `preview_digest` 等於預覽的值；來源永遠來自已保存的預覽，不能在 apply 加減或換順序。預覽一小時後過期。同一個 PR 同時只能有一個未結束的 apply；apply 進行中不能合併，合併進行中不能 apply（`INTEGRATION_IN_PROGRESS`、`MERGE_IN_PROGRESS`）。

## 來源

| kind | id | 釘住的版本 | 從哪裡讀 |
|---|---|---|---|
| `checkpoint`（人的成果） | `cp_…` | checkpoint 的 commit（不會變） | 人的 repository，只當 `git fetch` 的來源 |
| `checkpoint_run`（agent 成果） | `checkpoint.continue` 的 `op_…` | 預覽當下該分支的 tip | connector clone（必須在 managed root 內） |
| `branch`（GitHub 上同 repo 的分支） | 分支名稱 | 預覽當下遠端的 tip | `integrate.remote_url` |

每個來源可選 `mode: "merge"`（預設）或 `"pick"`（`commits` 列出要複製的 commit，各自帶 `(cherry picked from commit X)`）。來源與 PR 必須在同一台主機（`SOURCE_ON_OTHER_HOST`）。Task Service 的執行結果之後再加。

## 整合區

每個（主機、repository、remote URL）一個 bare repository：`<第一個 managed root>/.batc-integration/<name>-<8 hex>/repo.git`。不沿用 checkpoint clone：那個 clone 的設定、refs 與 hooks 和在它 worktree 裡工作的 agent 共用，agent 可以改 `origin` 或 `insteadOf`。

- 建立前先確認 managed root、`.batc-integration` 與整合區本身都是真實目錄（不是連結），所以連到人資料夾的 managed root 在寫入任何東西之前就被拒絕（`DESTINATION_MANUAL`）。
- 每個腳本動手前核對身分：真實路徑、`batc.*` 標記、本地設定白名單（任何 `remote.*`、`url.*`、`core.hooksPath`、`include.*`、`credential.*` 都會被拒），沒有 grafts、shallow、alternates、`commondir` 或 `refs/replace`，以及 repository 裡沒有任何連結：連到別處的 `objects`、`refs` 或 `packed-refs` 會把寫入送到那裡（`CLONE_NOT_OURS`、`CLONE_CONFIG_TAMPERED`）。
- `ls-remote` 以尾端比對 ref（`refs/heads/a/refs/heads/x` 也符合 `refs/heads/x`），所以腳本只取名稱完全相同的那一列。
- 組合只用 git plumbing（`merge-tree --write-tree`、`commit-tree`、`update-ref`），不 checkout，所以 hooks、filters、fsmonitor 都不會在推送前執行；組合時隔離主機使用者的 global／system 設定，簽章、merge driver、rerere 不會改變結果。網路操作（ls-remote、fetch、push）用主機使用者的設定，才有 git 憑證。
- Connector 的 commit 身分固定為 `BAT Connector <bat-connector@noreply.invalid>`，日期是 operation 建立時間，所以重算同一步會得到同一個 SHA；結果 ref 以 compare-and-swap 設定，已有不同的值就停下（`COMPOSE_NOT_DETERMINISTIC`）。Commit 訊息只有種類、ID、SHA 與 operation ID，沒有主機路徑或對話內容。

## integration.preview

1. 讀 PR（daemon 的 GitHub token，只讀）。PR 已關閉、head 在 fork、head 分支是 base、預設分支或 `integrate.protected_refs` 中的分支時，直接回帶 `blocking` 的預覽，不碰主機。
2. `prepare`：建立整合區；以主機憑證 `ls-remote` PR 分支與 `refs/pull/<n>/head`；逐一讀來源的 tip、以 SHA 從記錄的位置 fetch（本機路徑優先），釘在 `refs/batc/pv/<12 hex>/src/<seq>`；最後 fetch PR head 並做 `push --dry-run`。
3. `analyze`：每個來源的 merge base、會進 PR 的 commit（最多列 200 個，另給總數）、檔案、PR 那邊改過的檔案；從 PR head 開始依序模擬 fast-forward、merge 或 pick。第一個衝突之後的來源標 `not_predicted`。
4. 每個 commit 標 `own`（來源自己的工作）、`from_seq_N`（另一個已選來源的工作）或 `foreign`。例如 agent 分支從 Ted 尚未推送的 checkpoint commit 開始，只選 agent 成果時那個 commit 也會進來，預覽標 `foreign` 並警告 `BRINGS_FOREIGN_COMMITS`。這是「不悄悄多加來源」的做法：每個會進 PR 的 commit 都列出來。

`blocking`（不能 apply）：`PR_CLOSED`、`PR_HEAD_IN_FORK`、`TARGET_REF_FORBIDDEN`、`INTEGRATION_IN_PROGRESS`、`MERGE_IN_PROGRESS`、`REMOTE_REF_MISSING`、`REMOTE_IDENTITY_MISMATCH`（主機的遠端與 GitHub 對 PR head 說法不同：`remote_url` 指到別的 repository，或 GitHub 還沒更新）、`PUSH_ACCESS_DENIED`、`SOURCE_MISSING_REF`、`SOURCE_UNAVAILABLE`、`SOURCE_UNRELATED`、`PICK_*`、`LFS_UNSUPPORTED`、`NOTHING_TO_INTEGRATE`。預計衝突不擋：apply 會停在那裡。

`warnings`：`BRINGS_FOREIGN_COMMITS`、`UNCOMMITTED_NOT_INCLUDED`（人的 checkpoint 記錄時有未提交修改）、`SESSION_STILL_WORKING`、`DEPENDS_ON_UNPICKED`、`REDUNDANT_SOURCE`、`DELIVERED_EARLIER`、`PR_DRAFT`、`PUSH_ACCESS_UNPROVEN`。

`digest` 是 host、repository、PR、head 分支與 SHA、remote URL、預測的 tree 與每個來源（kind、id、mode、commits、釘住的 SHA）的 SHA-256。

## integration.apply

| 步驟 | 做什麼 | 讀回 |
|---|---|---|
| 開始前 | 第一次執行時為每個來源寫一列 `pending` receipt；PR 必須仍開著、head 仍是預覽的 SHA（GitHub 與主機的 `ls-remote` 兩邊都核對），ref-based 來源的 tip 仍是釘住的 SHA | 不符時 `failed`（`TARGET_HEAD_CHANGED`、`SOURCE_CHANGED`），什麼都還沒做 |
| `prepare` | 確認物件都在，把來源與 base 釘在 `refs/batc/ops/<12 hex>/…` | 冪等，重跑 |
| `compose.<seq>` | 依序 fast-forward、merge commit 或 pick | 確定性加 compare-and-swap，重跑得到同一個 SHA |
| `check.<12 hex>` | `base..head` 只含預覽的 commit 與 connector 的 merge／pick commit、所有來源都在、沒有衝突標記；沒有用到人工解衝突時 tree 必須等於預測 | 只讀，重跑 |
| `push.<12 hex>#<n>` | 推送前一刻 `ls-remote` 必須仍是 base，然後 `git push --porcelain --no-verify <url> <sha>:refs/heads/<ref>` | 回覆遺失時先讀遠端，見下 |
| 確認 | GitHub 顯示新 head；GitHub 落後於 git 時只加警告（`GITHUB_LAGGING`），不等待，所以取消不會把已落地的更新記成取消；遠端被改寫時 `needs_attention` | — |

衝突：第 k 項衝突時，receipt 記 `conflict` 與檔案，前面的項目已在整合區完成，什麼都沒推送，operation 停在 `needs_attention`（`INTEGRATION_CONFLICT`）。出路是交給 agent 解（見下），或取消、不含它重新預覽。

## 交給 agent 解衝突（integration.handoff）

1. `repair.prepare`：在整合區加 worktree `wt/batc-fix-<12 hex>`（分支 `batc/fix-<12 hex>`），停在第 k-1 項之後的結果，`merge --no-ff --no-commit` 第 k 項，留下衝突。已存在的 worktree 必須仍是這個衝突（或已 commit 在它上面），否則 `REPAIR_STATE_MISMATCH`。
2. 和 checkpoint 接續同一套步驟（`checkpoints.start_in_worktree`）：BAT 看到 worktree 在預期的 commit、啟動 session（`write_scope: "confined"`）、送出第一個指令。指令列出衝突檔案，要求保留兩邊的意圖、跑測試、以 `git commit --no-edit` 完成**一個** merge commit，不 push、不 rebase、不改 git 設定。
3. 人（或 Hermes）在 session commit 後對 apply 按 Resume。Apply 在 session 還在工作時等待（`waiting_external`，有上限），之後讀 worktree：沒 commit 是 `RESOLUTION_INCOMPLETE`；有未提交修改、不只一個 commit、parents 不是（前一項的結果、第 k 項）或留有衝突標記是 `RESOLUTION_INVALID`；都符合就在 `resolve.<k>.<12 hex>` 步驟裡再驗一次並以 SHA 釘住，receipt 記 `resolved`、`resolution_sha` 與 remerge-diff 統計（agent 在解衝突之外多改了什麼）。之後 worktree 不再被讀，第 k+1 項以後接著組合，前面的項目不重新組合。

Agent 可能在 worktree 設 `user.name`／`user.email`，所以整合區的設定白名單包含這兩個；組合時 connector 一律用自己的身分。Codex 的 sandbox 只允許寫 worktree，commit 寫入整合區的物件時會請求核准，由人回答。

推送回覆遺失（timeout、SSH 中斷、讀不懂的輸出）時，**不重推**，先讀遠端。SSH 中斷只結束本機的 ssh，主機上的 `git push` 可能還在跑：推送腳本執行期間在整合區留下自己的 PID，讀回時那個程序還在就繼續等。

| 遠端顯示 | 結果 |
|---|---|
| 等於我們的 head | 已推送 |
| 仍是 base | 還不能算沒到：推送可能已落地、之後被設回 base。GitHub 說組合後的 commit 不存在才再送同一個一般 push；存在時停在 `PUSH_UNPROVEN`，不再推 |
| 包含我們的 head（之後又有人推） | 已推送，警告 `REMOTE_MOVED_AFTER` |
| 從 base 往前、但不含我們的 | `REMOTE_MOVED`，沒推送 |
| 分支不見 | `REMOTE_REF_MISSING` |
| 讀不到 | GitHub API 只作為正向證據（API 顯示我們的 head 才算推送），否則維持 `uncertain`，退避重讀，最後 `UNCERTAIN_UNRESOLVED` |

推送結果對照：`=` 或 `already` 算推送；`!`（non-fast-forward、fetch first）是 `REMOTE_MOVED`；`! [remote rejected]` 是 `PUSH_REJECTED`（保護規則、簽章要求）；認證錯誤是 `PUSH_AUTH_FAILED`（修好憑證後 Resume）；`+` 或 `-` 不可能出現，出現就是 `INTERNAL_PUSH_SHAPE`。推送的舊值不等於 base（推送前一刻分支被往回改）時 commit 已落地，receipts 記為 delivered，operation 先停 `REMOTE_REWOUND_BEFORE_PUSH` 讓人看一下，Resume 後以警告完成；`*`（分支被刪後重建）同理是 `REMOTE_REF_RECREATED`。永遠不用強制推送修正。

## 不重複接收、不清理人的來源

`integration_receipts` 每個來源一列：`pending`、`composed`、`already_included`、`conflict`、`delivered`。只有在證明新狀態的步驟之後才改，用 `UPDATE … WHERE status IN (…)`，所以重播是 no-op，事件只在真的改變時發出。`delivered` 只在 git 讀回證明推送之後寫入，不會降級。讀取時才算 `effective_status`：失敗或取消的 operation 裡沒送達的列讀成 `not_delivered`；推送步驟從未證實（`started`／`uncertain`）時讀成 `unknown`（取消不會執行 handler，所以不能在 handler 裡改）。

一旦有推送步驟（不論狀態），apply 重跑時不再先讀 PR 狀態或做准入檢查，直接讀遠端：PR 被合併或 GitHub 出錯都不能讓一個可能已落地的推送被記成「沒推送」。OperationService 在讀回證明某步驟沒發生、準備再做一次之前，會先看有沒有取消，所以取消一個推送未證實的 apply 不會在取消後才把它推出去。

同一個 operation 內，步驟重播加上 (operation, seq) 主鍵保證只接收一次；跨 operation 時，git 祖先關係讓已在 PR 的來源在預覽與組合時都是 `already_included`，`DELIVERED_EARLIER` 警告曾經送過。刻意不在 delivered 上加跨 operation 的唯一限制：分支被改寫後重新送同一個來源是真的新事件。

Receipt 記 `location_class`（`human_checkout`、`managed_clone`、`remote`），之後的整理（§23）據此永遠不選人的來源。W06 只刪除自己的暫存（整合區內的 `batc-tmp-*`、`batc-check-*`），沒有 `branch -D`、`update-ref -d` 或 `gc --prune`。

## 憑證

Daemon 的 `[github]` token 只用來讀 PR（Pull requests read、Metadata read），不送到主機，不放進 URL 或腳本。每個 git 網路操作都在 BAT 主機上以 SSH alias 的使用者、用那個使用者對 `remote_url` 的 git 憑證執行（SSH key、deploy key、credential helper）。所以：

- GitHub 把推送記在那個憑證的帳號，不是 GitHub App，也不一定是 Ted；operation 另外記錄 API actor 與 `pushed_via: {host, remote_url, credential: "host"}`。
- Connector 無法縮小那個憑證。若它是 Ted 的個人 key 或管理員，connector 的推送靠上面的檢查不會強推或刪分支，但同一 OS 使用者下的 agent session 也能用它推送；agent 自己的推送會以 `REMOTE_MOVED` 出現，而不是被阻擋。建議用 machine user 或每個 repository 的可寫 deploy key（沒有 admin 或 bypass），並以分支保護擋強推與刪除。
- 憑證必須不需互動（`GIT_TERMINAL_PROMPT=0`、BatchMode）。預覽的 `push --dry-run` 在按鈕啟用前證明能推送；`integrate.hosts` 指定哪些主機可以推送這個 repository，因為不同主機的憑證可能不同。
- 用真實帳號推送會觸發 PR 的 workflows（GITHUB_TOKEN 的推送不會），分支保護也可能撤銷舊的 approval。

## 設定

```toml
[[github.repos]]
repository = "owner/name"
integrate = { hosts = ["workstation"], remote_url = "git@github.com:owner/name.git" }
```

- `remote_url` 必須是這個 repository 在這個 GitHub 上的 `git@`、`ssh://git@` 或 `https://` URL，不能帶帳密、query 或其他使用者；本機路徑只在 `[github] api_url` 是 loopback（測試）時允許。
- `protected_refs` 預設 `main`、`master`、`release/*`、`releases/*`、`production`、`staging`；PR 的 base 與預設分支一律拒絕。
- `fetch_timeout_s`（60–7200，預設 1800）：第一次預覽會 fetch 整個 repository。
- `workspace`：解衝突的 session 要開在哪個 BAT workspace；衝突來源是 checkpoint 或 checkpoint run 時用它自己的 workspace，GitHub 分支才需要這個設定（沒有時 `RESOLVE_UNAVAILABLE`）。
- 主機需要 `[verification] ssh_hosts` alias、managed root 與 write、orchestrate tier；git 2.38 以上（pick 需要 2.40）。

## 讀取與入口

- HTTP：`GET /api/v1/integrations/candidates?host=`（可放進 PR 的 agent 成果與 checkpoint，以及送過的 PR）、`/integrations/previews/{ipv_…}`、`/integrations?repository=&pull_number=`、`/integrations/{op_…}`（含 receipts）；PR 卡片（`/repositories/{o}/{r}/pulls/{n}`）多了 `integration`。`capabilities.features.integration` 列出能整合的 repository 與主機。
- MCP：`integration_candidates`、`integration_get`、`integrations_list`；寫入用 `operation_submit`（docstring 有完整流程）。
- CLI：`batc integrate candidates|preview|apply|handoff|show`；apply 只需要 `ipv_…`，其餘從預覽讀出；Resume 用 `batc op <op_id> --resume`。
- Dashboard：成果與 GitHub 頁的 PR 卡片有「更新 PR 成果」區塊，和「合併 PR」分開。選來源、排順序後自動預覽；預覽過期或 PR head 變了按鈕就停用。完成後顯示新 head 並提醒本機資料夾不會自動更新。Operation 頁有各來源紀錄。

## Repair 的執行限制（A10）

`integration.handoff` 共用 checkpoint 的 confined start：Claude 未查核 account 時用 default；BAT acceptEdits 沒有 path check，只有查核 account 才使用它。Codex workspace-write/on-request 最多 options_confirmed。Operation refs／結果保存 snapshot 與 current verification，表單依 host／agent 提示限制；force／bulk／persistent raises 不放寬 repair。沒有改 composition／PR／deploy policy。A10 尚待 W12 live run，見 [confinement](confinement.md)。

## 尚未涵蓋

- 整合後在 managed worktree 跑測試（`integrate.verify`）、Task Service 的執行結果作為來源、pick 模式的衝突交給 agent。
- 遠端前進時自動重新整合；第一版一律停在 `REMOTE_MOVED`，請重新預覽。
- 衝突時只推送前面完成的部分、建立新 PR、fork PR、stacked PR、Git LFS、跨主機來源、未提交內容。
- 整理整合區（§23）。
