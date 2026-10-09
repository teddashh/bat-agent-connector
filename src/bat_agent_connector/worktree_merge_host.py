"""Fixed read-only Git proof over the existing verifier SSH runner. No caller commands."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time

LIMIT = 262144
DEADLINE = float('inf')


def git(path, *args, codes=(0,), config_context=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    argv = ['git', '--no-optional-locks']
    if not config_context:
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
        argv += ['-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0']
    # Files avoid unbounded communicate() allocations; no data is stored in either carrier.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [*argv, '-C', path, *args],
            env=env, stdout=out, stderr=err)  # noqa: S603, S607 - fixed argv, no shell
        try:
            while p.poll() is None:
                if time.monotonic() >= DEADLINE or os.fstat(out.fileno()).st_size > LIMIT or os.fstat(err.fileno()).st_size > LIMIT:
                    raise ValueError('MERGE_GIT_UNAVAILABLE')
                time.sleep(.01)
            # Git status can exit 0 with empty stdout after warning that an
            # untracked directory could not be read. Such a read is not clean proof.
            if p.returncode not in codes or os.fstat(out.fileno()).st_size > LIMIT or os.fstat(err.fileno()).st_size:
                raise ValueError('MERGE_GIT_UNAVAILABLE')
            out.seek(0)
            return p.returncode, out.read(LIMIT + 1).decode('utf-8', errors='strict')
        finally:
            if p.poll() is None:
                p.kill()
            p.wait()


def canonical(path, roots):
    if (not isinstance(path, str) or len(path) > 4096 or not path.startswith('/') or '\0' in path
            or '..' in path.split('/') or os.path.realpath(path) != path
            or not any(path == r or path.startswith(r.rstrip('/') + '/') for r in roots)):
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    return path


def identity(path, roots):
    canonical(path, roots)
    root = git(path, 'rev-parse', '--show-toplevel')[1].strip()
    common = git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')[1].strip()
    canonical(common, roots)
    if root != path:
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    branch = git(path, 'symbolic-ref', '--short', 'HEAD')[1].strip()
    head = git(path, 'rev-parse', '--verify', 'HEAD')[1].strip()
    if not branch or len(branch) > 256 or not re.fullmatch('[0-9a-f]{40,64}', head):
        raise ValueError('MERGE_GIT_UNAVAILABLE')
    s, c = os.stat(path), os.stat(common)
    return {'root': root, 'common_dir': common, 'head': head, 'branch': branch,
            'directory': [s.st_dev, s.st_ino], 'common_directory': [c.st_dev, c.st_ino]}


def no_context_programs(path):
    # The configured SSH mapping must represent BAT's account/config context.
    # This cannot attest another process's environment. Refuse overlays rather
    # than silently sanitizing away a config path, injected config or diff helper.
    allowed = {'GIT_OPTIONAL_LOCKS', 'GIT_TERMINAL_PROMPT'}
    if os.environ.get('GIT_PAGER') in {'', 'cat'}:
        allowed.add('GIT_PAGER')  # fixed literal passthrough; all proof output is piped
    if any(k.startswith('GIT_') and k not in allowed for k in os.environ):
        raise ValueError('MERGE_GIT_UNAVAILABLE')
    # config --includes reads effective system/global/repository/worktree config;
    # it executes none of the configured programs. Return names only, never values.
    _, configured = git(path, 'config', '--includes', '--name-only', '--get-regexp',
                        r'^(filter\..*\.(clean|process)|diff\.(external|.*\.(command|textconv))|core\.fsmonitor)$',
                        codes=(0, 1), config_context=True)
    if configured.strip():
        raise ValueError('MERGE_GIT_UNAVAILABLE')


def no_repository_programs(path):
    # Git status can execute clean/process filters while hashing same-size edits.
    # Refuse them before status rather than invoking repository-provided commands.
    _, configured = git(path, 'config', '--get-regexp', r'^filter\..*\.(clean|process)$', codes=(0, 1))
    if configured.strip():  # including empty/multiline definitions; never parse shell commands
        raise ValueError('MERGE_GIT_UNAVAILABLE')
    # Nested submodule status could run an independently configured filter.
    # This bounded contract does not recurse into arbitrary repository configs.
    entries = git(path, 'ls-files', '--stage', '-z')[1]
    if any(entry.startswith('160000 ') for entry in entries.split('\0')):
        raise ValueError('MERGE_GIT_UNAVAILABLE')


def observe(req):
    roots = req['roots']
    if not isinstance(roots, list) or not roots or len(roots) > 100:
        raise ValueError('MERGE_GIT_UNAVAILABLE')
    if any(not isinstance(r, str) or not r.startswith('/') or os.path.realpath(r) != r for r in roots):
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    paths = [req['source'], req['destination']]
    for p in paths:
        canonical(p, roots)
        no_context_programs(p)
    before = [identity(p, roots) for p in paths]
    if paths[0] == paths[1] or before[0]['common_dir'] != before[1]['common_dir'] or before[0]['branch'] == before[1]['branch']:
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    # BAT's native merge uses the main checkout recorded in its worktree state.
    # A workspace opened on another linked worktree is not that destination.
    registrations = git(paths[0], 'worktree', 'list', '--porcelain', '-z')[1]
    worktrees = [part[9:] for part in registrations.split('\0') if part.startswith('worktree ')]
    if (not worktrees or worktrees[0] != paths[1] or paths[0] not in worktrees
            or any(not any(p == r or p.startswith(r.rstrip('/') + '/') for r in paths) for p in worktrees)):
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    for p in paths:
        no_repository_programs(p)
    clean = [git(p, 'status', '--porcelain=v1', '-z', '--untracked-files=all')[1] == '' for p in paths]
    ahead = git(paths[0], 'merge-base', '--is-ancestor', before[1]['head'], before[0]['head'], codes=(0, 1))[0] == 0
    merged = git(paths[0], 'merge-base', '--is-ancestor', before[0]['head'], before[1]['head'], codes=(0, 1))[0] == 0
    if ([identity(p, roots) for p in paths] != before
            or git(paths[0], 'worktree', 'list', '--porcelain', '-z')[1] != registrations):
        raise ValueError('MERGE_GIT_BINDING_CHANGED')
    return {'version': 1, 'source': {**before[0], 'clean': clean[0]},
            'destination': {**before[1], 'clean': clean[1]}, 'registered_paths': worktrees,
            'kind': 'merged' if merged else 'ahead' if ahead else 'diverged'}


def main():
    global DEADLINE
    DEADLINE = time.monotonic() + 20
    try:
        if len(sys.argv) != 2 or len(sys.argv[1]) > 32768:
            raise ValueError('MERGE_GIT_UNAVAILABLE')
        req = json.loads(base64.b64decode(sys.argv[1], validate=True))
        result = observe(req)
        print(json.dumps({'ok': True, 'proof': result}, separators=(',', ':')))
    except Exception as exc:  # noqa: BLE001 - bounded fixed errors only, no paths/stderr/config leak
        code = str(exc) if isinstance(exc, ValueError) and str(exc) in {'MERGE_GIT_UNAVAILABLE', 'MERGE_GIT_BINDING_CHANGED'} else 'MERGE_GIT_UNAVAILABLE'
        print(json.dumps({'ok': False, 'code': code}))


if __name__ == '__main__':
    main()
