import { afterEach, describe, expect, it, vi } from "vitest";

import { stubSystemScheme } from "../test/media";
import {
  applyTheme,
  isDark,
  readTheme,
  readView,
  saveTheme,
  saveView,
  systemIsDark,
} from "./preferences";

const html = document.documentElement;

describe("preferences", () => {
  afterEach(() => {
    localStorage.clear();
    html.className = "";
    vi.unstubAllGlobals();
  });

  it("starts with the system's theme and the simple view", () => {
    expect(readTheme()).toBe("system");
    expect(readView()).toBe("simple");
  });

  it("remembers the choices in the browser", () => {
    saveTheme("dark");
    saveView("detailed");
    expect(readTheme()).toBe("dark");
    expect(readView()).toBe("detailed");
    expect(localStorage.getItem("iplikci.theme")).toBe("dark");
    expect(localStorage.getItem("iplikci.view")).toBe("detailed");
  });

  it("ignores a stored value it does not know", () => {
    localStorage.setItem("iplikci.theme", "mor");
    localStorage.setItem("iplikci.view", "<b>");
    expect(readTheme()).toBe("system");
    expect(readView()).toBe("simple");
  });

  it("keeps working when the browser refuses its storage", () => {
    const refused = () => {
      throw new DOMException("storage is off", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(refused);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(refused);
    expect(readTheme()).toBe("system");
    expect(() => saveTheme("dark")).not.toThrow();
  });

  it("resolves the system's theme from the computer's setting", () => {
    expect(isDark("system", true)).toBe(true);
    expect(isDark("system", false)).toBe(false);
    expect(isDark("light", true)).toBe(false);
    expect(isDark("dark", false)).toBe(true);
  });

  it("reads the computer's setting where the browser can tell it, and light where it cannot", () => {
    expect(systemIsDark()).toBe(false);
    stubSystemScheme(true);
    expect(systemIsDark()).toBe(true);
  });

  it("puts the resolved theme on <html> as a class", () => {
    applyTheme(true);
    expect(html).toHaveClass("dark");
    expect(html).not.toHaveClass("light");
    applyTheme(false);
    expect(html).toHaveClass("light");
    expect(html).not.toHaveClass("dark");
  });
});
