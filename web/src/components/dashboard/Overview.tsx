// The simple view's home (F06), for anyone, with or without finance words: where the money stands, read as pictures
// first. The newest ended month's money in, out, saved and left as figures and one bar, with a sentence saying how it
// went: out is the spending, the money sent to people and the loan principal repaid, and left is the income less what
// went out and what was saved, as the month-end page says. A month that ended but still waits for documents (a card's
// statement covers its last days weeks later) is told at once, its figures and its verdict "for now" (şimdilik), with
// what it waits for and by when; until v0.10.1 the story waited for the month to close and told the one before it
// for weeks. The arrows beside its title go to the months before (?ay=). An ended month whose money in is not known
// yet (its account lists cover too little of it) says so in its own sentence. Then the months as bars above and below
// a line; where the story month's money went, by category; the next 30 days' money as a line with what is to be paid
// and to come in; and what to do now, each with its button. Every chart says how to read it and has its table
// (ChartFrame). The figures are the service's: a month's are its closing, the forecast is the calendar's, the advice
// the assessment's steps; nothing typical is reckoned here. Every chart leads on: a month's money in to its income,
// its money out to the rows that went out and its saving to its savings, a category to its rows of the month, a day of
// the next 30 to what the calendar expects on it.

import type { TFunction } from "i18next";
import { type ReactNode, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useForecast, useInsights, useSpending } from "../../api/queries";
import type { CalendarItem, Dashboard, Forecast, MonthClosing, OpenAlert } from "../../api/types";
import { cn } from "../../lib/cn";
import { addDays, formatDay, formatMoney, formatMonth } from "../../lib/format";
import { type Holdings, readHoldings, saveHoldings } from "../../lib/preferences";
import { monthDays, monthIncome, monthOut, monthRows, monthSaving, rowsLink } from "../../lib/rows";
import { untoldTotal } from "../accounts/UntoldNote";
import { HBars } from "../charts/HBars";
import type { StackSeries } from "../charts/layout";
import { LineChart } from "../charts/LineChart";
import { isUnclosed, type Unclosed, useMarkOf } from "../charts/marks";
import { SLOT_BG } from "../charts/palette";
import { StackedBars } from "../charts/StackedBars";
import { Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BankIcon,
  ChecklistIcon,
  ExclamationIcon,
  LightbulbIcon,
  UploadIcon,
} from "../ui/Icons";
import { LinkButton } from "../ui/LinkButton";
import { INCOMING } from "../ui/Money";
import { AddressStep, NextStep, ScreenLink } from "../ui/Say";
import { Segmented } from "../ui/Segmented";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const HOW = "text-sm text-zinc-700 dark:text-zinc-300";
const AHEAD_DAYS = 30;
const IN_SLOT = 3; // as an account's months draw money in (accounts/Sections, MonthsCard)
const OUT_SLOT = 2;
const SAVE_SLOT = 1; // what was set aside: blue beside the orange of what went out
const THIN = 0.1; // less than this share of the income left: said to be little

const tl = (minor: number) => ({ minor, currency: "TRY" });

/** The months whose money in is known, oldest first. */
function knownMonths(months: readonly MonthClosing[]): MonthClosing[] {
  return months.filter((m) => m.income !== null);
}

const MONTH = "ay"; // the address names a month of the story's other than the newest (?ay=2026-09)

export function Overview({ found }: { found: Dashboard }) {
  const [params] = useSearchParams();
  const months = knownMonths(found.closing.months);
  // The months the story tells: those that ended, their money in known, closed or still waiting for documents. The
  // newest is told unless the address names another; a month that runs is told only while none has ended.
  const ended = months.filter((m) => m.status !== "running");
  const latest = ended.at(-1) ?? months.at(-1) ?? null;
  const story = ended.find((m) => m.month === params.get(MONTH)) ?? latest;
  return (
    <div className="flex flex-col gap-6">
      <MonthStory found={found} month={story} months={ended} isLatest={story === latest} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <MonthsChart months={months} />
        {story ? <WhereItWent month={story.month} isOpen={story.status !== "closed"} /> : null}
      </div>
      <NextDays />
      <WhatToDo found={found} />
    </div>
  );
}

// --- the story's month ---------------------------------------------------------------------------------------------

interface FigureProps {
  label: string;
  hint: string;
  value: string;
  tone?: "in" | "out" | "saved" | "left" | "over";
}

