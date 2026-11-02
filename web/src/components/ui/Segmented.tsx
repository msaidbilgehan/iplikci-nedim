// A choice of one among a few, drawn as joined buttons: real radio buttons inside a named group, so the arrow keys
// move between them and a screen reader says which is chosen and how many there are.

import { type ReactNode, useId } from "react";

import { cn } from "../../lib/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

interface SegmentedProps<T extends string> {
  legend: string; // the group's name for screen readers: "Tema"
  options: ReadonlyArray<SegmentedOption<T>>;
  value: T;
  onChange: (value: T) => void;
  compact?: boolean; // icons alone on narrow screens; the labels stay for screen readers and as titles
}

export function Segmented<T extends string>({ legend, options, value, onChange, compact = false }: SegmentedProps<T>) {
  const name = useId();
  return (
    <fieldset className="inline-flex rounded-md border border-zinc-300 bg-white p-0.5 dark:border-zinc-600 dark:bg-zinc-800">
      <legend className="sr-only">{legend}</legend>
      {options.map((option) => (
        <label
          key={option.value}
          title={compact ? option.label : undefined}
          className={cn(
            "inline-flex min-h-10 min-w-10 cursor-pointer items-center justify-center gap-1.5 rounded px-2.5 text-sm font-medium",
            "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700",
            "has-checked:bg-teal-700 has-checked:text-white",
            "dark:has-checked:bg-teal-400 dark:has-checked:text-zinc-950",
            "has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-teal-600",
          )}
        >
          <input
            type="radio"
            className="sr-only"
            name={name}
            value={option.value}
            checked={option.value === value}
            onChange={() => onChange(option.value)}
          />
          {option.icon}
          <span className={compact ? "sr-only sm:not-sr-only" : undefined}>{option.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
