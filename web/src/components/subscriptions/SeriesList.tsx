// A section's series (F08): the simple view gives each a card — its status, what it costs while it runs (a month's
// amount, or a period's for a periodic one, never turned into a month's), its last and next payment, its price change
// and what the user may do; the detailed view a table of the same values. The name opens the series' panel with its
// payments.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { CategoryRules, Labels, Series } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Table, Td, Th } from "../ui/Table";
import { isLate, isRunning, monthOf, offerOf, priceOf, STATUS_TONES } from "./series";

export const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
export const CARD = cn(
  "flex flex-col gap-1.5 rounded-lg border border-zinc-200 bg-white p-3 text-sm",
  "dark:border-zinc-700 dark:bg-zinc-900",
);
export const NAME = cn(
  "min-w-0 rounded font-medium underline decoration-1 underline-offset-2 hover:decoration-2 wrap-break-word",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export type SeriesKind = "monthly" | "periodic" | "ended";

/** What opening a series' panel needs: its address, and the panel opened at one of its forms. */
export interface Opening {
  hrefOf: (id: string) => string;
  onAct: (id: string, act: "end" | "again") => void;
}

interface SeriesListProps {
  series: readonly Series[];
  kind: SeriesKind;
  caption: string;
  asOf: string;
  labels: Labels;
  rules: CategoryRules | undefined; // the `_biten` entries: which series may be ended, which expected again
  opening: Opening;
}

export function SeriesList(props: SeriesListProps) {
  const { series, kind, caption, asOf, labels, rules, opening } = props;
  return (
    <>
      <Simple>
        <ul aria-label={caption} className="grid gap-3 md:grid-cols-2">
          {series.map((s) => (
            <SeriesCard key={s.id} series={s} kind={kind} asOf={asOf} labels={labels} rules={rules} opening={opening} />
          ))}
        </ul>
      </Simple>
      <Detailed>
        <SeriesTable {...props} />
      </Detailed>
    </>
  );
}

interface ActionsProps {
  series: Series;
  rules: CategoryRules | undefined;
  opening: Opening;
}

/** "İptal ettim…" or "Yeniden bekle…", each opening the series' panel at its form, where the change is previewed. */
function SeriesActions({ series, rules, opening }: ActionsProps) {
  const { t } = useTranslation("subscriptions");
  const offer = offerOf(series, rules);
  if (offer === "end") {
    return (
      <Button
        variant="secondary"
        className="whitespace-nowrap"
        aria-label={t("series.endOf", { payee: series.payee })}
        onClick={() => opening.onAct(series.id, "end")}
      >
        {t("series.end")}
      </Button>
    );
  }
  if (offer === "again" || offer === "both") {
    return (
      <Button
        variant="secondary"
        className="whitespace-nowrap"
        aria-label={t("series.againOf", { payee: series.payee })}
        onClick={() => opening.onAct(series.id, "again")}
      >
        {t("series.again")}
      </Button>
    );
  }
  return null;
}

/** What it costs while it runs: a month's amount, a periodic one's per period; the median when the amounts move. */
function AmountLine({ series, labels }: { series: Series; labels: Labels }) {
  const { t } = useTranslation("subscriptions");
  const amount = formatMoney(series.amount);
  const moved = series.amount.minor !== series.last_amount.minor;
  return (
    <li>
      <span className="font-semibold">
        {series.period === "month"
          ? t("series.monthly", { amount })
          : t("series.perPeriod", { period: labelOf(labels, "SeriesPeriod", series.period), amount })}
      </span>
      {moved ? <span className={SMALL}> ({t("series.median")})</span> : null}
    </li>
  );
}

interface SeriesCardProps {
  series: Series;
  kind: SeriesKind;
  asOf: string;
  labels: Labels;
  rules: CategoryRules | undefined;
  opening: Opening;
}

function SeriesCard({ series, kind, asOf, labels, rules, opening }: SeriesCardProps) {
  const { t } = useTranslation("subscriptions");
  const running = isRunning(series);
  const where = [series.category, series.account.label];
  if (kind !== "monthly") {
    where.push(labelOf(labels, "SeriesPeriod", series.period));
  }
  return (
    <li className={CARD}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Link to={opening.hrefOf(series.id)} className={NAME}>
          {series.payee}
        </Link>
        <Badge tone={STATUS_TONES[series.status]}>{labelOf(labels, "SeriesStatus", series.status)}</Badge>
      </div>
      <p className={SMALL}>{where.filter(Boolean).join(" · ")}</p>
      <ul className="flex flex-col gap-0.5">
        {running ? <AmountLine series={series} labels={labels} /> : null}
        <li>{t("series.last", { day: formatDay(series.last_day), amount: formatMoney(series.last_amount) })}</li>
        {running && series.next_day ? (
          <li>
            {isLate(series, asOf)
              ? t("series.nextLate", { day: formatDay(series.next_day) })
              : t("series.next", { day: formatDay(series.next_day), amount: formatMoney(series.amount) })}
          </li>
        ) : null}
        {series.price_change ? <li>{priceOf(series, t)}</li> : null}
      </ul>
      {series.note ? <p className={SMALL}>{series.note}</p> : null}
      <div className="mt-1 flex flex-wrap gap-2">
        <SeriesActions series={series} rules={rules} opening={opening} />
      </div>
    </li>
  );
}

function SeriesTable({ series, kind, caption, asOf, labels, rules, opening }: SeriesListProps) {
  const { t } = useTranslation("subscriptions");
  const none = t("table.none");
  const total = series.reduce((sum, s) => sum + s.amount.minor, 0);
  const currency = series[0]?.amount.currency ?? "TRY";
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <Th>{t("table.payee")}</Th>
          <Th>{t("table.status")}</Th>
          {kind === "monthly" ? null : <Th>{t("table.period")}</Th>}
          {kind === "ended" ? null : (
            <Th className="text-right">{kind === "monthly" ? t("table.monthly") : t("table.perPeriod")}</Th>
          )}
          <Th>{t("table.last")}</Th>
          {kind === "ended" ? null : <Th>{t("table.next")}</Th>}
          <Th>{t("table.price")}</Th>
          <Th>{t("table.payments")}</Th>
          <Th>{t("table.actions")}</Th>
        </tr>
      </thead>
      <tbody>
        {series.map((s) => (
          <tr key={s.id}>
            <Td className="min-w-40">
              <Link to={opening.hrefOf(s.id)} className={NAME}>
                {s.payee}
              </Link>
              <span className={cn("block", SMALL)}>{s.category}</span>
              <span className={cn("block", SMALL)}>{s.account.label}</span>
            </Td>
            <Td className="min-w-36">
              <Badge tone={STATUS_TONES[s.status]}>{labelOf(labels, "SeriesStatus", s.status)}</Badge>
              {s.note ? <span className={cn("mt-1 block", SMALL)}>{s.note}</span> : null}
            </Td>
            {kind === "monthly" ? null : <Td>{labelOf(labels, "SeriesPeriod", s.period)}</Td>}
            {kind === "ended" ? null : (
              <Td className="text-right whitespace-nowrap tabular-nums">
                {formatMoney(s.amount)}
                {s.amount.minor !== s.last_amount.minor ? (
                  <span className={cn("block", SMALL)}>{t("series.median")}</span>
                ) : null}
              </Td>
            )}
            <Td className="whitespace-nowrap">
              {formatDay(s.last_day)}
              <span className={cn("block tabular-nums", SMALL)}>{formatMoney(s.last_amount)}</span>
            </Td>
            {kind === "ended" ? null : (
              <Td className="whitespace-nowrap">
                {s.next_day ? formatDay(s.next_day) : none}
                {s.next_day ? (
                  <span className={cn("block tabular-nums", SMALL)}>
                    {isLate(s, asOf) ? t("table.late") : formatMoney(s.amount)}
                  </span>
                ) : null}
              </Td>
            )}
            <Td className="whitespace-nowrap">
              {s.price_change ? (
                <>
                  {formatMoney(s.price_change.before)} → {formatMoney(s.price_change.after)}
                  <span className={cn("block", SMALL)}>
                    {t("table.priceSince", { since: monthOf(s.price_change.since) })}
                  </span>
                </>
              ) : (
                none
              )}
            </Td>
            <Td className="whitespace-nowrap">{t("series.payments", { count: s.payments.length })}</Td>
            <Td>
              <SeriesActions series={s} rules={rules} opening={opening} />
            </Td>
          </tr>
        ))}
      </tbody>
      {kind === "monthly" ? (
        <tfoot>
          <tr>
            <Th scope="row" colSpan={2} className="border-b-0">
              {t("table.monthlyTotal")}
            </Th>
            <Td className="border-b-0 text-right font-semibold whitespace-nowrap tabular-nums">
              {formatMoney({ minor: total, currency })}
            </Td>
            <Td colSpan={5} className="border-b-0" />
          </tr>
        </tfoot>
      ) : null}
    </Table>
  );
}
