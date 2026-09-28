"""Discord event publisher. Event IDs are the deduplication key."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from typing import Protocol

from .task_journal import Journal


class DiscordAdapter(Protocol):
    async def post(self, channel_id: str, text: str) -> str: ...
    async def edit(self, channel_id: str, message_id: str, text: str) -> None: ...
    async def find_marker(self, channel_id: str, marker: str) -> str | None: ...


class DiscordHTTP:
    def __init__(self, token_env: str = "BATC_DISCORD_BOT_TOKEN"):  # noqa: S107 - environment variable name
        self.token_env = token_env

    def _request(self, method: str, path: str, text: str | None = None):
        token = os.environ.get(self.token_env)
        if not token:
            raise RuntimeError(f"{self.token_env} is not set")
        req = urllib.request.Request(
            "https://discord.com/api/v10" + path, method=method,
            data=json.dumps({"content": text}).encode() if text is not None else None,
            headers={"Authorization": "Bot " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed Discord HTTPS API
            return json.load(resp)

    async def post(self, channel_id: str, text: str) -> str:
        result = await asyncio.to_thread(self._request, "POST", f"/channels/{channel_id}/messages", text)
        return str(result["id"])

    async def edit(self, channel_id: str, message_id: str, text: str) -> None:
        await asyncio.to_thread(self._request, "PATCH", f"/channels/{channel_id}/messages/{message_id}", text)

    async def find_marker(self, channel_id: str, marker: str) -> str | None:
        me = await asyncio.to_thread(self._request, "GET", "/users/@me")
        rows = await asyncio.to_thread(self._request, "GET", f"/channels/{channel_id}/messages?limit=100")
        return next((str(r["id"]) for r in rows if r.get("author", {}).get("id") == me.get("id")
                     and marker in str(r.get("content") or "")), None)


class DiscordPublisher:
    def __init__(self, journal: Journal, adapter: DiscordAdapter, board_channel_id: str | None = None):
        self.journal = journal
        self.adapter = adapter
        self.board_channel_id = board_channel_id

    async def flush(self):
        await self.reconcile()
        for event in self.journal.discord_events():
            eid = event["event_id"]
            if not self.journal.claim_discord_event(eid):
                continue
            # If the request times out after Discord accepts it, 'sending' stays
            # unresolved for operator reconciliation. We never blindly repost.
            body = json.loads(event["body"])
            text = f"BATC-EVENT:{eid}\n任務 {event['task_id'][:8]} · {event['kind']}\n{json.dumps(body, ensure_ascii=False)}"
            message_id = await self.adapter.post(event["discord_thread_id"], text[:2000])
            self.journal.mark_discord_event(eid, message_id)
        if self.board_channel_id:
            await self.update_board()

    async def reconcile(self):
        for event in self.journal.discord_inflight():
            marker = f"BATC-EVENT:{event['event_id']}"
            found = await self.adapter.find_marker(event["discord_thread_id"], marker)
            if found:
                self.journal.mark_discord_event(event["event_id"], found)
            else:
                self.journal.discord_mark_unresolved(event["event_id"])
        if self.board_channel_id:
            row = self.journal.board_get(self.board_channel_id)
            if row and row["status"] == "sending":
                if row["message_id"]:
                    self.journal.board_retry_edit(self.board_channel_id)
                else:
                    marker = "BATC-BOARD:" + self.board_channel_id
                    found = await self.adapter.find_marker(self.board_channel_id, marker)
                    if found:
                        self.journal.board_sent(self.board_channel_id, found)
                    else:
                        self.journal.board_mark_unresolved(self.board_channel_id)

    async def update_board(self):
        tasks = self.journal.list_active()
        lines = ["BATC-BOARD:" + self.board_channel_id, "任務看板"] + [
            f"{t['task_id'][:8]} · {t['project']} · {t['state']}" for t in tasks[:40]
        ]
        content = "\n".join(lines)[:2000]
        key = self.board_channel_id
        if not self.journal.board_claim(key, content):
            return
        row = self.journal.board_get(key)
        if row and row["message_id"]:
            await self.adapter.edit(key, row["message_id"], content)
            message_id = row["message_id"]
        else:
            message_id = await self.adapter.post(key, content)
        self.journal.board_sent(key, message_id)
