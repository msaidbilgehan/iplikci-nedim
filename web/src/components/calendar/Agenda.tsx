// What the next sixty days hold (F09): card due dates with the statement's debt and minimum, the regular and periodic
// payments a series expects, the salary and other regular income, card installments still to come, loan installments
// and non-bank bills not paid yet, each on its day with its kind, account and amount. Every item is an estimate from
// the past payments, labelled so; the detailed view says what each rests on. An item leads to its series, its bill
// or its account.

import { useTranslation } from "react-i18next";

import type { Calendar, CalendarItem, Destination, Labels, Money } from "../../api/types";
import { formatDay, formatFlow, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { useView } from "../Preferences";
import { Empty } from "../QueryState";
import { Flow } from "../ui/Money";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "block text-xs text-zinc-600 dark:text-zinc-300";
const SUBSCRIPTIONS = { screen: "subscription", id: "", query: {} } as const; // the list, no series open

function total(items: CalendarItem[], direction: CalendarItem["direction"]): Money {
  const minor = items.filter((i) => i.direction === direction).reduce((sum, i) => sum + i.amount.minor, 0);
  return { minor, currency: "TRY" };
}

/** Where an item leads: its series, the non-bank bills, or its account. */
function destination(item: CalendarItem): Destination {
  if (item.series) {
    return { screen: "subscription", id: item.series, query: {} };
  }
  if (item.kind === "bill") {
    return { screen: "invoices", id: "", query: {} };
  }
  return { screen: "account", id: item.account.id, query: {} };
}

/** The card's content: its loading and failure states stay with the card on the page. */
export function Agenda({ calendar, labels }: { calendar: Calendar; labels: Labels }) {
  const { t } = useTranslation("calendar");
  const span = { start: formatDay(calendar.today), end: formatDay(calendar.end) };
  if (calendar.items.length === 0) {
    return (
      <Empty title={t("agenda.empty")}>
        <p>{t("agenda.emptyText", span)}</p>
      </Empty>
    );
  }
  return <Items calendar={calendar} labels={labels} />;
}

function Items({ calendar, labels }: { calendar: Calendar; labels: Labels }) {
  const { t } = useTranslation("calendar");
  const detailed = useView().view === "detailed";
  const span = { start: formatDay(calendar.today), end: formatDay(calendar.end) };
  const out = calendar.items.filter((i) => i.direction === "out");
  const income = calendar.items.filter((i) => i.direction === "in");
  const first = calendar.items[0];
  const sentence = [
    out.length > 0 ? t("agenda.sayOut", { ...span, count: out.length, amount: formatMoney(total(out, "out")) }) : "",
    income.length > 0 ? t("agenda.sayIn", { count: income.length, amount: formatMoney(total(income, "in")) }) : "",
    first ? t("agenda.sayFirst", { day: first.day, title: first.title }) : "",
  ];
  return (
    <div className="flex flex-col gap-2">
      <Say next={{ link: SUBSCRIPTIONS, label: t("agenda.next") }}>{sentence.filter(Boolean).join(" ")}</Say>
      <p className="text-sm text-zinc-600 dark:text-zinc-300">{t("agenda.span", span)}</p>
      <Table>
        <caption className="sr-only">{t("agenda.caption")}</caption>
        <thead>
          <tr>
            <Th>{t("agenda.day")}</Th>
            <Th>{t("agenda.kind")}</Th>
            <Th>{t("agenda.what")}</Th>
            <Th>{t("agenda.account")}</Th>
            <Th className="text-right">{t("agenda.amount")}</Th>
          </tr>
        </thead>
        <tbody>
          {calendar.items.map((item, index) => (
            <tr key={`${item.day}-${item.kind}-${item.title}-${index}`}>
              <Td className="whitespace-nowrap">{formatDay(item.day)}</Td>
              <Td>{labelOf(labels, "PaymentKind", item.kind)}</Td>
              <Td>
                <ScreenLink link={destination(item)} className="font-medium">
                  {item.title}
                </ScreenLink>
                {detailed ? <span className={SMALL}>{item.basis}</span> : null}
              </Td>
              <Td>{item.account.label}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                <Flow value={item.amount} direction={item.direction} />
                {item.minimum ? (
                  <span className={SMALL}>{t("agenda.minimum", { amount: formatMoney(item.minimum) })}</span>
                ) : null}
              </Td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <Td colSpan={4} className="font-medium">
              {t("agenda.total")}
            </Td>
            <Td className="text-right tabular-nums">
              <span className="block">{t("agenda.in", { amount: formatFlow(total(calendar.items, "in"), "in") })}</span>
              <span className="block">
                {t("agenda.out", { amount: formatFlow(total(calendar.items, "out"), "out") })}
              </span>
            </Td>
          </tr>
        </tfoot>
      </Table>
    </div>
  );
}
