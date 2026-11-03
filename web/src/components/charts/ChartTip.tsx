// What the pointer rests on, beside it: the month's or the day's values by series and their total. It repeats the
// table view for the pointer alone, so screen readers skip it. It stands on the side of the chart with more room. When
// the part leads somewhere, its foot says what a click opens; a touch's tip, which stays until the next touch, holds
// the link itself instead, out of the keyboard's way (the table view's names are its links).

import type { ReactNode } from "react";
import { Link } from "react-router";

import { cn } from "../../lib/cn";
import { ArrowRightIcon } from "../ui/Icons";

export interface TipRow {
  key: string;
  label: string;
  value: string;
  swatch: ReactNode;
}

/** What a click on the part opens: said for a pointer, a link for a touch. */
export type TipOpen = { say: string } | { href: string; label: string };

interface ChartTipProps {
  at: number; // the x the pointer rests at, within the chart
  width: number; // the chart's width
  top: number;
  title: string;
  rows: readonly TipRow[];
  total?: { label: string; value: string } | undefined;
  marked?: string | null; // the row a click opens, set apart from the others
  open?: TipOpen | null;
}

export function ChartTip({ at, width, top, title, rows, total, marked = null, open = null }: ChartTipProps) {
  const side = at < width / 2 ? { left: at + 14, top } : { right: width - at + 14, top };
  const linked = open !== null && "href" in open;
  return (
    <div
      aria-hidden="true"
      style={side}
      className={cn(
        "absolute z-10 min-w-44 max-w-72 rounded-md border p-2 text-xs shadow-md",
        "border-zinc-200 bg-white text-zinc-800 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
        linked ? "pointer-events-auto" : "pointer-events-none",
      )}
    >
      <p className="mb-1 font-medium">{title}</p>
      <ul className="flex flex-col gap-0.5">
        {rows.map((row) => (
          <li key={row.key} className={cn("flex items-center gap-2", row.key === marked && "font-semibold")}>
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
      {open && "say" in open ? (
        <p className="mt-1 border-t border-zinc-200 pt-1 text-zinc-600 dark:border-zinc-600 dark:text-zinc-300">
          {open.say}
        </p>
      ) : null}
      {open && "href" in open ? (
        <Link
          to={open.href}
          tabIndex={-1}
          className={cn(
            "mt-1 flex min-h-11 items-center justify-between gap-2 border-t border-zinc-200 pt-1 font-medium",
            "text-teal-800 underline underline-offset-2 dark:border-zinc-600 dark:text-teal-300",
          )}
        >
          {open.label}
          <ArrowRightIcon className="size-4 shrink-0" />
        </Link>
      ) : null}
    </div>
  );
}
