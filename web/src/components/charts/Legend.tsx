// Which colour is which series: a swatch and the series' name for each, in the order the chart stacks them.

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface LegendItem {
  key: string;
  label: string;
  swatch: ReactNode | string; // a class for a square swatch (SLOT_BG[slot]), or a drawing of its own (a line's dash)
}

export function Legend({ items }: { items: readonly LegendItem[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-700 dark:text-zinc-300">
      {items.map((item) => (
        <li key={item.key} className="inline-flex items-center gap-1.5">
          {typeof item.swatch === "string" ? (
            <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", item.swatch)} />
          ) : (
            item.swatch
          )}
          {item.label}
        </li>
      ))}
    </ul>
  );
}
