// The service's own life on the Settings screen (ADR-0017, "Her iş arayüzde"): its state, stopping it, restarting it,
// putting a backup back and removing it from the computer. The service answers each step first and ends after the
// answer; the page then says what happened in place of its cards, whose questions could only fail now. A restart and a
// restore wait until the new service answers. A restored service does not know this session, so the page says to open
// the app again rather than that the session closed. Restarting, restoring and removing need the service registered
// for this data folder: one run by hand would only end, and removing it would take off another folder's registration.

import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useEffectEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type ServiceAnswer,
  serviceAnswer,
  useBackups,
  useLabels,
  useRemoveService,
  useRestartService,
  useRestoreBackup,
  useServiceState,
  useSetup,
  useStopService,
} from "../../api/queries";
import type { BackupItem, ServiceState } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatSize, formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge, type Tone } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Say } from "../ui/Say";
import { HINT } from "./NameList";

export const POLL_MS = 1000; // how often the page asks whether the new service answers
export const GIVE_UP_MS = 90_000; // a Windows task may take a minute to start the service again

type Why = "restart" | "restore";

/** Where the page stands after a step that ended the service. */
export type Ending =
  | { kind: "stopped" }
  | { kind: "removed"; dataToTrash: boolean; home: string; manager: string }
  | { kind: "waiting"; why: Why; before: string } // before: when the service that ended had started
  | { kind: "slow"; why: Why; before: string }
  | { kind: "back"; why: Why; signedOut: boolean }
  | { kind: "notRestored"; error: string }; // the new service could not put the backup back: the data stayed

/** Whether the page shows its cards: not while the service is gone, nor when a new session is needed. */
export function showsCards(ending: Ending | null): boolean {
  return ending === null || (ending.kind === "back" && ending.why === "restart" && !ending.signedOut);
}

// How the app itself is removed on each system, by the service manager the service named; all three when unknown.
const SYSTEMS = ["mac", "windows", "linux"] as const;
const SYSTEM_OF: Readonly<Record<string, (typeof SYSTEMS)[number]>> = {
  launchd: "mac",
  systemd: "linux",
  "Görev Zamanlayıcı": "windows",
};

/** What happened after a step that ended the service, and while a restart or a restore waits for the new one. */
export function EndingState({ ending, onChange }: { ending: Ending; onChange: (next: Ending) => void }) {
  const { t } = useTranslation("settings");
  const client = useQueryClient();
  useServiceReturn(ending, onChange, () => void client.invalidateQueries());
  switch (ending.kind) {
    case "stopped":
      return <Outcome tone="neutral" title={t("service.stopped")} />;
    case "removed": {
      const system = SYSTEM_OF[ending.manager];
      return (
        <Outcome tone="good" title={t("service.removed")}>
          <p>{ending.dataToTrash ? t("service.removedTrash") : t("service.removedKept", { home: ending.home })}</p>
          <p>{t("service.removeApp")}</p>
          <ul className="list-disc pl-5">
            {(system ? [system] : SYSTEMS).map((one) => (
              <li key={one}>{t(`service.app.${one}`)}</li>
            ))}
          </ul>
        </Outcome>
      );
    }
    case "waiting":
      return (
        <Outcome tone="neutral" title={ending.why === "restart" ? t("service.restarting") : t("backup.restoring")} busy>
          <Loading label={ending.why === "restart" ? t("service.restarting") : t("backup.restoring")} />
        </Outcome>
      );
    case "slow":
      return (
        <Outcome tone="warning" title={t("service.slow")}>
          <p>{t("service.slowText", { seconds: GIVE_UP_MS / 1000 })}</p>
          <Button
            variant="secondary"
            className="self-start"
            onClick={() => onChange({ kind: "waiting", why: ending.why, before: ending.before })}
          >
            {t("service.waitAgain")}
          </Button>
        </Outcome>
      );
    case "notRestored":
      return (
        <Outcome tone="critical" title={t("backup.notRestored")}>
          <p>{ending.error}</p>
          <p>{t("backup.notRestoredText")}</p>
        </Outcome>
      );
    case "back":
      if (ending.why === "restore") {
        return (
          <Outcome tone="good" title={t("backup.restored")}>
            <p>{t("backup.restoredText")}</p>
          </Outcome>
        );
      }
      return <Outcome tone="good" title={ending.signedOut ? t("service.signedOut") : t("service.restarted")} />;
  }
}

/**
 * While a restart or a restore waits, ask every second which service answers: a new one (or one that does not know
 * this session) ends the wait; none within a minute and a half says so.
 */
