// One item's detail in a panel at the side of the screen, over the list it came from (a modal Radix dialog): the page
// behind is inert, Escape and the close button close it, and the focus goes back to what opened it. Like the
// confirmation dialog it draws its own backdrop and holds the scroll on the root element, as the CSP refuses the
// inline style Radix's overlay would bring. A press on the backdrop closes it too: nothing is lost by closing.

import * as RadixDialog from "@radix-ui/react-dialog";
import { type ReactNode, type RefObject, useRef } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { inertBehind, useScrollHeld } from "./Dialog";
import { CloseIcon } from "./Icons";

interface SidePanelProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode; // a line under the title: what the item is
  // What the focus goes to when the panel opens for one of its controls ("İptal ettim…" opens it at its form); the
  // title otherwise, or when that control is not there.
  initialFocus?: RefObject<HTMLElement | null> | undefined;
  children: ReactNode;
}

export function SidePanel({ open, onClose, title, description, initialFocus, children }: SidePanelProps) {
  const { t } = useTranslation();
  const returnTo = useRef<HTMLElement | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useScrollHeld(open);
  return (
    <RadixDialog.Root open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <RadixDialog.Portal>
        <div aria-hidden="true" className="fixed inset-0 z-40 bg-zinc-950/50" />
        <RadixDialog.Content
          ref={inertBehind}
          {...(description ? {} : { "aria-describedby": undefined })}
          onOpenAutoFocus={(event) => {
            returnTo.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
            event.preventDefault();
            (initialFocus?.current ?? heading.current)?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnTo.current?.focus();
          }}
          className={cn(
            "fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col shadow-xl",
            "border-l border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-zinc-200 p-4 dark:border-zinc-700">
            <div className="min-w-0">
              <RadixDialog.Title
                ref={heading}
                tabIndex={-1}
                className={cn(
                  "rounded text-lg font-semibold wrap-break-word",
                  "focus:outline-none focus-visible:outline-2 focus-visible:outline-teal-600",
                )}
              >
                {title}
              </RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
                  {description}
                </RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close
              className={cn(
                "inline-flex size-11 shrink-0 items-center justify-center rounded-md text-zinc-700 hover:bg-zinc-100",
                "dark:text-zinc-200 dark:hover:bg-zinc-800",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
              )}
            >
              <CloseIcon className="size-5" />
              <span className="sr-only">{t("close")}</span>
            </RadixDialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
