// An item's one-click steps (F19), in the order the service offers them: a rule on the Kurallar screen, a document
// from the computer, reading it again, the place it is shown, a request to give Claude, or off the list. A step this
// version does not know is left out; one whose screen is not built yet waits for it. Taking an item off the list and
// reading a document again are the screen's (TodoHandlers): the item may leave the list before their answer is said.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Labels, TodoAction, TodoItem } from "../../api/types";
import { cn } from "../../lib/cn";
import { labelOf } from "../../lib/labels";
import { hrefOf } from "../../lib/links";
import { UploadPanel } from "../../pages/UploadPanel";
import { isReady } from "../navigation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { SidePanel } from "../ui/SidePanel";

/** What the screen does for an item, and what it is doing or failed to do for it now. */
export interface TodoHandlers {
  ignore: (item: TodoItem) => void;
  restore: (item: TodoItem) => void;
  reparse: (item: TodoItem) => void;
  busy: (item: TodoItem) => boolean; // a step of it is on its way to the service
  failure: (item: TodoItem) => string; // the service's word on its last step that failed; "" for none
}

// A step that leads somewhere looks like the steps that act: the secondary button's look.
const LINK_STEP = cn(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors",
  "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const SHA256 = /^[0-9a-f]{64}$/;

interface StepsProps {
  item: TodoItem;
  labels: Labels;
  handlers: TodoHandlers;
}

export function Steps({ item, labels, handlers }: StepsProps) {
  const { t } = useTranslation("todo");
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const [uploading, setUploading] = useState(false);
  const busy = handlers.busy(item);
  const failure = handlers.failure(item);
  const name = (action: TodoAction) => labelOf(labels, "TodoAction", action);
  // Each step names its item, among many alike.
  const about = (label: string) => `${label}: ${item.title}`;

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(item.prompt);
      setCopy("copied");
    } catch {
      setCopy("failed"); // no clipboard here (or it was refused): the request is shown to copy by hand
    }
  }

  function step(action: TodoAction) {
    switch (action) {
      case "add_rule":
        return isReady("rules") && item.target ? (
          <Link
            key={action}
            to={`/kurallar?${new URLSearchParams({ isyeri: item.target }).toString()}`}
            aria-label={about(name(action))}
            className={LINK_STEP}
          >
            {name(action)}
          </Link>
        ) : null;
      case "upload":
        return (
          <Button key={action} variant="secondary" aria-label={about(name(action))} onClick={() => setUploading(true)}>
            {name(action)}
          </Button>
        );
      case "reparse":
        return SHA256.test(item.target) ? (
          <Button
            key={action}
            variant="secondary"
            aria-label={about(name(action))}
            disabled={busy}
            onClick={() => handlers.reparse(item)}
          >
            {name(action)}
          </Button>
        ) : null;
      case "open": {
        const href = item.link ? hrefOf(item.link) : null;
        return href ? (
          <Link key={action} to={href} aria-label={about(name(action))} className={LINK_STEP}>
            {name(action)}
          </Link>
        ) : null;
      }
      case "ask_claude":
        return item.prompt ? (
          <Button key={action} variant="secondary" aria-label={about(name(action))} onClick={() => void copyPrompt()}>
            {name(action)}
          </Button>
        ) : null;
      case "ignore":
        return (
          <Button
            key={action}
            variant="secondary"
            aria-label={about(name(action))}
            disabled={busy}
            onClick={() => handlers.ignore(item)}
          >
            {name(action)}
          </Button>
        );
      default:
        return null;
    }
  }

  if (item.ignored) {
    return (
      <div className="flex flex-col gap-2">
        <Button
          variant="secondary"
          className="self-start"
          aria-label={about(t("restore"))}
          disabled={busy}
          onClick={() => handlers.restore(item)}
        >
          {t("restore")}
        </Button>
        {failure ? <Alert tone="critical" title={failure} /> : null}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">{item.actions.map(step)}</div>
      <p aria-live="polite" className={copy === "idle" ? "sr-only" : "text-sm text-zinc-700 dark:text-zinc-300"}>
        {copy === "copied" ? t("copied") : null}
        {copy === "failed" ? t("copyFailed") : null}
      </p>
      {copy === "failed" ? (
        <textarea
          readOnly
          value={item.prompt}
          rows={4}
          aria-label={t("prompt")}
          onFocus={(event) => event.target.select()}
          className={cn(
            "w-full rounded-md border p-2 text-sm",
            "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
          )}
        />
      ) : null}
      {failure ? <Alert tone="critical" title={failure} /> : null}
      <SidePanel
        open={uploading}
        onClose={() => setUploading(false)}
        title={t("upload")}
        description={`${item.title}: ${item.detail}`}
      >
        <UploadPanel />
      </SidePanel>
    </div>
  );
}
