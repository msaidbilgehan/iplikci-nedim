// The regular income (F08): what each is expected to bring (the median of its last three, or what the user declared),
// when it last came and when it comes next, and "Artık gelmiyor…" for one the user knows has stopped (or "Yeniden
// bekle…" for one they ended). An income the user says comes every month (`_düzenli_gelir`) says so, with "Değiştir…"
// and "Her ay gelir değil…". The name opens its panel with the payments it rests on.

import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { CategoryRules, Labels, Series } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney } from "../../lib/format";
import { Detailed, Simple } from "../Preferences";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Table, Td, Th } from "../ui/Table";
import { IncomeForm, UndeclareForm } from "./IncomeForm";
import { isLate, isRunning, STATUS_TONES, statusOf } from "./series";
import { CARD, CARD_ACTIONS, NAME, type Opening, SeriesActions, SeriesFoot, SMALL } from "./SeriesList";

type Change = "change" | "remove";

/** Which declared income has a form open, and what the last save said: one at a time on the list. */
function useChanges() {
  const [open, setOpen] = useState<{ id: string; change: Change } | null>(null);
  const [said, setSaid] = useState("");
  const toggle = (id: string, change: Change) => {
    setSaid("");
    setOpen((was) => (was?.id === id && was.change === change ? null : { id, change }));
  };
  const saved = (text: string) => {
    setOpen(null);
    setSaid(text);
  };
  return { open, said, toggle, saved };
}

/** Where an expected amount comes from: the last three incomes' median, or the user's word (at today's rate). */
function basisOf(series: Series, t: ReturnType<typeof useTranslation<"subscriptions">>["t"]): string {
  if (!series.declared) {
    return t("series.incomeMedian");
  }
  return series.declared.amount.currency === "TRY" ? t("income.declaredOwn") : t("income.declaredRate");
}

interface DeclaredProps {
  series: Series;
  open: Change | null;
  onToggle: (change: Change) => void;
}

/** A declared income's two buttons: change what it brings and when, or take the declaration back. */
function DeclaredButtons({ series, open, onToggle }: DeclaredProps) {
  const { t } = useTranslation("subscriptions");
  return (
    <>
      <Button
        variant="quiet"
        className="whitespace-nowrap"
        aria-expanded={open === "change"}
        aria-label={t("income.changeOf", { payee: series.payee })}
        onClick={() => onToggle("change")}
      >
        {t("income.change")}
      </Button>
      <Button
        variant="quiet"
        className="whitespace-nowrap"
        aria-expanded={open === "remove"}
        aria-label={t("income.removeOf", { payee: series.payee })}
        onClick={() => onToggle("remove")}
      >
        {t("income.remove")}
      </Button>
    </>
  );
}

/** The form a declared income's button opened. */
interface DeclaredFormProps {
  series: Series;
  change: Change;
  onSaved: (said: string) => void;
}

function DeclaredForm({ series, change, onSaved }: DeclaredFormProps) {
  const declared = series.declared;
  if (!declared) {
    return null;
  }
  return change === "change" ? (
    <IncomeForm starts={[{ payee: series.payee, amount: declared.amount, day: declared.day }]} onSaved={onSaved} />
  ) : (
    <UndeclareForm series={series} onSaved={onSaved} />
  );
}

interface IncomeListProps {
  income: readonly Series[];
  asOf: string;
  labels: Labels;
  rules: CategoryRules | undefined; // the `_biten` entries: which income may be ended, which expected again
  opening: Opening;
}

