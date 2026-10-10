"""Direct contract checks for durable, authoritative failover context."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from bat_agent_connector import task_handoff
from bat_agent_connector.task_core import initial_prompt, reviewer_prompt
from bat_agent_connector.task_journal import Journal


def test_generic_prompts_preserve_names_and_whitespace_in_original_words(tmp_path):
    words = "  Ted asked Alex: keep both names and `code`.\n原話：不要改寫。\t\n"
    journal = Journal(tmp_path / "tasks.db")
    try:
        task = journal.submit(project="p", host="h1", workspace="w", original_words=words,
                              idempotency_key="verbatim-user-request")
        prompts = [initial_prompt(task), reviewer_prompt(task, "a" * 40, "b" * 40),
                   task_handoff.ledger_summary(journal, task["task_id"])]
        for prompt in prompts:
            assert prompt.count(words) == 1
            instructions = prompt.replace(words, "")
            assert "user's" in instructions
            assert "Ted" not in instructions and "Alex" not in instructions
        journal.change(task["task_id"], "needs_ted", fields={"result": "Ask Ted and Alex to choose."})
        event = journal.milestones(0, 50)["events"][-1]
        assert event["kind"] == "needs_ted"  # Existing storage/API state remains compatible.
        assert event["summary"] == "Needs user input: Ask Ted and Alex to choose."
    finally:
        journal.close()


def test_original_words_archive_permissions_content_hash_and_collision(tmp_path, monkeypatch):
    private = tmp_path / "handoff"
    private.mkdir(mode=0o755)
    private.chmod(0o755)
    words = "Ted 原話：不要改寫。\n" + "字" * 4200 + "\nEND"
    data = words.encode("utf-8")
    real_fsync = os.fsync
    sync_modes = []

    def recorded_fsync(fd):
        sync_modes.append(os.fstat(fd).st_mode)
        real_fsync(fd)

    monkeypatch.setattr(task_handoff.os, "fsync", recorded_fsync)
    monkeypatch.setattr(task_handoff.uuid, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    archived = task_handoff.original_words_archive(words, private, "task-123")
    path = Path(archived["path"])
    assert path.read_bytes() == data
    assert archived == {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
                        "characters": len(words)}
    assert private.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(sync_modes) == 2
    assert stat.S_ISREG(sync_modes[0]) and stat.S_ISDIR(sync_modes[1])

    # An unlucky UUID collision must fail closed and leave the first archive intact.
    with pytest.raises(FileExistsError):
        task_handoff.original_words_archive("replacement", private, "task-123")
    assert path.read_bytes() == data
    assert len(list(private.iterdir())) == 1


def test_ledger_summary_keeps_full_scope_or_requires_archive(tmp_path):
    journal = Journal(tmp_path / "tasks.db")
    words = "完整原話：" + "字" * 4100 + "結尾"
    task = journal.submit(project="p", host="h1", workspace="w", original_words=words,
                          idempotency_key="ledger-bound")
    try:
        with pytest.raises(ValueError, match="verified archive"):
            task_handoff.ledger_summary(journal, task["task_id"])

        archive = task_handoff.original_words_archive(words, tmp_path / "private", task["task_id"])
        # Force the recent-events section over the prompt budget. The bounded
        # fallback must retain the archive pointer and authoritative scope.
        for index in range(8):
            journal.change(task["task_id"], "queued", event=f"event-{index}-" + "x" * 600)
        summary = task_handoff.ledger_summary(journal, task["task_id"],
                                               original_archive=archive)
        assert len(summary) <= 3900
        assert task["task_id"] in summary
        assert archive["path"] in summary
        assert archive["sha256"] in summary
        assert f"Characters: {len(words)}" in summary
        assert "Read it before planning" in summary
        assert words not in summary
        assert "Recent events:" not in summary
        assert Path(archive["path"]).read_text() == words
    finally:
        journal.close()
