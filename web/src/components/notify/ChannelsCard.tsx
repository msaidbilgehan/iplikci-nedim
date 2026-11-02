// The channels (F13, ADR-0010): the quiet hours, which channels are on and how much each says, and whether each can
// carry a notification now, in the service's own words. A test notification goes on any channel, on or off; when it
// cannot go, the service says why. The simple view says in a sentence where notifications go; the detailed view adds
// each channel's state as the service gives it.

import type { TFunction } from "i18next";
import { type FormEvent, type ReactNode, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useLabels, useNotifySettings, useSetNotifySettings, useTestNotification } from "../../api/queries";
import type { Channel, ChannelState, DetailLevel, Labels, NotifyPreferences, NotifySettings } from "../../api/types";
import { Detailed } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import {
  CHECKBOX,
  DETAIL_LEVELS,
  FIELD,
  labelOf,
  MUTED,
  perChannel,
  PUSH_CHANNELS,
  type PushChannel,
  STAGE_TONES,
} from "./common";

const CLOCK = /^([01]\d|2[0-3]):[0-5]\d$/;
const QUIET_DEFAULT = { start: "23:00", end: "08:00" }; // the shipped quiet hours, offered when they are turned on
const CHANNEL_BOX = "flex flex-col gap-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700";
const NOTE = "text-sm text-zinc-700 dark:text-zinc-300";

interface Draft {
  quiet: boolean;
  start: string;
  end: string;
  on: Record<PushChannel, boolean>;
  detail: Record<PushChannel, DetailLevel>;
}

function stateOf(settings: NotifySettings, channel: Channel): ChannelState | undefined {
  return settings.channels.find((state) => state.channel === channel);
}

function draftOf(settings: NotifySettings): Draft {
  const [start, end] = settings.quiet_hours.split("-");
  return {
    quiet: settings.quiet_hours !== "",
    start: start || QUIET_DEFAULT.start,
    end: end || QUIET_DEFAULT.end,
    on: perChannel((channel) => stateOf(settings, channel)?.on ?? false),
    detail: perChannel((channel) => settings.detail[channel] ?? "summary"),
  };
}

/** What is wrong with the quiet hours as typed; "" when nothing is. */
function quietProblem(draft: Draft, t: TFunction<"notifications">): string {
  if (!draft.quiet) {
    return "";
  }
  if (!CLOCK.test(draft.start) || !CLOCK.test(draft.end)) {
    return t("channels.needBoth");
  }
  return draft.start === draft.end ? t("channels.same") : "";
}

function preferencesOf(draft: Draft): NotifyPreferences {
  return {
    quiet_hours: draft.quiet ? `${draft.start}-${draft.end}` : "",
    detail: perChannel((channel) => draft.detail[channel]),
    channels: PUSH_CHANNELS.filter((channel) => draft.on[channel]),
  };
}

export function ChannelsCard() {
  const { t } = useTranslation("notifications");
  const settings = useNotifySettings();
  const labels = useLabels().data ?? {};
  return (
    <Card title={t("channels.title")}>
      {settings.data ? <ChannelsSay settings={settings.data} labels={labels} /> : null}
      {settings.isPending ? <Loading /> : null}
      {settings.isError ? <Failure error={settings.error} onRetry={() => void settings.refetch()} /> : null}
      {settings.data ? <ChannelsForm settings={settings.data} labels={labels} /> : null}
      {settings.data ? (
        <Detailed>
          <StatesTable settings={settings.data} labels={labels} />
        </Detailed>
      ) : null}
    </Card>
  );
}

/** Where notifications go now: the box always, then the channels that are on and can carry one; the quiet hours. */
function ChannelsSay({ settings, labels }: { settings: NotifySettings; labels: Labels }) {
  const { t } = useTranslation("notifications");
  const going = settings.channels
    .filter((state) => state.channel !== "in_app" && state.on && state.ready)
    .map((state) => labelOf(labels, "Channel", state.channel));
  const [start, end] = settings.quiet_hours.split("-");
  const quiet = start && end ? t("channels.sayQuiet", { start, end }) : t("channels.sayNoQuiet");
  const where = going.length > 0 ? t("channels.say", { channels: going.join(", ") }) : t("channels.sayInApp");
  return (
    <Say>
      {where} {quiet}
    </Say>
  );
}

