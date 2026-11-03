// The income that comes in a foreign currency, on Döviz (F12, "döviz geliri"; docs/domain/interpretation.md): for each
// currency, the last 12 months' rows with their TL value on their own day and at the current rate, the days the
// currency was changed into TL, and what a 5% move of the rate does to the monthly income — an average of complete
// months only, its sentence saying which and never folded away. Every row leads to itself on İşlemler.

import { useTranslation } from "react-i18next";

import type { CurrencyIncome, FxIncome } from "../../api/types";
import { formatDay, formatMoney, formatRate } from "../../lib/format";
import { rateOrigin } from "../../lib/rateOrigin";
import { useView } from "../Preferences";
import { Empty } from "../QueryState";
import { Card } from "../ui/Card";
import { Explain } from "../ui/Explain";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { currencyName } from "./currency";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const MUTED = "text-zinc-600 dark:text-zinc-300";
const FIGURE = "min-w-40 flex-1 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900";

export function IncomeCard({ found }: { found: FxIncome }) {
  const { t } = useTranslation("fx");
  if (found.currencies.length === 0) {
    return (
      <Card title={t("income.title")}>
        <Empty title={t("income.empty")}>
          <p>{found.note}</p>
        </Empty>
      </Card>
    );
  }
  const window = t("income.window", { start: formatDay(found.start), end: formatDay(found.end) });
  return (
    <Card title={t("income.title")}>
      <div className="flex flex-col gap-8">
        {found.currencies.map((c) => (
          <CurrencyPart key={c.currency} income={c} window={window} />
        ))}
      </div>
      {found.note ? <p className={`mt-4 ${SMALL}`}>{found.note}</p> : null}
    </Card>
  );
}

function CurrencyPart({ income: c, window }: { income: CurrencyIncome; window: string }) {
  const { t } = useTranslation("fx");
  const { t: tc } = useTranslation("common");
  const name = currencyName(t, c.currency);
  const s = c.sensitivity;
  return (
    <section aria-label={t("income.part", { currency: name })} className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold">{t("income.part", { currency: name })}</h3>
      <Say>
        {c.worth
          ? t("income.say", { received: formatMoney(c.received), worth: formatMoney(c.worth) })
          : t("income.sayNoRate", { received: formatMoney(c.received) })}
      </Say>
      <dl className="flex flex-wrap gap-3">
        <div className={FIGURE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("income.received")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(c.received)}</dd>
          <dd className={SMALL}>{t("income.rows", { window, count: c.rows.length })}</dd>
        </div>
        <div className={FIGURE}>
          <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("income.worth")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">
            {c.worth ? formatMoney(c.worth) : <span className={MUTED}>{t("income.noRate")}</span>}
          </dd>
          {c.rate ? (
            <dd className={SMALL}>
              {t("income.rate", {
                currency: c.currency,
                rate: formatRate(c.rate.rate),
                origin: rateOrigin(tc, c.rate.source, c.rate.day, "by"),
              })}
            </dd>
          ) : null}
        </div>
        {s ? (
          <div className={FIGURE}>
            <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("income.monthly")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(s.monthly)}</dd>
            {s.monthly_tl ? (
              <dd className={SMALL}>{t("income.monthlyTl", { value: formatMoney(s.monthly_tl) })}</dd>
            ) : null}
          </div>
        ) : null}
        {s?.change ? (
          <div className={FIGURE}>
            <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t("income.change")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums">
              {t("income.changeValue", { value: formatMoney(s.change) })}
            </dd>
            <dd className={SMALL}>{t("income.changeMeta", { currency: c.currency })}</dd>
          </div>
        ) : null}
      </dl>
      {/* The sentence that says which months the average is over is never folded (features.md). */}
      <p className="text-sm">{s ? s.say : t("income.noMonths")}</p>
      {c.rows.length > 0 ? <IncomeRows income={c} /> : null}
      <Sales income={c} />
      {c.note ? (
        <Explain>
          <p>{c.note}</p>
        </Explain>
      ) : null}
    </section>
  );
}

/** The window's income rows, the oldest first: each in the currency, in TL on its day, and at the current rate. */
function IncomeRows({ income: c }: { income: CurrencyIncome }) {
  const { t } = useTranslation("fx");
  const detailed = useView().view === "detailed";
  const name = currencyName(t, c.currency);
  return (
    <div>
      <h4 className="text-sm font-medium">{t("income.rowsTitle")}</h4>
      <Table>
        <caption className="sr-only">{t("income.rowsCaption", { currency: name })}</caption>
        <thead>
          <tr>
            <Th>{t("income.day")}</Th>
            <Th>{t("income.from")}</Th>
            <Th className="whitespace-nowrap text-right">{t("income.amount")}</Th>
            {detailed ? <Th className="whitespace-nowrap text-right">{t("income.counted")}</Th> : null}
            <Th className="whitespace-nowrap text-right">{t("income.now")}</Th>
          </tr>
        </thead>
        <tbody>
          {c.rows.map((row) => (
            <tr key={row.fingerprint}>
              <Td className="whitespace-nowrap tabular-nums">{formatDay(row.day)}</Td>
              <Td className="min-w-44">
                <ScreenLink link={{ screen: "transaction", id: row.fingerprint, query: {} }} className="font-medium">
                  {row.title}
                </ScreenLink>
                <span className={`block ${SMALL}`}>{row.account.label}</span>
              </Td>
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(row.amount)}</Td>
              {detailed ? (
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(row.counted)}</Td>
              ) : null}
              <Td className="whitespace-nowrap text-right tabular-nums">
                {row.worth ? formatMoney(row.worth) : <span className={MUTED}>{t("income.noRate")}</span>}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

/** The days the currency was changed into TL in the window, with the bank's rate: the "bozdurma" times. */
function Sales({ income: c }: { income: CurrencyIncome }) {
  const { t } = useTranslation("fx");
  const name = currencyName(t, c.currency);
  if (c.sold.length === 0) {
    return <p className="text-sm">{t("income.noSales", { currency: name })}</p>;
  }
  return (
    <div>
      <h4 className="text-sm font-medium">{t("income.salesTitle")}</h4>
      <Table>
        <caption className="sr-only">{t("income.salesCaption", { currency: name })}</caption>
        <thead>
          <tr>
            <Th>{t("income.day")}</Th>
            <Th>{t("income.into")}</Th>
            <Th className="whitespace-nowrap text-right">{t("income.amount")}</Th>
            <Th className="whitespace-nowrap text-right">{t("income.got")}</Th>
            <Th className="whitespace-nowrap text-right">{t("income.bankRate")}</Th>
          </tr>
        </thead>
        <tbody>
          {c.sold.map((sale) => (
            <tr key={sale.fingerprint}>
              <Td className="whitespace-nowrap tabular-nums">
                <ScreenLink link={{ screen: "transaction", id: sale.fingerprint, query: {} }}>
                  {formatDay(sale.day)}
                </ScreenLink>
              </Td>
              <Td className="min-w-40">{sale.account.label}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(sale.amount)}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(sale.tl)}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                {t("assets.rateText", { rate: formatRate(sale.rate) })}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
