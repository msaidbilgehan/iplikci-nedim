/**
 * The extension's settings page: where the bridge stands, "İplikçi Nedim'i aç", pairing with a code, the scan of
 * Gmail and which Gmail account to read. The extension's window (popup.html) leads here for all but the first two.
 * The page opens by itself when the extension is installed. Not paired, with no program answering on this computer,
 * it shows first how to download and install İplikçi Nedim, waits for the program and goes on to pairing once it
 * answers (ADR-0024).
 */

import type { Status } from "../bridge/messages";
import { RELEASES } from "../bridge/program";
import type { ScanSummary } from "../bridge/state";
import { ask, draw, element, openInterface, say, statusCard, version } from "../ui/dom";
import { type Guide, type Seen, follow, guideHere, openDownload, showGuide } from "../ui/program";
import { CHECKING, NO_PROGRAM, describe, scanning } from "../ui/status";

const card = statusCard();
const now = element("now", HTMLButtonElement);
const open = element("open", HTMLButtonElement);
const openAnswer = element("open-answer", HTMLParagraphElement);
const pairSummary = element("pair-summary", HTMLParagraphElement);
const pairForm = element("pair-form", HTMLFormElement);
const code = element("code", HTMLInputElement);
const codeHint = element("code-hint", HTMLParagraphElement);
const pairButton = element("pair", HTMLButtonElement);
const pairStatus = element("pair-status", HTMLParagraphElement);
const forget = element("forget", HTMLButtonElement);
const account = element("account", HTMLSelectElement);
const scan = element("scan", HTMLButtonElement);
const scanState = element("scan-state", HTMLParagraphElement);
const program = element("program", HTMLElement);
const download = element("download", HTMLButtonElement);
const guideParts = {
  label: element("download-label", HTMLSpanElement),
  target: element("download-for", HTMLParagraphElement),
  steps: element("program-steps", HTMLOListElement),
};
element("releases", HTMLAnchorElement).href = RELEASES;
element("version", HTMLSpanElement).textContent = version();

const UNPAIRED = "İplikçi Nedim'den aldığınız kodu aşağıdaki Eşleştirme bölümüne girin.";
const PAIR_LATER =
  "İplikçi Nedim kurulup açılınca eklenti onunla burada, programdan aldığınız tek kullanımlık bir kodla eşleşir.";
const PROGRAM_CAME =
  "İplikçi Nedim açıldı; şimdi eşleştirin. Kodu İplikçi Nedim'in “Tarayıcı eklentisi” sayfasında “Eşleştirme kodu " +
  "al”a basarak alın ve aşağıya girin.";
const TIME = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });
const DAY = new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" });

let guide: Guide | null = null;
/** Not paired, and nothing answers on the service's address, at the last look. */
let missing = false;

function show(seen: Seen): void {
  const { status } = seen;
  const came = missing && !seen.missing; // the program answers now: pairing goes on
  missing = seen.missing;
  draw(card, missing ? NO_PROGRAM : describe(status, UNPAIRED));
  program.hidden = !missing;
  open.hidden = missing; // nothing to open yet
  if (status === null) {
    return;
  }
  const busy = scanning(status.scan);
  account.value = String(status.account);
  forget.hidden = !status.paired;
  now.disabled = !status.paired || busy; // a scan delivers the new messages too
  pairForm.hidden = missing;
  codeHint.hidden = missing;
  say(
    pairSummary,
    status.paired
      ? "Bu tarayıcı İplikçi Nedim ile eşleşti. Yeni bir kodla yeniden eşleşebilir ya da eşleşmeyi unutabilirsiniz."
      : missing
        ? PAIR_LATER
        : "Eklenti İplikçi Nedim ile tek kullanımlık bir kodla eşleşir; sonra yeni banka iletileri her dakika, " +
          "Gmail'de görünenler de hemen taşınır.",
  );
  say(pairButton, status.paired ? "Yeniden eşleştir" : "Eşleştir");
  if (came && !status.paired) {
    say(pairStatus, PROGRAM_CAME);
    code.focus();
  }
  showScan(status, busy);
}

/** What a request to the service worker answered; the program's presence as the last look found it. */
function showStatus(status: Status | null): void {
  show({ status, missing: missing && status !== null && !status.paired });
}

