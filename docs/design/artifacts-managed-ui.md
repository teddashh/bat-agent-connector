# Managed artifact review in the shared Dashboard

Extends [managed capture and acceptance](artifacts-managed.md). Central remains the
only source/execution/credential authority. This page reuses the Dashboard panels,
form controls, evidence lists and English/zh-TW copy; it adds no alternate store.

Session and task links open a fixed source context. The execution selector loads
supported succeeded central operations and current accepted send commands. Standalone
`session.start` appears only with positive start and initial-prompt result evidence;
prompt-free and uncertain starts are excluded. Central rechecks the original start,
reservation, send receipts and incarnation during preview. An
explicit older command/operation ID is a selector only; the signed preview must
prove it. The preview displays one relative file, source folder, HEAD, size and
digest. It is not a dirty-worktree snapshot or an authorship claim.

Capture freezes the complete public envelope and key before POST. Recovery validates
actor/action/key/target/params/preconditions and the original accepted ID. Once an
ID is known, reload, events and polling only GET that operation and exact artifact
revision. The ready ArtifactRef must match the saved digest, source fingerprint,
capture operation and central source proof before review becomes available.

Review is a separate `artifact.accept` operation with explicit bounded text and
`approve` scope. The page can also open an existing exact managed ArtifactRef from
the central catalog, allowing a different reviewer to accept it. Acceptance records
only review of that revision; it does not finish tasks, verify tests, merge or deploy.
It neither attaches the ref automatically nor changes the existing attachment draft.

Drafts and both intents use endpoint/server/principal/actor storage namespaces.
Bootstrap identity does not distinguish credentials with the same actor/scopes.
Therefore a generic authorization failure preserves the original capture token/key;
it cannot create a replacement capture or adopt another credential. Central's
stronger original-credential check remains authoritative. Known accepted IDs are
read back under existing observe policy. No credential material enters this module.

Only a matching terminal receipt or an explicit pre-admission refusal permits a new
intent. Uncertain outcomes retain their IDs and links to operation controls. Failed
event reads block acknowledgment; focused text and fixed previews survive refreshes.
The native bridge permits only the fixed managed-preview route and typed source,
relative file and exactly one central selector; no path transport, force or supplied
lineage is accepted. Existing manual capture remains separate.

Validation uses mock browser/native transports and an actual central temporary Git /
MockBat fixture for capture, lost replies, ready readback and acceptance. Screenshots
check 390/768/1440 widths. Builds and fixtures do not claim installed/live acceptance.
