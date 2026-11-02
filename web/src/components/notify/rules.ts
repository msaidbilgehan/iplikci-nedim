// The alert rules as the screen shows and edits them (architecture §14): a rule in words, and the editor's draft
// with what is wrong with it before the service is asked. The service checks the whole list again and has the last
// word; its refusal is shown as it says it.

import type { AlertEvent, AlertRule, DetailLevel, EventKind, Labels } from "../../api/types";
import { liraInput, parseLira } from "../../lib/amount";
import { formatMoney } from "../../lib/format";
import { labelOf, PUSH_CHANNELS, type PushChannel } from "./common";

export const MAX_DAYS = 60; // the calendar's horizon (F09): a due date further away is no event yet
export const TEXT_LIMIT = 80; // the longest name and text the service takes
const PREVIEW_NAME = "Önizleme"; // a rule not named yet can be previewed: the service wants some name

/** A rule's condition in words, "en çok 3 gün kala, en az 7.500,00 TL"; "" for a rule without one. */
export function conditionWords(rule: AlertRule): string {
  const days = rule.condition?.days;
  const amount = rule.condition?.amount;
  const text = rule.condition?.text;
  const parts: string[] = [];
  if (days !== null && days !== undefined) {
    parts.push(days === 0 ? "günü gelince" : `en çok ${days} gün kala`);
  }
  if (amount !== null && amount !== undefined) {
    parts.push(`en az ${formatMoney({ minor: amount, currency: "TRY" })}`);
  }
  if (text) {
    parts.push(`başlığında “${text}” geçerse`);
  }
  return parts.join(", ");
}

/** Where a rule's notifications go: the interface's box always, then the rule's channels. */
export function channelWords(rule: AlertRule, labels: Labels): string {
  const channels = rule.channels.filter((channel) => channel !== "in_app");
  return ["in_app", ...channels].map((channel) => labelOf(labels, "Channel", channel)).join(", ");
}

export function detailWords(rule: AlertRule, labels: Labels): string {
  return rule.detail ? labelOf(labels, "DetailLevel", rule.detail) : "her kanalın kendi düzeyi";
}

/** A rule as the editor holds it: what is typed, the amount in lira as the user writes it. */
export interface RuleDraft {
  name: string;
  event: EventKind | "";
  days: string; // "" for no condition on the days
  amount: string;
  text: string;
  channels: PushChannel[];
  detail: DetailLevel | ""; // "": each channel's own level
  enabled: boolean;
  quiet: boolean;
}

export const NEW_RULE: RuleDraft = {
  name: "",
  event: "",
  days: "",
  amount: "",
  text: "",
  channels: ["desktop", "telegram"], // what a rule written without channels gets
  detail: "",
  enabled: true,
  quiet: true,
};

export function draftOf(rule: AlertRule): RuleDraft {
  const days = rule.condition?.days;
  const amount = rule.condition?.amount;
  return {
    name: rule.name,
    event: rule.event,
    days: days === null || days === undefined ? "" : String(days),
    amount: amount === null || amount === undefined ? "" : liraInput(amount),
    text: rule.condition?.text ?? "",
    channels: PUSH_CHANNELS.filter((channel) => rule.channels.includes(channel)),
    detail: rule.detail ?? "",
    enabled: rule.enabled ?? true,
    quiet: rule.quiet ?? true,
  };
}

export type DraftField = "name" | "event" | "days" | "amount";
export type DraftErrors = Partial<Record<DraftField, string>>;
export const DRAFT_FIELDS: readonly DraftField[] = ["name", "event", "days", "amount"];

export type Checked = { ok: true; rule: AlertRule } | { ok: false; errors: DraftErrors };

/**
 * The rule a draft makes, carrying only the conditions its event allows (a condition typed for another event is
 * dropped), or what is wrong with it field by field. A preview needs no name yet.
 */
export function checkDraft(draft: RuleDraft, events: readonly AlertEvent[], purpose: "save" | "preview"): Checked {
  const errors: DraftErrors = {};
  const name = draft.name.trim();
  if (purpose === "save" && !name) {
    errors.name = "Kurala bir ad verin.";
  }
  const event = events.find((candidate) => candidate.kind === draft.event);
  if (!event) {
    errors.event = "İzlenecek olayı seçin.";
  }
  const typedDays = draft.days.trim();
  const days = event?.days && typedDays ? (/^\d+$/.test(typedDays) ? Number(typedDays) : Number.NaN) : null;
  if (days !== null && !(days <= MAX_DAYS)) {
    errors.days = `Gün sayısı 0 ile ${MAX_DAYS} arasında bir tam sayı olmalı.`;
  }
  const typedAmount = draft.amount.trim();
  const amount = event?.amount && typedAmount ? parseLira(typedAmount) : null;
  if (event?.amount && typedAmount && amount === null) {
    errors.amount = "Tutar 7.500 ya da 7.500,50 gibi bir TL tutarı olmalı.";
  }
  if (!event || DRAFT_FIELDS.some((field) => errors[field])) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    rule: {
      name: name || PREVIEW_NAME,
      event: event.kind,
      condition: { days, amount, text: event.text ? draft.text.trim() : "" },
      channels: [...draft.channels],
      detail: draft.detail || null,
      enabled: draft.enabled,
      quiet: draft.quiet,
    },
  };
}

/** The errors left once some fields changed: a field's message goes when the field does. */
export function withoutFields(errors: DraftErrors, changed: readonly string[]): DraftErrors {
  const kept: DraftErrors = {};
  for (const field of DRAFT_FIELDS) {
    const message = errors[field];
    if (message && !changed.includes(field)) {
      kept[field] = message;
    }
  }
  return kept;
}
