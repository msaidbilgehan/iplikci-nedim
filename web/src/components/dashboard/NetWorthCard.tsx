// The dashboard's net worth (F06, F12): the balances "Şu an" shows and the cards' debts added up in TL, the assets and
// the debts apart, the same in euros, dollars and grams of gold at the documents' newest rates, and the accounts left
// out because nothing gives them a TL value. A worth without a rate is "belgelerde yok", never zero.

import { useTranslation } from "react-i18next";

import type { NetWorth } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { Detailed } from "../Preferences";
import { Money } from "../ui/Money";
import { Table, Td, Th } from "../ui/Table";
import { DashboardCard } from "./DashboardCard";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const CURRENCIES = ["EUR", "USD", "GR"] as const;

export function NetWorthCard({ worth }: { worth: NetWorth }) {
  const { t } = useTranslation("dashboard");
  const name = (currency: string) =>
    (CURRENCIES as readonly string[]).includes(currency)
      ? t(`netWorth.currency.${currency as (typeof CURRENCIES)[number]}`)
      : currency;
  return (
    <DashboardCard title={t("netWorth.title")} say={worth.say} next={{ link: worth.link, label: t("netWorth.next") }}>
      <p className="text-2xl font-semibold">
        <Money value={worth.total} certainty={worth.certainty} />
      </p>
      <p className={SMALL}>
        {t("netWorth.assets")} {formatMoney(worth.assets)} · {t("netWorth.debts")} {formatMoney(worth.debts)}
      </p>
      <h3 className="mt-3 text-sm font-medium">{t("netWorth.inOther")}</h3>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {worth.currencies.map((c) => (
          <div key={c.currency} className="contents">
            <dt className="text-zinc-600 dark:text-zinc-300">{name(c.currency)}</dt>
            <dd className="min-w-0">
              {c.amount ? (
                <>
                  <span className="tabular-nums">{formatMoney(c.amount)}</span>
                  {c.note ? <span className={`block ${SMALL}`}>{c.note}</span> : null}
                </>
              ) : (
                <span className="text-zinc-600 dark:text-zinc-300">{c.note || t("netWorth.noValue")}</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {worth.left_out.length > 0 ? (
        <>
          <h3 className="mt-3 text-sm font-medium">{t("netWorth.leftOut")}</h3>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm">
            {worth.left_out.map((u) => (
              <li key={u.account.id}>
                {u.account.label}: <span className="text-zinc-600 dark:text-zinc-300">{u.reason}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <Detailed>
        {worth.parts.length > 0 ? (
          <div className="mt-3">
            <Table>
              <caption className="sr-only">{t("netWorth.caption")}</caption>
              <thead>
                <tr>
                  <Th>{t("netWorth.account")}</Th>
                  <Th className="text-right">{t("netWorth.value")}</Th>
                </tr>
              </thead>
              <tbody>
                {worth.parts.map((part) => (
                  <tr key={part.account.id}>
                    <Td>{part.account.label}</Td>
                    <Td className="text-right">
                      <Money value={part.value} certainty={part.certainty} className="justify-end" />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ) : null}
        <p className={`mt-2 ${SMALL}`}>{worth.note}</p>
      </Detailed>
    </DashboardCard>
  );
}
