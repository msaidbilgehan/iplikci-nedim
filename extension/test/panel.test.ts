import { afterEach, describe, expect, it, vi } from "vitest";

import { asRequest } from "../src/bridge/messages";
import {
  HOME,
  LOGIN_PREFIX,
  type PanelTabs,
  SIGN_IN_TITLE,
  type ServiceTab,
  openPanel,
  signingIn,
} from "../src/bridge/panel";
import { expectedProof } from "../src/bridge/proof";
import { type Fetcher, type Paired, SERVICE } from "../src/bridge/service";
import { chromePanelTabs } from "../src/bridge/tabs";

const PAIRED: Paired = { id: "k1", token: "belirtec-123" };
const LINK = `${SERVICE}/giris?anahtar=tek-kullanimlik`;

interface ServiceOptions {
  readonly lie?: boolean;
  readonly down?: boolean;
  readonly revoked?: boolean;
  /** The service's answer to the request for a login link. */
  readonly link?: () => Response;
}

/** The service as the bridge sees it: proves itself with the token unless told to lie, and gives a login link. */
function fakeService(options: ServiceOptions = {}) {
  const asked: Array<{ path: string; method: string; auth: string }> = [];
  const fetcher: Fetcher = async (address, init) => {
    if (options.down) {
      throw new TypeError("Failed to fetch");
    }
    const url = new URL(address);
    expect(url.origin).toBe(SERVICE);
    expect(init.credentials).toBe("omit"); // never the browser's cookies, the session among them
    asked.push({
      path: url.pathname,
      method: init.method ?? "GET",
      auth: new Headers(init.headers).get("Authorization") ?? "",
    });
    if (url.pathname === "/api/bridge/hello") {
      if (options.revoked) {
        return Response.json({ code: "bridge_unknown", title: "Eşleşme yok." }, { status: 404 });
      }
      const nonce = url.searchParams.get("nonce") ?? "";
      return Response.json({ proof: options.lie ? "0".repeat(64) : await expectedProof(PAIRED.token, nonce) });
    }
    if (url.pathname === "/api/bridge/login-link") {
      return options.link?.() ?? Response.json({ url: LINK });
    }
    return new Response(null, { status: 404 });
  };
  return { fetcher, asked };
}

/** The browser's tabs on the service's address, and what was done with them. */
function fakeTabs(open: readonly ServiceTab[] = []) {
  const done: string[] = [];
  const tabs: PanelTabs = {
    async find() {
      return open;
    },
    async show(tab, url) {
      done.push(url === undefined ? `show ${tab.id}` : `show ${tab.id} ${url}`);
    },
    async open(url) {
      done.push(`open ${url}`);
    },
  };
  return { tabs, done };
}

function tab(id: number, shown: Partial<ServiceTab> = {}): ServiceTab {
  return {
    id,
    windowId: 1,
    url: `${SERVICE}/hesaplar`,
    title: "Hesaplar · İplikçi Nedim",
    front: false,
    lastAccessed: 1000 + id,
    ...shown,
  };
}

const SIGN_IN = { url: `${SERVICE}/`, title: SIGN_IN_TITLE } as const;

