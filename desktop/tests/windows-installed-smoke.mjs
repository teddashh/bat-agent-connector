// Installs only on a disposable GitHub-hosted Windows runner. No live BAT/central.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

assert.equal(process.platform, "win32", "Windows runner required");
assert.equal(process.env.GITHUB_ACTIONS, "true", "GitHub Actions required");
assert.equal(process.env.RUNNER_ENVIRONMENT, "github-hosted", "Disposable hosted runner required");
const evidence = resolve("test-results/windows-installed");
await mkdir(evidence, { recursive: true });
const caps = { actor: "fixture-operator", scopes: ["observe"], api_version: 1,
  contract_version: "2026-10-08", features: {}, actions: [], hosts: [] };
const checkpoint = { cursor: 0, token: "fixture-checkpoint" };
const requests = [];
const violations = [];
const server = createServer((req, res) => {
  const path = new URL(req.url, "http://127.0.0.1").pathname;
  res.setHeader("Content-Type", "application/json");
  if (path === "/_fixture/status" && req.method === "GET") {
    res.end(JSON.stringify({ requests, violations }));
    return;
  }
  requests.push({ method: req.method, path });
  if (req.method !== "GET" || req.headers.authorization !== "Bearer fixture-native-token"
      || !path.startsWith("/api/v1/")) {
    violations.push({ method: req.method, path });
    res.writeHead(403).end("{}");
    return;
  }
  res.end(JSON.stringify(path.endsWith("/capabilities") ? caps : path.endsWith("/bootstrap")
    ? { sync: { version: 1, server_id: "fixture-server", principal_id: "fixture-principal", checkpoint }, capabilities: caps }
    : path.endsWith("/events") ? { events: [], next_cursor: 0, head_cursor: 0, has_more: false, sync: { checkpoint } }
    : { sessions: [], work_items: [], operations: [], hosts: [] }));
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let diagnostic = "";
try {
  const child = spawn("pwsh", ["-NoLogo", "-NoProfile", "-NonInteractive", "-File",
    resolve("tests/windows-installed-smoke.ps1"), "-Endpoint", `http://127.0.0.1:${server.address().port}`,
    "-Evidence", evidence], { stdio: ["ignore", "pipe", "pipe"] });
  for (const stream of [child.stdout, child.stderr]) stream.on("data", data => {
    diagnostic += data;
    process.stdout.write(data);
  });
  const timer = setTimeout(() => child.kill(), 240_000);
  let code;
  try {
    code = await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("exit", resolve);
    });
  } finally { clearTimeout(timer); }
  assert.equal(code, 0, `Installed Windows smoke failed (exit ${code})`);
  assert.deepEqual(violations, [], "Fixture received an unauthorized or mutating request");
  for (const path of ["/api/v1/capabilities", "/api/v1/bootstrap", "/api/v1/events"]) {
    assert(requests.some(request => request.path === path), `Missing native request: ${path}`);
  }
  const receipt = JSON.parse(await readFile(resolve(evidence, "result.json"), "utf8"));
  assert.equal(receipt.status, "passed");
  console.log(JSON.stringify(receipt));
} finally {
  await writeFile(resolve(evidence, "fixture.json"), JSON.stringify({ requests, violations }, null, 2));
  await writeFile(resolve(evidence, "process.log"), diagnostic);
  server.closeAllConnections();
  server.close();
}
