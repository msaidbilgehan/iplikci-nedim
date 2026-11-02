// The choices of the filters several screens share: the accounts (by bank, with their type), the event kinds (by what
// they concern) and the certainty of rows. Every name comes from /api/accounts and /api/labels.

import type { Accounts, Labels } from "../api/types";
import { labelOf } from "../lib/labels";
import type { FilterOption } from "./ui/FilterPopover";

/** The accounts as filter choices: each under its bank, its type beside it, a closed one marked as closed. */
export function accountOptions(accounts: Accounts | undefined, labels: Labels, closed: string): FilterOption[] {
  if (!accounts) {
    return [];
  }
  const all = [...accounts.groups.flatMap((group) => group.accounts), ...accounts.closed];
  return all.map((item) => ({
    value: item.account.id,
    label: item.label,
    note: [labelOf(labels, "AccountType", item.type), item.closed ? closed : ""].filter(Boolean).join(" · "),
    ...(item.bank ? { group: item.bank } : {}),
  }));
}

/** What an event concerns, as the feed's kind filter groups them; the names are in feed.json under events.kinds. */
export type KindGroup = "documents" | "rows" | "invoices" | "payments" | "months" | "system";

export const KIND_GROUPS: readonly KindGroup[] = ["documents", "rows", "invoices", "payments", "months", "system"];

export function kindGroupOf(kind: string): KindGroup {
  if (kind.startsWith("document.")) {
    return "documents";
  }
  if (kind.startsWith("transaction.") || kind.startsWith("evidence.") || kind === "income.received") {
    return "rows";
  }
  if (kind.startsWith("invoice.")) {
    return "invoices";
  }
  if (["payment.", "expected_payment.", "subscription.", "balance."].some((p) => kind.startsWith(p))) {
    return "payments";
  }
  if (kind === "income.late") {
    return "payments";
  }
  return kind.startsWith("month.") ? "months" : "system";
}

/** The event kinds /api/labels names, as filter choices grouped by what they concern. */
export function kindOptions(labels: Labels, groupName: (group: KindGroup) => string): FilterOption[] {
  const kinds = Object.entries(labels["EventKind"] ?? {});
  return KIND_GROUPS.flatMap((group) =>
    kinds
      .filter(([kind]) => kindGroupOf(kind) === group)
      .map(([kind, label]) => ({ value: kind, label, group: groupName(group) })),
  );
}

/**
 * The kinds a request sends for the chosen ones: a whole family the API knows ("document") stands for all its kinds,
 * so a wide choice stays within the API's limit of 30.
 */
export function sentKinds(chosen: readonly string[], known: readonly string[]): string[] {
  const family = (kind: string) => kind.split(".")[0] ?? kind;
  const families = new Set(known.map(family));
  const sent: string[] = [];
  for (const name of families) {
    const members = known.filter((kind) => family(kind) === name);
    const picked = members.filter((kind) => chosen.includes(kind));
    if (picked.length === members.length) {
      sent.push(name);
    } else {
      sent.push(...picked);
    }
  }
  // A kind the labels do not name (a newer service's) goes as it is.
  sent.push(...chosen.filter((kind) => !known.includes(kind)));
  return sent;
}

/** The certainty of rows, as filter choices, in the order of how far a row counts. */
export function certaintyOptions(labels: Labels): FilterOption[] {
  return ["confirmed", "provisional", "excluded", "info"].map((code) => ({
    value: code,
    label: labelOf(labels, "Certainty", code),
  }));
}