describe("İplikçi Nedim'i aç", () => {
  it("brings a tab that shows the interface to the front and asks nothing of the service", async () => {
    const service = fakeService();
    const { tabs, done } = fakeTabs([tab(3, { lastAccessed: 5 }), tab(4, { lastAccessed: 9 }), tab(5, SIGN_IN)]);
    const answer = await openPanel({ service: service.fetcher, tabs }, PAIRED);
    expect(answer.outcome).toBe("shown");
    expect(done).toEqual(["show 4"]); // the one looked at last, not the sign-in page
    expect(service.asked).toEqual([]);
  });

  it("opens a login link once the service proves itself, in a new tab when none is open", async () => {
    const service = fakeService();
    const { tabs, done } = fakeTabs();
    const answer = await openPanel({ service: service.fetcher, tabs }, PAIRED);
    expect(answer).toEqual({ outcome: "signed-in", detail: "İplikçi Nedim açıldı." });
    expect(done).toEqual([`open ${LINK}`]);
    expect(service.asked).toEqual([
      { path: "/api/bridge/hello", method: "GET", auth: "" }, // the proof first: the token is not sent to it
      { path: "/api/bridge/login-link", method: "POST", auth: `Bearer ${PAIRED.token}` },
    ]);
  });

  it("opens the link in the tab that shows the service's sign-in page", async () => {
    const signIn = fakeTabs([tab(7, SIGN_IN)]);
    await openPanel({ service: fakeService().fetcher, tabs: signIn.tabs }, PAIRED);
    expect(signIn.done).toEqual([`show 7 ${LINK}`]);
    const expired = fakeTabs([tab(8, { url: `${SERVICE}/giris?anahtar=eski`, title: "127.0.0.1:8643/giris" })]);
    await openPanel({ service: fakeService().fetcher, tabs: expired.tabs }, PAIRED);
    expect(expired.done).toEqual([`show 8 ${LINK}`]); // on its way through a link, or left on a used one
  });

  it("opens a tab of the interface that is in front already again, signed in", async () => {
    // Its session may have ended, or it shows the browser's error page from when the service was not running.
    const { tabs, done } = fakeTabs([tab(2, { front: true, title: "127.0.0.1" }), tab(6, SIGN_IN)]);
    const answer = await openPanel({ service: fakeService().fetcher, tabs }, PAIRED);
    expect([answer.outcome, done]).toEqual(["signed-in", [`show 2 ${LINK}`]]);
  });

  it.each([
    ["another site", "https://kotu.example/giris?anahtar=x"],
    ["another port", "http://127.0.0.1:86430/giris?anahtar=x"],
    ["another page", `${SERVICE}/giris-baska?anahtar=x`],
    ["another host name", "http://localhost:8643/giris?anahtar=x"],
  ])("never opens a link to %s: the address opens without one", async (_where, link) => {
    const { tabs, done } = fakeTabs();
    const answer = await openPanel({ service: fakeService({ link: () => Response.json({ url: link }) }).fetcher, tabs }, PAIRED);
    expect(answer.outcome).toBe("opened");
    expect(done).toEqual([`open ${HOME}`]);
    expect(link.startsWith(LOGIN_PREFIX)).toBe(false);
  });

  it("sends nothing to a program that cannot prove it is the paired service, and opens nothing", async () => {
    const liar = fakeService({ lie: true });
    const { tabs, done } = fakeTabs([tab(1, SIGN_IN)]);
    const answer = await openPanel({ service: liar.fetcher, tabs }, PAIRED);
    expect(answer).toEqual({
      outcome: "not-the-service",
      detail: "Bu bilgisayarda eşleşilen İplikçi Nedim yerine başka bir program yanıt veriyor; açılmadı.",
    });
    expect(liar.asked.map((a) => a.path)).toEqual(["/api/bridge/hello"]); // no token, no request for a link
    expect(done).toEqual([]);
  });

  it("says the service is not running and opens nothing", async () => {
    const { tabs, done } = fakeTabs();
    const answer = await openPanel({ service: fakeService({ down: true }).fetcher, tabs }, PAIRED);
    expect(answer).toEqual({
      outcome: "service-down",
      detail: "İplikçi Nedim bu bilgisayarda çalışmıyor; uygulamayı açıp yeniden deneyin.",
    });
    expect(done).toEqual([]);
  });

  it("opens the address without a link when not paired, reusing the sign-in page's tab", async () => {
    const service = fakeService();
    const none = fakeTabs();
    const answer = await openPanel({ service: service.fetcher, tabs: none.tabs }, null);
    expect([answer.outcome, none.done]).toEqual(["opened", [`open ${HOME}`]]); // the browser may hold a session
    const signIn = fakeTabs([tab(9, SIGN_IN)]);
    await openPanel({ service: service.fetcher, tabs: signIn.tabs }, null);
    expect(signIn.done).toEqual([`show 9 ${HOME}`]);
    expect(service.asked).toEqual([]);
  });

  it("opens the address without a link when the pairing was revoked or the service is older", async () => {
    const revoked = fakeTabs();
    const gone = await openPanel({ service: fakeService({ revoked: true }).fetcher, tabs: revoked.tabs }, PAIRED);
    expect([gone.outcome, revoked.done]).toEqual(["opened", [`open ${HOME}`]]);
    expect(gone.detail).toContain("Eşleşme İplikçi Nedim'de iptal edilmiş");
    const refused = () => Response.json({ code: "forbidden", title: "Bu işlem bu oturumla yapılamaz." }, { status: 403 });
    const older = fakeTabs();
    const before = await openPanel({ service: fakeService({ link: refused }).fetcher, tabs: older.tabs }, PAIRED);
    expect([before.outcome, older.done]).toEqual(["opened", [`open ${HOME}`]]);
    expect(before.detail).toBe("İplikçi Nedim bu eklentiden eski bir sürüm; adres giriş bağlantısı olmadan açıldı.");
    const odd = await openPanel({ service: fakeService({ link: () => Response.json({}) }).fetcher, tabs: fakeTabs().tabs }, PAIRED);
    expect(odd.outcome).toBe("opened");
  });

  it("tells a sign-in page by its title or by the login address", () => {
    expect(signingIn(tab(1, SIGN_IN))).toBe(true);
    expect(signingIn(tab(1, { url: `${SERVICE}/giris?anahtar=x` }))).toBe(true);
    expect(signingIn(tab(1))).toBe(false);
    expect(signingIn(tab(1, { url: `${SERVICE}/girisler`, title: "Girişler · İplikçi Nedim" }))).toBe(false);
  });

  it("is a request only the extension's own pages make, checked like the others", () => {
    expect(asRequest({ kind: "open-panel" })).toEqual({ kind: "open-panel" });
    expect(asRequest({ kind: "open-panel", url: "https://kotu.example" })).toEqual({ kind: "open-panel" });
  });
});

