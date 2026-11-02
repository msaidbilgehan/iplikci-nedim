// The end-to-end tests (ADR-0008, architecture §23): the service runs on a demo data folder built from fake
// documents, the interface is the one the service serves from its build (`npm run build` in web/ first), and every
// test runs in the light and the dark theme. Nothing here reaches the real data folder, the keychain or the network.

import { defineConfig } from "@playwright/test";

import { BASE_URL, STATE } from "./service";

export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0, // a flaky test is fixed, not retried
  // A test that opens a panel and checks a long page twice with axe takes 15–20 seconds on a quiet machine. While a
  // test beside it changes the rules the service rebuilds its analysis and every page waits for it, and a busy
  // machine or a shared CI runner is slower again: the default 30 seconds failed tests that pass.
  timeout: 90_000,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    storageState: STATE,
    locale: "tr-TR",
    timezoneId: "Europe/Istanbul",
    // The computer's own Chrome: nothing is downloaded for the tests (CI's Linux images carry it too).
    channel: "chrome",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "acik", use: { colorScheme: "light" } },
    { name: "koyu", use: { colorScheme: "dark" } },
  ],
});
