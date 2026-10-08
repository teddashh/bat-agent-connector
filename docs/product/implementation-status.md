# Tauri v2 實作狀態

查核日期：2026-10-08。依 [v2 範圍](realignment-v2.md)；歷史交接見
[`2026-10-08-dispatch.md`](../handoff/2026-10-08-dispatch.md)。此表以 source evidence
追蹤，不以測試數或 PR 數代替產品驗收。開工時 main 為 `2568520`（#41 已合併）；
本輪已依序合併 #36（`800f6ec`）、#35（`8e687fb`）、#37（`2ac5715`）及 #38（`8c755a3`）。下面的接手基線保留歷史，
目前進度以「本輪進度」為準。

## 本輪進度

以下為 2026-10-08 23:03 UTC 查核點；PR heads 與 CI 請再即時核對。

| 工作 | 現在的成果 | 驗證與下一步 |
| --- | --- | --- |
| #36 Operations Part A | 已合併 `800f6ec`：pause/verifier 取消、failover authority、最終 frame gate | 合併 head `3ccbe92` 的 CI 與 Codex 審查通過 |
| #35 Observation Part A | 已合併 `8e687fb`：history/relations、cursor、durable operation actor | 合併 head `feed51b` 的 CI 與 Codex 審查通過；frontend 另列 #48 |
| #37 Confinement | 已合併 `2ac5715`，head `09faafd`：pre-Python closure proof、移除讀回與同 ID retry、實際 start gate | 四個 Python CI jobs 綠；本機 3.13/3.10 各 1619 passed/33 skipped。獨立 peer 審查；bot quota 不算 verdict；W12 未驗收 |
| #38 Cleanup Part A | 已合併 `8c755a3`，head `edf5683`：shared IDs/flock/claims、removed host、retirement | 四個 Python CI jobs 各 1835 passed/33 skipped。保留較早本機 3.10 的 1834 passed/33 skipped/1 個 settlement deadline failure；原碼 exact retry 通過不取代 full 結果 |
| #39 Hub import | 已關閉、不合併；保留 branch | 不是新功能依賴 |
| #43 Canonical skills | draft `f43f3c2`：canonical/generated wrappers、principal-only MCP | 此 head 四個 Python CI jobs 各 1851 passed/33 skipped；installer 尚未安裝最後組合 |
| #44 Tauri foundation | draft `5bccb63`：shared frontend、restricted bridge、tray/instance、signed event checkpoint | 已整合 confinement/cleanup；既有 packaging/native fixture 證據保留，最新 head CI 另查；非 Windows installed/live 驗收 |
| #45 Fleet desktop | draft `69f94d2`：固定 PS facade、受限 IPC、configuration/revision/epoch binding | 既有 Windows subprocess/NSIS、Linux deb 證據；最新整合 head CI 另查。Rust supervisor parity、實機安裝未完成 |
| Fleet Kit #8 | 已合併 `d3697dc`，head `2ec4b11`：唯一 monitor owner、CAS preferences、applied binding | Windows PS 5.1/7 各 219 passed/1 skipped；Linux 213 passed/7 skipped，24 scripts 檢查通過。未安裝 |
| #46 Artifacts Part A | draft `560870b`：store/materialization、exact replica proof、shared attachment UI | malformed scalar admission 與 fixture context 已修；focused/peer 證據，最新 CI 另查 |
| #47 Delivery Part B | draft `9874eae`：history step 3、owner lease、composite scopes、canonical UI | `831d670` CI 的兩個舊測試假設（generated UI source、schema==2）已修；14 個受影響案例兩版本通過。是測試修正，不是已證實產品 regression；新 CI 待確認 |
| #48 R04 frontend | draft `90e2392`：pending/linked、state axes、history/relations、穩定分頁/恢復 | browser/native-IPC/真中央 fixture 與 peer 證據；未宣稱 M1 |
| #49 R01 Part B | draft `3877da5`：legacy interrupt 接同一 durable action，原 actor/key/完整 prefix 綁定 | no-key、CLI read-only、final frame/lost ACK 回歸與 peer 審查；只完成第一片，其餘 legacy mutations 尚缺 |
| #50 R05 B1 capture | draft `c3b4abd`，stacked on #49：人工固定單檔 preview/capture | replay/resume/cancel 維持原 credential + manage/observe；139 focused tests 各 Python 版本、38 integration seam tests 通過。UI/native preview allowlist、B2/C 未做 |
| R09 installer | 私有 draft #6 `d33ddbf`：canonical pin/digest、principal-only、保留配置 | 14 temporary/mock tests 通過；final candidate pin/實際安裝待定 |

單一整合候選為 `1cffa7107232cb6dde35f634b998a62f3333174f`：由 `1498a6f` 加上
#38 main merge（無 source diff）及 Delivery `9874eae` 的測試修正組成。包含 #43 `f43f3c2`、
#44 `5bccb63`、#45 `69f94d2`、#46 `560870b`、#47 `9874eae`、#48 `90e2392`、
#49 `3877da5`、#50 `c3b4abd`。`1498a6f` 的 production source 與此候選相同：439 backend
focused、74 UI、8 state、20 Rust、5 個真中央 fixtures，加上 build/Clippy/release check 通過；
新增 Delivery 測試修正的 14 cases 兩版本通過。**最終候選 exact-head full CI 尚待執行／確認，
不能宣稱完整 Python matrix 已通過，也不能把各分支 CI 當成組合驗收。**
子 PR #48/#49/#50 仍可能顯示繼承的舊 Delivery fixture failures；上述候選已含兩項修正，
不為改 CI 顯示而改寫已審 PR heads。

