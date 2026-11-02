// The Akış screen's "Şu an" (F05): each account's balance as far as the documents tell, with what it rests on; each
// card's newest statement and the period it is in now; and the month's spending so far against the typical month.
// Every number comes from /api/feed/now. A balance moved by receipts and notices after the document that printed it
// is provisional and says so (architecture §8).

import type { UseQueryResult } from "@tanstack/react-query";
import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";

import type { Labels, Now, NowBalance, NowCard, Pace } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { PaceFigures } from "../Pace";
import { Detailed, Simple, useView } from "../Preferences";
import { Empty, Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import { Money } from "../ui/Money";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { Term } from "../ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

export function NowSection({ now, labels }: { now: UseQueryResult<Now>; labels: Labels }) {
  const { t } = useTranslation("feed");
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-3">
      <h2 id={heading} className="sr-only">
        {t("now.title")}
      </h2>
      {now.isPending ? <Loading /> : null}
      {now.isError ? <Failure error={now.error} onRetry={() => void now.refetch()} /> : null}
      {now.data ? <NowCards now={now.data} labels={labels} /> : null}
    </section>
  );
}

function NowCards({ now, labels }: { now: Now; labels: Labels }) {
  const { t } = useTranslation("feed");
  const { view } = useView();
  if (now.balances.length === 0 && now.unknown.length === 0 && now.cards.length === 0) {
    return <Empty title={t("now.empty")}>{t("now.emptyText")}</Empty>;
  }
  // Side by side the cards say what stands at a glance; the detailed view's tables need the screen's width.
  return (
    <div className={cn("grid items-start gap-4", view === "simple" && "md:grid-cols-2 xl:grid-cols-3")}>
      <BalancesCard now={now} labels={labels} />
      {now.cards.length > 0 ? <CardsCard cards={now.cards} today={now.today} /> : null}
      <PaceCard pace={now.pace} today={now.today} />
    </div>
  );
}

