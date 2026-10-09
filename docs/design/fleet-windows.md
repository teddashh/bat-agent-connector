# Windows Fleet process adapter

This implements the OS ownership boundary of [the Fleet port contract](fleet-rust.md), not the
supervisor, migration UI or installed parity. Source basis remains the reviewed Kit
`2ec4b11bc010bfd669040e942648c741b63d0b7c`; `4744507354466b1424b8ea369a00a94f1ca3a933`
contains no intervening client/tests changes. No private inventory, credential, host or service
configuration is copied. The module is not registered as a Tauri command.

## Interfaces and authority

`desktop/fleet-core/src/process_adapter.rs` supplies `ProcessSnapshot`, `TunnelRecord`,
`MonitorPointer`, `StopMode` and a held-process decision algorithm. `windows.rs` supplies:

| Native-only interface | Behavior |
| --- | --- |
| `current_login()` | SID and login session from the current process token |
| `WindowsProcess::observe(pid)` | Read a retained process handle; return complete evidence, proven absence, or an error |
| `WindowsProcess::from_child(&Child)` | Duplicate the retained launch handle, including for rollback if initial record publication fails |
| `process_state(pid)` | Birth/liveness only; inaccessible or incomplete evidence is `Unknown` |
| `MonitorMutex::try_acquire()` | Same `Global\BatFleetMonitor_<SID>` as PowerShell; occupied returns `None`, failures refuse |
| `MonitorMutex::stop_tunnel(record, mode)` | Current-login check, exact stored identity and final recheck on one held handle; no PID-based kill fallback |
| `PreferenceLock::try_acquire(path)` / `acquire(path)` | Same `fleet-client.json.lock`, OpenOrCreate/ReadWrite/FileShare.None; nonblocking attempt or fixed two-second wait |

The mutex is thread-affine and neither `Send` nor `Sync`. A dedicated supervisor thread retains it;
async work must communicate with that thread, not move the guard. Reentrant acquisition on the same
thread is refused. An abandoned mutex only acquires exclusion: it does not prove an old monitor,
child or record safe to replace. The runtime must still check both BAT directories, old monitor
records, configuration binding and existing listeners before any spawn or publication.

The runtime chooses fixed SSH executable/argv, creates a fresh unpredictable monitor epoch, starts
with a retained child handle and persists both child and parent identity before publishing. On record
write failure it may stop only that retained newly launched child. Normal later stops require
`Owned { current_epoch }`; orphan cleanup requires the recorded parent's incarnation to be proven
ended. Missing, partial, inaccessible or live parent evidence refuses orphan termination. Another
login's owner is readonly even when the account SID matches. No code kills a listener, port match,
substring match or an unrelated process tree.

The final child snapshot includes PID, exact native creation time, executable, parsed argv, epoch,
SID and login session. The first and final snapshots must be equal and match the persisted record.
`TerminateProcess` and the bounded two-second exit wait use that same retained process handle. An
unconfirmed termination returns `STOP_UNCONFIRMED`; callers preserve the record and reconcile,
never declare success or issue a blind repeat. A process can alter its own command line after a read;
this is identity evidence for a trusted fixed child, not an atomic attestation of a hostile process.

The preference lock remains held through caller read/CAS/configuration and owner checks/atomic
replacement. The lock file is never removed or replaced. Its parent directory must already exist
and the path comes from trusted native configuration. Uncooperative editors do not honor this lock;
callers still compare original bytes before replacement and retain the existing documented edit race.

## PowerShell compatibility and evidence sources

Existing flat SSH owner JSON keeps `pid`, `created`, `executable`, `arguments`, `monitor_instance`,
`owner_sid`, `session_id` and optional paired `monitor_pid` / `monitor_created`. Older records with
neither parent field may use an already-read `fleet-monitor.json` pointer only when the exact epoch
matches; a partially present parent never falls back. Decoded duplicate keys, unknown owner fields,
invalid values and inconsistent native/legacy time are rejected. Native writes add a decimal string
`created_filetime`; existing PowerShell's named-field checks ignore this additive field. Native
readers compare it exactly, including the final 100ns digit.

[GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)
reports FILETIME ticks since 1601. Adding `504911232000000000` yields .NET UTC DateTime ticks since
0001, bounded by `3155378975999999999`. The prior PowerShell source uses Win32_Process.CreationDate:
[CIM datetime](https://learn.microsoft.com/en-us/dotnet/api/system.management.cimtype)
has six fractional digits. The legacy `created` field therefore truncates the final 100ns digit
(`ticks / 10 * 10`), while the native record retains the full kernel timestamp. No local timezone
conversion occurs. A Windows fixture compares this conversion with actual CIM output for its own
temporary child; installed compatibility remains a gate until that fixture and packaging run there.

Executable comes from `QueryFullProcessImageNameW`; SID and session from `OpenProcessToken` /
`GetTokenInformation`, all against the held handle. Command line uses dynamically resolved
`NtQueryInformationProcess`, class 60 (`ProcessCommandLineInformation`), at most 64 KiB plus the
native header. Buffer length, alignment, returned pointer range and UTF-16 are validated before
`CommandLineToArgvW` parses it; executable argv[0] is omitted to match PowerShell. Exact argument
order/case is retained. There is no PEB-memory, substring, shell or WMI subprocess fallback.
Microsoft notes that [this NT API may change](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess),
and class 60 is not a public stability guarantee. Missing API, unsupported class, changed shape or
unreadable arguments return unknown. Production activation must pass the Windows owned-child tests.

An invalid-parameter OpenProcess failure is only absence when a complete bounded Toolhelp process
snapshot also excludes the PID; other failures remain unknown. A different observed creation time
proves the old incarnation ended, never permission to terminate the process now using that PID.
Legacy monitor script/inventory/index parsing, exact path binding and normal quit requests remain
in the supervisor/migration layer; this module exposes argv without inferring its original CWD.

## Validation limits

Linux executes pure record/decision tests, including denied access, other login, PID reuse during
parent checks, changed final evidence, unknown exit and legacy record recovery. Windows compile
checks include the OS adapter and test source. Windows runtime fixtures use only owned test children,
a synthetic SID mutex and a temporary preference file. They verify retained-handle termination,
CIM birth compatibility, exact argv, PowerShell mutex exclusion and .NET file-lock exclusion. The
fixture-only system PowerShell calls have fixed scripts, a restricted system module path and a
15-second deadline; production does not invoke them.

No live SSH tunnels, real Fleet mutex, real preferences, host topology or remote operations are
changed by tests. Windows runtime/packaged cross-login acceptance, startup migration, DPAPI credential
integration, discovery and supervisor/probe integration are separate gates. Compilation and Linux
mocks do not establish those results.
