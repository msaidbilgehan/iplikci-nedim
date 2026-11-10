/**
 * The messages an open Gmail tab shows (ADR-0016, note of 2026-11-10). The inbox feed (layer 1) lists unread messages
 * only, so a bank message read in Gmail before the next minute's run used to wait for a scan asked for by hand. The
 * extension's content script (content.ts) runs this in the user's Gmail tabs and tells the service worker which
 * listed senders' messages the tab shows, read or not. It reads ids and the senders' domains only:
 *
 * - a conversation list's rows (`tr.zA`): the conversation's id (`span[data-thread-id]`, "#thread-f:<decimal>"), which
 *   is its first message's, the last message's (`data-legacy-last-message-id`, hexadecimal), and the addresses of the
 *   row's senders (`span[email]`), whose domains decide whether it is a listed sender's;
 * - an opened conversation: each message's id (`data-message-id`, "#msg-f:<decimal>") and its sender's address
 *   (`span.gD[email]`).
 *
 * Only the ids of a listed sender's rows and messages leave it; of the others nothing is kept. Subjects, snippets,
 * bodies and names are never read, and an address is read only for its domain. The page is read only while the tab
 * is shown, at most every five seconds: when Gmail's main area changes, when the address's part after # changes and
 * when the tab is shown again. Gmail's page is not documented: what does not read as described is left alone.
 */

import { listed } from "../mail/headers";
import { ORIGIN } from "./http";
import { decimalId } from "./search";

/** The page is read at most this often. */
export const PAUSE_MS = 5000;
/** How long what the bridge looks for holds before it is asked again: the pairing, the senders or a scan change it. */
export const ASK_MS = 60_000;
/** Ids told at most at once: a list shows a hundred rows at most, and the rest wait for the next read. */
export const PER_MESSAGE = 500;
/** Ids told from one page at most before they are forgotten and may be told again (the service worker drops them). */
const TOLD_KEPT = 5000;

const THREAD = /^#thread-f:(\d{1,25})$/;
const MESSAGE = /^#msg-f:(\d{1,25})$/;
const HEX = /^[0-9a-f]{1,16}$/;
const DOMAIN = /^[a-z0-9.-]{1,253}$/;

/** What the bridge looks for in a Gmail tab: the domains of the senders whose messages it delivers. */
export interface Watch {
  readonly senders: readonly string[];
}

/** A Watch as the service worker answered it, checked; null when it is not one (the bridge takes nothing now). */
export function asWatch(value: unknown): Watch | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const { senders } = value as Record<string, unknown>;
  if (!Array.isArray(senders)) {
    return null;
  }
  const domains = senders.filter((sender): sender is string => typeof sender === "string" && DOMAIN.test(sender));
  return domains.length === senders.length ? { senders: domains } : null;
}

/** The Google account a Gmail address shows, as Gmail numbers them (/mail/u/N/); null for any other address. */
export function accountOf(url: string): number | null {
  if (!URL.canParse(url)) {
    return null;
  }
  const { origin, pathname } = new URL(url);
  const account = origin === ORIGIN ? /^\/mail\/u\/(\d{1,2})\//.exec(pathname)?.[1] : undefined;
  return account === undefined ? null : Number(account);
}

/**
 * The Gmail ids (decimal) of the listed senders' messages the page shows: each conversation row's first and last
 * message, and the messages of an opened conversation. Rows and messages Gmail keeps hidden behind the view in front
 * are left out, as are those of any other sender.
 */
export function shownIds(page: ParentNode, senders: readonly string[]): string[] {
  const ids = new Set<string>();
  for (const row of page.querySelectorAll('div[role="main"] tr.zA')) {
    const thread = THREAD.exec(row.querySelector("span[data-thread-id]")?.getAttribute("data-thread-id") ?? "")?.[1];
    if (thread === undefined || !shown(row) || !fromListed(row.querySelectorAll("span[email]"), senders)) {
      continue;
    }
    ids.add(thread);
    const last = row.querySelector("[data-legacy-last-message-id]")?.getAttribute("data-legacy-last-message-id") ?? "";
    if (HEX.test(last)) {
      ids.add(decimalId(last));
    }
  }
  for (const message of page.querySelectorAll('div[role="main"] [data-message-id]')) {
    const id = MESSAGE.exec(message.getAttribute("data-message-id") ?? "")?.[1];
    const sender = message.querySelector("span.gD[email]");
    if (id !== undefined && sender !== null && shown(message) && fromListed([sender], senders)) {
      ids.add(id);
    }
  }
  return [...ids];
}

