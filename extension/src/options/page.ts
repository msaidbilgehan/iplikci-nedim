/**
 * The extension's settings page: where the bridge stands, "İplikçi Nedim'i aç", pairing with a code, the scan of
 * Gmail and which Gmail account to read. The extension's window (popup.html) leads here for all but the first two.
 */

import type { Status } from "../bridge/messages";
import type { ScanSummary } from "../bridge/state";
import { ask, draw, element, openInterface, say, statusCard, version } from "../ui/dom";
import { CHECKING, describe, scanning } from "../ui/status";

const card = statusCard();
const now = element("now", HTMLButtonElement);
const open = element("open", HTMLButtonElement);
const openAnswer = element("open-answer", HTMLParagraphElement);
const pairSummary = element("pair-summary", HTMLParagraphElement);
const pairForm = element("pair-form", HTMLFormElement);
const code = element("code", HTMLInputElement);
const pairButton = element("pair", HTMLButtonElement);
const pairStatus = element("pair-status", HTMLParagraphElement);
const forget = element("forget", HTMLButtonElement);
const account = element("account", HTMLSelectElement);
const scan = element("scan", HTMLButtonElement);
const scanState = element("scan-state", HTMLParagraphElement);
element("version", HTMLSpanElement).textContent = version();

const UNPAIRED = "İplikçi Nedim'den aldığınız kodu aşağıdaki Eşleştirme bölümüne girin.";
const TIME = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });
const DAY = new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" });

function show(status: Status | null): void {
  draw(card, describe(status, UNPAIRED));
  if (status === null) {
    return;
  }
  const busy = scanning(status.scan);
  account.value = String(status.account);
  forget.hidden = !status.paired;
  now.disabled = !status.paired || busy; // a scan delivers the new messages too
  say(
    pairSummary,
    status.paired
      ? "Bu tarayıcı İplikçi Nedim ile eşleşti. Yeni bir kodla yeniden eşleşebilir ya da eşleşmeyi unutabilirsiniz."
      : "Eklenti İplikçi Nedim ile tek kullanımlık bir kodla eşleşir; sonra yeni banka iletileri her dakika, " +
          "Gmail'de görünenler de hemen taşınır.",
  );
  say(pairButton, status.paired ? "Yeniden eşleştir" : "Eşleştir");
  showScan(status, busy);
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
  show(status);
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
    show(await ask({ kind: "run" }));
    if (focused && !now.disabled) {
      now.focus();
    }
  })();
});

scan.addEventListener("click", () => {
  void (async () => {
    scan.disabled = true;
    show(await ask({ kind: "scan" }));
  })();
});

forget.addEventListener("click", () => {
  void (async () => {
    if (!window.confirm("Bu tarayıcıdaki eşleşme unutulsun mu? İplikçi Nedim'in sayfasından da iptal edebilirsiniz.")) {
      return;
    }
    show(await ask({ kind: "forget" }));
    say(pairStatus, "Eşleşme unutuldu.");
    code.focus(); // the button is hidden now: the focus goes where pairing starts again
  })();
});

account.addEventListener("change", () => {
  void (async () => show(await ask({ kind: "account", account: Number(account.value) })))();
});

async function refresh(): Promise<void> {
  show(await ask({ kind: "status" }));
}

// A run in the background changes what the page shows: it follows without being reloaded.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    void refresh();
  }
});

void refresh();