所有本機 backend full suites 使用同一把 lock 依序執行；source 執行中不改。失敗與重跑理由
保留，focused retry 不取代 full。GitHub Codex bot 額度用盡不代表乾淨 verdict；獨立本機
peer review 另記 head/發現/修正。Windows 打包成功不替代實際安裝、跨登入及 live 驗收。

46 項的 source／fixture／native／installed／live 證據與缺口見 [R10 驗收矩陣](acceptance-v2.md)。

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

## Owners、接口與依賴（目前分工）

| 包 | 整合 owner / 工作線 | 交付與依賴 | 現況 |
| --- | --- | --- | --- |
| R00 | Codex 主協調 | 決策、scope、狀態、中央/native 邊界 | 本分支文件 |
| R01 | Codex 主協調；既有 ops/confinement workers 完成當輪修正 | #36 → #37；legacy operations Part B；shared operation/task gates | #36/#37 main；#49 第一片已進候選 |
| R02 | Codex desktop worker | `desktop/**`、共用 UI source、受限 transport、window/tray；依 R00 | #44 已進候選；installed 驗收待做 |
| R03 | Codex 主協調（待 R02 bridge） | Fleet inventory/PS adapter → Rust parity、ownership、bootstrap | #45 PS adapter 已進候選；Rust parity 尚缺 |
| R04 | Codex 主協調；observation worker 完成修正 | #35 read models → 共用 frontend state/history/relations | #35 main；#48 frontend 已進候選 |
| R05 | Codex 主協調；保留 artifacts 分支 | fixed checkpoint、artifact bytes/manifest、跨 host；依 R01/R02/R08 接口 | checkpoint main；#46/#50 已進候選，B2/C 尚缺 |
| R06 | Codex 主協調 | 既有 project/work_items、completion + R04 詳情；無 importer | 基礎 main；桌面 history/details 在候選，剩餘能力待驗收 |
| R07 | Codex 主協調；保留 delivery 分支 | integration、cancel 追蹤、composite scopes、source SHA/recipe、UI；依 R01 | Part A main；#47 Part B 在候選 |
| R08 | Codex 主協調；cleanup worker 完成修正 | #38 + R01/R04/R05 引用、task cleanup、recovery | #38 main；task-owned cleanup 仍保留 |
| R09 | Codex 主協調 | canonical API/skill + 薄 wrappers、installer/client pins；隨 R01–R08 | #43 canonical/generated 在候選；final pin/安裝待做 |
| R10 | Codex 主協調 + 使用者環境 | 同 SHA app/backend、Windows WebView、BAT、選定測試 repo/environment、多 client | 未實機驗收 |

共用 `operations.py`、`service.py`、`api_v1.py`、`task_daemon.py`、`task_journal.py`
及 contract generator 的整合 owner 是主協調。Desktop worker 擁有 frontend transport/state
抽取與 build；其他功能提出接口需求，避免同時重構核心檔。Registry/flock、start claims
及 cleanup reservation 要跑组合回歸。

## 原定執行順序（完成狀態以上方快照為準）

1. 記錄 R00，更新 agent 入口，排除 #39。
2. 已在跑的 #36/#35 修正完成 → review → 順序跑 full checks → 合併；R02 可平行。
3. #37 接 #36/#35 並保留兩層 frame gate；再接 #38 observation IDs/flock/claim 衝突。
4. 共用 frontend 接 observation，完成事件 store、pending/linked 刷新與 M1；Fleet
   adapter 遵循唯一 owner，不靠第二個 monitor 補缺口。
5. 整合現有 artifacts/Delivery Part B，補 R01 Part B、R05/R06/R08；R03 Rust parity。
6. R09 版本與安裝一致；R10 用同一候選版本跑 46 項及正式展示，才宣稱 M3/v1 完成。

## 驗收證據與外部依賴

- R00：依 `git`/GitHub heads、handoff、worker logs、actual API registry 查核；無 runtime 變更。
- R02：候選有 build/fixture/native 子集證據；尚無 Windows installed/tray/跨登入、簽章或 live 組合證據。
- Backend：各舊分支的 full suite 結果保留在 handoff/worker 報告；未當作整合結果。
- #37 trusted auditor `check_ssh_alias`/`check_uid`/`bat_account` 與限定 sudoers 需實際
  host 配置。沒有這些證據不得宣稱全域隔離或授予較高受限執行模式。
- 正式部署示範仍需選定測試 repo/environment、使用者 scopes、Windows 與 signing 設定；
  開發授權不代表任意正式部署授權。

## 尚未涵蓋

M1/M2/M3 皆未完成。此表不代表已安裝或 live accepted；之後每輪加入實際 SHA、
user-visible behavior、測試層級及仍缺接口，保留未驗收項目。
