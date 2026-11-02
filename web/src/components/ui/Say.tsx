// The simple view's comment on a card (features.md, shared rules): one sentence on what the card shows and, after it,
// the next step: a link to the screen to go on with, once that screen is built (lib/links.ts). The detailed view shows
// the card's tables and raw data instead.

import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Destination } from "../../api/types";
import { cn } from "../../lib/cn";
import { hrefOf } from "../../lib/links";
import { Simple } from "../Preferences";
import { ArrowRightIcon } from "./Icons";

export interface Step {
  link: Destination;
  label: string; // what the step does, as a verb: "Takvimi aç"
}

interface SayProps {
  children: ReactNode; // the sentence
  next?: Step | null | undefined;
}

export function Say({ children, next }: SayProps) {
  return (
    <Simple>
      <div className="mb-3 flex flex-col items-start gap-1 border-l-[3px] border-teal-700 pl-3 dark:border-teal-400">
        <p className="text-sm text-zinc-800 dark:text-zinc-100">{children}</p>
        {next ? <NextStep step={next} /> : null}
      </div>
    </Simple>
  );
}

/** A next step's look, for a step whose address the caller builds (a list narrowed by several values of a filter). */
export const STEP = cn(
  "inline-flex min-h-8 items-center gap-1 rounded text-sm font-medium underline underline-offset-2",
  "text-teal-800 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

interface ScreenLinkProps {
  link: Destination;
  className?: string;
  children: ReactNode;
}

/** Words that lead to the screen a link names once that screen is built; until then, the words alone. */
export function ScreenLink({ link, className, children }: ScreenLinkProps) {
  const href = hrefOf(link);
  if (!href) {
    return <span className={className}>{children}</span>;
  }
  return (
    <Link
      to={href}
      className={cn(
        "rounded underline decoration-1 underline-offset-2 hover:decoration-2",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
        className,
      )}
    >
      {children}
    </Link>
  );
}

interface NextStepProps {
  step: Step;
  context?: string; // what the step is about, for screen readers among many alike: "Belgeyi aç: <its name>"
  className?: string;
}

/** A link to the screen a step goes on to, or nothing while that screen is not built. */
export function NextStep({ step, context, className }: NextStepProps) {
  const href = hrefOf(step.link);
  if (!href) {
    return null;
  }
  // The visible words lead the name (WCAG's label in name). An aria-label, not hidden words: the browser reads a flex
  // item's text apart and would say "İşlemleri göster : …" with a space before the colon.
  return (
    <Link to={href} aria-label={context ? `${step.label}: ${context}` : undefined} className={cn(STEP, className)}>
      {step.label}
      <ArrowRightIcon className="size-4 shrink-0" />
    </Link>
  );
}
