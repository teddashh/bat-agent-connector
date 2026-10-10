# Task-service review: regression and compatibility guidance

This review note preserves implementation lessons and source references. It does
not contain private fleet inventory, provider account probes, operational logs or
an installation sign-off. The filename remains stable for existing links.

## Method and evidence boundaries

Review task ownership, lifecycle, MCP authorization, BAT dispatch, verifier process
control, optional Goose integration and provider routing together. Follow both
normal and interrupted paths: ownership reservation before start, cancellation
while awaiting I/O, accepted writes with lost replies, and restart after each
journal boundary. Inspect logs and status projections for private values.

Mock BAT, fake provider transports and temporary Git repositories can demonstrate
specific contracts. They do not establish real-host deployment, provider login,
subscription availability or ACP restart compatibility. Record executed checks
against their exact source revision in the relevant change; do not substitute a
historical test count or a model's opinion for current evidence.

## Findings and regression boundaries

| Area | Contract to preserve | Source and focused coverage |
| --- | --- | --- |
| Legacy cleanup and relay | Task-owned sessions must be excluded from generic idle cleanup and main-session selection | [lifecycle.py](../../src/bat_agent_connector/lifecycle.py), [test_lifecycle.py](../../tests/test_lifecycle.py) |
| Start ownership race | Reserve `task_id` and role before BAT start, so pause before the initial send cannot make a task session appear standalone | [orchestrate.py](../../src/bat_agent_connector/orchestrate.py), [task_bat.py](../../src/bat_agent_connector/task_bat.py), [test_task_service.py](../../tests/test_task_service.py) |
| Worktree cleanup | Require clean, matching HEAD/branch; preserve the original branch and a retained task ref. No force removal or `branch -D`; restart needs exact Git evidence before clearing journal pointers | [task_bat.py](../../src/bat_agent_connector/task_bat.py), [task_daemon.py](../../src/bat_agent_connector/task_daemon.py), [test_task_service.py](../../tests/test_task_service.py) |
| Original-word handoff | Preserve complete UTF-8 input and authoritative archive pointers; verify digest, private permissions, durable writes and collision refusal | [task_handoff.py](../../src/bat_agent_connector/task_handoff.py), [test_task_handoff.py](../../tests/test_task_handoff.py) |
| Verification argument privacy | Journal the command digest, not credential-bearing argv; keep executable configuration and artifact logs private | [task_verifier.py](../../src/bat_agent_connector/task_verifier.py), [test_task_service.py](../../tests/test_task_service.py) |
| Shell quoting | Quote the whole external worktree record and each shell variable; repository paths containing apostrophes must not alter command structure | [task_bat.py](../../src/bat_agent_connector/task_bat.py), [test_task_service.py](../../tests/test_task_service.py) |
| Provider error privacy | Log structured classifications or exception types, not raw provider errors that may include prompt or token data | [task_daemon.py](../../src/bat_agent_connector/task_daemon.py), [test_task_service.py](../../tests/test_task_service.py) |
| Pause during routing | Re-read durable controls after awaited classification and before start, send or verification; pause must prevent the external frame | [task_core.py](../../src/bat_agent_connector/task_core.py), [test_task_service.py](../../tests/test_task_service.py) |
| Explicit provider selection | Preserve task → recipe → routed choice → default precedence and record the actual selection | [task_daemon.py](../../src/bat_agent_connector/task_daemon.py), [provider-routing.md](../design/provider-routing.md) |
| Optional ACP execution | Keep activation gated until the pinned adapter, restart, identity and permission contracts are verified | [goose_acp.py](../../src/bat_agent_connector/goose_acp.py), [task-service.md](../design/task-service.md) |
| Legacy waiting clients | Existing `session_wait` remains a compatibility tool; migration of an external client's waiting or notification loop is separate deployment work | [mcp_server.py](../../src/bat_agent_connector/mcp_server.py), [cutover guidance](../design/hermes-cutover-plan.md) |

## Provider and Goose evidence

A provider's `/v1/models` response advertises model identifiers. It does not prove
that a configured account can execute every advertised model, that effort options
are compatible, or that a quota remains. Probe model selection, resolver options,
authentication and error classification separately using an isolated endpoint and
synthetic content. Do not publish account identities, private URLs or raw responses.

Verify an optional Goose binary against its public release/version pin and test the
actual ACP contract. An `end_turn` response and one observed fake-tool call establish
only that synthetic exchange. They do not prove real BAT behavior, persistent resume,
UI approval semantics, provider switching or production readiness. Public source
references and the activation checklist are retained in the [task-service design](../design/task-service.md).

## Validation guidance

Use the project's supported Python versions, focused regression coverage and the
normal lint checks for changed contracts. Give timeout tests enough time to reach
the state they intend to exercise, while keeping production deadlines unchanged.
Test cancellation with a confirmed running descendant and require actual process
exit; do not turn missing startup evidence into a successful timeout assertion.

Deployment and live acceptance remain operator-owned. This document makes no claim
that a private installation, provider account or host fleet passed those checks.
