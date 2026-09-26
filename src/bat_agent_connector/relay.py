"""Verbatim relay, BAT-STATUS stop markers and seat-planned fan-out blocks.

Orchestrator-agnostic helpers for a supervising agent (e.g. a chat bot) that should relay a person's
instructions to a stronger agent session unchanged, and let that session (not the relay) plan any fan-out.

* ``build_relay`` renders "original + brief": the person's message verbatim between fixed markers, then the
  relay's own clearly-labeled brief (goal / context / constraints / acceptance criteria), a context header and
  instructions telling the seat to treat the original as the source of truth and state its interpretation.
* ``parse_status`` reads the optional ``BAT-STATUS: MILESTONE|CONTINUE|NEED-<WHO> <text>`` line a session
  ends its stop with. When present it is preferred over pattern/Jev heuristics; absent, those remain.
* ``parse_fanout`` reads a fenced ```bat-fanout JSON block ([{title, prompt, area}]) that the session
  returns when asked for a fan-out plan; the relay starts worktrees exactly per that block.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import BatError

STATUS_RE = re.compile(
    r"BAT-STATUS\s*:\s*(MILESTONE|CONTINUE|DONE|NEED[-_ ]?[A-Za-z]*)\b[ \t*`_]*[:\-–—]?[ \t]*([^\n]*)",
    re.IGNORECASE,
)
FANOUT_RE = re.compile(r"```[ \t]*bat-fanout[^\n]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
MAX_FANOUT_ITEMS = 16
BEGIN = "----- BEGIN MESSAGE FROM {who} (verbatim, unedited) -----"
END = "----- END MESSAGE FROM {who} -----"


def need_label(human_name: str | None) -> str:
    who = re.sub(r"[^A-Za-z0-9]", "", human_name or "").upper()
    return f"NEED-{who or 'HUMAN'}"


def parse_status(text: str | None) -> dict | None:
    """The last BAT-STATUS line in the tail of an agent reply, or None.

    kind is MILESTONE (DONE is an alias), CONTINUE or NEED_HUMAN (any NEED-<who> label)."""
    tail = (text or "")[-2500:]
    last = None
    for m in STATUS_RE.finditer(tail):
        last = m
    if last is None:
        return None
    raw = last.group(1).upper().replace("_", "-").replace(" ", "-")
    kind = "MILESTONE" if raw in ("MILESTONE", "DONE") else "CONTINUE" if raw == "CONTINUE" else "NEED_HUMAN"
    return {"kind": kind, "label": raw, "detail": last.group(2).strip().strip("*`_ ").strip()[:300]}


def status_footer(human_name: str | None = None) -> str:
    need = need_label(human_name)
    who = human_name or "a human"
    return (
        "Whenever you stop (at the end of this turn and at every later stop), end your reply with exactly one "
        "status line:\n"
        "BAT-STATUS: MILESTONE <name>  (a milestone/phase is complete)\n"
        "BAT-STATUS: CONTINUE <next step>  (you stopped mid-plan and the next step is clear)\n"
        f"BAT-STATUS: {need} <reason>  (you need {who}: a decision, credentials, money, a release or "
        "anything destructive)"
    )


def fanout_request(max_items: int, human_name: str | None = None) -> str:
    n = max(1, min(MAX_FANOUT_ITEMS, int(max_items)))
    return (
        "Do not start the work yet. Plan how to split it across parallel agents, each in its own git "
        "worktree/branch, and return the plan in exactly one fenced block:\n"
        "```bat-fanout\n"
        '[{"title": "short title", "prompt": "complete, self-contained instructions for that agent", '
        '"area": "files/directories this task owns"}]\n'
        "```\n"
        f"Rules: at most {n} items; independent tasks with disjoint files/areas; each prompt must stand on its "
        "own (the agent sees only its prompt and the repo) and should say to commit on its branch, run the "
        "relevant tests and not merge or push. If the work should not be split, return a one-item list. "
        "The relay starts the agents exactly as written, so write the prompts yourself.\n"
        "End with: BAT-STATUS: MILESTONE fan-out plan ready"
    )


BRIEF_FIELDS = (("goal", "Goal"), ("context", "Relevant context"), ("constraints", "Constraints"),
                ("acceptance", "Suggested acceptance criteria"))


def render_brief(brief: dict | str | None) -> str:
    if not brief:
        return ""
    if isinstance(brief, str):
        return brief.strip()[:4000]
    if not isinstance(brief, dict):
        raise BatError("brief must be a string or an object {goal, context, constraints, acceptance}")
    lines = []
    for key, label in BRIEF_FIELDS:
        v = brief.get(key)
        if isinstance(v, list):
            v = "\n".join(f"- {x}" for x in v if str(x).strip())
        if v and str(v).strip():
            lines.append(f"{label}: {str(v).strip()[:1500]}")
    return "\n".join(lines)


def build_relay(
    message: str,
    *,
    host: str,
    workspace: str | None = None,
    channel: str | None = None,
    thread: str | None = None,
    earlier: list[str] | None = None,
    brief: dict | str | None = None,
    human_name: str | None = None,
    relay_name: str | None = None,
    request_fanout: bool = False,
    max_items: int = 4,
) -> str:
    """Render "original + brief": the person's message verbatim (byte-for-byte between markers), then the
    relay's own clearly-labeled brief (its interpretation), a short context header and the seat instructions."""
    if not isinstance(message, str) or not message.strip():
        raise BatError("message must be a non-empty string")
    who = (human_name or "the user").strip()
    relay = (relay_name or "the chat relay").strip()
    ctx = [f"host/workspace: {host}/{workspace}" if workspace else f"host: {host}"]
    if channel:
        ctx.insert(0, f"channel: #{channel.lstrip('#')}")
    if thread:
        ctx.append(f"thread: {thread}")
    parts = [
        f"[Task from {who}, relayed by {relay}.] " + " | ".join(ctx),
        f"{who}'s original message is the source of truth. Below it, {relay} adds a brief with its own reading "
        f"of the task; use it as help only, it may be wrong. You have the repo context: fix anything unclear or "
        f"suboptimal in the ask using your judgment and the project plan. Before starting, state in one line how "
        f"you interpret the task (INTERPRETATION: ...). Only stop to ask {who} if it is genuinely ambiguous and "
        f"the choice is consequential.",
    ]
    for i, e in enumerate(x for x in (earlier or []) if isinstance(x, str) and x.strip()):
        tag = f"{who.upper()} EARLIER IN THIS THREAD #{i + 1}"
        parts += ["", BEGIN.format(who=tag), e, END.format(who=tag)]
    tag = who.upper()
    parts += ["", BEGIN.format(who=tag), message, END.format(who=tag)]
    b = render_brief(brief)
    if b:
        rtag = f"{relay.upper()} BRIEF ({relay}'s interpretation, not {who}'s words)"
        parts += ["", f"----- BEGIN {rtag} -----", b, f"----- END {relay.upper()} BRIEF -----"]
    parts.append("")
    if request_fanout:
        parts += [fanout_request(max_items, human_name), ""]
    parts.append(status_footer(human_name))
    return "\n".join(parts)


