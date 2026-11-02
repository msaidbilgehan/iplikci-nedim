// The spending of the twelve months up to this one (F11), with the typical month in its sentence: the median of up to
// six complete months before this one, which the service computes; the chart computes no average of its own. (Drawn
// as a line, its label would sit on the newest month's total, which is usually close to it.) The months before the
// first with any spending have no documents yet, so they are left out rather than drawn as nothing spent. A month
// still running is said to be incomplete.

import { useTranslation } from "react-i18next";

import type { MonthEndDetail } from "../../api/types";
import { formatMoney, formatMonth } from "../../lib/format";
import { StackedBars } from "../charts/StackedBars";
import { Card } from "../ui/Card";
import { SMALL } from "./parts";

export function TrendCard({ detail }: { detail: MonthEndDetail }) {
  const { t } = useTranslation("monthEnd");
  const first = detail.trend.findIndex((m) => m.expense.minor !== 0);
  const months = first === -1 ? [] : detail.trend.slice(first);
  const from = months[0];
  const to = months.at(-1);
  if (!from || !to) {
    return (
      <Card title={t("trend.title")}>
        <p className="text-sm">{t("trend.none")}</p>
      </Card>
    );
  }
  const running = detail.month.status === "running" && to.month === detail.month.month;
  // The highest and the lowest are of whole months: the running one has not had all its days.
  const ranked = running && months.length > 1 ? months.slice(0, -1) : months;
  const values = ranked.map((m) => m.expense.minor);
  const high = ranked[values.indexOf(Math.max(...values))] ?? to;
  const low = ranked[values.indexOf(Math.min(...values))] ?? to;
  const typical = detail.typical;
  return (
    <Card title={t("trend.title")}>
      <StackedBars
        title={t("trend.chart")}
        summary={[
          t("trend.say", {
            from: formatMonth(from.month),
            to: formatMonth(to.month),
            high: formatMoney(high.expense),
            highMonth: formatMonth(high.month),
            low: formatMoney(low.expense),
            lowMonth: formatMonth(low.month),
          }),
          typical ? t("trend.typicalSay", { amount: formatMoney(typical), count: detail.typical_months }) : "",
        ]
          .filter(Boolean)
          .join(" ")}
        series={[{ key: "expense", label: t("trend.series"), slot: 2 }]}
        months={months.map((m) => ({ month: m.month, values: { expense: m.expense.minor } }))}
      />
      {running ? <p className={`mt-2 ${SMALL}`}>{t("trend.running", { month: formatMonth(to.month) })}</p> : null}
    </Card>
  );
}
