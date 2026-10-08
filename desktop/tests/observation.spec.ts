import {test, expect, type Page} from "@playwright/test";

const cp = (cursor: number) => ({cursor, token: `observation-proof-${cursor}`});
const caps = {actor: "observer", scopes: ["observe", "operate", "manage"], api_version: 1,
  contract_version: "2026-10-08", hosts: [], features: {}, actions: []};
async function mount(page: Page, native: boolean, dispatch: (request: any) => Promise<any>) {
  if (native) {
    await page.exposeFunction("fixtureConnector", dispatch);
    await page.addInitScript(caps => Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
      if (command === "native_status") return {endpoint: "https://central.example/", credential_available: true};
      if (command === "connector_connect") return caps;
      if (command === "connector_disconnect") return null;
      if (command === "connector_request") return (window as any).fixtureConnector(args.input);
      throw new Error(`Unexpected native command ${command}`);
    }}}), caps);
  } else await page.addInitScript(() => sessionStorage.setItem("batc.dashboard.token", "fixture-token"));
  await page.route("**/api/v1/**", async route => {
    if (native) throw new Error("Native requests must use IPC");
    const request = route.request(), url = new URL(request.url());
    const result = await dispatch({method: request.method(), path: url.pathname.slice(7) + url.search,
      body: request.postDataJSON(), idempotency_key: request.headers()["idempotency-key"]});
    return route.fulfill({status: result.status, json: result.data});
  });
}
const saved = (page: Page) => page.evaluate(() => JSON.parse(Object.entries(localStorage).find(([key]) => key.startsWith("batc.sync."))?.[1] || "null"));
const ask = (id: string) => ({kind: "ask_user", toolUseId: id, questions: [{question: "Which branch?", options: ["main", "feature"]}]});

