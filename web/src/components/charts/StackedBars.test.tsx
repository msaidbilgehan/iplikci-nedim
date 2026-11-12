import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import type { Destination } from "../../api/types";
import { renderScreen } from "../../test/render";
import type { StackSeries } from "./layout";
import { type MonthPart, StackedBars } from "./StackedBars";

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
  return renderScreen(
    <StackedBars
      title="Aylık giderler"
      summary="Ağustos – Ekim 2026, ana gruplara göre."
      series={SERIES}
      months={MONTHS}
      {...props}
    />,
    { path: "/degerlendirme" },
  );
}

/** A month's rows on the İşlemler screen, or one group's of it. */
function rows({ month, series }: MonthPart): Destination {
  return { screen: "transactions", id: "", query: { from: `${month}-01`, ...(series ? { group: series } : {}) } };
}

const OPEN = { link: rows, hint: "Bir aya ya da bir gruba tıklayın: o harcamalar listelenir." };

/** The y a segment's path spans, read from its drawing ("M x,top H … V bottom …" for a segment under another). */
function middleOf(path: Element): number {
  const d = path.getAttribute("d") ?? "";
  const [top = 0, bottom = 0] = [/^M[\d.]+,([\d.]+)/, /V([\d.]+)/].map((r) => Number(r.exec(d)?.[1]));
  return (top + bottom) / 2;
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

  it("marks a month the documents cover only partly: lighter, its word above it, named so in the table", async () => {
    const { container } = renderChart({ partial: ["2026-09"] });
    expect(within(screen.getByRole("img")).getByText("eksik")).toBeInTheDocument();
    expect(screen.getByText("Soluk sütunlar: eksik aylar, ortalamaya girmez")).toBeInTheDocument();
    expect(container.querySelectorAll("path[fill-opacity='0.55']")).toHaveLength(3);
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    expect(screen.getByRole("cell", { name: "Eylül 2026 (eksik ay)" })).toBeInTheDocument();
  });

  it("marks a month in the caller's words, its word over the day it should close, and says it has not closed", async () => {
    renderChart({
      partial: ["2026-09", "2026-10"],
      marks: { "2026-09": { word: "bekliyor", day: "~24.11" }, "2026-10": { word: "sürüyor" } },
    });
    const image = within(screen.getByRole("img"));
    expect(image.getByText("bekliyor")).toBeInTheDocument();
    expect(image.getByText("~24.11")).toBeInTheDocument();
    expect(image.getByText("sürüyor")).toBeInTheDocument();
    expect(image.queryByText("eksik")).not.toBeInTheDocument();
    expect(screen.getByText("Soluk sütunlar: henüz kapanmamış aylar, ortalamaya girmez")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    expect(screen.getByRole("cell", { name: "Eylül 2026 (bekliyor, ~24.11)" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Ekim 2026 (sürüyor)" })).toBeInTheDocument();
  });

  it("opens the whole month with a click on its name under the axis, never one of its series", () => {
    const { container, location } = renderChart({ open: OPEN });
    const band = container.querySelectorAll("rect[fill='transparent']")[2] as Element;
    fireEvent.pointerDown(band, { clientY: 272 }); // "Eki 26", under the plot's 252
    fireEvent.click(band);
    expect(location()).toBe("/islemler?from=2026-10-01");
    const only = { link: ({ month, series }: MonthPart) => (series ? rows({ month, series }) : null), hint: OPEN.hint };
    const again = renderChart({ open: only });
    const named = again.container.querySelectorAll("rect[fill='transparent']")[2] as Element;
    fireEvent.pointerDown(named, { clientY: 272 });
    fireEvent.click(named);
    expect(again.location()).toBe("/degerlendirme"); // the month alone leads nowhere: its name opens nothing
  });

  it("names a column's sum as the caller says, and shows the caller's table instead of its own", async () => {
    const { container } = renderChart({ totalLabel: "Net", table: <p>Isı tablosu</p> });
    fireEvent.pointerEnter(container.querySelectorAll("rect[fill='transparent']")[2] as Element);
    expect(screen.getByText("Net")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    expect(screen.getByText("Isı tablosu")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
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

  it("opens a month's rows with a click beside its segments, and a series' rows with a click on its segment", () => {
    const { container, location } = renderChart({ open: OPEN });
    const bands = container.querySelectorAll("rect[fill='transparent']");
    expect(bands[2]?.getAttribute("class")).toContain("cursor-pointer");
    fireEvent.pointerDown(bands[2] as Element, { clientY: 0 }); // above the columns: the month
    fireEvent.click(bands[2] as Element);
    expect(location()).toBe("/islemler?from=2026-10-01");
    // October's Market & Gıda lies under its Ulaşım: its segment ends square at both sides.
    const market = container.querySelectorAll("path.fill-slot-1")[2] as Element;
    fireEvent.pointerDown(bands[2] as Element, { clientY: middleOf(market) });
    fireEvent.click(bands[2] as Element);
    expect(location()).toBe("/islemler?from=2026-10-01&group=market");
  });

  it("says in the tip what a click opens and sets its series apart, and under the chart what a click does", () => {
    const { container } = renderChart({ open: OPEN });
    const bands = container.querySelectorAll("rect[fill='transparent']");
    const market = container.querySelectorAll("path.fill-slot-1")[2] as Element;
    fireEvent.pointerMove(bands[2] as Element, { clientY: middleOf(market) });
    expect(screen.getByText("Tıklayın: bu ayın Market & Gıda işlemleri açılır.")).toBeInTheDocument();
    expect(market.getAttribute("class")).not.toContain("opacity-50");
    expect(container.querySelectorAll("path.fill-slot-2")[2]?.getAttribute("class")).toContain("opacity-50");
    fireEvent.pointerMove(bands[2] as Element, { clientY: 0 });
    expect(screen.getByText("Tıklayın: bu ayın işlemleri açılır.")).toBeInTheDocument();
    expect(screen.getByText(OPEN.hint)).toBeInTheDocument();
  });

  it("shows a touched month first and opens it at a second touch, or with the link its tip keeps", () => {
    const { container, location } = renderChart({ open: OPEN });
    const band = container.querySelectorAll("rect[fill='transparent']")[1] as Element;
    fireEvent.pointerDown(band, { pointerType: "touch", clientY: 0 });
    fireEvent.click(band);
    expect(location()).toBe("/degerlendirme"); // the first touch shows the month
    fireEvent.pointerLeave(container.querySelector("svg")?.parentElement as Element, { pointerType: "touch" });
    const tip = screen.getByText("Aç: bu ayın işlemleri").closest("a");
    expect(tip).toHaveAttribute("href", "/islemler?from=2026-09-01"); // the tip stays after the finger lifts
    fireEvent.pointerDown(band, { pointerType: "touch", clientY: 0 });
    fireEvent.click(band);
    expect(location()).toBe("/islemler?from=2026-09-01");
  });

  it("puts a touched month away at a press outside the chart, and after a finger's scroll over it", () => {
    const { container } = renderChart({ open: OPEN });
    const band = container.querySelectorAll("rect[fill='transparent']")[1] as Element;
    fireEvent.pointerDown(band, { pointerType: "touch", clientY: 0 });
    expect(screen.getByText("Eylül 2026")).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByText("Eylül 2026")).not.toBeInTheDocument();
    fireEvent.pointerDown(band, { pointerType: "touch", clientY: 0 });
    fireEvent.pointerCancel(band, { pointerType: "touch" });
    expect(screen.queryByText("Eylül 2026")).not.toBeInTheDocument();
  });

  it("opens the series on the pointer's side of zero when a month alone leads nowhere", () => {
    const money = [
      { key: "in", label: "Gelen", slot: 3 as const },
      { key: "out", label: "Giden", slot: 2 as const },
    ];
    const kind = (series: string) => (series === "in" ? "income" : "purchase");
    const open = {
      link: ({ month, series }: MonthPart): Destination | null =>
        series ? { screen: "transactions", id: "", query: { from: `${month}-01`, kind: kind(series) } } : null,
      hint: "Bir ayın gelen ya da giden parasına tıklayın.",
    };
    const { container, location } = renderChart({
      series: money,
      months: [{ month: "2026-10", values: { in: 500_000, out: -300_000 } }],
      open,
    });
    const band = container.querySelector("rect[fill='transparent']") as Element;
    expect(band.getAttribute("class")).toBeNull(); // the month alone leads nowhere: no hand over the column
    fireEvent.pointerDown(band, { clientY: 30 });
    fireEvent.click(band);
    expect(location()).toBe("/islemler?from=2026-10-01&kind=income");
    fireEvent.pointerDown(band, { clientY: 250 });
    fireEvent.click(band);
    expect(location()).toBe("/islemler?from=2026-10-01&kind=purchase");
  });

  it("names the months and the values of the table view with the same links", async () => {
    renderChart({ open: OPEN });
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    const table = screen.getByRole("table", { name: "Aylık giderler" });
    expect(within(table).getByRole("link", { name: "Ekim 2026" })).toHaveAttribute("href", "/islemler?from=2026-10-01");
    expect(within(table).getByRole("link", { name: "1.000,00 TL" })).toHaveAttribute(
      "href",
      "/islemler?from=2026-08-01&group=ulasim",
    );
  });

  it("draws no hand, no hint and no link without anywhere to lead", async () => {
    const { container } = renderChart();
    expect(container.querySelector("rect.cursor-pointer")).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("says when there is nothing to draw, without a switch", () => {
    renderChart({ months: [{ month: "2026-10", values: {} }] });
    expect(screen.getByText("Gösterilecek veri yok.")).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
