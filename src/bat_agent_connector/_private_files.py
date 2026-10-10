"""Validate private regular files before accessing their contents."""

import os
import stat
from pathlib import Path


def _validate(info, max_bytes):
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("private file must be a regular file")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("private file must be owned by the current user")
    if os.name != "nt" and info.st_mode & 0o077:
        raise ValueError("private file permissions must exclude group and other access")
    if max_bytes is not None and info.st_size > max_bytes:
        raise ValueError("private file exceeds size limit")


def open_private(path: Path, flags: int, *, max_bytes: int | None = None) -> int:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if not flags & os.O_CREAT:
            raise
        before = None
    if before is not None:
        if stat.S_ISLNK(before.st_mode):
            raise ValueError("private file must not be a symlink")
        _validate(before, max_bytes)
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), 0o600)
    try:
        opened = os.fstat(fd)
        current = path.lstat()
        if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("private file changed while opening")
        _validate(opened, max_bytes)
        if before is not None and (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("private file changed while opening")
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_private(path: Path, max_bytes: int) -> str:
    fd = open_private(path, os.O_RDONLY, max_bytes=max_bytes)
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("private file exceeds size limit")
    return data.decode("utf-8")


def mkdir_private(path: Path) -> None:
    if not path.exists():
        mkdir_private(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
