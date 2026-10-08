# Tauri v2 實作狀態

查核日期：2026-10-08。依 [v2 範圍](realignment-v2.md)；歷史交接見
[`2026-10-08-dispatch.md`](../handoff/2026-10-08-dispatch.md)。此表以 source evidence
追蹤，不以測試數或 PR 數代替產品驗收。開工時 main 為 `2568520`（#41 已合併）；
本輪已依序合併 #36（`800f6ec`）、#35（`8e687fb`）、#37（`2ac5715`）及 #38（`8c755a3`）。下面的接手基線保留歷史，
目前進度以「本輪進度」為準。

## 本輪收斂結果（2026-10-08 23:26 UTC）

- 公開 repo 已合併 #35、#36、#37、#38、#42–#51；產品整合 main 為 `6d88f4d0f72c9c5f363962e00c8fdbbaf37082c7`（#51）。
  #39 importer 關閉且保留 branch，沒有合入。Issue #32 的六項 Delivery findings 已隨 #47 合併並關閉。
- 固定候選 `e634c3067e0ba1761336f2bb02360281f9f8e93d` 的 [Python CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510798)：3.10、3.11、3.12、3.13 **各 2264 passed / 33 skipped**，Ruff、generated skills、secret scan 通過。
  [Desktop CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510691)：Windows NSIS、Linux deb、74 shared UI、8 state tests 通過；Rust Windows 19、Linux 20 tests 通過，Windows 包含真正 system PowerShell 子程序 fixture。
- 產品整合 commit `6d88f4d` 的 Git tree 與已測候選完全相同：`c89ee4c6b09b74d08f71459c405c96c2e76f2064`。
  本次收斂文件是後續 docs-only 更新，未更動該 runtime/build/skill source，沒有另宣稱文件 head 跑過一次 full suite。
- Fleet Kit #8 已合併 `d3697dc`；私有 installer #6 已合併 `2026750`，reviewed head `60ff6bd`。
  Installer pin 是上述完整 candidate、workflow `2026-10-08.4`、canonical digest `5f7e04d84dd9b207ee553e3308e988a07d890ba219ceebb9b26fc09a21c1b723`。
  17 temporary/mock tests 在 default Python 與 3.10 通過；真 source verify-only 通過。保留 `draft_candidate`，並非正式 v1 release。
- 獨立審查修正了 artifact scalar admission、deployment cursor bounds、interrupt history prefix binding、capture replay/control credential binding、installer YAML 與 concurrent config preservation。
  先前 full/CI failures 均保留；#48/#49/#50 的舊 fixture failures 已由 #51 的 canonical-source/data-step 修正及整組 CI 覆蓋，未把舊紅燈改稱綠燈。
- #38 早期本機 3.10 full 曾為 1834 passed/33 skipped/1 個 60 秒 settlement timeout；journal 顯示持續進展，原碼單測 2.52 秒重跑通過。後續 exact-head 四版 CI 各 1835/33 通過；不把單測 retry 當 full。
- 合併後新增 [Linux GLib release gate #53](https://github.com/teddashh/bat-agent-connector/issues/53)：鎖定的 `glib 0.18.5` 受 [RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html) 影響，目前 GTK/WebKit 0.18 相依沒有可直接更新的已發布修正版。Windows locked graph 不含該依賴；Linux production distribution 仍須已審修正。CI 綠燈不消除此 advisory，Dependabot 保持開啟。
- GitHub Codex bot 後期額度用盡，後續使用獨立本機 Codex peer review，沒有冒稱新 bot verdict。
  **沒有 live host/provider writes、主機安裝或 Windows installed acceptance；M1/M2/M3 與正式 v1 尚未完成。**

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
| R01 | Codex 主協調；既有 ops/confinement workers 完成當輪修正 | #36 → #37；legacy operations Part B；shared operation/task gates | #36/#37 main；#49 第一片已合併 |
| R02 | Codex desktop worker | `desktop/**`、共用 UI source、受限 transport、window/tray；依 R00 | #44 已合併；installed 驗收待做 |
| R03 | Codex 主協調（待 R02 bridge） | Fleet inventory/PS adapter → Rust parity、ownership、bootstrap | #45 PS adapter 已合併；Rust parity 尚缺 |
| R04 | Codex 主協調；observation worker 完成修正 | #35 read models → 共用 frontend state/history/relations | #35 main；#48 frontend 已合併 |
| R05 | Codex 主協調；保留 artifacts 分支 | fixed checkpoint、artifact bytes/manifest、跨 host；依 R01/R02/R08 接口 | checkpoint main；#46/#50 已合併，B2/C 尚缺 |
| R06 | Codex 主協調 | 既有 project/work_items、completion + R04 詳情；無 importer | 基礎 main；桌面 history/details 已合併，剩餘能力待驗收 |
| R07 | Codex 主協調；保留 delivery 分支 | integration、cancel 追蹤、composite scopes、source SHA/recipe、UI；依 R01 | Part A main；#47 Part B 已合併 |
| R08 | Codex 主協調；cleanup worker 完成修正 | #38 + R01/R04/R05 引用、task cleanup、recovery | #38 main；task-owned cleanup 仍保留 |
| R09 | Codex 主協調 | canonical API/skill + 薄 wrappers、installer/client pins；隨 R01–R08 | #43 canonical/generated 已合併；final candidate pin 已固定；實際安裝待做 |
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
- R02：已合併 source 有 build/fixture/native 子集證據；尚無 Windows installed/tray/跨登入、簽章或 live 組合證據。
- Backend：各舊分支的 full suite 結果保留在 handoff/worker 報告；未當作整合結果。
- #37 trusted auditor `check_ssh_alias`/`check_uid`/`bat_account` 與限定 sudoers 需實際
  host 配置。沒有這些證據不得宣稱全域隔離或授予較高受限執行模式。
- 正式部署示範仍需選定測試 repo/environment、使用者 scopes、Windows 與 signing 設定；
  開發授權不代表任意正式部署授權。

## 尚未涵蓋

M1/M2/M3 皆未完成。此表不代表已安裝或 live accepted；之後每輪加入實際 SHA、
user-visible behavior、測試層級及仍缺接口，保留未驗收項目。
