import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3010";

export default defineConfig({
  testDir: "./e2e-record",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  forbidOnly: Boolean(process.env.CI),
  reporter: [
    ["list"],
    ["json", { outputFile: process.env.WALKTHROUGH_PLAYWRIGHT_JSON ?? "../artifacts/walkthrough/playwright-results.json" }],
  ],
  use: {
    baseURL,
    ...(process.env.WALKTHROUGH_BROWSER_CHANNEL === "chrome" ||
    process.env.WALKTHROUGH_BROWSER_CHANNEL === "msedge"
      ? { channel: process.env.WALKTHROUGH_BROWSER_CHANNEL }
      : {}),
    viewport: { width: 1440, height: 900 },
    video: "off",
    screenshot: "off",
    trace: "off",
    actionTimeout: 20_000,
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    { name: "record", testMatch: /.*\.spec\.ts/, dependencies: ["setup"] },
  ],
});
