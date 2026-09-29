# Provider routing: what actually runs, and bringing Jev back (2026-09-29)

## What shipped in this change

Routing rows used to record a provider that nothing started. The task service now starts the BAT
agent it records, in Ted's order, from the agents the host can actually run:

1. **Claude Opus 5.5** (`claude-opus-5-5:auto-compact-300k`, pinned on every Claude session so a BAT
   default can never land on Sonnet). Offered only while the host's `agent:usage-snapshot` is fresh
   (under 30 min) and both windows are under 85% (5h) and 90% (7d).
2. **AGY `claude-opus-4-6-thinking`** is not a BAT runtime: BAT starts only Claude Code and Codex, and
   the AGY CLI on this box is Gemini/Sonnet/Opus-4.6-thinking, not a session kind. It stays in the
   Goose catalog only. Nothing in the task path can start it today, so it is not silently skipped
   inside a BAT session.
3. **Codex**, the always-available default. Unknown availability falls back here.

The reviewer is the other model family from the lead when both are available (a Codex lead gets a
Claude reviewer and the reverse). A reviewer that hits its usage limit is not a review outcome: a
Claude reviewer is replaced by a Codex reviewer for the same candidate; a Codex reviewer goes to
needs_ted. `provider_usage` records a `success` when a session actually starts and `quota_error`
when a session's output reports the usage limit, which latches Claude off for an hour. Routing rows
are written only for the agent that really receives the prompt.

## Bringing Jev routing back without undoing the savings

Item 3 removed the per-step Jev classification (planning, implementation, verification, review,
status relay, plus one call per status poll: 266 routing rows for 10 standard tasks, 181 of them
Jev-answered, 217 of them status polls). Do not put that back.

The small version, one Jev call per task:

- At `work_submit`, ask one typed choice among the providers `available_agents` reports right then
  (`claude` and/or `codex`, plus `grok` once it exists). The question's criteria are the available
  set, so Jev cannot pick something the host cannot run.
- Chain: TypeSafe, then OpenRouter Decisions `typesafe/jev-router`, then the rules above. Never a
  general LLM and never `typesafe/jev-1.13` (that model stays on the review gate and triage).
- The answer sets `lead_agent`. Everything after that stays rules: the reviewer is the other family,
  verification is the trusted runner, status is a journal read.
- Invalid, timed out or unavailable Jev uses the rules unchanged.

Call counts per task: before item 3, roughly 5-20 Jev calls (one per step plus one per status poll);
after item 3, 0 for routing (1 only for the minimal review gate); with this, 1 at submit plus the
gate. Not implemented here: it needs the `typesafe/jev-router` endpoint confirmed and a second
classifier, which is more than this wiring fix.

## Grok 4.7 (design only, not implemented)

Grok 4.7 is not in the pipeline today; it is used for research only. A later provider would be a
headless `grok -p --output-format json` inside a BAT terminal on castle1, offered to the one-call
Jev choice only after a read-only probe shows the CLI installed and authenticated there. It needs
its own availability signal and a `provider_usage` outcome, same as the others.
