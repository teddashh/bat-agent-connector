"""Read-only calibration table for the minimal Jev review gate.

Lists every minimal-path gate decision with Jev's choice and confidence, the
independent reviewer's outcome for the same candidate when one exists, and
how alternative policies would have decided. No model calls, no writes.

    python -m bat_agent_connector.gate_eval --db ~/.local/state/bat-agent-connector/tasks.sqlite3
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

TINY_DIFF_CHARS = 800


def _jev_choice(reason: str | None) -> str | None:
    if reason in {"jev_pass", "low_confidence"}:
        return "pass"
    if reason in {"jev_fail", "jev_risk", "jev_unsure"}:
        return reason[4:]
    return None  # escalated before Jev (size, sensitive path, no diff) or Jev unavailable


def evaluate(db_path: str | Path, thresholds: tuple[float, ...] = (0.50, 0.45),
             tiny_chars: int = TINY_DIFF_CHARS) -> dict:
    db = sqlite3.connect(f"file:{Path(db_path).expanduser()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        gates = db.execute("""SELECT g.*, t.review_passed, t.verification_commit, t.state
            FROM minimal_review_gates g JOIN tasks t USING(task_id)
            WHERE g.verdict<>'pending' ORDER BY g.created_at""").fetchall()
        rows = []
        for g in gates:
            reserved = db.execute("""SELECT body FROM events WHERE task_id=? AND kind='minimal_review_reserved'
                AND json_extract(body,'$.candidate_commit')=? ORDER BY event_id LIMIT 1""",
                (g["task_id"], g["candidate_commit"])).fetchone()
            body = json.loads(reserved["body"]) if reserved else {}
            rejected = db.execute("""SELECT 1 FROM events WHERE task_id=? AND kind='review_verdict_rejected'
                AND json_extract(body,'$.candidate_commit')=? LIMIT 1""",
                (g["task_id"], g["candidate_commit"])).fetchone()
            if rejected:
                review = "reject"
            elif g["review_passed"] and g["verification_commit"] == g["candidate_commit"]:
                review = "pass"
            else:
                review = "not_reviewed" if g["verdict"] == "pass" else "unknown"
            choice = _jev_choice(g["reason"])
            chars = body.get("diff_chars")
            paths = body.get("paths") or []
            tiny = None if chars is None else (chars <= tiny_chars and len(paths) <= 1)
            policies = {f"threshold_{t:.2f}": ("pass" if choice == "pass" and g["confidence"] is not None
                                               and g["confidence"] >= t else "escalate")
                        for t in thresholds}
            policies["pass_and_tiny"] = ("escalate" if choice != "pass" else
                                         None if tiny is None else "pass" if tiny else "escalate")
            rows.append({"task_id": g["task_id"], "candidate_commit": g["candidate_commit"],
                         "jev_choice": choice, "confidence": g["confidence"], "gate_reason": g["reason"],
                         "threshold_at_time": g["threshold"], "diff_chars": chars, "paths": paths,
                         "independent_review": review, "policies": policies})
    finally:
        db.close()
    summary = {}
    for name in rows[0]["policies"] if rows else []:
        decided = [(r["policies"][name], r["independent_review"]) for r in rows]
        summary[name] = {
            "pass": sum(p == "pass" for p, _ in decided),
            "escalate": sum(p == "escalate" for p, _ in decided),
            "false_pass": sum(p == "pass" and rv == "reject" for p, rv in decided),
            "false_escalate": sum(p == "escalate" and rv == "pass" for p, rv in decided),
            "undecidable": sum(p is None or rv in {"unknown", "not_reviewed"} for p, rv in decided),
        }
    return {"rows": rows, "summary": summary, "tiny_diff_chars": tiny_chars}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--tiny-chars", type=int, default=TINY_DIFF_CHARS)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.db, tiny_chars=args.tiny_chars), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
