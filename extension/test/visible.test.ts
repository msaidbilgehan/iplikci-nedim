// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ASK_MS,
  type Bridge,
  PAUSE_MS,
  PER_MESSAGE,
  type Watch,
  accountOf,
  asWatch,
  shownIds,
  watchGmail,
} from "../src/gmail/visible";

const BANK = "ekstre@teb.com.tr";
const OTHER = "haber@example.org";
const SENDERS = ["teb.com.tr", "isbank.com.tr"];
const WATCH: Watch = { senders: SENDERS };

/**
 * A conversation row as Gmail's list draws it: the senders' addresses, the subject's span with the conversation's ids
 * (decimal and legacy hexadecimal) and the last message's, a snippet, and the read state's classes ("zA yO" read,
 * "zA zE" unread). Synthetic values only.
 */
function row(thread: bigint, options: { last?: bigint; from?: readonly string[]; classes?: string } = {}): string {
  const from = (options.from ?? [BANK])
    .map((address) => `<span class="yP" email="${address}" name="Banka Bildirim">Banka Bildirim</span>`)
    .join(", ");
  const last = (options.last ?? thread).toString(16);
  return `<tr class="${options.classes ?? "zA yO"}"><td><div role="checkbox"></div></td>
    <td><div class="yW">${from}</div></td><td><span class="bqe" data-thread-id="#thread-f:${thread}"
    data-legacy-thread-id="${thread.toString(16)}" data-legacy-last-message-id="${last}">Hesap Özetiniz Hazır</span>
    <span class="y2"> - Sayın müşterimiz, ekstreniz ektedir.</span></td></tr>`;
}

/** A message of an opened conversation: its ids and its sender's name and address above the text. */
function message(id: bigint, from = BANK): string {
  return `<div class="adn ads" data-message-id="#msg-f:${id}" data-legacy-message-id="${id.toString(16)}">
    <h3 class="iw"><span class="gD" email="${from}" name="Banka Bildirim">Banka Bildirim</span></h3>
    <div class="a3s">Sayın müşterimiz, kartınızın ekstresi ektedir.</div></div>`;
}

/** Gmail's page: its main area (rows, or an opened conversation) inside the views' container, hidden parts too. */
function show(main: string, hidden = ""): void {
  document.body.innerHTML = `<div role="navigation">Gelen Kutusu</div>
    <div class="aeF"><div class="nH" role="main"><table hidden><tbody>${hidden}</tbody></table>
    <table><tbody>${main}</tbody></table></div></div>`;
}

let hidden = false;

