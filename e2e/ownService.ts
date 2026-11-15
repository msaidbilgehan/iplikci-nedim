// A service of a test's own on a new, empty data folder, not the demo's: the first run's test starts one, and so does
// the README's pictures' run for the setup wizard. Its own free port, the tests' made-up token (the keychain is never
// asked), no channel (no notification leaves the computer), no rate provider (no exchange rate is fetched) and no
// update check: nothing leaves the computer while it runs.

import { spawn } from "node:child_process";
import { mkdirSync, openSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";

import { request } from "@playwright/test";

import { TOKEN } from "./service";

const ROOT = resolve(import.meta.dirname, "..");

export interface OwnService {
  base: string; // http://127.0.0.1:<its port>
  stop: () => Promise<void>; // the service and uv that started it
}

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

async function answering(base: string, deadline: number, log: string): Promise<void> {
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
  throw new Error(`the service of a test's own did not answer on ${base}; see its log ${log}`);
}

/**
 * The service on home, made new and empty first: its settings are all it holds, as on a first run. Its output goes to
 * log; it must answer within startupMs, or it is stopped and the start fails.
 */
export async function startOwnService(home: string, log: string, startupMs: number): Promise<OwnService> {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  rmSync(home, { recursive: true, force: true });
  mkdirSync(home, { recursive: true });
  // Its port and no channel, nothing else: no name, no e-mail account and no document is what a first run is.
  writeFileSync(
    join(home, "settings.toml"),
    `[server]\nport = ${port}\n\n[notify]\nchannels = []\n\n[fx]\nproviders = ["document"]\n\n[updates]\nmode = "off"\n`,
  );
  const out = openSync(log, "a");
  const service = spawn("uv", ["run", "iplikci", "servis", "calistir", "--ev", home], {
    cwd: ROOT,
    env: { ...process.env, IPLIKCI_HOME: home, IPLIKCI_API_TOKEN: TOKEN },
    stdio: ["ignore", out, out],
    detached: true, // its own process group: stop() ends uv and the service together
  });
  service.unref();
  const stop = async (): Promise<void> => {
    if (service.pid === undefined) {
      return;
    }
    try {
      process.kill(-service.pid, "SIGTERM");
    } catch {
      // already gone
    }
    await new Promise((done) => setTimeout(done, 1000));
  };
  try {
    await answering(base, Date.now() + startupMs, log);
  } catch (error) {
    await stop();
    throw error;
  }
  return { base, stop };
}

/** A one-time login link from the service at base, as the app asks for one with the token. */
export async function loginLink(base: string): Promise<string> {
  const api = await request.newContext({ baseURL: base });
  try {
    const link = await api.post("/api/login-links", { headers: { Authorization: `Bearer ${TOKEN}` } });
    if (!link.ok()) {
      throw new Error(`no login link from ${base}: HTTP ${link.status()}`);
    }
    const { url } = (await link.json()) as { url: string };
    return url;
  } finally {
    await api.dispose();
  }
}