/** Each channel as the service gives it: on or not, able to carry a notification or not, its stage and note. */
function StatesTable({ settings, labels }: { settings: NotifySettings; labels: Labels }) {
  const { t } = useTranslation("notifications");
  const yes = (value: boolean) => (value ? t("channels.yes") : t("channels.no"));
  return (
    <div className="mt-4 flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{t("channels.states")}</h3>
      <Table>
        <caption className="sr-only">{t("channels.stateCaption")}</caption>
        <thead>
          <tr>
            <Th>{t("channels.channel")}</Th>
            <Th>{t("channels.turnedOn")}</Th>
            <Th>{t("channels.ready")}</Th>
            <Th>{t("channels.stage")}</Th>
            <Th>{t("channels.detail")}</Th>
            <Th>{t("channels.note")}</Th>
          </tr>
        </thead>
        <tbody>
          {settings.channels.map((state) => {
            const level = settings.detail[state.channel];
            return (
              <tr key={state.channel}>
                <Td className="font-medium">{labelOf(labels, "Channel", state.channel)}</Td>
                <Td>{yes(state.on)}</Td>
                <Td>{yes(state.ready)}</Td>
                <Td>{labelOf(labels, "ChannelStage", state.stage)}</Td>
                <Td>{level ? labelOf(labels, "DetailLevel", level) : "—"}</Td>
                <Td className={MUTED}>{state.note || "—"}</Td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </div>
  );
}

function ChannelsForm({ settings, labels }: { settings: NotifySettings; labels: Labels }) {
  const { t } = useTranslation("notifications");
  const save = useSetNotifySettings();
  // null: nothing changed, so the service's settings show as they come; a refresh never overwrites what was chosen.
  const [edited, setEdited] = useState<Draft | null>(null);
  const draft = edited ?? draftOf(settings);
  const problem = quietProblem(draft, t);
  const aboutId = useId();
  const problemId = useId();

  function change(next: Partial<Draft>) {
    setEdited({ ...draft, ...next });
    save.reset();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!problem) {
      save.mutate(preferencesOf(draft), { onSuccess: () => setEdited(null) });
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">{t("channels.quiet")}</legend>
        <p id={aboutId} className={MUTED}>
          {t("channels.quietAbout")}
        </p>
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={draft.quiet}
            onChange={(e) => change({ quiet: e.target.checked })}
            aria-describedby={aboutId}
          />
          {t("channels.useQuiet")}
        </label>
        <div className="flex flex-wrap gap-3">
          <TimeField
            label={t("channels.start")}
            value={draft.start}
            disabled={!draft.quiet}
            problemId={problem ? problemId : ""}
            onChange={(start) => change({ start })}
          />
          <TimeField
            label={t("channels.end")}
            value={draft.end}
            disabled={!draft.quiet}
            problemId={problem ? problemId : ""}
            onChange={(end) => change({ end })}
          />
        </div>
        {problem ? (
          <p id={problemId} className="text-sm text-red-800 dark:text-red-200">
            {problem}
          </p>
        ) : null}
      </fieldset>
      <ChannelList settings={settings} draft={draft} labels={labels} onChange={change} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={save.isPending || problem !== ""}>
          {save.isPending ? t("channels.saving") : t("channels.save")}
        </Button>
        {edited ? (
          <Button variant="secondary" disabled={save.isPending} onClick={() => setEdited(null)}>
            {t("channels.undo")}
          </Button>
        ) : null}
      </div>
      {save.isError ? (
        <Alert tone="critical" title={t("channels.saveFailed")} live>
          <p>{save.error.message}</p>
        </Alert>
      ) : null}
      {save.isSuccess ? <Alert tone="good" title={t("channels.saved")} live /> : null}
    </form>
  );
}

interface TimeFieldProps {
  label: string;
  value: string;
  disabled: boolean;
  problemId: string; // the message that says what is wrong with the hours; "" when nothing is
  onChange: (value: string) => void;
}

function TimeField({ label, value, disabled, problemId, onChange }: TimeFieldProps) {
  const invalid = problemId !== "" && !disabled;
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span>{label}</span>
      <input
        type="time"
        step={60}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value.slice(0, 5))}
        aria-invalid={invalid ? true : undefined}
        aria-describedby={invalid ? problemId : undefined}
        className={FIELD}
      />
    </label>
  );
}

interface ChannelListProps {
  settings: NotifySettings;
  draft: Draft;
  labels: Labels;
  onChange: (next: Partial<Draft>) => void;
}

/** Every channel with its state as the service tells it; those that leave the app can be turned on and tuned. */
function ChannelList({ settings, draft, labels, onChange }: ChannelListProps) {
  const { t } = useTranslation("notifications");
  const test = useTestNotification();
  const inAppName = labelOf(labels, "Channel", "in_app");
  const outcome = (channel: Channel) =>
    test.variables === channel ? <TestOutcome channel={channel} test={test} /> : null;
  return (
    <ul aria-label={t("channels.list")} className="flex flex-col gap-3">
      <li className={CHANNEL_BOX}>
        <ChannelHeading name={inAppName} badge={<Badge tone="good">{t("channels.alwaysOn")}</Badge>} />
        <p className={NOTE}>{stateOf(settings, "in_app")?.note || t("channels.inAppNote")}</p>
        <TestButton name={inAppName} busy={test.isPending} onClick={() => test.mutate("in_app")} />
        {outcome("in_app")}
      </li>
      {PUSH_CHANNELS.map((channel) => {
        const state = stateOf(settings, channel);
        const name = labelOf(labels, "Channel", channel);
        return (
          <li key={channel} className={CHANNEL_BOX}>
            <ChannelHeading name={name} badge={<StageBadges state={state} labels={labels} />} />
            {state?.note ? <p className={NOTE}>{state.note}</p> : null}
            <div className="flex flex-wrap items-end gap-3">
              <label className="inline-flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className={CHECKBOX}
                  checked={draft.on[channel]}
                  aria-label={t("channels.onLabel", { name })}
                  onChange={(e) => onChange({ on: { ...draft.on, [channel]: e.target.checked } })}
                />
                {t("channels.on")}
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span>{t("channels.detail")}</span>
                <select
                  aria-label={t("channels.detailLabel", { name })}
                  value={draft.detail[channel]}
                  onChange={(e) => {
                    const level = DETAIL_LEVELS.find((option) => option === e.target.value);
                    if (level) {
                      onChange({ detail: { ...draft.detail, [channel]: level } });
                    }
                  }}
                  className={FIELD}
                >
                  {DETAIL_LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {labelOf(labels, "DetailLevel", level)}
                    </option>
                  ))}
                </select>
              </label>
              <TestButton name={name} busy={test.isPending} onClick={() => test.mutate(channel)} />
            </div>
            {outcome(channel)}
          </li>
        );
      })}
    </ul>
  );
}

