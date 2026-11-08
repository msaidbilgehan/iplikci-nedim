// Telegram (F13, ADR-0010): the user's own bot. Its token is entered once, checked with Telegram and kept in the
// keyring; it never comes back to the page, and the page keeps no copy once it is sent. A one-time code then pairs
// the chat: the user sends it to the bot, and the page asks the service every few seconds whether it came. The
// channel's stage, as the service names it, says which step is next; the simple view says it in a sentence. Once the
// chat is paired, the documents it sends the bot are taken into the archive unless the user turns that off
// (ADR-0021).

import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useEffectEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  checkTelegramPairing,
  keys,
  sendTelegramToken,
  useLabels,
  useNotifySettings,
  useRemoveTelegram,
  useSetTelegramDocuments,
  useStartTelegramPairing,
} from "../../api/queries";
import type { ChannelStage, ChannelState, Labels, TelegramBot, TelegramPairing } from "../../api/types";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Say } from "../ui/Say";
import { CHECKBOX, FIELD, labelOf, LINK, messageOf, MUTED, STAGE_TONES } from "./common";

export const CHECK_EVERY_MS = 3000; // how often the page asks whether the code reached the bot

// The stages in which a token is entered: none yet, the keyring lost it, or Telegram refused it (a stopped channel).
const NEEDS_TOKEN: ReadonlySet<ChannelStage> = new Set(["no_bot", "token_lost", "stopped"]);

// What each stage means for the user, in a sentence; a paired chat whose channel is off says so instead.
const SAYS = {
  ready: "telegram.say.ready",
  not_paired: "telegram.say.notPaired",
  no_bot: "telegram.say.noBot",
  token_lost: "telegram.say.tokenLost",
  stopped: "telegram.say.stopped",
  unavailable: "telegram.say.unavailable",
} as const satisfies Record<ChannelStage, string>;

export function TelegramCard() {
  const { t } = useTranslation("notifications");
  const settings = useNotifySettings();
  const labels = useLabels().data ?? {};
  const state = settings.data?.channels.find((channel) => channel.channel === "telegram");
  const documents = settings.data?.telegram_documents ?? false;
  return (
    <Card title={t("telegram.title")}>
      {state ? <TelegramSay state={state} documents={documents} /> : null}
      {settings.isPending ? <Loading /> : null}
      {settings.isError ? <Failure error={settings.error} onRetry={() => void settings.refetch()} /> : null}
      {state ? <TelegramSetup state={state} labels={labels} /> : null}
      {state?.stage === "ready" ? <TelegramDocuments on={documents} /> : null}
    </Card>
  );
}

function TelegramSay({ state, documents }: { state: ChannelState; documents: boolean }) {
  const { t } = useTranslation("notifications");
  if (state.stage !== "ready") {
    return <Say>{t(SAYS[state.stage])}</Say>;
  }
  return <Say>{t(!state.on ? "telegram.say.readyOff" : documents ? "telegram.say.readyDocuments" : SAYS.ready)}</Say>;
}

/**
 * The documents the paired chat sends the bot (ADR-0021): taken into the archive and answered in the chat, or, turned
 * off, not read at all. Only the paired chat's are taken; what the user should know before sending one is said here.
 */
function TelegramDocuments({ on }: { on: boolean }) {
  const { t } = useTranslation("notifications");
  const change = useSetTelegramDocuments();
  const aboutId = useId();
  const headingId = useId();
  const checked = change.isPending ? change.variables : on;
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-2 border-t border-zinc-200 pt-3 dark:border-zinc-700"
    >
      <h3 id={headingId} className="text-sm font-semibold">
        {t("telegram.documents.title")}
      </h3>
      <p id={aboutId} className="text-sm text-zinc-700 dark:text-zinc-300">
        {t(checked ? "telegram.documents.on" : "telegram.documents.off")}
      </p>
      <label className="inline-flex min-h-11 items-center gap-2 text-sm">
        <input
          type="checkbox"
          className={CHECKBOX}
          checked={checked}
          disabled={change.isPending}
          onChange={(e) => change.mutate(e.target.checked)}
          aria-describedby={aboutId}
        />
        {t("telegram.documents.take")}
      </label>
      <p className={MUTED}>{t("telegram.documents.privacy")}</p>
      {change.isError ? (
        <Alert tone="critical" title={t("telegram.documents.failed")} live>
          <p>{change.error.message}</p>
        </Alert>
      ) : null}
    </section>
  );
}

