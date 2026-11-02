import { describe, expect, it } from "vitest";

import {
  ablative,
  fold,
  fromMonth,
  inMonth,
  lastWord,
  locative,
  monthsIn,
  onDay,
  percent,
  percentOrLess,
  percentPossessive,
  possessive,
  possessiveLocative,
  roundHalfEven,
  yearSuffix,
} from "./turkish";

describe("percentOrLess", () => {
  it("says a share that is not nothing but rounds to 0 % is less than one percent", () => {
    expect(percentOrLess(0.0004)).toBe("%1'den az");
    expect(percentOrLess(0.004)).toBe("%1'den az");
  });

  it("writes nothing as 0 % and any other share as percent() does", () => {
    expect(percentOrLess(0)).toBe("%0");
    expect(percentOrLess(0.006)).toBe("%1");
    expect(percentOrLess(0.92)).toBe("%92");
  });
});

describe("percentPossessive", () => {
  // The cases of tests/test_insights.py::test_percent_takes_the_right_suffix.
  it.each([
    [0.64, "%64'ü"],
    [0.72, "%72'si"],
    [0.29, "%29'u"],
    [0.45, "%45'i"],
    [0.3, "%30'u"],
    [0.6, "%60'ı"],
    [0.06, "%6'sı"],
    [1.0, "%100'ü"],
  ])("writes %s as %s, as the service does", (share, text) => {
    expect(percentPossessive(share)).toBe(text);
  });

  it("rounds an exact half to the even neighbour, as Python's round()", () => {
    expect(percentPossessive(0.125)).toBe("%12'si");
    expect(percentPossessive(0.135)).toBe("%14'ü");
    expect(percent(-0.05)).toBe("−%5");
  });
});

describe("year suffixes", () => {
  // The cases of tests/test_insights.py::test_years_take_the_right_suffix.
  it("writes since a month and in months as the service does", () => {
    expect(`${fromMonth("2026-05")} beri`).toBe("Mayıs 2026'dan beri");
    expect(`${fromMonth("2025-12")} beri`).toBe("Aralık 2025'ten beri");
    expect(monthsIn(["2026-03", "2026-07", "2025-12"])).toBe("Mart ve Temmuz 2026'da, Aralık 2025'te");
  });

  it("follows the year's last spoken word, as insights.year_suffix", () => {
    expect(yearSuffix("2026", true)).toBe("'dan");
    expect(yearSuffix("2026", false)).toBe("'da");
    expect(yearSuffix("2025", true)).toBe("'ten");
    expect(yearSuffix(2025, false)).toBe("'te");
    expect(yearSuffix("2024", false)).toBe("'te");
    expect(yearSuffix("2019", false)).toBe("'da");
    expect(yearSuffix("2020", false)).toBe("'de");
    expect(yearSuffix("2030", false)).toBe("'da");
    expect(yearSuffix("2040", true)).toBe("'tan");
    expect(yearSuffix("2000", false)).toBe("'de");
    expect(yearSuffix("1900", true)).toBe("'den");
    expect(inMonth("2026-03")).toBe("Mart 2026'da");
  });

  it("joins three months of a year as Turkish lists them", () => {
    expect(monthsIn(["2026-01", "2026-02", "2026-04"])).toBe("Ocak, Şubat ve Nisan 2026'da");
    expect(monthsIn(["2023-06"])).toBe("Haziran 2023'te");
  });

  it("puts a day's locative after its year", () => {
    expect(onDay("2026-11-06")).toBe("06.11.2026'da");
    expect(onDay("2025-12-31")).toBe("31.12.2025'te");
    expect(onDay("2030-01-02")).toBe("02.01.2030'da");
  });
});

describe("suffixes after any number", () => {
  // Every last word a number can end with, and what Turkish writes after it.
  it.each([
    [1, "bir", "'de", "'i", "'inde"],
    [2, "iki", "'de", "'si", "'sinde"],
    [3, "üç", "'te", "'ü", "'ünde"],
    [4, "dört", "'te", "'ü", "'ünde"],
    [5, "beş", "'te", "'i", "'inde"],
    [6, "altı", "'da", "'sı", "'sında"],
    [7, "yedi", "'de", "'si", "'sinde"],
    [8, "sekiz", "'de", "'i", "'inde"],
    [9, "dokuz", "'da", "'u", "'unda"],
    [10, "on", "'da", "'u", "'unda"],
    [20, "yirmi", "'de", "'si", "'sinde"],
    [30, "otuz", "'da", "'u", "'unda"],
    [40, "kırk", "'ta", "'ı", "'ında"],
    [50, "elli", "'de", "'si", "'sinde"],
    [60, "altmış", "'ta", "'ı", "'ında"],
    [70, "yetmiş", "'te", "'i", "'inde"],
    [80, "seksen", "'de", "'i", "'inde"],
    [90, "doksan", "'da", "'ı", "'ında"],
    [100, "yüz", "'de", "'ü", "'ünde"],
    [1000, "bin", "'de", "'i", "'inde"],
    [2_000_000, "milyon", "'da", "'u", "'unda"],
    [3_000_000_000, "milyar", "'da", "'ı", "'ında"],
    [0, "sıfır", "'da", "'ı", "'ında"],
  ])("%i ends in %s: %s, %s, %s", (n, word, inIt, its, onIts) => {
    expect(lastWord(n)).toBe(word);
    expect(locative(n)).toBe(inIt);
    expect(ablative(n)).toBe(`${inIt}n`);
    expect(possessive(n)).toBe(its);
    expect(possessiveLocative(n)).toBe(onIts);
  });

  it("listens to the lowest spoken part of a long number", () => {
    expect(lastWord(1_234_567)).toBe("yedi");
    expect(lastWord(1_200_000)).toBe("bin");
    expect(lastWord(15_000_300)).toBe("yüz");
    expect(lastWord(-45)).toBe("beş");
    expect(locative(12.5)).toBe("'de"); // the whole part: 12, iki
  });
});

describe("roundHalfEven", () => {
  it("rounds as Python's round() does", () => {
    expect([12.5, 13.5, -12.5, -13.5, 12.4, 12.6].map(roundHalfEven)).toEqual([12, 14, -12, -14, 12, 13]);
  });
});

describe("fold", () => {
  // The cases of domain/text.py's fold: the user's rules name a merchant as they like, the ledger as the bank prints.
  it.each([
    ["Migros Örnek Şube", "MIGROS ORNEK SUBE"],
    ["ığüşöç İĞÜŞÖÇ", "IGUSOC IGUSOC"],
    ["  Doğalgaz   (İGDAŞ) ", "DOGALGAZ (IGDAS)"],
    ["kâğıt îmân ûfuk", "KAGIT IMAN UFUK"],
    ["Café", "CAFE"],
  ])("folds %j to %j", (text, folded) => {
    expect(fold(text)).toBe(folded);
  });

  it("finds a name however it is written", () => {
    expect(fold("ÖRNEK VİDEO")).toBe(fold("Örnek Video"));
    expect(fold("ornek video")).toBe(fold("Örnek Video"));
  });
});
