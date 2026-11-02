// A word of the glossary (features.md: "Terimler sözlüğü"; architecture §18): it explains itself on hover and when the
// keyboard reaches it — a screen reader hears the explanation as the word's description — and on a tap or a click, as
// touch screens have no hover. The explanations are in the glossary namespace.

import * as Tooltip from "@radix-ui/react-tooltip";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import type glossary from "../../locales/tr/glossary.json";

export type TermId = keyof typeof glossary;

interface TermProps {
  id: TermId;
  children?: ReactNode; // the words as the sentence has them ("kesim tarihinde"); the term itself by default
  className?: string;
}

export function Term({ id, children, className }: TermProps) {
  const { t } = useTranslation("glossary");
  const [open, setOpen] = useState(false);
  return (
    <Tooltip.Root open={open} onOpenChange={setOpen}>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          className={cn(
            "cursor-help rounded-sm underline decoration-dotted decoration-1 underline-offset-4",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
            className,
          )}
          // Radix closes a tooltip when its trigger is pressed, as befits a hover hint. A glossary word opens on a tap
          // or a click instead; a finger lifting off the screen is no leave either.
          onPointerDown={(event) => event.preventDefault()}
          onPointerLeave={(event) => {
            if (event.pointerType === "touch") {
              event.preventDefault();
            }
          }}
          onClick={(event) => {
            event.preventDefault();
            setOpen(true);
          }}
        >
          {children ?? t(`${id}.term`)}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          collisionPadding={8}
          aria-label={t(`${id}.text`)}
          className={cn(
            "z-50 max-w-xs rounded-md border p-3 text-sm shadow-lg",
            "border-zinc-200 bg-white text-zinc-800 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
          )}
        >
          <span className="block font-semibold first-letter:uppercase">{t(`${id}.term`)}</span>
          <span className="mt-1 block">{t(`${id}.text`)}</span>
          <Tooltip.Arrow width={12} height={6} className="fill-white dark:fill-zinc-800" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
