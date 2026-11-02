// The regular income (F08): what each is expected to bring (the median of its last three), when it last came and when
// it comes next. The name opens its panel with the payments it rests on.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Labels, Series } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Badge } from "../ui/Badge";
import { Table, Td, Th } from "../ui/Table";
import { isLate, STATUS_TONES } from "./series";
import { CARD, NAME, type Opening, SMALL } from "./SeriesList";

interface IncomeListProps {
  income: readonly Series[];
  asOf: string;
  labels: Labels;
  opening: Opening;
}

export function IncomeList({ income, asOf, labels, opening }: IncomeListProps) {
  const { t } = useTranslation("subscriptions");
  const nextOf = (series: Series) => {
    if (!series.next_day) {
      return "";
    }
    return isLate(series, asOf)
      ? t("series.nextLate", { day: formatDay(series.next_day) })
      : t("series.nextDay", { day: formatDay(series.next_day) });
  };
  return (
    <>
      <Simple>
        <ul aria-label={t("income.caption")} className="grid gap-3 md:grid-cols-2">
          {income.map((series) => (
            <li key={series.id} className={CARD}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <Link to={opening.hrefOf(series.id)} className={NAME}>
                  {series.payee}
                </Link>
                {series.status === "active" ? null : (
                  <Badge tone={STATUS_TONES[series.status]}>{labelOf(labels, "SeriesStatus", series.status)}</Badge>
                )}
              </div>
              <p className={SMALL}>{[series.category, series.account.label].filter(Boolean).join(" · ")}</p>
              <ul className="flex flex-col gap-0.5">
                <li>
                  <span className="text-base font-semibold">
                    {t("series.expected", { amount: formatMoney(series.amount) })}
                  </span>
                  <span className={SMALL}> ({t("series.incomeMedian")})</span>
                </li>
                <li>
                  {t("series.lastIncome", { day: formatDay(series.last_day), amount: formatMoney(series.last_amount) })}
                </li>
                {series.next_day ? <li>{nextOf(series)}</li> : null}
              </ul>
              {series.note ? <p className={SMALL}>{series.note}</p> : null}
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("income.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("table.payer")}</Th>
              <Th>{t("table.account")}</Th>
              <Th className="text-right">{t("table.expected")}</Th>
              <Th>{t("table.lastIncome")}</Th>
              <Th>{t("table.nextIncome")}</Th>
              <Th>{t("table.payments")}</Th>
            </tr>
          </thead>
          <tbody>
            {income.map((series) => (
              <tr key={series.id}>
                <Td className="min-w-40">
                  <Link to={opening.hrefOf(series.id)} className={NAME}>
                    {series.payee}
                  </Link>
                  {series.status === "active" ? null : (
                    <span className="mt-1 block">
                      <Badge tone={STATUS_TONES[series.status]}>
                        {labelOf(labels, "SeriesStatus", series.status)}
                      </Badge>
                    </span>
                  )}
                </Td>
                <Td className="min-w-36">{series.account.label}</Td>
                <Td className="text-right whitespace-nowrap tabular-nums">
                  {formatMoney(series.amount)}
                  <span className={cn("block", SMALL)}>{t("series.incomeMedian")}</span>
                </Td>
                <Td className="whitespace-nowrap">
                  {formatDay(series.last_day)}
                  <span className={cn("block tabular-nums", SMALL)}>{formatMoney(series.last_amount)}</span>
                </Td>
                <Td className="whitespace-nowrap">
                  {series.next_day ? formatDay(series.next_day) : t("table.none")}
                  {isLate(series, asOf) ? <span className={cn("block", SMALL)}>{t("table.late")}</span> : null}
                </Td>
                <Td className="whitespace-nowrap">{t("series.payments", { count: series.payments.length })}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </>
  );
}
