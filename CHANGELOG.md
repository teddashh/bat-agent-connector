# Changelog

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
