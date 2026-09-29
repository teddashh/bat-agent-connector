"""Push milestone events to one generic, locally configured JSON webhook.

The service does not know who receives the callback or where it is shown.
Events are sent in cursor order; the push cursor only advances after a 2xx,
so a failed push is retried with capped exponential backoff and nothing is
skipped. Receivers catch up with ``work_events`` after any outage.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from .task_journal import Journal

MAX_BACKOFF_S = 300
BATCH = 20


def validate_callback_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("event webhook URL must be a loopback http(s) URL without credentials")
    return url


@dataclass(frozen=True)
class EventWebhook:
    url: str
    secret: str = ""
    timeout_s: float = 10.0


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Generic HMAC-SHA256 over ``<timestamp>.<body>`` (hex)."""
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class EventPusher:
    def __init__(self, journal: Journal, webhook: EventWebhook | None, *, repo_urls: dict | None = None,
                 clock=time.time):
        self.journal = journal
        self.webhook = webhook
        self.repo_urls = repo_urls or {}
        self.clock = clock

    def _post(self, payload: dict, request_id: str) -> int:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        timestamp = str(int(self.clock()))
        headers = {"Content-Type": "application/json", "X-Request-ID": request_id,
                   "User-Agent": "bat-agent-connector-event-push"}
        if self.webhook.secret:
            headers["X-Webhook-Timestamp"] = timestamp
            headers["X-Webhook-Signature-V2"] = sign(self.webhook.secret, timestamp, body)
        req = urllib.request.Request(self.webhook.url, method="POST", data=body, headers=headers)  # noqa: S310
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=self.webhook.timeout_s) as resp:  # noqa: S310 - loopback validated
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code

    async def run_once(self) -> int:
        """Push pending milestones; return how many were acknowledged."""
        if self.webhook is None:
            return 0
        state = self.journal.push_state()
        if state is None:
            # First configuration starts at "now": history is never pushed.
            state = self.journal.push_init(self.journal.head_cursor())
        if self.clock() < state["next_attempt_at"]:
            return 0
        feed = self.journal.milestones(state["cursor"], BATCH, repo_urls=self.repo_urls)
        acked = 0
        cursor = state["cursor"]
        for event in feed["events"]:
            payload = {**event, "type": "task.milestone", "delivered_through": cursor}
            request_id = f"batc-milestone-{event['cursor']}-{state['failures']}"
            try:
                status = await asyncio.to_thread(self._post, payload, request_id)
                error = None if 200 <= status < 300 else f"HTTP {status}"
            except Exception as exc:  # noqa: BLE001 - retried with backoff
                error = type(exc).__name__
            if error:
                failures = state["failures"] + 1
                self.journal.push_failed(error, self.clock() + min(MAX_BACKOFF_S, 2 ** min(failures, 9)))
                logging.warning("Milestone push %s failed (%s); retry with backoff", event["cursor"], error)
                return acked
            cursor = event["cursor"]
            self.journal.push_advance(cursor)
            state = {**state, "cursor": cursor, "failures": 0}
            acked += 1
        if feed["next_cursor"] > cursor and len(feed["events"]) < BATCH:
            self.journal.push_advance(feed["next_cursor"])
        return acked