function useServiceReturn(ending: Ending, onChange: (next: Ending) => void, onRestarted: () => void): void {
  const answered = useEffectEvent((why: Why, answer: ServiceAnswer) => {
    const signedOut = answer.kind === "signedOut";
    // A restore the start could not do keeps the data and its sessions: the same session reads why.
    const failed = why === "restore" && answer.kind === "new" ? answer.state.restore : null;
    if (failed && !failed.ok) {
      onRestarted();
      onChange({ kind: "notRestored", error: failed.error });
      return;
    }
    if (why === "restart" && !signedOut) {
      onRestarted(); // the same session goes on: everything is asked again of the new service
    }
    onChange({ kind: "back", why, signedOut });
  });
  const gaveUp = useEffectEvent((why: Why, before: string) => onChange({ kind: "slow", why, before }));
  const waiting = ending.kind === "waiting" ? ending : null;
  useEffect(() => {
    if (waiting === null) {
      return undefined;
    }
    const until = Date.now() + GIVE_UP_MS;
    let stopped = false;
    let timer = 0;
    const ask = async () => {
      const answer = await serviceAnswer(waiting.before);
      if (stopped) {
        return;
      }
      if (answer.kind === "new" || answer.kind === "signedOut") {
        answered(waiting.why, answer);
        return;
      }
      if (Date.now() >= until) {
        gaveUp(waiting.why, waiting.before);
        return;
      }
      timer = window.setTimeout(() => void ask(), POLL_MS);
    };
    timer = window.setTimeout(() => void ask(), POLL_MS);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [waiting]);
}

const TONES: Record<Tone, string> = {
  good: "border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950",
  warning: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950",
  critical: "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950",
  neutral: "border-zinc-300 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900",
};
const HEADING = cn(
  "rounded text-base font-semibold text-zinc-900 dark:text-zinc-100",
  "focus:outline-none focus-visible:outline-2 focus-visible:outline-teal-600",
);

interface OutcomeProps {
  tone: Tone;
  title: string;
  busy?: boolean;
  children?: ReactNode;
}

/** A step's outcome, its heading taking the focus as it changes: the button that asked is gone with the cards. */
function Outcome({ tone, title, busy = false, children }: OutcomeProps) {
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [title]);
  return (
    <section
      aria-labelledby={id}
      aria-busy={busy || undefined}
      className={cn("flex flex-col gap-3 rounded-lg border p-4 text-sm", TONES[tone])}
    >
      <h2 id={id} ref={heading} tabIndex={-1} className={HEADING}>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** The service as it runs now, whether it starts with the computer for this data folder, and its own steps. */
export function ServiceCard({ home, onEnding }: { home: string; onEnding: (ending: Ending) => void }) {
  const { t } = useTranslation("settings");
  const state = useServiceState();
  const step = useSetup().data?.steps.find((one) => one.step === "service");
  return (
    <Card title={t("page.service")}>
      <Say>{t("page.serviceSay")}</Say>
      <div className="flex flex-col gap-4">
        {state.isPending ? <Loading /> : null}
        {state.isError ? <Failure error={state.error} onRetry={() => void state.refetch()} /> : null}
        {state.data ? (
          <>
            <Facts
              items={[
                [t("service.version"), state.data.version],
                [t("service.since"), formatTime(state.data.started_at)],
                ...(step ? [[t("service.computer"), step.note] satisfies [string, ReactNode]] : []),
              ]}
            />
            <ServiceSteps state={state.data} home={home} onEnding={onEnding} />
          </>
        ) : null}
      </div>
    </Card>
  );
}

interface ServiceStepsProps {
  state: ServiceState;
  home: string;
  onEnding: (ending: Ending) => void;
}

/** Restart, stop and remove; stopping and removing ask first and say what follows. */
function ServiceSteps({ state, home, onEnding }: ServiceStepsProps) {
  const { t } = useTranslation("settings");
  const stop = useStopService();
  const restart = useRestartService();
  const remove = useRemoveService();
  const [asking, setAsking] = useState<"stop" | "remove" | null>(null);
  const [toTrash, setToTrash] = useState(false);
  const noteId = useId();
  const trashId = useId();
  if (!state.can_end) {
    return <p className={HINT}>{t("service.unmanaged")}</p>;
  }
  const busy = stop.isPending || restart.isPending || remove.isPending;
  const failed = [restart, stop, remove].find((step) => step.isError)?.error;
  const why = state.registered ? undefined : noteId;
  return (
    <div className="flex flex-col gap-3">
      {state.registered ? null : (
        <p id={noteId} className={HINT}>
          {t("service.notRegistered")}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={busy || !state.registered}
          aria-describedby={why}
          onClick={() =>
            restart.mutate(undefined, {
              onSuccess: () => onEnding({ kind: "waiting", why: "restart", before: state.started_at }),
            })
          }
        >
          {t("service.restart")}
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            stop.reset();
            setAsking("stop");
          }}
        >
          {t("service.stop")}
        </Button>
        <Button
          variant="danger"
          disabled={busy || !state.registered}
          aria-describedby={why}
          onClick={() => {
            remove.reset();
            setToTrash(false);
            setAsking("remove");
          }}
        >
          {t("service.remove")}
        </Button>
      </div>
      {failed ? (
        <Alert tone="critical" title={t("service.failed")} live>
          <p>{failed.message}</p>
        </Alert>
      ) : null}
      <ConfirmDialog
        open={asking === "stop"}
        onOpenChange={(open) => setAsking(open ? "stop" : null)}
        title={t("service.stopTitle")}
        description={t("service.stopText")}
        confirmLabel={t("service.stopConfirm")}
        busy={stop.isPending}
        onConfirm={() =>
          stop.mutate(undefined, { onSuccess: () => onEnding({ kind: "stopped" }), onSettled: () => setAsking(null) })
        }
      />
      <ConfirmDialog
        open={asking === "remove"}
        onOpenChange={(open) => setAsking(open ? "remove" : null)}
        title={t("service.removeTitle")}
        description={t("service.removeText")}
        confirmLabel={t("service.removeConfirm")}
        variant="danger"
        busy={remove.isPending}
        onConfirm={() =>
          remove.mutate(toTrash, {
            onSuccess: () => onEnding({ kind: "removed", dataToTrash: toTrash, home, manager: state.manager }),
            onSettled: () => setAsking(null),
          })
        }
      >
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            checked={toTrash}
            onChange={(event) => setToTrash(event.target.checked)}
            aria-describedby={trashId}
            className="mt-0.5 size-5 shrink-0 accent-teal-700"
          />
          <span className="font-medium">{t("service.removeData")}</span>
        </label>
        <p id={trashId} className={cn("mt-1", HINT)}>
          {t("service.removeDataHint", { home })}
        </p>
      </ConfirmDialog>
    </div>
  );
}

/** The whole backups, newest first, each put back after saying exactly what happens; a damaged one cannot be. */
export function BackupRestore({ onEnding }: { onEnding: (ending: Ending) => void }) {
  const { t } = useTranslation("settings");
  const backups = useBackups();
  const service = useServiceState().data;
  const labels = useLabels().data ?? {};
  const restore = useRestoreBackup();
  const [chosen, setChosen] = useState<BackupItem | null>(null);
  const noteId = useId();
  const allowed = service !== undefined && service.registered && service.can_end;
  const items = backups.data ?? [];
  return (
    <div className="flex flex-col gap-2 text-sm">
      <h3 className="font-semibold">{t("backup.restoreTitle")}</h3>
      <p className={HINT}>{t("backup.restoreAbout")}</p>
      {service !== undefined && !allowed ? (
        <p id={noteId} className={HINT}>
          {t("backup.notRegistered")}
        </p>
      ) : null}
      {backups.isPending ? <Loading /> : null}
      {backups.isError ? <Failure error={backups.error} onRetry={() => void backups.refetch()} /> : null}
      {backups.isSuccess && items.length === 0 ? <p className={HINT}>{t("backup.empty")}</p> : null}
      {items.length > 0 ? (
        <ul aria-label={t("backup.list")} className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
          {items.map((item) => (
            <li key={item.name} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="font-medium">{formatTime(item.created_at)}</span>
                <span className={HINT}>
                  {t("backup.item", {
                    reason: labelOf(labels, "BackupReason", item.reason),
                    app: item.app,
                    documents: item.documents,
                    size: formatSize(item.size),
                  })}
                </span>
                {item.damaged > 0 ? (
                  <span>
                    <Badge tone="critical">{t("backup.damaged", { count: item.damaged })}</Badge>
                  </span>
                ) : null}
              </div>
              <Button
                variant="secondary"
                disabled={!allowed || item.damaged > 0 || restore.isPending}
                aria-label={t("backup.restoreLabel", { time: formatTime(item.created_at) })}
                aria-describedby={allowed ? undefined : noteId}
                onClick={() => {
                  restore.reset();
                  setChosen(item);
                }}
              >
                {t("backup.restore")}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {restore.isError ? (
        <Alert tone="critical" title={t("backup.refused")} live>
          <p>{restore.error.message}</p>
        </Alert>
      ) : null}
      <ConfirmDialog
        open={chosen !== null}
        onOpenChange={(open) => (open ? undefined : setChosen(null))}
        title={t("backup.confirmTitle", { time: chosen ? formatTime(chosen.created_at) : "" })}
        description={t("backup.confirmText")}
        confirmLabel={t("backup.confirm")}
        variant="danger"
        busy={restore.isPending}
        onConfirm={() => {
          if (chosen !== null && service !== undefined) {
            const before = service.started_at;
            restore.mutate(chosen.name, {
              onSuccess: () => onEnding({ kind: "waiting", why: "restore", before }),
              onSettled: () => setChosen(null),
            });
          }
        }}
      />
    </div>
  );
}
