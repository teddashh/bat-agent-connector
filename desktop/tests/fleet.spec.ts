import {test, expect} from "@playwright/test";
import {readFileSync} from "node:fs";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/fleet-status.json", import.meta.url), "utf8")).result;

async function setup(page: any, options: any = {}) {
  await page.addInitScript(({doc, options}: any) => {
    const env = {doc, calls: [] as any[], lose: false, failReads: false, ...options};
    Object.assign(window, {__fleet: env, isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
      if (command === "native_status") return {endpoint: null, error: "Fixture: central is offline", credential_available: false};
      if (command === "connector_connect") throw new Error("Fixture: central is offline");
      if (command === "fleet_availability") return {configured: true, platform_supported: options.supported !== false};
      if (command !== "fleet_request") throw new Error("Unexpected command " + command);
      const input = structuredClone(args.input);
      if (input.action === "status") {
        if (env.failReads) throw new Error("Fixture unavailable");
        return structuredClone(env.doc);
      }
      env.calls.push(input);
      if (input.action === "set_connections") {
        env.doc.selection.connections = input.connections;
        env.doc.selection.revision = "e".repeat(64);
      }
      if (env.lose) {env.failReads = true; throw new Error("Fixture lost reply");}
      return structuredClone(env.doc);
    }}});
  }, {doc: fixture, options});
  await page.goto("/dashboard/#/settings");
}

for (const locale of ["en-US", "zh-TW"]) for (const width of [390, 768, 1440]) {
  test(`Fleet selection and readiness ${locale} ${width}`, async ({browser}) => {
    const context = await browser.newContext({locale, viewport: {width, height: 900}});
    const page = await context.newPage();
    const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
    await setup(page);
    await expect(page.locator("[data-fleet-name]")).toHaveCount(6);
    await page.locator('[data-fleet-name="node-2"]').uncheck();
    await page.getByRole("button", {name: locale === "en-US" ? "Save connections" : "儲存連線選擇", exact: true}).click();
    await expect.poll(() => page.evaluate(() => (window as any).__fleet.calls.length)).toBe(1);
    const input = await page.evaluate(() => (window as any).__fleet.calls[0]);
    expect(input).toEqual({action: "set_connections", connections: ["node-1", "node-3", "node-4", "node-5", "connector"],
      expected_configuration_binding: "c".repeat(64), expected_selection_revision: "d".repeat(64), expected_monitor_epoch: "a".repeat(32)});
    await expect(page.getByText(locale === "en-US" ? "Waiting for the monitor to read the current selection." : "等待監控讀取目前選擇。")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: `test-results/fleet-${locale}-${width}.png`, fullPage: true});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    await context.close();
  });
}

test("lost Fleet reply reads back without resending and keeps central independent", async ({page}) => {
  await setup(page, {lose: true});
  await page.locator('[data-fleet-name="node-2"]').uncheck();
  await page.getByRole("button", {name: "Save connections", exact: true}).click();
  await expect(page.getByText("The outcome is unknown;", {exact: false})).toBeVisible();
  await expect(page.getByRole("button", {name: "Save connections", exact: true})).toBeDisabled();
  expect(await page.evaluate(() => sessionStorage.getItem("batc.desktop.fleet.selection." + "c".repeat(64)))).toContain("node-1");
  await page.evaluate(() => {(window as any).__fleet.failReads = false;});
  await page.getByRole("button", {name: "Read status", exact: true}).click();
  await expect(page.locator('[data-fleet-name="node-2"]')).not.toBeChecked();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("batc.desktop.fleet.selection." + "c".repeat(64)))).toBe(null);
  expect(await page.evaluate(() => (window as any).__fleet.calls.length)).toBe(1);
  await expect(page.getByRole("button", {name: "Connect", exact: true})).toBeDisabled();
});

test("changed monitor or selection blocks a stale draft and other-login control", async ({page}) => {
  await setup(page);
  await page.locator('[data-fleet-name="node-2"]').uncheck();
  await page.evaluate(() => {(window as any).__fleet.doc.selection.revision = "f".repeat(64);});
  await page.getByRole("button", {name: "Read status", exact: true}).click();
  await expect(page.getByText("The selection or monitor changed.", {exact: false})).toBeVisible();
  await expect(page.getByRole("button", {name: "Save connections", exact: true})).toBeDisabled();
  await expect(page.locator('[data-fleet-name="node-2"]')).not.toBeChecked();
  await page.getByRole("button", {name: "Use current selection", exact: true}).click();
  await expect(page.locator('[data-fleet-name="node-2"]')).toBeChecked();
  await page.evaluate(() => {(window as any).__fleet.doc.monitor.controllable = false;});
  await page.getByRole("button", {name: "Read status", exact: true}).click();
  await expect(page.getByText("This monitor is outside", {exact: false})).toBeVisible();
  await expect(page.locator('[data-fleet-name="node-2"]')).toBeDisabled();
  await expect(page.getByRole("button", {name: "Stop local connection monitor", exact: true})).toBeDisabled();
  expect(await page.evaluate(() => (window as any).__fleet.calls.length)).toBe(0);
});

test("Fleet control unavailable on other platforms", async ({page}) => {
  await setup(page, {supported: false});
  await expect(page.getByText("Fleet connection management requires Windows.")).toBeVisible();
  await expect(page.locator("[data-fleet-name]")).toHaveCount(0);
});
