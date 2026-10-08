"""Offline Project Hub v4.68.2 import (B05), never a Hub runtime or a filesystem writer.

Parser, display order and completion hashes follow kieiken/project-hub@031aedd4 (MIT),
files listed in THIRD_PARTY_NOTICES.md. Design: docs/design/hub-import.md.
"""
from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from collections import Counter, defaultdict
from contextlib import contextmanager

from . import work_items as wi
from .api_auth import Principal
from .config import HubImportSource
from .operations import (
    RERUN,
    UNCERTAIN_RETRY_S,
    ActionDef,
    Cancelled,
    NeedsAttention,
    OpContext,
    OperationError,
    StepFailed,
    Uncertain,
)

HUB_COMMIT = "031aedd4bf62ef4bb1e6199c31aa9c4323a116bb"
PARSER_VERSION = 1
TTL = 86400
FILE_MAX = 8 * 1024 * 1024
TOTAL_MAX = 256 * 1024 * 1024
PROJECT_MAX = 5000
ITEM_MAX = 50000
PREVIEW_ID = re.compile(r"hip_[0-9a-f]{32}")
ACCEPTANCE = {"驗收條件", "受け入れ条件", "受入条件", "Acceptance"}
CLASSIFICATIONS = ("create", "update", "metadata_only", "unchanged", "local_only", "source_missing", "conflict")
STRUCTURAL = ("parent_id", "derived_from", "pinned")


def _error(code: str, message: str, status: int = 422):
    return OperationError(code, message, status)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def record_key(kind: str, project: str, task: str = "") -> str:
    return _json([kind, project, task])


def record_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _load(text: str):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


# Hub frontmatter.js: comments, top-level comma splitting, strings rather than numeric coercion.
def _comment(line: str) -> str:
    quote = None
    for i, c in enumerate(line):
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def _split(text: str) -> list[str]:
    parts, start, stack, quote = [], 0, [], None
    for i, c in enumerate(text):
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "[{":
            stack.append(c)
            if len(stack) > 32:
                raise ValueError("inline value too deep")
        elif c in "]}":
            if not stack or stack.pop() != ("]" == c and "[" or "{"):
                raise ValueError("unbalanced inline value")
        elif c == "," and not stack:
            parts.append(text[start:i])
            start = i + 1
    if quote or stack:
        raise ValueError("unbalanced inline value")
    if text[start:].strip():
        parts.append(text[start:])
    return parts


def _value(raw: str, depth: int = 0):
    if depth > 32:
        raise ValueError("frontmatter too deep")
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [_value(x, depth + 1) for x in _split(value[1:-1])]
    if value.startswith("{") and value.endswith("}"):
        pairs = []
        for part in _split(value[1:-1]):
            key, sep, v = part.partition(":")
            if not sep or not key.strip():
                raise ValueError("map entry needs a key")
            pairs.append((key.strip(), _value(v, depth + 1)))
        return _pairs(pairs)
    if value[:1] in ("'", '"'):
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError("unclosed string")
        return value[1:-1]
    if value.startswith(("[", "{", "&", "*", "!", "|", ">")):
        raise ValueError("unsupported frontmatter value")
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def parse_doc(text: str) -> tuple[dict, str]:
    """Hub's limited dialect, with invalid/ambiguous input reported instead of silently defaulted."""
    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n)?([\s\S]*)$", text)
    if not match:
        raise ValueError("missing frontmatter delimiters")
    data, key, block_indent = {}, None, None
    for raw in match[1].splitlines():
        line = _comment(raw).rstrip()
        if not line.strip():
            continue
        body = line.lstrip()
        if line == body:
            key, sep, value = body.partition(":")
            key = key.strip()
            block_indent = None
            if not sep or not key or key in data:
                raise ValueError("invalid or duplicate frontmatter key")
            data[key] = None if not value.strip() else _value(value)
        else:
            indent = len(line) - len(body)
            if not key or (block_indent is not None and block_indent != indent):
                raise ValueError("unsupported nested frontmatter block")
            block_indent = indent
        if line != body and key and body.startswith("-") and (body == "-" or body.startswith("- ")):
            if data[key] is None:
                data[key] = []
            if not isinstance(data[key], list):
                raise ValueError("mixed frontmatter list/map")
            data[key].append(_value(body[1:]))
        elif line != body and key:
            sub, sep, value = body.partition(":")
            sub = sub.strip()
            if not sep or not sub:
                raise ValueError("unsupported indented value")
            if data[key] is None:
                data[key] = {}
            if not isinstance(data[key], dict) or sub in data[key]:
                raise ValueError("mixed or duplicate frontmatter map")
            data[key][sub] = _value(value)
    return {k: "" if v is None else v for k, v in data.items()}, match[2]


def _sections(body: str) -> list[tuple[str, str]]:
    out, heading, lines = [], None, []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if heading is not None:
                out.append((heading, "\n".join(lines).strip()))
            heading, lines = m[1], []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        out.append((heading, "\n".join(lines).strip()))
    return out


def read_steps(body: str) -> list[dict]:
    steps, inside = [], False
    for line in body.replace("\r\n", "\n").split("\n"):
        if re.match(r"^##\s", line):
            inside = bool(re.match(r"^##\s+手順", line))
            continue
        m = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(\S.*)$", line) if inside else None
        if m:
            steps.append({"text": m[2].strip(), "done": m[1] != " "})
    return steps


def hub_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()


def _markdown_refs(text: str) -> list[dict]:
    # Never render or fetch Markdown. Mask code before extracting inline/reference/autolinks and bare URLs.
    masked = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    masked = re.sub(r"(`+)[\s\S]*?\1", "", masked)
    definitions = {m[1].strip().lower(): m[2] for m in re.finditer(
        r"(?m)^\s*\[([^\]]+)\]:\s*<?([^\s>]+)>?", masked)}
    refs = []
    for m in re.finditer(r"\[([^\]]*)\]\(<?([^\s>)]+)>?(?:\s+[^)]*)?\)", masked):
        refs.append({"label": m[1], "ref": m[2]})
    for m in re.finditer(r"\[([^\]]+)\](?:\[([^\]]*)\])?", masked):
        target = definitions.get((m[2] or m[1]).strip().lower())
        if target:
            refs.append({"label": m[1], "ref": target})
    for m in re.finditer(r"https?://[^\s<>\"'`]+", masked):
        ref = m[0].rstrip(".,;!?")
        while ref.endswith(")") and ref.count(")") > ref.count("("):
            ref = ref[:-1]
        refs.append({"label": "", "ref": ref})
    return list({_json(x): x for x in refs}.values())


# Paths are opened relative to descriptors, including every ancestor of the configured root.
@contextmanager
def _root(path: str):
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.split("/"):
            if not part:
                continue
            if part in (".", ".."):
                raise _error("IMPORT_SOURCE_UNSAFE", "source root has unsafe components")
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd
    except OSError as exc:
        code = "IMPORT_SOURCE_UNSAFE" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "IMPORT_SOURCE_UNREADABLE"
        raise _error(code, "cannot open configured source root") from None
    finally:
        os.close(fd)


