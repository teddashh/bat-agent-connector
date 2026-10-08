# Changelog

## Next release (unreleased)

- Checkpoints no longer call BAT's `git:status` on the person's checkout: BAT runs a plain `git status`, which can
  rewrite `.git/index`, and answers `[]` on failure. Uncommitted changes are counted over SSH with
  `git --no-optional-locks status`, or reported as not observed (`dirty: null`); `dirty` is a count, not a bool.
  Source reads go through the inventory's read-only fleet. A lost `session.start` reply is only started again when
  no registry reservation exists (a null session meta no longer counts as proof), and a lost first instruction to
  a Codex session is settled from its transcript. New: `GET /api/v1/sessions/{host}/{id}/checkpoint-preview`,
  `checkpoints/{id}?live=true` (`source.advanced`), `started_from` on the session read, MCP `checkpoint_preview`,
  `checkpoint_create`, `work_continue_from_checkpoint`, CLI `batc checkpoint`, and a commit picker and note in the
  Dashboard. The Dashboard no longer requests `/favicon.ico`.

- Checkpoints (docs/design/checkpoints.md): `checkpoint.create` records any session's commit, branch, uncommitted
  change count and a fixed conversation excerpt through read channels only; `checkpoint.continue` builds a
  connector-owned clone under the first managed root (its origin is the source's origin, never the person's
  folder), adds a worktree and branch at that commit over the host's SSH alias, starts a managed session there,
  checks BAT sees that commit, and only then sends the first instruction. New reads `GET /api/v1/checkpoints`,
  `GET /api/v1/checkpoints/{id}` and MCP `checkpoints_list`; the Dashboard's session page records checkpoints and
  starts work from them.
- Browser Dashboard at `/dashboard/` on the task daemon's loopback port (docs/design/dashboard.md): pending items,
  the session inventory with provenance and staleness, managed-session send (queued behind a running turn),
  interrupt and answer, a read-only view for sessions a person created in BAT, PR merge and merge-and-deploy
  buttons, and the operation log with deploy retry from the merged commit. Four static files with no build step,
  a strict CSP, and a client of `/api/v1` only.
- GitHub delivery operations (docs/design/delivery.md): `github.pr.merge` merges at the reviewed head SHA through
  the asynchronous merge API (waits on pending checks and merge queues, adopts a matching pending request,
  records the real merged SHA by reading the PR back), `deployment.start` runs a configured `[[deploy.recipes]]`
  workflow or tracks the run a merge started and only reports deployed when the recipe's deploy job succeeded,
  and `delivery.merge_and_deploy` keeps the merge when the deploy fails so only the deploy is retried. Lost
  replies are settled by reading GitHub back. New read `GET /api/v1/repositories/{owner}/{repo}/pulls/{n}` and
  MCP `github_pr_preview`.
- `/api/v1` on the task daemon (`batc serve`), sharing its loopback listener, journal and owner lock
  (docs/design/api-v1.md). Durable operations (`session.send`, `session.answer`, `session.interrupt`) with
  actor-scoped idempotency keys, steps whose intent is committed before the BAT call, and `uncertain` outcomes
  settled by read-back instead of resending (a lost send reply is found in BAT's transcript; a cancel waits for the
  read-back; `needs_attention` operations can be resumed with `POST …/resume`, `operation_resume` or
  `batc op ID --resume`). API tokens per actor and scope (`batc api-token`); the actor always
  comes from the token. A persisted session inventory refreshed through a read-only fleet, with keyset paging,
  `stale` rows for unreachable hosts and `gone` after two misses. One persistent event cursor (`api_events`) for
  tasks, operations, sessions and hosts, with SSE and `Last-Event-ID`. New MCP tools `operation_submit`,
  `operation_get`, `operations_list`, `operation_cancel`, `inventory_sessions`, `inventory_hosts`,
  `events_list`, `capabilities_get` and CLI `batc op`. MCP operation writes need `confirm=true` and the client's own
  `BATC_API_TOKEN`; they never run as the local admin.
