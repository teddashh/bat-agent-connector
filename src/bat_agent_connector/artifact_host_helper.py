"""Fixed artifact receiver, sent as code over SSH; standard library, Python 3.9+.

Not a shell API. The first stdin line is bounded JSON, followed by bounded raw bytes.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import unicodedata

VERSION = 1


class Refusal(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def directory(path):
    if not isinstance(path, str) or not path.startswith("/") or ".." in path.split("/"):
        raise Refusal("DESTINATION_UNKNOWN", "invalid absolute path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.split("/"):
            if not part:
                continue
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def child(fd, name, mode=0o700):
    try:
        os.mkdir(name, mode, dir_fd=fd)
        os.fsync(fd)
    except FileExistsError:
        pass
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)


def regular(fd, name, flags=os.O_RDONLY, mode=0o600):
    result = os.open(name, flags | os.O_NOFOLLOW, mode, dir_fd=fd)
    info = os.fstat(result)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(result)
        raise Refusal("DESTINATION_UNKNOWN", "not a private regular file")
    return result


def hash_file(fd, name):
    handle = regular(fd, name)
    digest, size = hashlib.sha256(), 0
    try:
        before = os.fstat(handle)
        for chunk in iter(lambda: os.read(handle, 65536), b""):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(handle)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise Refusal("ARTIFACT_CONTENT_UNAVAILABLE", "input changed while reading")
    finally:
        os.close(handle)
    return size, digest.hexdigest()


def json_file(fd, name, value):
    handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(handle, "w") as file:
        json.dump(value, file, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.fsync(fd)


def read_json(fd, name):
    with os.fdopen(regular(fd, name)) as file:
        data = file.read(4097)
    if len(data) > 4096:
        raise Refusal("BINDING_MISMATCH", "oversized marker")
    return json.loads(data)


def git(path, *args):
    result = subprocess.run(  # noqa: S603,S607 - fixed git verbs, validated managed cwd
                            ["git", "--no-optional-locks", "-C", path, *args],  # noqa: S607
                            capture_output=True, text=True, timeout=20, check=True)
    return result.stdout.strip()


def execute(request, stream):
    if sys.version_info < (3, 9) or not hasattr(os, "O_NOFOLLOW") or os.link not in os.supports_dir_fd:
        raise Refusal("ARTIFACT_ADAPTER_UNAVAILABLE", "Python 3.9+ with no-follow dirfd and link is required")
    if request.get("mode") == "probe":
        ready = {"helper_version": VERSION, "python": list(sys.version_info[:3]), "git_version": None}
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=20, check=True)  # noqa: S603,S607 - fixed read-only git verb
        except (OSError, subprocess.SubprocessError):
            return {**ready, "ok": False, "code": "ARTIFACT_ADAPTER_UNAVAILABLE", "message": "Git 2.31+ is required; git --version is unavailable"}
        version = result.stdout.strip().removeprefix("git version ")
        ready["git_version"] = version
        match = re.match(r"^(\d+)\.(\d+)(?:\.\d+)?(?:\s|\.|$)", version)
        if not match or tuple(map(int, match.groups())) < (2, 31):
            return {**ready, "ok": False, "code": "ARTIFACT_ADAPTER_UNAVAILABLE", "message": "Git 2.31+ is required for absolute common-dir paths; found " + version}
        return {**ready, "ok": True}
    clone, worktree = request["clone"], request["worktree"]
    operation = request["operation_id"]
    ref, name, attempt = request["ref"], request["name"], request["attempt"]
    if (not re.fullmatch(r"op_[0-9a-f]{32}", operation)
            or not re.fullmatch(r"art_[0-9a-f]{32}", ref["artifact_id"])
            or type(ref["revision"]) is not int or ref["revision"] < 1
            or not re.fullmatch(r"[0-9a-f]{64}", ref["digest"])
            or type(attempt) is not int or attempt < 1
            or name in {".", "..", ".git"} or not name or len(name.encode()) > 240
            or any(c in name for c in "/\\") or any(unicodedata.category(c) == "Cc" for c in name)):
        raise Refusal("DESTINATION_UNKNOWN", "invalid input identity")
    published = request.get("published_binding")
    if published is not None and (not isinstance(published, dict) or set(published) != {"binding_digest", "source_sha"}
            or not re.fullmatch(r"[0-9a-f]{64}", str(published.get("binding_digest")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(published.get("source_sha")))
            or os.path.basename(clone) != "batc-published-" + operation[3:]):
        raise Refusal("BINDING_MISMATCH", "invalid published input binding")
    prefix = "batc-published-" if published is not None else "batc-cp-"
    if worktree != clone + "/.bat-worktrees/" + prefix + operation[3:15]:
        raise Refusal("DESTINATION_UNKNOWN", "worktree differs from continuation intent")
    clone_fd, work_fd = directory(clone), directory(worktree)
    try:
        if git(clone, "config", "--local", "--get", "batc.managed-clone") != "true":
            raise Refusal("BINDING_MISMATCH", "not a connector clone")
        if published is not None and (git(clone, "config", "--local", "--get", "batc.role") != "published"
                or git(clone, "config", "--local", "--get", "batc.operation") != operation
                or git(clone, "config", "--local", "--get", "batc.binding") != published["binding_digest"]
                or git(worktree, "rev-parse", "HEAD") != published["source_sha"]
                or git(worktree, "branch", "--show-current") != "batc/published-" + operation[3:15]):
            raise Refusal("BINDING_MISMATCH", "published carrier differs from the original operation")
        common = git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if common != clone + "/.git" or git(worktree, "rev-parse", "--show-toplevel") != worktree:
            raise Refusal("BINDING_MISMATCH", "worktree git binding differs")
        try:
            existing_inputs = os.open(".batc-inputs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=work_fd)
        except FileNotFoundError:
            existing_inputs = None
        if existing_inputs is not None:
            try:
                try:
                    owner = read_json(existing_inputs, ".owner")
                except FileNotFoundError:
                    if os.listdir(existing_inputs):
                        raise Refusal("BINDING_MISMATCH", "unknown input directory") from None
                else:
                    if owner != {"operation_id": operation, "helper_version": VERSION}:
                        raise Refusal("BINDING_MISMATCH", "input owner differs")
                cursor = os.dup(existing_inputs)
                try:
                    for part in (".attempts", ref["artifact_id"] + "-r" + str(ref["revision"])):
                        try:
                            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cursor)
                        except FileNotFoundError:
                            break
                        os.close(cursor)
                        cursor = nxt
                    else:
                        for name_to_check in (".attempt-" + str(attempt), ".closed-" + str(attempt)):
                            try:
                                info = os.stat(name_to_check, dir_fd=cursor, follow_symlinks=False)
                                if not stat.S_ISREG(info.st_mode):
                                    raise Refusal("DESTINATION_UNKNOWN", "invalid attempt file")
                            except FileNotFoundError:
                                pass
                finally:
                    os.close(cursor)
            finally:
                os.close(existing_inputs)
        # Inspect existing destination components before even appending the Git exclude.
        check_fd = os.dup(work_fd)
        try:
            for part in (".batc-inputs", ref["artifact_id"] + "-r" + str(ref["revision"])):
                try:
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=check_fd)
                except FileNotFoundError:
                    break
                os.close(check_fd)
                check_fd = nxt
            else:
                try:
                    info = os.stat(name, dir_fd=check_fd, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise Refusal("DESTINATION_UNKNOWN", "invalid final file")
                except FileNotFoundError:
                    pass
        finally:
            os.close(check_fd)
        # The common exclude is the clone's, never the source checkout's.
        common_fd = directory(common)
        try:
            info_fd = child(common_fd, "info", 0o755) if request["mode"] == "receive" else os.open(
                "info", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=common_fd)
            try:
                if request["mode"] == "receive":
                    try:
                        exclude = regular(info_fd, "exclude", os.O_RDWR | os.O_APPEND)
                    except FileNotFoundError:
                        exclude = regular(info_fd, "exclude", os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL, 0o644)
                        os.fsync(info_fd)
                    try:
                        existing = os.read(exclude, 1024 * 1024)
                        if b"/.batc-inputs/" not in existing.splitlines():
                            os.write(exclude, b"\n/.batc-inputs/\n")
                            os.fsync(exclude)
                    finally:
                        os.close(exclude)
            finally:
                os.close(info_fd)
        finally:
            os.close(common_fd)
        if request["mode"] == "receive":
            inputs = child(work_fd, ".batc-inputs")
            try:
                try:
                    marker = read_json(inputs, ".owner")
                except FileNotFoundError:
                    if os.listdir(inputs):
                        raise Refusal("BINDING_MISMATCH", "unknown input directory") from None
                    json_file(inputs, ".owner", {"operation_id": operation, "helper_version": VERSION})
                    marker = read_json(inputs, ".owner")
                if marker != {"operation_id": operation, "helper_version": VERSION}:
                    raise Refusal("BINDING_MISMATCH", "inputs belong to another operation")
                folder = child(inputs, ref["artifact_id"] + "-r" + str(ref["revision"]))
                attempts = child(inputs, ".attempts")
                try:
                    attempt_fd = child(attempts, ref["artifact_id"] + "-r" + str(ref["revision"]))
                finally:
                    os.close(attempts)
            finally:
                os.close(inputs)
        else:
            inputs = os.open(".batc-inputs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=work_fd)
            try:
                if read_json(inputs, ".owner") != {"operation_id": operation, "helper_version": VERSION}:
                    raise Refusal("BINDING_MISMATCH", "input owner differs")
                folder = os.open(ref["artifact_id"] + "-r" + str(ref["revision"]), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=inputs)
                attempts = os.open(".attempts", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=inputs)
                try:
                    attempt_fd = os.open(ref["artifact_id"] + "-r" + str(ref["revision"]), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=attempts)
                finally:
                    os.close(attempts)
            finally:
                os.close(inputs)
        relative = ".batc-inputs/" + ref["artifact_id"] + "-r" + str(ref["revision"]) + "/" + name
        base = {"path": worktree + "/" + relative, "relative_path": relative, "ref": ref,
                "operation_id": operation, "observed_at": time.time()}
        partial, closed = ".attempt-" + str(attempt), ".closed-" + str(attempt)
        try:
            if request["mode"] in {"receive", "inspect"}:
                # Recover a crash between link and unlink only with an exact inode binding.
                try:
                    src = os.stat(partial, dir_fd=attempt_fd, follow_symlinks=False)
                    dst = os.stat(name, dir_fd=folder, follow_symlinks=False)
                    if stat.S_ISREG(src.st_mode) and (src.st_dev, src.st_ino) == (dst.st_dev, dst.st_ino):
                        os.unlink(partial, dir_fd=attempt_fd)
                        os.fsync(attempt_fd)
                except FileNotFoundError:
                    pass
            try:
                size, digest = hash_file(folder, name)
                return dict(base, ok=True, size_bytes=size, digest=digest, final=True)
            except FileNotFoundError:
                if request["mode"] == "verify":
                    return dict(base, ok=False, code="ARTIFACT_CONTENT_UNAVAILABLE")
            if request["mode"] == "inspect":
                try:
                    receipt = read_json(attempt_fd, closed)
                except FileNotFoundError:
                    return dict(base, ok=False, uncertain=True)
                return dict(base, **receipt)
            if request["mode"] != "receive":
                raise Refusal("INVALID_PARAMS", "unknown helper method")
            expected = request["size_bytes"]
            if type(expected) is not int or expected < 0 or shutil.disk_usage(worktree).free < expected + 4096:
                raise Refusal("MATERIALIZATION_STORE_FULL", "not enough free space")
            try:
                handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=attempt_fd)
            except FileExistsError:
                return dict(base, ok=False, uncertain=True)
            digest, size = hashlib.sha256(), 0
            with os.fdopen(handle, "wb") as file:
                while size <= expected:
                    chunk = stream.read(min(65536, expected - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    digest.update(chunk)
                    file.write(chunk)
                file.flush()
                os.fsync(file.fileno())
            result = {"size_bytes": size, "digest": digest.hexdigest(), "closed": True}
            if size != expected:
                result.update(ok=False, code="ARTIFACT_SIZE_MISMATCH")
            elif digest.hexdigest() != ref["digest"]:
                result.update(ok=False, code="ARTIFACT_DIGEST_MISMATCH")
            else:
                try:
                    os.link(partial, name, src_dir_fd=attempt_fd, dst_dir_fd=folder, follow_symlinks=False)
                    os.unlink(partial, dir_fd=attempt_fd)
                    os.fsync(attempt_fd)
                    os.fsync(folder)
                    result.update(ok=True, final=True)
                except FileExistsError:
                    result.update(ok=False, code="BINDING_MISMATCH")
            json_file(attempt_fd, closed, result)
            return dict(base, **result)
        finally:
            os.close(folder)
            os.close(attempt_fd)
    finally:
        os.close(work_fd)
        os.close(clone_fd)


def main():
    try:
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536:
            raise Refusal("INVALID_PARAMS", "oversized helper metadata")
        result = execute(json.loads(line), sys.stdin.buffer)
    except Refusal as exc:
        result = {"ok": False, "code": exc.code, "message": exc.message[:200]}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = {"ok": False, "code": "DESTINATION_UNKNOWN", "message": type(exc).__name__}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
