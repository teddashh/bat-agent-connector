# Project Hub 最新前端功能複查與採用決策

查核日期：2026-10-09。需求：重新查看最新 Project Hub，逐項確認前端值得借用的功能及適用性。
這是一份採用決策與後續工作表；「採用」表示決定納入後續實作，不表示功能已經完成。

## 查核版本與方式

- 上游：[kieiken/project-hub][upstream]，GitHub API 與 `git fetch` 核對最新 `main` 為
  **`a277d2ed5ce439c248fc32fa8ff9fa4124a06027` / v4.90.0**。commit 時間為
  2026-10-07 20:04:07 UTC；CHANGELOG 的 2026-10-08 是其文件日期。
  與先前 session 整理引用的 SHA 相同，不能把重查說成上游又發了新版。
- 我方比較基準：**`ba56322e22734f2a37f3dd6ee0b14ab65d9d42c6`**，即 Mac PR #69 合併後的 main。
  核對 `desktop/src` 實際原始碼，歷史設計文件中「尚缺」的描述不直接當成目前事實。
- 主線全部 **15 個自有前端 JS 模組、app.css、index.html、manifest.json** 納入入口盤點；
  同時核對 README、CHANGELOG、相關 frontend tests 與三個 open PR 的固定 head。
  `icon.png` 是品牌圖像，無需移植；`vendor/xterm*`／`vendor/addon-fit.js` 是外部終端元件，
  評估整合用途，沒有逐行審查第三方函式庫。
- 以原版 HTML/CSS/JS 搭配記憶體中的虛構 API/SSE，查看 1440、768、390 寬度的專案、
  對話、待辦、四個設定分頁、新專案與手機收合狀態，共產生 26 張截圖；檢視代表性桌面及手機截圖。
  沒有啟動 Hub server、AI CLI、真實工作區或帳號，也沒有操作實際刪除／合併。
- 上游六組相關測試（chat-scroll、rich-text、mobile-ui、settings-scroll-ui、zh-tw-ui、
  onboarding-ui）**52 passed / 0 failed / 0 skipped**。這是上游 fixture 證據，不能當成我方採用後的驗收。
  browser profile 與測試暫存均放磁碟，結束後清除。
- 下表共 **82 項**功能／提案決策。完整盤點來源與模組對應另見
  [machine-readable inventory](project-hub-frontend-inventory-2026-10-09.json)。

## 結論與實作順序

先補足日常使用的閱讀與派工體驗，沿用我們的 `--panel`、`--line`、`--chip`、
`--muted`、既有按鈕及雙語詞鍵。無須更換 frontend framework 或重做整套視覺。

| 順序 | 決定採用 | 我方真實缺口 | 完成條件 |
| --- | --- | --- | --- |
| P1-1 | 訊息程式碼區塊／表格、原文複製、閱讀位置與「回到最新」 | `viewSession.loadMessages` 目前直接顯示 `m.text`，每次替換訊息列；列表錨點保留不等於對話閱讀位置保留 | 安全 DOM renderer；不接受任意 HTML／URL；未完成串流不吞字；複製維持原文；捲動閱讀時不跳底；事件 ACK 與原訊息不變 |
| P1-2 | 待回覆、待確認、未讀分開；同用語與可解釋數量 | 待處理與工作完成確認已存在；缺少獨立的已讀位置／未讀結果語意 | 已讀狀態依 backend/principal/resource 隔離；不能將 event cursor 當已讀；跨頁未載入不能冒稱總數；不清除真正 pending |
| P1-3 | 專案內快速派工＋進階設定＋附件草稿 | 有 direct managed start、checkpoint continuation、附件；專案頁只有新增工作項目，沒有 Hub 式整合快速入口 | 顯示並固定 host/workspace/repository/agent；無唯一綁定時要求選擇；保存原 request/key；不得自動把待辦變成 Task Service task |
| P1-4 | 手機資訊／輸入區收合、鍵盤適應、可調側欄 | 現有 responsive 與 sessions 工作區選擇已具備；缺乏同等對話收合、側欄調寬 | 390/768/1440、鍵盤與觸控；草稿與焦點保留；44px 觸控範圍；側欄具鍵盤操作及最小內容寬；行動版不套用桌面寬度 |
| P1-5 | 設定依連線／本機／模型等職責分組，明確顯示未儲存；可恢復初始設定導引 | 目前連線、Fleet/bootstrap 等已有入口；缺少串連的首次使用流程 | 導引只做選擇與檢查，真正修改沿用既有操作；刷新不覆蓋草稿；不擅自更換帳號／模型；中英狀態同義 |
| P2 | 模型偏好、中央可驗證的額度摘要、專案 Skill 選擇、成果回到父工作的入口 | 有局部基礎，缺中央讀取／儲存合約或完整 UI | 先補 authoritative API、版本與作用域，再接 UI；每項分開驗收 |
| 暫緩 | freetalk、專案 phase、建立 GitHub repo、一般資料搬家 | 會新增產品模型或外部寫入能力 | 有明確使用情境與中央契約後再排；本次不因上游有按鈕就增設同一套後端 |

