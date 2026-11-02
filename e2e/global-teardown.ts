// After the tests: the service stopped and its demo data folder deleted (it holds only fake documents).

import { existsSync, readFileSync, rmSync } from "node:fs";

import { RUN, STATE_DIR } from "./service";

export default async function globalTeardown(): Promise<void> {
  if (existsSync(RUN)) {
    const { pid } = JSON.parse(readFileSync(RUN, "utf-8")) as { pid: number };
    try {
      process.kill(-pid, "SIGTERM"); // the whole group: uv and the service it started
    } catch {
      // already gone
    }
    await new Promise((done) => setTimeout(done, 1000));
  }
  if (!process.env.IPLIKCI_UCTAN_UCA_SAKLA) {
    rmSync(STATE_DIR, { recursive: true, force: true });
  }
}
