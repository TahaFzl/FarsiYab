import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running site and API with indexed data
 * (see apps/web/README.md). They do not start the servers themselves.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "fa-IR",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
