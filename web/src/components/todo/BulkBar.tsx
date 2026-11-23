// The bulk steps of the to-do list (F19): choose every item listed at once, then take the chosen ones off the list or
// put the ones taken off back, together. While items are chosen the bar stays in sight under the header, so its steps
// are at hand however far down the list the last one was chosen.

import { useTranslation } from "react-i18next";

import type { TodoItem } from "../../api/types";
import { cn } from "../../lib/cn";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Choice } from "./Choice";

interface TodoBulkBarProps {
  listed: readonly TodoItem[]; // every item shown now
  chosen: readonly TodoItem[]; // the ones of them chosen
  onChoose: (items: readonly TodoItem[], on: boolean) => void;
  onIgnore: (items: readonly TodoItem[]) => void;
  onRestore: (items: readonly TodoItem[]) => void;
  pending: boolean; // a step is on its way to the service
  failure: string; // the service's word on the last bulk step that failed; "" for none
}

export function TodoBulkBar({ listed, chosen, onChoose, onIgnore, onRestore, pending, failure }: TodoBulkBarProps) {
  const { t } = useTranslation("todo");
  const any = chosen.length > 0;
  if (listed.length === 0 || (listed.length === 1 && !any && !failure)) {
    return null; // a single item is chosen by its own checkbox
  }
  const waiting = chosen.filter((item) => !item.ignored);
  const taken = chosen.filter((item) => item.ignored);
  return (
    <section
      aria-label={t("bulk.label")}
      className={cn(
        "flex flex-col gap-2 rounded-lg",
        any && "sticky top-14 z-20 border border-teal-600 bg-teal-50 p-3 shadow-sm",
        any && "dark:border-teal-400 dark:bg-teal-950",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {listed.length > 1 ? (
          <Choice checked={chosen.length === listed.length} mixed={any} onChange={(on) => onChoose(listed, on)}>
            {t("bulk.all", { count: listed.length })}
          </Choice>
        ) : null}
        <p aria-live="polite" className="text-sm font-medium">
          {any ? t("bulk.selected", { count: chosen.length }) : ""}
        </p>
      </div>
      {any ? (
        <div className="flex flex-wrap gap-2">
          {waiting.length > 0 ? (
            <Button disabled={pending} onClick={() => onIgnore(waiting)}>
              {t("bulk.ignore", { count: waiting.length })}
            </Button>
          ) : null}
          {taken.length > 0 ? (
            <Button variant="secondary" disabled={pending} onClick={() => onRestore(taken)}>
              {t("bulk.restore", { count: taken.length })}
            </Button>
          ) : null}
          <Button variant="secondary" onClick={() => onChoose(listed, false)}>
            {t("bulk.clear")}
          </Button>
        </div>
      ) : null}
      {failure ? <Alert tone="critical" title={failure} /> : null}
    </section>
  );
}