function showScan(status: Status, busy: boolean): void {
  const summary = status.scan;
  scan.disabled = !status.paired || busy;
  say(scan, busy ? "Taranıyor…" : "Gmail'de eksikleri tara");
  if (!status.paired) {
    say(scanState, "Tarama için önce eşleştirin.");
  } else if (busy && summary !== null) {
    say(scanState, summary.detail);
  } else if (status.historyDue) {
    say(scanState, historyDue(status.startDay, summary));
  } else {
    say(scanState, summary === null ? "" : `${TIME.format(new Date(summary.at))} taraması: ${summary.detail}`);
  }
}

/** The service lacks the history: never scanned, a scan cut short, or the start day or the senders changed since. */
function historyDue(startDay: string, summary: ScanSummary | null): string {
  const start = startDay === "" ? "" : ` (başlangıç günü: ${DAY.format(new Date(`${startDay}T00:00:00`))})`;
  if (summary === null) {
    return `Geçmiş iletiler henüz taranmadı${start}. "Şimdi denetle" de önce bunu yapar.`;
  }
  const last = `${TIME.format(new Date(summary.at))} taraması: ${summary.detail}`;
  if (summary.phase !== "done") {
    return last;
  }
  const changed = "İplikçi Nedim'deki başlangıç günü ya da banka listesi o zamandan beri değişti";
  return `${last} ${changed}; geçmiş yeniden taranmalı${start}.`;
}

pairForm.addEventListener("submit", (event) => {
  event.preventDefault();
  void pairNow();
});

async function pairNow(): Promise<void> {
  const typed = code.value.trim();
  if (typed === "") {
    say(pairStatus, "Önce kodu girin.");
    code.focus();
    return;
  }
  const current = await ask({ kind: "status" });
  if (current?.paired && !window.confirm("Bu tarayıcı zaten eşleşmiş. Yeni kodla yeniden eşleşilsin mi?")) {
    return;
  }
  pairButton.disabled = true;
  say(pairStatus, "Eşleştiriliyor…");
  const status = await ask({ kind: "pair", code: typed });
  pairButton.disabled = false;
  if (status === null) {
    say(pairStatus, "Eşleştirilemedi; yeniden deneyin.");
    return;
  }
  say(pairStatus, status.problem === "" ? paired(status) : status.problem);
  if (status.problem === "") {
    code.value = "";
  }
  showStatus(status);
}

function paired(status: Status): string {
  return status.historyDue
    ? "Eşleşti. Geçmiş iletiler için Gmail yeni bir sekmede aranıyor; sekme arama bitince kendiliğinden kapanır."
    : "Eşleşti. Yeni banka iletileri her dakika, Gmail'de görünenler de hemen taşınır.";
}

open.addEventListener("click", () => {
  void openInterface(open, openAnswer); // the interface opens in another tab; this page says what happened
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

scan.addEventListener("click", () => {
  void (async () => {
    scan.disabled = true;
    showStatus(await ask({ kind: "scan" }));
  })();
});

forget.addEventListener("click", () => {
  void (async () => {
    if (!window.confirm("Bu tarayıcıdaki eşleşme unutulsun mu? İplikçi Nedim'in sayfasından da iptal edebilirsiniz.")) {
      return;
    }
    showStatus(await ask({ kind: "forget" }));
    say(pairStatus, "Eşleşme unutuldu.");
    code.focus(); // the button is hidden now: the focus goes where pairing starts again
  })();
});

account.addEventListener("change", () => {
  void (async () => showStatus(await ask({ kind: "account", account: Number(account.value) })))();
});

download.addEventListener("click", () => {
  if (guide !== null) {
    void openDownload(guide); // in a new tab; this page waits here for the program
  }
});

/** Where the bridge stands now, and again every few seconds while the program is missing. */
const refresh = follow(show);

// A run in the background changes what the page shows: it follows without being reloaded.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    void refresh();
  }
});

// A page in a tab behind others is asked again rarely by the browser; back in view, it looks at once.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    void refresh();
  }
});

void guideHere().then((found) => {
  guide = found;
  showGuide(guideParts, found);
});
void refresh();
