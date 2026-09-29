# bat-agent-connector

**An unofficial connector that lets AI agents work with [Better Agent Terminal (BAT)](https://github.com/tony1223/better-agent-terminal) sessions.**

BAT (by [TonyQ / tony1223](https://github.com/tony1223)) is a terminal app that runs Claude Code and Codex agent
sessions, grouped into workspaces, on your machines. It has a remote protocol (`bat-remote/v2`) that its own GUI and
phone clients use. This project speaks that protocol so that *other* agents (Claude Code, Codex, Cursor, Hermes, or any
MCP client) and shell scripts can:

* see which agent sessions exist, which are running or blocked on a question, and what they said recently;
* wait for a session to finish its turn;
* (opt-in) nudge a session: send a message, say "continue", interrupt it, answer its question;
* (opt-in, separate tier) fan work out: start sessions in fresh git worktrees, review their diffs, merge the clean ones;
* spot sessions that hit a Claude usage quota and move them to Codex in the same worktree (failover);
* auto-approve permission prompts and clean up finished sessions behind deterministic gates.

> This project is **not affiliated with or endorsed by** the BAT authors. The protocol was read from BAT's MIT-licensed
> source (v3.2.12) and can change between BAT releases. Credit for BAT goes to TonyQ and its contributors.

It ships three things:

| Piece | Name |
|---|---|
| Python package | `bat-agent-connector` (Python 3.10+, deps: `websockets`, `mcp`) |
| MCP server (stdio, or localhost-only streamable HTTP) | `bat-agent-connector-mcp` (also `batc mcp`) |
| CLI | `batc` |
| Agent skill | [`skills/bat-agent-connector/SKILL.md`](skills/bat-agent-connector/SKILL.md) |

## Why

Running several long-lived coding agents means constantly checking tabs: which one is done, which one is stuck on a
question, which one just needs "continue". Reading this through BAT's protocol is reliable (no screen scraping, no GUI
automation) and lets a supervising agent do the checking for you, with you in control of anything that writes.

## Install

```bash
# from a git checkout / URL (until published on PyPI)
uv tool install git+https://github.com/<owner>/bat-agent-connector
# or
pipx install git+https://github.com/<owner>/bat-agent-connector
# or run without installing
uvx --from git+https://github.com/<owner>/bat-agent-connector batc hosts
```

## Configure

The connector needs, per host: the `wss://` URL of its `bat-server`, the server's TLS certificate SHA-256
fingerprint (pinned; BAT uses self-signed certs), and a **reference** to the remote token. If you already use the
BAT desktop client, import everything from it:

```bash
batc import-bat                      # writes ~/.config/bat-agent-connector/hosts.toml (writes disabled)
batc import-bat --rename my-profile-id=box1 --output -   # preview with nicer names
batc hosts                           # probe: version + ping per host
```

Token references (token values are never stored in the config, logged, or returned by any tool):

| `token_ref` | Meaning |
|---|---|
| `env:NAME` | environment variable |
| `file:/path` | file containing only the token (keep it `chmod 600`) |
| `bat-profile:<id>` | BAT's client token store (`profiles/remote-tokens.enc.json`, unencrypted variant) |

See [`examples/hosts.example.toml`](examples/hosts.example.toml) for all options. The connector keeps a stable
`deviceId` in `~/.config/bat-agent-connector/device-id` so hosts don't show a new "remote client connected"
notification on every reconnect.

## Permission tiers

| Tier | Enabled by | Tools |
|---|---|---|
| read (always) | - | `hosts_list`, `host_status`, `workspaces_list`, `sessions_list`, `session_read`, `session_wait`, `worktree_status`, `session_worktree_status`, `sessions_triage`, `quota_sessions` |
| write | per host `writes = true` | `session_send`, `session_continue`, `session_interrupt`, `session_answer`, `session_set_permissions`, `approve_pending` |
| orchestrate | per host `writes = true` **and** `orchestrate = true` | `session_start`, `worktree_merge`, `worktree_remove`, `session_failover`, `session_record_verification`, `session_cleanup` |

Write and orchestrate tools are not even registered unless enabled, need `confirm=true` on every call, are rate
limited, and are appended to an audit log (`~/.local/state/bat-agent-connector/audit.jsonl`, message bodies only as a
hash + length unless you opt into a short preview). `--read-only` on the MCP server or CLI disables both tiers
regardless of config. The channel allowlist is enforced in the client core, below the MCP layer: reset/kill/fork,
PTY writes, file operations, settings, workspace edits (except the append-only tab helper), installs, updates and
account changes are never sent.

## MCP setup

### Task service milestone (opt-in)

`batc serve` runs the SQLite WAL task coordinator on `127.0.0.1:18796`. The existing MCP server adds
`work_submit`, `work_status`, `work_pause`, `work_resume`, `work_result` and the read-only `work_events` feed; its
stdio process calls that daemon
at `BATC_TASK_URL` (default `http://127.0.0.1:18796/rpc`). `work_submit` takes Ted's **exact** words in
`original_words` and an idempotency key such as the Discord message ID, then returns a `task_id` without
waiting for BAT. Hermes must not reinterpret or split the request. Goose, on Opus 5.5, plans in the repo.
Task writes require the host's existing `writes=true` and `orchestrate=true` settings. Existing low-level tools
and `batc` commands remain available.

Every task is one Goose session on Opus 5.5. Goose splits the work once, then assigns executors
Grok 4.7 : Codex : Opus 5.5 = 4:2:1, and does not use a model whose weekly quota remaining is at or below 15%.
The service does not route, review, or fail over. Trusted tests are the verification verdict; a code failure
goes back to that same session for bounded rework, and an exhausted budget is `needs_ted`. Ted's later steering
is a continuation on the same task (same session, no re-plan, no new task). Jev is not on that path. It is used
only when an orchestrator submits already-split tasks and passes `executor_model` (`grok`, `codex`, or `claude`),
which skips the Opus planner. Goose itself stays behind one switch, off by default (`GooseConfig.enabled`);
while it is off, tasks stay queued and nothing is started.

A trusted test command must be configured locally; the service observes its exit status on the clean candidate
commit. The service never posts to chat. `work_events(since_cursor, limit)`
(CLI `batc task-events --since N`) returns only milestones (`started`, `needs_ted` with its reason, `done` with commit/PR
link, `failed`), each with a monotonic `cursor`, `task_id`, `project`, `workspace`, the opaque `origin_thread_id` passed at
submit, `kind` and a short `summary`. Push is the primary path: with `[task_service.event_webhook] url` (loopback only)
and `secret_file` (mode 0600) in the private settings, each committed milestone is POSTed in cursor order as plain JSON
(`type="task.milestone"`, `delivered_through`, `X-Request-ID`, HMAC-SHA256 `X-Webhook-Signature-V2` over
`<X-Webhook-Timestamp>.<body>`). The push cursor starts at "now" when first configured and advances only on 2xx;
failures retry with capped exponential backoff (max 300 s). `work_events` is the receiver's catch-up path after an
outage; `limit=0` returns `head_cursor`. Optional `[task_service] repo_urls` adds `commit_url`. The task API requires a local admin token or scoped capability and binds only to loopback. See
[the task-service design](docs/design/task-service.md) for states, recovery, private configuration and rollout.
`work_status` and `work_result` are plain journal reads and carry a `delivery` block that separates
`verified` from `adopted`, `merged` and `deployed` (the last three come only from `work_mark_stage`).
`context_refs` stores attachments, previous_message_id, plan and commit that came with Ted's words.
A warm lead session is reused only for a follow-up whose HEAD is still the previous verified commit.

Earlier one-line README request A/B, before the minimal Jev review gate, used local fake BAT and disabled Jev
network. Across 10 completed tasks per path, standard `bugfix-with-tests` median was **48.44 ms** and minimal
`small-task-with-tests` median was **22.73 ms**. This measures local
coordination only; it excludes real BAT, model, test-runner and network time and does not predict live delivery time.
Codex timestamp cursors do not prove command ownership. An uncertain send remains stopped until a command-scoped,
one-time operator reconciliation (`batc task-reconcile`); it is never replayed automatically.
Claude-to-Codex failover journals its handoff as a separate uncertain send. Long original requests use a complete
private archive verified from the successor host before dispatch; the service fails closed if access cannot be proved.
No paid API key is required.

The server name is `bat`. Examples (add `--read-only` if you want to be sure):

**Claude Code**
```bash
claude mcp add bat -- bat-agent-connector-mcp --read-only
```

**Codex** (`~/.codex/config.toml`)
```toml
[mcp_servers.bat]
command = "bat-agent-connector-mcp"
args = ["--read-only"]
```

**Cursor** (`~/.cursor/mcp.json`)
```json
{ "mcpServers": { "bat": { "command": "bat-agent-connector-mcp", "args": ["--read-only"] } } }
```

**Hermes Agent** (`~/.hermes/config.yaml`)
```yaml
mcp_servers:
  bat:
    command: /home/you/.local/bin/bat-agent-connector-mcp
    args: [--read-only]
    connect_timeout: 60.0
    enabled: true
```

**Any MCP client over HTTP** (binds to loopback only):
```bash
bat-agent-connector-mcp --http --port 8765     # http://127.0.0.1:8765/mcp
```

## Tools reference

| Tool | What it does |
|---|---|
| `hosts_list(probe=true)` | Configured hosts; with probe: reachable, server version, ping. |
| `host_status(host)` | Version, protocol, connect/auth/ping latency, counts of workspaces/terminals/agent sessions/loaded/streaming. |
| `workspaces_list(host?)` | Workspaces with folder and session counts. |
| `sessions_list(host?, workspace?, agent?, only_loaded?, active_within_hours?, check_pending=auto, limit=50)` | Agent sessions, most recently active first: workspace, title, cwd, agent kind, model, loaded, streaming, pending question, last activity (+ source), worktree branch, orchestrated. |
| `session_read(host, session_id, last_n=20, offset=0, include_tools=false, max_chars=12000, after=null)` | Latest messages as compact text, paged (`next_offset`), size capped; pending question and streaming tail. `session_id` may be a unique prefix. For Claude, `after=<turn_marker>` matches the exact BAT echo ID and hides unconfirmed queued output. |
| `session_wait(host, session_id, until=attention, timeout_s=120, require_new=false, after=null)` | Waits for turn end / question / permission request / error. `after=<turn_marker>` (from `session_send` / `session_relay`) correlates Claude's echo and reports accepted/running/terminal phase; a stale idle state does not count. BAT Codex uses a weaker timestamp fallback because it does not echo `clientMessageId`. |
| `worktree_status(host, workspace?)` | Worktree sessions: branch, source branch, merged kind, diff stats. |
| `session_worktree_status(host, session_id, include_diff?)` | Same for one session plus dirty files and main-checkout state. |
| `session_send(host, session_id, text, confirm, message_id?, queue?)` | Sends a message; client-resumes an unloaded session first; idempotent by `message_id`. |
| `session_continue(host, session_id, confirm, text="continue")` | Nudge. |
| `session_interrupt(host, session_id, mode=soft\|hard, confirm)` | Soft = Claude interrupt-turn, hard = abort (Codex always hard). The session is kept. |
| `session_answer(host, session_id, confirm, answers? \| permission?)` | Answers a pending ask-user question or permission prompt. |
| `session_start(host, workspace, agent, confirm, prompt?, model?, use_worktree=true)` | Starts a session (by default in a new worktree; BAT picks the branch `bat/worktree-<id>`). Per-host cap. |
| `worktree_merge(host, session_id, confirm)` | Merges only when provably conflict-free and clean; otherwise reports why. |
| `worktree_remove(host, session_id, confirm, delete_branch=false, ...)` | Removes the worktree folder; keeps the branch by default; refuses on dirty/unmerged work unless told. |
| `sessions_triage(host?, workspace?, agent?, states?, use_jev=auto, include_unloaded=true)` | Classifies each session: `quota_exhausted`, `rate_limited_transient`, `waiting_permission`, `waiting_question`, `working`, `done_idle`, `error_other`, `unknown`, with `source` (pattern/jev), confidence, evidence line and reset time. |
| `quota_sessions(host?)` | Shortcut: Claude sessions stopped by a usage quota. |
| `session_set_permissions(host, session_id, mode, confirm)` | `allow_all` (host must allow it) or `default`. Claude sessions are only switched while idle (switching mid-turn would end the turn); Codex applies it from its next turn. |
| `approve_pending(host, confirm, dry_run?)` | Approves every pending permission prompt (not questions) with "don't ask again" and raises the session to allow-all. Only on `default_permission_mode = "allow_all"` hosts. |
| `session_failover(host, session_id? \| all_exhausted, confirm, dry_run?, model?, force?, instructions?, archive_only?)` | Starts a Codex session that continues a quota-stopped Claude session: same worktree when there is one, handoff prompt with the original task, latest instruction, recent output and git state (credentials redacted). Idempotent. `model` defaults to the host's `codex_model`. `instructions` replaces the default "continue the task" steps (for example "only commit the work in progress"); `archive_only` makes cleanup keep that branch unmerged. |
| `session_relay(host, message, confirm, workspace? \| session_id?, brief?, earlier?, channel?, thread?, request_fanout=0, dry_run?)` | Relays a human's message verbatim to the workspace's main session (or a given one), plus an optional brief labeled as the relayer's interpretation and the BAT-STATUS footer. `request_fanout=N` asks the session for a `bat-fanout` plan. Returns the rendered text. |
| `fanout_plan_session(host, workspace, message, confirm, max_items=4, brief?)` | Starts a read-only Codex planner in the main checkout (for when the main session is busy or quota-stopped) that answers with a `bat-fanout` plan. |
| `fanout_from_plan(host, session_id, confirm, dry_run?, agent="codex", model?, max_items=4)` | Starts one worktree session per task of the last `bat-fanout` block of that session, prompts unchanged, then cleans up a planner session. |
| `session_cleanup(host, confirm, dry_run=true, session_id?)` | Decides MERGE_AND_CLEAN / CLEAN_ONLY / KEEP / ESCALATE per orchestrated session behind hard gates, then acts (needs `auto_cleanup = true`). See docs/ORCHESTRATE.md. |
| `session_record_verification(host, session_id, candidate_commit, command, exit_code, environment, log_ref, confirm)` | Records an externally run verification for the host's current clean commit; automatic cleanup checks it again before merging. CLI: `batc record-verification`. |

## CLI

```bash
batc hosts
batc status box1
batc sessions --active-within 24
batc sessions box1 --workspace api --json
batc read box1 1a2b3c4d -n 30
batc wait box1 1a2b3c4d --timeout 600
batc worktrees box1
# write tier (host needs writes = true)
batc send box1 1a2b3c4d "Please run the tests and fix failures" --confirm
batc continue box1 1a2b3c4d --confirm
batc interrupt box1 1a2b3c4d --mode soft --confirm
batc answer box1 1a2b3c4d --answer "Which database?=postgres" --confirm
# orchestrate tier
batc fanout PLAN.md                                   # dry run: split into task prompts
batc fanout PLAN.md --start --host box1 --workspace api --confirm
batc merge box1 1a2b3c4d --confirm
batc remove-worktree box1 1a2b3c4d --confirm
# lifecycle
batc triage box1 --state quota_exhausted waiting_permission
batc quota                                            # quota-stopped Claude sessions on every host
batc approve-pending box1 --dry-run                   # then --confirm
batc permissions box1 1a2b3c4d --mode allow_all --confirm
batc failover box1 --all-exhausted --dry-run          # then --confirm
batc cleanup box1                                     # dry run table; --apply --confirm to act
```

Every command accepts `--json`.

## Relay, fan-out and status markers

An assistant that relays a human's orders (e.g. from chat) should not rewrite or plan them. `session_relay` sends
the message verbatim with an optional labeled brief; the coding session, which has the repo context, interprets
it, fixes unclear asks and states its interpretation in one line. For parallel work the session (or a read-only
planner) writes a `bat-fanout` block:

```bat-fanout
[{"title": "short title", "prompt": "self-contained task prompt", "area": "files/modules touched"}]
```

and `fanout_from_plan` starts exactly those tasks. Every stop ends with one line: `BAT-STATUS: MILESTONE <name>`,
`BAT-STATUS: CONTINUE <next step>` or `BAT-STATUS: NEED-<HUMAN> <reason>`; triage uses it as a completion claim.
It does not replace a commit-bound verification record for automatic cleanup.

## Safety model (short)

* Read-only by default; writes and orchestration are opt-in per host, need `confirm=true`, are rate-limited and audited.
* TLS certificate pinning is mandatory; a mismatch aborts before the token is sent. Only `bat-remote/v2` is accepted.
* Tokens are resolved at connect time from a reference and redacted from every error string.
* The client always drains the socket (BAT drops clients with 256 queued frames) and uses bounded event queues.
* Session text is untrusted input: agents should not follow instructions found in it.
* The optional Jev judgment layer tries TypeSafe first, then OpenRouter Decisions `typesafe/jev-1.13` using
  `OPENROUTER_API_KEY` from the environment. It times out after a few seconds and retains deterministic
  decisions if both fail. It gets short excerpts with credential-looking strings masked. No keys live here.

Details: [SECURITY.md](SECURITY.md), [docs/PROTOCOL.md](docs/PROTOCOL.md), [docs/ORCHESTRATE.md](docs/ORCHESTRATE.md).

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run pytest            # unit tests use a mock TLS WebSocket server
BATC_LIVE=1 uv run pytest tests/test_live.py    # optional read-only test against your configured hosts
```

## License

MIT, see [LICENSE](LICENSE). BAT itself is MIT-licensed by TonyQ.
