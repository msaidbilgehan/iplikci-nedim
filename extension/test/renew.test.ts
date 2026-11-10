import { describe, expect, it } from "vitest";

import { newer, shouldRenew, versionKey } from "../src/bridge/renew";
import { INITIAL } from "../src/bridge/state";

const PAIRED = { id: "k1", token: "belirtec-123" };

describe("versions", () => {
  it("compare as numbers, the zeros at their end left out", () => {
    expect(versionKey("0.10.0")).toEqual([0, 10]);
    expect(newer("0.10.0", "0.9.1")).toBe(true);
    expect(newer("0.9.1", "0.10.0")).toBe(false);
    expect(newer("1.0", "1.0.0")).toBe(false);
    expect(newer("1.0.1", "1.0")).toBe(true);
    expect(newer("", "0.8.0")).toBe(false);
    expect(newer("bir", "0.8.0")).toBe(false);
  });
});

describe("shouldRenew", () => {
  const state = { ...INITIAL, paired: PAIRED, carried: "0.9.0" };

  it("loads an unpacked extension again when the program carries a newer one", () => {
    expect(shouldRenew(state, "0.8.0", true)).toBe(true);
  });

  it("leaves an extension from the store to the store", () => {
    expect(shouldRenew(state, "0.8.0", false)).toBe(false);
  });

  it("never loads itself again twice for one version, whose folder may not have changed", () => {
    expect(shouldRenew({ ...state, reloadedFor: "0.9.0" }, "0.8.0", true)).toBe(false);
    expect(shouldRenew({ ...state, reloadedFor: "0.8.5", carried: "0.9.0" }, "0.8.0", true)).toBe(true);
  });

  it("does nothing when it is as new or newer, unpaired, or the service does not say", () => {
    expect(shouldRenew(state, "0.9.0", true)).toBe(false);
    expect(shouldRenew(state, "0.10.0", true)).toBe(false);
    expect(shouldRenew({ ...state, paired: null }, "0.8.0", true)).toBe(false);
    expect(shouldRenew({ ...state, carried: "" }, "0.8.0", true)).toBe(false);
  });
});
