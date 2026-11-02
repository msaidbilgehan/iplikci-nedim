// The rates on Döviz (F12, its Phase 6 part): the TL a unit cost on the documents' newest foreign currency row, each
// with its day and where it comes from, and, in the detailed view, every rate the documents print, the oldest first.
// Nothing is fetched from the network yet; a unit held without a rate is named.

import { useTranslation } from "react-i18next";

import type { CurrencyRates, FxRates, Labels } from "../../api/types";
import { formatDay, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Empty } from "../QueryState";
import { Detailed } from "../Preferences";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { currencyName } from "./currency";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

export function RatesCard({ found, labels }: { found: FxRates; labels: Labels }) {
  const { t } = useTranslation("fx");
  const first = found.currencies[0];
  const missing = found.missing.map((currency) => currencyName(t, currency)).join(", ");
  return (
    <Card title={t("rates.title")}>
      {first ? (
        <Say>
          {t("rates.say", {
            currency: currencyName(t, first.currency),
            day: formatDay(first.newest.day),
            rate: t("assets.rateText", { rate: formatRate(first.newest.rate) }),
          })}
        </Say>
      ) : null}
      {found.currencies.length === 0 ? (
        <Empty title={t("rates.empty")}>
          <p>{found.note || t("rates.emptyText")}</p>
        </Empty>
      ) : (
        <Table>
          <caption className="sr-only">{t("rates.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("rates.currency")}</Th>
              <Th className="text-right">{t("rates.newest")}</Th>
              <Th>{t("rates.day")}</Th>
              <Th>{t("rates.source")}</Th>
            </tr>
          </thead>
          <tbody>
            {found.currencies.map((c) => (
              <tr key={c.currency}>
                <Td>{currencyName(t, c.currency)}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">
                  {t("assets.rateText", { rate: formatRate(c.newest.rate) })}
                </Td>
                <Td className="whitespace-nowrap tabular-nums">{formatDay(c.newest.day)}</Td>
                <Td>{labelOf(labels, "RateSource", c.newest.source)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Detailed>
        {found.currencies.map((c) => (
          <History key={c.currency} rates={c} />
        ))}
      </Detailed>
      {missing ? <p className="mt-3 text-sm">{t("rates.missing", { currencies: missing })}</p> : null}
      {found.note && found.currencies.length > 0 ? <p className={`mt-2 ${SMALL}`}>{found.note}</p> : null}
    </Card>
  );
}

function History({ rates }: { rates: CurrencyRates }) {
  const { t } = useTranslation("fx");
  const name = currencyName(t, rates.currency);
  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium">{t("rates.history", { currency: name })}</h3>
      <Table>
        <caption className="sr-only">{t("rates.historyCaption", { currency: name })}</caption>
        <thead>
          <tr>
            <Th>{t("rates.day")}</Th>
            <Th className="text-right">{t("rates.rate")}</Th>
          </tr>
        </thead>
        <tbody>
          {rates.history.map((rate, index) => (
            <tr key={`${rate.day}-${index}`}>
              <Td className="whitespace-nowrap tabular-nums">{formatDay(rate.day)}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                {t("assets.rateText", { rate: formatRate(rate.rate) })}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
