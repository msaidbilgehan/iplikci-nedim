import { describe, expect, it } from "vitest";

import { formatCode, formatDay, formatPeriod, formatSize, formatTime } from "./format";

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
});
