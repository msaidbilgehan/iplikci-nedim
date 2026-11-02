// One series in a panel over the list (F08), as ?seri=<id> opens it from this screen or another (the feed's warning,
// an account's page): what it is and what it means, every payment it rests on leading to its row on the İşlemler
// screen (and from there to its document), and "İptal ettim" or "Yeniden bekle". A payment after the month the user's
// rules give as the last is marked: the warning is about it.

import type { TFunction } from "i18next";
import { type ReactNode, type RefObject, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { useCategoryRules } from "../../api/queries";
import type { Labels, Series, Subscriptions } from "../../api/types";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Facts } from "../ui/Card";
import { Money } from "../ui/Money";
import { Say, ScreenLink } from "../ui/Say";
import { SidePanel } from "../ui/SidePanel";
import { Table, Td, Th } from "../ui/Table";
import { AgainForm, EndForm } from "./EndForm";
import { endedOf, isLate, isRunning, monthOf, offerOf, priceOf, seriesOf, STATUS_TONES } from "./series";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

/** Which control a panel opened for: "İptal ettim…" opens it at the month, "Yeniden bekle…" at its preview. */
export type Act = "end" | "again" | null;

type Rules = ReturnType<typeof useCategoryRules>;

interface SeriesPanelProps {
  id: string; // "" while no series is open
  found: Subscriptions;
  labels: Labels;
  rules: Rules;
  act: Act;
  onClose: () => void;
}

export function SeriesPanel({ id, found, labels, rules, act, onClose }: SeriesPanelProps) {
  const { t } = useTranslation("subscriptions");
  const month = useRef<HTMLSelectElement>(null);
  const again = useRef<HTMLButtonElement>(null);
  const income = found.income.find((series) => series.id === id);
  const series = income ?? found.series.find((s) => s.id === id);
  const target = act === "end" ? month : act === "again" ? again : undefined;
  return (
    <SidePanel
      open={id !== ""}
      onClose={onClose}
      title={series ? series.payee : t("panel.missing")}
      description={series ? <Summary series={series} labels={labels} /> : undefined}
      initialFocus={target}
    >
      {series ? (
        // Keyed by the series: another one's panel starts with its own form, not this one's choices.
        <Body
          key={series.id}
          series={series}
          isIncome={income !== undefined}
          found={found}
          labels={labels}
          rules={rules}
          targets={{ month, again }}
        />
      ) : (
        <p className="text-sm">{t("panel.missingText")}</p>
      )}
    </SidePanel>
  );
}

/** The line under the series' name: its status, its category and the account it is paid from. */
function Summary({ series, labels }: { series: Series; labels: Labels }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <Badge tone={STATUS_TONES[series.status]}>{labelOf(labels, "SeriesStatus", series.status)}</Badge>
      <span>{[series.category, series.account.label].filter(Boolean).join(" · ")}</span>
    </span>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {title}
      </h3>
      {children}
    </section>
  );
}

interface Targets {
  month: RefObject<HTMLSelectElement | null>;
  again: RefObject<HTMLButtonElement | null>;
}

interface BodyProps {
  series: Series;
  isIncome: boolean;
  found: Subscriptions;
  labels: Labels;
  rules: Rules;
  targets: Targets;
}

function Body({ series, isIncome, found, labels, rules, targets }: BodyProps) {
  const { t } = useTranslation("subscriptions");
  const cancelled = endedOf(rules.data, series.payee)?.month;
  const next = isRunning(series) && series.next_day && !isLate(series, found.as_of) ? series.next_day : "";
  return (
    <div className="flex flex-col gap-6">
      <Say next={next ? { link: { screen: "calendar", id: next, query: {} }, label: t("panel.calendar") } : null}>
        {sayOf(series, isIncome, found.as_of, labels, t)}
      </Say>
      <Facts items={factsOf(series, isIncome, found.as_of, labels, t)} />
      <Section title={t("panel.payments")}>
        <PaymentsTable series={series} cancelled={cancelled} labels={labels} />
      </Section>
      {isIncome ? null : <Actions series={series} found={found} labels={labels} rules={rules} targets={targets} />}
    </div>
  );
}

/** The simple view's sentence: what the series costs and when its next payment comes, or what its status means. */
function sayOf(series: Series, isIncome: boolean, asOf: string, labels: Labels, t: TFunction<"subscriptions">): string {
  // A payment after the user's cancellation is what to look at first; an ended series says why it reads as ended.
  if (!isRunning(series) || series.next_day === null || series.status === "paid_after_cancel") {
    return series.note || t("panel.sayEnded", { day: series.last_day });
  }
  if (isLate(series, asOf)) {
    return t("panel.sayLate", { day: series.next_day });
  }
  const amount = formatMoney(series.amount);
  if (isIncome) {
    return t("panel.sayIncome", { amount, day: series.next_day });
  }
  if (series.period !== "month") {
    const period = labelOf(labels, "SeriesPeriod", series.period);
    return t("panel.sayPeriodic", { period, amount, day: series.next_day });
  }
  return t("panel.sayMonthly", { amount, day: series.next_day });
}

