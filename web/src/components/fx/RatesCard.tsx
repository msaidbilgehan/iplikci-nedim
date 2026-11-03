// The rates on Döviz (F12, architecture §15): each currency's newest TL rate, its day and where it comes from — TCMB's
// bulletin, ECB's reference rate on the days TCMB could not be reached, else the newest a bank's document prints — with
// the two sides a provider gives (assets are valued at buying, debts at selling); the providers' recent days as a chart
// with its table; and, in the detailed view, every rate the documents print. A unit held without a rate is named.

import { useTranslation } from "react-i18next";

import type { CurrencyRates, FxRate, FxRates, Labels } from "../../api/types";
import { formatDay, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { rateOrigin } from "../../lib/rateOrigin";
import { LineChart, type ValueFormat } from "../charts/LineChart";
import { Detailed } from "../Preferences";
import { Empty } from "../QueryState";
import { Card } from "../ui/Card";
import { Explain } from "../ui/Explain";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { currencyName, currencySlot } from "./currency";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const SYSTEM = { screen: "system", id: "", query: {} } as const;
// A rate on the chart's axis to two decimals; in its tip and its table as the provider prints it, to four.
const RATE_FORMAT: ValueFormat = {
  tick: (value) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value),
  value: (value) =>
    `${new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(value)} TL`,
};

export function RatesCard({ found, labels }: { found: FxRates; labels: Labels }) {
  const { t } = useTranslation("fx");
  const { t: tc } = useTranslation("common");
  const first = found.currencies[0];
  const missing = found.missing.map((currency) => currencyName(t, currency)).join(", ");
  return (
    <Card title={t("rates.title")}>
      {first ? (
        <Say next={{ link: SYSTEM, label: t("rates.next") }}>
          {t("rates.say", {
            origin: rateOrigin(tc, first.newest.source, first.newest.day, "by"),
            currency: first.currency,
            rate: formatRate(first.newest.rate),
          })}
        </Say>
      ) : null}
      {found.currencies.length === 0 ? (
        <Empty title={t("rates.empty")}>
          <p>{found.note || t("rates.emptyText")}</p>
        </Empty>
      ) : (
        <div className="flex flex-col gap-6">
          <Newest currencies={found.currencies} labels={labels} />
          {found.currencies.map((c) => (
            <Recent key={c.currency} rates={c} labels={labels} />
          ))}
          <Detailed>
            {found.currencies.map((c) => (
              <Printed key={c.currency} rates={c} />
            ))}
          </Detailed>
        </div>
      )}
      {missing ? <p className="mt-3 text-sm">{t("rates.missing", { currencies: missing })}</p> : null}
      {found.note && found.currencies.length > 0 ? (
        <Explain className="mt-2">
          <p>{found.note}</p>
        </Explain>
      ) : null}
    </Card>
  );
}

/** The newest rate of every currency: a provider's two sides, or the one rate a document's trade was made at. */
function Newest({ currencies, labels }: { currencies: CurrencyRates[]; labels: Labels }) {
  const { t } = useTranslation("fx");
  return (
    <Table>
      <caption className="sr-only">{t("rates.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("rates.currency")}</Th>
          <Th className="whitespace-nowrap text-right">{t("rates.buying")}</Th>
          <Th className="whitespace-nowrap text-right">{t("rates.selling")}</Th>
          <Th>{t("rates.day")}</Th>
          <Th>{t("rates.source")}</Th>
        </tr>
      </thead>
      <tbody>
        {currencies.map((c) => (
          <tr key={c.currency}>
            <Td>{currencyName(t, c.currency)}</Td>
            <Sides rate={c.newest} />
            <Td className="whitespace-nowrap tabular-nums">{formatDay(c.newest.day)}</Td>
            <Td>{labelOf(labels, "RateSource", c.newest.source)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Sides({ rate }: { rate: FxRate }) {
  const { t } = useTranslation("fx");
  const cell = "whitespace-nowrap text-right tabular-nums";
  if (rate.buying && rate.selling) {
    return (
      <>
        <Td className={cell}>{t("assets.rateText", { rate: formatRate(rate.buying) })}</Td>
        <Td className={cell}>{t("assets.rateText", { rate: formatRate(rate.selling) })}</Td>
      </>
    );
  }
  return (
    <Td colSpan={2} className={cell}>
      {t("assets.rateText", { rate: formatRate(rate.rate) })}
      <span className={`block ${SMALL}`}>{t("rates.oneRate")}</span>
    </Td>
  );
}

/** The providers' recent days of one currency, at the buying rate the assets are valued at. */
function Recent({ rates, labels }: { rates: CurrencyRates; labels: Labels }) {
  const { t } = useTranslation("fx");
  const quotes = rates.history.filter((rate) => rate.source !== "document");
  const [start, end] = [quotes[0], quotes[quotes.length - 1]];
  if (!start || !end || quotes.length < 2) {
    return null;
  }
  const name = currencyName(t, rates.currency);
  const sources = [...new Set(quotes.map((rate) => labelOf(labels, "RateSource", rate.source)))].join(", ");
  return (
    <LineChart
      title={t("rates.chart", { currency: name })}
      summary={t("rates.chartSummary", {
        currency: rates.currency,
        start: formatDay(start.day),
        first: formatRate(start.buying ?? start.rate),
        end: formatDay(end.day),
        last: formatRate(end.buying ?? end.rate),
        sources,
      })}
      series={[
        {
          key: rates.currency,
          label: t("rates.series", { currency: name }),
          slot: currencySlot(rates.currency),
          points: quotes.map((rate) => ({ day: rate.day, value: Number(rate.buying ?? rate.rate) })),
        },
      ]}
      format={RATE_FORMAT}
      height={220}
    />
  );
}

/** The rates the documents print for one currency, the oldest first: each a trade a bank made. */
function Printed({ rates }: { rates: CurrencyRates }) {
  const { t } = useTranslation("fx");
  const printed = rates.history.filter((rate) => rate.source === "document");
  if (printed.length === 0) {
    return null;
  }
  const name = currencyName(t, rates.currency);
  return (
    <div className="mt-2">
      <h3 className="text-sm font-medium">{t("rates.history", { currency: name })}</h3>
      <Table>
        <caption className="sr-only">{t("rates.historyCaption", { currency: name })}</caption>
        <thead>
          <tr>
            <Th>{t("rates.documentDay")}</Th>
            <Th className="text-right">{t("rates.rate")}</Th>
          </tr>
        </thead>
        <tbody>
          {printed.map((rate, index) => (
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
