# Security

## Reporting

Please report vulnerabilities privately via GitHub security advisories on this repository rather than in public
issues. Issues in BAT itself should go to the [BAT project](https://github.com/tony1223/better-agent-terminal).

## What the connector can do

A BAT remote token is powerful: BAT's protocol can run shells, edit files and change settings on the host. The
connector deliberately exposes a small subset:

| Tier | Default | Channels sent |
|---|---|---|
| read | on | `workspace:load`, `claude:get-session-meta/state`, `claude:load-archived`, `claude:list-sessions`, `worktree:status`, `git:status/branch/getRoot`, version/profile/notification reads |
| write | off (`writes = true`) | `claude:send-message`, `claude:client-resume`, `claude:interrupt-turn`, `claude:abort-session`, `claude:resolve-ask-user`, `claude:resolve-permission` |
| orchestrate | off (`orchestrate = true`, needs writes) | `claude:start-session`, `worktree:create/merge/remove/rehydrate`; `workspace:save` only via the append-only tab helper when `orchestrate_register_tabs = true` |

Everything else is rejected in the client core before a frame is written (see `channels.py` and `tests/test_client.py`).

## Controls

* **Pinning:** the server certificate's SHA-256 must match the configured fingerprint; otherwise the connection is
  closed before authentication. Downgrades to the legacy protocol are refused.
* **Tokens:** only references (`env:`, `file:`, `bat-profile:`) live in config. Values are registered with a redactor
  and scrubbed from every error. Tools never return them.
* **Writes:** hidden unless enabled, `confirm=true` per call, per-session minimum interval and hourly cap, audit log
  (`~/.local/state/bat-agent-connector/audit.jsonl`, mode 600) with a hash + length instead of message bodies.
* **Orchestrate:** per-host cap on concurrently orchestrated sessions (default 4), per-call cap for fan-out, merges
  only when BAT reports the branch strictly ahead of its source (no conflicts possible), the worktree and main checkout
  are clean and the main checkout already sits on the source branch; removal refuses dirty worktrees and (when
  deleting the branch) unmerged commits unless explicitly overridden. Nothing is ever forced by default.
* **Backpressure:** a background reader always drains the socket; per-subscriber queues are bounded (drop-oldest).
* **Size caps:** frames up to 48 MiB, tool output capped (`session_read` hard cap 60k chars, diffs 100k).

## Known risks

* **Prompt injection:** session transcripts are untrusted. A supervising agent that reads them must not follow
  instructions found inside, and should only write when its user asked.
* **Tab registration (`workspace:save`)** replaces BAT's whole workspace document; BAT has no compare-and-swap. The
  helper re-reads the document right before saving and aborts if it changed, appends exactly one terminal, then
  verifies every previous workspace/terminal is still present. A narrow race with a GUI client saving at the same
  moment remains, which could drop that client's latest unsaved tab change. Keep it off unless you need GUI tabs for
  orchestrated sessions; without it, sessions are tracked in the connector's local registry.
* **`worktree:remove`** in BAT always force-removes the folder. The connector checks for uncommitted changes first,
  but changes made between the check and the removal would be lost.
* **`bat-profile:` tokens** come from BAT's client store, which BAT writes unencrypted on some platforms. Protect that
  file (and the connector's config dir) with normal filesystem permissions.
