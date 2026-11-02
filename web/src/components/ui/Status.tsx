// A state — good, a warning, critical, or nothing to judge yet — drawn as the MVP report drew it: a filled disc with an
// icon, then the label. The colour never stands alone (features.md, the charts' rules); the status fills are the same
// in both themes, and the disc's icon keeps 3:1 against its fill.

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";
import type { Tone } from "./Badge";
import { CheckIcon, CloseIcon, DotsIcon, ExclamationIcon } from "./Icons";

const GLYPH = "size-3 [stroke-width:3]";

const MARKS: Record<Tone, { fill: string; icon: ReactNode }> = {
  good: { fill: "bg-status-good text-white", icon: <CheckIcon className={GLYPH} /> },
  warning: { fill: "bg-status-warning text-zinc-950", icon: <ExclamationIcon className={GLYPH} /> },
  critical: { fill: "bg-status-critical text-white", icon: <CloseIcon className={GLYPH} /> },
  neutral: {
    fill: "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100",
    icon: <DotsIcon className={GLYPH} />,
  },
};

interface StatusProps {
  tone: Tone;
  children: ReactNode; // the label, which says the state in words: "Kapandı", "Kontrol gerekli"
}

export function Status({ tone, children }: StatusProps) {
  const { fill, icon } = MARKS[tone];
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span aria-hidden="true" className={cn("inline-grid size-[1.125rem] shrink-0 place-items-center rounded-full", fill)}>
        {icon}
      </span>
      <span>{children}</span>
    </span>
  );
}
