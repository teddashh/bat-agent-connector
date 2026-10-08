"""Shared observation and cleanup identities; an ID never grants ownership."""

import hashlib
import json


def worktree_id(host: str, intent_type: str, intent_id: str, slot: str) -> str:
    raw = json.dumps(["worktree", host, intent_type, intent_id, slot],
                     sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "wt_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def connector_made(entry):
    """Recognize connector creation evidence, including legacy connector branches."""
    return bool(entry.get("worktree_made_by") == "connector" or entry.get("checkpoint_id")
                or entry.get("integration_operation_id") or str(entry.get("branch") or "").startswith("batc/"))


def registry_worktree_root(entries, host, session_id, lead_of=None):
    """Resolve the creation entry using registry facts only, without changing them.

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
    return entry


def registry_worktree_intent(entries, host, session_id, lead_of=None):
    """Return ("registry", "<root sid>@<root created_at>") only for a proven BAT-made root."""
    entry = registry_worktree_root(entries, host, session_id, lead_of)
    # Current-row connector evidence must not become BAT identity even if its parent disagrees.
    current = next((e for e in reversed(entries) if isinstance(e, dict) and e.get("session_id") == session_id
                    and e.get("host", host) == host), {})
    if (entry is None or connector_made(entry) or connector_made(current)
            or entry.get("created_at") is None or not entry.get("worktree_path")):
        return None
    return "registry", f"{entry['session_id']}@{str(entry['created_at'])}"
