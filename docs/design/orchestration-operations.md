# Relay 與固定 fan-out 的中央操作

依同一產品的 [legacy mutation 盤點](legacy-mutation-audit.md)、[operation／Task Service 合約](operations-unification.md)
及[產品澄清](../product/realignment-v2.md)。本切片先收斂 relay，再延伸固定 fan-out；不導入新 queue、schema step 或 user_version。

## 第一片：session.relay

Canonical action `session.relay` 使用 `operate`。target 保留 caller 原始 `host`，另有 `session_id` 或
`workspace`（兩者並存時 session 是目標、workspace 是明示脈絡）。params 保留 `message`、`channel`、`thread`、
`earlier`、`brief`、`request_fanout`、`max_items`、`queue`、`start_if_missing`。preconditions 可有
`control_version`。`start_if_missing=true` 同時需要 `start`，包括 replay／resume／cancel；不得在保存後用
同 actor 的較小 scope credential 取得新的啟動權限。不存在 writable session 且未指定 fallback 時，保留
`sent=false`／`no_session`／`read_only` 結果，絕不寫人工 session。

Legacy `session_relay` 與 `batc relay` 只進入已存在中央 owner，保留 confirm、read-only、原始字句與參數。
不 autostart daemon，不 direct Fleet fallback。named key 在動態 session 選擇、transcript 或 rendering 前
重播原操作；no-key 每次新 operation，public key=null／idempotency_enabled=false，storage sentinel 不外洩。
只允許相容 adapter 使用 no-key；raw HTTP operation 仍要求顯式 key。dry-run 使用 observe，只回讀取／渲染，
不建立 operation；它不是永久 preview token，也不使下一次 apply 免除重新確認目標的必要。

`relay.resolve` 只讀並保存正向選擇 receipt：完整 session ID、當時 registry creation／owner binding、runtime
與 workspace identity、rendered text、text digest、原文與 brief、選定 send／new-start／refusal 分支。caller 的
literal request 不被改寫。未完成的純讀取可再讀；已有 receipt 永不重新挑最近 session、較新訊息或另一個 workspace。
Explicit session prefix 僅允許既有至少六字元唯一解析；之後每個 effect 只使用 exact full ID。

一個 parent 最多建立一個既有 canonical `session.send` 或 `session.start` child。child insert、parent／child
link 與 local effect receipt 在同一 journal transaction；其 scope 來自 parent admission 保存的原 caller，
actor／entry 不冒用 admin。child 使用私有無 key identity，不把內部 recovery key 冒充 client key。啟動 fallback
仍是獨立 Codex/worktree，不能把 task-owned 或人工 session 當成新 session 採用。

Send child 仍由既有 TaskCoordinator 建立原 command／FrameGuard。每個尚未送出的 resume/send frame 前重查
parent 固定 incarnation／task owner、task version、resource／cleanup／confinement gates；awaiter 結束後再同步
重查原 guard。新增 parent hook 不取代 Task FrameGuard。Start child 沿用既有 worktree／start／tab／prompt
各個 intent／receipt、capacity／registry claim 與 confinement；parent 固定 workspace/source 與 child plan 必須相符。
Positive completed receipts 先於現行 policy／runtime 的新檢查；未知 reply 只由原 child 的 readback 判定，不重送。

Parent 結果包含固定 rendered text、selection、child operation ID/status/reason 與完整原 receipt。只有 child 正向
證明 initial prompt 已接受才 `sent=true`；未完成／未知為 null，沒有證明的副作用不能包成 succeeded。busy／quota／
manual refusal 的既有說明仍保留。Parent cancel 不把仍有 sent/unknown child 的操作直接 terminalize：先要求原 child
停止未送出工作、保留其 receipts／claims，再回報有待對帳的 outcome。resume 不建立第二 child、不換 target/text。
Child 不能在原 parent 已 cancelled 之後透過直接 resume 偷跑。

## 下一片與尚未涵蓋

