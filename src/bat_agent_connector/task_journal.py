"""SQLite authority for task, command, event and delivery state.

The service process is the only writer. Each short operation is a transaction;
network calls happen after committing an intent, never inside a transaction.
"""

from __future__ import annotations

import hashlib
import json
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
    "dispatching": {"accepted", "running", "verifying", "uncertain", "failed", "needs_ted"},
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
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
                review_passed INTEGER NOT NULL DEFAULT 0, verification_commit TEXT, result TEXT
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
        """)

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

    def _event(self, task_id: str, kind: str, body: dict | None = None):
        self.db.execute(
            "INSERT INTO events(task_id,kind,body,created_at) VALUES(?,?,?,?)",
            (task_id, kind, json.dumps(body or {}, ensure_ascii=False), time.time()),
        )

    def submit(self, *, project: str, host: str, workspace: str, original_words: str,
               discord_thread_id: str | None = None, recipe: str = "feature-to-staging",
               acceptance: str = "", engine: str = "rules", interpretation: str | None = None,
               idempotency_key: str) -> dict:
        if not all(isinstance(x, str) and x.strip() for x in (project, host, workspace, original_words, idempotency_key)):
            raise ValueError("project, host, workspace, original_words and idempotency_key are required")
        if engine not in {"rules", "goose"}:
            raise ValueError("unknown engine")
        from .task_recipes import load

        load(recipe)
        payload = dict(project=project, host=host, workspace=workspace, original_words=original_words,
                       discord_thread_id=discord_thread_id, recipe=recipe, acceptance=acceptance,
                       engine=engine, interpretation=interpretation)
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
                original_words,interpretation,discord_thread_id,recipe,acceptance,engine,state,submitted_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id, idempotency_key, digest, project, host, workspace, original_words,
                 interpretation, discord_thread_id, recipe, acceptance, engine, "queued", now, now))
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
        return d

    def list_active(self) -> list[dict]:
        ids = self.db.execute("SELECT task_id FROM tasks WHERE state NOT IN ('done','failed') ORDER BY submitted_at").fetchall()
        return [self.get(r[0]) for r in ids]

    def change(self, task_id: str, state: str, *, fields: dict | None = None, event: str | None = None):
        if state not in STATES:
            raise ValueError("invalid task state")
        fields = fields or {}
        allowed = {"session_id", "reviewer_session_id", "turn_marker", "result", "continuations",
                   "review_rejections", "review_passed", "verification_commit", "ted_interventions"}
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
                if not (old["review_passed"] or fields.get("review_passed")) or not (
                    old["verification_commit"] or fields.get("verification_commit")
                ):
                    raise ValueError("review and commit-bound verification required")
                values.update(delivered=1, delivered_at=time.time())
            self.db.execute("""UPDATE tasks SET state=?,updated_at=?,session_id=?,reviewer_session_id=?,
                turn_marker=?,result=?,continuations=?,review_rejections=?,review_passed=?,
                verification_commit=?,ted_interventions=?,delivered=?,delivered_at=? WHERE task_id=?""",
                (values["state"], values["updated_at"], values["session_id"], values["reviewer_session_id"],
                 values["turn_marker"], values["result"], values["continuations"], values["review_rejections"],
                 values["review_passed"], values["verification_commit"], values["ted_interventions"],
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

    def intervention(self, task_id: str):
        with self.tx():
            self.db.execute("UPDATE tasks SET ted_interventions=ted_interventions+1 WHERE task_id=?", (task_id,))
            self._event(task_id, "ted_intervention")

    def command(self, task_id: str, kind: str, session_id: str | None, payload: dict, idem_key: str):
        with self.tx():
            old = self.db.execute("SELECT * FROM commands WHERE idem_key=?", (idem_key,)).fetchone()
            if old:
                return dict(old), False
            task = self.get(task_id)
            if task["paused"] or task["state"] in TERMINAL or task["state"] == "human_owned":
                raise ValueError("task does not allow dispatch")
            command_id = str(uuid.uuid4())
            now = time.time()
            self.db.execute("""INSERT INTO commands(command_id,task_id,idem_key,session_id,kind,status,
                message_id,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (command_id, task_id, idem_key, session_id, kind, "intent", f"batc-{command_id}",
                 json.dumps(payload, ensure_ascii=False), now, now))
            self._event(task_id, "command_intent", {"command_id": command_id, "kind": kind})
        return dict(self.db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()), True

    def command_status(self, command_id: str, status: str, *, marker: str | None = None):
        if status not in {"intent", "accepted", "running", "settled", "uncertain", "rejected"}:
            raise ValueError("invalid command status")
        with self.tx():
            row = self.db.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise KeyError(command_id)
            self.db.execute("UPDATE commands SET status=?,marker=COALESCE(?,marker),updated_at=? WHERE command_id=?",
                            (status, marker, time.time(), command_id))
            self._event(row["task_id"], "command_" + status, {"command_id": command_id})

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
        if outcome not in {"success", "quota_error", "rate_limited"}:
            raise ValueError("invalid provider outcome")
        self.db.execute("INSERT INTO provider_usage(provider,outcome,created_at) VALUES(?,?,?)",
                        (provider, outcome, time.time()))

    def provider_daily_count(self, provider: str, *, since: float) -> int:
        return self.db.execute("SELECT count(*) FROM provider_usage WHERE provider=? AND created_at>=? AND outcome='success'",
                               (provider, since)).fetchone()[0]

    def provider_unavailable(self, provider: str, *, since: float) -> bool:
        row = self.db.execute("""SELECT outcome FROM provider_usage WHERE provider=? AND created_at>=?
            ORDER BY usage_id DESC LIMIT 1""", (provider, since)).fetchone()
        return bool(row and row[0] in {"quota_error", "rate_limited"})

    def discord_events(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("""SELECT e.*,t.discord_thread_id FROM events e
            JOIN tasks t USING(task_id) WHERE e.discord_status='pending' AND t.discord_thread_id IS NOT NULL
            ORDER BY e.event_id""")]

    def claim_discord_event(self, event_id: int) -> bool:
        with self.tx():
            cur = self.db.execute("UPDATE events SET discord_status='sending' WHERE event_id=? AND discord_status='pending'",
                                  (event_id,))
            return cur.rowcount == 1

    def mark_discord_event(self, event_id: int, message_id: str):
        self.db.execute("UPDATE events SET discord_status='sent',discord_message_id=? WHERE event_id=? AND discord_status='sending'",
                        (message_id, event_id))

    def board_get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT * FROM board WHERE board_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def board_claim(self, key: str, rendered: str) -> bool:
        with self.tx():
            row = self.board_get(key)
            if row and (row["status"] == "sending" or
                        (row["rendered"] == rendered and row["status"] == "sent")):
                return False
            self.db.execute("""INSERT INTO board(board_key,message_id,rendered,status) VALUES(?,?,?,'sending')
                ON CONFLICT(board_key) DO UPDATE SET rendered=excluded.rendered,status='sending'""",
                (key, row["message_id"] if row else None, rendered))
            return True

    def board_sent(self, key: str, message_id: str):
        self.db.execute("UPDATE board SET message_id=?,status='sent' WHERE board_key=? AND status='sending'",
                        (message_id, key))
