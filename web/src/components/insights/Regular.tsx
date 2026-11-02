// "Düzenli ödemeler ve abonelikler" (the MVP report's recurring card), short: what the monthly payments still running
// come to, each leading to its panel on the Abonelikler screen, and the card purchases with installments left. The
// statuses are today's; no filter changes them.

import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { Subscriptions } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { Detailed } from "../Preferences";
import { InstallmentList } from "../subscriptions/InstallmentList";
import { isRunning } from "../subscriptions/series";
import { Card } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const NUMBER = "text-right whitespace-nowrap tabular-nums";
const SUBSCRIPTIONS = { screen: "subscription", id: "", query: {} } as const;

export function RegularCard({ found }: { found: Subscriptions }) {
  const { t } = useTranslation("insights");
  const heading = useId();
  const monthly = found.series
    .filter((series) => series.listed && series.period === "month" && isRunning(series))
    .sort((a, b) => b.amount.minor - a.amount.minor);
  const currency = monthly[0]?.amount.currency ?? "TRY";
  const total = formatMoney({ minor: monthly.reduce((sum, series) => sum + series.amount.minor, 0), currency });
  return (
    <Card title={t("regular.title")}>
      <p className={`mb-3 ${SMALL}`}>{t("regular.hint")}</p>
      <Say next={{ link: SUBSCRIPTIONS, label: t("regular.next") }}>
        {monthly.length > 0 ? t("regular.say", { count: monthly.length, total }) : t("regular.sayNone")}
      </Say>
      <Detailed>
        {monthly.length > 0 ? (
          <Table>
            <caption className="sr-only">{t("regular.caption")}</caption>
            <thead>
              <tr>
                <Th>{t("regular.payee")}</Th>
                <Th className="text-right">{t("regular.monthly")}</Th>
                <Th>{t("regular.last")}</Th>
                <Th>{t("regular.nextDay")}</Th>
              </tr>
            </thead>
            <tbody>
              {monthly.map((series) => (
                <tr key={series.id}>
                  <Td className="min-w-44">
                    <ScreenLink link={{ screen: "subscription", id: series.id, query: {} }} className="font-medium">
                      {series.payee}
                    </ScreenLink>
                    <span className={`block ${SMALL}`}>
                      {[series.category, series.account.label].filter(Boolean).join(" · ")}
                    </span>
                  </Td>
                  <Td className={NUMBER}>{formatMoney(series.amount)}</Td>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(series.last_day)}</Td>
                  <Td className="whitespace-nowrap tabular-nums">
                    {series.next_day ? formatDay(series.next_day) : "–"}
                  </Td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <Th scope="row" className="border-b-0 text-zinc-900 dark:text-zinc-100">
                  {t("regular.total")}
                </Th>
                <Td className={`${NUMBER} border-b-0 font-semibold`}>{total}</Td>
                <Td className="border-b-0" colSpan={2} />
              </tr>
            </tfoot>
          </Table>
        ) : null}
      </Detailed>
      {found.installments.length > 0 ? (
        <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
          <h3 id={heading} className="text-base font-semibold">
            {t("regular.installments")}
          </h3>
          <InstallmentList installments={found.installments} />
        </section>
      ) : null}
    </Card>
  );
}
