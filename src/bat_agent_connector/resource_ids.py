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


def registry_worktree_parent(entry, by_id, lead_of=None):
    """Return only a parent whose worktree the child shares; ``by_id`` is scoped to one host."""
    shared = entry.get("shares_worktree_with")
    if shared:
        return by_id.get(shared)
    path = entry.get("worktree_path")
    predecessor = entry.get("failover_of")
    if predecessor:
        parent = by_id.get(predecessor)
        return parent if parent and path and path == parent.get("worktree_path") else None
    lead = entry.get("lead_session_id")
    task_lead = None
    if (not lead and entry.get("role") == "reviewer" or lead and not path) and entry.get("task_id") and lead_of:
        task_lead = lead_of(entry["task_id"])
        if not lead:
            lead = task_lead.get("session_id") if isinstance(task_lead, dict) else task_lead
    parent = by_id.get(lead)
    if not parent or not parent.get("worktree_path"):
        return None
    if path == parent["worktree_path"]:
        return parent
    if (not path and isinstance(task_lead, dict) and task_lead.get("session_id") == lead
            and task_lead.get("worktree_path") == parent["worktree_path"]):
        return parent
    return None


def registry_worktree_root(entries, host, session_id, lead_of=None):
    """Resolve the creation entry using registry facts only, without changing them.

    Missing parents stop at the last known entry. Cycles have no proven creation root.
    ``lead_of(task_id)`` may return a lead ID, or a dict with session_id/worktree_path.
    A reviewer without its own path needs the latter as task carrier evidence.
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
        parent = registry_worktree_parent(entry, by_id, lead_of)
        if parent is None:
            break
        entry = parent
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
