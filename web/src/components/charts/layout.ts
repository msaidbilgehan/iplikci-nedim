// The charts' geometry, apart from drawing it: scales from d3-scale, lines from d3-shape, and the MVP report's rules
// for bars — 2 px of the card between stacked segments, the data end rounded by 4 px and the baseline end square
// (features.md, the charts' rules; rapor.js). Amounts are minor units, as the API sends them.

import { scaleBand, scaleLinear, scaleUtc } from "d3-scale";
import { curveStepAfter, line } from "d3-shape";

import { formatMonthShort } from "../../lib/format";
import type { Slot } from "./palette";

export interface Size {
  width: number;
  height: number;
}

export interface Margin {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface Plot {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface Tick {
  value: number;
  y: number;
}

export const RADIUS = 4;
const MAX_BAR = 28;
const LABEL_SPACE = 34; // the least distance between two month labels

const round = (n: number): number => Math.round(n * 100) / 100;

function plotOf(size: Size, margin: Margin): Plot {
  return { left: margin.left, right: size.width - margin.right, top: margin.top, bottom: size.height - margin.bottom };
}

/** A value axis that always holds zero, its ends at round numbers. */
export function valueAxis(low: number, high: number, top: number, bottom: number, count = 5) {
  const lo = Math.min(0, low);
  const hi = Math.max(0, high);
  const scale = scaleLinear()
    .domain(lo === hi ? [0, 1] : [lo, hi])
    .nice(count)
    .range([bottom, top]);
  const ticks: Tick[] = scale.ticks(count).map((value) => ({ value, y: scale(value) }));
  return { scale, ticks };
}

/** A bar, its data end rounded: "top" for one rising from the baseline, "bottom" for one hanging below it. */
export function barPath(
  x: number,
  y: number,
  width: number,
  height: number,
  end: "top" | "bottom" | "none",
  radius = RADIUS,
): string {
  const [l, t, w, h] = [round(x), round(y), round(width), round(height)];
  const r = round(Math.max(0, Math.min(radius, w / 2, h)));
  if (end === "top") {
    return `M${l},${t + h}V${t + r}A${r},${r} 0 0 1 ${l + r},${t}H${l + w - r}A${r},${r} 0 0 1 ${l + w},${t + r}V${t + h}Z`;
  }
  if (end === "bottom") {
    return `M${l},${t}V${t + h - r}A${r},${r} 0 0 0 ${l + r},${t + h}H${l + w - r}A${r},${r} 0 0 0 ${l + w},${t + h - r}V${t}Z`;
  }
  return `M${l},${t}H${l + w}V${t + h}H${l}Z`;
}

// --- stacked columns -------------------------------------------------------------------------------------------------

export interface StackSeries {
  key: string;
  label: string;
  slot: Slot;
}

export interface StackInput {
  key: string; // the month, "2026-04"
  values: Readonly<Record<string, number>>; // by series key, minor units
}

export interface Segment {
  series: StackSeries;
  value: number;
  top: number;
  bottom: number;
  d: string;
}

export interface Column {
  key: string;
  index: number;
  center: number;
  band: { x: number; width: number };
  positive: number; // what rises above zero
  negative: number; // what hangs below it
  total: number;
  top: number; // the y of the column's highest point
  segments: Segment[];
}

export interface StackLayout {
  columns: Column[];
  ticks: Tick[];
  zero: number;
  plot: Plot;
  band: number;
  barWidth: number;
  y: (value: number) => number;
}

/**
 * Columns of stacked segments, one per entry: positive values rise from zero and negative ones hang below it, the
 * series in their order from the baseline outwards. Touching segments each give up 1 px of the side they share, so the
 * card shows 2 px between them; the outermost segment of each side has the rounded data end.
 */
export function stackLayout(
  data: readonly StackInput[],
  series: readonly StackSeries[],
  size: Size,
  margin: Margin,
): StackLayout {
  const plot = plotOf(size, margin);
  const sides = data.map((entry) => {
    let positive = 0;
    let negative = 0;
    for (const s of series) {
      const value = entry.values[s.key] ?? 0;
      if (value > 0) {
        positive += value;
      } else {
        negative += value;
      }
    }
    return { positive, negative };
  });
  const { scale: y, ticks } = valueAxis(
    Math.min(0, ...sides.map((side) => side.negative)),
    Math.max(0, ...sides.map((side) => side.positive)),
    plot.top,
    plot.bottom,
  );
  const x = scaleBand<string>()
    .domain(data.map((entry) => entry.key))
    .range([plot.left, plot.right]);
  const band = x.bandwidth();
  const barWidth = Math.max(2, Math.min(MAX_BAR, band * 0.62));
  const columns = data.map((entry, index): Column => {
    const bandX = x(entry.key) ?? plot.left;
    const center = bandX + band / 2;
    const left = center - barWidth / 2;
    const segments: Segment[] = [];
    for (const sign of [1, -1] as const) {
      const side = series.filter((s) => sign * (entry.values[s.key] ?? 0) > 0);
      let reached = 0;
      side.forEach((s, k) => {
        const value = entry.values[s.key] ?? 0;
        const [a, b] = [y(reached), y(reached + value)];
        const outermost = k === side.length - 1;
        const top = Math.min(a, b) + (sign > 0 ? (outermost ? 0 : 1) : k > 0 ? 1 : 0);
        const bottom = Math.max(a, b) - (sign > 0 ? (k > 0 ? 1 : 0) : outermost ? 0 : 1);
        if (bottom - top >= 0.5) {
          const end = outermost ? (sign > 0 ? "top" : "bottom") : "none";
          segments.push({ series: s, value, top, bottom, d: barPath(left, top, barWidth, bottom - top, end) });
        }
        reached += value;
      });
    }
    const { positive, negative } = sides[index] ?? { positive: 0, negative: 0 };
    return {
      key: entry.key,
      index,
      center,
      band: { x: bandX, width: band },
      positive,
      negative,
      total: positive + negative,
      top: y(positive),
      segments,
    };
  });
  return { columns, ticks, zero: y(0), plot, band, barWidth, y };
}

/**
 * The months that get a label under the axis, as the MVP report chose them: every month when the columns are wide
 * enough, else the first month of each quarter, else the years; never two labels closer than 34 px.
 */
export function monthLabels(months: readonly string[], band: number, left: number): Array<{ index: number; text: string }> {
  const labels: Array<{ index: number; text: string }> = [];
  let last = Number.NEGATIVE_INFINITY;
  months.forEach((month, index) => {
    const number = Number(month.slice(5, 7));
    let text: string | null = null;
    if (band >= 46) {
      text = formatMonthShort(month);
    } else if (band >= 15) {
      text = number % 3 === 1 ? formatMonthShort(month) : null;
    } else {
      text = number === 1 || index === 0 ? month.slice(0, 4) : null;
    }
    const center = left + band * index + band / 2;
    if (text !== null && center - last > LABEL_SPACE) {
      labels.push({ index, text });
      last = center;
    }
  });
  return labels;
}

// --- lines over days -------------------------------------------------------------------------------------------------

export interface LinePoint {
  day: string; // "2026-11-15"
  value: number; // minor units
}

export interface LineSeries {
  key: string;
  label: string;
  slot: Slot;
  points: readonly LinePoint[];
}

export interface LineLayout {
  paths: Array<{ series: LineSeries; d: string }>;
  ticks: Tick[];
  days: string[]; // every day of any series, in order
  dayTicks: Array<{ day: string; x: number }>;
  zero: number;
  belowZero: { top: number; height: number } | null; // the band under the zero line, when the axis reaches it
  plot: Plot;
  x: (day: string) => number;
  y: (value: number) => number;
}

const dateOf = (day: string): Date => new Date(`${day.slice(0, 10)}T00:00:00Z`);

/**
 * Lines of balances over days. A balance holds until the next day's moves, so each line steps rather than slopes; the
 * value axis always holds zero, and the part below it is a band of its own.
 */
export function lineLayout(series: readonly LineSeries[], size: Size, margin: Margin): LineLayout {
  const plot = plotOf(size, margin);
  const days = [...new Set(series.flatMap((s) => s.points.map((p) => p.day)))].sort();
  const values = series.flatMap((s) => s.points.map((p) => p.value));
  const { scale: yScale, ticks } = valueAxis(Math.min(0, ...values), Math.max(0, ...values), plot.top, plot.bottom);
  const first = days[0] ?? "1970-01-01";
  const last = days[days.length - 1] ?? first;
  const xScale = scaleUtc()
    .domain([dateOf(first), dateOf(last)])
    .range([plot.left, plot.right]);
  const x = (day: string): number => xScale(dateOf(day));
  const y = (value: number): number => yScale(value);
  const draw = line<LinePoint>()
    .x((p) => x(p.day))
    .y((p) => y(p.value))
    .curve(curveStepAfter);
  const count = Math.max(2, Math.floor((plot.right - plot.left) / 90));
  const dayTicks = xScale.ticks(count).map((date) => ({ day: date.toISOString().slice(0, 10), x: xScale(date) }));
  const zero = y(0);
  const lowest = yScale.domain()[0] ?? 0;
  return {
    paths: series.map((s) => ({ series: s, d: draw([...s.points]) ?? "" })),
    ticks,
    days,
    dayTicks,
    zero,
    belowZero: lowest < 0 ? { top: zero, height: plot.bottom - zero } : null,
    plot,
    x,
    y,
  };
}

/** The index of the day whose x is nearest to the pointer's. */
export function nearestDay(days: readonly string[], x: (day: string) => number, pointer: number): number {
  let best = 0;
  let distance = Number.POSITIVE_INFINITY;
  days.forEach((day, index) => {
    const d = Math.abs(x(day) - pointer);
    if (d < distance) {
      best = index;
      distance = d;
    }
  });
  return best;
}

// --- horizontal bars -------------------------------------------------------------------------------------------------

/** Each value's bar as a share of the longest, in percent; nothing below zero has a bar. */
export function barShares(values: readonly number[]): number[] {
  const longest = Math.max(0, ...values);
  if (longest === 0) {
    return values.map(() => 0);
  }
  const scale = scaleLinear().domain([0, longest]).range([0, 100]).clamp(true);
  return values.map((value) => round(scale(Math.max(0, value))));
}
