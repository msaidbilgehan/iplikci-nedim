/**
 * The content script in the user's Gmail tabs (the manifest's content_scripts: https://mail.google.com/*, once the
 * page is idle). It tells the service worker which listed senders' messages the tab shows, read or not, so that a bank
 * message read in Gmail before the next minute's run is taken all the same (ADR-0016, note of 2026-11-10). What it
 * reads of the page is gmail/visible.ts's; only Gmail's ids leave it, and only for the service worker.
 */

import type { TabRequest } from "./bridge/messages";
import { type Watch, asWatch, watchGmail } from "./gmail/visible";

const watcher = watchGmail(document, {
  watch: () => ask({ kind: "gmail-watch" }),
  seen: (ids) => ask({ kind: "gmail-seen", ids }),
});

async function ask(request: TabRequest): Promise<Watch | null> {
  try {
    return asWatch(await chrome.runtime.sendMessage(request));
  } catch {
    // The extension was reloaded or removed while the page stayed open: this script is left over and stops. Any
    // other trouble is the service worker's for now; the next read asks again.
    if (typeof chrome.runtime?.id !== "string") {
      watcher.stop();
    }
    return null;
  }
}
