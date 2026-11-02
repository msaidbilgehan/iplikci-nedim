// The Transactions screen's address is its state, in the API's own names (F04): other screens link to it narrowed
// (?merchant=…, ?kind=…&certainty=provisional), the back button undoes a change, and a kept view is the address's
// filters. The API is asked with the same names; `satir` names the row whose detail is open.

import type { Sort } from "../../api/schema";

/** The filters with many values: each value a choice of its own (?account=a&account=b). */
export const MANY = ["account", "kind", "category", "group", "necessity", "certainty", "tag"] as const;
/** The filters with one value. */
export const ONE = ["from", "to", "merchant", "q"] as const;
export type FilterName = (typeof MANY)[number] | (typeof ONE)[number];

export const PAGE_SIZE = 50;
export const ROW = "satir"; // the row whose detail is open

const ORDER = ["sort", "order"] as const;
// The order a column sorts in when first chosen: the newest and the largest first, names from A.
const FIRST_ORDER: Record<Sort, "asc" | "desc"> = {
  day: "desc",
  amount: "desc",
  title: "asc",
  category: "asc",
  account: "asc",
};

export interface Ordering {
  sort: Sort;
  order: "asc" | "desc";
}

/** The order the address asks for; the API's own default is the newest day first. */
export function orderingOf(params: URLSearchParams): Ordering {
  const sort = params.get("sort");
  const order = params.get("order");
  const known = sort !== null && sort in FIRST_ORDER;
  return {
    sort: known ? (sort as Sort) : "day",
    order: order === "asc" || order === "desc" ? order : known ? FIRST_ORDER[sort as Sort] : "desc",
  };
}

/** The address sorted by a column: the same column again turns the order round. The first page comes back. */
export function sortedBy(params: URLSearchParams, column: Sort): URLSearchParams {
  const next = new URLSearchParams(params);
  const now = orderingOf(params);
  next.set("sort", column);
  next.set("order", now.sort === column ? (now.order === "asc" ? "desc" : "asc") : FIRST_ORDER[column]);
  next.delete("offset");
  return next;
}

/** Where the page starts: the address's offset, never below zero. */
export function offsetOf(params: URLSearchParams): number {
  const offset = Number(params.get("offset") ?? "0");
  return Number.isInteger(offset) && offset > 0 ? offset : 0;
}

/** The address at another page; the first page has no offset in it. */
export function atOffset(params: URLSearchParams, offset: number): URLSearchParams {
  const next = new URLSearchParams(params);
  if (offset > 0) {
    next.set("offset", String(offset));
  } else {
    next.delete("offset");
  }
  return next;
}

/** The address with a filter changed: the list starts again at its first page. */
export function filtered(params: URLSearchParams, change: (next: URLSearchParams) => void): URLSearchParams {
  const next = new URLSearchParams(params);
  change(next);
  next.delete("offset");
  return next;
}

/** The address with a row's detail open, or closed with null. */
export function withRow(params: URLSearchParams, fingerprint: string | null): URLSearchParams {
  const next = new URLSearchParams(params);
  if (fingerprint) {
    next.set(ROW, fingerprint);
  } else {
    next.delete(ROW);
  }
  return next;
}

/** The address's filters alone, in a steady order: for the CSV, a kept view and the list's request. */
export function filtersOf(params: URLSearchParams, withOrder: boolean): URLSearchParams {
  const query = new URLSearchParams();
  for (const name of MANY) {
    for (const value of params.getAll(name)) {
      query.append(name, value);
    }
  }
  for (const name of [...ONE, ...(withOrder ? ORDER : [])]) {
    const value = params.get(name)?.trim();
    if (value) {
      query.set(name, value);
    }
  }
  return query;
}

/** Whether a filter of many values has none chosen (?account=): nothing to ask for. */
export function choosesNone(params: URLSearchParams): boolean {
  return MANY.some((name) => {
    const values = params.getAll(name);
    return values.length > 0 && values.every((value) => value === "");
  });
}

/** Whether the address narrows the list at all. */
export function isFiltered(params: URLSearchParams): boolean {
  return [...MANY, ...ONE].some((name) => params.getAll(name).some((value) => value.trim() !== ""));
}

/** The API's query for one page of the list: the filters, the order, where the page starts and its size. */
export function listQuery(params: URLSearchParams): string {
  const query = filtersOf(params, true);
  const offset = offsetOf(params);
  if (offset > 0) {
    query.set("offset", String(offset));
  }
  query.set("limit", String(PAGE_SIZE));
  return query.toString();
}

/** A kept view's query, as the API keeps it: each filter with its values. */
export function viewQuery(params: URLSearchParams): Record<string, string[]> {
  const query: Record<string, string[]> = {};
  for (const [name, value] of filtersOf(params, true)) {
    query[name] = [...(query[name] ?? []), value];
  }
  return query;
}

/** The address a kept view opens. */
export function paramsOfView(query: Record<string, string[]>): URLSearchParams {
  const params = new URLSearchParams();
  for (const [name, values] of Object.entries(query)) {
    for (const value of values) {
      params.append(name, value);
    }
  }
  return params;
}
