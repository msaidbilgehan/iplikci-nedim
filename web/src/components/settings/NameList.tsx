// A list of names saved whole with each change (F17): the user's own names and their forms, or the company names whose
// documents stay out. A name is added from the field under the list and taken off with the button beside it; the
// service answers with the list as it keeps it (each name once, trimmed).

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useSetIdentity } from "../../api/queries";
import type { Settings } from "../../api/types";
import { cn } from "../../lib/cn";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";

const FIELD = cn(
  "min-h-11 w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
export const HINT = "text-sm text-zinc-700 dark:text-zinc-300";
const ERROR = "text-sm text-red-800 dark:text-red-200";
const CHIP = "inline-flex items-center gap-1 rounded-full border border-zinc-300 pl-3 text-sm dark:border-zinc-600";
const MAX_NAMES = 20; // the service's limit (IdentityIn)

interface NameListProps {
  label: string; // the field's name: "Ad ve biçimleri"
  hint: string; // what the names are for
  listLabel: string; // the list's name for screen readers
  values: readonly string[];
  maxLength: number; // a name's longest, as the service takes it
  saving: boolean;
  saved: string; // what the last change did, said once it is saved; "" for none
  refusal: string; // the service's refusal of the last change, as it said it
  onSave: (values: string[]) => void; // the whole list
}

export function NameList({ label, hint, listLabel, values, maxLength, saving, saved, refusal, onSave }: NameListProps) {
  const { t } = useTranslation("settings");
  const [draft, setDraft] = useState("");
  const [problem, setProblem] = useState("");
  const id = useId();
  const hintId = `${id}-ipucu`;
  const errorId = `${id}-hata`;
  const said = problem || refusal;

  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = draft.split(/\s+/).filter(Boolean).join(" ");
    if (!name) {
      setProblem(t("names.needName"));
    } else if (values.some((value) => value.toLocaleLowerCase("tr-TR") === name.toLocaleLowerCase("tr-TR"))) {
      setProblem(t("names.twice"));
    } else if (values.length >= MAX_NAMES) {
      setProblem(t("names.tooMany", { count: MAX_NAMES }));
    } else {
      setProblem("");
      onSave([...values, name]);
      setDraft("");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {values.length > 0 ? (
        <ul aria-label={listLabel} className="flex flex-wrap gap-2">
          {values.map((value) => (
            <li key={value} className={CHIP}>
              <span className="break-all">{value}</span>
              <button
                type="button"
                disabled={saving}
                aria-label={t("names.remove", { name: value })}
                onClick={() => onSave(values.filter((other) => other !== value))}
                className={cn(
                  "inline-flex size-11 items-center justify-center rounded-full text-zinc-700 hover:bg-zinc-100",
                  "dark:text-zinc-200 dark:hover:bg-zinc-800 disabled:opacity-60",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
                )}
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <form noValidate onSubmit={add} className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm">
          {label}
        </label>
        <div className="flex flex-wrap items-start gap-2">
          <input
            id={id}
            type="text"
            value={draft}
            maxLength={maxLength}
            autoComplete="off"
            aria-describedby={said ? `${hintId} ${errorId}` : hintId}
            aria-invalid={said ? true : undefined}
            onChange={(event) => {
              setDraft(event.target.value);
              setProblem("");
            }}
            className={cn(FIELD, "max-w-md flex-1", said && "border-red-700 dark:border-red-400")}
          />
          <Button type="submit" variant="secondary" disabled={saving}>
            {t("names.add")}
          </Button>
        </div>
        <p id={hintId} className={HINT}>
          {hint}
        </p>
        {said ? (
          <p id={errorId} className={ERROR}>
            {said}
          </p>
        ) : null}
      </form>
      {saved ? <Alert tone="good" title={saved} live /> : null}
    </div>
  );
}

/** The user's own names and the forms banks write them in: transfers between their own accounts are known by them. */
export function NamesEditor({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const save = useSetIdentity();
  return (
    <NameList
      label={t("names.label")}
      hint={t("names.hint")}
      listLabel={t("names.list")}
      values={settings.names}
      maxLength={100}
      saving={save.isPending}
      saved={save.isSuccess ? t("names.saved") : ""}
      refusal={save.isError ? save.error.message : ""}
      onSave={(names) => save.mutate({ names, business_names: settings.business_names })}
    />
  );
}

/** The company names: their cards, commercial accounts and payroll are never read, kept or reported. */
export function BusinessNamesEditor({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const save = useSetIdentity();
  return (
    <NameList
      label={t("business.label")}
      hint={t("business.hint")}
      listLabel={t("business.list")}
      values={settings.business_names}
      maxLength={150}
      saving={save.isPending}
      saved={save.isSuccess ? t("business.saved") : ""}
      refusal={save.isError ? save.error.message : ""}
      onSave={(names) => save.mutate({ names: settings.names, business_names: names })}
    />
  );
}
