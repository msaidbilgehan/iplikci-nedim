// A month's totals by calendar month (F11; docs/domain/interpretation.md, "Ay sonu kapanışı"): the spending, the
// income where a bank list covers half the month, what went to people, to loans and to savings, and what is left. Only
// closed months are compared with each other — an open month lacks the days its statements have not reached — so the
// month before and the typical month (the median of up to six complete months before this one) stand beside a closed
// month only.

import type { TFunction } from "i18next";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { Money, MonthEndDetail, MonthEndTotals } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { Detailed, Simple } from "../Preferences";
import { Card, Facts } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { Term } from "../ui/Term";
import { SMALL } from "./parts";

type Item = "expense" | "income" | "people" | "debt" | "saving" | "fees" | "left";

const ITEMS: readonly Item[] = ["expense", "income", "people", "debt", "saving", "fees", "left"];
// Shown in the simple view only when there is something in them.
const WHEN_SOME: ReadonlySet<Item> = new Set(["people", "debt", "saving", "fees"]);

interface TotalsCardProps {
  detail: MonthEndDetail;
  previousClosed: boolean; // the month before is closed, as the months' list says
}

export function TotalsCard({ detail, previousClosed }: TotalsCardProps) {
  const { t } = useTranslation("monthEnd");
  const month = detail.month;
  const totals = month.totals;
  const closed = month.status === "closed";
  const previous = closed && previousClosed ? detail.previous : null;
  const typical = closed ? detail.typical : null;
  const shown = (value: Money | null) => (value ? formatMoney(value) : t("unknown"));
  const say =
    totals.income && totals.left
      ? t("totals.say", {
          expense: formatMoney(totals.expense),
          income: formatMoney(totals.income),
          left: formatMoney(totals.left),
        })
      : t("totals.sayNoIncome", { expense: formatMoney(totals.expense), note: month.income_note });

  // The income's note stands under the income, as on the month's own page: where it comes from, or why it may lack.
  const income = (value: Money | null) => (
    <>
      {shown(value)}
      {month.income_note ? <span className={`block whitespace-normal ${SMALL}`}>{month.income_note}</span> : null}
    </>
  );
  const notes: Array<[string, ReactNode]> = [];
  if (!closed) {
    notes.push(["open", t("totals.notClosed")]);
  } else if (!previousClosed) {
    notes.push(["previousOpen", t("totals.previousOpen")]);
  }
  if (previous) {
    notes.push(["against", t("totals.against", { change: changeOf(totals.expense, previous.expense, t) })]);
  }
  if (closed) {
    notes.push([
      "typical",
      typical ? (
        <>
          <Term id="typicalMonth">{t("totals.typical")}</Term>
          {t("totals.typicalLead", { count: detail.typical_months })}{" "}
          <Term id="completeMonth">{t("totals.complete")}</Term>{" "}
          {t("totals.typicalTail", { amount: formatMoney(typical) })}
        </>
      ) : (
        t("totals.noTypical")
      ),
    ]);
  }

  return (
    <Card title={t("totals.title")}>
      <Say>{say}</Say>
      <Simple>
        <Facts
          items={[
            ...ITEMS.filter((item) => !WHEN_SOME.has(item) || (totals[item]?.minor ?? 0) !== 0).map(
              (item): [string, ReactNode] => [
                t(`totals.${item}`),
                item === "income" ? income(totals.income) : shown(totals[item]),
              ],
            ),
            ...(detail.debt_end ? [[t("totals.debtEnd"), formatMoney(detail.debt_end)] as [string, ReactNode]] : []),
          ]}
        />
      </Simple>
      <Detailed>
        <TotalsTable
          totals={totals}
          previous={previous}
          typical={typical}
          debtEnd={detail.debt_end}
          incomeNote={month.income_note}
        />
      </Detailed>
      {notes.length > 0 ? (
        <ul className={`mt-3 flex flex-col gap-1 ${SMALL}`}>
          {notes.map(([key, note]) => (
            <li key={key}>{note}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

/** How this month's spending stands against the month before's: "1.234,56 TL fazla", "… az" or "aynı". */
function changeOf(now: Money, before: Money, t: TFunction<"monthEnd">): string {
  const difference = now.minor - before.minor;
  if (difference === 0) {
    return t("totals.same");
  }
  const amount = formatMoney({ minor: Math.abs(difference), currency: now.currency });
  return difference > 0 ? t("totals.more", { amount }) : t("totals.less", { amount });
}

interface TotalsTableProps {
  totals: MonthEndTotals;
  previous: MonthEndTotals | null; // only beside a closed month whose month before is closed
  typical: Money | null; // the typical month's spending, beside a closed month
  debtEnd: Money | null;
  incomeNote: string;
}

function TotalsTable({ totals, previous, typical, debtEnd, incomeNote }: TotalsTableProps) {
  const { t } = useTranslation("monthEnd");
  const cell = (value: Money | null | undefined) => (value ? formatMoney(value) : t("unknown"));
  const amount = "whitespace-nowrap text-right tabular-nums";
  return (
    <Table>
      <caption className="sr-only">{t("totals.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("totals.item")}</Th>
          <Th className="text-right">{t("totals.thisMonth")}</Th>
          {previous ? <Th className="text-right">{t("totals.previous")}</Th> : null}
          {typical ? <Th className="text-right">{t("totals.typical")}</Th> : null}
        </tr>
      </thead>
      <tbody>
        {ITEMS.map((item) => (
          <tr key={item}>
            <Td>{t(`totals.${item}`)}</Td>
            <Td className={amount}>
              {cell(totals[item])}
              {item === "income" && incomeNote ? (
                <span className={`block whitespace-normal ${SMALL}`}>{incomeNote}</span>
              ) : null}
            </Td>
            {previous ? <Td className={amount}>{cell(previous[item])}</Td> : null}
            {typical ? <Td className={amount}>{item === "expense" ? formatMoney(typical) : "—"}</Td> : null}
          </tr>
        ))}
        {debtEnd ? (
          <tr>
            <Td>{t("totals.debtEnd")}</Td>
            <Td className={amount}>{formatMoney(debtEnd)}</Td>
            {previous ? <Td className={amount}>—</Td> : null}
            {typical ? <Td className={amount}>—</Td> : null}
          </tr>
        ) : null}
      </tbody>
    </Table>
  );
}
