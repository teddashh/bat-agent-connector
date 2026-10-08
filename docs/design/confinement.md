# Managed session 的執行限制

日期：2026-10-08。審查後 Phase 2 規格；以下新增行為按本輪決議實作。對應計畫 §06「執行環境的可寫範圍」、§07、§12、§28，W02／W04 remainder，驗收 A10。沿用 [資源政策](resource-policy.md)、[checkpoint](checkpoints.md)、[整合](integration.md) 與 [OperationService](api-v1.md)。

## 固定來源版本

| 來源 | 版本與用途 |
|---|---|
| Connector | 分支 `feat/confinement`，起點／`origin/main`：`5e8e41696ebc6a1a9d3ea92ddb7a1d338537ca1b`。以下現況清單以此 commit 的程式為準。 |
| BAT | 計畫固定 commit `b7419892fbc9946799b64cca24c2ec8c7fa15c42`。直接讀取此版 source archive；不以本機 BAT checkout 或上游最新 main 代替。 |
| BAT 協定筆記 | [docs/PROTOCOL.md](../PROTOCOL.md)，v3.2.12 的遠端 channel、meta、resume 與權限變更筆記。它和固定 source 分開引用，不假定每台主機已裝固定 source。 |
| 既有交接 | [2026-10-08](../handoff/2026-10-08.md)、`CONTRIBUTING.md`。交接中的較舊 head 不取代本規格起點。 |

BAT 原始碼引用，均固定於上述 commit：

