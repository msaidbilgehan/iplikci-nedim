/**
 * The tabs of Chrome the bridge drives.
 *
 * - The scan's tab: opened on Gmail's search, read with the collector (chrome.scripting), moved from page to page and
 *   closed when the scan has what it needs, the tab the scan was started from shown again. Only mail.google.com is
 *   touched, as the manifest's host permission allows; on any other address the tab is not read.
 * - The interface's tabs, for "İplikçi Nedim'i aç": the host permission for the service's address lets their address
 *   and title be read, and no others'; the extension has no "tabs" permission.
 */

import { FormatError } from "../gmail/errors";
import { ORIGIN } from "../gmail/http";
import { collectList, isListPage } from "../gmail/list";
import type { PanelTabs, ServiceTab } from "./panel";
import { NotGmail, type TabDriver, TabGone, TabUnreadable } from "./scan";
import { SERVICE } from "./service";

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

/** The tabs on the service's address, as "İplikçi Nedim'i aç" finds, shows and opens them. */
export const chromePanelTabs: PanelTabs = {
  async find() {
    const [tabs, focused] = await Promise.all([
      chrome.tabs.query({ url: `${SERVICE}/*` }),
      chrome.windows.getLastFocused().catch(() => undefined),
    ]);
    const found: ServiceTab[] = [];
    for (const tab of tabs) {
      const url = tab.url ?? "";
      if (tab.id !== undefined && url.startsWith(`${SERVICE}/`)) {
        found.push({
          id: tab.id,
          windowId: tab.windowId,
          url,
          title: tab.title ?? "",
          front: tab.active && tab.windowId === focused?.id,
          lastAccessed: tab.lastAccessed ?? 0, // Chrome 121 on
        });
      }
    }
    return found;
  },
  async show(tab, url) {
    try {
      await chrome.tabs.update(tab.id, url === undefined ? { active: true } : { url, active: true });
    } catch {
      await chrome.tabs.create({ url: url ?? tab.url, active: true }); // the tab was closed meanwhile
      return;
    }
    await chrome.windows.update(tab.windowId, { focused: true });
  },
  async open(url) {
    await chrome.tabs.create({ url, active: true });
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