/** Whether one of the addresses (the `email` attributes) is a listed sender's. */
function fromListed(marks: Iterable<Element>, senders: readonly string[]): boolean {
  for (const mark of marks) {
    const address = mark.getAttribute("email") ?? "";
    const domain = address.slice(address.lastIndexOf("@") + 1).trim().toLowerCase();
    if (address.includes("@") && DOMAIN.test(domain) && listed(domain, senders)) {
      return true;
    }
  }
  return false;
}

/** Whether the element is laid out: Gmail keeps the views it left in the page, hidden. */
function shown(element: Element): boolean {
  return element.getClientRects().length > 0;
}

/** The service worker, as the content script talks to it. Both resolve; null when it did not answer. */
export interface Bridge {
  /** What to look for; null while the bridge takes nothing from this tab. */
  watch(): Promise<Watch | null>;
  /** Tell it the ids the tab shows; what to look for from now on, or null when it did not keep them. */
  seen(ids: readonly string[]): Promise<Watch | null>;
}

export interface Watcher {
  stop(): void;
}

/** Watch the Gmail page and tell the bridge the listed senders' messages it shows, each once. */
export function watchGmail(page: Document, bridge: Bridge): Watcher {
  return new GmailWatcher(page, bridge);
}

class GmailWatcher implements Watcher {
  private readonly observer: MutationObserver;
  private observed: Element | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private lastRead = Number.NEGATIVE_INFINITY;
  private reading = false;
  private again = false;
  private stopped = false;
  private watch: Watch | null = null;
  private askedAt = Number.NEGATIVE_INFINITY;
  /** The ids the bridge kept from this page. */
  private readonly told = new Set<string>();

  constructor(
    private readonly page: Document,
    private readonly bridge: Bridge,
  ) {
    this.observer = new MutationObserver(this.soon);
    page.defaultView?.addEventListener("hashchange", this.moved);
    page.addEventListener("visibilitychange", this.visibility);
    this.visibility();
  }

  stop(): void {
    this.stopped = true;
    this.rest();
    this.page.defaultView?.removeEventListener("hashchange", this.moved);
    this.page.removeEventListener("visibilitychange", this.visibility);
  }

  /** Another view: read now, and once more after the pause, as Gmail draws the view when its data has come. */
  private readonly moved = (): void => {
    this.again = true;
    this.soon();
  };

  /** Something changed: read the page now, or once the pause since the last read is over; nothing while hidden. */
  private readonly soon = (): void => {
    if (this.stopped || this.page.hidden || this.timer !== undefined) {
      return;
    }
    this.timer = setTimeout(
      () => {
        this.timer = undefined;
        void this.read();
      },
      Math.max(0, this.lastRead + PAUSE_MS - Date.now()),
    );
  };

  /** A hidden tab is neither watched nor read; shown again, it is read at once. */
  private readonly visibility = (): void => {
    if (this.page.hidden) {
      this.rest();
      return;
    }
    this.attach();
    this.soon();
  };

  private rest(): void {
    this.observer.disconnect();
    this.observed = null;
    clearTimeout(this.timer);
    this.timer = undefined;
  }

  /** Watch Gmail's main area, the container its views are drawn in; the whole page until Gmail has drawn it. */
  private attach(): void {
    const main = this.page.querySelector('div[role="main"]');
    const target: Element | null = main?.parentElement ?? main ?? this.page.body;
    if (target === null || target === this.observed || this.stopped) {
      return;
    }
    this.observer.disconnect();
    this.observer.observe(target, { childList: true, subtree: true });
    this.observed = target;
  }

  private async read(): Promise<void> {
    if (this.stopped || this.page.hidden) {
      return;
    }
    if (this.reading) {
      this.again = true; // a change while the bridge is asked: read once more after
      return;
    }
    this.reading = true;
    this.lastRead = Date.now();
    const again = this.again;
    this.again = false;
    try {
      this.attach();
      await this.tell();
    } finally {
      this.reading = false;
      if (again || this.again) {
        this.again = false;
        this.soon();
      }
    }
  }

  private async tell(): Promise<void> {
    if (Date.now() - this.askedAt >= ASK_MS) {
      this.heard(await this.bridge.watch());
    }
    const watch = this.watch;
    if (watch === null || this.stopped) {
      return;
    }
    const fresh = shownIds(this.page, watch.senders).filter((id) => !this.told.has(id));
    const ids = fresh.slice(0, PER_MESSAGE);
    if (ids.length === 0) {
      return;
    }
    const answer = await this.bridge.seen(ids);
    this.heard(answer);
    if (answer === null) {
      return; // not kept: told again once the bridge takes messages from this tab
    }
    if (this.told.size + ids.length > TOLD_KEPT) {
      this.told.clear();
    }
    for (const id of ids) {
      this.told.add(id);
    }
    this.again ||= fresh.length > ids.length;
  }

  private heard(watch: Watch | null): void {
    this.watch = watch;
    this.askedAt = Date.now();
  }
}