function BalancesCard({ now, labels }: { now: Now; labels: Labels }) {
  const { t } = useTranslation("feed");
  const known = now.balances.length;
  const unknown = now.unknown.length;
  const say =
    known === 0
      ? t("now.balances.empty")
      : unknown > 0
        ? t("now.balances.sayUnknown", { known, unknown })
        : t("now.balances.say", { known });
  const next = unknown > 0 ? { link: DOCUMENTS, label: t("now.balances.nextUpload") } : null;
  return (
    <Card title={t("now.balances.title")} level={3}>
      <Say next={next}>{say}</Say>
      {known > 0 ? (
        <>
          <Simple>
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {now.balances.map((b) => (
                <BalanceItem key={b.account.id} balance={b} />
              ))}
            </ul>
          </Simple>
          <Detailed>
            <BalanceTable balances={now.balances} labels={labels} />
          </Detailed>
        </>
      ) : null}
      {unknown > 0 ? (
        <div className="mt-3">
          <p className="text-sm font-medium">{t("now.balances.unknown")}</p>
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {now.unknown.map((u) => (
              <li key={u.account.id}>
                {u.account.label}: <span className="text-zinc-600 dark:text-zinc-300">{u.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;

function BalanceItem({ balance: b }: { balance: NowBalance }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-2">
      <div className="min-w-0">
        <p className="font-medium">{b.account.label}</p>
        <p className={SMALL}>{b.note}</p>
      </div>
      <div className="flex flex-col items-end">
        <Money value={b.balance} certainty={b.certainty} className="justify-end font-semibold" />
        <InTl balance={b} />
      </div>
    </li>
  );
}

/** A foreign or gold balance's value in TL at the documents' newest rate, or that the documents give none. */
function InTl({ balance: b }: { balance: NowBalance }) {
  const { t } = useTranslation("feed");
  if (b.balance.currency === "TRY") {
    return null;
  }
  if (b.value === null) {
    return <p className={SMALL}>{t("now.balances.noRate")}</p>;
  }
  return (
    <p className={`${SMALL} text-right`}>
      {t("now.balances.inTl", { value: formatMoney(b.value) })}
      {b.rate && b.rate_day ? (
        <span className="block">
          {t("now.balances.rate", {
            currency: b.balance.currency,
            rate: formatRate(b.rate),
            day: formatDay(b.rate_day),
          })}
        </span>
      ) : null}
    </p>
  );
}

function BalanceTable({ balances, labels }: { balances: NowBalance[]; labels: Labels }) {
  const { t } = useTranslation("feed");
  return (
    <Table>
      <caption className="sr-only">{t("now.balances.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("now.balances.account")}</Th>
          <Th>{t("now.balances.type")}</Th>
          <Th className="text-right">{t("now.balances.balance")}</Th>
          <Th className="text-right">{t("now.balances.value")}</Th>
          <Th>{t("now.balances.basis")}</Th>
          <Th>{t("now.balances.through")}</Th>
        </tr>
      </thead>
      <tbody>
        {balances.map((b) => (
          <tr key={b.account.id}>
            <Td className="font-medium">{b.account.label}</Td>
            <Td>{labelOf(labels, "AccountType", b.type)}</Td>
            <Td className="text-right">
              <Money value={b.balance} certainty={b.certainty} className="justify-end" />
            </Td>
            <Td className="text-right tabular-nums">{b.value ? formatMoney(b.value) : "—"}</Td>
            <Td className={SMALL}>{b.note}</Td>
            <Td className="tabular-nums">{formatDay(b.through)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** The card whose due date comes first among those still owing, and what it owes. */
function nextDue(cards: NowCard[], today: string): NowCard | undefined {
  return cards
    .filter((c) => c.due !== null && c.due >= today && c.debt !== null && c.debt.minor > 0)
    .sort((a, b) => (a.due ?? "").localeCompare(b.due ?? ""))[0];
}

function CardsCard({ cards, today }: { cards: NowCard[]; today: string }) {
  const { t } = useTranslation("feed");
  const due = nextDue(cards, today);
  let say: string;
  if (due && due.due && due.debt) {
    const values = { card: due.account.label, day: formatDay(due.due), debt: formatMoney(due.debt) };
    say = due.minimum
      ? t("now.cards.sayDueMinimum", { ...values, minimum: formatMoney(due.minimum) })
      : t("now.cards.sayDue", values);
  } else {
    say = t("now.cards.sayPaid");
  }
  return (
    <Card title={t("now.cards.title")} level={3}>
      <Say next={{ link: CALENDAR, label: t("now.cards.next") }}>{say}</Say>
      <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
        {cards.map((card) => (
          <li key={card.account.id} className="py-2">
            <p className="font-medium">{card.account.label}</p>
            <Simple>
              <CardSummary card={card} />
            </Simple>
            <Detailed>
              <CardFacts card={card} />
            </Detailed>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

/** A card's period so far and what it owes, in a line or two (also an account page's card, F07). */
export function CardSummary({ card }: { card: NowCard }) {
  const { t } = useTranslation("feed");
  const owing = [
    card.due ? t("now.cards.dueShort", { day: formatDay(card.due) }) : "",
    card.debt ? t("now.cards.debtShort", { amount: formatMoney(card.debt) }) : "",
    card.minimum ? t("now.cards.minimumShort", { amount: formatMoney(card.minimum) }) : "",
  ].filter(Boolean);
  return (
    <div className="mt-1 flex flex-col gap-0.5 text-sm">
      <p className="flex flex-wrap items-baseline gap-x-1.5">
        <span>{t("now.cards.period")}:</span>
        <Money value={card.current.spent} certainty={card.certainty} />
        <span className={SMALL}>
          {t("now.cards.periodText", {
            start: formatDay(card.current.start),
            end: formatDay(card.current.end),
            rows: card.current.rows,
          })}
        </span>
      </p>
      {owing.length > 0 ? <p className={SMALL}>{owing.join(" · ")}</p> : null}
    </div>
  );
}

/** Every value of a card's newest statement and period, as a list of names and values. */
export function CardFacts({ card }: { card: NowCard }) {
  const { t } = useTranslation("feed");
  const credit = card.type === "credit_card";
  const rows: Array<[string, ReactNode, ReactNode]> = [
    [
      "period",
      t("now.cards.period"),
      <>
        <Money value={card.current.spent} certainty={card.certainty} />{" "}
        <span className={SMALL}>
          {t("now.cards.periodText", {
            start: formatDay(card.current.start),
            end: formatDay(card.current.end),
            rows: card.current.rows,
          })}
        </span>
      </>,
    ],
    ["cut", <Term id="statementDate">{t("now.cards.cut")}</Term>, formatDay(card.cut)],
  ];
  if (card.total) {
    rows.push(["total", credit ? t("now.cards.total") : t("now.cards.spent"), formatMoney(card.total)]);
  }
  if (card.due) {
    rows.push(["due", <Term id="dueDate">{t("now.cards.due")}</Term>, formatDay(card.due)]);
  }
  if (card.minimum) {
    rows.push(["minimum", <Term id="minimumPayment">{t("now.cards.minimum")}</Term>, formatMoney(card.minimum)]);
  }
  if (card.limit) {
    rows.push(["limit", t("now.cards.limit"), formatMoney(card.limit)]);
  }
  if (credit) {
    rows.push(["paid", t("now.cards.paid"), formatMoney(card.paid)]);
  }
  if (card.debt) {
    rows.push(["debt", t("now.cards.debt"), <Money value={card.debt} certainty={card.certainty} />]);
  }
  return (
    <>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {rows.map(([key, name, value]) => (
          <div key={key} className="contents">
            <dt className="text-zinc-600 dark:text-zinc-300">{name}</dt>
            <dd className="min-w-0 tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {card.note ? <p className={`mt-1 ${SMALL}`}>{card.note}</p> : null}
    </>
  );
}

function PaceCard({ pace, today }: { pace: Pace; today: string }) {
  const { t } = useTranslation("feed");
  const spent = formatMoney(pace.spent);
  let say: string;
  if (pace.typical === null || pace.by_day === null) {
    say = t("now.pace.sayNoTypical", { month: pace.month, spent });
  } else {
    const values = { month: pace.month, spent, byDay: formatMoney(pace.by_day) };
    say = pace.covered < 1 ? t("now.pace.sayCovered", { ...values, share: pace.covered }) : t("now.pace.say", values);
  }
  const next = {
    link: { screen: "transactions", id: "", query: { from: `${pace.month}-01`, to: today } },
    label: t("now.pace.next"),
  } as const;
  return (
    <Card title={t("now.pace.title")} level={3}>
      <Say next={next}>{say}</Say>
      <PaceFigures pace={pace} />
    </Card>
  );
}
