// "Düzenli ödemeler ve abonelikler" (the MVP report's recurring card), short: what the monthly payments still running
// come to, each leading to its panel on the Abonelikler screen, and the card purchases with installments left. The
// statuses are today's. Every filter but the period narrows the payments (features.md, "Süzgeçlerin kapsamı"); the
// installments follow the account filter alone.

import type { TFunction } from "i18next";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { CategoryRules, Subscriptions } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { Detailed } from "../Preferences";
import { InstallmentList } from "../subscriptions/InstallmentList";
import { isRunning } from "../subscriptions/series";
import { Card } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { keepsInstallment, keepsSeries } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const NUMBER = "text-right whitespace-nowrap tabular-nums";
const SUBSCRIPTIONS = { screen: "subscription", id: "", query: {} } as const;

interface RegularCardProps {
  found: Subscriptions;
  params: URLSearchParams;
  rules: CategoryRules | undefined; // a series' group, when a filter or the search needs it
}

export function RegularCard({ found, params, rules }: RegularCardProps) {
  const { t } = useTranslation("insights");
  const heading = useId();
  const running = found.series.filter((series) => series.listed && series.period === "month" && isRunning(series));
  const monthly = running
    .filter((series) => keepsSeries(params, series, rules))
    .sort((a, b) => b.amount.minor - a.amount.minor);
  const narrowed = monthly.length < running.length;
  const installments = found.installments.filter((item) => keepsInstallment(params, item));
  const currency = monthly[0]?.amount.currency ?? "TRY";
  const total = formatMoney({ minor: monthly.reduce((sum, series) => sum + series.amount.minor, 0), currency });
  const said =
    monthly.length > 0
      ? t(narrowed ? "regular.sayFiltered" : "regular.say", { count: monthly.length, total })
      : t(narrowed ? "regular.sayNoneFiltered" : "regular.sayNone");
  const hint = [t("regular.hint"), ignoredOf(params, t)].filter(Boolean).join(" ");
  return (
    <Card title={t("regular.title")}>
      <p className={`mb-3 ${SMALL}`}>{hint}</p>
      <Say next={{ link: SUBSCRIPTIONS, label: t("regular.next") }}>{said}</Say>
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
        ) : (
          <p className="text-sm">{said}</p>
        )}
      </Detailed>
      {installments.length > 0 ? (
        <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
          <h3 id={heading} className="text-base font-semibold">
            {t("regular.installments")}
          </h3>
          <p className={SMALL}>{t("regular.installmentsHint")}</p>
          <InstallmentList installments={installments} />
        </section>
      ) : null}
    </Card>
  );
}

/** What the card says of the filters it cannot follow when they are set: a row's tags and certainty. */
function ignoredOf(params: URLSearchParams, t: TFunction<"insights">): string {
  const tags = params.has("tag");
  const certainty = params.has("certainty");
  if (tags && certainty) {
    return t("regular.ignoresBoth");
  }
  if (tags) {
    return t("regular.ignoresTag");
  }
  return certainty ? t("regular.ignoresCertainty") : "";
}
