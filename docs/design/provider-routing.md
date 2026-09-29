# One Goose session (2026-09-29)

The service does not choose a model per step and does not keep a rules-versus-Goose fork.

- One task is one Goose session on Opus 5.5. Goose splits once at the start, then assigns work
  Grok 4.7 : Codex : Opus 5.5 = 4:2:1. A model at or below 15% weekly remaining gets no new work.
- Verification is the trusted test runner. A code failure returns to the same session for bounded
  rework. When the budget is exhausted the task is `needs_ted`. There is no independent reviewer
  and no mid-task failover; a provider quota error is `needs_ted`.
- Ted's later steering is `continuation=true` with `parent_task_id`. That does not create a task.
  The words are stored on the original task and, when Goose runs, are handed to that same session
  with an instruction not to re-plan.
- Jev is not on the normal path. The only call is when an orchestrator submits already-split work
  and passes `executor_model` (`grok`, `codex`, or `claude`). That skips Opus. A Jev `reject`
  (the named model is at or below the 15% floor) refuses the submit; no answer keeps the named model.
- Ted hears four milestones: `started`, `needs_ted`, `done`, `failed`.

Goose runs only when `GooseConfig.enabled` is true. It is off by default, so submitted tasks stay
queued. What is missing before the switch can be turned on: a pinned Goose binary whose ACP version
matches the contract, a logged-in Claude ACP (Opus 5.5) in the isolated Goose home, and a durable
session id. Today's ACP run is one-shot, so a continuation that arrives after the process exits
cannot reattach to a live session; the note is kept and included if that task is started later.
