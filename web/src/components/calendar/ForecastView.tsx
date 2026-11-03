// Each TL account's balance day by day for the next sixty days (F09): a line per account, the part below zero hatched
// and the day an account goes under it marked, with the table of every day's balance. Each account says where its
// forecast starts and what it assumes, which account a payment leaves from among them; the items no account takes and
// the accounts left out are named. Everything here is an estimate, labelled so. A day of the chart leads to what is
// expected on it, in the list above (?gun=).

import { useTranslation } from "react-i18next";

import type { AccountForecast, Forecast } from "../../api/types";
import { formatDay, formatFlow, formatMoney } from "../../lib/format";
import { LineChart } from "../charts/LineChart";
import type { Slot } from "../charts/palette";
import { Empty } from "../QueryState";
import { Badge } from "../ui/Badge";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "block text-xs text-zinc-600 dark:text-zinc-300";
const LIST = "ml-4 list-disc text-sm text-zinc-700 dark:text-zinc-300";

/** The slots 1–8 in turn, an account each, as long as there are slots; any further one grey. */
function slotOf(index: number): Slot {
  return index < 8 ? ((index + 1) as Slot) : 0;
}

/** The card's content: its loading and failure states stay with the card on the page. */
export function ForecastView({ forecast }: { forecast: Forecast }) {
  const { t } = useTranslation("calendar");
  return (
    <div className="flex flex-col gap-4">
        {forecast.accounts.length === 0 ? (
          <Empty title={t("forecast.empty")}>
            <p>{t("forecast.emptyText")}</p>
          </Empty>
        ) : (
          <Balances forecast={forecast} />
        )}
        {forecast.notes.length > 0 ? (
          <ul className={LIST}>
            {forecast.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
        {forecast.elsewhere.length > 0 ? (
          <div className="text-sm">
            <h3 className="font-medium">{t("forecast.elsewhere")}</h3>
            <ul className={LIST}>
              {forecast.elsewhere.map((item, index) => (
                <li key={`${item.day}-${item.title}-${index}`}>
                  {t("forecast.elsewhereItem", {
                    day: formatDay(item.day),
                    title: item.title,
                    account: item.account.label,
                    amount: formatFlow(item.amount, item.direction),
                  })}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {forecast.skipped.length > 0 ? (
          <div className="text-sm">
            <h3 className="font-medium">{t("forecast.skipped")}</h3>
            <ul className={LIST}>
              {forecast.skipped.map((s) => (
                <li key={s.account.id}>
                  {s.account.label}: {s.reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
    </div>
  );
}

function Balances({ forecast }: { forecast: Forecast }) {
  const { t } = useTranslation("calendar");
  const accounts = forecast.accounts;
  const below = accounts
    .filter((a) => a.negative !== null)
    .sort((a, b) => (a.negative?.day ?? "").localeCompare(b.negative?.day ?? ""));
  return (
    <>
      <Sentence accounts={accounts} below={below} />
      <LineChart
        title={t("forecast.chart")}
        summary={t("forecast.summary", { start: formatDay(forecast.today), end: formatDay(forecast.end) })}
        series={accounts.map((a, index) => ({
          key: a.account.id,
          label: a.account.label,
          slot: slotOf(index),
          points: a.days.map((point) => ({ day: point.day, value: point.balance.minor })),
        }))}
        markers={below.map((a) => ({
          day: a.negative?.day ?? "",
          label: t("forecast.marker", { account: a.account.label }),
        }))}
        open={{
          link: (day) => ({ screen: "calendar", id: day, query: {} }),
          hint: t("forecast.openHint"),
          what: t("forecast.openWhat"),
        }}
      />
      <SummaryTable accounts={accounts} />
      {accounts.map((a) => (
        <section key={a.account.id} aria-label={t("forecast.assumptions", { account: a.account.label })}>
          <h3 className="text-sm font-semibold">{t("forecast.assumptionsTitle", { account: a.account.label })}</h3>
          <ul className={LIST}>
            {a.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

/** The simple view's sentence: the first account to go below zero, or the lowest balance of them all. */
function Sentence({ accounts, below }: { accounts: AccountForecast[]; below: AccountForecast[] }) {
  const { t } = useTranslation("calendar");
  const [first, ...more] = below;
  if (first?.negative) {
    return (
      <Say next={{ link: { screen: "account", id: first.account.id, query: {} }, label: t("forecast.nextAccount") }}>
        {t("forecast.sayNegative", {
          account: first.account.label,
          day: first.negative.day,
          balance: formatMoney(first.negative.balance),
        })}
        {more.length > 0 ? ` ${t("forecast.sayNegativeMore", { count: more.length })}` : ""}
      </Say>
    );
  }
  const lowest = accounts.reduce<AccountForecast | undefined>(
    (low, a) => (low === undefined || a.lowest.balance.minor < low.lowest.balance.minor ? a : low),
    undefined,
  );
  if (!lowest) {
    return null;
  }
  return (
    <Say>
      {t("forecast.sayLowest", {
        day: lowest.lowest.day,
        balance: formatMoney(lowest.lowest.balance),
        account: lowest.account.label,
      })}
    </Say>
  );
}

function SummaryTable({ accounts }: { accounts: AccountForecast[] }) {
  const { t } = useTranslation("calendar");
  return (
    <Table>
      <caption className="sr-only">{t("forecast.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("forecast.account")}</Th>
          <Th className="text-right">{t("forecast.start")}</Th>
          <Th className="text-right">{t("forecast.end")}</Th>
          <Th className="text-right">{t("forecast.lowest")}</Th>
          <Th>{t("forecast.negative")}</Th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((a) => {
          const base = t(a.start.source === "notice" ? "forecast.fromNotice" : "forecast.fromStatement", {
            day: formatDay(a.start.day),
          });
          return (
            <tr key={a.account.id}>
              <Td className="font-medium">{a.account.label}</Td>
              <Td className="text-right tabular-nums">
                {formatMoney(a.start.balance)}
                <span className={SMALL}>
                  {a.start.moves > 0 ? t("forecast.moves", { base, count: a.start.moves }) : base}
                </span>
              </Td>
              <Td className="text-right tabular-nums">{formatMoney(a.end_balance)}</Td>
              <Td className="text-right tabular-nums">
                {formatMoney(a.lowest.balance)}
                <span className={SMALL}>{formatDay(a.lowest.day)}</span>
              </Td>
              <Td>
                {a.negative ? (
                  <Badge tone="critical">
                    {t("forecast.below", { day: formatDay(a.negative.day), balance: formatMoney(a.negative.balance) })}
                  </Badge>
                ) : (
                  <Badge tone="good">{t("forecast.stays")}</Badge>
                )}
                {a.interest ? (
                  <span className={SMALL}>{t("forecast.interest", { amount: formatMoney(a.interest) })}</span>
                ) : null}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
