#!/usr/bin/env python3
"""Check tracked public content without printing potentially private values.

This is a publication guard, not a substitute for reviewing deployment narratives,
screenshots, Git history and issue/PR text. It does not read any live configuration.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

PRIVATE_CONFIG_NAMES = {"hosts.toml", "discord-channels.toml", ".env"}
SYNTHETIC_USERS = {
    "alice", "bob", "developer", "example", "fixture", "operator", "person", "runner",
    "runneradmin", "test", "user",
}
HOME_PATH = re.compile(
    r"(?<![A-Za-z0-9_])(?:/home/|/Users/|[A-Za-z]:/Users/)([A-Za-z][A-Za-z0-9_.-]*)",
    re.IGNORECASE,
)
SHARED_CHAT = re.compile(r"https?://(?:chatgpt\.com|chat\.openai\.com)/share/[A-Za-z0-9-]+")


def check_text(text: str) -> list[tuple[int, str]]:
    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if SHARED_CHAT.search(line):
            findings.append((line_number, "shared conversation link"))
        normalized = line.replace("\\\\", "\\").replace("\\", "/")
        if any(match[1].casefold() not in SYNTHETIC_USERS for match in HOME_PATH.finditer(normalized)):
            findings.append((line_number, "non-example home path"))
    return findings


def check_tree(root: Path) -> list[tuple[str, int, str]]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to inspect tracked public content")
    # Resolved executable and fixed arguments; root is only the working directory.
    tracked = subprocess.check_output([git, "ls-files", "-z"], cwd=root).decode().split("\0")  # noqa: S603
    findings = []
    for name in filter(None, tracked):
        path = Path(name)
        if path.name in PRIVATE_CONFIG_NAMES:
            findings.append((name, 1, "private configuration filename"))
        # Third-party source must retain its original provenance and checksum.
        if name.startswith("desktop/vendor/"):
            continue
        source = root / path
        if not source.is_file() or source.is_symlink():
            continue
        data = source.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend((name, line, category) for line, category in check_text(text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    findings = check_tree(args.root)
    for path, line, category in findings:
        print(f"{path}:{line}: {category}")
    if findings:
        print(f"Public content check failed: {len(findings)} finding(s); values withheld.")
        return 1
    print("Public content check passed for tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
