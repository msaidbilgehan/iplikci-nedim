// "İptal ettim" and "Yeniden bekle" (F08): a payment the user cancelled goes into their rule file's `_biten` with the
// month of its last payment, and comes off it when it is expected again (F15). As every rule edit, the change is shown
// before it is written: the rule file's difference and what it does. A payment after that month then reads as
// "İptalden sonra ödeme var", a warning.

import { type FormEvent, type RefObject, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePreviewRule, useSaveRule } from "../../api/queries";
import type { EndedPayment, EndedRule, Labels, NotEndedRule, RuleChange, Series } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { RuleDiff } from "./RuleDiff";
import { monthChoices, monthOf, paidAfter } from "./series";

const INPUT = cn(
  "min-h-11 w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const SECTION = "flex flex-col gap-3 rounded-md border border-zinc-200 p-3 dark:border-zinc-700";

interface PreviewProps {
  change: RuleChange;
  effect: string; // what saving does, in a sentence
  saving: boolean;
  onSave: () => void;
  onCancel: () => void;
}

/** A previewed rule edit: the difference it makes in the rule file and what it does, then "Kaydet". */
function RulePreview({ change, effect, saving, onSave, onCancel }: PreviewProps) {
  const { t } = useTranslation("subscriptions");
  const caption = useId();
  if (!change.diff) {
    return <p className="text-sm">{t("preview.noChange")}</p>;
  }
  return (
    <div className="flex flex-col gap-2 text-sm">
      {/* Named by its caption in words, as not every reader takes a figure's name from it. */}
      <figure aria-labelledby={caption} className="flex flex-col gap-1">
        <figcaption id={caption} className="font-medium">
          {t("preview.change")}
        </figcaption>
        <RuleDiff diff={change.diff} />
      </figure>
      <p>{effect}</p>
      <div className="flex flex-wrap gap-2">
        <Button disabled={saving} onClick={onSave}>
          {saving ? t("preview.saving") : t("preview.save")}
        </Button>
        <Button variant="secondary" disabled={saving} onClick={onCancel}>
          {t("preview.cancel")}
        </Button>
      </div>
    </div>
  );
}

interface EndFormProps {
  series: Series;
  asOf: string; // the documents' end: a cancellation may name the month after it
  others: number; // the payee's series besides this one, which the cancellation reaches too
  labels: Labels;
  changing: boolean; // the month the user gave before is changed: payments came after it
  target?: RefObject<HTMLSelectElement | null> | undefined; // what "İptal ettim…" puts the focus on
  onSaved: (said: string) => void;
}

/** "İptal ettim": the month of the last payment, a note if the user likes, previewed, then written. */
export function EndForm({ series, asOf, others, labels, changing, target, onSaved }: EndFormProps) {
  const { t } = useTranslation("subscriptions");
  const preview = usePreviewRule();
  const save = useSaveRule();
  const last = monthOf(series.last_day);
  const [month, setMonth] = useState(last);
  const [note, setNote] = useState("");
  const heading = useId();
  const monthId = useId();
  const noteId = useId();
  const hintId = useId();
  const after = paidAfter(series, month);
  const rule = (): EndedRule => ({ action: "ended", merchant: series.payee, month, note: note.trim() });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.reset();
    preview.mutate(rule());
  };
  const saveIt = () =>
    save.mutate(rule(), {
      onSuccess: () => {
        preview.reset();
        onSaved(t("end.saved", { payee: series.payee, month }));
      },
    });

  return (
    <section aria-labelledby={heading} className={SECTION}>
      <h3 id={heading} className="text-base font-semibold">
        {changing ? t("end.titleChange") : t("end.title")}
      </h3>
      <p className={SMALL}>{changing ? t("end.textChange") : t("end.text")}</p>
      <form onSubmit={submit} className="flex flex-col gap-2 text-sm">
        <label htmlFor={monthId}>{t("end.month")}</label>
        <select
          id={monthId}
          ref={target}
          value={month}
          onChange={(event) => {
            setMonth(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        >
          {monthChoices(series, asOf).map((choice) => (
            <option key={choice} value={choice}>
              {choice === last ? t("end.lastMark", { month: formatMonth(choice) }) : formatMonth(choice)}
            </option>
          ))}
        </select>
        {after.length > 0 ? (
          <p className="text-amber-900 dark:text-amber-200">
            {t("end.after", { count: after.length, status: labelOf(labels, "SeriesStatus", "paid_after_cancel") })}
          </p>
        ) : null}
        <label htmlFor={noteId}>{t("end.note")}</label>
        <input
          id={noteId}
          value={note}
          maxLength={200}
          aria-describedby={hintId}
          onChange={(event) => {
            setNote(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        />
        <span id={hintId} className={SMALL}>
          {t("end.noteHint")}
        </span>
        {others > 0 ? <p>{t("end.others", { payee: series.payee, count: others + 1 })}</p> : null}
        <Button type="submit" variant="secondary" className="self-start" disabled={preview.isPending}>
          {preview.isPending ? t("preview.previewing") : t("preview.preview")}
        </Button>
      </form>
      {preview.isError ? <Alert tone="critical" title={preview.error.message} /> : null}
      {preview.data ? (
        <RulePreview
          change={preview.data}
          effect={t("end.effect", { payee: series.payee, month })}
          saving={save.isPending}
          onSave={saveIt}
          onCancel={() => preview.reset()}
        />
      ) : null}
      {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
    </section>
  );
}

interface AgainFormProps {
  series: Series;
  entry: EndedPayment; // the user's own `_biten` entry that names the payee
  target?: RefObject<HTMLButtonElement | null> | undefined; // what "Yeniden bekle…" puts the focus on
  onSaved: (said: string) => void;
}

/** "Yeniden bekle": the user's own entry taken off `_biten`, previewed, then written. */
export function AgainForm({ series, entry, target, onSaved }: AgainFormProps) {
  const { t } = useTranslation("subscriptions");
  const preview = usePreviewRule();
  const save = useSaveRule();
  const heading = useId();
  // The entry as the rule file writes it; the service finds it by its folded name all the same.
  const rule: NotEndedRule = { action: "not_ended", merchant: entry.merchant };
  const saveIt = () =>
    save.mutate(rule, {
      onSuccess: () => {
        preview.reset();
        onSaved(t("again.saved", { payee: series.payee }));
      },
    });

  return (
    <section aria-labelledby={heading} className={SECTION}>
      <h3 id={heading} className="text-base font-semibold">
        {t("again.title")}
      </h3>
      <p className="text-sm">{t("again.text", { payee: series.payee, month: formatMonth(entry.month) })}</p>
      <Button
        ref={target}
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
          effect={t("again.effect")}
          saving={save.isPending}
          onSave={saveIt}
          onCancel={() => preview.reset()}
        />
      ) : null}
      {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
    </section>
  );
}
