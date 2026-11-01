import { describe, expect, it } from "vitest";

import { expectedProof } from "../src/bridge/proof";
import { PACE_MS, type RunEnvironment, deliverNew } from "../src/bridge/run";
import {
  type Cursor,
  type Fetcher,
  NotTheService,
  type Paired,
  Refused,
  SERVICE,
  ServiceDown,
  pair,
  prove,
} from "../src/bridge/service";
import { memoryStore } from "../src/bridge/state";
import { scansFirst } from "../src/bridge/steps";
import type { Fetcher as GmailFetcher } from "../src/gmail/http";
import { IK, type FakeEntry, feedXml, gmailPage, originalPage, rawMessage } from "./fixtures";

const PAIRED: Paired = { id: "k1", token: "belirtec-123" };
const BANK = "garantibbva.com.tr";
const START: Cursor = {
  lastId: "",
  lastDate: "",
  startDay: "2026-01-01",
  senders: [BANK, "isbank.com.tr"],
  historyDue: false,
};

describe("proof", () => {
  it("answers as the service does: HMAC-SHA256 keyed with the token's SHA-256", async () => {
    // Python: hmac.new(sha256(token).hexdigest().encode(), nonce.encode(), sha256).hexdigest()
    expect(await expectedProof("belirtec-123", "a".repeat(32))).toBe(
      "3d8f285787478853bc1de7c2eb7276302fa61cec5aafcea2592068dec5ce9cff",
    );
  });
});

interface Delivery {
  readonly id: string;
  readonly date: string;
  readonly raw: string;
  readonly auth: string;
}

/** The service as the bridge sees it, answering by address; proves itself with the token unless told to lie. */
interface ServiceOptions {
  readonly cursor?: Cursor;
  readonly lie?: boolean;
  readonly down?: boolean;
  readonly revoked?: boolean;
  /** The service's answer to a delivery of this Gmail id, when it does not take it. */
  readonly refuse?: (id: string) => Response | undefined;
}

function fakeService(options: ServiceOptions = {}) {
  const deliveries: Delivery[] = [];
  const alarms: unknown[] = [];
  const fetcher: Fetcher = async (address, init) => {
    if (options.down) {
      throw new TypeError("Failed to fetch");
    }
    const url = new URL(address);
    expect(url.origin).toBe(SERVICE);
    expect(init.credentials).toBe("omit"); // never the browser's cookies
    if (url.pathname === "/api/bridge/hello") {
      if (options.revoked) {
        return Response.json({ code: "bridge_unknown", title: "Eşleşme yok." }, { status: 404 });
      }
      const nonce = url.searchParams.get("nonce") ?? "";
      return Response.json({ proof: options.lie ? "0".repeat(64) : await expectedProof(PAIRED.token, nonce) });
    }
    const auth = new Headers(init.headers).get("Authorization") ?? "";
    if (url.pathname === "/api/ingest/mail/cursor") {
      const where = options.cursor ?? START;
      return Response.json({
        last_id: where.lastId,
        last_date: where.lastDate,
        start_day: where.startDay,
        senders: where.senders,
        history_due: where.historyDue,
      });
    }
    if (url.pathname === "/api/ingest/mail") {
      const headers = new Headers(init.headers);
      const refused = options.refuse?.(headers.get("X-Gmail-Id") ?? "");
      if (refused !== undefined) {
        return refused;
      }
      deliveries.push({
        id: headers.get("X-Gmail-Id") ?? "",
        date: headers.get("X-Gmail-Date") ?? "",
        raw: new TextDecoder().decode(init.body as Uint8Array),
        auth,
      });
      return Response.json({ taken: "stored", documents: 1 });
    }
    if (url.pathname === "/api/ingest/mail/alarm") {
      alarms.push(JSON.parse(String(init.body)));
      return Response.json({ news: true });
    }
    if (url.pathname === "/api/bridge/pair") {
      const body = JSON.parse(String(init.body)) as { code: string };
      return body.code === "ABCD-EFGH"
        ? Response.json(PAIRED)
        : Response.json({ code: "pairing_code_invalid", title: "Eşleştirme kodu geçersiz." }, { status: 403 });
    }
    return new Response(null, { status: 404 });
  };
  return { fetcher, deliveries, alarms };
}

