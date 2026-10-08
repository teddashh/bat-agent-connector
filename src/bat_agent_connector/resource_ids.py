"""Shared observation and cleanup identities; an ID never grants ownership."""

import hashlib
import json


def worktree_id(host: str, intent_type: str, intent_id: str, slot: str) -> str:
    raw = json.dumps(["worktree", host, intent_type, intent_id, slot],
                     sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "wt_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def registry_worktree_intent(entries, host, session_id, lead_of=None):
    """Return ("registry", "<root sid>@<root created_at>") for a BAT-made worktree, or None.

    Missing parents stop at the last known entry. Cycles have no proven creation root.
    ``lead_of(task_id)`` may supply a reviewer's lead from the caller's existing facts.
    """
    by_id = {e["session_id"]: e for e in entries
             if isinstance(e, dict) and e.get("session_id") and e.get("host", host) == host}
    entry = by_id.get(session_id)
    seen = set()
    while entry is not None:
        sid = entry["session_id"]
        if sid in seen:
            return None
        seen.add(sid)
        parent = entry.get("failover_of") or entry.get("shared_worktree_from") or entry.get("lead_session_id")
        if not parent and entry.get("role") == "reviewer" and entry.get("task_id") and lead_of:
            parent = lead_of(entry["task_id"])
        if not parent or parent not in by_id:
            break
        entry = by_id[parent]
    if (entry is None or entry.get("worktree_made_by") == "connector" or entry.get("checkpoint_id")
            or entry.get("integration_operation_id") or entry.get("created_at") is None or not entry.get("worktree_path")):
        return None
    return "registry", f"{entry['session_id']}@{str(entry['created_at'])}"
