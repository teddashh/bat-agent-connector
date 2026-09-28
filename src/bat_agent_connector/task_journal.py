"""SQLite authority for task, command, event and delivery state.

The service process is the only writer. Each short operation is a transaction;
network calls happen after committing an intent, never inside a transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

STATES = frozenset({
    "queued", "dispatching", "accepted", "running", "waiting_permission",
    "quota_limited", "human_owned", "needs_ted", "verifying", "done", "failed", "uncertain",
})
TERMINAL = frozenset({"done", "failed"})
ALLOWED = {
    "queued": {"dispatching", "uncertain", "failed", "needs_ted"},
    "dispatching": {"queued", "accepted", "running", "verifying", "uncertain", "failed", "needs_ted"},
    "accepted": {"running", "dispatching", "verifying", "uncertain", "needs_ted", "failed"},
    "running": {"accepted", "verifying", "waiting_permission", "quota_limited", "human_owned",
                "needs_ted", "uncertain", "failed"},
    "waiting_permission": {"running", "needs_ted", "human_owned", "uncertain", "failed"},
    "quota_limited": {"running", "needs_ted", "uncertain", "failed"},
    "human_owned": {"running", "needs_ted", "failed"},
    "needs_ted": {"running", "accepted", "failed", "uncertain"},
    "verifying": {"dispatching", "accepted", "running", "done", "needs_ted", "uncertain", "failed"},
    "uncertain": {"running", "accepted", "needs_ted", "failed"},
    "done": set(), "failed": set(),
}


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if not self.path.exists():
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        self.path.chmod(0o600)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        # Intent must survive a host crash before the network dispatch begins.
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, idem_key TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL,
                project TEXT NOT NULL, host TEXT NOT NULL, workspace TEXT NOT NULL,
                original_words TEXT NOT NULL, interpretation TEXT, discord_thread_id TEXT,
                recipe TEXT NOT NULL, acceptance TEXT NOT NULL, engine TEXT NOT NULL,
                state TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0, control_version INTEGER NOT NULL DEFAULT 0,
                session_id TEXT, reviewer_session_id TEXT, turn_marker TEXT,
                submitted_at REAL NOT NULL, updated_at REAL NOT NULL, delivered_at REAL,
                delivered INTEGER NOT NULL DEFAULT 0, review_rejections INTEGER NOT NULL DEFAULT 0,
                ted_interventions INTEGER NOT NULL DEFAULT 0, continuations INTEGER NOT NULL DEFAULT 0,
                review_passed INTEGER NOT NULL DEFAULT 0, verification_commit TEXT,
                verification_tree TEXT, review_commit TEXT, review_tree TEXT, review_marker TEXT,
                lead_agent TEXT NOT NULL DEFAULT 'codex', pm_provider TEXT, result TEXT
            );
            CREATE TABLE IF NOT EXISTS commands (
                command_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                idem_key TEXT NOT NULL UNIQUE, session_id TEXT, kind TEXT NOT NULL,
                status TEXT NOT NULL, message_id TEXT, marker TEXT, payload TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                kind TEXT NOT NULL, body TEXT NOT NULL, created_at REAL NOT NULL,
                discord_message_id TEXT, discord_status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS board (
                board_key TEXT PRIMARY KEY, message_id TEXT, rendered TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS routing (
                route_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                step TEXT NOT NULL, step_type TEXT NOT NULL, provider TEXT NOT NULL,
                confidence REAL, stakes TEXT NOT NULL, reason TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provider_usage (
                usage_id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
                outcome TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capabilities (
                token_hash TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(task_id),
                scope TEXT NOT NULL, expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observed_verifications (
                verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL REFERENCES tasks(task_id), candidate_commit TEXT NOT NULL,
                tree_hash TEXT NOT NULL, command TEXT NOT NULL, exit_code INTEGER NOT NULL,
                log_ref TEXT NOT NULL, output_sha256 TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daemon_owner (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner_id TEXT NOT NULL,
                pid INTEGER NOT NULL, heartbeat_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ted_actions (
                task_id TEXT NOT NULL REFERENCES tasks(task_id), source_message_id TEXT NOT NULL,
                action TEXT NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY(task_id,source_message_id)
            );
            CREATE TABLE IF NOT EXISTS branches (
                branch_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                session_id TEXT, provider TEXT NOT NULL, role TEXT NOT NULL,
                parent_branch_id TEXT, reason TEXT NOT NULL, created_at REAL NOT NULL,
                UNIQUE(task_id,session_id,role)
            );
            COMMIT;
        """)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(tasks)")}
        for name, sql_type in (("verification_tree", "TEXT"), ("review_commit", "TEXT"),
                               ("review_tree", "TEXT"), ("review_marker", "TEXT"),
                               ("lead_agent", "TEXT NOT NULL DEFAULT 'codex'"),
                               ("pm_provider", "TEXT")):
            if name not in columns:
                self.db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {sql_type}")  # noqa: S608 - fixed local identifiers

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()

    def issue_capability(self, task_id: str, *, ttl_s: int = 3600) -> str:
        self.get(task_id)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.db.execute("INSERT INTO capabilities(token_hash,task_id,scope,expires_at) VALUES(?,?,?,?)",
                        (digest, task_id, "task", time.time() + ttl_s))
        return token

    def authorize_capability(self, token: str, task_id: str) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self.db.execute("SELECT task_id,expires_at FROM capabilities WHERE token_hash=? AND scope='task'",
                              (digest,)).fetchone()
        return bool(row and row["task_id"] == task_id and row["expires_at"] > time.time())

    def record_observed_verification(self, task_id: str, evidence: dict) -> dict:
        required = {"candidate_commit", "tree_hash", "command", "exit_code", "log_ref", "output_sha256"}
        if required - evidence.keys() or evidence.get("source") != "observed_runner":
            raise ValueError("only observed runner evidence is accepted")
        with self.tx():
            cur = self.db.execute("""INSERT INTO observed_verifications
                (task_id,candidate_commit,tree_hash,command,exit_code,log_ref,output_sha256,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (task_id, evidence["candidate_commit"], evidence["tree_hash"],
                evidence["command"], evidence["exit_code"], evidence["log_ref"], evidence["output_sha256"],
                time.time()))
            self._event(task_id, "verification_observed", {"verification_id": cur.lastrowid,
                                                           "exit_code": evidence["exit_code"]})
        return dict(self.db.execute("SELECT * FROM observed_verifications WHERE verification_id=?",
                                    (cur.lastrowid,)).fetchone())

    def observed_verification(self, task_id: str) -> dict | None:
        row = self.db.execute("""SELECT * FROM observed_verifications WHERE task_id=?
            ORDER BY verification_id DESC LIMIT 1""", (task_id,)).fetchone()
        return dict(row) if row else None

    def _event(self, task_id: str, kind: str, body: dict | None = None):
        self.db.execute(
            "INSERT INTO events(task_id,kind,body,created_at) VALUES(?,?,?,?)",
            (task_id, kind, json.dumps(body or {}, ensure_ascii=False), time.time()),
        )

    def submit(self, *, project: str, host: str, workspace: str, original_words: str,
               discord_thread_id: str | None = None, recipe: str = "feature-to-staging",
               acceptance: str = "", engine: str = "rules", interpretation: str | None = None,
               lead_agent: str = "codex", pm_provider: str | None = None,
               idempotency_key: str) -> dict:
        if not all(isinstance(x, str) and x.strip() for x in (project, host, workspace, original_words, idempotency_key)):
            raise ValueError("project, host, workspace, original_words and idempotency_key are required")
        if len(original_words) > 18_000 or len(idempotency_key) > 256 or len(acceptance) > 4000:
            raise ValueError("task input is too long")
        if interpretation is not None and len(interpretation) > 4000:
            raise ValueError("interpretation note is too long")
        if engine not in {"rules", "goose"}:
            raise ValueError("unknown engine")
        if lead_agent not in {"codex", "claude"}:
            raise ValueError("lead_agent must be codex or claude")
        if pm_provider is not None and (not isinstance(pm_provider, str) or not pm_provider
                                        or len(pm_provider) > 100):
            raise ValueError("invalid PM provider id")
        from .task_recipes import load

        load(recipe)
        payload = dict(project=project, host=host, workspace=workspace, original_words=original_words,
                       discord_thread_id=discord_thread_id, recipe=recipe, acceptance=acceptance,
                       engine=engine, interpretation=interpretation, lead_agent=lead_agent,
                       pm_provider=pm_provider)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.tx():
            old = self.db.execute("SELECT * FROM tasks WHERE idem_key=?", (idempotency_key,)).fetchone()
            if old:
                if old["payload_hash"] != digest:
                    raise ValueError("idempotency_key already belongs to different task content")
                return dict(old)
            now = time.time()
            task_id = str(uuid.uuid4())
            self.db.execute("""INSERT INTO tasks(task_id,idem_key,payload_hash,project,host,workspace,
                original_words,interpretation,discord_thread_id,recipe,acceptance,engine,lead_agent,
                pm_provider,state,submitted_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id, idempotency_key, digest, project, host, workspace, original_words,
                 interpretation, discord_thread_id, recipe, acceptance, engine, lead_agent,
                 pm_provider, "queued", now, now))
            self._event(task_id, "submitted", {"state": "queued"})
        return self.get(task_id)

    def get(self, task_id: str) -> dict:
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        d = dict(row)
        d["paused"] = bool(d["paused"])
        d["delivered"] = bool(d["delivered"])
        d["review_passed"] = bool(d["review_passed"])
        d["time_to_deliver_s"] = (d["delivered_at"] - d["submitted_at"]) if d["delivered_at"] else None
        d["branches"] = self.branches(task_id)
        d["branch_ids"] = [b["branch_id"] for b in d["branches"]]
        return d

    def add_branch(self, task_id: str, *, session_id: str | None, provider: str,
                   role: str, reason: str, parent_branch_id: str | None = None) -> dict:
        with self.tx():
            old = (self.db.execute("SELECT * FROM branches WHERE task_id=? AND session_id=? AND role=?",
                                   (task_id, session_id, role)).fetchone() if session_id is not None else None)
            if old:
                return dict(old)
            branch_id = str(uuid.uuid4())
            self.db.execute("""INSERT INTO branches(branch_id,task_id,session_id,provider,role,
                parent_branch_id,reason,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                (branch_id, task_id, session_id, provider, role, parent_branch_id, reason, time.time()))
            self._event(task_id, "task_branch", {"branch_id": branch_id, "provider": provider,
                                                 "role": role, "reason": reason})
        return dict(self.db.execute("SELECT * FROM branches WHERE branch_id=?", (branch_id,)).fetchone())

    def branches(self, task_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM branches WHERE task_id=? ORDER BY created_at, rowid", (task_id,))]

    def list_active(self) -> list[dict]:
        ids = self.db.execute("SELECT task_id FROM tasks WHERE state NOT IN ('done','failed') ORDER BY submitted_at").fetchall()
        return [self.get(r[0]) for r in ids]

    def change(self, task_id: str, state: str, *, fields: dict | None = None, event: str | None = None):
        if state not in STATES:
            raise ValueError("invalid task state")
        fields = fields or {}
        allowed = {"session_id", "reviewer_session_id", "turn_marker", "result", "continuations",
                   "review_rejections", "review_passed", "verification_commit", "verification_tree",
                   "review_commit", "review_tree", "review_marker", "ted_interventions", "lead_agent"}
        if fields.keys() - allowed:
            raise ValueError("invalid task fields")
        with self.tx():
            old = self.get(task_id)
            if old["state"] in TERMINAL and old["state"] != state:
                raise ValueError("terminal task cannot transition")
            if old["state"] != state and state not in ALLOWED[old["state"]]:
                raise ValueError(f"invalid transition {old['state']} -> {state}")
            values = {**old, **fields, "state": state, "updated_at": time.time()}
            if state == "done":
                observed = self.observed_verification(task_id)
                if (not values["review_passed"] or not observed or observed["exit_code"] != 0
                        or values["verification_commit"] != observed["candidate_commit"]
                        or values["verification_tree"] != observed["tree_hash"]
                        or values["review_commit"] != observed["candidate_commit"]
                        or values["review_tree"] != observed["tree_hash"]):
                    raise ValueError("fresh review and observed commit/tree verification required")
                values.update(delivered=1, delivered_at=time.time())
            self.db.execute("""UPDATE tasks SET state=?,updated_at=?,session_id=?,reviewer_session_id=?,
                turn_marker=?,result=?,continuations=?,review_rejections=?,review_passed=?,
                verification_commit=?,verification_tree=?,review_commit=?,review_tree=?,review_marker=?,
                lead_agent=?,ted_interventions=?,delivered=?,delivered_at=? WHERE task_id=?""",
                (values["state"], values["updated_at"], values["session_id"], values["reviewer_session_id"],
                 values["turn_marker"], values["result"], values["continuations"], values["review_rejections"],
                 values["review_passed"], values["verification_commit"], values["verification_tree"],
                 values["review_commit"], values["review_tree"], values["review_marker"], values["lead_agent"],
                 values["ted_interventions"],
                 values["delivered"], values["delivered_at"], task_id))
            if old["state"] != state or event:
                self._event(task_id, event or "state", {"from": old["state"], "to": state})
        return self.get(task_id)

    def pause(self, task_id: str, *, abort_current: bool = False):
        with self.tx():
            old = self.get(task_id)
            if old["state"] in TERMINAL:
                return old
            self.db.execute("UPDATE tasks SET paused=1,control_version=control_version+1,updated_at=? WHERE task_id=?",
                            (time.time(), task_id))
            self._event(task_id, "paused", {"abort_current": abort_current})
        return self.get(task_id)

    def resume(self, task_id: str):
        with self.tx():
            old = self.get(task_id)
            if old["state"] in TERMINAL:
                return old
            self.db.execute("UPDATE tasks SET paused=0,control_version=control_version+1,updated_at=? WHERE task_id=?",
                            (time.time(), task_id))
            self._event(task_id, "resumed")
        task = self.get(task_id)
        if task["state"] in {"needs_ted", "human_owned"} and task["session_id"]:
            return self.change(task_id, "running")
        return task

    def ted_action(self, task_id: str, *, action: str, source_message_id: str):
        if not action or not source_message_id:
            raise ValueError("Ted action requires provenance")
        with self.tx():
            cur = self.db.execute("""INSERT OR IGNORE INTO ted_actions(task_id,source_message_id,action,created_at)
                VALUES(?,?,?,?)""", (task_id, source_message_id, action, time.time()))
            if not cur.rowcount:
                return
            self.db.execute("UPDATE tasks SET ted_interventions=ted_interventions+1 WHERE task_id=?", (task_id,))
            self._event(task_id, "ted_intervention", {"action": action, "source_message_id": source_message_id})

    def request_ted(self, task_id: str, reason: str):
        with self.tx():
            self._event(task_id, "ted_requested", {"reason": reason[:1000]})

    def command(self, task_id: str, kind: str, session_id: str | None, payload: dict, idem_key: str):
        with self.tx():
            old = self.db.execute("SELECT * FROM commands WHERE idem_key=?", (idem_key,)).fetchone()
            if old:
                return dict(old), False
            task = self.get(task_id)
            if (task["paused"] or task["state"] in TERMINAL or
                    task["state"] in {"human_owned", "uncertain", "needs_ted"}):
                raise ValueError("task does not allow dispatch")
            if kind == "send" and task["state"] not in {"accepted", "running", "verifying", "dispatching"}:
                raise ValueError("task state does not allow a prompt")
            unresolved = self.db.execute("""SELECT 1 FROM commands WHERE task_id=?
                AND status IN ('intent','needs_review','uncertain')
                AND (kind='send' OR kind='failover' OR kind LIKE 'start_%') LIMIT 1""",
                (task_id,)).fetchone()
            if unresolved:
                raise ValueError("task has a command requiring reconciliation")
            command_id = str(uuid.uuid4())
            now = time.time()
            self.db.execute("""INSERT INTO commands(command_id,task_id,idem_key,session_id,kind,status,
                message_id,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (command_id, task_id, idem_key, session_id, kind,
                 "needs_review" if kind == "send" else "intent", f"batc-{command_id}",
                 json.dumps(payload, ensure_ascii=False), now, now))
            self._event(task_id, "command_intent", {"command_id": command_id, "kind": kind,
                                                     "needs_review": kind == "send"})
        return dict(self.db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()), True

    def command_status(self, command_id: str, status: str, *, marker: str | None = None):
        if status not in {"intent", "needs_review", "accepted", "running", "settled", "uncertain",
                          "rejected", "cancelled"}:
            raise ValueError("invalid command status")
        with self.tx():
            row = self.db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise KeyError(command_id)
            self.db.execute("UPDATE commands SET status=?,marker=COALESCE(?,marker),updated_at=? WHERE command_id=?",
                            (status, marker, time.time(), command_id))
            self._event(row["task_id"], "command_" + status, {"command_id": command_id})

    def command_bind_session(self, command_id: str, session_id: str):
        self.db.execute("UPDATE commands SET session_id=?,updated_at=? WHERE command_id=?",
                        (session_id, time.time(), command_id))

    def commands(self, task_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM commands WHERE task_id=? ORDER BY created_at", (task_id,))]

    def events(self, task_id: str | None = None) -> list[dict]:
        if task_id:
            rows = self.db.execute("SELECT * FROM events WHERE task_id=? ORDER BY event_id", (task_id,))
        else:
            rows = self.db.execute("SELECT * FROM events ORDER BY event_id")
        return [dict(r) for r in rows]

    def route(self, task_id: str, *, step: str, step_type: str, provider: str,
              confidence: float | None, stakes: str, reason: str) -> dict:
        with self.tx():
            now = time.time()
            cur = self.db.execute("""INSERT INTO routing(task_id,step,step_type,provider,confidence,stakes,reason,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (task_id, step, step_type, provider, confidence, stakes, reason, now))
            self._event(task_id, "model_route", {"route_id": cur.lastrowid, "step_type": step_type,
                                                  "provider": provider, "confidence": confidence, "stakes": stakes})
        return dict(self.db.execute("SELECT * FROM routing WHERE route_id=?", (cur.lastrowid,)).fetchone())

    def routes(self, task_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM routing WHERE task_id=? ORDER BY route_id", (task_id,))]

    def provider_use(self, provider: str, outcome: str):
        if outcome not in {"success", "quota_error", "rate_limited", "auth_error"}:
            raise ValueError("invalid provider outcome")
        self.db.execute("INSERT INTO provider_usage(provider,outcome,created_at) VALUES(?,?,?)",
                        (provider, outcome, time.time()))

    def provider_daily_count(self, provider: str, *, since: float) -> int:
        return self.db.execute("SELECT count(*) FROM provider_usage WHERE provider=? AND created_at>=? AND outcome='success'",
                               (provider, since)).fetchone()[0]

    def provider_unavailable(self, provider: str, *, since: float) -> bool:
        row = self.db.execute("""SELECT outcome FROM provider_usage WHERE provider=? AND created_at>=?
            ORDER BY usage_id DESC LIMIT 1""", (provider, since)).fetchone()
        return bool(row and row[0] in {"quota_error", "rate_limited", "auth_error"})

    def discord_events(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("""SELECT e.*,t.discord_thread_id FROM events e
            JOIN tasks t USING(task_id) WHERE e.discord_status='pending' AND t.discord_thread_id IS NOT NULL
            ORDER BY e.event_id""")]

    def discord_inflight(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("""SELECT e.*,t.discord_thread_id FROM events e
            JOIN tasks t USING(task_id) WHERE e.discord_status='sending' AND t.discord_thread_id IS NOT NULL
            ORDER BY e.event_id""")]

    def discord_unresolved(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("""SELECT e.*,t.discord_thread_id FROM events e
            JOIN tasks t USING(task_id) WHERE e.discord_status='unresolved' AND t.discord_thread_id IS NOT NULL
            ORDER BY e.event_id""")]

    def claim_discord_event(self, event_id: int) -> bool:
        with self.tx():
            cur = self.db.execute("UPDATE events SET discord_status='sending' WHERE event_id=? AND discord_status='pending'",
                                  (event_id,))
            return cur.rowcount == 1

    def mark_discord_event(self, event_id: int, message_id: str):
        self.db.execute("UPDATE events SET discord_status='sent',discord_message_id=? WHERE event_id=? AND discord_status='sending'",
                        (message_id, event_id))

    def discord_mark_unresolved(self, event_id: int):
        self.db.execute("UPDATE events SET discord_status='unresolved' WHERE event_id=? AND discord_status='sending'",
                        (event_id,))

    def discord_confirm_absent(self, event_id: int):
        """Operator-confirmed retry after inspecting Discord history; never automatic."""
        self.db.execute("UPDATE events SET discord_status='pending' WHERE event_id=? AND discord_status='unresolved'",
                        (event_id,))

    def board_get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT * FROM board WHERE board_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def board_claim(self, key: str, rendered: str) -> bool:
        with self.tx():
            row = self.board_get(key)
            if row and (row["status"] in {"sending", "unresolved"} or
                        (row["rendered"] == rendered and row["status"] == "sent")):
                return False
            self.db.execute("""INSERT INTO board(board_key,message_id,rendered,status) VALUES(?,?,?,'sending')
                ON CONFLICT(board_key) DO UPDATE SET rendered=excluded.rendered,status='sending'""",
                (key, row["message_id"] if row else None, rendered))
            return True

    def board_sent(self, key: str, message_id: str):
        self.db.execute("UPDATE board SET message_id=?,status='sent' WHERE board_key=? AND status='sending'",
                        (message_id, key))

    def board_mark_unresolved(self, key: str):
        self.db.execute("UPDATE board SET status='unresolved' WHERE board_key=? AND status='sending'", (key,))

    def board_retry_edit(self, key: str):
        self.db.execute("UPDATE board SET status='pending' WHERE board_key=? AND status='sending' AND message_id IS NOT NULL",
                        (key,))

    def board_confirm_absent(self, key: str):
        self.db.execute("UPDATE board SET status='pending' WHERE board_key=? AND status='unresolved'", (key,))
