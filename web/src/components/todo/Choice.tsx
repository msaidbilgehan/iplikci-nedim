// A to-do's checkbox for the bulk steps (F19), or one that chooses many at once: half-ticked while only some of them
// are chosen. Its touch area is 44 px; its name is its words, or `label` where it has none to show.

import { type ReactNode, useEffect, useRef } from "react";

import { cn } from "../../lib/cn";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

interface ChoiceProps {
  checked: boolean;
  onChange: (on: boolean) => void;
  mixed?: boolean; // some of the items it stands for are chosen, not all
  label?: string; // the name, when it shows no words
  children?: ReactNode; // the words it shows
  className?: string;
}

export function Choice({ checked, onChange, mixed = false, label, children, className }: ChoiceProps) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) {
      box.current.indeterminate = mixed && !checked;
    }
  }, [mixed, checked]);
  return (
    <label
      className={cn(
        "inline-flex min-h-11 min-w-11 shrink-0 cursor-pointer items-center gap-2",
        !children && "justify-center",
        className,
      )}
    >
      <input
        ref={box}
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className={cn("size-4 accent-teal-700 dark:accent-teal-400", FOCUS)}
      />
      {children ? <span className="text-sm">{children}</span> : null}
    </label>
  );
}
