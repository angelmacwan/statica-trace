import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration — 0.2.2
 *
 * Runs E2E tests against the local Vite dev server.
 * CI can gate this on `npm run test:e2e`.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",

  use: {
    // Base URL of the local dev server (vite runs on 5173 by default)
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },

  projects: [
    {
      // 0.2.2: at least Chromium as a target browser
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Spin up the Vite dev server automatically before running E2E tests
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
