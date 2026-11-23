// Where a number's rows are on the İşlemler screen (features.md, "İz": every number leads to the rows it rests on): the
// screen narrowed by the API's own filters, so the rows it lists add up to the number. A month is its first and last
// day. Spending is its kinds written out — purchases, refunds, interest and fees (domain.codes.DEFAULT_EXPENSE_KINDS)
// — so the list keeps no card payment, transfer or saving, which the spending leaves out; what went out adds the money
// sent to people and the loan principal repaid. A month's saving is the rows that set money aside or took it out of the
// savings (the API's saving filter): BES and investments, currency and gold bought or sold with TL, and what came into
// or left an account that holds savings; their totals' saving is the month's.

import type { Destination } from "../api/types";
import { addDays } from "./format";
import type { LinkQuery } from "./links";

export const SPENDING_KINDS = ["purchase", "refund", "interest_fee"] as const;

/** "2026-02" → its first and last days, as the Transactions screen's filters take them. */
export function monthDays(month: string): { from: string; to: string } {
  const [year = 0, number = 1] = month.split("-").map(Number);
  const next = number === 12 ? `${year + 1}-01-01` : `${year}-${String(number + 1).padStart(2, "0")}-01`;
  return { from: `${month}-01`, to: addDays(next, -1) };
}

/** The Transactions screen narrowed by the query, in the API's names. */
export function rowsLink(query: LinkQuery): Destination {
  return { screen: "transactions", id: "", query };
}

/** A month's rows, narrowed further by the query given. */
export function monthRows(month: string, query: LinkQuery = {}): Destination {
  return rowsLink({ ...monthDays(month), ...query });
}

/** A month's spending: its purchases, refunds, interest and fees, narrowed further by the query given. */
export function monthSpending(month: string, query: LinkQuery = {}): Destination {
  return monthRows(month, { kind: [...SPENDING_KINDS], ...query });
}

/** What went out and is gone (the dashboard's closing `out`): the spending, money sent to people and loan principal. */
export const OUT_KINDS = [...SPENDING_KINDS, "p2p_transfer", "loan_principal"] as const;

/** A month's money gone out: its spending, what was sent to people and the loan principal repaid. */
export function monthOut(month: string, query: LinkQuery = {}): Destination {
  return monthRows(month, { kind: [...OUT_KINDS], ...query });
}

/** Where money set aside goes, as the API's saving filter names it (domain.codes.SavingPart). */
export const SAVING_PARTS = ["investment", "fx", "gold", "deposit", "brokerage"] as const;

/** What a month set aside, or took out of the savings: the rows of every part of its saving. */
export function monthSaving(month: string, query: LinkQuery = {}): Destination {
  return monthRows(month, { saving: [...SAVING_PARTS], ...query });
}

/** A month's income, narrowed further by the query given. */
export function monthIncome(month: string, query: LinkQuery = {}): Destination {
  return monthRows(month, { kind: "income", ...query });
}
