// The program's own updates on the Settings screen (ADR-0022, F21): which version runs, whether a newer one is out,
// what it brings and whether it is installed by itself. "Şimdi denetle" asks GitHub now whatever the mode says;
// "Şimdi güncelle" installs the version found, after a backup, and the service starts again with it. A copy installed
// by hand cannot install itself: the card leads to the release's page instead. The release's notes are the
// changelog's Markdown, shown as text: headings and list items only, nothing of it is taken as HTML.

import { type ReactNode, useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useCheckUpdate, useInstallUpdate, useUpdate, useUpdateMode } from "../../api/queries";
import type { UpdateMode, UpdateRelease, UpdateState } from "../../api/types";
import { formatDay, formatSize, formatTime } from "../../lib/format";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";
import { Explain } from "../ui/Explain";
import { Say } from "../ui/Say";
import { LINK } from "./MailFields";
import { HINT } from "./NameList";

const MODES: readonly UpdateMode[] = ["auto", "ask", "off"];
const WAIT_MS = 30_000; // how long the card asks again every few seconds after "Şimdi denetle"

export function UpdatesCard() {
  const { t } = useTranslation("settings");
  const [waitingSince, setWaitingSince] = useState<string | null>(null); // the check time before the one asked for
  const update = useUpdate(waitingSince !== null);
  const found = update.data;
  useEffect(() => {
    if (waitingSince === null) {
      return undefined;
    }
    const stop = window.setTimeout(() => setWaitingSince(null), WAIT_MS);
    return () => window.clearTimeout(stop);
  }, [waitingSince]);
  useEffect(() => {
    if (waitingSince !== null && found && found.checked_at !== waitingSince) {
      setWaitingSince(null); // the check asked for is done
    }
  }, [found, waitingSince]);
  return (
    <Card title={t("updates.title")} action={found ? <UpdateBadge state={found} /> : undefined}>
      {found ? (
        <Say>
          <Sentence state={found} />
        </Say>
      ) : null}
      {update.isPending ? <Loading /> : null}
      {update.isError ? <Failure error={update.error} onRetry={() => void update.refetch()} /> : null}
      {found ? (
        <UpdateFields
          state={found}
          checking={waitingSince !== null}
          onCheck={() => setWaitingSince(found.checked_at)}
        />
      ) : null}
    </Card>
  );
}

function UpdateBadge({ state }: { state: UpdateState }) {
  const { t } = useTranslation("settings");
  if (state.installing) {
    return <Badge tone="warning">{t("updates.badgeInstalling")}</Badge>;
  }
  if (state.available) {
    return <Badge tone="warning">{t("updates.badgeNew")}</Badge>;
  }
  if (state.mode === "off" && !state.checked_at) {
    return <Badge tone="neutral">{t("updates.badgeOff")}</Badge>;
  }
  return <Badge tone="good">{t("updates.badgeCurrent")}</Badge>;
}

/** The simple view's sentence: what happens with new versions here, or what is under way. */
function Sentence({ state }: { state: UpdateState }) {
  const { t } = useTranslation("settings");
  if (state.installing) {
    return t("updates.sayInstalling", { version: state.installing });
  }
  if (state.available) {
    return state.automatic
      ? t("updates.sayNew", { version: state.available.version })
      : t("updates.sayNewByHand", { version: state.available.version });
  }
  if (!state.automatic) {
    return t("updates.sayByHand");
  }
  return t(`updates.say_${state.mode}`);
}

interface FieldsProps {
  state: UpdateState;
  checking: boolean;
  onCheck: () => void;
}

function UpdateFields({ state, checking, onCheck }: FieldsProps) {
  const { t } = useTranslation("settings");
  const check = useCheckUpdate();
  const facts: Array<[string, ReactNode]> = [
    [t("updates.version"), state.version],
    [t("updates.checked"), state.checked_at ? formatTime(state.checked_at) : t("updates.never")],
  ];
  if (state.last) {
    facts.push([
      t("updates.last"),
      t(state.last.ok ? "updates.lastOk" : "updates.lastFailed", {
        from: state.last.from_version,
        to: state.last.to_version,
        at: formatTime(state.last.at),
      }),
    ]);
  }
  return (
    <div className="flex flex-col gap-4">
      <Facts items={facts} />
      {state.check_error ? (
        <Alert tone="warning" title={t("updates.checkFailed")}>
          <p>{state.check_error}</p>
        </Alert>
      ) : null}
      {state.last && !state.last.ok ? (
        <Alert tone="critical" title={t("updates.installFailed", { version: state.last.to_version })}>
          <p>{state.last.error}</p>
        </Alert>
      ) : null}
      {state.installing ? (
        <Alert tone="warning" title={t("updates.installingTitle", { version: state.installing })} live>
          <p>{t("updates.installingText")}</p>
        </Alert>
      ) : null}
      {state.available && !state.installing ? <Release state={state} release={state.available} /> : null}
      {!state.available && state.checked_at && !state.check_error && !checking ? (
        <p className="text-sm">{t("updates.current")}</p>
      ) : null}
      <div className="flex flex-col gap-1">
        <Button
          variant="secondary"
          className="self-start"
          disabled={check.isPending || checking || Boolean(state.installing)}
          onClick={() => check.mutate(undefined, { onSuccess: onCheck })}
        >
          {checking ? t("updates.checking") : t("updates.check")}
        </Button>
        <span aria-live="polite" className={HINT}>
          {checking ? t("updates.checkingText") : ""}
        </span>
        {check.isError ? <Alert tone="critical" title={check.error.message} live /> : null}
      </div>
      <ModeChoice state={state} />
      <p className={HINT}>{t("updates.privacy")}</p>
    </div>
  );
}

