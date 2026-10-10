# Hermes → BAT Task Service cutover plan

Status: generic deployment guidance. This document neither enables a cutover nor
records a particular installation. The operator supplies the private inventory,
accounts, credentials and rollout policy.

## Target topology

Run one task-service owner for a state directory. Bind its control API to loopback
and let integration clients use the authenticated task interface. A remote client
may use an explicitly configured, authenticated tunnel; restrict its endpoint,
operator identity and host key. Do not expose BAT credentials to a chat relay or
start an independent daemon with a copied journal for each client.

An installation may supervise `batc serve` with the operating system's service
manager. Service identity, private state paths and restart policy are deployment
configuration, not public repository defaults. Keep host/profile references and
provider credentials out of source control.

Goose is optional and controlled by `BATC_GOOSE_ENABLED`, off by default. Enabling
it requires the pinned runtime contract checks in [task-service.md](task-service.md).
A model name or successful mock test is not proof of a working live provider.

## Hermes tool contract

The integration uses the existing task-scoped calls:

- `work_submit`: create a durable task with project, acceptance, base branch and
  an idempotency key; preserve the user's original words.
- `work_status`: inspect state, verification/review evidence and recorded metrics.
- `work_pause` / `work_resume`: stop or resume automatic dispatch without losing
  journal state; resume first reconciles unresolved commands.
- `work_result`: retrieve the bounded result, candidate commit/tree, review
  outcome and verification evidence.
- `work_events`: read committed milestone events using a durable consumer cursor.

Display the compatibility status `needs_ted` as requiring operator attention.
Display `uncertain` as an unresolved result; never replay its prompt. Command-scoped
reconciliation requires an authorized operator's explicit evidence and decision.
The legacy identifiers remain unchanged for API and journal compatibility.

## Installation and staged enablement

1. Install compatible, pinned connector and optional executor versions in an
   isolated configuration. Keep a rollback copy of private configuration and state.
2. Configure one service owner, a private state directory, loopback control API
   and authenticated clients. For a user service, select appropriate process
   restrictions such as `NoNewPrivileges` and a supervised restart policy.
3. Configure host and provider references with owner-only permissions (or the
   equivalent Windows ACL). Keep token values in the supported credential store.
4. Verify submit, status, pause, resume, events and result using a synthetic task.
   Check ownership, idempotency, disconnect recovery and credentials before
   enabling a real integration route.
5. Enable only the chosen low-risk workload, then expand under an operator-defined
   observation window and explicit acceptance gates. No rollout percentage or
   schedule is implied by this document.

## Disable old paths

Inventory any existing submitters, timers, watchers and external publishers before
cutover. Disable duplicate writers and publishers while preserving their private
configuration and logs for rollback. Do not stop an active writer merely to replace
an integration; let it finish or cancel and confirm termination first.

The task journal is authoritative. The connector publishes committed milestone
events; the integration that owns the external chat service delivers notifications
and saves its cursor only after success. Do not turn a notification failure into a
second task or assume a posted chat message proves execution.

## Canary metrics and gates

Record submitted, accepted, delivered, operator-attention and uncertain counts;
delivery latency; verification duration/timeouts; review rejection; intervention;
session replacement; and duplicate/idempotency attempts. Report token, cost or quota
information only when a verified source supplies it. Unavailable provider data
must stay unavailable.

The gates are zero prompt replays, no unreviewed deliveries, bounded verification,
exact candidate attribution and no unexplained increase in uncertain starts/sends.
Pause rollout for credential exposure, cross-task access, conflicting ownership or
external reports inconsistent with the journal. Retain task, command and candidate
references in private evidence, not public operational transcripts.

## Rollback

1. Stop new submissions from the new integration and pause automatic dispatch.
2. Account for each in-flight command. Preserve unresolved intents; do not replay
   an uncertain prompt through the old route.
3. Stop the task-service owner if required and confirm its process has exited
   before changing state-directory ownership or starting a replacement.
4. Restore the previous integration configuration and its authorized access path.
   Re-enable only one writer and one publisher per task.
5. Leave the journal, worktrees and private evidence intact. Verify a synthetic
   dry run and investigate the failed gate before another cutover.

## Operator prerequisites

The operator chooses the service account, host inventory, authentication, provider
configuration, source integration and acceptance policy. Availability of those
resources is not assumed. The operator also owns uncertain-command adjudication,
policy overrides and deployment acceptance; the public project does not embed an
individual's machine layout, chat destinations or maintenance schedule.
