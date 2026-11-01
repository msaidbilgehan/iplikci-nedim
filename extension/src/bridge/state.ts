/**
 * What the extension keeps in the browser (chrome.storage.local): its pairing, which Google account to read, what the
 * last run did and which layers stopped. Where delivery stands, and whether the history was scanned, lives in the
 * service (ADR-0016: the extension keeps no position); the account's address is never kept.
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
  | "unshown" // Gmail did not show some messages' originals: the user downloads them
  | "failed";

export interface RunSummary {
  readonly at: string;
  readonly outcome: Outcome;
  readonly delivered: number;
  /** Turkish, for the extension's window; never an address, subject or message text. */
  readonly detail: string;
}

/** Where a scan of Gmail stands ("Gmail'de eksikleri tara"), kept as it goes so the window follows it. */
export interface ScanSummary {
  readonly at: string;
  readonly phase: "searching" | "downloading" | "done" | "stopped";
  /** Pages of Gmail's search read, and the conversations found on them. */
  readonly pages: number;
  readonly conversations: number;
  /** Messages the list names (each conversation's first and last), those the service lacked, those delivered. */
  readonly found: number;
  readonly missing: number;
  readonly delivered: number;
  /** Messages whose original Gmail did not show: the user downloads them from Gmail. */
  readonly unshown: number;
  /**
   * Messages inside conversations, between the first and the last, that the scan could not name; how many of them
   * are in conversations with unread messages, whose print view it does not ask for.
   */
  readonly between: number;
  readonly betweenUnread: number;
  /** Turkish, for the window; never an address, subject or message text. */
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
  readonly scan: ScanSummary | null;
  /**
   * What the service said last about the history: whether it still needs a scan of Gmail (the service keeps what the
   * last finished scan searched) and the day it begins (YYYY-MM-DD).
   */
  readonly historyDue: boolean;
  readonly startDay: string;
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
  scan: null,
  historyDue: false,
  startDay: "",
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
