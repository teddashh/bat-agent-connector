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

## Suggested workflow

1. Read the plan; split it into independent tasks (`batc fanout PLAN.md` gives a first cut; edit it).
2. Start one worktree session per task (`session_start` / `batc fanout --start`), within the caps.
3. Monitor with `sessions_list` and `session_wait`; answer questions only when you are sure.
4. Review each branch: `session_worktree_status(include_diff=true)`, `session_read`.
5. Merge the clean ones with `worktree_merge`; for `diverged` branches ask the session to rebase first.
6. `worktree_remove` merged worktrees (branch kept unless you ask). Report results to the user.
