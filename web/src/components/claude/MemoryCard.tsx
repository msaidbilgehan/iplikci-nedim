// What Claude remembers across conversations (K30, ADR-0023, F16): the notes any Claude connected to İplikçi Nedim
// reads and writes, whatever folder or application it connects from. Claude writes them; this card shows every note,
// grouped by what it is about, its text folded, and takes away the ones the user does not want kept (a question first:
// a removed note is not simply taken back).

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useDeleteMemory, useLabels, useMemories } from "../../api/queries";
import type { Memories, Memory, MemoryKind } from "../../api/types";
import { formatDate } from "../../lib/format";
import { Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";

// Who the user is first, as the service orders them.
const KINDS: readonly MemoryKind[] = ["user", "feedback", "project", "reference"];

export function MemoryCard() {
  const { t } = useTranslation("claude");
  const memories = useMemories();
  return (
    <Card title={t("memory.title")}>
      <div className="flex flex-col gap-3 text-sm">
        <p>{t("memory.intro")}</p>
        {memories.isPending ? <Loading /> : null}
        {memories.isError ? (
          <Failure
            error={memories.error}
            onRetry={() => void memories.refetch()}
          />
        ) : null}
        {memories.data ? <Notes memories={memories.data} /> : null}
      </div>
    </Card>
  );
}

function Notes({ memories }: { memories: Memories }) {
  const { t } = useTranslation("claude");
  const labels = useLabels().data ?? {};
  const remove = useDeleteMemory();
  const [asked, setAsked] = useState<Memory | null>(null);
  const notes = memories.memories;
  if (!notes.length) {
    return (
      <p className="text-zinc-600 dark:text-zinc-400">{t("memory.empty")}</p>
    );
  }
  return (
    <>
      <p className="text-zinc-600 dark:text-zinc-400">
        {t("memory.count", { count: notes.length, most: memories.most })}
      </p>
      {KINDS.map((kind) => {
        const kept = notes.filter((note) => note.kind === kind);
        return kept.length ? (
          <div key={kind} className="flex flex-col gap-1">
            <h3 className="font-semibold">
              {labels.MemoryKind?.[kind] ?? kind}
            </h3>
            <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
              {kept.map((note) => (
                <Note
                  key={note.name}
                  note={note}
                  busy={remove.isPending}
                  onRemove={() => setAsked(note)}
                />
              ))}
            </ul>
          </div>
        ) : null;
      })}
      <span aria-live="polite" className="text-zinc-700 dark:text-zinc-300">
        {remove.isSuccess ? t("memory.removed") : ""}
      </span>
      {remove.isError ? (
        <Alert tone="critical" title={t("memory.failed")} live>
          <p>{remove.error.message}</p>
        </Alert>
      ) : null}
      <ConfirmDialog
        open={asked !== null}
        onOpenChange={(open) => {
          if (!open) {
            setAsked(null);
          }
        }}
        title={t("memory.removeTitle")}
        description={t("memory.removeText", {
          description: asked?.description ?? "",
        })}
        confirmLabel={t("memory.remove")}
        variant="danger"
        onConfirm={() => {
          if (asked) {
            remove.mutate(asked.name);
          }
          setAsked(null);
        }}
      />
    </>
  );
}

/** One note: its line and handle, when it last changed, its text folded and the button that takes it away. */
function Note({
  note,
  busy,
  onRemove,
}: {
  note: Memory;
  busy: boolean;
  onRemove: () => void;
}) {
  const { t } = useTranslation("claude");
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="font-medium break-words">{note.description}</span>
          <span className="text-zinc-600 dark:text-zinc-400">
            <code className="break-all">{note.name}</code>
            {" · "}
            {t("memory.updated", { day: formatDate(note.updated_at) })}
          </span>
        </div>
        <Button variant="secondary" disabled={busy} onClick={onRemove}>
          {t("memory.remove")}
          <span className="sr-only">: {note.description}</span>
        </Button>
      </div>
      <details>
        <summary className="min-h-8 cursor-pointer font-medium text-teal-800 dark:text-teal-300">
          {t("memory.body")}
        </summary>
        <p className="mt-2 whitespace-pre-wrap break-words">{note.body}</p>
      </details>
    </li>
  );
}
