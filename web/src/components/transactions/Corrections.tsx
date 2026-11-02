// What the user may correct on a row (F04, architecture §7 "Kullanıcı düzeltmesi"): its category for this row only or
// as a rule for its merchant, its necessity, a note and tags, or a split into parts. Each is bound to the row's
// fingerprint, so a new reading of the documents keeps it. A note and tags show at once; a category, a necessity or a
// split shows as the service's new analysis settles, a few seconds later. A split row's category is in its parts:
// the split editor stands in for the category correction. A split the row no longer takes (a rule changed its kind,
// or its amount moved too far) is said, with the way to take it off.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useCategoryRules, useCorrection } from "../../api/queries";
import type { Category, Labels, Necessity, TransactionDetail } from "../../api/types";
import { labelOf } from "../../lib/labels";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { CloseIcon } from "../ui/Icons";
import { CategorySelect } from "./CategorySelect";
import { RuleForm } from "./RuleForm";
import { SplitEditor } from "./SplitEditor";

const NECESSITIES: readonly Necessity[] = ["required", "optional", "unnecessary", "unknown"];
const MAX_TAGS = 20;
const FIELD = [
  "min-h-11 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const CHIP = "inline-flex items-center gap-1 rounded-full border border-zinc-300 py-0.5 pl-3 pr-1 dark:border-zinc-600";

/**
 * The note and tags as the user last kept them. The detail's annotation is read fresh from the database; its row
 * waits for the service's new analysis, so right after a change the row may still show the one before.
 */
export function ownOf(found: TransactionDetail): { note: string; tags: string[] } {
  if (found.annotation) {
    return { note: found.annotation.note, tags: found.annotation.tags };
  }
  return found.correctable ? { note: "", tags: [] } : { note: found.row.note, tags: found.row.tags };
}

interface CorrectionsProps {
  found: TransactionDetail;
  fingerprint: string; // as the address has it: the row's or one of its parts'
  labels: Labels;
}

export function Corrections({ found, fingerprint, labels }: CorrectionsProps) {
  const { t } = useTranslation("transactions");
  const rules = useCategoryRules();
  const [splitting, setSplitting] = useState(false);
  const isSplit = found.parts.length > 0;
  const own = ownOf(found);
  if (rules.isPending) {
    return <Loading label={t("correct.loadingRules")} />;
  }
  if (rules.isError) {
    return <Failure error={rules.error} onRetry={() => void rules.refetch()} />;
  }
  const categories = rules.data.categories;
  return (
    <div className="flex flex-col gap-5">
      {found.split_dropped ? <DroppedSplit fingerprint={fingerprint} /> : null}
      {isSplit || splitting ? (
        <SplitEditor
          fingerprint={fingerprint}
          row={found.row}
          parts={found.parts}
          categories={categories}
          labels={labels}
          {...(isSplit ? {} : { onCancel: () => setSplitting(false) })}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <CategoryCorrection found={found} fingerprint={fingerprint} categories={categories} />
          {found.splittable ? (
            <Button variant="secondary" className="self-start" onClick={() => setSplitting(true)}>
              {t("split.open")}
            </Button>
          ) : null}
        </div>
      )}
      {found.why.necessity !== null && !isSplit ? (
        <NecessityCorrection found={found} fingerprint={fingerprint} labels={labels} />
      ) : null}
      <NoteCorrection note={own.note} fingerprint={fingerprint} />
      <TagsCorrection tags={own.tags} fingerprint={fingerprint} />
    </div>
  );
}

/** The user's split of a row that counts whole again: its kind no longer splits, or its amount moved too far. */
function DroppedSplit({ fingerprint }: { fingerprint: string }) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  return (
    <Alert tone="warning" title={t("split.droppedTitle")}>
      <p>{t("split.droppedText")}</p>
      <Button
        variant="secondary"
        className="mt-2"
        disabled={correction.isPending}
        onClick={() => correction.mutate({ parts: [] })}
      >
        {t("split.join")}
      </Button>
      {correction.isError ? <p className="mt-2">{correction.error.message}</p> : null}
    </Alert>
  );
}

interface CategoryCorrectionProps {
  found: TransactionDetail;
  fingerprint: string;
  categories: readonly Category[];
}

/** The category for this row only, back to the rules, or as a rule for every row of its merchant. */
function CategoryCorrection({ found, fingerprint, categories }: CategoryCorrectionProps) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  const own = found.annotation?.category ?? "";
  const current = own || found.row.category;
  // Untouched, the choice follows the row's category as it settles; a pick holds until it is saved.
  const [picked, setPicked] = useState<string | null>(null);
  const chosen = picked ?? (categories.some((category) => category.name === current) ? current : "");
  const [asRule, setAsRule] = useState(false);
  const [said, setSaid] = useState("");
  const save = (category: string) => {
    setSaid("");
    correction.mutate(
      { category },
      {
        onSuccess: () => {
          setSaid(t("correct.settling"));
          setPicked(null);
        },
      },
    );
  };
  return (
    <div className="flex flex-col gap-2">
      <CategorySelect
        label={t("correct.category")}
        categories={categories}
        value={chosen}
        placeholder={t("correct.choose")}
        onChange={(category) => {
          setPicked(category);
          setAsRule(false);
          setSaid("");
        }}
      />
      {own ? <p className={SMALL}>{t("correct.own", { value: own })}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!chosen || chosen === current || correction.isPending} onClick={() => save(chosen)}>
          {t("correct.onlyThis")}
        </Button>
        <Button variant="secondary" disabled={!chosen} aria-expanded={asRule} onClick={() => setAsRule(!asRule)}>
          {t("correct.asRule")}
        </Button>
        {own ? (
          <Button variant="secondary" disabled={correction.isPending} onClick={() => save("")}>
            {t("correct.back")}
          </Button>
        ) : null}
      </div>
      <p aria-live="polite" className="text-sm">
        {said}
      </p>
      {correction.isError ? <Alert tone="critical" title={correction.error.message} /> : null}
      {asRule && chosen ? (
        <RuleForm key={chosen} row={found.row} category={chosen} onDone={() => setAsRule(false)} />
      ) : null}
    </div>
  );
}

