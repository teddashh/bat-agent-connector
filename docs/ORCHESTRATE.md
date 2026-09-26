# Orchestrate tier: parallel worktree sessions

Off by default. Enable per host with `writes = true` **and** `orchestrate = true`.

## What BAT 3.2.12 does (upstream source)

| Channel | Behaviour | Source |
|---|---|---|
| `worktree:create {sessionId, cwd, installPnpm}` | Host finds the git root of `cwd`, creates `<root>/.bat-worktrees/<8 hex>` on a new branch **`bat/worktree-<8 hex>`** (host-chosen, collision-proof; a client cannot pick the name), adds `/.bat-worktrees/` to `.git/info/exclude`, links untracked `.claude/` files, copies local env files, records the fork point in `branch.<name>.bat-fork-head`. State is kept in host memory keyed by `sessionId`. | `src-tauri/src/commands/worktree.rs` `create_worktree_native`, `allocate_worktree_slot` |
| `claude:start-session {sessionId, options}` | Codex when `options.agentPreset` is a codex preset (`codex-agent`, `codex-agent-worktree`), else Claude via the Node sidecar. For worktrees the GUI passes `cwd` = worktree folder plus `useWorktree:true, worktreePath, worktreeBranch`. The host registers the session for notifications. | `remote_server.rs` (`should_handle_codex`), `node-sidecar/src/handlers/claude-session.mjs` (`applyWorktreeOptions`) |
| `worktree:status {sessionId}` | `{diff, branchName, worktreePath, sourceBranch, merged, mergedKind}`; `mergedKind` is `ancestor`/`patch-equivalent` (merged), `ahead` (source is an ancestor: conflict-free), `diverged`, or `unknown` (no new commits). `null` if the host lost its in-memory state (e.g. restart) until `worktree:rehydrate`. | `worktree_status_native`, `compute_merged_kind` |
| `worktree:merge {sessionId, strategy}` | In the **main checkout**: refuses if dirty, `git checkout <source>` if needed, then `merge --no-ff --no-edit` (or cherry-pick). A conflicting merge is not aborted. | `merge_worktree_native` |
| `worktree:remove {sessionId, deleteBranch=true}` | `git worktree remove --force` (falls back to `rm -rf` + prune) and `git branch -D` when `deleteBranch`. | `remove_worktree_native`, `force_remove_worktree` |
| `worktree:rehydrate {sessionId, cwd, worktreePath, branchName}` | Re-registers a worktree in host memory (also re-copies local env files into it). | `rehydrate_worktree_native` |
| `claude:cleanup-worktree` | Deletes the branch by default. **Not exposed.** | `remote_server.rs` |
| `claude:start-session` with `options.worktreePath` of an existing worktree (codex preset) | The host **reuses** that worktree for the new session (no new folder), keeps its branch, copies env files without overwriting. Used by failover. | `ensure_worktree_for_session_native` |
| `claude:stop-session {sessionId}` | Unloads the runtime session; the transcript stays and it can be resumed. | `remote_server.rs` |
| `claude:set-permission-mode`, `claude:set-codex-sandbox-mode`, `claude:set-codex-approval-policy` | Change a live session's permissions. A Claude query not launched with bypass cannot be raised mid-turn: the sidecar then closes the live query, ending the turn. Codex applies it via `thread/resume` for the next turn. | `claude-session.mjs`, `codex_app_server.rs` |

### Does a started session appear as a GUI tab?

No. BAT tabs are entries in the host's workspace document (`workspace:load`). The GUI creates the worktree, adds a
terminal entry and calls `workspace:save` with the **whole** document; the Claude/Codex session is started later when
the panel mounts. `claude:start-session` alone creates a running session with no tab, so neither the GUI nor
`workspace:load` show it.

The connector therefore:

1. tracks orchestrated sessions in a local registry (`~/.local/state/bat-agent-connector/orchestrated.json`); all
   read/write tools resolve them, `sessions_list` shows them with `orchestrated: true, has_tab: false`;
2. optionally (`orchestrate_register_tabs = true`) appends a tab using an append-only helper: load, add exactly one
   terminal (nothing else changes), re-load and abort if the document changed meanwhile, save, re-load and verify all
   previous workspaces/terminals are still present. BAT has no compare-and-swap, so a narrow race with a concurrent
   GUI save remains; see SECURITY.md. Connected GUI clients receive `workspace:reload` and show the new tab.

## Connector tools

