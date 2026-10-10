# Task provider routing boundaries

Provider setup belongs in private configuration. This document describes the
connector contract; it does not prescribe an individual's model subscriptions,
account pool, endpoint layout or allocation preferences.

- A Goose task uses its configured session and recipe. The service does not
  independently enforce executor ratios or inspect subscription quota. Any model
  allocation or quota instruction in a recipe prompt is guidance, not observed
  provider data or a scheduler guarantee.
- Verification uses the trusted test runner. A code failure returns to the same
  session for bounded rework. Exhausted recovery budget or a provider quota error
  requires operator attention (`needs_ted`). Do not interpret a provider switch
  as permission to replay a prompt whose acceptance is uncertain.
- Follow-up input with `continuation=true` and `parent_task_id` remains on the
  original task. It is stored and handed to the same session when available;
  it does not create another task or silently re-plan the original request.
- Jev is not on the normal Goose path. The existing pre-split submission contract
  accepts `executor_model` values `grok`, `codex` or `claude` and may ask the
  configured decision service whether to refuse that selection. A valid `reject`
  refuses submission; an unavailable answer preserves the named model. This is
  not a verified quota lookup.
- The committed milestone kinds remain `started`, `needs_ted`, `done` and `failed`.
  Interfaces should display operator-neutral labels while preserving wire and
  journal identifiers for compatibility.

Goose runs only when `GooseConfig.enabled` is true. It is off by default, so its
submitted tasks stay queued. Enabling it requires a pinned binary, compatible ACP
schema, authenticated provider configuration and durable session identity. The
one-shot ACP adapter cannot reattach a continuation to a process that has already
exited; the note remains stored for a later start. See the activation checklist and
provider-specific constraints in [task-service.md](task-service.md).

Status and results are reads: they must not select another model or issue provider
requests just to display a task. Usage summaries must distinguish service-recorded
calls from externally reported tokens, cost and subscription quota. Missing or
stale sources stay explicit; a published model ID does not prove account access,
remaining quota or successful execution.
