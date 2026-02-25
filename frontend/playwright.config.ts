import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E test configuration.
 *
 * Tests are in frontend/e2e/ and run against the Next.js dev server.
 * All backend calls are mocked via route interception — no real API is called.
 *
 * Run:   cd frontend && npx playwright test
 * UI:    cd frontend && npx playwright test --ui
 * Debug: cd frontend && npx playwright test --debug
 */
export default defineConfig({
  testDir: "./e2e",
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Single worker on CI to keep resource usage low */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter */
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  /* Global timeout per test */
  timeout: 30_000,
  /* Shared settings for all projects */
  use: {
    /* Base URL so tests can use relative paths like page.goto('/') */
    baseURL: "http://localhost:3000",
    /* Collect traces on first retry */
    trace: "on-first-retry",
    /* Screenshot on failure */
    screenshot: "only-on-failure",
    /* All requests go through the test proxy — no real backend needed */
    extraHTTPHeaders: {
      "x-playwright-test": "1",
    },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /* Start Next.js dev server before running tests */
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
