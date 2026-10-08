# Artifacts：附件版本與跨主機接續

日期：2026-10-08。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §08 Artifact、§12 第 3–5 步、§13、§28「03 managed execution」，工作包 W05b。主要驗收是 B04 與 A03 的附件部分；保留事實供 §23 整理工作包使用。

這是 Phase 1 規格，尚未提供 artifact API 或上傳功能。本次只提交本文件。以下新增欄位、actions、routes、測試與設定都是 Phase 2 合約，不描述成已完成的能力。

## 固定來源版本

| 來源 | 固定版本與核對位置 |
|---|---|
| Connector | `5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`，`feat/artifacts` 的起點；Python 套件版本 `0.2.4` |
| 既有規格 | [checkpoints.md](checkpoints.md)、[work-items.md](work-items.md)、[api-v1.md](api-v1.md)、[resource-policy.md](resource-policy.md)、[delivery.md](delivery.md)、[交接紀錄](../handoff/2026-10-08.md)、[CONTRIBUTING.md](../../CONTRIBUTING.md) |
| BAT | 計畫 §03 的 `b7419892fbc9946799b64cca24c2ec8c7fa15c42`；[remote_server.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/remote_server.rs)、[commands/worktree.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/worktree.rs)、[commands/git.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/git.rs) |

已讀上述固定 BAT 原始碼。`remote_server.rs` 的 `worktree:create` 接收 `sessionId`、`cwd`、`installPnpm`，沒有起點 commit 參數；`fs:upload-tmp-begin` 與 `fs:upload-begin-dir` 存在，但不是 Connector 已授權的 managed artifact 合約。`commands/git.rs::git_get_status_native` 使用一般 `git status`。人工來源仍使用 SSH 的 `git --no-optional-locks` 讀取。

[PROTOCOL.md](../PROTOCOL.md) 與 [ORCHESTRATE.md](../ORCHESTRATE.md) 的協定筆記另以 BAT v3.2.12 為基準，不把版本號等同上述 commit，也不宣稱所有配置主機已安裝相同版本。實際 host readiness 仍須檢查 BAT 能力。

本包不新增 BAT channel。`channels.py` 的 allowlist 保持原樣，包括拒絕 `fs:readFile`、`fs:upload-tmp-begin` 等未開放入口；不使用 PTY 或 agent shell 搬檔。若日後改採 BAT 檔案 channel，須另提規格，依 CONTRIBUTING 證明來源、分類及 tier 拒絕測試。

## 現有與新增行為差異

| 核對的現況 | 本規格新增 |
|---|---|
| `checkpoints._run_create` 保存 commit、固定摘錄與 hash；`checkpoints`／`checkpoint_runs` 沒有附件 | 建立 checkpoint 時凍結 artifact revisions；接續另保存本次完整輸入 manifest |
| `_admit_continue`、`_run_continue` 固定使用 `cp["host"]` 與來源 workspace | 可選已配置的目標 host／workspace；先取得同一 commit 與附件，再派工 |
| `start_in_worktree` 有 `verify.start`、`session.start`、`send`，派工回查使用穩定 ID | 加入附件 readiness 與送出前的讀回；沿用同一預留 session、operation 與 message ID |
| `work_items.LINK_KINDS` 只有 session、checkpoint、operation、task、pull_request；`fingerprint` 不含附件 | 附件成為工作內容的版本化欄位，納入完成確認指紋；不拿路徑字串當 artifact 身分 |
| `task_journal._context_refs` 的 `attachments` 是最多 20 個參考字串，沒有傳輸或驗證 | 舊字串仍是歷史文字，不推測成本機檔案，不表示已 materialize；本包派工以結構化 artifact refs 為準 |
| `SshGitRunner` 共用 `[verification] ssh_hosts`；`check_checkpoint_worktree` 檢查固定 clone／worktree 名稱 | 同一 SSH alias 加受限 byte-transfer adapter；目的端 canonical path 與檔案種類在 host 上再次檢查 |
| `resource_policy.norm` 只正規化文字，不能證明沒有 symlink | 新 artifact 路徑檢查仍在共用 resource policy；adapter 執行主機端無 symlink 寫入，不以字串前綴代替 |
| `ApiV1._read_body` 只收 JSON，`MAX_BODY = 200_000` | metadata 繼續走 JSON；另收有界 byte stream，仍執行同一 `artifact.upload` operation |
| Dashboard 的送字欄有 localStorage 草稿；checkpoint 接續及工作編輯多為記憶體狀態 | 這兩個附件入口保存文字、Blob、精確版本與 operation key，成功後才清除該份草稿 |

起點沒有 `docs/design/cleanup.md` 或集中式 cleanup actions。保留契約見下節，供平行整理包接入；不另建 housekeeping loop。部署的 GitHub Actions artifact ID／digest／run／期限仍由 delivery package 記錄，不能用本 store 的 ID 互換。

## 權威資料、IDs 與不可變版本

所有 metadata 使用現有 `Journal` 的 SQLite 與事件游標，不建立第二份 tasks／executions 資料庫。檔案 bytes 在 Connector 自有 store；遠端 materialization 是可重建的副本。

| 紀錄 | 身分、欄位與限制 |
|---|---|
| `artifacts` | `artifact_id = art_<32 hex>`，新上傳由 operation ID 的 hex 衍生；保存建立者、時間與 `latest_revision`。ID 永不重用 |
| `artifact_revisions` | PK `(artifact_id, revision)`；revision 是正整數。保存 SHA-256（64 小寫 hex）、`size_bytes`、`media_type`、`display_name`、來源、擷取時間、建立 operation、storage key、狀態。bytes、digest、大小與來源完成後不可修改 |
| `artifact_uploads` | 以 upload operation ID 為 PK；保存預留 revision、expected digest／size、配額、目前 attempt、接收狀態。只有上傳控制資料，不存 base64／bytes |
| `artifact_references` | 穩定 `reference_id`、owner kind／ID、精確 revision、role、建立 operation、釋放時間與釋放回執。owner 可為工作項目、checkpoint、草稿、接續 operation、task command、shared 或 restore 流程；查詢實體需求時不能只數外鍵 |
| `continuation_inputs` | PK 為 `checkpoint.continue` operation ID；不可變 manifest，含 checkpoint commit／manifest digest、目標 host／workspace、完整 artifact refs、來源前置指紋及 work item 內容指紋 |
| `continuation_input_confirmations` | 以確認 operation ID 去重；保存 parent operation、原 input manifest digest、新觀測的 source HEAD、actor、時間。只確認沿用原選擇，不替換 commit／附件／target |
| `artifact_materializations` | `mat_<32 hex>`；唯一鍵 `(artifact_id, revision, target_host, managed_path)`。保存來源 digest／size、clone 身分、建立 operation、狀態、generation／attempt、最後讀回與 tombstone |
| `artifact_acceptance_receipts` | 以接受 operation ID 去重，保存精確 revision／digest、來源 execution／session／commit、actor、時間、decision、驗收文字與可選 work item；receipt 不會被下一次 revision 覆蓋 |

新的 revision 在 journal 交易內預留，對既有 artifact 必帶 `expected_latest_revision`。同時更新者後到的回 `REVISION_CONFLICT`。失敗的預留號不重用，允許有缺號；`latest_revision` 只指向完成的版本。其他 upload 在該 artifact 尚有未釐清預留時回 `UPLOAD_IN_PROGRESS`。

相同 bytes 的重新上傳也可以是新 artifact 或新 revision，第一版不作內容去重。同一 actor／idempotency key／metadata 回同一 operation 與預留版本；相同 key 的名稱、大小、digest、目標或前置條件不同，沿用 `IDEMPOTENCY_CONFLICT`。對同一版本重送 content 仍以接收後的 digest 查證，不能只信 header。

