import { type ReactNode, useId } from "react";

import { cn } from "../../lib/cn";

interface CardProps {
  title: string;
  action?: ReactNode;
  className?: string;
  level?: 2 | 3; // 3 for a card inside a section that has its own heading
  children: ReactNode;
}

/**
 * A titled section of a screen; its title is the section's heading for screen readers too. It never widens the screen:
 * in a grid or a row of cards it may be narrower than its widest table, which scrolls inside it, and its action goes
 * under the title when they do not fit side by side.
 */
export function Card({ title, action, className, level = 2, children }: CardProps) {
  const heading = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section
      aria-labelledby={heading}
      className={cn(
        "min-w-0 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900",
        className,
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Heading id={heading} className="min-w-0 text-base font-semibold text-zinc-900 dark:text-zinc-100">
          {title}
        </Heading>
        {action}
      </div>
      {children}
    </section>
  );
}

interface FactsProps {
  items: Array<[string, ReactNode]>;
}

/** Name–value pairs, as a description list. */
export function Facts({ items }: FactsProps) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {items.map(([name, value]) => (
        <div key={name} className="contents">
          <dt className="text-zinc-500 dark:text-zinc-400">{name}</dt>
          {/* min-w-0 lets a long unbroken value (a folder's path) wrap instead of widening the card. */}
          <dd className="min-w-0 break-words text-zinc-900 dark:text-zinc-100">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
