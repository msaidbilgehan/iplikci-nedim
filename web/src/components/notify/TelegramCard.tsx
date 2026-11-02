// Telegram (F13, ADR-0010): the user's own bot. Its token is entered once, checked with Telegram and kept in the
// keyring; it never comes back to the page, and the page keeps no copy once it is sent. A one-time code then pairs
// the chat: the user sends it to the bot, and the page asks the service every few seconds whether it came. The
// channel's stage, as the service names it, says which step is next.

import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useEffectEvent, useId, useState } from "react";

import {
  checkTelegramPairing,
  keys,
  sendTelegramToken,
  useLabels,
  useNotifySettings,
  useRemoveTelegram,
  useStartTelegramPairing,
} from "../../api/queries";
import type { ChannelStage, ChannelState, Labels, TelegramBot, TelegramPairing } from "../../api/types";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FIELD, labelOf, LINK, messageOf, MUTED, STAGE_TONES } from "./common";

export const CHECK_EVERY_MS = 3000; // how often the page asks whether the code reached the bot

// The stages in which a token is entered: none yet, the keyring lost it, or Telegram refused it (a stopped channel).
const NEEDS_TOKEN: ReadonlySet<ChannelStage> = new Set(["no_bot", "token_lost", "stopped"]);

export function TelegramCard() {
  const settings = useNotifySettings();
  const labels = useLabels().data ?? {};
  const state = settings.data?.channels.find((channel) => channel.channel === "telegram");
  return (
    <Card title="Telegram">
      {settings.isPending ? <Loading /> : null}
      {settings.isError ? <Failure error={settings.error} onRetry={() => void settings.refetch()} /> : null}
      {state ? <TelegramSetup state={state} labels={labels} /> : null}
    </Card>
  );
}

function TelegramSetup({ state, labels }: { state: ChannelState; labels: Labels }) {
  const stage = state.stage; // "ready": paired, whether the channel is on or not
  const [bot, setBot] = useState<TelegramBot | null>(null); // the token just entered, as Telegram named its bot
  const [paired, setPaired] = useState(false); // the chat paired on this page just now
  const remove = useRemoveTelegram();
  const needsToken = NEEDS_TOKEN.has(stage) && bot === null;

  function forget() {
    const asked = "Telegram kaldırılsın mı? Bot belirteci ve eşleşen sohbet unutulur; bildirimler Telegram'a gitmez.";
    if (window.confirm(asked)) {
      remove.mutate(undefined, {
        onSuccess: () => {
          setBot(null);
          setPaired(false);
        },
      });
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Bildirimler kendi Telegram botunuzla size gelir. Telegram iletileri uçtan uca şifreli değildir; ne kadar ayrıntı
        gideceğini Kanallar kartında seçersiniz.
      </p>
      <div className="flex flex-col gap-1 text-sm">
        <span>
          <Badge tone={STAGE_TONES[stage]}>{labelOf(labels, "ChannelStage", stage)}</Badge>
        </span>
        <p>{state.note}</p>
      </div>
      {stage === "stopped" && bot === null ? (
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          Telegram reddettiği için kanal durdu; program kendiliğinden yeniden denemez. Bot silindiyse ya da belirteç
          değiştiyse belirteci yeniden girin. Botu engellediyseniz engeli Telegram'da kaldırıp Kanallar kartından deneme
          bildirimi gönderin.
        </p>
      ) : null}
      {needsToken ? <TokenForm again={stage !== "no_bot"} onSaved={setBot} /> : null}
      {bot && !paired && stage !== "ready" ? (
        <Alert tone="good" title={`@${bot.bot} botu kaydedildi`} live>
          <p>Şimdi botla sohbetinizi eşleştirin.</p>
        </Alert>
      ) : null}
      {bot && !bot.in_keyring ? (
        <Alert tone="warning" title="Belirteç saklanamadı">
          <p>Belirteç doğrulandı, ama bu bilgisayarda anahtar zinciri olmadığı için saklanamadı; Telegram çalışmaz.</p>
        </Alert>
      ) : null}
      {stage === "not_paired" && !paired ? <PairingPanel onPaired={() => setPaired(true)} /> : null}
      {paired ? (
        <Alert tone="good" title="Telegram bağlandı" live>
          <p>Bildirimler artık bu sohbete gelecek; bot bir karşılama iletisi gönderdi.</p>
        </Alert>
      ) : null}
      {stage === "ready" && !state.on ? (
        <Alert tone="neutral" title="Telegram kanalı kapalı">
          <p>Bildirimlerin Telegram'a gitmesi için Kanallar kartında Telegram'ı açıp kaydedin.</p>
        </Alert>
      ) : null}
      {stage !== "no_bot" ? (
        <Button variant="danger" className="self-start" onClick={forget} disabled={remove.isPending}>
          {remove.isPending ? "Kaldırılıyor…" : "Telegram'ı kaldır"}
        </Button>
      ) : null}
      {remove.isError ? (
        <Alert tone="critical" title="Telegram kaldırılamadı" live>
          <p>{remove.error.message}</p>
        </Alert>
      ) : null}
      {remove.isSuccess && stage === "no_bot" ? <Alert tone="good" title="Telegram kaldırıldı" live /> : null}
    </div>
  );
}

/** The bot's token, read from the field when the form is sent and gone from the page with that request. */
function TokenForm({ again, onSaved }: { again: boolean; onSaved: (bot: TelegramBot) => void }) {
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
      setFailure(messageOf(error));
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3">
      {again ? <p className="text-sm font-medium">Bot belirtecini yeniden girin.</p> : null}
      <ol id={stepsId} className="list-decimal pl-5 text-sm">
        <li>
          Telegram'da{" "}
          <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className={LINK}>
            @BotFather
          </a>{" "}
          ile bir sohbet açın.
        </li>
        <li>
          <code>/newbot</code> yazın; bota bir ad ve sonu "bot" ile biten bir kullanıcı adı verin.
        </li>
        <li>BotFather'ın verdiği belirteci (123456789:AA… biçiminde) aşağıya yapıştırın.</li>
      </ol>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span>Bot belirteci</span>
          <input
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
          {sending ? "Denetleniyor…" : "Belirteci kaydet"}
        </Button>
      </div>
      <p className={MUTED}>
        Belirteç Telegram'la denenir ve bu bilgisayarın anahtar zincirinde saklanır; bir daha gösterilmez.
      </p>
      {failure ? (
        <div id={errorId}>
          <Alert tone="critical" title="Belirteç kaydedilemedi" live>
            <p>{failure}</p>
          </Alert>
        </div>
      ) : null}
    </form>
  );
}

