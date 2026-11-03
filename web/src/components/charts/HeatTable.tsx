// The months' values as a heat table (the MVP report's heatTable): a row per month, the newest first, a column per
// series and the month's total, each cell shaded on the sequential ramp by its share of its column's highest month. In
// the dark theme the low values sit on the dark end, as the MVP had it. Every value is written, so the shade only
// follows it; a month the documents cover only partly is marked and counted in no average. The foot gives each
// column's total and its average over the whole months alone. A month and each of its values may lead to their rows,
// as the chart's columns and segments do.

import { useTranslation } from "react-i18next";

import type { Destination } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMonth } from "../../lib/format";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import type { StackSeries } from "./layout";
import { SLOT_BG } from "./palette";
import type { MonthValues } from "./StackedBars";

// Seven steps of the ramp, the light theme's then the dark one's, whole class names for Tailwind: from the fifth step
// on the light ramp's blue is dark enough for white text (AA), below it the text stays near black; the dark theme
// turns the ramp round.
const STEPS = [
  "bg-seq-100 text-zinc-950 dark:bg-seq-700 dark:text-white",
  "bg-seq-200 text-zinc-950 dark:bg-seq-600 dark:text-white",
  "bg-seq-300 text-zinc-950 dark:bg-seq-500 dark:text-white",
  "bg-seq-400 text-zinc-950 dark:bg-seq-400 dark:text-zinc-950",
  "bg-seq-500 text-white dark:bg-seq-300 dark:text-zinc-950",
  "bg-seq-600 text-white dark:bg-seq-200 dark:text-zinc-950",
  "bg-seq-700 text-white dark:bg-seq-100 dark:text-zinc-950",
] as const;

/** A value's shade: none for nothing or below zero, else one of seven steps by its share of the highest. */
export function heatOf(value: number, highest: number): string {
  if (!(value > 0) || !(highest > 0)) {
    return "";
  }
  return STEPS[Math.min(STEPS.length - 1, Math.round((value / highest) * (STEPS.length - 1)))] ?? "";
}

interface HeatTableProps {
  caption: string;
  series: readonly StackSeries[];
  months: readonly MonthValues[]; // oldest first, as the chart has them
  partial?: readonly string[]; // months not whole: marked, and in no average
  currency?: string;
  linkOf?: (month: string, series: string | null) => Destination | null; // a month's rows, or a series' of it
}

export function HeatTable({ caption, series, months, partial = [], currency = "TRY", linkOf }: HeatTableProps) {
  const { t } = useTranslation("charts");
  const money = (minor: number) => formatMoney({ minor, currency });
  const linked = (month: string, key: string | null, text: string) => {
    const link = linkOf?.(month, key) ?? null;
    return link ? <ScreenLink link={link}>{text}</ScreenLink> : text;
  };
  const shown = series.filter((s) => months.some((m) => (m.values[s.key] ?? 0) !== 0));
  const valueOf = (m: MonthValues, key: string) => m.values[key] ?? 0;
  const totalOf = (m: MonthValues) => shown.reduce((sum, s) => sum + valueOf(m, s.key), 0);
  const highest = (of: (m: MonthValues) => number) => Math.max(0, ...months.map(of));
  const whole = months.filter((m) => !partial.includes(m.month));
  const sum = (rows: readonly MonthValues[], of: (m: MonthValues) => number) => rows.reduce((s, m) => s + of(m), 0);
  const average = (of: (m: MonthValues) => number) => (whole.length ? Math.round(sum(whole, of) / whole.length) : 0);
  return (
    <div className="flex flex-col gap-2">
      <Table>
        <caption className="sr-only">{caption}</caption>
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
            <Th className="text-right">{t("total")}</Th>
          </tr>
        </thead>
        <tbody>
          {[...months].reverse().map((m) => (
            <tr key={m.month}>
              <Th scope="row" className="font-normal whitespace-nowrap text-zinc-900 dark:text-zinc-100">
                {linked(
                  m.month,
                  null,
                  partial.includes(m.month) ? t("partialMonth", { month: formatMonth(m.month) }) : formatMonth(m.month),
                )}
              </Th>
              {shown.map((s) => {
                const value = valueOf(m, s.key);
                return (
                  <Td
                    key={s.key}
                    className={cn(
                      "text-right whitespace-nowrap tabular-nums",
                      heatOf(value, highest((row) => valueOf(row, s.key))),
                    )}
                  >
                    {value === 0 ? "–" : linked(m.month, s.key, money(value))}
                  </Td>
                );
              })}
              <Td
                className={cn(
                  "text-right font-medium whitespace-nowrap tabular-nums",
                  heatOf(totalOf(m), highest(totalOf)),
                )}
              >
                {money(totalOf(m))}
              </Td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <Th scope="row">{t("total")}</Th>
            {shown.map((s) => (
              <Td key={s.key} className="text-right whitespace-nowrap tabular-nums">
                {money(sum(months, (m) => valueOf(m, s.key)))}
              </Td>
            ))}
            <Td className="text-right font-medium whitespace-nowrap tabular-nums">{money(sum(months, totalOf))}</Td>
          </tr>
          <tr>
            <Th scope="row" className="border-b-0">
              {whole.length ? t("heat.average", { count: whole.length }) : t("heat.noAverage")}
            </Th>
            {shown.map((s) => (
              <Td key={s.key} className="border-b-0 text-right whitespace-nowrap tabular-nums">
                {whole.length ? money(average((m) => valueOf(m, s.key))) : "–"}
              </Td>
            ))}
            <Td className="border-b-0 text-right font-medium whitespace-nowrap tabular-nums">
              {whole.length ? money(average(totalOf)) : "–"}
            </Td>
          </tr>
        </tfoot>
      </Table>
      <p className="flex flex-wrap items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300">
        <span>{t("heat.scaleLow")}</span>
        <span aria-hidden="true" className="inline-flex">
          {STEPS.map((step) => (
            <span key={step} className={cn("h-3 w-4", step.split(" ").filter((c) => c.includes("bg-")).join(" "))} />
          ))}
        </span>
        <span>{t("heat.scaleHigh")}</span>
      </p>
    </div>
  );
}
