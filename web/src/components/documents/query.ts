// The Belgeler screen's address is its state, in the API's own names (F03): the Pano links to it narrowed
// (?status=unreadable), the back button undoes a change, and the API is asked with the same names. The list goes on a
// page at a time by the service's cursor, which the address does not keep. On a document's page, `satir` names the row
// shown where it is printed and `sayfa` the PDF page turned to.

/** The filters with many values: each value a choice of its own (?kind=a&kind=b). */
export const MANY = ["status", "kind", "source", "account", "bank"] as const;
/** The filters with one value. */
export const ONE = ["q"] as const;

export const PAGE_SIZE = 50;
export const ROW = "satir"; // the row the viewer shows
export const PAGE = "sayfa"; // the PDF page the viewer is turned to
/** What was not read: the statuses of the screen's second tab (F03's "İşlenmeyenler ve okunamayanlar"). */
export const UNREAD: readonly string[] = ["unprocessed", "unreadable"];
/** The kind of a document no reader took, as the API names it in the kind filter. */
export const NO_READER = "none";

export type Tab = "all" | "unread";

/** The tab the address shows: the unread one while every status it names is one of theirs. */
export function tabOf(params: URLSearchParams): Tab {
  const statuses = params.getAll("status").filter(Boolean);
  return statuses.length > 0 && statuses.every((status) => UNREAD.includes(status)) ? "unread" : "all";
}

/** The address on a tab: its statuses, every other filter kept. */
export function onTab(params: URLSearchParams, tab: Tab): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete("status");
  if (tab === "unread") {
    for (const status of UNREAD) {
      next.append("status", status);
    }
  }
  return next;
}

/** Whether the tab's statuses are narrowed further, as a link narrows them (?status=unreadable). */
export function narrowsStatus(params: URLSearchParams): boolean {
  const statuses = params.getAll("status");
  return statuses.length > 0 && !(tabOf(params) === "unread" && UNREAD.every((s) => statuses.includes(s)));
}

/** The address's filters alone, in a steady order: the list's request. */
export function filtersOf(params: URLSearchParams): URLSearchParams {
  const query = new URLSearchParams();
  for (const name of MANY) {
    for (const value of params.getAll(name)) {
      query.append(name, value);
    }
  }
  for (const name of ONE) {
    const value = params.get(name)?.trim();
    if (value) {
      query.set(name, value);
    }
  }
  return query;
}

/** Whether a filter of many values has none chosen (?kind=): nothing to ask for. */
export function choosesNone(params: URLSearchParams): boolean {
  return MANY.some((name) => {
    const values = params.getAll(name);
    return values.length > 0 && values.every((value) => value === "");
  });
}

/** Whether the address narrows the list beyond its tab. */
export function isFiltered(params: URLSearchParams): boolean {
  return (
    narrowsStatus(params) ||
    [...MANY.filter((name) => name !== "status"), ...ONE].some((name) =>
      params.getAll(name).some((value) => value.trim() !== ""),
    )
  );
}

/** The API's query for the list: the filters and the page's size; the cursor is the list's own. */
export function listQuery(params: URLSearchParams): string {
  const query = filtersOf(params);
  query.set("limit", String(PAGE_SIZE));
  return query.toString();
}

/** The address with every filter taken off, the tab's statuses kept. */
export function withoutFilters(params: URLSearchParams): URLSearchParams {
  const next = onTab(params, tabOf(params));
  for (const name of [...MANY.filter((name) => name !== "status"), ...ONE]) {
    next.delete(name);
  }
  return next;
}