## 逐項決策

「保留」＝我方已有對應能力，保留其語意；「採用」＝適用且尚有 UI 缺口；
「改接」＝採用使用者體驗，但必須接我方中央合約；「暫緩」＝目前不排入；
「不採用」＝與已定產品方向衝突。行號均指上述固定上游 SHA。

### A. 導覽、專案與狀態

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| A01 | 緊湊樹狀導覽、名稱優先、次要證據收起；app:244–410 | 保留／補強 P1 | sessions 已有 host/workspace 分組與 details；projects 可提高一致性，不猜 project 歸屬。`app.js:viewSessions/viewProjects` |
| A02 | 子項目縮排，衍生分支與來源同層；project-order | 保留 | 已有 parent/source IDs 與工作樹；我方分支位置按 `parent_id`，不跟來源自動搬動。`work-items.md` |
| A03 | 改名不改工作 ID／位置；hierarchy:31 | 保留 | 中央 rename/version 操作已有；保留穩定 ID、歷史與關係。 |
| A04 | 固定、拖曳排序、上下鍵按鈕；hierarchy:62 | 採用拖曳 P2 | 固定、上下移已具備；新增拖曳仍送完整同層 expected version/order，保留可及性替代。 |
| A05 | 右鍵與「…」同一組操作；hierarchy:5 | 採用 P2 | 行內多個低頻動作可收進共用 menu；不能只有右鍵入口，權限原因仍可讀。 |
| A06 | 步驟進度和人工確認完成分開；app:42、592 | 保留 | 我方已有 steps、completion fingerprint、approve/continue；不把全勾、idle 或 AI 說完成當核准。 |
| A07 | Phase 路線、目前階段展開、下一階段確認；app:54、601 | 暫緩 | 我方工作樹已有狀態；沒有獨立 phase 資料模型，不能從 steps 推造 phase。 |
| A08 | 專案說明收合、父／衍生／相關專案、問題原文；app:540、687、753 | 改接 P2 | 已有 description、relations、history；補清楚的來源與問題摘要，摘要不得取代原文或猜測解決。 |
| A09 | 未讀結果與讀取後解除；app:177 | 採用 P1 | 我方缺此獨立 UX；中央事件已處理與人已閱讀不同，需要 principal 範圍及讀取位置。 |
| A10 | 「輪到你」分待回覆／完成確認、數字同義；app:185、426 | 改接 P1 | Home 已有需要你／待確認，但後者含未結束 operations，不能直接改名成工作完成確認；補明確分組。 |
| A11 | 工作中、等待輸入、上限停止、完成各狀態；app:102、260 | 採用語意，不採 timeout 推定 | Hub 用畫面靜止 20/60 秒提示等待；我方只用中央 pending/activity/staleness，保留未知。 |
| A12 | 旁路啟動 AI 的背景工作提示；app:261、687 | 改接 P2 | 只顯示 BAT inventory/discovery 的已觀測來源；不能依名字/PID 自行賦予管理權。 |

