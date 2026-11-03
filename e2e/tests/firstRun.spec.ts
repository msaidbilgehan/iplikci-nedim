// The first run on the service itself (F17, ADR-0017): with nothing set up yet, opening the interface through a
// one-time login link, as the installed app opens it, leads to the setup wizard by itself, and only once a session.
// This file starts a service of its own on a new, empty data folder, not the demo's: its own free port, the tests'
// made-up token (the keychain is never asked), no channel (no notification leaves the computer) and no rate provider
// (no exchange rate is fetched). Each theme's project runs its own.

import { type ChildProcess, spawn } from "node:child_process";
import { mkdirSync, openSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, request, test } from "@playwright/test";

import { STATE_DIR, TOKEN } from "../service";

const ROOT = resolve(import.meta.dirname, "..", "..");
const STARTUP_MS = 90_000; // the first start makes the data folder, on a machine busy with the other tests
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

// Not the demo's session: this service gives its own.
test.use({ storageState: { cookies: [], origins: [] } });

let service: ChildProcess | undefined;
let base = "";
let home = "";

/** A port nothing listens on now. */
function freePort(): Promise<number> {
  return new Promise((done, fail) => {
    const probe = createServer();
    probe.once("error", fail);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      probe.close(() => done(typeof address === "object" && address !== null ? address.port : 0));
    });
  });
}

async function answering(deadline: number): Promise<void> {
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) {
        return;
      }
    } catch {
      // not listening yet
    }
    await new Promise((done) => setTimeout(done, 250));
  }
  throw new Error(`the first run's service did not answer on ${base}; see its log in ${STATE_DIR}`);
}

test.beforeAll(async ({}, testInfo) => {
  testInfo.setTimeout(STARTUP_MS + 30_000);
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  home = join(STATE_DIR, `ilk-acilis-${testInfo.project.name}`);
  rmSync(home, { recursive: true, force: true });
  mkdirSync(home, { recursive: true });
  // Its port and no channel, nothing else: no name, no e-mail account and no document is what a first run is.
  // No channel and no rate provider: nothing leaves the computer while the tests run.
  writeFileSync(
    join(home, "settings.toml"),
    `[server]\nport = ${port}\n\n[notify]\nchannels = []\n\n[fx]\nproviders = ["document"]\n`,
  );
  const log = openSync(join(STATE_DIR, `ilk-acilis-${testInfo.project.name}.log`), "a");
  service = spawn("uv", ["run", "iplikci", "servis", "calistir", "--ev", home], {
    cwd: ROOT,
    env: { ...process.env, IPLIKCI_HOME: home, IPLIKCI_API_TOKEN: TOKEN },
    stdio: ["ignore", log, log],
    detached: true, // its own process group: the end stops uv and the service together
  });
  service.unref();
  await answering(Date.now() + STARTUP_MS);
});

test.afterAll(async () => {
  if (service?.pid !== undefined) {
    try {
      process.kill(-service.pid, "SIGTERM");
    } catch {
      // already gone
    }
    await new Promise((done) => setTimeout(done, 1000));
  }
  rmSync(home, { recursive: true, force: true });
});

/** A one-time login link from the service, as the app asks for one with the token. */
async function loginLink(): Promise<string> {
  const api = await request.newContext({ baseURL: base });
  const link = await api.post("/api/login-links", { headers: { Authorization: `Bearer ${TOKEN}` } });
  expect(link.ok()).toBe(true);
  const { url } = (await link.json()) as { url: string };
  await api.dispose();
  return url;
}

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

test("ilk açılışta arayüz kurulum sihirbazını kendiliğinden açar, oturumda bir kez", async ({ page }) => {
  await page.goto(await loginLink());
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
