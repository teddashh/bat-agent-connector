"""Wait for operation outcomes rather than a best-effort worker drain deadline."""

import asyncio


async def settle_operations(ops, *, timeout=60):
    """Run due operations and wait for each attempt's persisted status and worker completion.

    Uncertain/waiting attempts return without forcing their future retries. Yield after scheduling so a retry
    enters running before wait() observes the previous attempt's uncertain status.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        await ops.run_due()
        active = [(op_id, task) for op_id, task in ops._active.items() if not task.done()]
        if not active:
            return
        await asyncio.sleep(0)
        for op_id, task in active:
            outcome = await ops.wait(op_id, timeout=max(0, deadline - loop.time()))
            assert outcome["status"] not in {"accepted", "running"}, (
                f"operation {op_id} did not settle within {timeout}s: {outcome['status']}"
            )
            await asyncio.wait_for(asyncio.shield(task), timeout=max(0, deadline - loop.time()))