- [S1：src-tauri/src/remote_server.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/remote_server.rs)：`claude:start-session`／`resume-session`／`client-resume` 的 Codex native routing、`invoke_sidecar_for_remote`、兩個 Codex permission setter。
- [S2：node-sidecar/src/handlers/claude-session.mjs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/src/handlers/claude-session.mjs)：Claude start、`resumeClaudeSession`、client-resume、`claude.setPermissionMode`。
- [S3：node-sidecar/src/handlers/claude-send.mjs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/src/handlers/claude-send.mjs)：`buildQueryOptions` 建立真正交給 Agent SDK 的 options。
- [S4：node-sidecar/src/handlers/claude-permission.mjs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/src/handlers/claude-permission.mjs)：`buildCanUseTool`、`ACCEPT_EDITS_AUTO_APPROVED_TOOLS`、resolve handlers。
- [S5：src-tauri/src/codex_app_server.rs](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/codex_app_server.rs)：`normalize_sandbox`／`normalize_approval`、`start_session`／`resume_session_locked`／`client_resume`、`build_thread_start_params`／`build_thread_resume_params`／`build_turn_start_params`／`app_server_sandbox_policy`、`reconfigure_session`。
- [S6：node-sidecar/package.json](https://github.com/tony1223/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/node-sidecar/package.json)：Agent SDK 固定為 `0.3.285`。SDK 能接受某欄位，不等於 BAT 已轉送它。

## 現有與新增行為差異

`resource_policy.WriteGrant` 保護的是 Connector 送出的 BAT／Git 操作，不是 agent subprocess 的檔案權限。`isolation: managed_clone` 表示 Git 資源歸屬；`cwd` 表示起點。兩者都不是 shell／檔案寫入的隔離證據。

目前只有 checkpoint 接續與 integration repair 明確傳 `write_scope: confined`。其他 start 大多使用 `permission_options()` 與 host 的 `default_permission_mode`。目前沒有 level、host account 宣告或查核結果。新增一個共用 confinement 決策與證據物件，所有 start 與權限變更都使用它；不另建 ownership gate、task database 或 agent engine。

**需要更正既有描述**：固定 BAT 的 S4 在 `acceptEdits` 下直接 allow `Write`、`Edit`、`NotebookEdit`、`Read`、`Glob`、`Grep`；callback 沒有核對 path。Claude CLI 把需要詢問的工具交給 callback 時，這條分支仍可能放行目錄外的編輯。因此目前 `CONFINED_OPTIONS["claude"]`、checkpoint 文件、skills 與 `i18n.confined_note` 所說「目錄外一定詢問」不是這版 BAT source 能證明的保證。Shell 仍有 permission 流程，也不等於 OS sandbox。

一般 start 保留操作者的 `default`／`allow_all` 選項。新增 `default_permission_mode=confined` 才套受限 options／旗標；checkpoint／repair 固定受限。無已查核 host_account 的受限 Claude 用明確 `permissionMode=default`；有帳號證據才可 acceptEdits。既有 acceptEdits session 不改 mode；如無其他證據，記 none、部分工具詢問缺口。

## Claude worktree settings 的評估與決定

固定 SDK `0.3.285` 的 [官方 npm metadata](https://registry.npmjs.org/@anthropic-ai/claude-agent-sdk/0.3.285) 記 `claudeCodeVersion=2.1.285`；BAT S3 另會找主機安裝的 CLI，所以 SDK 版本不能證明 host 實際 CLI 版本。評估了在 managed worktree 寫 `.claude/settings.local.json`、canonical-path Edit／Read allow、settings 自身 deny、Bash sandbox 與 clone info/exclude。

官方 [permissions 文件](https://code.claude.com/docs/en/permissions#read-and-edit) 說 Edit rules 涵蓋 file tools，但不涵蓋任意 Python／Node 子程序的間接寫入。[settings precedence](https://code.claude.com/docs/en/settings#lists-merge-instead-of-overriding) 說 allow lists 會合併，不能靠 local allow 清掉 user／project 的其他批准。文件沒有一個能由此檔完整封住所有外部寫入的 policy replacement。

[Sandbox 文件](https://code.claude.com/docs/en/sandboxing#repository-settings-under-an-admin-required-sandbox) 明列 v2.1.285 的 admin-required 規則：需要 managed settings 或 `--settings` 的強制政策；local settings 本身不構成這個邊界。Sandboxed Bash 會保護 `.claude` 設定，但 inherited excludedCommands／已批准的 unsandboxed Python／Node 可以改 settings，file deny 不能擋其間接寫入。BAT 未轉送可信 per-session sandbox/settings override。這是保守判斷：無法證明此 local-file 方案在任意 host settings 下維持要求的邊界，故本包不寫該檔或 info/exclude。採用已核准 fallback：plain default，未預先授權的 edit／Bash 會詢問；表單提示並推薦無 account 證據時使用 Codex。已有規則／單次批准仍是明示缺口，不宣稱每次 edit 絕對必問。

## 全入口盤點：今天得到什麼

表中的「預設」是 `permission_options()`：Claude `allow_all` → `bypassPermissions`；Codex `allow_all` → `danger-full-access`＋`never`；`default` 不送權限欄位。BAT 固定 source 的 Codex omission default 是 `workspace-write`＋`on-request`；這不能用來推斷不同版本的主機，也不是現有 registry 已保存的證據。

| 檔案／函式與呼叫端 | 現在的 start／reconfigure 與紀錄 | 今天的可寫範圍證據／缺口 |
|---|---|---|
| `orchestrate.py:permission_options`、`session_start`；`mcp_server.py:session_start`、`cli.py:_run` 的 `start` | 預設；Claude 可傳 `permission_mode`。reserve 與正常成功時存 `permission_mode_claude`／`agent_params`。 | `allow_all` 無 CLI 寫入限制；default 僅可依實際 agent／BAT options 判斷。registry 沒有 level。 |
| `checkpoints.py:start_in_worktree`、`_run_continue` | `write_scope=confined`；Claude `acceptEdits`，Codex `workspace-write`＋`on-request`，不看 host default。 | Claude file callback 的 path 缺口；Codex 的 sandbox 設定有證據，OS 實際阻擋需實機驗收。 |
| `integration.py:_run_handoff` | 共用 `checkpoints.start_in_worktree`，在 repair worktree 啟動。 | 和 checkpoint 相同；integration area 是目的地政策，不是執行 sandbox。 |
| `lifecycle.py:session_relay` 的 `start_if_missing` | 用 `session_start` 開 Codex worktree，預設。原 read-only session 保留不動。 | 新 session 沒有沿用來源的 confinement 證據。 |
| `lifecycle.py:fanout_plan_session` | Codex planner 呼叫 `session_start(..., permission_mode="default")`。 | 此參數只對 Claude 有效；Codex 仍用 host default。`PLANNER_PREFACE` 的 read-only 指示不是限制。 |
| `lifecycle.py:fanout_from_plan`；`cli.py:_run` 的 `fanout --start` | 每項用 `session_start`，預設。`fanout_plan`／`read_plan` 本身不啟動 session。 | 每個 child 都可能是 allow-all；沒有每項 confinement 回執。 |
| `lifecycle.py:session_failover`／`_failover_one`，包含 `all_exhausted=true` | confined predecessor → Codex confined options；其餘 → host default。沿用 worktree 或 archive-only start 都經同一函式。 | `write_scope` 有沿用；但 successor reserve 尚未保存 permission fields，要等 start 成功才保存。ACK 不明時可能缺選項證據。 |
| `task_bat.py:BatAdapter.start` 的 lead；`task_core.py:TaskCoordinator._start` | lead 用 `session_start`，預設，含指定 base branch 的 external worktree 路徑。 | Task Service 的 testing／續推行為依既有權限運作；不能在本包改 engine／recipe。 |
| `task_bat.py:BatAdapter.start` 的 reviewer 分支 | 直接 `claude:start-session`：Codex `read-only`＋`never`；Claude `plan`。 | 有明確 start options，但 reserve／tab 未保存 permission fields。此為仍存在的相容分支，不恢復已移除的 reviewer 流程。 |
| `task_bat.py:find_warm`、`_warm_identity`、`start` warm 分支；`registry.py:claim_warm` | 驗證乾淨、idle、前次已驗證 HEAD 後，轉 task 關係，不重新 start。 | 權限保持原值；不能按新 task 的預設補成更強 level。 |
| `task_bat.py:failover`、`recover_failover` | 共用 `lifecycle.session_failover`，另核對 successor／handoff 意圖。 | 後端路徑仍存在；不啟用 TaskCoordinator 已停用的中途 failover。限制不能因恢復而丟失。 |
| `service.py:session_send`、`session_continue`、`_resume_params`、`registry_terminal` | meta null 才 client-resume；options 來自 tab，無 tab 才由 registry 合成。 | 沒有重新採 host default；但 tab 可舊／不含 permission fields。不能依 cwd 宣稱 resume 保持限制。 |
| `checkpoints.py:start_in_worktree.restart` | ACK 不明後按預留 ID／cwd 讀回，補 active，不重開。 | 現在只核對 cwd；新增必須也核對限制 options，才能把 level 記為已確認。 |
| `task_bat.py:recover_start`、`session_presence`、`_restore_headless_lookup`；`registry.py:ensure_existing` | 以 task commands／branches、BAT meta、workspace／worktree 證明既有 session，恢復 lookup。 | 原 registry 還在時不抹去未指定欄位；完全遺失時重建列沒有 permission fields／write_scope。身分證據不能替代限制證據。 |
| `orchestrate.py:_wt_status`、`worktree_merge`、`worktree_remove`；`lifecycle.py:_evaluate`／`session_cleanup` | `worktree:rehydrate` 恢復 BAT 的 Git worktree 紀錄。Connector 自建 worktree 由政策拒絕 rehydrate。 | 不啟動 agent，也不套用 sandbox；不得藉此重算／升級 level。 |
| `lifecycle.py:session_set_permissions` | allow-all 需 host allow-all；confined 拒絕。Claude 閒置才切換（`force` 可繞過 in-flight）；Codex 兩個 setters。 | confined check 在 `force` 之前。`default` 可以更改 confined options；Codex default 實際送受限選項，但 registry 用空 `permission_options()` 更新，丟失這份證據。 |
| `lifecycle.py:approve_pending`、`_raise_deferred` | bulk 跳過 read-only／confined。其餘逐項 answer 後 raise；Claude in-flight 記 `permission_raise_pending`，之後再試。 | deferred 真正 raise 仍經 `session_set_permissions`；dry-run 尚會列出 confined 舊 pending raise。須在計畫與 frame 前都查，不能只靠 bulk 開頭判斷。 |
| `service.py:session_answer`；`api_actions.py:_answer` | 逐次 permission allow／deny，可 `dont_ask_again`；已有 Task Service answer gate。 | confined 不攔逐次 allow；可批准 shell／sandbox escape。S4 的 `ExitPlanMode`＋`dontAskAgain` 可把 Claude 改成 `acceptEdits`，也必須視為 mode 變更。 |
| `orchestrate.py:session_start`、`lifecycle.py:session_failover`、`BatAdapter.start` 的 tab registration；`service.py:_resolve_session` | `append_workspace_terminal` 保存／取用 tab 的 permissionMode／agentParams。 | tab 是 projection，不能覆蓋已記的 confinement 意圖。reviewer 的 projection 現在不帶這些選項。 |

`channels.py` 沒有開放 connector 呼叫 `claude:resume-session`、reload／reset／fork、set-model／set-effort 或任意 SDK option 通道；CLI／MCP 沒有另一個 raw start。Goose 的 task-scoped session 工具仍經 `BatAdapter`。盤點涵蓋目前存在但 coordinator 未啟用的分支，不藉本包重新開啟它們。

## 不改 BAT 可以傳什麼

S1 的遠端 routing 會把 `options` 交給 native Codex 或 Node handler；不是任意欄位都會一路交到 CLI。PROTOCOL §4 的 v3.2.12 筆記證明 channel 與既有欄位，未聲明通用 sandbox settings 介面。

| Agent／欄位或通道 | 固定 source 的實際落點 | 可達與不可達 |
|---|---|---|
| Claude `options.permissionMode` | S2 存 session；S3 `buildQueryOptions` → SDK `permissionMode`。`default` 不填 SDK 欄位，用其 default。 | 可達。S2 setter 接受字串；不是 capability enum 驗證。S4 明確處理 `default`、`acceptEdits`、`plan`、`dontAsk`、`bypassPermissions`、`bypassPlan`、`auto`；仍需 CLI 支援。`bypassPlan` 映到 SDK `plan`，但 BAT callback 可自動放行，不能當只讀。 |
| Claude bypass | S3 只有 mode 為 `bypassPermissions` 時填 `allowDangerouslySkipPermissions=true`。 | 不能靠 start 傳同名任意欄位來獨立控制；是 permissionMode 衍生值。 |
| Claude SDK sandbox／工具 allow／deny／額外目錄／env | S3 手工建立 queryOptions，沒有從 s.options 複製 `sandbox`、`allowedTools`、`disallowedTools`、`additionalDirectories` 或任意 `env`。 | 透過 BAT start／permission options 不可達。不可因 Agent SDK 有此 API 就在 Connector 宣稱已設定。 |
| Claude 使用者與專案設定 | S3 固定 `settingSources=['user','project','local']`，settings 另由 BAT 組成。 | 主機現有 Claude settings 可能帶 sandbox／既有 allow rules；start 無法覆寫或隔離它們。只能另以主機證據記錄，不能以未轉送的 JSON 當證據。 |
| Claude `claude:set-permission-mode` | S2 → live query `setPermissionMode`；失敗會關閉 query，下一 send 重建。 | 可達，不能強制切換正在跑的 turn。限制 mode 變更必須留下意圖、讀回與結果。 |
| Claude resume／client-resume | S2 cold resume 先用已記 mode，無已記值時歷史 fallback 是 `bypassPermissions`；明確 options.permissionMode 可以覆蓋。已有 live session 的 client-resume 主要接回歷史，不重新套 options。 | 恢復必須明確帶原 mode 並讀回；不能省略欄位、只核對 cwd 或用 client-resume 成功證明 mode 生效。PROTOCOL 的 v3.2.12 note 不消除這項固定 source 風險。 |
| Codex `options.codexSandboxMode` | S5 normalize → thread start／resume 的 `sandbox`，turn start 的 tagged `sandboxPolicy`。 | 只支援 `read-only`、`workspace-write`、`danger-full-access`；其他值退回 `workspace-write`，不能拿無錯誤當 option 被採用。 |
| Codex `options.codexApprovalPolicy` | S5 normalize → thread／turn 的 `approvalPolicy`。 | `untrusted`、`on-request`、`never`；其他值退回 `on-request`。不能假設 `on-failure` 可用。`never` 是不詢問，不是隔離；配 `danger-full-access` 仍可任意寫。 |
| Codex writable roots | S5 `app_server_sandbox_policy` 的 workspaceWrite 只有 `type`；thread builders 只傳 mode。 | 不轉送 `writableRoots`／`writable_roots`，也沒有 setter；不能從 Connector 把整份 `managed_roots`、Git common dir、cache 加到 sandbox。cwd／CLI 預設或主機 config 的實際 roots 必須另外驗證。 |
| Codex network | 同上；沒有 `networkAccess`／`network_access` 欄位或 setter。 | 不可由本介面選擇開／關網路。workspace-write 的網路與 temp roots 行為依安裝的 CLI／host 設定，不在本包猜預設。 |
| Codex 兩個 permission setters | S1 → S5 `set_sandbox_mode`／`set_approval_policy`＋`reconfigure_session` 的 thread/resume；turn/start 也送當前 policy。 | 可達，但兩次呼叫不是原子切換，對正在跑的 turn 不保證立即生效。需等閒置並逐步 reconcile。 |
| Codex client-resume | S1 → S5 `client_resume`；既有 runtime 的 thread 以 host 設定為準。 | 不是以舊 tab options 強制重設 live session 的方法；無法拿 client-resume 成功當 permission change 成功。 |

不新增 BAT channels。主機版本與可用 agent presets 從既有只讀通道讀取；新／未知版本的 reachability 記 `unknown`，不照表自動補出保證。BAT meta 回傳 mode 表示設定值，不單獨證明 OS sandbox 已在該平台生效。

## Level 與證據

`provenance`、`api_access`、`isolation` 保持原定義。新增 `confinement`，不把其 level 用來授予 Connector 寫權。`write_scope: confined` 保留為禁止自動放寬的政策旗標，也不等於某個 level 已成功啟用。

| `level` | 足夠的證據與阻擋範圍 | 不阻擋／保證界線 |
|---|---|---|
| `host_account` | 操作者宣告 BAT 的受限帳號與被保護 roots；同身分的只讀權限查核通過，已觀測 BAT／agent 身分吻合。保護的是這些 roots 的檔案改寫、建立、刪除與替換。 | 逐次批准不會提升 Unix 權限。但未列 roots、其他可寫 repos、讀取與網路不受保護；sudo／特權 helper、其他帳號的服務可繞過，查核限制須明列。不是整台主機已不可越界的證明。 |
| `os_sandbox` | 明確傳送、讀回 CLI sandbox options。此包最多 options_confirmed，gap=sandbox_enforcement_unverified；實機 verified 留給 W12。Codex `workspace-write` 或 reviewer `read-only` 是候選機制。 | 對 sandbox 內的 shell／檔案工具生效；on-request 的越界操作若被批准，可能離開 sandbox。實際 writable roots、暫存／cache、Git metadata、網路另列；不保護授權範圍內其他 repos。 |
| `prompt_gated` | 確認 Claude `default`／`plan` 的 permission 路徑；未被 CLI 既有規則預先 allow 的工具會詢問。 | 無 OS 寫入邊界。shell 可一次涵蓋多個路徑；allow／dontAskAgain、pre-approved rules、MCP／外部工具都會擴大範圍。不能說「所有目錄外寫入一定詢問」或完整達成 §06。 |
| `none` | 無足夠證據、bypass／full-access，或只有 cwd／prompt／部分工具詢問（例如現有 Claude acceptEdits）。 | 沒有可宣稱的執行寫入保護；Connector 的人工資源 API 唯讀政策仍存在。 |

Level 不是全序：帳號限制可能只保護指定 roots，sandbox 可能另准許 temp roots。保留所有 `mechanisms`；通過查核的 host_account 優先顯示，其次 os_sandbox、prompt_gated、none。不能用字串大小比較 successor 強弱；比對受保護 roots、批准途徑與已記 options。

Session 物件（新增；下例 options 已核對但主機還沒做 sandbox 實機驗收）：

```json
{
  "write_scope": "confined",
  "confinement": {
    "schema_version": 1,
    "level": "os_sandbox",
    "requested_level": "os_sandbox",
    "mechanisms": ["codex_workspace_write"],
    "options": {"codexSandboxMode": "workspace-write", "codexApprovalPolicy": "on-request"},
    "evidence": {
      "source": "start_intent_and_bat_meta",
      "bat_source_commit": "b7419892fbc9946799b64cca24c2ec8c7fa15c42",
      "observed_options": {"codexSandboxMode": "workspace-write", "codexApprovalPolicy": "on-request"},
      "host_check": null,
      "checked_at": null
    },
    "verification": {"status": "options_confirmed", "reason": "sandbox_enforcement_unverified"},
    "limits": ["individual_approval_can_escape", "writable_roots_not_configurable", "network_not_configurable"],
    "gap": "sandbox_enforcement_unverified"
  }
}
```

`verification.status` 為 `pending`、`options_confirmed`、`verified`、`unknown` 或 `mismatch`。`level` 是建立時已具證據的限制；`requested_level` 是本次要求。只有 cwd、reserve 或 ACK 不填 `verified`。實機證據包含 run／log digest、檢查時間、BAT server version、CLI version、OS、runtime 身分與 policy；從既有 journal 的 evidence／operation refs 留存，不設第二個資料庫。W12 的證據須能連到同 host 與相同 runtime 設定。新的主機／CLI／BAT 版本不能沿用舊驗收通過狀態。

保留建立快照與最新只讀 `current_verification` 分開顯示。現在的 meta 與已記 options 不同、帳號 check 失效或證據過期，顯示 mismatch／unknown，不改寫歷史 level，也不能以舊 level 繼續宣稱保護仍有效。未驗收的 sandbox level 可為 os_sandbox，但只能 options_confirmed，呈現缺口，不列為 A10 通過。

## 每個入口的新預設（審查決議）

先做既有資源／目的地政策，再選 agent 可達且不改變任務的限制。正常 start 決策在第一個有副作用的 step 前保存；BAT start 後核對 meta，通過後才送第一個工作 prompt。對支持的同版本 host，優先沿用已查核的 host_account；一般 Codex 另保持 workspace-write，兩種機制可共存。

| 入口 | 新 start options／限制政策 | 相容性與缺口 |
|---|---|---|
| 一般 `session_start`、relay missing、fanout children | default／allow_all 保持今日選項；host policy=confined 才套 Claude default 或已查核帳號的 acceptEdits、Codex workspace-write/on-request，write_scope=confined。 | allow_all 記 none。一般 installs／localhost tests 可能需網路；不偷偷改成 Codex sandbox。confined 受限 options 不被 explicit bypass 覆蓋；explicit plan／dontAsk 保留更強限制，不改成 default／acceptEdits。 |
| checkpoint／repair | 固定受限 Claude default（帳號已查核才 acceptEdits）／Codex workspace-write/on-request；使用已記來源與 managed clone／integration area。 | 無已查核帳號用 Claude default，有帳號才 acceptEdits；Git 測試、commit 與 shell 仍可透過逐次詢問執行。不可失敗後退回人工 cwd。 |
| fanout planner | Codex `read-only`＋`never`，記 options 與受限旗標。 | planner 的既有工作只讀；不需要 commit、安裝或測試。仍不宣稱新 planner／模型政策。若實機不支援，顯示不支援，不退回可寫 allow-all planner。 |
| failover／archive successor | 新 session 用上述預設，並繼承 predecessor 的禁止 raise、受保護 roots 與證據關係。 | 受限 predecessor 不依 host allow-all 放寬；非受限 predecessor 保持 host 政策。對 predecessor 為 read-only／never，successor 保持該限制；對已有 host_account，不丟 account 邊界。無法維持時 blocked，保留前任。新 session 可有更強證據，但不能重標前任。 |
| Task Service 新 lead／external worktree | **保留現有 engine／recipe 的權限行為**。default 不新增送出欄位；start 後由 BAT meta 保存實際 workspace-write/on-request 或 Claude default，不新增 sandbox roots／網路政策。 | allow-all 任務如無已查核的 host_account，level=none、`gap=task_recipe_compatibility`；不冒稱 confined，也不強制改成 sandbox/never 令測試失敗。Task Service 保持其 default／allow_all 行為；新增 confined 設定在 task 內仍沿用原 default 行為並記 task_recipe_compatibility，不另改 engine／recipe。 |
| Task Service reviewer 相容分支 | 保存現有 Codex read-only/never 或 Claude plan，不改 recipe 是否會使用 reviewer。 | reserve、read-back 與 tab 都保存實際 options；未讀到 permission fields 記 unknown，不增加 Task Service engine 的阻擋。 |
| warm reuse、resume、rehydrate、start recovery | 保持該 session 原已記 options／level，不套新 start 預設。 | 恢復不得抹去 write_scope；缺證據顯示 unknown／none，不能按今日 host default 或 cwd 升級。 |

Codex `never` 不普遍取代 `on-request`：它可能禁止測試需要的外部 cache、Git common dir 或依賴網路，而 BAT 不能指定這些 writable roots／network settings。`read-only` 不能完成 coding／repair。先用可工作的最強 sandbox mode，保留有界的逐次詢問；禁止的是 mode raise 與自動批准，不能聲稱批准後仍完全隔離。Task Service 的自動測試 runner（`task_verifier.py:ObservedVerifier`，含安裝依賴）不是 session 的 sandbox subprocess；只能用其既有 cwd／SSH 政策與已查核帳號解釋限制，不拿 session level 替它背書。

Task Service 若不能在既有 engine／recipe 下保持測試，這一包記錄 gap，README／Dashboard 明示尚未達成該任務的 A10。後續 engine／recipe 調整由另一工作包決定；不偷偷改模型、路由、測試命令、cache／HOME、安裝位置或選另一個 host。

Task Service 的 metadata 未包含權限欄位時只記 unknown，不改原 start／recovery／非 confined failover 行為；confined 的 resume／send 仍由共用 service guard 保持其原限制。Task Service 的新列保存既有 options／level；原 task 用 allow_all 就保持 none＋task_recipe_compatibility，不用改 policy 來讓測試過關。新 host confined 不悄悄改 task engine 的原行為；此例外只在既有 task-owned write point 內記證據，不新增外部 bypass 參數。

## Host account 宣告與只讀查核

新增 `HostConfig.confinement`，預設不宣告 account。以下都是範例值：

```toml
[hosts.buildbox]
managed_roots = ["/srv/batc-managed"]

[hosts.buildbox.confinement]
host_account = true
expected_uid = 2001
protected_roots = ["/srv/example-personal"]
check_max_age_s = 300
check_timeout_s = 10
check_max_entries = 10000
bat_port = 9876 # BAT 主機實際 listener port；SSH tunnel 本機 port 不是此值
```

沿用 `BATC_TASK_SETTINGS` 的 `[verification].ssh_hosts`，不加另一套 SSH credentials／alias。`host_account=true` 須有正整數 expected_uid、非空絕對 protected_roots 與 alias；禁止 protected roots 和 managed roots 重疊，禁止 root UID。`check_max_age_s` 須為正整數（最多 3600），預設 300。`check_timeout_s`（最多 30）、`check_max_entries`（最多 100000）及 `bat_port`（1–65535）也驗證為正整數；預設 10 秒、10000 entries、9876。讀取 claim 本身不授予 level。只讀 check 的結果參考同一 journal／inventory，新的 start 在副作用前重新查核，cache 不超過設定期限。

第一版實作 Linux POSIX 查核。SSH alias 必須直接以預期 BAT UID 執行，且能唯一觀測 BAT process 與所有已觀測 runtime descendant 的 UID／GID／supplementary groups。尚無 runtime 的 idle host 可通過；證據保存 `runtimes: []`，並加 `runtime_identity_inherited_unobserved`，表示未來子程序預期繼承 BAT 身分但尚未觀測。只讀指令使用既有 runner 的 `BatchMode` 與 timeout，不 `sudo -u` 模擬另一個人。alias 身分不符、看不到 BAT process、無法唯一對應該 BAT server、process namespace／群組不符，記 unknown，不能宣稱 host_account。

Account check 使用獨立 `SshGitRunner.run_account_check`，Git runner 原本的 `sh -lc` 不改。SSH 固定命令從 `/` 執行 `/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C /usr/bin/python3 -I -S -B - <JSON payload>`；不另啟 login shell，Python 不載入 user site、cwd import 或 PYTHON* 設定，不寫 bytecode。所有 find 都固定 `/usr/bin/find`，不透過 PATH 找程式。不新增 interpreter／find config keys。舊 checker 的 cache signature 失效，只能重新查核。

查核在 protected-root／process scan 前先證明 interpreter 的 realpath、stdlib 目錄、find、passwd 指定的 login shell 與各自所有父目錄為 root-owned，且 BAT UID／groups 不可寫。先以 effective-ID access 檢查 find 不可被替換，再以 GNU find -writable 核對 ACL；不可信時回 unknown／`check_executable_untrusted`，證據列 paths。Home 與 shell 只取 `pwd.getpwuid(expected_uid)`，不用 config／HOME。支援 sh／dash（.profile）、bash（.bashrc、.bash_profile、.bash_login、.profile）、zsh（.zshenv、.zprofile、.zshrc、.zlogin）；其他 shell 回 unknown／`login_shell_unsupported`。

Home 本身、.ssh 及其中全部 entries、.pam_environment 與以上 startup files 都不得由 BAT UID 擁有或可寫；owner 可 chmod，不能把當下只讀算安全。用 find -uid／-writable、相同 entry／time budget；缺檔只在 parent 不可寫時安全，home 的可替換 ancestors 也按 sticky-bit 規則查核。這些入口的 symlink 保守拒絕；不可信回 unknown／`login_environment_writable` 並列 paths。不掃 .claude／.codex／.cache 等正常 agent state 的內容。

**信任模型與 hardening 前置條件：** sshd 仍以帳號的 login shell -c 執行命令，可能先讀 .ssh/rc、bash／zsh startup 或 PAM environment。此同 UID check 只有在環境原本乾淨、再 harden 時才可信；它無法識別早已植入、之後變 root-owned 的惡意內容。主機操作者須從可信來源替換 home startup、.ssh 與 PAM 設定，確認沒有未信任 hook／environment，並把 home、startup files／.ssh 改成 root-owned 且 BAT 不可寫（也不得經 ACL／group／ancestor 替換）；interpreter、stdlib、find／shell 同樣使用可信系統版本。可預先建立由 BAT 帳號擁有的 .claude、.codex、.cache 等 state 子目錄；root-owned home 不阻止在這些子目錄內正常工作。本包只讀檢查，不代做 hardening，也不聲稱能從已被劫持的 shell 中證明乾淨。

固定 BAT 的 [src-tauri/src/sidecar.rs:4](https://github.com/teddashh/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/sidecar.rs#L4) re-export bridge；實際 `SidecarState` 位於 [src-tauri/crates/bat-agent-bridge/src/lib.rs:291](https://github.com/teddashh/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/crates/bat-agent-bridge/src/lib.rs#L291)。`call()` 在 371–390 行進入 `ensure_spawned()`，344 行才 spawn；因此不以「尚無 lazy sidecar」拒絕第一個 start。

查核腳本只讀 Linux metadata，不讀人的檔案內容、不建立 probe、不寫入、不 sudo。以 `find <root> -xdev -writable`（GNU find 的 access(2) 判定，涵蓋 ACL）配 entry／time budget，首個可寫 entry 即失敗。用 -printf 計數；另用 find 的 -uid 拒絕 BAT 擁有的 entries／祖先（owner 可 chmod，不能因當下不可寫而 pass）。跨 mount／symlink、列舉錯誤或 budget 用盡回 unknown，不重實作 mode／ACL 判定。Root 的父目錄／祖先以同 UID 查 writable 與 search，並按 sticky bit／owner 決定是否可移除 child。讀 `/proc/<pid>/status` 的 Uid、Gid、Groups、CapEff／CapPrm／CapAmb；三種 capability 任一非零均 mismatch。須能唯一識別該 BAT server 與已觀測 runtime、alias UID／groups 相符，不能只靠 process 名稱或 cwd。不同身分、無法識別或權限能力不明均 unknown；root／DAC override 為 mismatch。檢查前後的 canonical path／inode 與 process 身分須一致。讀取時有 entry/time 上限，cache 的上限不取代新 start 前核對。

此查核是時間點、指定 roots、目前觀測到的執行身分的證據。既有 SSH／BAT 不能完整證明未列出的所有私人資料夾、其他帳號、未來 ACL 改變、所有 hardlink 別名、遠端可寫服務、setuid／sudo／credential 可取得的權限，或之後產生的子程序都不換身分。這些列在 `limits`；有已知繞過途徑不能回 verified。不得以跑提權命令來驗證「不能提權」。不可觀測的部分由主機操作者維持帳號配置，不能改寫成工具已證實。

未宣告時跳過 check，選可達的 CLI 限制。已宣告但新 integrity 前置條件不足（上述三種 unknown reason）時，confined Claude 新 start 明示 gap，使用 plain default／prompt_gated，不送 acceptEdits，也不把宣告 roots 記成已保護；一般 default／allow_all 與 Task recipe 維持操作者既有 policy。其他 mismatch／unknown（roots 可寫、身分不符、budget／I/O 失敗等）仍回 `HOST_ACCOUNT_UNVERIFIED`。若 admission 曾 verified、已準備 host-account options，frame check 卻失去 verified，回 unsent refusal；不得把先前準備的 acceptEdits 送出去。macOS／Windows／SSH 登入為另一管理帳號的查核在本版為 unsupported，顯示原因；不假造 ACL 結果。

## 輸入／輸出與前置條件

不新增提升權限 API 或 raw SDK option 入口。Start 的 agent／workspace／instructions 沿用現有 action contracts；confinement 是後端從可信 host settings、任務身分、來源與 BAT 讀回產生的結果。呼叫者不得傳 `level`、`verified=true` 或解除 `write_scope`。

| 表面 | 新增輸出／既有入口 |
|---|---|
| Session reads | `service.sessions_list`／`session_read`、triage、`inventory`、`GET /api/v1/sessions` 與 `GET /api/v1/sessions/{host}/{id}` 的 session 列帶 write_scope、confinement、current_verification；MCP `sessions_list`／`session_read` 與 CLI `sessions`／`read` 同值。manual／unknown 不因加欄位取得寫權。 |
| `GET /api/v1/capabilities` | `hosts[].confinement`：`agents.{claude,codex}` 的 reachable_options、requested_level、verified_level、limits／gap；`host_account` 的 declared、status、checked_at、protected_roots、evidence_ref、reason。supported／unknown／unsupported 分開；不把 host 的 capability level 直接套到既有 session。 |
| Host reads | 既有 `hosts_list`／`host_status`、`GET /api/v1/hosts` 帶同一 account check 摘要。只讀刷新不新增 mutation action；離線回最後證據與 stale，不因 capabilities 載入卡住 Dashboard。 |
| Checkpoint／repair | `checkpoint-preview` 與 capabilities 提供所選 agent 的預計限制；`checkpoint.continue`／`integration.handoff` 的結果與 operation.external_refs 帶 confinement snapshot／evidence_ref。work item 的 `continueFrom` 也使用此摘要。 |
| 權限與 bulk | operations-unification 的 `session.permissions`／`session.approve_pending`；現有 `session_set_permissions`／`approve_pending`、CLI `permissions`／`approve-pending`。結果沿用 per-item，新增 skipped=confined 與穩定 error code；dry-run 也不顯示「would raise」受限列。 |
| Task Service | commands start payload 與 registry 保存 actual options 與 snapshot；`work_status`／task reads 顯示 session 限制與 task_recipe_compatibility gap，不改 engine_decision／recipe。 |

必要條件仍為 scopes、write／orchestrate tier、resource_policy 的來源與目的地檢查、穩定 session／worktree 身分。CLI sandbox 不把 legacy shared clone 變成 §07 的獨立 clone；本包不變更 shared_clone_worktrees 遷移政策，UI 仍同時列 isolation 與 confinement。

## 不可放寬與操作銜接

新共用 confinement helper 只決定 options、證據與是否放寬；沿用原 `WriteGrant` 與 task coordinator gate。一般新 start 的選項在 registry reservation 與 Task Service command payload 記下，不等 ACK 才記。Checkpoint／repair step request 保存 session ID、cwd、agent、write_scope，完整選項以同 ID 的 registry intent 為準；核對成功後在 operation external_refs 保存 snapshot。`registry_permission_fields()` 由實際送出的 options 生成，不能用空 `permission_options(default)` 清掉有效值。

- `write_scope=confined` 不可由 permission change 進 bypass／full-access、減少 protected_roots、開啟更寬的批准政策或移除其已記限制。`force`／confirm 不繞過；等價 default 要轉成該 session 原 options，只有真正不放寬的變更可送。
- Bulk 與 deferred raises 在列項時及送 frame 前重查受限旗標、最新 registry 與 task gate；舊的 pending raise 保留 refused 回執後清除，不在重啟後執行。單一 session refused 不阻止其他可操作列回報結果。
- 逐次回答仍是 `session.answer`；既有任意批准就可能越過 prompt／sandbox，UI 必須說明。Confined session 拒絕 `dont_ask_again=true` 的 session-wide allow 與會把 mode 改成較寬值的 ExitPlanMode answer；`deny`／AskUserQuestion 不因此被擋。單次 allow 不得更新 level 為「更安全」，並留下批准的限制說明。
- 兩份 skill 同步要求先讀 write_scope／confinement：受限 session 不要求 allow-all、不呼叫 raise、不用 bulk／dontAskAgain 消除限制，不批准寫往 protected_roots。合法測試被擋時，回報具體限制與待處理項，不自行改 host／engine／recipe。
- 權限閘門不能把不受限的舊 Task Service session 接管給低階 agent；操作權限與 confinement 是兩個累加檢查。

**與 operations-unification 相接處**：該包負責 ActionDef、HTTP／MCP／CLI adapters、scope／task authority gate、冪等與每個 BAT channel 的 step／reconcile。本包只在 `session_start`、`session_failover`、`session_set_permissions`、`approve_pending`／`_raise_deferred`、resume 與 BatAdapter start/recovery 的實際 frame 前插入 confinement 決策／核對，供它的 actions 共用。不得重寫上述函式的操作流程或再加第二個 Task Service gate。其 `session.permissions`／bulk 的任務 gate 和本包的不可 raise 必須兩者通過；任一拒絕，零 permission frame。

**與 cleanup／delivery 相接處**：cleanup 讀 registry／operation.external_refs 時保留 confinement snapshot／evidence refs，不藉 remove／rehydrate 重標 level。delivery 的 repair 仍經 `checkpoints.start_in_worktree` 取本包預設；`integration.py:_run_handoff` 只補結果 projection，不重構 delivery steps、PR／deploy policy。

## 實際副作用、失敗與升級

Phase 2 新增的副作用只有 Connector 記錄／projection、既有 managed start options 與經允許的既有 permission channels。Account check、capabilities 與來源 preview 是只讀。絕不代為建立帳號、改 ACL、改 BAT／CLI 全域設定、人的 checkout 或 deployment recipe。

| 情況／錯誤碼 | 行為與恢復 |
|---|---|
| `CONFINEMENT_RAISE_REFUSED` | 不送任何 permission frame；含 force／bulk／deferred／failover。回傳原 level、禁止放寬原因與 evidence_ref。 |
| `CONFINEMENT_UNSUPPORTED` | 所需限制在 host／agent 不可達；planner 或需保留前任限制的 successor 不啟動。一般工作可用已定義的較低候選 options，但明示 gap，不能用未知欄位碰運氣。 |
| `check_executable_untrusted`／`login_environment_writable`／`login_shell_unsupported` | Host evidence reason（非 operation error code）：unknown，列不可信 paths／shell；confined Claude 以 plain default 啟動，creation level 為 prompt_gated。無 verified account 絕不送 acceptEdits。 |
| `HOST_ACCOUNT_UNVERIFIED` | 宣告與 roots／process 查核不一致或無法完成，或 frame check 失去 admission 的 verified；新 start blocked。來源與既有工作不動；明確標記 sent=false，釋放 reservation，按 caller 的 retain_on_error 決定是否沿用原 rollback。Task start command 記 rejected、task 到 needs_ted 並記 code，不 retry／read-back。Checkpoint／repair 到 NeedsAttention，同 operation 在設定修正後重跑未送步驟。 |
| `CONFINEMENT_MISMATCH` | start 讀回／resume／permission reconcile 的 options 與意圖不同。停止新 prompt 派送，needs_attention；已 ACK 的 session 一律保留 reservation 與 worktree、記 uncertain 與 code。Start 初次讀回或 recovery 觀察到 mismatch 時保存原 creation record；其 verification=mismatch 為 terminal，下次在讀 BAT 前就拒絕，confirm 不覆寫；不能因稍後 options 相符而升級或送 handoff。非 confined 的未知 metadata 只記 unknown 並繼續；confined 的 unknown 仍拒絕。Reviewer 的未知 read 仍 best-effort；可讀 mismatch 則不得 promote／送 review prompt，command 與 task 按既有 acknowledged-but-unusable start 規則到 uncertain，原因記在 reservation 的 code／creation verification。不自動修改 live runtime 來掩飾。 |
| `FAILOVER_SUCCESSOR_MISMATCH`／`START_SESSION_MISMATCH` | 讀回的 cwd 與 reservation 不同。用 resource_policy.norm 的絕對 POSIX 路徑正規化，先比 cwd 再比 permission options；不以 Connector 本機 realpath 解遠端 symlink。記 terminal error_code、保留原 reservation／worktree，不 promote、不送 prompt／handoff、不重新 start。後續即使 cwd 修正也不自動恢復。Failover 用前者，session_start、checkpoint continue／integration handoff 與 Task Service start recovery 用後者。 |
| `CONFINEMENT_START_UNSETTLED` | 前次 successor start 未定，或 ACK 後尚未寫 active 就中斷，這次只讀回 reserved ID。須先證明 meta.cwd 和 reserved cwd 相符；cwd 缺失／無效時不 promote、不送 handoff，保留 reservation。cwd 相符且 options_confirmed／verified 時清 start_uncertain、active 並完成 confirm；保留 reserve 時的 cwd／worktree_path／branch／permission fields，與正常 ACK 路徑一致。若 handoff 的未送證據仍在，重建 prompt、沿用 message ID 與所有 Task Service callbacks／frame guards，走原 send 路徑並回 prompt_sent／message_id／error，不回 skipped。mismatch 用上列 code；unreadable／null 保留 reservation，不重送 start，也不把「未定」說成 options mismatch。Checkpoint／repair 的可讀 metadata 缺 cwd 時到 needs_attention；null／transport unreadable 沿用 step 的 uncertain retry。 |
| `CONFINEMENT_EVIDENCE_MISSING` | 已記 confined 的 session 在 meta=null 且遺失原 mode／policy、無可信 intent／回執可恢復時，不送 client-resume／cold resume；不可觸發 BAT 的 omission／bypass fallback。保留既有 session 與讀取，由操作者核對原證據；不把它重新 start 成新預設。loaded live session 的 send 不改 mode，不因 legacy 證據缺失而阻擋。另對升級時 in-flight checkpoint／repair 的 reservation 缺 confinement record，回 NeedsAttention，不無限讀回。 |
| Start／setter ACK 遺失 | uncertain；以同 session ID 讀 meta 和已記 intent。cwd 相同但 options 不明不能確認限制；不 start 第二次，不退回 allow-all。 |
| 首個 instruction 已 accepted，結果用的 evidence read timeout／disconnect | `start_in_worktree` 的 durable send step 保持 succeeded；回 registry 的原 creation evidence，current_verification=unknown、reason=readback_failed。Checkpoint continue／integration handoff operation 仍 succeeded，同 idempotency key 回同 operation；不重送 prompt、不重開 session。 |
| Codex 第二個 setter 失敗 | 保留各 step 的回執與不明狀態，逐項讀回，不重送已證明的 step；完成後及下一 turn 邊界再核對。沒有原子 sandbox＋approval 保證。 |
| Host offline／check stale | session read 回原快照＋current_verification=unknown；不偽裝 verified。不得用 stale account check 開新 session。 |
| BAT／CLI 更新或原生 GUI 改 mode | 原快照不動；current_verification unknown／mismatch，新的證據需重新查核／驗收。Connector 無法禁止 GUI，亦無法追回已被批准的 shell 寫入。 |

升級不遍歷 running sessions 送 setter、resume 或 stop。既有有完整 start intent／實際 options 的紀錄可以只讀回填證據；只有 cwd／tab／事後 host default 的紀錄填 none、reason=legacy_evidence_missing。現有 confined flag 保留，即使其實際 level 為 none；人工／unknown 資源不回填成 managed。之後補到較強 host 證據只更新 current_verification，不把建立快照升級；要採新限制，開新的 managed session。Warm reuse 同樣不升級。

Failover reserve 先保存 branch、permission fields、handoff_message_id（Task Service 用 journal 已保留的 ID）、handoff_status=pending 與明確的 handoff_frame_sha256=null。只有 pending＋明確 null 才證明未進入 frame 派送；缺 key 的舊 active row 不算。升級前仍在 start block 的 unsettled／starting row 尚未嘗試 handoff，可在 readonly read-back 成功時，以 registry flock 補 null 與缺失的 ID／branch；不得覆寫另一個恢復程序已記的 hash 或 ID。

session_start 在已知工作目錄後、start frame 前保存 cwd／worktree_path／branch，讓 ACK 遺失時也有原目的地。Checkpoint／repair 共用 start_in_worktree.restart；升級前尚缺 cwd 的 reservation 只能沿用原 session.start step 已持久化的 cwd，不採新的 host default 或 observed cwd。它們與 failover、Task Service reviewer poll／headless recovery 均在 promote 前核對原目錄。Creation permission mismatch 與 identity error 不由重試清除；只讀 session fields 仍可顯示 current_verification，不能因此改 creation snapshot。

Reviewer start 的 ACK 後 read 與 lost-ACK identity poll，都在 cwd check 後、active 前以原 requested options 核對可讀 meta。Mismatch 一次就保存 creation verification=mismatch／permission_options_changed 與 error_code=CONFINEMENT_MISMATCH，reservation 保持 uncertain，並在既有 start command payload 保存同份 evidence。沒有第二次 read 洗掉 mismatch，沒有 start retry、branch settlement、reviewer_session_id 或 review send intent。TaskCoordinator 沿用原 start failure 路徑：command／task 到 uncertain，因 BAT 已有該 session，不能當成 unsent refusal 釋放或到 needs_ted。recover_start 對 registry 或 journal 已記 mismatch 在讀 BAT 前回 False；後續 tick 保持 uncertain，不生成 review prompt。Unreadable／null meta 仍只記 unknown，不改變既有 reviewer activation 行為。

Task Service 的 promotion／第一個 prompt 邊界查核如下。一般 task 的 default／allow_all／recipe 不變；未知 options 仍明示 gap，不因這次修正新增 policy。

| 路徑 | 可讀 mismatch 的處理 |
|---|---|
| Lead `BatTaskAdapter.start` → `orchestrate.session_start` | 原 post-ACK ensure_confirmed 在 active／首個 prompt 前拒絕；保留 uncertain reservation 與 terminal creation record。下一次 start／recover_start 不重讀或重送。 |
| Reviewer `BatTaskAdapter.start` 的 ACK read／identity poll | 兩處都核對 cwd 與 requested options；保存 terminal mismatch、raise ConfinementRefused，不 active、不 settle start、不送 review prompt。未知 read 沿用 best-effort。 |
| `recover_start`／`_restore_headless_lookup` | 先拒絕 registry／journal 的 terminal record，再在 ensure_existing 前核對新的可讀 meta。Pending creation 首次 mismatch 保存至 registry（若仍在）與原 command payload；lookup 遺失時不重建 active。已確認 creation 遇到 live drift 保留原快照、拒絕本次恢復；有 lookup 時記 uncertain／code。 |
| Headless `session_presence`／TaskCoordinator 首個 `_send` | 共用上述 restore gate；mismatch 回 uncertain，不建立 send intent。不把 active lookup 或已存在 session 當作權限證明。 |
| Warm lead `_warm_identity` | 在 claim_warm 前核對原 creation options；可讀 drift 不提供／不 claim warm session，不撤銷舊 task capability、不改 creation snapshot。 |
| Task failover successor | lifecycle 的 post-start／reserved-start recovery 先核對 options 才 active；Task 的 _verified_failover_successor 另核對 creation options，before_handoff 與實際 frame guard 遇到可讀 drift 回 False／TaskIdentityMismatch，不送第一個 handoff。既有 mismatch record 在讀 BAT 前就拒絕；保留 journal／hash／ownership guards。 |

實際 handoff frame 在所有 async checks 後、transport 前以 flock 消耗 null 證據並記 SHA-256，再執行原 handoff_frame_guard；Task Service 仍核對 journal 的 prompt hash 與 ownership。pending／sent／uncertain 集合不新增值。讀回到 send 之間再 crash，null 仍在、下次可送一次；正常 ACK 到 active／handoff 之間的中斷也走同一恢復路徑。hash 已存在就永不重送，即使 crash 發生在 fence 與 transport 之間；pending 的此種結果記 uncertain，保留既有 prior-successor 回應。Codex 不依 clientMessageId 去重，不能把這個保守未定當成已收到 prompt。Start timeout／connection loss 同樣保留非 confined successor；一般 policy 仍不變，metadata 真 mismatch 或不可讀仍拒絕 read-back。

已寫入後的 evidence reads 查核如下；只為顯示證據的 read 不能讓已完成 operation failed。派送前的 identity／confinement／Task Service authority checks 仍須通過，不改成 best-effort gate。

| 路徑／read | 時點與處理 |
|---|---|
| `checkpoints.start_in_worktree` 最後的 `service._meta`／`session_fields` | durable send accepted 後的顯示證據。捕捉 timeout／disconnect／其他 read exception，保存 creation、current 標 unknown／readback_failed；operation succeeds。 |
| `checkpoints._run_continue`／`integration._run_handoff` 結果 | 取上述共用 helper 的 fields，不再必須讀 meta；continue 的 inventory refresh 已 suppress exception。Repair receipt 的本地 journal 寫入沿用原流程。 |
| `orchestrate.session_start` post-ACK `_meta` | 在第一個 prompt 前確認 start options；read exception 轉 None，non-confined 只記 unknown、confined 沿用原拒絕未知的 gate。ACK／reservation 不丟；結果用已記 record，accepted prompt 後不追加 evidence read。 |
| `lifecycle._failover_one` post-start `_meta`／結果 | 同上，read exception 不 orphan successor；confined 的 required options gate 在 handoff 前。Handoff 完成的 result 只回已記 record，沒有額外 evidence read。 |
| `BatTaskAdapter.start` reviewer post-start meta | 未知 read 為 best-effort；read exception 記 unknown／session_unloaded，仍 active。可讀但 cwd 或 requested permissions 不同則為必要拒絕，保留 reservation，非顯示證據失敗。 |
| `BatTaskAdapter.failover` 的 after-send `_verified_failover_successor` | 此為既有 Task Service journal／registry／worktree authority proof，非顯示 evidence read，保持原未知／不相符行為；也核對 creation options 的可讀 drift，不能用此修正略過 Task gate。 |

Journal schema additive：confinement_host_checks 在每次 open 以 CREATE TABLE IF NOT EXISTS 建立，不占 user_version，不需要 data migration。其餘 migration 沿用各工作包版本。利用原 commands／operation_steps／sessions_observed 的 JSON 與 evidence refs，不重建 task tables。registry 增 schema_version／confinement 欄位，missing 值按上述保守規則解讀。不改 delivery 的 2／3 或 observation 的 4 migration。

## Dashboard、文件與預計修改檔案

Session card 與 detail 同時顯示 level、write_scope、Git isolation；可展開 actual options、來源、檢查時間、目前核對狀態與 limits。Checkpoint continue、work item continueFrom、repair form 在選 agent 時更新預計限制，unknown／gap 要可見；後端結果取代預估值。表單的提示不是「只能寫自己的資料夾」。不新增使用者必須自行調整 SDK options 的流程。

兩種語言最低共用字串如下；每個限制原因另以 key 翻譯，不能印出 null／undefined：

| key／語意 | zh-TW | en |
|---|---|---|
| level `host_account` | 主機帳號限制（指定目錄） | Host account restriction (listed roots) |
| level `os_sandbox` | OS sandbox 選項（尚未實機驗收） | OS sandbox options (live acceptance pending) |
| level `prompt_gated` | 工具詢問；批准後可越界 | Tool approvals; an approval can allow access outside the folder |
| level `none` | 無已證實的執行寫入限制 | No verified execution write restriction |
| options confirmed／OS unverified | 已核對 sandbox 選項；OS 阻擋尚未驗收 | Sandbox options confirmed; OS enforcement not yet tested |
| account check unknown | 帳號宣告尚未查核／查核不完整 | Account claim unchecked or check incomplete |
| Task Service gap | 保留既有測試流程；本任務限制不足 | Existing test workflow preserved; this task has a confinement gap |
| confined policy | 禁止提升權限與批次批准 | Permission raises and bulk approvals are disabled |

預計 Phase 2 修改；Phase 1 只提交本文件：

| 檔案 | 最小變更 |
|---|---|
| 新 `src/bat_agent_connector/confinement.py`、`config.py` | 共用 options／不可放寬判斷、evidence schema、HostConfig 宣告、只讀查核。使用現有 runner，不新增可寫 channel。 |
| `orchestrate.py`、`lifecycle.py`、`service.py`、`registry.py` | 各入口、reserve／resume／permission／failover 保持限制與證據；修 registry_permission_fields 缺口。不重構 operations-unification 的流程。 |
| `task_bat.py`、`task_journal.py` | start／recovery／warm／reviewer 保存證據；migration；Task Service 相容缺口，不改 engine／recipe／verifier 命令。 |
| `checkpoints.py`、`integration.py` | start read-back 核對限制、preview／result projection。 |
| `inventory.py`、`triage.py`、`api_v1.py` | Session／host／capabilities projections、只讀 freshness、同一 evidence schema。 |
| `api_actions.py`、`mcp_server.py`、`cli.py` | 沿用統一 operations；暴露結果與穩定拒絕，沒有 bypass action。 |
| `dashboard/app.js`、`app.css`、`i18n.js` | cards／detail／checkpoint／repair forms、en 與 zh-TW；沿用 fill()、CSP 與 live-update hold 規則。 |
| `skills/bat-agent-connector/SKILL.md`、`skills/hermes/bat-agent-connector/SKILL.md` | 同步讀證據、不要求受限 session raise；修正 acceptEdits 說法。 |
| `README.md`、`README.zh-TW.md`、`CHANGELOG.md` | 設定、限制與缺口，連到本文件；unreleased entry 引計畫 §06／§07／§12、A10。 |
| `docs/PROTOCOL.md`、`docs/design/checkpoints.md`、`resource-policy.md`、`integration.md`、`api-v1.md`、`dashboard.md`、`task-service.md` | 引固定 source 可達欄位；更正 A10／acceptEdits 描述，更新各自「尚未涵蓋」但保留尚未實機驗收、Task Service gap。 |
| `tests/mockbat.py`、`tests/test_confinement.py`（新增）、`test_checkpoints.py`、`test_lifecycle.py`、`test_task_service.py`、`test_api_v1.py`、`test_config.py` | 下列 mock、失敗恢復與 projection 驗證。 |

## A10 測試計畫

Mock 只能證明 Connector 的 options、gate、evidence 與顯示；不假造 Claude／Codex 的檔案 sandbox。所有人路徑是 fixture，例如 `/srv/example-personal/source`；不送 real-host 寫入 channel。用 `tests/mockbat.py`、checkpoint 的 `LocalRunner`／`RealGitLog` 與 temp repos。

| 驗收／計畫 | 實作測試 | 結果與邊界 |
|---|---|---|
| A10；§06、§07、§12 | `test_host_account_refusal_before_frame_releases_start`、`test_task_start_refused_before_frame_needs_ted_not_uncertain`、`test_checkpoint_continue_host_account_refusal_needs_attention_and_resumes` | 明確 unsent refusal：零 start frame、釋放 reservation、按 retain_on_error rollback；task rejected／needs_ted 與 code；同 operation resume。 |
| A10；§06、§12 | `test_general_start_unreadable_meta_records_unknown_and_keeps_session`、`test_post_start_mismatch_keeps_reservation_and_worktree`、`test_reviewer_start_meta_failure_still_activates`、`test_post_start_cancellation_keeps_acknowledged_reservation` | ACK 後不釋放 session；non-confined unknown 可繼續、真 mismatch 保留 uncertain；reviewer best-effort。 |
| A10；§06 | `test_confined_failover_unsettled_successor_reads_back_before_new_attempt`、`test_host_check_table_is_created_without_consuming_schema_version`、`test_legacy_codex_predecessor_uses_its_recorded_agent`、`test_checkpoint_reconcile_legacy_reservation_requires_evidence` | Successor confirmed／mismatch／unreadable／null 的 readonly recovery；vanished 尚缺可信 absence signal。高版本 journal 補 table 不占版本；legacy agent 辨識與缺證據停在 needs_attention。 |
| A10；§06、§12 | `test_manual_failover_recovered_start_sends_reserved_handoff_once`、`test_task_failover_recovered_start_preserves_journal_and_frame_guards`、`test_recovered_failover_row_matches_normally_confirmed_successor` | Manual confined／allow_all 的 lost ACK／post-start evidence failure；Task Service 沿用 reserved message ID、before_send 重記 hash、原 identity／frame guards 通過、after-send verification=True。只送一個 handoff；恢復後 row 除 timestamps 外等同正常 successor。 |
| A10；§06、§12 | `test_failover_crash_before_handoff_keeps_durable_unsent_proof`、`test_failover_crash_after_start_ack_before_activation_recovers_handoff`、`test_failover_attempted_handoff_is_never_resent`、`test_legacy_unsettled_failover_backfills_proof_without_resetting_a_frame` | Read-back 到 send 之間與正常 ACK 到 activation／handoff 的 crash，可用原 ID 重建 prompt；frame 已嘗試則保持 uncertain、永不重送。Legacy start-only row 可補證據，較晚的 read-back 不清已記 hash／ID。 |
| A10；§06、§12 | `test_failover_recovery_checks_reserved_cwd_before_promotion`、`test_acknowledged_start_checks_reserved_cwd_before_promotion`、`test_reviewer_readback_checks_reserved_cwd_without_retrying_start`、`test_checkpoint_start_readback_refuses_identity_and_terminal_mismatch`、`test_handoff_start_readback_refuses_identity_and_terminal_mismatch` | 不同 cwd 保留 reservation、terminal identity code、零 prompt／handoff、不 promote；缺 cwd 保持 unsettled；正規化相同的 cwd 可恢復。Start／checkpoint／repair／reviewer 共用檢查，無追加 reviewer start frame。 |
| A10；§06、§12 | `test_failover_recorded_permission_mismatch_is_terminal`、`test_checkpoint_start_readback_refuses_identity_and_terminal_mismatch`、`test_handoff_start_readback_refuses_identity_and_terminal_mismatch` | 初次 post-start 或 recovery 記 mismatch 後，matching metadata 也不重新讀取、覆寫或 promote；creation record 不變、零 handoff，confined／allow_all 同樣 terminal。 |
| A10；§06、§12 | `test_checkpoint_accepted_send_survives_evidence_read_failure`、`test_handoff_accepted_send_survives_evidence_read_failure` | Timeout／disconnect 都在首個 send accepted 後發生；operation succeeded、creation 不變、current unknown／readback_failed，僅一個 start／prompt frame，同 key 回同 operation。 |
| A10；§06、§12、§28 | `test_reviewer_permission_mismatch_keeps_task_uncertain_without_prompt` | Codex danger-full-access／Claude bypassPermissions 取代原 read-only／plan；ACK 與 lost-ACK poll 都只一次 read 就拒絕。Reservation uncertain／CONFINEMENT_MISMATCH、creation terminal、command／task uncertain、零 review prompt／send intent；matching meta 或 lookup 遺失後的 recover_start 仍不讀 BAT。 |
| A10；§06、§28 | `test_reviewer_matching_readback_still_activates`、`test_reviewer_start_meta_failure_still_activates` | Claude／Codex matching ACK／identity poll 仍 active；unreadable meta 仍 active、unknown／session_unloaded，不改既有 best-effort 行為。 |
| A10；§06、§12、§28 | `test_task_lead_start_mismatch_never_sends_initial_prompt`、`test_task_headless_start_mismatch_never_promotes`、`test_task_failover_options_mismatch_blocks_first_handoff`、`test_bat_warm_reuse_claims_only_clean_completed_service_session` | Lead／reviewer 的 reserved／headless recovery、pending／confirmed creation 分開；已確認快照不被 live drift 改寫。Lead start、warm claim 與 failover post-start／before-handoff／frame checks 均拒絕 mismatch，零第一個 prompt，不新增 engine／recipe policy。 |
| A10；§06、§12 | `test_a10_checkpoint_absolute_path_carries_confinement`（Claude／Codex） | 摘錄含人的絕對路徑；options／flag／level、拒絕 force raise、bulk skipped、來源零寫入。 |
| A10；§06 | `test_a10_general_start_preserves_operator_policy_and_records_evidence`、`test_a10_confined_start_preserves_stronger_explicit_claude_mode`、`test_a10_level_requires_options_not_cwd` | default／allow_all／confined 的 options／level；explicit plan／dontAsk 不放寬；相同 cwd 不決定 level；os 最多 options_confirmed。 |
| A10；§06、§12 | `test_a10_accept_edits_requires_verified_account_and_checks_are_read_only`、`test_a10_declared_unverified_account_blocks_new_start` | 未查核 account 不送 acceptEdits；宣告失敗不降級 start，零 start／worktree frame。 |
| A10；§06 | `test_a10_raise_and_deferred_raise_are_refused`、`test_confined_sessions_stay_confined_on_an_allow_all_host` | force、dry-run、舊 pending raise、bulk 與 failover 保持限制。 |
| A10；§06、§12 | `test_a10_loaded_legacy_send_works_but_missing_evidence_resume_is_blocked`、`test_a10_resume_uses_original_options_not_stale_tab`、`test_a_lost_start_reply_is_read_back_not_started_again`、`test_a10_lost_confined_start_ack_retains_options_and_worktree` | loaded legacy send 不受缺舊證據阻擋；null meta 的 confined resume 須原 policy；lost ACK 不重開。 |
| A10；§06、§07 | `test_a10_planner_is_read_only_never_and_successor_preserves_limits`、`test_relay_to_bat_session_starts_a_new_worktree_instead`、`test_fanout_from_planner_starts_verbatim_and_cleans_planner`、`test_c03_handoff_resolution_resumes_without_recomposing_or_receiving_twice` | 真正的 planner／relay／children／repair starts 保存 evidence；successor 不丟原限制。 |
| A10；§06、§28 | `test_a10_task_service_keeps_engine_policy_and_reports_gap`、`test_a10_task_failover_records_missing_options_without_changing_engine`、`test_reviewer_start_polls_existing_session_after_start_timeout`、`test_bat_restart_null_meta_and_worktree_never_creates_replacement`、`test_claude_sessions_pin_opus_55_for_lead_and_reviewer`、`test_bat_warm_reuse_claims_only_clean_completed_service_session`、`test_headless_session_lookup_restored_from_task_branch_and_bat_meta` | Engine／recipe／verifier 行為不變；Task Service 的 gap 與原 snapshot、warm/recovery 證據；metadata 缺欄位／重開 journal 不增加 engine 阻擋。 |
| A10；§06、§07、§12 | `test_account_check_remote_command_is_isolated_and_git_runner_unchanged`、`test_account_integrity_rejects_account_controlled_check_inputs`、`test_account_integrity_accepts_root_owned_nonwritable_layout`、`test_account_integrity_unknown_uses_plain_default_never_accept_edits`、`test_account_integrity_gap_at_frame_never_sends_prepared_accept_edits` | Synthetic passwd/home/executable layouts；absolute isolated command、不可替換 interpreter/find/stdlib/parents、owner/ACL/SSH/startup 入口、缺檔 parent、unsupported shell、未知 gap fallback default；第二次查核失去 verified 時零 start frame。Git SSH 不變，無 fleet host／真 home 寫入。 |
| A10；§06 | `test_a10_linux_read_only_scan_uses_find_and_process_identity`、`test_a10_host_account_cache_expires_without_upgrading_creation`、`test_a10_closed_host_evidence_journal_returns_unknown`、`test_a10_host_account_configuration_rejects_uncheckable_claims`、`test_a10_host_evidence_migration_is_idempotent_and_persists` | Linux /proc 身分、capability、實際 GNU find 的可寫 fixture／symlink／readonly owner 的 chmod 出口、父目錄、budget／timeout／process 不明、stale 與 journal 不可讀；不寫 probe。Exec fixture 只替換其 pathlib import，保留真 Path；Python 3.10／3.11 也跑完整 suite。ACL 使用 find 的 access 判定，完整 ACL host matrix 留 W12。 |
| A10；§06 | `test_a10_partial_permission_ack_preserves_creation_and_reports_drift`、`test_a10_start_mismatch_stays_uncertain_and_never_sends_prompt`、`test_a10_frame_guard_catches_drift_after_first_read`、`test_a10_creation_snapshot_survives_runtime_drift_and_send_refuses` | Partial setter ACK／GUI drift／start mismatch 保留快照並顯示 current；受限 drift 不送下一 prompt。 |
| A10；§06 | `test_a10_persistent_and_exit_plan_approvals_are_refused` | dont_ask_again、ExitPlanMode mode raise 被拒絕；deny／一般問題仍走原流程。 |
| A10；§10、§19 | `test_a10_session_capabilities_inventory_and_triage_share_evidence`、`test_a10_cached_legacy_inventory_exposes_unknown_evidence_without_rewriting` | REST／service／inventory／triage 一致；既有 MCP／CLI 直接轉出同 reads。manual readonly 不變。Dashboard Playwright fixture：en／zh-TW、390／768／1440 px、session card 與 checkpoint／repair forms 切 agent、無 null／undefined／[object／水平 overflow。 |

Mock 與只讀 fixture 只能證明 options／gate／證據，不能宣布 A10 的實機阻擋通過。完成須跑 `uv run ruff check .`、完整 `uv run pytest -q`、`.mjs` 的 `node --check` 與雙語 Playwright。Host check table 的 DDL 每次 open 執行、idempotent，不更動 user_version；既有高版本 journal 缺 table 也可補齊。

## 交給 W12 的實機驗收程序

這是書面交付程序，本工作包不連實機做寫入。只在專用驗收 host／repo 執行；由主機操作者提供測試帳號、managed clone 與 SSH alias。人的既有 folder 永遠不作 write target；它們只可供上述 account metadata check。

1. 記錄 Connector commit、BAT serverVersion／來源版本、實際 CLI 版本、OS、session preset、SSH／BAT／CLI 身分、options、managed roots 與 network 狀態（無法讀到就記 unknown）。確定測試 host 沒有共用人的可寫工作區，停用本次 bulk auto-approve。
2. 操作者在專用測試 parent 建一個唯一的 `batc-a10-<random>` **目錄**，canonical path 必須位於所有 managed roots 外，且和 protected 個人 roots 完全不重疊。Sandbox 案例也須在 CLI 實際准許的其他 writable roots 外；不能使用 CLI 可寫的 temp／cache parent 來宣稱越界。不得用人的 home／repo 當 parent。先用 `mktemp -d`／`realpath` 證明 ownership 與位置，記錄 inode；只在這個目錄建立 `sentinel.txt`（固定內容）及預備 `new.txt` 的路徑。
3. Sandbox／prompt-gated 測試：目錄對 BAT UID 可寫，先由操作者以同 UID 在此測試目錄做一次寫入正向控制並還原 sentinel，確認失敗不是 host DAC。Host-account 測試：改用另一個專用 fixture owner，於本次專用目錄內另建 parent／target，讓 BAT UID 可只讀列舉但不可寫；測試 target、其 parent 與可替換的祖先都必須阻擋 BAT 的寫入／刪除。所有 chmod／chown 都限本程序建立的專用 fixture，不改既有 parent 或個人資料夾。透過同身分 metadata check 證明文件／目錄／parent 的 deny，記錄結果。
4. 用專用來源 session／temp repo 建 checkpoint。摘錄放入這個 **測試目錄**的絕對路徑，指示「用 Write／Edit 改 sentinel，再用 shell 改 sentinel、建立 new.txt、rename／刪除 sentinel」。從 checkpoint 開新的 managed Claude／Codex session；記錄 start intent／meta／confinement 與 operation ID。另在 managed worktree 指示寫一個測試檔、跑既有小測試並 commit，驗證限制仍能完成正常工作。
5. Prompt-gated 不批准越界詢問；保存工具名稱、input、pending／deny 結果。os_sandbox 保存真正的拒絕錯誤／runtime log，不能以 agent 自稱「沒寫」代替；on-request 的批准出口未使用。測 host_account 時，在這個專用 fixture 的測試請求可由操作者逐次批准，仍須被帳號權限拒絕，證明批准不改 DAC。Claude file tools 與 shell 分開驗證，不能只測 shell 就掩蓋 acceptEdits 缺口。
6. 對新的受限 session 測一次 allow-all／force、approve-pending dry-run／apply 與 deferred raises；應 refused／skipped，零 raise frame。驗證 failover successor 的 policy 不變；不靠切換 agent 逃出限制。resume／daemon restart 後讀回原 level 和 actual options；null／不明保持 uncertain，不自動再啟動。
7. 操作者在同一測試目錄只讀比對 sentinel digest／inode、new.txt 不存在與目錄 entries；任何寫入、刪除、rename 成功都判該宣告失敗。若只看到待詢問，最多證明 prompt_gated，不能給 os_sandbox。若 CLI 不可觀测 sandbox 拒絕，記未證明。network 沒有測／不能設定時保持 unknown，這次檔案測試不升級成網路隔離。
8. 留存帶 timestamp 的開始選項、meta、拒絕 log、讀回指紋、正向測試結果、批准／raise 拒絕與清理結果，連到 W12 的 A10 run；證據匯入格式及可信 evidence file 由 W12 工作包定義。遮蔽真實 host／person paths 後才產生可公開報告。不同 BAT／CLI／account／policy 的證據不可混用；host-account 的 DAC 失敗不可代作 sandbox 的正向控制／拒絕證據。
9. 操作者停止測試 session，按既有 managed cleanup 流程整理測試 worktree。只移除第 2 步保存的專用目錄：先核對唯一命名、canonical parent、owner／inode 與無 mount／symlink 替換，再清理已知 fixture entries 與空目錄。不能對 prompt 回傳的任意路徑執行 recursive remove；個人 roots 全程沒有 probe，亦不做清理。

A10 的通過紀錄必須注明 level／機制與批准限制。`none`、只有 options_confirmed、或 Task Service 相容缺口都不是實機驗收通過。prompt_gated 只證明未授權的工具請求被擋，不能宣布帳號或 OS 永久阻擋；完整保護須相符的 os_sandbox／host_account 測試證據與上列界線。

## 尚未涵蓋

- 更強的獨立 trusted account 查核：經 `sudo -n -u <bat> <python> -I -S -B -` 執行，可避開 BAT 帳號的 login startup。此包不新增 credentials／sudo 路徑。現有同 UID 查核不能偵測 hardening 前已植入、後變 root-owned 的 payload；可信替換與乾淨部署由主機操作者保證。

- 舊 active successor 的 pending 若沒有明確 null frame fence，不能證明未送，保持原 prior-successor 行為；不回填成可重送。Reserved start 沒有可比對的 permission options 時，仍無法得到 options_confirmed，維持 CONFINEMENT_START_UNSETTLED；不為 handoff 恢復而假造證據。已記 frame hash 的 crash 結果只保證不重送，不證明 BAT 收到 prompt。
- Failover 的 vanished proof 待釐清：既有 BatTaskAdapter.session_presence 對 null 一律 uncertain，claude:list-sessions 列 SDK history；無 tab 的 headless／unloaded session 也可存在。不得以 missing tab／null 或 history 缺項釋放可能仍在跑的 successor。已有唯讀 read-back 可恢復相符 successor，其餘保持 unsettled；需可信 host absence signal 才可重新 start。固定 BAT 的 [remote_server.rs:3174](https://github.com/teddashh/better-agent-terminal/blob/b7419892fbc9946799b64cca24c2ec8c7fa15c42/src-tauri/src/remote_server.rs#L3174) 以 cwd／agentKind 呼叫 list_sessions_native；不提供完整 live local-session-ID 清單。
- W12 的 sandbox_evidence_file 設定、可信證據匯入、其檢查與測試延後；schema 保留 verified，但本包不把 OS sandbox 標為 verified。
- 真 host 的 BAT／CLI 版本、OS sandbox 實際 roots／network 與實機阻擋尚未驗收。W12 要提供可核對同 runtime 的證據；沒有證據的主機保持 gap。
- Task Service 的 allow-all engine／recipe 如何改成更強限制且保留測試，屬後續決策。這裡只保存現況與限制不足，不修改 §28 禁止增加的模型／recipe 政策。
- 需主機操作者確認哪些 protected_roots 構成完整的私人寫入邊界、SSH alias 是否同 BAT UID。無法從現有 BAT protocol 取得完整身分或全域不可提權證明。
- macOS／Windows 的 account／ACL 查核；任意 SDK sandbox、Codex writable roots／network 的 BAT pass-through；容器／新 runner／BAT 上游改動，都不在本包。
- 原生 GUI、逐次批准與其他主機服務的外部寫入不可由 Connector 全面禁止。`cwd`、managed clone、skill 指示與任何單次檢查都不稱為完整永久保護。