| Tool | Tier | Guard rails |
|---|---|---|
| `worktree_status`, `session_worktree_status` | read | Only reads (`worktree:status`, `git:status/branch/getRoot`). |
| `session_start(host, workspace, agent, confirm, prompt?, model?, use_worktree=true, title?)` | orchestrate | `confirm`, per-host cap `orchestrate_max_sessions` (default 4) counted from the registry, hourly write cap, audit. Rolls back the fresh worktree if the session fails to start. Custom branch names are not supported by BAT 3.2.12. |
| `worktree_merge(host, session_id, confirm)` | orchestrate | Merges only if `mergedKind == ahead`, session idle, worktree clean, main checkout clean **and already on the source branch** (so BAT never switches branches there). Otherwise returns the reason and changes nothing. Never forced. |
| `worktree_remove(host, session_id, confirm, delete_branch=false, allow_unmerged=false, discard_uncommitted=false)` | orchestrate | Refuses if the session is streaming, if the worktree has uncommitted changes (unless `discard_uncommitted`), or if `delete_branch` and the branch has unmerged commits (unless `allow_unmerged`). The session itself is not stopped. |
| `batc fanout PLAN.md [--start ...]` | CLI helper | Splits a markdown plan (`- [ ]` items, numbered items, `##` headings) into task prompts; `--start` needs `--confirm` and is capped by `max_start_per_call`. |

| `session_failover(...)` | orchestrate | Only for sessions classified `quota_exhausted` (unless `force`), never while streaming; one successor per session (registry `failover_of`); `max_start_per_call` for `all_exhausted`; the old registry entry becomes `superseded`. |
| `session_cleanup(...)` | orchestrate | Dry run by default; acting needs `confirm` **and** host `auto_cleanup = true`. Gates below. |

## Quota failover

BAT has no "quota exhausted" field. The connector detects it from the limit text Claude writes into the transcript
("You've hit your … limit", "usage limit reached|<epoch>", "… resets <time>") and treats 429/overloaded messages
as transient. Only ambiguous cases are sent to Jev when it is configured. The Codex successor is started with the
`codex-agent-worktree` preset and the old `worktreePath`/`worktreeBranch` (same folder, same branch) or, for a
main-checkout session, `codex-agent` in the same folder. Its first message is a handoff prompt: original task, latest
instruction, recent output, git state (branch, dirty files, commits, diff stats) and the quota evidence.

## Automatic cleanup gates

`session_cleanup` evaluates every orchestrated session (and failed-over Claude sessions) and decides:

| Decision | When |
|---|---|
| `KEEP` | Streaming, waiting for a permission/answer, quota or transient limit, idle for less than `min_idle_s`, worktree shared by another active session. **Never stops a session that is mid-work.** |
| `CLEAN_ONLY` | Superseded by a failover successor that is running; archive-only successor (see below) that is idle and clean; worktree already merged or removed; no new commits and no diff; main-checkout session whose final output Jev confirms as finished. Stops the agent, removes the worktree with the branch **kept**. |
| `MERGE_AND_CLEAN` | All hard gates pass: idle, worktree clean, `mergedKind == ahead` (conflict-free, via `worktree_merge` never-force semantics), main checkout clean and on the source branch, last test run not failed, deterministic risk checks clean (no credential-looking additions, no secrets/infra paths, no large deletions or huge diffs); **then** Jev must confirm the final output claims completion (≥ 0.8), the diff is `safe_complete` (≥ 0.7), and, if no test run was seen, that tests passed. Merges locally, removes the worktree (branch kept), stops the agent. |
| `ESCALATE` | Uncommitted changes, diverged branch, dirty main checkout, failing tests, risk-check hit, Jev unavailable/unsure. Collected into one `escalation_summary` line per call. |

`ESCALATE_TO_TED` (the 0.2.0 name of `ESCALATE`) is still accepted as an alias by `normalize_decision`.

**Preserving superseded work.** When a session's work is superseded but its uncommitted changes should not be lost,
fail it over with `force`, `archive_only=true` and `instructions` such as "only commit everything on the current
branch with message …; do not build, test, push or merge". The Codex helper commits in the same worktree; cleanup
then stops the old session, removes the worktree and keeps the branch, and never merges it.

Every decision and action is appended to the audit log with its reasons. Branches are never deleted by cleanup, so a
merge or removal can be undone from the branch. BAT's remote protocol has no push, tag or PR channel: merges stay in
the host's main checkout, and pushing or opening a PR is left to the host's own workflow.

## Suggested workflow

1. Read the plan; split it into independent tasks (`batc fanout PLAN.md` gives a first cut; edit it).
2. Start one worktree session per task (`session_start` / `batc fanout --start`), within the caps.
3. Monitor with `sessions_list` and `session_wait`; answer questions only when you are sure.
4. Review each branch: `session_worktree_status(include_diff=true)`, `session_read`.
5. Merge the clean ones with `worktree_merge`; for `diverged` branches ask the session to rebase first.
6. `worktree_remove` merged worktrees (branch kept unless you ask), or let `session_cleanup` do steps 5-6 behind its
   gates. Report results to the user.