`ArtifactRef` 的合約固定為 `{artifact_id, revision, digest}`。不得省略 revision 或送 `latest`；服務核對 digest 與 journal，再從 store 重算 hash。檔名與媒體類型只作資料展示，不能決定儲存路徑或觸發解壓縮／執行。

Manifest digest 使用 UTF-8 canonical JSON（排序 object keys、無多餘空白、保留 Unicode）再做 SHA-256。Checkpoint hash 輸入為 checkpoint ID、commit_sha、excerpt_sha256 與按 `(artifact_id, revision)` 排序的 refs；舊 checkpoint 對空集合計算同樣 digest。Continuation hash 另包含目標 host／workspace、完整 refs、instructions 的 SHA-256、agent、來源預覽指紋及可選 work item 指紋，所有欄位在 admission 凍結。

Revision 狀態為 `receiving`、`ready`、`unavailable`、`purged`。只有 `ready` 可新掛載或派工；遺失或 hash 不符標成 `unavailable`，不偷偷改寫原版本。修復 bytes 須由原 operation 的可證明接收結果恢復，或新增版本。`purged` 保留 metadata 與回執，不能讀回內容。

## Storage layout、limits 與設定

預設 root 是 `<journal 所在目錄>/artifacts`，可由 `BATC_TASK_SETTINGS` 的 `[artifacts] store_root` 指定獨立的 Connector 自有絕對路徑。不得指向人的 checkout、任意 client 路徑或既有 unknown 目錄。首次初始化亦先有 operation intent；以共用政策確認受配置的 Connector storage，核對 owner、模式、root marker 與每一層真實路徑。

```text
<store_root>/
  .batc-artifact-store                 # Connector store 身分；不是「資料夾名稱即授權」
  staging/<operation_id>/a0001/content.partial
  revisions/<artifact_id>/r00000001/content
  revisions/<artifact_id>/r00000001/manifest.json
```

Storage keys 由 validated ID／revision 生成，不由 display name 或使用者路徑拼接。目錄模式 `0700`；staging file `0600`，正式 bytes `0400`。manifest 只含不可變 metadata 與建立 operation，不含 token、alias 認證或原始 client 絕對路徑。SQLite 是查詢權威；manifest 協助檔案已完成但 journal ACK 遺失時讀回。寫完 bytes／manifest 後 fsync，原子發布 revision 目錄並 fsync parent，最後交易寫 `ready` 與事件。既有正式位置不得覆寫；相同 operation 的重跑要讀回證明。

| 設定 | 提議預設值 | 執行時限制 |
|---|---|---|
| `max_file_bytes` | 16 MiB（16,777,216 bytes） | 上傳及 capture 都檢查宣告值與實際接收值，超過立刻停止接收 |
| `max_selection_count` | 20 | 每次 checkpoint／工作項目附件集合及派工集合的上限 |
| `max_selection_bytes` | 64 MiB（67,108,864 bytes） | 加總選定 revision 的大小，去除重複 ref 後檢查 |
| `max_store_bytes` | 512 MiB（536,870,912 bytes） | 正式 bytes、所有 partial 與未釐清操作的配額一併計入，不靠過期刪檔騰空間 |
| `max_host_materialization_bytes` | 每 host 512 MiB（536,870,912 bytes） | 受控副本、partial 與傳輸預留一併計入；host 可用空間不足亦 blocked，不自動清其他路徑 |
| `max_uploads_per_actor`／`max_uploads_total` | 2／8 | 同時接收的資料串流；跨程序重啟由 journal 預留與既有單一 owner 去重 |
| `transfer_timeout_s`／`stream_idle_timeout_s` | 300／30 秒 | 逾時不表示遠端沒有完成；走 uncertain/read-back |
| `unreferenced_retention_days` | 7 | 最後實體需求釋放後，未掛載 bytes 的最低保留期 |
| `accepted_retention_days` | 30 | 成果接受且最後實體需求釋放後的最低保留期 |
| `materialization_retention_days` | 7 | 最後實體需求釋放後，遠端副本的最低保留期 |

以上是待審的初始部署值，不是既有設定。正整數驗證、上限及目前用量由 capabilities 回傳；設定降低不回收既有內容，只拒絕新預留。零 bytes 檔案可以上傳；media type 以有界 MIME 字串保存，未提供用 `application/octet-stream`。display name 最多 200 字元，移除路徑成分並拒絕控制字元。

配額在短 journal 交易內先預留，不跨網路持有 SQLite 交易。預留涵蓋接收 attempt 的最壞 bytes；發布以 rename 移動同一份內容，不複製。重試若留有 partial，另計新 attempt 配額，或在證明舊 attempt 已停止後交整理操作處理。ENOSPC／quota refusal 不自動刪原 revision 或草稿。

遠端配額由 materialization／attempt 紀錄預留，helper 再核對受控路徑的實際大小與磁碟空間；未釐清 bytes 仍占額度。只查受控 cache 與已記錄 paths，不遍歷主機其他磁碟。

Store 與 journal 須一起備份。只還原 journal 不能宣稱 bytes 已存在；啟動時讀回被引用版本，失聯／遺失內容明確顯示。備份是外部保留政策的一部分，本包不加排程備份程式。

## 輸入／輸出與入口

全部 mutation 註冊為 `ActionDef`，經現有 `OperationService.create`。HTTP、MCP 與 CLI 共用 handler、前置條件及逐項結果；操作身分來自 bearer token。MCP／CLI 寫入入口需要 `confirm=true`／`--confirm`；Dashboard 的一次主按鈕就是操作意圖，沿用現有 HTTP operation 合約，上傳 content 綁定已授權意圖，不再要求第二次確認。沿用既有 rate／audit 慣例；bytes、文字全文、認證與原始路徑不寫進 audit。資料流另受上表配額限流，重送同一成功操作不再算新寫入。

| Action | Scope | Target、params、preconditions | 成功結果 |
|---|---|---|---|
| `artifact.upload` | manage | 新 artifact 的 target 為 `{}`，新 revision 為 `{artifact_id}`；params：`display_name, media_type, size_bytes, expected_digest, draft_id?`；更新必帶 `expected_latest_revision` | `artifact_id, revision, digest, size_bytes, media_type, source, operation_id` |
| `artifact.capture` | manage | target：`{host, session_id}`；params：`source_relpath, expected_file_fingerprint, role=input|result, checkpoint_id?, execution_ref?, draft_id?`；來源 commit／路徑指紋必須與預覽相符 | 同上，加讀取證據及真實來源關係 |
| `artifact.materialize` | start | target：`{host}`；params：`checkpoint_id, continuation_operation_id, artifacts`；只能重用該接續 intent 的 clone 與 server 衍生目的地，拒絕任意 `path` | `materializations` 逐項 ID、revision、digest、size、managed path、狀態及證據；不開 session |
| `artifact.accept` | approve | target：`{artifact_id}`；params：`revision, decision=accepted|rejected, acceptance, work_item_id?`；pre：`expected_digest`，有工作項目時另需其內容指紋 | 精確版本的 acceptance receipt；不代表測試、merge 或部署完成 |
| `artifact.draft.bind` | manage | target：`{draft_id}`；params：`refs`；只能是同 actor 的 `drf_<32 hex>` 草稿，核對 ready revisions | 冪等增加 server draft references，回目前 manifest digest；選取既有 artifact 也要 bind |
| `artifact.draft.release` | manage | target：`{draft_id}`；params：`refs`；pre：`expected_draft_manifest_digest` | 只釋放同 actor 的該份 server draft references；不刪 bytes |
| `work_item.create`／`work_item.update`（擴充） | manage | `attachments: [{artifact_id, revision, digest, role=input|result}]`；update 仍帶 `expected_version` | 完整內容與新 version／completion fingerprint |
| `checkpoint.create`（擴充） | operate | `artifacts: [ArtifactRef]`；和 commit／excerpt 一次凍結 | `checkpoint_id, artifacts, artifact_manifest_digest` |
| `checkpoint.continue`（擴充） | start | `checkpoint_id` target；params：既有 `instructions, agent`，加 `target_host?, target_workspace?, artifacts?, work_item_id?`；pre：`expected_checkpoint_manifest_digest, expected_source_head_sha`，有工作項目時另帶 `expected_work_item_fingerprint` | 既有結果，加固定 `input_manifest_digest`、materializations、來源／目標 host；session 仍 confined |
| `checkpoint.continue.revalidate` | start | target：`{operation_id}` 指原 parent；params：`observed_source_head_sha`；pre：`expected_input_manifest_digest`。只適用 SOURCE_MOVED 且已證明未送第一個指令的 parent，核對已預留 session binding | 保存 confirmation receipt、resume 同一 parent；沿用原 refs、worktree、session／message ID |