def _as_text(v: Any, limit: int) -> str:
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return str(v or "").strip()[:limit]


def parse_fanout(text: str | None, max_items: int = MAX_FANOUT_ITEMS) -> dict:
    """Parse the last ```bat-fanout block in ``text`` into validated tasks (prompts kept verbatim)."""
    blocks = FANOUT_RE.findall(text or "")
    if not blocks:
        raise BatError("no ```bat-fanout block found in the session's reply")
    try:
        data = json.loads(blocks[-1])
    except json.JSONDecodeError as e:
        raise BatError(f"bat-fanout block is not valid JSON: {e.msg} (line {e.lineno})") from None
    if isinstance(data, dict):
        data = data.get("tasks")
    if not isinstance(data, list) or not data:
        raise BatError("bat-fanout block must be a non-empty JSON list of {title, prompt, area}")
    cap = max(1, min(MAX_FANOUT_ITEMS, int(max_items)))
    if len(data) > cap:
        raise BatError(f"bat-fanout plan has {len(data)} items; the cap is {cap}. Ask the session for a smaller plan")
    tasks = []
    for i, it in enumerate(data, 1):
        if not isinstance(it, dict):
            raise BatError(f"bat-fanout item {i} is not an object")
        prompt = it.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise BatError(f"bat-fanout item {i} has no prompt")
        if len(prompt) > 19_000:
            raise BatError(f"bat-fanout item {i} prompt is longer than 19000 characters")
        tasks.append(
            {
                "index": i,
                "title": _as_text(it.get("title"), 200) or f"task {i}",
                "prompt": prompt,
                "area": _as_text(it.get("area") or it.get("files"), 500),
            }
        )
    return {"tasks": tasks, "count": len(tasks)}
