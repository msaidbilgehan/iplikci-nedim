// Monthly stacks — by group or by necessity level — as the MVP report drew them (rapor.js stackedChart): each series in
// its fixed colour slot, 2 px of the card between stacked segments, the data end rounded by 4 px; what is below zero
// hangs under the axis, so its sign shows in its place and not in its colour alone. Months from `forecastFrom` on are
// a forecast: lighter, after a dashed line marked "tahmin". A month the documents cover only partly is lighter too and
// marked "eksik", or in the caller's words when it knows why: a month that waits for its statements says "bekliyor"
// and the day it should close. A reference line (the typical month, from complete months only) is the caller's to
// give; the chart computes no average of its own. The pointer shows a month's values; the table view shows them all,
// or what the caller gives instead (a heat table). A month, or one series of it, may lead to its rows (open): a click
// on its segment opens that series, a click beside the segments or on the month's name the whole month; the table's
// months and values are the same links.

import { type PointerEvent, type ReactNode, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Destination } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMoneyShort, formatMonth } from "../../lib/format";
import { hrefOf } from "../../lib/links";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { ChartFrame } from "./ChartFrame";
import { ChartTip, type TipOpen } from "./ChartTip";
import { type Column, monthLabels, type Segment, type StackSeries, stackLayout } from "./layout";
import { Legend } from "./Legend";
import { type MonthMark, partialName } from "./marks";
import { type ChartOpen, isTouch, useDismiss, useOpener } from "./open";
import { SLOT_BG, SLOT_FILL } from "./palette";
import { useWidth } from "./useWidth";

export interface MonthValues {
  month: string; // "2026-04"
  values: Readonly<Record<string, number>>; // by series key, minor units
}

/** A month's column, or one series of it: a part of the chart that may lead to its rows. */
export interface MonthPart {
  month: string;
  series: string | null; // a series' key; null for the whole month
}

export interface StackedOpen extends ChartOpen<MonthPart> {
  // What a click opens, in the tip: "bu ayın giderleri"; by default the month's rows, or a series' rows of it.
  what?: (series: StackSeries | null) => string;
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
  // The partial months' own marks, by month, when the caller knows why they are not whole: a month not closed is not
  // missing anything while it waits for its statements.
  marks?: Readonly<Record<string, MonthMark>>;
  reference?: { label: string; value: number }; // a line across the chart, minor units
  totalLabel?: string; // what a column's sum is called: "Toplam", or "Net" for money in above and out below
  table?: ReactNode; // the table view, when the caller's says more than the months' values (a heat table)
  height?: number;
  open?: StackedOpen; // where the months and their series lead
}

/** The part the pointer is on, and whether a touch chose it: then it stays until the next press. */
interface Aim {
  column: number;
  series: string | null;
  touch: boolean;
}

const MARGIN = { top: 26, right: 12, bottom: 28, left: 76 };
// A mark of two lines, a word over the day, needs the room of both above the plot; a column's total under them stays
// clear of the day.
const MARKED_MARGIN = { ...MARGIN, top: 40 };
const MARK_BAND = 44; // a column narrower than this has no room for a word over a day: one line of the two
const MARK_CHAR = 6.2; // the width of a mark's letter at 11 px, so a longer word needs a wider column
const HALO = "[paint-order:stroke] stroke-white stroke-[3px] [stroke-linejoin:round] dark:stroke-zinc-900";

const sameAim = (a: Aim | null, b: Aim) => a !== null && a.column === b.column && a.series === b.series;

