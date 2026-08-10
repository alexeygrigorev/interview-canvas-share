import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const repoRoot = path.resolve(__dirname, "..");

/**
 * The compose stack publishes the app on APP_PORT (8100 by default). Point
 * E2E_BASE_URL at an already-running deployment to test that one instead.
 */
const appPort = process.env.APP_PORT ?? "8100";
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${appPort}`;

export default defineConfig({
  testDir: "./tests",
  // Building the image and booting Postgres is slow; the tests themselves wait
  // on realtime round-trips, so keep the per-test budget generous.
  timeout: 120_000,
  expect: { timeout: 20_000 },
  // The suite drives one shared deployment, so runs stay serial.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],

  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [{ name: "chromium" }],

  webServer: {
    // Foreground `up` so Playwright can stop the stack when the run finishes.
    command: "docker compose up --build",
    cwd: repoRoot,
    url: baseURL,
    env: { APP_PORT: appPort },
    // The first run builds the frontend bundle and the Python image.
    timeout: 900_000,
    reuseExistingServer: !process.env.CI,
    stdout: "pipe",
    stderr: "pipe",
  },
});
