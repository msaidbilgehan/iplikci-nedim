/**
 * The fallback for layer 2 (ADR-0016): Gmail's thread-list address no longer answers, so the history is read from
 * the conversation list of a Gmail search shown in a tab of its own ("Gmail'de eksikleri tara"). The collector runs
 * in that tab (chrome.scripting.executeScript) and reads only ids from the visible list: no subject, address or text.
 * Gmail's page is not documented: rows without the ids it knows are a format error.
 *
 * Opening a conversation would mark its messages read, so the scan never opens one. The list names a conversation's
 * first message (the conversation's id) and its last; the messages between them stay out of reach and are counted.
 */

import { ORIGIN } from "./http";

/** A conversation as the list shows it: Gmail's ids in hexadecimal, and how many messages it holds (0: unknown). */
export interface Conversation {
  readonly thread: string;
  readonly last: string;
  readonly count: number;
}

export interface ListPage {
  /** The visible list's conversations, top to bottom. */
  readonly conversations: readonly Conversation[];
  /** Rows of the list without the ids the collector knows: Gmail changed its page. */
  readonly unknownRows: number;
  /** Whether the list moved on from the page before and stopped changing before the wait ran out. */
  readonly settled: boolean;
}

/** Gmail's search for the listed senders' messages from the start day on (YYYY-MM-DD; "" for all). */
export function searchQuery(senders: readonly string[], startDay: string): string {
  const from = `from:(${senders.join(" OR ")})`;
  return startDay === "" ? from : `${from} after:${startDay.replaceAll("-", "/")}`;
}

/** The address part Gmail's page shows a search's page under. */
export function searchHash(query: string, page: number): string {
  return `#search/${encodeURIComponent(query)}${page > 1 ? `/p${page}` : ""}`;
}

export function searchUrl(account: number, query: string): string {
  return `${ORIGIN}/mail/u/${account}/${searchHash(query, 1)}`;
}

/** Whether a value the page returned is a ListPage: the page is not trusted to answer in shape. */
export function isListPage(value: unknown): value is ListPage {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { conversations, unknownRows, settled } = value as Record<string, unknown>;
  return (
    Array.isArray(conversations) &&
    conversations.every(
      (c: unknown) =>
        typeof c === "object" &&
        c !== null &&
        HEX.test(String((c as Record<string, unknown>)["thread"])) &&
        HEX.test(String((c as Record<string, unknown>)["last"])) &&
        Number.isInteger((c as Record<string, unknown>)["count"])
    ) &&
    Number.isInteger(unknownRows) &&
    typeof settled === "boolean"
  );
}

const HEX = /^[0-9a-f]{1,16}$/;

/**
 * Runs in the Gmail tab: waits until the visible conversation list shows something other than `before` (the first
 * conversation of the page before; "" on the first page) and stops changing, then reads it; after `waitMs` it reads
 * what there is. Self-contained, as it is copied into the page: no import, no outer name.
 */
export async function collectList(waitMs: number, before: string): Promise<ListPage> {
  const hex = /^[0-9a-f]{1,16}$/;
  const pause = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));
  const read = (): ListPage => {
    // A conversation's row has a checkbox; rows of the lists Gmail keeps hidden behind the search have no box.
    const rows = Array.from(document.querySelectorAll('div[role="main"] tr')).filter(
      (row) => row.getClientRects().length > 0 && row.querySelector('[role="checkbox"]') !== null,
    );
    const conversations: Conversation[] = [];
    let unknownRows = 0;
    for (const row of rows) {
      const marked = row.querySelector("[data-legacy-thread-id]");
      const thread = marked?.getAttribute("data-legacy-thread-id") ?? "";
      if (!hex.test(thread)) {
        unknownRows += 1;
        continue;
      }
      const last = marked?.getAttribute("data-legacy-last-message-id") ?? "";
      const count = Number.parseInt((row.querySelector(".bx0")?.textContent ?? "").replace(/\D/g, ""), 10);
      conversations.push({ thread, last: hex.test(last) ? last : thread, count: count > 0 ? count : 0 });
    }
    return { conversations, unknownRows, settled: false };
  };
  const deadline = Date.now() + waitMs;
  let previous = "";
  for (;;) {
    const page = read();
    const signature = `${page.conversations.map((c) => c.thread).join(",")}|${page.unknownRows}`;
    const shown = page.conversations.length + page.unknownRows > 0;
    const movedOn = (page.conversations[0]?.thread ?? "") !== before;
    if (shown && movedOn && signature === previous) {
      return { ...page, settled: true };
    }
    if (Date.now() >= deadline) {
      return page;
    }
    previous = signature;
    await pause(500);
  }
}
