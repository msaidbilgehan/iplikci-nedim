// Spending in real terms on the Settings screen (F12's V1+ part): an optional feature, off until the user gives their
// own EVDS key. The card says what it does in plain words with an example, whether it is on, and how a key is got,
// with links to EVDS's own sign-in page and guides (opened in the user's browser; the service itself only ever asks
// EVDS for TÜFE). The service tries a key once with EVDS and keeps it in the keychain only when EVDS takes it. The key
// is only entered, never shown again: the card says which months of TÜFE came, how the last daily fetch went and when
// the series stops giving new months, and offers to forget the key, which turns the feature off.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useEvds, useRemoveEvdsKey, useSetEvdsKey } from "../../api/queries";
import type { EvdsState } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMonth, formatTime } from "../../lib/format";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Explain } from "../ui/Explain";
import { NextStep, Say } from "../ui/Say";
import { LINK } from "./MailFields";
import { HINT } from "./NameList";

// EVDS's own pages: the sign-in page, whose "Kayıt" tab makes a new member, and the guides, among them "Benim Sayfam -
// Üye İşlemleri Kılavuzu" on getting the key.
export const EVDS_LOGIN = "https://evds3.tcmb.gov.tr/login";
export const EVDS_GUIDES = "https://evds3.tcmb.gov.tr/dokumanlar";
// Where the feature shows: the spending trend, in Değerlendirme's Harcamalar part.
const SPENDING = { screen: "insights", id: "", query: { bolum: "harcamalar" } } as const;

const FIELD = cn(
  "min-h-11 w-full max-w-md rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const INVALID = "border-red-700 dark:border-red-400";
const PART = "flex flex-col gap-2 text-sm";
const PART_TITLE = "text-sm font-semibold";

export function EvdsCard() {
  const { t } = useTranslation("settings");
  const evds = useEvds();
  const on = evds.data?.has_key;
  return (
    <Card
      title={t("evds.title")}
      action={evds.data ? <Badge tone={on ? "good" : "neutral"}>{on ? t("evds.on") : t("evds.off")}</Badge> : undefined}
    >
      {evds.data ? <Say>{on ? t("evds.sayOn") : t("evds.sayOff")}</Say> : null}
      {evds.isPending ? <Loading /> : null}
      {evds.isError ? <Failure error={evds.error} onRetry={() => void evds.refetch()} /> : null}
      {evds.data ? <EvdsFields state={evds.data} /> : null}
    </Card>
  );
}

function EvdsFields({ state }: { state: EvdsState }) {
  const { t } = useTranslation("settings");
  // Here rather than in Forget, which goes with the key: the removal is said once the card shows the feature off.
  const remove = useRemoveEvdsKey();
  const kept: Array<[string, string]> = [
    [t("evds.status"), state.has_key ? t("evds.statusOn") : t("evds.statusOff")],
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
      <About on={state.has_key} />
      <Facts items={kept} />
      {state.has_key && state.behind ? (
        <Alert tone="warning" title={t("evds.behind")}>
          <p>{state.newest ? t("evds.behindText", { month: formatMonth(state.newest) }) : t("evds.behindNone")}</p>
        </Alert>
      ) : null}
      {state.has_key && state.last_error ? (
        <Alert tone="warning" title={t("evds.failed")}>
          <p>{state.last_error}</p>
        </Alert>
      ) : null}
      {remove.isSuccess && !state.has_key ? <Alert tone="good" title={t("evds.removed")} live /> : null}
      <KeyForm hasKey={state.has_key} />
      {state.has_key ? <Forget remove={remove} /> : null}
    </div>
  );
}

/** What the feature does, in words a user without a finance background reads, with an example one click away. */
function About({ on }: { on: boolean }) {
  const { t } = useTranslation("settings");
  const heading = useId();
  return (
    <section aria-labelledby={heading} className={PART}>
      <h3 id={heading} className={PART_TITLE}>
        {t("evds.whatTitle")}
      </h3>
      <p>{t("evds.what1")}</p>
      <p>{t("evds.what2")}</p>
      <Explain label={t("evds.exampleLabel")}>
        <p>{t("evds.example")}</p>
      </Explain>
      {on ? <NextStep step={{ link: SPENDING, label: t("evds.see") }} className="self-start" /> : null}
      {on ? null : <p className={HINT}>{t("evds.offText")}</p>}
    </section>
  );
}

/** A page of EVDS's own, opened in a new tab. Its name says so after the visible words (WCAG's label in name): an
 * aria-label, as hidden words would be read without the space before them. */
function EvdsLink({ href, label }: { href: string; label: string }) {
  const { t } = useTranslation("settings");
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${label} ${t("evds.newTab")}`}
      className={LINK}
    >
      {label}
    </a>
  );
}

/** The key typed, sent once and cleared from the page with the request that takes it. */
function KeyForm({ hasKey }: { hasKey: boolean }) {
  const { t } = useTranslation("settings");
  const save = useSetEvdsKey();
  const [filled, setFilled] = useState(false); // whether a key is typed; never the key itself
  const ids = { key: useId(), steps: useId(), error: useId(), heading: useId() };

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
    <form noValidate onSubmit={submit} aria-labelledby={ids.heading} className="flex flex-col gap-3">
      <h3 id={ids.heading} className={PART_TITLE}>
        {hasKey ? t("evds.howAgain") : t("evds.how")}
      </h3>
      <ol id={ids.steps} className="flex list-decimal flex-col gap-1 pl-5 text-sm">
        <li>
          <EvdsLink href={EVDS_LOGIN} label={t("evds.step1Link")} /> {t("evds.step1After")}
        </li>
        <li>{t("evds.step2")}</li>
        <li>{t("evds.step3")}</li>
      </ol>
      <p className={HINT}>
        {t("evds.guideBefore")} <EvdsLink href={EVDS_GUIDES} label={t("evds.guideLink")} /> {t("evds.guideAfter")}
      </p>
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

/** Forgetting the key, which turns the feature off, after asking. */
function Forget({ remove }: { remove: ReturnType<typeof useRemoveEvdsKey> }) {
  const { t } = useTranslation("settings");
  const [asking, setAsking] = useState(false);
  return (
    <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
      <Button variant="danger" className="self-start" disabled={remove.isPending} onClick={() => setAsking(true)}>
        {t("evds.remove")}
      </Button>
      {remove.isError ? <Alert tone="critical" title={remove.error.message} /> : null}
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