/** Gmail with a feed of entries, every message's original, and a record of every request. */
function fakeGmail(entries: readonly FakeEntry[], overrides: { feed?: () => Response } = {}) {
  const requests: string[] = [];
  const fetcher: GmailFetcher = async (address, init) => {
    requests.push(address);
    expect(init.method).toBe("GET"); // the bridge never changes anything in Gmail
    const url = new URL(address);
    if (url.pathname.endsWith("/feed/atom")) {
      return overrides.feed?.() ?? new Response(feedXml(entries));
    }
    if (url.searchParams.get("view") === "om") {
      const id = (url.searchParams.get("permmsgid") ?? "").replace("msg-f:", "");
      const entry = entries.find((e) => e.id.toString() === id);
      return new Response(originalPage(rawMessage({ from: entry?.sender ?? "x@example.org" }), BigInt(id)));
    }
    return new Response(gmailPage(IK));
  };
  return { fetcher, requests };
}

function environment(gmail: GmailFetcher, service: Fetcher, at = "2026-11-01T10:00:00Z", version = "0.2.0") {
  const sleeps: number[] = [];
  const env: RunEnvironment = {
    gmail,
    service,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
    now: () => new Date(at),
    version,
  };
  return { env, sleeps };
}

const NEW = { id: 1001n, sender: `ekstre@${BANK}`, issued: "2026-10-30T08:00:00Z" } as const;
const NEWER = { id: 1002n, sender: "bilgi@isbank.com.tr", issued: "2026-10-31T08:00:00Z" } as const;
const OTHER = { id: 1003n, sender: "haber@example.org", issued: "2026-10-31T09:00:00Z" } as const;

