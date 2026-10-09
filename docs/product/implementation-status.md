# Better Agent Dashboard／Connector 實作狀態

查核日期：2026-10-09。依 [共用產品與 Tauri 方向](realignment-v2.md)；兩份計畫是同一產品的 UI 修訂，共用一份功能 backlog。歷史交接見
[`2026-10-08-dispatch.md`](../handoff/2026-10-08-dispatch.md)。此表以 source evidence
追蹤，不以測試數或 PR 數代替產品驗收。開工時 main 為 `2568520`（#41 已合併）；
本輪已依序合併 #36（`800f6ec`）、#35（`8e687fb`）、#37（`2ac5715`）及 #38（`8c755a3`）。下面的接手基線保留歷史，
已合併證據以「本輪收斂結果」為準，續作以「目前續作」為準。

## 目前續作

### 2026-10-09 macOS 交付續作

使用者新增 Mac 版本要求。從已合併 #68（`2d2570b`）開工，新增 Apple Silicon／Intel
DMG、ICNS、Dock Reopen／正常 Quit 與兩種架構的 disposable native install fixture。
Mac 候選須以自己的完整 head CI、DMG digest、WKWebView screenshots 和清理 receipts 驗證，
不能沿用 Windows/Linux 的結果。新增 Mac 原生 secure-field／Keychain adapter 與隔離 Keychain fixtures，並備妥正式
Developer ID／公證 candidate workflow；待各自 exact-head 結果。正式簽署執行、Mac updater 及 I／L
仍分開追蹤；Windows Fleet supervisor 不因 Mac 可啟動就宣稱跨平台支援。

