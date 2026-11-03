// What the banks' rates cost, on Döviz (F12, "kur makası"; docs/domain/interpretation.md): the last 12 months' currency
// trades between own accounts and card purchases abroad, each against TCMB's rate of its day in the trade's direction
// (a buy against its forex selling rate, a sale against its buying rate), and what the difference came to in TL. A row
// without a TCMB rate for its day is in no total, and the note counts it. Every row leads to itself on İşlemler.

import { useTranslation } from "react-i18next";

import type { FxSpread, FxSpreadRow, Labels, Money } from "../../api/types";
import { formatDay, formatMoney, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { useView } from "../Preferences";
import { Empty } from "../QueryState";
import { Card } from "../ui/Card";
import { Explain } from "../ui/Explain";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { Term } from "../ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const TOTAL = "min-w-40 flex-1 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900";

const positive = (money: Money): Money => ({ ...money, minor: Math.abs(money.minor) });

export function CostCard({ found, labels }: { found: FxSpread; labels: Labels }) {
  const { t } = useTranslation("fx");
  const count = found.trades.length + found.purchases.length;
  const window = t("cost.window", { start: formatDay(found.start), end: formatDay(found.end) });
  if (count === 0) {
    return (
      <Card title={t("cost.title")}>
        <Empty title={t("cost.empty")}>
          <p>{found.note}</p>
        </Empty>
      </Card>
    );
  }
  return (
    <Card title={t("cost.title")}>
      <Say>
        {t(found.total.minor < 0 ? "cost.sayBetter" : "cost.say", { total: formatMoney(positive(found.total)), count })}
      </Say>
      <div className="flex flex-col gap-4">
        <section aria-label={t("cost.figures")}>
          <dl className="flex flex-wrap gap-3">
            <div className={TOTAL}>
              <dt className="text-sm text-zinc-600 dark:text-zinc-300">
                <Term id="fxSpread">{t("cost.total")}</Term>
              </dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(found.total)}</dd>
              <dd className={SMALL}>{t("cost.totalMeta", { window, count })}</dd>
            </div>
            {(
              [
                ["trades", found.trades_total, found.trades.length],
                ["purchases", found.purchases_total, found.purchases.length],
              ] as const
            ).map(([key, money, rows]) => (
              <div key={key} className={TOTAL}>
                <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t(`cost.${key}`)}</dt>
                <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(money)}</dd>
                <dd className={SMALL}>{t("cost.rows", { count: rows })}</dd>
              </div>
            ))}
          </dl>
        </section>
        {found.trades.length > 0 ? <CostTable group="trades" rows={found.trades} labels={labels} /> : null}
        {found.purchases.length > 0 ? <CostTable group="purchases" rows={found.purchases} labels={labels} /> : null}
        {found.note ? (
          <Explain>
            <p>{found.note}</p>
          </Explain>
        ) : null}
      </div>
    </Card>
  );
}

interface CostTableProps {
  group: "trades" | "purchases"; // a trade says which way it went; a card purchase abroad is always a buy
  rows: FxSpreadRow[];
  labels: Labels;
}

/** The rows of one group, by day: what the bank charged, TCMB's rate of the day, and the difference in TL. */
function CostTable({ group, rows, labels }: CostTableProps) {
  const { t } = useTranslation("fx");
  const detailed = useView().view === "detailed";
  return (
    <div>
      <h3 className="text-sm font-medium">{t(`cost.${group}Title`)}</h3>
      <Table>
        <caption className="sr-only">{t(`cost.${group}Caption`)}</caption>
        <thead>
          <tr>
            <Th>{t("cost.day")}</Th>
            <Th>{t("cost.row")}</Th>
            <Th className="whitespace-nowrap text-right">{t("cost.amount")}</Th>
            {detailed ? (
              <>
                <Th className="whitespace-nowrap text-right">{t("cost.tl")}</Th>
                <Th className="whitespace-nowrap text-right">{t("cost.bankRate")}</Th>
                <Th className="whitespace-nowrap text-right">{t("cost.tcmbRate")}</Th>
              </>
            ) : null}
            <Th className="whitespace-nowrap text-right">{t("cost.cost")}</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.fingerprint}>
              <Td className="whitespace-nowrap tabular-nums">{formatDay(row.day)}</Td>
              <Td className="min-w-44">
                <ScreenLink link={{ screen: "transaction", id: row.fingerprint, query: {} }} className="font-medium">
                  {row.title}
                </ScreenLink>
                <span className={`block ${SMALL}`}>
                  {group === "trades" ? `${labelOf(labels, "TradeSide", row.side)} · ` : ""}
                  {row.account.label}
                </span>
              </Td>
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(row.amount)}</Td>
              {detailed ? (
                <>
                  <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(row.tl)}</Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">
                    {t("assets.rateText", { rate: formatRate(row.rate) })}
                  </Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">
                    {t("assets.rateText", { rate: formatRate(row.tcmb_rate) })}
                    {row.tcmb_day !== row.day ? (
                      <span className={`block ${SMALL}`}>{t("cost.tcmbDay", { day: formatDay(row.tcmb_day) })}</span>
                    ) : null}
                  </Td>
                </>
              ) : null}
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(row.cost)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