- Sessions a person created in BAT are read-only through every tool. A new resource policy
  (`resource_policy.py`, docs/design/resource-policy.md) classifies sessions as `manual`, `connector_managed` or
  `unknown`, checks that a managed session's folder is one the connector owns (a `managed_roots` folder or a
  worktree it created) and re-reads BAT's session folder, worktree and git root before each write. The client core
  refuses any write frame without a policy grant, so send, continue, answer, interrupt, resume, permissions,
  approve_pending, relay, failover, stop, rehydrate, merge, remove and cleanup are all covered; override flags do
  not bypass it. Refusals carry a code (`MANUAL_READ_ONLY`, `WORKDIR_NOT_MANAGED`, `BINDING_MISMATCH`,
  `DESTINATION_MANUAL`, ...).
- Behaviour changes: `session_relay` targets the workspace's most recent connector-managed session and, with
  `start_if_missing`, starts a new worktree session instead of writing to a person's session; failover only continues
  connector-managed sessions (`all_exhausted` lists the others under `skipped_read_only`, outside the per-call cap);
  `worktree_merge` and cleanup merges only target the main checkout recorded at start, inside `managed_roots`
  (otherwise `DESTINATION_MANUAL` / `BINDING_MISMATCH` / ESCALATE); the fan-out planner runs in its own worktree;
  `session_start` refuses `use_worktree=false` outside a managed root and any managed-root destination whose git
  root resolves elsewhere; cleanup keeps (never stops) BAT sessions and connector sessions left in a human checkout.
- New host settings `managed_roots` and `shared_clone_worktrees` (default true: worktrees may still be created
  inside a human clone, which shares its refs). New read tool `session_policy` / `batc policy`; `sessions_list`,
  `sessions_triage` and `worktree_status` rows carry `provenance` and `api_access`.
- Every task is one Goose session on Opus 5.5 (switch off by default). The `goose-session` recipe
  prompt tells Goose to split once, aim for Grok 4.7 : Codex : Opus 5.5 = 4:2:1, and give no new work
  to a model at or below 15% weekly remaining; that is prompt guidance, not something the service
  enforces or measures. The service no longer routes per step, starts an independent reviewer, or
  fails over mid-task. Trusted-test failures return to the same session for bounded rework. A
  continuation does not create a task. Jev runs only when an orchestrator passes `executor_model`
  for already-split work.
- Routing decisions now start the BAT agent they name. Sessions use the host's actually available
  agents in Ted's order: Claude Opus 5.5 (pinned `claude-opus-5-5:auto-compact-300k`, offered only
  while the host usage snapshot is fresh and under 85%/90%), then Codex. The reviewer is the other
  model family from the lead when possible; a reviewer that hits its usage limit falls back to the
  next provider instead of counting as a review. `provider_usage` records real session starts and
  quota hits. AGY `claude-opus-4-6-thinking` is not a BAT runtime and is not started.
- Warm session reuse requires the current HEAD to equal the previous task's verified commit and is limited to
  follow-ups in the same workstream (`parent_task_id`, or `continuation=true` in the same origin thread);
  independent requests start fresh from base.
- Status separates `verified` / `adopted` / `merged` / `deployed` (`delivery` block); the last three come only
  from `work_mark_stage` records. `work_submit` stores optional `context_refs` (attachments, previous message
  id, plan, commit). New read-only `python -m bat_agent_connector.gate_eval` calibration table for the minimal
  Jev gate; gate reservations now record diff size and paths. The 0.50 threshold is unchanged.
- No model calls where code already knows the answer: `work_status`/`work_result` are plain journal reads;
  PM provider choice is explicit rules by step type and stakes (no Jev classification or confidence); the
  advisory candidate pre-screen is removed; minimal submit uses rules directly when it is the only runnable
  engine (Goose live gate closed) and asks Jev only when both engines can run.
- Trusted verification runs under one deadline (start, drain, exit) in its own process group; a
  timeout kills the group and, over SSH, the remote `setsid` group, and must confirm it is gone.
- Verification has two clocks: last meaningful progress (idle budget per recipe) and an absolute cap
  (3x) from the start of the verifying phase; `updated_at` heartbeats no longer extend it.
