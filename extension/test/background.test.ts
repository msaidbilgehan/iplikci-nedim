import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SERVICE } from "../src/bridge/service";

type Listener = (...args: never[]) => unknown;

/** The part of Chrome the service worker touches as it starts and as it answers; its listeners kept by event. */
function fakeChrome() {
  const listeners: Record<string, Listener> = {};
  const on = (name: string) => ({
    addListener: (listener: Listener) => {
      listeners[name] = listener;
    },
  });
  const api = {
    runtime: {
      id: "eklenti",
      getURL: (path: string) => `chrome-extension://eklenti/${path}`,
      getManifest: () => ({ version: "0.9.0" }),
      getPlatformInfo: vi.fn(async () => ({ os: "mac", arch: "arm64" })),
      openOptionsPage: vi.fn(async () => undefined),
      onInstalled: on("installed"),
      onStartup: on("startup"),
      onMessage: on("message"),
    },
    alarms: { get: vi.fn(async () => ({ name: "yeni-iletiler" })), create: vi.fn(), onAlarm: on("alarm") },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(), setAccessLevel: vi.fn(async () => undefined) } },
    tabs: { query: vi.fn(async () => []) },
    scripting: { executeScript: vi.fn(async () => []) },
  };
  vi.stubGlobal("chrome", api);
  return { api, listeners };
}

const OWN_PAGE = { id: "eklenti", url: "chrome-extension://eklenti/options.html" };
const GMAIL_TAB = { id: "eklenti", url: "https://mail.google.com/mail/u/0/#inbox", tab: { id: 3 }, frameId: 0 };

/** A message to the service worker as a page sends it; what it answers, or undefined when it does not. */
function send(listeners: Record<string, Listener>, message: unknown, sender: object = OWN_PAGE): Promise<unknown> {
  return new Promise((resolve) => {
    const later = (listeners["message"] as (m: unknown, s: object, r: (a: unknown) => void) => unknown)(
      message,
      sender,
      resolve,
    );
    if (later !== true) {
      resolve(undefined);
    }
  });
}

describe("the service worker", () => {
  beforeEach(() => {
    vi.resetModules(); // the worker's module starts afresh, as Chrome starts it
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens its settings page by itself when it is installed, and not when it is updated", async () => {
    const { api, listeners } = fakeChrome();
    await import("../src/background");
    const installed = listeners["installed"] as (details: { reason: string }) => void;
    installed({ reason: "update" });
    installed({ reason: "chrome_update" });
    expect(api.runtime.openOptionsPage).not.toHaveBeenCalled();
    installed({ reason: "install" });
    expect(api.runtime.openOptionsPage).toHaveBeenCalledTimes(1);
  });

  it("tells its own pages whether anything answers on the service's address, from its health check", async () => {
    const { listeners } = fakeChrome();
    const asked: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        asked.push(url);
        throw new TypeError("Failed to fetch"); // nothing listens: a computer without the program
      }),
    );
    await import("../src/background");
    expect(await send(listeners, { kind: "service" })).toEqual({ answers: false });
    vi.stubGlobal("fetch", vi.fn(async () => new Response('{"status": "ok"}', { status: 200 })));
    expect(await send(listeners, { kind: "service" })).toEqual({ answers: true });
    expect(asked).toEqual([`${SERVICE}/healthz`]);
  });

  it("answers that question to its own pages only, never to a Gmail tab", async () => {
    const { listeners } = fakeChrome();
    const fetched = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetched);
    await import("../src/background");
    expect(await send(listeners, { kind: "service" }, GMAIL_TAB)).toBeUndefined();
    expect(fetched).not.toHaveBeenCalled();
  });
});
