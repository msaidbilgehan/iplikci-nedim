// The payments and income the calendar expects in the days ahead (F05's "Yaklaşanlar", F06's payments due within a
// week): by day, each with its kind, account, amount and what the amount rests on. They are estimates, as the
// calendar's are: a regular payment's amount is its last one's or the median of its last three (F09).

import type { UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { CalendarItem, Labels, Now } from "../../api/types";
import { addDays, daysBetween, formatDay, formatFlow, formatMoney, formatWeekday } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

/** The items by their day, in the order the calendar gives them. */
function byDay(items: readonly CalendarItem[]): Array<[string, CalendarItem[]]> {
  const days = new Map<string, CalendarItem[]>();
  for (const item of items) {
    days.set(item.day, [...(days.get(item.day) ?? []), item]);
  }
  return [...days];
}

interface DueListProps {
  items: readonly CalendarItem[];
  today: string;
  labels: Labels;
}

/** The items under their days' headings: "Bugün", "Yarın", then the weekday and the date. */
export function DueList({ items, today, labels }: DueListProps) {
  const { t } = useTranslation("feed");
  const heading = (day: string) =>
    day === today
      ? `${t("upcoming.headingToday")} · ${formatDay(day)}`
      : day === addDays(today, 1)
        ? `${t("upcoming.headingTomorrow")} · ${formatDay(day)}`
        : formatWeekday(day);
  return (
    <ol className="flex flex-col gap-3">
      {byDay(items).map(([day, list]) => (
        <li key={day}>
          <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">{heading(day)}</h3>
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {list.map((item, index) => (
              <li
                key={`${item.series || item.title}-${index}`}
                className="flex flex-wrap items-start justify-between gap-x-4 gap-y-0.5 py-1.5"
              >
                <div className="min-w-0">
                  <p className="font-medium">{item.title}</p>
                  <p className={SMALL}>
                    {labelOf(labels, "PaymentKind", item.kind)} · {item.account.label}
                  </p>
                  <p className={SMALL}>{item.basis}</p>
                </div>
                <div className="text-right">
                  <span className="whitespace-nowrap font-medium tabular-nums">
                    {formatFlow(item.amount, item.direction)}
                  </span>
                  {item.minimum ? (
                    <p className={SMALL}>{t("upcoming.minimum", { amount: formatMoney(item.minimum) })}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

/** The same items as a table, for the detailed view. */
export function DueTable({ items, caption, labels }: { items: readonly CalendarItem[]; caption: string; labels: Labels }) {
  const { t } = useTranslation("feed");
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <Th>{t("upcoming.day")}</Th>
          <Th>{t("upcoming.item")}</Th>
          <Th>{t("upcoming.kind")}</Th>
          <Th>{t("upcoming.account")}</Th>
          <Th className="text-right">{t("upcoming.amount")}</Th>
          <Th>{t("upcoming.basis")}</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item, index) => (
          <tr key={`${item.day}-${item.series || item.title}-${index}`}>
            <Td className="whitespace-nowrap tabular-nums">{formatDay(item.day)}</Td>
            <Td className="font-medium">{item.title}</Td>
            <Td>{labelOf(labels, "PaymentKind", item.kind)}</Td>
            <Td>{item.account.label}</Td>
            <Td className="text-right tabular-nums">
              <span className="whitespace-nowrap">{formatFlow(item.amount, item.direction)}</span>
              {item.minimum ? (
                <span className={`block ${SMALL}`}>{t("upcoming.minimum", { amount: formatMoney(item.minimum) })}</span>
              ) : null}
            </Td>
            <Td className={SMALL}>{item.basis}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** How a sentence names a day ahead: "bugün", "yarın", or the day with its locative (feed.json, upcoming). */
export function whenKey(day: string, today: string): "today" | "tomorrow" | "on" {
  if (day === today) {
    return "today";
  }
  return day === addDays(today, 1) ? "tomorrow" : "on";
}

export function UpcomingCard({ now, labels }: { now: UseQueryResult<Now>; labels: Labels }) {
  const { t } = useTranslation("feed");
  return (
    <Card title={t("upcoming.title")}>
      {now.isPending ? <Loading /> : null}
      {now.isError ? <Failure error={now.error} onRetry={() => void now.refetch()} /> : null}
      {now.data ? <Upcoming now={now.data} labels={labels} /> : null}
    </Card>
  );
}

function Upcoming({ now, labels }: { now: Now; labels: Labels }) {
  const { t } = useTranslation("feed");
  const days = daysBetween(now.today, now.end) + 1;
  const items = now.upcoming;
  const first = items[0];
  if (!first) {
    return <p className="text-sm">{t("upcoming.empty", { days })}</p>;
  }
  const payments = items.filter((item) => item.direction === "out").length;
  const incomes = items.length - payments;
  const when = t(`upcoming.${whenKey(first.day, now.today)}`, { day: first.day });
  const values = { days, payments, incomes, when, title: first.title };
  const say =
    payments && incomes
      ? t("upcoming.sayBoth", values)
      : payments
        ? t("upcoming.sayPayments", values)
        : t("upcoming.sayIncomes", values);
  return (
    <>
      <Say next={{ link: CALENDAR, label: t("upcoming.next") }}>{say}</Say>
      <p className={`mb-2 ${SMALL}`}>{t("upcoming.estimate")}</p>
      <Simple>
        <DueList items={items} today={now.today} labels={labels} />
      </Simple>
      <Detailed>
        <DueTable items={items} caption={t("upcoming.caption", { days })} labels={labels} />
      </Detailed>
    </>
  );
}
