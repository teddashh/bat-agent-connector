"""Resource identities shared by observation and cleanup."""

import hashlib
import json


def worktree_id(host: str, intent_type: str, intent_id: str, slot: str) -> str:
    raw = json.dumps(["worktree", host, intent_type, intent_id, slot],
                     sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "wt_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