/** The version found: its day, its size, what it brings, and the way to install it. */
function Release({ state, release }: { state: UpdateState; release: UpdateRelease }) {
  const { t } = useTranslation("settings");
  const install = useInstallUpdate();
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="flex flex-col gap-2 text-sm">
      <h3 id={heading} className="text-sm font-semibold">
        {t("updates.newTitle", { version: release.version, day: formatDay(release.date) })}
      </h3>
      {release.notes ? (
        <Explain label={t("updates.notes")}>
          <ReleaseNotes text={release.notes} />
        </Explain>
      ) : null}
      {state.automatic && release.size > 0 ? (
        <>
          <Button
            className="self-start"
            disabled={install.isPending || install.isSuccess}
            onClick={() => install.mutate()}
          >
            {t("updates.install", { size: formatSize(release.size) })}
          </Button>
          <p className={HINT}>{t("updates.installHint")}</p>
          {install.isSuccess ? (
            <Alert tone="good" title={t("updates.installAsked")} live>
              <p>{t("updates.installingText")}</p>
            </Alert>
          ) : null}
          {install.isError ? (
            <Alert tone="critical" title={t("updates.installRefused")} live>
              <p>{install.error.message}</p>
            </Alert>
          ) : null}
        </>
      ) : (
        <p>
          {state.automatic ? t("updates.noFile") : t("updates.byHand")}{" "}
          <a
            href={release.page}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${t("updates.page")} ${t("updates.newTab")}`}
            className={LINK}
          >
            {t("updates.page")}
          </a>
        </p>
      )}
    </section>
  );
}

/** Whether a new version is installed by itself, only told, or never asked for: a choice of three. */
function ModeChoice({ state }: { state: UpdateState }) {
  const { t } = useTranslation("settings");
  const save = useUpdateMode();
  const name = useId();
  const legend = useId();
  return (
    <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 text-sm dark:border-zinc-700">
      <fieldset className="flex flex-col gap-2" disabled={save.isPending} aria-labelledby={legend}>
        <legend id={legend} className="text-sm font-semibold">
          {t("updates.modeLegend")}
        </legend>
        {MODES.map((mode) => (
          <label key={mode} className="flex min-h-11 cursor-pointer items-start gap-2">
            <input
              type="radio"
              className="mt-1 size-4 accent-teal-700 dark:accent-teal-400"
              name={name}
              value={mode}
              checked={state.mode === mode}
              onChange={() => save.mutate(mode)}
            />
            <span className="flex flex-col">
              <span className="font-medium">{t(`updates.mode_${mode}`)}</span>
              <span className="text-zinc-600 dark:text-zinc-400">
                {t(state.automatic || mode === "off" ? `updates.mode_${mode}Hint` : "updates.modeByHandHint")}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <span aria-live="polite" className="text-zinc-700 dark:text-zinc-300">
        {save.isSuccess ? t("updates.saved") : ""}
      </span>
      {save.isError ? (
        <Alert tone="critical" title={t("updates.saveFailed")} live>
          <p>{save.error.message}</p>
        </Alert>
      ) : null}
    </div>
  );
}

interface Part {
  kind: "heading" | "item" | "text";
  text: string;
}

/** The changelog's section in parts: "### " headings, "- " list items with the lines that go on under them, and
 * paragraphs. Marks of emphasis and code are left out; links stay as their words. */
export function notesParts(text: string): Part[] {
  const parts: Part[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const last = parts.at(-1);
    if (!line.trim()) {
      parts.push({ kind: "text", text: "" });
    } else if (line.startsWith("#")) {
      parts.push({ kind: "heading", text: plain(line.replace(/^#+\s*/, "")) });
    } else if (/^\s*[-*]\s+/.test(line)) {
      parts.push({ kind: "item", text: plain(line.replace(/^\s*[-*]\s+/, "")) });
    } else if (last && last.kind !== "heading" && last.text) {
      last.text = `${last.text} ${plain(line.trim())}`;
    } else {
      parts.push({ kind: "text", text: plain(line.trim()) });
    }
  }
  return parts.filter((part) => part.text);
}

function plain(text: string): string {
  return text.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[`*_]/g, "");
}

function ReleaseNotes({ text }: { text: string }) {
  const parts = notesParts(text);
  const blocks: ReactNode[] = [];
  let items: string[] = [];
  const flush = () => {
    if (items.length) {
      blocks.push(
        <ul key={`l${blocks.length}`} className="flex list-disc flex-col gap-1 pl-5">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>,
      );
      items = [];
    }
  };
  for (const part of parts) {
    if (part.kind === "item") {
      items.push(part.text);
      continue;
    }
    flush();
    blocks.push(
      part.kind === "heading" ? (
        <h4 key={`h${blocks.length}`} className="font-semibold">
          {part.text}
        </h4>
      ) : (
        <p key={`p${blocks.length}`}>{part.text}</p>
      ),
    );
  }
  flush();
  return <div className="flex max-h-80 flex-col gap-2 overflow-y-auto text-sm">{blocks}</div>;
}
