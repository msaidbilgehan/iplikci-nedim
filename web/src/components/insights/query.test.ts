import { describe, expect, it } from "vitest";

import type { CategoryRules } from "../../api/types";
import { CATEGORY_RULES, category, series, SUBSCRIPTIONS } from "../../test/server";
import { keepsInstallment, keepsSeries, needsGroups } from "./query";

const CASH = { id: "teb-123456789", label: "Örnek Vadesiz TL" };
const CARD = { id: "teb-1234", label: "Örnek Kart •1234" };
const RENT = series({ account: CASH }); // "Ev kirası": Kira, a required purchase
const MUSIC = series({
  id: "fp-muzik",
  payee: "Örnek Müzik",
  category: "Dijital Abonelikler",
  necessity: "optional",
  account: CARD,
});
// Money put by every month: no necessity, and a category the rules do not name.
const FUND = series({ id: "fp-fon", payee: "Örnek Fon", category: "Yatırım", necessity: null, kind: "investment" });
const RULES: CategoryRules = {
  ...CATEGORY_RULES,
  categories: [
    ...CATEGORY_RULES.categories,
    category("Kira", "Ev", 4, { necessity: "required", regular: true }),
    category("Dijital Abonelikler", "Eğlence", 6),
  ],
};

/** The payees an address keeps of the rent, the music and the fund. */
function kept(query: string): string[] {
  const params = new URLSearchParams(query);
  return [RENT, MUSIC, FUND].filter((found) => keepsSeries(params, found, RULES)).map((found) => found.payee);
}

describe("keepsSeries", () => {
  it("keeps every series without a filter, and whatever the period", () => {
    expect(kept("")).toEqual(["Ev kirası", "Örnek Müzik", "Örnek Fon"]);
    expect(kept("from=2027-01-01&to=2027-01-31")).toEqual(["Ev kirası", "Örnek Müzik", "Örnek Fon"]);
  });

  it("keeps the series last paid from an account chosen, and none when no account is chosen", () => {
    expect(kept("account=teb-1234")).toEqual(["Örnek Müzik"]);
    expect(kept("account=teb-1234&account=teb-123456789")).toEqual(["Ev kirası", "Örnek Müzik", "Örnek Fon"]);
    expect(kept("account=")).toEqual([]);
  });

  it("keeps the series of a kind chosen", () => {
    expect(kept("kind=investment")).toEqual(["Örnek Fon"]);
    expect(kept("kind=purchase&kind=refund")).toEqual(["Ev kirası", "Örnek Müzik"]);
  });

  it("keeps the series of a category chosen", () => {
    expect(kept("category=Kira")).toEqual(["Ev kirası"]);
    expect(kept("category=Market")).toEqual([]);
  });

  it("keeps the series whose category the rules put in a group chosen, a category they do not name in Diğer", () => {
    expect(kept("group=Ev")).toEqual(["Ev kirası"]);
    expect(kept("group=Eğlence&group=Ev")).toEqual(["Ev kirası", "Örnek Müzik"]);
    expect(kept("group=Diğer")).toEqual(["Örnek Fon"]);
  });

  it("keeps the series of a necessity chosen, never one without a necessity when a level is chosen", () => {
    expect(kept("necessity=optional")).toEqual(["Örnek Müzik"]);
    const every = "necessity=required&necessity=optional&necessity=unnecessary&necessity=unknown";
    expect(kept(every)).toEqual(["Ev kirası", "Örnek Müzik"]);
  });

  it("keeps the series paid to the merchant by its folded name, as the rows are kept, not by a part of it", () => {
    expect(kept("merchant=ORNEK MUZIK")).toEqual(["Örnek Müzik"]);
    expect(kept("merchant=%20örnek%20%20müzik%20")).toEqual(["Örnek Müzik"]);
    expect(kept("merchant=Örnek")).toEqual([]);
  });

  it("keeps the series with every word of the search in its payee, category, group or account", () => {
    expect(kept("q=kira")).toEqual(["Ev kirası"]);
    expect(kept("q=MÜZİK kart")).toEqual(["Örnek Müzik"]); // the payee and the account
    expect(kept("q=eglence")).toEqual(["Örnek Müzik"]); // the group
    expect(kept("q=yatırım")).toEqual(["Örnek Fon"]); // the category
    expect(kept("q=müzik vadesiz")).toEqual([]); // each word in another series
    expect(kept("q=%20%20")).toEqual(["Ev kirası", "Örnek Müzik", "Örnek Fon"]);
  });

  it("keeps every series whatever the tags and the certainty, which a series does not have", () => {
    expect(kept("tag=ev&certainty=provisional")).toEqual(["Ev kirası", "Örnek Müzik", "Örnek Fon"]);
  });

  it("keeps only the series every filter keeps", () => {
    expect(kept("account=teb-1234&necessity=optional&q=müzik")).toEqual(["Örnek Müzik"]);
    expect(kept("account=teb-1234&category=Kira")).toEqual([]);
  });
});

describe("keepsInstallment", () => {
  const [installment] = SUBSCRIPTIONS.installments; // on the card, teb-1234

  it("follows the account filter alone", () => {
    const keeps = (query: string) => keepsInstallment(new URLSearchParams(query), installment!);
    expect(keeps("")).toBe(true);
    expect(keeps("account=teb-1234&category=Kira&necessity=required&merchant=Örnek Market&q=yok")).toBe(true);
    expect(keeps("account=teb-123456789")).toBe(false);
    expect(keeps("account=")).toBe(false);
  });
});

describe("needsGroups", () => {
  it("asks for the category rules only for a group or a search", () => {
    expect(needsGroups(new URLSearchParams("group=Ev"))).toBe(true);
    expect(needsGroups(new URLSearchParams("q=kira"))).toBe(true);
    expect(needsGroups(new URLSearchParams("q=%20&account=teb-1234&category=Kira&merchant=Ev kirası"))).toBe(false);
  });
});