export function StackedBars({
  title,
  summary,
  series,
  months,
  currency = "TRY",
  forecastFrom,
  partial = [],
  marks = {},
  reference,
  totalLabel,
  table: ownTable,
  height = 280,
  open,
}: StackedBarsProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const [measure, width, box] = useWidth();
  const [aim, setAim] = useState<Aim | null>(null);
  const pressed = useRef<Aim | null>(null);
  const opener = useOpener();
  useDismiss(box, aim?.touch === true, () => setAim(null));
  const money = (minor: number) => ({ minor, currency });
  const shown = series.filter((s) => months.some((m) => (m.values[s.key] ?? 0) !== 0));
  const forecastIndex = forecastFrom ? months.findIndex((m) => m.month >= forecastFrom) : -1;
  const isForecast = (index: number) => forecastIndex >= 0 && index >= forecastIndex;
  const isPartial = (index: number) => partial.includes(months[index]?.month ?? "");
  const markOf = (index: number): MonthMark | undefined =>
    isPartial(index) && !isForecast(index) ? marks[months[index]?.month ?? ""] : undefined;
  const monthName = (index: number) => {
    const name = formatMonth(months[index]?.month ?? "");
    if (isForecast(index)) {
      return t("forecastMonth", { month: name });
    }
    return isPartial(index) ? partialName(name, markOf(index), t) : name;
  };
  const sumName = totalLabel ?? t("total");
  const linkTo = (month: string, key: string | null) => open?.link({ month, series: key }) ?? null;

  const size = { width: Math.max(280, width), height };
  const stacks = months.map((m) => ({ key: m.month, values: m.values }));
  const plain = stackLayout(stacks, shown, size, MARGIN);
  // A mark's word and its day stand over each other where the columns are wide enough for the word.
  const twoLines = plain.band >= MARK_BAND && months.some((_, index) => markOf(index)?.day !== undefined);
  const layout = twoLines ? stackLayout(stacks, shown, size, MARKED_MARGIN) : plain;
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

  /** Where a part leads: a series' own rows, else its month's; null when neither leads anywhere. */
  const resolve = (part: Omit<Aim, "touch">): { link: Destination; series: string | null } | null => {
    const month = months[part.column]?.month ?? "";
    const own = part.series === null ? null : linkTo(month, part.series);
    if (own) {
      return { link: own, series: part.series };
    }
    const whole = linkTo(month, null);
    return whole ? { link: whole, series: null } : null;
  };

  /**
   * The part under the pointer: the segment it is on; beside the segments the whole month when the month leads
   * somewhere, else the nearest segment (above zero what rises, below it what hangs). The month's name under the
   * axis is the whole month alone.
   */
  const aimAt = (column: Column, event: PointerEvent<SVGRectElement>, touch: boolean): Aim => {
    const at = { column: column.index, touch };
    if (!open) {
      return { ...at, series: null };
    }
    const frame = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
    const y = event.clientY - (frame?.top ?? 0);
    if (y > plot.bottom) {
      return { ...at, series: null };
    }
    const on = column.segments.find((s) => y >= s.top - 1 && y <= s.bottom + 1);
    if (on) {
      return { ...at, series: on.series.key };
    }
    if (linkTo(months[column.index]?.month ?? "", null)) {
      return { ...at, series: null };
    }
    const away = (s: Segment) => (y < s.top ? s.top - y : y > s.bottom ? y - s.bottom : 0);
    const nearest = column.segments.reduce<Segment | undefined>(
      (best, s) => (best === undefined || away(s) < away(best) ? s : best),
      undefined,
    );
    return { ...at, series: nearest?.series.key ?? null };
  };
  const hover = (column: Column, event: PointerEvent<SVGRectElement>) => {
    if (!isTouch(event)) {
      const next = aimAt(column, event, false);
      setAim((was) => (sameAim(was, next) && was?.touch === false ? was : next));
    }
  };

  const activeColumn = aim === null ? undefined : layout.columns[aim.column];
  const target = aim === null ? null : resolve(aim);
  const tipOpen = ((): TipOpen | null => {
    const href = target ? hrefOf(target.link) : null;
    if (!open || !target || !href) {
      return null;
    }
    const of = target.series === null ? null : (shown.find((s) => s.key === target.series) ?? null);
    const what = open.what ? open.what(of) : of ? t("open.series", { series: of.label }) : t("open.month");
    return aim?.touch ? { href, label: t("open.tap", { what }) } : { say: t("open.click", { what }) };
  })();

  const chart = (
    <div
      ref={measure}
      className="relative"
      onPointerLeave={(event) => {
        if (!isTouch(event)) {
          setAim(null);
        }
      }}
    >
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
            className={cn("transition-opacity", aim !== null && aim.column !== column.index && "opacity-45")}
          >
            {column.segments.map((segment) => (
              <path
                key={segment.series.key}
                d={segment.d}
                className={cn(
                  SLOT_FILL[segment.series.slot],
                  // The series a click opens stands out of its month; the month's others step back.
                  target !== null &&
                    target.series !== null &&
                    aim?.column === column.index &&
                    segment.series.key !== target.series &&
                    "opacity-50",
                )}
                fillOpacity={isForecast(column.index) ? 0.42 : isPartial(column.index) ? 0.55 : undefined}
              />
            ))}
          </g>
        ))}
        {layout.band >= 26
          ? layout.columns
              .filter((column) => isPartial(column.index) && !isForecast(column.index))
              .map((column) => {
                // A month without a mark of its own is "eksik"; one with a mark says its word where the column is
                // wide enough for it, with its day under it, and the day alone where the word does not fit.
                const mark = markOf(column.index);
                const fits = mark !== undefined && layout.band >= mark.word.length * MARK_CHAR;
                const word = mark ? (fits ? mark.word : null) : t("partial");
                const day = mark?.day ?? null;
                return (
                  <g key={column.key}>
                    {word ? (
                      <text
                        x={column.center}
                        y={plot.top - (twoLines ? 27 : 12)}
                        textAnchor="middle"
                        className={cn("fill-chart-ink-2 text-[11px] font-semibold", HALO)}
                      >
                        {word}
                      </text>
                    ) : null}
                    {day !== null && (twoLines || word === null) ? (
                      <text
                        x={column.center}
                        y={plot.top - (twoLines ? 14 : 12)}
                        textAnchor="middle"
                        className={cn("fill-chart-ink-2 text-[11px]", HALO)}
                      >
                        {day}
                      </text>
                    ) : null}
                  </g>
                );
              })
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
        {/* Down to the month's name under the axis: a click on the name is a click beside the segments. */}
        {layout.columns.map((column) => (
          <rect
            key={column.key}
            x={column.band.x}
            y={plot.top}
            width={column.band.width}
            height={size.height - plot.top}
            fill="transparent"
            className={open && resolve({ column: column.index, series: null }) !== null ? "cursor-pointer" : undefined}
            onPointerEnter={(event) => hover(column, event)}
            onPointerMove={open ? (event) => hover(column, event) : undefined}
            onPointerDown={(event) => {
              const next = aimAt(column, event, isTouch(event));
              opener.press(event, sameAim(aim, next));
              pressed.current = next;
              setAim(next);
            }}
            onPointerCancel={() => {
              // A finger that scrolls the page over the chart chose nothing.
              if (pressed.current?.touch) {
                pressed.current = null;
                setAim(null);
              }
            }}
            onClick={
              open
                ? () => opener.click(resolve(pressed.current ?? { column: column.index, series: null })?.link ?? null)
                : undefined
            }
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
          marked={target?.series ?? null}
          open={tipOpen}
        />
      ) : null}
    </div>
  );

  const marked = months.some((_, index) => isPartial(index) && !isForecast(index));
  // The months the caller says why of are not closed yet; the others are only partly covered.
  const partials = months.map((_, index) => index).filter((index) => isPartial(index) && !isForecast(index));
  const said = partials.filter((index) => markOf(index) !== undefined).length;
  const partialLegend = said === 0 ? "partialLegend" : said === partials.length ? "markedLegend" : "mixedLegend";
  const legend = (
    <Legend
      items={[
        ...shown.map((s) => ({ key: s.key, label: s.label, swatch: SLOT_BG[s.slot] })),
        ...(forecastIndex >= 0 ? [{ key: "forecast", label: t("forecastLegend"), swatch: "bg-chart-ink-2 opacity-40" }] : []),
        ...(marked
          ? [{ key: "partial", label: t(partialLegend), swatch: "bg-chart-ink-2 opacity-55" }]
          : []),
      ]}
    />
  );

  const linked = (link: Destination | null, text: string) =>
    link ? <ScreenLink link={link}>{text}</ScreenLink> : text;
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
        {[...layout.columns].reverse().map((column) => {
          const month = months[column.index]?.month ?? "";
          return (
            <tr key={column.key}>
              <Td className="whitespace-nowrap">{linked(linkTo(month, null), monthName(column.index))}</Td>
              {shown.map((s) => {
                const value = months[column.index]?.values[s.key] ?? 0;
                return (
                  <Td key={s.key} className="whitespace-nowrap text-right tabular-nums">
                    {value === 0 ? t("none") : linked(linkTo(month, s.key), formatMoney(money(value)))}
                  </Td>
                );
              })}
              <Td className="whitespace-nowrap text-right font-medium tabular-nums">
                {formatMoney(money(column.total))}
              </Td>
            </tr>
          );
        })}
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
      hint={open?.hint}
    />
  );
}
