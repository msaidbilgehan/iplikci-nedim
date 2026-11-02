// Where the tests' service runs and what it is called with; the setup writes the rest into STATE_DIR.

import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Each checkout (a git worktree too) gets a port and a folder of its own: two runs side by side never stop each
// other's service or delete each other's session.
const CHECKOUT = createHash("sha256").update(import.meta.dirname).digest();

export const PORT = 8800 + (CHECKOUT.readUInt16BE(0) % 200); // never the installed service's 8643
export const BASE_URL = `http://127.0.0.1:${PORT}`;
export const TOKEN = "uctan-uca-belirteci"; // a made-up token: the keychain is never asked
export const STATE_DIR = join(tmpdir(), `iplikci-uctan-uca-${CHECKOUT.toString("hex").slice(0, 8)}`);
export const STATE = join(STATE_DIR, "oturum.json"); // the browser session the login link opened
export const RUN = join(STATE_DIR, "calisan.json"); // the service's process and data folder, for the teardown
