// The alert rule editor (F13): the name, the event, the conditions the chosen event allows (days ahead, an amount
// in lira, a text in the title), the channels, the level of detail, the quiet hours and whether the rule is on. "Son
// 30 günde kaç kez?" asks the service how often the rule would have spoken; nothing is saved by it.

import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

import { usePreviewAlertRule } from "../../api/queries";
import type { AlertEvent, AlertPreview, AlertRule, Labels } from "../../api/types";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { CHECKBOX, DETAIL_LEVELS, FIELD, labelOf, MUTED, PUSH_CHANNELS, type PushChannel } from "./common";
import {
  checkDraft,
  DRAFT_FIELDS,
  type DraftErrors,
  type DraftField,
  draftOf,
  NEW_RULE,
  type RuleDraft,
  TEXT_LIMIT,
  withoutFields,
} from "./rules";

const ERROR = "text-sm text-red-800 dark:text-red-200";

interface RuleEditorProps {
  rule: AlertRule | null; // null: a new rule
  events: readonly AlertEvent[];
  labels: Labels;
  saving: boolean;
  refusal: string; // the service's refusal of the last save, as it said it
  onSave: (rule: AlertRule) => void;
  onCancel: () => void;
}

export function RuleEditor({ rule, events, labels, saving, refusal, onSave, onCancel }: RuleEditorProps) {
  const [draft, setDraft] = useState<RuleDraft>(() => (rule ? draftOf(rule) : NEW_RULE));
  const [errors, setErrors] = useState<DraftErrors>({});
  const preview = usePreviewAlertRule();
  const headingId = useId();
  const ids: Record<DraftField | "text", string> = {
    name: useId(),
    event: useId(),
    days: useId(),
    amount: useId(),
    text: useId(),
  };
  const nameField = useRef<HTMLInputElement>(null);
  const event = events.find((candidate) => candidate.kind === draft.event);

  useEffect(() => {
    nameField.current?.focus();
  }, []);

  function change(next: Partial<RuleDraft>) {
    setDraft({ ...draft, ...next });
    setErrors(withoutFields(errors, Object.keys(next)));
    preview.reset();
  }

  /** The rule the draft makes, or nothing after showing what is wrong and moving to the first wrong field. */
  function checked(purpose: "save" | "preview"): AlertRule | null {
    const found = checkDraft(draft, events, purpose);
    if (found.ok) {
      return found.rule;
    }
    setErrors(found.errors);
    const first = DRAFT_FIELDS.find((field) => found.errors[field]);
    if (first) {
      document.getElementById(ids[first])?.focus();
    }
    return null;
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const made = checked("save");
    if (made) {
      onSave(made);
    }
  }

  function ask() {
    const made = checked("preview");
    if (made) {
      preview.mutate(made);
    }
  }

  function escape(e: KeyboardEvent<HTMLFormElement>) {
    // Escape in a list of options only closes the list.
    if (e.key === "Escape" && !saving && !(e.target instanceof HTMLSelectElement)) {
      e.preventDefault();
      onCancel();
    }
  }

  return (
    <form
      onSubmit={submit}
      onKeyDown={escape}
      aria-labelledby={headingId}
      noValidate
      className="flex flex-col gap-4 rounded-md border border-zinc-200 p-3 dark:border-zinc-700"
    >
      <h3 id={headingId} className="text-base font-semibold">
        {rule ? `“${rule.name}” kuralını düzenle` : "Yeni kural"}
      </h3>
      <Field label="Ad" id={ids.name} error={errors.name}>
        <input
          ref={nameField}
          id={ids.name}
          type="text"
          value={draft.name}
          maxLength={TEXT_LIMIT}
          autoComplete="off"
          onChange={(e) => change({ name: e.target.value })}
          {...invalid(ids.name, errors.name)}
          className={`max-w-md ${FIELD}`}
        />
      </Field>
      <Field label="Olay" id={ids.event} error={errors.event}>
        <select
          id={ids.event}
          value={draft.event}
          onChange={(e) => change({ event: events.find((option) => option.kind === e.target.value)?.kind ?? "" })}
          {...invalid(ids.event, errors.event)}
          className={`max-w-md ${FIELD}`}
        >
          <option value="" disabled>
            Bir olay seçin
          </option>
          {events.map((option) => (
            <option key={option.kind} value={option.kind}>
              {option.label}
            </option>
          ))}
        </select>
      </Field>
      <Conditions event={event} draft={draft} errors={errors} ids={ids} onChange={change} />
      <fieldset className="flex flex-col gap-1">
        <legend className="text-sm font-medium">Kanallar</legend>
        <p className={MUTED}>Uygulamadaki bildirim kutusuna her zaman gelir.</p>
        <div className="flex flex-wrap gap-x-4">
          {PUSH_CHANNELS.map((channel) => (
            <label key={channel} className="inline-flex min-h-11 items-center gap-2 text-sm">
              <input
                type="checkbox"
                className={CHECKBOX}
                checked={draft.channels.includes(channel)}
                onChange={(e) => {
                  const on = (c: PushChannel) => (c === channel ? e.target.checked : draft.channels.includes(c));
                  change({ channels: PUSH_CHANNELS.filter(on) });
                }}
              />
              {labelOf(labels, "Channel", channel)}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex flex-col gap-1 text-sm">
        <span>Ayrıntı düzeyi</span>
        <select
          value={draft.detail}
          onChange={(e) => change({ detail: DETAIL_LEVELS.find((level) => level === e.target.value) ?? "" })}
          className={`self-start ${FIELD}`}
        >
          <option value="">Her kanalın kendi düzeyi</option>
          {DETAIL_LEVELS.map((level) => (
            <option key={level} value={level}>
              {labelOf(labels, "DetailLevel", level)}
            </option>
          ))}
        </select>
      </label>
      <div className="flex flex-col">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={draft.quiet}
            onChange={(e) => change({ quiet: e.target.checked })}
          />
          Sessiz saatlere uy
        </label>
        <p className={MUTED}>İşaret kaldırılırsa bu kuralın bildirimleri sessiz saatlerde de hemen gider.</p>
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={draft.enabled}
            onChange={(e) => change({ enabled: e.target.checked })}
          />
          Kural açık
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Kaydediliyor…" : "Kaydet"}
        </Button>
        <Button variant="secondary" onClick={ask} disabled={preview.isPending}>
          {preview.isPending ? "Bakılıyor…" : "Son 30 günde kaç kez?"}
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          Vazgeç
        </Button>
      </div>
      {preview.data ? <PreviewResult found={preview.data} /> : null}
      {preview.isError ? (
        <Alert tone="critical" title="Önizleme yapılamadı" live>
          <p>{preview.error.message}</p>
        </Alert>
      ) : null}
      {refusal ? (
        <Alert tone="critical" title="Kurallar kaydedilemedi" live>
          <p>{refusal}</p>
        </Alert>
      ) : null}
    </form>
  );
}

/** The attributes that tie a field to its error message. */
function invalid(id: string, error: string | undefined) {
  return error ? { "aria-invalid": true, "aria-describedby": `${id}-hata` } : {};
}

interface FieldProps {
  label: string;
  id: string; // the control's, which the label names
  error?: string | undefined;
  children: ReactNode;
}

function Field({ label, id, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? (
        <p id={`${id}-hata`} className={ERROR}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

interface ConditionsProps {
  event: AlertEvent | undefined;
  draft: RuleDraft;
  errors: DraftErrors;
  ids: Record<DraftField | "text", string>;
  onChange: (next: Partial<RuleDraft>) => void;
}

/** Only the conditions the chosen event carries; an empty one is not looked at. */
function Conditions({ event, draft, errors, ids, onChange }: ConditionsProps) {
  const none = event !== undefined && !event.days && !event.amount && !event.text;
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-medium">Koşullar</legend>
      {event === undefined ? (
        <p className={MUTED}>Olayı seçin; o olayın izin verdiği koşullar burada görünür.</p>
      ) : null}
      {none ? <p className={MUTED}>Bu olayda koşul yok: olay her olduğunda bildirim gelir.</p> : null}
      {event?.days ? (
        <Field label="En çok kaç gün kala" id={ids.days} error={errors.days}>
          <input
            id={ids.days}
            type="text"
            inputMode="numeric"
            value={draft.days}
            placeholder="ör. 3"
            autoComplete="off"
            onChange={(e) => onChange({ days: e.target.value })}
            {...invalid(ids.days, errors.days)}
            className={`w-32 ${FIELD}`}
          />
        </Field>
      ) : null}
      {event?.amount ? (
        <Field label="En az tutar (TL)" id={ids.amount} error={errors.amount}>
          <input
            id={ids.amount}
            type="text"
            inputMode="decimal"
            value={draft.amount}
            placeholder="ör. 7.500"
            autoComplete="off"
            onChange={(e) => onChange({ amount: e.target.value })}
            {...invalid(ids.amount, errors.amount)}
            className={`w-40 ${FIELD}`}
          />
        </Field>
      ) : null}
      {event?.text ? (
        <Field label="Başlığında geçen yazı" id={ids.text}>
          <input
            id={ids.text}
            type="text"
            value={draft.text}
            maxLength={TEXT_LIMIT}
            placeholder="ör. bir işyerinin ya da ödemenin adı"
            autoComplete="off"
            onChange={(e) => onChange({ text: e.target.value })}
            className={`max-w-md ${FIELD}`}
          />
        </Field>
      ) : null}
      {event && !none ? <p className={MUTED}>Boş bırakılan koşul aranmaz.</p> : null}
    </fieldset>
  );
}

function PreviewResult({ found }: { found: AlertPreview }) {
  return (
    <div role="status" className="flex flex-col gap-2 rounded-md bg-zinc-100 p-3 text-sm dark:bg-zinc-800">
      <p className="font-medium">
        {found.count > 0
          ? `Son ${found.days} günde ${found.count} kez bildirim verirdi.`
          : `Son ${found.days} günde hiç bildirim vermezdi.`}
      </p>
      {found.examples.length > 0 ? (
        <>
          <p className={MUTED}>{found.examples.length < found.count ? "En yenileri:" : "Bildirimler:"}</p>
          <ul className="flex flex-col gap-1">
            {found.examples.map((example, index) => (
              // The examples come in order and never move: their place tells two alike apart.
              <li key={`${index}-${example.title}`}>
                <span className="font-medium">{example.title}</span>: {example.body}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
