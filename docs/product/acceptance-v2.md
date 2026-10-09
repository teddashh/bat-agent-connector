# Better Agent Dashboard／Connector：R10 驗收證據矩陣

證據快照：2026-10-08 23:26 UTC；產品整合 main 至 `6d88f4d`（#51 merge）。依產品負責人提供的
Tauri 第二版計畫 §24，保留 **A01–A10、B01–B05、C01–C07、D01–D06、E01–E06、T01–T12，共 46 項**。
範圍見 [realignment-v2.md](realignment-v2.md)，進度見 [implementation-status.md](implementation-status.md)。
兩份計畫對應同一產品與功能 backlog；Tauri 是更新的介面方向。
此表不是通過清單：**尚未建立同一候選版本的 installed／live 證據，M1、M2、M3 及完整產品交付均未完成。**

## 證據層級與版本

- **主線／分支**：程式所在位置；有程式或測試來源不等於已驗收。本輪彙整已記錄測試與審查證據；本文件更新沒有重跑測試。
- **F（fixture）**：MockBat、FakeGitHub、暫存真 Git／bytes、HTTP、browser／IPC mock。可證明指定邏輯，不能證明真 BAT、WebView 或實際部署。
- **N（native fixture）**：真 OS 子程序或打包 WebView 接合成服務。Windows PowerShell startup 與 Linux WebKit smoke 都不等於已安裝產品的端到端驗收。
- **I／L（installed／live）**：實際安裝組合、真中央／BAT／provider 的記錄。以下 46 項均仍需補對應 I／L 證據；未測平台不標支援。

以下代號供矩陣引用。SHA 與 CI 狀態會變；合併／發行前須重新記錄完整 SHA 和該 head 的 checks，不能沿用前一個 head 的綠燈。
本表的測試檔名預設位於所列候選的 `tests/`；`desktop/`、Kit 路徑另寫全名。連結固定到證據版本，不代表目前 main。

