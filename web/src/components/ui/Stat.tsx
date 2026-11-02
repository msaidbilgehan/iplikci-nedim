// A figure of a card (features.md F06): its name and value, the small print that says what it rests on (its window and
// numbers, shown in both views), and in the simple view a one-sentence comment on what it means.

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";
import { Simple } from "../Preferences";

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  meta?: ReactNode; // "6 tam ay: Nisan – Eylül 2026"
  comment?: ReactNode; // "Bu ay tipik aydan %12 fazla harcandı."
  className?: string;
}

export function Stat({ label, value, meta, comment, className }: StatProps) {
  return (
    <div className={cn("rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900", className)}>
      <dl>
        <dt className="text-sm text-zinc-600 dark:text-zinc-300">{label}</dt>
        <dd className="mt-1 text-2xl font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">{value}</dd>
      </dl>
      {meta ? <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{meta}</p> : null}
      {comment ? (
        <Simple>
          <p className="mt-2 text-sm text-zinc-800 dark:text-zinc-200">{comment}</p>
        </Simple>
      ) : null}
    </div>
  );
}
