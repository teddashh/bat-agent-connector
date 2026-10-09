# Connector-local session labels

A03 labels organize existing session identities inside the Connector. They never
rename a BAT tab, modify its conversation, infer project ownership, grant managed
status, or call BAT/Git/Task Service effects. Manual and unknown resources retain
all existing execution restrictions.

`session.labels.set` uses the common durable operation envelope and `manage` scope:

```json
{"action":"session.labels.set","target":{"host":"demo","session_id":"full-session-id"},
 "params":{"labels":["Review","UI"]},"preconditions":{"expected_version":0}}
```

The target must exactly match a persisted observed/history session identity or a
session cleanup tombstone/alias. No prefix resolution or live lookup is performed.
Removed hosts and gone sessions remain eligible when their identity is retained.
Labels are a complete replacement list: at most eight unique, nonempty single-line
strings, at most 40 Unicode code points each, with surrounding whitespace trimmed.
Control/format/surrogate characters and line/paragraph separators are refused.
An empty list clears labels. Order is preserved; comparison is case sensitive.

A separate `session_metadata` table is keyed by `(host, session_id)`. An absent row
means version 0 / empty labels; unreadable stored data is an error, not an empty
value. Idempotent additive DDL leaves data-step 3, all IDs and existing events intact.
Inventory scans never write this table. Existing list rows and fixed session
reads expose `connector_metadata: {labels, version, updated_by, updated_at}`; the
fixed document also exposes it when only cleanup evidence remains.

Admission checks identity, shape and the observed metadata version after the
operation service has checked existing actor/key replay. The local `ctx.effect`
transaction repeats the identity/version check and commits metadata, incremented
version, actor, `session.labels_updated` event and exact effect receipt together.
Every successful new operation advances the version, including a replacement with
identical labels. The result includes host, full session ID, the new metadata and
previous metadata. Retry/restart reads the original receipt; a later edit cannot
change that historical result. An effect transaction failure rolls back all its
metadata/event/receipt writes. No external reconciliation is needed.

History uses the existing session event projection and operation link. Its redacted
summary carries version and `changed_fields: ["labels"]`; label prose stays in the
exact operation result/previous metadata. The existing observe scope controls
reads. The action registry is shared by HTTP, principal MCP operation_submit and
CLI op submit, without a separate legacy BAT mutation path. Native clients use the
existing typed operation transport; no new URL/path/credential permission exists.

The shared UI preserves an edited draft's original metadata version, exact labels,
operation key/ID and backend/principal/session namespace. A definitive
`METADATA_VERSION_CONFLICT` before admission permits only an explicit new intent
based on the current read; it does not discard the typed labels. Generic auth,
transport or idempotency errors cannot clear a possibly accepted request. Once an
operation ID is accepted, refresh reads it rather than POSTing again. Unknown or
needs_attention receipts stay fixed. Receipt acceptance verifies actor, key, full
envelope and successful result identity/version/labels. Event refresh joins a
pending submission, then reads the receipt and metadata before checkpoint ACK.

Validation uses synthetic browser/native transports, temporary real central state
and a temporary Git source with committed, staged, unstaged and untracked bytes.
The A03 fixture compares every source/Git file byte and rejects BAT mutation frames.
No live host, native installed runtime or user repository is exercised.
