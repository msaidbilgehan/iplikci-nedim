/**
 * The bridge's service worker (ADR-0016): every minute (and when the browser starts) it delivers the inbox's new
 * bank messages to the paired service; it pairs with a code typed into the extension's settings page and then scans
 * Gmail for the history the service lacks; it opens the service's interface for "İplikçi Nedim'i aç" (ADR-0019); and
 * it runs the ADR-0016 verification for its own page. All network work happens here, never in a page or a content
 * script.
 */

import { type Request, type Status, asRequest } from "./bridge/messages";
import { openPanel } from "./bridge/panel";
import { type RunEnvironment, deliverNew } from "./bridge/run";
import { scanGmail } from "./bridge/scan";
import { NotTheService, Refused, ServiceDown, cursor, pair, prove } from "./bridge/service";
import { type RunSummary, type ScanSummary, chromeStore } from "./bridge/state";
import { scansFirst } from "./bridge/steps";
import { chromePanelTabs, chromeTabs } from "./bridge/tabs";
import { type Environment, verify } from "./verify/run";

const ALARM = "yeni-iletiler";
/** How long "İplikçi Nedim'i aç" waits for the service: a service that does not answer counts as not running. */
const PANEL_WAIT_MS = 5000;
let running: Promise<RunSummary> | null = null;
let scanning: Promise<ScanSummary> | null = null;

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
void forgetUnfinishedScan();

chrome.action.onClicked.addListener(() => {
  void chrome.runtime.openOptionsPage();
});

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  const fromOwnPage = sender.id === chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL("")) === true;
  const request = fromOwnPage ? asRequest(message) : null;
  if (request === null) {
    return false;
  }
  answer(request, sender.tab?.id).then(sendResponse, () => sendResponse(null));
  return true; // the answer comes later
});

async function schedule(): Promise<void> {
  if ((await chrome.alarms.get(ALARM)) === undefined) {
    await chrome.alarms.create(ALARM, { periodInMinutes: 1, delayInMinutes: 0.1 });
  }
}

/**
 * One delivery run at a time: an alarm that comes during a run joins it. While a scan of Gmail runs, the scan holds
 * Gmail's one request a second and delivers in the meantime: no run starts.
 */
function runOnce(): Promise<RunSummary | null> {
  if (scanning !== null) {
    return Promise.resolve(null);
  }
  running ??= environment()
    .then((env) => deliverNew(env, chromeStore))
    .finally(() => {
      running = null;
    });
  return running;
}

/**
 * One scan of Gmail at a time ("Gmail'de eksikleri tara"); a delivery run under way finishes first. The window that
 * started it is shown again when the scan's tab closes.
 */
function scanOnce(returnTo: number | undefined): Promise<ScanSummary> {
  scanning ??= (async () => {
    await running?.catch(() => undefined);
    return scanGmail({ ...(await environment()), tabs: chromeTabs(returnTo) }, chromeStore);
  })().finally(() => {
    scanning = null;
  });
  return scanning;
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
  await runOnce();
}

/** A scan that was under way when the worker stopped (the browser closed, the extension reloaded) is over. */
async function forgetUnfinishedScan(): Promise<void> {
  const { scan } = await chromeStore.get();
  if (scanning === null && scan !== null && (scan.phase === "searching" || scan.phase === "downloading")) {
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
      // another account starts afresh: a wait Gmail asked for was for the one before
      await chromeStore.update({ account: request.account, calmUntil: 0, failures: 0 });
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
      await chromeStore.update({ paired: null, lastRun: null });
      return status("");
    case "open-panel":
      return openPanel({ service: answeringSoon, tabs: chromePanelTabs }, (await chromeStore.get()).paired);
  }
}

/** The service, for "İplikçi Nedim'i aç": the window waits for it, so a service that hangs does not hold it. */
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
    });
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
