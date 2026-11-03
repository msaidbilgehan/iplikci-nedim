// Balances over days (F09's forecast, an account's balance curve): each account a line in its colour slot, stepping
// from one day's closing balance to the next. Zero is always on the axis and drawn darker than the gridlines; the part
// below it is hatched and named "eksi bakiye", so a balance under zero shows by its place, a pattern and words rather
// than by colour alone. Lines after the first are dashed, so they part without colour too. Markers name days, such as
// the first one under zero. The pointer shows a day's balances; the table view shows them all.

import { type PointerEvent, type ReactNode, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { formatDay, formatDayShort, formatMoney, formatMoneyShort } from "../../lib/format";
import { Table, Td, Th } from "../ui/Table";
import { ChartFrame } from "./ChartFrame";
import { ChartTip } from "./ChartTip";
import { type LineSeries, lineLayout, nearestDay } from "./layout";
import { Legend } from "./Legend";
import { SLOT_FILL, SLOT_STROKE } from "./palette";
import { useWidth } from "./useWidth";

/** How a value is written: on the axis (short) and in the tip and the table (whole). */
export interface ValueFormat {
  tick: (value: number) => string;
  value: (value: number) => string;
}

interface LineChartProps {
  title: string;
  summary: ReactNode;
  series: readonly LineSeries[];
  currency?: string;
  markers?: ReadonlyArray<{ day: string; label: string }>;
  height?: number;
  // Values that are no money (a rate): how to write them, with an axis around them rather than from zero.
  format?: ValueFormat;
}

const MARGIN = { top: 26, right: 16, bottom: 28, left: 76 };
const DASHES: ReadonlyArray<string | undefined> = [undefined, "6 3", "2 3", "8 3 2 3"];
const HALO = "[paint-order:stroke] stroke-white stroke-[3px] [stroke-linejoin:round] dark:stroke-zinc-900";

const dashOf = (index: number): string | undefined => DASHES[index % DASHES.length];

/** A short line in a series' colour and dash, as its legend swatch. */
function LineSwatch({ series, index }: { series: LineSeries; index: number }) {
  return (
    <svg width="20" height="8" aria-hidden="true" className="shrink-0">
      <line
        x1="0"
        x2="20"
        y1="4"
        y2="4"
        strokeWidth={2}
        strokeDasharray={dashOf(index)}
        className={SLOT_STROKE[series.slot]}
      />
    </svg>
  );
}

export function LineChart({
  title,
  summary,
  series,
  currency = "TRY",
  markers = [],
  height = 260,
  format,
}: LineChartProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const hatchId = useId();
  const [measure, width] = useWidth();
  const [active, setActive] = useState<number | null>(null);
  const written: ValueFormat = format ?? {
    tick: (minor) => formatMoneyShort({ minor, currency }),
    value: (minor) => formatMoney({ minor, currency }),
  };
  const size = { width: Math.max(280, width), height };
  const layout = lineLayout(series, size, MARGIN, format === undefined);
  const { plot } = layout;
  const activeDay = active === null ? undefined : layout.days[active];

  function follow(event: PointerEvent<SVGRectElement>) {
    const box = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
    setActive(nearestDay(layout.days, layout.x, event.clientX - (box?.left ?? 0)));
  }

  const valueOn = (s: LineSeries, day: string) => s.points.find((p) => p.day === day)?.value;

  const chart = (
    <div ref={measure} className="relative" onPointerLeave={() => setActive(null)}>
      <svg
        width={size.width}
        height={size.height}
        role="img"
        aria-label={t("image.line", { title })}
        aria-describedby={summaryId}
        className="block overflow-visible"
      >
        <defs>
          <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" strokeWidth={2} strokeOpacity={0.35} className="stroke-chart-bad" />
          </pattern>
        </defs>
        {layout.belowZero && layout.belowZero.height > 0 ? (
          <g>
            <rect
              x={plot.left}
              y={layout.belowZero.top}
              width={plot.right - plot.left}
              height={layout.belowZero.height}
              fill={`url(#${hatchId})`}
            />
            {layout.belowZero.height >= 18 ? (
              <text
                x={plot.left + 6}
                y={layout.belowZero.top + 14}
                className={cn("fill-chart-bad text-[11px] font-semibold", HALO)}
              >
                {t("belowZero")}
              </text>
            ) : null}
          </g>
        ) : null}
        {layout.ticks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={plot.left}
              x2={plot.right}
              y1={tick.y}
              y2={tick.y}
              shapeRendering="crispEdges"
              className={tick.value === 0 ? "stroke-chart-ink-2" : "stroke-chart-grid"}
            />
            <text x={plot.left - 8} y={tick.y} dy="0.32em" textAnchor="end" className="fill-chart-ink-2 text-[11px]">
              {written.tick(tick.value)}
            </text>
          </g>
        ))}
        {layout.dayTicks.map((tick) => (
          <text
            key={tick.day}
            x={tick.x}
            y={size.height - 8}
            textAnchor="middle"
            className="fill-chart-ink-2 text-[11px]"
          >
            {formatDayShort(tick.day)}
          </text>
        ))}
        {markers.map((marker) => (
          <g key={`${marker.day}-${marker.label}`}>
            <line
              x1={layout.x(marker.day)}
              x2={layout.x(marker.day)}
              y1={plot.top - 10}
              y2={plot.bottom}
              strokeDasharray="3 3"
              shapeRendering="crispEdges"
              className="stroke-chart-ink-2"
            />
            <text
              x={layout.x(marker.day) + 4}
              y={plot.top - 12}
              className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
            >
              {marker.label}
            </text>
          </g>
        ))}
        {layout.paths.map((path, index) => (
          <path
            key={path.series.key}
            d={path.d}
            fill="none"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeDasharray={dashOf(index)}
            className={SLOT_STROKE[path.series.slot]}
          />
        ))}
        {activeDay ? (
          <g>
            <line
              x1={layout.x(activeDay)}
              x2={layout.x(activeDay)}
              y1={plot.top}
              y2={plot.bottom}
              shapeRendering="crispEdges"
              className="stroke-chart-axis"
            />
            {series.map((s) => {
              const value = valueOn(s, activeDay);
              return value === undefined ? null : (
                <circle
                  key={s.key}
                  cx={layout.x(activeDay)}
                  cy={layout.y(value)}
                  r={4}
                  strokeWidth={2}
                  className={cn("stroke-white dark:stroke-zinc-900", SLOT_FILL[s.slot])}
                />
              );
            })}
          </g>
        ) : null}
        <rect
          x={plot.left}
          y={plot.top}
          width={Math.max(0, plot.right - plot.left)}
          height={Math.max(0, plot.bottom - plot.top)}
          fill="transparent"
          onPointerMove={follow}
          onPointerDown={follow}
        />
      </svg>
      {activeDay ? (
        <ChartTip
          at={layout.x(activeDay)}
          width={size.width}
          top={plot.top}
          title={formatDay(activeDay)}
          rows={series.flatMap((s, index) => {
            const value = valueOn(s, activeDay);
            return value === undefined
              ? []
              : [
                  {
                    key: s.key,
                    label: s.label,
                    value: written.value(value),
                    swatch: <LineSwatch series={s} index={index} />,
                  },
                ];
          })}
        />
      ) : null}
    </div>
  );

  const legend = (
    <Legend
      items={series.map((s, index) => ({
        key: s.key,
        label: s.label,
        swatch: <LineSwatch series={s} index={index} />,
      }))}
    />
  );

  const table = (
    <Table>
      <caption className="sr-only">{title}</caption>
      <thead>
        <tr>
          <Th>{t("day")}</Th>
          {series.map((s) => (
            <Th key={s.key} className="text-right">
              {s.label}
            </Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {layout.days.map((day) => (
          <tr key={day}>
            <Td className="whitespace-nowrap">{formatDay(day)}</Td>
            {series.map((s) => {
              const value = valueOn(s, day);
              return (
                <Td key={s.key} className="whitespace-nowrap text-right tabular-nums">
                  {value === undefined ? t("none") : written.value(value)}
                </Td>
              );
            })}
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
      empty={layout.days.length === 0}
    />
  );
}
