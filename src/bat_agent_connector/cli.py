"""`batc` command-line interface (mirrors the MCP tools)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__, lifecycle, orchestrate, service, triage
from .config import DEFAULT_BAT_PROFILES_DIR, default_config_path, load_config
from .errors import BatError
from .fleet import Fleet
from .importer import read_bat_profiles, render_hosts_toml
from .redact import redact


def _print(obj: Any, as_json: bool, render=None) -> None:
    if as_json or render is None:
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
    else:
        render(obj)


def _table(rows: list[list[Any]], headers: list[str]) -> None:
    cells = [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [len(h) for h in headers]
    for r in cells:
        for i, v in enumerate(r):
            widths[i] = min(max(widths[i], len(v)), 48)
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    for r in cells:
        print(fmt.format(*[v if len(v) <= 48 else v[:47] + "…" for v in r]))


def r_hosts(o):
    _table(
        [
            [
                h["name"],
                h["url"],
                h.get("server_version"),
                h.get("ping_ms"),
                "rw" if h["writes_enabled"] else "ro",
                "ok" if h.get("reachable") else (h.get("error") or "-"),
            ]
            for h in o["hosts"]
        ],
        ["host", "url", "version", "ping_ms", "mode", "status"],
    )


def r_status(o):
    lat = o["latency"]
    print(f"{o['host']}: bat-server {o['server_version']} ({o['protocol']})")
    print(
        f"  latency: connect={lat['connect_ms']}ms auth={lat['auth_ms']}ms ping={lat['ping_ms']} median={lat['ping_median_ms']}ms"
    )
    print(
        f"  workspaces={o['workspaces']} terminals={o['terminals']} agent_sessions={o['agent_sessions']} "
        f"{o['agent_sessions_by_kind']} loaded={o['loaded']} streaming={o['streaming']}"
    )
    print(f"  writes: {'enabled' if o['writes_enabled'] else 'disabled'}")


def r_workspaces(o):
    _table(
        [[w["host"], w["name"], w["agent_sessions"], w["terminals"], w["folder"]] for w in o["workspaces"]],
        ["host", "workspace", "agents", "terms", "folder"],
    )
    for h, e in o["errors"].items():
        print(f"! {h}: {e}", file=sys.stderr)


def r_sessions(o):
    rows = []
    for s in o["sessions"]:
        state = "streaming" if s["streaming"] else ("loaded" if s["loaded"] else "unloaded")
        pend = (s["pending"] or {}).get("kind") or ""
        rows.append(
            [
                s["host"],
                s["session_id"][:8],
                s["workspace"],
                s["agent_kind"],
                state,
                pend,
                s["last_activity_age"],
                s["last_activity"],
                s["title"],
            ]
        )
    _table(
        rows, ["host", "session", "workspace", "agent", "state", "pending", "age", "last_activity", "title"]
    )
    print(f"({o['count']} of {o['total_matched']})")
    for h, e in o["errors"].items():
        print(f"! {h}: {e}", file=sys.stderr)


def r_read(o):
    print(
        f"# {o['host']} {o['session_id']} [{o['workspace']}] {o['agent_kind']} "
        f"loaded={o['loaded']} streaming={o['streaming']}"
    )
    if o.get("after"):
        print(f"# after {o['after']['iso']}: turn_started={o.get('turn_started')} turn_done={o.get('turn_done')}")
        if not o["messages"]:
            print(f"# {o.get('note')}")
    for m in o["messages"]:
        tag = m["role"] if m["role"] != "tool" else f"tool:{m.get('tool')}"
        print(f"\n--- {m.get('ts')} {tag}\n{m.get('text')}")
    if o.get("pending"):
        print("\n*** PENDING:", json.dumps(o["pending"], ensure_ascii=False))
    if o.get("next_offset") is not None:
        print(f"\n(older: --offset {o['next_offset']})")


def r_triage(o):
    rows = [
        [
            s["host"],
            s["session_id"][:8],
            s.get("workspace"),
            s.get("agent_kind"),
            s.get("state"),
            s.get("source"),
            s.get("confidence"),
            s.get("resets") or "",
            s.get("evidence") or "",
        ]
        for s in o["sessions"]
    ]
    _table(rows, ["host", "session", "workspace", "agent", "state", "source", "conf", "resets", "evidence"])
    print(f"({o['count']} rows; by state: {o['counts_by_state']}; jev: {o['jev']}; {o['elapsed_s']}s)")
    for h, e in o["errors"].items():
        print(f"! {h}: {e}", file=sys.stderr)


def r_cleanup(o):
    rows = [
        [
            (d.get("session_id") or "")[:8],
            d.get("workspace"),
            d.get("agent_kind"),
            d.get("branch") or "",
            d.get("state") or "",
            d.get("decision"),
            "; ".join(d.get("reasons") or []),
            "; ".join(d.get("actions") or []),
        ]
        for d in o["decisions"]
        if not d.get("noop")
    ]
    _table(rows, ["session", "workspace", "agent", "branch", "state", "decision", "reasons", "actions"])
    print(f"{'DRY RUN ' if o['dry_run'] else ''}{o['host']}: {o['counts']} (jev: {o['jev']})")
    if o.get("escalation_summary"):
        print(o["escalation_summary"])


def _parse_answers(items: list[str] | None):
    if not items:
        return None
    if all("=" not in i for i in items):
        return items
    out = {}
    for i in items:
        k, sep, v = i.partition("=")
        if not sep:
            raise BatError("use --answer 'question=answer' (or only positional answers)")
        out[k] = v
    return out


async def _run(args) -> Any:
    cfg = load_config(args.config)
    fleet = Fleet(cfg, read_only=args.read_only, idle_timeout=0, actor="cli")
    try:
        c = args.cmd
        if c == "hosts":
            return await service.hosts_list(fleet, probe=not args.no_probe), r_hosts
        if c == "status":
            return await service.host_status(fleet, args.host), r_status
        if c == "workspaces":
            return await service.workspaces_list(fleet, args.host), r_workspaces
        if c == "sessions":
            return await service.sessions_list(
                fleet,
                args.host,
                args.workspace,
                args.agent,
                args.loaded,
                args.active_within,
                args.pending,
                not args.fast,
                args.limit,
            ), r_sessions
        if c == "read":
            return await service.session_read(
                fleet, args.host, args.session, args.n, args.offset, args.tools, args.max_chars, after=args.after
            ), r_read
        if c == "wait":
            return await service.session_wait(
                fleet, args.host, args.session, args.until, args.timeout, args.require_new, after=args.after
            ), None
        if c == "send":
            text = sys.stdin.read() if args.text == "-" else args.text
            return await service.session_send(
                fleet, args.host, args.session, text, args.confirm, args.message_id, True, args.queue
            ), None
        if c == "continue":
            return await service.session_continue(
                fleet, args.host, args.session, args.confirm, args.text, args.queue
            ), None
        if c == "interrupt":
            return await service.session_interrupt(
                fleet, args.host, args.session, args.mode, args.confirm
            ), None
        if c == "answer":
            return await service.session_answer(
                fleet,
                args.host,
                args.session,
                args.confirm,
                _parse_answers(args.answer),
                args.permission,
                args.deny_message,
                args.tool_use_id,
                args.dont_ask_again,
            ), None
        if c in ("triage", "quota"):
            states = ["quota_exhausted"] if c == "quota" else args.state
            return await triage.sessions_triage(
                fleet, args.host, args.workspace, args.agent, states, args.jev, not args.loaded_only
            ), r_triage
        if c == "permissions":
            return await lifecycle.session_set_permissions(
                fleet, args.host, args.session, args.mode, args.confirm
            ), None
        if c in ("relay", "fanout-plan"):
            msg = sys.stdin.read() if args.message == "-" else args.message
            brief = json.loads(args.brief) if args.brief and args.brief.lstrip().startswith("{") else args.brief
            if c == "relay":
                return await lifecycle.session_relay(
                    fleet, args.host, msg, args.workspace, args.session, args.channel, args.thread,
                    args.earlier, brief, args.fanout is not None, args.fanout, args.confirm, args.dry_run, args.queue,
                    args.start_if_missing,
                ), None
            return await lifecycle.fanout_plan_session(
                fleet, args.host, args.workspace, msg, args.max_items, args.channel, args.thread, args.earlier,
                brief, args.confirm,
            ), None
        if c == "fanout-start":
            return await lifecycle.fanout_from_plan(
                fleet, args.host, args.session, args.confirm, args.dry_run, args.agent, None, args.max_items
            ), None
        if c == "approve-pending":
            return await lifecycle.approve_pending(
                fleet, args.host, args.confirm, args.dry_run, args.workspace
            ), None
        if c == "failover":
            return await lifecycle.session_failover(
                fleet,
                args.host,
                args.session,
                args.confirm,
                args.all_exhausted,
                args.dry_run,
                args.model,
                args.force,
                args.tail,
                args.workspace,
                args.instructions,
                args.archive_only,
            ), None
        if c == "cleanup":
            return await lifecycle.session_cleanup(
                fleet, args.host, args.confirm, not args.apply, args.session
            ), r_cleanup
        if c == "record-verification":
            return await lifecycle.session_record_verification(
                fleet, args.host, args.session, args.commit, args.command, args.exit_code,
                args.environment, args.log_ref, args.confirm,
            ), None
        if c == "worktrees":
            return await orchestrate.worktree_status(fleet, args.host, args.workspace), None
        if c == "wt-status":
            return await orchestrate.session_worktree_status(
                fleet, args.host, args.session, args.diff, args.max_diff_chars
            ), None
        if c == "start":
            prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
            return await orchestrate.session_start(
                fleet,
                args.host,
                args.workspace,
                args.agent,
                args.confirm,
                prompt,
                args.model,
                not args.no_worktree,
                args.title,
            ), None
        if c == "merge":
            return await orchestrate.worktree_merge(fleet, args.host, args.session, args.confirm), None
        if c == "remove-worktree":
            return await orchestrate.worktree_remove(
                fleet,
                args.host,
                args.session,
                args.confirm,
                args.delete_branch,
                args.allow_unmerged,
                args.discard_uncommitted,
            ), None
        if c == "fanout":
            plan = orchestrate.fanout_plan(orchestrate.read_plan(args.plan), max_tasks=args.max_tasks)
            if not args.start:
                return plan, None
            if not (args.host and args.workspace):
                raise BatError("--start needs --host and --workspace")
            cap = fleet.config.safety.max_start_per_call
            if plan["count"] > cap:
                raise BatError(
                    f"plan has {plan['count']} tasks; max_start_per_call={cap}. Use --max-tasks or split"
                )
            started = []
            for tk in plan["tasks"]:
                try:
                    r = await orchestrate.session_start(
                        fleet,
                        args.host,
                        args.workspace,
                        args.agent,
                        args.confirm,
                        tk["prompt"],
                        args.model,
                        True,
                        f"fanout {tk['index']}: {tk['title'][:40]}",
                    )
                    started.append({"task": tk["index"], "title": tk["title"], **r})
                except BatError as e:
                    started.append({"task": tk["index"], "title": tk["title"], "error": redact(e)})
                    break
            return {"started": started, "count": len(started)}, None
        raise BatError(f"unknown command {c}")
    finally:
        await fleet.close()


def cmd_import(args) -> int:
    profs = read_bat_profiles(args.profiles_dir)
    rename = dict(r.split("=", 1) for r in args.rename or [])
    text = render_hosts_toml(profs, profiles_dir=args.profiles_dir, rename=rename, only=args.only)
    if args.output == "-":
        print(text)
        return 0
    out = Path(args.output).expanduser() if args.output else default_config_path()
    if out.exists() and not args.force:
        print(f"{out} exists; pass --force to overwrite (or --output -)", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    print(
        f"wrote {out} ({len([p for p in profs if not args.only or p['id'] in args.only])} hosts, writes disabled)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="batc", description="Better Agent Terminal connector CLI (unofficial)")
    ap.add_argument("--config", help=f"hosts.toml (default {default_config_path()})")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--read-only", action="store_true", help="refuse all write commands regardless of config")
    ap.add_argument("--version", action="version", version=__version__)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("hosts", help="list configured hosts (+ probe)")
    p.add_argument("--no-probe", action="store_true")
    p = sp.add_parser("status", help="host status")
    p.add_argument("host")
    p = sp.add_parser("workspaces", help="list workspaces")
    p.add_argument("host", nargs="?")
    p = sp.add_parser("sessions", help="list agent sessions, most recent first")
    p.add_argument("host", nargs="?")
    p.add_argument("--workspace")
    p.add_argument("--agent", choices=["claude", "codex"])
    p.add_argument("--loaded", action="store_true", help="only sessions loaded in the host runtime")
    p.add_argument("--active-within", type=float, metavar="HOURS")
    p.add_argument("--pending", choices=["auto", "all", "none"], default="auto")
    p.add_argument("--fast", action="store_true", help="skip transcript/archive lookups for last activity")
    p.add_argument("--limit", type=int, default=50)
    p = sp.add_parser("read", help="read latest messages of a session")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("-n", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--tools", action="store_true", help="include tool calls")
    p.add_argument("--max-chars", type=int, default=12000)
    p.add_argument("--after", help="turn_marker from relay/send: show only newer messages")
    p = sp.add_parser("wait", help="wait for turn-end / ask-user")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--until", choices=["attention", "turn-end", "ask-user"], default="attention")
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--require-new", action="store_true")
    p.add_argument("--after", help="turn_marker from relay/send: wait for the reply to that send")

    p = sp.add_parser("send", help="WRITE: send a message (needs --confirm and writes=true)")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("text", help="message text, or - for stdin")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--message-id")
    p.add_argument("--queue", action="store_true", help="queue behind a running turn")
    p = sp.add_parser("continue", help="WRITE: nudge a session with 'continue'")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--text", default="continue")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--queue", action="store_true")
    p = sp.add_parser("interrupt", help="WRITE: interrupt the running turn")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--mode", choices=["soft", "hard"], default="soft")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("answer", help="WRITE: answer a pending question / permission")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--answer", action="append", help="'question=answer' or positional answer (repeatable)")
    p.add_argument("--permission", choices=["allow", "deny"])
    p.add_argument("--deny-message")
    p.add_argument("--tool-use-id")
    p.add_argument("--dont-ask-again", action="store_true", help="Codex: accept for the rest of the session")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("triage", help="classify sessions (quota / waiting / working / done), pattern + optional Jev")
    p.add_argument("host", nargs="?")
    p.add_argument("--workspace")
    p.add_argument("--agent", choices=["claude", "codex"])
    p.add_argument("--state", action="append", choices=list(triage.STATES))
    p.add_argument("--jev", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--loaded-only", action="store_true")
    p = sp.add_parser("quota", help="list sessions stuck on a quota / usage limit (with evidence)")
    p.add_argument("host", nargs="?")
    p.add_argument("--workspace")
    p.add_argument("--agent", choices=["claude", "codex"])
    p.add_argument("--jev", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--loaded-only", action="store_true")
    p = sp.add_parser("permissions", help="WRITE: set a live session's permission mode (allow_all|default)")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--mode", choices=["allow_all", "default"], default="allow_all")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("approve-pending", help="WRITE: approve all pending permission prompts on a host")
    p.add_argument("host")
    p.add_argument("--workspace")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")

    p = sp.add_parser("relay", help="WRITE: send a task verbatim + a labeled brief to a session (default: main)")
    p.add_argument("host")
    p.add_argument("--workspace")
    p.add_argument("--session")
    p.add_argument("--message", required=True, help="the person's exact words, or - for stdin")
    p.add_argument("--brief", help="relay's interpretation: text or JSON {goal, context, constraints, acceptance}")
    p.add_argument("--channel")
    p.add_argument("--thread")
    p.add_argument("--earlier", action="append", help="earlier message in the thread, verbatim (repeatable)")
    p.add_argument("--fanout", type=int, metavar="N", help="ask for a bat-fanout plan of at most N items")
    p.add_argument("--queue", action="store_true")
    p.add_argument("--start-if-missing", action="store_true", help="no session yet: start Codex in the main checkout")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("fanout-plan", help="ORCHESTRATE: start a read-only Codex planner for a bat-fanout plan")
    p.add_argument("host")
    p.add_argument("workspace")
    p.add_argument("--message", required=True)
    p.add_argument("--brief")
    p.add_argument("--max-items", type=int)
    p.add_argument("--channel")
    p.add_argument("--thread")
    p.add_argument("--earlier", action="append")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("fanout-start", help="ORCHESTRATE: start worktrees exactly per a session's bat-fanout block")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--agent", choices=["claude", "codex"], default="codex")
    p.add_argument("--max-items", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")

    p = sp.add_parser("worktrees", help="list worktree sessions on a host")
    p.add_argument("host")
    p.add_argument("--workspace")
    p = sp.add_parser("wt-status", help="worktree status of one session")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--diff", action="store_true")
    p.add_argument("--max-diff-chars", type=int, default=20000)
    p = sp.add_parser("start", help="ORCHESTRATE: start a session (default: in a new worktree)")
    p.add_argument("host")
    p.add_argument("workspace")
    p.add_argument("--agent", choices=["claude", "codex"], default="claude")
    p.add_argument("--prompt", help="initial prompt, or - for stdin")
    p.add_argument("--model")
    p.add_argument("--title")
    p.add_argument("--no-worktree", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("merge", help="ORCHESTRATE: merge a clean worktree branch (never forced)")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("remove-worktree", help="ORCHESTRATE: remove a worktree (keeps branch by default)")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--delete-branch", action="store_true")
    p.add_argument("--allow-unmerged", action="store_true")
    p.add_argument("--discard-uncommitted", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("failover", help="ORCHESTRATE: continue a quota-exhausted Claude session with Codex")
    p.add_argument("host")
    p.add_argument("session", nargs="?")
    p.add_argument("--all-exhausted", action="store_true")
    p.add_argument("--workspace", help="with --all-exhausted: limit to one workspace")
    p.add_argument("--model")
    p.add_argument("--tail", type=int, default=12, help="recent messages to include in the handoff")
    p.add_argument("--force", action="store_true", help="fail over even if not detected as exhausted")
    p.add_argument("--instructions", help="replace the default 'continue the task' steps (single session)")
    p.add_argument("--archive-only", action="store_true", help="cleanup never merges this successor's branch")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("cleanup", help="ORCHESTRATE: gated merge/clean/stop of finished sessions (dry run by default)")
    p.add_argument("host")
    p.add_argument("session", nargs="?")
    p.add_argument("--apply", action="store_true", help="act (needs --confirm and auto_cleanup = true)")
    p.add_argument("--dry-run", action="store_true", help="report only (default)")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("record-verification", help="ORCHESTRATE: bind a test run to the current clean commit")
    p.add_argument("host")
    p.add_argument("session")
    p.add_argument("--commit", required=True, help="full current candidate commit hash")
    p.add_argument("--command", required=True, help="exact verification command")
    p.add_argument("--exit-code", required=True, type=int)
    p.add_argument("--environment", required=True, help="where and with which runtime the command ran")
    p.add_argument("--log-ref", required=True, help="durable verification log path or URL")
    p.add_argument("--confirm", action="store_true")
    p = sp.add_parser("fanout", help="split a plan into worktree task prompts (and optionally start them)")
    p.add_argument("plan", help="markdown plan file")
    p.add_argument("--max-tasks", type=int, default=8)
    p.add_argument("--start", action="store_true", help="ORCHESTRATE: start one worktree session per task")
    p.add_argument("--host")
    p.add_argument("--workspace")
    p.add_argument("--agent", choices=["claude", "codex"], default="claude")
    p.add_argument("--model")
    p.add_argument("--confirm", action="store_true")

    p = sp.add_parser(
        "import-bat", help="generate hosts.toml from BAT's profiles/index.json (no tokens copied)"
    )
    p.add_argument("--profiles-dir", default=DEFAULT_BAT_PROFILES_DIR)
    p.add_argument("--output", help="output path (default: config path; - for stdout)")
    p.add_argument("--rename", action="append", metavar="PROFILE_ID=NAME")
    p.add_argument("--only", action="append", metavar="PROFILE_ID")
    p.add_argument("--force", action="store_true")
    sp.add_parser("mcp", help="run the MCP server on stdio (see bat-agent-connector-mcp --help)")
    p = sp.add_parser("serve", help="run the loopback task daemon and worker (no deployment is made)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18796)
    p.add_argument("--db", help="SQLite task journal path")
    sp.add_parser("config-path", help="print the config path")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["mcp"]:
        from .mcp_server import main as mcp_main

        mcp_main(argv[1:])
        return 0
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "serve":
            from .task_daemon import TaskDaemon

            asyncio.run(TaskDaemon(load_config(args.config), args.db).serve(args.host, args.port))
            return 0
        if args.cmd == "import-bat":
            return cmd_import(args)
        if args.cmd == "config-path":
            print(args.config or default_config_path())
            return 0
        obj, render = asyncio.run(_run(args))
        _print(obj, args.json, render)
        return 0
    except BatError as e:
        print(f"error: {redact(e)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
