// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { collectList, isListPage, searchHash, searchQuery, searchUrl } from "../src/gmail/list";

/** A conversation row as Gmail's list draws it: a checkbox, the sender cell's count, the subject's ids. */
function row(thread: string, last = thread, count = 0): string {
  const badge = count > 0 ? `<span class="bx0">${count}</span>` : "";
  const ids = `data-legacy-thread-id="${thread}" data-legacy-last-message-id="${last}"`;
  return `<tr><td><div role="checkbox"></div></td><td>Banka ${badge}</td>
    <td><span data-thread-id="#thread-f:1" ${ids}>…</span></td></tr>`;
}

function show(rows: string, hidden = ""): void {
  document.body.innerHTML = `
    <table><tr><td>araç çubuğu</td></tr></table>
    <div role="main">
      <table hidden><tbody>${hidden}</tbody></table>
      <table><tbody>${rows}</tbody></table>
    </div>`;
}

beforeEach(() => {
  vi.useFakeTimers();
  // jsdom lays nothing out: an element counts as shown unless it sits in something hidden.
  vi.spyOn(Element.prototype, "getClientRects").mockImplementation(function (this: Element) {
    return (this.closest("[hidden]") === null ? [new DOMRect()] : []) as unknown as DOMRectList;
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function collected(waitMs: number, before: string) {
  const page = collectList(waitMs, before);
  await vi.advanceTimersByTimeAsync(waitMs + 1000);
  return page;
}

describe("collectList", () => {
  it("reads the ids of the shown conversations only, with how many messages each holds", async () => {
    show(row("18f0a1") + row("18f0b2", "18f0c3", 3), row("aaaa"));
    expect(await collected(5000, "")).toEqual({
      conversations: [
        { thread: "18f0a1", last: "18f0a1", count: 0 },
        { thread: "18f0b2", last: "18f0c3", count: 3 },
      ],
      unknownRows: 0,
      settled: true,
      main: true,
      rows: 2,
    });
  });

  it("counts the rows it cannot read: Gmail changed its page", async () => {
    show('<tr><td><div role="checkbox"></div></td><td>yeni biçim</td></tr>');
    const page = await collected(5000, "");
    expect([page.conversations, page.unknownRows]).toEqual([[], 1]);
  });

  it("waits until the list moves on from the page before and stops changing", async () => {
    show(row("18f0a1"));
    const page = collectList(10_000, "18f0a1");
    await vi.advanceTimersByTimeAsync(1200);
    show(row("17e0a1") + row("17e0b2"));
    await vi.advanceTimersByTimeAsync(2000);
    expect((await page).conversations.map((c) => c.thread)).toEqual(["17e0a1", "17e0b2"]);
  });

  it("gives up after the wait with what it has, not settled", async () => {
    show(row("18f0a1"));
    const page = await collected(3000, "18f0a1");
    expect([page.settled, page.conversations.length]).toEqual([false, 1]);
  });
});

describe("the search", () => {
  it("asks for the listed senders' messages from the start day, page by page", () => {
    const query = searchQuery(["teb.com.tr", "isbank.com.tr"], "2025-01-01");
    expect(query).toBe("from:(teb.com.tr OR isbank.com.tr) after:2025/01/01");
    expect(searchQuery(["teb.com.tr"], "")).toBe("from:(teb.com.tr)");
    expect(searchHash(query, 1)).toBe(`#search/${encodeURIComponent(query)}`);
    expect(searchHash(query, 3)).toBe(`#search/${encodeURIComponent(query)}/p3`);
    expect(searchUrl(1, query)).toBe(`https://mail.google.com/mail/u/1/#search/${encodeURIComponent(query)}`);
  });

  it("takes nothing from the page that is not a list in shape", () => {
    const list = (thread: string) => ({
      conversations: [{ thread, last: "1", count: 0 }],
      unknownRows: 0,
      settled: true,
      main: true,
      rows: 1,
    });
    expect(isListPage(list("18f0a1"))).toBe(true);
    for (const bad of [null, "x", list("<b>")]) {
      expect(isListPage(bad)).toBe(false);
    }
  });
});
