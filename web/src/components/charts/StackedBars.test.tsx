import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../AppProviders";
import type { StackSeries } from "./layout";
import { StackedBars } from "./StackedBars";

const SERIES: StackSeries[] = [
  { key: "market", label: "Market & Gıda", slot: 1 },
  { key: "ulasim", label: "Ulaşım", slot: 2 },
  { key: "diger", label: "Diğer", slot: 0 },
];

const MONTHS = [
  { month: "2026-08", values: { market: 400_000, ulasim: 100_000 } },
  { month: "2026-09", values: { market: 350_000, ulasim: -50_000, diger: 20_000 } },
  { month: "2026-10", values: { market: 500_000, ulasim: 150_000 } },
];

function renderChart(props: Partial<ComponentProps<typeof StackedBars>> = {}) {
  return render(
    <AppProviders>
      <StackedBars
        title="Aylık giderler"
        summary="Ağustos – Ekim 2026, ana gruplara göre."
        series={SERIES}
        months={MONTHS}
        {...props}
      />
    </AppProviders>,
  );
}

describe("StackedBars", () => {
  it("draws the months as an image named after the chart and described by its window", () => {
    renderChart();
    const image = screen.getByRole("img", {
      name: "Aylık giderler: yığılmış sütun grafiği. Değerler Tablo görünümünde.",
    });
    expect(image).toHaveAccessibleDescription("Ağustos – Ekim 2026, ana gruplara göre.");
    expect(screen.getByRole("figure", { name: "Aylık giderler" })).toBeInTheDocument();
  });

  it("paints each series in its fixed slot and Diğer grey", () => {
    const { container } = renderChart();
    expect(container.querySelectorAll("path.fill-slot-1")).toHaveLength(3);
    expect(container.querySelectorAll("path.fill-slot-2")).toHaveLength(3);
    expect(container.querySelectorAll("path.fill-slot-0")).toHaveLength(1);
    expect(screen.getByText("Diğer")).toBeInTheDocument(); // in the legend
  });

  it("writes the axis and the highest month's total in round amounts", () => {
    renderChart();
    const image = screen.getByRole("img");
    expect(within(image).getByText("0 TL")).toBeInTheDocument();
    expect(within(image).getByText("6,5 bin TL")).toBeInTheDocument(); // October, the highest and the last
    expect(within(image).getByText("Eki 26")).toBeInTheDocument();
  });

  it("shows the same data as a table, the newest month first, signs written", async () => {
    renderChart();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    const table = screen.getByRole("table", { name: "Aylık giderler" });
    const rows = within(table).getAllByRole("row");
    expect(rows.map((row) => within(row).queryAllByRole("cell")[0]?.textContent)).toEqual([
      undefined,
      "Ekim 2026",
      "Eylül 2026",
      "Ağustos 2026",
    ]);
    const september = rows[2];
    expect(september).toHaveTextContent("−500,00 TL");
    expect(september).toHaveTextContent("3.200,00 TL"); // its total
    expect(within(rows[1] as HTMLElement).getAllByRole("cell")[3]).toHaveTextContent("–"); // October has no Diğer
  });

  it("marks the forecast months: lighter, after a dashed line, and named so in the table", async () => {
    const { container } = renderChart({ forecastFrom: "2026-10" });
    expect(within(screen.getByRole("img")).getByText("tahmin")).toBeInTheDocument();
    expect(screen.getByText("Soluk sütunlar: tahmin")).toBeInTheDocument();
    expect(container.querySelectorAll("path[fill-opacity='0.42']")).toHaveLength(2);
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    expect(screen.getByRole("cell", { name: "Ekim 2026 (tahmin)" })).toBeInTheDocument();
  });

  it("draws the reference line the caller gives, and no average of its own", () => {
    renderChart({ reference: { label: "Tipik ay", value: 480_000 } });
    expect(within(screen.getByRole("img")).getByText("Tipik ay: 4,8 bin TL")).toBeInTheDocument();
  });

  it("shows a month's values where the pointer rests", () => {
    const { container } = renderChart();
    const bands = container.querySelectorAll("rect[fill='transparent']");
    fireEvent.pointerEnter(bands[1] as Element);
    expect(screen.getByText("Eylül 2026")).toBeInTheDocument();
    expect(screen.getByText("3.500,00 TL")).toBeInTheDocument();
    fireEvent.pointerLeave(container.querySelector("svg")?.parentElement as Element);
    expect(screen.queryByText("Eylül 2026")).not.toBeInTheDocument();
  });

  it("says when there is nothing to draw, without a switch", () => {
    renderChart({ months: [{ month: "2026-10", values: {} }] });
    expect(screen.getByText("Gösterilecek veri yok.")).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
