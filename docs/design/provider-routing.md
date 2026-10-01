# One Goose session (2026-09-29)

The service does not choose a model per step and does not keep a rules-versus-Goose fork.

- One task is one Goose session on Opus 5.5. The `goose-session` recipe prompt tells Goose to split
  once at the start, to aim for an executor mix of Grok 4.7 : Codex : Opus 5.5 = 4:2:1, and to give
  no new work to a model at or below 15% weekly remaining. This is guidance in the prompt: the
  service does not count assignments or read quota.
- Verification is the trusted test runner. A code failure returns to the same session for bounded
  rework. When the budget is exhausted the task is `needs_ted`. There is no independent reviewer
  and no mid-task failover; a provider quota error is `needs_ted`.
- Ted's later steering is `continuation=true` with `parent_task_id`. That does not create a task.
  The words are stored on the original task and, when Goose runs, are handed to that same session
  with an instruction not to re-plan.
- Jev is not on the normal path. The only call is when an orchestrator submits already-split work
  and passes `executor_model` (`grok`, `codex`, or `claude`). That skips Opus. The question text
  asks Jev to reject the named model when it is at or below 15% weekly remaining (the service does
  not check quota itself); a valid `reject` refuses the submit, and no answer keeps the named model.
- Ted hears four milestones: `started`, `needs_ted`, `done`, `failed`.

Goose runs only when `GooseConfig.enabled` is true. It is off by default, so submitted tasks stay
queued. What is missing before the switch can be turned on: a pinned Goose binary whose ACP version
matches the contract, a logged-in Claude ACP (Opus 5.5) in the isolated Goose home, and a durable
session id. Today's ACP run is one-shot, so a continuation that arrives after the process exits
cannot reattach to a live session; the note is kept and included if that task is started later.
