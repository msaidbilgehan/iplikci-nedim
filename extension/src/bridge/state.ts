/**
 * What the extension keeps in the browser (chrome.storage.local): its pairing, which Google account to read, what the
 * last run did and which layers stopped. Where delivery stands lives in the service (ADR-0016: the extension keeps
 * no position); the account's address is never kept.
 */

import type { Paired } from "./service";

export type Outcome =
  | "delivered"
  | "nothing-new"
  | "unpaired"
  | "service-down"
  | "not-the-service"
  | "revoked"
  | "gmail-signed-out"
  | "gmail-busy"
  | "stopped"
  | "failed";

export interface RunSummary {
  readonly at: string;
  readonly outcome: Outcome;
  readonly delivered: number;
  /** Turkish, for the extension's window; never an address, subject or message text. */
  readonly detail: string;
}

export interface BridgeState {
  readonly paired: Paired | null;
  /** Which signed-in Google account to read, as Gmail numbers them (mail/u/N). */
  readonly account: number;
  /** The account key Gmail's own links carry, kept per account so the big Gmail page is fetched rarely. */
  readonly keys: Readonly<Record<string, string>>;
  readonly lastRun: RunSummary | null;
  /** Layers stopped by a format alarm, with the version that stopped them: a newer version tries again. */
  readonly stopped: Readonly<Record<string, string>>;
  /** No Gmail request before this time (ms since the epoch): Gmail asked to slow down, or kept failing. */
  readonly calmUntil: number;
  readonly failures: number;
  /** Gmail ids of messages the service can never take (too large, empty), so they are not downloaded again. */
  readonly skipped: readonly string[];
}

export const INITIAL: BridgeState = {
  paired: null,
  account: 0,
  keys: {},
  lastRun: null,
  stopped: {},
  calmUntil: 0,
  failures: 0,
  skipped: [],
};

export interface Store {
  get(): Promise<BridgeState>;
  update(patch: Partial<BridgeState>): Promise<BridgeState>;
}

const KEY = "kopru";

/** The state in chrome.storage.local, under one key. */
export const chromeStore: Store = {
  async get() {
    const found = (await chrome.storage.local.get(KEY))[KEY] as Partial<BridgeState> | undefined;
    return { ...INITIAL, ...found };
  },
  async update(patch) {
    const next = { ...(await this.get()), ...patch };
    await chrome.storage.local.set({ [KEY]: next });
    return next;
  },
};

/** The state in memory: for the tests. */
export function memoryStore(start: Partial<BridgeState> = {}): Store & { current: BridgeState } {
  const store = {
    current: { ...INITIAL, ...start },
    async get() {
      return store.current;
    },
    async update(patch: Partial<BridgeState>) {
      store.current = { ...store.current, ...patch };
      return store.current;
    },
  };
  return store;
}
