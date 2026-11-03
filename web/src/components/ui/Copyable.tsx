// A path, an address or a piece of configuration in full, with a button that puts it on the clipboard and says whether
// it did. A block keeps its lines (a JSON configuration); a line breaks anywhere so a long path never scrolls sideways.

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { Button } from "./Button";

type Copied = "idle" | "done" | "failed";

interface CopyableProps {
  label: string; // what it is, shown above it and named by the button: "Kopyala: <label>"
  text: string;
  block?: boolean; // several lines, kept as they are
}

export function Copyable({ label, text, block = false }: CopyableProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState<Copied>("idle");
  const [shown, setShown] = useState(text);
  if (shown !== text) {
    setShown(text);
    setCopied("idle");
  }
  const copy = () => {
    if (navigator.clipboard === undefined) {
      setCopied("failed");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => setCopied("done"),
      () => setCopied("failed"),
    );
  };
  const box =
    "rounded bg-zinc-100 px-2 py-1 font-mono text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100";
  return (
    <div className="flex flex-col gap-1">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      {block ? (
        <pre
          className={cn(
            box,
            "overflow-x-auto py-2 text-xs whitespace-pre-wrap break-all",
          )}
        >
          {text}
        </pre>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {block ? null : <code className={cn(box, "break-all")}>{text}</code>}
        <Button
          variant="secondary"
          onClick={copy}
          aria-label={t("copy.named", { name: label })}
        >
          {t("copy.button")}
        </Button>
        <span aria-live="polite" className="text-zinc-700 dark:text-zinc-300">
          {copied === "done"
            ? t("copy.done")
            : copied === "failed"
              ? t("copy.failed")
              : ""}
        </span>
      </div>
    </div>
  );
}
