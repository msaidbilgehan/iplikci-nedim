// What a chart says over a month that has not closed, as the month-end closing tells it (F11): a month waiting for
// its statements is not missing anything and says the day it should close ("bekliyor", "~24.11"), the month that runs
// runs on, one missing a document or wanting a check says so. The Pano's months mark their months by the dashboard's
// closing, Değerlendirme's charts their partial months by the month-end list; a partial month the closing has closed
// (a period cuts it) keeps the chart's own "eksik".

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { useMonthEnds } from "../../api/queries";
import type { MonthStatus } from "../../api/types";
import { formatDayMonth } from "../../lib/format";

/** Why a partial month is not whole, in the caller's words: "bekliyor" and "~24.11", the day it should close. */
export interface MonthMark {
  word: string; // over its column, short enough for a narrow one
  day?: string;
  name?: string; // in its name, when the word alone says too little there: "belge eksik"
}

export type Unclosed = Exclude<MonthStatus, "closed">;

/** A month's status when it has not closed. */
export function isUnclosed(status: MonthStatus): status is Unclosed {
  return status !== "closed";
}

/** A month not closed in a word over its column, with the day it should close when one can be promised. */
export function useMarkOf(): (status: Unclosed, closesBy: string | null) => MonthMark {
  const { t } = useTranslation("charts");
  return (status, closesBy) => {
    const word = t(`marks.${status}`);
    if (status === "missing" || status === "check") {
      return { word, name: t(`markNames.${status}`) };
    }
    return status === "waiting" && closesBy ? { word, day: `~${formatDayMonth(closesBy)}` } : { word };
  };
}

/** The marks of the months the month-end closing has not closed (the Ay sonu list's), by month. */
export function useClosingMarks(): Readonly<Record<string, MonthMark>> {
  const markOf = useMarkOf();
  const months = useMonthEnds().data?.months ?? [];
  const marks: Record<string, MonthMark> = {};
  for (const month of months) {
    if (isUnclosed(month.status)) {
      marks[month.month] = markOf(month.status, month.closes_by);
    }
  }
  return marks;
}

/** A partial month's name as a chart's tip and table write it: "Ekim 2026 (bekliyor, ~24.11)", or "(eksik ay)". */
export function partialName(name: string, mark: MonthMark | undefined, t: TFunction<"charts">): string {
  if (!mark) {
    return t("partialMonth", { month: name });
  }
  return t("markedMonth", { month: name, mark: mark.name ?? (mark.day ? `${mark.word}, ${mark.day}` : mark.word) });
}
