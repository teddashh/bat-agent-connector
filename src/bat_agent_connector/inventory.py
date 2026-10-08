"""Persisted session inventory for /api/v1: what each host had, when it was seen, and whether that is stale.

A refresher polls each configured host with its own read-only Fleet (every write channel is refused in the client
core, so observation can never change BAT), upserts one row per (host, session_id), and appends an /api/v1 event
only when something material changed. An unreachable host keeps its last rows, marked stale, instead of dropping
them; a row is only marked gone after two consecutive successful enumerations without it.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import time
from dataclasses import dataclass

from . import service
from .config import Config
from .fleet import Fleet
from .redact import redact

# Changes to these fields produce a session.updated event; activity time alone does not.
MATERIAL = ("workspace", "workspace_id", "title", "cwd", "agent_kind", "agent_preset", "model", "loaded",
            "streaming", "runtime_status", "pending", "worktree_branch", "orchestrated", "has_tab", "provenance",
            "api_access", "read_only_code", "isolation", "write_scope", "confinement", "current_verification")
GONE_AFTER_MISSES = 2
MAX_PAGE = 200


@dataclass
class InventorySettings:
    interval_s: float = 60.0
    stale_after_s: float = 180.0
    activity_every: int = 5  # transcript/archive lookups every Nth refresh (they are the slow part)
    max_backoff_s: float = 600.0


def _material(row: dict) -> dict:
    return {k: row.get(k) for k in MATERIAL}


def _digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(_material(row), sort_keys=True, default=str).encode()).hexdigest()


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Inventory:
    def __init__(self, journal, config: Config, settings: InventorySettings | None = None,
                 fleet: Fleet | None = None) -> None:
        self.journal = journal
        self.db = journal.db
        self.config = config
        self.settings = settings or InventorySettings()
        # Observation must never be able to write, whatever the host tiers say.
        self.fleet = fleet or Fleet(config, read_only=True, idle_timeout=0, actor="inventory")
        self._runs: dict[str, int] = {}
        self._next_at: dict[str, float] = {}

    # ------------------------------------------------------------------ refresh
    async def refresh_host(self, host: str) -> dict:
        self.config.host(host)
        runs = self._runs.get(host, 0)
        self._runs[host] = runs + 1
        activity = runs % max(1, self.settings.activity_every) == 0
        started = time.time()
        try:
            rows = await service._host_sessions(self.fleet, host, None, None, "auto", activity)
            if not rows and self._has_live_rows(host):
                await self._confirm_empty(host)  # a null workspace document must not mark every session gone
            version = self.fleet.client(host).auth_info.get("serverVersion")
        except Exception as exc:  # noqa: BLE001 - recorded on the host row; rows stay and turn stale
            return self._record_failure(host, started, exc)
        return self._record_success(host, started, rows, version)

    def _has_live_rows(self, host: str) -> bool:
        return self.db.execute("SELECT 1 FROM sessions_observed WHERE host=? AND gone_at IS NULL LIMIT 1",
                               (host,)).fetchone() is not None

    async def _confirm_empty(self, host: str) -> None:
        c = self.fleet.client(host)
        raw = await c.invoke("workspace:load", {"profileId": c.host.profile_id})
        if isinstance(raw, str):
            with contextlib.suppress(ValueError):
                raw = json.loads(raw)
        if not (isinstance(raw, dict) and isinstance(raw.get("terminals"), list)):
            raise ValueError("workspace:load returned no workspace document")

    @staticmethod
    def _merge_previous(row: dict, prev_body: dict, *, meta_failed: bool) -> dict:
        """What one refresh did not observe stays as last observed; an unobserved field is not a new fact."""
        if meta_failed:  # the session's meta read failed: keep the last good row
            return {**prev_body, **{k: row[k] for k in ("provenance", "api_access", "read_only_code", "isolation")
                                    if k in row}}
        if not row.pop("pending_checked", False) and row.get("loaded") and prev_body.get("pending"):
            row["pending"] = prev_body["pending"]  # not re-read this time (auto check): still pending
        if (row.get("last_activity_ms") or 0) < (prev_body.get("last_activity_ms") or 0):
            # Cheap refreshes see fewer activity sources; activity never moves backwards.
            row["last_activity_ms"] = prev_body["last_activity_ms"]
            row["last_activity_source"] = prev_body.get("last_activity_source")
        return row

    def _record_failure(self, host: str, at: float, exc: BaseException) -> dict:
        error = redact(f"{type(exc).__name__}: {exc}")[:300]
        with self.journal.tx():
            old = self.db.execute("SELECT * FROM hosts_observed WHERE host=?", (host,)).fetchone()
            failures = (old["consecutive_failures"] if old else 0) + 1
            self.db.execute("""INSERT INTO hosts_observed(host,reachable,error,last_attempt_at,consecutive_failures)
                VALUES(?,0,?,?,?) ON CONFLICT(host) DO UPDATE SET reachable=0,error=excluded.error,
                last_attempt_at=excluded.last_attempt_at,consecutive_failures=excluded.consecutive_failures""",
                            (host, error, at, failures))
            if old is None or old["reachable"]:
                self.journal.api_event("host", host, "host.unreachable", {"error": error})
        return {"host": host, "reachable": False, "error": error, "consecutive_failures": failures}

    def _record_success(self, host: str, at: float, rows: list[dict], version: str | None) -> dict:
        added = updated = gone = 0
        with self.journal.tx():
            old_host = self.db.execute("SELECT reachable FROM hosts_observed WHERE host=?", (host,)).fetchone()
            seen: set[str] = set()
            for raw in rows:
                sid = raw.get("session_id")
                if not isinstance(sid, str) or not sid:
                    continue
                seen.add(sid)
                prev = self.db.execute("""SELECT digest,gone_at,body FROM sessions_observed
                    WHERE host=? AND session_id=?""", (host, sid)).fetchone()
                row = {k: v for k, v in raw.items() if k != "meta_error"}
                if prev is not None:
                    row = self._merge_previous(row, json.loads(prev["body"]), meta_failed="meta_error" in raw)
                row.pop("pending_checked", None)
                activity = row.get("last_activity_ms") or 0
                digest = _digest(row)
                self.db.execute("""INSERT INTO sessions_observed(host,session_id,body,digest,provenance,api_access,
                    attention,sort_key,first_seen_at,last_seen_at,missing_count,gone_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,0,NULL) ON CONFLICT(host,session_id) DO UPDATE SET
                    body=excluded.body,digest=excluded.digest,provenance=excluded.provenance,
                    api_access=excluded.api_access,attention=excluded.attention,sort_key=excluded.sort_key,
                    last_seen_at=excluded.last_seen_at,missing_count=0,gone_at=NULL""",
                                (host, sid, json.dumps(row, default=str), digest, row.get("provenance") or "unknown",
                                 row.get("api_access") or "read_only", 1 if row.get("pending") else 0,
                                 -int(activity), at, at))
                if prev is None:
                    added += 1
                    self.journal.api_event("session", f"{host}/{sid}", "session.added", _material(row))
                elif prev["digest"] != digest or prev["gone_at"] is not None:
                    updated += 1
                    self.journal.api_event("session", f"{host}/{sid}", "session.updated", _material(row))
            for missing in self.db.execute("""SELECT session_id,missing_count FROM sessions_observed
                    WHERE host=? AND gone_at IS NULL""", (host,)).fetchall():
                if missing["session_id"] in seen:
                    continue
                misses = missing["missing_count"] + 1
                if misses >= GONE_AFTER_MISSES:
                    gone += 1
                    self.db.execute("""UPDATE sessions_observed SET missing_count=?,gone_at=?
                        WHERE host=? AND session_id=?""", (misses, at, host, missing["session_id"]))
                    self.journal.api_event("session", f"{host}/{missing['session_id']}", "session.gone",
                                           {"misses": misses})
                else:
                    self.db.execute("UPDATE sessions_observed SET missing_count=? WHERE host=? AND session_id=?",
                                    (misses, host, missing["session_id"]))
            self.db.execute("""INSERT INTO hosts_observed(host,reachable,error,server_version,last_attempt_at,
                last_success_at,consecutive_failures,session_count) VALUES(?,1,NULL,?,?,?,0,?)
                ON CONFLICT(host) DO UPDATE SET reachable=1,error=NULL,server_version=excluded.server_version,
                last_attempt_at=excluded.last_attempt_at,last_success_at=excluded.last_success_at,
                consecutive_failures=0,session_count=excluded.session_count""",
                            (host, version, at, at, len(seen)))
            if old_host is None or not old_host["reachable"]:
                self.journal.api_event("host", host, "host.reachable", {"sessions": len(seen)})
        return {"host": host, "reachable": True, "sessions": len(seen), "added": added, "updated": updated,
                "gone": gone}

    async def refresh_all(self) -> list[dict]:
        return list(await asyncio.gather(*(self.refresh_host(h) for h in self.config.hosts)))

    async def _refresh_scheduled(self, host: str) -> None:
        try:
            result = await self.refresh_host(host)
        except Exception:  # noqa: BLE001 - refresh_host records its own failures; this is a last resort
            result = {"consecutive_failures": 1}
        failures = result.get("consecutive_failures", 0)
        delay = (self.settings.interval_s if not failures
                 else min(self.settings.max_backoff_s, self.settings.interval_s * 2 ** min(failures, 6)))
        self._next_at[host] = time.time() + delay
        with contextlib.suppress(Exception):
            await self.fleet.client(host).close()  # do not hold an idle socket between refreshes

    async def loop(self) -> None:
        """Refresh each host on its own schedule, independently: a slow host never delays the others.
        Failures back off up to max_backoff_s."""
        running: dict[str, asyncio.Task] = {}
        try:
            while True:
                now = time.time()
                for host in self.config.hosts:
                    task = running.get(host)
                    if (task is None or task.done()) and self._next_at.get(host, 0) <= now:
                        running[host] = asyncio.create_task(self._refresh_scheduled(host),
                                                            name=f"inventory-{host}")
                await asyncio.sleep(1.0)
        finally:
            for task in running.values():
                task.cancel()

    async def close(self) -> None:
        await self.fleet.close()

    # ------------------------------------------------------------------ reads
    def hosts(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        observed = {r["host"]: dict(r) for r in self.db.execute("SELECT * FROM hosts_observed")}
        out = []
        for name in self.config.hosts:
            r = observed.get(name) or {}
            stale, reason = self._host_stale(r, now)
            out.append({"host": name, "reachable": bool(r.get("reachable")), "error": r.get("error"),
                        "server_version": r.get("server_version"), "sessions": r.get("session_count"),
                        "last_attempt_at": _iso(r.get("last_attempt_at")),
                        "last_success_at": _iso(r.get("last_success_at")),
                        "consecutive_failures": r.get("consecutive_failures", 0), "stale": stale,
                        "stale_reason": reason})
        return out

    def _host_stale(self, r: dict, now: float) -> tuple[bool, str | None]:
        if not r:
            return True, "never_observed"
        if not r.get("reachable"):
            return True, "host_unreachable"
        if now - (r.get("last_success_at") or 0) > self.settings.stale_after_s:
            return True, "host_not_refreshed"
        return False, None

    def _session_out(self, r, hosts: dict, now: float) -> dict:
        body = json.loads(r["body"])
        stale, reason = self._host_stale(hosts.get(r["host"]) or {}, now)
        if r["gone_at"] is not None:
            stale, reason = True, "gone"
        elif not stale and now - r["last_seen_at"] > self.settings.stale_after_s:
            stale, reason = True, "not_enumerated"
        activity = body.pop("last_activity_ms", None)
        body.pop("last_activity", None)
        body.pop("last_activity_age", None)
        return {**body, "host": r["host"], "session_id": r["session_id"], "last_activity_ms": activity,
                "last_activity_at": _iso(activity / 1000) if activity else None,
                "first_seen_at": _iso(r["first_seen_at"]), "observed_at": _iso(r["last_seen_at"]),
                "gone_at": _iso(r["gone_at"]), "stale": stale, "stale_reason": reason}

    def get_session(self, host: str, session_id: str, now: float | None = None) -> dict | None:
        r = self.db.execute("SELECT * FROM sessions_observed WHERE host=? AND session_id=?",
                            (host, session_id)).fetchone()
        if r is None:
            return None
        hosts = {h["host"]: dict(h) for h in self.db.execute("SELECT * FROM hosts_observed")}
        return self._session_out(r, hosts, now or time.time())

    def list_sessions(self, *, host: str | None = None, provenance: str | None = None,
                      api_access: str | None = None, attention: bool | None = None, include_gone: bool = False,
                      order: str = "activity", cursor: str | None = None, limit: int = 50,
                      now: float | None = None) -> dict:
        """Keyset-paged inventory. Page 1 returns ``as_of`` (the event cursor at read time); follow
        /api/v1/events?after=as_of for changes instead of re-listing."""
        if order not in {"activity", "id"}:
            raise ValueError("order must be activity or id")
        limit = max(1, min(MAX_PAGE, int(limit)))
        filters = {"host": host, "provenance": provenance, "api_access": api_access, "attention": attention,
                   "include_gone": include_gone, "order": order}
        fhash = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:16]
        key, as_of = None, None
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode() + b"=" * (-len(cursor) % 4)))
                if decoded["f"] != fhash:
                    raise ValueError
                key, as_of = decoded["k"], int(decoded["a"])
            except (ValueError, KeyError, TypeError):
                raise ValueError("cursor does not match these filters; start again without it") from None
        as_of = as_of if as_of is not None else self.journal.api_head()
        configured = list(self.config.hosts) or [""]  # rows of hosts removed from the config are not listed
        sql = f"SELECT * FROM sessions_observed WHERE host IN ({','.join('?' * len(configured))})"  # noqa: S608
        args = list(configured)
        for column, value in (("host", host), ("provenance", provenance), ("api_access", api_access)):
            if value:
                sql, args = sql + f" AND {column}=?", [*args, value]  # fixed identifiers only
        if attention is not None:
            sql, args = sql + " AND attention=?", [*args, 1 if attention else 0]
        if not include_gone:
            sql += " AND gone_at IS NULL"
        cols = ("sort_key", "host", "session_id") if order == "activity" else ("host", "session_id")
        if key is not None:
            if len(key) != len(cols):
                raise ValueError("cursor does not match these filters; start again without it")
            sql += f" AND ({','.join(cols)}) > ({','.join('?' * len(cols))})"
            args += list(key)
        rows = self.db.execute(sql + f" ORDER BY {','.join(cols)} LIMIT ?", (*args, limit + 1)).fetchall()
        now = now or time.time()
        hosts = {h["host"]: dict(h) for h in self.db.execute("SELECT * FROM hosts_observed")}
        items = [self._session_out(r, hosts, now) for r in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            payload = {"f": fhash, "a": as_of, "k": [last[c] for c in cols]}
            next_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return {"sessions": items, "count": len(items), "next_cursor": next_cursor, "as_of": as_of,
                "hosts": self.hosts(now)}
