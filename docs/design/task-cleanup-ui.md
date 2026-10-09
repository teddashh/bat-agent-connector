# Task cleanup in the shared Dashboard

Extends [reviewed cleanup](cleanup.md); central TaskCoordinator/resource policy remains authoritative.
The additive `features.cleanup_task` capability exposes a task scope and a link from execution details.
Preview submits exactly `{kind:"task",task_id:<full ID>}` through the existing endpoint and operation.
The native typed target accepts only an ID; no automatic lifecycle origin, force, path or child-expansion
authority is accepted from the WebView. Older central services do not show the new scope.

Cards show central decisions/reasons and retain the complete coordinator task/version/command/shared-owner
evidence under details. An eligible task worktree may explicitly release undelivered commits while keeping
the retained copy. Task-owned uncommitted content never exposes the discard override; branches and
unsupported carriers remain retained. Viewing or selecting a task does not itself authorize reclamation.

Cleanup also retains its exact public request/key separately from preview display state. A transport,
generic authorization or conflict failure cannot clear that key. Old pending previews adopt the existing
UI draft-derived key; new admissions store their intent before POST. The returned action/actor/key,
preview/token/fingerprint and accepted ID must match before adoption. Once accepted, reload and events
read the original operation, including partial receipts; they do not resubmit cleanup. Event acknowledgment
waits for pending submission and required readback. Read failures disable a fresh operation.

Only terminal readback or specific pre-admission token/expiry/mismatch/blocked errors permit an explicit
new preview. Backend/account-scoped local storage keeps intents across a native restart, with old tab
storage read/write compatibility. Removing the local draft does not cancel the central operation; central
cancel/resume controls remain on its operation page. No new queue or implicit force-unlock is introduced.

Browser/native transport fixtures exercise task scope, dirty retention, original-key recovery through
lost replies and authorization failures, mismatched response refusal and fresh-tab recovery. Rust validates
the exact typed target and refuses synthetic path/force/origin overrides. Actual-central fixtures are run
against the integrated task cleanup backend; mock and build evidence alone is not installed/live acceptance.
