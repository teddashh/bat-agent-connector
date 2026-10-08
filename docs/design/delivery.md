# GitHub 交付：合併 PR 與部署

日期：2026-10-07。對應《Better Agent Dashboard／Connector 計畫》v1.0 的 §15–§18，工作包 W07（GitHub adapter）與 W08（部署 adapter），驗收 C04–C07、D01–D04。程式在 `delivery.py`（action）與 `github.py`（REST client），經 [OperationService](api-v1.md) 執行。

## 原則

- Dashboard 的按鈕與有權限的 agent 走同一個 handler；沒有 LLM 轉述，也不需要 task_id。
- 只有 `[[github.repos]]` 列出的 repository 能合併；只有 `[[deploy.recipes]]` 列出的 recipe 能部署。瀏覽器只能指定 recipe 名稱，不能傳 workflow 或任意 inputs。
- GitHub token 只在後端（`[github] token_ref`），不回傳給瀏覽器或 MCP。
- API 版本固定為 `2026-03-10`（`X-GitHub-Api-Version`），依據 GitHub 公開的 OpenAPI 描述撰寫。

## 合併：`github.pr.merge`

Scope `merge`。輸入：`target {repository, pull_number}`、`params {method}`、`preconditions {expected_head_sha}`（必填，完整 40 hex）。

1. 讀 PR。已合併：只有合併時的 head 等於 `expected_head_sha` 才算成功，並標明 `merged_by_this_operation`；不同 head 轉 `needs_attention`。已關閉、草稿、head 已變（`TARGET_HEAD_CHANGED`，409）直接失敗；有衝突轉 `needs_attention`。
2. 必要 checks 尚未完成（`mergeable_state = blocked` 且有未完成的 check run）時轉 `waiting_checks`，不送合併。
3. 步驟 `merge.submit`：`PUT /pulls/{n}/merge-async`，帶 `sha` 與 `merge_method`、`merge_action = default`（有 merge queue 就進 queue）。
   - 202：記下 request UUID。
   - 200 `merged`／`enqueued`：已合併或已在 queue。
   - 409：既有請求。只有 `expected_head_sha` 與方法相符才沿用它的 UUID，否則 `needs_attention`。
   - 400：PR 不能合併，失敗。
4. 輪詢 `GET …/merge-async/{uuid}`：`pending` 轉 `waiting_external`；`failed`（分支保護或規則在執行時才判斷）轉 `needs_attention`；`enqueued` 等 PR 真正合併，queue 狀態不算合併。
5. 讀回 PR，以 `merged` 與 `merge_commit_sha` 為準記錄實際合併版本。

送出後回應遺失（逾時、5xx、429、回應內容被截斷）：步驟記為 `uncertain`。回查 PR：已合併就補記成功；仍開著才再送一次，因為 GitHub 會把同一 PR 的待處理請求以 409 回傳原 UUID，不會產生第二次合併。

讀取沒有回應（含帶 rate-limit header 的 403）時 `waiting_external`，稍後再讀。讀取被拒（401、403、404）時，若這個操作還沒送出任何寫入就 `failed`；已送出合併請求或 dispatch 後則轉 `needs_attention`，因為 GitHub 可能仍在合併或部署，`failed` 會釋放 recipe 的部署鎖。修好 token 或權限後 `resume`。Token 每次請求重新讀取，所以輪替或會過期的 token（GitHub App token 一小時）不必重啟 daemon。

## 部署：`deployment.start`

Scope `deploy`。輸入：`target {recipe}`、`params {source_sha}`（完整 40 hex，通常是實際合併版本）。同一個 recipe 同時只允許一個未結束的部署操作（409 `DEPLOY_IN_PROGRESS`）。

| Recipe 模式 | Connector 的動作 |
|---|---|
| `workflow_dispatch` | 步驟 `deploy.dispatch` 呼叫已配置的 workflow，inputs 只能來自 `source_sha`、`operation_id`、`environment`、`repository`。200 回應帶 run ID；舊格式 204 則以 run-name 裡的 operation ID 找 run |
| `on_merge` | 不 dispatch。找該 workflow 中 `head_sha = source_sha`、event 為 push 的 run；還沒出現就 `waiting_external` |

追蹤 run：未完成時 `waiting_external`（環境審核等待會標明）。完成後要 run 的 conclusion 為 success，**且** recipe 的 `deploy_job` 也為 success；job 被 skipped 或不存在都不算部署（`DEPLOY_NOT_RUN`）。

Dispatch 回應遺失：以 run-name 含 operation ID 的 run 回查；找不到就維持 `uncertain`，不再 dispatch。所以 `workflow_dispatch` recipe 必須把 `operation_id` 列為 input，workflow 也要設定含它的 `run-name`，例如：

```yaml
on:
  workflow_dispatch:
    inputs:
      source_sha: { required: true }
      operation_id: { required: true }
run-name: deploy ${{ inputs.source_sha }} (${{ inputs.operation_id }})
```

接入條件：workflow 本身要在部署前檢查實際部署的內容等於 `inputs.source_sha`。Connector 的事後讀回不能取代這個檢查。

## 合併並部署：`delivery.merge_and_deploy`

需要 `merge` 與 `deploy` 兩個 scope。先依上面的合併流程取得實際合併版本，記入 `external_refs.merged_sha`，再以這個版本部署。部署失敗時操作為 `failed`，但合併結果保留；Dashboard 以 `merged_sha` 發起新的 `deployment.start` 重試，不會再合併。

## 讀取

- `GET /api/v1/repositories/{owner}/{repo}/pulls/{n}`（MCP `github_pr_preview`）：head／base SHA、mergeable 狀態、check run 數量（總數、未完成、失敗）、允許的合併方法與該 repository 的 recipes。按鈕送出時以這裡的 `head_sha` 作為 `expected_head_sha`。
- `GET /api/v1/capabilities` 列出已配置的 repositories 與 recipes。

## 設定

```toml
[github]
token_ref = "env:GITHUB_TOKEN"   # 或 file:；建議使用只安裝在指定 repositories 的 GitHub App token
wait_max_s = 3600                # 等 checks、queue、run 超過這個時間就轉 needs_attention

[[github.repos]]
repository = "owner/name"
merge_methods = ["squash", "merge"]
default_merge_method = "squash"

[[deploy.recipes]]
name = "site-production"
repository = "owner/name"
environment = "production"
mode = "workflow_dispatch"       # 或 on_merge
workflow = "deploy.yml"
ref = "main"
deploy_job = "deploy"
inputs = { source_sha = "source_sha", operation_id = "operation_id" }
run_name_contains = "operation_id"
```

所需權限依用到的 API：Contents（merge）、Pull requests、Checks read、Actions read／write（dispatch 與讀 run）。不需要 Administration、secrets 或規則 bypass；`bypass_rules` 永遠不送。

## 尚未涵蓋

- 同一環境的部署順序目前以「同 recipe 同時只能有一個操作」保證；較舊 run 較晚完成的情況（D05）依賴 workflow 的 concurrency 設定。
- 回退（D06）：以已保存的舊 `source_sha` 發起新的 `deployment.start`；資料庫 migration 等外部副作用由 recipe 說明。
- 更新 PR head（整合成果，§14）見 [integration.md](integration.md)；整合進行中不能合併同一個 PR（`INTEGRATION_IN_PROGRESS`）。
- Stacked PR：`merge-async` 對 stack 會一併合併下層 PR；第一版不偵測，請勿對 stack 使用。
