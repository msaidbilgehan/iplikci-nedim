import { describe, expect, it } from "vitest";

import { asRequest } from "../src/bridge/messages";
import { expectedProof } from "../src/bridge/proof";
import { hear } from "../src/bridge/sayings";
import { type Fetcher, type Paired, SERVICE, asSaying } from "../src/bridge/service";
import { FACES, spoken } from "../src/ui/nedim";

const PAIRED: Paired = { id: "k1", token: "belirtec-123" };

/** The service's answer as /api/bridge/sayings gives it: the most pressing first, a dialogue among them. */
const ITEMS = [
  {
    situation: "overspent",
    mood: "critical",
    reason: "Ekim 2026'da harcanan, gelen paradan fazlaydı.",
    quote: { id: "dark_future", lines: ["Kara bahtım, kör talihim benim; geleceğim çok karanlık."] },
  },
  {
    situation: "best_month",
    mood: "good",
    reason: "Ekim 2026, kapanan son 6 ay içinde en çok paranın kaldığı ay oldu.",
    quote: {
      id: "who_is_bigger",
      lines: ["Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle.", "Siz efendim.", "Hıh. Tamam canım."],
    },
  },
];

interface ServiceOptions {
  readonly lie?: boolean;
  readonly down?: boolean;
  /** The status the service refuses the lines with: 404 from an older one, 401 once revoked, 503 while busy. */
  readonly refuse?: number;
  readonly items?: unknown;
}

/** The service as the bridge sees it: proves itself with the token unless told to lie, and gives its lines. */
function fakeService(options: ServiceOptions = {}) {
  const asked: Array<{ path: string; auth: string }> = [];
  const fetcher: Fetcher = async (address, init) => {
    if (options.down) {
      throw new TypeError("Failed to fetch");
    }
    const url = new URL(address);
    expect(url.origin).toBe(SERVICE);
    expect(init.credentials).toBe("omit"); // never the browser's cookies, the session among them
    asked.push({ path: url.pathname, auth: new Headers(init.headers).get("Authorization") ?? "" });
    if (url.pathname === "/api/bridge/hello") {
      const nonce = url.searchParams.get("nonce") ?? "";
      return Response.json({ proof: options.lie ? "0".repeat(64) : await expectedProof(PAIRED.token, nonce) });
    }
    if (url.pathname === "/api/bridge/sayings") {
      if (options.refuse !== undefined) {
        return Response.json({ code: "refused", title: "Olmadı." }, { status: options.refuse });
      }
      return Response.json({ items: options.items ?? ITEMS });
    }
    return new Response(null, { status: 404 });
  };
  return { fetcher, asked };
}

describe("İplikçi Nedim's lines in the extension's window", () => {
  it("are asked of the paired service once it proves itself, with the token and without a cookie", async () => {
    const service = fakeService();
    expect(await hear(service.fetcher, PAIRED)).toEqual([
      {
        situation: "overspent",
        mood: "critical",
        reason: "Ekim 2026'da harcanan, gelen paradan fazlaydı.",
        lines: ["Kara bahtım, kör talihim benim; geleceğim çok karanlık."],
      },
      {
        situation: "best_month",
        mood: "good",
        reason: "Ekim 2026, kapanan son 6 ay içinde en çok paranın kaldığı ay oldu.",
        lines: ["Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle.", "Siz efendim.", "Hıh. Tamam canım."],
      },
    ]);
    expect(service.asked).toEqual([
      { path: "/api/bridge/hello", auth: "" }, // the proof first: the token goes to the paired service only
      { path: "/api/bridge/sayings", auth: "Bearer belirtec-123" },
    ]);
  });

  it("are not asked for without a pairing", async () => {
    const service = fakeService();
    expect(await hear(service.fetcher, null)).toEqual([]);
    expect(service.asked).toEqual([]);
  });

  it("are not asked of what is not the paired service, and the token never goes to it", async () => {
    const stranger = fakeService({ lie: true });
    expect(await hear(stranger.fetcher, PAIRED)).toEqual([]);
    expect(stranger.asked.map((call) => call.path)).toEqual(["/api/bridge/hello"]);
    expect(await hear(fakeService({ down: true }).fetcher, PAIRED)).toEqual([]);
  });

  it.each([
    [404, "an older service"],
    [401, "a revoked pairing"],
    [503, "documents being read"],
  ])("are none when the service refuses them with %i: %s", async (refuse) => {
    expect(await hear(fakeService({ refuse }).fetcher, PAIRED)).toEqual([]);
  });

  it("leave out whatever is not a line of his", async () => {
    const [good] = ITEMS;
    const items = [
      { ...good, mood: "happy" },
      { ...good, quote: { id: "x", lines: [] } },
      { ...good, quote: { id: "x", lines: ["a", "b", "c", "d", "e", "f"] } },
      { ...good, quote: { id: "x", lines: [42] } },
      { ...good, reason: "x".repeat(401) },
      { ...good, quote: null },
      "söz",
      good,
    ];
    expect((await hear(fakeService({ items }).fetcher, PAIRED)).map((s) => s.situation)).toEqual(["overspent"]);
    expect(asSaying({ situation: "good", mood: "good", reason: "r", lines: ["a"] })).toHaveLength(1); // as passed on
  });

  it("are a request the service worker takes from the window", () => {
    expect(asRequest({ kind: "sayings" })).toEqual({ kind: "sayings" });
  });

  it("are spoken in quotation marks, a dialogue's turns each on a line of its own", () => {
    expect(spoken(["Çakır, kuzum…"])).toBe("“Çakır, kuzum…”");
    expect(spoken(["Ortadoğu mu büyük?", "Siz efendim.", "Hıh. Tamam canım."])).toBe(
      "– Ortadoğu mu büyük?\n– Siz efendim.\n– Hıh. Tamam canım.",
    );
  });

  it("colour his face from the extension's own icons, the logo itself when the money goes well", () => {
    // That every face is drawn is the service's tests' to check (tests/test_sayings.py), with the Pano's.
    expect(FACES).toEqual({
      good: "icons/icon-128.png",
      warning: "icons/face-warning.png",
      critical: "icons/face-critical.png",
      neutral: "icons/face-neutral.png",
    });
  });
});
