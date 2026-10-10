"""Own a verification process tree before any child code is allowed to run.

The subprocess is created with CREATE_SUSPENDED. A kill-on-close job is assigned
before its one primary thread is resumed. Failure closes that job and the caller
kills its still-suspended child; there is no PID-based taskkill fallback.
"""

from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w

from .windows_files import ULONG_PTR, VOID, _bind, _close, _error, kernel

CREATE_SUSPENDED = 0x00000004


class BasicLimits(c.Structure):
    _fields_ = [("process_time", c.c_longlong), ("job_time", c.c_longlong), ("flags", w.DWORD),
                ("min_working_set", ULONG_PTR), ("max_working_set", ULONG_PTR), ("active_limit", w.DWORD),
                ("affinity", ULONG_PTR), ("priority", w.DWORD), ("scheduling", w.DWORD)]


class IoCounters(c.Structure):
    _fields_ = [(name, c.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(c.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("process_memory", ULONG_PTR),
                ("job_memory", ULONG_PTR), ("peak_process_memory", ULONG_PTR), ("peak_job_memory", ULONG_PTR)]


class ThreadEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("thread_id", w.DWORD),
                ("process_id", w.DWORD), ("base_priority", w.LONG), ("delta_priority", w.LONG), ("flags", w.DWORD)]


class Accounting(c.Structure):
    _fields_ = [("user_time", c.c_longlong), ("kernel_time", c.c_longlong), ("period_user", c.c_longlong),
                ("period_kernel", c.c_longlong), ("page_faults", w.DWORD), ("total", w.DWORD),
                ("active", w.DWORD), ("terminated", w.DWORD)]


_create_job = _bind(kernel, "CreateJobObjectW", [VOID, w.LPCWSTR], w.HANDLE)
_set_job = _bind(kernel, "SetInformationJobObject", [w.HANDLE, c.c_int, VOID, w.DWORD])
_query_job = _bind(kernel, "QueryInformationJobObject", [w.HANDLE, c.c_int, VOID, w.DWORD, VOID])
_assign_job = _bind(kernel, "AssignProcessToJobObject", [w.HANDLE, w.HANDLE])
_terminate_job = _bind(kernel, "TerminateJobObject", [w.HANDLE, w.UINT])
_open_process = _bind(kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
_snapshot = _bind(kernel, "CreateToolhelp32Snapshot", [w.DWORD, w.DWORD], w.HANDLE)
_first_thread = _bind(kernel, "Thread32First", [w.HANDLE, c.POINTER(ThreadEntry)])
_next_thread = _bind(kernel, "Thread32Next", [w.HANDLE, c.POINTER(ThreadEntry)])
_open_thread = _bind(kernel, "OpenThread", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
_thread_process = _bind(kernel, "GetProcessIdOfThread", [w.HANDLE], w.DWORD)
_resume = _bind(kernel, "ResumeThread", [w.HANDLE], w.DWORD)


class ProcessTree:
    def __init__(self):
        self.handle = _create_job(None, None)
        if not self.handle:
            _error()
        limits = ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _set_job(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            self.close()
            _error()

    def attach_and_resume(self, process):
        # The caller still owns subprocess' live process handle, so its PID
        # cannot be recycled while this additional handle is obtained.
        handle = _open_process(0x0101, False, process.pid)  # SET_QUOTA | TERMINATE
        if not handle:
            _error()
        try:
            if not _assign_job(self.handle, handle):
                _error()
        finally:
            _close(handle)
        snapshot = _snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == w.HANDLE(-1).value:
            _error()
        threads = []
        try:
            entry = ThreadEntry(size=c.sizeof(ThreadEntry))
            found = _first_thread(snapshot, c.byref(entry))
            while found:
                if entry.process_id == process.pid:
                    threads.append(entry.thread_id)
                entry.size = c.sizeof(ThreadEntry)
                found = _next_thread(snapshot, c.byref(entry))
        finally:
            _close(snapshot)
        if len(threads) != 1:
            raise RuntimeError("suspended verification process has an unexpected thread set")
        thread = _open_thread(0x0802, False, threads[0])  # QUERY_LIMITED_INFORMATION | SUSPEND_RESUME
        if not thread:
            _error()
        try:
            if _thread_process(thread) != process.pid:
                raise RuntimeError("verification thread ownership changed")
            if _resume(thread) != 1:
                raise RuntimeError("verification process was not suspended exactly once")
        finally:
            _close(thread)

    def terminate(self):
        if self.handle and not _terminate_job(self.handle, 124):
            _error()

    def alive(self):
        if not self.handle:
            return False
        info = Accounting()
        if not _query_job(self.handle, 1, c.byref(info), c.sizeof(info), None):
            _error()
        return bool(info.active)

    def close(self):
        if self.handle:
            _close(self.handle)
            self.handle = None
