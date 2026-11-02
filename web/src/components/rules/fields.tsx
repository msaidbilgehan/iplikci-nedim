// The Rules screen's form fields: a label over its control, a hint and an error under it, both tied to the control
// (aria-describedby), the control marked invalid while its error stands.

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

const CONTROL = cn(
  "min-h-11 w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const INVALID = "border-red-700 dark:border-red-400";

export const HINT = "text-xs text-zinc-600 dark:text-zinc-300";
export const ERROR = "text-sm text-red-800 dark:text-red-200";

/** A field's errors by its name; a field without one is fine. */
export type Errors<K extends string> = Partial<Record<K, string>>;

/** The id of a field's error message, for a message said elsewhere about the same field. */
export function errorIdOf(id: string): string {
  return `${id}-hata`;
}

/** The attributes that tie a control to its hint and its error, and its look while the error stands. */
export function control(id: string, { hint = false, error }: { hint?: boolean; error?: string | undefined }) {
  const describedBy = [hint ? `${id}-ipucu` : "", error ? errorIdOf(id) : ""].filter(Boolean).join(" ");
  return {
    id,
    "aria-describedby": describedBy || undefined,
    "aria-invalid": error ? true : undefined,
    className: cn(CONTROL, error && INVALID),
  };
}

interface FieldProps {
  id: string; // the control's, which the label names
  label: string;
  hint?: string;
  error?: string | undefined;
  children: ReactNode;
}

export function Field({ id, label, hint, error, children }: FieldProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint ? (
        <p id={`${id}-ipucu`} className={HINT}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorIdOf(id)} className={ERROR}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** The first field with an error gets the focus, so the keyboard lands where the form needs it. */
export function focusFirst<K extends string>(order: readonly K[], errors: Errors<K>, ids: Record<K, string>): void {
  const first = order.find((field) => errors[field]);
  if (first) {
    document.getElementById(ids[first])?.focus();
  }
}
