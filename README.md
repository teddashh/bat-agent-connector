# bat-agent-connector

**English** · [繁體中文](README.zh-TW.md)

**An unofficial connector that lets AI agents work with [Better Agent Terminal (BAT)](https://github.com/tony1223/better-agent-terminal) sessions.**

**Project page:** https://teddashh.github.io/bat-agent-connector/

**Development direction:** [Tauri v2 product decisions](docs/product/realignment-v2.md) and
[implementation status](docs/product/implementation-status.md). The desktop client will share the Dashboard
frontend and the existing Python backend. Project Hub import is outside the v2 scope; project/work-item management remains.

BAT (by [TonyQ / tony1223](https://github.com/tony1223)) is a terminal app that runs Claude Code and Codex agent
sessions, grouped into workspaces, on your machines. It has a remote protocol (`bat-remote/v2`) that its own GUI and
phone clients use. This project speaks that protocol so that *other* agents (Claude Code, Codex, Cursor, Hermes, or any
MCP client) and shell scripts can:

* see which agent sessions exist, which are running or blocked on a question, and what they said recently;
* wait for a session to finish its turn;
* (opt-in) nudge a session: send a message, say "continue", interrupt it, answer its question;
* (opt-in, separate tier) fan work out: start sessions in fresh git worktrees, review their diffs, merge the clean ones;
* spot sessions that hit a Claude usage quota and move them to Codex in the same worktree (failover);
* auto-approve permission prompts behind deterministic gates, and reclaim managed resources through a reviewed preview.

> This project is **not affiliated with or endorsed by** the BAT authors. The protocol was read from BAT's MIT-licensed
> source (v3.2.12) and can change between BAT releases. Credit for BAT goes to TonyQ and its contributors.

General managed starts keep the operator's `default_permission_mode`: `default` preserves BAT defaults and
`allow_all` preserves bypass/full access (level `none`). Choose `confined` to restrict general starts too. Checkpoint
and repair starts always use confined options: Claude `default`, or `acceptEdits` only with a verified BAT host
account; Codex `workspace-write/on-request`. Host-account verification requires a separate trusted auditor SSH
alias (`check_ssh_alias`), its UID (`check_uid`) and the target `bat_account`, set up by the operator. The auditor
proves the entire system Python closure before executing it, then uses a narrow sudo rule and `-c` argv without
the BAT account's shell or startup files. Unknown layouts or incomplete gates use plain default.
The channel and verdict UID are checked; the auditor login must be beyond the BAT account's control.
Without that channel, `unknown/check_channel_untrusted` means `fallback_default`, never acceptEdits.
Defense in depth still requires a root-owned, non-writable BAT home and trusted startup files, plus system-owned
Python/find. The verdict assumes no hostile BAT-UID process during the check; ptrace_scope is recorded, not an
isolation proof. Install clean startup files before hardening; agent
state may live in account-owned `.claude`, `.codex` and `.cache` subdirectories. Unhardened hosts report unknown and
confined Claude uses plain `default`. Cwd alone offers no protection, and acceptEdits has no path check.
BAT cannot configure network or writable roots, so confined Codex may break installs and localhost test servers.
Task Service engine/recipes stay unchanged and expose their compatibility gap. Session reads and the Dashboard
show creation evidence separately from current verification. A10 is not proven until W12's live acceptance run.
See [configuration, limits and the live procedure](docs/design/confinement.md).

The Dashboard start note follows capabilities `hosts[].confinement.host_account.start_effect`: `verified`,
`recheck` (unchecked or stale; checked live at start), `fallback_default` (a supported hardening gap or no account
declaration; confined Claude uses plain default), or `refused` (blocks Claude and Codex). The read itself runs no
check and keeps the reason visible. A non-verified status alone does not mean starts are blocked.

`START_IN_PROGRESS` means another process is starting this session: read it back later, do not retry blindly;
`CONFINEMENT_START_UNSETTLED` requires read-back of a possibly sent start.

It ships four things:

| Piece | Name |
|---|---|
| Python package | `bat-agent-connector` (Python 3.10+, deps: `websockets`, `mcp`) |
| MCP server (stdio, or localhost-only streamable HTTP) | `bat-agent-connector-mcp` (also `batc mcp`) |
| CLI | `batc` |
| Agent skill | [`skills/bat-agent-connector/SKILL.md`](skills/bat-agent-connector/SKILL.md) |

Hermes and Grokbot adapters are [generated from the canonical skill](docs/agent-skills.md);
regenerate them after workflow changes and install bundles from the matching Connector release.

Persisted observation is available through `batc inventory`, `batc history` and `batc relations`, or the matching
HTTP/MCP reads. Session history uses journal facts; warm reuse keeps each task’s relation ranges. Discovery shows
the latest host/profile scope and what was outside the scan. Unknown actors and states stay unknown; these reads
do not start sessions or probe Git. See [observation](docs/design/observation.md). The Dashboard history and scope
screens are Part B, to follow separately.

## Why

Running several long-lived coding agents means constantly checking tabs: which one is done, which one is stuck on a
question, which one just needs "continue". Reading this through BAT's protocol is reliable (no screen scraping, no GUI
automation) and lets a supervising agent do the checking for you, with you in control of anything that writes.

Artifact attachments have immutable revisions in Connector-owned storage (SHA-256, size and explicit quotas).
Upload with `batc artifact upload FILE --key KEY --confirm` or a Dashboard picker, attach an exact
`{artifact_id, revision, digest}` to a work item or checkpoint, and continue on the checkpoint's host. Bytes are
verified in the session's worktree before the first command; a moved source requires confirmation that resumes the
same operation. Dashboard text and uploaded refs survive reloads and failures. Store content has no delete;
Use `batc artifact capture-preview HOST SESSION_ID relative/file` to review one manual-session file, save
the JSON, then `batc artifact capture --preview-file PREVIEW.json --key KEY --confirm` with the same credential.
Capture needs `observe` and `manage`, refuses source changes, and never changes the manual checkout. It preserves
one file, not a dirty snapshot. Managed-result capture/accept and cross-host commit fetch remain later parts.
See [the artifact design](docs/design/artifacts.md).

## Install

```bash
# from a git checkout / URL (until published on PyPI)
uv tool install git+https://github.com/teddashh/bat-agent-connector
# or
pipx install git+https://github.com/teddashh/bat-agent-connector
# or run without installing
uvx --from git+https://github.com/teddashh/bat-agent-connector batc hosts
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
| read (always) | - | `hosts_list`, `host_status`, `workspaces_list`, `sessions_list`, `session_read`, `session_wait`, `worktree_status`, `session_worktree_status`, `sessions_triage`, `quota_sessions`, `session_policy`, `work_status`, `work_result`, `work_events` |
| write | per host `writes = true` | `session_send`, `session_continue`, `session_interrupt`, `session_answer`, `session_set_permissions`, `approve_pending`, `session_relay` |
| orchestrate | per host `writes = true` **and** `orchestrate = true` | `session_start`, `worktree_merge`, `worktree_remove`, `session_failover`, `session_record_verification`, `session_cleanup`, `fanout_plan_session`, `fanout_from_plan`, `work_submit`, `work_pause`, `work_resume`, `work_mark_stage` |

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

Task mutations now record an operation and return `operation_id` / `operation_status` with the existing result.
Keep a key for retries; keys belong to the authenticated actor. Unkeyed old task controls are separate requests.
Task-bound operations capture the task version at admission, including when `control_version` is omitted;
session controls also capture the current session. Read this server binding in `external_refs.admission_binding`,
separate from caller preconditions. A pause/resume or session replacement before execution refuses the old request
with `CONTROL_VERSION_CONFLICT` / `TASK_BINDING_MISMATCH`. The same key replays the refusal or original success;
read the task and use a new key for an authorized new decision. Older operations without this binding retain
their previous behaviour.
Task-owned sends, answers, interrupts and permission changes pass the same coordinator, including legacy tools:
`TASK_PAUSED`, `TASK_VERIFYING` and `TASK_COMMAND_PENDING` mean stop and read `work_status`, never jump the queue
with force or continue. `CONTROL_VERSION_CONFLICT` requires reading the changed state. A second daemon, even with
a different `--db`, returns `OWNER_CONFLICT` with the existing owner; clients use that owner. This is
[operations unification Part A](docs/design/operations-unification.md); the remaining legacy operations and
no-key/null result projection are Part B.

Every task is one Goose session on Opus 5.5. The `goose-session` recipe prompt tells Goose to split the work
once, to aim for an executor mix of Grok 4.7 : Codex : Opus 5.5 = 4:2:1, and to give no new work to a model
whose weekly quota remaining is at or below 15%. These are instructions in the prompt, not rules the service
enforces: it does not count assignments or read quota. The service does not route, review, or fail over.
Trusted tests are the verification verdict; a code failure
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
`work_submit` takes an optional `task_path` (`standard` or `minimal`); without it the daemon uses `standard`, or
`minimal` when it runs with `BATC_TASK_DEFAULT_PATH=minimal`. A warm lead session is reused only on the minimal
path and only for a follow-up whose HEAD is still the previous verified commit.

Earlier one-line README request A/B, before the minimal Jev review gate, used local fake BAT and disabled Jev
network. Across 10 completed tasks per path, standard `bugfix-with-tests` median was **48.44 ms** and minimal
`small-task-with-tests` median was **22.73 ms**. This measures local
coordination only; it excludes real BAT, model, test-runner and network time and does not predict live delivery time.
Codex timestamp cursors do not prove command ownership. An uncertain send remains stopped until a command-scoped,
one-time operator reconciliation (`batc task-reconcile`); it is never replayed automatically.
Claude-to-Codex failover journals its handoff as a separate uncertain send. Long original requests use a complete
private archive verified from the successor host before dispatch; the service fails closed if access cannot be proved.
No paid API key is required.

### Dashboard API (`/api/v1`)

The task daemon also serves `/api/v1` on its loopback port: capabilities, a persisted session inventory with
staleness, durable operations, and one event cursor with SSE. Issue a token per client
(`batc api-token issue --actor ted-dashboard --scope observe --scope operate --scope start --scope integrate --scope
manage --scope approve --scope merge --scope deploy --scope cleanup`; `start` lets it start new agent sessions from checkpoints,
`integrate` lets it push results to a PR's head branch, `manage` edits projects and work items, `approve` accepts work
items as done, `merge` and `deploy` back the Delivery buttons) and send it as
`Authorization: Bearer`. MCP clients reach the same operations with `operation_submit`, `operation_cancel` and
`operation_resume` (`confirm=true`, and `BATC_API_TOKEN` set to the client's own token: operations never run as the
local admin). See [docs/design/api-v1.md](docs/design/api-v1.md).

With `[github]` and `[[deploy.recipes]]` configured, the same operations merge pull requests at a reviewed head
SHA and deploy the merged commit (`github.pr.merge`, `deployment.start`, `delivery.merge_and_deploy`). See
[docs/design/delivery.md](docs/design/delivery.md).

The same daemon serves a browser Dashboard at `http://127.0.0.1:18796/dashboard/`: what needs you, every
session with its provenance (sessions a person created in BAT stay read-only), managed-session controls, PR
merge and deploy buttons, and the operation log. Connect it with an API token. See
[docs/design/dashboard.md](docs/design/dashboard.md).

To continue a person's work without touching their session, record a checkpoint (`checkpoint.create`: its commit
and recent conversation, read-only) and start managed work from it (`checkpoint.continue`: a connector-owned clone,
worktree, branch and session at that commit). This needs `managed_roots` and an SSH alias for the host. See
[docs/design/checkpoints.md](docs/design/checkpoints.md).

To put results into an existing PR, preview them (`integration.preview`: every commit and file that would enter,
pinned by SHA) and apply the preview (`integration.apply`: one normal push of the composed commit to the PR's head
branch, with the host's git credentials; never forced, and your folders are never changed). This needs
`integrate = {hosts, remote_url}` on the repository's `[[github.repos]]` entry. See
[docs/design/integration.md](docs/design/integration.md).

Projects and work items record what is being done and why: the request verbatim, acceptance, steps, and links to
the sessions, checkpoints, operations and PRs that carried it. An agent with `manage` can claim an item done; only
a token with `approve` accepts it, for the content it read, and editing the content afterwards asks again. Order,
pins, renames and archive follow Project Hub's rules. See [docs/design/work-items.md](docs/design/work-items.md).

PR delivery now has a separate metadata action (`github.pr.update`, existing `integrate` scope, per-repository
`allow_pr_update = true`; default false) and saved merge scope previews. Read `github_pr_preview` / `batc delivery pr`,
review all commits and affected PRs, then `github_pr_merge` / `batc delivery merge --preview mpv_... --key KEY`.
Unknown metadata writes still unchanged after ten minutes settle as not applied, freeing the PR without resending;
review a fresh digest before a new edit. Identical previews reuse their ID, and event reloads throttle scope reads.
Metadata edits compare the title/body digest before writing and read back afterward; GitHub's final read/write race
still exists. Merge checks the reviewed head/base/scope before submit and verifies the actual merged SHA; queue merges
onto a newer base report the extra commits. Unsupported stacks and indirect merges are refused. MCP/CLI writes need
the caller's `BATC_API_TOKEN`. See [delivery design](docs/design/delivery.md) for envelopes, errors and recovery.
Deployment history, environment generations, runtime verification and rollback remain Part B.

### Connect an MCP client

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


Cleanup and retained work (`#/cleanup`, also linked from work item details) lists actual resources, all retention
reasons and exact steps before applying a signed preview valid for 15 minutes. Changed state requires a new preview.
HTTP `/cleanup-previews` and the `cleanup.apply` operation, MCP `cleanup_preview`, `cleanup_apply`,
`cleanup_retained`, `cleanup_tombstones`, and CLI `batc resource-cleanup preview|apply|retained|history` share the
contract. Scope `cleanup` reclaims managed sessions, worktrees and exact temporaries; explicit
`release_undelivered` keeps commits and the branch and records that results were not delivered.
A reviewed preview can also release capacity when all eligible sessions and their carriers are already absent.
Only `discard_uncommitted` needs the person's `cleanup_discard` scope; Hermes/Grokbot tokens do not receive it,
and agents never request it. Manual, unknown, task-owned, streaming, waiting and unresolved resources are retained.
A ref is written before non-force removal. All `refs/batc/*`, clones and integration areas stay. Original IDs,
locations, reasons, receipts and PR destinations remain searchable forever. Supported settings are
`[cleanup] retained_refs="keep", history_retention="forever", permanent_delete=false`. This release lists actual
retained content; restore and reviewed task cleanup follow in Part B. `auto_cleanup` still parses but is deprecated
and never enables writes. Legacy `batc cleanup` / `session_cleanup` only evaluate, without worktree rehydration.
Fanout stops the planner only with confirmation and every planned task started, keeping its worktree; failed
or incomplete starts keep the planner for retry. See [docs/design/cleanup.md](docs/design/cleanup.md).

```sh
batc resource-cleanup preview --checkpoint cp_EXAMPLE --json > preview.json
batc resource-cleanup apply --preview-file preview.json --key cleanup-review-1 --confirm
batc resource-cleanup retained
batc resource-cleanup history --original-id cp_EXAMPLE
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
| `worktree_merge(host, session_id, confirm)` | Merges only into a main checkout inside a managed root, and only when provably conflict-free and clean; otherwise reports why. |
| `worktree_remove(host, session_id, confirm, delete_branch=false, ...)` | Removes the worktree folder; keeps the branch by default; refuses on dirty/unmerged work unless told. |
| `sessions_triage(host?, workspace?, agent?, states?, use_jev=auto, include_unloaded=true)` | Classifies each session: `quota_exhausted`, `rate_limited_transient`, `waiting_permission`, `waiting_question`, `working`, `done_idle`, `error_other`, `unknown`, with `source` (pattern/jev), confidence, evidence line and reset time. |
| `quota_sessions(host?)` | Shortcut: Claude sessions stopped by a usage quota. |
| `session_set_permissions(host, session_id, mode, confirm)` | `allow_all` (host must allow it) or `default`. Claude sessions are only switched while idle (switching mid-turn would end the turn); Codex applies it from its next turn. |
| `approve_pending(host, confirm, dry_run?)` | Approves every pending permission prompt (not questions) with "don't ask again" and raises the session to allow-all. Only on `default_permission_mode = "allow_all"` hosts. |
| `session_failover(host, session_id? \| all_exhausted, confirm, dry_run?, model?, force?, instructions?, archive_only?)` | Starts a Codex session that continues a quota-stopped connector-managed Claude session: same worktree when there is one, handoff prompt with the original task, latest instruction, recent output and git state (credentials redacted). Idempotent. `model` defaults to the host's `codex_model`. `instructions` replaces the default "continue the task" steps (for example "only commit the work in progress"); `archive_only` marks the successor for preservation; reviewed release keeps its commits and branch. |
| `session_relay(host, message, confirm, workspace? \| session_id?, brief?, earlier?, channel?, thread?, request_fanout=0, dry_run?, start_if_missing?)` | Relays a human's message verbatim to the workspace's most recent connector-managed session (or a given one; sessions created in BAT are never written to, and `start_if_missing` starts a new worktree session instead), plus an optional brief labeled as the relayer's interpretation and the BAT-STATUS footer. `request_fanout=N` asks the session for a `bat-fanout` plan. Returns the rendered text. |
| `fanout_plan_session(host, workspace, message, confirm, max_items=4, brief?)` | Starts a Codex planner in its own worktree (for when no managed session can plan) that answers with a `bat-fanout` plan. |
| `session_policy(host, session_id?)` | Read. The host's mutation table and managed roots, or one session's provenance (`manual`, `connector_managed`, `unknown`), folder ownership and per-action verdicts with refusal codes. |
| `fanout_from_plan(host, session_id, confirm, dry_run?, agent="codex", model?, max_items=4)` | Starts one worktree session per task of the last `bat-fanout` block of that session, prompts unchanged. Stops a planner only with confirmation and every task started; otherwise keeps it for retry. Its worktree is kept. |
| `session_cleanup(host, confirm, dry_run=true, session_id?)` | Decides MERGE_AND_CLEAN / CLEAN_ONLY / KEEP / ESCALATE per orchestrated session behind hard gates, read-only evaluation; apply returns `LEGACY_CLEANUP_DISABLED`; `auto_cleanup` is deprecated. See docs/ORCHESTRATE.md. |
| `session_record_verification(host, session_id, candidate_commit, command, exit_code, environment, log_ref, confirm)` | Records an externally run verification for the host's current clean commit; legacy read-only evaluation checks it against the candidate commit. CLI: `batc record-verification`. |

## CLI

```bash
batc hosts
batc status box1
batc sessions --active-within 24
batc --json sessions box1 --workspace api
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
batc policy box1                                      # mutation table; `batc policy box1 1a2b3c4d` explains one session
batc triage box1 --state quota_exhausted --state waiting_permission
batc quota                                            # quota-stopped Claude sessions on every host
batc approve-pending box1 --dry-run                   # then --confirm
batc permissions box1 1a2b3c4d --mode allow_all --confirm
batc failover box1 --all-exhausted --dry-run          # then --confirm
batc cleanup box1                                     # read-only evaluation; --apply returns LEGACY_CLEANUP_DISABLED
```

Every command accepts the global `--json` flag, placed before the command: `batc --json hosts`.

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
It does not replace a commit-bound verification record for legacy cleanup evaluation.

## Safety model (short)

* Read-only by default; writes and orchestration are opt-in per host, need `confirm=true`, are rate-limited and audited.
* Sessions a person created in BAT are read-only through every tool. Writes only reach sessions the connector started,
  in folders it owns; the client core refuses any write frame without a resource policy grant
  ([docs/design/resource-policy.md](docs/design/resource-policy.md)).
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