### B. 建立工作、輸入與確認

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| B01 | 專案內寫需求即開始，細節另展開；app:618–752 | 改接 P1 | 複用 `session-start.js`／work-item continuation；名稱新增待辦與開始 managed session 仍是不同動作。 |
| B02 | 初始 AI 與上次選擇分開，保留失效候選說明；app:1051、1873 | 改接 P2 | 我方有 agent/model 輸入，缺可驗證模型目錄及偏好；不複製上游寫死的 model/effort 名稱。 |
| B03 | 專案／作業草稿保存，成功後只清此次提交；app:618、1399 | 保留／擴充 P1 | 我方已有 namespace 草稿與 durable request；快速入口須沿用，儲存失敗不送出。 |
| B04 | 圖片貼上、拖入、縮圖、移除、只有圖片也能送；app:654、992 | 改接 P1 | 既有 native-files／artifact attachments 已有挑檔、拖入、預覽；缺完整 composer 縮圖與貼上 UX，不能當純視覺補丁。 |
| B05 | 新專案／工作精簡表單＋詳細角色、關係、位置；app:516、687 | 改接 P1 | 我方已有 project/work-item/start；合併呈現既有欄位，仍固定中央 scope／binding，不提供人工原目錄直接寫入模式。 |
| B06 | 一次拆成子專案並各自啟動；app:438 | 暫緩整套，保留批次概念 | `orchestration.js` 已有並行 managed starts；不因方便就把每個工作自動升成新專案。 |
| B07 | 勾步驟、新增步驟、備註、狀態與來源；app:899 | 保留 | `viewWorkItem` 已提供目標／驗收／steps／links；需要 manage/approve 及版本檢查。 |
| B08 | 問題選項＋自由輸入、可多題一次提交；app:851、1314 | 保留／補強 P1 | 既有 pending 問題與 permissions/bulk approval；只答固定 pending ID，過期題唯讀、草稿不串題。 |
| B09 | 「清除不傳送」單筆／整批消去問題提醒；app:489、426 | 不採用清除 pending | 未處理權限與問題不可被 UI 消音當作處理；未來只可對獨立通知做已讀，保留中央 pending。 |
| B10 | 子工作未結束時，父工作啟動前提示；app:484 | 改接 P2 | 顯示中央 related tasks/active consumers；說明影響並尊重 coordinator gate，不增加每次都要聊天批准。 |

### C. 對話、執行與接續

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| C01 | 程式碼區塊、表格、串流未閉合區塊；app:1145 | 採用 P1 | 我方訊息目前純文字；以安全 DOM 渲染及原文 fallback 實作，保留 CSP。Hub 本身也不是完整 Markdown renderer。 |
| C02 | 複製整段／程式碼、失敗提供手動選取；app:1206、1214 | 採用 P1 | 只複製使用者選的可見內容；不監聽背景剪貼簿，成功訊息必須依 API 結果。 |
| C03 | 回覆顯示 AI、model、時間與耗時；app:1284 | 改接 P1 | session 已有 agent/model 與訊息角色/時間；逐次來源只顯示中央實際提供的 metadata，不以目前 model 補寫舊訊息。 |
| C04 | 靠底跟隨、向上閱讀不跳動、回到最新；chat-scroll | 採用 P1 | sessions／operations 的列表錨點已存在；session 訊息尚缺同等行為。 |
| C05 | 預設收合工具細節，保留重要通知；app:1278、1284 | 改接 P1 | 保留 error、pending、sent/uncertain；只收起中央已有且可揭露的細節，不隱藏失敗原因。 |
| C06 | Enter／Cmd+Enter 偏好，Shift+Enter 換行；app:1280、1399 | 採用 P2 | 加入平台適用快捷鍵與 IME composition 保護，繁中選字不誤送。 |
| C07 | 串流、執行中、耗時與最後活動；app:1477 | 改接 P2 | 現有 event refresh 與 activity 已有；只依中央執行證據顯示，斷線／stale 不假裝持續運作。 |
| C08 | 待送指示順序、單筆取消、重新開始；app:1462 | 改接 P2 | 我方已有執行中排隊送出與操作回執；可補 queue 呈現，但需中央明確 queue identity/control，不能在瀏覽器另造排程。 |
| C09 | 「取消重做／補充說明／完成後接續」分開；app:1444 | 部分改接 P2 | 清楚表達意圖值得採用；不承諾取消會撤回已發生副作用，也不把 interrupt＋send 包裝成原子重做。 |
| C10 | AI 交接、不同模型共用可見對話；app:1618、2537 | 改接既有流程 | 我方已有 checkpoint、managed continuation、受限 failover；保留來源／新 execution 身分與回執，不覆寫人工 session。 |
| C11 | 內嵌 xterm、並排兩個終端、直接輸入 model 命令；app:1574–1631 | 不採用 | BAT 是執行介面；Dashboard 不另造 PTY、CLI runtime 或任意 shell command bridge。 |
| C12 | ChatGPT 側窗、複製上下文／貼回、剪貼簿偵測；app:798–850 | 暫緩手動交接；不採側窗監聽 | 已有 principal-only MCP/CLI；未來可設固定內容的手動交接匯出，不加入遠端特權 WebView 或自動讀剪貼簿。 |
| C13 | 常設 freetalk、新話題、獨立續接；app:320–374、2488 | 暫緩 | 類似一般聊天產品；目前主軸是跨主機專案與工作管理，不新增第二套聊天執行器。 |
| C14 | 先審核摘要再接續／升級為專案；app:325、340、2491 | 改接 P2 | 可用於 checkpoint／work-item 接續摘要，但原始記錄與來源 ID 永存，摘要不當驗收或權限證據。 |
| C15 | 每月自動清 freetalk、清空後新對話；app:320、2488 | 不採用自動刪歷史 | 與 durable operations、追溯及人工資源保護不符；沿用明確 preview/reviewed cleanup。 |

