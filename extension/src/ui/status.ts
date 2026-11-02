/**
 * Where the bridge stands, as the extension's window and its settings page show it: an icon, a word and a sentence.
 * The colour never says it alone: every state has a word and an icon of its own (WCAG 1.4.1), as the interface's
 * status marks do.
 */

import type { Status } from "../bridge/messages";
import type { Outcome, ScanSummary } from "../bridge/state";

export type Tone = "good" | "warning" | "critical" | "neutral" | "busy";
export type Icon = "check" | "exclamation" | "cross" | "dash" | "dots" | "turn";

export interface Shown {
  readonly tone: Tone;
  readonly icon: Icon;
  /** The state in a word, beside the icon. */
  readonly word: string;
  readonly detail: string;
  /** When the last check ran; "" before the first. */
  readonly when: string;
}

/** The icons, 24 by 24 and drawn with the stroke, as the interface's (web/src/components/ui/Icons.tsx). */
export const ICON_PATHS: Readonly<Record<Icon, string>> = {
  check: "M20 6 9 17l-5-5",
  exclamation: "M12 5v9M12 19h.01",
  cross: "M6 6l12 12M18 6 6 18",
  dash: "M6 12h12",
  dots: "M6 12h.01M12 12h.01M18 12h.01",
  turn: "M20 12a8 8 0 1 1-2.3-5.7M20 4v4h-4",
};

/** The service worker did not answer: the extension's background stopped. */
export const SILENT =
  "Eklentinin arka planı yanıt vermedi; eklentiyi tarayıcının eklentiler sayfasında yeniden yükleyin.";

/** While a check asked for by hand runs. */
export const CHECKING: Shown = { tone: "busy", icon: "turn", word: "Denetleniyor…", detail: "", when: "" };

const CALM: ReadonlySet<Outcome> = new Set(["delivered", "nothing-new"]);
const TIME = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });

export function scanning(summary: ScanSummary | null): summary is ScanSummary {
  return summary !== null && (summary.phase === "searching" || summary.phase === "downloading");
}

/** What to show for status; `unpaired` says where the pairing code goes, as the page showing it has it. */
export function describe(status: Status | null, unpaired: string): Shown {
  if (status === null) {
    return { tone: "critical", icon: "cross", word: "Yanıt yok", detail: SILENT, when: "" };
  }
  if (!status.paired) {
    return { tone: "neutral", icon: "dash", word: "Eşleşmedi", detail: unpaired, when: "" };
  }
  const run = status.lastRun;
  const when = run === null ? "" : `Son denetim: ${TIME.format(new Date(run.at))} (her dakika denetlenir)`;
  if (scanning(status.scan)) {
    return { tone: "busy", icon: "turn", word: "Taranıyor", detail: status.scan.detail, when };
  }
  if (run === null) {
    return { tone: "neutral", icon: "dots", word: "Bekleniyor", detail: "Eşleşti; ilk denetim birazdan yapılır.", when };
  }
  if (run.outcome === "service-down") {
    return { tone: "critical", icon: "cross", word: "Kapalı", detail: run.detail, when };
  }
  if (CALM.has(run.outcome)) {
    return { tone: "good", icon: "check", word: "Çalışıyor", detail: run.detail, when };
  }
  return { tone: "warning", icon: "exclamation", word: "Dikkat", detail: run.detail, when };
}
