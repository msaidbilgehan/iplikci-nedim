// A change of the category rules as it would land (F15): how many rows it changes, from which category to which, some
// of them, and the rule file's difference; then the one button that writes it. Every change of the Rules screen goes
// through it, so nothing is written unseen. A change made from a list (a commitment category, a payment expected
// again, a merchant given back to its category) is asked in a side panel; a form shows it under its fields.

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePreviewRule, useSaveRule } from "../../api/queries";
import type { ChangedRow, Labels, RuleChange, RuleEdit } from "../../api/types";
import { formatDay } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Money } from "../ui/Money";
import { SidePanel } from "../ui/SidePanel";
import { Table, Td, Th } from "../ui/Table";

export const MUTED = "text-sm text-zinc-700 dark:text-zinc-300";

/** A change previewed, then written: the preview and the save of one place of the screen. */
export interface RuleEditFlow {
  preview: ReturnType<typeof usePreviewRule>;
  save: ReturnType<typeof useSaveRule>;
  ask: (edit: RuleEdit) => void; // preview it; nothing is written
  forget: () => void; // what the fields say changed: the preview no longer shows it
  write: (onSaved: (change: RuleChange) => void) => void; // write what was previewed
}

export function useRuleEdit(): RuleEditFlow {
  const preview = usePreviewRule();
  const save = useSaveRule();
  return {
    preview,
    save,
    ask: (edit) => {
      save.reset();
      preview.mutate(edit);
    },
    forget: () => {
      preview.reset();
      save.reset();
    },
    write: (onSaved) => {
      // The service makes the file again from the same change: what it writes is what the preview showed, unless the
      // rules changed meanwhile, and then it says so by what it returns.
      const edit = preview.variables;
      if (edit) {
        save.mutate(edit, {
          onSuccess: (change) => {
            preview.reset();
            onSaved(change);
          },
        });
      }
    },
  };
}

/** What a saved change did, in a sentence. */
export function useSavedText(): (change: RuleChange) => string {
  const { t } = useTranslation("rules");
  return (change) => {
    const done = change.changed > 0 ? t("change.saved", { count: change.changed }) : t("change.savedNone");
    return change.backup ? `${done} ${t("change.backup")}` : done;
  };
}

/**
 * What a place of the screen last saved, said where its fields or list are. The focus goes to it when the button that
 * saved is gone (it was part of the preview) or the item it changed left the list.
 */
