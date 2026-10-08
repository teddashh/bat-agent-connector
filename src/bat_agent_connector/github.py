"""Minimal GitHub REST client for delivery operations (PR merge, workflow runs), pinned to one API version.

Writes and reads return (status, body) for every HTTP answer the caller must interpret. A transport failure, a
timeout, 429 or a 5xx raises ``GitHubAmbiguous``: for a write the effect is unknown and the operation settles it by
reading GitHub back (operations.py), never by sending blindly again. The token comes from ``[github] token_ref`` and
never appears in results or errors.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlsplit

from . import __version__
from .config import GitHubConfig
from .operations import AmbiguousOutcome
from .redact import redact


class GitHubAmbiguous(AmbiguousOutcome):
    pass


class GitHubClient:
    def __init__(self, cfg: GitHubConfig, token: str | None = None) -> None:
        self.cfg = cfg
        self._token = token if token is not None else cfg.token()
        host = urlsplit(cfg.api_url).hostname or ""
        # A loopback test server must not go through the egress proxy; real GitHub uses the environment's proxy.
        handlers = [urllib.request.ProxyHandler({})] if host in {"127.0.0.1", "localhost"} else []
        self._opener = urllib.request.build_opener(*handlers)

    def _request(self, method: str, path: str, body: dict | None = None, query: dict | None = None) -> tuple[int, dict]:
        url = self.cfg.api_url + path + (("?" + urlencode({k: v for k, v in query.items() if v is not None}))
                                         if query else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={  # noqa: S310 - https or loopback
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": self.cfg.api_version,
            "Authorization": "Bearer " + self._token, "User-Agent": f"bat-agent-connector/{__version__}",
            **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with self._opener.open(req, timeout=self.cfg.timeout_s) as resp:  # noqa: S310
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {"message": raw[:200].decode(errors="replace")}
            if e.code == 429 or e.code >= 500:
                raise GitHubAmbiguous(f"GitHub {method} {path} answered {e.code}") from None
            return e.code, payload if isinstance(payload, dict) else {"items": payload}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise GitHubAmbiguous(redact(f"GitHub {method} {path} failed: {type(e).__name__}")) from None

    async def call(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        return await asyncio.to_thread(self._request, method, path, body, query)

    @staticmethod
    def _repo(repository: str) -> str:
        owner, name = repository.split("/", 1)
        return f"/repos/{quote(owner)}/{quote(name)}"

    # ------------------------------------------------------------------ pulls
    async def pull(self, repository: str, number: int):
        return await self.call("GET", f"{self._repo(repository)}/pulls/{int(number)}")

    async def merge_async(self, repository: str, number: int, sha: str, method: str):
        return await self.call("PUT", f"{self._repo(repository)}/pulls/{int(number)}/merge-async",
                               {"sha": sha, "merge_method": method, "merge_action": "default"})

    async def merge_async_result(self, repository: str, number: int, uuid: str):
        return await self.call("GET", f"{self._repo(repository)}/pulls/{int(number)}/merge-async/{quote(uuid)}")

    async def commit(self, repository: str, sha: str):
        return await self.call("GET", f"{self._repo(repository)}/commits/{quote(sha)}")

    async def check_runs(self, repository: str, sha: str):
        return await self.call("GET", f"{self._repo(repository)}/commits/{quote(sha)}/check-runs",
                               query={"per_page": 100})

    # ------------------------------------------------------------------ actions
    async def dispatch(self, repository: str, workflow: str, ref: str, inputs: dict):
        return await self.call("POST", f"{self._repo(repository)}/actions/workflows/{quote(workflow)}/dispatches",
                               {"ref": ref, "inputs": inputs})

    async def runs(self, repository: str, workflow: str, **filters):
        return await self.call("GET", f"{self._repo(repository)}/actions/workflows/{quote(workflow)}/runs",
                               query={"per_page": 50, **filters})

    async def run(self, repository: str, run_id: int):
        return await self.call("GET", f"{self._repo(repository)}/actions/runs/{int(run_id)}")

    async def jobs(self, repository: str, run_id: int):
        return await self.call("GET", f"{self._repo(repository)}/actions/runs/{int(run_id)}/jobs",
                               query={"per_page": 100})
