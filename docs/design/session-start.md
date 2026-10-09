# Durable standalone session start

`session.start` is the standalone R01 action. It uses the existing central
`OperationService`, `start` scope, registry start claim/cap, resource policy and
confinement evidence. It neither creates nor adopts a task. Task submit, failover,
relay, fanout and merge retain their existing contracts.

## Request and identity

`POST /api/v1/operations`: action `session.start`, target `{host, workspace}`;
params `agent` (Claude/Codex), optional original `prompt`, `model`, `title`, and
`use_worktree` (default true). This slice refuses false at admission with
`START_WORKTREE_REQUIRED`: a new standalone SID does not prove exclusive ownership
of an existing task/manual/shared folder. Internal coordinator/checkpoint starts
keep their established authority. The legacy flag remains available to return this
explicit refusal; it never falls back to raw BAT. Unknown fields, caller session/task IDs, cwd overrides
and preconditions are refused. A canonical request needs an explicit literal
idempotency key. Replay checks caller scope and the original request hash before
resolving the workspace again. The compatibility RPC/MCP `session_start` and CLI
`start` retain `confirm=true`, host tier and independent no-key calls; they submit
the same action, never start another daemon or fall back to direct BAT writes.

Read-only `workspaces_list` / `GET /api/v1/workspaces` require `observe`, return a
bounded configured-host listing, and expose no write authority. Workspace selection
accepts an exact ID/name or one unambiguous legacy substring. The first durable
resolution fixes the full workspace ID/folder, Git root/branch/full commit, generated
session ID and start options. Recovery never reselects by name. The original prompt
is stored unchanged; no planner-generated replacement is inserted.

## Effects and recovery

Each external effect has a separate intent/receipt: `worktree.create`,
`session.start`, optional `workspace.register`, and optional `send`. Local registry
reservation/confirmation is recorded separately and bound to the operation ID.
Before each new frame, recheck cancellation, configured write/orchestration tier,
fixed policy, absence of task ownership and exact registry/workspace/Git binding.
The client identity-read path is used while a write owns its semaphore, including
when max_in_flight is one. Existing manual-root/shared-clone policy still applies;
`use_worktree=false` remains refused until a reviewed shared-folder authority contract exists.

BAT worktree creation uses its existing branch selection contract. The fixed source
branch/commit is checked before creation and the created worktree HEAD must equal
that commit before starting. Drift fails closed; it never silently starts another
revision. External BAT/GUI/Git clients are not governed by Connector's lock; the
read/check-to-frame race is not an atomic cross-client transaction.

A persisted transport fence distinguishes positively unsent calls from unknown
outcomes. A lost worktree reply requires matching BAT worktree identity plus Git
read-back; missing evidence never authorizes another create. A sent start requires
exact session/cwd/confinement read-back; it is never resent. A known created carrier
is retained after positively unsent failure or cancellation. Creation ownership
alone does not prove that no other session, new commit or uncommitted result now
uses it, so this action never removes worktrees or branches. The original durable
source/reservation/creation receipts remain available for canonical reviewed cleanup;
retention itself grants no cleanup authority. External consumers remain subject to
cleanup's existing fresh dependency, content and final-frame checks.

Completed receipts replay without new write authority. Local registry projections compare the original operation/incarnation and owner under the registry flock; they do not overwrite a later binding. Positively unsent cancellation records a failed reservation and retains its known carrier for reviewed cleanup; unresolved external effects retain capacity.

Tab registration remains append-only with the existing GUI save race limitation. A detected loss of previous workspace identities stays an explicit sticky conflict; it is never repaired by another save.
Lost tab ACK needs exact terminal identity read-back; an uncertain tab blocks later
effects. A first prompt uses a fixed operation message ID and no automatic client
resume. Positive ACK, its saved operation-generated accepted-turn record, or the exact Claude user-message echo proves acceptance;
Codex metadata/text similarity does not. Unknown send never resends. A partial
projection retains `started=true` and `prompt_sent=null` when start is known and
the prompt is unproven. It never claims the whole start failed merely because a
later effect is unresolved.

B2 managed artifact lineage accepts this action only after successful completion,
matching operation-owned reservation/start identity, and a positive initial-send
receipt with its exact generated message ID. A prompt-free start is not execution
evidence. Acceptance still does not mark work done, merged or deployed.

## Validation layers

Focused tests use actual central HTTP/RPC admission, MockBat frames and temporary
Git repositories. Cover scope/key replay and no-key isolation; malformed/reserved
inputs; cap/manual/task/cleanup policy; per-frame owner/policy/workspace/commit drift;
max_in_flight=1; worktree/start/send lost ACK and restart; positive-unsent retention of new consumers and committed/uncommitted results;
tab identity; original prompt; partial projection; and B2 lineage. Native or live
host/provider acceptance is separate evidence, not implied by these fixtures.

Protocol shapes reuse the repository’s [BAT 3.2.12 source table](../ORCHESTRATE.md)
(`src-tauri/src/commands/worktree.rs`, `remote_server.rs`,
`node-sidecar/src/handlers/claude-session.mjs`) and
[pinned protocol/permission notes](../PROTOCOL.md). No new BAT channel is introduced.
