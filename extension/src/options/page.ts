/** The extension's window: where it stands, pairing with a code, and which Gmail account to read. */

import type { Status } from "../bridge/messages";
import type { Outcome } from "../bridge/state";

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

const CALM: ReadonlySet<Outcome> = new Set(["delivered", "nothing-new"]);
const TIME = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });

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
    state.textContent = "Eklentinin arka planı yanıt vermedi; eklentiyi tarayıcının eklentiler sayfasında yeniden yükleyin.";
    return;
  }
  account.value = String(status.account);
  forget.hidden = !status.paired;
  now.disabled = !status.paired;
  if (!status.paired) {
    state.textContent = "Henüz eşleşmedi: aşağıya İplikçi Nedim'den aldığınız kodu girin.";
  } else if (status.lastRun === null) {
    state.textContent = "Eşleşti; ilk denetim birazdan yapılır.";
  } else {
    state.textContent = `${CALM.has(status.lastRun.outcome) ? "Çalışıyor" : "Dikkat"}: ${status.lastRun.detail}`;
  }
  last.textContent =
    status.lastRun === null ? "" : `Son denetim: ${TIME.format(new Date(status.lastRun.at))} (her dakika denetlenir)`;
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
  pairStatus.textContent = status.problem === "" ? "Eşleşti. Yeni banka iletileri her dakika taşınır." : status.problem;
  if (status.problem === "") {
    code.value = "";
  }
  show(status);
}

now.addEventListener("click", () => {
  void (async () => {
    now.disabled = true;
    state.textContent = "Denetleniyor…";
    show(await ask({ kind: "run" }));
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
