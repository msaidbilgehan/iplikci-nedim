// The README's pictures (docs/gorseller/), made again by `npm run gorseller`: the end-to-end tests' service on the demo
// data folder (the same setup and teardown), its screens photographed and recorded in the light theme unless a picture
// says otherwise. Not a test run: `npx playwright test` leaves this folder out (playwright.config.ts reads ./tests).
// Build web/ first, as for the tests; ffmpeg turns the recordings into GIFs.

import { defineConfig } from "@playwright/test";

import { BASE_URL, STATE } from "./service";

export default defineConfig({
  testDir: "./gorseller",
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  // One after another, in the file's order: the last picture changes the demo's rules for its notification.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // A recording plays its scene in real time and ffmpeg works on it after; the first-run picture starts a service.
  timeout: 240_000,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    storageState: STATE,
    locale: "tr-TR",
    timezoneId: "Europe/Istanbul",
    channel: "chrome",
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
    colorScheme: "light",
    trace: "retain-on-failure",
  },
  projects: [{ name: "gorseller", use: { colorScheme: "light" } }],
});