interface NecessityCorrectionProps {
  found: TransactionDetail;
  fingerprint: string;
  labels: Labels;
}

/** How necessary the row's spending was, or back to what its merchant's and category's rules say. */
function NecessityCorrection({ found, fingerprint, labels }: NecessityCorrectionProps) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  const own = found.annotation?.necessity ?? "";
  const [picked, setPicked] = useState<Necessity | "" | null>(null); // null: the choice follows what is kept
  const chosen = picked ?? own;
  const [said, setSaid] = useState("");
  const id = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSaid("");
    correction.mutate(
      { necessity: chosen },
      {
        onSuccess: () => {
          setSaid(t("correct.settling"));
          setPicked(null);
        },
      },
    );
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={id}>{t("correct.necessity")}</label>
          <select
            id={id}
            value={chosen}
            onChange={(event) => {
              setPicked(event.target.value as Necessity | "");
              setSaid("");
            }}
            className={FIELD}
          >
            <option value="">{t("correct.necessityRules")}</option>
            {NECESSITIES.map((code) => (
              <option key={code} value={code}>
                {labelOf(labels, "Necessity", code)}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" variant="secondary" disabled={chosen === own || correction.isPending}>
          {t("correct.saveNecessity")}
        </Button>
      </div>
      {own ? <p className={SMALL}>{t("correct.own", { value: labelOf(labels, "Necessity", own) })}</p> : null}
      <p aria-live="polite" className="text-sm">
        {said}
      </p>
      {correction.isError ? <Alert tone="critical" title={correction.error.message} /> : null}
    </form>
  );
}

/** The row's note, up to 500 characters; it shows at once and goes back if the service refuses it. */
function NoteCorrection({ note, fingerprint }: { note: string; fingerprint: string }) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  const [text, setText] = useState(note);
  const [said, setSaid] = useState("");
  const id = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSaid("");
    correction.mutate({ note: text.trim() }, { onSuccess: () => setSaid(t("correct.saved")) });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 text-sm">
      <label htmlFor={id}>{t("correct.note")}</label>
      <textarea
        id={id}
        value={text}
        rows={3}
        maxLength={500}
        onChange={(event) => {
          setText(event.target.value);
          setSaid("");
        }}
        className={`${FIELD} py-2`}
      />
      <Button
        type="submit"
        variant="secondary"
        className="self-start"
        disabled={text.trim() === note.trim() || correction.isPending}
      >
        {t("correct.saveNote")}
      </Button>
      <p aria-live="polite">{said}</p>
      {correction.isError ? <Alert tone="critical" title={correction.error.message} /> : null}
    </form>
  );
}

/** The row's tags: each removed with its own button, new ones added (several at once with commas between). */
function TagsCorrection({ tags, fingerprint }: { tags: readonly string[]; fingerprint: string }) {
  const { t } = useTranslation("transactions");
  const correction = useCorrection(fingerprint);
  const [text, setText] = useState("");
  const [said, setSaid] = useState("");
  const id = useId();
  const hint = useId();
  const heading = useId();
  const change = (next: string[]) => {
    setSaid("");
    correction.mutate({ tags: next }, { onSuccess: () => setSaid(t("correct.saved")) });
  };
  const add = (event: FormEvent) => {
    event.preventDefault();
    const added = text
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (added.length > 0) {
      change([...new Set([...tags, ...added])].slice(0, MAX_TAGS));
      setText("");
    }
  };
  return (
    <div role="group" aria-labelledby={heading} className="flex flex-col gap-2 text-sm">
      <span id={heading}>{t("correct.tags")}</span>
      {tags.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <li key={tag} className={CHIP}>
              {tag}
              <button
                type="button"
                aria-label={t("correct.removeTag", { tag })}
                disabled={correction.isPending}
                onClick={() => change(tags.filter((other) => other !== tag))}
                className={[
                  "inline-flex size-8 items-center justify-center rounded-full text-zinc-600 hover:bg-zinc-100",
                  "dark:text-zinc-300 dark:hover:bg-zinc-800",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
                ].join(" ")}
              >
                <CloseIcon className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={SMALL}>{t("correct.noTags")}</p>
      )}
      <form onSubmit={add} className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <label htmlFor={id} className="sr-only">
            {t("correct.tagNew")}
          </label>
          <input
            id={id}
            value={text}
            maxLength={40}
            placeholder={t("correct.tagNew")}
            aria-describedby={hint}
            onChange={(event) => setText(event.target.value)}
            className={`${FIELD} w-48`}
          />
        </div>
        <Button
          type="submit"
          variant="secondary"
          disabled={!text.trim() || tags.length >= MAX_TAGS || correction.isPending}
        >
          {t("correct.addTag")}
        </Button>
      </form>
      <span id={hint} className={SMALL}>
        {t("correct.tagHint")}
      </span>
      <p aria-live="polite">{said}</p>
      {correction.isError ? <Alert tone="critical" title={correction.error.message} /> : null}
    </div>
  );
}
