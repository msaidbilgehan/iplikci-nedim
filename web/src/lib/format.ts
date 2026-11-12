// How the interface writes dates, times, sizes and amounts: 31.10.2026, 31.10.2026 14:03, 1,5 MB, 1.234,56 TL
// (features.md, shared rules). Times are shown in the computer's own time zone.

import type { MoneyOut } from "../api/schema";

const DAY = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
const MONTH = new Intl.DateTimeFormat("tr-TR", { month: "long", year: "numeric" });
const WHOLE = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0, useGrouping: "always" });
const CURRENCIES: Record<string, string> = { TRY: "TL", GR: "gr altın" }; // GR: grams of gold, as the service counts them
const MINUTE = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const ONE_DECIMAL = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

/** "2026-10-31" (a calendar day) → "31.10.2026"; "" stays "". */
export function formatDay(iso: string): string {
  if (!iso) {
    return "";
  }
  const [year, month, day] = iso.slice(0, 10).split("-");
  return year && month && day ? `${day}.${month}.${year}` : iso;
}

/** "2026-11-24" → "24.11": a day of the coming weeks, as the month-end's texts name a statement's cut. */
export function formatDayMonth(iso: string): string {
  const [, month, day] = iso.slice(0, 10).split("-");
  return month && day ? `${day}.${month}` : iso;
}

/** An ISO time → "31.10.2026 14:03" in the local time zone; "" stays "". */
export function formatTime(iso: string): string {
  if (!iso) {
    return "";
  }
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : MINUTE.format(at).replace(",", "");
}

/** An ISO time → its local calendar day, "31.10.2026". */
export function formatDate(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : DAY.format(at);
}

const CLOCK = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit" });
const WEEKDAY = new Intl.DateTimeFormat("tr-TR", { weekday: "long", timeZone: "UTC" });

/** An ISO time → its local hour and minute, "14:03", for a list whose headings name the day. */
export function formatClock(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : CLOCK.format(at);
}

/** An ISO time → the calendar day it falls on in the local time zone, "2026-10-31"; "" for no time. */
export function localDay(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) {
    return "";
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
}

/** A calendar day the given number of days after another: ("2026-10-31", 1) → "2026-11-01". */
export function addDays(day: string, days: number): string {
  const [year, month, date] = day.split("-").map(Number);
  if (!year || !month || !date) {
    return day;
  }
  return new Date(Date.UTC(year, month - 1, date + days)).toISOString().slice(0, 10);
}

/** The days from one calendar day to another: ("2026-11-02", "2026-11-15") → 13. */
export function daysBetween(from: string, to: string): number {
  const start = Date.parse(`${from.slice(0, 10)}T00:00:00Z`);
  const end = Date.parse(`${to.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(start) || Number.isNaN(end) ? 0 : Math.round((end - start) / 86_400_000);
}

/** "2026-10-31" → "Cumartesi, 31.10.2026". */
export function formatWeekday(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  if (!year || !month || !date) {
    return day;
  }
  const name = WEEKDAY.format(new Date(Date.UTC(year, month - 1, date)));
  return `${name.charAt(0).toLocaleUpperCase("tr-TR")}${name.slice(1)}, ${formatDay(day)}`;
}

/** Bytes in the largest unit under 1024 of it: 1536 → "1,5 KB". */
export function formatSize(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${value} B` : `${ONE_DECIMAL.format(value)} ${UNITS[unit]}`;
}

/** A period of two calendar days: "01.02.2026 – 28.02.2026", or the one that is known. */
export function formatPeriod(start: string, end: string): string {
  if (start && end) {
    return `${formatDay(start)} – ${formatDay(end)}`;
  }
  return formatDay(start || end);
}

/** A pairing code as people type it: "ABCD-EFGH". */
export function formatCode(code: string): string {
  return code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
}

/**
 * An amount the service sends in its currency's smallest unit, as Turkish readers write it: {minor: 123456,
 * currency: "TRY"} → "1.234,56 TL", below zero with a minus sign. Whole units and the rest are split in integers, so
 * no amount is rounded on the way.
 */
export function formatMoney(money: MoneyOut): string {
  const units = Math.abs(money.minor);
  const sign = money.minor < 0 ? "−" : "";
  const cents = String(units % 100).padStart(2, "0");
  return `${sign}${WHOLE.format(Math.trunc(units / 100))},${cents} ${CURRENCIES[money.currency] ?? money.currency}`;
}

/** A rate as the service sends it, a decimal number in a string, with its digits kept: "34.5012" → "34,5012". */
export function formatRate(rate: string): string {
  const [whole = "", fraction] = rate.split(".");
  const grouped = /^\d+$/.test(whole) ? WHOLE.format(Number(whole)) : whole;
  return fraction === undefined ? grouped : `${grouped},${fraction}`;
}

/** An amount with the way it goes: "+40.000,00 TL" in, "−15.000,00 TL" out; nothing is "0,00 TL", either way. */
export function formatFlow(money: MoneyOut, direction: "in" | "out"): string {
  if (money.minor === 0) {
    return formatMoney(money);
  }
  return `${direction === "in" ? "+" : "−"}${formatMoney(money)}`;
}

/** "2026-04" → "Nisan 2026". */
export function formatMonth(month: string): string {
  const [year, number] = month.split("-").map(Number);
  return year && number ? MONTH.format(new Date(year, number - 1, 1)) : month;
}

const COMPACT = new Intl.NumberFormat("tr-TR", { notation: "compact", compactDisplay: "long", maximumFractionDigits: 1 });
const MONTH_SHORT = new Intl.DateTimeFormat("tr-TR", { month: "short", year: "2-digit", timeZone: "UTC" });
const DAY_SHORT = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", timeZone: "UTC" });

/** An amount rounded for a chart's axis or label, as Turkish says it: "12 bin TL", "1,3 milyon TL", "−450 TL". */
export function formatMoneyShort(money: MoneyOut): string {
  const text = COMPACT.format(money.minor / 100).replace("-", "−");
  return `${text} ${CURRENCIES[money.currency] ?? money.currency}`;
}

/** "2026-04" → "Nis 26", for a chart's axis. */
export function formatMonthShort(month: string): string {
  const [year, number] = month.split("-").map(Number);
  return year && number ? MONTH_SHORT.format(new Date(Date.UTC(year, number - 1, 1))) : month;
}

/** "2026-11-15" → "15 Kas", for a chart's axis. */
export function formatDayShort(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return year && month && day ? DAY_SHORT.format(new Date(Date.UTC(year, month - 1, day))) : iso;
}
