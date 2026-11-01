import type { ReactNode } from "react";

import { cn } from "../../lib/cn";
import { CheckIcon, CrossIcon, InfoIcon, WarningIcon } from "./Icons";

export type Tone = "good" | "warning" | "critical" | "neutral";

const TONES: Record<Tone, { className: string; icon: ReactNode }> = {
  good: {
    className: "bg-emerald-50 text-emerald-800 ring-emerald-600/30 dark:bg-emerald-950 dark:text-emerald-200",
    icon: <CheckIcon className="size-3.5" />,
  },
  warning: {
    className: "bg-amber-50 text-amber-900 ring-amber-600/30 dark:bg-amber-950 dark:text-amber-200",
    icon: <WarningIcon className="size-3.5" />,
  },
  critical: {
    className: "bg-red-50 text-red-800 ring-red-600/30 dark:bg-red-950 dark:text-red-200",
    icon: <CrossIcon className="size-3.5" />,
  },
  neutral: {
    className: "bg-zinc-100 text-zinc-700 ring-zinc-500/30 dark:bg-zinc-800 dark:text-zinc-200",
    icon: <InfoIcon className="size-3.5" />,
  },
};

/** A status: always an icon and a label with the colour, never the colour alone. */
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  const { className, icon } = TONES[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}