### D. 附件、成果與 GitHub

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| D01 | 拖檔／貼圖、附件路徑與預覽；app:2933 | 保留／補強 | `native-files.js`、`artifact-content.js`、attachmentDraft 已有實作；送中央固定 artifact revision/digest，不把 client path 當遠端檔案。 |
| D02 | 路徑連結、Finder 開原檔、資料夾內容；app:1106、1239 | 改接 P2 | 只開既有 artifact／受限 native handle；遠端 host 路徑不等於本機，禁止任意 path／URL bridge。 |
| D03 | GitHub 連結依本體或工作 branch；app:195 | 保留／補強 | 已有綁定 repo、PR、source SHA；增加相應來源連結即可，不由同名資料夾猜 remote。 |
| D04 | 建立 private repo、帳號／owner、push 另選、部分成功；github | 暫緩新建能力 | 我方已有 repository binding/publish/delivery，尚無此 UI 合約；外部建立與 push 須各有 receipt，不能 UI 直接呼叫 gh。 |
| D05 | 合併前列檔案數、差異、衝突；app:1553 | 保留／補強 | `integrationPanel`、delivery preview 已有固定 SHA／順序與 blocker；優化摘要，不取消現有檢查。 |
| D06 | 父工作收到子成果、依順序整合、逐項回執／繼續；task-transfer、task-integrate | 改接 P2 | 既有 artifact-review/integration/operations 已涵蓋核心；補父子工作直接入口，保留已成功步驟與依賴。 |
| D07 | 排除某副本合併、仍保留位置與內容；app:2574 起 | 改接 P2 | 可做 integration selection／保留意圖，不把排除當完成或可刪，中央 references／pins 才是保留權威。 |
| D08 | 子成果整理、驗收與缺漏原因；app:592、2563 | 保留 | 既有 capture／artifact accept＋independent review；AI 生成的說明不能替代內容 digest 與驗收證據。 |
| D09 | 自動保存原專案、git add -A、合入後丟垃圾桶 | 不採用 | 我方工作在獨立 managed 資源；不自動提交／修改人工原目錄，不把成功 merge 等同 cleanup 授權。 |

