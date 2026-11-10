import { describe, expect, it } from "vitest";

import { asRequest, asTabRequest } from "../src/bridge/messages";
import { expectedProof } from "../src/bridge/proof";
import { PACE_MS, type RunEnvironment, deliverNew } from "../src/bridge/run";
import { keep, unhandled, watchFor } from "../src/bridge/seen";
import { type Fetcher, type Paired, SERVICE } from "../src/bridge/service";
import { type BridgeState, INITIAL, type RunSummary, memoryStore } from "../src/bridge/state";
import type { Fetcher as GmailFetcher } from "../src/gmail/http";
import { PER_MESSAGE } from "../src/gmail/visible";
import { IK, type FakeEntry, feedXml, gmailPage, originalPage, rawMessage } from "./fixtures";

const PAIRED: Paired = { id: "k1", token: "belirtec-123" };
const SENDERS = ["teb.com.tr", "isbank.com.tr"];
const BANK = "ekstre@teb.com.tr";
const VERSION = "0.7.0";
const NOW = "2026-11-10T15:00:00Z";
/** A bank message the inbox feed lists, unread. */
const UNREAD: FakeEntry = { id: 1001n, sender: BANK, issued: "2026-11-10T14:41:00Z" };

/**
 * The service: proves itself, says where delivery stands, which of the ids asked for it lacks (those it holds or was
 * given), and records what it is given; `refuse` answers a delivery it does not take.
 */
function fakeService(held: ReadonlySet<string> = new Set(), refuse?: (id: string) => Response | undefined) {
  const delivered: Array<{ id: string; date: string }> = [];
  const asked: string[][] = [];
  const fetcher: Fetcher = async (address, init) => {
    const url = new URL(address);
    expect(url.origin).toBe(SERVICE);
    switch (url.pathname) {
      case "/api/bridge/hello":
        return Response.json({ proof: await expectedProof(PAIRED.token, url.searchParams.get("nonce") ?? "") });
      case "/api/ingest/mail/cursor":
        return Response.json({ last_id: "", last_date: "", start_day: "2026-01-01", senders: SENDERS });
      case "/api/ingest/mail/known": {
        const ids = (JSON.parse(String(init.body)) as { ids: string[] }).ids;
        asked.push(ids);
        return Response.json({ missing: ids.filter((id) => !held.has(id) && !delivered.some((d) => d.id === id)) });
      }
      case "/api/ingest/mail": {
        const headers = new Headers(init.headers);
        const id = headers.get("X-Gmail-Id") ?? "";
        const refused = refuse?.(id);
        if (refused !== undefined) {
          return refused;
        }
        delivered.push({ id, date: headers.get("X-Gmail-Date") ?? "" });
        return Response.json({ taken: "stored", documents: 1 });
      }
      case "/api/ingest/mail/alarm":
        return Response.json({ news: true });
      default:
        return new Response(null, { status: 404 });
    }
  };
  return { fetcher, delivered, asked };
}

/** Gmail: the inbox feed's entries and every message's "Show original", without its text for `unshown`. */
function fakeGmail(entries: readonly FakeEntry[] = [], unshown: ReadonlySet<string> = new Set()) {
  const requests: string[] = [];
  const fetcher: GmailFetcher = async (address, init) => {
    requests.push(address);
    expect(init.method).toBe("GET"); // nothing in Gmail changes
    const url = new URL(address);
    if (url.pathname.endsWith("/feed/atom")) {
      return new Response(feedXml(entries));
    }
    if (url.searchParams.get("view") === "om") {
      const id = (url.searchParams.get("permmsgid") ?? "").replace("msg-f:", "");
      const page = originalPage(rawMessage({ from: BANK }), BigInt(id));
      return new Response(unshown.has(id) ? page.replace(/<pre[\s\S]*<\/pre>/, "") : page);
    }
    return new Response(gmailPage(IK));
  };
  const originals = (): string[] =>
    requests
      .filter((r) => r.includes("view=om"))
      .map((r) => (new URL(r).searchParams.get("permmsgid") ?? "").replace("msg-f:", ""));
  return { fetcher, requests, originals };
}

function environment(gmail: GmailFetcher, service: Fetcher, at = NOW) {
  const sleeps: number[] = [];
  const env: RunEnvironment = {
    gmail,
    service,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
    now: () => new Date(at),
    version: VERSION,
  };
  return { env, sleeps };
}

/** Paired, with the account key kept: the big Gmail page is not read again. */
function paired(state: Partial<BridgeState> = {}) {
  return memoryStore({ paired: PAIRED, keys: { "0": IK }, ...state });
}

