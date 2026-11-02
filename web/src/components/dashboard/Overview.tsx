// The simple view's home (F06), for anyone, with or without finance words: where the money stands, read as pictures
// first. The last closed month's money in, out and left as three figures and one bar, with a sentence saying how it
// went; the months before as bars above and below a line; where that month's money went, by category; the next 30
// days' money as a line with what is to be paid and to come in; and what to do now, each with its button. Every chart
// says how to read it and has its table (ChartFrame). The figures are the service's: a month's are its closing, the
// forecast is the calendar's, the advice the assessment's steps; nothing typical is reckoned here.

import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";

import { useForecast, useInsights, useSpending } from "../../api/queries";
import type { CalendarItem, Dashboard, Forecast, MonthClosing, OpenAlert } from "../../api/types";
import { cn } from "../../lib/cn";
import { addDays, formatDay, formatMoney, formatMonth } from "../../lib/format";
import { HBars } from "../charts/HBars";
import { LineChart } from "../charts/LineChart";
import { SLOT_BG } from "../charts/palette";
import { StackedBars } from "../charts/StackedBars";
import { Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import { ArrowRightIcon, BankIcon, ChecklistIcon, ExclamationIcon, LightbulbIcon } from "../ui/Icons";
import { INCOMING } from "../ui/Money";
import { NextStep, ScreenLink } from "../ui/Say";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const HOW = "text-sm text-zinc-700 dark:text-zinc-300";
const AHEAD_DAYS = 30;
const IN_SLOT = 3; // as an account's months draw money in (accounts/Sections, MonthsCard)
const OUT_SLOT = 2;
const THIN = 0.1; // less than this share of the income left: said to be little

const tl = (minor: number) => ({ minor, currency: "TRY" });

/** The months whose money in is known, oldest first; the newest closed one is the story's. */
function knownMonths(months: readonly MonthClosing[]): MonthClosing[] {
  return months.filter((m) => m.income !== null);
}

export function Overview({ found }: { found: Dashboard }) {
  const months = knownMonths(found.closing.months);
  const story = [...months].reverse().find((m) => m.status === "closed") ?? months.at(-1) ?? null;
  return (
    <div className="flex flex-col gap-6">
      <MonthStory found={found} month={story} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <MonthsChart months={months} />
        {story ? <WhereItWent month={story.month} /> : null}
      </div>
      <NextDays />
      <WhatToDo found={found} />
    </div>
  );
}

// --- the last closed month ----------------------------------------------------------------------------------------

interface FigureProps {
  label: string;
  hint: string;
  value: string;
  tone?: "in" | "out" | "left" | "over";
}

function Figure({ label, hint, value, tone }: FigureProps) {
  return (
    <div className="min-w-0 flex-1 rounded-xl bg-zinc-50 p-3 dark:bg-zinc-800/60">
      <dt className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        <span
          aria-hidden="true"
          className={cn(
            "size-2.5 shrink-0 rounded-full",
            tone === "over" ? "bg-status-critical" : tone === "out" ? SLOT_BG[OUT_SLOT] : SLOT_BG[IN_SLOT],
          )}
        />
        {label}
      </dt>
      <dd
        className={cn(
          "mt-1 text-2xl font-semibold tracking-tight tabular-nums",
          tone === "left" && INCOMING,
          tone === "over" && "text-red-800 dark:text-red-300",
        )}
      >
        {value}
      </dd>
      <dd className={`mt-0.5 ${SMALL}`}>{hint}</dd>
    </div>
  );
}

/**
 * Money in as the bar's whole, out and left as its parts, each part named under it with its share; when more went out,
 * out is the whole, what came in a part and the rest is what was spent beyond it. The sentence beside it says the same
 * in words, so the bar itself is hidden from screen readers.
 */
function MoneyBar({ moneyIn, moneyOut }: { moneyIn: number; moneyOut: number }) {
  const { t } = useTranslation("dashboard");
  const whole = Math.max(moneyIn, moneyOut, 1);
  const spent = Math.min(moneyOut, moneyIn) / whole;
  const rest = Math.abs(moneyIn - moneyOut) / whole;
  const over = moneyOut > moneyIn;
  return (
    <div aria-hidden="true" className="flex flex-col gap-1">
      <div className="flex h-4 w-full gap-0.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <span className={cn("h-full", SLOT_BG[OUT_SLOT])} style={{ width: `${spent * 100}%` }} />
        <span className={cn("h-full", over ? "bg-status-critical" : SLOT_BG[IN_SLOT])} style={{ width: `${rest * 100}%` }} />
      </div>
      <div className={cn("flex justify-between gap-3", SMALL)}>
        <span>{t(over ? "overview.story.barIncome" : "overview.story.barSpent", { share: spent })}</span>
        <span>{t(over ? "overview.story.barOver" : "overview.story.barLeft", { share: rest })}</span>
      </div>
    </div>
  );
}

function MonthStory({ found, month }: { found: Dashboard; month: MonthClosing | null }) {
  const { t } = useTranslation("dashboard");
  const running = found.closing.months.find((m) => m.status === "running");
  const worth = found.net_worth;
  // The total is said with what it rests on: the last documents, the card debts taken off, the accounts left out.
  const total = (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <BankIcon className="size-4 shrink-0 text-teal-800 dark:text-teal-300" />
      <span>
        {t(worth.debts.minor > 0 ? "overview.story.totalAfterDebts" : "overview.story.total", {
          amount: formatMoney(worth.total),
        })}
        {worth.left_out.length > 0 ? ` ${t("overview.story.leftOut", { count: worth.left_out.length })}` : null}
      </span>
      <NextStep step={{ link: worth.link, label: t("overview.story.accounts") }} />
    </p>
  );
  if (!month || month.income === null) {
    return (
      <Card title={t("overview.story.titleNone")}>
        <div className="flex flex-col gap-3">
          <p className="text-base">{t("overview.story.none")}</p>
          {total}
        </div>
      </Card>
    );
  }
  const moneyIn = month.income.minor;
  const moneyOut = month.expense.minor;
  const left = moneyIn - moneyOut;
  const share = moneyIn > 0 ? left / moneyIn : 0;
  const tone = left < 0 ? "critical" : moneyIn > 0 && share < THIN ? "warning" : "good";
  const verdict =
    moneyIn === 0 && moneyOut === 0
      ? t("overview.story.quiet")
      : tone === "critical"
        ? t("overview.story.over", { amount: formatMoney(tl(-left)) })
        : tone === "warning"
          ? t("overview.story.thin", { share })
          : t("overview.story.good", { share });
  return (
    <Card title={t("overview.story.title", { month: formatMonth(month.month) })}>
      <div className="flex flex-col gap-4">
        <dl className="flex flex-col gap-3 sm:flex-row">
          <Figure
            label={t("overview.story.in")}
            hint={t("overview.story.inHint")}
            value={formatMoney(month.income)}
            tone="in"
          />
          <Figure
            label={t("overview.story.out")}
            hint={t("overview.story.outHint")}
            value={formatMoney(month.expense)}
            tone="out"
          />
          <Figure
            label={left < 0 ? t("overview.story.overLabel") : t("overview.story.left")}
            hint={t("overview.story.leftHint")}
            value={formatMoney(tl(Math.abs(left)))}
            tone={left < 0 ? "over" : "left"}
          />
        </dl>
        <MoneyBar moneyIn={moneyIn} moneyOut={moneyOut} />
        <p
          className={cn(
            "flex items-start gap-2 rounded-lg px-3 py-2 text-base",
            tone === "good" && "bg-teal-50 text-teal-950 dark:bg-teal-950/60 dark:text-teal-50",
            tone === "warning" && "bg-amber-50 text-amber-950 dark:bg-amber-950/60 dark:text-amber-50",
            tone === "critical" && "bg-red-50 text-red-950 dark:bg-red-950/60 dark:text-red-50",
          )}
        >
          {tone === "good" ? null : <ExclamationIcon className="mt-1 size-4 shrink-0" />}
          <span>{verdict}</span>
        </p>
        {month.status === "closed" ? null : <p className={SMALL}>{t("overview.story.partial")}</p>}
        {running && running.month !== month.month ? (
          <p className={SMALL}>
            {running.expense.minor > 0
              ? t("overview.story.running", { month: formatMonth(running.month), amount: formatMoney(running.expense) })
              : t("overview.story.runningNone", { month: formatMonth(running.month) })}
          </p>
        ) : null}
        {total}
      </div>
    </Card>
  );
}

// --- the months --------------------------------------------------------------------------------------------------

function MonthsChart({ months }: { months: readonly MonthClosing[] }) {
  const { t } = useTranslation("dashboard");
  if (months.length === 0) {
    return null;
  }
  const closed = months.filter((m) => m.status === "closed");
  const ahead = closed.filter((m) => (m.income?.minor ?? 0) > m.expense.minor).length;
  const say =
    closed.length === 0
      ? t("overview.months.sayNone")
      : ahead === closed.length
        ? t("overview.months.sayAll", { count: closed.length })
        : t("overview.months.say", { count: closed.length, ahead });
  const partial = months.filter((m) => m.status !== "closed").map((m) => m.month);
  return (
    <Card title={t("overview.months.title")}>
      <div className="flex flex-col gap-2">
        <p className={HOW}>{t("overview.months.how")}</p>
        <StackedBars
          title={t("overview.months.chart")}
          summary={say}
          series={[
            { key: "in", label: t("overview.months.in"), slot: IN_SLOT },
            { key: "out", label: t("overview.months.out"), slot: OUT_SLOT },
          ]}
          months={months.map((m) => ({
            month: m.month,
            values: { in: m.income?.minor ?? 0, out: -m.expense.minor },
          }))}
          partial={partial}
          totalLabel={t("overview.months.net")}
          height={240}
        />
      </div>
    </Card>
  );
}

// --- where the money went ------------------------------------------------------------------------------------------

function lastDayOf(month: string): string {
  const [year, number] = month.split("-").map(Number);
  const days = new Date(year ?? 1970, number ?? 1, 0).getDate();
  return `${month}-${String(days).padStart(2, "0")}`;
}

function WhereItWent({ month }: { month: string }) {
  const { t } = useTranslation("dashboard");
  const range = { from: `${month}-01`, to: lastDayOf(month) };
  const spending = useSpending(new URLSearchParams(range).toString());
  const found = spending.data;
  const rows = { screen: "transactions", id: "", query: range } as const;
  return (
    <Card title={t("overview.where.title")}>
      {spending.isPending ? <Loading /> : null}
      {spending.isError ? <Failure error={spending.error} onRetry={() => void spending.refetch()} /> : null}
      {found ? (
        <div className="flex flex-col gap-2">
          <p className={HOW}>{t("overview.where.how")}</p>
          <HBars
            title={t("overview.where.chart", { month: formatMonth(month) })}
            summary={
              found.categories[0]
                ? t("overview.where.say", {
                    month,
                    total: formatMoney(found.tiles.total),
                    name: found.categories[0].category,
                    amount: formatMoney(found.categories[0].total),
                  })
                : t("overview.where.none", { month })
            }
            itemName={t("overview.where.item")}
            items={found.categories.slice(0, 8).map((line) => ({
              key: line.category,
              label: line.category,
              value: line.total.minor,
              slot: OUT_SLOT, // all of it went out: one colour, the names beside the bars tell them apart
              link: line.link,
            }))}
          />
          <NextStep step={{ link: rows, label: t("overview.where.rows") }} />
        </div>
      ) : null}
    </Card>
  );
}

// --- the next 30 days ----------------------------------------------------------------------------------------------

/** The accounts' balances summed day by day from today, for the days ahead. */
function summed(forecast: Forecast, end: string): Array<{ day: string; value: number }> {
  const byDay = new Map<string, number>();
  for (const account of forecast.accounts) {
    for (const point of account.days) {
      if (point.day >= forecast.today && point.day <= end) {
        byDay.set(point.day, (byDay.get(point.day) ?? 0) + point.balance.minor);
      }
    }
  }
  return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, value]) => ({ day, value }));
}

