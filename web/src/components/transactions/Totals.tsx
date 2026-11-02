// What the rows a filter keeps add up to (F04): how many and how many count, the spending net of refunds, the money
// out and in, the rows only a receipt or a notice shows yet, and those the statements leave out, which count in no
// total. The simple view says it in a sentence first.

import { useTranslation } from "react-i18next";

import type { Totals as TotalsData } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { Say } from "../ui/Say";
import { Term } from "../ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

export function Totals({ totals }: { totals: TotalsData }) {
  const { t } = useTranslation("transactions");
  const say =
    totals.count === 0
      ? t("sayNone")
      : t("say", {
          count: totals.count,
          spent: formatMoney(totals.spent),
          moneyIn: formatMoney(totals.money_in),
          moneyOut: formatMoney(totals.money_out),
        });
  const figures: Array<[string, string, string]> = [
    ["count", t("totals.count"), String(totals.count)],
    ["spent", t("totals.spent"), formatMoney(totals.spent)],
    ["out", t("totals.moneyOut"), formatMoney(totals.money_out)],
    ["in", t("totals.moneyIn"), formatMoney(totals.money_in)],
  ];
  return (
    <section aria-label={t("totals.label")} className="flex flex-col gap-2">
      <Say>
        {say} <span className="text-zinc-600 dark:text-zinc-300">{t("hint")}</span>
      </Say>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {figures.map(([key, name, value]) => (
          <div key={key} className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900">
            <dt className="text-sm text-zinc-600 dark:text-zinc-300">{name}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums">{value}</dd>
            {key === "count" ? <dd className={SMALL}>{t("totals.counted", { count: totals.counted })}</dd> : null}
            {key === "spent" ? <dd className={SMALL}>{t("totals.spentNote")}</dd> : null}
          </div>
        ))}
        <div className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900">
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">
            <Term id="provisional">{t("totals.provisional")}</Term>
          </dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{totals.provisional}</dd>
          <dd className={SMALL}>{t("totals.provisionalNote")}</dd>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900">
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">
            <Term id="notOnStatement">{t("totals.excluded")}</Term>
          </dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{totals.excluded}</dd>
          <dd className={SMALL}>{t("totals.excludedNote")}</dd>
        </div>
      </dl>
    </section>
  );
}
