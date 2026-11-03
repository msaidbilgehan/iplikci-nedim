// İplikçi Nedim's word on the money (F06): his face, coloured by how the money stands, beside a line of his from the
// series, and under it the situation the line is said about. The service chooses the lines (app.sayings): the first is
// the most pressing situation's, the day's own; "Başka bir söz" goes through the rest, each true of today. The face is
// decoration: the line and its sentence say all its colour does.

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Saying } from "../../api/types";
import { cn } from "../../lib/cn";

type Mood = Saying["mood"];

// The logo is his face when the money goes well; the others are drawn from it in the verdicts' colours
// (packaging/icons.py).
export const FACES: Record<Mood, string> = {
  good: "/logo.png",
  warning: "/face-warning.png",
  critical: "/face-critical.png",
  neutral: "/face-neutral.png",
};

// The bubble and its tail in the verdicts' colours, opaque so the tail meets the bubble without a seam.
const BUBBLES: Record<Mood, string> = {
  good: "border-teal-200 bg-teal-50 text-teal-950 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-50",
  warning: "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-50",
  critical: "border-red-200 bg-red-50 text-red-950 dark:border-red-800 dark:bg-red-950 dark:text-red-50",
  neutral: "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
};

/** A line as it is spoken: one sentence in quotation marks, a dialogue's turns each on a line of its own. */
function Spoken({ lines }: { lines: readonly string[] }) {
  if (lines.length === 1) {
    return <p className="text-lg font-medium leading-snug">“{lines[0]}”</p>;
  }
  return (
    <div className="flex flex-col gap-0.5 text-lg font-medium leading-snug">
      {lines.map((line) => (
        <p key={line}>– {line}</p>
      ))}
    </div>
  );
}

export function NedimSays({ sayings }: { sayings: readonly Saying[] }) {
  const { t } = useTranslation("dashboard");
  const [turn, setTurn] = useState(0);
  const said = sayings[turn % Math.max(sayings.length, 1)];
  if (!said) {
    return null;
  }
  return (
    <section aria-label={t("nedim.label")} className="flex items-start gap-3 sm:gap-4">
      <img
        src={FACES[said.mood]}
        alt=""
        width={64}
        height={64}
        className="size-12 shrink-0 rounded-xl sm:size-16 sm:rounded-2xl"
      />
      <div className={cn("relative min-w-0 flex-1 rounded-2xl border px-4 py-3", BUBBLES[said.mood])}>
        {/* The bubble's tail, pointing at the face. */}
        <span
          aria-hidden="true"
          className={cn("absolute -left-[7px] top-4 size-3 rotate-45 border-b border-l sm:top-6", BUBBLES[said.mood])}
        />
        <div aria-live="polite" aria-atomic="true" className="relative flex flex-col gap-2">
          <blockquote>
            <Spoken lines={said.quote.lines} />
          </blockquote>
          {/* One run of text: on a narrow screen the sentence wraps within itself, the dot staying by the name. */}
          <p className="text-sm">
            <span className="font-semibold">{t("nedim.name")}</span>
            {"\u00a0· "}
            <span>{said.reason}</span>
          </p>
        </div>
        {sayings.length > 1 ? (
          <button
            type="button"
            onClick={() => setTurn((was) => (was + 1) % sayings.length)}
            className={cn(
              "relative -ml-2 mt-1 inline-flex min-h-11 items-center rounded-lg px-2 text-sm font-medium",
              "underline underline-offset-2 hover:no-underline",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
            )}
          >
            {t("nedim.another")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
