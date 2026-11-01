/** The verification page: asks the service worker to run the ADR-0016 checks and shows what they found. */

import type { Check, Report } from "./run";

function element<T extends HTMLElement>(id: string, type: new () => T): T {
  const found = document.getElementById(id);
  if (!(found instanceof type)) {
    throw new Error(`the page has no #${id}`);
  }
  return found;
}

const form = element("form", HTMLFormElement);
const account = element("account", HTMLSelectElement);
const start = element("start", HTMLButtonElement);
const status = element("status", HTMLParagraphElement);
const summary = element("summary", HTMLElement);
const results = element("results", HTMLOListElement);
const output = element("output", HTMLTextAreaElement);
const copy = element("copy", HTMLButtonElement);
const copied = element("copied", HTMLSpanElement);

const MARKS = {
  true: { sign: "✓", label: "geçti" },
  false: { sign: "✗", label: "geçmedi" },
  null: { sign: "–", label: "denenemedi" },
} as const;

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void run();
});

copy.addEventListener("click", () => {
  void copyReport();
});

async function run(): Promise<void> {
  start.disabled = true;
  summary.hidden = true;
  status.textContent = "Denetleniyor; yarım dakika kadar sürer…";
  try {
    const report: unknown = await chrome.runtime.sendMessage({ kind: "verify", account: Number(account.value) });
    if (!isReport(report)) {
      throw new Error("no report");
    }
    show(report);
    status.textContent = "Bitti. Sonucu kopyalayıp sohbete yapıştırabilirsiniz.";
  } catch {
    status.textContent = "Doğrulama çalıştırılamadı. Eklentiyi tarayıcının eklentiler sayfasında yeniden yükleyip deneyin.";
  } finally {
    start.disabled = false;
  }
}

function show(report: Report): void {
  results.replaceChildren(...report.checks.map(item));
  output.value = report.text;
  copied.textContent = "";
  summary.hidden = false;
}

function item(check: Check): HTMLLIElement {
  const mark = MARKS[`${check.ok}`];
  const li = document.createElement("li");
  li.className = `check check-${mark.label.replace(/\s/g, "-")}`;
  const sign = document.createElement("span");
  sign.className = "mark";
  sign.textContent = mark.sign;
  sign.setAttribute("aria-hidden", "true");
  const title = document.createElement("strong");
  title.textContent = `${check.title} — ${mark.label}`;
  const lines = document.createElement("ul");
  lines.replaceChildren(
    ...check.lines.map((line) => {
      const entry = document.createElement("li");
      entry.textContent = line;
      return entry;
    }),
  );
  li.replaceChildren(sign, title, lines);
  return li;
}

async function copyReport(): Promise<void> {
  try {
    await navigator.clipboard.writeText(output.value);
    copied.textContent = "Kopyalandı.";
  } catch {
    output.select();
    copied.textContent = "Kopyalanamadı; metin seçildi, klavyeyle kopyalayın.";
  }
}

function isReport(value: unknown): value is Report {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { checks, text } = value as Record<string, unknown>;
  return Array.isArray(checks) && typeof text === "string";
}