### E. 整理、檢查與恢復

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| E01 | 刪除前明列移除／保留／拒絕原因、過期重讀；remove | 保留／補強 | `viewCleanup` 已有 preview、選擇、逐項 receipts、retained content；可借用更易讀的分段，不更換中央判定。 |
| E02 | AI 檢查外部資料夾共用、判定後預選；remove:15 | 不採用 AI 當刪除依據 | AI 可解釋既有 evidence，但不能決定 ownership、shared refs 或擴大刪除集合。 |
| E03 | 整理紀錄、復原、失敗保留原交易；maintenance | 保留紀錄，復原按既有合約 | 我方保留 tombstone/retained refs；不能泛稱任何刪除都能 Undo，缺 restore action 的項目不出假按鈕。 |
| E04 | 搜尋空對話並批次丟垃圾桶；app:2472 | 不採用「空即安全」 | 空輸出不是無效果證明；採中央 cleanup candidates，保護 writer/pending/consumer/唯一內容。 |
| E05 | 台帳／連結健檢與明確區分 app test；maintenance:5 | 改接 P2 | 可整合現有 discovery、relations、verification 的讀取頁；中央沒有的任意 npm test 不直接執行。 |
| E06 | 健檢問題一鍵開修復工作、重用進行中項目；maintenance | 改接 P2 | 有價值；只能建立固定 evidence 的 managed repair intent，與一般重新讀取區分，不改原人工資料。 |
| E07 | 最近操作、階段、錯誤與恢復入口；app:2460 | 保留 | 我方 `viewOperation` 與分頁歷史更完整；可在相關資源頁增加短摘要，不另存前端權威日誌。 |

### F. 設定、模型、連線與更新

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| F01 | 基本／AI／連線／管理分頁，草稿標記、焦點與捲動保留；app:1633、2184 | 採用 P1 | 我方 native settings 含多種責任；依現有 capability 分組，切頁不丟待存設定。 |
| F02 | 模型隱藏、排序、重置，保留當前值；model-order、app:1766 | 改接 P2 | 視覺偏好不得改中央允許模型與既有工作；需要真實候選目錄，失效值保留說明。 |
| F03 | 手機模型簡稱、完整 aria label、自訂顯示名；app:1024、1914 | 採用 P2 | 僅變 label，永不變 API model ID；先做自動縮排／截短，不必先加每個模型的設定負擔。 |
| F04 | 多 AI 帳號、登入狀態、工作所選帳號；app:1990 | 改接唯讀 P2，帳號管理暫緩 | Dashboard 的中央 principal 與遠端 provider account 不同；可顯示 host inventory，不在 client 掃描或操作其他帳號登入資料。 |
| F05 | 角色主／備援 AI、已登入候選、未儲存標記；app:2209 | 暫緩編輯，借用狀態呈現 | Task Service recipe/coordinator 是權威，不能把 Hub roles.yaml 變成另一排程／自動切換策略。 |
| F06 | CLI 更新確認與套用分離，busy 禁套用；app:1649–1765 | 暫緩新 host 管理能力 | 可以借用顯示已安裝／未知／忙碌的 UX；現無 remote CLI 更新合約，不由 Tauri 跑 shell 更新。 |
| F07 | 額度百分比、重設時間、帳號、stale、取得失敗；usage | 改接 P2 | 先新增受限中央 read model；明確區分訂閱額度、token、context 與費用，不讀 client 上的 provider secrets。 |
| F08 | 全域 Fast 許可＋各工作選擇與成本提示；app:2048、2372 | 暫緩 | 依中央 agent capability／明確成本資訊提供；不能直接複製上游寫死的速度、額度倍數或 CLI 參數。 |
| F09 | 可稍後繼續的四步 onboarding、檢查與真正開始分離；onboarding | 改接 P1 | 組合現有 bootstrap/Fleet/credential/version readiness；顯示哪一端要準備，不在 client 裝遠端 AI。 |
| F10 | 應用程式更新狀態、最後／下次檢查、busy 延後；app-update | 保留／補強 | 我方有固定來源與簽章 updater；Mac updater 尚待實作。狀態 UX 可共用，已下載不代表已安裝。 |
| F11 | 更新時用 AI 改譯原始碼、測試、建置與送翻譯 PR | 不採用產品內自改碼 | 翻譯在 source/CI 固定審查；使用者 app 只接受受信版本，不在更新過程動態生成待執行程式。 |
| F12 | iPhone/Tailscale 設定、其他裝置登出；app:2335 | 採用導引，保留現有 transport | browser fallback/Fleet/Tailscale 已有；不複製無本機登入的 Hub server 或另建 shared-passcode 身分體系。 |
| F13 | macOS 資料夾權限說明與重新檢查；app:2280 附近 | 改接限定範圍 | 已有原生選檔與 handle；只處理必要資源的可讀性，不以 Full Disk Access 作預設解法。 |
| F14 | CLI 顯示名／實際旗標、重新取得模型與未知說明；app:2403 | 暫緩旗標編輯；採用錯誤說明 | 中央 capability 決定支援；不提供任意 CLI flag，未知型號不能偷偷換預設。 |

