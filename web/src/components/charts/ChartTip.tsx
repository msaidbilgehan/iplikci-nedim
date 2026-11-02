// What the pointer rests on, beside it: the month's or the day's values by series and their total. It repeats the
// table view for the pointer alone, so screen readers skip it. It stands on the side of the chart with more room.

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface TipRow {
  key: string;
  label: string;
  value: string;
  swatch: ReactNode;
}

interface ChartTipProps {
  at: number; // the x the pointer rests at, within the chart
  width: number; // the chart's width
  top: number;
  title: string;
  rows: readonly TipRow[];
  total?: { label: string; value: string } | undefined;
}

export function ChartTip({ at, width, top, title, rows, total }: ChartTipProps) {
  const side = at < width / 2 ? { left: at + 14, top } : { right: width - at + 14, top };
  return (
    <div
      aria-hidden="true"
      style={side}
      className={cn(
        "pointer-events-none absolute z-10 min-w-44 max-w-72 rounded-md border p-2 text-xs shadow-md",
        "border-zinc-200 bg-white text-zinc-800 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
      )}
    >
      <p className="mb-1 font-medium">{title}</p>
      <ul className="flex flex-col gap-0.5">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2">
            {row.swatch}
            <span className="min-w-0 flex-1 truncate">{row.label}</span>
            <span className="whitespace-nowrap tabular-nums">{row.value}</span>
          </li>
        ))}
      </ul>
      {total ? (
        <p className="mt-1 flex justify-between gap-2 border-t border-zinc-200 pt-1 font-medium dark:border-zinc-600">
          <span>{total.label}</span>
          <span className="tabular-nums">{total.value}</span>
        </p>
      ) : null}
    </div>
  );
}
