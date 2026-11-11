import { describe, expect, it } from "vitest";

import { row } from "../../test/server";
import {
  atOffset,
  choosesNone,
  filtered,
  filtersOf,
  isFiltered,
  listQuery,
  orderingOf,
  paramsOfView,
  periodOf,
  sortedBy,
  viewQuery,
  withPeriod,
  withRow,
} from "./query";
import { daysInWords } from "./Filters";
import { partNumber } from "./RowsTable";
import { suggestedPattern } from "./RuleForm";

const at = (query: string) => new URLSearchParams(query);

describe("the Transactions screen's address", () => {
  it("orders by the newest day first unless it says otherwise, a name column from A", () => {
    expect(orderingOf(at(""))).toEqual({ sort: "day", order: "desc" });
    expect(orderingOf(at("sort=title"))).toEqual({ sort: "title", order: "asc" });
    expect(orderingOf(at("sort=amount&order=asc"))).toEqual({ sort: "amount", order: "asc" });
    expect(orderingOf(at("sort=nothing&order=sideways"))).toEqual({ sort: "day", order: "desc" });
  });

  it("sorts by a column, turns the order round on the same column, and goes back to the first page", () => {
    const once = sortedBy(at("offset=50&q=kira"), "amount");
    expect(once.toString()).toBe("q=kira&sort=amount&order=desc");
    expect(sortedBy(once, "amount").get("order")).toBe("asc");
    expect(sortedBy(once, "category").get("order")).toBe("asc");
  });

  it("starts the list again at its first page when a filter changes", () => {
    expect(filtered(at("q=kira&offset=100"), (next) => next.set("q", "aidat")).toString()).toBe("q=aidat");
    expect(atOffset(at("q=kira"), 50).toString()).toBe("q=kira&offset=50");
    expect(atOffset(at("q=kira&offset=50"), 0).toString()).toBe("q=kira");
  });

  it("asks the API with the filters in a steady order, without the open row, blanks or a stray name", () => {
    const params = at("satir=abc&q=+kira+&tag=ev&account=a&account=b&merchant=&order=asc&sort=amount&offset=50&x=1");
    expect(filtersOf(params, false).toString()).toBe("account=a&account=b&tag=ev&q=kira");
    expect(listQuery(params)).toBe("account=a&account=b&tag=ev&q=kira&sort=amount&order=asc&offset=50&limit=50");
  });

  it("knows a filter with nothing chosen, and whether the list is narrowed at all", () => {
    expect(choosesNone(at("account="))).toBe(true);
    expect(choosesNone(at("account=&account=a"))).toBe(false);
    expect(isFiltered(at("sort=amount&satir=abc"))).toBe(false);
    expect(isFiltered(at("merchant=Migros"))).toBe(true);
  });

  it("keeps a view's filters and order, and opens them again", () => {
    const params = at("category=Market&category=Kafe&sort=amount&order=desc&offset=50&satir=abc");
    const query = viewQuery(params);
    expect(query).toEqual({ category: ["Market", "Kafe"], sort: ["amount"], order: ["desc"] });
    expect(paramsOfView(query).toString()).toBe("category=Market&category=Kafe&sort=amount&order=desc");
  });

  it("keeps a named period's name, in place of its days, so a kept view moves with time", () => {
    expect(periodOf(at("period=this_month"))).toBe("this_month");
    expect(periodOf(at("period=yarin"))).toBeNull(); // no period the screen names
    expect(withPeriod(at("from=2026-10-01&to=2026-10-31&q=kira&offset=50"), "last_month").toString()).toBe(
      "q=kira&period=last_month",
    );
    expect(withPeriod(at("period=this_year&q=kira"), "").toString()).toBe("q=kira");
    const params = at("min=1500.5&period=this_month&direction=out&max=2000");
    expect(filtersOf(params, false).toString()).toBe("period=this_month&direction=out&min=1500.5&max=2000");
    expect(viewQuery(params)).toEqual({
      period: ["this_month"],
      direction: ["out"],
      min: ["1500.5"],
      max: ["2000"],
    });
    expect(isFiltered(at("direction=in"))).toBe(true);
  });

  it("says chosen days in words: a whole month by its name", () => {
    expect(daysInWords("2026-02-01", "2026-02-28")).toBe("Şubat 2026");
    expect(daysInWords("2026-02-01", "2026-02-27")).toBe("01.02.2026 – 27.02.2026");
    expect(daysInWords("2026-02-01", "")).toBe("01.02.2026 – …");
  });

  it("opens and closes a row's detail, keeping the filters", () => {
    expect(withRow(at("q=kira"), "abc").toString()).toBe("q=kira&satir=abc");
    expect(withRow(at("q=kira&satir=abc"), null).toString()).toBe("q=kira");
  });
});

describe("a row's parts and rules", () => {
  it("reads a part's number from its fingerprint", () => {
    expect(partNumber("e4e4e4e4e4e4e4e4e4e4-1")).toBe(1);
    expect(partNumber("e4e4e4e4e4e4e4e4e4e4-12")).toBe(12);
  });

  it("suggests the first word of what the bank printed as a rule's pattern, else the merchant's name", () => {
    expect(suggestedPattern(row({ description: "ORNEK MARKET KADIKOY" }))).toBe("ORNEK");
    expect(suggestedPattern(row({ description: "** IYZICO/ORNEKSHOP" }))).toBe("IYZICO/ORNEKSHOP");
    expect(suggestedPattern(row({ description: "*AB* 12", merchant: "Örnek Kafe" }))).toBe("Örnek Kafe");
    expect(suggestedPattern(row({ description: "", merchant: "", title: "Örnek Kişi" }))).toBe("Örnek Kişi");
  });
});
