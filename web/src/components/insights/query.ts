// The Değerlendirme screen's address: the Transactions screen's filters in the API's names (F10, "Süzgeçler"), which
// /api/spending takes as they are, and the period presets the MVP report offered. Without a period the service shows
// the data's last twelve months, so "Son 12 ay" is the address without one. The regular payments come from
// /api/subscriptions, which takes no filter, so the screen narrows them itself. A card's month leads to the rows it
// counts there: the address's filters, the month's days within the period's, and the part a click names.

import type { CategoryRules, Destination, Installment, MonthTable, Series } from "../../api/types";
import { queryOf } from "../../lib/links";
import { monthDays, rowsLink, SAVING_PARTS, SPENDING_KINDS } from "../../lib/rows";
import { isFound, type SearchPart, searchParts } from "../../lib/search";
import { selectionOf } from "../../lib/selection";
import { fold } from "../../lib/turkish";
import type { StackSeries } from "../charts/layout";
import { OTHER_GROUP, slotOf } from "../charts/palette";
import type { MonthValues } from "../charts/StackedBars";
import { filtersOf, type MANY } from "../transactions/query";

// What the spending counts when no kind is chosen (domain.codes.DEFAULT_EXPENSE_KINDS), and the kinds it leaves out
// that the MVP offered to add ("Toplama dahil değil").
export { SPENDING_KINDS };
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

/** The preset the address's period is, if it is one; a period the İşlemler screen names ("Bu ay") is none of them. */
export function presetOf(params: URLSearchParams, first: string, last: string): Preset | null {
  if (params.has("period")) {
    return null;
  }
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
  next.delete("period"); // a preset's days take the place of a named period
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

/** A month's days within the address's period, with the part a click names: one group, one level, one kind. */
function monthOf(query: URLSearchParams, params: URLSearchParams, month: string, part: Record<string, string>) {
  const days = monthDays(month);
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  query.set("from", from > days.from ? from : days.from);
  query.set("to", to && to < days.to ? to : days.to);
  for (const [name, value] of Object.entries(part)) {
    query.set(name, value); // the one part in place of the filter's values
  }
  return rowsLink(queryOf(query));
}

/**
 * A month's spending as the cards count it, on the İşlemler screen: the address's filters with the spending's kinds
 * written out, the month's days within the period's, narrowed to the part given (a group, a level).
 */
export function monthRowsOf(params: URLSearchParams, month: string, part: Record<string, string> = {}): Destination {
  return monthOf(rowsFilters(params), params, month, part);
}

/**
 * A month's rows of one kind as "Gelir ve gider" counts them (income, money to people, debt, savings): the address's
 * filters but its kinds, categories, groups and levels, which the card leaves to the spending.
 */
export function monthKindOf(params: URLSearchParams, month: string, kind: string): Destination {
  const query = filtersOf(params, false);
  for (const name of ["kind", "category", "group", "necessity"]) {
    query.delete(name);
  }
  return monthOf(query, params, month, { kind });
}

/**
 * A month's saving as "Gelir ve gider" counts it: the address's filters but its kinds, categories, groups and levels,
 * with the rows that set money aside or took it out of the savings (BES and investments, currency, gold, deposits).
 */
export function monthSavingOf(params: URLSearchParams, month: string): Destination {
  const query = filtersOf(params, false);
  for (const name of ["kind", "category", "group", "necessity"]) {
    query.delete(name);
  }
  const link = monthOf(query, params, month, {});
  return { ...link, query: { ...link.query, saving: [...SAVING_PARTS] } };
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

// The regular payments follow every filter but the period (features.md, "Süzgeçlerin kapsamı"), matched on the series
// as /api/transactions matches a row (app/transactions.Filter): its account, kind, category, the category's group and
// its necessity among the ones chosen, its payee as the merchant by the folded name, and the search in its names, read
// as the service reads it (one of its comma-separated parts, every word of that part). A series has no tags and no
// certainty, so those two keep every series, and the card says so.

/** The search's parts, as the service reads them. */
function partsOf(params: URLSearchParams): SearchPart[] {
  return searchParts(params.get("q") ?? "");
}

/** Whether the regular payments need the category rules to be matched: a group, or a search that may name one. */
export function needsGroups(params: URLSearchParams): boolean {
  return selectionOf(params, "group") !== null || partsOf(params).length > 0;
}

/** Whether a filter of many values keeps a value: no filter keeps every one, none chosen keeps none. */
function among(params: URLSearchParams, name: (typeof MANY)[number], value: string | null): boolean {
  const chosen = selectionOf(params, name);
  return chosen === null || (value !== null && chosen.has(value));
}

/** A category's group as categorize gives a row its group: the rules' own, else "Diğer". */
function groupOf(rules: CategoryRules | undefined, category: string): string {
  return rules?.categories.find((item) => item.name === category)?.group ?? OTHER_GROUP;
}

/** Whether the address's filters keep a regular payment: every one but the period, the tags and the certainty. */
export function keepsSeries(params: URLSearchParams, series: Series, rules: CategoryRules | undefined): boolean {
  const group = groupOf(rules, series.category);
  const merchant = fold(params.get("merchant") ?? "");
  const names = fold([series.payee, series.category, group, series.account.label].join(" "));
  return (
    among(params, "account", series.account.id) &&
    among(params, "kind", series.kind) &&
    among(params, "category", series.category) &&
    among(params, "group", group) &&
    among(params, "necessity", series.necessity) &&
    (!merchant || fold(series.payee) === merchant) &&
    isFound(partsOf(params), names)
  );
}

/** Whether the address's filters keep a card purchase in installments: the account filter alone. */
export function keepsInstallment(params: URLSearchParams, installment: Installment): boolean {
  return among(params, "account", installment.card.id);
}
