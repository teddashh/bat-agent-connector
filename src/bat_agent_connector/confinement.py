"""Execution evidence, separate from resource ownership. BAT source: docs/design/confinement.md.

No settings files, probes, privilege changes or new BAT channels. OS sandbox settings are evidence of options,
not of enforcement: only the W12 live run can prove A10. Existing creation snapshots are never upgraded by reads.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shlex
import time

from . import registry
from .errors import WriteRefused

BAT_SOURCE = "b7419892fbc9946799b64cca24c2ec8c7fa15c42"
CONFINED_OPTIONS = {
    "claude": {"permissionMode": "default"},
    "codex": {"codexSandboxMode": "workspace-write", "codexApprovalPolicy": "on-request"},
}
OPTION_KEYS = ("permissionMode", "codexSandboxMode", "codexApprovalPolicy")


class ConfinementRefused(WriteRefused):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def policy_options(agent: str, mode: str, claude_mode: str | None = None) -> dict:
    if mode == "confined":
        return dict(CONFINED_OPTIONS[agent])
    if agent == "claude":
        return {"permissionMode": claude_mode} if claude_mode else (
            {"permissionMode": "bypassPermissions"} if mode == "allow_all" else {})
    return {"codexSandboxMode": "danger-full-access", "codexApprovalPolicy": "never"} if mode == "allow_all" else {}


def recorded_options(entry: dict) -> dict:
    if "execution_options" in entry:
        return dict(entry["execution_options"])
    snapshot = entry.get("confinement") or {}
    if "options" in snapshot:
        return dict(snapshot["options"])
    params = entry.get("agent_params") or {}
    options = {"permissionMode": entry.get("permission_mode_claude"),
               "codexSandboxMode": params.get("sandboxMode"), "codexApprovalPolicy": params.get("approvalPolicy")}
    return {k: v for k, v in options.items() if v}


def snapshot(agent: str, options: dict, *, account: dict | None = None, task: bool = False,
             inherited: dict | None = None) -> dict:
    options = {k: options[k] for k in OPTION_KEYS if options.get(k)}
    full = options.get("permissionMode") in {"bypassPermissions", "bypassPlan", "acceptEdits", "auto"}
    full = full or options.get("codexSandboxMode") == "danger-full-access"
    level = "none"
    mechanisms, limits = [], ["individual_approval_can_escape", "network_not_configurable"]
    account_ok = (account or {}).get("status") == "verified"
    if account_ok:
        mechanisms.append("host_account")
        limits.extend(["host_account_declared_roots_only", "account_check_is_point_in_time",
                       "hardlinks_and_privilege_paths_unverified"])
    if agent == "codex" and options.get("codexSandboxMode") in {"workspace-write", "read-only"}:
        level = "os_sandbox"
        mechanisms.append("codex_" + options["codexSandboxMode"].replace("-", "_"))
        limits.append("writable_roots_not_configurable")
    elif agent == "claude" and options.get("permissionMode") in {"default", "plan", "dontAsk"}:
        level = "prompt_gated"
        mechanisms.append("claude_permissions")
        limits.append("preapproved_rules_and_shell_can_write_outside")
    if account_ok and options.get("permissionMode") != "bypassPermissions" and not (
            options.get("codexSandboxMode") == "danger-full-access"):
        level = "host_account"
    gap = ("task_recipe_compatibility" if task and (full or not options) else
           "sandbox_enforcement_unverified" if level == "os_sandbox" else
           "prompt_rules_are_not_os_isolation" if level == "prompt_gated" else
           "execution_restriction_unverified" if level == "none" else None)
    return {"schema_version": 1, "level": level, "requested_level": level, "mechanisms": mechanisms,
            "options": options, "protected_roots": list((account or {}).get("protected_roots") or []),
            "evidence": {"source": "start_intent", "bat_source_commit": BAT_SOURCE,
                         "host_check": copy.deepcopy(account), "inherited_from": inherited,
                         "agent": agent, "task_owned": task},
            "verification": {"status": "pending", "reason": "start_not_confirmed"},
            "limits": limits, "gap": gap}


def verify(record: dict, meta: dict | None) -> dict:
    if not isinstance(meta, dict):
        return {"status": "unknown", "reason": "session_unloaded", "observed_options": {}}
    options = record.get("options") or {}
    observed = {k: meta[k] for k in OPTION_KEYS if meta.get(k)}
    if any(k in observed and observed[k] != v for k, v in options.items()):
        return {"status": "mismatch", "reason": "permission_options_changed", "observed_options": observed}
    if not options or any(k not in observed for k in options):
        return {"status": "unknown", "reason": "permission_options_missing", "observed_options": observed}
    account = (record.get("evidence") or {}).get("host_check") or {}
    return {"status": "verified" if record.get("level") == "host_account" and account.get("status") == "verified"
            else "options_confirmed", "reason": record.get("gap"), "observed_options": observed}


def confirm(record: dict, meta: dict | None) -> dict:
    result = copy.deepcopy(record)
    if not result.get("options") and isinstance(meta, dict):
        actual = {k: meta[k] for k in OPTION_KEYS if meta.get(k)}
        if actual:
            evidence = result["evidence"]
            result = snapshot(evidence["agent"], actual, account=evidence.get("host_check"),
                              task=evidence.get("task_owned", False), inherited=evidence.get("inherited_from"))
            if record.get("gap") == "task_recipe_compatibility":
                result["gap"] = record["gap"]
    result["verification"] = verify(result, meta)
    result["evidence"].update(source="start_intent_and_bat_meta",
                                observed_options=result["verification"]["observed_options"], checked_at=time.time())
    return result


def ensure_confirmed(record: dict, meta: dict | None) -> None:
    state = verify(record, meta)
    if state["status"] in {"unknown", "mismatch"} and record.get("options"):
        raise ConfinementRefused("CONFINEMENT_MISMATCH", state["reason"])


def session_fields(host: str, sid: str, meta: dict | None = None, *, account: dict | None = None) -> dict:
    entry = registry.get(host, sid) or {}
    record = entry.get("confinement") or {
        "schema_version": 1, "level": "none", "requested_level": "none", "mechanisms": [],
        "options": recorded_options(entry), "evidence": {"source": "legacy_registry"},
        "verification": {"status": "unknown", "reason": "legacy_evidence_missing"},
        "limits": ["legacy_evidence_missing"], "gap": "legacy_evidence_missing"}
    current = verify({**record, "options": recorded_options(entry)}, meta)
    current["matches_creation"] = recorded_options(entry) == record.get("options")
    if record.get("level") == "host_account":
        current["host_check"] = copy.deepcopy(account)
        if not account or account.get("status") != "verified":
            current.update(status="unknown", reason="host_account_unverified")
    return {"write_scope": entry.get("write_scope"), "confinement": copy.deepcopy(record),
            "current_verification": current}


def guard_raise(host: str, sid: str) -> None:
    if (registry.get(host, sid) or {}).get("write_scope") == "confined":
        raise ConfinementRefused("CONFINEMENT_RAISE_REFUSED", "confined sessions cannot raise permissions")


def guard_permissions(host: str, sid: str, options: dict) -> None:
    entry = registry.get(host, sid) or {}
    if entry.get("write_scope") == "confined" and options != recorded_options(entry):
        raise ConfinementRefused("CONFINEMENT_RAISE_REFUSED", "confined permission changes must preserve its policy")


def guard_loaded(host: str, sid: str, meta: dict | None) -> None:
    entry = registry.get(host, sid) or {}
    record = entry.get("confinement")
    if entry.get("write_scope") == "confined" and record and record.get("options"):
        ensure_confirmed(record, meta)


def resume_options(host: str, sid: str, agent: str) -> dict:
    entry = registry.get(host, sid) or {}
    options = recorded_options(entry)
    required = ("permissionMode",) if agent == "claude" else ("codexSandboxMode", "codexApprovalPolicy")
    if entry.get("write_scope") == "confined" and any(not options.get(k) for k in required):
        raise ConfinementRefused("CONFINEMENT_EVIDENCE_MISSING", "confined resume requires its original policy")
    return options


def guard_answer(host: str, sid: str, tool: str | None, *, dont_ask_again: bool, allow: bool) -> None:
    if allow and (registry.get(host, sid) or {}).get("write_scope") == "confined":
        if dont_ask_again or tool == "ExitPlanMode":
            raise ConfinementRefused("CONFINEMENT_RAISE_REFUSED", "confined approval cannot persist wider permissions")


def account_status(fleet, host: str) -> dict:
    config = fleet.config.host(host).confinement
    result = getattr(fleet, "_confinement_checks", {}).get(host)
    signature = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if not result and getattr(fleet, "confinement_journal", None):
        row = fleet.confinement_journal.db.execute(
            "SELECT evidence FROM confinement_host_checks WHERE host=?", (host,)).fetchone()
        result = json.loads(row[0]) if row else None
    if result and result.get("config_sha256") == signature:
        if time.time() - result["checked_at"] <= config.get("check_max_age_s", 300):
            return copy.deepcopy(result)
    return {"declared": bool(config.get("host_account")), "status": "unknown", "reason": "unchecked_or_stale",
            "protected_roots": list(config.get("protected_roots") or []), "checked_at": None,
            "config_sha256": signature}


async def check_account(fleet, host: str) -> dict:
    config = fleet.config.host(host).confinement
    result = account_status(fleet, host)
    if not config.get("host_account"):
        return result
    try:
        runner = getattr(fleet, "confinement_runner", None)
        if runner is None:
            from .checkpoints import SshGitRunner
            from .task_verifier import load_settings
            runner = SshGitRunner(load_settings().ssh_hosts)
        if not runner.available(host):
            raise ValueError("ssh_alias_unavailable")
        raw = await runner.run(host, account_script(config), timeout_s=config.get("check_timeout_s", 10) + 2)
        observation = json.loads(raw)
        if observation.get("status") not in {"verified", "unknown", "mismatch"}:
            raise ValueError("invalid_account_check")
        result.update(observation)
    except Exception as exc:  # noqa: BLE001 - absence of a check never proves protection
        result.update(status="unknown", reason=type(exc).__name__)
    result.update(declared=True, checked_at=time.time(), protected_roots=list(config.get("protected_roots") or []))
    result["evidence_ref"] = "host_account:" + host + ":" + str(result["checked_at"])
    if not hasattr(fleet, "_confinement_checks"):
        fleet._confinement_checks = {}
    fleet._confinement_checks[host] = result
    journal = getattr(fleet, "confinement_journal", None)
    if journal:
        journal.db.execute("INSERT OR REPLACE INTO confinement_host_checks(host,evidence) VALUES(?,?)",
                           (host, json.dumps(result, sort_keys=True)))
    return copy.deepcopy(result)


async def start_account(fleet, host: str) -> dict:
    result = await check_account(fleet, host)
    if result["declared"] and result["status"] != "verified":
        raise ConfinementRefused("HOST_ACCOUNT_UNVERIFIED", result["reason"])
    return result


async def start_decision(fleet, host: str, agent: str, *, confined: bool = False, task: bool = False,
                         planner: bool = False, claude_mode: str | None = None, predecessor: dict | None = None):
    account = await start_account(fleet, host)
    mode = fleet.config.host(host).default_permission_mode
    if task and mode == "confined":
        mode = "default"  # Keep the existing Task Service engine/recipe behavior.
    confined = confined or (not task and mode == "confined") or planner
    if confined and claude_mode not in (None, "default", "plan", "dontAsk"):
        raise ConfinementRefused("CONFINEMENT_RAISE_REFUSED", "confined start cannot request a wider mode")
    options = dict(CONFINED_OPTIONS[agent]) if confined else policy_options(agent, mode, claude_mode)
    if confined and agent == "claude" and account["status"] == "verified":
        options["permissionMode"] = "acceptEdits"
    if planner:
        options = {"codexSandboxMode": "read-only", "codexApprovalPolicy": "never"}
    if predecessor:
        previous = resume_options(host, predecessor["session_id"],
                                  (predecessor.get("confinement") or {}).get("evidence", {}).get("agent", "claude"))
        protected = (predecessor.get("confinement") or {}).get("protected_roots") or []
        if protected and (account["status"] != "verified" or not set(protected) <= set(account["protected_roots"])):
            raise ConfinementRefused("CONFINEMENT_UNSUPPORTED", "successor cannot preserve protected roots")
        if previous.get("codexSandboxMode") == "read-only" or previous.get("permissionMode") == "plan":
            options = {"codexSandboxMode": "read-only", "codexApprovalPolicy": "never"}
        elif previous.get("codexApprovalPolicy") == "never" or previous.get("permissionMode") == "dontAsk":
            options["codexApprovalPolicy"] = "never"
    record = snapshot(agent, options, account=account, task=task,
                      inherited={"session_id": predecessor["session_id"],
                                 "limits": (predecessor.get("confinement") or {}).get("limits", [])}
                      if predecessor else None)
    if predecessor:
        record["limits"] = list(dict.fromkeys(record["limits"] +
                                             (predecessor.get("confinement") or {}).get("limits", [])))
    if task and fleet.config.host(host).default_permission_mode == "confined":
        record["gap"] = "task_recipe_compatibility"
    return options, "confined" if confined else None, record


def host_capability(fleet, host: str) -> dict:
    account = account_status(fleet, host)
    verified = account["status"] == "verified"
    return {"policy": fleet.config.host(host).default_permission_mode, "host_account": account,
            "network_configurable": False, "writable_roots_configurable": False,
            "agents": {"claude": {"requested_level": "host_account" if verified else "prompt_gated",
                                   "verified_level": "host_account" if verified else "none",
                                   "reachable_options": ["permissionMode"],
                                   "limits": ["preapproved_rules_and_shell_can_write_outside",
                                              "host_account_declared_roots_only"], "gap": None if verified else
                                   "plain_default_requires_approvals"},
                       "codex": {"requested_level": "os_sandbox", "verified_level": "none",
                                 "reachable_options": ["codexSandboxMode", "codexApprovalPolicy"],
                                 "limits": ["individual_approval_can_escape", "writable_roots_not_configurable",
                                            "network_not_configurable"], "gap": "sandbox_enforcement_unverified"}}}


def account_script(config: dict) -> str:
    """Linux-only metadata scan. GNU find evaluates ACLs; no probe or hand-written ACL evaluator."""
    payload = json.dumps({"uid": config["expected_uid"], "roots": config["protected_roots"],
                          "entries": config.get("check_max_entries", 10000),
                          "seconds": config.get("check_timeout_s", 10), "port": config.get("bat_port", 9876)})
    return "python3 -B - " + shlex.quote(payload) + " <<'BATC_CONFINEMENT'\n" + _ACCOUNT_PROGRAM + "\nBATC_CONFINEMENT"


_ACCOUNT_PROGRAM = r'''
import json, os, pathlib, selectors, stat, subprocess, sys, time
c = json.loads(sys.argv[1]); deadline = time.monotonic() + c['seconds']; remaining = c['entries']
def finish(status, reason, **evidence):
    print(json.dumps(dict(status=status, reason=reason, **evidence))); raise SystemExit
def budget():
    if time.monotonic() >= deadline: finish('unknown', 'time_budget_exhausted')
if not sys.platform.startswith('linux'): finish('unknown', 'linux_only')
if os.geteuid() != c['uid'] or os.getuid() != c['uid']: finish('unknown', 'ssh_uid_mismatch')
groups = sorted(set(os.getgroups() + [os.getegid()]))
def identity(pid):
    text = pathlib.Path('/proc', str(pid), 'status').read_text()
    values = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
    return dict(pid=int(pid), ppid=int(values['PPid']), uid=[int(x) for x in values['Uid'].split()],
                gid=[int(x) for x in values['Gid'].split()], groups=sorted(int(x) for x in values['Groups'].split()),
                capabilities=int(values['CapEff'].strip(), 16))
try:
    sockets = set()
    for table in ('tcp', 'tcp6'):
        for line in pathlib.Path('/proc/net', table).read_text().splitlines()[1:]:
            parts = line.split()
            if parts[3] == '0A' and int(parts[1].split(':')[1], 16) == c['port']: sockets.add(parts[9])
    procs = {}; bats = []; names = {}
    for proc in pathlib.Path('/proc').iterdir():
        budget()
        if not proc.name.isdigit(): continue
        try:
            info = identity(proc.name); procs[info['pid']] = info
            name = (proc/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'); names[info['pid']] = name
            if 'bat-server' in name or 'better-agent-terminal' in name:
                if any(os.readlink(fd) in {'socket:[' + x + ']' for x in sockets} for fd in (proc/'fd').iterdir()):
                    bats.append(info)
        except (OSError, ValueError, KeyError): continue
    if len(bats) != 1: finish('unknown', 'bat_process_unidentified')
    bat = bats[0]; descendants = {bat['pid']}
    for _ in range(len(procs)):
        more = {p for p, i in procs.items() if i['ppid'] in descendants}
        if more <= descendants: break
        descendants |= more
    runtimes = [procs[p] for p in descendants - {bat['pid']} if any(
        token in names[p] for token in ('claude', 'codex', 'node-sidecar', 'server.mjs'))]
    if not runtimes: finish('unknown', 'runtime_process_unidentified')
    for i in [bat] + runtimes:
        if any(u != c['uid'] for u in i['uid']) or len(set(i['gid'])) != 1 or i['gid'][1] != os.getegid() or i['groups'] != sorted(os.getgroups()):
            finish('unknown', 'runtime_identity_mismatch')
        if i['capabilities']: finish('mismatch', 'runtime_has_capabilities')
    before = []
    for root in c['roots']:
        budget(); path = pathlib.Path(root)
        if not path.is_dir() or path.is_symlink() or str(path.resolve()) != str(path): finish('unknown', 'root_unresolved')
        info = path.stat(); before.append((root, info.st_dev, info.st_ino))
        child = path
        for parent in path.parents:
            budget(); info = parent.stat(); victim = child.stat()
            if info.st_uid == os.geteuid(): finish('mismatch', 'owned_ancestor_can_chmod')
            if os.access(parent, os.W_OK | os.X_OK, effective_ids=True) and (not info.st_mode & stat.S_ISVTX or os.geteuid() in (info.st_uid, victim.st_uid)):
                finish('mismatch', 'writable_ancestor')
            child = parent
        proc = subprocess.Popen(['find', root, '-xdev', '-printf', 'E:%D\n', '-writable', '-printf', 'W\n', '-quit', '-o', '-uid', str(c['uid']), '-printf', 'O\n', '-quit', '-o', '-type', 'l', '-printf', 'L\n', '-quit'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        selector = selectors.DefaultSelector(); selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            pending = b''
            while True:
                budget()
                ready = selector.select(max(0, deadline - time.monotonic()))
                if not ready: finish('unknown', 'time_budget_exhausted')
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk: break
                pending += chunk
                lines = pending.split(b'\n'); pending = lines.pop()
                for line in lines:
                    if line == b'W': finish('mismatch', 'writable_entry')
                    if line == b'O': finish('mismatch', 'owned_entry_can_chmod')
                    if line == b'L': finish('unknown', 'symlink_unchecked')
                    if not line.startswith(b'E:'): finish('unknown', 'find_output_invalid')
                    if int(line[2:]) != path.stat().st_dev: finish('unknown', 'mount_unchecked')
                    remaining -= 1
                    if remaining <= 0: finish('unknown', 'entry_budget_exhausted')
            _, errors = proc.communicate(timeout=max(.01, deadline - time.monotonic()))
            if proc.returncode or errors: finish('unknown', 'find_incomplete')
        finally:
            selector.close()
            if proc.poll() is None: proc.kill(); proc.wait()
    if any((os.stat(p).st_dev, os.stat(p).st_ino) != (dev, ino) for p, dev, ino in before): finish('unknown', 'root_changed')
    if any(identity(i['pid']) != i for i in [bat] + runtimes): finish('unknown', 'runtime_changed')
    finish('verified', 'read_only_account_check', alias_uid=os.geteuid(), bat=bat, runtimes=runtimes, roots=before)
except (OSError, ValueError, KeyError, subprocess.TimeoutExpired): finish('unknown', 'check_incomplete')
'''


def record_task_start(journal, task_id: str, sid: str, entry: dict) -> None:
    """Add evidence at the existing start-command write point, before BAT gets the frame."""
    if journal is None:
        return
    command = next((c for c in journal.commands(task_id) if c["session_id"] == sid
                    and c["kind"] in {"start_lead", "start_reviewer"}), None)
    if command:
        payload = json.loads(command["payload"])
        payload.update({k: entry[k] for k in ("confinement", "write_scope", "permission_mode_claude", "agent_params")
                        if k in entry})
        journal.db.execute("UPDATE commands SET payload=? WHERE command_id=?",
                           (json.dumps(payload), command["command_id"]))


async def guard_frame(client, host: str, sid: str) -> None:
    entry = registry.get(host, sid) or {}
    if entry.get("write_scope") == "confined" and entry.get("confinement"):
        guard_loaded(host, sid, await client.guard_read("claude:get-session-meta", {"sessionId": sid}))


def guard_resume_frame(host: str, sid: str, agent: str, frame: dict) -> None:
    original = resume_options(host, sid, agent)
    if (registry.get(host, sid) or {}).get("write_scope") == "confined":
        actual = frame["params"].get("options") or {}
        if any(actual.get(k) != v for k, v in original.items()):
            raise ConfinementRefused("CONFINEMENT_MISMATCH", "resume frame differs from the recorded policy")


async def guard_start_frame(fleet, host: str) -> None:
    # Fresh identity/ACL evidence at the start boundary, after worktree preparation.
    if fleet.config.host(host).confinement.get("host_account"):
        await start_account(fleet, host)