固定 fan-out 將使用同一個 narrowly allowlisted parent/child contract，但必須保存原 plan block、exact items/text、
workspace/source、每個 child ID。只在每個 child 正向完成且原 planner incarnation 仍符合時，執行獨立 stop receipt；
worktree 交既有 reviewed cleanup，未知 child 不視為完成，不從新 transcript 重挑 plan。

Standalone failover 另行設計：它共享原 worktree、替代 capacity、持有 handoff fence；不能把整個 lifecycle helper
包一個 step，也不能暗改成 fresh `session.start`。Task-owned failover 繼續只接受 coordinator 發行的 authority。
Task control 的 no-key null projection 可獨立接續，保留 task_send 的既有 step_id retry identity。
本文件不宣稱後兩者已交付，也不變更原 public worktree merge／停用 remove 的決議。

驗證使用 MockBat／臨時 Git／中央 HTTP-RPC-MCP-CLI：scope、named/no-key、exact prefix、workspace choice、manual
不變、owner/version race、lost child reply、重啟、parent cancel/resume、逐 effect receipt 與 zero resend。後端與 UI
分開；full CI 由整合者序列執行，測試不代表 installed/live host 驗收。

## 第二片：固定 fan-out（實作前合約）

`fanout.plan`（start）target 固定 host/workspace；params 是原 message、brief、earlier、channel、thread、max_items。
純讀 resolve receipt 固定 workspace ID／folder／Git root、branch、HEAD 與 planner 完整 prompt。唯一 start child
透過 server-only parent receipt 選用 Codex read-only sandbox、never approval 和 role=planner；公開 session.start
仍不接受 role／permission override。role 隨最初 reservation 保存，不能在 initial prompt 未完成時被 main relay 選中。

`fanout.start` target 有 host，加上 source session_id 或 workspace。來源 session 的模式需要 start＋operate；
純 caller-reviewed `params.plan=[{index,title,prompt,area?}]` 的模式只需 start，沒有 source stop 權限。
前者 resolve 時一次讀原 session 最近回覆，固定 exact full ID、選中 block／digest、每項原字句、來源 incarnation
和 destination workspace Git identity；後者直接保存 caller literal plan。agent=claude|codex、model、max_items
保留原語意與每次 cap。Read dry-run（observe）不寫 registry／operation，apply 不可暗中換 source 或較新 plan。
Source-session 的每項 prompt 保留原文加既有 BAT-STATUS footer；file plan 保留已解析 prompt，不另改寫。

每項依序建立單一 `session.start` child，同 journal transaction 保存 link／intent receipt。只在前項正向證明
prompt acceptance 後派下一項；部分失敗／未知停止新派送，保存每項 operation/session/carrier evidence。
Parent cancel 逐一取消已建立 child 的未送工作；sent unknown 不隱藏，resume 僅續讀原 children，永不另挑 plan。
控制／replay 保留最初 actor 及目前所需 caller scopes；children 私有 no-key identity 不暴露作 caller retry key。

只有所有子項正向完成、原 source 的 creation/role=planner/standalone binding 未變、無 successor／active writer／
pending prompt 且目前允許 orchestrate 時，獨立 `planner.stop` step 才可送一個 stop frame。每個 await 後重查原 binding、
取消與 resource policy；stop ACK 與 unloaded readback 分開保存。Sent/unknown stop 永不重送；之後 meta=None 只能
證明原被綁定 runtime 已不 loaded，不能聲稱由本操作唯一造成。原 reservation 在 stop 有 ACK／readback 且 registry
CAS 仍屬此 incarnation 時才 retire；不刪 worktree／branch／tab，不採用 task-owned session，不釋放 shared successor。
若原 planner 已被後續擁有者替換，保留 child successes 並顯式回報 retained，不覆蓋較新 record。

MCP fanout_plan_session／fanout_from_plan 與 CLI fanout-plan／fanout-start／fanout PLAN --start 全進入中央；
保留 confirm、read-only、optional explicit key、無 key 各自獨立。CLI 解析檔案本身純本機，未 --start 不呼叫寫 API。
Standalone failover／task no-key 仍是下一片，不借此開回 raw fallback 或 parallel authority。