`artifact.materialize` 是補齊已保存接續意圖的入口，與 parent 共用 materialization records／lock；不另產生 execution。parent 在派工前仍要讀回。不讓 MCP／CLI 任意挑一個 managed root 下的檔案覆寫。`artifact.capture` 不能以 client path 開啟 Connector 主機上的檔案。

`artifact.accept` 只接受 `source.kind=managed_result` 或明確標示人工來源的成果。輸出 lineage 必須可讀回，不能接受任意自報 execution。對同一版本的另一個接受決定另建 receipt，保留前一筆歷史；`rejected` 不釋放未接收成果保留需求。工作項目的「確認完成」與逐 artifact 接受分開保存。

| HTTP（皆 `/api/v1`） | MCP | CLI |
|---|---|---|
| `POST /artifacts`：JSON metadata，薄轉接 `artifact.upload`，回 202 與 operation／預留版本／`content_url` | `artifact_upload`：metadata 與 `content_base64`；薄 client 解碼後傳同一上傳流程，不接受 host-local path | `batc artifact upload FILE [--artifact-id ID --expected-revision N] --confirm`；FILE 只在 CLI 所在 client 讀取 |
| `POST /artifacts/uploads/{op}/content`：`application/octet-stream`，固定 Content-Length，綁到上列同一 operation | 上傳工具先保存 key／operation，逾時回該 operation；不重建 | 與 HTTP 相同；key／operation 可指定或輸出供恢復 |
| `GET /artifacts?limit=&cursor=`、`GET /artifacts/{art}/revisions/{revision}` | `artifacts_list`、`artifact_get` | `batc artifact list|show` |
| `GET /artifacts/{art}/revisions/{revision}/content`：observe；attachment download、nosniff、no-store；沒有 inline HTML preview | `artifact_get` 回 metadata，不把大型內容塞進工具結果 | `batc artifact download ID --revision N --output FILE`；只在 client 寫 FILE |
| `GET /artifact-materializations?artifact_id=&revision=&host=&limit=&cursor=`、`GET /artifact-materializations/{mat}` | `artifact_materializations_list`、`artifact_materialization_get` | `batc artifact materializations` |
| `GET /sessions/{host}/{sid}/artifact-preview?path=`：observe，path 是有界相對路徑；唯讀取得 file 指紋 | `artifact_capture_preview` | `batc artifact capture-preview` |
| `POST /operations`：capture／materialize／accept／draft.bind／draft.release、revalidate 及既有擴充 actions | `artifact_capture`、`artifact_materialize`、`artifact_accept`；draft／revalidate 用 operation_submit，需要 confirm | `batc artifact capture|materialize|accept|draft-bind|draft-release`，`batc checkpoint revalidate`；新增薄命令，既有 `batc op ID --resume` 沿用 |

列表限制 1–200，預設 50，游標以時間加穩定 ID 排序。GET 一律 observe；mutation scope 以 action 為準。metadata 回傳 `content_available`、來源、引用、retention facts 與 stale 時間，不洩漏 store 的內部絕對路徑。

`content` route 是原 `artifact.upload` 的 payload adapter，不是另一個 mutation action。認證、Origin／Host、operation actor、manage scope、revision 預留及宣告長度檢查完成後，handler 先提交 `upload.receive.<attempt>` intent，才開啟 staging file。只允許原 actor 或 admin 為該 operation 供給 bytes，不接受改 metadata。

需在 `ApiV1.handle` 中於 `_read_body` 之前分流此固定 route；只對它採串流，保留其他 JSON 的 200,000 bytes 限制。第一版拒絕 chunked transfer、Content-Length 矛盾與未知 content type；有界區塊讀取、累計實際 bytes／hash。MCP base64 亦先限制 encoded／decoded 大小；不把 base64 放進 `operations.params`、event 或 audit。generic operation_submit 可預留上傳，必須補 content 才成功。

## 上傳步驟與 read-back

Operation worker 與 payload adapter 共用服務內的單一 operation 執行鎖；adapter 只供給 authenticated stream，不自己直接寫檔。新 operation 初期 `waiting_external`，reason 為等待 content；stream 綁入後由同一 handler 執行。重啟後沒有 stream 就繼續等待，已有完成內容先讀回，不向 browser 猜測本機檔案位置。

| Step | 意圖及副作用 | 回應遺失／重啟的讀回 |
|---|---|---|
| `upload.reserve` | 同一 journal 交易預留 ID、revision、配額及可選 draft reference | 用 operation ID 找既有列，不配置第二個版本 |
| `upload.receive.<attempt>` | intent 包含固定 staging key、expected size／digest；寫 bytes，不改來源 | 讀正式 manifest 或 staging 實際 bytes／hash；完整相符可補記，partial 不可發布 |
| `upload.publish` | 主機本地再檢查無 symlink、fsync、無覆寫發布，寫正式 manifest | 正式目錄的 artifact／revision／operation／hash 必須全部相符；相符即補記，不再 rename |
| `upload.record` | journal 交易寫 ready、來源、refs、quota 轉換、api_event | 以建立 operation 去重；檔案已發布但列尚未 ready 時補記 |

Confirmed incomplete receive 以結果記下實際長度並停在 `needs_attention/UPLOAD_INCOMPLETE`，不把該 step 記成不可重試的 `failed`。重新供給同一 upload operation 時先 resume，建立下一個 attempt；從第 0 byte 重送，第一版沒有部分續傳。partial 留下的 retention facts 交整理包處理，不直接 unlink。

Connection ACK 遺失但接收結果尚不能確認時是 `uncertain`；沒有證據不開第二個 writer。不同內容即使同長度也不能完成這個預留。上傳已成功而 HTTP 回應遺失時，GET 原 operation 取回同一 revision，content route 不再寫檔。

## 人工來源檔案與成果擷取（A03）

Capture 的 file preview 由 session 的已觀測 cwd／repo root 綁定，來源分類使用既有 registry／inventory。source_relpath 必須是指向該來源 repo 的相對檔案，拒絕絕對路徑、`..`、NUL／控制字元、`.git` 及 symlink；不遞迴找檔、不 glob、不接 browser 自報 host-local 絕對路徑。

主機 reader 只執行固定的 stat／open-read／hash 程式；以 no-follow dirfd 逐層開啟，限 regular file，拒絕 directory、device、FIFO、socket 及多重 hardlink。preview fingerprint 含 resolved root、相對路徑、device／inode、大小、mtime／ctime、digest、觀測 commit。擷取前核對，讀取後重算 fingerprint；大小與前後 hash 不符回 `SOURCE_MOVED`。檢查無法證實時拒絕，不把檔案當成已擷取。

`source.read.<attempt>` intent 先保存選擇與預期指紋，再由受限 reader 將 bytes 送回 Connector staging。其他發布步驟與 upload 共用。從 manual／unknown 來源讀取不授予 session 寫入權；不送 start／resume／send，不 stash、commit、checkout、chmod、rename、unlink 或寫 refs／index。讀檔可能產生作業系統的 access-time 更新，不以讀後 utime「還原」，測試的檔案不變指 bytes 與未由 Connector 改寫的內容／權限。

