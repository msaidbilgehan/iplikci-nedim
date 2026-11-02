// The card purchases with installments still to come (F08): how many are left and what they come to (the amount the
// card's newest statement billed, once for each left), and the month the last one is billed, each leading to its row
// on the İşlemler screen.

import { useTranslation } from "react-i18next";

import type { Installment } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMonth } from "../../lib/format";
import { Detailed, Simple } from "../Preferences";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { monthOf } from "./series";
import { CARD, SMALL } from "./SeriesList";

const rowOf = (installment: Installment) => ({
  screen: "transaction" as const,
  id: installment.fingerprint,
  query: {},
});

export function InstallmentList({ installments }: { installments: readonly Installment[] }) {
  const { t } = useTranslation("subscriptions");
  const total = installments.reduce((sum, item) => sum + item.remaining.minor, 0);
  const currency = installments[0]?.remaining.currency ?? "TRY";
  const last = installments.map((item) => monthOf(item.last_day)).sort().at(-1) ?? "";
  return (
    <>
      <Say>{t("installments.say", { total: formatMoney({ minor: total, currency }), month: last })}</Say>
      <Simple>
        <ul aria-label={t("installments.caption")} className="grid gap-3 md:grid-cols-2">
          {installments.map((item) => (
            <li key={item.fingerprint || `${item.card.id}-${item.title}-${item.number}`} className={CARD}>
              <ScreenLink link={rowOf(item)} className="font-medium wrap-break-word">
                {item.title}
              </ScreenLink>
              <p className={SMALL}>{item.card.label}</p>
              <p>
                {[
                  t("installments.number", { number: item.number, count: item.count }),
                  t("installments.left", { left: item.left, amount: formatMoney(item.remaining) }),
                  t("installments.end", { month: formatMonth(monthOf(item.last_day)) }),
                ].join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("installments.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("table.purchase")}</Th>
              <Th>{t("table.card")}</Th>
              <Th>{t("table.installment")}</Th>
              <Th className="text-right">{t("table.installmentAmount")}</Th>
              <Th className="text-right">{t("table.left")}</Th>
              <Th className="text-right">{t("table.remaining")}</Th>
              <Th>{t("table.endMonth")}</Th>
            </tr>
          </thead>
          <tbody>
            {installments.map((item) => (
              <tr key={item.fingerprint || `${item.card.id}-${item.title}-${item.number}`}>
                <Td className="min-w-40">
                  <ScreenLink link={rowOf(item)} className="font-medium wrap-break-word">
                    {item.title}
                  </ScreenLink>
                </Td>
                <Td className="min-w-36">{item.card.label}</Td>
                <Td className="tabular-nums">
                  {item.number}/{item.count}
                </Td>
                <Td className="text-right whitespace-nowrap tabular-nums">{formatMoney(item.amount)}</Td>
                <Td className="text-right tabular-nums">{item.left}</Td>
                <Td className="text-right whitespace-nowrap tabular-nums">{formatMoney(item.remaining)}</Td>
                <Td className="whitespace-nowrap">{formatMonth(monthOf(item.last_day))}</Td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <Th scope="row" colSpan={5} className="border-b-0">
                {t("table.remainingTotal")}
              </Th>
              <Td className={cn("border-b-0 text-right font-semibold whitespace-nowrap tabular-nums")}>
                {formatMoney({ minor: total, currency })}
              </Td>
              <Td className="border-b-0" />
            </tr>
          </tfoot>
        </Table>
      </Detailed>
    </>
  );
}
