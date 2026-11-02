// The spending of the twelve months up to this one (F11), with the typical month in its sentence: the median of up to
// six complete months before this one, which the service computes; the chart computes no average of its own. (Drawn
// as a line, its label would sit on the newest month's total, which is usually close to it.) The months before the
// first with any spending have no documents yet, so they are left out rather than drawn as nothing spent. The highest
// and the lowest are named among the closed months only: a month still running, waiting for a statement, missing a
// list's days or with a statement to check may lack some of its spending, so such months are named apart.

import { useTranslation } from "react-i18next";

import { useMonthEnds } from "../../api/queries";
import type { MonthEndDetail, MonthStatus } from "../../api/types";
import { formatMoney, formatMonth } from "../../lib/format";
import { StackedBars } from "../charts/StackedBars";
import { Card } from "../ui/Card";
import { SMALL } from "./parts";

export function TrendCard({ detail }: { detail: MonthEndDetail }) {
  const { t } = useTranslation("monthEnd");
  const list = useMonthEnds();
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
  // The list of months knows the others' statuses; a month it does not reach (older than its twelve) counts as closed.
  const statuses = new Map<string, MonthStatus>((list.data?.months ?? []).map((m) => [m.month, m.status]));
  statuses.set(detail.month.month, detail.month.status);
  const ranked = months.filter((m) => (statuses.get(m.month) ?? "closed") === "closed");
  const open = months.filter((m) => !ranked.includes(m));
  const values = ranked.map((m) => m.expense.minor);
  const high = ranked[values.indexOf(Math.max(...values))];
  const low = ranked[values.indexOf(Math.min(...values))];
  const typical = detail.typical;
  const range = { from: formatMonth(from.month), to: formatMonth(to.month) };
  return (
    <Card title={t("trend.title")}>
      <StackedBars
        title={t("trend.chart")}
        summary={[
          high && low
            ? t("trend.say", {
                ...range,
                high: formatMoney(high.expense),
                highMonth: formatMonth(high.month),
                low: formatMoney(low.expense),
                lowMonth: formatMonth(low.month),
              })
            : t("trend.sayNoneClosed", range),
          typical ? t("trend.typicalSay", { amount: formatMoney(typical), count: detail.typical_months }) : "",
        ]
          .filter(Boolean)
          .join(" ")}
        series={[{ key: "expense", label: t("trend.series"), slot: 2 }]}
        months={months.map((m) => ({ month: m.month, values: { expense: m.expense.minor } }))}
      />
      {open.length > 0 ? (
        <p className={`mt-2 ${SMALL}`}>
          {t("trend.open", { count: open.length, months: open.map((m) => formatMonth(m.month)).join(", ") })}
        </p>
      ) : null}
    </Card>
  );
}
