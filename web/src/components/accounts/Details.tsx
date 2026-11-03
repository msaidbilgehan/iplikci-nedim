// What an account's type adds to its page (F07's table of pages by type): a credit card's statements with how each was
// paid, its installments and the months they reach; an overdraft's use and cost; a deposit's principal and return; a
// currency or gold account's amount, value and cost; a brokerage account's portfolio; a loan's installments. What the
// documents never print is said to be missing from them ("belgelerde yok"), never shown as zero.

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type {
  Brokerage,
  CardPage,
  Deposit,
  Holding,
  Labels,
  Loan,
  Money as Amount,
  Overdraft,
  PaidStatus,
} from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { rateOrigin } from "../../lib/rateOrigin";
import { DueTable } from "../DueList";
import { CardFacts, CardSummary } from "../feed/Now";
import { Detailed, Simple } from "../Preferences";
import type { Tone } from "../ui/Badge";
import { Card, Facts } from "../ui/Card";
import { Money } from "../ui/Money";
import { Say } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";
import { Term } from "../ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const SHOWN_STATEMENTS = 6; // the simple view's payment history: the newest statements

// How a statement was paid, as a state that is good, a warning, critical, or not judged yet.
const PAID_TONES: Readonly<Record<PaidStatus, Tone>> = {
  full: "good",
  minimum: "warning",
  partial: "warning",
  unpaid: "critical",
  open: "neutral",
  nothing_due: "good",
};

/** An amount, or that the documents do not print it. */
function Known({ value, children }: { value: Amount | null; children?: ReactNode }) {
  const { t } = useTranslation("accounts");
  if (value === null) {
    return <span className="text-zinc-600 dark:text-zinc-300">{t("unknown")}</span>;
  }
  return (
    <span className="tabular-nums">
      {formatMoney(value)}
      {children}
    </span>
  );
}

function Note({ text }: { text: string }) {
  return text ? <p className={cn("mt-2", SMALL)}>{text}</p> : null;
}