完成 artifact 保存 `source.kind=manual_file`、來源 host／session、repo root／相對路徑、觀測 commit、fingerprint、擷取時間與 digest。來源 path 是 provenance，只在授權 metadata 中展示。接續使用 store 的 bytes，不回頭讀人的檔案；來源後來修改或刪除也不改已選定 revision。

這是選定單檔的不可變 continuation data，不是完整 dirty worktree snapshot；不把檔案自動覆寫到 target repo 同名位置。`checkpoint.preview.snapshot.supported` 仍是 false，能力須明確說明 tracked diff／untracked 全量套用尚未提供。

`source.kind=managed_result` 額外記 `execution_ref`（既有 checkpoint run 的 operation ID，或 Task Service task／command ID）、host／session、實際 commit 與 bytes hash。服務驗證 registry／journal 的來源關係並讀回 commit，擷取前後 commit 不同也拒絕。建立結果 artifact 不要求 session 停止，但檔案變動不得被當成固定成果。一般 client upload 不可信自報 managed lineage；其 source.kind 仍是 upload。capture 的 role=result 與工作項目掛上的 result 都建立 RESULT_UNACCEPTED holder，即使尚未掛到項目也保存，直到有接受或明確處置回執。

## 附件關聯與凍結輸入

工作項目附件與 `work_item.update`、`management_applied` 在同一交易寫入，使用 expected_version。集合排序以 `(role, artifact_id, revision)` 固定；同 ref 不重複，digest 必須符合 ready revision。替換附件集合亦保留被移除的引用歷史及釋放回執，不刪 bytes。

`work_items.fingerprint` 加入附件的 role／ID／revision／digest。接受後換 revision 或新增結果會使指紋不同，重新待確認。Migration 不讓舊完成項目突然失效：沒有附件的項目仍使用既有指紋算法；有附件才加入附件欄位。`work_item.approve` 仍只保存工作完成事實，不自動產生 artifact.accept receipt。

Checkpoint 在 create 時一次保存 commit、excerpt 及 artifact refs／manifest digest；不可事後替換其附件。舊 checkpoint 的集合為空。現有 checkpoint 接續表單新上傳的附件，掛在新 continuation_inputs，與原 checkpoint manifest 一起可追蹤；不改寫舊 checkpoint。需要將新附件長期放進 checkpoint 時建立新的 checkpoint。

`checkpoint.continue` admission 凍結完整集合：params.artifacts 存在時即為本次明確選擇的完整集合；未提供時沿用 checkpoint 的集合。Dashboard 從工作項目派工時展示 checkpoint 與工作項目附件的合併去重清單，再送完整 refs，不讓 server 在執行時偷偷讀 latest。

選定 work item 時服務檢查 manage scope（連回操作的管理權），帶 expected_work_item_fingerprint；連結與 continuation_inputs 在保存接續 intent 的同一交易內建立。避免現有 `continueFrom` 的「已派工，work_item.link 卻失敗」裂縫；重啟亦能從 operation.external_refs 找到尚未寫 checkpoint_runs 的執行。

## 受限 host adapter 與目的端政策

Phase 2 新增 `artifact_host.py`，對外只提供 capture、receive、verify 等具名方法，不能讓 action params 提供 script、command、argv、SSH hostname、port 或任意檔案目的地。沿用 `[verification] ssh_hosts` 的已配置 alias 與 host 身分；不用另一份 SSH 路由或認證資料。

選用固定 SSH helper，以 stdin 傳 raw bytes、stdout 傳有界 JSON receipt。這和受控 SFTP/scp 同屬 §13 的 host adapter；不啟動 agent shell。helper 是 Connector 版本化的固定程式，參數以資料傳入，不拼接使用者 shell。可重用 `SshGitRunner` 的 host routing 與錯誤慣例，但不能把其任意 script 方法公開成 artifact API。

必要 host readiness：已配置 alias、BatchMode、受信 known_hosts（StrictHostKeyChecking=yes，不自動加新 key）、writes 與 orchestrate tiers、managed_roots、可用 Python 3.10+ helper 環境、flock／等效可靠鎖、atomic rename 與 no-follow dirfd。缺一項即 capability blocked。probe 只讀；不藉 readiness 安裝套件、建人的目錄或重啟 BAT。

目的路徑固定為：

```text
<connector clone>/.batc-artifacts/<artifact_id>/r00000001/<digest>/content
```

不放在 worktree 裡以免把附件算成未提交程式；prompt 給 target host 上這個已驗證路徑，包含顯示名稱與精確 ref。cache 不是來源真本。Session 能否讀 clone 旁的附件亦屬 host readiness；不能讀時回 capability blocked，不降低 sandbox 或改往人的目錄放檔。

每次 host mutation 都先經 `resource_policy`：clone／worktree 用 `check_checkpoint_worktree`，新增 `artifact.storage`、`artifact.materialize` 的 `MUTATIONS` 列與共用 artifact destination check。新的 destination check 是現有政策的擴充，不是 adapter 自訂的 ownership 授權。

| 寫入前／發布前檢查 | 拒絕時行為 |
|---|---|
| managed root 是配置的絕對實體目錄；clone 有建立 intent 與 `batc.managed-clone`／來源 marker，且正好是核准路徑 | manual／unknown 永久唯讀；資料夾存在但不是 Connector 的不接管 |
| 原始 params 不接受目的 path；生成的每一段只來自 validated ID／revision／digest；檢查原始路徑分量再正規化 | 擋 `..`、絕對覆寫、相似前綴、NUL、shell metachar 路徑注入；不能只呼叫 norm 後檢查 |
| 在 host 逐層 lstat／dirfd no-follow；root、clone、cache、tmp、final 任一 symlink 都拒絕；root／clone marker 與 canonical path 再核對 | 不跟隨到人的 cwd，測試也須證明沒有外部檔案被開啟寫入 |
| cache 目錄由 Connector 建立、限制寫入者；正式／partial 只接受 regular file，拒絕 hardlink count > 1；不沿用 unknown 既有 cache | 不 chmod／清空／覆寫可疑檔案；回 DESTINATION_UNKNOWN／BINDING_MISMATCH |
| 鎖定 `(host, clone, materialization)`；以 O_EXCL／O_NOFOLLOW 建 deterministic attempt 暫存檔，傳輸完 fsync；發布使用無覆寫原子 primitive（例如 renameat2 的 RENAME_NOREPLACE） | SSH 斷線後鎖不明即 uncertain；禁止兩個 writer 或普通 scp 直接截斷 final |
| 既有 final 只有 marker、ref、digest／size 都相符才可沿用 | 不符標 blocked，不當成 cache miss 自動覆寫或 unlink |

Host helper 用 opened dirfd 完成後續操作，再核對實際 ancestry 與 path 身分，避免檢查後切換 symlink 的 race。規格要求整個寫入路徑都在受控 root 內，單次 `realpath` 加任意 scp 不符合。Host OS 若不支援此限制就不開寫入能力。

這保護 Connector 發出的傳輸。與 managed agent 相同 OS 帳號的外部程序仍可能改檔；cache 權限及 Connector 鎖不能宣稱阻擋該帳號所有寫入。要隔離這類 writer，使用不同的 storage 帳號／ACL。發現內容已改即拒絕派工，不以 prompt 自律替代檢查。

## Materialization 步驟、狀態與讀回（B04）

Parent admission 先持久化 selected refs、target host／workspace、固定 clone／worktree／branch、既有 UUID5 session ID、message ID，並在 journal 建立或重用各 materialization 列。輸入保持不變；per-item request 包含 ref、預期大小／digest、destination key、attempt，不能只記總操作成功。