export function useNotice() {
  const [notice, setNotice] = useState<{ text: string; at: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    // After a side panel has given the focus back to what opened it, if that is still on the page.
    const timer = setTimeout(() => {
      const active = document.activeElement;
      if (!active || active === document.body) {
        ref.current?.focus();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [notice]);
  return {
    ref,
    text: notice?.text ?? "",
    show: (text: string) => setNotice({ text, at: Date.now() }),
    clear: () => setNotice(null),
  };
}

export function Notice({ notice }: { notice: ReturnType<typeof useNotice> }) {
  return (
    <div
      ref={notice.ref}
      tabIndex={-1}
      className="rounded-md empty:hidden focus-visible:outline-2 focus-visible:outline-teal-600"
    >
      {notice.text ? <Alert tone="good" title={notice.text} live /> : null}
    </div>
  );
}

interface ChangePreviewProps {
  flow: RuleEditFlow;
  labels: Labels;
  onSaved: (change: RuleChange) => void;
  errorId?: string; // a refused preview's message, for the field it is about (aria-describedby)
}

export function ChangePreview({ flow, labels, onSaved, errorId }: ChangePreviewProps) {
  const { t } = useTranslation("rules");
  const { t: tc } = useTranslation();
  const { preview, save } = flow;
  const found = preview.data;
  let sentence = "";
  if (preview.isPending) {
    sentence = t("change.previewing");
  } else if (found && !found.diff) {
    sentence = t("change.sameFile");
  } else if (found) {
    sentence = found.changed > 0 ? t("change.changes", { count: found.changed }) : t("change.noChange");
  }
  // With nothing to show the box gives way, so it adds no gap to its form; its sentence stays, hidden.
  const idle = !sentence && !preview.isError && !save.isError;
  return (
    <div className={idle ? "contents" : "flex flex-col gap-3 text-sm"}>
      {/* One sentence is announced, not the whole preview; the element stays on the page so that it is heard. */}
      <p aria-live="polite" className={sentence ? "font-medium" : "sr-only"}>
        {sentence}
      </p>
      {preview.isError ? (
        <div id={errorId}>
          <Alert tone="critical" title={t("change.previewFailed")}>
            <p>{preview.error.message}</p>
            <Button
              variant="secondary"
              className="mt-2"
              onClick={() => {
                if (preview.variables) {
                  preview.mutate(preview.variables);
                }
              }}
            >
              {tc("retry")}
            </Button>
          </Alert>
        </div>
      ) : null}
      {found && found.diff ? (
        <>
          <Effect change={found} labels={labels} />
          <Button className="self-start" disabled={save.isPending} onClick={() => flow.write(onSaved)}>
            {save.isPending ? t("change.saving") : t("change.save")}
          </Button>
        </>
      ) : null}
      {save.isError ? (
        <Alert tone="critical" title={t("change.saveFailed")}>
          <p>{save.error.message}</p>
        </Alert>
      ) : null}
    </div>
  );
}

/** The rows a change moves, from which category to which, and the file's difference. */
function Effect({ change, labels }: { change: RuleChange; labels: Labels }) {
  const { t } = useTranslation("rules");
  return (
    <>
      {change.moves.length > 0 ? (
        <ul className="list-disc pl-5">
          {change.moves.map((move) => (
            <li key={`${move.before}\u0000${move.after}`}>
              {t("change.move", { before: move.before, after: move.after, count: move.count, total: move.total })}
            </li>
          ))}
        </ul>
      ) : null}
      {change.examples.length > 0 ? (
        <Table>
          <caption className="text-left text-xs font-medium">{t("change.examples")}</caption>
          <thead>
            <tr>
              <Th>{t("change.day")}</Th>
              <Th>{t("change.row")}</Th>
              <Th className="text-right">{t("change.amount")}</Th>
              <Th>{t("change.before")}</Th>
              <Th>{t("change.after")}</Th>
            </tr>
          </thead>
          <tbody>
            {change.examples.map((example) => (
              <tr key={example.fingerprint}>
                <Td className="whitespace-nowrap">{formatDay(example.day)}</Td>
                <Td className="break-words">{example.description}</Td>
                <Td className="text-right">
                  <Money
                    value={{ ...example.amount, minor: Math.abs(example.amount.minor) }}
                    direction={example.amount.minor < 0 ? "in" : "out"}
                  />
                </Td>
                <Td>{described(example, "before", labels)}</Td>
                <Td>{described(example, "after", labels)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : null}
      <details>
        <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-teal-600">
          {t("change.diff")}
        </summary>
        <pre className="mt-1 overflow-x-auto rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">{change.diff}</pre>
      </details>
    </>
  );
}

/** A row's category before or after the change, with its necessity, kind or merchant where the change moves those. */
function described(row: ChangedRow, side: "before" | "after", labels: Labels): string {
  const it = row[side];
  const other = row[side === "before" ? "after" : "before"];
  const parts = [it.category];
  if (it.necessity !== other.necessity) {
    parts.push(labelOf(labels, "Necessity", it.necessity ?? "unknown"));
  }
  if (it.kind !== other.kind) {
    parts.push(labelOf(labels, "TransactionKind", it.kind));
  }
  if (it.merchant !== other.merchant && it.merchant) {
    parts.push(it.merchant);
  }
  return parts.join(" · ");
}

interface ChangePanelProps {
  open: boolean;
  title: string; // the change, as a wish: "Kira taahhüt kategorisi olsun"
  text: string; // what follows from it, in a sentence
  flow: RuleEditFlow; // asked when the panel opened
  labels: Labels;
  onSaved: (change: RuleChange) => void; // the panel closes after it
  onClose: () => void;
}

/** A change made from a list, previewed at once in a side panel: written only from there. */
export function ChangePanel({ open, title, text, flow, labels, onSaved, onClose }: ChangePanelProps) {
  const { t } = useTranslation("rules");
  const { t: tc } = useTranslation();
  return (
    <SidePanel open={open} onClose={onClose} title={title} description={text}>
      <div className="flex flex-col gap-4">
        <ChangePreview flow={flow} labels={labels} onSaved={onSaved} />
        <Button variant="secondary" className="self-start" disabled={flow.save.isPending} onClick={onClose}>
          {flow.preview.isError || flow.preview.data?.diff === "" ? t("panel.close") : tc("cancel")}
        </Button>
      </div>
    </SidePanel>
  );
}
