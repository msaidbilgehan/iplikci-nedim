import { describe, expect, it } from "vitest";

import type { Fetcher as GmailFetcher } from "../src/gmail/http";
import type { ListPage } from "../src/gmail/list";
import { expectedProof } from "../src/bridge/proof";
import { NotGmail, type ScanEnvironment, type TabDriver, TabGone, scanGmail } from "../src/bridge/scan";
import { type Fetcher, type Paired, SERVICE } from "../src/bridge/service";
import { type ScanSummary, type Store, memoryStore } from "../src/bridge/state";
import { IK, gmailPage, originalPage, rawMessage } from "./fixtures";

const PAIRED: Paired = { id: "k1", token: "belirtec-123" };
const SENDERS = ["teb.com.tr", "isbank.com.tr"];

/** Gmail's search shown page by page; going past the last page leaves the last one on screen, as Gmail does. */
function fakeTabs(pages: readonly ListPage[], trouble?: Error) {
  const calls: string[] = [];
  let shown = 0;
  const tabs: TabDriver = {
    async open(url) {
      calls.push(`open ${url}`);
      return 7;
    },
    async collect(_tab, _waitMs, before) {
      if (trouble !== undefined) {
        throw trouble;
      }
      calls.push(`collect after "${before}"`);
      return pages[Math.min(shown, pages.length - 1)] ?? empty();
    },
    async go(_tab, hash) {
      calls.push(`go ${hash.slice(hash.lastIndexOf("/"))}`);
      shown += 1;
    },
    async close() {
      calls.push("close");
    },
  };
  return { tabs, calls };
}

function page(...conversations: Array<[string, string, number]>): ListPage {
  const listed = conversations.map(([thread, last, count]) => ({ thread, last, count }));
  return { conversations: listed, unknownRows: 0, settled: true, main: true, rows: listed.length };
}

function empty(shown: Partial<ListPage> = {}): ListPage {
  return { conversations: [], unknownRows: 0, settled: false, main: true, rows: 0, ...shown };
}

/** The service: proves itself, says where delivery stands, which ids it holds, and records what it is given. */
function fakeService(held: ReadonlySet<string> = new Set(), down = false, older = false) {
  const delivered: Array<{ id: string; date: string | null }> = [];
  const alarms: unknown[] = [];
  const asked: string[][] = [];
  const fetcher: Fetcher = async (address, init) => {
    if (down) {
      throw new TypeError("Failed to fetch");
    }
    const url = new URL(address);
    expect(url.origin).toBe(SERVICE);
    switch (url.pathname) {
      case "/api/bridge/hello":
        return Response.json({ proof: await expectedProof(PAIRED.token, url.searchParams.get("nonce") ?? "") });
      case "/api/ingest/mail/cursor":
        return Response.json({ last_id: "", last_date: "", start_day: "2026-01-01", senders: SENDERS });
      case "/api/ingest/mail/known": {
        if (older) {
          return Response.json({ code: "http_404", title: "Bulunamadı." }, { status: 404 });
        }
        const ids = (JSON.parse(String(init.body)) as { ids: string[] }).ids;
        asked.push(ids);
        return Response.json({ missing: ids.filter((id) => !held.has(id)) });
      }
      case "/api/ingest/mail": {
        const headers = new Headers(init.headers);
        delivered.push({ id: headers.get("X-Gmail-Id") ?? "", date: headers.get("X-Gmail-Date") });
        return Response.json({ taken: "stored", documents: 1 });
      }
      case "/api/ingest/mail/alarm":
        alarms.push(JSON.parse(String(init.body)));
        return Response.json({ news: true });
      default:
        return new Response(null, { status: 404 });
    }
  };
  return { fetcher, delivered, alarms, asked };
}

/** Gmail: its page with the account key, and every message's "Show original". */
function fakeGmail() {
  const requests: string[] = [];
  const fetcher: GmailFetcher = async (address) => {
    requests.push(address);
    const url = new URL(address);
    if (url.searchParams.get("view") === "om") {
      const id = (url.searchParams.get("permmsgid") ?? "").replace("msg-f:", "");
      return new Response(originalPage(rawMessage({ from: "ekstre@teb.com.tr" }), BigInt(id)));
    }
    return new Response(gmailPage(IK));
  };
  return { fetcher, requests };
}

interface Setup {
  readonly service?: Fetcher;
  readonly gmail?: GmailFetcher;
  readonly store?: Store;
  readonly version?: string;
}

/** Scan with tabs, the service and Gmail faked; a paired store unless one is given. */
function scan(tabs: TabDriver, setup: Setup = {}): Promise<ScanSummary> {
  const env: ScanEnvironment = {
    tabs,
    service: setup.service ?? fakeService().fetcher,
    gmail: setup.gmail ?? fakeGmail().fetcher,
    sleep: async () => undefined,
    now: () => new Date("2026-11-01T10:00:00Z"),
    version: setup.version ?? "0.3.0",
  };
  return scanGmail(env, setup.store ?? memoryStore({ paired: PAIRED }));
}

