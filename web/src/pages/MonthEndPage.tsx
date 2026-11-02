// The Ay sonu screen (F11): the current month and the twelve before it with documents, the newest first, each with its
// status — an icon and its name, the five statuses explained beside them — and the closing in a sentence after the
// name, never repeating it (docs/domain/interpretation.md). The detailed view adds each month's totals. A month opens
// its page (/ay-sonu/:ay); the months' script-free pages download zipped.

import { useTranslation } from "react-i18next";

import { useLabels, useMonthEnds } from "../api/queries";
import type { Labels, MonthEnd, MonthEndList, MonthStatus } from "../api/types";
import { ExportLink, MonthStatusMark, SMALL } from "../components/monthEnd/parts";
import { useView } from "../components/Preferences";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { Say, ScreenLink } from "../components/ui/Say";
import { Table, Td, Th } from "../components/ui/Table";
import { cn } from "../lib/cn";
import { formatMoney, formatMonth } from "../lib/format";

// The statuses in the order a month passes through them, for their explanation.
const STATUSES: readonly MonthStatus[] = ["running", "waiting", "missing", "check", "closed"];

export default function MonthEndPage() {
  const { t } = useTranslation("monthEnd");
  const list = useMonthEnds();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("list.title")} description={t("list.description")} />
      {list.isPending ? <Loading /> : null}
      {list.isError ? <Failure error={list.error} onRetry={() => void list.refetch()} /> : null}
      {list.data ? <Months found={list.data} labels={labels} /> : null}
    </div>
  );
}

function Months({ found, labels }: { found: MonthEndList; labels: Labels }) {
  const { t } = useTranslation("monthEnd");
  const { view } = useView();
  const [newest] = found.months;
  if (!newest) {
    return <Empty title={t("list.empty")}>{t("list.emptyText")}</Empty>;
  }
  // What wants the user first: the newest month that ended and is not closed; else the month that runs.
  const open = found.months.filter((m) => m.status !== "closed" && m.status !== "running");
  const closed = found.months.filter((m) => m.status === "closed").length;
  const next = open[0] ?? found.months.find((m) => m.status === "running") ?? newest;
  const say =
    open.length > 0
      ? t("list.say", { closed, open: open.length })
      : t("list.sayAll", { month: formatMonth(next.month) });
  return (
    <div className={cn("grid items-start gap-4", view === "simple" && "lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]")}>
      <Card title={t("list.months")}>
        <Say next={{ link: next.link, label: t("list.next", { month: formatMonth(next.month) }) }}>{say}</Say>
        {view === "simple" ? <MonthList months={found.months} labels={labels} /> : null}
        {view === "detailed" ? <MonthTable months={found.months} labels={labels} /> : null}
      </Card>
      <div className="flex min-w-0 flex-col gap-4">
        <Card title={t("status.title")}>
          <dl className="flex flex-col gap-2 text-sm">
            {STATUSES.map((status) => (
              <div key={status}>
                <dt>
                  <MonthStatusMark status={status} labels={labels} />
                </dt>
                <dd className={`mt-0.5 ${SMALL}`}>{t(`status.about.${status}`)}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card title={t("export.title")}>
          <ExportLink kind={found.export} />
        </Card>
      </div>
    </div>
  );
}

const money = (value: MonthEnd["totals"]["income"], unknown: string) => (value ? formatMoney(value) : unknown);

function MonthList({ months, labels }: { months: readonly MonthEnd[]; labels: Labels }) {
  const { t } = useTranslation("monthEnd");
  return (
    <ol className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
      {months.map((m) => (
        <li key={m.month} className="flex flex-col gap-1 py-2 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <ScreenLink link={m.link} className="font-medium">
              {formatMonth(m.month)}
            </ScreenLink>
            <MonthStatusMark status={m.status} labels={labels} />
          </div>
          <p>{m.summary}</p>
          <p className={SMALL}>
            {t("list.figures", {
              expense: formatMoney(m.totals.expense),
              income: money(m.totals.income, t("unknown")),
              left: money(m.totals.left, t("unknown")),
            })}
          </p>
        </li>
      ))}
    </ol>
  );
}

function MonthTable({ months, labels }: { months: readonly MonthEnd[]; labels: Labels }) {
  const { t } = useTranslation("monthEnd");
  const amount = "whitespace-nowrap text-right tabular-nums";
  return (
    <Table>
      <caption className="sr-only">{t("list.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("list.month")}</Th>
          <Th>{t("list.statusName")}</Th>
          <Th className="text-right">{t("list.expense")}</Th>
          <Th className="text-right">{t("list.income")}</Th>
          <Th className="text-right">{t("list.left")}</Th>
          <Th className="text-right">{t("list.provisional")}</Th>
          <Th className="text-right">{t("list.unmatched")}</Th>
        </tr>
      </thead>
      <tbody>
        {months.map((m) => (
          <tr key={m.month}>
            <Td className="whitespace-nowrap">
              <ScreenLink link={m.link}>{formatMonth(m.month)}</ScreenLink>
            </Td>
            <Td className="min-w-56">
              <MonthStatusMark status={m.status} labels={labels} />
              <span className={`mt-1 block ${SMALL}`}>{m.summary}</span>
            </Td>
            <Td className={amount}>{formatMoney(m.totals.expense)}</Td>
            <Td className={amount}>
              {money(m.totals.income, t("unknown"))}
              {m.income_note ? (
                <span className={`block whitespace-normal ${SMALL}`}>
                  {t("list.incomeNote", { note: m.income_note })}
                </span>
              ) : null}
            </Td>
            <Td className={amount}>{money(m.totals.left, t("unknown"))}</Td>
            <Td className="text-right tabular-nums">{m.provisional}</Td>
            <Td className="text-right tabular-nums">{m.unmatched}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
