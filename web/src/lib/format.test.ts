import { describe, expect, it } from "vitest";

import {
  addDays,
  daysBetween,
  formatClock,
  formatCode,
  formatDay,
  formatDayShort,
  formatFlow,
  formatMoney,
  formatMoneyShort,
  formatMonth,
  formatMonthShort,
  formatPeriod,
  formatRate,
  formatSize,
  formatTime,
  formatWeekday,
  localDay,
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

  it("writes a rate with a decimal comma and every digit the service sent", () => {
    expect(formatRate("34.5012")).toBe("34,5012");
    expect(formatRate("3215.40")).toBe("3.215,40");
    expect(formatRate("37")).toBe("37");
  });

  it("writes money in with a plus and money out with a minus", () => {
    expect(formatFlow({ minor: 4000000, currency: "TRY" }, "in")).toBe("+40.000,00 TL");
    expect(formatFlow({ minor: 9999, currency: "TRY" }, "out")).toBe("−99,99 TL");
  });

  it("names a month in Turkish", () => {
    expect(formatMonth("2026-04")).toBe("Nisan 2026");
    expect(formatMonth("2026-12")).toBe("Aralık 2026");
  });

  it("rounds amounts for a chart's axis as Turkish says them", () => {
    expect(formatMoneyShort({ minor: 1200000, currency: "TRY" })).toBe("12 bin TL");
    expect(formatMoneyShort({ minor: 125000000, currency: "TRY" })).toBe("1,3 milyon TL");
    expect(formatMoneyShort({ minor: 45000, currency: "TRY" })).toBe("450 TL");
    expect(formatMoneyShort({ minor: -4500000, currency: "TRY" })).toBe("−45 bin TL");
    expect(formatMoneyShort({ minor: 0, currency: "EUR" })).toBe("0 EUR");
  });

  it("names months and days briefly for a chart's axis", () => {
    expect(formatMonthShort("2026-04")).toBe("Nis 26");
    expect(formatMonthShort("2026-08")).toBe("Ağu 26");
    expect(formatDayShort("2026-11-15")).toBe("15 Kas");
  });

  it("writes a time's hour and minute and finds its day in the local time zone", () => {
    // Local times: whatever the computer's time zone, they stay on their day and hour.
    expect(formatClock("2026-10-31T14:03:00")).toBe("14:03");
    expect(localDay("2026-10-31T23:59:00")).toBe("2026-10-31");
    expect(localDay("2026-11-01T00:00:00")).toBe("2026-11-01");
    expect(localDay("")).toBe("");
  });

  it("counts days across the ends of months and years", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(daysBetween("2026-11-02", "2026-11-15")).toBe(13);
    expect(daysBetween("2026-12-31", "2027-01-01")).toBe(1);
    expect(daysBetween("2026-03-29", "2026-03-30")).toBe(1); // a day a clock moves on is a day all the same
  });

  it("names a day with its weekday", () => {
    expect(formatWeekday("2026-10-31")).toBe("Cumartesi, 31.10.2026");
    expect(formatWeekday("2026-11-02")).toBe("Pazartesi, 02.11.2026");
  });
});