const DOTS: Readonly<Record<NonNullable<FigureProps["tone"]>, string>> = {
  in: SLOT_BG[IN_SLOT],
  out: SLOT_BG[OUT_SLOT],
  saved: SLOT_BG[SAVE_SLOT],
  left: SLOT_BG[IN_SLOT],
  over: "bg-status-critical",
};

function Figure({ label, hint, value, tone = "in" }: FigureProps) {
  return (
    <div className="min-w-0 flex-1 rounded-xl bg-zinc-50 p-3 dark:bg-zinc-800/60">
      <dt className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-full", DOTS[tone])} />
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

interface Money {
  moneyIn: number; // minor units, as every figure here
  moneyOut: number; // spending, money sent to people and loan principal repaid
  saved: number;
  left: number; // moneyIn less moneyOut and saved: below zero when more went out
}

/**
 * Money in as the bar's whole, and what went out, what was saved and what was left as its parts, each named under it
 * with its share; when more went out, what went out and was saved is the whole, what came in a part and the rest is
 * what went out beyond it. The sentence beside it says the same in words, so the bar itself is hidden from screen
 * readers.
 */
function MoneyBar({ moneyIn, moneyOut, saved, left }: Money) {
  const { t } = useTranslation("dashboard");
  if (left < 0) {
    const whole = Math.max(moneyOut + saved, 1);
    const came = Math.max(moneyIn, 0) / whole;
    const beyond = -left / whole;
    return (
      <div aria-hidden="true" className="flex flex-col gap-1">
        <div className="flex h-4 w-full gap-0.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
          <span className={cn("h-full", SLOT_BG[OUT_SLOT])} style={{ width: `${came * 100}%` }} />
          <span className="h-full bg-status-critical" style={{ width: `${beyond * 100}%` }} />
        </div>
        <div className={cn("flex justify-between gap-3", SMALL)}>
          <span>{t("overview.story.barIncome", { share: came })}</span>
          <span>{t("overview.story.barOver", { share: beyond })}</span>
        </div>
      </div>
    );
  }
  const whole = Math.max(moneyIn, 1);
  const parts = [
    { key: "out", share: moneyOut / whole, fill: SLOT_BG[OUT_SLOT], said: "overview.story.barSpent" },
    { key: "saved", share: saved / whole, fill: SLOT_BG[SAVE_SLOT], said: "overview.story.barSaved" },
    { key: "left", share: left / whole, fill: SLOT_BG[IN_SLOT], said: "overview.story.barLeft" },
  ] as const;
  const shown = parts.filter((part) => part.key !== "saved" || saved > 0);
  return (
    <div aria-hidden="true" className="flex flex-col gap-1">
      <div className="flex h-4 w-full gap-0.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        {shown.map((part) => (
          <span key={part.key} className={cn("h-full", part.fill)} style={{ width: `${part.share * 100}%` }} />
        ))}
      </div>
      <div className={cn("flex flex-wrap justify-between gap-x-3", SMALL)}>
        {shown.map((part) => (
          <span key={part.key}>{t(part.said, { share: part.share })}</span>
        ))}
      </div>
    </div>
  );
}

/** What went out is named by what it holds besides the spending: money sent to people, loan principal or both. */
function outContext(month: MonthClosing): string {
  const people = month.people.minor !== 0;
  const debt = month.debt.minor !== 0;
  return people && debt ? "both" : people ? "people" : debt ? "debt" : "";
}

type Tone = "good" | "warning" | "critical";

/**
 * The month's verdict, as İplikçi Nedim's (app.sayings): more went out than came in, little left, or a part left. A
 * month still open says it for now: its documents to come can only add to what went out.
 */
function verdictOf(
  { moneyIn, moneyOut, saved, left }: Money,
  isOpen: boolean,
  t: TFunction<"dashboard">,
): { tone: Tone; said: string } {
  const share = moneyIn > 0 ? left / moneyIn : 0;
  const context = saved > 0 ? "saved" : "";
  const savedShare = moneyIn > 0 ? saved / moneyIn : 0;
  if (moneyIn === 0 && moneyOut === 0 && saved === 0) {
    return { tone: "good", said: t(isOpen ? "overview.story.quietOpen" : "overview.story.quiet") };
  }
  if (left < 0) {
    const amount = formatMoney(tl(-left));
    return { tone: "critical", said: t(isOpen ? "overview.story.overOpen" : "overview.story.over", { amount, context }) };
  }
  if (moneyIn > 0 && share < THIN) {
    const said = t(isOpen ? "overview.story.thinOpen" : "overview.story.thin", { share, saved: savedShare, context });
    return { tone: "warning", said };
  }
  const said = t(isOpen ? "overview.story.goodOpen" : "overview.story.good", { share, saved: savedShare, context });
  return { tone: "good", said };
}

