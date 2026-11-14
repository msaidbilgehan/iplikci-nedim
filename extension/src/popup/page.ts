/**
 * The extension's window, from its toolbar button: İplikçi Nedim's word on the money under his face (ADR-0020), where
 * the bridge stands, "İplikçi Nedim'i aç", "Şimdi denetle" and the way to the settings page. Pairing, the Gmail
 * account and the scan of Gmail live there, as this window closes when the focus leaves it: the pairing code is
 * copied from İplikçi Nedim's page, and the scan runs for minutes. Not paired, with no program answering on this
 * computer, the window offers the program's download and its steps instead (ADR-0024).
 */

import type { Status } from "../bridge/messages";
import type { Saying } from "../bridge/service";
import { IN_FRONT, ask, askSayings, draw, element, openInterface, say, statusCard, version } from "../ui/dom";
import { FACES, spoken } from "../ui/nedim";
import { type Guide, type Seen, follow, guideHere, openDownload, showGuide } from "../ui/program";
import { CHECKING, NO_PROGRAM, describe, scanning } from "../ui/status";

const card = statusCard();
const note = element("status-note", HTMLParagraphElement);
const open = element("open", HTMLButtonElement);
const now = element("now", HTMLButtonElement);
const answer = element("open-answer", HTMLParagraphElement);
const settings = element("settings", HTMLButtonElement);
const face = element("brand-logo", HTMLImageElement);
const nedim = element("nedim", HTMLElement);
const line = element("nedim-line", HTMLElement);
const reason = element("nedim-reason", HTMLElement);
const another = element("nedim-next", HTMLButtonElement);
const program = element("program", HTMLElement);
const download = element("download", HTMLButtonElement);
const guideParts = {
  label: element("download-label", HTMLSpanElement),
  target: element("download-for", HTMLParagraphElement),
  steps: element("program-steps", HTMLOListElement),
};
element("version", HTMLSpanElement).textContent = version();

let heard: Saying[] = [];
let turn = 0;
let guide: Guide | null = null;
/** Not paired, and nothing answers on the service's address, at the last look. */
let missing = false;

const UNPAIRED = "Eşleştirme kodunu girmek için “Eşleştirme ve ayarlar”ı açın.";
const HISTORY_DUE = "Geçmiş iletiler taranmayı bekliyor: “Şimdi denetle” önce Gmail'i yeni bir sekmede tarar.";
const WATCHING = "Gmail açıkken görünen banka iletileri, okunmuş olsalar da, kendiliğinden alınır.";

function show(seen: Seen): void {
  const { status } = seen;
  missing = seen.missing;
  draw(card, missing ? NO_PROGRAM : describe(status, UNPAIRED));
  program.hidden = !missing;
  open.hidden = missing; // nothing to open yet: the download is the window's act then
  now.hidden = missing;
  if (missing && document.activeElement === document.body) {
    download.focus(); // where "İplikçi Nedim'i aç", hidden now, had it
  }
  const busy = status !== null && scanning(status.scan);
  now.disabled = status === null || !status.paired || busy; // a scan delivers the new messages too
  say(note, status === null || !status.paired || busy ? "" : noteFor(status));
  note.hidden = note.textContent === "";
}

/** What a request to the service worker answered; the program's presence as the last look found it. */
function showStatus(status: Status | null): void {
  show({ status, missing: missing && status !== null && !status.paired });
}

/** What the window adds under the status: the history still to scan, else what an open Gmail tab brings. */
function noteFor(status: Status): string {
  if (status.historyDue) {
    return HISTORY_DUE;
  }
  // the list and "Show original" (layers 2 and 3) take what a Gmail tab shows
  return status.stopped.includes("2") || status.stopped.includes("3") ? "" : WATCHING;
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
    showStatus(await ask({ kind: "run" }));
    if (focused && !now.disabled) {
      now.focus();
    }
  })();
});

settings.addEventListener("click", () => {
  void chrome.runtime.openOptionsPage().then(() => window.close());
});

download.addEventListener("click", () => {
  if (guide !== null) {
    void openDownload(guide); // the browser downloads it in the new tab; this window closes as the tab comes up
  }
});

/** The line in turn under his face, its colour on the face; nothing of the money without one. */
function speak(): void {
  const said = heard[turn];
  nedim.hidden = said === undefined;
  face.src = said === undefined ? FACES.good : FACES[said.mood];
  if (said === undefined) {
    return;
  }
  nedim.dataset["mood"] = said.mood;
  say(line, spoken(said.lines));
  say(reason, said.reason);
  another.hidden = heard.length < 2;
}

another.addEventListener("click", () => {
  turn = (turn + 1) % Math.max(heard.length, 1);
  speak();
});

async function listen(): Promise<void> {
  heard = await askSayings();
  turn = 0;
  speak();
}

/** Where the bridge stands now, and again every few seconds while the program is missing. */
const refresh = follow(show);

// A run in the background changes what the window shows: it follows without being opened again.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    void refresh();
  }
});

void guideHere().then((found) => {
  guide = found;
  showGuide(guideParts, found);
});
void refresh();
void listen();
