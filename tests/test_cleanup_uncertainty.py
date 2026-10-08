"""E01/plan §23: a host refusal cannot erase a partially applied cleanup phase."""
from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path

import pytest

from bat_agent_connector import cleanup
from bat_agent_connector.errors import ResourceReadOnly
from tests.test_cleanup import (  # noqa: F401 - shared real Git/MockBat fixtures
    CLEANER,
    DISCARDER,
    LocalRunner,
    apply,
    git,
    known_live_terminals,
    setup_work,
)
from tests.test_cleanup import (
    daemon as checkpoint_daemon,
)
from tests.test_cleanup import (
    human as checkpoint_human,
)

daemon = checkpoint_daemon
human = checkpoint_human


@pytest.fixture(autouse=True)
async def close_clients(daemon):
    yield
    await daemon.inventory.fleet.close()
    await daemon.fleet.close()


class FaultRunner(LocalRunner):
    """Faults run only in the transported host script, never in pytest's stdlib or real hosts."""
    def __init__(self, original, phase, fault, path):
        super().__init__()
        self.original, self.phase, self.fault, self.path = original, phase, fault, path
        self.reply = None

    async def run(self, host, script, timeout_s=None):
        argv = shlex.split(script)
        req = json.loads(base64.b64decode(argv[-1]))
        if req.get("phase") == self.phase and req.get("path") == self.path and self.reply is None:
            source = argv[2]
            if self.fault == "second_unlink":
                injection = '''
original_unlink = exact_unlink
def exact_unlink(base, names, facts):
    original_unlink(base, names[:1], facts)
    raise ValueError("PREVIEW_STALE: injected second unlink failure")
'''
            elif self.fault == "rmdir":
                source = source.replace('            os.rmdir(wt)',
                                        '            raise OSError("injected root rmdir failure")')
                # The production mutation wrapper keeps the exact call inside its lambda/argv.
                source = source.replace('changing("rmdir", wt, os.rmdir, wt)',
                                        'changing("rmdir", wt, fail_rmdir, wt)')
                injection = 'def fail_rmdir(*args):\n    raise OSError("injected root rmdir failure")\n'
            elif self.fault == "before_mutation":
                injection = 'def mutate(req):\n    raise ValueError("PREVIEW_STALE")\n'
            elif self.fault == "pin_read":
                injection = '''
original_git = git
def git(repo, *args, **kwargs):
    if args[0] == "rev-parse" and args[-1].endswith("^{tree}"):
        raise ValueError("GIT_FAILED: injected read after pin creation")
    return original_git(repo, *args, **kwargs)
'''
            else:
                injection = '''
original_git = git
def git(repo, *args, **kwargs):
    if args[0] == "restore":
        raise ValueError("GIT_FAILED: injected restore failure")
    return original_git(repo, *args, **kwargs)
'''
            source = source.replace('if __name__ == "__main__":', injection + '\nif __name__ == "__main__":')
            script = "python3 -c " + shlex.quote(source) + " " + shlex.quote(argv[-1])
            out = await self.original.run(host, script, timeout_s)
            self.reply = json.loads(out)
            return out
        return await self.original.run(host, script, timeout_s)


