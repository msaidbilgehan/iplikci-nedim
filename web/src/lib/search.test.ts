import { describe, expect, it } from "vitest";

import { isFound, searchInWords, searchParts } from "./search";
import { fold } from "./turkish";

const texts = (search: string) => searchParts(search).map((part) => part.text);
const finds = (search: string, text: string) => isFound(searchParts(search), fold(text));

// The same cases as the service's tests/test_search.py: the screen reads a search as the service does.
describe("searchParts", () => {
  it("finds the rows of either part a comma separates", () => {
    expect(texts("Ayşe, Mehmet")).toEqual(["Ayşe", "Mehmet"]);
    expect(finds("Ayşe, Mehmet", "FAST AYSE ORNEK")).toBe(true);
    expect(finds("Ayşe, Mehmet", "EFT MEHMET ORNEK")).toBe(true);
    expect(finds("Ayşe, Mehmet", "MIGROS")).toBe(false);
  });

  it("needs every word of a part, as the box always did", () => {
    expect(finds("migros kadıköy", "MIGROS KADIKOY SUBE")).toBe(true);
    expect(finds("migros kadıköy", "MIGROS ATASEHIR")).toBe(false);
    expect(finds("migros kadıköy, a101", "A101 MAGAZA")).toBe(true);
  });

  it("needs no space after a comma, and an empty part adds nothing", () => {
    expect(texts("market,kira")).toEqual(["market", "kira"]);
    expect(texts(" , ,market,, ")).toEqual(["market"]);
    expect(searchParts(" , ")).toEqual([]);
    expect(finds("", "ANY ROW")).toBe(true);
  });

  it("reads a comma between two digits as a decimal comma", () => {
    expect(searchParts("1,50").map((part) => part.terms)).toEqual([["1,50"]]);
    expect(texts("1, 50")).toEqual(["1", "50"]);
    expect(texts("kira,5")).toEqual(["kira", "5"]);
  });

  it("keeps a quoted term as written, a curly or an unclosed quote too", () => {
    expect(searchParts('"ornek gida, kadikoy"')).toEqual([
      { text: '"ornek gida, kadikoy"', terms: ["ORNEK GIDA, KADIKOY"] },
    ]);
    expect(finds('"ornek gida, kadikoy"', "KADIKOY ORNEK GIDA")).toBe(false);
    expect(texts('"a, b" c, d')).toEqual(['"a, b" c', "d"]);
    for (const quoted of ["“ornek, kadikoy”", "„ornek, kadikoy”", '"ornek, kadikoy']) {
      expect(searchParts(quoted).map((part) => part.terms)).toEqual([["ORNEK, KADIKOY"]]);
    }
  });

  it("compares the terms folded and keeps a part written twice once", () => {
    expect(finds("KİRA", "kira ödemesi")).toBe(true);
    expect(texts("Ayşe, ayse, AYŞE")).toEqual(["Ayşe"]);
  });
});

describe("searchInWords", () => {
  it("names the parts as alternatives", () => {
    expect(searchInWords("ayşe")).toBe("ayşe");
    expect(searchInWords(" market ,kira ")).toBe("market veya kira");
    expect(searchInWords('market, kira, "a, b"')).toBe('market, kira veya "a, b"');
    expect(searchInWords(" , ")).toBe("");
  });
});
