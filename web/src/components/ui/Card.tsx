import { type ReactNode, useId } from "react";

import { cn } from "../../lib/cn";

interface CardProps {
  title: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** A titled section of a screen; its title is the section's heading for screen readers too. */
export function Card({ title, action, className, children }: CardProps) {
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      className={cn(
        "rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900",
        className,
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id={heading} className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          {title}
        </h2>
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
          <dd className="break-words text-zinc-900 dark:text-zinc-100">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
