import type { ReactNode } from "react";

import { cn } from "../../lib/cn";
import { CheckIcon, CrossIcon, InfoIcon, WarningIcon } from "./Icons";
import type { Tone } from "./Badge";

const TONES: Record<Tone, string> = {
  good: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100",
  warning: "border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100",
  critical: "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100",
  neutral: "border-zinc-300 bg-zinc-50 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
};

const ICONS: Record<Tone, ReactNode> = {
  good: <CheckIcon className="mt-0.5 size-5 shrink-0" />,
  warning: <WarningIcon className="mt-0.5 size-5 shrink-0" />,
  critical: <CrossIcon className="mt-0.5 size-5 shrink-0" />,
  neutral: <InfoIcon className="mt-0.5 size-5 shrink-0" />,
};

interface AlertProps {
  tone: Tone;
  title: string;
  children?: ReactNode;
  live?: boolean; // announce it when it appears (a result of the user's action)
}

export function Alert({ tone, title, children, live = false }: AlertProps) {
  return (
    <div
      role={tone === "critical" ? "alert" : "status"}
      aria-live={live ? "polite" : undefined}
      className={cn("flex gap-3 rounded-md border p-3 text-sm", TONES[tone])}
    >
      {ICONS[tone]}
      <div>
        <p className="font-medium">{title}</p>
        {children ? <div className="mt-1">{children}</div> : null}
      </div>
    </div>
  );
}
