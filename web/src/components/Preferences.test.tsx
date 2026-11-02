import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Theme, View } from "../lib/preferences";
import { stubSystemScheme } from "../test/media";
import { AppProviders } from "./AppProviders";
import { Detailed, Simple, useTheme, useView } from "./Preferences";

const html = document.documentElement;

function Probe() {
  const { theme, dark, setTheme } = useTheme();
  const { view, setView } = useView();
  const themes: Theme[] = ["light", "dark", "system"];
  const views: View[] = ["simple", "detailed"];
  return (
    <div>
      <p>
        {theme} · {dark ? "koyu" : "açık"} · {view}
      </p>
      {themes.map((t) => (
        <button key={t} type="button" onClick={() => setTheme(t)}>
          tema {t}
        </button>
      ))}
      {views.map((v) => (
        <button key={v} type="button" onClick={() => setView(v)}>
          görünüm {v}
        </button>
      ))}
      <Simple>
        <p>Bir cümlelik yorum</p>
      </Simple>
      <Detailed>
        <p>Tablo</p>
      </Detailed>
    </div>
  );
}

function renderProbe() {
  return render(
    <AppProviders>
      <Probe />
    </AppProviders>,
  );
}

describe("display preferences", () => {
  afterEach(() => {
    localStorage.clear();
    html.className = "";
    vi.unstubAllGlobals();
  });

  it("puts the chosen theme on <html> and remembers it", async () => {
    renderProbe();
    expect(html).toHaveClass("light");
    await userEvent.click(screen.getByRole("button", { name: "tema dark" }));
    expect(html).toHaveClass("dark");
    expect(localStorage.getItem("iplikci.theme")).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: "tema light" }));
    expect(html).toHaveClass("light");
    expect(html).not.toHaveClass("dark");
  });

  it("starts from the remembered theme", () => {
    localStorage.setItem("iplikci.theme", "dark");
    renderProbe();
    expect(screen.getByText("dark · koyu · simple")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
  });

  it("follows the computer's setting live while the theme is Sistem", () => {
    const scheme = stubSystemScheme(true);
    renderProbe();
    expect(html).toHaveClass("dark");
    act(() => scheme.set(false));
    expect(html).toHaveClass("light");
    act(() => scheme.set(true));
    expect(screen.getByText("system · koyu · simple")).toBeInTheDocument();
  });

  it("stops following the computer once a theme is chosen", async () => {
    const scheme = stubSystemScheme(false);
    renderProbe();
    await userEvent.click(screen.getByRole("button", { name: "tema light" }));
    act(() => scheme.set(true));
    expect(html).toHaveClass("light");
  });

  it("shows a card's comment in the simple view and its tables in the detailed one, remembering the choice", async () => {
    renderProbe();
    expect(screen.getByText("Bir cümlelik yorum")).toBeInTheDocument();
    expect(screen.queryByText("Tablo")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "görünüm detailed" }));
    expect(screen.getByText("Tablo")).toBeInTheDocument();
    expect(screen.queryByText("Bir cümlelik yorum")).not.toBeInTheDocument();
    expect(localStorage.getItem("iplikci.view")).toBe("detailed");
  });
});
