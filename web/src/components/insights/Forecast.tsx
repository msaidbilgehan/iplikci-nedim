// "Önümüzdeki aylar" (the MVP report's forecast): the next three months' spending in three parts — the regular
// payments still running at their monthly amount, the installments still due, the rest by necessity level at the
// median of the base months — beside the last six months, and what the regular income leaves after it, the savings
// and the typical money to people and debt. Every filter but the period narrows it; it is an estimate and says so. A
// past month, or one level of it, leads to its rows; the months ahead have none.

import { useTranslation } from "react-i18next";

import type { ForecastLine, ForecastPart, Labels, MonthTable, SpendingForecast } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { NECESSITY_SLOTS, SLOT_BG, slotOf } from "../charts/palette";
import { StackedBars } from "../charts/StackedBars";
import { Detailed } from "../Preferences";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Stat } from "../ui/Stat";
import { Table, Td, Th } from "../ui/Table";
import { monthRowsOf, stackOf, withRange } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const NUMBER = "text-right whitespace-nowrap tabular-nums";
const PARTS: readonly ForecastPart[] = ["regular", "installments", "variable"];
const LIRA = 100;
const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

/** A level's amount in a month table's row, by the level's code; 0 when the table has no such slice. */
function levelIn(table: MonthTable, index: number, level: string): number {
  const slice = table.slices.findIndex((s) => s.key === level);
  return slice < 0 ? 0 : (table.months[index]?.values[slice]?.minor ?? 0);
}

interface ForecastCardProps {
  found: SpendingForecast | null;
  labels: Labels;
  params: URLSearchParams; // the screen's filters: every one but the period narrows the forecast
}

interface ForecastPartProps {
  found: SpendingForecast;
  labels: Labels;
}

export function ForecastCard({ found, labels, params }: ForecastCardProps) {
  const { t } = useTranslation("insights");
  const title = t("forecast.title");
  if (!found || found.months.length === 0) {
    return (
      <Card title={title}>
        <p className="text-sm">{t("forecast.none")}</p>
      </Card>
    );
  }
  const [next] = found.months;
  const currency = found.totals[0]?.currency ?? "TRY";
  const money = (minor: number) => formatMoney({ minor, currency });
  const first = found.totals[0]?.minor ?? 0;
  const level = (code: string) => money(levelIn(found.by_level, 0, code));
  const hasIncome = found.income.minor > 0;
  return (
    <Card title={title} action={<Badge tone="neutral">{t("forecast.label")}</Badge>}>
      <p className={`mb-3 ${SMALL}`}>
        {t("forecast.hint", { from: formatMonth(found.base[0] ?? ""), to: formatMonth(found.base.at(-1) ?? "") })}
      </p>
      <Say next={{ link: CALENDAR, label: t("forecast.calendar") }}>
        {found.left
          ? t("forecast.say", { month: formatMonth(next ?? ""), amount: money(first), left: formatMoney(found.left) })
          : t("forecast.sayNoIncome", { month: formatMonth(next ?? ""), amount: money(first) })}
      </Say>
      <section aria-label={t("forecast.tiles")} className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label={t("forecast.next", { month: formatMonth(next ?? "") })}
          value={money(first)}
          meta={t("forecast.nextMeta", {
            required: level("required"),
            optional: level("optional"),
            unnecessary: level("unnecessary"),
          })}
        />
        <Stat
          label={t("forecast.three", { count: found.months.length })}
          value={money(found.totals.reduce((sum, m) => sum + m.minor, 0))}
          meta={t("forecast.threeMeta", {
            from: formatMonth(found.months[0] ?? ""),
            to: formatMonth(found.months.at(-1) ?? ""),
          })}
        />
        <Stat
          label={t("forecast.income")}
          value={hasIncome ? formatMoney(found.income) : "—"}
          meta={hasIncome && found.income_names.length ? found.income_names.join(", ") : t("forecast.incomeNone")}
        />
        <Stat
          label={t("forecast.left", { month: formatMonth(next ?? "") })}
          value={found.left ? formatMoney(found.left) : "—"}
          meta={
            found.left
              ? [
                  t("forecast.leftMeta"),
                  found.saving.minor >= LIRA ? t("forecast.leftSaving", { amount: formatMoney(found.saving) }) : "",
                  found.other.minor >= LIRA ? t("forecast.leftOther", { amount: formatMoney(found.other) }) : "",
                ]
                  .filter(Boolean)
                  .join(" − ")
              : t("forecast.leftNone")
          }
        />
      </section>
      <ForecastChart found={found} labels={labels} params={params} />
      <Detailed>
        <div className="mt-4">
          <ForecastTable found={found} labels={labels} />
        </div>
      </Detailed>
    </Card>
  );
}

/** The last six months and the three ahead, stacked by necessity level; the months ahead lighter, after a line. */
function ForecastChart({ found, labels, params }: ForecastPartProps & { params: URLSearchParams }) {
  const { t } = useTranslation("insights");
  const first = found.months[0] ?? ""; // the first month ahead
  // The past months count every filter but the period, as the forecast does.
  const anyPeriod = withRange(params, null);
  const name = (code: string) => labelOf(labels, "Necessity", code);
  const actual = stackOf(found.actual, name);
  const ahead = stackOf(found.by_level, name);
  // Both tables keep only the levels with an amount: the chart takes every level either has, in the levels' order.
  const series = [...actual.series, ...ahead.series.filter((s) => !actual.series.some((a) => a.key === s.key))].sort(
    (a, b) => Object.keys(NECESSITY_SLOTS).indexOf(a.key) - Object.keys(NECESSITY_SLOTS).indexOf(b.key),
  );
  return (
    <StackedBars
      title={t("forecast.chart")}
      summary={t("forecast.summary")}
      series={series}
      months={[...actual.months, ...ahead.months]}
      partial={actual.partial}
      {...(found.months[0] ? { forecastFrom: found.months[0] } : {})}
      currency={found.totals[0]?.currency ?? "TRY"}
      open={{
        link: ({ month, series }) =>
          first && month >= first ? null : monthRowsOf(anyPeriod, month, series ? { necessity: series } : {}),
        hint: t("forecast.openHint"),
        what: (s) =>
          s ? t("necessity.openLevel", { level: s.label.toLocaleLowerCase("tr-TR") }) : t("necessity.openMonth"),
      }}
    />
  );
}