- A trusted-test code failure goes back to the lead with a redacted output tail for bounded rework;
  missing dependencies get one lockfile install and a retry; environment problems go to Ted.
- The task service no longer knows about chat delivery. The Discord publisher, its per-event outbox columns,
  the board table and `batc task-delivery` / `work_delivery_*` are removed; opening an older journal drops the
  outbox (`events.discord_status`, `events.discord_message_id`, `board`) so the old backlog can never be posted.
  New read-only milestone feed: MCP `work_events(since_cursor, limit)`, RPC `work_events`, CLI `batc task-events`.
  Transitions into `needs_ted`/`failed` now store the reason on the event.
- Milestones are pushed to an optional generic loopback JSON webhook (`[task_service.event_webhook]`), signed with
  HMAC-SHA256, in order, retried with backoff; `work_events` stays as catch-up.
- Task review verdicts are structured: only the reviewer's final message counts, and it must carry
  `{"verdict","candidate_commit","tree_hash","findings"}` for the exact candidate. Missing, invalid,
  conflicting or mismatched verdicts, and PASS with high-severity findings, become bounded rework.
  Lead `BAT-STATUS` is read from the last marker of the final agent message only.
- The direct-send fence reads the running daemon's actual journal (`task-service.json` pointer) and
  refuses sends/answers to task-owned sessions whose state cannot be read.
- The minimal task path, with a typed Jev candidate review gate, can be made the daemon's default by
  setting `BATC_TASK_DEFAULT_PATH=minimal`; without it the default stays `standard`. An explicit
  `task_path` on `work_submit` (`"standard"` for the full-review path) overrides either default.
- Claude turn markers now use BAT's exact `clientMessageId` echo (`batc-<uuid>`), with an explicit
  timestamp cursor and conservative queued-turn phases. Codex is labeled as a timestamp fallback
  because BAT does not echo that ID; Codex sends are not automatically retried after a disconnect.
- Failover successor reservation is atomic per source session and worktree. The old session is
  cleaned only after the new handoff is acknowledged.
- Automatic cleanup requires an explicit passing verification record for the current clean commit.
  `session_record_verification` / `batc record-verification` capture command, exit code, environment
  and log reference. Jev and `BAT-STATUS` remain completion claims, not test evidence.
- In-process writes now serialize per host. The remaining GUI workspace-save race and cross-process
  ownership limits are documented in `docs/design/next-gen-connector.md`.

## 0.2.4 (unreleased)

- Turn markers: `session_send` and `session_relay` return `turn_marker` / `after_ms` (the host-side id and
  timestamp of the message just sent; fallback: the newest host timestamp before the send). `session_wait` and
  `session_read` take `after=<turn_marker>` (CLI `--after`). With it, `session_wait` returns only once the
  session has replied after that send (`done` / `event`, `turn_done=true`): a stale idle state, or the end of an
  older turn that the send was queued behind, no longer counts, and a timeout reports whether the turn started.
  `session_read` shows only messages newer than the marker and hides the live streaming tail until the new turn
  has produced output, with a note not to report older messages as the result. Callers that read right after
  relaying could otherwise pick up the previous task's last reply.

## 0.2.3 (unreleased)

- Relay mode: `session_relay` (CLI `batc relay`) forwards the human's message verbatim, followed by an optional
  brief clearly labeled as the relaying assistant's interpretation (goal, context, constraints, acceptance
  criteria). The session is told that the original is the source of truth, to fix unclear or suboptimal asks using
  its own judgment and the project plan, to state its interpretation in one line, and to ask only when the ambiguity
  is genuine and consequential. Earlier thread messages can be included verbatim. `[client] human_name` /
  `relay_name` set the names used. With no session in the workspace it reports `no_session`, or starts a Codex
  session in the main checkout when `start_if_missing=true`.