describe("deliverNew", () => {
  it("delivers the unread messages of listed banks, oldest first, a second apart", async () => {
    const gmail = fakeGmail([NEWER, OTHER, NEW]);
    const service = fakeService();
    const { env, sleeps } = environment(gmail.fetcher, service.fetcher);
    const store = memoryStore({ paired: PAIRED });
    const summary = await deliverNew(env, store);
    expect(summary.outcome).toBe("delivered");
    expect(summary.delivered).toBe(2);
    expect(service.deliveries.map((d) => [d.id, d.date])).toEqual([
      ["1001", "2026-10-30T08:00:00Z"],
      ["1002", "2026-10-31T08:00:00Z"],
    ]);
    expect(service.deliveries[0]?.raw).toContain(`From: Banka <ekstre@${BANK}>`);
    expect(service.deliveries[0]?.auth).toBe(`Bearer ${PAIRED.token}`);
    expect(gmail.requests.some((r) => r.includes("msg-f:1003"))).toBe(false); // not a listed sender: never read
    expect(sleeps.every((ms) => ms === PACE_MS) && sleeps.length >= 2).toBe(true);
    expect(store.current.keys["0"]).toBe(IK); // the big Gmail page is read once and its key kept
    expect(store.current.lastRun?.detail).toBe("2 yeni ileti İplikçi Nedim'e teslim edildi.");
  });

  it("delivers nothing the service has taken already and nothing from before the start day", async () => {
    const old = { id: 999n, sender: `ekstre@${BANK}`, issued: "2025-12-31T08:00:00Z" };
    const gmail = fakeGmail([old, NEW, NEWER]);
    const where: Cursor = { ...START, lastId: "1001", lastDate: NEW.issued };
    const service = fakeService({ cursor: where });
    const { env } = environment(gmail.fetcher, service.fetcher);
    await deliverNew(env, memoryStore({ paired: PAIRED, keys: { "0": IK } }));
    expect(service.deliveries.map((d) => d.id)).toEqual(["1002"]);
  });

  it("keeps what the service says of the history: a check by hand then scans Gmail first", async () => {
    const store = memoryStore({ paired: PAIRED });
    const due = fakeService({ cursor: { ...START, historyDue: true } });
    await deliverNew(environment(fakeGmail([]).fetcher, due.fetcher).env, store);
    expect([store.current.historyDue, store.current.startDay]).toEqual([true, "2026-01-01"]);
    expect(scansFirst(store.current, "0.2.0")).toBe(true);
    expect(scansFirst({ ...store.current, stopped: { "2": "0.2.0" } }, "0.2.0")).toBe(false); // no scan can run
    expect(scansFirst({ ...store.current, paired: null }, "0.2.0")).toBe(false);
    await deliverNew(environment(fakeGmail([]).fetcher, fakeService().fetcher).env, store);
    expect(scansFirst(store.current, "0.2.0")).toBe(false); // scanned meanwhile
  });

  it("takes a service that says nothing of the history as having none to scan", async () => {
    const older: Fetcher = async (address, init) => {
      const answer = await fakeService().fetcher(address, init);
      if (!address.includes("/cursor")) {
        return answer;
      }
      const { history_due: _, ...rest } = (await answer.json()) as Record<string, unknown>;
      return Response.json(rest);
    };
    const store = memoryStore({ paired: PAIRED, historyDue: true });
    await deliverNew(environment(fakeGmail([]).fetcher, older).env, store);
    expect(store.current.historyDue).toBe(false);
  });

  it("asks nothing of Gmail when the feed has nothing new", async () => {
    const gmail = fakeGmail([OTHER]);
    const { env } = environment(gmail.fetcher, fakeService().fetcher);
    const summary = await deliverNew(env, memoryStore({ paired: PAIRED }));
    expect(summary.outcome).toBe("nothing-new");
    expect(gmail.requests).toHaveLength(1); // the feed only
  });

  it("waits for a pairing and sends nothing to a service that cannot prove itself", async () => {
    const gmail = fakeGmail([NEW]);
    expect((await deliverNew(environment(gmail.fetcher, fakeService().fetcher).env, memoryStore())).outcome).toBe(
      "unpaired",
    );
    const liar = fakeService({ lie: true });
    const summary = await deliverNew(environment(gmail.fetcher, liar.fetcher).env, memoryStore({ paired: PAIRED }));
    expect(summary.outcome).toBe("not-the-service");
    expect(liar.deliveries).toEqual([]);
    expect(gmail.requests).toEqual([]); // Gmail is not even read
  });

  it("says when the service is not running or the pairing was revoked", async () => {
    const gmail = fakeGmail([NEW]);
    const store = memoryStore({ paired: PAIRED });
    const down = await deliverNew(environment(gmail.fetcher, fakeService({ down: true }).fetcher).env, store);
    expect(down.outcome).toBe("service-down");
    const revoked = await deliverNew(environment(gmail.fetcher, fakeService({ revoked: true }).fetcher).env, store);
    expect(revoked.outcome).toBe("revoked");
  });

  it("stops a layer on a page it does not know, tells the service once, and tries again after an update", async () => {
    const gmail = fakeGmail([NEW], { feed: () => new Response("<html>yeni bir sayfa</html>") });
    const service = fakeService();
    const store = memoryStore({ paired: PAIRED });
    expect((await deliverNew(environment(gmail.fetcher, service.fetcher).env, store)).outcome).toBe("stopped");
    expect(service.alarms).toEqual([{ layer: 1, version: "0.2.0" }]);
    await deliverNew(environment(gmail.fetcher, service.fetcher).env, store);
    expect(gmail.requests).toHaveLength(1); // stopped: Gmail is not asked again by this version
    expect(service.alarms).toHaveLength(1);
    const updated = environment(fakeGmail([NEW]).fetcher, service.fetcher, "2026-11-01T10:00:00Z", "0.2.1");
    expect((await deliverNew(updated.env, store)).outcome).toBe("delivered");
  });

  it("waits longer each time Gmail asks it to slow down", async () => {
    const gmail = fakeGmail([NEW], { feed: () => new Response(null, { status: 429 }) });
    const store = memoryStore({ paired: PAIRED });
    const first = await deliverNew(environment(gmail.fetcher, fakeService().fetcher).env, store);
    expect(first.outcome).toBe("gmail-busy");
    expect(store.current.calmUntil).toBe(Date.parse("2026-11-01T10:01:00Z"));
    await deliverNew(environment(gmail.fetcher, fakeService().fetcher, "2026-11-01T10:00:30Z").env, store);
    expect(gmail.requests).toHaveLength(1); // still calm: no request
    await deliverNew(environment(gmail.fetcher, fakeService().fetcher, "2026-11-01T10:01:30Z").env, store);
    expect(store.current.calmUntil).toBe(Date.parse("2026-11-01T10:03:30Z")); // two minutes the second time
  });

  it("skips a message the service can never take and does not download it again", async () => {
    const gmail = fakeGmail([NEW, NEWER]);
    const tooLarge = () =>
      Response.json({ code: "message_too_large", title: "İleti 40 MB sınırından büyük." }, { status: 413 });
    const service = fakeService({ refuse: (id) => (id === "1001" ? tooLarge() : undefined) });
    const store = memoryStore({ paired: PAIRED, keys: { "0": IK } });
    const summary = await deliverNew(environment(gmail.fetcher, service.fetcher).env, store);
    expect([summary.outcome, summary.delivered]).toEqual(["delivered", 1]);
    expect(service.deliveries.map((d) => d.id)).toEqual(["1002"]);
    expect(store.current.skipped).toEqual(["1001"]);
    gmail.requests.length = 0;
    await deliverNew(environment(gmail.fetcher, fakeService().fetcher).env, store);
    expect(gmail.requests.some((r) => r.includes("msg-f:1001"))).toBe(false);
  });

  it("stops at a message the service fails on, keeps it for the next try and waits before that", async () => {
    const gmail = fakeGmail([NEW, NEWER]);
    const broken = () => Response.json({ code: "internal", title: "Beklenmeyen bir hata oldu." }, { status: 500 });
    const service = fakeService({ refuse: broken });
    const store = memoryStore({ paired: PAIRED, keys: { "0": IK } });
    const summary = await deliverNew(environment(gmail.fetcher, service.fetcher).env, store);
    expect(summary.outcome).toBe("failed");
    expect(summary.detail).toBe(
      "İplikçi Nedim bir iletiyi almadı (Beklenmeyen bir hata oldu); biraz sonra yeniden denenecek.",
    );
    expect(store.current.skipped).toEqual([]);
    expect(gmail.requests.filter((r) => r.includes("view=om"))).toHaveLength(1); // the run stopped at the first
    const meanwhile = await deliverNew(environment(gmail.fetcher, service.fetcher, "2026-11-01T10:00:59Z").env, store);
    expect(meanwhile).toEqual(summary); // still waiting: nothing is asked and the last summary stands
    expect(gmail.requests.filter((r) => r.includes("view=om"))).toHaveLength(1);
  });

  it("says when Gmail cannot be reached", async () => {
    const offline: GmailFetcher = async () => {
      throw new TypeError("Failed to fetch");
    };
    const summary = await deliverNew(environment(offline, fakeService().fetcher).env, memoryStore({ paired: PAIRED }));
    expect(summary.detail).toBe(
      "Gmail'e ulaşılamadı (ağ bağlantısı ya da tarayıcı izni); biraz sonra yeniden denenecek.",
    );
  });

  it("says when the chosen Google account is not signed in", async () => {
    const gmail = fakeGmail([NEW], { feed: () => new Response(null, { status: 302 }) });
    const summary = await deliverNew(environment(gmail.fetcher, fakeService().fetcher).env, memoryStore({ paired: PAIRED }));
    expect(summary.outcome).toBe("gmail-signed-out");
  });
});

describe("service", () => {
  it("pairs with a typed code and proves the service before the pairing is kept", async () => {
    const service = fakeService();
    expect(await pair(service.fetcher, " ABCD-EFGH ", "Chrome 140, macOS")).toEqual(PAIRED);
    await expect(pair(service.fetcher, "YANLIS", "Chrome")).rejects.toThrow(Refused);
    await expect(prove(fakeService({ lie: true }).fetcher, PAIRED)).rejects.toThrow(NotTheService);
    await expect(prove(fakeService({ down: true }).fetcher, PAIRED)).rejects.toThrow(ServiceDown);
  });
});