describe("scanGmail", () => {
  it("delivers what the service lacks of the conversations found page by page, oldest first, dateless", async () => {
    // 0x10 = 16, 0x20 = 32 (held already), 0x30 = 48, 0x40 = 64
    const { tabs, calls } = fakeTabs([page(["30", "30", 0], ["20", "40", 5]), page(["10", "10", 0])]);
    const service = fakeService(new Set(["32"]));
    const gmail = fakeGmail();
    const store = memoryStore({ paired: PAIRED });
    const summary = await scan(tabs, { service: service.fetcher, gmail: gmail.fetcher, store });
    const query = encodeURIComponent("from:(teb.com.tr OR isbank.com.tr) after:2026/01/01");
    expect(calls).toEqual([
      `open https://mail.google.com/mail/u/0/#search/${query}`,
      'collect after ""',
      "go /p2",
      'collect after "30"', // shorter than the page before: the last
      "close",
    ]);
    expect(service.asked).toEqual([["16", "32", "48", "64"]]);
    expect(service.delivered).toEqual([
      { id: "16", date: "" },
      { id: "48", date: "" },
      { id: "64", date: "" },
    ]);
    expect(gmail.requests.filter((r) => r.includes("view=om"))).toHaveLength(3);
    expect(summary).toMatchObject({ phase: "done", pages: 2, conversations: 3, found: 4, missing: 3, delivered: 3 });
    expect(summary.between).toBe(3); // the five-message conversation's three in the middle
    expect(summary.detail).toBe(
      "Gmail'de listedeki bankalardan 4 ileti bulundu; eksik 3 iletiden 3 tanesi teslim edildi. Konuşmaların " +
        "ortasındaki 3 ileti bu yolla alınamaz: konuşmayı açmak iletilerini okundu yapar.",
    );
    expect(store.current.scan).toEqual(summary);
  });

  it("ends where a page does not move on, as Gmail keeps showing its last page", async () => {
    const { tabs, calls } = fakeTabs([page(["30", "30", 0]), page(["10", "10", 0])]);
    const summary = await scan(tabs);
    expect(calls.slice(1, -1)).toEqual([
      'collect after ""',
      "go /p2",
      'collect after "30"',
      "go /p3",
      'collect after "10"',
    ]);
    expect([summary.pages, summary.conversations]).toEqual([2, 2]);
  });

  it("downloads nothing when the service holds every message", async () => {
    const gmail = fakeGmail();
    const summary = await scan(fakeTabs([page(["10", "10", 0])]).tabs, {
      service: fakeService(new Set(["16"])).fetcher,
      gmail: gmail.fetcher,
    });
    expect(summary.detail).toBe("Gmail'de listedeki bankalardan 1 ileti bulundu; hepsi İplikçi Nedim'de.");
    expect(gmail.requests).toEqual([]);
  });

  it("stops on a list it cannot read, tells the service once, and waits for an update", async () => {
    const { tabs, calls } = fakeTabs([empty({ unknownRows: 3, rows: 3, settled: true })]);
    const service = fakeService();
    const store = memoryStore({ paired: PAIRED });
    const summary = await scan(tabs, { service: service.fetcher, store });
    expect(summary.phase).toBe("stopped");
    expect(summary.detail).toBe("Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi bekleniyor.");
    expect(service.alarms).toEqual([{ layer: 2, version: "0.3.0" }]);
    expect(calls.at(-1)).toBe("close");
    const again = fakeTabs([page(["10", "10", 0])]);
    await scan(again.tabs, { service: service.fetcher, store });
    expect(again.calls).toEqual([]); // no tab until a newer version
    const updated = fakeTabs([page(["10", "10", 0])]);
    expect((await scan(updated.tabs, { service: service.fetcher, store, version: "0.3.1" })).phase).toBe("done");
  });

  it("tells an empty search from a page it could not read", async () => {
    expect((await scan(fakeTabs([empty()]).tabs)).detail).toBe(
      "Gmail'in aramasında listedeki bankalardan ileti çıkmadı.",
    );
    expect((await scan(fakeTabs([empty({ rows: 4 })]).tabs)).detail).toBe(
      "Gmail'in arama sayfasında 4 satır vardı ama hiçbiri bir konuşma gibi okunamadı; eklentinin güncellenmesi " +
        "gerekebilir.",
    );
    expect((await scan(fakeTabs([empty({ main: false })]).tabs)).detail).toBe(
      "Gmail sekmede açılamadı (ağ bağlantısı olmayabilir); tarama durdu, yeniden başlatılabilir.",
    );
  });

  it("says when the chosen Google account is signed out or the tab was closed", async () => {
    const signedOut = fakeTabs([], new NotGmail("x"));
    expect((await scan(signedOut.tabs)).detail).toBe(
      "Bu tarayıcıda seçilen Gmail hesabına girilmemiş; Gmail'e girip taramayı yeniden başlatın.",
    );
    expect(signedOut.calls.at(-1)).toBe("close");
    const closed = fakeTabs([], new TabGone("x"));
    expect((await scan(closed.tabs)).detail).toBe("Tarama sekmesi kapatıldı; tarama durdu. Yeniden başlatılabilir.");
  });

  it("says when the service is older than the extension and knows no scan", async () => {
    const older = fakeService(new Set(), false, true);
    const summary = await scan(fakeTabs([page(["10", "10", 0])]).tabs, { service: older.fetcher });
    expect(summary.detail).toBe("İplikçi Nedim bu eklentiden eski bir sürüm: bu iş için onu güncelleyin.");
  });

  it("opens no tab without a pairing or a service that answers", async () => {
    const unpaired = fakeTabs([page(["10", "10", 0])]);
    expect((await scan(unpaired.tabs, { store: memoryStore() })).detail).toBe(
      "Önce eklentiyi İplikçi Nedim ile eşleştirin.",
    );
    const down = fakeTabs([page(["10", "10", 0])]);
    expect((await scan(down.tabs, { service: fakeService(new Set(), true).fetcher })).detail).toBe(
      "İplikçi Nedim bu bilgisayarda çalışmıyor; açılınca iletiler alınır.",
    );
    expect([...unpaired.calls, ...down.calls]).toEqual([]);
  });
});
