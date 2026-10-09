# Native Fleet route selection and recovery

This ports the local route policy from reviewed Kit `2ec4b11` `bat-servers.ps1`
(`Test-TailscaleDirect`, `Test-TcpPort`, `Get-ServerAlias`) and `bat-connect.ps1`
(`Select-Alias`, `Register-TunnelExit`, `Ensure-Tunnel`). It does not spawn SSH,
change central tasks, declare BAT ready, or query installed/live Tailscale in tests.

Routes come only from the validated inventory. Direct is eligible only when the
configured Tailscale IP occurs in exactly one status peer with literal `Online: true`
and a nonempty string `CurAddr`, followed by a successful bounded TCP connection to
the configured probe endpoint. DERP relay information or a fast TCP connection alone
is insufficient. LAN needs a successful TCP probe. Cloudflare remains a configured
fallback; selection does not prove that its future tunnel or BAT protocol is ready.
The Connector's single configured SSH alias is an explicitly `configured` route;
no alias means no tunnel route, rather than inventing one.

Two intentional corrections to historical Kit behavior are part of this port:

- Direct-only hosts and no-Cloudflare fallback do not bypass genuine-direct proof.
  No eligible route returns `ROUTE_UNAVAILABLE`.
- Fast-failure demotion only ranks routes whose eligibility was checked. A demoted
  preferred route cannot cause an unproven direct/LAN tier to be selected.

Within eligible routes, preference remains direct, LAN, then Cloudflare. Skip aliases
blocked by fast failures when another eligible route is available. If every eligible
route is blocked, retain the best eligible route, as in the Kit's last-resort policy.
Three observed failures lasting less than 15 seconds demote that alias for ten minutes
and reset its fast-failure counter. A run lasting at least 15 seconds clears its counter.
Deliberate stops do not count as failures. Exact active run identity makes repeated or
stale exit reports no-ops. The caller must prove the process exited; unknown ownership
or uncertain stop results are not exit evidence.

Recovery reuses the core's existing bounded schedule: wait five seconds after failure,
then at most three recovery attempts with 15/45/45-second next-attempt spacing. A
positively observed owned tunnel alive for at least 60 seconds resets recovery. This
does not clear a ten-minute alias demotion early. Initial launch, explicit selection
changes and configuration-generation changes remain supervisor decisions; this module
does not silently reconnect an intentionally disconnected host.

A selection captures configuration/selection/epoch/generation plus the per-host policy
revision and a random policy-instance identity. `SelectionRequest::new` freezes an owned,
immutable input for an independent background worker; it does not borrow or clone mutable
policy. Its native alias accessor refuses changed state, future timestamps and evidence
older than 60 seconds. Configuration must still be revalidated by the supervisor before
passing the alias to `tunnel::Plan`; that planner independently accepts only a configured
alias. An active run prevents selecting or consuming another recovery attempt.
`update_selection_generation(expected, next)` is a compare-and-set for preference/probe
changes within the same monitor epoch and configuration binding; the generation must
increase. It invalidates pending choices but retains the exact active `Run`, recovery
budget, fast-failure count and demotion deadlines. Source/credential/configuration changes
require a new policy after the old owned process is stopped. A no-op identical generation
preserves choices; stale writers and backwards generation changes refuse.

At launch, the supervisor checks current configuration/selection and choice, consumes a due
recovery attempt, then records `started` only for a process bound to a retained handle.
A positively proven launch failure with no remaining child uses `launch_failed`; uncertain
launch/stop evidence must not be counted as an exit or trigger another launch.
No alias, endpoint, Tailscale payload or process output is serialized as status.

The injectable probe boundary has no global lock or serial host queue. Independent host
selection futures can run concurrently. Direct and LAN checks share a finite total
selection deadline; each TCP or local status call is also bounded by the inventory's
probe budget. Cancelling an attempt drops TCP sockets and terminates only the owned
status child via its retained process object, never a PID lookup or process-tree search.
The native status adapter uses a fixed absolute, canonical trusted Tailscale executable
with exactly `status --json`, cleared environment, null stdin/stderr and bounded stdout.
It never searches PATH or accepts a command from the WebView. Runtime installation-path
trust and configuration revalidation remain prerequisites; path validation is not a
binary-signature attestation or an atomic defense against an installer replacing files.

Tests use synthetic inventory/status documents, injectable reachability and temporary
loopback listeners. A tiny independently compiled executable double exercises argv,
environment, output, timeout and cancellation contracts; it does not call Tailscale or
SSH. Linux/Windows CI fixtures do not establish installed routing, Cloudflare, account
login, cross-login ownership, or packaged Fleet acceptance.
