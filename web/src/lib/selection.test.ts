import { describe, expect, it } from "vitest";

import { selectionOf, sentOf, withSelection } from "./selection";

describe("a filter of many choices in the address", () => {
  it("reads no value as every choice, values as those chosen, and one empty value as none", () => {
    expect(selectionOf(new URLSearchParams(""), "account")).toBeNull();
    expect(selectionOf(new URLSearchParams("account=b&account=a"), "account")).toEqual(new Set(["a", "b"]));
    expect(selectionOf(new URLSearchParams("account="), "account")).toEqual(new Set());
  });

  it("writes the choices in a steady order and keeps the rest of the address", () => {
    const params = new URLSearchParams("q=kira&account=x");
    expect(withSelection(params, "account", new Set(["b", "a"])).toString()).toBe("q=kira&account=a&account=b");
    expect(withSelection(params, "account", null).toString()).toBe("q=kira");
    expect(withSelection(params, "account", new Set()).toString()).toBe("q=kira&account=");
    expect(params.toString()).toBe("q=kira&account=x"); // the address given is left as it was
  });

  it("sends no filter for every choice and an empty list for none", () => {
    expect(sentOf(null)).toBeNull();
    expect(sentOf(new Set(["b", "a"]))).toEqual(["a", "b"]);
    expect(sentOf(new Set())).toEqual([]);
  });
});
