// What the rows a filter keeps add up to (F04): the money in, the money out and what is left between them, the
// spending net of refunds (purchases, refunds, interest and fees: what was spent, not what moved), and how many rows
// there are and how many count. The rows only a receipt or a notice shows yet and those the statements leave out, which
// count in no total, are named when there are any. The simple view says it in a sentence first. A month's saving's rows
// (the saving filter) also say what they set aside, the figure the Pano and the month-end page show: money coming into
// a savings account and money going out of a current one both add to it, so neither money in nor out is it.

import { useTranslation } from "react-i18next";

import type { Totals as TotalsData } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatFlow, formatMoney } from "../../lib/format";
import { INCOMING } from "../ui/Money";
import { Say } from "../ui/Say";
import { Term } from "../ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const TILE = "rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900";

interface TotalsProps {
  totals: TotalsData;
  saving?: boolean; // the rows are a saving's (the saving filter): say what they set aside
}

export function Totals({ totals, saving = false }: TotalsProps) {
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
  const net = totals.money_in.minor - totals.money_out.minor;
  const left = formatFlow({ minor: Math.abs(net), currency: totals.money_in.currency }, net >= 0 ? "in" : "out");
  return (
    <section aria-label={t("totals.label")} className="flex flex-col gap-2">
      <Say>
        {say} <span className="opacity-80">{t("hint")}</span>
      </Say>
      {saving && totals.count > 0 ? (
        <p className="text-base font-medium">
          {t(totals.saving.minor < 0 ? "totals.savingDrawn" : "totals.saving", {
            amount: formatMoney({ minor: Math.abs(totals.saving.minor), currency: totals.saving.currency }),
          })}
        </p>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className={TILE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("totals.moneyIn")}</dt>
          <dd className={cn("mt-0.5 text-lg font-semibold tabular-nums", totals.money_in.minor > 0 && INCOMING)}>
            {formatFlow(totals.money_in, "in")}
          </dd>
        </div>
        <div className={TILE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("totals.moneyOut")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatFlow(totals.money_out, "out")}</dd>
          <dd className={SMALL}>{t("totals.moneyOutNote")}</dd>
        </div>
        <div className={TILE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("totals.net")}</dt>
          <dd className={cn("mt-0.5 text-lg font-semibold tabular-nums", net > 0 && INCOMING)}>{left}</dd>
          <dd className={SMALL}>{t("totals.netNote")}</dd>
        </div>
        <div className={TILE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("totals.spent")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(totals.spent)}</dd>
          <dd className={SMALL}>{t("totals.spentNote")}</dd>
        </div>
      </dl>
      <p className={SMALL}>
        {t("totals.rows", { count: totals.count })} · {t("totals.counted", { count: totals.counted })}
        {totals.provisional > 0 ? (
          <>
            {" · "}
            {totals.provisional} <Term id="provisional">{t("totals.provisionalWord")}</Term>{" "}
            ({t("totals.provisionalNote")})
          </>
        ) : null}
        {totals.excluded > 0 ? (
          <>
            {" · "}
            {totals.excluded} <Term id="notOnStatement">{t("totals.excludedWord")}</Term>{" "}
            ({t("totals.excludedNote")})
          </>
        ) : null}
      </p>
    </section>
  );
}