| 代號／候選 | 固定證據來源 | 此快照狀態與限制 |
| --- | --- | --- |
| M：#35、#36、#37 與既有核心 | [main `2ac5715`](https://github.com/teddashh/bat-agent-connector/tree/2ac5715549e08e36cfc0d2fd6b2c9e84a39a9334)：policy、operation/task gates、confinement、observation、checkpoints、integration | #37 已合併；head `09faafd` 四個 Python CI jobs 綠，本機 3.13/3.10 各 1619 passed/33 skipped。逐 host runtime／installed/live 尚缺。 |
| C：[#38](https://github.com/teddashh/bat-agent-connector/pull/38) cleanup | [`edf5683`](https://github.com/teddashh/bat-agent-connector/tree/edf5683af8a79ec802192b84a0b23029fa770ad5)：`cleanup.py`、`cleanup_host.py`、`test_cleanup*.py` | 已合併 `8c755a3`；四個 Python CI jobs 各 1835 passed/33 skipped。保留較早本機 3.10 的 settlement deadline failure 與原碼重跑紀錄；不以 retry 取代 full。Task-owned cleanup 未交付。 |
| S：[#43](https://github.com/teddashh/bat-agent-connector/pull/43) skills | [`f43f3c2`](https://github.com/teddashh/bat-agent-connector/tree/f43f3c2237d4c5092326a67fd5c7b90e6979f680)：canonical workflow `.3`、generator、principal-only MCP | 該 head 四個 Python CI jobs 各 1851 passed/33 skipped，已合併；installer 已改 pin 最終整合候選 `.4`，未實際安裝。 |
| U：[#44](https://github.com/teddashh/bat-agent-connector/pull/44) desktop foundation | [`5bccb63`](https://github.com/teddashh/bat-agent-connector/tree/5bccb63594b10fe61a772e45f3198e8b3969415e)：shared frontend、Rust bridge/main、capabilities、desktop design | 已合併；該 head 四個 Python jobs 各 1878/33，packaging 通過；保留 Linux WebKit N 證據。Windows install/tray/跨登入尚缺。 |
| F：[#45](https://github.com/teddashh/bat-agent-connector/pull/45) Fleet desktop | [`69f94d2`](https://github.com/teddashh/bat-agent-connector/tree/69f94d2719ba4c428392f087782e7ae4d290924e)：`fleet.rs`、`fleet.spec.ts` | 已合併；該 head 四個 Python jobs 各 1878/33、Windows 固定 PS subprocess/packaging 通過，候選整組另列。Rust supervisor parity、installed Kit 合驗尚缺。 |
| K：Fleet Kit [#8](https://github.com/teddashh/bat-fleet-kit/pull/8) | [merge `d3697dc`](https://github.com/teddashh/bat-fleet-kit/commit/d3697dc)，[reviewed head `2ec4b11`](https://github.com/teddashh/bat-fleet-kit/tree/2ec4b11bc010bfd669040e942648c741b63d0b7c)：`client/fleet-desktop.ps1`、`tests/fleet-*.tests.ps1` | 已合併；Windows PS 5.1／7、Linux PS 7 CI；所有環境均為合成 fixtures 或自有測試程序，未安裝。 |
| A：[#46](https://github.com/teddashh/bat-agent-connector/pull/46) artifacts Part A | [`560870b`](https://github.com/teddashh/bat-agent-connector/tree/560870b568ffa202d01501c3e553fbc3011c3561)：store/host、exact replica cleanup、binary upload bridge | 已合併；該 head 四個 Python jobs 各 1982/33，admission/fixture 修正與 peer 證據已含。跨 host Git、完整 native file/save/download 尚缺。 |
| D：[#47](https://github.com/teddashh/bat-agent-connector/pull/47) Delivery Part B | [`9874eae`](https://github.com/teddashh/bat-agent-connector/tree/9874eae4ae2c6622a866a792dff45d010dd16dd7)：deployment/store/verifier、owner/scope/history、shared UI | `831d670` CI 兩項舊 fixture 假設已修（canonical UI source、latest data step）；14 受影響 tests 兩版本通過。該 head full CI 四版各 2141/33，已合併且 issue #32 關閉；無真 deployed version 證據。 |
| O：[#48](https://github.com/teddashh/bat-agent-connector/pull/48) R04 UI | [`90e2392`](https://github.com/teddashh/bat-agent-connector/tree/90e2392bb8409c1d37cb76f27c8caae72af8e00c)：observation UI、pending/linked events、`desktop/tests/observation*` | 經 #51 合併；browser/native IPC mock/真中央加 MockBat 的 F 證據，最終整組 CI 綠；不是 M1。 |
| I：[#49](https://github.com/teddashh/bat-agent-connector/pull/49) R01 interrupt | [`3877da5`](https://github.com/teddashh/bat-agent-connector/tree/3877da5d0f8dc949fe19e3d8bfc61455d1eef5e0)：legacy interrupt adapter、`test_interrupt_operations.py` | 經 #51 合併；focused/peer 及最終整組 CI 綠。只是 Part B 第一片，其他 legacy mutations 尚未統一。 |
| B1：[#50](https://github.com/teddashh/bat-agent-connector/pull/50) manual single-file capture | [`c3b4abd`](https://github.com/teddashh/bat-agent-connector/tree/c3b4abd2617f4d46a1f35beb0230fa1bb5a4d80e)：`artifact_capture*.py`、capture/interrupt/principal tests | 經 #51 合併；139 focused tests 各 Python 版本、38 seam checks 及最終整組 CI 通過。同 credential/雙 scope replay/control 已審；UI/native preview allowlist、B2/C 尚缺。 |
| P：私有 installer #6 | reviewed `60ff6bd`，merge `2026750`：canonical pin/digest、principal-only、保留既有配置 | 已 pin `e634c30`/workflow `.4`；17 mock tests default Python/3.10、source verify-only、獨立審查通過。沒有實際安裝；不複製私有配置。 |

整合候選 `e634c3067e0ba1761336f2bb02360281f9f8e93d` 已經 #51 合併。其 [Python 3.10–3.13 full CI](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510798) 各 2264 passed/33 skipped；
[Windows NSIS/Linux deb、74 UI、8 state、Rust checks](https://github.com/teddashh/bat-agent-connector/actions/runs/37857510691) 皆通過。
Canonical workflow 是 `2026-10-08.4`；S 列 `.3` 僅描述獨立 PR 的歷史 head。
產品整合 commit `6d88f4d` 與已測候選 Git tree 完全相同；本次 docs-only 收斂更新未改 runtime/build/skills。
先前 439 focused、5 真中央 fixtures 與獨立審查仍保留其證據層級；沒有升格為 I/L。
#48/#49/#50 舊 CI 的 canonical-source/data-step fixture failures 已在候選修正，原失敗紀錄保留。

## 共用產品續作證據

[#55](https://github.com/teddashh/bat-agent-connector/issues/55) 的關聯 PR 保存本輪 exact-head CI、review、合併與 pin。
`c7525c3` 補 A01/A05/A07 的 send/continue/answer 全入口 fixture；`a866510` 補 B1 UI/native preview allowlist、
reload/lost reply 與真中央唯讀 bytes/index/refs fixture；`2fc8fd8` 關閉 A01/E01/E02 的 unsafe legacy removal。
[目前實作狀態](implementation-status.md#目前續作) 保留 focused 失敗／修正／重跑與完整 UI 結果。
這些是 F／N 子集，沒有把 46 項改成 I／L 通過；歷史表格的「尚缺」描述各列固定 commit 的快照。

## 46 項對照

每列的「已有證據」只涵蓋明寫的範圍；「尚缺」包括實作缺口及候選版的驗收前置條件。
測試名稱中的 acceptance ID 可直接用 `pytest -k` 定位；未命名 ID 的案例以下列檔案與描述定位。

### A：權限、來源與執行

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| A01 人工／unknown 的 send、answer、interrupt、resume、permissions、cleanup，含 force/bulk/舊入口 | M `test_resource_policy.py`、`test_api_v1.py`；C `test_cleanup.py`；I `test_interrupt_operations.py`：拒絕在 frame 前、原 caller scope。 | 其餘 legacy 入口的 R01 Part B 全覆蓋；同 RC 的 HTTP/MCP/CLI/Windows Tauri 零 BAT/Git mutation 證據。 |
| A02 Registry 與 cwd／symlink／clone binding 不符 | M `test_resource_policy.py` 的 human checkout／linked root／reviewer carrier，`test_confinement.py`／`test_confinement_integrity.py`。 | 各啟用寫入 host 的真路徑與 symlink 負例；人工檔案、HEAD/index/refs 前後比對。 |
| A03 人工 checkpoint、連結、標籤不改來源 | M `test_checkpoints.py::test_checkpoint_reads_a_person_session_and_writes_nothing`、`test_work_items.py`；B1 單檔 capture 前後不變 F。 | 標籤管理尚無對應 action／驗收來源；補 Windows 真人工專案唯讀路徑。未 commit 內容不能標成 checkpoint 已包含，B1 不代替 B2 或完整 snapshot。 |
| A04 人工／managed 同時新增 tab | M `test_orchestrate.py` 的 append/recheck/concurrent GUI cases；Task Service 預設 headless 邊界。 | **尚未消除 BAT `workspace:save` 整份覆寫 race**。正式路徑須證明原子能力或採 dedicated/headless，不能把「已知 race」當通過。 |
| A05 同 actor/key 重送與同 key 改內容 | M `test_api_v1.py`、`test_operations_unification.py`；I named-key 跨真 HTTP/MCP/CLI、no-key 明示、固定 prefix；A/B1 upload/capture replay。 | R01 Part B 其餘 mutation 的全入口統一；同 RC 跨兩個 client replay/conflict，保留同 operation／effect。 |
| A06 Start 送出前、lost ACK、ACK 後讀取失敗、重啟 | M `test_start_rollback.py`、`test_start_claims.py`、`test_confinement_recovery.py`、`test_operation_confinement.py`。 | 真 BAT 各失敗窗口與重啟；原 reservation/session/worktree、sent/readback receipt 不丟，不第二次 start。 |
| A07 paused/verifying/pending，入列後 binding/version 改變 | M `test_operations_unification.py`、`test_task_start_confinement.py`、`test_task_failover_authority.py`；I final-frame 回歸。 | 剩餘 legacy permissions/answer/resume 等完整入口盤點與同 RC 組合驗收；真 frame 前的暫停競態。 |
| A08 人工接續與 managed failover writer 不明 | M `test_checkpoints.py`、`test_failover_recovery.py`、`test_confinement_recovery.py`；I lost interrupt ACK 只讀回。 | 人工固定 checkpoint 新資源、managed 未知 writer 不增第二 writer 的真 BAT 失聯／恢復；全 legacy Part B 尚缺。 |
| A09 多 client／同 fleet 不同 journal 第二 daemon | M `test_operations_unification.py` 的 `test_a09_*`：owner-first flock、失 lease frame fence、共用中央 owner。 | 實際兩個 client／第二 daemon 啟動與中央重啟；Fleet 本機 owner 是另一層，不能互相代替。 |
| A10 Agent 寫 protected roots | M `test_confinement_closure.py`／`test_confinement_channel.py` 與 pre-interpreter proof、recorded/current evidence。 | **缺 W12 真 runtime 隔離證據**；逐 host/BAT/agent 版本測 outside-write 拒絕。Claude default/options、Codex workspace-write 或 prompt 均不算隔離證明。 |

### B：觀測、附件與升級

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| B01 多 sessions、無 tab、跨時期工作關聯 | M `test_observation.py` 的 B01、`test_inventory_cursors.py`；O `desktop/tests/observation.spec.ts` 穩定 ID 分頁/history。 | 同 RC 真多 session、warm reuse／歷史工作切換；UI 與 API 各頁時間／關聯一致。 |
| B02 Host 離線、SSE 中斷、client 重開、retention reset | M observation freshness；U `test_dashboard_sync.py`、`desktop/tests/events.test.ts`／`recovery.spec.ts`／`refresh-ack.spec.ts`、`central-integration.mjs`。 | 真中央斷線／休眠／reset，另一 host 正常、草稿不丟。桌面目前以 journal polling 接續；不得宣稱原生 SSE 訂閱已實作。 |
| B03 Actor／provenance 無證據 | M `test_observation.py` 的 B03、`test_observation_facts.py`；O state axes／unknown presentation。 | 真資料缺證據時保持 unknown/stale，不以顯示值授權；不同 agent actor 的 UI 證據。 |
| B04 傳輸中斷、digest 錯、來源選後更新 | A `test_artifacts.py` 的 B04：暫存真 bytes、materialize/readback、ready 前不送首指令、同 parent 恢復。 | **跨 host Git objects/materialization Part C 未實作**；B2 managed capture/accept 仍缺；真 SSH 與 native 中斷後固定 refs/ID 驗收。 |
| B05 Connector 自有 schema／registry／資料升級重開 | M observation step 2/backfill；A `test_artifacts.py::test_artifact_migration_preserves_existing_journal_and_empty_manifests`；D `test_deployment_history.py` step 1→2→3。 | 同 RC 用去識別舊 Connector fixture 升級再重開，比對 IDs/樹/links/provenance/歷史及 rollback；**不讀 Hub snapshot，不引入 #39**。 |

### C：同 PR 整合與 merge

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| C01 人工＋兩個 AI 成果更新同 PR | M `test_integration.py` 的 C01：暫存真 Git、managed integration area、人工來源不變。 | 真人工專案＋兩個獨立 managed 工作同 PR；來源覆蓋及跨 host 所需 objects 完整，人工 HEAD/index/files 不變。 |
| C02 Preview 後 source／PR head／scope 變動 | M `test_integration.py` 的 C02、`test_delivery.py` scope-change：拒絕舊意圖、非 force push。 | 真 provider 競態及 Tauri 差異顯示；固定來源、不以新 branch head 替代。 |
| C03 中途衝突／push lost ACK | M `test_integration.py` 的 C03：compose receipts、resolver handoff、遠端讀回、重啟不重複 push。 | 真 Git remote 的衝突／失聯／讀回與 UI 續做；仍只寫 managed integration 區。 |
| C04 Merge queue／accepted／existing request | M `test_delivery.py` 的 C04、`pr_delivery.py`；保留 #40 metadata settlement。 | 選定 repo 的真 queue/provider 行為與 exact intent；queued/accepted 不顯示 merged。 |
| C05 Merge 後 crash／check 後 base 前進 | M `test_delivery.py` 的 C05、固定 merge preview/readback。 | 真 provider 的 actual merged SHA、範圍與重啟查回；記錄 base 競態限制，不宣稱跨系統原子鎖。 |
| C06 無 managed task ID 的人工 PR | M PR merge operation；D `desktop/tests/delivery.spec.ts`、`delivery-integration.mjs`：UI 直接 central action。 | 有權限 Windows 使用者對真人工 PR merge/deploy；不建立虛構 task。 |
| C07 UI／agent／CLI 共用 action 與 caller scopes | M `test_delivery.py` C07；D `test_deployment_surfaces.py`、`test_delivery_resume_scopes.py`；S principal-only；B1 replay/control credential 回歸。 | 同 RC 三入口與不同 principal 實測；composite resume 需目前雙 scope，agent 不借 local-admin/Ted authority。 |

### D：部署

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| D01 Merge 觸發部署，run 尚未出現 | D `test_deployments.py` on_merge route／exact unique operation token、`test_deployment_recovery.py`。 | 選定真 workflow 的延遲 run，追原 route 且零額外 dispatch。 |
| D02 Dispatch 已送但 ACK／204 lookup／讀回失敗 | D `test_deployments.py::test_d01_d02_204_requires_exact_unique_operation_token_and_never_redispatches`、recovery throttling/readback。 | 真 provider 故障窗口；保存同 operation/run，未知不重送；明確 429 refusal/backoff 與 ambiguous 分開。 |
| D03 缺 source SHA／skipped／環境等待／產品版本不符 | D `test_deployment_config.py`、`test_deployments.py` D03、`test_deployment_verifier.py`。 | 配置真 source mapping 與 runtime verifier；記 actual product SHA/artifact digest＋health，workflow 成功不代替 deployed。 |
| D04 Merge 成功、deploy 失敗後 retry/restart | D `test_deployment_rollback.py::test_d04_retry_keeps_saved_identity_and_never_merges_again`；recipe change/readback cases。 | 真固定 merged SHA 的 deployment retry；recipe 更新不能換 route 或再次 merge。 |
| D05 舊部署晚完成、cancel、另一部署進來 | D `test_deployments.py` D05、`test_deployment_recovery.py`、`test_delivery_owner.py`：generation/slot 與 owner-gated reconcile。 | 真環境同時部署、cancel 後外部 run 仍在跑；current/desired/history 正確，未終結前不釋放排他。 |
| D06 回退已部署版本 | D `test_deployment_rollback.py` D06：saved source/artifact identity、新 operation、lost reply、拒絕未驗證／過期版本。 | 真 release/artifact 可取回及 runtime 版本；先列不能回退的 DB migration 等外部效果，記實際結果。 |

### E：清理、Fleet 與版本

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| E01 混合人工／unknown／active／completed 工作樹 | C `test_cleanup.py`、`test_cleanup_task_authority.py`、`test_cleanup_resource_ids.py`；U `desktop/tests/cleanup.spec.ts`／`cleanup-integration.mjs`。 | 真樹 preview/apply/receipts/tombstones；**Task Service reviewed cleanup/finalization 未實作，仍 TASK_OWNED 保留**。 |
| E02 共用 worktree/artifact、squash、remove 後讀回失敗 | C `test_cleanup.py` squash/pick exact receipts、`test_cleanup_uncertainty.py`／`test_cleanup_protocol.py`；A `test_artifact_cleanup.py` readable-original／resume gate。 | 同 RC 真 shared consumer／唯一內容與故障恢復；不重 remove，不把 metadata 存在當原 bytes 尚可讀。 |
| E03 選兩台、零 BAT profiles、Dashboard、一台 auth 卡住 | K `tests/fleet-client.tests.ps1` 的 E03、`fleet-readiness.tests.ps1`；F `desktop/tests/fleet.spec.ts` selection/readback。 | Installed app＋Kit＋真中央、Dashboard-only 的完整組合；不開 BAT、不停中央工作，故障 host 不拖累其他項目。 |
| E04 重開／crash／tray quit／其他登入／PID reuse | K `fleet-lifecycle.tests.ps1`、`fleet-desktop.tests.ps1` ownership/budget；F Rust subprocess timeout 只終止自有 facade。 | 真同/跨 Windows login session、foreign listener 與 crash；另補 Rust supervisor parity，不能以 Tauri single-instance 代替跨登入 owner。 |
| E05 TCP 通但 identity/auth/version/workspace/contract 不符 | K `fleet-readiness.tests.ps1`、`fleet-desktop.tests.ps1` applied generation；F typed DTO；U central actor/contract refusal。 | 真 host 各 readiness 層、舊 generation、修配置後 budget；blocked/degraded 不標 Ready，不擅自重啟。 |
| E06 新舊 skill/client/backend 混用 | S generator/version checks、`test_agent_skills.py`／`test_mcp_principal.py`；P pin/digest installer。 | 同 RC 實際安裝、升級／不相容拒絕；顯示 repo、installed、server contract、skill version，兩個 agent 各用自身 actor。 |

### T：真正桌面產品

| ID／情境 | 已有實作與測試來源 | 尚缺／完成條件 |
| --- | --- | --- |
| T01 安裝並啟動打包 app | U Vite packaged assets、Rust bridge、`desktop/tests/native-smoke.mjs`；F Windows NSIS／Linux deb CI。 | Windows 實際 install/launch、真中央資料；正式 runtime 無 Vite。Linux N 只接 fixture，不能算此項已通過。 |
| T02 Close-to-tray、同/跨登入重開、草稿/event 接續 | U `main.rs`、single-instance、Linux N close/handoff；F/K other-session owner DTO。 | 實體 Windows tray、同 session focus、跨 session app fence/owner 說明；未完成跨登入 app 行為，不承諾聚焦另一桌面。 |
| T03 未安裝 BAT 的 Dashboard-only | U desktop 不啟動 BAT/daemon；F Fleet missing/configured 狀態與中央分離。 | 真乾淨 Windows 帳號可管理中央；BAT open 功能尚未提供，實作後只在該功能提示缺 BAT。 |
| T04 PS→Rust supervisor 遷移／回退 | F 固定 PS facade；K 唯一 monitor owner，現有 frontend 不另啟 tunnel loop。 | **Rust supervisor parity 與新舊 autostart 遷移未實作**；真升級／回退時始終一個 owner。 |
| T05 PID/SID/inventory/args 不符或外部 listener | K `fleet-lifecycle.tests.ps1`、`fleet-desktop.tests.ps1`；F `fleet.rs` DTO／固定 quit epoch。 | Installed Kit＋native bridge 真負例，零 foreign kill／零搶占；不以 fixture process adapter 代替實機。 |
| T06 非法 native 參數／外部內容 | U Rust bridge/main/capabilities 的 allowlist/origin/size/credential tests；F `fleet.rs` 固定 script/環境、無 arbitrary PID/path/URL。 | Windows 真 WebView navigation/IPC 負例；整合後所有新增 commands 重查，不暴露 shell、任意檔案或帶 token URL。 |
| T07 Pending、linked operation、parent archive 即時更新 | O `desktop/tests/observation.spec.ts`、`observation-integration.mjs`；U refresh barrier、D history sibling read barrier。 | 真中央＋Windows mounted view，另一 client 改狀態；草稿不丟、舊 pending identity 不能誤送。 |
| T08 原生選檔／拖放／上下傳中斷／同名目的地 | A `desktop/tests/artifacts.spec.ts`、`artifact-integration.mjs`、Rust operation-bound binary upload；`test_artifacts.py` download API。 | **完整 native file/save/download adapter、拖放與同名檔案政策未交付**；真 bytes/digest、重試與人工來源不變。WebView upload fixture 不等於整項通過。 |
| T09 Client 更新／睡眠／crash／切網路 | U `desktop/tests/recovery.spec.ts`／`account-switch.spec.ts`／`dashboard.spec.ts` 的 lost reply/drafts；M durable operations。 | 真 Windows suspend/network/crash 與安裝更新；原 ID 查回、中央 task 不停。簽章 updater 尚未提供。 |
| T10 Tailscale 未登入、中央停止、固定 bootstrap | K 分層 readiness；U/F 顯示連線／配置失敗，native 不自動建中央 journal。 | **Tauri 登入/固定 ensure bootstrap 流程尚未交付**；先配置明確 recipe，有限恢復，零第二 owner／空 journal。 |
| T11 帳號／backend 切換與 scope 隔離 | U `test_dashboard_sync.py` T11、`desktop/tests/account-switch.spec.ts`；F local DTO 不含中央 token；S principal-only。 | **OS 保護 credential enrollment/storage 尚未實作**；目前啟動環境變數→Rust memory 是暫時 adapter。真切換/重啟隔離與 Fleet observe 身分待驗。 |
| T12 Canonical desktop/browser、build/update/signature | U `desktop/src`＋`build:all`／`check:browser`、locked dependencies；S generator/version checks；F packaging CI。 | 最終單一整合 source/pins、可重建產物、簽章與更新相容／回退；不能把 unsigned NSIS/deb 或兩個分支各綠當正式發行。另有 [Linux GLib advisory gate #53](https://github.com/teddashh/bat-agent-connector/issues/53)，須已審修正後才作 Linux production distribution。 |

## 同一候選版本的可重現驗收

1. **固定 RC**：整合上述必要能力後，記 app/backend 同一完整 commit、Kit/installer pins、skill digest、OS/WebView/BAT/agent 版本及中央 contract。尚缺實作的列先補能力；不能只把格子改為「待實機」。沒有這組 manifest，不彙總為 R10 通過。
2. **F／CI gate**：在固定 RC 的隔離 CI 跑 Python 3.10–3.13 full suites、Ruff、secret scan；再跑 shared UI 的 browser/native-IPC tests 與 central fixtures。來源合併後必須是該 RC 的結果；已有 exact-head CI 不需為累加數字重跑相同本機 full。
3. **N gate**：Windows 真 system PowerShell subprocess＋Kit 自身 Pester、Rust tests、打包 WebView fixture；另保存 Linux N 的平台範圍。DOM／IPC mock 與真 WebView 日誌分開，跳過的能力不能宣稱通過。
4. **I／L gate**：選一個非正式部署的驗收 repo/environment、一個人工專案、兩個 managed 工作、至少兩個 client，各自 scopes；環境引用只放私有 run manifest。依 A→B→C→D→E 路徑與 T 場景執行，注入指定故障，查回同 ID/key。每台允許無人寫入的 host 另留 A10 證據。

以下為 **完成整合後 RC** 的 fixture 重現入口，並非本文件執行紀錄，也不連真 hosts/provider：

```sh
# Repository root；full Python matrix 由 CI 的各 interpreter 執行
uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
python3 scripts/generate_agent_skills.py --check

# Shared frontend；先依 CI 安裝 Playwright/browser 與 native build prerequisites
cd desktop
npm ci
npm run build:all
npm run check:browser
npm test
npm run test:ui
npm run test:central
npm run test:cleanup
npm run test:artifacts
npm run test:delivery
npm run test:observation
cargo test --locked --manifest-path src-tauri/Cargo.toml
```

Windows 打包／Linux native smoke 的具體入口見 U `docs/design/desktop.md`；Kit 的固定 modules 與
`tests/run-tests.ps1` 見 K `.github/workflows/client-tests.yml`。這些測試各有 fixture 邊界，不提供任意真 host write 指令。

每次 run 的最小記錄：`RC manifest / acceptance IDs / layer(F,N,I,L) / scenario + fault / expected / actual / result(pass,fail,blocked,not-run) / log或artifact引用 / operation與receipt IDs / remaining gap`。
敏感環境名稱、tokens、fingerprints、完整檔案與原始日誌留在私有證據位置；公開表只放去識別摘要與可取用的證據引用。
保留所有失敗及重跑原因；GitHub review bot 無額度不算乾淨 verdict，本機獨立審查另記 reviewer/head。

正式收斂路徑仍是：Windows 登入 → Fleet/中央 → 唯讀人工 checkpoint → 兩個 managed 工作與附件 → 同 PR
→ merge/deploy 查實際版本 → reviewed cleanup 留歷史 → client 重開中央繼續 → 新 agent 以自身 MCP 身分接手。
唯有同 RC 的 46 項結果及上述缺口都可追溯，才能重新判定各里程碑；本快照不作完成宣告。
