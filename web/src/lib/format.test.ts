import { describe, expect, it } from "vitest";

import {
  formatCode,
  formatDay,
  formatFlow,
  formatMoney,
  formatMonth,
  formatPeriod,
  formatSize,
  formatTime,
} from "./format";

describe("format", () => {
  it("writes calendar days as Turkish readers do", () => {
    expect(formatDay("2026-10-31")).toBe("31.10.2026");
    expect(formatDay("")).toBe("");
  });

  it("writes a time to the minute without a comma", () => {
    expect(formatTime("2026-10-31T14:03:00")).toBe("31.10.2026 14:03");
    expect(formatTime("")).toBe("");
  });

  it("writes sizes with a decimal comma in the largest fitting unit", () => {
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(1536)).toBe("1,5 KB");
    expect(formatSize(10 * 1024 * 1024)).toBe("10,0 MB");
  });

  it("writes a period or the side of it that is known", () => {
    expect(formatPeriod("2026-02-01", "2026-02-28")).toBe("01.02.2026 – 28.02.2026");
    expect(formatPeriod("", "2026-02-28")).toBe("28.02.2026");
  });

  it("splits a pairing code as people type it", () => {
    expect(formatCode("ABCDEFGH")).toBe("ABCD-EFGH");
  });

  it("writes amounts from their smallest unit with dots between thousands and a decimal comma", () => {
    expect(formatMoney({ minor: 123456, currency: "TRY" })).toBe("1.234,56 TL");
    expect(formatMoney({ minor: 18438010, currency: "TRY" })).toBe("184.380,10 TL");
    expect(formatMoney({ minor: 5, currency: "TRY" })).toBe("0,05 TL");
    expect(formatMoney({ minor: -1400000, currency: "TRY" })).toBe("−14.000,00 TL");
    expect(formatMoney({ minor: 1999, currency: "USD" })).toBe("19,99 USD");
  });

  it("writes money in with a plus and money out with a minus", () => {
    expect(formatFlow({ minor: 4000000, currency: "TRY" }, "in")).toBe("+40.000,00 TL");
    expect(formatFlow({ minor: 9999, currency: "TRY" }, "out")).toBe("−99,99 TL");
  });

  it("names a month in Turkish", () => {
    expect(formatMonth("2026-04")).toBe("Nisan 2026");
    expect(formatMonth("2026-12")).toBe("Aralık 2026");
  });
});