- Session-planned fan-out: `session_relay(request_fanout=N)` asks the session for a ```` ```bat-fanout ```` JSON
  plan; `fanout_plan_session` starts a read-only Codex planner in the main checkout when the main session is busy
  or quota-stopped; `fanout_from_plan` starts one worktree per planned task with the prompt unchanged and cleans up
  the planner. The relaying assistant never writes the plan.
- Status markers: sessions are asked to end every stop with `BAT-STATUS: MILESTONE <name>`, `CONTINUE <next step>`
  or `NEED-<HUMAN> <reason>`. Triage and cleanup prefer the marker over heuristics (MILESTONE counts as a completion
  claim, CONTINUE keeps the session, NEED escalates).

## 0.2.2 (unreleased)

- Merge gate is language-independent: Jev's "claims completion" question says the final output may be in any
  language (e.g. Traditional Chinese) and that `task` may be empty, and a deterministic backstop lifts the score to
  0.9 when the final output has a done/committed phrase (en or zh-TW/zh-CN, e.g. 已完成 / 已提交 / 全部通過), names a
  commit SHA and reports no blocker (尚未 / 需要你 / should I ...). Jev's diff verdict is still required.
- The final output used by the gate skips BAT's own system notices.
- Cleanup rebuilds an empty branch diff commit by commit and file by file (new read channel `git:diff-files`).
  BAT's `worktree:status` / `git:diff` return an empty diff when git prints more than a pipe buffer (~64 KB),
  because the host reads the child's stdout only after it exits; large branches then reached Jev with no diff.
- The diff secret check ignores obvious placeholders (alphabet/digit runs, `example`, `your-...`, repeated chars),
  e.g. fake webhook tokens in unit tests.

## 0.2.1 (unreleased)

- Cleanup decision `ESCALATE_TO_TED` is now `ESCALATE` (the old name is accepted as an alias).
- Per-host `codex_model`: default model for Codex sessions started or failed over on that host.
- `session_failover(instructions=..., archive_only=...)`: custom handoff steps, and successors whose branch cleanup
  keeps but never merges (to preserve superseded work).
- Fix: `worktree_remove` (and cleanup) re-registers the worktree with BAT before removing it and verifies the folder
  is gone. BAT's `worktree:remove` reports success without doing anything when its worktree manager has no record
  for the session (e.g. a failover session that reused an existing worktree).
- Cleanup treats a host timeout as KEEP (retry on the next sweep) instead of ESCALATE; `worktree:status` gets 90 s.

## 0.2.0 (unreleased)

- **Triage**: `sessions_triage` / `quota_sessions` / `batc triage` / `batc quota` classify sessions (quota exhausted,
  transient rate limit, waiting for permission/answer, working, done, error) with evidence and reset time.
- **Quota failover**: `session_failover` / `batc failover` continue a quota-stopped Claude session in Codex, in the
  same worktree when there is one, with a handoff prompt. Idempotent and capped.
- **Permissions**: per-host `default_permission_mode` (`default` | `allow_all`); `session_start` and failover apply it;
  `session_set_permissions`, `approve_pending`, and `session_answer(dont_ask_again)`. Claude sessions are never
  switched mid-turn.
- **Automatic cleanup**: `session_cleanup` / `batc cleanup` with MERGE_AND_CLEAN / CLEAN_ONLY / KEEP /
  ESCALATE_TO_TED decisions behind hard gates, per-host `auto_cleanup`, branches always kept, one escalation summary.
- **Optional Jev judgment** (`[jev]`, off without `TYPESAFE_API_KEY`): refines ambiguous states and gates merges;
  fails open for triage and safe (escalate) for cleanup. Credential-looking strings are redacted from anything sent.
- Newly allowed channels: `git:log`, `git:diff` (read); the three permission-mode setters (write);
  `claude:stop-session` (orchestrate, used only by cleanup on idle sessions).

## 0.1.0 (unreleased)

- First version. It has three tiers:
  - **read**: hosts, workspaces, sessions, reading, waiting, and worktree status. It is always on.
  - **write**: send, continue, interrupt, and answer. It is off by default and turned on per host.
  - **orchestrate**: start a worktree session, merge, and remove a worktree. It is off by default, turned on per host, and needs the write tier.
- Connections pin TLS to the host certificate and use v2 authentication only.
- An audit log records every write, and writes are rate-limited.
- Includes the `batc` CLI, the `bat-agent-connector-mcp` MCP server (stdio or loopback HTTP), and an agent skill.
