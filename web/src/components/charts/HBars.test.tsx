import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../AppProviders";
import { type BarItem, HBars } from "./HBars";

const ITEMS: BarItem[] = [
  { key: "market", label: "Market", value: 400_000, slot: 1 },
  { key: "ulasim", label: "Ulaşım", value: 200_000, slot: 2 },
  { key: "iade", label: "İade alınan mağaza", value: -50_000, slot: 0 },
];

function renderBars(items: BarItem[] = ITEMS) {
  return render(
    <AppProviders>
      <HBars title="Kategoriler" summary="Son 6 tam ay." itemName="Kategori" items={items} />
    </AppProviders>,
  );
}

describe("HBars", () => {
  it("lists the rows in order, each with its name and amount", () => {
    renderBars();
    const list = screen.getByRole("list", { name: "Kategoriler" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      "Market: 4.000,00 TL",
      "Ulaşım: 2.000,00 TL",
      "İade alınan mağaza: −500,00 TL",
    ]);
    expect(list).toHaveAccessibleDescription("Son 6 tam ay.");
  });

  it("measures each bar against the longest, and gives nothing below zero a bar", () => {
    const { container } = renderBars();
    const bars = [...container.querySelectorAll<HTMLElement>("li span[aria-hidden='true'][style]")];
    // The share of the track the bar takes: calc() is written back in the browser's own order.
    const factor = (width: string) => Number(/([\d.]+) \*|\* ([\d.]+)/.exec(width)?.slice(1).find(Boolean));
    expect(bars.map((bar) => factor(bar.style.width))).toEqual([1, 0.5, 0]);
    expect(bars[0]?.className).toContain("bg-slot-1");
  });

  it("shows the same rows as a table with each one's share of the whole", async () => {
    renderBars();
    await userEvent.click(screen.getByRole("tab", { name: "Tablo" }));
    const table = screen.getByRole("table", { name: "Kategoriler" });
    expect(within(table).getByRole("columnheader", { name: "Kategori" })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /Market 4\.000,00 TL %73/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /Toplam 5\.500,00 TL/ })).toBeInTheDocument();
  });

  it("says when there is nothing to show", () => {
    renderBars([]);
    expect(screen.getByText("Gösterilecek veri yok.")).toBeInTheDocument();
  });
});