### G. 跨畫面品質

| ID | Hub 功能／原始碼入口 | 決策 | 我方對照與理由 |
| --- | --- | --- | --- |
| G01 | 手機把資訊和 composer 分別收起，顯示有草稿；mobile | 採用 P1 | 390px 對話閱讀面積明顯改善；採同一 DOM，不拆第二套手機 frontend。 |
| G02 | visualViewport 適應鍵盤、不誤處理 pinch zoom；mobile:29 | 採用 P1 | browser fixture 只能查 layout；iOS/Android 真鍵盤、縮放仍需裝置驗證。 |
| G03 | 系統明暗主題與一致 CSS tokens；app.css | 保留 | 我方已有 light/dark token；不複製品牌色、emoji／裝飾或與本產品不合的密度。 |
| G04 | focus-visible、鍵盤 tab/menu、reduced motion、觸控替代 | 保留／補強 P1 | menu、resizer、drawer 均需完整鍵盤；Hub 若僅 40px 控制，我方仍依 44px 觸控標準調整。 |
| G05 | UI 翻譯與不透明 user content 分離；locale | 保留 | 我方 en/zh-TW 詞鍵與身份隔離保留；上游 main 的部分未標記日文仍漏翻，PR #3 的補譯值得對照。 |
| G06 | manifest／加入主畫面／standalone 顯示；index、manifest | 暫緩獨立 PWA 擴充 | 我方已有 browser fallback 與 Tauri；manifest 本身不代表 service worker、離線可寫或背景同步。 |
| G07 | ETag、局部刷新、不可用資料不覆寫草稿；app:84、2894 | 保留／借用局部更新 | 我方有 seq/checkpoint/namespace/event ACK 屏障；不能直接換成 Hub 的 15 秒 poll或忽略讀取失敗。 |

### H. 尚未合併 PR 的新增提案

這三個 PR 都不能視為 main 已交付。#4 自述基於 v4.68.2，尚未與 v4.90.0 完整整合；
#2 亦有自己的較早基底。評估功能設計，不接收整枝覆蓋我方或假稱其驗證已重跑。

