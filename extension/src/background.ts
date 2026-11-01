/**
 * The bridge's service worker (ADR-0016): every minute (and when the browser starts) it delivers the inbox's new
 * bank messages to the paired service; it pairs with a code typed into the extension's window; and it runs the
 * ADR-0016 verification for its own page. All network work happens here, never in a page or a content script.
 */

import { type Request, type Status, asRequest } from "./bridge/messages";
import { type RunEnvironment, deliverNew } from "./bridge/run";
import { NotTheService, Refused, ServiceDown, pair, prove } from "./bridge/service";
import { type RunSummary, chromeStore } from "./bridge/state";
import { type Environment, verify } from "./verify/run";

const ALARM = "yeni-iletiler";
let running: Promise<RunSummary> | null = null;

chrome.runtime.onInstalled.addListener(() => void schedule());
chrome.runtime.onStartup.addListener(() => {
  void schedule();
  void runOnce();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) {
    void runOnce();
  }
});
void schedule(); // an alarm may be gone after a browser restart

chrome.action.onClicked.addListener(() => {
  void chrome.runtime.openOptionsPage();
});

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  const fromOwnPage = sender.id === chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL("")) === true;
  const request = fromOwnPage ? asRequest(message) : null;
  if (request === null) {
    return false;
  }
  answer(request).then(sendResponse, () => sendResponse(null));
  return true; // the answer comes later
});

async function schedule(): Promise<void> {
  if ((await chrome.alarms.get(ALARM)) === undefined) {
    await chrome.alarms.create(ALARM, { periodInMinutes: 1, delayInMinutes: 0.1 });
  }
}

/** One delivery run at a time: an alarm that comes during a run joins it. */
function runOnce(): Promise<RunSummary> {
  running ??= environment()
    .then((env) => deliverNew(env, chromeStore))
    .finally(() => {
      running = null;
    });
  return running;
}

async function answer(request: Request): Promise<unknown> {
  switch (request.kind) {
    case "verify":
      return verify(await verifyEnvironment(), request.account);
    case "status":
      return status("");
    case "pair":
      return status(await pairWith(request.code));
    case "account":
      // another account starts afresh: a wait Gmail asked for was for the one before
      await chromeStore.update({ account: request.account, calmUntil: 0, failures: 0 });
      return status("");
    case "run":
      // asked for by hand: the wait after a trouble does not hold back a single check
      await chromeStore.update({ calmUntil: 0 });
      await runOnce();
      return status("");
    case "forget":
      await chromeStore.update({ paired: null, lastRun: null });
      return status("");
  }
}

async function status(problem: string): Promise<Status> {
  const state = await chromeStore.get();
  const version = chrome.runtime.getManifest().version;
  return {
    paired: state.paired !== null,
    account: state.account,
    lastRun: state.lastRun,
    stopped: Object.keys(state.stopped).filter((layer) => state.stopped[layer] === version),
    problem,
  };
}

/** Pair with a code; the problem in Turkish, "" when it worked. The new service proves itself before it is kept. */
async function pairWith(code: string): Promise<string> {
  const env = await environment();
  try {
    const paired = await pair(env.service, code, await browserLabel());
    await prove(env.service, paired);
    await chromeStore.update({ paired, stopped: {}, calmUntil: 0, failures: 0, lastRun: null });
  } catch (error) {
    if (error instanceof ServiceDown) {
      return "İplikçi Nedim bu bilgisayarda çalışmıyor; açıp yeniden deneyin.";
    }
    if (error instanceof Refused) {
      return error.message;
    }
    if (error instanceof NotTheService) {
      return "Bu bilgisayarda İplikçi Nedim yerine başka bir program yanıt veriyor; eşleşilmedi.";
    }
    return "Eşleştirilemedi; yeniden deneyin.";
  }
  void runOnce();
  return "";
}

async function environment(): Promise<RunEnvironment> {
  return {
    gmail: (url, init) => fetch(url, init),
    service: (url, init) => fetch(url, init),
    sleep: keepAwakeSleep,
    now: () => new Date(),
    version: chrome.runtime.getManifest().version,
  };
}

async function verifyEnvironment(): Promise<Environment> {
  const platform = await chrome.runtime.getPlatformInfo();
  return {
    fetcher: (url, init) => fetch(url, init),
    sleep: keepAwakeSleep,
    os: platform.os,
    browser: browserName(navigator.userAgent),
    version: chrome.runtime.getManifest().version,
    now: () => new Date(),
  };
}

async function keepAwakeSleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
  // Chrome stops a service worker that stays idle for 30 seconds; calling an extension API resets that timer, so a
  // slow run is not cut short.
  await chrome.runtime.getPlatformInfo();
}

const OS_NAMES: Readonly<Record<string, string>> = { mac: "macOS", win: "Windows", linux: "Linux", cros: "ChromeOS" };

/** How the paired service lists this browser: "Chrome 140, macOS". */
async function browserLabel(): Promise<string> {
  const platform = await chrome.runtime.getPlatformInfo();
  const browser = browserName(navigator.userAgent).replace(/ \(.*\)$/, "");
  return `${browser}, ${OS_NAMES[platform.os] ?? platform.os}`;
}

function browserName(agent: string): string {
  const edge = /Edg\/(\d+)/.exec(agent)?.[1];
  if (edge !== undefined) {
    return `Edge ${edge}`;
  }
  const chromium = /Chrome\/(\d+)/.exec(agent)?.[1];
  return chromium === undefined ? "bilinmeyen tarayıcı" : `Chrome ${chromium} (ya da Chromium tabanlı bir tarayıcı)`;
}
