// A row split into parts, each counted under its own category (F04's "bölme"): a market receipt that was partly
// cleaning goods, a bill paid for two. The parts add up to the row to the kuruş: the user types the amounts of the
// second part on and the first part takes what is left, so the sum never has to be worked out by hand. Two to twenty
// parts; a part's necessity is its category's unless the user chooses another. Joining the row again asks first.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useCorrection } from "../../api/queries";
import type { Category, Labels, Necessity, Row } from "../../api/types";
import { liraInput, parseLira } from "../../lib/amount";
import { cn } from "../../lib/cn";
import { formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/Dialog";
import { CategorySelect } from "./CategorySelect";

export const MAX_PARTS = 20; // annotate.MAX_PARTS
const NECESSITIES: readonly Necessity[] = ["required", "optional", "unnecessary", "unknown"];
const FIELD = [
  "min-h-11 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");
const INVALID = "border-red-700 dark:border-red-400";
const ERROR = "text-sm text-red-800 dark:text-red-200";
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

interface Draft {
  key: number; // the part's own, so React keeps each part's fields as parts come and go
  amount: string; // as typed; the first part's is not typed: it takes what the others leave
  category: string;
  necessity: Necessity | "";
}

interface Errors {
  amounts: Record<number, string>;
  categories: Record<number, string>;
  rest: string;
}

const NO_ERRORS: Errors = { amounts: {}, categories: {}, rest: "" };

function without(errors: Record<number, string>, key: number): Record<number, string> {
  return Object.fromEntries(Object.entries(errors).filter(([found]) => Number(found) !== key));
}

/** A part's necessity as the editor shows it: its own only when it differs from what its category's rules give. */
function ownNecessity(part: Row, categories: readonly Category[]): Necessity | "" {
  const rules = categories.find((category) => category.name === part.category)?.necessity ?? "unknown";
  return part.necessity !== null && part.necessity !== rules ? part.necessity : "";
}

function draftsOf(row: Row, parts: readonly Row[], categories: readonly Category[]): Draft[] {
  if (parts.length > 0) {
    return parts.map((part, index) => ({
      key: index,
      amount: liraInput(part.amount.minor),
      category: part.category,
      necessity: ownNecessity(part, categories),
    }));
  }
  const known = categories.some((category) => category.name === row.category);
  return [
    { key: 0, amount: "", category: known ? row.category : "", necessity: "" },
    { key: 1, amount: "", category: "", necessity: "" },
  ];
}

/**
 * What the parts after the first add up to, in kuruş: a part with no amount typed yet adds nothing, so the first part
 * starts with the whole row; null while one of them holds what is no amount.
 */
function othersOf(drafts: readonly Draft[]): number | null {
  let sum = 0;
  for (const draft of drafts.slice(1)) {
    if (!draft.amount.trim()) {
      continue;
    }
    const minor = parseLira(draft.amount);
    if (minor === null) {
      return null;
    }
    sum += minor;
  }
  return sum;
}

interface SplitEditorProps {
  fingerprint: string; // the row's or one of its parts': either means the row
  row: Row; // the whole row
  parts: readonly Row[]; // its parts now; none before it is split
  categories: readonly Category[];
  labels: Labels;
  onCancel?: () => void; // a row not split yet: the editor closes without a change
}

export function SplitEditor({ fingerprint, row, parts, categories, labels, onCancel }: SplitEditorProps) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  const join = useCorrection(fingerprint);
  const [drafts, setDrafts] = useState<Draft[]>(() => draftsOf(row, parts, categories));
  const [errors, setErrors] = useState<Errors>(NO_ERRORS);
  const [said, setSaid] = useState("");
  const [joining, setJoining] = useState(false);
  const [nextKey, setNextKey] = useState(drafts.length);
  const heading = useId();
  const isSplit = parts.length > 0;
  const total = row.amount.minor;
  const others = othersOf(drafts);
  const rest = others === null ? null : total - others;

  const change = (key: number, next: Partial<Draft>) => {
    setDrafts((was) => was.map((draft) => (draft.key === key ? { ...draft, ...next } : draft)));
    // What was wrong with the part goes once it is changed; the rest is worked out again from the amounts.
    setErrors((was) => ({
      amounts: "amount" in next ? without(was.amounts, key) : was.amounts,
      categories: "category" in next ? without(was.categories, key) : was.categories,
      rest: "amount" in next ? "" : was.rest,
    }));
    setSaid("");
    correction.reset();
  };
  const add = () => {
    setDrafts((was) => [...was, { key: nextKey, amount: "", category: "", necessity: "" }]);
    setNextKey(nextKey + 1);
  };
  const remove = (key: number) => setDrafts((was) => was.filter((draft) => draft.key !== key));

  const check = (): Errors => {
    const found: Errors = { amounts: {}, categories: {}, rest: "" };
    drafts.forEach((draft, index) => {
      const minor = parseLira(draft.amount);
      if (index > 0 && (minor === null || minor <= 0)) {
        found.amounts[draft.key] = t("split.errorAmount");
      }
      if (!draft.category) {
        found.categories[draft.key] = t("split.errorCategory");
      }
    });
    if (rest !== null && rest <= 0) {
      found.rest = t("split.errorRest");
    }
    return found;
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = check();
    setErrors(found);
    const failed =
      Object.keys(found.amounts).length > 0 || Object.keys(found.categories).length > 0 || found.rest !== "";
    if (failed || rest === null) {
      return;
    }
    const minors = [rest, ...drafts.slice(1).map((draft) => parseLira(draft.amount) ?? 0)];
    correction.mutate(
      {
        parts: drafts.map((draft, index) => ({
          minor: minors[index] ?? 0,
          category: draft.category,
          ...(draft.necessity ? { necessity: draft.necessity } : {}),
        })),
      },
      { onSuccess: () => setSaid(t("correct.settling")) },
    );
  };

  return (
    <section aria-labelledby={heading} className="flex flex-col gap-3">
      <h4 id={heading} className="font-medium">
        {t("split.title")}
      </h4>
      <p className={SMALL}>{t("split.intro", { amount: formatMoney(row.amount) })}</p>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        {drafts.map((draft, index) => (
          <Part
            key={draft.key}
            number={index + 1}
            draft={draft}
            errors={{ amount: errors.amounts[draft.key] ?? "", category: errors.categories[draft.key] ?? "" }}
            categories={categories}
            labels={labels}
            onChange={(next) => change(draft.key, next)}
            {...(index === 0 ? { rest: { minor: rest, error: errors.rest } } : {})}
            {...(drafts.length > 2 && index > 0 ? { onRemove: () => remove(draft.key) } : {})}
          />
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={drafts.length >= MAX_PARTS} onClick={add}>
            {t("split.add")}
          </Button>
          {drafts.length >= MAX_PARTS ? <span className={SMALL}>{t("split.max", { max: MAX_PARTS })}</span> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={correction.isPending}>
            {correction.isPending ? t("split.saving") : isSplit ? t("split.saveChange") : t("split.save")}
          </Button>
          {onCancel ? (
            <Button variant="secondary" onClick={onCancel}>
              {t("split.cancel")}
            </Button>
          ) : null}
          {isSplit ? (
            <Button variant="secondary" onClick={() => setJoining(true)}>
              {t("split.join")}
            </Button>
          ) : null}
        </div>
      </form>
      <p aria-live="polite" className="text-sm">
        {said}
      </p>
      {correction.isError ? <Alert tone="critical" title={correction.error.message} /> : null}
      {join.isError ? <Alert tone="critical" title={join.error.message} /> : null}
      <ConfirmDialog
        open={joining}
        onOpenChange={setJoining}
        title={t("split.joinTitle")}
        description={t("split.joinText")}
        confirmLabel={t("split.join")}
        variant="danger"
        busy={join.isPending}
        onConfirm={() =>
          join.mutate(
            { parts: [] },
            {
              onSuccess: () => setSaid(t("correct.settling")),
              onSettled: () => setJoining(false),
            },
          )
        }
      />
    </section>
  );
}

interface PartProps {
  number: number;
  draft: Draft;
  rest?: { minor: number | null; error: string }; // the first part's amount: what the others leave, once known
  errors: { amount: string; category: string };
  categories: readonly Category[];
  labels: Labels;
  onChange: (next: Partial<Draft>) => void;
  onRemove?: () => void;
}

/** One part: its amount (the first part's is what is left), its category and its necessity. */
function Part({ number, draft, rest, errors, categories, labels, onChange, onRemove }: PartProps) {
  const { t } = useTranslation("transactions");
  const amountId = useId();
  const amountErrorId = useId();
  const restId = useId();
  const restErrorId = useId();
  const categoryErrorId = useId();
  const necessityId = useId();
  return (
    <fieldset className="flex flex-col gap-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700">
      <legend className="px-1 text-sm font-medium">{t("split.part", { number })}</legend>
      <div className="flex flex-wrap items-start gap-3">
        {rest ? (
          <div className="flex flex-col gap-1 text-sm">
            <span id={restId}>{t("split.rest")}</span>
            {/* An output is a status: a screen reader hears what is left as the other amounts are typed. */}
            <output
              aria-labelledby={restId}
              aria-describedby={rest.error ? restErrorId : undefined}
              className={cn("min-h-11 py-2 font-medium tabular-nums", rest.error && "text-red-800 dark:text-red-200")}
            >
              {rest.minor === null
                ? t("split.restUnknown")
                : rest.minor <= 0
                  ? t("split.restNone")
                  : formatMoney({ minor: rest.minor, currency: "TRY" })}
            </output>
            {rest.error ? (
              <p id={restErrorId} className={ERROR}>
                {rest.error}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor={amountId}>{t("split.amount")}</label>
            <input
              id={amountId}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={draft.amount}
              placeholder="250,00"
              onChange={(event) => onChange({ amount: event.target.value })}
              aria-invalid={errors.amount ? true : undefined}
              aria-describedby={errors.amount ? amountErrorId : undefined}
              className={cn(FIELD, "w-36", errors.amount && INVALID)}
            />
            {errors.amount ? (
              <p id={amountErrorId} className={ERROR}>
                {errors.amount}
              </p>
            ) : null}
          </div>
        )}
        <CategorySelect
          label={t("split.category")}
          categories={categories}
          value={draft.category}
          placeholder={t("correct.choose")}
          onChange={(category) => onChange({ category })}
          {...(errors.category ? { error: { text: errors.category, id: categoryErrorId } } : {})}
        />
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={necessityId}>{t("split.necessity")}</label>
          <select
            id={necessityId}
            value={draft.necessity}
            onChange={(event) => onChange({ necessity: event.target.value as Necessity | "" })}
            className={FIELD}
          >
            <option value="">{t("split.necessityRules")}</option>
            {NECESSITIES.map((code) => (
              <option key={code} value={code}>
                {labelOf(labels, "Necessity", code)}
              </option>
            ))}
          </select>
        </div>
        {onRemove ? (
          <Button variant="secondary" className="self-end" onClick={onRemove}>
            {t("split.remove", { number })}
          </Button>
        ) : null}
      </div>
    </fieldset>
  );
}
