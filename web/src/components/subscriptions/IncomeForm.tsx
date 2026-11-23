// "Her ay gelir" (F08): an income the user says comes every month goes into their rule file's `_düzenli_gelir` with
// its amount, its currency and its day, and comes off it with "Her ay gelir değil". A salary that just started has no
// three months of documents to make it a series: declared, the calendar and the forecast count it from its first
// payment, a foreign one at today's rate. As every rule edit, the change is shown before it is written.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePreviewRule, useSaveRule } from "../../api/queries";
import type { IncomeCandidate, IncomeRule, Money, NotIncomeRule, Series } from "../../api/types";
import { liraInput, parseLira } from "../../lib/amount";
import { formatMoney, formatMonth } from "../../lib/format";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { INPUT, RulePreview, SECTION } from "./EndForm";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

/** What the form starts from: a payer's newest month (a candidate's), or what is declared (a change). */
export interface IncomeStart {
  payee: string;
  amount: Money; // in the income's currency
  day: number;
  parts?: readonly Money[]; // the newest month's payments, said beside the amount
  month?: string;
}

export function startOf(candidate: IncomeCandidate): IncomeStart {
  return {
    payee: candidate.payee,
    amount: candidate.amount,
    day: candidate.day,
    parts: candidate.parts,
    month: candidate.month,
  };
}

interface IncomeFormProps {
  starts: readonly IncomeStart[]; // the payers to choose from; one when an income's declaration is changed
  onSaved: (said: string) => void;
}

/** "Her ay gelir…": the payer, the monthly amount in its currency and the day, previewed, written. */
export function IncomeForm({ starts, onSaved }: IncomeFormProps) {
  const { t } = useTranslation("subscriptions");
  const preview = usePreviewRule();
  const save = useSaveRule();
  const [payee, setPayee] = useState(starts[0]?.payee ?? "");
  const chosen = starts.find((start) => start.payee === payee) ?? starts[0];
  const [amount, setAmount] = useState(chosen ? liraInput(chosen.amount.minor) : "");
  const [day, setDay] = useState(String(chosen?.day ?? 1));
  const heading = useId();
  const payeeId = useId();
  const amountId = useId();
  const amountHint = useId();
  const dayId = useId();
  const dayHint = useId();
  if (!chosen) {
    return null;
  }
  const currency = chosen.amount.currency;
  const minor = parseLira(amount);
  const dayNumber = Number(day);
  const dayOk = Number.isInteger(dayNumber) && dayNumber >= 1 && dayNumber <= 31;
  const ready = minor !== null && minor > 0 && dayOk;
  const rule = (): IncomeRule => ({
    action: "income",
    merchant: chosen.payee,
    amount: ((minor ?? 0) / 100).toFixed(2),
    currency,
    day: dayNumber,
  });
  const choose = (next: string) => {
    const found = starts.find((start) => start.payee === next);
    setPayee(next);
    if (found) {
      setAmount(liraInput(found.amount.minor));
      setDay(String(found.day));
    }
    preview.reset();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready) {
      return;
    }
    save.reset();
    preview.mutate(rule());
  };
  const said = { payee: chosen.payee, amount: formatMoney({ minor: minor ?? 0, currency }), day: dayNumber };
  const saveIt = () =>
    save.mutate(rule(), {
      onSuccess: () => {
        preview.reset();
        onSaved(t("declare.saved", said));
      },
    });

  return (
    <section aria-labelledby={heading} className={SECTION}>
      <h3 id={heading} className="text-base font-semibold">
        {t("declare.title")}
      </h3>
      <p className={SMALL}>{t("declare.text")}</p>
      <form onSubmit={submit} className="flex flex-col gap-2 text-sm">
        {starts.length > 1 ? (
          <>
            <label htmlFor={payeeId}>{t("declare.payee")}</label>
            <select
              id={payeeId}
              value={chosen.payee}
              onChange={(event) => choose(event.target.value)}
              className={INPUT}
            >
              {starts.map((start) => (
                <option key={start.payee} value={start.payee}>
                  {start.payee}
                </option>
              ))}
            </select>
          </>
        ) : (
          <p className="font-medium">{chosen.payee}</p>
        )}
        <label htmlFor={amountId}>
          {t("declare.amount", { currency: currency === "TRY" ? t("declare.tl") : currency })}
        </label>
        <input
          id={amountId}
          inputMode="decimal"
          value={amount}
          aria-describedby={amountHint}
          aria-invalid={minor === null || minor <= 0}
          onChange={(event) => {
            setAmount(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        />
        <span id={amountHint} className={SMALL}>
          {chosen.parts && chosen.month
            ? t("declare.parts", {
                month: formatMonth(chosen.month),
                parts: chosen.parts.map((part) => formatMoney(part)).join(" + "),
              })
            : t("declare.amountHint")}
        </span>
        <label htmlFor={dayId}>{t("declare.day")}</label>
        <input
          id={dayId}
          type="number"
          min={1}
          max={31}
          value={day}
          aria-describedby={dayHint}
          aria-invalid={!dayOk}
          onChange={(event) => {
            setDay(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        />
        <span id={dayHint} className={SMALL}>
          {t("declare.dayHint")}
        </span>
        <Button type="submit" variant="secondary" className="self-start" disabled={!ready || preview.isPending}>
          {preview.isPending ? t("preview.previewing") : t("preview.preview")}
        </Button>
      </form>
      {preview.isError ? <Alert tone="critical" title={preview.error.message} /> : null}
      {preview.data ? (
        <RulePreview
          change={preview.data}
          effect={t("declare.effect", said)}
          saving={save.isPending}
          onSave={saveIt}
          onCancel={() => preview.reset()}
        />
      ) : null}
      {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
    </section>
  );
}

/** "Her ay gelir değil": the declaration taken off `_düzenli_gelir`, previewed, then written. */
export function UndeclareForm({ series, onSaved }: { series: Series; onSaved: (said: string) => void }) {
  const { t } = useTranslation("subscriptions");
  const preview = usePreviewRule();
  const save = useSaveRule();
  const heading = useId();
  const rule: NotIncomeRule = { action: "not_income", merchant: series.payee };
  const saveIt = () =>
    save.mutate(rule, {
      onSuccess: () => {
        preview.reset();
        onSaved(t("undeclare.saved", { payee: series.payee }));
      },
    });
  return (
    <section aria-labelledby={heading} className={SECTION}>
      <h3 id={heading} className="text-base font-semibold">
        {t("undeclare.title")}
      </h3>
      <p className="text-sm">{t("undeclare.text", { payee: series.payee })}</p>
      <Button
        variant="secondary"
        className="self-start"
        disabled={preview.isPending}
        onClick={() => {
          save.reset();
          preview.mutate(rule);
        }}
      >
        {preview.isPending ? t("preview.previewing") : t("preview.preview")}
      </Button>
      {preview.isError ? <Alert tone="critical" title={preview.error.message} /> : null}
      {preview.data ? (
        <RulePreview
          change={preview.data}
          effect={t("undeclare.effect", { payee: series.payee })}
          saving={save.isPending}
          onSave={saveIt}
          onCancel={() => preview.reset()}
        />
      ) : null}
      {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
    </section>
  );
}
