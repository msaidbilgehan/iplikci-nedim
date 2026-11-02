// A filter of many choices, as the MVP report's were: a button that says what is chosen ("Hesaplar: Tümü", "Hesaplar:
// 3/7", "Kategori: Market") opens a panel of checkboxes — by group when the options have one, a group's own box
// choosing all of it — with "Tümü" and "Hiçbiri". Every option chosen is the same as no filter: null. The chips below
// a screen's filters show what is set, each with a button that takes it off.

import * as Popover from "@radix-ui/react-popover";
import { type ReactNode, useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { ChevronDownIcon, CloseIcon } from "./Icons";

export interface FilterOption {
  value: string;
  label: string;
  group?: string; // options of a group stand together under its name: an account's bank
  note?: string; // a word beside the option: an account's type
  mark?: ReactNode; // a colour swatch, as a chart's legend shows it
}

export type Selection = ReadonlySet<string> | null; // null: no filter, every option

interface FilterPopoverProps {
  label: string;
  options: readonly FilterOption[];
  selected: Selection;
  onChange: (selected: Selection) => void;
}

/** values turned on or off in the selection; every option on comes back as null, no filter. */
export function toggled(selected: Selection, all: readonly string[], values: readonly string[], on: boolean): Selection {
  const next = new Set(selected ?? all);
  for (const value of values) {
    if (on) {
      next.add(value);
    } else {
      next.delete(value);
    }
  }
  return next.size === all.length && all.every((value) => next.has(value)) ? null : next;
}

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

/** What a filter is set to, in a word: "Tümü", "Hiçbiri", the one option's name, or how many of how many. */
export function useSelectionSummary(): (selected: Selection, options: readonly FilterOption[]) => string {
  const { t } = useTranslation();
  return (selected, options) => {
    if (selected === null) {
      return t("filter.all");
    }
    if (selected.size === 0) {
      return t("filter.none");
    }
    const [only] = selected;
    if (selected.size === 1 && only !== undefined) {
      // A value the options do not name (they are still loading, or a link chose it) stands as it is.
      return options.find((option) => option.value === only)?.label ?? only;
    }
    if (options.length > 0 && options.every((option) => selected.has(option.value))) {
      return t("filter.all");
    }
    return t("filter.count", { count: selected.size, total: options.length });
  };
}

export function FilterPopover({ label, options, selected, onChange }: FilterPopoverProps) {
  const { t } = useTranslation();
  const summarize = useSelectionSummary();
  const all = options.map((option) => option.value);
  const isOn = (value: string) => selected === null || selected.has(value);
  const summary = summarize(selected, options);
  const groups = groupOf(options);
  const toggle = (value: string, on: boolean) => onChange(toggled(selected, all, [value], on));
  return (
    <Popover.Root>
      <Popover.Trigger
        className={cn(
          "inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm",
          "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
          "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
          FOCUS,
        )}
      >
        {t("filter.summary", { label, value: summary })}
        <ChevronDownIcon className="size-4 text-zinc-600 dark:text-zinc-300" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          aria-label={label}
          align="start"
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            "z-50 max-h-[60vh] w-72 overflow-y-auto rounded-lg border p-2 text-sm shadow-lg",
            "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
          )}
        >
          <div className="mb-1 flex items-center justify-between gap-2 border-b border-zinc-200 px-2 pb-2 dark:border-zinc-600">
            <span className="font-medium">{label}</span>
            <span className="flex gap-1">
              <button type="button" className={LINK} onClick={() => onChange(null)}>
                {t("filter.all")}
              </button>
              <button type="button" className={LINK} onClick={() => onChange(new Set())}>
                {t("filter.none")}
              </button>
            </span>
          </div>
          <fieldset>
            <legend className="sr-only">{label}</legend>
            {groups.map(([group, members]) => {
              if (!group) {
                return members.map((option) => (
                  <OptionCheck key={option.value} option={option} on={isOn(option.value)} onToggle={toggle} />
                ));
              }
              const values = members.map((option) => option.value);
              const on = values.filter(isOn).length;
              return (
                <div key={group} role="group" aria-label={group} className="py-1">
                  <Check
                    checked={on === values.length}
                    mixed={on > 0 && on < values.length}
                    onChange={(next) => onChange(toggled(selected, all, values, next))}
                    className="font-semibold"
                  >
                    {group}
                  </Check>
                  {members.map((option) => (
                    <OptionCheck key={option.value} option={option} on={isOn(option.value)} indent onToggle={toggle} />
                  ))}
                </div>
              );
            })}
          </fieldset>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

const LINK = cn("rounded px-1.5 py-1 text-teal-800 underline-offset-2 hover:underline dark:text-teal-300", FOCUS);

/** The options in their order, those of a group together; options without a group stand on their own. */
function groupOf(options: readonly FilterOption[]): Array<[string, FilterOption[]]> {
  const groups = new Map<string, FilterOption[]>();
  for (const option of options) {
    const group = option.group ?? "";
    groups.set(group, [...(groups.get(group) ?? []), option]);
  }
  return [...groups];
}

interface OptionCheckProps {
  option: FilterOption;
  on: boolean;
  indent?: boolean;
  onToggle: (value: string, on: boolean) => void;
}

function OptionCheck({ option, on, indent = false, onToggle }: OptionCheckProps) {
  return (
    <Check checked={on} onChange={(next) => onToggle(option.value, next)} className={indent ? "pl-7" : undefined}>
      {option.mark}
      <span className="min-w-0 flex-1 truncate">{option.label}</span>
      {/* The space stands between the spans: the checkbox's name keeps the words apart, the flex box drops it. */}
      {option.note ? (
        <>
          {" "}
          <span className="text-xs text-zinc-600 dark:text-zinc-300">{option.note}</span>
        </>
      ) : null}
    </Check>
  );
}

interface CheckProps {
  checked: boolean;
  mixed?: boolean; // some of a group chosen, not all
  onChange: (checked: boolean) => void;
  className?: string | undefined;
  children: ReactNode;
}

/** A checkbox with its label; a mixed one shows a dash, as the browser draws an indeterminate box. */
function Check({ checked, mixed = false, onChange, className, children }: CheckProps) {
  const box = useRef<HTMLInputElement>(null);
  const id = useId();
  useEffect(() => {
    if (box.current) {
      box.current.indeterminate = mixed; // a DOM property only: React has no attribute for it
    }
  }, [mixed]);
  return (
    <div className={cn("flex min-h-9 items-center gap-2 rounded px-2 hover:bg-zinc-100 dark:hover:bg-zinc-700", className)}>
      <input
        ref={box}
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className={cn("size-4 shrink-0 accent-teal-700 dark:accent-teal-400", FOCUS)}
      />
      <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
        {children}
      </label>
    </div>
  );
}

export interface FilterChip {
  key: string;
  name: string; // "Kategori"
  value: string; // "Market"
  onRemove: () => void;
}

/** The filters that are set, each with a button that takes it off, and one that clears them all. */
export function FilterChips({ chips, onReset }: { chips: readonly FilterChip[]; onReset?: () => void }) {
  const { t } = useTranslation();
  if (chips.length === 0) {
    return null;
  }
  return (
    <ul aria-label={t("filter.active")} className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <li
          key={chip.key}
          className="inline-flex items-center gap-1 rounded-full border border-zinc-300 bg-white py-0.5 pl-3 pr-0.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
        >
          <span className="text-zinc-600 dark:text-zinc-300">{chip.name}:</span>
          <span>{chip.value}</span>
          <button
            type="button"
            aria-label={t("filter.remove", { name: chip.name })}
            onClick={chip.onRemove}
            className={cn(
              "inline-flex size-8 items-center justify-center rounded-full text-zinc-600 hover:bg-zinc-100",
              "dark:text-zinc-300 dark:hover:bg-zinc-700",
              FOCUS,
            )}
          >
            <CloseIcon className="size-4" />
          </button>
        </li>
      ))}
      {onReset ? (
        <li>
          <button type="button" className={LINK} onClick={onReset}>
            {t("filter.reset")}
          </button>
        </li>
      ) : null}
    </ul>
  );
}
