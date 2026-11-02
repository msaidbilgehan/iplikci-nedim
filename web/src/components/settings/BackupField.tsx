// How many days of daily backups are kept (F17, F20): a whole number of days from 1 to 365, as the service takes it.
// A backup can be asked for at once (ADR-0017); the next one, the rehearsal and the space they take stand on the
// System screen.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useBackupNow, useSetBackupDays, useSystem } from "../../api/queries";
import type { Settings } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatTime } from "../../lib/format";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { HINT } from "./NameList";

const FIELD = cn(
  "min-h-11 w-28 rounded-md border px-3 text-sm tabular-nums",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const LEAST = 1;
const MOST = 365;

export function BackupEditor({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const save = useSetBackupDays();
  const [draft, setDraft] = useState(String(settings.backup_days));
  const [problem, setProblem] = useState("");
  const id = useId();
  const said = problem || (save.isError ? save.error.message : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const days = Number(draft.trim());
    if (!/^\d+$/.test(draft.trim()) || days < LEAST || days > MOST) {
      setProblem(t("backup.outside", { least: LEAST, most: MOST }));
      document.getElementById(id)?.focus();
      return;
    }
    save.mutate({ keep_days: days });
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{t("backup.label")}</label>
      <div className="flex flex-wrap items-start gap-2">
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={LEAST}
          max={MOST}
          step={1}
          value={draft}
          aria-describedby={said ? `${id}-ipucu ${id}-hata` : `${id}-ipucu`}
          aria-invalid={said ? true : undefined}
          onChange={(event) => {
            setDraft(event.target.value);
            setProblem("");
            save.reset();
          }}
          className={cn(FIELD, said && "border-red-700 dark:border-red-400")}
        />
        <Button type="submit" variant="secondary" disabled={save.isPending || draft === String(settings.backup_days)}>
          {t("backup.save")}
        </Button>
      </div>
      <p id={`${id}-ipucu`} className={HINT}>
        {t("backup.now", { count: settings.backup_days })}
      </p>
      {said ? (
        <p id={`${id}-hata`} className="text-sm text-red-800 dark:text-red-200">
          {said}
        </p>
      ) : null}
      {save.isSuccess ? <Alert tone="good" title={t("backup.saved", { count: settings.backup_days })} live /> : null}
    </form>
  );
}

/** A backup asked for now: the service's worker takes it within seconds; when the last one was taken, beside it. */
export function BackupNow() {
  const { t } = useTranslation("settings");
  const now = useBackupNow();
  const last = useSystem().data?.backup.last;
  return (
    <div className="flex flex-col items-start gap-2 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={now.isPending} onClick={() => now.mutate()}>
          {now.isPending ? t("backup.asking") : t("backup.takeNow")}
        </Button>
        {last !== undefined ? (
          <span className={HINT}>{last ? t("backup.last", { time: formatTime(last) }) : t("backup.none")}</span>
        ) : null}
      </div>
      {now.isSuccess ? <Alert tone="good" title={t("backup.asked")} live /> : null}
      {/* The same button asks again. */}
      {now.isError ? (
        <Alert tone="critical" title={t("backup.askFailed")} live>
          <p>{now.error.message}</p>
        </Alert>
      ) : null}
    </div>
  );
}
