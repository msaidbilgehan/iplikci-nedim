// The selected rows' actions (F04's "toplu işlem"): one category for them all, or a tag added to each. The service
// says how many changed and which it skipped (a row the statements leave out carries no correction).

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useBulkCorrection } from "../../api/queries";
import type { Category } from "../../api/types";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { CategorySelect } from "./CategorySelect";

const INPUT = [
  "min-h-11 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");

interface BulkBarProps {
  selected: ReadonlySet<string>;
  categories: readonly Category[];
  onDone: () => void; // the action went through: the selection is cleared
}

export function BulkBar({ selected, categories, onDone }: BulkBarProps) {
  const { t } = useTranslation("transactions");
  const bulk = useBulkCorrection();
  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [result, setResult] = useState(""); // what the last action did, said once the selection is cleared
  const tagId = useId();
  const fingerprints = [...selected];
  if (selected.size === 0 && !result) {
    return null;
  }

  const run = (change: { category?: string; tags?: string[] }) =>
    bulk.mutate(
      { fingerprints, ...change },
      {
        onSuccess: (done) => {
          const said = [t("bulk.changed", { count: done.changed })];
          if (done.skipped.length > 0) {
            said.push(t("bulk.skipped", { count: done.skipped.length }));
          }
          setResult(said.join(" "));
          setTag("");
          onDone();
        },
      },
    );
  const addTag = (event: FormEvent) => {
    event.preventDefault();
    if (tag.trim()) {
      run({ tags: [tag.trim()] });
    }
  };

  return (
    <section
      aria-label={t("bulk.label")}
      className="flex flex-col gap-3 rounded-lg border border-teal-600 bg-teal-50 p-3 dark:border-teal-400 dark:bg-teal-950"
    >
      <p aria-live="polite" className="text-sm font-medium">
        {selected.size > 0 ? t("bulk.selected", { count: selected.size }) : result}
      </p>
      {selected.size > 0 ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-end gap-2">
            <CategorySelect
              label={t("bulk.category")}
              categories={categories}
              value={category}
              onChange={setCategory}
            />
            <Button disabled={!category || bulk.isPending} onClick={() => run({ category })}>
              {t("bulk.giveCategory")}
            </Button>
          </div>
          <form onSubmit={addTag} className="flex items-end gap-2">
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor={tagId}>{t("bulk.tag")}</label>
              <input
                id={tagId}
                value={tag}
                maxLength={40}
                onChange={(event) => setTag(event.target.value)}
                className={`${INPUT} w-40`}
              />
            </div>
            <Button type="submit" disabled={!tag.trim() || bulk.isPending}>
              {t("bulk.addTag")}
            </Button>
          </form>
          <Button
            variant="secondary"
            onClick={() => {
              setResult("");
              onDone();
            }}
          >
            {t("bulk.clear")}
          </Button>
        </div>
      ) : null}
      {bulk.isError ? <Alert tone="critical" title={bulk.error.message} /> : null}
    </section>
  );
}
