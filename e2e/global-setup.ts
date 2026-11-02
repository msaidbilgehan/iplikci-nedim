// Before the tests: a demo data folder built from fake documents, the service on it in the background, and a
// browser session opened through a one-time login link, as the user's own browser gets one (ADR-0007).

import { execFileSync, spawn } from "node:child_process";
import { appendFileSync, mkdirSync, openSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { request } from "@playwright/test";

import { BASE_URL, PORT, RUN, STATE, STATE_DIR, TOKEN } from "./service";

const ROOT = resolve(import.meta.dirname, "..");
const STARTUP_MS = 60_000;

async function answering(deadline: number): Promise<void> {
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${BASE_URL}/healthz`)).ok) {
        return;
      }
    } catch {
      // not listening yet
    }
    await new Promise((done) => setTimeout(done, 250));
  }
  throw new Error(`the tests' service did not answer on ${BASE_URL}; see ${join(STATE_DIR, "servis.log")}`);
}

export default async function globalSetup(): Promise<void> {
  rmSync(STATE_DIR, { recursive: true, force: true });
  mkdirSync(STATE_DIR, { recursive: true });
  const home = join(STATE_DIR, "veri");
  execFileSync("uv", ["run", "iplikci", "dev", "demo", home], { cwd: ROOT, stdio: "inherit" });
  // Its own port; and no notification leaves the computer or shows on its screen while the tests run.
  appendFileSync(join(home, "settings.toml"), `\n[server]\nport = ${PORT}\n\n[notify]\nchannels = []\n`);
  const log = openSync(join(STATE_DIR, "servis.log"), "a");
  const service = spawn("uv", ["run", "iplikci", "servis", "calistir", "--ev", home], {
    cwd: ROOT,
    env: { ...process.env, IPLIKCI_HOME: home, IPLIKCI_API_TOKEN: TOKEN },
    stdio: ["ignore", log, log],
    detached: true, // its own process group: the teardown stops uv and the service together
  });
  service.unref();
  writeFileSync(RUN, JSON.stringify({ pid: service.pid, home }));
  await answering(Date.now() + STARTUP_MS);

  // The login link the service gives a client holding the token, opened as a browser opens it: the session cookie
  // it sets is what every test starts with.
  const api = await request.newContext({ baseURL: BASE_URL });
  const link = await api.post("/api/login-links", { headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!link.ok()) {
    throw new Error(`no login link: HTTP ${link.status()}`);
  }
  const { url } = (await link.json()) as { url: string };
  const opened = await api.get(url);
  if (!opened.ok()) {
    throw new Error(`the login link did not open a session: HTTP ${opened.status()}`);
  }
  await api.storageState({ path: STATE });
  await api.dispose();
}