export function IncomeList({ income, asOf, labels, rules, opening }: IncomeListProps) {
  const { t } = useTranslation("subscriptions");
  const changes = useChanges();
  const openOf = (series: Series) => (changes.open?.id === series.id ? changes.open.change : null);
  const nextOf = (series: Series) => {
    if (!series.next_day) {
      return "";
    }
    return isLate(series, asOf)
      ? t("series.nextLate", { day: formatDay(series.next_day) })
      : t("series.nextDay", { day: formatDay(series.next_day) });
  };
  return (
    <>
      {changes.said ? <Alert tone="good" title={changes.said} live /> : null}
      <Simple>
        <ul aria-label={t("income.caption")} className="grid gap-3 md:grid-cols-2">
          {income.map((series) => (
            <li key={series.id} className={CARD}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <Link to={opening.hrefOf(series.id)} className={NAME}>
                  {series.payee}
                </Link>
                {series.status === "active" ? null : (
                  <Badge tone={STATUS_TONES[series.status]}>{statusOf(series, "income", labels, t)}</Badge>
                )}
              </div>
              <p className={SMALL}>{[series.category, series.account.label].filter(Boolean).join(" · ")}</p>
              {series.declared ? (
                <p className={SMALL}>
                  {t("income.declared", { amount: formatMoney(series.declared.amount), day: series.declared.day })}
                </p>
              ) : null}
              <ul className="flex flex-col gap-0.5">
                {isRunning(series) ? (
                  <li>
                    <span className="text-base font-semibold">
                      {t("series.expected", { amount: formatMoney(series.amount) })}
                    </span>
                    <span className={SMALL}> ({basisOf(series, t)})</span>
                  </li>
                ) : null}
                <li>
                  {t("series.lastIncome", { day: formatDay(series.last_day), amount: formatMoney(series.last_amount) })}
                </li>
                {series.next_day ? <li>{nextOf(series)}</li> : null}
              </ul>
              {series.note ? <p className={SMALL}>{series.note}</p> : null}
              {series.declared ? (
                <div className={CARD_ACTIONS}>
                  <DeclaredButtons
                    series={series}
                    open={openOf(series)}
                    onToggle={(change) => changes.toggle(series.id, change)}
                  />
                  <SeriesActions series={series} wording="income" rules={rules} opening={opening} quiet />
                </div>
              ) : (
                <SeriesFoot series={series} wording="income" rules={rules} opening={opening} />
              )}
              {openOf(series) ? (
                <DeclaredForm series={series} change={openOf(series) ?? "change"} onSaved={changes.saved} />
              ) : null}
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("income.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("table.payer")}</Th>
              <Th>{t("table.account")}</Th>
              <Th className="text-right">{t("table.expected")}</Th>
              <Th>{t("table.lastIncome")}</Th>
              <Th>{t("table.nextIncome")}</Th>
              <Th>{t("table.payments")}</Th>
              <Th>{t("table.actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {income.map((series) => (
              <Fragment key={series.id}>
                <tr>
                  <Td className="min-w-40">
                    <Link to={opening.hrefOf(series.id)} className={NAME}>
                      {series.payee}
                    </Link>
                    {series.status === "active" ? null : (
                      <span className="mt-1 block">
                        <Badge tone={STATUS_TONES[series.status]}>{statusOf(series, "income", labels, t)}</Badge>
                      </span>
                    )}
                    {series.declared ? (
                      <span className={cn("mt-1 block", SMALL)}>
                        {t("income.declared", {
                          amount: formatMoney(series.declared.amount),
                          day: series.declared.day,
                        })}
                      </span>
                    ) : null}
                    {series.note ? <span className={cn("mt-1 block", SMALL)}>{series.note}</span> : null}
                  </Td>
                  <Td className="min-w-36">{series.account.label}</Td>
                  <Td className="text-right whitespace-nowrap tabular-nums">
                    {isRunning(series) ? (
                      <>
                        {formatMoney(series.amount)}
                        <span className={cn("block", SMALL)}>{basisOf(series, t)}</span>
                      </>
                    ) : (
                      t("table.none")
                    )}
                  </Td>
                  <Td className="whitespace-nowrap">
                    {formatDay(series.last_day)}
                    <span className={cn("block tabular-nums", SMALL)}>{formatMoney(series.last_amount)}</span>
                  </Td>
                  <Td className="whitespace-nowrap">
                    {series.next_day ? formatDay(series.next_day) : t("table.none")}
                    {isLate(series, asOf) ? <span className={cn("block", SMALL)}>{t("table.late")}</span> : null}
                  </Td>
                  <Td className="whitespace-nowrap">{t("series.payments", { count: series.payments.length })}</Td>
                  <Td>
                    <div className="flex flex-col items-start gap-1">
                      {series.declared ? (
                        <DeclaredButtons
                          series={series}
                          open={openOf(series)}
                          onToggle={(change) => changes.toggle(series.id, change)}
                        />
                      ) : null}
                      <SeriesActions series={series} wording="income" rules={rules} opening={opening} />
                    </div>
                  </Td>
                </tr>
                {openOf(series) ? (
                  <tr>
                    <Td colSpan={7}>
                      <DeclaredForm series={series} change={openOf(series) ?? "change"} onSaved={changes.saved} />
                    </Td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </>
  );
}