重用副本時核對的是該 materialization 的建立 operation 與 ref，不要求建立者等於本次 parent；新 parent 另加使用 reference。經 cleanup 讀回 removed 後的重建沿用 materialization ID、增加 generation，保存舊 removal receipt，並重新跑完整傳輸／驗證。Step 名稱與 receipt 包含 generation，不能把刪除前的 succeeded step 當成本次 verified。

下表名稱省略 generation 前綴；實際使用 `artifact.<mat>.g<N>.<step>.<attempt>`。同一 host 的 store 配額鎖與 resource lock 有固定取得順序，cleanup／materialize 共用，避免去重後仍同時發布或移除。

| Step | 成功證據 | uncertain／重啟 read-back |
|---|---|---|
| `artifact.<mat>.source.verify` | Connector 正式 bytes 重算 digest／size；核對 immutable manifest | 可重讀；missing／hash 不符 blocked，保留已選定 ref |
| `artifact.<mat>.prepare.<attempt>` | 共用政策及 host helper 核對 root／clone／cache／lock，產生固定暫存 key | 讀 marker、path／lock 與 partial；另一個 writer 未停止時不重做 |
| `artifact.<mat>.transfer.<attempt>` | 串流接收，host receipt 有 mat／ref／attempt／bytes | 先查 final、partial 及鎖；complete 且相符可補記，confirmed partial 才記結果並允許新 attempt |
| `artifact.<mat>.verify.<attempt>` | host 自行從收到的 file 重算 SHA-256 與 size；不能用傳入 hash 當回應 | 可重讀；mismatch 是 blocked，不發布、不送指令 |
| `artifact.<mat>.publish.<attempt>` | host fsync、無覆寫原子發布 content／manifest | final 對應相同 ref／建立 operation／generation 且實際 hash 符合時補記成功，不再次寫入 |
| `artifact.<mat>.readback.<attempt>` | 另一次 host 讀取正式 content，回 canonical path、file 種類、digest、size、marker、observed_at | 只有這個讀回成功才能標 verified；rename ACK 本身不足 |

已確認的中斷或 mismatch 留逐項 evidence，以 `NeedsAttention` 停 parent；step 記回可證明的結果，再在 step 外判斷阻擋，避免 `OpContext.step` 的 failed replay 使恢復永遠卡在同一錯誤。恢復先 reconcile，再使用新 attempt 名稱；不清除原 step／receipt。不可證實遠端結果則保留 `uncertain`，沿用 OperationService 的有限次回查與 `UNCERTAIN_UNRESOLVED`。

| Materialization state | 意義 |
|---|---|
| `pending` | 已保存意圖，尚未開始 |
| `transferring` | 固定 attempt 正在接收 |
| `uncertain` | 遠端狀態／鎖尚無法證實，不能重寫 |
| `verified` | 正式位置的獨立讀回符合 revision 的 digest／size／path |
| `blocked` | 已證實的 size／digest／policy／來源問題；附 code 與下一步 |
| `removed` | 整理已讀回移除；保留 tombstone，原 revision 仍在 store |

Operation 的狀態仍使用既有 `STATES`；本包不增加 `blocked` operation enum。產品「blocked」對應 `needs_attention` 加穩定 error_code，或 admission 的明確拒絕。部分附件已 verified 時保持該結果；parent 無任何 first send，UI 列每一項的證據。

## 派工閘門與跨主機 continuation

Phase 2 預計包含跨主機取得已可 fetch 的 commit；不把現有 prepare_script 的 source 本機路徑直接放到另一台主機上讀。

跨主機需在受 0600 保護的 task settings 配置 `[[artifacts.repository_routes]]`：`source_host, source_repo_root, repository_key, remote_url, targets`，targets 明定允許的 `{host, workspace}`。`remote_url` 是受配置的 https／ssh repository，去除內嵌認證；來源 route 只作同一 repository 的映射，不授予 ownership。若已有 GitHub repo 的 `integrate.remote_url`，route 引用該配置，避免複製不一致 URL。沒有可證明映射時 blocked，不從 browser 接受 URL／任意 git transport。

同主機預設保留現有 host／workspace；跨主機必須選 route 的目標 workspace，不能複用來源的 workspace ID。Target readiness 檢查 writes、orchestrate、managed root、alias、BAT workspace／agent 能力與 confined runtime；人工來源 host 可以保持唯讀。沒有人工 source session 的 start／resume。

順序固定如下：

1. **Admission／凍結**：保存 continuation_inputs 與 `external_refs`，ref／manifest／work item 指紋必須符合畫面選擇。來源預覽讀到的 HEAD 以 `expected_source_head_sha` 保存；舊 client 同主機、無附件的呼叫保持原合約，其餘新功能要求新前置條件，不偷偷補 latest。
2. **`source.guard`**：唯讀核對來源 HEAD 與選定的 checkpoint manifest。擷取時來源正在改檔或預覽後 HEAD 前進，回 SOURCE_MOVED；不更換 checkpoint commit 或附件。來源無法觀測時顯示 blocked，不把 null 當相符。
3. **`commit.fetch`／`worktree.prepare`**：目的在 target 第一個 managed root，固定命名沿用 `clone_path`／checkpoint worktree 規則。跨主機的 clone 身分另保存 immutable source host／root／repository key，marker 不符不沿用。從 configured remote 在目標 clone fetch，證明 `cat-file <selected_sha>^{commit}` 存在；必要時抓取 remote advertised refs 到 managed clone 的私有 namespace，仍以原 SHA 查證，不選 branch 的最新 HEAD。禁止 local-path origin、任意 protocol／ext helper 或寫 source repo。建立 worktree 的 SHA 必須相符且乾淨。
4. **Artifact steps**：對每個選定 revision 執行上表；全部 verified 才能向下。不能用某一檔傳成功或 metadata receipt 代替完整集合。
5. **`verify.start`／`inputs.ready.<attempt>`**：BAT `git:getRoot`／`git:log` 查證新 worktree 的起點；另外讀回全體正式附件與 source guard，核對完整 manifest。記下 evidence，尚未啟動 session。
6. **`session.start`**：沿用 `start_in_worktree` 的 UUID5 預留、confined 選項、registry binding 與 lost-start reconcile。未確定先前 start 是否成功時不另開 session。
7. **送出前最後檢查**：沒有既有 send intent／結果時，再讀全體 artifact 的正式 hash／size／path、目標 worktree 起點與 source guard；保存 `inputs.dispatch.<attempt>`。有 session 但輸入被更動就 blocked，保留 session。成功後才產生 `send` intent；prompt 只把 target 的 verified materialization path 列為可讀附件，附 ref／digest；client 的 FILE 絕對路徑不傳入。歷史摘錄可能含人工路徑，仍只作背景。
8. **`send`／記錄**：沿用 message ID／prompt marker 的 turn／transcript 讀回，再保存 checkpoint_runs、materialization 使用關係與來源鏈。回應遺失先查 send；已證明指令接受後，不因 agent 已改 commit 或 cache 而重跑起點驗證、重送或另開 execution。

須調整 `start_in_worktree` 的內部步驟銜接，讓 artifact gate 能落在 start 前與 send 前；不能包在外面先 call 現有會立即 send 的 helper 再補驗證。沒有新增另一個 execution store；接續 execution 身分仍是既有 `checkpoint.continue` operation。

新的 send 與材料 gate 由同一 operation 執行鎖序列化；材料引用在 gate 至 send 的期間保持 active，cleanup 不能同時移除。已有 send step started／uncertain 時首先 reconcile 它，不能因目前 source 已前進就把已可能接受的 send 隱藏成「尚未派工」。

Gate 保存各 host 的實際 observed_at，不宣稱跨 host 讀回是原子 snapshot，也不鎖人的來源。它拒絕讀回時發現的變動；來源稍後的開發不改已凍結 bytes／SHA，送出後以固定 inputs 與真實 turn receipt 追蹤，不能再當作未送出而重派。

