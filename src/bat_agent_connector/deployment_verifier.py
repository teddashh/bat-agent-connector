"""Bounded backend runtime reads. Response text and credentials never leave this module."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

from .config import DEFAULT_BAT_PROFILES_DIR, _resolve_token_ref, verification_url
from .redact import register_secret

FIELDS = {"repository_id": int, "environment": str, "source_sha": str, "artifact_id": int,
          "artifact_digest": str, "healthy": bool}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(settings):
    try:
        verification_url(settings["url"])
        headers = {"Accept": "application/json"}
        secret = None
        if settings.get("token_ref"):
            secret = _resolve_token_ref(settings["token_ref"], DEFAULT_BAT_PROFILES_DIR)
            register_secret(secret)
            headers["Authorization"] = "Bearer " + secret
        req = urllib.request.Request(settings["url"], headers=headers)  # noqa: S310 (validated above)
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=settings["timeout_s"]) as reply:
            if reply.status != 200:
                return {"waiting": "runtime check refused", "reason": "http_status"}
            raw = reply.read(settings["max_bytes"] + 1)
        if len(raw) > settings["max_bytes"]:
            return {"waiting": "runtime check exceeded max_bytes", "reason": "oversized"}
        body = json.loads(raw)
        if not isinstance(body, dict):
            return {"waiting": "runtime check omitted evidence", "reason": "invalid_json"}
        # Explicit types exclude bool-as-int. Even a credential echoed into a known field is excluded.
        return {k: v for k, v in body.items() if k in FIELDS and type(v) is FIELDS[k]
                and (not isinstance(v, str) or (len(v) <= 512 and (not secret or secret not in v)))}
    except urllib.error.HTTPError as exc:
        return {"waiting": "runtime check refused", "reason": "redirect" if 300 <= exc.code < 400 else "http_status"}
    except Exception:
        # Exceptions can contain URLs, response bodies or credentials. Persist only this bounded classification.
        return {"waiting": "runtime check unavailable", "reason": "unavailable"}


async def fetch(settings):
    return await asyncio.to_thread(_fetch, settings)
