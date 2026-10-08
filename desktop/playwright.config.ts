import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  testMatch: "**/*.spec.ts",
  use: { baseURL: "http://127.0.0.1:1421", locale: "en-US", headless: true },
  webServer: { command: "node tests/static-server.mjs", url: "http://127.0.0.1:1421/dashboard/", reuseExistingServer: false }
});