#68 的固定候選 `771d0099a9cae74e3446f3121a2747439583b136` 已通過
[Python 四版各 3187／33](https://github.com/teddashh/bat-agent-connector/actions/runs/37949144734)
及 [Windows 真 NSIS 安裝／Linux 實際 deb WebView](https://github.com/teddashh/bat-agent-connector/actions/runs/37949144823)，
merge tree 與候選同為 `992aa5b356d6ee9cab04bd126f0ae54f0045ef5c`。
私有 installer #13 已合併，pin 該 source；Python 3.10／3.13 各 17 regressions 與真正隔離
Connector／Hermes installs 通過並清理。這些均不代表使用者主機或 live 服務已安裝。

### 2026-10-09 發行門檻收斂

#64／#65／#66 已合併；以下各段保留當時候選的歷史證據。
[#67](https://github.com/teddashh/bat-agent-connector/pull/67) 再合併為
`68106542e1b120de8457f4e64a134c2c76e5481e`，與已測候選
`be9804039dd526ec105bb466a0f9f72bf47902e0` 的 tree 同為
`384bf572df18f65970c4fac2639ef4c9e2c003c5`。Canonical workflow 保持 `2026-10-08.14`。
GLib 保留 0.18.5 原版本並 backport upstream 的兩行指標修正，來源完整性／真正 dependency graph
與 optimized iterator regression 成為 gates；未忽略 advisory。
[#53](https://github.com/teddashh/bat-agent-connector/issues/53) 已關閉，Dependabot alert #1 為 fixed，未 dismissed。

固定候選 [Python CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37934974542)
3.10–3.13 各 **3187 passed／33 skipped**；
[desktop CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37934974673)
Windows NSIS／Linux deb、585 shared UI、12 state、每平台 81 app Rust、release verifier、GLib release
regression 及 Linux 真 packaged WebView／關窗隱藏／single-instance 通過。Windows metadata locale
failure 已修正並由最終 Windows job 通過，舊失敗保留。這些仍是 unsigned／F／N 證據。
私有 installer #12 已合併，pin 同一候選與 `.14`；17 temporary tests 在 Python 3.10／3.13 通過，
source verify-only 通過。未執行 live 安裝。正式簽章、實機／live 驗收及 release feed 發布仍未完成。

新增 Windows installed fixture 只允許 GitHub-hosted disposable runner：驗證 NSIS 真安裝、
binary digest／PE 與 registry version、license resources、真 WebView loopback polling、WM_CLOSE、
single-instance、process restart 與 uninstall，保存 screenshots／JSON。這是 N 層安裝 fixture，
不能替代真人 Credential Manager／跨登入、實體 tray 操作、signed update 或真中央／BAT 的 I／L 驗收。
其執行結果以包含此 fixture 的候選 CI 為準，不沿用 #67 的綠燈。

### 先前整合證據

最新追蹤 [#59](https://github.com/teddashh/bat-agent-connector/issues/59)。[#61](https://github.com/teddashh/bat-agent-connector/pull/61)
已合併為 `1a8984cac57146c3bd8b842b94b32a30c5525c15`；固定候選 `07bc762089e00e00bcf6e06d93051427a8ad6f84`
與 merge 的 tree 同為 `8ca0a54b46facd3a2e5e209f5491ca088b8cc609`。Managed start、task reviewed／automatic cleanup、
native 選檔／上傳／Save As、成果擷取／獨立審核及 canonical `.8` 已在 main。Project Hub 的 session 整理方向保留：
依實際 host／workspace 分組，不從名稱猜測專案歸屬。GUI／CLI／MCP 都在指定 BAT host／workspace 工作；
跨主機只接續明確 repository 的已發布 commit，未發布 Git-pack transport 不在交付條件。

Exact-head CI：Python 3.10–3.13 各 **2680 passed／33 skipped**；333 UI、12 state、每平台 53 app Rust，
Fleet core Windows 63／Linux 58 通過。Windows NSIS／Linux deb unsigned packages、Ruff、generator、Clippy、
generated browser drift 與 secrets scan 通過。Actual-central fixtures 用 temporary Git／MockBat 驗證 start、bulk、
cleanup、native files 及獨立 reviewer 的固定 bytes/revision。Local full Python 3.10、3.13 各 2680／33；先前磁碟
壅塞的 3.13 run 有未釐清 failures 且中止，沒有計為通過，後續 isolated fixtures 與 exact-head CI 完整通過。
私有 installer #10 已合併 `67be22ea748c49e055a58e9fb72ef0c91d8b2161`，pin 此候選／`.8`；17 temporary tests
在 3.13／3.10 通過，真 source verify-only 通過，沒有修改 live 安裝。當時 Linux GLib release gate #53 尚開啟；現況見上方收斂紀錄。

後續主線與候選分開追蹤，不計為 installed 完成：

- [#62](https://github.com/teddashh/bat-agent-connector/pull/62) 已合併為 `c9ed361067e84f092ddabe2a3c057e4e1db688b5`。
  候選 `927053dd6e6e87185f013c4bfd7834054de179ba` 與 merge 的 tree 同為 `e4a8e281015c2b376623ce91911feb9fab7e9743`。
  明確 repository binding、GitHub numeric ID、固定 ref/head 與 fresh managed carrier、published-start UI 及 `.9` 已在 main。
  Exact CI Python 3.10–3.13 各 **2725 passed／33 skipped**，兩平台 desktop／unsigned packaging 通過。
  Local 3.13 full 先有 operation settlement timeout，重跑另有兩項 subprocess deadline failure；沒有宣稱 local full 綠燈。
  原碼 targeted integration 1、subprocess 3 通過；本機高負載下停止重複全套，以四版 exact-head CI 作完整驗證。
- [#63](https://github.com/teddashh/bat-agent-connector/pull/63) 已合併為 `a14a9ddb36f203ad4116252457f5fd2c0f90825f`。
  候選 `3835b14dbaf2a5241461c5db2f780f0b56407114` 與 merge tree 同為 `192fd59c88cde19b54668c21add3d397453e6e55`。
  Central relay、fanout planner／fixed-plan dispatch、standalone Claude→Codex failover、omitted-key task controls 與 `.11`
  已在 main。Exact CI Python 3.10–3.13 各 **2888 passed／33 skipped**，Windows／Linux desktop packaging 通過。
  Focused 490 在 3.13／3.10 通過；舊 principal fixture 斷言已修。兩次主動中止的 local full 不計通過，第二次是在 CI 四版通過後停止重複驗證。
- [#64](https://github.com/teddashh/bat-agent-connector/pull/64) 整合 native Fleet／bootstrap／signed update；來源候選 `d6b23ae8d2d043ce9127452aaf212da2a8e229bd`。
  真 Windows fixture 先暴露空閒 endpoint 在 100 ms 尚未回 refusal，修為 bounded 3 s refusal＋bind proof。
  接著修正 ownership 掃描與 selection 的短路徑差異、WScript Startup 短路徑辨識，以及並行 discovery fixtures 的時間戳撞名。
  完整 Windows Fleet core gate 已通過，包含真 WScript synthetic links；22 discovery、42 ownership/configuration regressions 與獨立 review 通過。
  另一次 app fixture 在原 10 s PowerShell contract budget 逾時，後續不同條件的 probes 通過不當作原測試通過；失敗及原碼查核／重跑證據保留於 PR。
  原 combined evidence：416 UI、12 state、218 Linux core、78 app Rust／1 fixture-only ignored、release verifier example 1；bootstrap 44 在兩版 Python 通過。
- [#65](https://github.com/teddashh/bat-agent-connector/pull/65) 整合四個 orchestration 表單、task pause/resume、操作分頁、明確 BAT profile 入口、principal transcript/wait、A03 labels 及中央 verification testimony。
  候選 `460c792de40f35d84155219b06bc3f3948b92ee5` 保留原 actor/key/request 與 receipts。Labels 只改中央 metadata，含人工／unknown／retained 與版本 CAS；verification 是外部證詞，不能授予 trusted task verification。
  Observation 86、labels／verification／principal／lifecycle／canonical 152 在兩版 Python 通過；3 trusted verifier、91 affected UI、actual-central labels／task／orchestration fixtures 通過。
  Full CI 在 `921caf7` 發現 3 個 API remount 重複註冊 failures 與 1 個舊 MCP 工具清單斷言；`f6603a4` 修正後，101 related regressions 在 3.13／3.10 通過並經獨立 review。
  本機 orchestration fixture 曾在一般暫存磁碟遇到 5 s UI deadline，原碼在 `/dev/shm` 通過；沒有放寬 deadline 或計為 local full 通過。
- [#66](https://github.com/teddashh/bat-agent-connector/pull/66) 是同一產品的最後整合工作線，累加 Tailscale recovery、中央 `worktree.merge` 與 canonical `.14`。
  Tailscale 使用固定 Windows vendor paths、bounded sanitized status、原 request receipt、Launcher／Quit／update fences；返回畫面只查狀態，不自動登入或修改網路。
  Source `5598b46` 已獨立 review；9 durable core＋1 synthetic process、3 Linux Tauri IPC、29 final UI、12 state 通過。Windows MSVC isolated compile 是分層證據，實際 Windows matrix 另留 CI。
  Merge 固定來源／目的 Git identity 與全部 consumers，保留雙 carrier reservation、各 effect 的 ACK、未知結果與原 key。支援明確 idle／unloaded／headless／retired managed consumers，拒絕 task-owned／manual／unknown／未決 writer。
  先以設定的 verifier SSH 讀 effective Git config，拒絕 diff/filter programs、ambient overlays、submodules、incomplete status，再讀 BAT worktree status；SSH mapping 必須由 operator 綁到同一 BAT Git account/configuration context，不能當作獨立環境 attestation。
  Merge source `9366396` 的 140 merge/client cases 在 3.13、254 related cases 在 3.10 通過；先前 shared layers 705／707 通過。獨立 review 的 Git diff-program finding 已修正，原始失敗／修正 evidence 保留。
  Root integration 的共用 UI **585**、state **12** 全通過；merge／verification／client／MCP／canonical／cleanup／SSE／labels 共 **282** 在 Python 3.13／3.10 均通過。
  固定候選的完整 Python／Windows／Linux、late recovery corrections 與 installer SHA/digest，以此 PR 最後記錄為準。

本節是送審來源與分層 evidence 快照；PR 的完整 SHA、checks、merge commit 與 tree 比對記錄才是合併判準。
不以先前 head 綠燈、較小 focused suite 或不同來源的 installer pin 當最終 release candidate 證據。

以上沒有正式簽章身分、release feed 發布、Windows installed 或 live host/provider writes 的完成宣稱。
本機 fixtures 不代替 PID／account／Startup／原生視窗及完整產品展示。GitHub Codex review quota 用盡，
本輪採具體 source／repro 的獨立本機 peer review，不宣稱 bot approval。

本輪來源與審查（以下保留合併前各層證據）：

- Native credentials `67223d0`：Windows 原生憑證對話框／Credential Manager、固定 endpoint／actor／
  contract 及中央身分驗證、可恢復連線。獨立審查找到 native bootstrap 404 誤入 legacy namespace，
  及手動連線時 Disable Disconnect；`8aff900` 修正，51 focused UI cases 通過。原 head 的 156 UI、
  32 Linux Rust、8 state 與 Windows 模組 typecheck 是分層 fixture 證據；完整 Windows build 交 CI，
  沒有原生對話框／Credential Manager 實機驗收。
- Managed artifacts `9de3572`：獨立 preview、中央 accepted execution／command lineage、固定 bytes／HEAD，
  `artifact.capture.managed` 與精確 revision 的 `artifact.accept`。獨立審查無 findings；整合 B1／B2
  119 cases 通過。原工作線的 Python 3.13 B1 instrumentation stub 曾漏 optional keyword，僅修 fixture
  signature 後通過；未抹去先前失敗。不標記工作完成或交付，UI 仍需接入。
- Bulk approval `afa9161`：明確選定 preview、原 answer／permissions children、逐項 partial receipts、
  送出前重新核對 prompt／owner／取消狀態。獨立審查無 production findings；同一 focused regression set
  Python 3.13／3.10 各 753 passed。`7732a1a` 依 child deadline 限制 parent polling，71 focused
  cases 在兩版本均通過，明確取消／恢復仍立即喚醒。原內部 deferred raise 保持停用；公開入口缺 preview 時拒絕。
- B2／bulk／canonical `.7` 的整合 123 cases 通過；API/MCP/RPC unions 與 generated skills 經獨立審查。
  本機後端驗證使用獨立 `/dev/shm` Git／bytes／SQLite fixtures 避開磁碟排程壅塞，並非斷電持久性證明。
  最後候選仍須完整 checks、exact-head CI、Windows packaging；installer 尚未 pin 本輪候選。
- Session 整理 `c6c148a`：依記錄中的 host／workspace 分組、已載入範圍搜尋與筆數、compact rows，
  詳情保留完整 ID／狀態證據，長名稱不溢出。獨立畫面／source review 修正 runtime fields stale
  仍顯示目前 streaming 的誤判。175 shared UI 在最後文字與展開細節調整前通過；最終 34 focused UI、
  12 state、真中央 MockBat observation fixture、desktop／browser builds 與 generated drift 通過。
  Root 已檢視 en／zh-TW 的桌面、平板、手機及極長名稱截圖；整組候選 UI 與 backend full 正在驗證。

以下保留 #57 的權限工作紀錄：

追蹤 [#57](https://github.com/teddashh/bat-agent-connector/issues/57)，基底 main `565a7d5`（#56）。
R01 `session.permissions` 接中央 authority，Claude／Codex 每個 setting 保存 intent／receipt，
保留 task incarnation／control version、confinement 與 host policy；sent error／lost ACK 不以相符
metadata 當成功證據。共用 UI 只對 positively managed 且 action／write scope 支援的 session 顯示控制，
保存要求的 mode、key／operation，未知結果不自動換 key。Claude streaming 不排 deferred；歷史 flag
與 legacy bulk-raise apply 停用，preview 保留。完整合約見 [session permissions](../design/session-permissions.md)。
Canonical workflow 為 `2026-10-08.6`；最新候選 SHA、exact-head CI、peer review、merge 與 installer pin
證據以 #57 關聯 PR 為準，不把功能清單當作 installed/live 驗收；
[本輪交接](../handoff/2026-10-08-permissions.md) 保留實作與失敗修正脈絡。

## 上一輪續作（#56 已合併）

候選 `867864b75cf2cf1898ce5b5ddedcdd6308003b76` 已合併為 `565a7d57074f6628b5ef9cecec6cc9eb5b56c1e6`，
tree 完全相同。Python 3.10–3.13 各 **2370 passed／33 skipped**；101 UI、8 state、20 Windows／21 Linux Rust、
六組 actual-central fixtures 與 Windows／Linux unsigned packages 通過。Installer #7 已合併並 pin 此候選與
workflow `.5`；17 mock tests 兩 Python 版本及 real-source verify-only 通過，沒有真安裝。
收斂證據見 [#55](https://github.com/teddashh/bat-agent-connector/issues/55#issuecomment-6072185401)。

追蹤 [#55](https://github.com/teddashh/bat-agent-connector/issues/55)，基底 main `0c7c8fb`。
以下三個提交已整合到同一候選工作線；最新整組 CI、合併與 installer pin 證據見該 issue 關聯 PR。

| 包 | 提交與行為 | 這次 fixture／review 證據 |
| --- | --- | --- |
| R01 | `c7525c3` + `57de020`：legacy send／continue／answer 共用 durable operations；原 caller、完整 session/prompt、message ID、queue、dont_ask_again、完整 receipt 與 no-key 語意保留 | 94 個新案例含真 HTTP/MCP/CLI、lost ACK／restart、task final-frame、無 token／owner 拒絕。3.13 focused 曾 590 pass／1 個既有 verifier 5 秒進入等待 timeout；未改原碼的 12-case family 重跑通過，不當作 full 綠燈。3.10 同組 591 通過；peer 發現 receipt 漏 status reason，57de020 修補後 controls/interrupt 154 個案例兩 Python 版本均通過。 |
| R05 B1 UI | `a866510`：共用 browser／Tauri remote-file preview/capture；明示 host、完整 manual session ID 與相對路徑；保存原 intent/key 並明確加入附件草稿 | 101 UI（含 27 新 capture）、8 state、21 Linux Rust、fmt/Clippy/release check、真中央 temporary-source fixture；bytes/index/refs 不變、零 BAT writes。獨立 exact-head review 無 findings。 |
| Legacy removal | `2fc8fd8`：人工／task policy 後停用 unsafe `worktree_remove`，回 `LEGACY_WORKTREE_REMOVE_DISABLED`；改用既有 reviewed cleanup | 基底 active-successor regression 重現；所有 override 零 rehydrate/remove；canonical cleanup shared consumer 拒絕與 eligible removal 仍測到。Focused 3.13 112 通過；新增 apply 斷言原預期錯誤，改為既有 PREVIEW_BLOCKED 拒絕後兩 Python 版本 exact case 通過。 |

UI 曾有 100 pass／1 timeout：不支援 capture 的 session 過早建立隱藏 summary；修為 positively manual 且 capability 支援才掛載，最後整組 101 通過。
兩個既有 MCP fixtures 已改用 caller token 並只提供一種 pending prompt，保留原 task command assertions，另驗 operation actor/binding。
Canonical workflow 更新為 `2026-10-08.5`，Hermes／Grokbot 從同一 source 產生；installer 仍須 pin 已審完整候選，不能只比 package version。
Desktop CI 現在也跑六組 actual-central fixtures，保存合成 UI 證據；完整交付仍依 46 項矩陣，沒有 Windows installed/live 宣稱。
該輪留下的 R01 permissions 合約由上方 #57 接續；bulk approval、starts／orchestration 仍有獨立契約，詳見 [mutation 盤點](../design/legacy-mutation-audit.md)。

## 本輪收斂結果（2026-10-08 23:26 UTC）

- 公開 repo 已合併 #35、#36、#37、#38、#42–#51；產品整合 main 為 `6d88f4d0f72c9c5f363962e00c8fdbbaf37082c7`（#51）。
  #39 importer 關閉且保留 branch，沒有合入。Issue #32 的六項 Delivery findings 已隨 #47 合併並關閉。
- 固定候選 `e634c3067e0ba1761336f2bb02360281f9f8e93d` 的 [Python CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510798)：3.10、3.11、3.12、3.13 **各 2264 passed / 33 skipped**，Ruff、generated skills、secret scan 通過。
  [Desktop CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510691)：Windows NSIS、Linux deb、74 shared UI、8 state tests 通過；Rust Windows 19、Linux 20 tests 通過，Windows 包含真正 system PowerShell 子程序 fixture。
- 產品整合 commit `6d88f4d` 的 Git tree 與已測候選完全相同：`c89ee4c6b09b74d08f71459c405c96c2e76f2064`。
  本次收斂文件是後續 docs-only 更新，未更動該 runtime/build/skill source，沒有另宣稱文件 head 跑過一次 full suite。
- Fleet Kit #8 已合併 `d3697dc`；私有 installer #6 已合併 `2026750`，reviewed head `60ff6bd`。
  Installer pin 是上述完整 candidate、workflow `2026-10-08.4`、canonical digest `5f7e04d84dd9b207ee553e3308e988a07d890ba219ceebb9b26fc09a21c1b723`。
  17 temporary/mock tests 在 default Python 與 3.10 通過；真 source verify-only 通過。保留 `draft_candidate`，並非完整產品發行。
- 獨立審查修正了 artifact scalar admission、deployment cursor bounds、interrupt history prefix binding、capture replay/control credential binding、installer YAML 與 concurrent config preservation。
  先前 full/CI failures 均保留；#48/#49/#50 的舊 fixture failures 已由 #51 的 canonical-source/data-step 修正及整組 CI 覆蓋，未把舊紅燈改稱綠燈。
- #38 早期本機 3.10 full 曾為 1834 passed/33 skipped/1 個 60 秒 settlement timeout；journal 顯示持續進展，原碼單測 2.52 秒重跑通過。後續 exact-head 四版 CI 各 1835/33 通過；不把單測 retry 當 full。
- 當時新增 [Linux GLib release gate #53](https://github.com/teddashh/bat-agent-connector/issues/53)：registry `glib 0.18.5` 受 [RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html) 影響。後續 #67 已 backport upstream 修正並驗證來源／optimized regression，#53 關閉、Dependabot fixed；見上方固定候選證據。
- GitHub Codex bot 後期額度用盡，後續使用獨立本機 Codex peer review，沒有冒稱新 bot verdict。
  **沒有 live host/provider writes、主機安裝或 Windows installed acceptance；M1/M2/M3 與完整產品交付尚未完成。**

## 接手基線

| 來源 | 接手時 remote head | 狀態及下一步 |
| --- | --- | --- |
| #35 observation | `1c27371` | CI 綠；worker 修無資料時 relations cursor 驗證，完成後審查與整合；legacy reviewer root/policy 一致性待核對 |
| #36 operations Part A | `d51290b` | CI 綠但不是最新修正；worker 已有 `c9c5a2e` pause/verifier 修正，內部 failover authority 尚在跑 |
| #37 confinement | `d03fc1f` | 衝突、無 CI；worker 修 Python 啟動前依賴完整性與 pre-send rollback；須累加 #36 gate |
| #38 cleanup Part A | `51bb65c` | 衝突、無 CI；worker 已有 `26fecc2`/`cad864f` 容量及移除 host 修正，retirement follow-up 尚在跑 |
| #39 Hub import | `0018b58` | 明確排除，不合併、不作依賴；通用 project/work-item 已在 main |
| Delivery Part B（local） | `b2e2050` | 既有已審成果需在 #35/#36 後整合；data step 3、history adapter、owner lease、固定 UI key 等 pending notes 仍適用 |
| Artifacts Part A（local） | `3c59f4f` | 保留已有成果；在 confinement/cleanup 後整合 exact replica manifest，無 Hub import 依賴 |
| Fleet Kit main | `4ca47d0`（計畫 pin） | #7 已合併；既有 inventory/readiness/ownership 是 R03 基礎，Rust parity 尚未交付 |

四個舊 worker 接手時仍活著；不在它們的 dirty clones 同時編輯。Review 完成的 SHA
才能作整合來源；查 remote head 並以 expected head 合併，避免合入未審的新 push。

## Owners、接口與依賴（目前分工）

| 包 | 整合 owner / 工作線 | 交付與依賴 | 現況 |
| --- | --- | --- | --- |
| R00 | Codex 主協調 | 決策、scope、狀態、中央/native 邊界 | 本分支文件 |
| R01 | Codex 主協調；既有 ops/confinement workers 完成當輪修正 | #36 → #37；legacy operations Part B；shared operation/task gates | #36/#37/#49 main；本輪加 send/continue/answer，其餘依盤點 |
| R02 | Codex desktop worker | `desktop/**`、共用 UI source、受限 transport、window/tray；依 R00 | #44 已合併；installed 驗收待做 |
| R03 | Codex 主協調（待 R02 bridge） | Fleet inventory/PS adapter → Rust parity、ownership、bootstrap | #45 PS adapter 已合併；Rust parity 尚缺 |
| R04 | Codex 主協調；observation worker 完成修正 | #35 read models → 共用 frontend state/history/relations | #35 main；#48 frontend 已合併 |
| R05 | Codex 主協調；保留 artifacts 分支 | fixed checkpoint、artifact bytes/manifest、明確 repository 的已發布版本同步；依 R01/R02/R08 接口 | checkpoint/#46/#50/B1 UI main；B2 工作線續作，repository 同步待查核；直接未發布 Git relay 已排除 |
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
6. R09 版本與安裝一致；R10 用同一候選版本跑 46 項及正式展示，才宣稱 M3／完整產品交付完成。

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