/** What the series is, in name–value pairs; the amount and the next payment only while it runs. */
function factsOf(
  series: Series,
  isIncome: boolean,
  asOf: string,
  labels: Labels,
  t: TFunction<"subscriptions">,
): Array<[string, ReactNode]> {
  const facts: Array<[string, ReactNode]> = [
    [
      t("panel.status"),
      <span key="status" className="flex flex-col items-start gap-1">
        <Badge tone={STATUS_TONES[series.status]}>{labelOf(labels, "SeriesStatus", series.status)}</Badge>
        {series.note ? <span>{series.note}</span> : null}
      </span>,
    ],
    [t("panel.period"), labelOf(labels, "SeriesPeriod", series.period)],
  ];
  if (isRunning(series)) {
    const perPeriod = series.period === "month" ? t("panel.monthly") : t("panel.perPeriod");
    const name = isIncome ? t("panel.expected") : perPeriod;
    const median = isIncome ? t("series.incomeMedian") : t("series.median");
    const moved = isIncome || series.amount.minor !== series.last_amount.minor;
    facts.push([
      name,
      <span key="amount">
        {formatMoney(series.amount)}
        {moved ? <span className={`block ${SMALL}`}>{median}</span> : null}
      </span>,
    ]);
  }
  facts.push([t("panel.last"), `${formatDay(series.last_day)} · ${formatMoney(series.last_amount)}`]);
  if (isRunning(series) && series.next_day) {
    facts.push([
      t("panel.next"),
      isLate(series, asOf)
        ? t("series.nextLate", { day: formatDay(series.next_day) })
        : `${formatDay(series.next_day)} · ${formatMoney(series.amount)}`,
    ]);
  }
  if (series.price_change) {
    facts.push([t("panel.price"), priceOf(series, t)]);
  }
  facts.push([
    t("panel.account"),
    <ScreenLink key="account" link={{ screen: "account", id: series.account.id, query: {} }}>
      {series.account.label}
    </ScreenLink>,
  ]);
  if (series.category) {
    facts.push([t("panel.category"), series.category]);
  }
  if (series.necessity) {
    facts.push([t("panel.necessity"), labelOf(labels, "Necessity", series.necessity)]);
  }
  return facts;
}

interface PaymentsTableProps {
  series: Series;
  cancelled: string | undefined; // the month the user's rules give as the last payment's
  labels: Labels;
}

/** The rows the series rests on, newest first: each day leads to its row, which leads to its document. */
function PaymentsTable({ series, cancelled, labels }: PaymentsTableProps) {
  const { t } = useTranslation("subscriptions");
  const payments = [...series.payments].sort((a, b) => b.day.localeCompare(a.day));
  return (
    <Table>
      <caption className="sr-only">{t("panel.paymentsCaption", { payee: series.payee })}</caption>
      <thead>
        <tr>
          <Th>{t("panel.day")}</Th>
          <Th className="text-right">{t("panel.amount")}</Th>
          <Th>{t("panel.document")}</Th>
        </tr>
      </thead>
      <tbody>
        {payments.map((payment) => (
          <tr key={payment.fingerprint || `${payment.day}-${payment.document}`}>
            <Td className="whitespace-nowrap">
              {payment.fingerprint ? (
                <ScreenLink link={{ screen: "transaction", id: payment.fingerprint, query: {} }}>
                  {formatDay(payment.day)}
                </ScreenLink>
              ) : (
                formatDay(payment.day)
              )}
              {cancelled && monthOf(payment.day) > cancelled ? (
                <span className="mt-1 block">
                  <Badge tone="warning">{t("panel.afterCancel")}</Badge>
                </span>
              ) : null}
            </Td>
            <Td className="text-right">
              <Money value={payment.amount} certainty={payment.certainty} className="justify-end" />
            </Td>
            <Td className="min-w-40 wrap-break-word">
              {payment.document || <span className={SMALL}>{t("panel.noDocument")}</span>}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

interface ActionsProps {
  series: Series;
  found: Subscriptions;
  labels: Labels;
  rules: Rules;
  targets: Targets;
}

/**
 * "İptal ettim", "Yeniden bekle", or both when payments came after the month the user gave; what was saved stays said
 * while the panel is open.
 */
function Actions({ series, found, labels, rules, targets }: ActionsProps) {
  const { t } = useTranslation("subscriptions");
  const [said, setSaid] = useState("");
  if (rules.isPending) {
    return <Loading />;
  }
  if (rules.isError) {
    return <Failure error={rules.error} onRetry={() => void rules.refetch()} />;
  }
  const entry = endedOf(rules.data, series.payee);
  const offer = offerOf(series, rules.data);
  // A form starts afresh once its change is in the rules: the entry it made or took away changes its key.
  const version = entry ? `${entry.merchant}:${entry.month}` : "";
  return (
    <div className="flex flex-col gap-3">
      {said ? <Alert tone="good" title={said} live /> : null}
      {entry && (offer === "again" || offer === "both") ? (
        <AgainForm key={`again:${version}`} series={series} entry={entry} target={targets.again} onSaved={setSaid} />
      ) : null}
      {offer === "end" || offer === "both" ? (
        <EndForm
          key={`end:${version}`}
          series={series}
          asOf={found.as_of}
          others={seriesOf(found.series, series.payee) - 1}
          labels={labels}
          changing={offer === "both"}
          target={targets.month}
          onSaved={setSaid}
        />
      ) : null}
      {entry && offer === "shipped" ? (
        <p className="text-sm">{t("end.shipped", { month: formatMonth(entry.month) })}</p>
      ) : null}
    </div>
  );
}
