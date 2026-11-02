// The Değerlendirme screen's address: the Transactions screen's filters in the API's names (F10, "Süzgeçler"), which
// /api/spending takes as they are, and the period presets the MVP report offered. Without a period the service shows
// the data's last twelve months, so "Son 12 ay" is the address without one.

import type { MonthTable } from "../../api/types";
import type { StackSeries } from "../charts/layout";
import { slotOf } from "../charts/palette";
import type { MonthValues } from "../charts/StackedBars";
import { filtersOf } from "../transactions/query";

// What the spending counts when no kind is chosen (domain.codes.DEFAULT_EXPENSE_KINDS), and the kinds it leaves out
// that the MVP offered to add ("Toplama dahil değil").
export const SPENDING_KINDS = ["purchase", "refund", "interest_fee"] as const;
export const LEFT_OUT = ["p2p_transfer", "loan_principal", "cash_advance", "card_payment_no_statement"] as const;

export type Preset = "last3" | "last6" | "last12" | "thisYear" | "lastYear" | "all";
export const PRESETS: readonly Preset[] = ["last3", "last6", "last12", "thisYear", "lastYear", "all"];

interface Range {
  from: string; // YYYY-MM-DD
  to: string;
}

/** A month k months on: ("2026-10", -2) → "2026-08". */
export function shiftMonth(month: string, k: number): string {
  const date = new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1 + k, 1));
  return date.toISOString().slice(0, 7);
}

function firstDay(month: string): string {
  return `${month}-01`;
}

function lastDay(month: string): string {
  const next = new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0));
  return next.toISOString().slice(0, 10);
}

const later = (a: string, b: string) => (a > b ? a : b);

/**
 * The days a preset names, from the first and last month of the data in the accounts kept (the period's bounds); null
 * for "Son 12 ay", the service's own period.
 */
export function presetRange(preset: Preset, first: string, last: string): Range | null {
  const year = Number(last.slice(0, 4));
  switch (preset) {
    case "last3":
      return { from: firstDay(later(first, shiftMonth(last, -2))), to: lastDay(last) };
    case "last6":
      return { from: firstDay(later(first, shiftMonth(last, -5))), to: lastDay(last) };
    case "last12":
      return null;
    case "thisYear":
      return { from: firstDay(later(first, `${year}-01`)), to: lastDay(last) };
    case "lastYear":
      return { from: `${year - 1}-01-01`, to: `${year - 1}-12-31` };
    case "all":
      return { from: firstDay(first), to: lastDay(last) };
  }
}

/** The preset the address's period is, if it is one. */
export function presetOf(params: URLSearchParams, first: string, last: string): Preset | null {
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  if (!from && !to) {
    return "last12";
  }
  return (
    PRESETS.find((preset) => {
      const range = presetRange(preset, first, last);
      return range !== null && range.from === from && range.to === to;
    }) ?? null
  );
}

/** The address with a preset's period. */
export function withRange(params: URLSearchParams, range: Range | null): URLSearchParams {
  const next = new URLSearchParams(params);
  if (range) {
    next.set("from", range.from);
    next.set("to", range.to);
  } else {
    next.delete("from");
    next.delete("to");
  }
  return next;
}

/** What /api/spending is asked: the address's filters alone. */
export function spendingQuery(params: URLSearchParams): string {
  return filtersOf(params, false).toString();
}

/**
 * The address's filters with the spending's kinds written out when none is chosen, so that the İşlemler screen and the
 * CSV show the rows the cards count.
 */
export function rowsFilters(params: URLSearchParams): URLSearchParams {
  const query = filtersOf(params, false);
  if (query.getAll("kind").length === 0) {
    for (const kind of SPENDING_KINDS) {
      query.append("kind", kind);
    }
  }
  return query;
}

/** The address with a kind the spending leaves out added to the ones it counts. */
export function withKind(params: URLSearchParams, kind: string): URLSearchParams {
  const next = new URLSearchParams(params);
  const kinds = next.getAll("kind");
  next.delete("kind");
  for (const chosen of new Set([...(kinds.length ? kinds : SPENDING_KINDS), kind])) {
    next.append("kind", chosen);
  }
  return next;
}

/** A month table as the stacked chart draws it: its slices as series, its months' values, its months not whole. */
export function stackOf(
  table: MonthTable,
  label: (key: string) => string,
): { series: StackSeries[]; months: MonthValues[]; partial: string[] } {
  return {
    series: table.slices.map((slice) => ({ key: slice.key, label: label(slice.key), slot: slotOf(slice.slot) })),
    months: table.months.map((row) => ({
      month: row.month,
      values: Object.fromEntries(table.slices.map((slice, index) => [slice.key, row.values[index]?.minor ?? 0])),
    })),
    partial: table.months.filter((row) => row.partial).map((row) => row.month),
  };
}
