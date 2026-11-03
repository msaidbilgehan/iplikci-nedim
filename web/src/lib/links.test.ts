import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Destination } from "../api/types";
import { hrefOf, queryOf } from "./links";

// Which screens are built is the test's to say, not the menu's of the day.
const built = vi.hoisted(() => ({ screens: new Set<string>(), details: { document: false, account: false, month: false } }));
vi.mock("../components/navigation", () => ({
  isReady: (key: string) => built.screens.has(key),
  DETAILS: built.details,
}));

function link(screen: Destination["screen"], id = "", query: Record<string, string> = {}): Destination {
  return { screen, id, query };
}

describe("hrefOf", () => {
  beforeEach(() => {
    built.screens = new Set([
      "transactions",
      "calendar",
      "documents",
      "subscriptions",
      "invoices",
      "system",
      "insights",
    ]);
    Object.assign(built.details, { document: true, account: false, month: false });
  });

  it("opens a document in the viewer at its row", () => {
    const sha = "a".repeat(64);
    expect(hrefOf(link("document", sha, { satir: "0123456789abcdef0123" }))).toBe(
      `/belgeler/${sha}?satir=0123456789abcdef0123`,
    );
  });

  it("opens a list screen with the link's query as its filters, in the API's names", () => {
    expect(hrefOf(link("transactions", "", { merchant: "Migros", kind: "purchase" }))).toBe(
      "/islemler?merchant=Migros&kind=purchase",
    );
    expect(hrefOf(link("documents", "", { status: "unreadable" }))).toBe("/belgeler?status=unreadable");
    expect(hrefOf(link("system"))).toBe("/sistem");
    expect(hrefOf(link("insights"))).toBe("/degerlendirme");
  });

  it("opens one item of a list screen by its id", () => {
    expect(hrefOf(link("transaction", "0123456789abcdef0123"))).toBe("/islemler?satir=0123456789abcdef0123");
    expect(hrefOf(link("calendar", "2026-11-25"))).toBe("/takvim?gun=2026-11-25");
    expect(hrefOf(link("calendar"))).toBe("/takvim");
    expect(hrefOf(link("forecast", "teb-123456789"))).toBe("/takvim?hesap=teb-123456789");
    expect(hrefOf(link("subscription", "627a7e2837c95bf260ac"))).toBe("/abonelikler?seri=627a7e2837c95bf260ac");
    expect(hrefOf(link("invoice", `${"b".repeat(64)}:0`))).toBe(`/faturalar?fatura=${"b".repeat(64)}%3A0`);
  });

  it("writes what an id or a filter holds safely into the address", () => {
    expect(hrefOf(link("transactions", "", { q: "kira & aidat" }))).toBe("/islemler?q=kira+%26+aidat");
  });

  it("gives a filter of many values each of them, as the screen's own address does", () => {
    const spending = { from: "2026-06-01", to: "2026-06-30", kind: ["purchase", "refund", "interest_fee"] };
    expect(hrefOf({ screen: "transactions", id: "", query: spending })).toBe(
      "/islemler?from=2026-06-01&to=2026-06-30&kind=purchase&kind=refund&kind=interest_fee",
    );
  });

  it("leads nowhere while the screen is not built", () => {
    expect(hrefOf(link("account", "teb-123456789"))).toBeNull(); // the account's page
    expect(hrefOf(link("month", "2026-10"))).toBeNull();
    expect(hrefOf(link("todo", "missing_documents"))).toBeNull();
    expect(hrefOf(link("fx"))).toBeNull();
    built.details.document = false;
    expect(hrefOf(link("document", "a".repeat(64)))).toBeNull();
  });

  it("leads nowhere for a screen this version does not know", () => {
    expect(hrefOf({ screen: "elsewhere" as Destination["screen"], id: "", query: {} })).toBeNull();
  });
});

describe("queryOf", () => {
  it("keeps one value as a string and a filter's many values as their list", () => {
    const params = new URLSearchParams("from=2026-06-01&kind=purchase&kind=refund");
    expect(queryOf(params)).toEqual({ from: "2026-06-01", kind: ["purchase", "refund"] });
    expect(hrefOf({ screen: "transactions", id: "", query: queryOf(params) })).toBe(`/islemler?${params.toString()}`);
  });
});