| ID | 提案與固定 head | 決策 | 我方用途與邊界 |
| --- | --- | --- | --- |
| H01 | [#2][pr2] 原生 session picker：搜尋、200 筆提示、選取保留、preview；`session-links.js` | 改接唯讀 P2 | 可參考 discovery 的大量來源選取與明示範圍；不建立 Hub snapshot importer，不自行掃使用者 CLI history。 |
| H02 | #2 在原 ID／原 cwd 繼續人工 Codex/Claude session；`af9c4d824d772a5be7a4f299d01a14ecdde6179b` | 不採用 | 直接違反人工 BAT 資源唯讀；我方以固定 checkpoint 在新 managed 資源接續。 |
| H03 | #2 拖曳／鍵盤調整側欄、保存寬度、手機停用；`sidebar-resize.js` | 採用 P1 | 改接我方 sessions sidebar，沿用 tokens；保留主內容最小寬、focus、取消拖曳與鍵盤操作。 |
| H04 | #2 限定資料夾存取與只阻擋相關工作之退出 | 保留邊界，借用說明 | 我方已有 resource confinement／Fleet ownership；不以全主機有 AI 就擋 client 退出，也不擴大資料夾權限。 |
| H05 | [#3][pr3] Windows／平台用語、繁中漏字補齊；`318b29c995f2e342aadfcaaf768e51af83b9a542` | 採用平台語意 P1 | 我方 Windows/Mac native 已具備；檢查 Cmd/Ctrl、Finder/Explorer、unsupported 原因，不搬 Hub 的 browser-based runtime。 |
| H06 | [#4][pr4] Skill 來源、重新掃描、專案勾選、遺失／相容性；`skills.js` | 改接 P2 | Skill 應由指定 host/workspace 的中央目錄供選取，固定版本/digest 與限制；不信任 client 本機路徑，也不保證只在 prompt 提醒就已套用。 |
| H07 | #4 工作資料位置 copy/empty、保留原檔與重啟；`1d88eeda4786f704b20f93e8873a8a6454c238aa` | 暫緩搬家，採用位置說明 | 顯示本機資料與遠端 workspace 的差別；使用者已排除直接跨主機搬工作目錄，不把此設定當同步。 |
| H08 | #4 safe URL、Windows 名稱、請求來源檢查 | 保留／作防禦案例 | 我方已有 CSP、固定 origin/native route、路徑／artifact confinement；新增閱讀器／複製／連結時納入 regressions，不以這份 PR 當完整安全審查。 |

## 來源覆蓋與後續驗收

| 上游入口 | 本次評估範圍 |
| --- | --- |
| [app.js][u-app] | A01–A12、B01–B10、C01–C15、D01–D09、E04/E07、F01–F14、G07；包含表單、事件、排隊、設定與背景刷新 |
| [project-order.js][u-order]、[hierarchy.js][u-hierarchy] | A02–A05、D06；父子／衍生／孤立／循環、排序、menu、drag |
| [chat-scroll.js][u-scroll]、[mobile.js][u-mobile] | C04、G01/G02；訊息跟隨、mobile drawer/composer、可視 viewport |
| [model-order.js][u-model]、[usage.js][u-usage] | B02、F02–F08；候選順序、帳號／來源／過期與額度顯示 |
| [onboarding.js][u-onboarding]、[app-update.js][u-update] | F09–F11；初始導引、失敗／稍後／忙碌、更新狀態與原始碼自改方案 |
| [github.js][u-github] | D03/D04；owner、preview、private、push 另選、partial result |
| [task-transfer.js][u-transfer]、[task-integrate.js][u-integrate] | D06/D08；成果說明、順序、衝突、缺漏、已完成與恢復 |
| [remove.js][u-remove]、[maintenance.js][u-maintenance] | E01–E06；候選、外部／共用資料、preview 失效、恢復與檢查 |
| [locale.js][u-locale]、[app.css][u-css]、[index.html][u-index]、[manifest.json][u-manifest] | G01–G07；語系、tokens、版面配置、鍵盤、主畫面入口及靜態資源 |

採用前的共同要求：維持中央 ActionDef/OperationService、固定身份與原 request/key、
manual/managed/unknown、變更版本及最後送出前檢查；兩語、browser/native、
390/768/1440、失敗/重連/換帳號、草稿/焦點/捲動與安全文字顯示各自驗證。
新的 code reuse 須記上游 SHA、來源檔、改接處與 MIT notices；本次只新增評估文件，沒有複製 runtime code。

本地證據目錄：`~/agent-work/artifacts/project-hub-frontend-audit-20261009/`。
內含固定 PR metadata、原始碼檔案雜湊／入口清單、隔離 rendering harness、26 張截圖、
`ui-inspection.json` 及 52 項測試 log。初次 rendering harness 曾把手機收起的 composer 當成必須可見、
且少填 settings fixture 欄位；修正的是展示 fixture，沒有修改上游產品來取得結果。
這份審查沒有將未合併 PR、測試替身或截圖視為 live/native acceptance。

[upstream]: https://github.com/kieiken/project-hub/tree/a277d2ed5ce439c248fc32fa8ff9fa4124a06027
[pr2]: https://github.com/kieiken/project-hub/pull/2
[pr3]: https://github.com/kieiken/project-hub/pull/3
[pr4]: https://github.com/kieiken/project-hub/pull/4
[u-app]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/app.js
[u-order]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/project-order.js
[u-hierarchy]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/hierarchy.js
[u-scroll]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/chat-scroll.js
[u-mobile]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/mobile.js
[u-model]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/model-order.js
[u-usage]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/usage.js
[u-onboarding]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/onboarding.js
[u-update]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/app-update.js
[u-github]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/github.js
[u-transfer]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/task-transfer.js
[u-integrate]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/task-integrate.js
[u-remove]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/remove.js
[u-maintenance]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/maintenance.js
[u-locale]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/locale.js
[u-css]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/app.css
[u-index]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/index.html
[u-manifest]: https://github.com/kieiken/project-hub/blob/a277d2ed5ce439c248fc32fa8ff9fa4124a06027/hub/public/manifest.json
