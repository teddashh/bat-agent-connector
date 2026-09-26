"""A small pool of BatClient connections, one per configured host."""

from __future__ import annotations

import asyncio
import contextlib
import time

from .client import BatClient
from .config import Config, device_id


class Fleet:
    def __init__(
        self,
        config: Config,
        *,
        read_only: bool = False,
        idle_timeout: float = 120.0,
        actor: str = "cli",
    ) -> None:
        self.config = config
        self.read_only = read_only
        self.idle_timeout = idle_timeout
        self.actor = actor
        self._clients: dict[str, BatClient] = {}
        self._device_id: str | None = None
        self._reaper: asyncio.Task | None = None

    def writes_enabled(self, host: str) -> bool:
        return (not self.read_only) and self.config.host(host).writes

    def orchestrate_enabled(self, host: str) -> bool:
        h = self.config.host(host)
        return (not self.read_only) and h.writes and h.orchestrate

    @property
    def any_writes(self) -> bool:
        return (not self.read_only) and self.config.any_writes

    @property
    def any_orchestrate(self) -> bool:
        return (not self.read_only) and self.config.any_orchestrate

    def client(self, name: str) -> BatClient:
        hc = self.config.host(name)
        c = self._clients.get(name)
        if c is None:
            if self._device_id is None:
                self._device_id = device_id()
            c = BatClient(
                hc,
                device_id=self._device_id,
                client_label=self.config.client_label,
                allow_writes=self.writes_enabled(name),
                allow_orchestrate=self.orchestrate_enabled(name),
            )
            self._clients[name] = c
        if self.idle_timeout and self._reaper is None:
            with contextlib.suppress(RuntimeError):
                self._reaper = asyncio.get_running_loop().create_task(self._reap_loop())
        return c

    async def _reap_loop(self) -> None:
        while True:
            await asyncio.sleep(max(5.0, self.idle_timeout / 4))
            now = time.monotonic()
            for c in list(self._clients.values()):
                if c.connected and now - c.last_used > self.idle_timeout:
                    await c.close()

    async def close(self) -> None:
        if self._reaper:
            self._reaper.cancel()
            with contextlib.suppress(BaseException):
                await self._reaper
            self._reaper = None
        await asyncio.gather(*(c.close() for c in self._clients.values()), return_exceptions=True)
