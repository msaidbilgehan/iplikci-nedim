import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../AppProviders";
import type { LineSeries } from "./layout";
import { LineChart } from "./LineChart";

const days = (values: number[]) =>
  values.map((value, i) => ({ day: `2026-11-${String(15 + i).padStart(2, "0")}`, value }));

const CASH: LineSeries = { key: "vadesiz", label: "Örnek Vadesiz", slot: 1, points: days([100_000, 60_000, -40_000, -20_000]) };
const OTHER: LineSeries = { key: "diger", label: "Başka Vadesiz", slot: 2, points: days([300_000, 300_000, 250_000, 250_000]) };

function renderChart(props: Partial<ComponentProps<typeof LineChart>> = {}) {
  return render(
    <AppProviders>
      <LineChart title="Bakiye öngörüsü" summary="15.11.2026 – 18.11.2026, tahmin." series={[CASH, OTHER]} {...props} />
    </AppProviders>,
  );
}

describe("LineChart", () => {
  it("draws the balances as an image named after the chart and described by its window", () => {
    renderChart();
    const image = screen.getByRole("img", { name: "Bakiye öngörüsü: çizgi grafiği. Değerler Tablo görünümünde." });
    expect(image).toHaveAccessibleDescription("15.11.2026 – 18.11.2026, tahmin.");
  });

  it("hatches and names the part below zero when a balance goes under it", () => {
    const { container } = renderChart();
    expect(within(screen.getByRole("img")).getByText("Sıfırın altı: eksi bakiye")).toBeInTheDocument();
    expect(container.querySelector("rect[fill^='url(#']")).not.toBeNull();
    expect(container.querySelector("line.stroke-chart-ink-2")).not.toBeNull(); // zero, darker than the grid
  });

  it("leaves the band out while every balance stays above zero", () => {
    const { container } = renderChart({ series: [OTHER] });
    expect(screen.queryByText("Sıfırın altı: eksi bakiye")).not.toBeInTheDocument();
    expect(container.querySelector("rect[fill^='url(#']")).toBeNull();
  });

  it("parts the lines by their dash as well as their colour", () => {
    const { container } = renderChart();
    const lines = [...container.querySelectorAll("path[fill='none']")];
    expect(lines.map((line) => line.getAttribute("class"))).toEqual(["stroke-slot-1", "stroke-slot-2"]);
    expect(lines.map((line) => line.getAttribute("stroke-dasharray"))).toEqual([null, "6 3"]);
    expect(screen.getByText("Başka Vadesiz")).toBeInTheDocument(); // in the legend
  });

  it("names the days the caller marks", () => {
    renderChart({ markers: [{ day: "2026-11-17", label: "Eksiye düşüyor" }] });
    expect(within(screen.getByRole("img")).getByText("Eksiye düşüyor")).toBeInTheDocument();
  });

  it("shows a day's balances where the pointer rests", () => {
    const { container } = renderChart();
    const surface = container.querySelector("rect[fill='transparent']") as Element;
    fireEvent.pointerMove(surface, { clientX: 640 });
    expect(screen.getByText("18.11.2026")).toBeInTheDocument();
    expect(screen.getByText("−200,00 TL")).toBeInTheDocument();
  });

  it("shows the same balances as a table, a day a row", async () => {
    renderChart();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    const table = screen.getByRole("table", { name: "Bakiye öngörüsü" });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(within(table).getByRole("row", { name: "17.11.2026 −400,00 TL 2.500,00 TL" })).toBeInTheDocument();
  });

  it("writes values that are no money, a rate, as the caller says, on the axis and in the table", async () => {
    const rate = { key: "eur", label: "Euro döviz alış kuru", slot: 2 as const, points: days([36.31, 36.4205]) };
    const format = { tick: (v: number) => v.toFixed(2).replace(".", ","), value: (v: number) => `${v} kur` };
    renderChart({ series: [rate], format });
    expect(screen.queryByText("Sıfırın altı: eksi bakiye")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    const table = screen.getByRole("table", { name: "Bakiye öngörüsü" });
    expect(within(table).getByRole("row", { name: "16.11.2026 36.4205 kur" })).toBeInTheDocument();
  });
});
