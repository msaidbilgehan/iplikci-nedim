import { describe, expect, it } from "vitest";

import { FormatError } from "../src/gmail/errors";
import { feedUrl, parseFeed, sameMessage } from "../src/gmail/feed";
import { HttpError, Redirected, get } from "../src/gmail/http";
import { NoRawText, originalUrl, parseOriginal } from "../src/gmail/original";
import { answerKind, decimalId, senderQuery, threadIds, threadListUrl } from "../src/gmail/search";
import { appUrl, parseAccountKey } from "../src/gmail/session";
import { attribute, decodeEntities, elements, text } from "../src/gmail/xml";
import { ADDRESS, IK, SUBJECT, feedXml, gmailPage, originalPage, rawMessage, threadList } from "./fixtures";

const BANK_ID = 1799999999999999999n;
const OTHER_ID = 1799999999999999000n;

describe("xml helpers", () => {
  it("decode named, decimal and hexadecimal references and keep unknown ones", () => {
    expect(decodeEntities("a &amp; b &lt;c&gt; &quot;d&quot; &#39;e&#x27; &#x130;&#305; &bogus;")).toBe(
      "a & b <c> \"d\" 'e' İı &bogus;",
    );
  });

  it("read elements, their text and attributes", () => {
    const xml = '<a><b x="1">one &amp; two</b><b>three</b></a><link rel="alternate" href="h?x=1&amp;y=2" />';
    expect(elements(xml, "b")).toEqual(["one &amp; two", "three"]);
    expect(text(xml, "b")).toBe("one & two");
    expect(text(xml, "missing")).toBe("");
    expect(attribute('<link rel="alternate" href="h?x=1&amp;y=2" />', "href")).toBe("h?x=1&y=2");
    expect(attribute("<link rel='x' />", "href")).toBeNull();
  });
});

describe("inbox feed (layer 1)", () => {
  it("lists every unread message with its ids and its sender's domain", () => {
    const feed = parseFeed(
      feedXml([
        { id: BANK_ID, sender: "ekstre@garantibbva.com.tr" },
        { id: OTHER_ID, sender: "Haber@Example.ORG" },
      ], 7),
    );
    expect(feed.unread).toBe(7);
    expect(feed.entries).toEqual([
      { id: BANK_ID.toString(), hexId: BANK_ID.toString(16), issued: "2026-10-31T09:00:00Z", senderDomain: "garantibbva.com.tr" },
      { id: OTHER_ID.toString(), hexId: OTHER_ID.toString(16), issued: "2026-10-31T09:00:00Z", senderDomain: "example.org" },
    ]);
    expect(feed.entries.every(sameMessage)).toBe(true);
  });

  it("keeps nothing of the user's address, the subject or the text", () => {
    const kept = JSON.stringify(parseFeed(feedXml([{ id: BANK_ID, sender: "ekstre@garantibbva.com.tr" }])));
    expect(kept).not.toContain(ADDRESS);
    expect(kept).not.toContain(SUBJECT);
    expect(kept).not.toContain("müşterimiz");
  });

  it("tells a link without a hexadecimal id", () => {
    const [entry] = parseFeed(feedXml([{ id: BANK_ID, sender: "a@teb.com.tr", hexInLink: false }])).entries;
    expect(entry?.hexId).toBe("");
    expect(entry && sameMessage(entry)).toBe(false);
  });

  it("refuses an answer that is not Gmail's Atom feed", () => {
    expect(() => parseFeed("<!DOCTYPE html><html>Sign in</html>")).toThrow(FormatError);
    expect(() => parseFeed(feedXml([]).replace("2004:", "2005:") + "<entry><id>tag:x</id></entry>")).toThrow(
      FormatError,
    );
  });

  it("reads the account's own feed", () => {
    expect(feedUrl(1)).toBe("https://mail.google.com/mail/u/1/feed/atom");
  });
});

describe("account key", () => {
  it("is the tenth item of the page's GLOBALS, past strings and nested arrays", () => {
    expect(parseAccountKey(gmailPage(IK))).toEqual({ ik: IK, where: "GLOBALS" });
  });

  it("falls back to a link that carries it", () => {
    expect(parseAccountKey('<a href="?ui=2&amp;ik=0f1e2d3c4b&amp;view=om">x</a>')).toEqual({
      ik: "0f1e2d3c4b",
      where: "bağlantı",
    });
    expect(parseAccountKey("<html>nothing</html>")).toBeNull();
    expect(appUrl(0)).toBe("https://mail.google.com/mail/u/0/");
  });
});

