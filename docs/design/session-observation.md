# 中央 session 對話與等待

依 [共同產品決策](../product/realignment-v2.md) D02／agent principal 邊界與 Tauri
計畫 §20，標準 MCP agent 必須能以自己的 observe 身分讀取送出後的對話。
這是既有唯讀 service 的中央 adapter，不是 operation、排程或另一份 event journal。

## 接口與語意

- RPC／MCP `session_read(host, session_id, last_n=20, offset=0,
  include_tools=false, max_chars=12000, after=null)`；HTTP 沿用
  `GET /api/v1/sessions/{host}/{id}/messages`。
- RPC／MCP `session_wait(host, session_id, until="attention", timeout_s=120,
  require_new=false, after=null)`；HTTP 新增相同 session 的 `/wait`。
- CLI `read`／`wait` 與兩種 MCP profile 均走中央，需要自己的 `BATC_API_TOKEN`。
  缺 token／daemon 時拒絕，不讀本機 admin token、不自行啟 daemon、不用本機 Fleet 旁路。
  `--read-only` 仍可使用這兩個工具；中央要求 observe，不要求 managed 或 write scope。
- 沿用唯一 prefix（至少六字元）解析，單次 wait 固定完整 session ID。人工與 unknown
  可觀察，不能由此取得 mutation authority；原 Claude 缺 cwd 的 state 安全判斷保留。
- 原 service 的 messages、next_offset、size truncation、pending、turn_started／done／
  attribution／phase 原樣回傳。Claude echo correlation 與 queued boundary 不降級；
  Codex timestamp fallback 不提升為確定歸屬。`idle`／event／無 tab 不是 task 完成證據。

所有型別、必要字串、有限數字、boolean 與 allowed fields 在建立 readonly Fleet 或 BAT frame
前檢查。read 最多 100 messages、60000 characters；offset 最多 1000000，after 最多 512
characters。沿用 read 的數值 clamp（last_n 至少 1，max_chars 至少 500），offset 不可負。
`max_message_chars` 預設 2000，可指定 100–60000；仍受整體 max_chars 上限限制。
wait 保留 1–1800 秒 clamp（預設 120），until 為 attention／turn-end／ask-user。
HTTP 拒絕重複／未知 query keys；RPC 拒絕未知欄位或 caller 提供 transport／principal。

## Deadline、資源與身分

每次受理擁有獨立 `Fleet(read_only=True, idle_timeout=0)`；只使用中央 host config。
其 lifetime 不依賴 inventory 每輪 refresh 的 close，取消也不 close coordinator／inventory。
同時最多 32 requests、每 actor 4、每 host 8，超額立即 429 `OBSERVATION_BUSY`，沒有排隊。
read wall deadline 30 秒；wait wall deadline 為 timeout_s + 30 秒，包含連線／初始觀察。
RPC client socket timeout 另外加 5 秒。wall deadline 到期回 504 `OBSERVATION_TIMEOUT`；
正常等待期限則保留 service 的 `status=timeout`，不假稱未啟動或已完成。

HTTP／RPC 在等待期間監看 client EOF，並每 10 秒重新驗證原 token；回傳資料前再驗一次。
revoked／expired／actor 或 scopes 改變回 `FORBIDDEN`，不回舊觀察結果。
EOF／caller cancellation／deadline 均取消自己的 reader coroutine、解除 subscription、close
自己的 Fleet 並釋放 counts。觀察不新增 operation／command，不永久複製 transcript。
另以冪等 metadata 表記錄[對話閱讀](session-reading.md)的原 message ID／revision；觀察不會
標記已讀。index 掃描也受同一 wall deadline 與 archive raw budget 限制。

## 驗證與尚未涵蓋

MockBat＋actual HTTP/RPC/MCP/CLI 覆蓋 scope／missing-token、malformed 零 frame、manual
read、prefix、pagination／after correlation、event filtering、長 timeout transport、超額拒絕、
token revoke、disconnect／cancel／deadline cleanup，及 inventory close 不干擾自己的 wait。
現有 service／turn-marker regressions 沿用。沒有 live BAT 或 installed agent 驗收宣稱。
對話不是跨頁 atomic snapshot，BAT reconnect 期間可能漏 event；原 polling／readback 規則仍適用。
其他 operator-only read tools 不在本次遷移；不能把它們列為 principal profile 已支援工具。