class _Reader:
    def __init__(self, fd: int):
        self.fd, self.total = fd, 0
        self.files: dict[str, dict | None] = {}
        st = os.fstat(fd)
        self.identity = [st.st_dev, st.st_ino]

    @contextmanager
    def open(self, relative: str, *, directory: bool = False, optional: bool = False):
        fd = os.dup(self.fd)
        try:
            try:
                parts = relative.split("/")
                for i, part in enumerate(parts):
                    if not part or part in (".", "..") or "\\" in part or "\x00" in part:
                        raise _error("IMPORT_SOURCE_UNSAFE", "unsafe source component")
                    is_dir = i < len(parts) - 1 or directory
                    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                    if is_dir:
                        flags |= os.O_DIRECTORY
                    nxt = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = nxt
            except FileNotFoundError:
                if not optional:
                    raise _error("IMPORT_SOURCE_UNREADABLE", f"required source is missing: {relative}") from None
                yield None
                return
            except OSError as exc:
                code = "IMPORT_SOURCE_UNSAFE" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "IMPORT_SOURCE_UNREADABLE"
                raise _error(code, f"cannot read source: {relative}") from None
            yield fd
        finally:
            os.close(fd)

    def names(self, relative: str, *, optional: bool = False) -> list[str]:
        with self.open(relative, directory=True, optional=optional) as fd:
            try:
                return sorted(os.listdir(fd), key=lambda s: s.encode()) if fd is not None else []
            except UnicodeEncodeError:
                raise _error("IMPORT_FORMAT_INVALID", f"source filename is not UTF-8: {relative}") from None

    def read(self, relative: str, *, optional: bool = False) -> str | None:
        with self.open(relative, optional=optional) as fd:
            if fd is None:
                self.files[relative] = None
                return None
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise _error("IMPORT_SOURCE_UNSAFE", f"source is not a regular file: {relative}")
            chunks, size = [], 0
            while chunk := os.read(fd, 65536):
                size += len(chunk)
                self.total += len(chunk)
                if size > FILE_MAX or self.total > TOTAL_MAX:
                    raise _error("IMPORT_LIMIT_EXCEEDED", f"source limit exceeded: {relative}")
                chunks.append(chunk)
            after = os.fstat(fd)
            signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)  # noqa: E731
            if signature(before) != signature(after):
                raise _error("SOURCE_CHANGED", f"source changed while reading: {relative}", 409)
            raw = b"".join(chunks)
            self.files[relative] = {"identity": list(signature(after)), "sha256": hashlib.sha256(raw).hexdigest()}
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                raise _error("IMPORT_FORMAT_INVALID", f"source is not UTF-8: {relative}") from None


def _scan(source: HubImportSource) -> dict:
    with _root(source.path) as fd:
        reader = _Reader(fd)
        names = [x for x in reader.names("Product") if not x.startswith((".", "_"))]
        if len(names) > PROJECT_MAX:
            raise _error("IMPORT_LIMIT_EXCEEDED", "too many projects")
        projects, count, warnings = {}, 0, []
        for pid in names:
            path = f"Product/{pid}/PROJECT.md"
            text = reader.read(path, optional=True)
            if text is None:
                warnings.append({"code": "PROJECT_SKIPPED", "path": path})
                continue
            tasks = {}
            for name in reader.names(f"Product/{pid}/.ai/tasks", optional=True):
                if name.startswith((".", "_")) or not name.endswith(".md"):
                    continue
                count += 1
                if count > ITEM_MAX:
                    raise _error("IMPORT_LIMIT_EXCEEDED", "too many tasks")
                tid = name[:-3]
                tasks[tid] = {"text": reader.read(f"Product/{pid}/.ai/tasks/{name}"),
                              "chat": reader.read(f"Product/{pid}/.ai/chat/{tid}.jsonl", optional=True)}
            projects[pid] = {"text": text, "tasks": tasks}
        extras = {name: reader.read(f"_hub/{name}", optional=True) for name in (
            "project-order.json", "project-pins.json", "completion.json", "completion.migrated")}
        manifest = {"root": reader.identity, "files": reader.files,
                    "binding": _hash({"path": source.path, "retired": source.runtime_retired}),
                    "parser_version": PARSER_VERSION}
        return {"projects": projects, "extras": extras, "manifest": manifest, "warnings": warnings}


def snapshot(source: HubImportSource) -> dict:
    first, second = _scan(source), _scan(source)
    if first["manifest"] != second["manifest"]:
        raise _error("SOURCE_CHANGED", "source changed between snapshot passes", 409)
    return second


