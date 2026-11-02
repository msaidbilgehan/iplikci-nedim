// A category chosen from the rules' categories, under their groups (the browser's own select: the keyboard and screen
// readers know it). An optional first choice gives the row back to the rules.

import { useId } from "react";

import type { Category } from "../../api/types";
import { cn } from "../../lib/cn";

const SELECT = [
  "min-h-11 max-w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");

interface CategorySelectProps {
  label: string;
  categories: readonly Category[];
  value: string; // "" for none chosen, or for the rules when `back` is given
  onChange: (category: string) => void;
  back?: string; // the first choice's words when the row may go back to the rules: "Kurallara bırak"
  placeholder?: string; // the first choice's words when nothing is chosen yet
  error?: { text: string; id: string }; // what is wrong with the choice, said beside it
}

/** The categories under their groups, in the rule file's order. */
function byGroup(categories: readonly Category[]): Array<[string, Category[]]> {
  const groups = new Map<string, Category[]>();
  for (const category of categories) {
    groups.set(category.group, [...(groups.get(category.group) ?? []), category]);
  }
  return [...groups];
}

export function CategorySelect({ label, categories, value, onChange, back, placeholder, error }: CategorySelectProps) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error?.id}
        className={cn(SELECT, error && "border-red-700 dark:border-red-400")}
      >
        <option value="">{back ?? placeholder ?? "—"}</option>
        {byGroup(categories).map(([group, members]) => (
          <optgroup key={group} label={group}>
            {members.map((category) => (
              <option key={category.name} value={category.name}>
                {category.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {error ? (
        <p id={error.id} className="text-sm text-red-800 dark:text-red-200">
          {error.text}
        </p>
      ) : null}
    </div>
  );
}
