"""Deterministic job accounting/handle ordering; native exit proof runs on Windows CI."""

import ctypes as c
import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def native(monkeypatch):
    state = types.SimpleNamespace(total=2, active=2, members=[1, 2], owned={1001, 1002},
                                  signaled=set(), closed=[], terminated=0, complete=True)

    def query(_job, kind, pointer, _size, _returned):
        value = pointer._obj
        if kind == 1:
            value.total, value.active = state.total, state.active
        else:
            value.assigned, value.count = len(state.members), len(state.members)
            for index, pid in enumerate(state.members):
                value.ids[index] = pid
        return state.complete

    def membership(handle, _job, result):
        result._obj.value = handle in state.owned
        return True

    def terminate(_job, _code):
        state.terminated += 1
        state.active = 0
        return True

    def error(*_args):
        raise OSError("native query failed")

    callbacks = {"CreateJobObjectW": lambda *_: 100, "QueryInformationJobObject": query,
                 "OpenProcess": lambda _access, _inherit, pid: pid + 1000, "IsProcessInJob": membership,
                 "WaitForSingleObject": lambda handle, _timeout: 0 if handle in state.signaled else 258,
                 "TerminateJobObject": terminate}
    fake = types.ModuleType("bat_agent_connector.windows_files")
    fake.ULONG_PTR, fake.VOID = c.c_size_t, c.c_void_p
    fake._bind = lambda _library, name, _args, *_rest: callbacks.get(name, lambda *_: True)
    fake._close, fake._error, fake.kernel = state.closed.append, error, object()
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    spec = importlib.util.spec_from_file_location("bat_agent_connector._job_test",
        Path(__file__).parents[1] / "src/bat_agent_connector/windows_processes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, state


def test_zero_accounting_does_not_replace_pinned_process_exit_proof(native):
    module, state = native
    tree = module.ProcessTree()
    tree.terminate()
    assert state.active == 0 and state.terminated == 1
    assert tree.alive()  # Termination initiated, but both handles remain unsignaled.
    state.signaled.add(1001)
    assert tree.alive() and state.closed == [1001]
    state.signaled.add(1002)
    assert not tree.alive() and state.closed == [1001, 1002]
    tree.close()
    assert state.closed == [1001, 1002, 100]


def test_recycled_unrelated_pid_is_never_waited_or_terminated(native):
    module, state = native
    state.owned.remove(1002)
    tree = module.ProcessTree()
    tree.terminate()
    assert state.closed == [1002] and state.terminated == 1
    state.signaled.add(1001)
    assert not tree.alive()
    tree.close()


def test_new_member_during_termination_remains_unconfirmed(native):
    module, state = native
    tree = module.ProcessTree()
    tree.terminate()
    state.signaled.update(state.owned)
    state.total += 1
    assert tree.alive()  # Its late exit was never pinned, even though accounting is zero.
    tree.close()


def test_incomplete_snapshot_still_terminates_owned_job_and_refuses_confirmation(native):
    module, state = native
    tree = module.ProcessTree()
    state.complete = False
    with pytest.raises(OSError, match="native query"):
        tree.terminate()
    assert state.terminated == 1
    tree.close()
