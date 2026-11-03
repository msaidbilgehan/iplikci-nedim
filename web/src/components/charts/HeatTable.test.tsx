import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderScreen } from "../../test/render";
import { AppProviders } from "../AppProviders";
import { HeatTable, heatOf } from "./HeatTable";
import type { StackSeries } from "./layout";

const SERIES: StackSeries[] = [
  { key: "market", label: "Market & Gıda", slot: 1 },
  { key: "kira", label: "Kira", slot: 3 },
  { key: "diger", label: "Diğer", slot: 0 },
];

// September is covered only partly: shown, marked, and in no average.
const MONTHS = [
  { month: "2026-08", values: { market: 400_000, kira: 1_500_000 } },
  { month: "2026-09", values: { market: 100_000, kira: 0 } },
  { month: "2026-10", values: { market: 600_000, kira: 1_500_000 } },
];

function renderTable() {
  return render(
    <AppProviders>
      <HeatTable caption="Aylık giderler" series={SERIES} months={MONTHS} partial={["2026-09"]} />
    </AppProviders>,
  );
}

describe("heatOf", () => {
  it("gives nothing, or what is below zero, no shade", () => {
    expect(heatOf(0, 100)).toBe("");
    expect(heatOf(-50, 100)).toBe("");
    expect(heatOf(50, 0)).toBe("");
  });

  it("shades a value by its share of the highest, in seven steps", () => {
    expect(heatOf(100, 100)).toContain("bg-seq-700");
    expect(heatOf(50, 100)).toContain("bg-seq-400");
    expect(heatOf(1, 100)).toContain("bg-seq-100");
  });

  it("turns the ramp round in the dark theme, the text readable on every step", () => {
    expect(heatOf(100, 100)).toContain("dark:bg-seq-100");
    expect(heatOf(100, 100)).toContain("text-white");
    expect(heatOf(100, 100)).toContain("dark:text-zinc-950");
    expect(heatOf(1, 100)).toContain("text-zinc-950");
    expect(heatOf(1, 100)).toContain("dark:text-white");
  });
});

describe("HeatTable", () => {
  it("writes every month, the newest first, the partial one marked, and only the series with an amount", () => {
    renderTable();
    const table = screen.getByRole("table", { name: "Aylık giderler" });
    expect(within(table).getAllByRole("rowheader").map((header) => header.textContent)).toEqual([
      "Ekim 2026",
      "Eylül 2026 (eksik ay)",
      "Ağustos 2026",
      "Toplam",
      "Aylık ortalama (2 tam ay)",
    ]);
    expect(within(table).queryByRole("columnheader", { name: "Diğer" })).not.toBeInTheDocument();
  });

  it("shades each value by its share of its column's highest month and writes it too", () => {
    renderTable();
    const october = screen.getByRole("row", { name: /^Ekim 2026/ });
    const [market, kira, total] = within(october).getAllByRole("cell");
    expect(market).toHaveTextContent("6.000,00 TL");
    expect(market?.className).toContain("bg-seq-700"); // the market's highest month
    expect(kira?.className).toContain("bg-seq-700");
    expect(total).toHaveTextContent("21.000,00 TL");
    const september = screen.getByRole("row", { name: /^Eylül 2026/ });
    const [, nothing] = within(september).getAllByRole("cell");
    expect(nothing).toHaveTextContent("–");
    expect(nothing?.className).not.toContain("bg-seq");
  });

  it("adds each column up and averages it over the whole months alone", () => {
    renderTable();
    const sum = screen.getByRole("row", { name: /^Toplam/ });
    expect(within(sum).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "11.000,00 TL",
      "30.000,00 TL",
      "41.000,00 TL",
    ]);
    const average = screen.getByRole("row", { name: /^Aylık ortalama/ });
    expect(within(average).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "5.000,00 TL",
      "15.000,00 TL",
      "20.000,00 TL",
    ]);
  });

  it("leads from a month and each of its values to their rows, as the chart's columns do", () => {
    const linkOf = (month: string, series: string | null) =>
      series === "diger" ? null : { screen: "transactions" as const, id: "", query: { from: month, group: series ?? "" } };
    renderScreen(<HeatTable caption="Aylık giderler" series={SERIES} months={MONTHS} linkOf={linkOf} />);
    const october = screen.getByRole("row", { name: /^Ekim 2026/ });
    expect(within(october).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10&group=",
    );
    expect(within(october).getByRole("link", { name: "15.000,00 TL" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-10&group=kira",
    );
    expect(within(october).getAllByRole("link")).toHaveLength(3); // no link for nothing, nor for the total
  });

  it("shows the ramp's ends in words beside it, and what the shade is measured against", () => {
    renderTable();
    expect(screen.getByText("Az")).toBeInTheDocument();
    expect(screen.getByText(/^Çok — renk koyuluğu her sütunun kendi en yüksek ayına göredir/)).toBeInTheDocument();
  });
});
