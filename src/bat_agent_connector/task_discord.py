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


class DiscordHTTP:
    def __init__(self, token_env: str = "BATC_DISCORD_BOT_TOKEN"):  # noqa: S107 - environment variable name
        self.token_env = token_env

    def _request(self, method: str, path: str, text: str) -> dict:
        token = os.environ.get(self.token_env)
        if not token:
            raise RuntimeError(f"{self.token_env} is not set")
        req = urllib.request.Request(
            "https://discord.com/api/v10" + path, method=method,
            data=json.dumps({"content": text}).encode(),
            headers={"Authorization": "Bot " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed Discord HTTPS API
            return json.load(resp)

    async def post(self, channel_id: str, text: str) -> str:
        result = await asyncio.to_thread(self._request, "POST", f"/channels/{channel_id}/messages", text)
        return str(result["id"])

    async def edit(self, channel_id: str, message_id: str, text: str) -> None:
        await asyncio.to_thread(self._request, "PATCH", f"/channels/{channel_id}/messages/{message_id}", text)


class DiscordPublisher:
    def __init__(self, journal: Journal, adapter: DiscordAdapter, board_channel_id: str | None = None):
        self.journal = journal
        self.adapter = adapter
        self.board_channel_id = board_channel_id

    async def flush(self):
        for event in self.journal.discord_events():
            eid = event["event_id"]
            if not self.journal.claim_discord_event(eid):
                continue
            # If the request times out after Discord accepts it, 'sending' stays
            # unresolved for operator reconciliation. We never blindly repost.
            body = json.loads(event["body"])
            text = f"任務 {event['task_id'][:8]} · {event['kind']} · #{eid}\n{json.dumps(body, ensure_ascii=False)}"
            message_id = await self.adapter.post(event["discord_thread_id"], text[:2000])
            self.journal.mark_discord_event(eid, message_id)
        if self.board_channel_id:
            await self.update_board()

    async def update_board(self):
        tasks = self.journal.list_active()
        lines = ["任務看板"] + [f"{t['task_id'][:8]} · {t['project']} · {t['state']}" for t in tasks[:40]]
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
