import { describe, expect, it } from "vitest";

import {
  barPath,
  barShares,
  lineLayout,
  monthLabels,
  nearestDay,
  type StackSeries,
  stackLayout,
  valueAxis,
} from "./layout";

const SIZE = { width: 640, height: 280 };
const MARGIN = { top: 20, right: 10, bottom: 30, left: 60 };
const SERIES: StackSeries[] = [
  { key: "market", label: "Market", slot: 1 },
  { key: "ulasim", label: "Ulaşım", slot: 2 },
  { key: "ev", label: "Ev", slot: 3 },
];

const arcs = (d: string): number => (d.match(/A/g) ?? []).length;

describe("valueAxis", () => {
  it("always holds zero and ends at round amounts", () => {
    const { scale, ticks } = valueAxis(0, 1_234_567, 20, 250);
    expect(scale.domain()).toEqual([0, 1_400_000]);
    expect(ticks[0]).toEqual({ value: 0, y: 250 });
    expect(ticks.at(-1)).toEqual({ value: 1_400_000, y: 20 });
    expect(valueAxis(150_000, 300_000, 0, 100).scale.domain()[0]).toBe(0);
    expect(valueAxis(-250_000, 100_000, 0, 100).scale.domain()).toEqual([-250_000, 100_000]);
  });
});

describe("barPath", () => {
  it("rounds the data end by 4 px and keeps the baseline end square", () => {
    const rising = barPath(10, 20, 20, 100, "top");
    expect(rising.startsWith("M10,120")).toBe(true); // from the baseline
    expect(rising).toContain("A4,4 0 0 1 14,20");
    expect(arcs(rising)).toBe(2);
    const hanging = barPath(10, 20, 20, 100, "bottom");
    expect(hanging).toContain("A4,4 0 0 0 14,120");
    expect(arcs(barPath(10, 20, 20, 100, "none"))).toBe(0);
  });

  it("rounds a short or narrow bar no more than it can take", () => {
    expect(barPath(0, 0, 20, 2, "top")).toContain("A2,2");
    expect(barPath(0, 0, 3, 50, "top")).toContain("A1.5,1.5");
  });
});

describe("stackLayout", () => {
  const layout = stackLayout(
    [
      { key: "2026-04", values: { market: 400_000, ulasim: 100_000, ev: 0 } },
      { key: "2026-05", values: { market: 300_000, ulasim: -50_000, ev: 200_000 } },
    ],
    SERIES,
    SIZE,
    MARGIN,
  );
  const [april, may] = layout.columns;

  it("stacks the series from the baseline outwards, the card showing 2 px between them", () => {
    expect(april?.segments.map((s) => s.series.key)).toEqual(["market", "ulasim"]);
    const [inner, outer] = april?.segments ?? [];
    expect(inner && outer && inner.top - outer.bottom).toBeCloseTo(2);
    expect(inner?.bottom).toBeCloseTo(layout.zero);
  });

  it("rounds only each side's outermost segment", () => {
    const [inner, outer] = april?.segments ?? [];
    expect(arcs(inner?.d ?? "")).toBe(0);
    expect(arcs(outer?.d ?? "")).toBe(2);
  });

  it("hangs what is below zero under the axis, its outer end rounded", () => {
    const below = may?.segments.find((s) => s.series.key === "ulasim");
    expect(below?.top).toBeGreaterThanOrEqual(layout.zero);
    expect(below?.d).toContain("0 0 0"); // the arcs of a hanging end
    expect(may?.positive).toBe(500_000);
    expect(may?.negative).toBe(-50_000);
    expect(may?.total).toBe(450_000);
  });

  it("draws nothing for a series without an amount", () => {
    expect(april?.segments.some((s) => s.series.key === "ev")).toBe(false);
  });

  it("keeps a column narrow and centred in its month", () => {
    expect(layout.barWidth).toBeLessThanOrEqual(28);
    expect(april?.center).toBeCloseTo((april?.band.x ?? 0) + layout.band / 2);
    expect(layout.ticks.some((tick) => tick.value < 0)).toBe(true);
  });
});

describe("monthLabels", () => {
  const months = Array.from({ length: 24 }, (_, i) => `${2025 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`);

  it("labels every month when the columns are wide", () => {
    expect(monthLabels(months.slice(0, 6), 60, 0).map((label) => label.text)).toEqual([
      "Oca 25",
      "Şub 25",
      "Mar 25",
      "Nis 25",
      "May 25",
      "Haz 25",
    ]);
  });

  it("labels the first month of each quarter when they are narrower, and the years when narrower still", () => {
    expect(monthLabels(months, 20, 0).map((label) => label.text)).toEqual([
      "Oca 25",
      "Nis 25",
      "Tem 25",
      "Eki 25",
      "Oca 26",
      "Nis 26",
      "Tem 26",
      "Eki 26",
    ]);
    expect(monthLabels(months, 8, 0).map((label) => label.text)).toEqual(["2025", "2026"]);
  });
});

describe("lineLayout", () => {
  const days = (values: number[]) =>
    values.map((value, i) => ({ day: `2026-11-${String(15 + i).padStart(2, "0")}`, value }));

  it("spans the days across the plot and holds zero on the value axis", () => {
    const layout = lineLayout([{ key: "a", label: "Vadesiz", slot: 1, points: days([500_000, 400_000, 450_000]) }], SIZE, MARGIN);
    expect(layout.x("2026-11-15")).toBe(MARGIN.left);
    expect(layout.x("2026-11-17")).toBe(SIZE.width - MARGIN.right);
    expect(layout.zero).toBe(SIZE.height - MARGIN.bottom);
    expect(layout.belowZero).toBeNull();
    expect(layout.paths[0]?.d.startsWith(`M${MARGIN.left},`)).toBe(true);
  });

  it("gives the part below zero a band of its own when a balance goes under it", () => {
    const layout = lineLayout([{ key: "a", label: "Vadesiz", slot: 1, points: days([100_000, -50_000]) }], SIZE, MARGIN);
    expect(layout.belowZero).not.toBeNull();
    expect(layout.belowZero?.top).toBeCloseTo(layout.zero);
    expect((layout.belowZero?.top ?? 0) + (layout.belowZero?.height ?? 0)).toBeCloseTo(SIZE.height - MARGIN.bottom);
  });

  it("steps from one day's balance to the next rather than sloping", () => {
    const layout = lineLayout([{ key: "a", label: "Vadesiz", slot: 1, points: days([100_000, 50_000]) }], SIZE, MARGIN);
    const corners = (layout.paths[0]?.d ?? "").split("L").length - 1;
    expect(corners).toBe(2); // across at the first balance, then down to the second
  });

  it("finds the day nearest the pointer", () => {
    const layout = lineLayout([{ key: "a", label: "Vadesiz", slot: 1, points: days([1, 2, 3, 4, 5]) }], SIZE, MARGIN);
    expect(nearestDay(layout.days, layout.x, MARGIN.left + 1)).toBe(0);
    expect(nearestDay(layout.days, layout.x, SIZE.width)).toBe(4);
  });
});

describe("barShares", () => {
  it("measures each bar against the longest, giving nothing below zero a bar", () => {
    expect(barShares([400, 200, 100, -50])).toEqual([100, 50, 25, 0]);
    expect(barShares([0, 0])).toEqual([0, 0]);
  });
});
