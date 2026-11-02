// A question before an action that is not simply taken back (features.md F03: removing a document asks first). It is
// a modal alert dialog: Radix keeps the focus inside it and closes it on Escape; the page behind is inert while it
// asks, the safe choice has the focus first, a press outside does not count as an answer, and the focus goes back to
// whatever opened it. It draws its own backdrop: Radix's overlay locks the page's scroll with an inline <style>, which
// the CSP refuses (style-src 'self'), so the root element's own style holds the scroll instead.

import * as RadixDialog from "@radix-ui/react-dialog";
import { type ReactNode, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { Button } from "./Button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode; // what will happen, in a sentence or two
  confirmLabel: string; // the action itself: "Çöp kutusuna taşı"
  onConfirm: () => void;
  cancelLabel?: string; // "Vazgeç" by default
  variant?: "primary" | "danger";
  busy?: boolean; // the action runs: the dialog waits for it
  children?: ReactNode; // more about what is affected, below the description
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  cancelLabel,
  variant = "primary",
  busy = false,
  children,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const cancel = useRef<HTMLButtonElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  useScrollHeld(open);
  return (
    <RadixDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!busy) {
          onOpenChange(next);
        }
      }}
    >
      <RadixDialog.Portal>
        <div aria-hidden="true" className="fixed inset-0 z-40 bg-zinc-950/50" />
        <RadixDialog.Content
          ref={inertBehind}
          role="alertdialog"
          onOpenAutoFocus={(event) => {
            returnTo.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
            event.preventDefault();
            cancel.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnTo.current?.focus();
          }}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2",
            "max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-lg border p-5 shadow-xl",
            "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
          )}
        >
          <RadixDialog.Title className="text-lg font-semibold">{title}</RadixDialog.Title>
          <RadixDialog.Description className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
            {description}
          </RadixDialog.Description>
          {children ? <div className="mt-3 text-sm">{children}</div> : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button ref={cancel} variant="secondary" disabled={busy} onClick={() => onOpenChange(false)}>
              {cancelLabel ?? t("cancel")}
            </Button>
            <Button variant={variant} disabled={busy} onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/**
 * While the dialog is on the page, everything else is inert: neither focusable nor read. Radix hides the page from
 * screen readers with aria-hidden alone, which leaves its controls in the tab order (axe: aria-hidden-focus). A ref
 * callback, as the dialog's element mounts only after its portal has; Radix's focus guards stay as they are.
 */
function inertBehind(dialog: HTMLDivElement | null): (() => void) | undefined {
  if (!dialog) {
    return undefined;
  }
  const others = [...document.body.children].filter(
    (child) => !child.contains(dialog) && !child.hasAttribute("inert") && !child.hasAttribute("data-radix-focus-guard"),
  );
  for (const other of others) {
    other.setAttribute("inert", "");
  }
  return () => {
    for (const other of others) {
      other.removeAttribute("inert");
    }
  };
}

/** While open, the page behind does not scroll: set on the root element's style, which the CSP allows. */
function useScrollHeld(held: boolean): void {
  useEffect(() => {
    if (!held) {
      return undefined;
    }
    const root = document.documentElement;
    const before = root.style.overflow;
    root.style.overflow = "hidden";
    return () => {
      root.style.overflow = before;
    };
  }, [held]);
}