來源在等待期間前進的處理遵守 B04：本次預覽指紋過期則不送第一個指令，保留原 checkpoint／artifact 選擇。Dashboard 顯示新的 HEAD 及原選定 SHA；若人仍選舊 checkpoint，使用 checkpoint.continue.revalidate 保存「仍使用這些固定輸入」的 confirmation，resume 同一 parent，新的 source guard 核對 confirmation 的 HEAD。原 manifest／commit／refs／target 不改，沿用同一 session 與 message ID；不能用新的 key 作為重試捷徑。

Revalidate 先讀回 send 是否曾離開程序；已有 started／uncertain send 就只 reconcile，不接受 confirmation 或重新派工。確認只可補 source HEAD 的前置證據，不可繞過材料 hash、target 起點或 work item 內容已變的拒絕。每次 confirmation 有自己的 operation／receipt，新的 guard／dispatch attempt 使用新 step 名稱，不重播過期 gate。若要換 commit／附件／target，須先對帳並明確結束原執行，再由新的使用者意圖開工。

若原 SHA 只在人工來源本機、configured remote 取不到，回 `COMMIT_UNAVAILABLE`。保留工作、原 SHA、所有 bytes 與 drafts；不 clone target 上碰巧同名的本機路徑，不回退來源主目錄。跨 host 唯讀匯出未發布 commit 的 bundle 是明確 follow-up，見尚未涵蓋；本規格的跨 host 成功路徑限目標可從受配置 remote 取得同一 SHA。

## Dashboard 草稿與 operation 顯示

工作詳情與 checkpoint 接續表單共用附件 picker：選檔後先 upload，顯示名稱、大小、type、revision／digest；上傳完成才可保存附件集合或派工。工作詳情的保存掛到 work item；接續表單的上傳掛到 draft，提交後凍結到 continuation_inputs。Target picker 只列 capabilities 提供的 host／workspace 與具體阻擋原因。

Draft 以 `(connector endpoint, actor, form kind, work_item_id/checkpoint_id, draft_id)` 隔離。文字、agent／target、選定 refs、未完成 upload metadata、operation key／ID 及本機 File Blob 存 IndexedDB。已有 text localStorage 草稿需讀入遷移，不保存 client 絕對路徑或 token 在 draft。保存失敗時明示草稿未持久化，不把 picker 清空或顯示成功。

Upload 帶 draft_id 時 server 保存該 actor 的 draft reference；視窗關閉不會釋放。Blob 與文字在 upload 成功後仍保留，因為 upload 成功不等於使用者的工作提交成功。沒有 IndexedDB／容量不足時必須告知重開 browser 不保證未上傳 Blob，但已上傳 revision 及 server draft references 仍可找回；不能假稱可替 browser 自動重新選本機檔案。

挑選已存在 revision 亦透過 artifact.draft.bind 建立 hold，不能只存 browser ref 讓 cleanup 看不到。送出時凍結該 draft_id；等待期間的編輯產生新的 draft_id，先為新 generation bind 同樣 refs。舊 generation 仍等原提交成功或明確捨棄才釋放。Server draft manifest 是按 ID／revision 排序的 active refs hash；文字只在 browser，不建另一套工作資料。

只有 work item 保存 operation 或 checkpoint.continue **succeeded** 才清除該次提交的草稿。HTTP 202、upload ready、session 已啟動、partial／uncertain／blocked 都不清除。操作成功時只刪除提交時 digest 相同的 draft generation，人在等待期間輸入的新字與新附件留下。成功後以 `artifact.draft.release` 釋放該份 server draft ref；該 action 失敗只顯示保留中，重試不重新派工。

使用者明確移除草稿附件／捨棄草稿亦可 release refs，屬可追蹤管理修改，不刪 bytes。新開 Dashboard 找到未結束 upload／continuation 時查原 operation；既有 `keyFor` 遇 terminal 狀態會換 key，附件派工需保存已提交 key，不能對同一 failed 草稿自動換 key 重開 session。可恢復的 needs_attention 用 `/operations/{op}/resume`，來源前進時用上列 revalidate，uncertain 等回查。

Operation 頁列固定來源／目標 commit、manifest digest 與每個附件的 pending／transferring／verified／uncertain／blocked 狀態、驗證時間、實際 target path、error code／下一步。整組 ready 後才顯示開始派工；部分成功繼續顯示，不抹掉原版本或工作。

UI 沿用 `fill()`、`holdRender` 與有焦點／drawer 的 live update hold。文字全部有 en／zh-TW；CSS 不用 inline style attribute。手機 390 px 要能看附件與失敗原因，長 ID／path 可換行，不用水平大表格。MCP／CLI 相同結果不可把 local path 告訴遠端 agent「可直接讀取」。

## 成果與 retention facts（交給 cleanup）

Artifact source、工作完成、Git 整合、成果接受及 runtime 存活是不同事實。`integration_receipts` 的 delivered 只證明該 commit 成果已進 PR；除非回執明確包含本 artifact revision／digest，不推論附檔也已接收。Squash／ancestor、工作 done、視窗關閉或 host 離線都不釋放引用。

本包提供 `retention_facts(db, resource)` 讀模型，含 `resource_id, artifact_id, revision, materialization_id?, facts_version, observed_at, retain_until, holders, uncertainty`。holders 每項含 `owner_kind, owner_id, reference_id, reason_code, needs=bytes|materialization, release_receipt_id?`。facts 是來自管理列、operation／command 與回執的查詢投影，不是可任意勾選的另一份 ownership 資料。

| 活著的事實／reason code | Revision bytes | 目標 materialization |
|---|---|---|
| 未提交 server draft reference／`DRAFT_OPEN` | 保留，沒有以關視窗判定的期限 | 尚未產生就無需求；有正在執行的傳輸由 operation 保留 |
| 未完成 work item 的 input，或尚未接受的 result／`WORK_INPUT`、`RESULT_UNACCEPTED` | 保留精確 revision；拒絕成果也保留到明確處置 | 若工作／execution 仍需該 host path 則保留，只有可由 store 重建的需求可釋放副本 |
| 凍結 checkpoint 且仍列為可接續／`CHECKPOINT_CONTINUATION` | 保留 bytes；日後整理將它轉成 history-only 才可釋放 | 單有 checkpoint 不要求某台 host 的 cache 存在 |
| accepted／running／waiting／uncertain／needs_attention 的接續、upload、capture 或 task command／`OPERATION_ACTIVE`、`OUTCOME_UNCERTAIN` | 保留，包括失敗傳輸的原 selected refs；needs_attention 不表示可刪 | 保留該操作可能正使用的 path／partial／lock；cancel 須先 reconcile |
| session／execution 仍在使用、可能存活 writer 或 reader／`EXECUTION_ACTIVE` | 保留本次 input refs 與未接收 result | 保留實際使用的 host path；idle 或沒 tab 不算釋放 |
| shared 流程的 active ref／`SHARED_REFERENCE` | 所有 holder 都釋放前保留 | shared 流程指定需要實體 path 時保留 |
| restore 流程、復原保留回執／`RESTORE_REQUIRED` | 保留明確指定 revision | 需要該實體才保留；若 receipt 明確可由 store 重建，允許只移除副本 |
| 明確接受／取消／釋放後，最低期限仍未到／`RETENTION_WINDOW` | 至 retain_until | 至各副本的 retain_until |
| 純歷史 reference、已釋放 input、已保存接受回執／`HISTORY_ONLY` | 本身不阻擋，仍核對其他 holder／期限 | 本身不阻擋；保留 metadata／tombstone |

Active reference 一律沒有 TTL 自動到期；retain_until 是**最後實體 holder 有釋放回執之後**才開始計算的最低期限。未掛載 upload 自成功時間起算；server draft hold 優先於此期限。無法確定 holder 已釋放或 bytes 是否有別處完整備份時保守保留並列 uncertainty，不用「查不到」代表無需求。

