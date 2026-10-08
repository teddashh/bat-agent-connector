"""Host-side cleanup script, transported through SshGitRunner; no connector installation needed on the host.

Only stdlib and Git. Reads never create locks. Mutations lock the existing repository directory inode, verify
canonical bindings again, and operate on exact reviewed names. There is no directory discovery or prune fallback.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import select
import stat
import subprocess
import sys
import time

DEADLINE = float("inf")
MUTATED = False
EFFECTS = []


def changing(action, target, fn, *args, **kwargs):
    """Once a mutating call starts, even its error may hide partial effects."""
    global MUTATED
    MUTATED = True
    effect = {"action": action, "target": target, "completed": False}
    EFFECTS.append(effect)
    result = fn(*args, **kwargs)
    effect["completed"] = True
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def git(repo, *args, optional=False):
    if time.monotonic() >= DEADLINE:
        raise ValueError("OBSERVATION_UNAVAILABLE")
    if os.path.isdir(os.path.join(repo, "repo.git")):
        repo = os.path.join(repo, "repo.git")
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_"):
            del env[k]
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
               GIT_TERMINAL_PROMPT="0")
    p = subprocess.run(  # noqa: S603, S607 - fixed commands, argv only
        ["git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null", "-c",  # noqa: S607 - host Git executable
                        "core.fsmonitor=false", "-c", "gc.auto=0", "-C", repo, *args], env=env,
                       capture_output=True, timeout=max(.01, min(30, DEADLINE - time.monotonic())))  # noqa: S603, S607 - fixed Git commands, argv only
    if p.returncode and not optional:
        raise ValueError("GIT_FAILED: " + p.stderr.decode(errors="replace")[-300:])
    return p.stdout.decode(errors="surrogateescape") if not p.returncode else None


def canonical(path, roots):
    if not isinstance(path, str) or not path.startswith("/") or ".." in path.split("/"):
        raise ValueError("BINDING_MISMATCH")
    real = os.path.realpath(path)
    if real != path or not any(real.startswith(r.rstrip("/") + "/") and os.path.realpath(r) == r for r in roots):
        raise ValueError("WORKDIR_NOT_MANAGED")
    return real


def file_fact(path, relative, *, dir_fd=None):
    s = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    if stat.S_ISLNK(s.st_mode):
        return {"path": relative, "type": "link", "digest": digest(os.readlink(path, dir_fd=dir_fd)), "bytes": s.st_size}
    if stat.S_ISDIR(s.st_mode):
        return {"path": relative, "type": "directory", "mode": stat.S_IMODE(s.st_mode)}
    if not stat.S_ISREG(s.st_mode):
        raise ValueError("DISCARD_MANIFEST_UNAVAILABLE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    h = hashlib.sha256()
    with os.fdopen(fd, "rb") as f:
        if os.fstat(f.fileno()) != s:
            raise ValueError("PREVIEW_STALE")
        for b in iter(lambda: f.read(131072), b""):
            if time.monotonic() >= DEADLINE:
                raise ValueError("OBSERVATION_UNAVAILABLE")
            h.update(b)
    return {"path": relative, "type": "file" if s.st_nlink == 1 else "hardlink", "digest": h.hexdigest(),
            "bytes": s.st_size, "mode": stat.S_IMODE(s.st_mode)}


def walk_error(error):
    raise error


def manifest(path, *, include_git=False):
    # A complete exact file manifest also detects ignored files and same-status content edits.
    out = []
    for parent, dirs, files in os.walk(path, followlinks=False, onerror=walk_error):
        if time.monotonic() >= DEADLINE:
            raise ValueError("OBSERVATION_UNAVAILABLE")
        dirs[:] = sorted(d for d in dirs if include_git or d != ".git")
        relative = os.path.relpath(parent, path)
        if not include_git and input_path(relative):
            out.append(file_fact(parent, relative))
            if len(out) > 10000:
                raise ValueError("DISCARD_MANIFEST_UNAVAILABLE: too many files")
        for d in list(dirs):
            if os.path.islink(os.path.join(parent, d)):
                files.append(d)
                dirs.remove(d)
        if not include_git and parent != path and ".git" in files:
            raise ValueError("RESOURCE_KIND_UNSUPPORTED: nested repository")
        for name in sorted(files):
            if not include_git and parent == path and name == ".git":
                continue
            p = os.path.join(parent, name)
            out.append(file_fact(p, os.path.relpath(p, path)))
            if len(out) > 10000:
                raise ValueError("DISCARD_MANIFEST_UNAVAILABLE: too many files")
    return out


def input_path(path):
    return path == ".batc-inputs" or path.startswith(".batc-inputs/")


def replica_content(facts, evidence, tracked, acknowledged):
    """Exempt only exact verified replicas and supplied helper names, never an entire directory."""
    expected = {}
    books = set(evidence.get("bookkeeping_names", []))
    for entry in evidence.get("replica_manifest", []):
        path = entry["path"]
        if (not path.startswith(".batc-inputs/") or any(p in {"", ".", ".."} for p in path.split("/")) or
                not isinstance(entry["bytes"], int) or entry["bytes"] < 0 or
                not re.fullmatch(r"[0-9a-f]{64}", entry["digest"]) or path in expected):
            raise ValueError("DISCARD_MANIFEST_UNAVAILABLE")
        expected[path] = entry
    if set(expected) & books or any(not re.fullmatch(r"\.batc-inputs/(?:\.owner|\.attempts/[^/]+-r[0-9]+/\.(?:attempt|closed)-[0-9]+)", p)
           or any(c in {"", ".", ".."} for c in p.split("/")) for p in books):
        raise ValueError("DISCARD_MANIFEST_UNAVAILABLE")
    parents = set()
    for path in set(expected) | books | {p for p in tracked if input_path(p)}:
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            parents.add(path)
    ordinary, replicas, bookkeeping = [], [], []
    seen = {f["path"] for f in facts}
    for fact in facts:
        path = fact["path"]
        entry = expected.get(path)
        if fact["type"] == "file" and path not in tracked:
            if entry and all(fact[k] == entry[k] for k in ("bytes", "digest")):
                replicas.append(fact)
                continue
            if path in books:
                bookkeeping.append(fact)
                continue
        if fact["type"] == "directory" and path in parents:
            continue
        ordinary.append(fact)
    missing = sorted(set(expected) - seen)
    ordinary += [{"path": p, "type": "missing", "expected": expected[p]} for p in missing if p not in acknowledged]
    return ordinary, replicas, bookkeeping, missing


def identity(repo, roots):
    canonical(repo, roots)
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    canonical(common, roots)
    for parent, dirs, files in os.walk(common, followlinks=False, onerror=walk_error):
        if time.monotonic() >= DEADLINE:
            raise ValueError("OBSERVATION_UNAVAILABLE")
        if any(os.path.islink(os.path.join(parent, n)) for n in dirs + files) or any(
                os.stat(os.path.join(parent, n)).st_nlink > 1 for n in files):
            raise ValueError("CLONE_CONFIG_TAMPERED")
    for name in ("objects", "refs", "config"):
        canonical(os.path.join(common, name), roots)
    if git(repo, "config", "--get", "batc.managed-clone", optional=True) != "true\n":
        raise ValueError("CLONE_NOT_OURS")
    if (os.path.lexists(os.path.join(common, "objects/info/alternates")) or
            os.path.lexists(os.path.join(common, "info/grafts")) or
            os.path.lexists(os.path.join(common, "shallow")) or
            git(repo, "for-each-ref", "refs/replace/")):
        raise ValueError("CLONE_CONFIG_TAMPERED")
    cfg = git(repo, "config", "--local", "--list").splitlines()
    allowed = ("core.repositoryformatversion=", "core.filemode=", "core.bare=", "core.logallrefupdates=",
               "core.ignorecase=", "core.precomposeunicode=", "core.worktree=", "remote.origin.url=", "remote.origin.fetch=",
               "branch.", "batc.", "user.name=", "user.email=")
    if any(not c.startswith(allowed) for c in cfg):
        raise ValueError("CLONE_CONFIG_TAMPERED")
    markers = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in cfg if line.startswith("batc.")}
    return {"common_dir": common, "markers": markers, "config_digest": digest(cfg)}


def registrations(repo):
    out = []
    for block in git(repo, "worktree", "list", "--porcelain").strip().split("\n\n"):
        d = dict(line.split(" ", 1) if " " in line else (line, True) for line in block.splitlines())
        if d.get("worktree"):
            out.append(d)
    return out


def observe(req):
    repo, roots = req["repository"], req["roots"]
    result = {"repository": repo, "exists": os.path.isdir(repo), "worktrees": {}, "refs": {}, "temporaries": {}}
    if not result["exists"]:
        return result
    result.update(identity(repo, roots))
    regs = registrations(repo)
    if len(regs) > 500:
        raise ValueError("PREVIEW_TOO_LARGE")
    result["registrations"] = regs
    result["refs"] = dict(line.split(" ", 1) for line in
                          git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines())
    if len(result["refs"]) > 2000:
        raise ValueError("PREVIEW_TOO_LARGE")
    requested = set(req.get("worktrees", []))
    if not req.get("paths_only"):
        requested |= {r["worktree"] for r in regs}
    for wt in sorted(requested):
        d = {"path": wt, "exists": os.path.isdir(wt), "registration": next(
            (r for r in regs if r["worktree"] == wt), None)}
        result["worktrees"][wt] = d
        if not d["exists"]:
            continue
        try:
            canonical(wt, roots)
            common = git(wt, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
            if common != result["common_dir"]:
                raise ValueError("BINDING_MISMATCH")
            d["head"] = git(wt, "rev-parse", "HEAD").strip()
            d["branch"] = git(wt, "symbolic-ref", "--short", "HEAD", optional=True)
            d["branch"] = (d["branch"] or "").strip()
            d["status"] = git(wt, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                              "--ignored=matching")
            d["diff"] = digest([git(wt, "diff", "--binary"), git(wt, "diff", "--cached", "--binary")])
            tracked = set(git(wt, "ls-files", "-z").split("\0"))
            evidence = req.get("replicas", {}).get(wt, {})
            acknowledged = req.get("acknowledged_missing_replicas", {}).get(wt, [])
            d["manifest"], d["exempted_replicas"], d["exempted_bookkeeping"], d["missing_replicas"] = replica_content(
                manifest(wt), evidence, tracked, acknowledged)
            exempted = {f["path"] for f in d["exempted_replicas"] + d["exempted_bookkeeping"]}
            # Git collapses ignored directories. Replace those entries with exact ordinary content, including
            # missing expected replicas and unexpected empty directories which Git cannot report.
            d["status"] = "".join(x + "\0" for x in d["status"].split("\0") if x and not (
                x[:3] in {"!! ", "?? "} and input_path(x[3:].rstrip("/"))))
            d["status"] += "".join("!! " + f["path"] + "\0" for f in d["manifest"]
                                  if input_path(f["path"]) and f["path"] not in tracked)
            d["manifest_digest"] = digest(d["manifest"])
            d["extras"] = sorted(set(git(wt, "ls-files", "--others", "--exclude-standard", "-z").split("\0") +
                                     git(wt, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").split("\0")) - {""})
            d["extras"] = sorted((set(d["extras"]) - exempted) | {
                f["path"] for f in d["manifest"] if input_path(f["path"]) and f["type"] != "missing" and f["path"] not in tracked})
            gd = git(wt, "rev-parse", "--absolute-git-dir").strip()
            canonical(gd, roots)
            d["complex_state"] = any(os.path.lexists(os.path.join(gd, x)) for x in
                                     ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply", "BISECT_LOG"))
            base = req.get("bases", {}).get(wt)
            d["results"] = (git(wt, "rev-list", base + ".." + d["head"], optional=True) if base else None)
            d["results"] = d["results"].splitlines() if d["results"] is not None else None
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            d["error"] = str(e).split(":", 1)[0]
    result["branches"] = {}
    for br, base in req.get("branches", {}).items():
        sha = result["refs"].get("refs/heads/" + br)
        commits = git(repo, "rev-list", base + ".." + sha, optional=True) if sha and base else None
        result["branches"][br] = {"head": sha, "results": commits.splitlines() if commits is not None else None}
    for temp in req.get("temporaries", []):
        d = {}
        try:
            canonical(temp, roots)
            d = {"exists": os.path.lexists(temp)}
            result["temporaries"][temp] = d
            if not d["exists"]:
                continue
            if not os.path.isdir(temp):
                d.update(layout="file", manifest=[file_fact(temp, os.path.basename(temp))], git_only=False,
                         content_available=False, head=None)
                continue
            # A partially removed Git directory may no longer pass identity(). Its exact remaining files
            # still provide read-back evidence; canonical/no-follow checks precede this read.
            d["manifest"] = manifest(temp, include_git=True)
            d["manifest_digest"] = digest(d["manifest"])
            d["directories"] = sorted(os.path.relpath(parent, temp) for parent, dirs, files in os.walk(temp, followlinks=False, onerror=walk_error))
            d["manifest_complete"] = True
            d["identity"] = identity(temp, roots)
            d["layout"] = "bare" if git(temp, "rev-parse", "--is-bare-repository").strip() == "true" else "clone"
            head = git(temp, "rev-parse", "--verify", "HEAD", optional=True)
            d["head"] = head.strip() if head else None
            d["refs"] = dict(line.split(" ", 1) for line in git(temp, "for-each-ref", "--format=%(refname) %(objectname)").splitlines())
            if d["head"] is None and d["refs"]:
                d["head"] = sorted(d["refs"].values())[0]
            d["content_available"] = all(git(repo, "cat-file", "-e", sha + "^{commit}", optional=True) is not None
                                         for sha in set(d["refs"].values()) | ({d["head"]} if d["head"] else set()))
            d["git_only"] = all(f["type"] == "file" and (
                f["path"].startswith(".git/") if d["layout"] == "clone" else
                f["path"] in {"HEAD", "config", "description", "packed-refs", "info/exclude"} or
                f["path"].startswith(("objects/", "refs/", "logs/"))) for f in d["manifest"])
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            result["temporaries"][temp] = {**d, "error": str(e).split(":", 1)[0]}
    return result


def retained(repo, ref, sha):
    return (git(repo, "rev-parse", "--verify", ref, optional=True) == sha + "\n" and
            git(repo, "cat-file", "-e", sha + "^{commit}", optional=True) is not None)


def exact_unlink(base, names, facts):
    by_path = {f["path"]: f for f in facts}
    # Resolve each parent with dirfds and O_NOFOLLOW. Do not follow a newly inserted directory link.
    # Keep the caller's file order (temporary config markers go last); remove directories deepest first.
    for name in sorted(names, key=lambda n: (by_path.get(n, {}).get("type") == "directory",
                                            -n.count("/") if by_path.get(n, {}).get("type") == "directory" else 0)):
        parts = name.split("/")
        if any(p in {"", ".", ".."} for p in parts):
            raise ValueError("BINDING_MISMATCH")
        fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            current = file_fact(parts[-1], name, dir_fd=fd)
            if current != by_path.get(name):
                raise ValueError("PREVIEW_STALE")
            if current["type"] == "directory":
                changing("rmdir", os.path.join(base, name), os.rmdir, parts[-1], dir_fd=fd)
            else:
                changing("unlink", os.path.join(base, name), os.unlink, parts[-1], dir_fd=fd)
        finally:
            os.close(fd)


def temporary_subset(original, current):
    """Only unchanged reviewed entries may remain after a partial exact temporary removal."""
    old = {f["path"]: f for f in original.get("manifest", [])}
    return (original.get("git_only") and original.get("content_available") and current.get("exists") and
            current.get("manifest_complete") and
            set(current.get("directories", [])) <= set(original.get("directories", [])) and
            all(f == old.get(f["path"]) for f in current["manifest"]))


def mutate(req):
    if not req.get("locked_check"):
        raise ValueError("CLEANUP_GATE_REQUIRED")
    repo = req["repository"]
    canonical(repo, req["roots"])
    fd = os.open(repo, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if req.get("locked_check"):
            if req["phase"] != "lock.session":
                checked = identity(repo, req["roots"])
                if checked != req["identity"]:
                    raise ValueError("PREVIEW_STALE")
            print(json.dumps({"locked": True}), flush=True)
            if not select.select([sys.stdin], [], [], max(0, DEADLINE - time.monotonic()))[0]:
                raise ValueError("OBSERVATION_UNAVAILABLE")
            permission = sys.stdin.readline()
            if not permission or json.loads(permission) != {"proceed": True}:
                return {"aborted": True}
        if req["phase"] == "lock.session":
            canonical(repo, req["roots"])
            return {"released": True}
        observed = observe(req)
        expected = req["identity"]
        if any(observed.get(k) != expected.get(k) for k in ("common_dir", "markers", "config_digest")):
            raise ValueError("PREVIEW_STALE")
        phase, ref, sha = req["phase"], req.get("retained_ref"), req.get("sha")
        wt = req.get("path")
        before = observed["worktrees"].get(wt) if wt else None
        if phase in {"preserve", "discard", "remove.worktree"} and req.get("kind") != "temporary":
            if before != req["before"]:
                raise ValueError("PREVIEW_STALE")
        if req.get("kind") == "temporary":
            before = observed["temporaries"].get(wt)
            if before != req["before"]:
                raise ValueError("PREVIEW_STALE")
        if phase == "preserve":
            if req.get("kind") == "local_branch" and observed["refs"].get("refs/heads/" + req["branch"]) != sha:
                raise ValueError("PREVIEW_STALE")
            if not ref.startswith("refs/batc/retained/"):
                raise ValueError("BINDING_MISMATCH")
            commits = set(before["refs"].values()) | ({sha} if sha else set()) if req.get("kind") == "temporary" else {sha}
            pins = []
            for commit in sorted(commits):
                pin = ref.rsplit("/", 1)[0] + "/" + commit
                current = observed["refs"].get(pin)
                if current and current != commit:
                    raise ValueError("RETAINED_REF_MISMATCH")
                if not current:
                    changing("update-ref", pin, git, repo, "update-ref", pin, commit, "0" * 40)
                if not retained(repo, pin, commit):
                    raise ValueError("RETAINED_CONTENT_MISSING")
                pins.append({"ref": pin, "sha": commit, "tree": git(repo, "rev-parse", commit + "^{tree}").strip()})
            return {"ref": ref, "sha": sha, "tree": git(repo, "rev-parse", sha + "^{tree}").strip(), "pins": pins}
        if sha and not retained(repo, ref, sha):
            raise ValueError("RETAINED_CONTENT_MISSING")
        if phase == "remove.temporary":
            original = req.get("recovery_before", before)
            if req.get("recovery_before") and not temporary_subset(original, before):
                raise ValueError("PREVIEW_STALE")
            if req.get("kind") != "temporary" or not original["content_available"]:
                raise ValueError("RETAINED_CONTENT_MISSING")
            if not original["git_only"]:
                raise ValueError("RESOURCE_KIND_UNSUPPORTED")
            for other in sorted(set(original["refs"].values()) | ({original["head"]} if original.get("head") else set())):
                if not ref or not retained(repo, ref.rsplit("/", 1)[0] + "/" + other, other):
                    raise ValueError("RETAINED_CONTENT_MISSING")
            names = sorted((f["path"] for f in before["manifest"]), key=lambda n: n in {".git/config", "config"})
            exact_unlink(wt, names, before["manifest"])
            for d in sorted((x for x in before["directories"] if x != "."), key=lambda x: x.count("/"), reverse=True):
                canonical(os.path.join(wt, d), req["roots"])
                changing("rmdir", os.path.join(wt, d), os.rmdir, os.path.join(wt, d))
            changing("rmdir", wt, os.rmdir, wt)
            return {"removed": True, "retained_commits": sorted(set(original["refs"].values()) | ({sha} if sha else set()))}
        if phase == "discard":
            if before["complex_state"] or any(f["type"] != "file" and not (
                    input_path(f["path"]) and f["type"] in {"link", "hardlink", "directory", "missing"})
                    for f in before["manifest"]):
                raise ValueError("DISCARD_MANIFEST_UNAVAILABLE")
            exact_unlink(wt, before["extras"], before["manifest"])
            changing("restore", wt, git, wt, "restore", "--source=" + sha, "--staged", "--worktree", "--", ".")
            removed_replicas = {e["path"] for e in req.get("replicas", {}).get(wt, {}).get("replica_manifest", [])
                                if e["path"] in before["extras"]}
            return {"discarded": True, "acknowledged_missing_replicas": sorted(set(before["missing_replicas"]) | removed_replicas)}
        if phase == "remove.worktree":
            if before["status"] or before["complex_state"] or before["head"] != sha:
                raise ValueError("PREVIEW_STALE")
            try:
                changing("worktree.remove", wt, git, repo, "worktree", "remove", wt)
            except ValueError as e:
                raise ValueError("WORKTREE_REMOVE_REFUSED") from e
            return {"removed": True}
        if phase == "remove.branch":
            branch = req["branch"]
            connector_branch = branch.startswith(("batc/cp-", "batc/fix-")) or (
                req.get("flavor") == "bat" and branch.startswith("bat/"))
            if not connector_branch or not req["delivered"]:
                raise ValueError("BINDING_MISMATCH")
            full = "refs/heads/" + branch
            if any(r.get("branch") == full for r in observed["registrations"]):
                raise ValueError("REF_CHANGED")
            if observed["refs"].get(full) != sha:
                raise ValueError("REF_CHANGED")
            changing("update-ref", full, git, repo, "update-ref", "-d", full, sha)
            return {"deleted": True, "ref": full, "sha": sha}
        raise ValueError("RESOURCE_KIND_UNSUPPORTED")
    finally:
        os.close(fd)


def main():
    global DEADLINE, MUTATED, EFFECTS
    MUTATED, EFFECTS = False, []
    req = json.loads(base64.b64decode(sys.argv[1]))
    DEADLINE = time.monotonic() + min(60, req.get("deadline_s", 20))
    try:
        if "canonical_paths" in req:
            out = {}
            for path in req["canonical_paths"]:
                try:
                    real = canonical(path, req["roots"])
                    if not os.path.isdir(real):
                        raise ValueError("OBSERVATION_UNAVAILABLE")
                    out[path] = {"canonical": real, "exists": True}
                except (ValueError, OSError) as e:
                    out[path] = {"error": str(e).split(":", 1)[0]}
        elif req.get("phase") == "verify.retained":
            identity(req["repository"], req["roots"])
            out = []
            for r in req["retained"]:
                available = retained(req["repository"], r["ref"], r["commit_sha"])
                out.append({**r, "available": available, "tree_sha": git(req["repository"], "rev-parse",
                    r["commit_sha"] + "^{tree}").strip() if available else r.get("tree_sha")})
        elif req.get("probe"):
            fd = os.open(req["repository"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                out = observe(req)
                out["process_ended"] = True
            finally:
                os.close(fd)
        else:
            out = mutate(req) if req.get("phase") else observe(req)
        print(json.dumps({"result": out}, ensure_ascii=True))
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print(json.dumps({"error": str(e).split(":", 1)[0],
                          **({"mutated": True, "effects": EFFECTS} if MUTATED else {})}))


if __name__ == "__main__":
    main()