for (const native of [false, true]) {
  test(`mounted pending refresh preserves drafts and refuses stale answers (${native ? "native" : "browser"})`, async ({page}) => {
    let cursor = 0, reads = 0, failRead = false;
    let pending: any = null;
    const writes: any[] = [];
    const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
    await mount(page, native, async input => {
      const url = new URL(input.path, "http://fixture"), path = url.pathname;
      if (input.method === "POST") { writes.push(input); return {status: 200, data: {operation: {operation_id: "op_" + "f".repeat(32), status: "accepted"}}}; }
      if (path === "/sessions/demo/session-1") {
        reads++;
        if (failRead) return {status: 503, data: {error: {code: "UNAVAILABLE", message: "Session observation unavailable"}}};
        return {status: 200, data: {session: {host: "demo", session_id: "session-1", title: "Observed session",
          api_access: "managed", pending, provenance: "connector"}}};
      }
      return {status: 200, data: path === "/capabilities" ? caps : path === "/bootstrap" ? {capabilities: caps,
        sync: {version: 1, server_id: "server", principal_id: "principal", checkpoint: cp(0)}}
        : path === "/events" ? {events: Number(url.searchParams.get("after")) < cursor
          ? [{seq: cursor, resource_type: "session", resource_id: "demo/session-1", kind: "session.updated"}] : [],
          head_cursor: cursor, next_cursor: cursor, has_more: false, sync: {checkpoint: cp(cursor)}}
        : {messages: [], checkpoints: [], operations: [], hosts: [], sessions: [], work_items: []}};
    });
    await page.goto("/dashboard/#/session/demo/session-1");
    const composer = page.locator("textarea").first();
    await composer.fill("Preserved session instructions");
    pending = ask("question-1"); cursor = 1;
    await expect(page.getByRole("textbox", {name: "Which branch?"})).toBeVisible();
    await expect.poll(() => saved(page)).toEqual(cp(1));
    const answer = page.getByRole("textbox", {name: "Which branch?"});
    await answer.fill("Original answer draft");
    cursor = 2;
    await expect.poll(() => saved(page)).toEqual(cp(2));
    await expect(answer).toHaveValue("Original answer draft");
    await expect(composer).toHaveValue("Preserved session instructions");
    // The pending ID changes before its event reaches this view. Preflight must refuse the old answer.
    pending = {kind: "permission", toolUseId: "permission-2", toolName: "git", input_preview: "Publish branch"};
    await page.getByRole("button", {name: "Answer", exact: true}).click();
    await expect(page.getByText(/PENDING_CHANGED/)).toBeVisible();
    expect(writes).toHaveLength(0);
    await expect(page.getByRole("button", {name: "Allow", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Allow", exact: true}).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0].body.params).toEqual({permission: "allow", tool_use_id: "permission-2"});
    pending = ask("question-1"); cursor = 3;
    await expect.poll(() => saved(page)).toEqual(cp(3));
    await expect(answer).toHaveValue("Original answer draft");
    failRead = true; cursor = 4;
    await expect(page.getByText("UNAVAILABLE Session observation unavailable")).toBeVisible();
    expect(await saved(page)).toEqual(cp(3));
    await page.getByRole("button", {name: "Send", exact: true}).click();
    await expect(page.getByText(/CENTRAL_OFFLINE/)).toBeVisible();
    expect(writes).toHaveLength(1);
    failRead = false;
    await expect.poll(() => saved(page), {timeout: 10000}).toEqual(cp(4));
    await expect(answer).toHaveValue("Original answer draft");
    await expect(composer).toHaveValue("Preserved session instructions");
    expect(reads).toBeGreaterThan(5); expect(errors).toEqual([]);
  });

  test(`parent archive updates mounted controls while retaining the edit (${native ? "native" : "browser"})`, async ({page}) => {
    let archived = false, cursor = 0, linkedStatus = "running";
    const writes: any[] = [];
    await mount(page, native, async input => {
      const url = new URL(input.path, "http://fixture"), path = url.pathname;
      if (input.method === "POST") {writes.push(input); return {status: 200, data: {operation: {status: "succeeded"}}};}
      return {status: 200, data: path === "/capabilities" ? caps : path === "/bootstrap" ? {capabilities: caps,
        sync: {version: 1, server_id: "server", principal_id: "principal", checkpoint: cp(0)}}
        : path === "/events" ? {events: Number(url.searchParams.get("after")) < cursor ? [{seq: cursor,
          resource_type: cursor === 1 ? "operation" : "project", resource_id: cursor === 1 ? "op_link" : "p_fixture", kind: "updated"}] : [],
          head_cursor: cursor, next_cursor: cursor, has_more: false, sync: {checkpoint: cp(cursor)}}
        : path === "/work-items/wi_fixture" ? {work_item: {work_item_id: "wi_fixture", title: "Linked work", version: 1,
          state: "todo", goal: "", request: "", acceptance: "", steps: [], completion: {display_state: "todo", fingerprint: "fp"}},
          project: {project_id: "p_fixture", name: "Parent", archived}, links: [{kind: "operation", ref: "op_link",
            target: {found: true, action: "fixture.operation", status: linkedStatus}}], children: [], derived: [], path: [], events: []}
        : {operations: [], sessions: [], hosts: [], work_items: []}};
    });
    await page.goto("/dashboard/#/item/wi_fixture");
    await expect(page.getByRole("heading", {name: "Linked work"})).toBeVisible();
    linkedStatus = "succeeded"; cursor = 1;
    await expect(page.locator(".status-succeeded")).toBeVisible();
    await expect.poll(() => saved(page)).toEqual(cp(1));
    await page.getByRole("button", {name: "More", exact: true}).click();
    await page.locator("input[maxlength='120']").fill("Retained project archive draft");
    archived = true; cursor = 2;
    await expect(page.getByText("This item or its project is archived. Your edit draft is retained.")).toBeVisible();
    await expect(page.getByRole("button", {name: "Save", exact: true})).toBeDisabled();
    await expect(page.locator("input[maxlength='120']")).toHaveValue("Retained project archive draft");
    expect(await saved(page)).toEqual(cp(1)); expect(writes).toHaveLength(0);
    await page.getByRole("button", {name: "More", exact: true}).click();
    await expect.poll(() => saved(page)).toEqual(cp(2));
    expect(await page.evaluate(() => JSON.stringify({...localStorage, ...sessionStorage}))).toContain("Retained project archive draft");
  });
}
