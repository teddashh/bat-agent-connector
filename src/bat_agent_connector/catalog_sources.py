"""Private cache identity for actual configured catalog read sources."""
from __future__ import annotations

import hashlib
import json


def host_binding(ops, host, *, skills=False):
    config = ops.context["fleet"].config
    if host not in config.hosts:
        return None
    value = config.host(host)
    source = [value.url, value.fingerprint, value.profile_id, value.token_ref, value.bat_profiles_dir]
    if skills:
        adapter = ops.context.get("skill_host") or ops.context.get("artifact_host")
        source.append(getattr(adapter, "aliases", {}).get(host))
    # Kept inside private journal documents; neither references nor this hash
    # are exposed as provider/account data in API catalog responses.
    return hashlib.sha256(json.dumps(source, separators=(",", ":")).encode()).hexdigest()


def cached_document(row, binding):
    if row is None:
        return None
    value = json.loads(row["document"])
    return value if value.pop("_source_binding", None) == binding else None
