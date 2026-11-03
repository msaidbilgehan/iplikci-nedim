// The EVDS key on the Settings screen (F12's V1+ part): optional, for the spending trend in real terms on Değerlendirme.
// The user copies their own key from EVDS's profile page; the service tries it once with EVDS and keeps it in the
// keychain only when EVDS takes it. The key is only entered, never shown again: the card says whether one is kept,
// which months of TÜFE came and how the last daily fetch went, and offers to forget it.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useEvds, useRemoveEvdsKey, useSetEvdsKey } from "../../api/queries";
import type { EvdsState } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMonth, formatTime } from "../../lib/format";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Say } from "../ui/Say";
import { HINT } from "./NameList";

const FIELD = cn(
  "min-h-11 w-full max-w-md rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const INVALID = "border-red-700 dark:border-red-400";

export function EvdsCard() {
  const { t } = useTranslation("settings");
  const evds = useEvds();
  return (
    <Card title={t("evds.title")}>
      <Say>{t("evds.say")}</Say>
      {evds.isPending ? <Loading /> : null}
      {evds.isError ? <Failure error={evds.error} onRetry={() => void evds.refetch()} /> : null}
      {evds.data ? <EvdsFields state={evds.data} /> : null}
    </Card>
  );
}

function EvdsFields({ state }: { state: EvdsState }) {
  const { t } = useTranslation("settings");
  const kept: Array<[string, string]> = [
    [t("evds.key"), state.has_key ? t("evds.kept") : t("evds.none")],
    [
      t("evds.months"),
      state.first && state.newest
        ? t("evds.monthsValue", {
            count: state.months,
            first: formatMonth(state.first),
            newest: formatMonth(state.newest),
          })
        : t("evds.noMonths"),
    ],
  ];
  if (state.has_key) {
    kept.push([t("evds.lastRun"), state.last_run ? formatTime(state.last_run) : t("evds.never")]);
  }
  return (
    <div className="flex flex-col gap-4">
      <Facts items={kept} />
      {state.has_key && state.last_error ? (
        <Alert tone="warning" title={t("evds.failed")}>
          <p>{state.last_error}</p>
        </Alert>
      ) : null}
      <KeyForm hasKey={state.has_key} />
      {state.has_key ? <Forget /> : null}
    </div>
  );
}

/** The key typed, sent once and cleared from the page with the request that takes it. */
function KeyForm({ hasKey }: { hasKey: boolean }) {
  const { t } = useTranslation("settings");
  const save = useSetEvdsKey();
  const [filled, setFilled] = useState(false); // whether a key is typed; never the key itself
  const ids = { key: useId(), steps: useId(), error: useId() };

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const field = event.currentTarget.elements.namedItem("evds-key");
    const key = field instanceof HTMLInputElement ? field.value.trim() : "";
    if (field instanceof HTMLInputElement) {
      field.value = "";
    }
    setFilled(false);
    if (key) {
      save.mutate(key);
    }
  }

  const refused = save.isError ? save.error.message : "";
  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-3">
      <ol id={ids.steps} className="list-decimal pl-5 text-sm">
        <li>{t("evds.step1")}</li>
        <li>{t("evds.step2")}</li>
        <li>{t("evds.step3")}</li>
      </ol>
      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor={ids.key}>{hasKey ? t("evds.newKey") : t("evds.keyLabel")}</label>
        <input
          id={ids.key}
          name="evds-key"
          type="password"
          maxLength={200}
          autoComplete="off"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          aria-describedby={refused ? `${ids.steps} ${ids.error}` : ids.steps}
          aria-invalid={refused ? true : undefined}
          onChange={(event) => {
            setFilled(event.target.value.trim() !== "");
            save.reset();
          }}
          className={cn(FIELD, refused && INVALID)}
        />
      </div>
      <Button type="submit" className="self-start" disabled={save.isPending || !filled}>
        {save.isPending ? t("evds.sending") : t("evds.send")}
      </Button>
      <p className={HINT}>{t("evds.privacy")}</p>
      {refused ? (
        <div id={ids.error}>
          <Alert tone="critical" title={t("evds.refused")} live>
            <p>{refused}</p>
          </Alert>
        </div>
      ) : null}
      {save.isSuccess ? (
        <Alert tone="good" title={t("evds.done", { count: save.data.months })} live>
          <p>{t("evds.doneText")}</p>
        </Alert>
      ) : null}
    </form>
  );
}

function Forget() {
  const { t } = useTranslation("settings");
  const remove = useRemoveEvdsKey();
  const [asking, setAsking] = useState(false);
  return (
    <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
      <Button variant="danger" className="self-start" disabled={remove.isPending} onClick={() => setAsking(true)}>
        {t("evds.remove")}
      </Button>
      {remove.isError ? <Alert tone="critical" title={remove.error.message} /> : null}
      {remove.isSuccess ? <Alert tone="good" title={t("evds.removed")} live /> : null}
      <ConfirmDialog
        open={asking}
        onOpenChange={setAsking}
        title={t("evds.removeTitle")}
        description={t("evds.removeText")}
        confirmLabel={t("evds.remove")}
        onConfirm={() => {
          setAsking(false);
          remove.mutate();
        }}
      />
    </div>
  );
}
