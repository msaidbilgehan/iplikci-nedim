// Where the tests' service runs and what it is called with; the setup writes the rest into STATE_DIR.

import { tmpdir } from "node:os";
import { join } from "node:path";

export const PORT = 8746; // not the installed service's 8643
export const BASE_URL = `http://127.0.0.1:${PORT}`;
export const TOKEN = "uctan-uca-belirteci"; // a made-up token: the keychain is never asked
export const STATE_DIR = join(tmpdir(), "iplikci-uctan-uca");
export const STATE = join(STATE_DIR, "oturum.json"); // the browser session the login link opened
export const RUN = join(STATE_DIR, "calisan.json"); // the service's process and data folder, for the teardown
