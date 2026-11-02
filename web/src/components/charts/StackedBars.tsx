// Monthly stacks — by group or by necessity level — as the MVP report drew them (rapor.js stackedChart): each series in
// its fixed colour slot, 2 px of the card between stacked segments, the data end rounded by 4 px; what is below zero
// hangs under the axis, so its sign shows in its place and not in its colour alone. Months from `forecastFrom` on are
// a forecast: lighter, after a dashed line marked "tahmin". A month the documents cover only partly is lighter too and
// marked "eksik". A reference line (the typical month, from complete months only) is the caller's to give; the chart
// computes no average of its own. The pointer shows a month's values; the table view shows them all, or what the
// caller gives instead (a heat table).

import { type ReactNode, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { formatMoney, formatMoneyShort, formatMonth } from "../../lib/format";
import { Table, Td, Th } from "../ui/Table";
import { ChartFrame } from "./ChartFrame";
import { ChartTip } from "./ChartTip";
import { monthLabels, type StackSeries, stackLayout } from "./layout";
import { Legend } from "./Legend";
import { SLOT_BG, SLOT_FILL } from "./palette";
import { useWidth } from "./useWidth";

export interface MonthValues {
  month: string; // "2026-04"
  values: Readonly<Record<string, number>>; // by series key, minor units
}

interface StackedBarsProps {
  title: string;
  summary: ReactNode;
  series: readonly StackSeries[]; // from the baseline outwards, each with its slot
  months: readonly MonthValues[];
  currency?: string;
  forecastFrom?: string; // the first month that is a forecast
  // Months the documents cover only partly (or a period cuts): drawn lighter and marked "eksik"; an average the
  // caller gives leaves them out.
  partial?: readonly string[];
  reference?: { label: string; value: number }; // a line across the chart, minor units
  totalLabel?: string; // what a column's sum is called: "Toplam", or "Net" for money in above and out below
  table?: ReactNode; // the table view, when the caller's says more than the months' values (a heat table)
  height?: number;
}

const MARGIN = { top: 26, right: 12, bottom: 28, left: 76 };
const HALO = "[paint-order:stroke] stroke-white stroke-[3px] [stroke-linejoin:round] dark:stroke-zinc-900";

export function StackedBars({
  title,
  summary,
  series,
  months,
  currency = "TRY",
  forecastFrom,
  partial = [],
  reference,
  totalLabel,
  table: ownTable,
  height = 280,
}: StackedBarsProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const [measure, width] = useWidth();
  const [active, setActive] = useState<number | null>(null);
  const money = (minor: number) => ({ minor, currency });
  const shown = series.filter((s) => months.some((m) => (m.values[s.key] ?? 0) !== 0));
  const forecastIndex = forecastFrom ? months.findIndex((m) => m.month >= forecastFrom) : -1;
  const isForecast = (index: number) => forecastIndex >= 0 && index >= forecastIndex;
  const isPartial = (index: number) => partial.includes(months[index]?.month ?? "");
  const monthName = (index: number) => {
    const name = formatMonth(months[index]?.month ?? "");
    if (isForecast(index)) {
      return t("forecastMonth", { month: name });
    }
    return isPartial(index) ? t("partialMonth", { month: name }) : name;
  };
  const sumName = totalLabel ?? t("total");

  const size = { width: Math.max(280, width), height };
  const layout = stackLayout(
    months.map((m) => ({ key: m.month, values: m.values })),
    shown,
    size,
    MARGIN,
  );
  const { plot } = layout;
  const actual = layout.columns.filter((column) => !isForecast(column.index));
  const labelled = new Set<number>();
  if (layout.band >= 26 && actual.length > 0) {
    // As the MVP: the highest month and the last one with an amount carry their totals.
    const highest = actual.reduce((best, column) => (column.positive > best.positive ? column : best));
    const last = [...actual].reverse().find((column) => column.total !== 0);
    for (const column of [highest, last]) {
      if (column && column.positive > 0) {
        labelled.add(column.index);
      }
    }
  }
  const activeColumn = active === null ? undefined : layout.columns[active];

  const chart = (
    <div ref={measure} className="relative" onPointerLeave={() => setActive(null)}>
      <svg
        width={size.width}
        height={size.height}
        role="img"
        aria-label={t("image.stacked", { title })}
        aria-describedby={summaryId}
        className="block overflow-visible"
      >
        {layout.ticks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={plot.left}
              x2={plot.right}
              y1={tick.y}
              y2={tick.y}
              shapeRendering="crispEdges"
              className={tick.value === 0 ? "stroke-chart-axis" : "stroke-chart-grid"}
            />
            <text x={plot.left - 8} y={tick.y} dy="0.32em" textAnchor="end" className="fill-chart-ink-2 text-[11px]">
              {formatMoneyShort(money(tick.value))}
            </text>
          </g>
        ))}
        {layout.columns.map((column) => (
          <g
            key={column.key}
            className={cn("transition-opacity", active !== null && active !== column.index && "opacity-45")}
          >
            {column.segments.map((segment) => (
              <path
                key={segment.series.key}
                d={segment.d}
                className={SLOT_FILL[segment.series.slot]}
                fillOpacity={isForecast(column.index) ? 0.42 : isPartial(column.index) ? 0.55 : undefined}
              />
            ))}
          </g>
        ))}
        {layout.band >= 26
          ? layout.columns
              .filter((column) => isPartial(column.index) && !isForecast(column.index))
              .map((column) => (
                <text
                  key={column.key}
                  x={column.center}
                  y={plot.top - 12}
                  textAnchor="middle"
                  className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
                >
                  {t("partial")}
                </text>
              ))
          : null}
        {forecastIndex > 0 ? (
          <g>
            <line
              x1={plot.left + layout.band * forecastIndex}
              x2={plot.left + layout.band * forecastIndex}
              y1={plot.top - 10}
              y2={plot.bottom}
              strokeDasharray="3 3"
              shapeRendering="crispEdges"
              className="stroke-chart-axis"
            />
            <text
              x={plot.left + layout.band * forecastIndex + 6}
              y={plot.top - 12}
              className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
            >
              {t("forecast")}
            </text>
          </g>
        ) : null}
        {reference ? (
          <g>
            <line
              x1={plot.left}
              x2={plot.right}
              y1={layout.y(reference.value)}
              y2={layout.y(reference.value)}
              shapeRendering="crispEdges"
              className="stroke-chart-ink-2"
              strokeOpacity={0.6}
            />
            <text
              x={plot.right}
              y={layout.y(reference.value) - 6}
              textAnchor="end"
              className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
            >
              {t("reference", { label: reference.label, amount: formatMoneyShort(money(reference.value)) })}
            </text>
          </g>
        ) : null}
        {layout.columns
          .filter((column) => labelled.has(column.index))
          .map((column) => (
            <text
              key={column.key}
              x={column.center}
              y={column.top - 6}
              textAnchor="middle"
              className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
            >
              {formatMoneyShort(money(column.total))}
            </text>
          ))}
        {monthLabels(
          months.map((m) => m.month),
          layout.band,
          plot.left,
        ).map((label) => (
          <text
            key={label.index}
            x={layout.columns[label.index]?.center ?? 0}
            y={size.height - 8}
            textAnchor="middle"
            className="fill-chart-ink-2 text-[11px]"
          >
            {label.text}
          </text>
        ))}
        {layout.columns.map((column) => (
          <rect
            key={column.key}
            x={column.band.x}
            y={plot.top}
            width={column.band.width}
            height={plot.bottom - plot.top}
            fill="transparent"
            onPointerEnter={() => setActive(column.index)}
            onPointerDown={() => setActive(column.index)}
          />
        ))}
      </svg>
      {activeColumn ? (
        <ChartTip
          at={activeColumn.center}
          width={size.width}
          top={plot.top}
          title={monthName(activeColumn.index)}
          rows={shown
            .map((s) => ({ s, value: months[activeColumn.index]?.values[s.key] ?? 0 }))
            .filter(({ value }) => value !== 0)
            .sort((a, b) => b.value - a.value)
            .map(({ s, value }) => ({
              key: s.key,
              label: s.label,
              value: formatMoney(money(value)),
              swatch: <span className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[s.slot])} />,
            }))}
          total={{ label: sumName, value: formatMoney(money(activeColumn.total)) }}
        />
      ) : null}
    </div>
  );

  const marked = months.some((_, index) => isPartial(index) && !isForecast(index));
  const legend = (
    <Legend
      items={[
        ...shown.map((s) => ({ key: s.key, label: s.label, swatch: SLOT_BG[s.slot] })),
        ...(forecastIndex >= 0 ? [{ key: "forecast", label: t("forecastLegend"), swatch: "bg-chart-ink-2 opacity-40" }] : []),
        ...(marked ? [{ key: "partial", label: t("partialLegend"), swatch: "bg-chart-ink-2 opacity-55" }] : []),
      ]}
    />
  );

  const table = ownTable ?? (
    <Table>
      <caption className="sr-only">{title}</caption>
      <thead>
        <tr>
          <Th>{t("month")}</Th>
          {shown.map((s) => (
            <Th key={s.key} className="text-right">
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[s.slot])} />
                {s.label}
              </span>
            </Th>
          ))}
          <Th className="text-right">{sumName}</Th>
        </tr>
      </thead>
      <tbody>
        {/* The newest month first, as the MVP's table. */}
        {[...layout.columns].reverse().map((column) => (
            <tr key={column.key}>
              <Td className="whitespace-nowrap">{monthName(column.index)}</Td>
              {shown.map((s) => {
                const value = months[column.index]?.values[s.key] ?? 0;
                return (
                  <Td key={s.key} className="whitespace-nowrap text-right tabular-nums">
                    {value === 0 ? t("none") : formatMoney(money(value))}
                  </Td>
                );
              })}
              <Td className="whitespace-nowrap text-right font-medium tabular-nums">
                {formatMoney(money(column.total))}
              </Td>
            </tr>
          ))}
      </tbody>
    </Table>
  );

  return (
    <ChartFrame
      title={title}
      summary={summary}
      summaryId={summaryId}
      legend={legend}
      chart={chart}
      table={table}
      empty={shown.length === 0}
    />
  );
}