async def exact_temporary(d, mock):
    cp, op = await setup_work(d, mock)
    clone = Path(op["external_refs"]["clone_path"])
    temp = Path(str(clone) + ".batc-tmp-" + op["operation_id"][3:15])
    git(clone.parent, "clone", "-q", "--no-checkout", "--no-hardlinks", str(clone), str(temp))
    git(temp, "config", "batc.managed-clone", "true")
    git(temp, "config", "batc.source", cp["repo_root"])
    doc = await cleanup.preview(d.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    item = next(i for i in doc["items"] if i["kind"] == "temporary" and i["path"] == str(temp))
    assert item["decision"] == "reclaim"
    return doc, item


def assert_reserved(d, done, item, phase):
    row = next(r for r in cleanup.receipts(d.ops, done["operation_id"]) if r["resource_id"] == item["resource_id"])
    assert row["status"] == "uncertain", row
    step = next(s for s in done["steps"] if s["name"].startswith("item." + item["resource_id"] + "." + phase))
    assert step["status"] == "uncertain", step
    with pytest.raises(ResourceReadOnly, match="CLEANUP_IN_PROGRESS"):
        cleanup.guard(item["host"], session_id=item.get("session_id"), path=item["path"])
    return row


async def read_back(d, operation_id):
    d.journal.db.execute("UPDATE operations SET next_run_at=0 WHERE operation_id=?", (operation_id,))
    await d.ops.drain(timeout=60)
    return d.ops.get(operation_id)


@pytest.mark.parametrize("fault", ["second_unlink", "rmdir"])
async def test_e01_temporary_post_mutation_failure_keeps_guard_and_reconciles(daemon, mock, fault):
    doc, item = await exact_temporary(daemon, mock)
    runner = FaultRunner(daemon.ops.context["git_runner"], "remove.temporary", fault, item["path"])
    daemon.ops.context["git_runner"] = runner
    done = await apply(daemon, doc)
    assert done["status"] == "uncertain", done
    assert runner.reply["mutated"] is True
    assert_reserved(daemon, done, item, "remove.temporary")
    # The retained pins remain readable even if the temporary's Git metadata is partly gone.
    for commit in set(item["observation"]["refs"].values()) | {item["observation"]["head"]}:
        assert git(item["repository"], "rev-parse", "refs/batc/retained/" + item["resource_id"] + "/" + commit) == commit
    settled = await read_back(daemon, done["operation_id"])
    assert settled["status"] == "succeeded", settled
    assert not Path(item["path"]).exists()


async def test_e01_discard_restore_failure_after_unlink_reports_partial_evidence(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    path = Path(op["result"]["worktree_path"])
    (path / "extra.txt").write_text("reviewed discard")
    (path / "notes.txt").write_text("uncommitted tracked content")
    target = {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]}
    doc = await cleanup.preview(daemon.ops, DISCARDER, target)
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    doc = await cleanup.preview(daemon.ops, DISCARDER, target, {"discard_uncommitted": [item["resource_id"]]})
    runner = FaultRunner(daemon.ops.context["git_runner"], "discard", "restore", item["path"])
    daemon.ops.context["git_runner"] = runner
    done = await apply(daemon, doc, DISCARDER)
    assert done["status"] == "uncertain", done
    assert runner.reply["mutated"] is True
    assert_reserved(daemon, done, item, "discard")
    assert not (path / "extra.txt").exists() and (path / "notes.txt").read_text() == "uncommitted tracked content"
    settled = await read_back(daemon, done["operation_id"])
    assert settled["status"] == "needs_attention" and settled["error_code"] == "CLEANUP_PARTIAL_STATE", settled
    row = assert_reserved(daemon, settled, item, "discard")
    evidence = row["after_state"]
    assert "extra.txt" in evidence["removed"]
    assert "notes.txt" in {f["path"] for f in evidence["remaining"]}
    assert evidence["phase"] == "discard"
    assert path.exists()


async def test_e01_refusal_before_host_mutation_stays_definitive(daemon, mock):
    cp, op = await setup_work(daemon, mock)
    # No stop in this cleanup: only the new host refusal is under test.
    mock.metas[op["result"]["session_id"]] = None
    doc = await cleanup.preview(daemon.ops, CLEANER, {"kind": "checkpoint", "checkpoint_id": cp["checkpoint_id"]})
    item = next(i for i in doc["items"] if i["kind"] == "worktree")
    runner = FaultRunner(daemon.ops.context["git_runner"], "preserve", "before_mutation", item["path"])
    daemon.ops.context["git_runner"] = runner
    done = await apply(daemon, doc)
    assert done["status"] == "needs_attention"
    assert runner.reply == {"error": "PREVIEW_STALE"}
    row = next(r for r in cleanup.receipts(daemon.ops, done["operation_id"]) if r["resource_id"] == item["resource_id"])
    assert row["status"] == "blocked_stale" and row["error"]["code"] == "PREVIEW_STALE"
    step = next(s for s in done["steps"] if s["name"].startswith("item." + item["resource_id"] + ".preserve"))
    assert step["status"] == "failed" and step["error"]["code"] == "PREVIEW_STALE"
    cleanup.guard(item["host"], path=item["path"])
    assert Path(item["path"]).exists()
    assert not git(item["repository"], "for-each-ref", "refs/batc/retained/" + item["resource_id"])


async def test_e01_preserve_failure_after_a_pin_completes_missing_pins(daemon, mock):
    doc, item = await exact_temporary(daemon, mock)
    # The temporary has two result revisions, both already available in the carrier.
    git(item["path"], "update-ref", "refs/heads/other", git(item["repository"], "rev-parse", "HEAD~1"))
    doc = await cleanup.preview(daemon.ops, CLEANER, doc["target"])
    item = next(i for i in doc["items"] if i["resource_id"] == item["resource_id"])
    runner = FaultRunner(daemon.ops.context["git_runner"], "preserve", "pin_read", item["path"])
    daemon.ops.context["git_runner"] = runner
    done = await apply(daemon, doc)
    assert done["status"] == "uncertain", done
    row = assert_reserved(daemon, done, item, "preserve")
    assert row["error"]["mutated"] and any(e["action"] == "update-ref" and e["completed"] for e in row["error"]["effects"])
    assert len(git(item["repository"], "for-each-ref", "refs/batc/retained/" + item["resource_id"]).splitlines()) == 1
    settled = await read_back(daemon, done["operation_id"])
    assert settled["status"] == "succeeded", settled
    for commit in set(item["observation"]["refs"].values()):
        assert git(item["repository"], "rev-parse", "refs/batc/retained/" + item["resource_id"] + "/" + commit) == commit


@pytest.mark.parametrize("change", ["content", "retained_ref"])
async def test_e01_partial_temporary_unreviewed_changes_or_missing_pins_need_attention(daemon, mock, change):
    doc, item = await exact_temporary(daemon, mock)
    runner = FaultRunner(daemon.ops.context["git_runner"], "remove.temporary", "second_unlink", item["path"])
    daemon.ops.context["git_runner"] = runner
    done = await apply(daemon, doc)
    assert_reserved(daemon, done, item, "remove.temporary")
    path = Path(item["path"])
    if change == "content":
        # A crash can leave the durable phase started rather than uncertain; partial read-back fixes it too.
        daemon.journal.db.execute("UPDATE operation_steps SET status='started' WHERE operation_id=? AND name=?",
            (done["operation_id"], "item." + item["resource_id"] + ".remove.temporary.a1"))
        config = path / ".git/config"
        config.write_text(config.read_text() + "\n# unexpected content change\n")
        (path / "new.txt").write_text("not in the reviewed manifest")
    else:
        git(item["repository"], "update-ref", "-d", "refs/batc/retained/" + item["resource_id"] + "/" + item["observation"]["head"])
    before = {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    settled = await read_back(daemon, done["operation_id"])
    assert settled["status"] == "needs_attention" and settled["error_code"] == "CLEANUP_PARTIAL_STATE", settled
    row = assert_reserved(daemon, settled, item, "remove.temporary")
    evidence = row["after_state"]
    assert evidence["removed"] and evidence["remaining"]
    if change == "content":
        assert ".git/config" in {f["path"] for f in evidence["changed"]}
        assert "new.txt" in {f["path"] for f in evidence["added"]}
    else:
        assert any(not r["available"] for r in evidence["retained_refs"])
    assert {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()} == before
