"""Stock Goose ACP subprocess adapter. One task gets one scoped MCP server."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

from .task_recipes import load


@dataclass(frozen=True)
class GooseConfig:
    command: tuple[str, ...] = ("goose", "acp")
    provider: str = "chatgpt_codex"  # subscription OAuth; no paid API key
    timeout_s: float = 300


class GooseACP:
    def __init__(self, config: GooseConfig | None = None):
        self.config = config or GooseConfig()

    async def run_task(self, task: dict, cwd: str, *, command: tuple[str, ...] | None = None) -> dict:
        recipe = load(task["recipe"])
        prompt = (recipe["instructions"] + "\n\n" + recipe["prompt"] +
                  "\n\nTed's original words (verbatim):\n" + task["original_words"] +
                  "\n\nAcceptance criteria:\n" + task["acceptance"])
        return await self.run(task["task_id"], cwd, prompt, command=command)

    async def run(self, task_id: str, cwd: str, prompt: str, *, command: tuple[str, ...] | None = None) -> dict:
        cfg = self.config
        if cfg.provider not in {"chatgpt_codex", "codex-acp", "codex", "claude-acp"}:
            raise ValueError("Goose PM provider must be a configured subscription provider")
        env = {k: v for k, v in os.environ.items() if k not in {
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOSE_API_KEY", "GOOGLE_API_KEY",
        }}
        env["GOOSE_PROVIDER"] = cfg.provider
        proc = await asyncio.create_subprocess_exec(*(command or cfg.command), stdin=asyncio.subprocess.PIPE,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.DEVNULL, env=env)
        assert proc.stdin and proc.stdout
        next_id = 0

        async def rpc(method: str, params: dict) -> dict:
            nonlocal next_id
            next_id += 1
            ident = next_id
            proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": ident, "method": method,
                                          "params": params}) + "\n").encode())
            await proc.stdin.drain()
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), cfg.timeout_s)
                if not line or len(line) > 2_000_000:
                    raise RuntimeError("Goose ACP stopped or sent an oversized message")
                reply = json.loads(line)
                if reply.get("id") == ident:
                    if "error" in reply:
                        raise RuntimeError("Goose ACP request failed")
                    return reply["result"]
                if "method" in reply and "id" in reply:
                    # No implicit approval of Goose's own permission requests.
                    proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": reply["id"],
                                                  "result": {"outcome": {"outcome": "cancelled"}}}) + "\n").encode())
                    await proc.stdin.drain()

        try:
            await rpc("initialize", {"protocolVersion": 2, "clientCapabilities": {},
                                     "clientInfo": {"name": "bat-task-service", "version": "0.1"}})
            scoped = {"name": "bat-task", "command": sys.executable,
                      "args": ["-m", "bat_agent_connector.task_scoped_mcp", task_id], "env": []}
            session = await rpc("session/new", {"cwd": cwd, "mcpServers": [scoped]})
            result = await rpc("session/prompt", {"sessionId": session["sessionId"],
                                                  "prompt": [{"type": "text", "text": prompt}]})
            return {"session_id": session["sessionId"], "stop_reason": result.get("stopReason")}
        finally:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