function TelegramSetup({ state, labels }: { state: ChannelState; labels: Labels }) {
  const { t } = useTranslation("notifications");
  const stage = state.stage; // "ready": paired, whether the channel is on or not
  const [bot, setBot] = useState<TelegramBot | null>(null); // the token just entered, as Telegram named its bot
  const [paired, setPaired] = useState(false); // the chat paired on this page just now
  const remove = useRemoveTelegram();
  const removal = useRemoval(stage);
  const needsToken = NEEDS_TOKEN.has(stage) && bot === null;

  function forget() {
    remove.mutate(undefined, {
      onSuccess: () => {
        setBot(null);
        setPaired(false);
        removal.done();
      },
      onSettled: () => removal.ask(false),
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-zinc-700 dark:text-zinc-300">{t("telegram.intro")}</p>
      <div className="flex flex-col gap-1 text-sm">
        <span>
          <Badge tone={STAGE_TONES[stage]}>{labelOf(labels, "ChannelStage", stage)}</Badge>
        </span>
        <p>{state.note}</p>
      </div>
      {stage === "stopped" && bot === null ? (
        <p className="text-sm text-zinc-700 dark:text-zinc-300">{t("telegram.stopped")}</p>
      ) : null}
      {needsToken ? <TokenForm again={stage !== "no_bot"} inputId={removal.fieldId} onSaved={setBot} /> : null}
      {bot && !paired && stage !== "ready" ? (
        <Alert tone="good" title={t("telegram.botSaved", { bot: bot.bot })} live>
          <p>{t("telegram.pairNow")}</p>
        </Alert>
      ) : null}
      {bot && !bot.in_keyring ? (
        <Alert tone="warning" title={t("telegram.noKeyring")}>
          <p>{t("telegram.noKeyringText")}</p>
        </Alert>
      ) : null}
      {stage === "not_paired" && !paired ? <PairingPanel onPaired={() => setPaired(true)} /> : null}
      {paired ? (
        <Alert tone="good" title={t("telegram.paired")} live>
          <p>{t("telegram.pairedText")}</p>
        </Alert>
      ) : null}
      {stage === "ready" && !state.on ? (
        <Alert tone="neutral" title={t("telegram.off")}>
          <p>{t("telegram.offText")}</p>
        </Alert>
      ) : null}
      {stage !== "no_bot" ? (
        <Button
          variant="danger"
          className="self-start"
          onClick={() => {
            remove.reset();
            removal.ask(true);
          }}
          disabled={remove.isPending}
        >
          {remove.isPending ? t("telegram.removing") : t("telegram.remove")}
        </Button>
      ) : null}
      {remove.isError ? (
        <Alert tone="critical" title={t("telegram.removeFailed")} live>
          <p>{remove.error.message}</p>
        </Alert>
      ) : null}
      {remove.isSuccess && stage === "no_bot" ? <Alert tone="good" title={t("telegram.removed")} live /> : null}
      <ConfirmDialog
        open={removal.asking}
        onOpenChange={removal.ask}
        title={t("telegram.removeTitle")}
        description={t("telegram.removeText")}
        confirmLabel={remove.isPending ? t("telegram.removing") : t("telegram.remove")}
        variant="danger"
        busy={remove.isPending}
        onConfirm={forget}
      />
    </div>
  );
}

/**
 * Whether the removal is asked about. Once Telegram is gone, the focus goes to the token's field that takes the
 * button's place: the button that asked is gone, whichever comes first, the new stage or the question closing.
 */
function useRemoval(stage: ChannelStage) {
  const [asking, setAsking] = useState(false);
  const removed = useRef(false); // removed on this page, until the focus has moved
  const fieldId = useId();
  useEffect(() => {
    if (removed.current && !asking && stage === "no_bot") {
      removed.current = false;
      document.getElementById(fieldId)?.focus();
    }
  }, [asking, stage, fieldId]);
  return {
    asking,
    ask: setAsking,
    fieldId, // the token field's
    done() {
      removed.current = true;
    },
  };
}

interface TokenFormProps {
  again: boolean; // a token was entered before: the keyring lost it, or Telegram refused it
  inputId: string;
  onSaved: (bot: TelegramBot) => void;
}

/** The bot's token, read from the field when the form is sent and gone from the page with that request. */
function TokenForm({ again, inputId, onSaved }: TokenFormProps) {
  const { t } = useTranslation("notifications");
  const client = useQueryClient();
  const [filled, setFilled] = useState(false); // whether anything is typed; never the token itself
  const [sending, setSending] = useState(false);
  const [failure, setFailure] = useState("");
  const stepsId = useId();
  const errorId = useId();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const token = String(new FormData(form).get("token") ?? "").trim();
    form.reset();
    setFilled(false);
    if (!token) {
      return;
    }
    setSending(true);
    setFailure("");
    try {
      onSaved(await sendTelegramToken(client, token));
    } catch (error) {
      setFailure(messageOf(error, t("unexpected", { ns: "common" })));
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
      {again ? <p className="text-sm font-medium">{t("telegram.tokenAgain")}</p> : null}
      <ol id={stepsId} className="list-decimal pl-5 text-sm">
        <li>
          {t("telegram.step1Before")}{" "}
          <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className={LINK}>
            @BotFather
          </a>{" "}
          {t("telegram.step1After")}
        </li>
        <li>
          <code>/newbot</code> {t("telegram.step2After")}
        </li>
        <li>{t("telegram.step3")}</li>
      </ol>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span>{t("telegram.token")}</span>
          <input
            id={inputId}
            name="token"
            type="password"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            maxLength={100}
            onChange={(e) => {
              setFilled(e.target.value.trim() !== "");
              setFailure("");
            }}
            aria-describedby={failure ? `${stepsId} ${errorId}` : stepsId}
            aria-invalid={failure ? true : undefined}
            className={FIELD}
          />
        </label>
        <Button type="submit" disabled={!filled || sending}>
          {sending ? t("telegram.checking") : t("telegram.saveToken")}
        </Button>
      </div>
      <p className={MUTED}>{t("telegram.kept")}</p>
      {failure ? (
        <div id={errorId}>
          <Alert tone="critical" title={t("telegram.tokenFailed")} live>
            <p>{failure}</p>
          </Alert>
        </div>
      ) : null}
    </form>
  );
}

function PairingPanel({ onPaired }: { onPaired: () => void }) {
  const { t } = useTranslation("notifications");
  const start = useStartTelegramPairing();
  const pairing = start.data;
  const watch = usePairingWatch(pairing, onPaired, t("unexpected", { ns: "common" }));
  return (
    <div className="flex flex-col gap-3">
      <ol className="list-decimal pl-5 text-sm">
        <li>{t("telegram.pairStep1")}</li>
        <li>{t("telegram.pairStep2")}</li>
        <li>{t("telegram.pairStep3")}</li>
      </ol>
      {pairing && watch.waiting ? <PairingCode pairing={pairing} left={watch.left} /> : null}
      {pairing && watch.expired ? (
        <Alert tone="warning" title={t("telegram.expired")}>
          <p>{t("telegram.expiredText")}</p>
        </Alert>
      ) : null}
      {watch.failure ? (
        <Alert tone="critical" title={t("telegram.checkFailed")} live>
          <p>{watch.failure}</p>
        </Alert>
      ) : null}
      {start.isError ? (
        <Alert tone="critical" title={t("telegram.codeFailed")} live>
          <p>{start.error.message}</p>
        </Alert>
      ) : null}
      <Button className="self-start" onClick={() => start.mutate()} disabled={start.isPending}>
        {pairing ? t("telegram.newCode") : t("telegram.getCode")}
      </Button>
    </div>
  );
}

function PairingCode({ pairing, left }: { pairing: TelegramPairing; left: number }) {
  const { t } = useTranslation("notifications");
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-1">
      <span className="text-sm text-zinc-600 dark:text-zinc-300">{t("telegram.code")}</span>
      <span className="font-mono text-3xl tracking-widest">{pairing.code}</span>
      {pairing.link ? (
        <a href={pairing.link} target="_blank" rel="noopener noreferrer" className={`self-start ${LINK}`}>
          {t("telegram.openChat", { bot: pairing.bot })}
        </a>
      ) : null}
      <span className="text-sm">
        {t("telegram.sendThis")} <code>/start {pairing.code}</code>
      </span>
      <span className={MUTED}>{t("telegram.once", { minutes: Math.max(1, Math.ceil(left / 60_000)) })}</span>
    </div>
  );
}

interface Watch {
  waiting: boolean; // the code is open and the page asks whether it came
  expired: boolean;
  failure: string; // why the service could not tell; the page stopped asking
  left: number; // milliseconds until the code ends
}

/**
 * While a code is open, ask the service every few seconds whether it reached the bot; stop when it did, when the
 * code ends, or when the service refuses (a refused token is never tried again by a program: a new code starts
 * over).
 */
function usePairingWatch(pairing: TelegramPairing | undefined, onPaired: () => void, unexpected: string): Watch {
  const client = useQueryClient();
  const [failure, setFailure] = useState<{ code: string; message: string } | null>(null);
  const ends = pairing ? Date.parse(pairing.expires) : null;
  const now = useClock(ends);
  const paired = useEffectEvent(() => {
    void client.invalidateQueries({ queryKey: keys.notifySettings });
    onPaired();
  });
  const failed = useEffectEvent((code: string, error: unknown) => {
    setFailure({ code, message: messageOf(error, unexpected) });
  });
  useEffect(() => {
    if (!pairing) {
      return undefined;
    }
    const until = Date.parse(pairing.expires);
    let stopped = false;
    let timer = 0;
    const check = async () => {
      if (Date.now() >= until) {
        return;
      }
      try {
        const found = await checkTelegramPairing();
        if (stopped) {
          return;
        }
        if (found.paired) {
          paired();
          return;
        }
      } catch (error) {
        if (!stopped) {
          failed(pairing.code, error);
        }
        return;
      }
      timer = window.setTimeout(() => void check(), CHECK_EVERY_MS);
    };
    timer = window.setTimeout(() => void check(), CHECK_EVERY_MS);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [pairing]);
  const message = failure !== null && failure.code === pairing?.code ? failure.message : "";
  const open = ends !== null && now < ends;
  return {
    waiting: open && !message,
    expired: pairing !== undefined && !open,
    failure: message,
    left: ends === null ? 0 : Math.max(0, ends - now),
  };
}

/** The time now, ticking every second until `until` (milliseconds since the epoch) has passed; still without one. */
function useClock(until: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (until === null) {
      return undefined;
    }
    setNow(Date.now());
    const timer = window.setInterval(() => {
      const at = Date.now();
      setNow(at);
      if (at >= until) {
        window.clearInterval(timer);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return now;
}