describe("the messages an open Gmail tab showed", () => {
  it("delivers those the service lacks, oldest first, a second apart and without a date", async () => {
    const service = fakeService(new Set(["32"]));
    const gmail = fakeGmail();
    const { env, sleeps } = environment(gmail.fetcher, service.fetcher);
    const store = paired();
    const summary = await deliverNew(env, store, ["48", "16", "32"]);
    expect(service.asked).toEqual([["48", "16", "32"]]);
    expect(service.delivered).toEqual([
      { id: "16", date: "" }, // the service's position stays where the feed's messages put it
      { id: "48", date: "" },
    ]);
    expect(gmail.originals()).toEqual(["16", "48"]);
    expect(sleeps).toEqual([PACE_MS, PACE_MS]);
    expect(summary).toMatchObject({ outcome: "delivered", delivered: 2 });
    expect(summary.detail).toBe("2 yeni ileti İplikçi Nedim'e teslim edildi.");
    expect(store.current.seen).toEqual([]);
    expect([...store.current.known].sort()).toEqual(["16", "32", "48"]); // 32: the service holds it
    expect(store.current.senders).toEqual(SENDERS); // what the Gmail tabs look for, as the service said
  });

  it("reads the inbox feed first: an unread message it lists comes with its date, and only once", async () => {
    const service = fakeService();
    const gmail = fakeGmail([UNREAD]);
    const store = paired();
    await deliverNew(environment(gmail.fetcher, service.fetcher).env, store, ["1001", "1005"]);
    expect(service.delivered).toEqual([
      { id: "1001", date: UNREAD.issued },
      { id: "1005", date: "" },
    ]);
    expect(service.asked).toEqual([["1005"]]); // the feed's message was delivered already
    expect(gmail.originals()).toEqual(["1001", "1005"]);
  });

  it("does not download for the feed a message it took from a Gmail tab before the feed listed it", async () => {
    const service = fakeService();
    const store = paired();
    await deliverNew(environment(fakeGmail().fetcher, service.fetcher).env, store, ["1001"]);
    const gmail = fakeGmail([UNREAD]); // a minute later the feed lists it; the service's position did not move
    const summary = await deliverNew(environment(gmail.fetcher, service.fetcher).env, store);
    expect([summary.outcome, gmail.originals(), service.delivered]).toEqual([
      "nothing-new",
      [],
      [{ id: "1001", date: "" }],
    ]);
  });

  it("drops the ids it delivered, skipped or keeps waiting already, and keeps none while unpaired", async () => {
    const state: BridgeState = { ...INITIAL, paired: PAIRED, known: ["1"], skipped: ["2"], seen: ["3"] };
    expect(unhandled(state, ["1", "2", "3", "4", "5", "4"])).toEqual(["4", "5"]);
    const store = memoryStore(state);
    await keep(store, ["3", "4", "1"]);
    expect(store.current.seen).toEqual(["3", "4"]);
    const unpaired = memoryStore();
    await keep(unpaired, ["4"]);
    expect(unpaired.current.seen).toEqual([]);
  });

  it("keeps the ids while it waits after a trouble, and delivers them when the wait is over", async () => {
    const last: RunSummary = { at: NOW, outcome: "gmail-busy", delivered: 0, detail: "Gmail yavaşlamayı istedi." };
    const store = paired({ calmUntil: Date.parse("2026-11-10T15:01:00Z"), lastRun: last });
    const service = fakeService();
    const gmail = fakeGmail();
    expect(await deliverNew(environment(gmail.fetcher, service.fetcher).env, store, ["16"])).toEqual(last);
    expect([store.current.seen, gmail.requests, service.asked]).toEqual([["16"], [], []]);
    await deliverNew(environment(gmail.fetcher, service.fetcher, "2026-11-10T15:02:00Z").env, store);
    expect(service.delivered.map((d) => d.id)).toEqual(["16"]);
  });

  it("takes nothing from a Gmail tab while Gmail's list is stopped, as the feed goes on", async () => {
    const service = fakeService();
    const store = paired({ stopped: { "2": VERSION } });
    await deliverNew(environment(fakeGmail([UNREAD]).fetcher, service.fetcher).env, store, ["16"]);
    expect(service.delivered.map((d) => d.id)).toEqual(["1001"]);
    expect(store.current.seen).toEqual(["16"]); // for the version that knows the list
  });

  it("goes on taking what a Gmail tab shows while the inbox feed is stopped, and says the feed is", async () => {
    const service = fakeService();
    const gmail = fakeGmail([UNREAD]);
    const store = paired({ stopped: { "1": VERSION } });
    const summary = await deliverNew(environment(gmail.fetcher, service.fetcher).env, store, ["16"]);
    expect(gmail.requests.some((r) => r.endsWith("/feed/atom"))).toBe(false);
    expect(service.delivered.map((d) => d.id)).toEqual(["16"]);
    expect(summary).toMatchObject({ outcome: "stopped", delivered: 1 });
    expect(summary.detail).toBe(
      "1 yeni ileti İplikçi Nedim'e teslim edildi. Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi " +
        "bekleniyor.",
    );
    const none = paired({ stopped: { "1": VERSION } });
    const idle = fakeGmail([UNREAD]);
    expect((await deliverNew(environment(idle.fetcher, service.fetcher).env, none)).outcome).toBe("stopped");
    expect(idle.requests).toEqual([]); // nothing waits: nothing is asked
  });

  it("skips a message the service can never take or Gmail shows no original for, and never asks again", async () => {
    const tooLarge = () =>
      Response.json({ code: "message_too_large", title: "İleti 40 MB sınırından büyük." }, { status: 413 });
    const service = fakeService(new Set(), (id) => (id === "16" ? tooLarge() : undefined));
    const gmail = fakeGmail([], new Set(["32"]));
    const store = paired();
    const summary = await deliverNew(environment(gmail.fetcher, service.fetcher).env, store, ["16", "32", "48"]);
    expect(service.delivered.map((d) => d.id)).toEqual(["48"]);
    expect(store.current.skipped).toEqual(["16", "32"]);
    expect(summary.outcome).toBe("unshown");
    gmail.requests.length = 0;
    service.asked.length = 0;
    await deliverNew(environment(gmail.fetcher, service.fetcher).env, store, ["16", "32", "48"]);
    expect([gmail.originals(), service.asked, store.current.seen]).toEqual([[], [], []]);
  });

  it("stops at a message the service fails on, and keeps it and the rest waiting for after the pause", async () => {
    const broken = () => Response.json({ code: "internal", title: "Beklenmeyen bir hata oldu." }, { status: 500 });
    const service = fakeService(new Set(), (id) => (id === "48" ? broken() : undefined));
    const store = paired();
    const summary = await deliverNew(environment(fakeGmail().fetcher, service.fetcher).env, store, ["16", "48", "64"]);
    expect(service.delivered.map((d) => d.id)).toEqual(["16"]);
    expect(summary.outcome).toBe("failed");
    expect(store.current.seen).toEqual(["48", "64"]);
    expect(store.current.calmUntil).toBe(Date.parse(NOW) + 60_000);
  });
});

