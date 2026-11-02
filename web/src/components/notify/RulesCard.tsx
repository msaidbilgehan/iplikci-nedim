// The alert rules (F13, architecture §14): each rule in words with a switch, edited in place; every change saves the
// whole list, which the service checks and refuses whole when it would not read it. Until the user changes one, the
// rules shipped with the app apply. The simple view says how many are on; the detailed view adds each rule's event
// code, as the rule file writes it.

import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAlertRules, useLabels, useSetAlertRules } from "../../api/queries";
import type { AlertEvent, AlertRule, AlertRules, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { Detailed } from "../Preferences";
import { Empty, Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Say } from "../ui/Say";
import { CHECKBOX, labelOf, MUTED } from "./common";
import { RuleEditor } from "./RuleEditor";
import { channelWords, conditionWords, detailWords } from "./rules";

// What the editor is open on: a new rule, or a rule as it was when the editor opened (found again by its name, which
// is the rule's own: the service refuses two of the same name).
type Editing = { kind: "new" } | { kind: "edit"; rule: AlertRule };
type SaveRules = ReturnType<typeof useSetAlertRules>;

export function RulesCard() {
  const { t } = useTranslation("notifications");
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
      title={t("rules.title")}
      action={
        rules.data ? (
          <Button
            id={editor.addId}
            variant="secondary"
            disabled={editor.editing !== null || save.isPending}
            onClick={(e) => open({ kind: "new" }, e.currentTarget)}
          >
            {t("rules.add")}
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
          addId={editor.addId}
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

/**
 * Which rule the deletion asks about. Once a rule is gone the focus goes to "Yeni kural": the button that asked is
 * gone with its rule, whichever comes first, the list without it or the question closing.
 */
function useDeleting(rules: readonly AlertRule[], addId: string) {
  const [asking, setAsking] = useState<AlertRule | null>(null);
  const deleted = useRef<string | null>(null); // the name of the rule just deleted, until the focus has moved
  useEffect(() => {
    const name = deleted.current;
    if (name !== null && asking === null && !rules.some((rule) => rule.name === name)) {
      deleted.current = null;
      document.getElementById(addId)?.focus();
    }
  }, [rules, asking, addId]);
  return {
    asking,
    ask: setAsking,
    done(rule: AlertRule) {
      deleted.current = rule.name;
    },
  };
}

interface RuleBookProps {
  found: AlertRules;
  labels: Labels;
  save: SaveRules;
  editing: Editing | null;
  addId: string;
  onOpen: (next: Editing, from: HTMLElement) => void;
  onClose: () => void;
}

function RuleBook({ found, labels, save, editing, addId, onOpen, onClose }: RuleBookProps) {
  const { t } = useTranslation("notifications");
  const busy = save.isPending;
  const deleting = useDeleting(found.rules, addId);

  function commit(rule: AlertRule) {
    const at = editing?.kind === "edit" ? found.rules.findIndex((r) => r.name === editing.rule.name) : -1;
    const rules = at < 0 ? [...found.rules, rule] : found.rules.map((r, i) => (i === at ? rule : r));
    save.mutate(rules, { onSuccess: onClose });
  }

  function toggle(index: number) {
    save.mutate(found.rules.map((r, i) => (i === index ? { ...r, enabled: !(r.enabled ?? true) } : r)));
  }

  function drop(rule: AlertRule) {
    const rest = found.rules.filter((r) => r !== rule);
    save.mutate(rest, { onSuccess: () => deleting.done(rule), onSettled: () => deleting.ask(null) });
  }

  const asked = deleting.asking;
  return (
    <div className="flex flex-col gap-3">
      {found.rules.length > 0 ? <RulesSay found={found} /> : null}
      {found.problem ? (
        <Alert tone="warning" title={t("rules.problem")}>
          <p>{found.problem}</p>
          <p className="mt-1">{t("rules.problemText")}</p>
        </Alert>
      ) : null}
      {!found.own ? <p className="text-sm text-zinc-700 dark:text-zinc-300">{t("rules.shipped")}</p> : null}
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
          <Empty title={t("rules.empty")}>{t("rules.emptyText")}</Empty>
        ) : (
          <ul aria-label={t("rules.list")} className="flex flex-col gap-2">
            {found.rules.map((rule, index) => (
              <RuleItem
                key={rule.name}
                rule={rule}
                events={found.events}
                labels={labels}
                busy={busy}
                onToggle={() => toggle(index)}
                onEdit={(from) => onOpen({ kind: "edit", rule }, from)}
                onDelete={() => {
                  save.reset();
                  deleting.ask(rule);
                }}
              />
            ))}
          </ul>
        )}
        {save.isError && editing === null ? (
          <Alert tone="critical" title={t("rules.saveFailed")} live>
            <p>{save.error.message}</p>
          </Alert>
        ) : null}
        {save.isSuccess && editing === null ? <Alert tone="good" title={t("rules.saved")} live /> : null}
      </div>
      <ConfirmDialog
        open={asked !== null}
        onOpenChange={(next) => (next ? undefined : deleting.ask(null))}
        title={t("rules.deleteTitle", { name: asked?.name ?? "" })}
        description={t("rules.deleteAbout")}
        confirmLabel={busy ? t("rules.deleting") : t("rules.deleteConfirm")}
        variant="danger"
        busy={busy}
        onConfirm={() => (asked ? drop(asked) : undefined)}
      />
    </div>
  );
}

/** How many rules are on and how many off; while the user has none of their own, that the shipped ones apply. */
function RulesSay({ found }: { found: AlertRules }) {
  const { t } = useTranslation("notifications");
  if (!found.own) {
    return <Say>{t("rules.sayShipped", { count: found.rules.length })}</Say>;
  }
  const count = found.rules.length;
  const on = found.rules.filter((rule) => rule.enabled ?? true).length;
  if (on === count || on === 0) {
    return <Say>{t(on === count ? "rules.sayAllOn" : "rules.sayAllOff", { count })}</Say>;
  }
  return <Say>{t("rules.say", { on, off: count - on })}</Say>;
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
  const { t } = useTranslation("notifications");
  const enabled = rule.enabled ?? true;
  const event = events.find((candidate) => candidate.kind === rule.event)?.label;
  const condition = conditionWords(rule, t);
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
          {enabled ? null : <Badge tone="neutral">{t("rules.off")}</Badge>}
        </p>
        <p>
          {t("rules.event", { event: event ?? labelOf(labels, "EventKind", rule.event) })} ·{" "}
          {condition ? t("rules.condition", { condition }) : t("rules.noCondition")}
        </p>
        <p className={MUTED}>
          {t("rules.channels", { channels: channelWords(rule, labels) })} ·{" "}
          {t("rules.detail", { detail: detailWords(rule, labels, t) })}
          {rule.quiet === false ? ` · ${t("rules.loud")}` : ""}
        </p>
        <Detailed>
          <p className={MUTED}>
            {t("rules.code")} <code>{rule.event}</code>
          </p>
        </Detailed>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            role="switch"
            className={CHECKBOX}
            checked={enabled}
            disabled={busy}
            aria-label={t("rules.on", { name: rule.name })}
            onChange={onToggle}
          />
          {t("rules.onText")}
        </label>
        <Button
          variant="secondary"
          disabled={busy}
          aria-label={t("rules.edit", { name: rule.name })}
          onClick={(e) => onEdit(e.currentTarget)}
        >
          {t("rules.editText")}
        </Button>
        {/* Not red: a red button on every rule would shout; the deletion is asked about first. */}
        <Button
          variant="secondary"
          disabled={busy}
          aria-label={t("rules.delete", { name: rule.name })}
          onClick={onDelete}
        >
          {t("rules.deleteText")}
        </Button>
      </div>
    </li>
  );
}