def _scalar(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a scalar string")
    return value


def _ledger(raw: str | None, default, filename: str):
    if raw is None:
        return default
    try:
        return _load(raw)
    except (ValueError, TypeError):
        raise ValueError(f"invalid JSON: _hub/{filename}") from None


def _graph(nodes: dict, field: str, *, depth_limit: bool = False):
    depths = {}
    for start in nodes:
        seen, path, cur = set(), [], start
        while cur and cur not in depths:
            if cur not in nodes or cur in seen:
                raise ValueError(f"missing or cyclic {field}: {start}")
            seen.add(cur)
            path.append(cur)
            cur = nodes[cur].get(field)
        depth = depths.get(cur, 0)
        for key in reversed(path):
            depth += 1
            depths[key] = depth
            if depth_limit and depth > wi.MAX_DEPTH:
                raise ValueError(f"{field} exceeds {wi.MAX_DEPTH} levels: {start}")


def _near(items: list[str], records: dict, fixed: set[str]) -> list[str]:
    branches = defaultdict(list)
    present = set(items)
    for key in items:
        source = records[key].get("derived_key")
        if source in present and key not in fixed:
            branches[source].append(key)
    result, seen = [], set()
    for key in [x for x in items if x in fixed or records[x].get("derived_key") not in present] + items:
        stack = [key]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            result.append(cur)
            stack.extend(reversed(branches[cur]))
    return result


def normalize(snap: dict) -> dict:
    """Pure normalization: raw provenance remains intact; invalid structures become preview blockers."""
    records, warnings, blockers, groups = {}, list(snap["warnings"]), [], {}
    location = "_hub"
    try:
        extras = snap["extras"]
        order = _ledger(extras["project-order.json"], {"groups": {}}, "project-order.json")
        pins = _ledger(extras["project-pins.json"], [], "project-pins.json")
        ledger = _ledger(extras["completion.json"], None, "completion.json")
        if not isinstance(order, dict) or not isinstance(order.get("groups"), dict):
            raise ValueError("project order needs groups")
        for parent, ids in order["groups"].items():
            if not isinstance(parent, str) or not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
                raise ValueError("invalid project order group")
        if not isinstance(pins, list) or any(not isinstance(x, str) or not x for x in pins) or len(pins) != len(set(pins)):
            raise ValueError("invalid project pins")
        if ledger is not None and (not isinstance(ledger, dict) or type(ledger.get("version")) is not int or ledger.get("version") != 1 or any(
                not isinstance(ledger.get(k), dict) for k in ("tasks", "projects", "continued"))):
            raise ValueError("unsupported completion ledger")
        for filename, raw in extras.items():
            if raw is None:
                warnings.append({"code": "OPTIONAL_SOURCE_MISSING", "path": f"_hub/{filename}"})
        ledger = ledger or {"tasks": {}, "projects": {}, "continued": {}}
        if any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in ledger["continued"].values()):
            raise ValueError("invalid continued hash")
        for cp in ledger["tasks"].values():
            if not isinstance(cp, dict) or not isinstance(cp.get("hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", cp["hash"]):
                raise ValueError("invalid completion task record")
        for cp in ledger["projects"].values():
            if not isinstance(cp, dict) or not isinstance(cp.get("phases"), dict):
                raise ValueError("invalid completion project record")
        for pid, p in snap["projects"].items():
            location = f"Product/{pid}/PROJECT.md"
            data, body = parse_doc(p["text"])
            key = record_key("project", pid)
            name = wi._one_line(_scalar(data, "name", pid), "name", wi.NAME_MAX["project"])
            records[key] = {"key": key, "path": location, "kind": "project", "hub_project_id": pid, "hub_task_id": "",
                            "values": {"name": name, "description": wi._text(_scalar(data, "description"), "description")},
                            "raw_parent": _scalar(data, "parent"), "raw_derived": _scalar(data, "derivedFrom"),
                            "updated": _scalar(data, "updated"), "pinned": pid in pins,
                            "snapshot": {"text": p["text"], "data": data, "body": body,
                                         "historical_completion": {"raw_state": data.get("status"),
                                             "phases": data.get("phases", []), "record": ledger["projects"].get(pid)},
                                         "references": [], "external_links": [], "related_projects": []}}
            refs = _markdown_refs(body)
            chats = data.get("chats", [])
            if not isinstance(chats, list):
                raise ValueError("project chats must be a list")
            for chat in chats:
                if not isinstance(chat, dict) or not isinstance(chat.get("url"), str):
                    raise ValueError("chat must contain a URL")
                refs.append({"label": str(chat.get("title", "")), "ref": chat["url"]})
            folders = data.get("folders", {})
            if not isinstance(folders, dict):
                raise ValueError("folders must be a map")
            refs.extend({"label": k, "ref": v} for k, v in folders.items() if v)
            records[key]["snapshot"]["references"] = refs
            for tid, task in p["tasks"].items():
                location = f"Product/{pid}/.ai/tasks/{tid}.md"
                td, tb = parse_doc(task["text"])
                if "id" in td and td["id"] != tid:
                    raise ValueError(f"task id differs from filename: {pid}/{tid}")
                tk = record_key("item", pid, tid)
                sections = _sections(tb)
                goals = [v for k, v in sections if "次にやること" in k]
                if len(goals) > 1:
                    raise ValueError("ambiguous next section")
                steps = wi._steps(read_steps(tb))
                raw_state = _scalar(td, "state", "未着手") or "未着手"
                state = {"未着手": "todo", "実行中": "doing", "返事待ち": "waiting", "上限で停止": "waiting",
                         "停止": "waiting", "完了": "done"}.get(raw_state)
                if state is None:
                    raise _error("IMPORT_STATE_UNSUPPORTED", f"unsupported task state: {pid}/{tid}")
                if state == "done" and any(not s["done"] for s in steps):
                    raise _error("COMPLETION_STEPS_OPEN", f"done task has open steps: {pid}/{tid}")
                cp = ledger["tasks"].get(f"{pid}/{tid}")
                if cp is not None and (not isinstance(cp, dict) or not isinstance(cp.get("hash"), str)):
                    raise ValueError("invalid completion task record")
                sh = hub_hash(json.dumps(steps, ensure_ascii=False, separators=(",", ":")))
                continued = ledger["continued"].get(f"{pid}/{tid}") == sh
                approved = state == "done" and bool(cp) and cp.get("hash") == hub_hash(task["text"])
                history = []
                if task["chat"] is None:
                    warnings.append({"code": "REQUEST_HISTORY_MISSING", "path": f"Product/{pid}/.ai/chat/{tid}.jsonl"})
                else:
                    for line_no, line in enumerate(task["chat"].splitlines(), 1):
                        if not line.strip():
                            continue
                        row = _load(line)
                        if not isinstance(row, dict):
                            raise ValueError("chat row must be an object")
                        if row.get("role") == "user":
                            if not isinstance(row.get("text"), str):
                                raise ValueError("user request needs text")
                            history.append({"text": row["text"], "at": row.get("at"), "request": row.get("request"), "line": line_no})
                kind = _scalar(td, "kind", "main") or "main"
                if kind not in ("main", "derived"):
                    raise ValueError("unsupported task kind")
                records[tk] = {"key": tk, "path": location, "kind": "item", "hub_project_id": pid, "hub_task_id": tid,
                              "values": {"title": wi._one_line(_scalar(td, "title", tid), "title", wi.NAME_MAX["work_item"]),
                                  "goal": wi._text(goals[0] if goals else "", "goal"), "request": wi._text(tb, "request"),
                                  "acceptance": wi._text("\n\n".join(v for k, v in sections if k in ACCEPTANCE), "acceptance"),
                                  "steps": steps, "state": state,
                                  "continued_steps": wi.steps_hash(steps) if continued and state != "done" else None},
                              "raw_parent": _scalar(td, "parent"),
                              "raw_derived": _scalar(td, "derivedFrom") if kind == "derived" else "",
                              "updated": _scalar(td, "updated"), "pinned": False,
                              "snapshot": {"text": task["text"], "data": td, "body": tb, "request_history": history,
                                  "references": _markdown_refs(tb) + [r for x in history for r in _markdown_refs(x["text"])],
                                  "historical_completion": {"raw_state": raw_state, "record": cp, "hash_matches": approved,
                                      "continued_hash": ledger["continued"].get(f"{pid}/{tid}"), "continued": continued,
                                      "approved": approved, "pending": not approved and (state == "done" or bool(steps) and all(x["done"] for x in steps) and not continued),
                                      "ledger_missing": extras["completion.json"] is None,
                                      "legacy_unverified": extras["completion.json"] is None and extras["completion.migrated"] is None},
                                  "external_links": []}}
        project_records = {k: r for k, r in records.items() if r["kind"] == "project"}
        by_name = defaultdict(list)
        for k, r in project_records.items():
            by_name[r["values"]["name"]].append(k)

        def project_ref(ref):
            if not ref:
                return None
            direct = record_key("project", ref)
            if direct in project_records:
                return direct
            if len(by_name[ref]) != 1:
                raise ValueError(f"missing or ambiguous project relation: {ref}")
            return by_name[ref][0]

        for key, r in records.items():
            if r["kind"] == "project":
                r["raw_parent_key"] = project_ref(r["raw_parent"])
                r["derived_key"] = project_ref(r["raw_derived"])
                related = r["snapshot"]["data"].get("related", [])
                if not isinstance(related, list):
                    raise ValueError("related must be a list")
                for ref in related:
                    try:
                        rk = project_ref(ref)
                    except (ValueError, TypeError):
                        rk = None
                        warnings.append({"code": "RELATED_UNRESOLVED", "record_key": key, "ref": ref})
                    r["snapshot"]["related_projects"].append({"ref": ref, "key": rk})
            else:
                r["raw_parent_key"] = record_key("item", r["hub_project_id"], r["raw_parent"]) if r["raw_parent"] else None
                ref = r["raw_derived"]
                if ref:
                    pid, sep, tid = ref.partition("/")
                    r["derived_key"] = record_key("item", pid if sep else r["hub_project_id"], tid if sep else pid)
                else:
                    r["derived_key"] = None
        _graph(records, "raw_parent_key")
        _graph(records, "derived_key")
        parents = {}
        for key, r in records.items():
            chain, cur = [], key
            while cur not in parents:
                node = records[cur]
                target = records.get(node["derived_key"])
                if target is None:
                    parents[cur] = node["raw_parent_key"]
                    break
                if target["kind"] != node["kind"]:
                    raise ValueError("invalid derived kind")
                if node["kind"] == "item" and target["hub_project_id"] != node["hub_project_id"]:
                    parents[cur] = None
                    break
                chain.append(cur)
                cur = node["derived_key"]
            for ancestor in reversed(chain):
                parents[ancestor] = parents[cur]
            r["parent_key"] = parents[key]
            refs = r["snapshot"]["references"]
            links = []
            for ref in refs:
                try:
                    url = wi.external_url(ref["ref"])
                except OperationError:
                    warnings.append({"code": "REFERENCE_NOT_MATERIALIZED", "record_key": key, "ref": ref.get("ref")})
                else:
                    links.append(url)
            r["links"] = list(dict.fromkeys(links))
            r["snapshot"]["external_links"] = r["links"]
            r["source_digest"] = _hash(r)
        _graph(records, "parent_key", depth_limit=True)
        buckets = defaultdict(list)
        for key, r in records.items():
            gk = record_key(r["kind"], r["hub_project_id"] if r["kind"] == "item" else "", r["parent_key"] or "")
            buckets[gk].append(key)
        for gk, keys in buckets.items():
            keys.sort(key=lambda k: k.encode())
            keys.sort(key=lambda k: records[k]["updated"], reverse=True)
            kind, _, parent_key = json.loads(gk)
            saved = []
            if kind == "project":
                parent = records[parent_key]["hub_project_id"] if parent_key else ""
                saved = [record_key("project", x) for x in order["groups"].get(parent, [])]
                rank = {k: i for i, k in enumerate(saved)}
                keys.sort(key=lambda k: rank.get(k, -1))
            ordered = _near(keys, records, set(saved))
            ordered = [k for k in ordered if records[k]["pinned"]] + [k for k in ordered if not records[k]["pinned"]]
            groups[gk] = {"keys": ordered, "source_digest": _hash([(k, records[k]["pinned"]) for k in ordered])}
    except OperationError as exc:
        code = "IMPORT_LIMIT_EXCEEDED" if exc.code == "INVALID_PARAMS" else exc.code
        blockers.append({"code": code, "path": location, "message": str(exc)})
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        code = "IMPORT_RELATION_INVALID" if "relation" in str(exc) or "cyclic" in str(exc) or "levels" in str(exc) else "IMPORT_FORMAT_INVALID"
        blockers.append({"code": code, "path": location, "message": str(exc)})
    return {"records": records, "groups": groups, "warnings": warnings, "blockers": blockers}

# --------------------------------------------------------------------------- journal read models and preconditions
def _source(ops, sid: str) -> HubImportSource:
    if not isinstance(sid, str):
        raise _error("INVALID_TARGET", "source_id must be a configured string")
    source = ops.context.get("hub_import_sources", {}).get(sid)
    if source is None:
        raise _error("IMPORT_SOURCE_NOT_CONFIGURED", "source_id is not configured on the daemon", 404)
    return source


def sources_list(ops) -> dict:
    rows = []
    for source in ops.context.get("hub_import_sources", {}).values():
        reason = None if source.runtime_retired else "HUB_NOT_RETIRED"
        available = True
        try:
            with _root(source.path):
                pass
        except OperationError as exc:
            available, reason = False, exc.code
        rows.append({"source_id": source.source_id, "runtime_retired": source.runtime_retired,
                     "can_preview": available, "can_apply": available and source.runtime_retired, "reason": reason})
    return {"sources": rows}


def source_for(db, connector_id: str, *, detail: bool = False) -> dict | None:
    row = db.execute("SELECT * FROM hub_import_map WHERE connector_id=?", (connector_id,)).fetchone()
    if row is None:
        return None
    record = json.loads(row["pending"] or row["snapshot"] or "{}")
    snap = record.get("snapshot", record)
    out = {"kind": "project_hub", "source_id": row["source_id"], "hub_project_id": row["hub_project_id"],
           "hub_task_id": row["hub_task_id"] or None, "hub_commit": HUB_COMMIT,
           "source_digest": record.get("source_digest", row["source_digest"]), "import_operation_id": row["operation_id"],
           "imported_at": row["imported_at"], "import_state": row["import_state"],
           "historical_completion": snap.get("historical_completion")}
    if detail:
        out["snapshot"] = snap
        out["original_relations"] = {k: snap.get("data", {}).get(k) for k in ("parent", "derivedFrom")}
        related = snap.get("related_projects", [])
        out["related_projects"] = [{**x, "project_id": _mapped_id(db, row["source_id"], x.get("key"))} for x in related]
        out["source_snapshot_operation_id"] = row["operation_id"]
    return out


def _mapped_id(db, sid: str, key: str | None) -> str | None:
    if not key:
        return None
    row = db.execute("SELECT connector_id FROM hub_import_map WHERE source_id=? AND record_key=?", (sid, key)).fetchone()
    return row[0] if row else None


def _maps(db, sid: str) -> dict:
    return {r["record_key"]: dict(r) for r in db.execute("SELECT * FROM hub_import_map WHERE source_id=?", (sid,))}


def _event_seq(db, resource: str, rid: str, *, exclude: str | None = None) -> int:
    row = db.execute("""SELECT MAX(seq) FROM api_events WHERE resource_type=? AND resource_id=?
        AND (? IS NULL OR COALESCE(json_extract(body,'$.operation_id'),'') != ?)""", (resource, rid, exclude, exclude)).fetchone()
    return row[0] or 0


def _destination(db, kind: str, cid: str | None, *, exclude: str | None = None) -> dict | None:
    if not cid:
        return None
    table, pk = ("projects", "project_id") if kind == "project" else ("work_items", "work_item_id")
    row = db.execute(f"SELECT * FROM {table} WHERE {pk}=?", (cid,)).fetchone()  # noqa: S608 - fixed identifiers
    if row is None:
        return None
    value = dict(row)
    value.update(wi.split_creation_reference(value.pop("operation_id")))
    links = [dict(r) for r in db.execute("SELECT * FROM work_item_links WHERE work_item_id=? ORDER BY link_id", (cid,))] if kind == "item" else []
    return {"row": value, "links": links, "event_seq": _event_seq(db, "work_item" if kind == "item" else "project", cid, exclude=exclude)}


def _group_state(db, sid: str, gk: str, *, exclude: str | None = None, ignore_new: bool = False) -> dict | None:
    kind, project, parent = json.loads(gk)
    parent_id = _mapped_id(db, sid, parent) or ""
    project_id = _mapped_id(db, sid, record_key("project", project)) if kind == "item" else None
    if (parent and not parent_id) or (kind == "item" and not project_id):
        return None
    if ignore_new:
        for cid, table, pk in ((project_id, "projects", "project_id"),
                               (parent_id, "projects" if kind == "project" else "work_items",
                                "project_id" if kind == "project" else "work_item_id")):
            if cid:
                row = db.execute(f"SELECT operation_id FROM {table} WHERE {pk}=?", (cid,)).fetchone()  # noqa: S608 - fixed identifiers
                if row and wi.split_creation_reference(row[0])["operation_id"] == exclude:
                    return None
    scope = "projects" if kind == "project" else f"items:{project_id}"
    if kind == "project":
        rows = list(db.execute("SELECT * FROM projects WHERE parent_id IS ? ORDER BY created_at,project_id", (parent_id or None,)))
    else:
        rows = list(db.execute("SELECT * FROM work_items WHERE project_id=? AND parent_id IS ? ORDER BY created_at,work_item_id", (project_id, parent_id or None)))
    members = []
    for row in rows:
        if ignore_new and wi.split_creation_reference(row["operation_id"])["operation_id"] == exclude:
            continue
        cid = row["project_id"] if kind == "project" else row["work_item_id"]
        seq = 0
        for e in db.execute("SELECT seq,kind,body FROM api_events WHERE resource_type=? AND resource_id=? ORDER BY seq", ("project" if kind == "project" else "work_item", cid)):
            body = json.loads(e["body"])
            if exclude and body.get("operation_id") == exclude:
                continue
            if e["kind"].endswith(("pinned", "unpinned", "archived", "restored")) or "parent_id" in body.get("fields", []):
                seq = e["seq"]
        members.append({"id": cid, "pinned": bool(row["pinned"]), "archived": row["archived_at"] is not None, "seq": seq})
    order = wi._saved_order(db, scope, parent_id)
    if ignore_new and order:
        ids = {x["id"] for x in members}
        order = [x for x in order if x in ids]
    ordered_seq = 0
    for e in db.execute("SELECT seq,body FROM api_events WHERE kind=? AND resource_id=? ORDER BY seq", ("project.ordered" if kind == "project" else "work_item.ordered", parent_id or "root" if kind == "project" else project_id)):
        body = json.loads(e["body"])
        if (body.get("parent_id") or "") == parent_id and (not exclude or body.get("operation_id") != exclude):
            ordered_seq = e["seq"]
    return {"scope": scope, "parent": parent_id, "members": members, "order": order, "event_seq": ordered_seq}


def _values(record: dict, maps: dict) -> dict:
    values = dict(record["values"])
    values["parent_id"] = maps.get(record.get("parent_key"), {}).get("connector_id")
    values["derived_from"] = maps.get(record.get("derived_key"), {}).get("connector_id")
    if record["kind"] == "project":
        values["pinned"] = int(record["pinned"])
    if "steps" in values:
        values["steps"] = _json(values["steps"])
    return values


def _plan(ops, snap: dict, normalized: dict) -> dict:
    sid, db = snap["source_id"], ops.db
    maps = _maps(db, sid)
    records, blockers, warnings = normalized["records"], list(normalized["blockers"]), list(normalized["warnings"])
    rows, counts = [], {"projects": dict.fromkeys(CLASSIFICATIONS, 0), "work_items": dict.fromkeys(CLASSIFICATIONS, 0),
                        "links": {"add": 0, "remove": 0}, "order_groups": {"change": 0, "conflict": 0}}
    source_keys = set()
    for pid, p in snap.get("projects", {}).items():
        source_keys.add(record_key("project", pid))
        source_keys.update(record_key("item", pid, tid) for tid in p["tasks"])
    all_keys = set(maps) | source_keys
    for key in sorted(all_keys, key=lambda k: (json.loads(k)[0] != "project", k.encode())):
        kind, pid, tid = json.loads(key)
        mapping, record = maps.get(key), records.get(key)
        if record and "source_digest" not in record:
            record = None
        cid = mapping["connector_id"] if mapping else None
        dest = _destination(db, kind, cid)
        comparable = dest
        base = json.loads(mapping["baseline"]) if mapping and mapping["baseline"] else None
        if mapping and mapping["import_state"] == "incomplete":
            comparable = _destination(db, kind, cid, exclude=mapping["operation_id"])
            receipt = db.execute("SELECT after_state FROM hub_import_receipts WHERE operation_id=? AND record_key=?", (mapping["operation_id"], key)).fetchone()
            base = json.loads(receipt[0])["destination"] if receipt and receipt[0] else base
            structure = _receipt(db, mapping["operation_id"], ":structure")
            if structure and key in structure["after"]["records"]:
                base = structure["after"]["records"][key]["destination"]
            pending = json.loads(mapping["pending"]) if mapping["pending"] else None
        else:
            pending = None
        fields, code = [], None
        if record is None:
            classification = "source_missing" if mapping and key not in source_keys else "conflict"
            if classification == "source_missing":
                warnings.append({"code": "SOURCE_MISSING", "record_key": key})
        elif mapping is None:
            classification = "create"
        elif dest is None:
            classification, code = "conflict", "IMPORT_TARGET_MISSING"
        else:
            source_changed = record["source_digest"] != (pending or {}).get("source_digest", mapping["source_digest"])
            local_changed = comparable != base
            incomplete = mapping["import_state"] == "incomplete"
            classification = "conflict" if (source_changed or incomplete) and local_changed else (
                "local_only" if local_changed else "update" if source_changed or incomplete else "unchanged")
            if classification == "update":
                project = db.execute("SELECT archived_at FROM projects WHERE project_id=?", (dest["row"]["project_id"],)).fetchone() if kind == "item" else None
                if kind == "item" and project is None:
                    classification, code = "conflict", "IMPORT_TARGET_MISSING"
                elif dest["row"]["archived_at"] is not None or (project and project[0] is not None):
                    classification, code = "conflict", "ARCHIVED"
                fields = [k for k, v in _values(record, maps).items() if dest["row"].get(k) != v]
                old_links = set((pending or json.loads(mapping["snapshot"] or "{}" )).get("links", []))
                new_links = set(record["links"])
                fields += ["links"] if old_links != new_links and kind == "item" else []
                if not fields and classification == "update":
                    classification = "metadata_only"
        if classification == "conflict":
            blockers.append({"code": code or "IMPORT_CONFLICT", "record_key": key, "message": "source and destination cannot be applied safely"})
        if record:
            existing_links = {x["ref"] for x in (dest or {}).get("links", []) if x["kind"] == "external_url" and x["removed_at"] is None}
            if classification in ("create", "update", "metadata_only") and kind == "item":
                old_links = set(json.loads(mapping["snapshot"] or "{}").get("links", [])) if mapping else set()
                counts["links"]["add"] += len(set(record["links"]) - existing_links)
                counts["links"]["remove"] += len((old_links - set(record["links"])) & existing_links)
        counts["projects" if kind == "project" else "work_items"][classification] += 1
        rows.append({"key": key, "kind": kind, "hub_project_id": pid, "hub_task_id": tid,
                     "connector_id": cid, "classification": classification, "changed_fields": fields,
                     "record": record, "expected": dest, "mapping_digest": _hash(mapping) if mapping else None,
                     "previous": json.loads(mapping["snapshot"] or "{}").get("values") if mapping else None,
                     "previous_source": json.loads(mapping["pending"] or mapping["snapshot"] or "{}") if mapping else None})
    for row in rows:
        if row["classification"] not in ("create", "update", "metadata_only"):
            continue
        record = row["record"]
        dependencies = [record.get("parent_key")]
        if row["kind"] == "item":
            dependencies.append(record_key("project", row["hub_project_id"]))
        for key in dependencies:
            mapping = maps.get(key)
            if mapping:
                dest = _destination(db, mapping["kind"], mapping["connector_id"])
                if not dest or dest["row"]["archived_at"] is not None:
                    blockers.append({"code": "ARCHIVED" if dest else "IMPORT_TARGET_MISSING",
                                     "record_key": row["key"], "message": "destination parent/project is unavailable"})
    # Name conflicts use the final projected names, never matching/claiming a local row by display name.
    changed = {x["connector_id"] for x in rows if x["kind"] == "project" and x["classification"] in ("create", "update")}
    names = {r["name"] for r in db.execute("SELECT project_id,name FROM projects WHERE archived_at IS NULL") if r["project_id"] not in changed}
    for row in rows:
        if row["kind"] == "project" and row["classification"] in ("create", "update"):
            name = row["record"]["values"]["name"]
            if name in names:
                blockers.append({"code": "NAME_TAKEN", "record_key": row["key"], "message": "project name already exists"})
            names.add(name)
    # The preview validates imported relationships against local descendants too.
    for kind, table, pk in (("project", "projects", "project_id"), ("item", "work_items", "work_item_id")):
        graph = {r[pk]: dict(r) for r in db.execute(f"SELECT * FROM {table}")}  # noqa: S608 - fixed identifiers
        identities = {k: m["connector_id"] for k, m in maps.items()}
        identities.update({r["key"]: r["connector_id"] or r["key"] for r in rows})
        for row in rows:
            if row["kind"] == kind and row["classification"] in ("create", "update", "metadata_only") and row["record"]:
                record = row["record"]
                graph[identities[row["key"]]] = {"parent_id": identities.get(record.get("parent_key")),
                                                "derived_from": identities.get(record.get("derived_key"))}
        try:
            _graph(graph, "parent_id", depth_limit=True)
            _graph(graph, "derived_from")
        except ValueError as exc:
            blockers.append({"code": "IMPORT_RELATION_INVALID", "message": str(exc)})
    group_plans = []
    saved_groups = {r["group_key"]: dict(r) for r in db.execute("SELECT * FROM hub_import_groups WHERE source_id=?", (sid,))}
    pending_groups = {}
    for op in {m["operation_id"] for m in maps.values() if m["import_state"] == "incomplete"}:
        structure = _receipt(db, op, ":structure")
        if structure:
            pending_groups.update({k: (op, v) for k, v in structure["after"]["groups"].items()})
    for gk in sorted(set(normalized["groups"]) | set(saved_groups)):
        group = normalized["groups"].get(gk, {"keys": [], "source_digest": _hash([])})
        state, old = _group_state(db, sid, gk), saved_groups.get(gk)
        changed = not old or old["source_digest"] != group["source_digest"]
        comparable = state
        baseline = json.loads(old["baseline"]) if old else None
        if gk in pending_groups:
            pending_op, baseline = pending_groups[gk]
            comparable = _group_state(db, sid, gk, exclude=pending_op)
        conflict = bool(changed and (old or gk in pending_groups) and comparable != baseline)
        if conflict:
            blockers.append({"code": "IMPORT_CONFLICT", "group_key": gk, "message": "destination sibling group was edited"})
        counts["order_groups"]["conflict" if conflict else "change"] += int(conflict or changed)
        group_plans.append({"key": gk, **group, "changed": changed, "conflict": conflict, "expected": state})
    if not _source(ops, sid).runtime_retired:
        blockers.append({"code": "HUB_NOT_RETIRED", "message": "retire the Hub runtime before applying"})
    counts.update(blockers=len(blockers), warnings=len(warnings))
    return {"source_id": sid, "manifest": snap["manifest"], "records": rows, "groups": group_plans,
            "source_files": snap["extras"],
            "counts": counts, "blockers": blockers, "warnings": warnings, "can_apply": not blockers,
            "source_revision": (ops.db.execute("SELECT revision FROM hub_import_sources WHERE source_id=?", (sid,)).fetchone() or [0])[0]}


def get_preview(ops, preview_id: str, principal: Principal) -> dict:
    if not isinstance(preview_id, str) or not PREVIEW_ID.fullmatch(preview_id):
        raise _error("INVALID_PARAMS", "preview_id must be hip_ followed by 32 hex characters")
    row = ops.db.execute("SELECT * FROM hub_import_previews WHERE preview_id=?", (preview_id,)).fetchone()
    if row is None:
        raise _error("PREVIEW_NOT_FOUND", "Hub import preview not found", 404)
    if row["actor"] != principal.actor and not principal.admin:
        raise _error("FORBIDDEN", "preview belongs to another actor", 403)
    doc = json.loads(row["document"])
    doc["expired"] = time.time() > row["expires_at"]
    try:
        source = _source(ops, row["source_id"])
        doc["expired"] |= doc["manifest"].get("binding") != _hash({"path": source.path, "retired": source.runtime_retired})
    except OperationError:
        doc["expired"] = True
    return doc


def apply_request(doc: dict) -> dict:
    return {"action": "hub.import.apply", "target": {"source_id": doc["source_id"]},
            "params": {"preview_id": doc["preview_id"]}, "preconditions": {"preview_digest": doc["digest"]},
            "idempotency_key": f"hub.import.apply.{doc['preview_id']}"}


def _admit_preview(ops, principal, target, params, pre):
    if set(target) != {"source_id"} or params or pre:
        raise _error("INVALID_PARAMS", "Hub preview takes only target.source_id")
    _source(ops, target["source_id"])


async def _run_preview(ctx: OpContext) -> dict:
    existing = ctx.service.db.execute("SELECT preview_id FROM hub_import_previews WHERE operation_id=?", (ctx.operation_id,)).fetchone()
    if existing:
        return _preview_result(get_preview(ctx.service, existing[0], Principal(ctx.actor, frozenset({"manage"}))))
    source = _source(ctx.service, ctx.target["source_id"])
    try:
        snap = await asyncio.to_thread(snapshot, source)
        snap["source_id"] = source.source_id
        normalized = await asyncio.to_thread(normalize, snap)
        doc = _plan(ctx.service, snap, normalized)
    except OperationError as exc:
        doc = {"source_id": source.source_id, "manifest": {}, "records": [], "groups": [], "warnings": [],
               "counts": {"blockers": 1}, "can_apply": False, "blockers": [{"code": exc.code, "message": str(exc)}]}
    now = time.time()
    doc.update(preview_id="hip_" + secrets.token_hex(16), actor=ctx.actor, hub_commit=HUB_COMMIT,
               parser_version=PARSER_VERSION, created_at=now, expires_at=now + TTL)
    doc["digest"] = _hash(doc)
    with ctx.service.journal.tx():
        ctx.service.db.execute("INSERT INTO hub_import_previews VALUES(?,?,?,?,?,?,?,?)", (doc["preview_id"], ctx.operation_id, ctx.actor,
            source.source_id, doc["digest"], _json(doc), now, now + TTL))
    return _preview_result(doc)


def _preview_result(doc):
    # General operation reads must not expose an actor-bound, unimported source snapshot.
    return {"preview": {k: doc[k] for k in ("preview_id", "source_id", "digest", "counts", "can_apply", "expires_at")}}


def _busy(ops, sid: str, *, exclude: str | None = None):
    for row in ops.db.execute("SELECT operation_id,target FROM operations WHERE action='hub.import.apply' AND status NOT IN ('succeeded','failed','cancelled')"):
        if row["operation_id"] != exclude and json.loads(row["target"]).get("source_id") == sid:
            raise _error("IMPORT_BUSY", "another apply for this source is active", 409)


def _admit_apply(ops, principal, target, params, pre):
    if set(target) != {"source_id"} or set(params) != {"preview_id"} or set(pre) != {"preview_digest"}:
        raise _error("INVALID_PARAMS", "Hub apply takes source_id, preview_id and preview_digest")
    source = _source(ops, target["source_id"])
    doc = get_preview(ops, params["preview_id"], principal)
    if doc["actor"] != principal.actor or doc["source_id"] != source.source_id or doc["digest"] != pre["preview_digest"]:
        raise _error("PREVIEW_MISMATCH", "preview actor, source or digest differs", 409)
    if doc["expired"]:
        raise _error("PREVIEW_EXPIRED", "preview expired; preview again", 409)
    if not source.runtime_retired:
        raise _error("HUB_NOT_RETIRED", "retire the Hub runtime before applying", 409)
    if not doc["can_apply"]:
        raise _error("IMPORT_CONFLICT", "preview has conflicts or blockers", 409)
    _busy(ops, source.source_id)


def _receipt(db, op: str, key: str) -> dict | None:
    row = db.execute("SELECT * FROM hub_import_receipts WHERE operation_id=? AND record_key=?", (op, key)).fetchone()
    return {"result": json.loads(row["result"]), "after": json.loads(row["after_state"]) if row["after_state"] else None} if row else None


def _save_receipt(ctx, key: str, result: dict, after=None):
    ctx.service.db.execute("INSERT INTO hub_import_receipts VALUES(?,?,?,?,?)", (ctx.operation_id, key, _json(result), _json(after) if after is not None else None, time.time()))


def import_get(ops, operation_id: str) -> dict:
    op = ops.get(operation_id)
    if op["action"] != "hub.import.apply":
        raise _error("NOT_FOUND", "not a Hub import apply", 404)
    row = ops.db.execute("SELECT document FROM hub_import_previews WHERE preview_id=?", (op["params"]["preview_id"],)).fetchone()
    doc = json.loads(row[0]) if row else {"records": [], "groups": []}
    result = _result(ops.db, op["operation_id"], doc)
    # Request/provenance bodies are private until imported, and are never in the aggregate read model.
    out = {"operation": op, "import": result}
    if result["complete"]:
        snapshot = ops.db.execute("SELECT manifest,snapshot FROM hub_import_source_snapshots WHERE operation_id=?", (operation_id,)).fetchone()
        if snapshot:
            out["source_snapshot"] = {"manifest": json.loads(snapshot["manifest"]), "files": json.loads(snapshot["snapshot"])}
    return out


def _result(db, op: str, doc: dict) -> dict:
    rows = []
    for row in doc["records"]:
        receipt = _receipt(db, op, row["key"])
        status = row["classification"]
        if receipt:
            rows.append(receipt["result"])
        else:
            rows.append({"key": row["key"], "connector_id": row["connector_id"], "status": status if status in ("unchanged", "local_only", "source_missing") else "pending"})
    done = _receipt(db, op, ":finalize") is not None
    return {"preview_id": doc.get("preview_id"), "source_id": doc.get("source_id"), "records": rows,
            "counts": dict(Counter(x["status"] for x in rows)), "partial": not done and any(x["status"] in ("created", "updated", "metadata_only") for x in rows),
            "complete": done, "groups": (_receipt(db, op, ":structure") or {}).get("result", {})}


def _verify_record(ctx, row: dict):
    db, sid = ctx.service.db, ctx.target["source_id"]
    mapping = db.execute("SELECT * FROM hub_import_map WHERE source_id=? AND record_key=?", (sid, row["key"])).fetchone()
    receipt = _receipt(db, ctx.operation_id, row["key"])
    structure = _receipt(db, ctx.operation_id, ":structure")
    expected = receipt["after"] if receipt else {"destination": row["expected"], "mapping_digest": row["mapping_digest"]}
    cid = mapping["connector_id"] if mapping else None
    current = _destination(db, row["kind"], cid, exclude=ctx.operation_id)
    if structure and row["key"] in structure["after"]["records"]:
        expected = structure["after"]["records"][row["key"]]
    if current != expected["destination"] or (_hash(dict(mapping)) if mapping else None) != expected["mapping_digest"]:
        raise _error("DESTINATION_CHANGED", f"destination changed: {row['key']}", 409)


def _verify_destinations(ctx, doc):
    for row in doc["records"]:
        _verify_record(ctx, row)
    structure = _receipt(ctx.service.db, ctx.operation_id, ":structure")
    for group in doc["groups"]:
        expected = structure["after"]["groups"][group["key"]] if structure else group["expected"]
        current = _group_state(ctx.service.db, ctx.target["source_id"], group["key"], exclude=ctx.operation_id, ignore_new=not structure)
        if current != expected:
            raise _error("DESTINATION_CHANGED", "destination sibling group changed", 409)


async def _verify_source(ctx, doc):
    source = _source(ctx.service, doc["source_id"])
    if not source.runtime_retired:
        raise _error("HUB_NOT_RETIRED", "Hub retirement declaration changed", 409)
    snap = await asyncio.to_thread(snapshot, source)
    if snap["manifest"] != doc["manifest"]:
        raise _error("SOURCE_CHANGED", "source differs from the reviewed snapshot", 409)
    revision = (ctx.service.db.execute("SELECT revision FROM hub_import_sources WHERE source_id=?", (source.source_id,)).fetchone() or [0])[0]
    if revision != doc["source_revision"]:
        raise _error("DESTINATION_CHANGED", "source mapping revision changed", 409)


def _sync_links(ctx, cid, record, previous, now):
    db = ctx.service.db
    old = set(previous.get("links", []))
    new = set(record["links"])
    for url in old - new:
        link = db.execute("SELECT * FROM work_item_links WHERE work_item_id=? AND kind='external_url' AND ref=? AND removed_at IS NULL", (cid, url)).fetchone()
        if link and db.execute("SELECT 1 FROM hub_import_receipts WHERE operation_id=?", (link["link_operation"],)).fetchone():
            db.execute("UPDATE work_item_links SET removed_at=?,removed_by=?,remove_operation=? WHERE link_id=?", (now, ctx.actor, ctx.operation_id, link["link_id"]))
            wi._event(ctx, "work_item", cid, "work_item.unlinked", {"kind": "external_url", "ref": url})
    for url in new:
        if wi._active_link(db, cid, "external_url", url):
            continue
        db.execute("INSERT INTO work_item_links(work_item_id,kind,ref,note,linked_by,linked_at,link_operation) VALUES(?,?,?,?,?,?,?)", (cid, "external_url", url, "Project Hub", ctx.actor, now, ctx.operation_id))
        wi._event(ctx, "work_item", cid, "work_item.linked", {"kind": "external_url", "ref": url})


def _save_source_snapshot(ctx, doc):
    if not ctx.service.db.execute("SELECT 1 FROM hub_import_source_snapshots WHERE operation_id=?", (ctx.operation_id,)).fetchone():
        ctx.service.db.execute("INSERT INTO hub_import_source_snapshots VALUES(?,?,?,?,?)",
            (ctx.operation_id, doc["source_id"], _json(doc["manifest"]), _json(doc["source_files"]), time.time()))


def _write_record(ctx, row: dict, doc: dict) -> dict:
    key = row["key"]
    reference = f"{ctx.operation_id}#{record_id(key)}"

    def change(db, now):
        _verify_record(ctx, row)
        record = row["record"]
        kind, sid = row["kind"], ctx.target["source_id"]
        mapping = db.execute("SELECT * FROM hub_import_map WHERE source_id=? AND record_key=?", (sid, key)).fetchone()
        cid = mapping["connector_id"] if mapping else ("prj_" if kind == "project" else "wi_") + secrets.token_hex(10)
        values = dict(record["values"])
        if "steps" in values:
            values["steps"] = _json(values["steps"])
        if mapping is None:
            columns = {"project_id" if kind == "project" else "work_item_id": cid, **values,
                       "created_by": ctx.actor, "operation_id": reference, "created_at": now, "updated_at": now}
            if kind == "item":
                columns["project_id"] = _mapped_id(db, sid, record_key("project", record["hub_project_id"]))
                if not columns["project_id"]:
                    raise _error("IMPORT_RELATION_INVALID", "project has not been imported")
                if values["state"] == "done":
                    columns.update(done_by=f"project_hub:{sid}", done_at=now)
            table = "projects" if kind == "project" else "work_items"
            db.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", tuple(columns.values()))  # noqa: S608 - fixed identifiers
            wi._event(ctx, "project" if kind == "project" else "work_item", cid, "project.created" if kind == "project" else "work_item.created", {"source_id": sid})
            db.execute("INSERT INTO hub_import_map(source_id,record_key,kind,hub_project_id,hub_task_id,connector_id,operation_id,imported_at) VALUES(?,?,?,?,?,?,?,?)", (sid, key, kind, record["hub_project_id"], record["hub_task_id"], cid, ctx.operation_id, now))
            status = "created"
        else:
            dest = _destination(db, kind, cid, exclude=ctx.operation_id)["row"]
            changes = {k: v for k, v in values.items() if v != dest[k]}
            if changes:
                if kind == "item" and "state" in changes:
                    changes.update(done_by=f"project_hub:{sid}" if changes["state"] == "done" else None,
                                   done_at=now if changes["state"] == "done" else None,
                                   approved_fingerprint=None, approved_by=None, approved_at=None)
                table, pk = ("projects", "project_id") if kind == "project" else ("work_items", "work_item_id")
                db.execute(f"UPDATE {table} SET {','.join(k+'=?' for k in changes)},version=version+1,updated_at=? WHERE {pk}=?", (*changes.values(), now, cid))  # noqa: S608 - fixed fields
                wi._event(ctx, "project" if kind == "project" else "work_item", cid, "project.updated" if kind == "project" else "work_item.updated", {"fields": sorted(changes)})
            status = "metadata_only" if row["classification"] == "metadata_only" else "updated"
        previous = json.loads(mapping["pending"] or mapping["snapshot"] or "{}") if mapping else {}
        if kind == "item":
            _sync_links(ctx, cid, record, previous, now)
        db.execute("UPDATE hub_import_map SET pending=?,import_state='incomplete',operation_id=?,imported_at=? WHERE source_id=? AND record_key=?", (_json(record), ctx.operation_id, now, sid, key))
        mapping = dict(db.execute("SELECT * FROM hub_import_map WHERE source_id=? AND record_key=?", (sid, key)).fetchone())
        result = {"key": key, "connector_id": cid, "operation_id": ctx.operation_id, "import_record": record_id(key), "status": status}
        after = {"destination": _destination(db, kind, cid, exclude=ctx.operation_id), "mapping_digest": _hash(mapping)}
        _save_source_snapshot(ctx, doc)
        _save_receipt(ctx, key, result, after)
        return result
    return wi._once(ctx, change, key=reference)


async def _records(ctx, doc):
    for i, row in enumerate(doc["records"]):
        try:
            ctx.check_cancel()
        except Cancelled:
            return {"records": i, "cancelled": True}
        if row["classification"] in ("create", "update", "metadata_only") and not _receipt(ctx.service.db, ctx.operation_id, row["key"]):
            try:
                _write_record(ctx, row, doc)
            except sqlite3.Error as exc:
                raise OSError("Hub record transaction could not be completed") from exc
        if i % 32 == 0:
            await asyncio.sleep(0)
    return {"records": len(doc["records"])}


def _merge_order(existing: list[str], imported: list[str], members: list[dict], owned: set[str]) -> list[str]:
    present = {x["id"] for x in members}
    base = list(dict.fromkeys([*existing, *(x["id"] for x in members)]))
    pinned = {x["id"] for x in members if x["pinned"]}
    archived = {x["id"] for x in members if x["archived"]}
    result = []
    for pin in (True, False):
        wanted = [x for x in imported if (x in pinned) == pin and x not in archived]
        wanted_set = set(wanted)
        pos = 0
        for cid in base:
            if cid not in present or cid in archived:
                if not pin:
                    result.append(cid)
                continue
            if (cid in pinned) != pin:
                continue
            if cid in owned and cid in wanted_set:
                if pos < len(wanted):
                    result.append(wanted[pos])
                    pos += 1
            else:
                result.append(cid)
        result.extend(wanted[pos:])
    return list(dict.fromkeys(result))


def _structure(ctx, doc):
    def change(db, now):
        _verify_destinations(ctx, doc)
        _save_source_snapshot(ctx, doc)
        maps = _maps(db, doc["source_id"])
        changed_records = []
        for row in doc["records"]:
            if row["classification"] not in ("create", "update", "metadata_only"):
                continue
            r, cid = row["record"], maps[row["key"]]["connector_id"]
            dest = _destination(db, row["kind"], cid, exclude=ctx.operation_id)["row"]
            changes = {k: v for k, v in _values(r, maps).items() if k in STRUCTURAL and dest.get(k) != v}
            if changes:
                table, pk = ("projects", "project_id") if row["kind"] == "project" else ("work_items", "work_item_id")
                db.execute(f"UPDATE {table} SET {','.join(k+'=?' for k in changes)},version=version+1,updated_at=? WHERE {pk}=?", (*changes.values(), now, cid))  # noqa: S608 - fixed columns
                wi._event(ctx, "project" if row["kind"] == "project" else "work_item", cid, "project.updated" if row["kind"] == "project" else "work_item.updated", {"fields": sorted(changes)})
            changed_records.append(row)
        # Validate the combined destination, including local descendants below imported rows.
        for _kind, table, pk in (("project", "projects", "project_id"), ("item", "work_items", "work_item_id")):
            graph = {r[pk]: dict(r) for r in db.execute(f"SELECT * FROM {table}")}  # noqa: S608 - fixed table
            try:
                _graph(graph, "parent_id", depth_limit=True)
                _graph(graph, "derived_from")
            except ValueError as exc:
                raise _error("IMPORT_RELATION_INVALID", str(exc)) from None
        groups = []
        owned = {r["connector_id"] for r in maps.values()}
        for group in doc["groups"]:
            if not group["changed"]:
                continue
            state = _group_state(db, doc["source_id"], group["key"], exclude=ctx.operation_id)
            if state is None:
                continue
            imported = [maps[k]["connector_id"] for k in group["keys"] if k in maps]
            order = _merge_order(state["order"] or [], imported, state["members"], owned)
            if state["order"] != order:
                db.execute("INSERT INTO tree_order(scope,parent,ids) VALUES(?,?,?) ON CONFLICT(scope,parent) DO UPDATE SET ids=excluded.ids", (state["scope"], state["parent"], _json(order)))
                kind, project, _ = json.loads(group["key"])
                wi._event(ctx, "project", state["parent"] or "root" if kind == "project" else _mapped_id(db, doc["source_id"], record_key("project", project)),
                          "project.ordered" if kind == "project" else "work_item.ordered", {"parent_id": state["parent"] or None})
            groups.append({"key": group["key"], "order": order})
        after = {"records": {r["key"]: {"destination": _destination(db, r["kind"], maps[r["key"]]["connector_id"], exclude=ctx.operation_id), "mapping_digest": _hash(maps[r["key"]])} for r in changed_records},
                 "groups": {g["key"]: _group_state(db, doc["source_id"], g["key"], exclude=ctx.operation_id) for g in doc["groups"]}}
        _save_receipt(ctx, ":structure", {"groups": groups}, after)
        return {"groups": groups}
    return wi._once(ctx, change, key=ctx.operation_id + "#structure")


def _summary(ctx, doc, *, complete: bool):
    def change(db, now):
        result = _result(db, ctx.operation_id, doc)
        ctx.service.journal.api_event("hub_import", ctx.operation_id, "hub_import.completed" if complete else "hub_import.incomplete",
                                     {"source_id": doc["source_id"], "operation_id": ctx.operation_id, "counts": result["counts"]}, actor=ctx.actor)
        return {"complete": complete}
    return wi._once(ctx, change, key=ctx.operation_id + "#summary")


def _finalize(ctx, doc):
    def change(db, now):
        _verify_destinations(ctx, doc)
        for row in doc["records"]:
            if row["classification"] not in ("create", "update", "metadata_only"):
                continue
            mapping = db.execute("SELECT * FROM hub_import_map WHERE source_id=? AND record_key=?", (doc["source_id"], row["key"])).fetchone()
            baseline = _destination(db, row["kind"], mapping["connector_id"])
            db.execute("UPDATE hub_import_map SET source_digest=?,snapshot=pending,baseline=?,pending=NULL,import_state='complete' WHERE source_id=? AND record_key=?", (row["record"]["source_digest"], _json(baseline), doc["source_id"], row["key"]))
        for group in doc["groups"]:
            if group["changed"]:
                baseline = _group_state(db, doc["source_id"], group["key"])
                db.execute("INSERT INTO hub_import_groups VALUES(?,?,?,?) ON CONFLICT(source_id,group_key) DO UPDATE SET source_digest=excluded.source_digest,baseline=excluded.baseline", (doc["source_id"], group["key"], group["source_digest"], _json(baseline)))
        db.execute("INSERT INTO hub_import_sources(source_id,revision,manifest,operation_id,actor,updated_at) VALUES(?,1,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET revision=revision+1,manifest=excluded.manifest,operation_id=excluded.operation_id,actor=excluded.actor,updated_at=excluded.updated_at", (doc["source_id"], _json(doc["manifest"]), ctx.operation_id, ctx.actor, now))
        _save_receipt(ctx, ":finalize", {"complete": True})
        return _result(db, ctx.operation_id, doc)
    return wi._once(ctx, change, key=ctx.operation_id + "#finalize")


async def _finalized_result(ctx, doc):
    return _result(ctx.service.db, ctx.operation_id, doc)


async def _run_apply(ctx: OpContext):
    doc = get_preview(ctx.service, ctx.params["preview_id"], Principal(ctx.actor, frozenset({"manage"})))
    finalized = _receipt(ctx.service.db, ctx.operation_id, ":finalize")
    if finalized:
        await ctx.step("baseline.finalize", lambda: _finalized_result(ctx, doc),
                       reconcile=lambda _: _finalized_result(ctx, doc))
        _summary(ctx, doc, complete=True)
        return _result(ctx.service.db, ctx.operation_id, doc)

    async def source_verify():
        _verify_destinations(ctx, doc)
        return {"manifest_digest": _hash(doc["manifest"])}

    async def records_reconcile(_):
        _verify_destinations(ctx, doc)
        return RERUN

    async def structure_run():
        try:
            return _structure(ctx, doc)
        except sqlite3.Error as exc:
            raise OSError("Hub structure transaction could not be completed") from exc

    async def finalize_run():
        try:
            return _finalize(ctx, doc)
        except sqlite3.Error as exc:
            raise OSError("Hub baseline transaction could not be completed") from exc

    def phase_reconcile(key):
        async def reconcile(_):
            row = ctx.service.db.execute("SELECT result FROM management_applied WHERE operation_id=?", (ctx.operation_id + "#" + key,)).fetchone()
            return json.loads(row[0]) if row else RERUN
        return reconcile

    try:
        _busy(ctx.service, doc["source_id"], exclude=ctx.operation_id)
        await _verify_source(ctx, doc)
        _verify_destinations(ctx, doc)
        await ctx.step("source.verify", source_verify, reconcile=lambda _: source_verify())
        await ctx.step("records", lambda: _records(ctx, doc), reconcile=records_reconcile)
        ctx.check_cancel()
        await _verify_source(ctx, doc)
        await ctx.step("structure.apply", structure_run, reconcile=phase_reconcile("structure"))
        await _verify_source(ctx, doc)
        await ctx.step("baseline.finalize", finalize_run, reconcile=phase_reconcile("finalize"))
        _summary(ctx, doc, complete=True)
        return _result(ctx.service.db, ctx.operation_id, doc)
    except Cancelled:
        _summary(ctx, doc, complete=False)
        raise
    except Uncertain:
        if ctx.op["uncertain_tries"] >= len(UNCERTAIN_RETRY_S):
            _summary(ctx, doc, complete=False)
        raise
    except (OperationError, StepFailed, sqlite3.Error) as exc:
        _summary(ctx, doc, complete=False)
        code = getattr(exc, "code", "IMPORT_DATABASE_ERROR")
        raise NeedsAttention(code, str(exc)) from None


ACTIONS = [
    ActionDef("hub.import.preview", "manage", "Preview a configured, read-only Project Hub snapshot", _run_preview, _admit_preview, ("source_id",)),
    ActionDef("hub.import.apply", "manage", "Apply the reviewed Hub import, preserving local edits", _run_apply, _admit_apply, ("source_id",)),
]