beforeEach(() => {
  hidden = false;
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  // jsdom lays nothing out: an element counts as shown unless it sits in something hidden.
  vi.spyOn(Element.prototype, "getClientRects").mockImplementation(function (this: Element) {
    return (this.closest("[hidden]") === null ? [new DOMRect()] : []) as unknown as DOMRectList;
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("what the content script reads of Gmail's page", () => {
  it("names a listed sender's conversation rows by their first and last message, read or not", () => {
    show(
      row(1_000n) + // one message, read
        row(2_000n, { last: 2_300n, classes: "zA zE" }) + // three messages, unread
        row(3_000n, { from: [OTHER] }),
    );
    expect(shownIds(document, SENDERS)).toEqual(["1000", "2000", "2300"]);
  });

  it("takes a sender's subdomain and the bank among a conversation's senders", () => {
    show(row(1_000n, { from: ["bilgi@posta.isbank.com.tr"] }) + row(2_000n, { from: ["ben@example.com", BANK] }));
    expect(shownIds(document, SENDERS)).toEqual(["1000", "2000"]);
  });

  it("leaves out other senders, the rows Gmail keeps hidden and rows it does not know", () => {
    const draft = row(4_000n).replace("#thread-f:4000", "#thread-a:r-12345");
    const nameless = row(5_000n, { from: ["Banka Bildirim"] });
    const unmarked = row(6_000n).replace(/data-thread-id="[^"]*"/, "");
    show(row(1_000n, { from: [OTHER] }) + draft + nameless + unmarked, row(7_000n));
    expect(shownIds(document, SENDERS)).toEqual([]);
    expect(shownIds(document, [])).toEqual([]);
  });

  it("takes the last message's legacy id only when it is one", () => {
    show(row(1_000n).replace(/data-legacy-last-message-id="[^"]*"/, 'data-legacy-last-message-id="<b>"'));
    expect(shownIds(document, SENDERS)).toEqual(["1000"]);
  });

  it("names the messages of an opened conversation by their senders", () => {
    show(`<tr><td>${message(1_000n)}${message(1_100n, OTHER)}${message(1_200n)}</td></tr>`);
    expect(shownIds(document, SENDERS)).toEqual(["1000", "1200"]);
  });

  it("knows the Google account of a Gmail page by its address, and no other page", () => {
    expect(accountOf("https://mail.google.com/mail/u/0/#inbox")).toBe(0);
    expect(accountOf("https://mail.google.com/mail/u/3/#label/Banka/FMfcgz")).toBe(3);
    for (const other of [
      "https://mail.google.com/mail/#inbox", // no account in the address
      "https://mail.google.com/mail/b/123/u/0/", // a delegated mailbox
      "https://mail.google.com.example.org/mail/u/0/",
      "http://mail.google.com/mail/u/0/",
      "chrome-extension://abc/options.html",
      "bir adres değil",
    ]) {
      expect(accountOf(other)).toBeNull();
    }
  });

  it("takes from the service worker only a list of domains to look for", () => {
    expect(asWatch({ senders: SENDERS })).toEqual(WATCH);
    expect(asWatch({ senders: [] })).toEqual({ senders: [] });
    for (const bad of [null, "x", { senders: "teb.com.tr" }, { senders: ["<b>teb</b>"] }, { senders: [1] }]) {
      expect(asWatch(bad)).toBeNull();
    }
  });
});

/**
 * The service worker as the content script sees it: what it looks for, and what it was told. It answers a telling as
 * it answers the question, unless told otherwise: null when it did not keep the ids.
 */
function fakeBridge(first: Watch | null = WATCH) {
  let answer = first;
  let keeps = true;
  const told: string[][] = [];
  let asked = 0;
  const bridge: Bridge = {
    async watch() {
      asked += 1;
      return answer;
    },
    async seen(ids) {
      told.push([...ids]);
      return keeps ? answer : null;
    },
  };
  return {
    bridge,
    told,
    asked: () => asked,
    answer: (next: Watch | null) => {
      answer = next;
    },
    keeps: (next: boolean) => {
      keeps = next;
    },
  };
}

function append(rows: string): void {
  document.querySelector("div[role='main'] table:not([hidden]) tbody")?.insertAdjacentHTML("beforeend", rows);
}

describe("watching an open Gmail tab", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("tells the listed senders' messages the tab shows at once, and each only once", async () => {
    show(row(1_000n) + row(2_000n, { from: [OTHER] }));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.told).toEqual([["1000"]]);
    append(row(3_000n, { last: 3_100n }));
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"], ["3000", "3100"]]); // what was told is not told again
    expect(fake.asked()).toBe(1); // what to look for holds for a while
    watcher.stop();
  });

  it("reads the page at most every five seconds, however often Gmail changes it", async () => {
    show(row(1_000n));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    for (let n = 1n; n <= 8n; n += 1n) {
      append(row(1_000n + n));
      await vi.advanceTimersByTimeAsync(500);
    }
    expect(fake.told).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toHaveLength(2);
    expect(fake.told[1]).toEqual(["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008"]);
    watcher.stop();
  });

  it("reads nothing while the tab is hidden, and reads at once when it is shown again", async () => {
    hidden = true;
    show(row(1_000n));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    append(row(2_000n));
    await vi.advanceTimersByTimeAsync(3 * PAUSE_MS);
    expect([fake.asked(), fake.told]).toEqual([0, []]);
    hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.told).toEqual([["1000", "2000"]]);
    hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    append(row(3_000n));
    await vi.advanceTimersByTimeAsync(3 * PAUSE_MS);
    expect(fake.told).toHaveLength(1);
    watcher.stop();
  });

  it("reads when the address changes, and once more after the pause as Gmail draws the view late", async () => {
    show(row(1_000n));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await vi.advanceTimersByTimeAsync(0);
    // Gmail draws the opened conversation in a page of its own: nothing the watcher watched changed.
    const opened = `${message(1_100n)}${message(1_200n, OTHER)}`;
    document.body.innerHTML = `<div class="aeF"><div role="main">${opened}</div></div>`;
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"], ["1100"]]);
    watcher.stop();
  });

  it("waits for Gmail to draw its main area, then watches it", async () => {
    document.body.innerHTML = '<div class="yukleniyor">Yükleniyor…</div>';
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    expect(fake.told).toEqual([]);
    show(row(1_000n));
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"]]);
    append(row(2_000n)); // the main area is watched now
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"], ["2000"]]);
    watcher.stop();
  });

  it("tells nothing of a page without a listed sender's message", async () => {
    show(row(1_000n, { from: [OTHER] }) + row(2_000n, { from: ["ben@example.com"] }));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect([fake.asked(), fake.told]).toEqual([1, []]);
    watcher.stop();
  });

  it("reads nothing while the bridge takes nothing from the tab, and asks again a minute later", async () => {
    show(row(1_000n));
    const fake = fakeBridge(null);
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    for (let n = 1n; n <= 4n; n += 1n) {
      append(row(1_000n + n, { from: [OTHER] }));
      await vi.advanceTimersByTimeAsync(PAUSE_MS);
    }
    expect([fake.asked(), fake.told]).toEqual([1, []]);
    fake.answer(WATCH);
    await vi.advanceTimersByTimeAsync(ASK_MS);
    append(row(2_000n));
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.asked()).toBe(2);
    expect(fake.told).toEqual([["1000", "2000"]]);
    watcher.stop();
  });

  it("tells again what the bridge did not keep, once it takes messages from the tab again", async () => {
    show(row(1_000n));
    const fake = fakeBridge();
    fake.keeps(false); // a scan began between the question and the telling
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    append(row(2_000n));
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"]]); // not kept: nothing more until the bridge is asked again
    fake.keeps(true);
    await vi.advanceTimersByTimeAsync(ASK_MS);
    append(row(3_000n));
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told).toEqual([["1000"], ["1000", "2000", "3000"]]);
    expect(fake.asked()).toBe(2);
    watcher.stop();
  });

  it("tells a long page in parts", async () => {
    let rows = "";
    for (let n = 1n; n <= BigInt(PER_MESSAGE) + 10n; n += 1n) {
      rows += row(1_000n + n);
    }
    show(rows);
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(PAUSE_MS);
    expect(fake.told.map((ids) => ids.length)).toEqual([PER_MESSAGE, 10]);
    watcher.stop();
  });

  it("stops watching when it is stopped", async () => {
    show(row(1_000n));
    const fake = fakeBridge();
    const watcher = watchGmail(document, fake.bridge);
    await vi.advanceTimersByTimeAsync(0);
    watcher.stop();
    append(row(2_000n));
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(3 * PAUSE_MS);
    expect(fake.told).toEqual([["1000"]]);
  });
});