/** The lines of the months ahead by part, each part's sums on its heading row; below, what the income leaves. */
function ForecastTable({ found, labels }: ForecastPartProps) {
  const { t } = useTranslation("insights");
  const currency = found.totals[0]?.currency ?? "TRY";
  const money = (minor: number) => formatMoney({ minor, currency });
  const income = found.income.minor;
  const saving = found.saving.minor;
  const other = found.other.minor;
  const rows: Array<{ key: string; label: string; values: number[] }> = [
    { key: "totals", label: t("forecast.totals"), values: found.totals.map((m) => m.minor) },
  ];
  if (income > 0) {
    rows.push({ key: "income", label: t("forecast.expected"), values: found.months.map(() => income) });
    if (saving >= LIRA) {
      const names = found.saving_names.join(", ");
      rows.push({ key: "saving", label: t("forecast.savingRow", { names }), values: found.months.map(() => saving) });
    }
    rows.push({
      key: "after",
      label: saving >= LIRA ? t("forecast.afterSaving") : t("forecast.afterExpense"),
      values: found.totals.map((m) => income - m.minor - (saving >= LIRA ? saving : 0)),
    });
    if (other >= LIRA) {
      rows.push({ key: "other", label: t("forecast.otherRow"), values: found.months.map(() => other) });
      rows.push({
        key: "left",
        label: t("forecast.leftRow"),
        values: found.totals.map((m) => income - m.minor - (saving >= LIRA ? saving : 0) - other),
      });
    }
  }
  return (
    <Table>
      <caption className="sr-only">{t("forecast.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("forecast.line")}</Th>
          <Th>{t("forecast.level")}</Th>
          {found.months.map((month) => (
            <Th key={month} className="text-right whitespace-nowrap">
              {formatMonth(month)}
            </Th>
          ))}
        </tr>
      </thead>
      {PARTS.map((part) => {
        const lines = found.lines
          .map((line, index) => ({ line, index }))
          .filter(({ line }) => line.part === part)
          .sort((a, b) => (b.line.amounts[0]?.minor ?? 0) - (a.line.amounts[0]?.minor ?? 0));
        if (lines.length === 0) {
          return null;
        }
        const label = labelOf(labels, "ForecastPart", part);
        return (
          <tbody key={part}>
            <tr className="bg-zinc-50 dark:bg-zinc-800/60">
              <Th scope="rowgroup" colSpan={2} className="text-zinc-900 dark:text-zinc-100">
                {part === "variable" ? `${label} (${t("forecast.median", { count: found.base.length })})` : label}
              </Th>
              {found.months.map((month, i) => (
                <Td key={month} className={cn(NUMBER, "font-medium")}>
                  {money(lines.reduce((sum, { line }) => sum + (line.amounts[i]?.minor ?? 0), 0))}
                </Td>
              ))}
            </tr>
            {lines.map(({ line, index }) => (
              // Two series may share a payee (two Migros days): a line is its place in the forecast.
              <LineRow key={`${part}:${index}`} line={line} labels={labels} months={found.months} />
            ))}
          </tbody>
        );
      })}
      <tfoot>
        {rows.map((row, i) => (
          <tr key={row.key}>
            <Th
              scope="row"
              colSpan={2}
              className={cn("text-zinc-900 dark:text-zinc-100", i === rows.length - 1 && "border-b-0")}
            >
              {row.label}
            </Th>
            {row.values.map((value, k) => (
              <Td
                key={found.months[k] ?? k}
                className={cn(NUMBER, "font-medium", i === rows.length - 1 && "border-b-0 font-semibold")}
              >
                {money(value)}
              </Td>
            ))}
          </tr>
        ))}
      </tfoot>
    </Table>
  );
}

function LineRow({ line, labels, months }: { line: ForecastLine; labels: Labels; months: readonly string[] }) {
  const swatch = line.group ? slotOf(line.slot) : NECESSITY_SLOTS[line.necessity];
  return (
    <tr>
      <Td className="min-w-48">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[swatch])} />
          {line.link ? (
            <ScreenLink link={line.link} className="font-medium">
              {line.label}
            </ScreenLink>
          ) : (
            <span className="font-medium">{line.label}</span>
          )}
        </span>
        {line.note ? <span className={`mt-0.5 block ${SMALL}`}>{line.note}</span> : null}
      </Td>
      <Td className="whitespace-nowrap">
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[NECESSITY_SLOTS[line.necessity]])}
          />
          {labelOf(labels, "Necessity", line.necessity)}
        </span>
      </Td>
      {months.map((month, i) => {
        const value = line.amounts[i];
        return (
          <Td key={month} className={NUMBER}>
            {value && value.minor !== 0 ? formatMoney(value) : "–"}
          </Td>
        );
      })}
    </tr>
  );
}
