/**
 * The bridge's service worker (ADR-0016): every minute (and when the browser starts) it delivers the inbox's new
 * bank messages to the paired service, and those an open Gmail tab showed, read or not, as its content script tells
 * it; it pairs with a code typed into the extension's settings page and then scans Gmail for the history the service
 * lacks; it opens the service's interface for "İplikçi Nedim'i aç" (ADR-0019); it asks the service for İplikçi
 * Nedim's lines on the money the window shows (ADR-0020); and it runs the ADR-0016 verification for its own page. All
 * network work happens here, never in a page or a content script. The toolbar button opens the extension's window
 * (popup.html); its settings page is options.html.
 */

import { type Request, type Status, type TabRequest, asRequest, asTabRequest } from "./bridge/messages";
import { openPanel } from "./bridge/panel";
import { type RunEnvironment, deliverNew } from "./bridge/run";
import { hear } from "./bridge/sayings";
import { scanGmail } from "./bridge/scan";
import { unhandled, watchFor } from "./bridge/seen";
import { NotTheService, Refused, ServiceDown, cursor, pair, prove } from "./bridge/service";
import { type ScanSummary, chromeStore } from "./bridge/state";
import { scansFirst } from "./bridge/steps";
import { chromePanelTabs, chromeTabs } from "./bridge/tabs";
import { Turns } from "./bridge/turns";
import { type Watch, accountOf } from "./gmail/visible";
import { type Environment, verify } from "./verify/run";

const ALARM = "yeni-iletiler";
/** How long "İplikçi Nedim'i aç" waits for the service: a service that does not answer counts as not running. */
const PANEL_WAIT_MS = 5000;
/** One delivery run or scan at a time; the ids the Gmail tabs tell wait there for the next run. */
const turns = new Turns(async (shown) => deliverNew(await environment(), chromeStore, shown));

chrome.runtime.onInstalled.addListener(() => void schedule());
chrome.runtime.onStartup.addListener(() => {
  void schedule();
  void turns.run();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) {
    void turns.run();
  }
});
void schedule(); // an alarm may be gone after a browser restart
void forgetUnfinishedScan();

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  const reply = (work: Promise<unknown>): true => {
    work.then(sendResponse, () => sendResponse(null));
    return true; // the answer comes later
  };
  if (sender.id === chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL("")) === true) {
    const request = asRequest(message);
    return request !== null && reply(answer(request, sender.tab?.id));
  }
  const account = gmailTab(sender);
  const told = account === null ? null : asTabRequest(message);
  return told !== null && account !== null && reply(answerTab(told, account));
});

async function schedule(): Promise<void> {
  if ((await chrome.alarms.get(ALARM)) === undefined) {
    await chrome.alarms.create(ALARM, { periodInMinutes: 1, delayInMinutes: 0.1 });
  }
}

/**
 * The scan of Gmail ("Gmail'de eksikleri tara"), one at a time; a delivery run under way finishes first. The window
 * that started it is shown again when the scan's tab closes.
 */
function scanOnce(returnTo: number | undefined): Promise<ScanSummary> {
  return turns.scan(async () => scanGmail({ ...(await environment()), tabs: chromeTabs(returnTo) }, chromeStore));
}

/** The Google account of the Gmail tab whose content script sent a message, from its top frame's address. */
function gmailTab(sender: chrome.runtime.MessageSender): number | null {
  const ours = sender.id === chrome.runtime.id && sender.tab !== undefined && sender.frameId === 0;
  return ours ? accountOf(sender.url ?? "") : null;
}

/**
 * A Gmail tab's request: what to look for while the bridge takes messages from that tab (paired, the account it
 * reads, the layers running, no scan: the scan reads Gmail itself, its own tab included); the ids the tab shows that
 * the bridge has not dealt with wait for the next run.
 */
