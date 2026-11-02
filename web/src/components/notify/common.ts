// What the notification screen's cards share: the channels that leave the app, the levels of detail, how a code
// gets its Turkish label from /api/labels, how a channel's stage looks, and the form controls' look.

import type { Channel, ChannelStage, DetailLevel, Labels } from "../../api/types";
import type { Tone } from "../ui/Badge";

/** The channels that carry a notification out of the app; the interface's box is always on besides them. */
export type PushChannel = Exclude<Channel, "in_app">;

export const PUSH_CHANNELS: readonly PushChannel[] = ["desktop", "telegram", "email"];
export const DETAIL_LEVELS: readonly DetailLevel[] = ["full", "summary", "minimal"];

/** How a channel's stage looks beside its label: what the user still has to do is a warning, a refusal critical. */
export const STAGE_TONES: Record<ChannelStage, Tone> = {
  ready: "good",
  stopped: "critical",
  unavailable: "neutral",
  no_bot: "neutral",
  token_lost: "warning",
  not_paired: "warning",
};

/** One value per channel that leaves the app. */
export function perChannel<T>(value: (channel: PushChannel) => T): Record<PushChannel, T> {
  return { desktop: value("desktop"), telegram: value("telegram"), email: value("email") };
}

/** A code's Turkish label from /api/labels (the code itself until they arrive). */
export function labelOf(labels: Labels, type: string, code: string): string {
  return labels[type]?.[code] ?? code;
}

/** What went wrong, as the service said it in Turkish. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Beklenmeyen bir hata oldu.";
}

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
export const FIELD =
  "min-h-11 rounded-md border border-zinc-300 bg-white px-3 disabled:cursor-not-allowed disabled:opacity-60 " +
  `dark:border-zinc-600 dark:bg-zinc-900 ${FOCUS}`;
export const CHECKBOX = `size-5 shrink-0 accent-teal-700 disabled:cursor-not-allowed ${FOCUS}`;
export const MUTED = "text-xs text-zinc-600 dark:text-zinc-300";
export const LINK = `rounded font-medium text-teal-800 underline dark:text-teal-200 ${FOCUS}`;
