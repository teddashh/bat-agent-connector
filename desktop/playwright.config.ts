import { defineConfig } from "@playwright/test";
const origin = `http://127.0.0.1:${process.env.BATC_UI_TEST_PORT || 1421}`;
export default defineConfig({
  testDir: "tests",
  testMatch: "**/*.spec.ts",
  use: { baseURL: origin, locale: "en-US", headless: true },
  webServer: { command: "node tests/static-server.mjs", url: `${origin}/dashboard/`, reuseExistingServer: false }
});
