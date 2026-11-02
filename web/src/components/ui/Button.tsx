import type { ComponentProps } from "react";

import { cn } from "../../lib/cn";

// Every pair keeps WCAG AA's 4.5:1 for its text, hovered too. In the dark theme the filled buttons are light tints with
// near-black text, as the unread count beside Bildirimler: white on a mid teal or red falls under 4.5:1 there.
const VARIANTS = {
  primary: "bg-teal-700 text-white hover:bg-teal-800 dark:bg-teal-400 dark:text-zinc-950 dark:hover:bg-teal-300",
  secondary:
    "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-800 " +
    "dark:text-zinc-100 dark:hover:bg-zinc-700",
  danger: "bg-red-700 text-white hover:bg-red-800 dark:bg-red-400 dark:text-zinc-950 dark:hover:bg-red-300",
} as const;

export type ButtonVariant = keyof typeof VARIANTS;

/** A button's look, for a link that stands among buttons as one (ui/LinkButton). */
export function buttonClass(variant: ButtonVariant = "primary"): string {
  return cn(
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium",
    "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
    VARIANTS[variant],
  );
}

// With its ref, so a dialog can put the focus on one of its buttons.
interface ButtonProps extends ComponentProps<"button"> {
  variant?: ButtonVariant;
}

export function Button({ variant = "primary", className, type = "button", ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonClass(variant), "disabled:cursor-not-allowed disabled:opacity-60", className)}
      {...rest}
    />
  );
}
