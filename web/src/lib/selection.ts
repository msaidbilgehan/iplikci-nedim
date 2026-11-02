// A filter of many choices kept in the screen's address in the API's own names (?account=a&account=b): a link from
// another screen opens the list filtered, and the browser's back button undoes a change. No value means every choice,
// no filter. One empty value means none chosen; no request can say that, so the screen shows nothing without asking.

import type { Selection } from "../components/ui/FilterPopover";

const NONE = "";

/** The choices an address names for a filter: null for every choice, an empty set for none. */
export function selectionOf(params: URLSearchParams, name: string): Selection {
  const values = params.getAll(name);
  return values.length === 0 ? null : new Set(values.filter((value) => value !== NONE));
}

/** The address with a filter's choices, in a steady order; every other part of it stays. */
export function withSelection(params: URLSearchParams, name: string, selected: Selection): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete(name);
  if (selected === null) {
    return next;
  }
  if (selected.size === 0) {
    next.append(name, NONE);
    return next;
  }
  for (const value of [...selected].sort()) {
    next.append(name, value);
  }
  return next;
}

/** What a request sends for a filter: null for no filter, [] for none chosen. */
export function sentOf(selected: Selection): string[] | null {
  return selected === null ? null : [...selected].sort();
}
