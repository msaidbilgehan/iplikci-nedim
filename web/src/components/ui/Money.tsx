// An amount with how sure it is (features.md: a figure that is not certain is never shown as certain; architecture §8).
// A confirmed amount stands alone. A provisional one carries "geçici", one its statement does not show "ekstrede yok",
// and a non-bank bill's unmatched one "yalnızca bilgi", each mark explaining itself from the glossary. The last two
// count in no total, so their figures are muted. The sign is written, never left to colour: −1.234,56 TL, +40.000,00 TL.

import type { Certainty, Money as Amount } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatFlow, formatMoney } from "../../lib/format";
import { Term, type TermId } from "./Term";

const MARKS: Record<Exclude<Certainty, "confirmed">, TermId> = {
  provisional: "provisional",
  excluded: "notOnStatement",
  info: "infoOnly",
};

interface MoneyProps {
  value: Amount;
  certainty?: Certainty;
  direction?: "in" | "out"; // written with + or −, money coming in or going out
  className?: string;
}

export function Money({ value, certainty = "confirmed", direction, className }: MoneyProps) {
  const counted = certainty === "confirmed" || certainty === "provisional";
  return (
    <span className={cn("inline-flex flex-wrap items-baseline gap-x-1.5", className)}>
      <span className={cn("whitespace-nowrap tabular-nums", !counted && "text-zinc-600 dark:text-zinc-400")}>
        {direction ? formatFlow(value, direction) : formatMoney(value)}
      </span>
      {certainty === "confirmed" ? null : (
        <Term
          id={MARKS[certainty]}
          className={cn(
            "rounded border border-dashed px-1 text-xs font-normal no-underline",
            "border-zinc-400 text-zinc-700 dark:border-zinc-500 dark:text-zinc-300",
          )}
        />
      )}
    </span>
  );
}