function ChannelHeading({ name, badge }: { name: string; badge: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-sm font-semibold">{name}</h3>
      {badge}
    </div>
  );
}

/**
 * What stands in the channel's way, as the service names it: a channel turned off says so, and why it could not carry
 * a notification even if it were on. Always in words, never the colour alone.
 */
function StageBadges({ state, labels }: { state: ChannelState | undefined; labels: Labels }) {
  const { t } = useTranslation("notifications");
  if (!state) {
    return null;
  }
  const stage = <Badge tone={STAGE_TONES[state.stage]}>{labelOf(labels, "ChannelStage", state.stage)}</Badge>;
  if (state.on) {
    return stage;
  }
  return (
    <span className="flex flex-wrap gap-1">
      <Badge tone="neutral">{t("channels.off")}</Badge>
      {state.stage === "ready" ? null : stage}
    </span>
  );
}

function TestButton({ name, busy, onClick }: { name: string; busy: boolean; onClick: () => void }) {
  const { t } = useTranslation("notifications");
  return (
    <Button
      variant="secondary"
      className="self-start"
      disabled={busy}
      aria-label={t("channels.test", { name })}
      onClick={onClick}
    >
      {t("channels.testLabel")}
    </Button>
  );
}

function TestOutcome({ channel, test }: { channel: Channel; test: ReturnType<typeof useTestNotification> }) {
  const { t } = useTranslation("notifications");
  if (test.isPending) {
    return (
      <p role="status" className="text-sm">
        {t("channels.testing")}
      </p>
    );
  }
  if (test.isError) {
    return (
      <Alert tone="critical" title={t("channels.testFailed")} live>
        <p>{test.error.message}</p>
      </Alert>
    );
  }
  if (test.isSuccess) {
    return <Alert tone="good" title={channel === "in_app" ? t("channels.testInApp") : t("channels.testSent")} live />;
  }
  return null;
}
