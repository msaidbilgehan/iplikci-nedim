// The net worth at the top of Döviz (F12): the assets less the debts in TL, the same in euros, dollars and grams of gold
// at the documents' newest rates, and the accounts left out of the total because nothing gives them a TL value. A unit
// without a rate says so; it is never shown as zero.

import { useTranslation } from "react-i18next";

import type { Holdings } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { Explain } from "../ui/Explain";
import { Money } from "../ui/Money";
import { currencyName } from "./currency";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const TOTAL = "min-w-36 flex-1 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900";

export function WorthSummary({ found }: { found: Holdings }) {
  const { t } = useTranslation("fx");
  const worth = found.worth;
  return (
    <section aria-label={t("summary.label")} className="flex flex-col gap-3">
      {/* Side by side while the amounts fit; on a phone each takes a row of its own. */}
      <dl className="flex flex-wrap gap-3 sm:max-w-xl">
        <div className={TOTAL}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("summary.total")}</dt>
          <dd className="mt-0.5 text-lg font-semibold">
            <Money value={worth.total} certainty={worth.certainty} />
          </dd>
        </div>
        {(
          [
            ["assets", worth.assets],
            ["debts", worth.debts],
          ] as const
        ).map(([key, value]) => (
          <div key={key} className={TOTAL}>
            <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t(`summary.${key}`)}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(value)}</dd>
          </div>
        ))}
      </dl>
      <div>
        <h2 className="text-sm font-medium">{t("inOther")}</h2>
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {worth.currencies.map((c) => (
            <div key={c.currency} className="contents">
              <dt className="text-zinc-600 dark:text-zinc-300">{currencyName(t, c.currency)}</dt>
              <dd className="min-w-0">
                {c.amount ? (
                  <span className="tabular-nums">{formatMoney(c.amount)}</span>
                ) : (
                  <span className="text-zinc-600 dark:text-zinc-300">{c.note || t("noValue")}</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </div>
      {worth.left_out.length > 0 ? (
        <div>
          <h2 className="text-sm font-medium">{t("leftOut")}</h2>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm">
            {worth.left_out.map((u) => (
              <li key={u.account.id}>
                {u.account.label}: <span className="text-zinc-600 dark:text-zinc-300">{u.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {worth.note ? (
        <Explain>
          <p>{worth.note}</p>
        </Explain>
      ) : null}
    </section>
  );
}