describe('"Show original" (layer 3)', () => {
  it("gives the raw message as it was, and the page's download link", () => {
    const raw = rawMessage({ from: "ekstre@garantibbva.com.tr" });
    const url = originalUrl(0, BANK_ID.toString(), IK);
    expect(url).toBe(`https://mail.google.com/mail/u/0/?ik=${IK}&view=om&permmsgid=msg-f%3A${BANK_ID}`);
    const original = parseOriginal(originalPage(raw, BANK_ID), url);
    expect(original.raw).toBe(raw);
    expect(original.download).toBe(
      `https://mail.google.com/mail/u/0/?ui=2&ik=${IK}&attid=0&permmsgid=msg-f:${BANK_ID}&view=att&disp=comp&safe=1&zw`,
    );
  });

  it("asks without the account key when there is none", () => {
    expect(originalUrl(2, "5", null)).toBe("https://mail.google.com/mail/u/2/?view=om&permmsgid=msg-f%3A5");
  });

  it("refuses a page without the message", () => {
    expect(() => parseOriginal("<html><pre>other</pre></html>", "https://mail.google.com/mail/u/0/")).toThrow(
      FormatError,
    );
    const page = parseOriginal(originalPage("From: a@b.c", 1n, false), "https://mail.google.com/mail/u/0/");
    expect(page.download).toBeNull();
  });

  it("tells what a page without the message showed, but no text of it except its title, masked", () => {
    const page = originalPage("From: a@b.c", 1n)
      .replace(/<pre[\s\S]*<\/pre>/, "<p>Çok büyük</p>")
      .replace("Original Message", "Ileti 12345 kisi@example.org Gmail");
    let error: unknown;
    try {
      parseOriginal(page, "https://mail.google.com/mail/u/0/");
    } catch (thrown) {
      error = thrown;
    }
    expect(error).toBeInstanceOf(NoRawText);
    expect((error as NoRawText).traits).toEqual({
      length: page.length,
      title: "Ileti ##### Gmail",
      download: true,
      rawId: false,
    });
  });
});

describe("full search (layer 2)", () => {
  it("asks the thread list for the senders' read and archived messages", () => {
    const query = senderQuery(["teb.com.tr", "isbank.com.tr"], "-in:inbox -is:unread");
    expect(query).toBe("from:(teb.com.tr OR isbank.com.tr) -in:inbox -is:unread");
    const url = new URL(threadListUrl(0, IK, query));
    expect(url.origin + url.pathname).toBe("https://mail.google.com/mail/u/0/");
    expect(Object.fromEntries(url.searchParams)).toMatchObject({ ik: IK, view: "tl", search: "query", q: query });
  });

  it("finds the thread ids in a data answer and tells answers apart", () => {
    const ids = ["18f0a1b2c3d4e5f6", "18f0a1b2c3d4e5f7"];
    expect(threadIds(threadList(ids))).toEqual(ids);
    expect(answerKind(threadList(ids))).toBe("json");
    expect(answerKind("<!DOCTYPE html><html></html>")).toBe("html");
    expect(answerKind("Not Found")).toBe("other");
    expect(decimalId("18f0a1b2c3d4e5f6")).toBe(BigInt("0x18f0a1b2c3d4e5f6").toString());
  });
});

describe("requests", () => {
  it("are GETs with the browser's cookies that never follow a redirect", async () => {
    const seen: RequestInit[] = [];
    await get(async (_url, init) => {
      seen.push(init);
      return new Response("ok");
    }, "https://mail.google.com/mail/u/0/feed/atom");
    expect(seen).toEqual([{ method: "GET", credentials: "include", redirect: "manual", cache: "no-store" }]);
  });

  it("turn a redirect and an error status into errors and go nowhere but Gmail", async () => {
    const answer = (status: number) => async () => new Response(null, { status });
    await expect(get(answer(302), "https://mail.google.com/x")).rejects.toThrow(Redirected);
    await expect(get(answer(404), "https://mail.google.com/x")).rejects.toThrow(HttpError);
    await expect(get(answer(200), "https://example.com/")).rejects.toThrow(/not a Gmail address/);
  });
});
