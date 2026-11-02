// How e-mail comes in (F17, ADR-0016): the browser extension, which reads Gmail as the user sees it and asks for no
// password, or an IMAP account that allows app passwords. The extension is installed from the folder the service keeps
// (K20) and pairing it makes it the way; setting an account up makes IMAP the way. The app password is entered and
// sent, never kept in the page, shown or logged; the address is shown masked, as the service gives it. A refused login
// is never tried again from here: the user changes something and sends the form again.

import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { setUpImap, useBridges, useRemoveImap, useSetMail } from "../../api/queries";
import type { ImapSetUp, Settings } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, localDay } from "../../lib/format";
import { yearSuffix } from "../../lib/turkish";
import { PairedCard, PairingCard } from "../../pages/ExtensionPage";
import { InstallCard } from "../extension/InstallCard";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/Dialog";
import { HINT } from "./NameList";

type Connector = Settings["mail"]["connector"];

const FIELD = cn(
  "min-h-11 w-full max-w-md rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const INVALID = "border-red-700 dark:border-red-400";
const ERROR = "text-sm text-red-800 dark:text-red-200";
export const LINK = cn(
  "rounded font-medium text-teal-800 underline underline-offset-2 hover:text-teal-950",
  "dark:text-teal-300 dark:hover:text-teal-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const EARLIEST = "2000-01-01"; // the service's earliest start day

/** "2026-01-15" → "15.01.2026'dan": the day e-mail is read from. */
function fromDay(day: string): string {
  return `${formatDay(day)}${yearSuffix(day.slice(0, 4), true)}`;
}

interface MailEditorProps {
  settings: Settings;
  // The extension installed and paired here (the wizard), or a link to the Tarayıcı eklentisi screen that does it.
  pairing?: "here" | "link";
}

export function MailEditor({ settings, pairing = "here" }: MailEditorProps) {
  const { t } = useTranslation("settings");
  const mail = settings.mail;
  const bridges = useBridges();
  const paired = (bridges.data ?? []).filter((bridge) => bridge.active).length;
  // What the form shows first: the way in use, or the extension until an account is set up (Gmail's way, ADR-0016).
  const [choice, setChoice] = useState<Connector>(
    mail.connector === "imap" && mail.configured ? "imap" : "browser_bridge",
  );
  const name = useId();
  return (
    <div className="flex flex-col gap-4">
      <Current settings={settings} paired={paired} />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">{t("mail.choose")}</legend>
        {(["browser_bridge", "imap"] as const).map((option) => (
          <label
            key={option}
            className={cn(
              "flex cursor-pointer gap-3 rounded-md border p-3 text-sm",
              "border-zinc-300 dark:border-zinc-600",
              "has-checked:border-teal-700 has-checked:bg-teal-50 dark:has-checked:border-teal-400",
              "dark:has-checked:bg-teal-950",
              "has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-teal-600",
            )}
          >
            <input
              type="radio"
              name={name}
              value={option}
              checked={choice === option}
              onChange={() => setChoice(option)}
              className="mt-1 size-4 shrink-0 accent-teal-700"
            />
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">{t(`mail.option.${option}`)}</span>
              <span className={HINT}>{t(`mail.about.${option}`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {choice === "browser_bridge" ? (
        <BridgeWay settings={settings} paired={paired} pairing={pairing} />
      ) : (
        <ImapWay settings={settings} />
      )}
      <StartDay settings={settings} />
    </div>
  );
}

/** The way in use now, and what stops it if anything does. */
function Current({ settings, paired }: { settings: Settings; paired: number }) {
  const { t } = useTranslation("settings");
  const mail = settings.mail;
  if (mail.connector === "browser_bridge") {
    return (
      <Alert tone={paired > 0 ? "good" : "warning"} title={t("mail.now.bridge")}>
        <p>{paired > 0 ? t("mail.now.paired", { count: paired }) : t("mail.now.notPaired")}</p>
      </Alert>
    );
  }
  if (!mail.configured) {
    return <Alert tone="neutral" title={t("mail.now.none")} />;
  }
  if (mail.stopped) {
    // A refused login stopped it: nothing tries again until the account is set up again.
    return (
      <Alert tone="critical" title={t("mail.now.refused", { address: mail.address })}>
        {mail.last_error ? <p>{mail.last_error}</p> : null}
        <p>{t("mail.now.again")}</p>
      </Alert>
    );
  }
  return <Alert tone="good" title={t("mail.now.imap", { address: mail.address, server: mail.server })} />;
}

interface BridgeWayProps {
  settings: Settings;
  paired: number;
  pairing: "here" | "link";
}

function BridgeWay({ settings, paired, pairing }: BridgeWayProps) {
  const { t } = useTranslation("settings");
  const set = useSetMail();
  return (
    <div className="flex flex-col gap-4">
      {/* An extension paired before an account was set up: it can be the way again without pairing anew. */}
      {settings.mail.connector === "imap" && paired > 0 ? (
        <div className="flex flex-col gap-2">
          <Button
            variant="secondary"
            className="self-start"
            disabled={set.isPending}
            onClick={() => set.mutate({ connector: "browser_bridge" })}
          >
            {t("mail.useBridge")}
          </Button>
          {set.isError ? <Alert tone="critical" title={set.error.message} /> : null}
        </div>
      ) : null}
      {pairing === "here" ? (
        <>
          <InstallCard />
          <PairingCard />
          <PairedCard />
        </>
      ) : (
        <p className="text-sm">
          {t("mail.pairingThere")}{" "}
          <Link to="/kurulum/eklenti" className={LINK}>
            {t("mail.openExtension")}
          </Link>
        </p>
      )}
    </div>
  );
}

function ImapWay({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const client = useQueryClient();
  const remove = useRemoveImap();
  const [address, setAddress] = useState("");
  const [filled, setFilled] = useState(false); // whether a password is typed; never the password itself
  const [sending, setSending] = useState(false);
  const [refusal, setRefusal] = useState("");
  const [done, setDone] = useState<ImapSetUp | null>(null);
  const [asking, setAsking] = useState(false);
  const ids = { address: useId(), password: useId(), steps: useId(), error: useId() };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const field = event.currentTarget.elements.namedItem("password");
    const password = field instanceof HTMLInputElement ? field.value : "";
    if (field instanceof HTMLInputElement) {
      field.value = ""; // gone from the page with the request that takes it
    }
    setFilled(false);
    if (!address.trim() || !password) {
      return;
    }
    setSending(true);
    setRefusal("");
    setDone(null);
    try {
      // The mailbox is read from the day set below (StartDay), as with the extension.
      setDone(await setUpImap(client, { address: address.trim(), password, start: null }));
      setAddress("");
    } catch (error) {
      setRefusal(error instanceof Error ? error.message : t("mail.imap.failed"));
    } finally {
      setSending(false);
    }
  }

  const described = refusal ? `${ids.steps} ${ids.error}` : ids.steps;
  return (
    <div className="flex flex-col gap-4">
      <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
        <ol id={ids.steps} className="list-decimal pl-5 text-sm">
          <li>{t("mail.imap.step1")}</li>
          <li>{t("mail.imap.step2")}</li>
          <li>{t("mail.imap.step3")}</li>
        </ol>
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={ids.address}>{t("mail.imap.address")}</label>
          <input
            id={ids.address}
            type="email"
            value={address}
            maxLength={254}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            aria-describedby={described}
            aria-invalid={refusal ? true : undefined}
            onChange={(event) => {
              setAddress(event.target.value);
              setRefusal("");
            }}
            className={cn(FIELD, refusal && INVALID)}
          />
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={ids.password}>{t("mail.imap.password")}</label>
          <input
            id={ids.password}
            name="password"
            type="password"
            maxLength={200}
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            aria-describedby={described}
            aria-invalid={refusal ? true : undefined}
            onChange={(event) => {
              setFilled(event.target.value !== "");
              setRefusal("");
            }}
            className={cn(FIELD, refusal && INVALID)}
          />
        </div>
        <Button type="submit" className="self-start" disabled={sending || !filled || !address.trim()}>
          {sending ? t("mail.imap.sending") : t("mail.imap.send")}
        </Button>
        <p className={HINT}>{t("mail.imap.kept")}</p>
        {refusal ? (
          <div id={ids.error}>
            <Alert tone="critical" title={t("mail.imap.refused")} live>
              <p>{refusal}</p>
              <p className="mt-1">{t("mail.imap.noRetry")}</p>
            </Alert>
          </div>
        ) : null}
        {done ? (
          <Alert tone={done.in_keyring ? "good" : "warning"} title={t("mail.imap.done", { folder: done.folder })} live>
            {done.in_keyring ? null : <p>{t("mail.imap.noKeyring")}</p>}
          </Alert>
        ) : null}
      </form>
      {settings.mail.connector === "imap" && settings.mail.configured ? (
        <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-700">
          <Button variant="danger" className="self-start" disabled={remove.isPending} onClick={() => setAsking(true)}>
            {t("mail.imap.remove")}
          </Button>
          {remove.isError ? <Alert tone="critical" title={remove.error.message} /> : null}
          {remove.isSuccess ? <Alert tone="good" title={t("mail.imap.removed")} live /> : null}
          <ConfirmDialog
            open={asking}
            onOpenChange={setAsking}
            title={t("mail.imap.removeTitle")}
            description={t("mail.imap.removeText")}
            confirmLabel={t("mail.imap.remove")}
            variant="danger"
            busy={remove.isPending}
            onConfirm={() => remove.mutate(undefined, { onSettled: () => setAsking(false) })}
          />
        </div>
      ) : null}
    </div>
  );
}

/** The day the mailbox is read from: a new one makes the next reading start again from it. */
function StartDay({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const set = useSetMail();
  const [day, setDay] = useState(settings.mail.start);
  const id = useId();
  const today = localDay(new Date().toISOString());
  const problem = day && (day < EARLIEST || day > today) ? t("mail.start.outside", { today: formatDay(today) }) : "";
  const said = problem || (set.isError ? set.error.message : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (day && !problem) {
      set.mutate({ start: day });
    }
  }

  return (
    <form
      noValidate
      onSubmit={submit}
      className="flex flex-col gap-1 border-t border-zinc-200 pt-4 text-sm dark:border-zinc-700"
    >
      <label htmlFor={id} className="font-medium">
        {t("mail.start.label")}
      </label>
      <div className="flex flex-wrap items-start gap-2">
        <input
          id={id}
          type="date"
          value={day}
          min={EARLIEST}
          max={today}
          aria-describedby={said ? `${id}-ipucu ${id}-hata` : `${id}-ipucu`}
          aria-invalid={said ? true : undefined}
          onChange={(event) => {
            setDay(event.target.value);
            set.reset();
          }}
          className={cn(FIELD, "max-w-56", said && INVALID)}
        />
        <Button type="submit" variant="secondary" disabled={set.isPending || !day || day === settings.mail.start}>
          {t("mail.start.save")}
        </Button>
      </div>
      <p id={`${id}-ipucu`} className={HINT}>
        {t("mail.start.now", { day: fromDay(settings.mail.start) })}
      </p>
      {said ? (
        <p id={`${id}-hata`} className={ERROR}>
          {said}
        </p>
      ) : null}
      {set.isSuccess ? (
        <Alert tone="good" title={t("mail.start.saved", { day: fromDay(settings.mail.start) })} live />
      ) : null}
    </form>
  );
}