async function answerTab(request: TabRequest, account: number): Promise<Watch | null> {
  const state = await chromeStore.get();
  const watch = turns.scanning ? null : watchFor(state, chrome.runtime.getManifest().version, account);
  if (watch !== null && request.kind === "gmail-seen") {
    turns.seen(unhandled(state, request.ids));
  }
  return watch;
}

/**
 * A check asked for by hand, or the first after pairing: while the service lacks the history, a scan of Gmail (it
 * delivers the new messages too), else a delivery run. A scan is not awaited: it runs for minutes and the window
 * follows it through the stored state. No scan starts unasked, as its tab would come up over whatever the user does.
 */
async function checkNow(from: number | undefined): Promise<void> {
  if (scansFirst(await chromeStore.get(), chrome.runtime.getManifest().version)) {
    void scanOnce(from);
    return;
  }
  await turns.run();
}

/** A scan that was under way when the worker stopped (the browser closed, the extension reloaded) is over. */
async function forgetUnfinishedScan(): Promise<void> {
  const { scan } = await chromeStore.get();
  if (!turns.scanning && scan !== null && (scan.phase === "searching" || scan.phase === "downloading")) {
    await chromeStore.update({
      scan: { ...scan, phase: "stopped", detail: "Tarama yarıda kaldı; yeniden başlatılabilir, kaldığı yerden sürer." },
    });
  }
}

async function answer(request: Request, from: number | undefined): Promise<unknown> {
  switch (request.kind) {
    case "verify":
      return verify(await verifyEnvironment(), request.account);
    case "status":
      return status("");
    case "pair": {
      const problem = await pairWith(request.code);
      if (problem === "") {
        void checkNow(from);
      }
      return status(problem);
    }
    case "account":
      // another account starts afresh: a wait Gmail asked for was for the one before, and Gmail's ids are each
      // mailbox's own
      turns.forget();
      await chromeStore.update({ account: request.account, calmUntil: 0, failures: 0, seen: [], known: [] });
      return status("");
    case "run":
      // asked for by hand: the wait after a trouble does not hold back a single check
      await chromeStore.update({ calmUntil: 0 });
      await checkNow(from);
      return status("");
    case "scan":
      void scanOnce(from); // it runs for minutes: the window follows it through the stored state
      return status("");
    case "forget":
      turns.forget();
      await chromeStore.update({ paired: null, lastRun: null, seen: [], known: [] });
      return status("");
    case "open-panel":
      return openPanel({ service: answeringSoon, tabs: chromePanelTabs }, (await chromeStore.get()).paired);
    case "sayings":
      return hear(answeringSoon, (await chromeStore.get()).paired);
  }
}

/** The service, for "İplikçi Nedim'i aç" and his lines: the window waits for it, so a service that hangs does not hold
 * it. */
function answeringSoon(url: string, init: RequestInit): Promise<Response> {
  return fetch(url, { ...init, signal: AbortSignal.timeout(PANEL_WAIT_MS) });
}

async function status(problem: string): Promise<Status> {
  const state = await chromeStore.get();
  const version = chrome.runtime.getManifest().version;
  return {
    paired: state.paired !== null,
    account: state.account,
    lastRun: state.lastRun,
    scan: state.scan,
    historyDue: state.paired !== null && state.historyDue,
    startDay: state.startDay,
    stopped: Object.keys(state.stopped).filter((layer) => state.stopped[layer] === version),
    problem,
  };
}

/**
 * Pair with a code; the problem in Turkish, "" when it worked. The new service proves itself before it is kept, and
 * says whether it lacks the history.
 */
async function pairWith(code: string): Promise<string> {
  const env = await environment();
  try {
    const paired = await pair(env.service, code, await browserLabel());
    await prove(env.service, paired);
    const where = await cursor(env.service, paired);
    await chromeStore.update({
      paired,
      stopped: {},
      calmUntil: 0,
      failures: 0,
      lastRun: null,
      historyDue: where.historyDue,
      startDay: where.startDay,
      senders: where.senders,
      seen: [], // what the bridge knew of the messages was the service's paired before
      known: [],
    });
    turns.forget();
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
