/**
 * The extension's window, from its toolbar button: İplikçi Nedim's word on the money under his face (ADR-0020), where
 * the bridge stands, "İplikçi Nedim'i aç", "Şimdi denetle" and the way to the settings page. Pairing, the Gmail
 * account and the scan of Gmail live there, as this window closes when the focus leaves it: the pairing code is
 * copied from İplikçi Nedim's page, and the scan runs for minutes.
 */

import type { Status } from "../bridge/messages";
import type { Saying } from "../bridge/service";
import { IN_FRONT, ask, askSayings, draw, element, openInterface, say, statusCard, version } from "../ui/dom";
import { FACES, spoken } from "../ui/nedim";
import { CHECKING, describe, scanning } from "../ui/status";

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
element("version", HTMLSpanElement).textContent = version();

let heard: Saying[] = [];
let turn = 0;

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
void listen();