export function CardDetails({ card, labels }: { card: CardPage; labels: Labels }) {
  const { t } = useTranslation("accounts");
  return (
    <>
      <Card title={t("card.title")}>
        {card.statement ? (
          <>
            <Simple>
              <CardSummary card={card.statement} />
            </Simple>
            <Detailed>
              <CardFacts card={card.statement} />
            </Detailed>
          </>
        ) : null}
        <h3 className="mt-4 mb-2 text-sm font-semibold">{t("card.statements")}</h3>
        {card.statements.length === 0 ? <p className="text-sm">{t("card.noStatements")}</p> : null}
        <Simple>
          <ul className="flex flex-col gap-1 text-sm">
            {card.statements.slice(0, SHOWN_STATEMENTS).map((s) => (
              <li key={s.cut} className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span>
                  {t("card.statementLine", { cut: formatDay(s.cut) })}
                  {s.total ? <span className={cn("ml-2", SMALL)}>{formatMoney(s.total)}</span> : null}
                </span>
                {s.status ? (
                  <Status tone={PAID_TONES[s.status]}>{labelOf(labels, "PaidStatus", s.status)}</Status>
                ) : null}
              </li>
            ))}
          </ul>
        </Simple>
        <Detailed>
          <Table>
            <caption className="sr-only">{t("card.statements")}</caption>
            <thead>
              <tr>
                <Th>
                  <Term id="statementDate">{t("card.cut")}</Term>
                </Th>
                <Th>{t("card.period")}</Th>
                <Th className="text-right">{t("card.total")}</Th>
                <Th>
                  <Term id="dueDate">{t("card.due")}</Term>
                </Th>
                <Th className="text-right">
                  <Term id="minimumPayment">{t("card.minimum")}</Term>
                </Th>
                <Th className="text-right">{t("card.limit")}</Th>
                <Th className="text-right">{t("card.paid")}</Th>
                <Th>{t("card.status")}</Th>
                <Th className="text-right">{t("card.spent")}</Th>
                <Th>{t("card.verified")}</Th>
              </tr>
            </thead>
            <tbody>
              {card.statements.map((s) => (
                <tr key={s.cut}>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(s.cut)}</Td>
                  <Td className="whitespace-nowrap tabular-nums">
                    {formatDay(s.start)} – {formatDay(s.end)}
                    <span className={cn("block", SMALL)}>{t("card.rows", { count: s.rows })}</span>
                  </Td>
                  <Td className="text-right">
                    <Known value={s.total} />
                  </Td>
                  <Td className="whitespace-nowrap tabular-nums">{s.due ? formatDay(s.due) : "—"}</Td>
                  <Td className="text-right">
                    <Known value={s.minimum} />
                  </Td>
                  <Td className="text-right">
                    <Known value={s.limit} />
                  </Td>
                  <Td className="text-right">{s.status ? <Known value={s.paid} /> : "—"}</Td>
                  <Td>{s.status ? <Status tone={PAID_TONES[s.status]}>{labelOf(labels, "PaidStatus", s.status)}</Status> : "—"}</Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(s.spent)}</Td>
                  <Td>{s.verified ? t("card.verifiedYes") : t("card.verifiedNo")}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Detailed>
      </Card>
      {card.installments.length > 0 ? <Installments card={card} /> : null}
    </>
  );
}

function Installments({ card }: { card: CardPage }) {
  const { t } = useTranslation("accounts");
  const last = card.schedule.at(-1);
  return (
    <Card title={t("card.installments")}>
      <Say>
        {t("card.installmentsSay", {
          count: card.installments.length,
          left: formatMoney(card.left),
          month: last ? formatMonth(last.month) : "",
        })}
      </Say>
      <Simple>
        <ul className="flex flex-col gap-1 text-sm">
          {card.installments.map((item) => (
            <li key={item.fingerprint} className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span>
                {item.title}{" "}
                <span className={SMALL}>
                  {t("card.installmentLine", { number: item.number, count: item.count, left: item.left })}
                </span>
              </span>
              <span className="whitespace-nowrap tabular-nums">{formatMoney(item.remaining)}</span>
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("card.installments")}</caption>
          <thead>
            <tr>
              <Th>{t("card.purchase")}</Th>
              <Th>{t("card.installment")}</Th>
              <Th className="text-right">{t("card.installmentAmount")}</Th>
              <Th className="text-right">{t("card.left")}</Th>
              <Th className="text-right">{t("card.remaining")}</Th>
              <Th>{t("card.lastDay")}</Th>
            </tr>
          </thead>
          <tbody>
            {card.installments.map((item) => (
              <tr key={item.fingerprint}>
                <Td>{item.title}</Td>
                <Td className="tabular-nums">
                  {item.number}/{item.count}
                </Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(item.amount)}</Td>
                <Td className="text-right tabular-nums">{item.left}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(item.remaining)}</Td>
                <Td className="whitespace-nowrap tabular-nums">{formatDay(item.last_day)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
        <h3 className="mt-4 mb-2 text-sm font-semibold">{t("card.schedule")}</h3>
        <Table>
          <caption className="sr-only">{t("card.schedule")}</caption>
          <thead>
            <tr>
              <Th>{t("card.month")}</Th>
              <Th className="text-right">{t("card.scheduleAmount")}</Th>
              <Th className="text-right">{t("card.scheduleCount")}</Th>
            </tr>
          </thead>
          <tbody>
            {card.schedule.map((m) => (
              <tr key={m.month}>
                <Td>{formatMonth(m.month)}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(m.amount)}</Td>
                <Td className="text-right tabular-nums">{m.count}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </Card>
  );
}

export function OverdraftDetails({ overdraft: o }: { overdraft: Overdraft }) {
  const { t } = useTranslation("accounts");
  const span =
    o.window_start && o.window_end ? t("overdraft.window", { start: formatDay(o.window_start), end: formatDay(o.window_end) }) : "";
  return (
    <Card title={t("overdraft.title")}>
      <Facts
        items={[
          [t("overdraft.limit"), <Known key="limit" value={o.limit} />],
          [t("overdraft.used"), <Money key="used" value={o.used} />],
          [t("overdraft.daysBelow"), [t("overdraft.days", { count: o.days_below }), span].filter(Boolean).join(" · ")],
          [t("overdraft.interest"), <Money key="interest" value={o.interest} />],
        ]}
      />
      <Note text={o.note} />
    </Card>
  );
}

export function DepositDetails({ deposit: d }: { deposit: Deposit }) {
  const { t } = useTranslation("accounts");
  return (
    <Card title={t("deposit.title")}>
      <Facts
        items={[
          [t("deposit.principal"), <Known key="principal" value={d.principal} />],
          [t("deposit.rate"), d.rate ? `%${formatRate(d.rate)}` : t("unknown")],
          [t("deposit.maturity"), d.maturity ? formatDay(d.maturity) : t("unknown")],
          [t("deposit.interest"), <Known key="interest" value={d.interest} />],
        ]}
      />
      <Note text={d.note} />
    </Card>
  );
}

export function HoldingDetails({ holding: h, title }: { holding: Holding; title: string }) {
  const { t } = useTranslation("accounts");
  const { t: tc } = useTranslation("common");
  return (
    <Card title={title}>
      <Facts
        items={[
          [t("holding.amount"), <Known key="amount" value={h.amount} />],
          [t("holding.value"), <Known key="value" value={h.value} />],
          [
            t("holding.rate"),
            h.rate
              ? [
                  t("holding.rateText", { rate: formatRate(h.rate) }),
                  h.rate_day ? rateOrigin(tc, h.rate_source, h.rate_day, "of") : "",
                ]
                  .filter(Boolean)
                  .join(" · ")
              : t("unknown"),
          ],
          [t("holding.cost"), <Known key="cost" value={h.cost} />],
          [t("holding.gain"), <Known key="gain" value={h.gain} />],
        ]}
      />
      <Note text={h.note} />
    </Card>
  );
}

export function BrokerageDetails({ brokerage: b }: { brokerage: Brokerage }) {
  const { t } = useTranslation("accounts");
  return (
    <Card title={t("brokerage.title")}>
      <Facts
        items={[
          [t("brokerage.asOf"), b.as_of ? formatDay(b.as_of) : t("unknown")],
          [t("brokerage.worth"), <Known key="worth" value={b.worth} />],
          [t("brokerage.cash"), <Known key="cash" value={b.cash} />],
          [t("brokerage.dividends"), t("brokerage.dividendsText", { amount: formatMoney(b.dividends), count: b.dividend_rows })],
        ]}
      />
      {b.securities.length > 0 ? (
        <>
          <h3 className="mt-4 mb-2 text-sm font-semibold">{t("brokerage.securities")}</h3>
          <Table>
            <caption className="sr-only">{t("brokerage.securities")}</caption>
            <thead>
              <tr>
                <Th>{t("brokerage.code")}</Th>
                <Th>{t("brokerage.name")}</Th>
                <Th className="text-right">{t("brokerage.quantity")}</Th>
                <Th className="text-right">{t("brokerage.value")}</Th>
                <Th>{t("brokerage.day")}</Th>
              </tr>
            </thead>
            <tbody>
              {b.securities.map((s) => (
                <tr key={s.code}>
                  <Td className="font-medium">{s.code}</Td>
                  <Td>{s.name}</Td>
                  <Td className="text-right tabular-nums">{formatRate(s.quantity)}</Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(s.value)}</Td>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(s.as_of)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      ) : null}
      <Note text={b.note} />
    </Card>
  );
}

export function LoanDetails({ loan, labels }: { loan: Loan; labels: Labels }) {
  const { t } = useTranslation("accounts");
  return (
    <Card title={t("loan.title")}>
      <Facts
        items={[
          [t("loan.remaining"), <Known key="remaining" value={loan.remaining} />],
          [t("loan.principalPaid"), <Money key="principal" value={loan.principal_paid} />],
          [t("loan.interestPaid"), <Money key="interest" value={loan.interest_paid} />],
        ]}
      />
      {loan.next.length > 0 ? (
        <>
          <h3 className="mt-4 mb-2 text-sm font-semibold">{t("loan.next")}</h3>
          <DueTable items={loan.next} caption={t("loan.next")} labels={labels} />
        </>
      ) : null}
      {loan.installments.length > 0 ? (
        <>
          <h3 className="mt-4 mb-2 text-sm font-semibold">{t("loan.paid")}</h3>
          <Table>
            <caption className="sr-only">{t("loan.paid")}</caption>
            <thead>
              <tr>
                <Th>{t("loan.day")}</Th>
                <Th className="text-right">{t("loan.principal")}</Th>
                <Th className="text-right">{t("loan.cost")}</Th>
              </tr>
            </thead>
            <tbody>
              {loan.installments.map((item) => (
                <tr key={`${item.day}-${item.document}`}>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(item.day)}</Td>
                  <Td className="text-right">
                    <Money value={item.principal} certainty={item.certainty} className="justify-end" />
                  </Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(item.cost)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      ) : null}
      <Note text={loan.note} />
    </Card>
  );
}
