# Durable worktree merge

本合約延續 [產品決策](../product/realignment-v2.md) 與
[legacy mutation audit](legacy-mutation-audit.md)：`worktree.merge` 是既有
OperationService 的 `integrate` action，不是另一個 Git queue。

## 呼叫與固定輸入

HTTP `POST /api/v1/operations`：`action=worktree.merge`、
`target={host,session_id}`、`params={}`，必須提供 idempotency key。
既有 MCP `worktree_merge` / CLI `merge` 保留 confirm，增加 optional key；無 key
每次獨立建立 operation，公開 receipt 的 key 為 null。原 caller 的 integrate scope
及 actor 用於 replay/resume/cancel。既有 key 在目前 tier/helper admission 前重播；
新請求需要 orchestrate tier。沒有 direct BAT fallback 或 daemon autostart。

準備步驟只讀，將 unique prefix 固定為完整 SID，固定 creation evidence、host profile /
managed roots、terminal/workspace、source worktree 與 destination checkout 的 real Git
root、common directory、branch、HEAD 及所有 carrier consumers。禁止 manual、unknown、
task-owned（含 journal-only owner）、尚未確認的 start / handoff、active writer、pending
prompt、未決 command / external effect。兩端都必須是 managed root 下的現有 Git carrier；
相同 path 名稱不構成 repository identity。

## Affirmative Git evidence

需要現有 verifier 的 host → SSH alias mapping（capabilities 提供 available/reason）。
只透過既有 `SshGitRunner` 傳送 packaged read-only Python helper；request 僅含從固定
managed binding 得出的 paths/roots，沒有 caller shell / command、fallback transport。
Git 使用固定 argv、sanitized environment、禁用 hooks/fsmonitor/optional locks，逐一檢查
process exit / timeout / output bounds；直接讀取 status，不使用 shell pipeline。
`git:status=[]` **不能**證明 clean，因 pinned BAT read wrapper 也用空陣列表示失敗。
helper before/after identity 必須一致；source 與 destination 的 common directory 必須相同，
HEAD/branch 與 BAT 固定讀取一致，status 成功且無 tracked/untracked changes。

這是受管理 writer 的最終 frame 檢查，不是對任意本機／同 UID process 的原子 filesystem
snapshot。Pinned BAT merge 沒有 SHA/CAS；外部 unmanaged process 不遵守 Connector fences。
BAT 仍會在 merge 內自行檢查 destination cleanliness。不得以 changed HEAD / mergedKind
推論遺失的 ACK。

## Reservation、effects 與 recovery

在現有 registry flock 下保留兩個 carrier roots 及 descendants，探查既有 start claims、
固定每個 consumer incarnation。新 start/shared/warm claim、一般 write frame、cleanup
都使用相同 reservation；read/stop/interrupt 保持可用。無 public force 或 bypass；僅原
operation 的 private execution context 可使用自身 reservation。衝突或不可讀 registry
fail closed。每個 frame 的 awaited identity/idle/Git proof 後再同步重查所有 owner/config /
registry consumers，避免 async 間隙穿越 task owner 或 start claim。

缺失 native worktree registration 時，只在仍有 read-only fallback status 的完整原始
branch/sourceBranch/path binding 時允許 `worktree:rehydrate`。它可能複製 local env files，
所以有獨立 durable intent / positive ACK receipt；其後重新檢查全部證據才送 merge。
完全遺失 source branch 證據時拒絕，不猜 branch。rehydrate ACK 不聲稱已驗證 env bytes。
Merge 只支援固定 `strategy=merge`；保留 already merged / no new commits / diverged 的
no-op reason，沒有 force/cherry-pick 或 implicit checkout。

每個 effect 持久化 exact channel/params。只有正面 ACK 可完成；sent error、false/malformed
reply、timeout、process crash 都保留 unknown 及兩端 reservation，永不重送。
`merged_now=null` 表示不確定。成功回覆只證明 BAT 接受 merge，保留其 branch/strategy
receipt，不宣稱固定 merge commit/parents 或測試通過。已完成 receipts 的 recovery 不需
重新通過 moving HEAD / live policy；只做原 marker CAS 的 local release。cancel 不隱藏
unknown effects，不釋放未知 writer；在已 ACK 後取消仍可完成 local receipt bookkeeping。

來源：BAT `b7419892fbc9946799b64cca24c2ec8c7fa15c42` 的
[merge / rehydrate](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/crates/bat-git/src/worktree.rs#L1469)、
[read status wrapper](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/commands/git.rs#L301)。

尚未涵蓋：task-owned merge、manual checkout merge、unknown ACK 人工裁決 API、GitHub PR
delivery、native/實機驗收；既有 integration / Task Service ownership 不變。
