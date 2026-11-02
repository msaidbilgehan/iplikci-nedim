// "Gelir ve gider" (the MVP report's cash flow): the months an account list covers, the income rising above the axis
// and the spending hanging below it, each column's sum the month's net. Its table adds what went to people, to debt
// principal and to savings, and what was left after all of it; the averages count the whole months alone. Under it,
// the regular income the interpretation found, which no filter changes.

import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { FlowMonth, Insights, Labels, Spending } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { StackedBars } from "../charts/StackedBars";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const COLUMNS = ["income", "expense", "net", "people", "debt", "saving", "left"] as const;
type Column = (typeof COLUMNS)[number];

/** Each column's average over the whole months, in minor units; null without one. */
function averages(months: readonly FlowMonth[]): Record<Column, number> | null {
  const whole = months.filter((m) => !m.partial);
  if (whole.length === 0) {
    return null;
  }
  const of = (column: Column) => Math.round(whole.reduce((sum, m) => sum + m[column].minor, 0) / whole.length);
  return Object.fromEntries(COLUMNS.map((column) => [column, of(column)])) as Record<Column, number>;
}

interface FlowCardProps {
  found: Spending;
  insights: Insights | undefined; // the regular income under the months; none until it arrives
  labels: Labels;
}

export function FlowCard({ found, insights, labels }: FlowCardProps) {
  const { t } = useTranslation("insights");
  const months = found.flow;
  const first = months[0]?.month;
  const last = months.at(-1)?.month;
  const average = averages(months);
  const currency = months[0]?.income.currency ?? "TRY";
  const money = (minor: number) => formatMoney({ minor, currency });
  return (
    <Card title={t("flow.title")}>
      {first && last ? (
        <>
          <p className={`mb-3 ${SMALL}`}>
            {t("flow.hint", { count: months.length, from: formatMonth(first), to: formatMonth(last) })}
          </p>
          <StackedBars
            title={t("flow.chart")}
            summary={[
              t("flow.summary"),
              average
                ? t("flow.average", {
                    income: money(average.income),
                    expense: money(average.expense),
                    left: money(average.left),
                  })
                : "",
            ]
              .filter(Boolean)
              .join(" ")}
            series={[
              { key: "income", label: t("flow.income"), slot: 1 },
              { key: "expense", label: t("flow.expense"), slot: 8 },
            ]}
            months={months.map((m) => ({
              month: m.month,
              values: { income: m.income.minor, expense: -m.expense.minor },
            }))}
            partial={months.filter((m) => m.partial).map((m) => m.month)}
            totalLabel={t("flow.net")}
            currency={currency}
            table={<FlowTable months={months} average={average} currency={currency} />}
          />
        </>
      ) : (
        <p className="text-sm">{t("flow.none")}</p>
      )}
      {insights && insights.income.length > 0 ? <Income found={insights} labels={labels} /> : null}
    </Card>
  );
}

interface FlowTableProps {
  months: readonly FlowMonth[];
  average: Record<Column, number> | null;
  currency: string;
}

function FlowTable({ months, average, currency }: FlowTableProps) {
  const { t } = useTranslation("insights");
  const { t: tc } = useTranslation("charts");
  const money = (minor: number) => formatMoney({ minor, currency });
  const whole = months.filter((m) => !m.partial).length;
  const total = (column: Column) => months.reduce((sum, m) => sum + m[column].minor, 0);
  const NUMBER = "text-right whitespace-nowrap tabular-nums";
  return (
    <Table>
      <caption className="sr-only">{t("flow.chart")}</caption>
      <thead>
        <tr>
          <Th>{t("flow.month")}</Th>
          {COLUMNS.map((column) => (
            <Th key={column} className="text-right">
              {t(`flow.${column}`)}
            </Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {/* The newest month first, as the MVP's table. */}
        {[...months].reverse().map((m) => (
          <tr key={m.month}>
            <Th scope="row" className="font-normal whitespace-nowrap text-zinc-900 dark:text-zinc-100">
              {m.partial ? tc("partialMonth", { month: formatMonth(m.month) }) : formatMonth(m.month)}
            </Th>
            {COLUMNS.map((column) => (
              <Td key={column} className={cn(NUMBER, (column === "net" || column === "left") && "font-medium")}>
                {formatMoney(m[column])}
              </Td>
            ))}
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <Th scope="row" className="text-zinc-900 dark:text-zinc-100">
            {t("flow.total")}
          </Th>
          {COLUMNS.map((column) => (
            <Td key={column} className={cn(NUMBER, "font-medium")}>
              {money(total(column))}
            </Td>
          ))}
        </tr>
        <tr>
          <Th scope="row" className="border-b-0 text-zinc-900 dark:text-zinc-100">
            {average ? tc("heat.average", { count: whole }) : tc("heat.noAverage")}
          </Th>
          {COLUMNS.map((column) => (
            <Td key={column} className={cn(NUMBER, "border-b-0")}>
              {average ? money(average[column]) : "–"}
            </Td>
          ))}
        </tr>
      </tfoot>
    </Table>
  );
}

/** The regular income the interpretation found: what each brings in a month and when it last came. */
function Income({ found, labels }: { found: Insights; labels: Labels }) {
  const { t } = useTranslation("insights");
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {t("income.title")}
      </h3>
      <ul className="flex flex-col gap-1.5 text-sm">
        {found.income.map((item) => (
          <li key={item.name} className="flex flex-wrap items-center gap-2">
            <span>
              {t("income.item", { name: item.name, amount: formatMoney(item.monthly), day: formatDay(item.last) })}
            </span>
            {item.status === "active" ? null : (
              <Badge tone="neutral">{labelOf(labels, "SeriesStatus", item.status)}</Badge>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
