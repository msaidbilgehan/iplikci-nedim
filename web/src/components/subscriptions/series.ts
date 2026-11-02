// What the Subscriptions screen works out from a series beside what the service says of it: whether it still runs,
// the user's `_biten` entry that names its payee, the months a cancellation may name and the payments after one.

import type { TFunction } from "i18next";

import type { CategoryRules, EndedPayment, Payment, Series, SeriesStatus } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { fold } from "../../lib/turkish";
import type { Tone } from "../ui/Badge";

export const SERIES = "seri"; // the address's name for the series whose panel is open

export const STATUS_TONES: Record<SeriesStatus, Tone> = {
  active: "good",
  ended: "neutral",
  cancelled: "neutral",
  paid_after_cancel: "warning",
};

const RUNNING: ReadonlySet<SeriesStatus> = new Set(["active", "paid_after_cancel"]);

/** Whether a series still runs: active, or paid on after the month the user's rules give as its last. */
export function isRunning(series: Series): boolean {
  return RUNNING.has(series.status);
}

/** Whether a running series' next payment was due within the documents and has not shown in them yet. */
export function isLate(series: Series, asOf: string): boolean {
  return isRunning(series) && series.next_day !== null && series.next_day <= asOf;
}

/** The month a day falls in: "2026-10-03" → "2026-10". */
export function monthOf(day: string): string {
  return day.slice(0, 7);
}

/** The month after one: "2026-12" → "2027-01". */
export function nextMonth(month: string): string {
  const year = Number(month.slice(0, 4));
  const number = Number(month.slice(5, 7));
  return number === 12 ? `${year + 1}-01` : `${year}-${String(number + 1).padStart(2, "0")}`;
}

/** The months from first to last, newest first. */
export function monthsDown(first: string, last: string): string[] {
  const months: string[] = [];
  for (let month = first; month <= last; month = nextMonth(month)) {
    months.unshift(month);
  }
  return months;
}

/**
 * The months a cancellation may give as the last payment's, newest first: from the series' first payment to the month
 * after its last one or after the documents' end, whichever is later (a payment may still come after the user
 * cancelled).
 */
export function monthChoices(series: Series, asOf: string): string[] {
  const days = [series.last_day, ...series.payments.map((payment) => payment.day)].sort();
  const latest = [monthOf(series.last_day), monthOf(asOf)].sort().at(-1) ?? monthOf(asOf);
  return monthsDown(monthOf(days[0] ?? series.last_day), nextMonth(latest));
}

/** The payments made after a month: those a cancellation in that month did not expect. */
export function paidAfter(series: Series, month: string): Payment[] {
  return series.payments.filter((payment) => monthOf(payment.day) > month);
}

/** The `_biten` entry that names a payee, the user's own or a shipped one, as the service finds it (by fold). */
export function endedOf(rules: CategoryRules | undefined, payee: string): EndedPayment | undefined {
  const name = fold(payee);
  return rules?.ended.find((entry) => fold(entry.merchant) === name);
}

/** How many series a payee has: a cancellation names the payee, so it applies to every one of them. */
export function seriesOf(all: readonly Series[], payee: string): number {
  const name = fold(payee);
  return all.filter((series) => fold(series.payee) === name).length;
}

/** A price change in words: "Fiyat Temmuz 2026'dan beri 14.000,00 TL yerine 15.000,00 TL"; "" for none. */
export function priceOf(series: Series, t: TFunction<"subscriptions">): string {
  const change = series.price_change;
  if (!change) {
    return "";
  }
  return t("series.price", {
    since: monthOf(change.since),
    before: formatMoney(change.before),
    after: formatMoney(change.after),
  });
}

/** What the user may do with a series: end it, expect it again, both (its month changed), or nothing here. */
export type Offer = "end" | "again" | "both" | "shipped" | "none";

/**
 * What a series offers. Only a `_biten` entry makes a series cancelled (insights.settle), so a running or ended one may
 * be ended before the rules are read; whether a cancelled one is the user's own to take back, the rules say. An entry
 * just written counts before the series' new status arrives.
 */
export function offerOf(series: Series, rules: CategoryRules | undefined): Offer {
  const entry = endedOf(rules, series.payee);
  if (entry) {
    if (!entry.own) {
      return "shipped";
    }
    return series.status === "paid_after_cancel" ? "both" : "again";
  }
  return series.status === "active" || series.status === "ended" ? "end" : "none";
}
