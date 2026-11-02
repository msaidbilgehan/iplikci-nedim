// The payments and income the calendar expects in the days ahead (F05's "Yaklaşanlar", F06's payments due within a
// week): by day, each with its kind, account, amount and what the amount rests on. They are estimates, as the
// calendar's are: a regular payment's amount is its last one's or the median of its last three (F09).

import { useTranslation } from "react-i18next";

import type { CalendarItem, Labels } from "../api/types";
import { addDays, formatDay, formatMoney, formatWeekday } from "../lib/format";
import { labelOf } from "../lib/labels";
import { Flow } from "./ui/Money";
import { Table, Td, Th } from "./ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

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
  const { t } = useTranslation();
  const heading = (day: string) =>
    day === today
      ? `${t("due.today")} · ${formatDay(day)}`
      : day === addDays(today, 1)
        ? `${t("due.tomorrow")} · ${formatDay(day)}`
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
                  <Flow value={item.amount} direction={item.direction} className="font-medium" />
                  {item.minimum ? (
                    <p className={SMALL}>{t("due.minimum", { amount: formatMoney(item.minimum) })}</p>
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

interface DueTableProps {
  items: readonly CalendarItem[];
  caption: string;
  labels: Labels;
}

/** The same items as a table, for the detailed view. */
export function DueTable({ items, caption, labels }: DueTableProps) {
  const { t } = useTranslation();
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <Th>{t("due.day")}</Th>
          <Th>{t("due.item")}</Th>
          <Th>{t("due.kind")}</Th>
          <Th>{t("due.account")}</Th>
          <Th className="text-right">{t("due.amount")}</Th>
          <Th>{t("due.basis")}</Th>
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
              <Flow value={item.amount} direction={item.direction} />
              {item.minimum ? (
                <span className={`block ${SMALL}`}>{t("due.minimum", { amount: formatMoney(item.minimum) })}</span>
              ) : null}
            </Td>
            <Td className={SMALL}>{item.basis}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
