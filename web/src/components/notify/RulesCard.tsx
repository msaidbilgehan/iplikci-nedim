// The alert rules (F13, architecture §14): each rule in words with a switch, edited in place; every change saves the
// whole list, which the service checks and refuses whole when it would not read it. Until the user changes one, the
// rules shipped with the app apply.

import { useEffect, useId, useRef, useState } from "react";

import { useAlertRules, useLabels, useSetAlertRules } from "../../api/queries";
import type { AlertEvent, AlertRule, AlertRules, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { Empty, Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { CHECKBOX, labelOf, MUTED } from "./common";
import { RuleEditor } from "./RuleEditor";
import { channelWords, conditionWords, detailWords } from "./rules";

// What the editor is open on: a new rule, or a rule as it was when the editor opened (found again by its name, which
// is the rule's own: the service refuses two of the same name).
type Editing = { kind: "new" } | { kind: "edit"; rule: AlertRule };
type SaveRules = ReturnType<typeof useSetAlertRules>;

export function RulesCard() {
  const rules = useAlertRules();
  const labels = useLabels().data ?? {};
  const save = useSetAlertRules();
  const editor = useEditing();

  function open(next: Editing, from: HTMLElement) {
    save.reset();
    editor.open(next, from);
  }

  // One card through loading and after: the screen reader's region stays where it is.
  return (
    <Card
      title="Kurallar"
      action={
        rules.data ? (
          <Button
            id={editor.addId}
            variant="secondary"
            disabled={editor.editing !== null || save.isPending}
            onClick={(e) => open({ kind: "new" }, e.currentTarget)}
          >
            Yeni kural
          </Button>
        ) : undefined
      }
    >
      {rules.isPending ? <Loading /> : null}
      {rules.isError ? <Failure error={rules.error} onRetry={() => void rules.refetch()} /> : null}
      {rules.data ? (
        <RuleBook
          found={rules.data}
          labels={labels}
          save={save}
          editing={editor.editing}
          onOpen={open}
          onClose={editor.close}
        />
      ) : null}
    </Card>
  );
}

/** Which rule the editor is open on; when it closes, the focus goes back to what opened it, or to "Yeni kural". */
function useEditing() {
  const [editing, setEditing] = useState<Editing | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const returning = useRef(false);
  const addId = useId();

  useEffect(() => {
    if (editing !== null || !returning.current) {
      return;
    }
    returning.current = false;
    const target = opener.current?.isConnected ? opener.current : document.getElementById(addId);
    target?.focus();
  }, [editing, addId]);

  return {
    editing,
    addId, // the "Yeni kural" button's
    open(next: Editing, from: HTMLElement) {
      opener.current = from;
      setEditing(next);
    },
    close() {
      returning.current = true;
      setEditing(null);
    },
  };
}

interface RuleBookProps {
  found: AlertRules;
  labels: Labels;
  save: SaveRules;
  editing: Editing | null;
  onOpen: (next: Editing, from: HTMLElement) => void;
  onClose: () => void;
}

function RuleBook({ found, labels, save, editing, onOpen, onClose }: RuleBookProps) {
  const busy = save.isPending;

  function commit(rule: AlertRule) {
    const at = editing?.kind === "edit" ? found.rules.findIndex((r) => r.name === editing.rule.name) : -1;
    const rules = at < 0 ? [...found.rules, rule] : found.rules.map((r, i) => (i === at ? rule : r));
    save.mutate(rules, { onSuccess: onClose });
  }

  function toggle(index: number) {
    save.mutate(found.rules.map((r, i) => (i === index ? { ...r, enabled: !(r.enabled ?? true) } : r)));
  }

  function drop(rule: AlertRule) {
    if (window.confirm(`“${rule.name}” kuralı silinsin mi?`)) {
      save.mutate(found.rules.filter((r) => r !== rule));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {found.problem ? (
        <Alert tone="warning" title="Kural dosyanız okunamadı">
          <p>{found.problem}</p>
          <p className="mt-1">
            Şimdilik uygulamayla gelen kurallar geçerli. Burada kaydederseniz dosyanın yerine bu liste yazılır; eski
            dosya kural geçmişinde saklanır.
          </p>
        </Alert>
      ) : null}
      {!found.own ? (
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          Bunlar uygulamayla gelen hazır kurallar. Birini değiştirdiğinizde ya da yeni kural eklediğinizde kendi kural
          dosyanız oluşur.
        </p>
      ) : null}
      {editing !== null ? (
        <RuleEditor
          key={editing.kind === "edit" ? `duzenle-${editing.rule.name}` : "yeni"}
          rule={editing.kind === "edit" ? editing.rule : null}
          events={found.events}
          labels={labels}
          saving={busy}
          refusal={save.isError ? save.error.message : ""}
          onSave={commit}
          onCancel={onClose}
        />
      ) : null}
      {/* Hidden, not gone, while the editor is open: the button that opened it gets the focus back. */}
      <div hidden={editing !== null} className="flex flex-col gap-3">
        {found.rules.length === 0 ? (
          <Empty title="Hiç kural yok">Kural olmadan bildirim gelmez; "Yeni kural" ile ekleyin.</Empty>
        ) : (
          <ul aria-label="Bildirim kuralları" className="flex flex-col gap-2">
            {found.rules.map((rule, index) => (
              <RuleItem
                key={rule.name}
                rule={rule}
                events={found.events}
                labels={labels}
                busy={busy}
                onToggle={() => toggle(index)}
                onEdit={(from) => onOpen({ kind: "edit", rule }, from)}
                onDelete={() => drop(rule)}
              />
            ))}
          </ul>
        )}
        {save.isError && editing === null ? (
          <Alert tone="critical" title="Kurallar kaydedilemedi" live>
            <p>{save.error.message}</p>
          </Alert>
        ) : null}
        {save.isSuccess && editing === null ? <Alert tone="good" title="Kurallar kaydedildi" live /> : null}
      </div>
    </div>
  );
}

interface RuleItemProps {
  rule: AlertRule;
  events: readonly AlertEvent[];
  labels: Labels;
  busy: boolean;
  onToggle: () => void;
  onEdit: (from: HTMLElement) => void;
  onDelete: () => void;
}

function RuleItem({ rule, events, labels, busy, onToggle, onEdit, onDelete }: RuleItemProps) {
  const enabled = rule.enabled ?? true;
  const event = events.find((candidate) => candidate.kind === rule.event)?.label;
  const condition = conditionWords(rule);
  return (
    <li
      className={cn(
        "flex flex-col gap-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700",
        "sm:flex-row sm:items-start sm:justify-between",
      )}
    >
      <div className="flex flex-col gap-1 text-sm">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          {rule.name}
          {enabled ? null : <Badge tone="neutral">Kapalı</Badge>}
        </p>
        <p>
          Olay: {event ?? labelOf(labels, "EventKind", rule.event)} · {condition ? `Koşul: ${condition}` : "Koşulsuz"}
        </p>
        <p className={MUTED}>
          Kanallar: {channelWords(rule, labels)} · Ayrıntı: {detailWords(rule, labels)}
          {rule.quiet === false ? " · sessiz saatte de gider" : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            role="switch"
            className={CHECKBOX}
            checked={enabled}
            disabled={busy}
            onChange={onToggle}
          />
          <span className="sr-only">{rule.name}:</span> Açık
        </label>
        <Button variant="secondary" disabled={busy} onClick={(e) => onEdit(e.currentTarget)}>
          <span className="sr-only">{rule.name}:</span> Düzenle
        </Button>
        {/* Not red: a red button on every rule would shout; the deletion is asked about first. */}
        <Button variant="secondary" disabled={busy} onClick={onDelete}>
          <span className="sr-only">{rule.name}:</span> Sil
        </Button>
      </div>
    </li>
  );
}
