// The first run on the service itself (F17, ADR-0017): with nothing set up yet, opening the interface through a
// one-time login link, as the installed app opens it, leads to the setup wizard by itself, and only once a session.
// This file starts a service of its own on a new, empty data folder, not the demo's (../ownService.ts: its own free
// port, the tests' made-up token, no channel and no rate provider). Each theme's project runs its own.

import { rmSync } from "node:fs";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { loginLink, type OwnService, startOwnService } from "../ownService";
import { STATE_DIR } from "../service";

const STARTUP_MS = 90_000; // the first start makes the data folder, on a machine busy with the other tests
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

// Not the demo's session: this service gives its own.
test.use({ storageState: { cookies: [], origins: [] } });

let service: OwnService | undefined;
let base = "";
let home = "";

test.beforeAll(async ({}, testInfo) => {
  testInfo.setTimeout(STARTUP_MS + 30_000);
  home = join(STATE_DIR, `ilk-acilis-${testInfo.project.name}`);
  service = await startOwnService(home, join(STATE_DIR, `ilk-acilis-${testInfo.project.name}.log`), STARTUP_MS);
  base = service.base;
});

test.afterAll(async () => {
  await service?.stop();
  rmSync(home, { recursive: true, force: true });
});

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

test("ilk açılışta arayüz kurulum sihirbazını kendiliğinden açar, oturumda bir kez", async ({ page }) => {
  await page.goto(await loginLink(base));
  await expect(page).toHaveURL(`${base}/kurulum`, { timeout: 15_000 });
  await expect(page.getByRole("heading", { level: 1, name: "Kurulum" })).toBeVisible();
  await loaded(page);
  // Opened without a step, the wizard starts at the first one still to do: the user's names.
  await expect(page.getByRole("heading", { level: 2, name: "Adım 2/9: Adınız" })).toBeVisible();
  const found = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);

  // Once a session: the home page opened again stays the home page, after the setup's answer said "first run" again.
  const answered = page.waitForResponse((response) => response.url() === `${base}/api/setup`);
  await page.goto(`${base}/`);
  await answered;
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  await expect(page).toHaveURL(`${base}/`);
  await expect(page.getByRole("heading", { level: 1, name: "Pano" })).toBeVisible();
  await loaded(page);
});