interface MonthStoryProps {
  found: Dashboard;
  month: MonthClosing | null;
  months: readonly MonthClosing[]; // the ended months the story can tell, oldest first
  isLatest: boolean; // the newest of them, as the Pano opens on
}

function MonthStory({ found, month, months, isLatest }: MonthStoryProps) {
  const { t } = useTranslation("dashboard");
  const running = found.closing.months.find((m) => m.status === "running");
  const worth = found.net_worth;
  const untold = untoldTotal(worth.untold);
  // The total is said with what it rests on: the last documents, the card debts and the money in no document tells yet
  // taken off, the accounts left out.
  const total = (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <BankIcon className="size-4 shrink-0 text-teal-800 dark:text-teal-300" />
      <span>
        {t(worth.debts.minor > 0 ? "overview.story.totalAfterDebts" : "overview.story.total", {
          amount: formatMoney(worth.total),
        })}
        {untold ? ` ${t("overview.story.untold", { amount: formatMoney(untold) })}` : null}
        {worth.left_out.length > 0 ? ` ${t("overview.story.leftOut", { count: worth.left_out.length })}` : null}
      </span>
      <NextStep step={{ link: worth.link, label: t("overview.story.accounts") }} />
    </p>
  );
  if (!month || month.income === null || month.left === null) {
    return (
      <Card title={t("overview.story.titleNone")}>
        <div className="flex flex-col gap-3">
          <p className="text-base">{t("overview.story.none")}</p>
          {/* Why none is told yet: the newest ended month, whose money in is not known yet. */}
          {heldAfter(found.closing.months, "")
            .slice(-1)
            .map((held) => (
              <HeldMonth key={held.month} month={held} />
            ))}
          {total}
        </div>
      </Card>
    );
  }
  // The month-end page's figures: what is left is the income less what went out and what was saved.
  const money: Money = {
    moneyIn: month.income.minor,
    moneyOut: month.out.minor,
    saved: month.saving.minor,
    left: month.left.minor,
  };
  const isOpen = month.status !== "closed";
  const { tone, said } = verdictOf(money, isOpen, t);
  const over = money.left < 0;
  return (
    <Card
      title={t("overview.story.title", { month: formatMonth(month.month) })}
      action={<MonthNav months={months} current={month.month} />}
    >
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
            hint={t("overview.story.outHint", { context: outContext(month) })}
            value={formatMoney(month.out)}
            tone="out"
          />
          {money.saved > 0 ? (
            <Figure
              label={t("overview.story.saved")}
              hint={t("overview.story.savedHint")}
              value={formatMoney(month.saving)}
              tone="saved"
            />
          ) : null}
          <Figure
            label={over ? t("overview.story.overLabel") : t(isOpen ? "overview.story.leftOpen" : "overview.story.left")}
            hint={t("overview.story.leftHint", { context: money.saved > 0 ? "saved" : "" })}
            value={formatMoney(tl(Math.abs(money.left)))}
            tone={over ? "over" : "left"}
          />
        </dl>
        <MoneyBar {...money} />
        <p
          className={cn(
            "flex items-start gap-2 rounded-lg px-3 py-2 text-base",
            tone === "good" && "bg-teal-50 text-teal-950 dark:bg-teal-950/60 dark:text-teal-50",
            tone === "warning" && "bg-amber-50 text-amber-950 dark:bg-amber-950/60 dark:text-amber-50",
            tone === "critical" && "bg-red-50 text-red-950 dark:bg-red-950/60 dark:text-red-50",
          )}
        >
          {tone === "good" ? null : <ExclamationIcon className="mt-1 size-4 shrink-0" />}
          <span>{said}</span>
        </p>
        {isOpen ? <OpenMonth month={month} /> : null}
        {isLatest
          ? heldAfter(found.closing.months, month.month).map((held) => <HeldMonth key={held.month} month={held} />)
          : null}
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

/**
 * The months before and after the one told, as links: the address keeps the month (?ay=), so the back button and a
 * new tab follow it; the newest needs none. Hidden while the story has one month only.
 */
function MonthNav({ months, current }: { months: readonly MonthClosing[]; current: string }) {
  const { t } = useTranslation("dashboard");
  const [params] = useSearchParams();
  const index = months.findIndex((m) => m.month === current);
  const before = index > 0 ? months[index - 1] : undefined;
  const after = index >= 0 ? months[index + 1] : undefined;
  if (!before && !after) {
    return null;
  }
  const to = (month: string, newest: boolean) => {
    const next = new URLSearchParams(params);
    if (newest) {
      next.delete(MONTH);
    } else {
      next.set(MONTH, month);
    }
    const query = next.toString();
    return { search: query ? `?${query}` : "" };
  };
  const PAGE = "min-h-10 px-3"; // beside the title: a little lower than a form's buttons
  return (
    <nav aria-label={t("overview.story.months")} className="flex flex-wrap gap-2">
      {before ? (
        <LinkButton to={to(before.month, false)} preventScrollReset className={PAGE}>
          <ArrowLeftIcon className="size-4" />
          <span className="sr-only">{t("overview.story.before")}</span> {formatMonth(before.month)}
        </LinkButton>
      ) : null}
      {after ? (
        <LinkButton to={to(after.month, index + 1 === months.length - 1)} preventScrollReset className={PAGE}>
          <span className="sr-only">{t("overview.story.after")}</span> {formatMonth(after.month)}
          <ArrowRightIcon className="size-4" />
        </LinkButton>
      ) : null}
    </nav>
  );
}

/**
 * The story's month ended but has not closed: what it waits for and by when, a missing document or a check, and that
 * its figures are the documents' so far; with the way to its month-end page.
 */
function OpenMonth({ month }: { month: MonthClosing }) {
  const { t } = useTranslation("dashboard");
  const said =
    month.status === "waiting"
      ? t("overview.story.open", {
          context: month.closes_by ? "" : "undated",
          count: Math.max(month.waiting.length, 1),
          month: month.month,
          day: month.closes_by ?? "",
        })
      : month.status === "running"
        ? t("overview.story.partial")
        : t("overview.story.open", { context: month.status, month: month.month });
  // What it waits for, by name: each account's document, its days and its cut, as the month-end page lists them.
  const awaited = month.status === "running" ? [] : month.waiting;
  return (
    <div className={cn("flex flex-col gap-1", SMALL)}>
      <p>{said}</p>
      {awaited.length > 0 ? (
        <>
          <p>{t("overview.story.awaited")}</p>
          <ul className="list-disc pl-5">
            {awaited.map((w) => (
              <li key={w.account.id}>
                <span className="font-medium">{w.account.label}</span>: {w.waiting_for}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {month.status === "running" ? null : (
        <NextStep step={{ link: month.link, label: t("overview.story.heldOpen", { month: month.month }) }} />
      )}
    </div>
  );
}

/**
 * The ended months after the story's whose money in is not known yet, oldest first: the story cannot tell them, and
 * each says why. A month whose money in is known is the story's itself, closed or not.
 */
function heldAfter(months: readonly MonthClosing[], story: string): MonthClosing[] {
  return months.filter((m) => m.month > story && m.status !== "running" && m.income === null);
}

/** An ended month the story cannot tell yet, in one sentence: what was spent in it so far, and its month-end page. */
function HeldMonth({ month }: { month: MonthClosing }) {
  const { t } = useTranslation("dashboard");
  return (
    <p className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", SMALL)}>
      <span>{t("overview.story.held", { month: month.month, amount: formatMoney(month.expense) })}</span>
      <NextStep step={{ link: month.link, label: t("overview.story.heldOpen", { month: month.month }) }} />
    </p>
  );
}

// --- the months --------------------------------------------------------------------------------------------------

function MonthsChart({ months }: { months: readonly MonthClosing[] }) {
  const { t } = useTranslation("dashboard");
  if (months.length === 0) {
    return null;
  }
  const closed = months.filter((m) => m.status === "closed");
  const ahead = closed.filter((m) => (m.left?.minor ?? 0) > 0).length;
  const say =
    closed.length === 0
      ? t("overview.months.sayNone")
      : ahead === closed.length
        ? t("overview.months.sayAll", { count: closed.length })
        : t("overview.months.say", { count: closed.length, ahead });
  const markOf = useMarkOf();
  const unclosed = months.filter(unclosedMonth);
  const partial = unclosed.map((m) => m.month);
  // A month not closed says why over its column: one waiting for its statements is not missing anything.
  const marks = Object.fromEntries(unclosed.map((m) => [m.month, markOf(m.status, m.closes_by)]));
  const saving = months.some((m) => m.saving.minor !== 0);
  const series: StackSeries[] = [
    { key: "in", label: t("overview.months.in"), slot: IN_SLOT },
    { key: "out", label: t("overview.months.out"), slot: OUT_SLOT },
  ];
  if (saving) {
    series.push({ key: "saved", label: t("overview.months.saved"), slot: SAVE_SLOT });
  }
  return (
    <Card title={t("overview.months.title")}>
      <div className="flex flex-col gap-2">
        <p className={HOW}>{t("overview.months.how", { context: saving ? "saved" : "" })}</p>
        <StackedBars
          title={t("overview.months.chart")}
          summary={say}
          series={series}
          months={months.map((m) => ({
            month: m.month,
            values: { in: m.income?.minor ?? 0, out: -m.out.minor, ...(saving ? { saved: -m.saving.minor } : {}) },
          }))}
          partial={partial}
          marks={marks}
          totalLabel={t("overview.months.net")}
          height={240}
          open={{
            // Money in is the month's income, money out the rows that went out, a saving the month's savings; the month
            // itself, beside its bars or by its name, every row of it.
            link: ({ month, series }) =>
              series === "in"
                ? monthIncome(month)
                : series === "out"
                  ? monthOut(month)
                  : series === "saved"
                    ? monthSaving(month)
                    : monthRows(month),
            hint: t("overview.months.openHint"),
            what: (s) =>
              s?.key === "in"
                ? t("overview.months.openIn")
                : s?.key === "saved"
                  ? t("overview.months.openSaved")
                  : s?.key === "out"
                    ? t("overview.months.openOut")
                    : t("overview.months.openMonth"),
          }}
        />
        {unclosed.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {unclosed.map((m) => (
              <li key={m.month} className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", SMALL)}>
                <span>{unclosedSay(m, t)}</span>
                <ScreenLink link={monthRows(m.month)}>{t("overview.months.rows", { month: m.month })}</ScreenLink>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Card>
  );
}

type UnclosedMonth = MonthClosing & { status: Unclosed };

function unclosedMonth(month: MonthClosing): month is UnclosedMonth {
  return isUnclosed(month.status);
}

/**
 * Why a month is not closed, under the chart: one waiting for its statements is not missing anything, and says how
 * many it waits for and when the last comes; one running runs on; one missing a document or wanting a check says so.
 */
function unclosedSay(month: UnclosedMonth, t: TFunction<"dashboard">): string {
  if (month.status === "waiting") {
    return t("overview.months.unclosed.waiting", {
      context: month.closes_by ? "" : "undated",
      count: Math.max(month.waiting.length, 1),
      month: month.month,
      day: month.closes_by ?? "",
    });
  }
  return t(`overview.months.unclosed.${month.status}`, { month: month.month });
}

// --- where the money went ------------------------------------------------------------------------------------------

/** Where the story month's money went; a month still open says so far. */
function WhereItWent({ month, isOpen }: { month: string; isOpen: boolean }) {
  const { t } = useTranslation("dashboard");
  const range = monthDays(month);
  const spending = useSpending(new URLSearchParams(range).toString());
  const found = spending.data;
  const rows = rowsLink(range);
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
                ? t(isOpen ? "overview.where.sayOpen" : "overview.where.say", {
                    month,
                    total: formatMoney(found.tiles.total),
                    name: found.categories[0].category,
                    amount: formatMoney(found.categories[0].total),
                  })
                : t(isOpen ? "overview.where.noneOpen" : "overview.where.none", { month })
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

/** The accounts' balances summed day by day from today, for the days ahead, with extra (minor units) on each day. */
function summed(forecast: Forecast, end: string, extra = 0): Array<{ day: string; value: number }> {
  const byDay = new Map<string, number>();
  for (const account of forecast.accounts) {
    for (const point of account.days) {
      if (point.day >= forecast.today && point.day <= end) {
        byDay.set(point.day, (byDay.get(point.day) ?? 0) + point.balance.minor);
      }
    }
  }
  return [...byDay.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, value]) => ({ day, value: value + extra }));
}

/** What the line takes off every day: each account's money out tied to no day, the median month of its complete
 * months, card payments apart; with the first and the last of those months. Undefined when nothing is spread. */
function spreadOf(forecast: Forecast): { cards: number; spend: number; from: string; to: string } | undefined {
  const spreads = forecast.accounts.flatMap((a) => [a.cards, a.spend]).filter((s) => s !== null);
  const months = spreads.flatMap((s) => s.months).sort();
  const sum = (list: Array<Forecast["accounts"][number]["spend"]>) =>
    list.reduce((total, s) => total + (s?.monthly.minor ?? 0), 0);
  const cards = sum(forecast.accounts.map((a) => a.cards));
  const spend = sum(forecast.accounts.map((a) => a.spend));
  const from = months[0];
  const to = months[months.length - 1];
  return from && to && cards + spend > 0 ? { cards, spend, from, to } : undefined;
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
  const [holdings, setHoldings] = useState<Holdings>(readHoldings);
  const end = addDays(forecast.today, AHEAD_DAYS - 1);
  // What moves with a rate or a market is left out of the forecast; the user may count it too, at today's value.
  const valued = forecast.outside.filter((h) => h.value !== null);
  const unvalued = forecast.outside.length - valued.length;
  const held = valued.reduce((total, h) => total + (h.value?.minor ?? 0), 0);
  const all = holdings === "all" && valued.length > 0;
  const extra = all ? held : 0;
  const points = summed(forecast, end, extra);
  const spread = spreadOf(forecast);
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
  const known = forecast.accounts.reduce((total, account) => total + account.start.balance.minor, 0) + extra;
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
            ? t("overview.ahead.negative", {
                context: all ? "all" : "",
                day: below.day,
                amount: formatMoney(tl(below.value)),
              })
            : t("overview.ahead.safe", {
                context: all ? "all" : "",
                day: lowest.day,
                amount: formatMoney(tl(lowest.value)),
              })}
          {below && !all && held > 0 ? ` ${t("overview.ahead.convert", { amount: formatMoney(tl(held)) })}` : ""}
        </span>
      </p>
      <div className="grid items-start gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="flex min-w-0 flex-col gap-2">
          <p className={HOW}>{t("overview.ahead.how")}</p>
          {valued.length > 0 ? (
            <div className="self-start">
              <Segmented
                legend={t("overview.ahead.holdings")}
                options={[
                  { value: "tl", label: t("overview.ahead.holdingsTl") },
                  { value: "all", label: t("overview.ahead.holdingsAll") },
                ]}
                value={all ? "all" : "tl"}
                onChange={(value) => {
                  setHoldings(value);
                  saveHoldings(value);
                }}
              />
            </div>
          ) : null}
          <p className={SMALL}>
            {scope}
            {start}
            {valued.length > 0
              ? ` ${t(all ? "overview.ahead.outsideCounted" : "overview.ahead.outside", {
                  amount: formatMoney(tl(held)),
                })}`
              : ""}
            {unvalued > 0 ? ` ${t("overview.ahead.unvalued", { count: unvalued })}` : ""}
            {` ${t("overview.ahead.undocumented")}`}
          </p>
          {spread ? (
            <p className={SMALL}>
              {t(spread.cards > 0 ? "overview.ahead.daily" : "overview.ahead.dailySpend", {
                from: spread.from,
                to: spread.to,
                cards: formatMoney(tl(spread.cards)),
                spend: formatMoney(tl(spread.spend)),
              })}
            </p>
          ) : null}
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
            series={[
              { key: "total", label: t(all ? "overview.ahead.lineAll" : "overview.ahead.line"), slot: IN_SLOT, points },
            ]}
            height={220}
            open={{
              link: (day) => ({ screen: "calendar", id: day, query: {} }),
              hint: t("overview.ahead.openHint"),
              what: t("overview.ahead.openWhat"),
            }}
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
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <UploadIcon className="size-4 shrink-0 text-teal-800 dark:text-teal-300" />
          <span>{t("overview.todo.addText")}</span>
          <AddressStep to="/belge-ekle" label={t("overview.todo.add")} />
        </p>
      </div>
    </Card>
  );
}
