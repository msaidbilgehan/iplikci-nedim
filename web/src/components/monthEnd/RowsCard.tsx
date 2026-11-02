// A list of a month's rows (F11): its big one-off spending, the rows only receipts and notices show yet (counted,
// provisional), or the receipts' rows no statement covering their days shows (left out). Each row opens its detail at
// the side of the page, and from there its document.

import { useTranslation } from "react-i18next";

import type { Labels, Row } from "../../api/types";
import { formatMoney } from "../../lib/format";
import type { Ordering } from "../transactions/query";
import { RowsTable } from "../transactions/RowsTable";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { SMALL } from "./parts";

interface RowsCardProps {
  title: string;
  about?: string; // what the rows are, said in both views
  say?: string; // the simple view's sentence
  none: string;
  rows: readonly Row[];
  order: "day" | "amount"; // the oldest day first, or the largest amount first
  labels: Labels;
  rowHref: (fingerprint: string) => string;
}

const ORDERINGS: Readonly<Record<RowsCardProps["order"], Ordering>> = {
  day: { sort: "day", order: "asc" },
  amount: { sort: "amount", order: "desc" },
};

export function RowsCard({ title, about, say, none, rows, order, labels, rowHref }: RowsCardProps) {
  const sorted = [...rows].sort((a, b) =>
    order === "day" ? a.day.localeCompare(b.day) : b.amount.minor - a.amount.minor || a.day.localeCompare(b.day),
  );
  return (
    <Card title={title}>
      {rows.length > 0 && say ? <Say>{say}</Say> : null}
      {about ? <p className={`mb-3 ${SMALL}`}>{about}</p> : null}
      {rows.length === 0 ? (
        <p className="text-sm">{none}</p>
      ) : (
        <RowsTable rows={sorted} labels={labels} ordering={ORDERINGS[order]} rowHref={rowHref} />
      )}
    </Card>
  );
}

/** The big purchases' sentence: how many and, when they are in one currency, their total. */
export function useBigSay(rows: readonly Row[]): string {
  const { t } = useTranslation("monthEnd");
  const currency = rows[0]?.amount.currency;
  const same = currency !== undefined && rows.every((row) => row.amount.currency === currency);
  if (!same) {
    return t("rows.bigSayCount", { count: rows.length });
  }
  const total = rows.reduce((sum, row) => sum + row.amount.minor, 0);
  return t("rows.bigSay", { count: rows.length, total: formatMoney({ minor: total, currency }) });
}
