/**
 * The scan's tab in Chrome: opened on Gmail's search, read with the collector (chrome.scripting), moved from page to
 * page and closed when the scan has what it needs, the tab the scan was started from shown again. Only
 * mail.google.com is touched, as the manifest's host permission allows; on any other address the tab is not read.
 */

import { FormatError } from "../gmail/errors";
import { ORIGIN } from "../gmail/http";
import { collectList, isListPage } from "../gmail/list";
import { NotGmail, type TabDriver, TabGone, TabUnreadable } from "./scan";

const LOAD_MS = 60_000;

/** The tabs of Chrome; `returnTo` is the tab shown again when the scan's tab closes (the extension's window). */
export function chromeTabs(returnTo?: number): TabDriver {
  return { ...driver, close: (tab) => closeAndReturn(tab, returnTo) };
}

async function closeAndReturn(tabId: number, returnTo: number | undefined): Promise<void> {
  await chrome.tabs.remove(tabId);
  if (returnTo !== undefined) {
    await chrome.tabs.update(returnTo, { active: true }).catch(() => undefined); // closed meanwhile
  }
}

const driver: TabDriver = {
  async open(url) {
    const tab = await chrome.tabs.create({ url, active: true });
    if (tab.id === undefined) {
      throw new TabGone("Gmail sekmesi açılamadı");
    }
    await loaded(tab.id);
    return tab.id;
  },
  async collect(tabId, waitMs, before) {
    await onGmail(tabId);
    const [injection] = await inject(() =>
      chrome.scripting.executeScript({ target: { tabId }, func: collectList, args: [waitMs, before] }),
    );
    const page: unknown = injection?.result;
    if (!isListPage(page)) {
      throw new FormatError("Gmail'in arama listesi beklenen biçimde okunamadı");
    }
    return page;
  },
  async go(tabId, hash) {
    await onGmail(tabId);
    await inject(() =>
      chrome.scripting.executeScript({
        target: { tabId },
        func: (to: string) => {
          window.location.hash = to;
        },
        args: [hash],
      }),
    );
  },
  async close(tabId) {
    await chrome.tabs.remove(tabId);
  },
};

/** Run a script in the tab; a tab showing an error page (Gmail did not load) refuses scripts. */
async function inject<T>(run: () => Promise<T>): Promise<T> {
  try {
    return await run();
  } catch {
    throw new TabUnreadable("Gmail sekmesine betik çalıştırılamadı");
  }
}

/** The tab is still open and on Gmail; its address is readable only there (the host permission). */
async function onGmail(tabId: number): Promise<void> {
  let url: string | undefined;
  try {
    url = (await chrome.tabs.get(tabId)).url;
  } catch {
    throw new TabGone("tarama sekmesi kapandı");
  }
  if (!(url ?? "").startsWith(`${ORIGIN}/`)) {
    throw new NotGmail("sekme Gmail'de değil");
  }
}

function loaded(tabId: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const finish = (error?: Error): void => {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      if (error === undefined) {
        resolve();
      } else {
        reject(error);
      }
    };
    const listener = (id: number, change: chrome.tabs.OnUpdatedInfo): void => {
      if (id === tabId && change.status === "complete") {
        finish();
      }
    };
    const timer = setTimeout(() => finish(new TabGone("Gmail sekmesi bir dakikada yüklenmedi")), LOAD_MS);
    chrome.tabs.onUpdated.addListener(listener);
    // It may have loaded before the listener was there.
    chrome.tabs.get(tabId).then(
      (tab) => {
        if (tab.status === "complete") {
          finish();
        }
      },
      () => finish(new TabGone("tarama sekmesi kapandı")),
    );
  });
}