function NextDays() {
  const { t } = useTranslation("dashboard");
  const forecast = useForecast();
  const found = forecast.data;
  return (
    <Card title={t("overview.ahead.title")}>
      {forecast.isPending ? <Loading /> : null}
      {forecast.isError ? <Failure error={forecast.error} onRetry={() => void forecast.refetch()} /> : null}
      {found ? <Ahead forecast={found} /> : null}
    </Card>
  );
}

function Ahead({ forecast }: { forecast: Forecast }) {
  const { t } = useTranslation("dashboard");
  const listHeading = useId();
  const end = addDays(forecast.today, AHEAD_DAYS - 1);
  const points = summed(forecast, end);
  const items: CalendarItem[] = [...forecast.accounts.flatMap((a) => a.items), ...forecast.elsewhere]
    .filter((item) => item.day >= forecast.today && item.day <= end)
    .sort((a, b) => a.day.localeCompare(b.day));
  if (points.length === 0) {
    return <p className="text-sm">{t("overview.ahead.none")}</p>;
  }
  const out = items.filter((item) => item.direction === "out");
  const came = items.filter((item) => item.direction === "in");
  const sum = (list: CalendarItem[]) => tl(list.reduce((total, item) => total + item.amount.minor, 0));
  const lowest = points.reduce((low, point) => (point.value < low.value ? point : low));
  const below = points.find((point) => point.value < 0);
  // The line starts today, after what was expected since the accounts' last documents: said, so that its first day and
  // the balances the other screens show do not read as two answers to one question.
  const known = forecast.accounts.reduce((total, account) => total + account.start.balance.minor, 0);
  const now = points[0]?.value ?? known;
  const only = forecast.accounts.length === 1 ? forecast.accounts[0] : undefined;
  const scope = only
    ? t("overview.ahead.scopeOne", { name: only.account.label })
    : t("overview.ahead.scopeMany", { count: forecast.accounts.length });
  const start =
    now === known ? "" : ` ${t("overview.ahead.start", { known: formatMoney(tl(known)), now: formatMoney(tl(now)) })}`;
  const calendar = { screen: "calendar", id: "", query: {} } as const;
  return (
    <div className="flex flex-col gap-3">
      <p
        className={cn(
          "flex items-start gap-2 rounded-lg px-3 py-2 text-base",
          below
            ? "bg-red-50 text-red-950 dark:bg-red-950/60 dark:text-red-50"
            : "bg-teal-50 text-teal-950 dark:bg-teal-950/60 dark:text-teal-50",
        )}
      >
        {below ? <ExclamationIcon className="mt-1 size-4 shrink-0" /> : null}
        <span>
          {below
            ? t("overview.ahead.negative", { day: below.day, amount: formatMoney(tl(below.value)) })
            : t("overview.ahead.safe", { day: lowest.day, amount: formatMoney(tl(lowest.value)) })}
        </span>
      </p>
      <div className="grid items-start gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="flex min-w-0 flex-col gap-2">
          <p className={HOW}>{t("overview.ahead.how")}</p>
          <p className={SMALL}>
            {scope}
            {start}
          </p>
          <LineChart
            title={t("overview.ahead.chart")}
            summary={t("overview.ahead.say", {
              start: formatDay(forecast.today),
              end: formatDay(end),
              out: out.length,
              outAmount: formatMoney(sum(out)),
              came: came.length,
              inAmount: formatMoney(sum(came)),
            })}
            series={[{ key: "total", label: t("overview.ahead.line"), slot: IN_SLOT, points }]}
            height={220}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <h3 id={listHeading} className="text-sm font-semibold">
            {t("overview.ahead.list")}
          </h3>
          {items.length === 0 ? (
            <p className="text-sm">{t("overview.ahead.nothing")}</p>
          ) : (
            <ul
              aria-labelledby={listHeading}
              className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800"
            >
              {items.slice(0, 6).map((item) => (
                <li key={`${item.day}-${item.series}-${item.title}`} className="flex items-baseline gap-3 py-1.5">
                  <span className={`w-20 shrink-0 tabular-nums ${SMALL}`}>{formatDay(item.day)}</span>
                  <span className="min-w-0 flex-1 truncate" title={item.title}>
                    {item.title}
                  </span>
                  <span
                    className={cn(
                      "shrink-0 font-medium tabular-nums",
                      item.direction === "in" && INCOMING,
                    )}
                  >
                    {item.direction === "in" ? "+" : "−"}
                    {formatMoney(item.amount)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {items.length > 6 ? <p className={SMALL}>{t("overview.ahead.more", { count: items.length - 6 })}</p> : null}
          <NextStep step={{ link: calendar, label: t("overview.ahead.calendar") }} />
        </div>
      </div>
    </div>
  );
}

// --- what to do now ------------------------------------------------------------------------------------------------

interface DoItem {
  key: string;
  icon: ReactNode;
  tone: "critical" | "attention" | "advice"; // an alert of the service's by its level, or a step of the assessment's
  level?: string | undefined; // an alert's level in words, before its title: the colour is not the only sign
  title: string;
  text: string;
  extra?: string | undefined;
  next: { link: OpenAlert["link"]; label: string };
}

const INSIGHTS = { screen: "insights", id: "", query: {} } as const;

function WhatToDo({ found }: { found: Dashboard }) {
  const { t } = useTranslation("dashboard");
  const insights = useInsights();
  const alerts: DoItem[] = found.alerts.items.map((alert, index) => ({
    key: `alert-${index}`,
    icon: <ExclamationIcon className="size-4" />,
    tone: alert.level === "critical" ? ("critical" as const) : ("attention" as const),
    level: t(`alerts.level.${alert.level}`),
    title: alert.title,
    text: alert.text,
    next: { link: alert.link, label: t("overview.todo.open") },
  }));
  const steps: DoItem[] = (insights.data?.steps ?? []).map((step, index) => ({
    key: `step-${index}`,
    icon: <LightbulbIcon className="size-4" />,
    tone: "advice" as const,
    title: step.title,
    text: step.text,
    extra: step.monthly ? t("overview.todo.monthly", { amount: formatMoney(step.monthly) }) : undefined,
    next: { link: INSIGHTS, label: t("overview.todo.more") },
  }));
  const items = [...alerts, ...steps].slice(0, 4);
  return (
    <Card title={t("overview.todo.title")}>
      <div className="flex flex-col gap-3">
        {items.length === 0 && !insights.isPending ? <p className="text-sm">{t("overview.todo.none")}</p> : null}
        {items.length > 0 ? (
          <ol className="grid gap-3 md:grid-cols-2">
            {items.map((item) => (
              <li
                key={item.key}
                className="flex flex-col gap-1.5 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
              >
                <p className="flex items-center gap-2 font-semibold">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid size-7 shrink-0 place-items-center rounded-lg",
                      item.tone === "critical" && "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
                      item.tone === "attention" && "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
                      item.tone === "advice" && "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
                    )}
                  >
                    {item.icon}
                  </span>
                  <span>
                    {item.level ? `${item.level}: ` : null}
                    {item.title}
                  </span>
                </p>
                <p className="text-sm text-zinc-700 dark:text-zinc-300">{item.text}</p>
                {item.extra ? <p className="text-sm font-medium">{item.extra}</p> : null}
                <NextStep step={item.next} context={item.title} className="mt-auto self-start" />
              </li>
            ))}
          </ol>
        ) : null}
        {found.todo.total > 0 ? (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <ChecklistIcon className="size-4 shrink-0 text-amber-800 dark:text-amber-300" />
            <span>{t("overview.todo.data", { count: found.todo.total })}</span>
            <ScreenLink link={found.todo.link} className="inline-flex items-center gap-1">
              {t("overview.todo.dataNext")}
              <ArrowRightIcon className="size-4" />
            </ScreenLink>
          </p>
        ) : null}
      </div>
    </Card>
  );
}
