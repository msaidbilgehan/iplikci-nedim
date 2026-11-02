// An account's page, what every type shows (F07): where the account stands and how far its documents reach, its
// balance day by day, the last 12 months' money in and out, its interest and fees, and the regular payments and
// income that run through it.

import { useTranslation } from "react-i18next";

import type { AccountItem, CurvePoint, Fees, Labels, MonthTotals, Series } from "../../api/types";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { HBars } from "../charts/HBars";
import { LineChart } from "../charts/LineChart";
import { StackedBars } from "../charts/StackedBars";
import { Detailed, Simple } from "../Preferences";
import { Card, Facts } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Balance } from "./AccountList";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const tl = (minor: number) => ({ minor, currency: "TRY" });

/** Where the account stands: its balance and the day it knows of, this month's money, and its documents' reach. */
export function StatusCard({ item, labels }: { item: AccountItem; labels: Labels }) {
  const { t } = useTranslation("accounts");
  const m = item.month;
  const f = item.freshness;
  const balance = item.balance
    ? t("status.balance", { balance: formatMoney(item.balance), day: item.day ? formatDay(item.day) : "—" })
    : t("status.noBalance");
  // The service's note goes with the figures: a month no document reaches yet reads 0 and 0 until one does.
  const month = t(m.note ? "status.monthNote" : "status.month", {
    month: m.month,
    moneyIn: formatMoney(m.money_in),
    moneyOut: formatMoney(m.money_out),
    note: m.note,
  });
  return (
    <Card title={t("status.title")}>
      <Say>
        {balance} {month}
      </Say>
      <Simple>
        <div className="flex flex-col gap-1 text-sm">
          <Balance item={item} />
          {f ? (
            <p className={SMALL}>
              {[f.note, f.behind === 0 ? t("account.today") : t("account.behind", { count: f.behind })]
                .filter(Boolean)
                .join(" · ")}
            </p>
          ) : null}
          {f?.late ? <Status tone="warning">{t("account.late")}</Status> : null}
          {item.note ? <p className={SMALL}>{item.note}</p> : null}
        </div>
      </Simple>
      <Detailed>
        <Facts
          items={[
            [t("status.balanceName"), item.balance ? formatMoney(item.balance) : t("unknown")],
            [t("status.value"), item.value ? formatMoney(item.value) : t("unknown")],
            [t("status.day"), item.day ? formatDay(item.day) : "—"],
            [t("status.certainty"), item.certainty ? labelOf(labels, "Certainty", item.certainty) : "—"],
            [
              t("status.lastDocument"),
              f ? (
                <ScreenLink key="document" link={{ screen: "document", id: f.document, query: {} }}>
                  {[labelOf(labels, "DocumentKind", f.kind), f.name].filter(Boolean).join(": ")}
                </ScreenLink>
              ) : (
                "—"
              ),
            ],
            [t("status.reach"), f ? `${formatDay(f.last)} · ${t("account.behind", { count: f.behind })}` : "—"],
            [t("status.expected"), f?.expected ? formatDay(f.expected) : "—"],
            [t("status.missing"), f && f.missing.length > 0 ? f.missing.map(formatMonth).join(", ") : "—"],
            [t("status.monthName"), `${month}${m.provisional > 0 ? ` ${t("account.monthProvisional", { count: m.provisional })}` : ""}`],
            [t("status.note"), [item.note, m.note].filter(Boolean).join(" · ") || "—"],
          ]}
        />
      </Detailed>
    </Card>
  );
}

/** The balance at each day's end as the documents tell it; a day no document covers is blank. */
export function CurveCard({ curve, note, label }: { curve: readonly CurvePoint[]; note: string; label: string }) {
  const { t } = useTranslation("accounts");
  const first = curve[0];
  const last = curve.at(-1);
  if (!first || !last) {
    return (
      <Card title={t("curve.title")}>
        <p className="text-sm">{note}</p>
      </Card>
    );
  }
  const values = curve.map((point) => point.balance.minor);
  const summary = t("curve.say", {
    start: formatDay(first.day),
    end: formatDay(last.day),
    low: formatMoney(tl(Math.min(...values))),
    high: formatMoney(tl(Math.max(...values))),
    last: formatMoney(last.balance),
  });
  return (
    <Card title={t("curve.title")}>
      <LineChart
        title={t("curve.chart", { account: label })}
        summary={summary}
        series={[
          {
            key: "balance",
            label,
            slot: 1,
            gaps: true,
            points: curve.map((point) => ({ day: point.day, value: point.balance.minor })),
          },
        ]}
      />
      <p className={`mt-2 ${SMALL}`}>{note}</p>
    </Card>
  );
}

/** The last 12 months' money in above the axis and out below it; the summary names the newest complete month. */
export function MonthsCard({ months }: { months: readonly MonthTotals[] }) {
  const { t } = useTranslation("accounts");
  if (months.every((m) => m.rows === 0)) {
    return null;
  }
  const complete = months.filter((m) => m.complete).at(-1);
  const summary = complete
    ? t("months.say", {
        month: formatMonth(complete.month),
        moneyIn: formatMoney(complete.money_in),
        moneyOut: formatMoney(complete.money_out),
      })
    : t("months.sayNone");
  return (
    <Card title={t("months.title")}>
      <StackedBars
        title={t("months.chart")}
        summary={summary}
        series={[
          { key: "in", label: t("months.in"), slot: 3 },
          { key: "out", label: t("months.out"), slot: 2 },
        ]}
        months={months.map((m) => ({ month: m.month, values: { in: m.money_in.minor, out: -m.money_out.minor } }))}
      />
      {months.some((m) => !m.complete) ? <p className={`mt-2 ${SMALL}`}>{t("months.partial")}</p> : null}
    </Card>
  );
}

/** The interest and fees of the window, by category, the largest first. */
export function FeesCard({ fees }: { fees: Fees }) {
  const { t } = useTranslation("accounts");
  const first = fees.months[0];
  const last = fees.months.at(-1);
  if (!first || !last) {
    return null;
  }
  const span = { from: formatMonth(first), to: formatMonth(last) };
  if (fees.categories.length === 0) {
    return (
      <Card title={t("fees.title")}>
        <p className="text-sm">{t("fees.none", span)}</p>
      </Card>
    );
  }
  return (
    <Card title={t("fees.title")}>
      <HBars
        title={t("fees.chart")}
        summary={t("fees.say", { ...span, total: formatMoney(fees.total) })}
        itemName={t("fees.category")}
        items={fees.categories.map((fee) => ({ key: fee.category, label: fee.category, value: fee.amount.minor, slot: 0 }))}
      />
    </Card>
  );
}

/** The regular payments made from it, or the regular income that came into it, each leading to its series. */
export function SeriesCard({ title, series, labels }: { title: string; series: readonly Series[]; labels: Labels }) {
  const { t } = useTranslation("accounts");
  if (series.length === 0) {
    return null;
  }
  return (
    <Card title={title}>
      <ul className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
        {series.map((s) => (
          <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5">
            <span>
              <ScreenLink link={{ screen: "subscription", id: s.id, query: {} }} className="font-medium">
                {s.payee}
              </ScreenLink>
              <span className={`block ${SMALL}`}>
                {[
                  labelOf(labels, "SeriesPeriod", s.period),
                  labelOf(labels, "SeriesStatus", s.status),
                  t("series.last", { day: formatDay(s.last_day), amount: formatMoney(s.last_amount) }),
                  s.next_day ? t("series.next", { day: formatDay(s.next_day) }) : "",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
            <span className="whitespace-nowrap tabular-nums">{formatMoney(s.amount)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
