# Managed artifact capture / acceptance (B2)

Issue #59, base `b80225d476bc99ec2e9e1bb9be0041fb15353120`. This extends the
existing [artifact store and B1 capture](artifacts.md), not execution authority.
Manual capture remains a separate read-only source contract. No frontend or live
acceptance is claimed by this backend change.

## Fixed central evidence

`POST /api/v1/artifact-managed-capture-previews` requires `observe` and an
authenticated API credential. The body contains `host`, full `session_id`, one
safe `relative_path`, and exactly one selector: `execution_operation_id`, or
`task_id` plus `command_id`. A selector is not evidence. The server must prove:

- Current workspace/registry creation evidence and positive live metadata classify
  the exact session and folder as managed. GUI tabs are optional; conflicting tabs
  are refused, while headless sessions require the same live cwd/root evidence.
  Missing, retired, uncertain or manual sources are refused. Metadata cwd must
  match the registry folder; Git must resolve inside its owned boundary.
- An execution operation is a succeeded supported execution action with an
  accepted durable send receipt for this host/session incarnation. Initially
  supported: `checkpoint.continue`, `integration.handoff`, `session.send` (also
  used by legacy continue). A task-owned execution additionally needs its central
  command binding. Arbitrary operation IDs and work-item links do not prove it.
- A task selector identifies an accepted `send` command in this journal, bound
  to the task's current host and session and the registry's task ownership.
  Its positive journal event must postdate that incarnation; the reservation may
  precede the session start, as in an existing failover handoff.
  A client cannot supply a commit, arbitrary lineage document or creation proof.

The preview binds central lineage, registry creation/folder identity, observed
runtime identity, host configuration, actual Git HEAD and bounded single-file
bytes/hash/identity. It uses the existing credential-bound signed preview (ten
minutes), read slots and strict no-follow helper. The source is rechecked before
and after every read; bytes and HEAD must match the original preview exactly.
The captured bytes may be uncommitted: HEAD is observed context, not a claim that
the bytes are tracked at that commit or were authored exclusively by one agent.
No source writes, chmod, status refresh, snapshot, stop or execution occur.
External writers are not locked; the existing observable-change limits apply.

## Actions and recovery

`artifact.capture.managed` requires `manage` plus `observe`. Its target is
`{preview_id}`, params `{preview_token}`, preconditions `{expected_fingerprint}`.
Manual and managed preview tokens cannot cross actions. Replay/resume/cancel
require the original credential and both scopes without re-expiring an accepted
preview. The existing reserve/receive/verify/publish/record steps produce one
immutable ArtifactRef. A completed receive receipt plus exact staged/published
bytes permits recovery without re-reading a removed or changed source. A failed
or unknown read can only re-read the same fixed source; it cannot switch inputs.
No start/send mutation is part of capture, and no uncertain host mutation is
resent. Source proof is `kind=managed_capture`, with central lineage and actual
commit/hash; upload/manual capture cannot acquire that label through parameters.

`artifact.accept` requires `approve`. Target is `{artifact_id, revision}`;
params are `{digest, source_fingerprint, receipt}`; preconditions are empty.
`receipt` is non-empty bounded review text (maximum 2000 characters), not a
provider or test verdict. Admission requires a ready managed capture with an
exact central capture receipt and accepted execution lineage. Before recording,
the immutable store bytes and saved source evidence must still match. It never
re-reads the live source, which may legitimately have advanced or been cleaned.
One atomic journal transaction records actor, operation ID, exact ref, source
fingerprint, lineage, observed commit and review text, plus an observation event.
Its idempotent local effect replays the existing receipt after a lost response;
later content loss cannot erase an already recorded acceptance. A new key is a
separate review receipt, never an overwrite. Artifact GET exposes acceptances.

Acceptance does not change an artifact's bytes/latest revision, work item
fingerprint/state, task state, PR/merge or deployment. It does not prove test
success, execution completion, OS enforcement or production readiness. Approval
scope is rechecked on replay/resume/cancel. No additional numbered data migration
or second store is introduced; acceptance DDL is additive and idempotent.

## Verification and surfaces

HTTP/RPC/MCP/CLI are thin central adapters. MCP requires its explicit API token;
no fallback to an admin credential. CLI preserves its existing confirmation and
read-only guard. Existing operation tools handle fixed keys/recovery. Capabilities
advertise the supported source selector types and managed capture/accept actions.

Tests use actual temporary Git and binary bytes through the fixed helper, plus
MockBat and the real operation journal. Cover forged/wrong/uncertain lineage,
changes to the session incarnation, owner, folder, HEAD and file; scope and
credential restrictions; restart and lost replies during capture and acceptance;
exact old revision
acceptance after later revisions, corrupt originals, and no task/work completion.
Existing B1 regressions remain required. Full integrated CI, installed clients
and live-host acceptance are separate evidence layers.
