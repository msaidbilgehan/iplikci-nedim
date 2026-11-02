// How a figure is reached, folded under "Nasıl hesaplandı?": the rules behind a total (which documents, which accounts
// are left out and why) stay one click away instead of filling the screen. A native disclosure, so the keyboard and
// screen readers handle it as they do every other; open from the start in the detailed view, which shows the workings.

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { useView } from "../Preferences";
import { QuestionIcon } from "./Icons";

interface ExplainProps {
  children: ReactNode;
  label?: string; // the summary's words; "Nasıl hesaplandı?" by default
  className?: string;
}

export function Explain({ children, label, className }: ExplainProps) {
  const { t } = useTranslation();
  const { view } = useView();
  return (
    // The view's key: switching to the detailed view opens it, back to the simple view folds it again.
    <details key={view} open={view === "detailed"} className={cn("text-xs text-zinc-600 dark:text-zinc-300", className)}>
      <summary
        className={cn(
          "inline-flex min-h-8 cursor-pointer items-center gap-1 rounded font-medium",
          "text-teal-800 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
        )}
      >
        <QuestionIcon className="size-4 shrink-0" />
        {label ?? t("explain")}
      </summary>
      <div className="mt-1 max-w-3xl">{children}</div>
    </details>
  );
}
