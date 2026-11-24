// The day the user closed an account (F07): from then on it is listed with the closed accounts, in no total, and the
// month-end, the forecast and the to-do list await no document of it. The mark is the user's own: taking it away opens
// the account again (or leaves it to the 180 days' rule). The service refuses a day after today, or one before a
// movement its documents tell.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useCloseAccount } from "../../api/queries";
import type { AccountItem } from "../../api/types";
import { localDay } from "../../lib/format";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";

const INPUT = [
  "min-h-11 w-full max-w-56 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");

interface ClosingFormProps {
  item: AccountItem;
  onDone: (said: string) => void; // marked or opened again (what to say about it), or given up (""): the form closes
}

export function ClosingForm({ item, onDone }: ClosingFormProps) {
  const { t } = useTranslation("accounts");
  const change = useCloseAccount(item.account.id);
  const today = localDay(new Date().toISOString());
  const [day, setDay] = useState(item.closed_on ?? today);
  const id = useId();
  const hint = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    change.mutate(day, { onSuccess: () => onDone(t("closing.saved", { day })) });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
      <label htmlFor={id} className="font-medium">
        {t("closing.label")}
      </label>
      <input
        id={id}
        type="date"
        required
        value={day}
        max={today}
        aria-describedby={hint}
        onChange={(event) => {
          setDay(event.target.value);
          change.reset();
        }}
        className={INPUT}
      />
      <span id={hint} className="text-xs text-zinc-600 dark:text-zinc-300">
        {t("closing.hint")}
      </span>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!day || day === item.closed_on || change.isPending}>
          {t("closing.save")}
        </Button>
        {item.closed_on ? (
          <Button
            variant="secondary"
            disabled={change.isPending}
            onClick={() => change.mutate(null, { onSuccess: () => onDone(t("closing.reopened")) })}
          >
            {t("closing.reopen")}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={() => onDone("")}>
          {t("closing.cancel")}
        </Button>
      </div>
      {change.isError ? <Alert tone="critical" title={change.error.message} /> : null}
    </form>
  );
}
