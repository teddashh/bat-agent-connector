"""Mock BAT only; the integration script runs the real packaged owned central."""
from __future__ import annotations

import asyncio
import json
import sys

from bat_agent_connector.channels import GUARDED_CHANNELS, ORCHESTRATE_CHANNELS, WRITE_CHANNELS
from tests.mockbat import MockBat


async def main():
    mock = MockBat()
    await mock.start()
    print(json.dumps({"url": mock.url, "fingerprint": mock.fingerprint, "token": mock.token}), flush=True)
    try:
        while line := await asyncio.to_thread(sys.stdin.readline):
            command = json.loads(line)
            if command["action"] == "stop":
                break
            if command["action"] != "snapshot":
                raise ValueError("Unknown fixture command")
            print(json.dumps({"auth_count": len(mock.auth_frames), "writes": [frame["channel"] for frame in mock.invokes
                if frame["channel"] in WRITE_CHANNELS | ORCHESTRATE_CHANNELS | GUARDED_CHANNELS]}), flush=True)
    finally:
        await mock.stop()


if __name__ == "__main__":
    asyncio.run(main())
