/**
 * What the extension's own pages and its content script in Gmail's tabs ask its service worker, checked before
 * anything is done with it. A Gmail tab may only ask what to look for and tell the ids it shows.
 */

import { PER_MESSAGE } from "../gmail/visible";
import type { RunSummary, ScanSummary } from "./state";

export type Request =
  | { readonly kind: "verify"; readonly account: number }
  | { readonly kind: "status" }
  | { readonly kind: "pair"; readonly code: string }
  | { readonly kind: "account"; readonly account: number }
  | { readonly kind: "run" }
  | { readonly kind: "scan" }
  | { readonly kind: "forget" }
  | { readonly kind: "open-panel" } // answered with a PanelAnswer (bridge/panel.ts), not a Status
  | { readonly kind: "sayings" }; // answered with İplikçi Nedim's lines (bridge/sayings.ts), not a Status

/** What the extension's window and its settings page show; the token never leaves the service worker. */
export interface Status {
  readonly paired: boolean;
  readonly account: number;
  readonly lastRun: RunSummary | null;
  /** The scan of Gmail ("Gmail'de eksikleri tara"): the one running, or the last one. */
  readonly scan: ScanSummary | null;
  /** The service lacks the history from this day on (YYYY-MM-DD): a check asked for by hand scans Gmail first. */
  readonly historyDue: boolean;
  readonly startDay: string;
  readonly stopped: readonly string[];
  /** The answer to a pairing attempt, in Turkish; "" when it worked or none was made. */
  readonly problem: string;
}

const ACCOUNTS = 10;

function isAccount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value < ACCOUNTS;
}

export function asRequest(message: unknown): Request | null {
  if (typeof message !== "object" || message === null) {
    return null;
  }
  const { kind, account, code } = message as Record<string, unknown>;
  switch (kind) {
    case "verify":
    case "account":
      return isAccount(account) ? { kind, account } : null;
    case "pair":
      return typeof code === "string" && code.length <= 20 ? { kind, code } : null;
    case "status":
    case "run":
    case "scan":
    case "forget":
    case "open-panel":
    case "sayings":
      return { kind };
    default:
      return null;
  }
}

/**
 * What the content script in a Gmail tab asks (content.ts): what to look for, or it tells the Gmail ids (decimal) of
 * the listed senders' messages the tab shows. Both are answered with what to look for (gmail/visible.ts's Watch), or
 * null while the bridge takes nothing from that tab.
 */
export type TabRequest =
  | { readonly kind: "gmail-watch" }
  | { readonly kind: "gmail-seen"; readonly ids: readonly string[] };

/** Gmail's message id in decimal, as "Show original" and the service take it. */
const GMAIL_ID = /^[0-9]{1,25}$/;

export function asTabRequest(message: unknown): TabRequest | null {
  if (typeof message !== "object" || message === null) {
    return null;
  }
  const { kind, ids } = message as Record<string, unknown>;
  if (kind === "gmail-watch") {
    return { kind };
  }
  if (kind !== "gmail-seen" || !Array.isArray(ids) || ids.length > PER_MESSAGE) {
    return null;
  }
  const found = ids.filter((id): id is string => typeof id === "string" && GMAIL_ID.test(id));
  return found.length === ids.length ? { kind, ids: found } : null;
}