工作項目封存不釋放 bytes。完成並接受且有保存回執時，整理包才可把不再需要內容的 reference 降為 HISTORY_ONLY。完成後仍有 shared／restore／unaccepted holder 會繼續擋清理；checkpoint 提供內容接續時一直是實體 holder，不能只因 metadata 是歷史就刪 bytes。

Artifact store 不執行 delete、TTL sweeper 或 cleanup.apply；本包也不新增 artifact.delete action。整理包決定候選、丟棄／保留政策、逐項 removal receipt／tombstone。它在 preview 與 apply 各讀一次 facts_version 與即時 holders，持有與 materialize 相同的 resource lock 再移除。新增引用與 cleanup claim 在同一 journal 協調，刪除中的內容不能新掛載；任一 active holder 或 uncertain mutation 出現就停止。

刪除 managed materialization 僅移除受控副本；不碰 Connector 原 revision，也不碰人工 source file／HEAD／refs。重建以 store 的原 bytes 再 materialize，讀回前不宣稱已 restored。原 bytes 已按政策釋放並清除時 metadata 顯示 unavailable／purged，不能承諾復原。若 cleanup 包尚未可用，所有內容保留，容量滿則拒絕新上傳。

## 失敗與恢復代碼

Admission 的拒絕使用表中 HTTP status；已有 operation 的失敗則回 operation.error_code／逐項 code。`uncertain` 不宣稱已無副作用。所有失敗保持工作項目、原 checkpoint、選定 revisions 與草稿。

| Code | HTTP／operation | 恢復 |
|---|---|---|
| `INVALID_ARTIFACT_REF`／`ARTIFACT_NOT_FOUND` | 422／404 | 重新選定合法精確版本；不補 latest |
| `ARTIFACT_TOO_LARGE`／`ARTIFACT_SELECTION_TOO_LARGE` | 413／422 | 縮減大小／選擇；不刪原稿 |
| `ARTIFACT_STORE_FULL`／`UPLOAD_LIMIT` | 409／429 | 等有效上傳完成或由 cleanup 預覽釋放；不自動丟內容 |
| `MATERIALIZATION_STORE_FULL` | 409／needs_attention | 核對 host quota／可用空間，由 cleanup 決定可釋放副本；不刪原 revision |
| `REVISION_CONFLICT`／`UPLOAD_IN_PROGRESS` | 409 | 讀回 artifact／既有 upload；不搶預留 revision |
| `IDEMPOTENCY_CONFLICT` | 409 | 同 key 不改內容，或明確建立新的使用者意圖 |
| `UPLOAD_INCOMPLETE` | needs_attention | 證明前 attempt 停止，對同 operation 供給完整 content |
| `ARTIFACT_DIGEST_MISMATCH`／`ARTIFACT_SIZE_MISMATCH` | needs_attention／逐項 blocked | 保留 ref；查 source／partial，核准新的 attempt，正式不符檔不得覆寫 |
| `ARTIFACT_CONTENT_UNAVAILABLE` | 409／needs_attention | 讀回備份或新增 revision；不從 provenance path 偷抓新的檔案代替 |
| `ARTIFACT_ADAPTER_UNAVAILABLE`／`NO_MANAGED_ROOT`／`GIT_RUNNER_UNAVAILABLE`／`NO_WORKSPACE` | 409 | 修正已配置 host readiness；不退回 manual cwd |
| `FORBIDDEN`／`TIER_DISABLED` | 403 | 需要 action scope／host tier；confirm／force 無法提升 |
| `DESTINATION_MANUAL`／`DESTINATION_UNKNOWN`／`BINDING_MISMATCH` | 403／needs_attention | 修改 target 配置或處理可疑檔案；拒絕接管、unlink 或跟隨連結 |
| `SOURCE_UNAVAILABLE`／`SOURCE_MOVED`／`CONTENT_CHANGED` | 409／needs_attention | 重新讀預覽，保留舊版本；已有 start／send 意圖先對帳 |
| `REPOSITORY_ROUTE_UNAVAILABLE`／`COMMIT_UNAVAILABLE` | 409／needs_attention | 配置可信映射、發布原 SHA 或選同主機；不改用別的 commit |
| `START_MISMATCH` | needs_attention | 查目標 root／HEAD／dirty；不送第一個指令 |
| `UNCERTAIN`／`UNCERTAIN_UNRESOLVED` | uncertain／needs_attention | 查同 operation 的鎖、manifest、BAT meta／turn／transcript；不盲目重送 |

## 實際副作用與預計修改檔案

副作用限 journal／事件、Connector 自有 storage、target managed clone／cache／worktree、既有受限 session 啟動及第一個指令。Cross-host fetch 只寫目的 clone；source files／人工 Git 狀態與 session 永久唯讀。Download 的 client 輸出位置不成為遠端 prompt 或 host mutation 的參數。metadata 標為 ready／verified 前須有 bytes read-back。

