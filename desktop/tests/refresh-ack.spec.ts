import {test, expect} from "@playwright/test";

for (const native of [false, true]) {
  test(`checkpoint waits for successful view refresh (${native ? "native" : "browser"})`, async ({page}) => {
    const caps = {actor: "refresh-fixture", scopes: ["observe", "operate"], api_version: 1,
      contract_version: "2026-10-08", hosts: [], features: {}, actions: []};
    let changed = false, failing = true, messageReads = 0;
    const writes: any[] = [], errors: string[] = [];
    let release!: () => void;
    const hold = new Promise<void>(resolve => { release = resolve; });
    const checkpoint = (cursor: number) => ({cursor, token: `fixture-proof-${cursor}`});
    const dispatch = async (input: any) => {
      const url = new URL(input.path, "http://fixture"), path = url.pathname;
      if (input.method === "POST") {
        writes.push(input);
        return {status: 200, data: {operation: {operation_id: "op_" + "d".repeat(32), status: "accepted"}}};
      }
      if (path.endsWith("/messages")) {
        messageReads++;
        if (changed) {
          if (messageReads === 2) await hold;
          if (failing) return {status: 503, data: {error: {code: "UNAVAILABLE", message: "View refresh unavailable"}}};
        }
        return {status: 200, data: {messages: [{role: "assistant", text: changed ? "Refreshed evidence" : "Original evidence"}]}};
      }
      const data = path === "/capabilities" ? caps : path === "/bootstrap" ? {capabilities: caps,
        sync: {version: 1, server_id: "refresh-server", principal_id: "refresh-principal", checkpoint: checkpoint(0)}}
        : path === "/events" ? {events: changed && url.searchParams.get("after") === "0"
          ? [{seq: 1, kind: "session.updated", resource_type: "session", resource_id: "demo/session-1"}] : [],
          head_cursor: changed ? 1 : 0, next_cursor: changed ? 1 : 0, has_more: false, sync: {checkpoint: checkpoint(changed ? 1 : 0)}}
        : path === "/sessions/demo/session-1" ? {session: {host: "demo", session_id: "session-1", title: "Refresh fixture",
          api_access: "managed", provenance: "connector"}} : {checkpoints: [], sessions: [], operations: [], hosts: [], work_items: []};
      return {status: 200, data};
    };
    page.on("pageerror", error => errors.push(error.message));
    if (native) {
      await page.exposeFunction("fixtureConnector", dispatch);
      await page.addInitScript(caps => {
        Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
          if (command === "native_status") return {endpoint: "https://central.example/", credential_available: true};
          if (command === "connector_connect") return caps;
          if (command === "connector_disconnect") return null;
          if (command === "connector_request") return (window as any).fixtureConnector(args.input);
          throw new Error(`Unexpected command: ${command}`);
        }}});
      }, caps);
    } else await page.addInitScript(() => sessionStorage.setItem("batc.dashboard.token", "fixture-token"));
    await page.route("**/api/v1/**", async route => {
      if (native) throw new Error("Native client must use IPC");
      const request = route.request(), url = new URL(request.url());
      const result = await dispatch({method: request.method(), path: url.pathname.slice("/api/v1".length) + url.search,
        body: request.postDataJSON(), idempotency_key: request.headers()["idempotency-key"]});
      return route.fulfill({status: result.status, json: result.data});
    });
    await page.goto("/dashboard/#/session/demo/session-1");
    const saved = () => page.evaluate(() => JSON.parse(Object.entries(localStorage)
      .find(([key]) => key.startsWith("batc.sync."))?.[1] || "null"));
    await expect.poll(saved).toEqual(checkpoint(0));
    const draft = page.locator("textarea").first();
    await draft.fill("Keep this exact draft and original operation key");
    changed = true;
    await expect.poll(() => messageReads).toBe(2);
    expect(await saved()).toEqual(checkpoint(0));
    await page.getByRole("button", {name: "Send", exact: true}).click();
    await expect(page.locator(".error")).toContainText("actions paused");
    expect(writes).toHaveLength(0);
    const originalKey = await page.evaluate(() => JSON.parse(Object.entries(localStorage)
      .find(([key]) => key.startsWith("batc.key."))![1]).key);
    release();
    await expect(page.getByText("UNAVAILABLE View refresh unavailable")).toBeVisible();
    expect(await saved()).toEqual(checkpoint(0));
    await expect(draft).toHaveValue("Keep this exact draft and original operation key");
    failing = false;
    await expect.poll(saved, {timeout: 10000}).toEqual(checkpoint(1));
    await expect(page.getByText("Refreshed evidence")).toBeVisible();
    await page.getByRole("button", {name: "Send", exact: true}).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0].idempotency_key).toBe(originalKey);
    expect(errors).toEqual([]);
  });
}