describe("what a Gmail tab may look for and tell", () => {
  const state: BridgeState = { ...INITIAL, paired: PAIRED, account: 1, senders: SENDERS };

  it("looks for the listed senders only in the account the bridge reads, while the bridge takes from tabs", () => {
    expect(watchFor(state, VERSION, 1)).toEqual({ senders: SENDERS });
    expect(watchFor(state, VERSION, 0)).toBeNull(); // another account's tab
    expect(watchFor({ ...state, paired: null }, VERSION, 1)).toBeNull();
    expect(watchFor({ ...state, senders: [] }, VERSION, 1)).toBeNull(); // nothing heard from the service yet
    expect(watchFor({ ...state, stopped: { "2": VERSION } }, VERSION, 1)).toBeNull();
    expect(watchFor({ ...state, stopped: { "3": VERSION } }, VERSION, 1)).toBeNull();
    expect(watchFor({ ...state, stopped: { "1": VERSION } }, VERSION, 1)).not.toBeNull(); // the feed's own
    expect(watchFor({ ...state, stopped: { "2": "0.6.0" } }, VERSION, 1)).not.toBeNull(); // an older version's
  });

  it("asks what to look for or tells Gmail ids in decimal, and nothing else", () => {
    expect(asTabRequest({ kind: "gmail-watch" })).toEqual({ kind: "gmail-watch" });
    expect(asTabRequest({ kind: "gmail-seen", ids: ["1000", "2300"] })).toEqual({
      kind: "gmail-seen",
      ids: ["1000", "2300"],
    });
    const many = Array.from({ length: PER_MESSAGE + 1 }, (_, n) => String(n + 1));
    for (const bad of [
      null,
      "gmail-watch",
      { kind: "gmail-seen", ids: "1000" },
      { kind: "gmail-seen", ids: [1000] },
      { kind: "gmail-seen", ids: ["18f0a1"] }, // hexadecimal
      { kind: "gmail-seen", ids: ["1000", "Hesap Özetiniz Hazır"] },
      { kind: "gmail-seen", ids: many },
      { kind: "forget" }, // a request only the extension's own pages make
      { kind: "pair", code: "ABCD-EFGH" },
    ]) {
      expect(asTabRequest(bad)).toBeNull();
    }
    expect(asRequest({ kind: "gmail-seen", ids: ["1000"] })).toBeNull(); // nor is a tab's request a page's
  });
});
