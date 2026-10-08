"""Fixed read-only single-file reader, sent verbatim over the configured SSH adapter.

No package imports or caller commands. JSON header then optional bounded raw bytes.
Python 3.9+ on POSIX hosts; this is detection of observable changes, not a writer lock.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import unicodedata

VERSION = 1


class Refusal(Exception):
    def __init__(self, code):
        self.code = code


def relative_parts(value):
    if (not isinstance(value, str) or not value or len(value.encode()) > 4096
            or "\\" in value or any(unicodedata.category(c) == "Cc" for c in value)
            or any(p in {"", ".", ".."} or p.casefold() == ".git" for p in value.split("/"))):
        raise Refusal("INVALID_CAPTURE_PATH")
    return value.split("/")


def directory(path):
    if not isinstance(path, str) or not path.startswith("/") or ".." in path.split("/"):
        raise Refusal("SOURCE_UNAVAILABLE")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.split("/"):
            if part:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def identity(info):
    return {key: getattr(info, "st_" + key) for key in
            ("dev", "ino", "mode", "nlink", "size", "mtime_ns", "ctime_ns")}


def root_identity(info):
    return {key: getattr(info, "st_" + key) for key in ("dev", "ino", "mode")}


def head(root, repository):
    # No status/index refresh, hooks, filters, prompts, replacement objects or inherited Git routing.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    out = subprocess.run(  # noqa: S603 - fixed read-only verbs, centrally observed root
        ["git", "--no-optional-locks", "--no-replace-objects", "-C", root,  # noqa: S607
         "rev-parse", "--show-toplevel", "--verify", "HEAD"],
        capture_output=True, text=True, timeout=20, check=True, env=env).stdout.splitlines()
    if len(out) != 2 or out[0] != repository or not re.fullmatch(r"[0-9a-f]{40}", out[1]):
        raise Refusal("SOURCE_CHANGED")
    return out[1]


def open_file(root_fd, parts):
    parent = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = nxt
        # NONBLOCK makes FIFO rejection bounded before inspecting its type.
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        return fd
    finally:
        os.close(parent)


def read_chunk(fd, size):
    return os.read(fd, size)


def execute(request):
    if (sys.version_info < (3, 9) or not hasattr(os, "O_NOFOLLOW")
            or os.open not in os.supports_dir_fd):
        raise Refusal("ARTIFACT_ADAPTER_UNAVAILABLE")
    if request.get("mode") not in {"preview", "capture"}:
        raise Refusal("INVALID_PARAMS")
    parts = relative_parts(request.get("relative_path"))
    maximum = request.get("max_file_bytes")
    if type(maximum) is not int or maximum <= 0:
        raise Refusal("INVALID_PARAMS")
    root, repository = request["root"], request["repository_root"]
    root_fd = directory(root)
    try:
        root_before = root_identity(os.fstat(root_fd))
        first_head = head(root, repository)
        fd = open_file(root_fd, parts)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise Refusal("CAPTURE_FILE_UNSAFE")
            if before.st_size > maximum:
                raise Refusal("ARTIFACT_TOO_LARGE")
            digest, size, chunks = hashlib.sha256(), 0, []
            while True:
                chunk = read_chunk(fd, min(65536, maximum - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum:
                    raise Refusal("ARTIFACT_TOO_LARGE")
                digest.update(chunk)
                if request["mode"] == "capture":
                    chunks.append(chunk)
            if identity(before) != identity(os.fstat(fd)) or size != before.st_size:
                raise Refusal("SOURCE_CHANGED")
            reopened_root = directory(root)
            try:
                reopened_file = open_file(reopened_root, parts)
                try:
                    if (root_identity(os.fstat(reopened_root)) != root_before
                            or identity(os.fstat(reopened_file)) != identity(before)):
                        raise Refusal("SOURCE_CHANGED")
                finally:
                    os.close(reopened_file)
            finally:
                os.close(reopened_root)
            if head(root, repository) != first_head:
                raise Refusal("SOURCE_CHANGED")
            final_root = directory(root)
            try:
                final_file = open_file(final_root, parts)
                try:
                    if (root_identity(os.fstat(final_root)) != root_before
                            or identity(os.fstat(final_file)) != identity(before)
                            or identity(os.fstat(fd)) != identity(before)):
                        raise Refusal("SOURCE_CHANGED")
                finally:
                    os.close(final_file)
            finally:
                os.close(final_root)
            evidence = {"helper_version": VERSION, "root_identity": root_before,
                        "file_identity": identity(before), "head_sha": first_head,
                        "digest": digest.hexdigest(), "size_bytes": size}
            if request["mode"] == "capture" and request.get("expected") != evidence:
                raise Refusal("SOURCE_CHANGED")
            return {"ok": True, "evidence": evidence}, b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(root_fd)


def main():
    data = b""
    try:
        line = sys.stdin.buffer.readline(32769)
        if len(line) > 32768:
            raise Refusal("INVALID_PARAMS")
        result, data = execute(json.loads(line))
    except Refusal as exc:
        result = {"ok": False, "code": exc.code}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        result = {"ok": False, "code": "SOURCE_UNAVAILABLE"}
    sys.stdout.buffer.write(json.dumps(result, separators=(",", ":")).encode() + b"\n")
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    main()
