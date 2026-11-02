// The months of the spending (F10, the MVP report's "Aylık giderler" and "Gerekli ve gereksiz harcamalar"): stacked by
// group, then by necessity level, each group and level in its fixed colour slot; their table view is a heat table whose
// averages count the whole months alone. The level tiles narrow every card to one level, as the MVP's did.

import { useTranslation } from "react-i18next";

import type { Insights, Labels, Spending } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { HeatTable } from "../charts/HeatTable";
import { SLOT_BG } from "../charts/palette";
import { StackedBars } from "../charts/StackedBars";
import { Card } from "../ui/Card";
import { Habits } from "./Habits";
import { stackOf } from "./query";

function periodOf(found: Spending): { from: string; to: string } {
  return { from: formatMonth(found.period?.start ?? ""), to: formatMonth(found.period?.end ?? "") };
}

export function MonthlyCard({ found }: { found: Spending }) {
  const { t } = useTranslation("insights");
  const stack = stackOf(found.by_group, (key) => key);
  const { tiles } = found;
  const summary = [
    t("monthly.summary", periodOf(found)),
    tiles.average ? t("monthly.average", { amount: formatMoney(tiles.average), count: tiles.average_months }) : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Card title={t("monthly.title")}>
      <StackedBars
        title={t("monthly.chart")}
        summary={summary}
        series={stack.series}
        months={stack.months}
        partial={stack.partial}
        table={
          <HeatTable caption={t("monthly.chart")} series={stack.series} months={stack.months} partial={stack.partial} />
        }
      />
    </Card>
  );
}

interface NecessityCardProps {
  found: Spending;
  insights: Insights | undefined; // the habits under the levels; none until they arrive
  labels: Labels;
  chosen: readonly string[]; // the necessity levels the address narrows to
  onChoose: (level: string | null) => void; // one level alone, or every level again
}

export function NecessityCard({ found, insights, labels, chosen, onChoose }: NecessityCardProps) {
  const { t } = useTranslation("insights");
  const stack = stackOf(found.by_level, (key) => labelOf(labels, "Necessity", key));
  const whole = stack.months.filter((m) => !stack.partial.includes(m.month));
  const totalOf = (key: string) => stack.months.reduce((sum, m) => sum + (m.values[key] ?? 0), 0);
  const grand = stack.series.reduce((sum, s) => sum + totalOf(s.key), 0);
  return (
    <Card title={t("necessity.title")}>
      <p className="mb-3 text-xs text-zinc-600 dark:text-zinc-300">{t("necessity.hint")}</p>
      <div
        role="group"
        aria-label={t("necessity.tiles")}
        className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
      >
        {stack.series.map((level) => {
          const total = totalOf(level.key);
          const alone = chosen.length === 1 && chosen[0] === level.key;
          const average = whole.length
            ? Math.round(whole.reduce((sum, m) => sum + (m.values[level.key] ?? 0), 0) / whole.length)
            : null;
          const share = grand > 0 ? total / grand : 0;
          return (
            <button
              key={level.key}
              type="button"
              aria-pressed={alone}
              onClick={() => onChoose(alone ? null : level.key)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border p-3 text-left",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
                alone
                  ? "border-teal-700 bg-teal-50 dark:border-teal-400 dark:bg-teal-950"
                  : cn(
                      "border-zinc-200 bg-white hover:bg-zinc-50",
                      "dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800",
                    ),
              )}
            >
              <span className="inline-flex items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-200">
                <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[level.slot])} />
                {level.label}
              </span>
              <span className="text-lg font-semibold tabular-nums">
                {formatMoney({ minor: total, currency: "TRY" })}
              </span>
              <span className="text-xs text-zinc-600 dark:text-zinc-300">
                {average === null
                  ? t("necessity.tileShare", { share })
                  : t("necessity.tileMeta", { share, amount: formatMoney({ minor: average, currency: "TRY" }) })}
              </span>
              {/* What pressing does, after the visible words, which lead the button's name. */}
              <span className="sr-only">{alone ? t("necessity.all") : t("necessity.only")}</span>
            </button>
          );
        })}
      </div>
      <StackedBars
        title={t("necessity.chart")}
        summary={t("necessity.summary", periodOf(found))}
        series={stack.series}
        months={stack.months}
        partial={stack.partial}
        table={
          <HeatTable
            caption={t("necessity.chart")}
            series={stack.series}
            months={stack.months}
            partial={stack.partial}
          />
        }
      />
      {insights ? <Habits found={insights} labels={labels} /> : null}
    </Card>
  );
}
