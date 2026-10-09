"""Pure projection of durable standalone-start creation receipts for reviewed cleanup."""
from __future__ import annotations

import json
import math
import re


def carriers(ops, operations, entries):
    """Keep original registry resource IDs even after an unsent failure or local-row loss.

    A generic failed registry entry is never new ownership evidence. Only positive
    central source/reservation/create receipts can project this carrier. Current
    root policy, live consumers, content and cleanup reservations are checked by
    the ordinary cleanup planner/executor, not by this read model.
    """
    for op in operations:
        if op["action"] != "session.start":
            continue
        steps = {r["name"]: r for r in ops.db.execute("SELECT name,request,response FROM operation_steps "
            "WHERE operation_id=? AND status='succeeded' AND name IN ('source.resolve','session.reserve','worktree.create')",
            (op["operation_id"],))}
        if len(steps) != 3:
            continue
        try:
            source, reserved, carrier = (json.loads(steps[name]["response"]) for name in
                                         ("source.resolve", "session.reserve", "worktree.create"))
            request = json.loads(steps["worktree.create"]["request"])
            reservation = json.loads(steps["session.reserve"]["request"])
            host, sid, created = source["host"], source["session_id"], reserved["created_at"]
            path, branch, root = carrier["worktree_path"], carrier["branch"], source["origin_root"]
            if (any(not isinstance(s, str) or not s for s in
                    (host, sid, path, branch, root, source["folder"], source["source_branch"], source["workspace_id"]))
                    or source["use_worktree"] is not True or op["target"]["host"] != host
                    or not isinstance(source["base_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", source["base_commit"])
                    or type(created) not in (int, float) or not math.isfinite(created) or created <= 0
                    or reservation != {"session_id": sid} or reserved["session_id"] != sid
                    or carrier["cwd"] != path or carrier["source_branch"] != source["source_branch"]
                    or request != {"session_id": sid, "cwd": source["folder"],
                                   "branch": source["source_branch"], "commit": source["base_commit"]}):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        current = [e for e in entries if e.get("host") == host and e.get("session_id") == sid]
        # A changed row cannot lend its ownership to an older receipt. Keep the
        # old resource visible but blocked; never rewrite a successor's pointer.
        mismatch = bool(current and (len(current) != 1 or any(current[0].get(k) != v for k, v in {
            "created_at": created, "start_operation_id": op["operation_id"], "origin_root": root,
            "origin_cwd": source["folder"], "workspace_id": source["workspace_id"],
            "cwd": path, "worktree_path": path, "branch": branch}.items())))
        yield {"host": host, "session_id": sid, "created_at": created, "path": path, "branch": branch,
               "repository": root, "base": source["base_commit"], "operation_id": op["operation_id"],
               "intent": f"{sid}@{created}", "binding_mismatch": mismatch}
