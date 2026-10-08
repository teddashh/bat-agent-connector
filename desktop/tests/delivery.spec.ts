import {test, expect} from "@playwright/test";

for (const native of [false, true]) {
  test(`delivery refresh and fixed confirmations over ${native ? "native IPC" : "browser HTTP"}`, async ({page}) => {
    const caps = {actor: "delivery-fixture", scopes: ["observe", "deploy"], api_version: 1,
      contract_version: "2026-10-08", hosts: [], repositories: [],
      features: {deploy: true, deployment_history: true, environment_generation: true},
      actions: ["deployment.start", "deployment.rollback"].map(action => ({action, allowed: true})),
      deploy_recipes: [{name: "prod", repository: "o/r", environment: "production", readiness: {ready: true}, rollback: {supported: true}}]};
    const dep = {deployment_id: "dep_" + "a".repeat(32), operation_id: "op_" + "a".repeat(32),
      recipe: "prod", environment: "production", repository: "o/r", state: "failed", provider_terminal: true,
      identity: {source_sha: "9".repeat(40)}, rollback_eligible: true, rollback: {not_undone: ["database migrations"]}};
    let generation = 2, sequence = 0;
    const events: any[] = [], requests: any[] = [], writes: any[] = [], errors: string[] = [];
    const checkpoint = (cursor: number) => ({cursor, token: `fixture-${cursor}`});
    const dispatch = async (input: any) => {
      requests.push(input);
      const url = new URL(input.path, "http://fixture");
      const route = url.pathname;
      if (input.method === "POST") {
        writes.push(input);
        return {status: 200, data: {operation: {operation_id: "op_" + "b".repeat(32),
          status: writes.length === 1 ? "failed" : "succeeded", error_code: writes.length === 1 ? "ENVIRONMENT_CHANGED" : null}}};
      }
      const data = route === "/capabilities" ? caps : route === "/bootstrap" ? {capabilities: caps,
        sync: {version: 1, server_id: "delivery-server", principal_id: "delivery-principal", checkpoint: checkpoint(sequence)}}
        : route === "/events" ? {events: events.filter(ev => ev.seq > Number(url.searchParams.get("after"))),
          next_cursor: sequence, head_cursor: sequence, has_more: false, sync: {checkpoint: checkpoint(sequence)}}
        : route === "/deployment-environments" ? {environment: {environment: "production", desired_generation: generation,
          desired: dep, observed: {source_sha: "1".repeat(40)}}}
        : route === "/deployment-environments/history" ? {items: [dep], next_cursor: null}
        : route === "/deployments/preview" ? {preview: {environment: "production", environment_generation: generation,
          readiness: {ready: true}, preconditions: {expected_recipe_digest: "fixture-digest", expected_environment_generation: generation}}}
        : {sessions: [], work_items: [], operations: [], hosts: []};
      return {status: 200, data};
    };
    page.on("pageerror", error => errors.push(error.message));
    let httpCalls = 0;
    if (native) {
      await page.exposeFunction("fixtureConnector", dispatch);
      await page.addInitScript(caps => {
        Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
          if (command === "native_status") return {endpoint: "https://central.example/", credential_available: true};
          if (command === "connector_connect") return caps;
          if (command === "connector_disconnect") return null;
          if (command === "connector_request") return (window as any).fixtureConnector(args.input);
          throw new Error(`Unexpected native command: ${command}`);
        }}});
      }, caps);
    } else await page.addInitScript(() => sessionStorage.setItem("batc.dashboard.token", "fixture-token"));
    await page.route("**/api/v1/**", async route => {
      httpCalls++;
      if (native) return route.abort();
      const request = route.request(), url = new URL(request.url());
      const response = await dispatch({method: request.method(), path: url.pathname.slice("/api/v1".length) + url.search,
        body: request.postDataJSON(), idempotency_key: request.headers()["idempotency-key"]});
      return route.fulfill({status: response.status, json: response.data});
    });
    await page.goto("/dashboard/#/delivery");
    const card = page.locator('[data-environment="production"]');
    await expect(card).toContainText("Environment generation 2");
    const append = (resource_type: string) => { generation++; events.push({seq: ++sequence, resource_type,
      resource_id: dep.deployment_id, kind: "deployment.updated", payload: {}}); };
    append("deployment");
    await expect(card).toContainText("Environment generation 3");
    append("deployment_environment");
    await expect(card).toContainText("Environment generation 4");
    await card.getByTestId("deployment-rollback").click();
    const drawer = card.locator(".drawer:not([hidden])");
    await expect(drawer.getByTestId("deployment-preview-generation")).toContainText("generation 4");
    append("deployment_environment");
    await expect.poll(async () => page.evaluate(() => JSON.parse(Object.entries(localStorage)
      .find(([key]) => key.startsWith("batc.sync."))?.[1] || "null")?.cursor)).toBe(sequence);
    await expect(drawer.getByTestId("deployment-preview-generation")).toContainText("generation 4");
    await drawer.getByTestId("deployment-rollback-confirm").click();
    await expect(drawer).toContainText("Review the fresh preview");
    await expect(drawer.getByTestId("deployment-preview-generation")).toContainText("generation 5");
    expect(writes).toHaveLength(1);
    expect(writes[0].body.preconditions.expected_environment_generation).toBe(4);
    await drawer.getByTestId("deployment-rollback-confirm").evaluate((el: HTMLButtonElement) => {el.click(); el.click();});
    await expect.poll(() => writes.length).toBe(2);
    expect(writes[1].body).toEqual({action: "deployment.rollback", target: {recipe: "prod"},
      params: {deployment_id: dep.deployment_id}, preconditions: {expected_recipe_digest: "fixture-digest", expected_environment_generation: 5}});
    expect(writes[1].idempotency_key).toBeTruthy();
    expect(writes[1].idempotency_key).not.toBe(writes[0].idempotency_key);
    await drawer.getByRole("button", {name: "Close", exact: true}).click();
    await expect(card).toContainText("Environment generation 5");
    expect(requests.every(input => !input.token && !input.headers)).toBe(true);
    expect(errors).toEqual([]);
    if (native) expect(httpCalls).toBe(0);
  });
}