/** The part of Chrome the panel's tabs use, recording each call. */
function fakeChrome(tabs: Array<Partial<chrome.tabs.Tab>>, options: { gone?: boolean } = {}) {
  const calls: unknown[][] = [];
  const api = {
    tabs: {
      query: vi.fn(async (query: chrome.tabs.QueryInfo) => {
        calls.push(["query", query]);
        return tabs;
      }),
      update: vi.fn(async (id: number, change: chrome.tabs.UpdateProperties) => {
        calls.push(["update", id, change]);
        if (options.gone) {
          throw new Error("No tab with id");
        }
        return {};
      }),
      create: vi.fn(async (properties: chrome.tabs.CreateProperties) => {
        calls.push(["create", properties]);
        return { id: 99 };
      }),
    },
    windows: {
      getLastFocused: vi.fn(async () => ({ id: 2 })),
      update: vi.fn(async (id: number, change: chrome.windows.UpdateInfo) => {
        calls.push(["focus", id, change]);
        return {};
      }),
    },
  };
  vi.stubGlobal("chrome", api);
  return calls;
}

describe("the interface's tabs in Chrome", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("finds the tabs on the service's address only, and which one is in front of the window in use", async () => {
    const calls = fakeChrome([
      { id: 1, windowId: 2, url: `${SERVICE}/`, title: "Akış · İplikçi Nedim", active: true, lastAccessed: 50 },
      { id: 2, windowId: 3, url: `${SERVICE}/hesaplar`, title: SIGN_IN_TITLE, active: true },
      { id: 3, windowId: 2, url: "https://mail.google.com/mail/u/0/", active: false }, // not asked for: left out
      { windowId: 2, url: `${SERVICE}/` }, // no id: a tab of a devtools window
    ]);
    const found = await chromePanelTabs.find();
    expect(calls[0]).toEqual(["query", { url: `${SERVICE}/*` }]); // the host permission, no "tabs" permission
    expect(found).toEqual([
      { id: 1, windowId: 2, url: `${SERVICE}/`, title: "Akış · İplikçi Nedim", front: true, lastAccessed: 50 },
      { id: 2, windowId: 3, url: `${SERVICE}/hesaplar`, title: SIGN_IN_TITLE, front: false, lastAccessed: 0 },
    ]);
  });

  it("brings a tab and its window to the front, showing a link in it first when there is one", async () => {
    const calls = fakeChrome([]);
    await chromePanelTabs.show(tab(4, { windowId: 6 }));
    await chromePanelTabs.show(tab(5, { windowId: 6 }), LINK);
    await chromePanelTabs.open(HOME);
    expect(calls).toEqual([
      ["update", 4, { active: true }],
      ["focus", 6, { focused: true }],
      ["update", 5, { url: LINK, active: true }],
      ["focus", 6, { focused: true }],
      ["create", { url: HOME, active: true }],
    ]);
  });

  it("opens a new tab when the one it meant to show was closed meanwhile", async () => {
    const calls = fakeChrome([], { gone: true });
    await chromePanelTabs.show(tab(4), LINK);
    await chromePanelTabs.show(tab(5));
    expect(calls.filter(([name]) => name === "create")).toEqual([
      ["create", { url: LINK, active: true }],
      ["create", { url: `${SERVICE}/hesaplar`, active: true }],
    ]);
  });
});
