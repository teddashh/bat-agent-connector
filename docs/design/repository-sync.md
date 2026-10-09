# 從已發佈版本建立工作

依[產品負責人的 host／repository 澄清](../product/realignment-v2.md#原始需求與後續澄清)及
[成果 Part C](artifacts.md#主機與-repository-同步part-c依產品負責人澄清)，跨主機程式碼來自明確綁定的
GitHub repository。這不是搬移 workspace，也不採用未發布的 Git pack／bundle。

## 明確綁定與操作

既有 `github.repos` 是 repository 設定權威。每個 repository 可額外設定：

```toml
[[github.repos]]
repository = "example/project"
sync = { remote_url = "git@github.com:example/project.git", bindings = [{ host = "worker", workspace_id = "exact-workspace-id" }] }
```

同一 host／workspace ID 只能綁定一個 repository。`sync` 不授予 integration push 權限；未設定時
不提供本功能。workspace 名稱、路徑相同、`task_service.repo_urls`、既有 clone 的 origin 都不是綁定。
主機需 write／orchestrate、managed root、SSH Git runner 及現有 confinement readiness。
`remote_url` 沿用 repository URL 驗證，不接受 token、任意本機路徑或呼叫者 URL；本機 bare repository
只在 loopback mock GitHub fixture 允許。

唯讀 preview 需要 `observe`，指定 repository、host、精確 workspace ID、`refs/heads/…`。
回傳 provider repository numeric ID、ref 的完整 40-hex head SHA、綁定 digest、workspace ID／folder。
preview 不建立 clone、session 或 operation；不是永久授權。

`repository.continue` 需要 `start`：

```json
{"action":"repository.continue","target":{"repository":"example/project","host":"worker","workspace_id":"exact-workspace-id"},
 "params":{"source_ref":"refs/heads/main","source_sha":"<40 hex>","agent":"claude","prompt":"<instructions>"},
 "preconditions":{"repository_id":123,"binding_digest":"<64 hex>"},"idempotency_key":"<original key>"}
```

本切片只接受已檢視 ref 的**精確 head**，不提供 ancestor／tag／PR fork 選擇。首次 fetch 前 ref 前進
即停止，永不把選定 SHA 換成 latest。已成功 fetch／固定的 receipt 優先於之後移動的 ref；重播不要求
原 head 永遠停在遠端。repository numeric ID、原 ref／head、remote URL、host profile、workspace ID／folder、
managed root、設定 digest 存在同一 operation 的固定來源 receipt，不另建工作佇列。

## 效果、回復與邊界

1. `source.resolve`：唯讀確認 GitHub repository numeric ID／名稱、ref SHA、workspace 身分、設定與 preview
   digest。具名 key 先回既有 operation；不同 payload 同 key 拒絕。CLI 省略 key 時每次產生新 key 並回傳；
   MCP／HTTP 明確要求 key，不能用預覽內容自動去重。
2. `repository.fetch`：在 managed root 內建立本 operation 自有尚未 checkout 的 clone，核對 marker、無符號／硬連結、
   無 alternates／replace／危險 Git 設定，使用設定的 host Git 憑證 fetch 固定 SHA。GitHub 讀取證據與
   host `ls-remote` 的精確 ref／SHA 必須一致。物件驗證及 operation ref 固定成功後才能繼續。
   host directory flock 防止舊 SSH 程序與重啟後讀回同時寫，Git 子程序繼承 lock FD；丟失 reply
   只依固定 marker／ref／object 讀回或安全補完。
3. `worktree.prepare`：只在自有 clone 加固定 operation branch／worktree。重試已有 carrier 需核對
   common Git directory、branch、HEAD、原 creation intent；不 reset、pull、checkout 已有 worktree。
4. 沿用中央 `verify.start`、`session.start`、`send` 的獨立 durable intents、claim／capacity、confinement
   與 receipt。每個未送出的 BAT frame 前重新驗證 host／workspace／設定與 ownership。回覆不明保留
   session ID／carrier／claims；沒有正向 readback 不再送 start 或 prompt。已完成 receipt 不因新政策而消失。
   reservation 的 created_at 在 transport 前寫入 operation；registry 遺失、重建、retire 或 task 接管
   不代表舊 start 沒送出，停止於明確 needs_attention，不重開或覆寫後繼者。
5. receipt-owned cleanup 投影保留原 operation／session／branch／path，沿用 reviewed cleanup 的全部
   writer、shared owner、command、content、retention／uncertain gates。不能因沒有 registry row 就取得管理權。

GitHub token 只在中央讀 API；不送到主機或放入 URL。Git 網路操作用主機既有憑證；本 action 沒有
GitHub write／push。checkout 的 hooks／filters／submodules 不執行。來源人工 checkout 不讀 index、
不改 HEAD／refs／worktree 註冊，不做 pull／reset／merge。原人工目錄的更新由使用者自行操作。

UI 文案是 **Start from a published version／從已發佈版本建立工作**。只能從 capabilities 的明確綁定
選擇目標，先檢視固定 repository／host／workspace／ref／SHA，再保存原 envelope／key。accepted 後
只讀原 operation；重啟、credential 切換或 generic error 不偷偷換 key。來源主機不會被接管或停止。

## 驗證與尚未涵蓋

測試使用臨時 Git、mock GitHub／BAT：同名未綁定、錯 numeric ID／URL／ref、移動 head、workspace
重綁、caller scopes、manual snapshot 不變、惡意 clone 設定／連結、fetch/start/send 斷線、重啟、
cancel、cleanup claim、capacity／confinement final-frame races、HTTP／RPC／MCP／CLI parity。
後端與 UI 分開提交；不以 fixture 宣稱 installed／live GitHub 或 host 驗收。

不含未發布跨主機搬運、任意 branch push、修改人工 checkout、task takeover、dirty snapshot、
LFS／submodule 展開、Git 憑證安裝、ancestor／tag 選擇。發布既有成果仍走原 integration／PR 流程，
本功能只消費明確已發佈版本。
