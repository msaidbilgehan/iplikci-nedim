/**
 * The extension's window, from its toolbar button: where the bridge stands, "İplikçi Nedim'i aç", "Şimdi denetle" and
 * the way to the settings page. Pairing, the Gmail account and the scan of Gmail live there, as this window closes
 * when the focus leaves it: the pairing code is copied from İplikçi Nedim's page, and the scan runs for minutes.
 */

import type { Status } from "../bridge/messages";
import { IN_FRONT, ask, draw, element, openInterface, say, statusCard, version } from "../ui/dom";
import { CHECKING, describe, scanning } from "../ui/status";

const card = statusCard();
const note = element("status-note", HTMLParagraphElement);
const open = element("open", HTMLButtonElement);
const now = element("now", HTMLButtonElement);
const answer = element("open-answer", HTMLParagraphElement);
const settings = element("settings", HTMLButtonElement);
element("version", HTMLSpanElement).textContent = version();

const UNPAIRED = "Eşleştirme kodunu girmek için “Eşleştirme ve ayarlar”ı açın.";
const HISTORY_DUE = "Geçmiş iletiler taranmayı bekliyor: “Şimdi denetle” önce Gmail'i yeni bir sekmede tarar.";

function show(status: Status | null): void {
  draw(card, describe(status, UNPAIRED));
  const busy = status !== null && scanning(status.scan);
  now.disabled = status === null || !status.paired || busy; // a scan delivers the new messages too
  const due = status !== null && status.paired && status.historyDue && !busy;
  say(note, due ? HISTORY_DUE : "");
  note.hidden = !due;
}

open.addEventListener("click", () => {
  void (async () => {
    const result = await openInterface(open, answer);
    if (result !== null && IN_FRONT.has(result.outcome)) {
      window.close(); // the interface is in front: the window has nothing more to say
    }
  })();
});

now.addEventListener("click", () => {
  void (async () => {
    const focused = document.activeElement === now;
    now.disabled = true;
    draw(card, CHECKING);
    show(await ask({ kind: "run" }));
    if (focused && !now.disabled) {
      now.focus();
    }
  })();
});

settings.addEventListener("click", () => {
  void chrome.runtime.openOptionsPage().then(() => window.close());
});

async function refresh(): Promise<void> {
  show(await ask({ kind: "status" }));
}

// A run in the background changes what the window shows: it follows without being opened again.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    void refresh();
  }
});

void refresh();