function PairingPanel({ onPaired }: { onPaired: () => void }) {
  const start = useStartTelegramPairing();
  const pairing = start.data;
  const watch = usePairingWatch(pairing, onPaired);
  return (
    <div className="flex flex-col gap-3">
      <ol className="list-decimal pl-5 text-sm">
        <li>Aşağıdan bir eşleştirme kodu alın.</li>
        <li>Bağlantıyla botunuzun sohbetini açıp "Başlat"a basın ya da bota /start ve kodu yazın.</li>
        <li>Kod bota ulaşınca eşleşme burada kendiliğinden görünür.</li>
      </ol>
      {pairing && watch.waiting ? <PairingCode pairing={pairing} left={watch.left} /> : null}
      {pairing && watch.expired ? (
        <Alert tone="warning" title="Kodun süresi doldu">
          <p>Yeni bir kod alın.</p>
        </Alert>
      ) : null}
      {watch.failure ? (
        <Alert tone="critical" title="Eşleşme denetlenemedi" live>
          <p>{watch.failure}</p>
        </Alert>
      ) : null}
      {start.isError ? (
        <Alert tone="critical" title="Eşleştirme kodu alınamadı" live>
          <p>{start.error.message}</p>
        </Alert>
      ) : null}
      <Button className="self-start" onClick={() => start.mutate()} disabled={start.isPending}>
        {pairing ? "Yeni kod al" : "Eşleştirme kodu al"}
      </Button>
    </div>
  );
}

function PairingCode({ pairing, left }: { pairing: TelegramPairing; left: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-1">
      <span className="text-sm text-zinc-600 dark:text-zinc-300">Eşleştirme kodu</span>
      <span className="font-mono text-3xl tracking-widest">{pairing.code}</span>
      {pairing.link ? (
        <a href={pairing.link} target="_blank" rel="noopener noreferrer" className={`self-start ${LINK}`}>
          Telegram'da @{pairing.bot} sohbetini aç
        </a>
      ) : null}
      <span className="text-sm">
        Ya da bota şunu gönderin: <code>/start {pairing.code}</code>
      </span>
      <span className={MUTED}>
        Tek kullanımlık; {Math.max(1, Math.ceil(left / 60_000))} dakika içinde gönderin. Kod gelince bu sayfa
        kendiliğinden güncellenir.
      </span>
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
function usePairingWatch(pairing: TelegramPairing | undefined, onPaired: () => void): Watch {
  const client = useQueryClient();
  const [failure, setFailure] = useState<{ code: string; message: string } | null>(null);
  const ends = pairing ? Date.parse(pairing.expires) : null;
  const now = useClock(ends);
  const paired = useEffectEvent(() => {
    void client.invalidateQueries({ queryKey: keys.notifySettings });
    onPaired();
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
          setFailure({ code: pairing.code, message: messageOf(error) });
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
  const failed = failure !== null && failure.code === pairing?.code ? failure.message : "";
  const open = ends !== null && now < ends;
  return {
    waiting: open && !failed,
    expired: pairing !== undefined && !open,
    failure: failed,
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
