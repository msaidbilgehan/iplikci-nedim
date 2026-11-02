import { describe, expect, it } from "vitest";

import { liraInput, parseLira } from "./amount";

describe("parseLira", () => {
  it("reads lira as Turkish readers write them into kuruş", () => {
    expect(parseLira("7500")).toBe(750000);
    expect(parseLira("7.500")).toBe(750000);
    expect(parseLira("7.500,5")).toBe(750050);
    expect(parseLira(" 1.234.567,89 TL ")).toBe(123456789);
    expect(parseLira("0,05")).toBe(5);
    expect(parseLira("0")).toBe(0);
  });

  it("refuses what is no lira amount, and a dot that would mean thousands", () => {
    for (const text of ["", "TL", "-5", "7500.50", "7.50", "75.00,1", "1,234", "on bin", "5e3", "7,"]) {
      expect(parseLira(text)).toBeNull();
    }
  });

  it("gives back every amount it writes for the user, to the kuruş", () => {
    // A walk over amounts from kuruş to millions: the property, without a library for it.
    let kurus = 1;
    while (kurus < 10 ** 12) {
      for (const amount of [kurus, kurus + 7, kurus * 3 + 50]) {
        expect(parseLira(liraInput(amount))).toBe(amount);
      }
      kurus = kurus * 7 + 13;
    }
    expect(liraInput(750000)).toBe("7.500");
    expect(liraInput(750050)).toBe("7.500,50");
    expect(liraInput(5)).toBe("0,05");
  });
});
