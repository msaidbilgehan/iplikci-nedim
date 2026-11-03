// Where an item of a screen leads in the interface (app/links.py; architecture §18): the service names a screen and
// what to open there, the interface knows the addresses. A list screen opens with the link's query as its filters, in
// the API's names, so the Transactions screen narrowed by `merchant` or `kind` is one address; a filter given many
// values (?kind=purchase&kind=refund) has their list. A screen not built yet has no address to lead to: hrefOf gives
// null, and the item is shown without a link until the screen comes.

import type { Destination } from "../api/types";
import { DETAILS, isReady, type ScreenKey } from "../components/navigation";

type Address = (link: Destination) => string | null;
export type LinkQuery = Destination["query"];

function address(path: string, query: LinkQuery, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries({ ...query, ...extra })) {
    for (const one of typeof value === "string" ? [value] : value) {
      params.append(name, one);
    }
  }
  const written = params.toString();
  return written ? `${path}?${written}` : path;
}

/** An address's query as a link carries it: one value as a string, a filter given many as their list. */
export function queryOf(params: URLSearchParams): LinkQuery {
  const query: LinkQuery = {};
  for (const name of new Set(params.keys())) {
    const values = params.getAll(name);
    query[name] = values.length === 1 ? (values[0] ?? "") : values;
  }
  return query;
}

/** The list screen at path, its filters from the link's query, and what the link's id opens there under name. */
function list(key: ScreenKey, path: string, name?: string): Address {
  return (link) => (isReady(key) ? address(path, link.query, name && link.id ? { [name]: link.id } : {}) : null);
}

/** The page of one thing under path: its id in the address, built when DETAILS says so. */
function page(detail: keyof typeof DETAILS, path: string): Address {
  return (link) => (DETAILS[detail] ? address(`${path}/${encodeURIComponent(link.id)}`, link.query) : null);
}

const ADDRESSES: Record<Destination["screen"], Address> = {
  document: page("document", "/belgeler"), // its query's `satir`: the row the viewer opens at
  documents: list("documents", "/belgeler"),
  transaction: list("transactions", "/islemler", "satir"), // the list with the row's detail open
  transactions: list("transactions", "/islemler"),
  account: page("account", "/hesaplar"),
  accounts: list("accounts", "/hesaplar"),
  month: page("month", "/ay-sonu"),
  invoice: list("invoices", "/faturalar", "fatura"),
  invoices: list("invoices", "/faturalar"),
  subscription: list("subscriptions", "/abonelikler", "seri"),
  calendar: list("calendar", "/takvim", "gun"),
  forecast: list("calendar", "/takvim", "hesap"), // the forecast is on the calendar's screen
  insights: list("insights", "/degerlendirme"),
  fx: list("fx", "/doviz"),
  todo: list("todo", "/yapilacaklar", "tur"),
  system: list("system", "/sistem"),
  notifications: list("notifications", "/bildirimler"),
};

/** The address a link leads to, or null while its screen is not built (or the service names one this version lacks). */
export function hrefOf(link: Destination): string | null {
  const found: Address | undefined = ADDRESSES[link.screen];
  return found ? found(link) : null;
}
