import { test, expect } from "@playwright/test";

const capabilities = {actor: "fixture-operator", scopes: ["observe", "operate"], api_version: 1,
  contract_version: "2026-10-08", features: {}, hosts: [], actions: []};
const checkpoint = {cursor: 0, token: "fixture-checkpoint"};
const bootstrap = {sync: {version: 1, server_id: "fixture-server", principal_id: "fixture-principal", checkpoint}, capabilities};
const events = {events: [], head_cursor: 0, next_cursor: 0, has_more: false, sync: {checkpoint}};

for (const width of [390, 768, 1440]) {
  test(`shared browser dashboard at ${width}px`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/v1/**", route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/bootstrap")) return route.fulfill({json: bootstrap});
      if (path.endsWith("/events")) return route.fulfill({json: events});
      if (path.endsWith("/events/stream")) return route.fulfill({contentType: "text/event-stream", body: ": keepalive\n\n"});
      return route.fulfill({json: path.endsWith("/capabilities") ? capabilities :
        {sessions: [], operations: [], hosts: [], work_items: []}});
    });
    await page.goto("/dashboard/");
    await expect(page.getByRole("heading", {name: "Connection"})).toBeVisible();
    await page.locator('input[type="password"]').fill("fixture-token");
    await page.getByRole("button", {name: "Connect", exact: true}).click();
    await expect(page.getByText("Nothing needs you right now.")).toBeVisible();
    await page.screenshot({path: `test-results/browser-${width}.png`, fullPage: true});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("desktop UI uses IPC without a WebView credential", async ({page}) => {
  await page.addInitScript(({caps, boot, eventPage}) => {
    const requests: unknown[] = [];
    Object.assign(window, { __fixtureRequests: requests, isTauri: true, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: any) => {
        if (command === "native_status") return {endpoint: "https://central.example/", error: null, credential_available: true};
        if (command === "connector_connect") return caps;
        if (command === "connector_disconnect") return null;
        if (command !== "connector_request") throw new Error("unexpected native command");
        requests.push(args.input);
        return {status: 200, data: args.input.path === "/bootstrap" ? boot : args.input.path.startsWith("/events")
          ? eventPage
          : {sessions: [], operations: [], hosts: [], work_items: []}};
      }
    }});
  }, {caps: capabilities, boot: bootstrap, eventPage: events});
  let networkCalls = 0;
  await page.route("**/api/v1/**", route => { networkCalls++; return route.abort(); });
  await page.goto("/dashboard/");
  await expect(page.getByText("Nothing needs you right now.")).toBeVisible();
  await page.getByRole("link", {name: "Connection", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Desktop central connection"})).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  expect(networkCalls).toBe(0);
  expect(await page.evaluate(() => JSON.stringify({...localStorage, ...sessionStorage}))).not.toContain("fixture-token");
  const requests = await page.evaluate(() => (window as any).__fixtureRequests);
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every((r: any) => !r.token && !r.headers && r.method === "GET")).toBe(true);
  await page.screenshot({path: "test-results/desktop-settings.png", fullPage: true});
});

test("lost operation reply preserves draft and idempotency key across reopening", async ({page}) => {
  const keys: string[] = [];
  const bodies: unknown[] = [];
  await page.addInitScript(() => sessionStorage.setItem("batc.dashboard.token", "fixture-token"));
  await page.route("**/api/v1/**", route => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    if (path.endsWith("/bootstrap")) return route.fulfill({json: bootstrap});
    if (path.endsWith("/events")) return route.fulfill({json: events});
    if (req.method() === "POST") {
      keys.push(req.headers()["idempotency-key"]); bodies.push(req.postDataJSON());
      if (keys.length === 1) return route.abort("connectionreset");
      return route.fulfill({json: {operation: {operation_id: "op_" + "a".repeat(32), status: "accepted"}}});
    }
    if (path.endsWith("/events/stream")) return route.fulfill({contentType: "text/event-stream", body: ": keepalive\n\n"});
    return route.fulfill({json: path.endsWith("/capabilities") ? capabilities : path.endsWith("/sessions/demo/session-1")
      ? {session: {host: "demo", session_id: "session-1", title: "Fixture managed session", api_access: "managed", provenance: "connector"}}
      : {messages: [], checkpoints: []}});
  });
  await page.goto("/dashboard/#/session/demo/session-1");
  const draft = page.locator("textarea").first();
  await draft.fill("Fixture task instructions");
  await page.getByRole("button", {name: "Send", exact: true}).click();
  await expect(page.locator(".error")).toContainText("Failed to fetch");
  await page.reload();
  await expect(draft).toHaveValue("Fixture task instructions");
  await page.getByRole("button", {name: "Send", exact: true}).click();
  await expect(page.getByText("op_" + "a".repeat(32), {exact: true})).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy(); expect(keys[0]).toBe(keys[1]);
  expect(bodies[0]).toEqual(bodies[1]);
  expect(bodies[1]).toEqual({action: "session.send", target: {host: "demo", session_id: "session-1"},
    params: {text: "Fixture task instructions", queue: false}, preconditions: {}});
});
