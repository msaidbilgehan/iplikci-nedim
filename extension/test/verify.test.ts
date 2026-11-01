import { describe, expect, it } from "vitest";

import type { Fetcher } from "../src/gmail/http";
import { type Environment, PACE_MS, verify } from "../src/verify/run";
import { ADDRESS, IK, SUBJECT, feedXml, gmailPage, originalPage, rawMessage, threadList } from "./fixtures";

const BANK = 1799999999999999999n;
const OLD = 0x18f0a1b2c3d4e5f6n;

type Answers = Record<"feed" | "feedAgain" | "app" | "original" | "download" | "list" | "old", () => Response>;

const ok = (body: string) => () => new Response(body);
const status = (code: number) => () => new Response(null, { status: code });

/** A fake Gmail that answers by address and records every request. */
function fakeGmail(overrides: Partial<Answers> = {}) {
  const bankFeed = feedXml([
    { id: BANK, sender: "ekstre@garantibbva.com.tr" },
    { id: 5n, sender: "haber@example.org" },
  ]);
  const answers: Answers = {
    feed: ok(bankFeed),
    feedAgain: ok(bankFeed),
    app: ok(gmailPage(IK)),
    original: ok(originalPage(rawMessage({ from: "ekstre@garantibbva.com.tr" }), BANK)),
    download: ok(rawMessage({ from: "ekstre@garantibbva.com.tr" })),
    list: ok(threadList([OLD.toString(16)])),
    old: ok(originalPage(rawMessage({ from: "bilgi@isbank.com.tr" }), OLD)),
    ...overrides,
  };
  const requests: { url: string; init: RequestInit }[] = [];
  let feeds = 0;
  const fetcher: Fetcher = async (address, init) => {
    requests.push({ url: address, init });
    const url = new URL(address);
    const view = url.searchParams.get("view");
    if (url.pathname.endsWith("/feed/atom")) {
      return (feeds++ === 0 ? answers.feed : answers.feedAgain)();
    }
    if (view === "om") {
      return url.searchParams.get("permmsgid") === `msg-f:${OLD}` ? answers.old() : answers.original();
    }
    if (view === "att") {
      return answers.download();
    }
    if (view === "tl") {
      return answers.list();
    }
    return url.pathname === "/mail/u/0/" && url.search === "" ? answers.app() : new Response(null, { status: 404 });
  };
  return { fetcher, requests };
}

function environment(fetcher: Fetcher): { env: Environment; sleeps: number[] } {
  const sleeps: number[] = [];
  const env: Environment = {
    fetcher,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
    os: "win",
    browser: "Chrome 140",
    version: "0.1.0",
    now: () => new Date("2026-11-01T12:00:00Z"),
  };
  return { env, sleeps };
}

async function run(overrides: Partial<Answers> = {}) {
  const gmail = fakeGmail(overrides);
  const { env, sleeps } = environment(gmail.fetcher);
  const report = await verify(env, 0);
  return { report, requests: gmail.requests, sleeps, results: report.checks.map((check) => check.ok) };
}

describe("the ADR-0016 verification", () => {
  it("passes all four checks when Gmail answers as the layers expect", async () => {
    const { report, results } = await run();
    expect(results).toEqual([true, true, true, true]);
    expect(report.text).toContain("✓ 1. Gelen kutusu akışı");
    expect(report.text).toContain("En üstteki Authentication-Results'ı Gmail (mx.google.com) eklemiş; DMARC From alan adı");
    expect(report.text).toContain("İleti indirildikten sonra da okunmamış duruyor.");
    expect(report.text).toContain("Bulunan ilk ileti indirildi; gönderen isbank.com.tr.");
    expect(report.text).toContain("Windows · Chrome 140 · eklenti 0.1.0");
  });

  it("lets no address, subject, message text or account key out", async () => {
    const { report } = await run();
    const everything = JSON.stringify(report);
    for (const secret of [ADDRESS, SUBJECT, "müşterimiz", "ekstreniz", IK, "example.org"]) {
      expect(everything).not.toContain(secret);
    }
  });

  it("asks only Gmail, only with GETs, one request at a time and a second apart", async () => {
    const { requests, sleeps } = await run();
    expect(requests.every((r) => r.url.startsWith("https://mail.google.com/mail/u/0/"))).toBe(true);
    expect(requests.every((r) => r.init.method === "GET" && r.init.credentials === "include")).toBe(true);
    expect(requests).toHaveLength(7);
    expect(sleeps).toHaveLength(requests.length - 1);
    expect(sleeps.every((ms) => ms >= PACE_MS)).toBe(true);
  });

  it("fails the second check when downloading marks the message read", async () => {
    const { report, results } = await run({ feedAgain: ok(feedXml([{ id: 5n, sender: "haber@example.org" }])) });
    expect(results[1]).toBe(false);
    expect(report.checks[1]?.lines).toContain("İleti akıştan düştü: okundu sayılmış olabilir.");
  });

  it("fails the second check when DMARC did not pass", async () => {
    const raw = rawMessage({ from: "ekstre@garantibbva.com.tr", authentication: "mx.google.com; dmarc=fail header.from=garantibbva.com.tr" });
    const { report, results } = await run({ original: ok(originalPage(raw, BANK)) });
    expect(results[1]).toBe(false);
    expect(report.text).toContain("DMARC geçmemiş ya da hiç denenmemiş");
  });

  it("says when the browser has no Gmail session and leaves the second check untried", async () => {
    const { report, results } = await run({ feed: status(302) });
    expect(results.slice(0, 2)).toEqual([false, null]);
    expect(report.checks[0]?.lines[0]).toContain("Gmail başka bir adrese yönlendirdi");
  });

  it("tries an unread message of another sender when no bank's is unread, without naming the sender", async () => {
    const other = rawMessage({ from: "haber@example.org" });
    const { report, results } = await run({
      feed: ok(feedXml([{ id: 5n, sender: "haber@example.org" }])),
      feedAgain: ok(feedXml([{ id: 5n, sender: "haber@example.org" }])),
      original: ok(originalPage(other, 5n)),
    });
    expect(results[1]).toBe(true);
    expect(report.checks[1]?.lines).toContain("Okunmamış banka iletisi yok; deneme en yeni okunmamış iletiyle yapıldı.");
    expect(report.text).not.toContain("example.org");
  });

  it("fails the third check when the thread list no longer answers", async () => {
    const { report, results } = await run({ list: status(404) });
    expect(results[2]).toBe(false);
    expect(report.checks[2]?.lines[0]).toContain("Gmail 404 yanıtı verdi.");
  });

  it("cannot try the second and third checks without an unread message and without the account key", async () => {
    const { report, results } = await run({ feed: ok(feedXml([])), app: ok("<html></html>") });
    expect(results).toEqual([null, null, null, true]);
    expect(report.text).toContain("– (denenemedi) 2. Ham ileti");
    expect(report.text).toContain("Hesap anahtarı (ik) Gmail sayfasında bulunamadı.");
  });

  it("reports a page whose shape changed as a format error", async () => {
    const { report, results } = await run({ original: ok("<html><body>Yeni tasarım</body></html>") });
    expect(results[1]).toBe(false);
    expect(report.text).toContain('"Orijinali göster" sayfasında iletinin metni bulunamadı.');
  });
});
