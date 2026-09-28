# Hermes → BAT Task Service cutover plan

Status: design only; this document does not enable the cutover.

## Target topology

Run `batc serve` as a `systemd --user` service on `grok-bot-01`, bound only to
`127.0.0.1` (the task API and MCP endpoint). Hermes talks to the loopback task
API; it does not receive BAT credentials or call BAT directly. Castle1/OpenClaw
traffic reaches the service through an SSH forward, for example
`ssh -N -L 127.0.0.1:18796:127.0.0.1:18796 grok-bot-01`, with the forward
restricted to the intended operator account and host key.

The rules engine remains the default. Goose 1.52.0 is opt-in per task via the
submit engine/provider fields, with the task-scoped MCP server as its only
extension. Discord publishing remains disabled for the canary unless explicitly
enabled for Ted's board.

## Hermes tool contract

Hermes switches from ad-hoc BAT/crons to these task-scoped calls:

- `work_submit`: create a durable task with project, acceptance, base branch,
  engine, and idempotency key.
- `work_status`: inspect state, verification/review evidence, and metrics.
- `work_pause` / `work_resume`: stop or resume automatic dispatch without
  losing journal state.
- `work_result`: retrieve the bounded result, candidate commit/tree, reviewer
  outcome, and verification evidence.

Hermes should display `needs_ted` and `uncertain` as operator states, never
replay a prompt, and use command-scoped reconciliation only when Ted explicitly
chooses it.

## Installation and staged enablement

1. Install the pinned connector and dependencies on grok-bot-01.
2. Install a user unit such as `batc-task.service` with `Restart=on-failure`,
   a private `StateDirectory`, `NoNewPrivileges=yes`, and loopback-only bind.
3. Store host/profile references and provider configuration mode `0600`; keep
   BAT tokens outside TOML. Run `systemctl --user daemon-reload` and start the
   service manually for preflight.
4. Verify `work_submit → work_status → work_result` on a no-op repository task,
   then enable Hermes' rules-engine route. Goose remains an explicit per-task
   opt-in until its ACP/reconciliation metrics meet the canary gate.
5. Enable the 24-hour canary at 10% of eligible low-risk tasks, then 50%, then
   100% only if the gates below hold.

## Disable old paths

During the cutover window, disable (do not delete) the `bat-watch-*` timers,
`bat-watch-*` services, and the `idle-push` cron/script path. Preserve their
unit files and last logs under the rollback directory. Disable duplicate
Discord publishers so one task cannot produce both a legacy notification and a
board update.

Discord board events should point to Ted's task threads, with unresolved board
messages remaining pending until the task service observes delivery. Do not use
Discord as the source of truth; the SQLite WAL journal is authoritative.

## 24-hour canary metrics and gates

Record per task and engine: submitted, accepted, delivered, `needs_ted`, and
`uncertain` counts; p50/p95 time-to-deliver; verification duration/timeouts;
review rejections; interventions; session replacements; duplicate/idempotency
attempts; Goose/AGY request and quota counts; and token usage when available.
Sample every state transition and retain the task ID, candidate commit/tree,
review marker, and verification command evidence.

The canary gate is: zero prompt replays, zero unreviewed deliveries, no stalled
verifying tasks, 100% base-commit attribution, and no unexplained increase in
uncertain session starts/sends. Pause rollout on any credential leak, cross-task
MCP access, or Discord/journal disagreement.

## Rollback (<5 minutes)

1. Stop Hermes' task-service route and `systemctl --user stop batc-task.service`.
2. Re-enable the previously disabled `bat-watch-*` units and `idle-push` cron,
   then verify their health/status output.
3. Repoint castle1/OpenClaw to the old local route or remove the SSH forward.
4. Leave the WAL journal and canary worktrees intact; do not replay uncertain
   prompts. Export the journal/metrics and reconcile only with Ted's approval.
5. Confirm one legacy dry run and announce the rollback; investigate before a
   second cutover attempt.

## Ted prerequisites

None for the planned installation if the existing grok-bot-01 systemd user,
castle1 SSH identity, BAT profile, and Discord board credentials remain valid.
Ted is only needed for an explicit uncertain-command reconciliation, a canary
gate override, or a rollback decision after a policy/security alert.
