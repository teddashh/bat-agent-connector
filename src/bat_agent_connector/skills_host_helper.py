"""Bounded read-only skill inventory for a selected POSIX BAT workspace.

Transported as fixed source over configured SSH. Input names one observed
workspace, never a client-supplied file. All paths are walked through no-follow
directory handles; links, special files and hard links are refused. Digests bind
the whole skill directory including supporting files, not just a prompt title.
This helper never installs, edits, activates, or executes a skill.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

MAX_SKILLS = 200
MAX_FILES = 128
MAX_FILE = 262144
MAX_TOTAL = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid workspace")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(parent, name, budget):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE:
            raise ValueError("unsafe or oversized skill file")
        content = source.read(MAX_FILE + 1)
        after = os.fstat(source.fileno())
        if (len(content) > MAX_FILE or (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("skill source changed while reading")
        budget[0] += len(content)
        if budget[0] > MAX_TOTAL:
            raise ValueError("skill inventory byte limit")
        return content


def _bundle(fd, budget, prefix="", depth=0):
    if depth > 8:
        raise ValueError("skill directory nesting limit")
    before = os.fstat(fd)
    facts, skill = [], None
    with os.scandir(fd) as entries:
        for entry in entries:
            budget[1] += 1
            if budget[1] > 5000:
                raise ValueError("skill directory-entry limit")
            name = entry.name
            relative = prefix + name
            if len(relative) > 512 or any(ord(char) < 32 for char in name):
                raise ValueError("invalid skill source name")
            if entry.is_dir(follow_symlinks=False):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    nested, _ = _bundle(child, budget, relative + "/", depth + 1)
                    facts.extend(nested)
                finally:
                    os.close(child)
            else:
                raw = _read(fd, name, budget)
                facts.append({"path": relative, "digest": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
                if relative == "SKILL.md":
                    skill = raw
            if len(facts) > MAX_FILES:
                raise ValueError("skill file-count limit")
    after = os.fstat(fd)
    if (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("skill directory changed while reading")
    return sorted(facts, key=lambda row: row["path"]), skill


def _metadata(raw, fallback):
    text = raw.decode("utf-8", errors="replace")
    fields = {}
    if text.startswith("---\n") and "\n---" in text[4:]:
        front, _, text = text[4:].partition("\n---")
        for line in front.splitlines():
            match = re.fullmatch(r"(name|description):\s*(.+)", line)
            if match:
                fields[match[1]] = match[2].strip().strip("\"'")
    heading = next((line.lstrip("# ") for line in text.splitlines() if line.strip()), fallback)
    clean = lambda value, size: " ".join(str(value).split())[:size]  # noqa: E731
    return {"name": clean(fields.get("name", fallback), 120),
            "description": clean(fields.get("description", heading), 300)}


def scan(workspace, *, include_global=True):
    roots = [(Path(workspace) / ".claude", "project")]
    if include_global:
        roots.append((Path.home() / ".claude", "global"))
    rows, budget, complete = [], [0, 0], True
    for base, scope in roots:
        for folder in ("commands", "skills"):
            try:
                parent = directory(base / folder)
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                complete = False
                continue
            try:
                with os.scandir(parent) as entries:
                    for entry in entries:
                        budget[1] += 1
                        if len(rows) >= MAX_SKILLS or budget[0] > MAX_TOTAL or budget[1] > 5000:
                            complete = False
                            break
                        name = entry.name
                        if len(name) > 200 or any(ord(char) < 32 for char in name):
                            complete = False
                            continue
                        relative = folder + "/" + name
                        identity = "skill_" + hashlib.sha256((scope + ":" + relative).encode()).hexdigest()[:32]
                        row = {"skill_id": identity, "scope": scope, "relative_path": relative, "agent": "claude"}
                        try:
                            if folder == "skills" and entry.is_dir(follow_symlinks=False):
                                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                                try:
                                    facts, skill = _bundle(fd, budget)
                                finally:
                                    os.close(fd)
                                if skill is None:
                                    continue
                            elif name.endswith(".md"):
                                skill = _read(parent, name, budget)
                                facts = [{"path": name, "digest": hashlib.sha256(skill).hexdigest(), "size_bytes": len(skill)}]
                            else:
                                continue
                            row.update(_metadata(skill, name.removesuffix(".md")), available=True, reason=None,
                                       digest=hashlib.sha256(canonical(facts).encode()).hexdigest(), files=len(facts),
                                       size_bytes=sum(fact["size_bytes"] for fact in facts))
                        except (OSError, ValueError):
                            row.update(name=name, description="", digest=None, files=None, size_bytes=None,
                                       available=False, reason="unsafe_or_changed_source")
                        rows.append(row)
            finally:
                os.close(parent)
    rows.sort(key=lambda row: (row["scope"] != "project", row["relative_path"]))
    names = set()
    for row in rows:
        if row["available"]:
            if row["name"] in names:
                row.update(available=False, reason="shadowed_source")
            names.add(row["name"])
    return {"version": 1, "skills": rows, "complete": complete}


def main():
    try:
        raw = sys.stdin.buffer.readline(16385)
        if len(raw) > 16384:
            raise ValueError("request too large")
        request = json.loads(raw)
        if set(request) - {"workspace", "include_global"} or not isinstance(request.get("workspace"), str):
            raise ValueError("invalid request")
        if type(request.get("include_global", True)) is not bool:
            raise ValueError("invalid scope")
        result = scan(request["workspace"], include_global=request.get("include_global", True))
        print(canonical({"ok": True, **result}))
    except (OSError, ValueError, TypeError):
        print(canonical({"ok": False, "reason": "skill_inventory_unavailable"}))


if __name__ == "__main__":
    main()