| 預計檔案 | 修改目的 |
|---|---|
| 新 `src/bat_agent_connector/artifacts.py` | schema／refs、store、upload／capture／materialize／accept／draft.bind／draft.release ActionDefs、retention facts 與讀模型 |
| 新 `src/bat_agent_connector/artifact_host.py` | 固定 SSH helper、no-follow path／檔案限制、鎖與逐項 read-back；沒有通用 shell API |
| `task_journal.py` | additive、versioned migration；現有 user_version 是 1，本包預計版本 2，若其他包先佔用則 rebase 後使用下一版；舊項目與 checkpoint refs 為空，不能遷移舊 path 字串為 ready artifact |
| `resource_policy.py` | MUTATIONS、Connector storage／artifact destination 規則；所有入口共用，不建立第二個 ownership check |
| `checkpoints.py` | checkpoint manifest、凍結接續輸入、target routing／fetch、readiness／dispatch gates、source revalidate receipt；沿用 start／send reconcile |
| `work_items.py` | typed attachments、版本交易、含附件指紋、work item 與接續 intent 的原子關聯 |
| `operations.py` | 必要的 payload stream 綁定／單 operation 執行鎖支援；保留既有 STATES、idempotency 與 step replay，不另建上傳操作引擎 |
| `task_verifier.py`、`task_daemon.py` | 在現有 settings loader 加 artifacts 設定，註冊 actions／共享 adapter 與 API/RPC 讀模型；不混用 verification.artifact_dir 的 verifier log |
| `api_v1.py`、`mcp_server.py`、`cli.py` | 上表薄 adapters、binary payload／download、capabilities／contract version；所有入口相同 scope／policy |
| `dashboard/app.js`、`app.css`、`i18n.js` | 工作詳情與接續 picker、IndexedDB draft、target selection、operation 材料狀態、en／zh-TW |
| 新 `tests/test_artifacts.py`；既有 checkpoint／work item／resource policy／API 測試 | 下表的 fixture／故障注入與合約檢查 |
| `docs/design/api-v1.md`、`checkpoints.md`、`work-items.md`、`dashboard.md` | Phase 2 完成相應項目後更新 routes 與尚未涵蓋；和 cleanup 規格對接 retention facts |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md`、兩份 `skills/*/bat-agent-connector/SKILL.md` | Phase 2 同步說明 upload→精確 refs→verified→continue／reconcile；引用本文件、計畫章節與驗收，不讓 skill 把 client path 當遠端附件 |

Migration 在同一 journal 的版本流程演進，保存既有 tasks、events、operation、checkpoint、approval／integration receipts。升級失敗不能把半成 schema 宣告可用；重啟可重跑。metadata 更新與 api_event 同交易，傳輸不持有 SQLite transaction。

capabilities 新增 artifacts limits／store readiness、每 host 的 transfer／cross-host target readiness、source capture 與 snapshot=false 原因；actions 仍依 actor scopes 回 allowed。更新 CONTRACT_VERSION 並加入 HTTP／MCP／CLI fixture 契約測試。舊 client 不支援附件時能力明確不可用，不能靠舊 work_* attachments 字串繞過 gate。

## 測試計畫與驗收對照

以下名稱是 Phase 2 應新增的測試，不是本次已執行的驗收證據。BAT 全用 `tests/mockbat.py`；git 使用 temp repos 與 `tests/test_checkpoints.py` 的 LocalRunner／RealGitLog。新 byte adapter fake 支援多 host、真實 tempfile bytes、lost reply 與主機端 symlink race；每 host 使用不同 root，防止「跨 host」測試其實共用同一路徑。

| 計畫／驗收 | 預計測試名稱 | 必須證明 |
|---|---|---|
| §08、§13 | `test_artifact_upload_is_immutable_and_idempotent` | digest／size／type 正確；same key 重送同 revision，改 metadata 衝突；並行 revision CAS、缺號、metadata／bytes 不可覆寫 |
| §13 | `test_artifact_limits_include_partial_and_concurrent_reservations` | 實際串流超量、偽造 length、base64 膨脹、selection／quota／ENOSPC 都拒絕，原稿與 ready bytes 保留 |
| §09、§13 | `test_upload_publish_lost_reply_and_restart_read_back` | 發布後、journal ACK 前重啟補記同版本；partial 重送以新 attempt；沒有第二個 writer，未知結果保持 uncertain |
| A03，§06、§12、§13 | `test_A03_manual_file_capture_and_attachment_leave_source_unchanged` | 附件 preview／capture／checkpoint／link 前後 source bytes、permissions、HEAD、index hash／mtime、refs／config 相同；沒有來源 start／resume／send；後續 source 修改不改 artifact |
| A03，§12 | `test_A03_capture_source_moved_and_snapshot_unavailable` | 檔案／commit 在擷取中變動必拒絕，不發布半份；symlink／hardlink／特殊檔拒絕；snapshot=false 可見，不冒充完整工作副本 |
| B04，§12 第 3–5 步、§13 | `test_B04_cross_host_transfer_interrupted_before_dispatch` | target 已準備但傳輸中斷：零 first-send／零 start；工作、草稿、原 artifact／SHA 保留；同 parent resume 只補不足項目 |
| B04，§13 | `test_B04_digest_size_or_path_mismatch_blocks_first_command` | host read-back 被改、size／digest／path 不符，不能標 verified；不同項部分成功仍保存，沒有指令 |
| B04，§07、§12 | `test_B04_cross_host_commit_fetch_is_pinned_or_blocked` | 目標從 configured remote 真 fetch 原 SHA，BAT 起點一致；不可取、同名 repo／錯 marker／錯 workspace 則 blocked，未落回人工來源 |
| B04，§12 | `test_B04_source_advanced_after_preview_keeps_selection` | source 在 preview／gate／start 到 send 間前進都擋 first-send；舊 cp／refs 不變；明確 revalidate 才 resume 同一 parent／session，已有可能 send 時只對帳 |
| B04，§09、§28 | `test_B04_resume_after_start_or_send_ack_loss_never_duplicates_execution` | 材料 verified 後 start ACK 遺失／daemon 重啟，讀回同 UUID5 ID；send ACK 遺失讀回 marker，不再派工；agent commit 後重播不誤檢起點 |
| B04，§13 | `test_B04_inputs_changed_after_start_keep_session_and_block_send` | start 之後改 cache／target HEAD，送前再驗證失敗，保留同一 session；恢復不建立另一個 execution |
| A03／B04，§06、§13 | `test_artifact_policy_refuses_escape_before_any_host_write` | traversal、相似 root prefix、任一層 symlink／競態、hardlink、manual／unknown cache、file type／alias 注入在寫入前拒絕；force／confirm 不繞過 |
| §09、§10 | `test_artifact_http_mcp_cli_contract_and_scopes` | 三入口 action／results／error／confirm 一致；payload 是同 operation，權限及長度在接收前檢查；manage 不授予 start，start 不授予 accept |
| §13、§19 | `test_dashboard_artifact_drafts_survive_failure_and_clear_exact_success`（Playwright） | 重開頁／browser、upload 成功但 submit 失敗、202／uncertain／材料 blocked 都留原稿；成功只清提交 generation，新編輯留下；沒有 local path 進 prompt |
| §08、§13 | `test_attachment_change_invalidates_work_item_approval` | role／revision／digest 改變重新待確認；expected_version 衝突不丟草稿，migration 不改無附件舊 approval |
| §13；供 E02／§23 接入 | `test_artifact_retention_facts_require_receipts_and_all_holders` | 未接收、draft、shared、restore、active／uncertain holder 擋刪；純歷史可釋放；squash／ancestor 不代替 receipt，移除副本不刪 store／人工來源 |
| §24、§28 | `test_artifact_migration_preserves_existing_journal_and_empty_manifests` | 舊 journal 升級／重啟保留 ID、歷史、approval；舊字串 attachments 不變成 ready artifact；contract version／capability 限制一致 |

Phase 2 UI 檢查 en／zh-TW、390 px、無 `null`／`undefined`／`[object` 字樣、CSP／fill／hold 行為；app.js 複製成 .mjs 後 `node --check`。交付需 `uv run ruff check .`、`uv run pytest -q` 全套通過。Phase 1 只執行現有 regression suite，不據此聲稱 B04／A03 新附件驗收已通過。

## 尚未涵蓋

- 本文件全部新增行為仍待 Phase 2 審查／實作；現有 checkpoints.md、work-items.md 的附件與跨主機尚未涵蓋暫不刪除。Phase 1 不修改產品、README、changelog 或 skills。
- **未發布 commit 跨主機搬移**是 follow-up：唯讀來源 reader 匯出選定 commit 的完整 git bundle 到 Connector storage，固定 SHA／bundle digest／size；受限 adapter 傳到 target managed clone，驗證 bundle 與內容，再 fetch 原 SHA、BAT 查起點，才進 artifact gates。任何匯出／限制／驗證失敗保留原工作並 blocked。不得在人的 repo 建 bundle 檔、refs 或 lock，不讓 target 讀來源 host 的本機絕對路徑。實作前需另定 bundle 大小／完整物件與敏感歷史的接入範圍；本包先對取不到原 SHA 回 COMMIT_UNAVAILABLE。
- 完整 dirty snapshot、tracked patch／untracked 套用、任意目錄／archive 解壓、URL 自動下載、可執行附件、browser filesystem handle 自動恢復不在本包；manual source capture 只複製明選的 regular file。
- Task Service 非 checkpoint 的 work_submit／failover 自動掛附件及 readiness 銜接由執行統一包處理；這些入口在接上相同 gate 前不能宣稱支援本 store 附件。舊 context_refs 字串不提供 readiness。
- 集中 cleanup preview／apply、捨棄／封存／restore 政策、tombstone 與實際刪檔由 §23 包實作。本包提供可查 facts、引用釋放回執與協調契約，不排第二套清理。待兩包 spec 合併時核對 reason codes／facts_version／resource lock 合約。
- **待確認部署值**：16 MiB／64 MiB／512 MiB 與 7／30／7 天是提議預設，需對試行 repo 的實際附件容量確認。Active draft／shared／restore 不受最低保留期限自動釋放；長期未捨棄草稿可能佔滿配額，整理 UI 應讓人看得見原因。
- **待確認接入環境**：每 host 的 SSH helper／atomic rename／no-follow／cache 可讀範圍，以及同 OS 帳號或分離 storage 帳號的配置，需要 mock 故障驗收後做唯讀 readiness；本次沒有連實機或安裝 helper。
- GitHub Actions build artifacts、部署 promotion／rollback 與 provider 到期不納入本 store；未來若有橋接須保存兩邊身分及 digest 驗證，不能只改 ID prefix 冒充同一 revision。
