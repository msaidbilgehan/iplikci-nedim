/**
 * The bridge's service worker (ADR-0016). For now it runs the verification for the extension's own page; pairing,
 * the three layers and delivery to the service come once the verification has passed.
 */

import { type Environment, verify } from "./verify/run";

interface VerifyRequest {
  readonly kind: "verify";
  readonly account: number;
}

function isVerifyRequest(message: unknown): message is VerifyRequest {
  if (typeof message !== "object" || message === null) {
    return false;
  }
  const { kind, account } = message as Record<string, unknown>;
  return kind === "verify" && typeof account === "number" && Number.isInteger(account) && account >= 0 && account < 10;
}

chrome.action.onClicked.addListener(() => {
  void chrome.runtime.openOptionsPage();
});

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  const fromOwnPage = sender.id === chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL("")) === true;
  if (!fromOwnPage || !isVerifyRequest(message)) {
    return false;
  }
  environment()
    .then((env) => verify(env, message.account))
    .then(sendResponse, () => sendResponse(null));
  return true; // the answer comes later
});

async function environment(): Promise<Environment> {
  const platform = await chrome.runtime.getPlatformInfo();
  return {
    fetcher: (url, init) => fetch(url, init),
    sleep: async (ms) => {
      await new Promise((resolve) => setTimeout(resolve, ms));
      // Chrome stops a service worker that stays idle for 30 seconds; calling an extension API resets that timer,
      // so a slow run is not cut short.
      await chrome.runtime.getPlatformInfo();
    },
    os: platform.os,
    browser: browserName(navigator.userAgent),
    version: chrome.runtime.getManifest().version,
    now: () => new Date(),
  };
}

function browserName(agent: string): string {
  const edge = /Edg\/(\d+)/.exec(agent)?.[1];
  if (edge !== undefined) {
    return `Edge ${edge}`;
  }
  const chromium = /Chrome\/(\d+)/.exec(agent)?.[1];
  return chromium === undefined ? "bilinmeyen tarayıcı" : `Chrome ${chromium} (ya da Chromium tabanlı bir tarayıcı)`;
}
