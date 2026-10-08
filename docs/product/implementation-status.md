# Tauri v2 實作狀態

查核日期：2026-10-08。依 [v2 範圍](realignment-v2.md)；歷史交接見
[`2026-10-08-dispatch.md`](../handoff/2026-10-08-dispatch.md)。此表以 source evidence
追蹤，不以測試數或 PR 數代替產品驗收。開工時 main 為 `2568520`（#41 已合併）；
本輪已依序合併 #36（`800f6ec`）及 #35（`8e687fb`）。下面的接手基線保留歷史，
目前進度以「本輪進度」為準。

## 本輪進度

以下為 2026-10-08 22:35 UTC 查核點；PR heads 與 CI 請再即時核對。

| 工作 | 現在的成果 | 驗證與下一步 |
| --- | --- | --- |
| #36 Operations Part A | 已合併：pause/verifier 取消語意、coordinator 發出的 failover authority、最終 frame gate | 合併 head `3ccbe92` 的 CI 與 Codex 審查通過 |
| #35 Observation Part A | 已合併：歷史/relations、穩定 inventory cursor、舊 reviewer carrier 拒絕、durable operation actor | 合併 head `feed51b` 的 CI 與 Codex 審查通過；frontend 另列 R04 |
| #37 Confinement | 本機 `09faafd`：Python 啟動前 closure proof、同 ID retry、worktree 移除讀回、整合 start frame gate | 3.13 full：1619 passed/33 skipped；3.10 與 CI 執行中；獨立本機 Codex 審查無新發現 |
| #38 Cleanup Part A | 本機 `ef18d5f`：shared IDs/flock、start claim/reservation、移除 host、容量 retirement、bookkeeping refusal | 3.13 full：1835 passed/33 skipped；3.10：1834 passed/33 skipped/1 個 60 秒 settlement timeout。journal 顯示持續進展；原碼單測重跑 2.52 秒通過；已 push 跑隔離 CI，先 #37 再 #38 |
| #39 Hub import | 已關閉、不合併；保留舊 branch | 不再作為任何新功能的依賴 |
| #43 Canonical skills | draft `6927f5f`：canonical 產生兩份薄 wrappers；agent MCP `--principal-only` 強制自己的 token | 3.13/3.10 full、CI、Codex 通過。新 cleanup/artifact adapters 要一併維持同樣身份限制 |
| #44 Tauri foundation | draft `c9a470b`：共用 frontend、native central bridge、tray/instance、signed checkpoint refresh barrier | Windows NSIS/Linux deb CI、Codex 通過；Linux 真正 WebKit fixture 通過，尚非 Windows/live 驗收 |
| #45 Fleet desktop | draft `525fe48`：固定 PowerShell facade、受限 native IPC、logical connection selection 與 config/revision/epoch preconditions | 全部最新 CI 通過，含 Windows 原生 subprocess、NSIS 與 Linux deb；固定 system PSModulePath 修正 startup；獨立本機 Codex delta review 通過；未實機安裝 |
| Fleet Kit #8 | 已合併 `d3697dc`（head `2ec4b11`）：headless facade、唯一 monitor owner、CAS preferences、applied configuration binding | 最新 Windows 5.1/7 各 219 passed/1 skipped；Linux 213 passed/7 skipped，24 scripts 檢查通過。Root 與獨立本機 Codex 審查後合併；未安裝 |
| Artifacts Part A | draft #46 `e7eeca8`：既有 backend + exact replica cleanup evidence + shared browser/native attachment UI | focused backend 與真正 HTTP/temp Git/MockBat bytes fixture 通過；peer review 的 malformed role/artifact ID 拒絕修正中，full waiter 已安全取消，修完重排 |
| Delivery Part B | draft #47 `1354397`：data step 3、history adapter、owner lease、composite scopes、canonical UI | focused backend、6 個語系/尺寸 fixture、4 個 refresh race tests 通過；stacked on #46，CI/peer review 中；等 artifacts 修正後重排 full；issue #32 保留追蹤 |
| R04 frontend | 本機 `ef3ada1`：pending/linked controls、history/relations、state axes、穩定分頁、初次讀取失敗恢復 | shared browser/native/real central fixtures 與獨立本機 Codex 審查通過；尚未合併，不宣稱 M1 |
| R01 Part B | 本機 `0690856`：legacy MCP/CLI interrupt 接既有 `session.interrupt` action | no-key 明示、prefix 固定綁定、CLI read-only、lost ACK；56 focused tests 兩版本通過；peer 找到 prefix history 歸屬缺口，修正及回歸中；full 尚未排入 |
| R09 installer | 私有 fleet draft #6 `d33ddbf`：canonical installer | exact pin/digest、generated bundles、principal-only、保留配置；修完整 YAML 提案驗證，14 tests 通過。pin 仍為 draft candidate；不曾 live 安裝。舊 #3 被 #5 supersede 而關閉 |

「本機」commit 不代表 GitHub PR、main 或已部署版本。所有 backend full suites 使用
同一把本機 lock 依序執行，執行中的 source 不修改。未通過的 run 保留失敗證據；
單次 focused 重跑通過不能替代 full 通過。新 desktop 與 backend PR 在各自最新 head
通過 CI/審查後才合併，Windows 打包成功也不替代 Windows 安裝與跨登入驗收。
GitHub Codex review bot 在 #45/Kit #8 後回報額度用盡；這不是乾淨 verdict。
後續獨立本機 Codex 審查要另記 reviewer/head/發現與修正，不冒稱 GitHub 已審。

## 接手基線

