import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the REAL stack (Vite dev server → FastAPI →
 * PostgreSQL). Credentials come from the environment, never from the repo:
 *   E2E_USER / E2E_PASSWORD  (an analyst or admin account)
 * Browser: the locally installed Chrome channel (no download needed);
 * override with E2E_CHANNEL=msedge.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    channel: process.env.E2E_CHANNEL ?? "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: process.env.E2E_CHANNEL ?? "chrome", viewport: { width: 1440, height: 900 } }, grepInvert: /@mobile/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: process.env.E2E_CHANNEL ?? "chrome" }, grep: /@mobile/ },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
