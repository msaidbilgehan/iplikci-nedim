/** The extension's window: where it stands, pairing with a code, and which Gmail account to read. */

import type { Status } from "../bridge/messages";
import type { Outcome, ScanSummary } from "../bridge/state";

function element<T extends HTMLElement>(id: string, type: new () => T): T {
  const found = document.getElementById(id);
  if (!(found instanceof type)) {
    throw new Error(`the page has no #${id}`);
  }
  return found;
}

const state = element("state", HTMLParagraphElement);
const last = element("last", HTMLParagraphElement);
const now = element("now", HTMLButtonElement);
const pairForm = element("pair-form", HTMLFormElement);
const code = element("code", HTMLInputElement);
const pairButton = element("pair", HTMLButtonElement);
const pairStatus = element("pair-status", HTMLParagraphElement);
const forget = element("forget", HTMLButtonElement);
const account = element("account", HTMLSelectElement);
const scan = element("scan", HTMLButtonElement);
const scanState = element("scan-state", HTMLParagraphElement);

const CALM: ReadonlySet<Outcome> = new Set(["delivered", "nothing-new"]);
const TIME = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });
const DAY = new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" });

async function ask(request: object): Promise<Status | null> {
  try {
    const answer: unknown = await chrome.runtime.sendMessage(request);
    return isStatus(answer) ? answer : null;
  } catch {
    return null;
  }
}

function show(status: Status | null): void {
  if (status === null) {
    state.textContent =
      "Eklentinin arka planı yanıt vermedi; eklentiyi tarayıcının eklentiler sayfasında yeniden yükleyin.";
    return;
  }
  const busy = scanning(status.scan);
  account.value = String(status.account);
  forget.hidden = !status.paired;
  now.disabled = !status.paired || busy; // a scan delivers the new messages too
  if (!status.paired) {
    state.textContent = "Henüz eşleşmedi: aşağıya İplikçi Nedim'den aldığınız kodu girin.";
  } else if (status.lastRun === null) {
    state.textContent = busy
      ? "Eşleşti; önce geçmiş iletiler taranıyor (aşağıda), sonra yeni iletiler her dakika denetlenir."
      : "Eşleşti; ilk denetim birazdan yapılır.";
  } else {
    state.textContent = `${CALM.has(status.lastRun.outcome) ? "Çalışıyor" : "Dikkat"}: ${status.lastRun.detail}`;
  }
  last.textContent =
    status.lastRun === null ? "" : `Son denetim: ${TIME.format(new Date(status.lastRun.at))} (her dakika denetlenir)`;
  showScan(status, busy);
}

function scanning(summary: ScanSummary | null): boolean {
  return summary !== null && (summary.phase === "searching" || summary.phase === "downloading");
}

function showScan(status: Status, busy: boolean): void {
  const summary = status.scan;
  scan.disabled = !status.paired || busy;
  scan.textContent = busy ? "Taranıyor…" : "Gmail'de eksikleri tara";
  if (!status.paired) {
    scanState.textContent = "Tarama için önce eşleştirin.";
  } else if (busy && summary !== null) {
    scanState.textContent = summary.detail;
  } else if (status.historyDue) {
    scanState.textContent = historyDue(status.startDay, summary);
  } else {
    scanState.textContent = summary === null ? "" : `${TIME.format(new Date(summary.at))} taraması: ${summary.detail}`;
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
    pairStatus.textContent = "Önce kodu girin.";
    return;
  }
  const current = await ask({ kind: "status" });
  if (current?.paired && !window.confirm("Bu tarayıcı zaten eşleşmiş. Yeni kodla yeniden eşleşilsin mi?")) {
    return;
  }
  pairButton.disabled = true;
  pairStatus.textContent = "Eşleştiriliyor…";
  const status = await ask({ kind: "pair", code: typed });
  pairButton.disabled = false;
  if (status === null) {
    pairStatus.textContent = "Eşleştirilemedi; yeniden deneyin.";
    return;
  }
  pairStatus.textContent = status.problem === "" ? paired(status) : status.problem;
  if (status.problem === "") {
    code.value = "";
  }
  show(status);
}

function paired(status: Status): string {
  return status.historyDue
    ? "Eşleşti. Geçmiş iletiler için Gmail yeni bir sekmede aranıyor; sekme arama bitince kendiliğinden kapanır."
    : "Eşleşti. Yeni banka iletileri her dakika taşınır.";
}

now.addEventListener("click", () => {
  void (async () => {
    now.disabled = true;
    state.textContent = "Denetleniyor…";
    show(await ask({ kind: "run" }));
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
    pairStatus.textContent = "Eşleşme unutuldu.";
  })();
});

account.addEventListener("change", () => {
  void (async () => show(await ask({ kind: "account", account: Number(account.value) })))();
});

function isStatus(value: unknown): value is Status {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { paired, account: index, problem } = value as Record<string, unknown>;
  return typeof paired === "boolean" && typeof index === "number" && typeof problem === "string";
}

async function refresh(): Promise<void> {
  show(await ask({ kind: "status" }));
}

// A run in the background changes what the window shows: it follows without being reloaded.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    void refresh();
  }
});

void refresh();