| 來源 | 接手時 remote head | 狀態及下一步 |
| --- | --- | --- |
| #35 observation | `1c27371` | CI 綠；worker 修無資料時 relations cursor 驗證，完成後審查與整合；legacy reviewer root/policy 一致性待核對 |
| #36 operations Part A | `d51290b` | CI 綠但不是最新修正；worker 已有 `c9c5a2e` pause/verifier 修正，內部 failover authority 尚在跑 |
| #37 confinement | `d03fc1f` | 衝突、無 CI；worker 修 Python 啟動前依賴完整性與 pre-send rollback；須累加 #36 gate |
| #38 cleanup Part A | `51bb65c` | 衝突、無 CI；worker 已有 `26fecc2`/`cad864f` 容量及移除 host 修正，retirement follow-up 尚在跑 |
| #39 Hub import | `0018b58` | v2 排除，不合併、不作依賴；通用 project/work-item 已在 main |
| Delivery Part B（local） | `b2e2050` | 既有已審成果需在 #35/#36 後整合；data step 3、history adapter、owner lease、固定 UI key 等 pending notes 仍適用 |
| Artifacts Part A（local） | `3c59f4f` | 保留已有成果；在 confinement/cleanup 後整合 exact replica manifest，無 Hub import 依賴 |
| Fleet Kit main | `4ca47d0`（計畫 pin） | #7 已合併；既有 inventory/readiness/ownership 是 R03 基礎，Rust parity 尚未交付 |

四個舊 worker 接手時仍活著；不在它們的 dirty clones 同時編輯。Review 完成的 SHA
才能作整合來源；查 remote head 並以 expected head 合併，避免合入未審的新 push。

## Owners、接口與依賴

| 包 | 整合 owner / 工作線 | 交付與依賴 | 接手狀態 |
| --- | --- | --- | --- |
| R00 | Codex 主協調 | 決策、scope、狀態、中央/native 邊界 | 本分支文件 |
| R01 | Codex 主協調；既有 ops/confinement workers 完成當輪修正 | #36 → #37；legacy operations Part B；shared operation/task gates | 部分分支，未完成整合 |
| R02 | Codex desktop worker | `desktop/**`、共用 UI source、受限 transport、window/tray；依 R00 | 開發中 |
| R03 | Codex 主協調（待 R02 bridge） | Fleet inventory/PS adapter → Rust parity、ownership、bootstrap | 待開工，沿用 Fleet #7 |
| R04 | Codex 主協調；observation worker 完成修正 | #35 read models → 共用 frontend state/history/relations | backend 分支；frontend 尚缺 |
| R05 | Codex 主協調；保留 artifacts 分支 | fixed checkpoint、artifact bytes/manifest、跨 host；依 R01/R02/R08 接口 | checkpoint 已在 main；artifacts local |
| R06 | Codex 主協調 | 既有 project/work_items、completion + R04 詳情；無 importer | 基礎已在 main，桌面整合待做 |
| R07 | Codex 主協調；保留 delivery 分支 | integration、cancel 追蹤、composite scopes、source SHA/recipe、UI；依 R01 | Part A main，Part B local |
| R08 | Codex 主協調；cleanup worker 完成修正 | #38 + R01/R04/R05 引用、task cleanup、recovery | Part A 分支；task-owned 保留 |
| R09 | Codex 主協調 | canonical API/skill + 薄 wrappers、installer/client pins；隨 R01–R08 | 既有兩份 skill；產生/安裝同版待做 |
| R10 | Codex 主協調 + 使用者環境 | 同 SHA app/backend、Windows WebView、BAT、選定測試 repo/environment、多 client | 未實機驗收 |

共用 `operations.py`、`service.py`、`api_v1.py`、`task_daemon.py`、`task_journal.py`
及 contract generator 的整合 owner 是主協調。Desktop worker 擁有 frontend transport/state
抽取與 build；其他功能提出接口需求，避免同時重構核心檔。Registry/flock、start claims
及 cleanup reservation 要跑组合回歸。

## 實際執行順序

1. 記錄 R00，更新 agent 入口，排除 #39。
2. 已在跑的 #36/#35 修正完成 → review → 順序跑 full checks → 合併；R02 可平行。
3. #37 接 #36/#35 並保留兩層 frame gate；再接 #38 observation IDs/flock/claim 衝突。
4. 共用 frontend 接 observation，完成事件 store、pending/linked 刷新與 M1；Fleet
   adapter 遵循唯一 owner，不靠第二個 monitor 補缺口。
5. 整合現有 artifacts/Delivery Part B，補 R01 Part B、R05/R06/R08；R03 Rust parity。
6. R09 版本與安裝一致；R10 用同一候選版本跑 46 項及正式展示，才宣稱 M3/v1 完成。

## 驗收證據與外部依賴

- R00：依 `git`/GitHub heads、handoff、worker logs、actual API registry 查核；無 runtime 變更。
- R02：開發中；尚無 Windows 安裝/WebView/tray、跨登入 session、簽章或 live server 證據。
- Backend：各舊分支的 full suite 結果保留在 handoff/worker 報告；未當作整合結果。
- #37 trusted auditor `check_ssh_alias`/`check_uid`/`bat_account` 與限定 sudoers 需實際
  host 配置。沒有這些證據不得宣稱全域隔離或授予較高受限執行模式。
- 正式部署示範仍需選定測試 repo/environment、使用者 scopes、Windows 與 signing 設定；
  開發授權不代表任意正式部署授權。

## 尚未涵蓋

M1/M2/M3 皆未完成。此表不代表已安裝或 live accepted；之後每輪加入實際 SHA、
user-visible behavior、測試層級及仍缺接口，保留未驗收項目。
