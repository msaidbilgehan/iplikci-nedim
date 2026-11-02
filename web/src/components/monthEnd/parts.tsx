// What the month-end screens share (F11): a month's status as an icon and its name, the window of days a month's rows
// are asked for, and the download of the months' script-free pages (F20). The pages are written by the analysis and
// downloaded zipped, the month's own among them; the interface writes none of its own.

import { useTranslation } from "react-i18next";

import { useExports } from "../../api/queries";
import type { Destination, ExportKind, Labels, MonthStatus } from "../../api/types";
import { cn } from "../../lib/cn";
import { addDays, formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { MONTH_TONES } from "../dashboard/ClosingCard";
import { Status } from "../ui/Status";

export const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

// A link that opens a row's detail at the side of the page.
export const ROW_LINK = cn(
  "rounded underline decoration-1 underline-offset-2 hover:decoration-2",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export const LINK_BUTTON = cn(
  "inline-flex min-h-11 items-center gap-1 rounded-md border px-3 text-sm font-medium",
  "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

/** A month's status, an account's in it too: its icon and its name, never the colour alone. */
export function MonthStatusMark({ status, labels, label }: { status: MonthStatus; labels: Labels; label?: string }) {
  return <Status tone={MONTH_TONES[status]}>{label ?? labelOf(labels, "MonthStatus", status)}</Status>;
}

/** "2026-02" → its first and last days, as the Transactions screen's filters take them. */
export function monthWindow(month: string): { from: string; to: string } {
  const from = `${month}-01`;
  const [year = 0, number = 1] = month.split("-").map(Number);
  const next = number === 12 ? `${year + 1}-01-01` : `${year}-${String(number + 1).padStart(2, "0")}-01`;
  return { from, to: addDays(next, -1) };
}

/** The month's rows on the Transactions screen, narrowed by the filters given (in the API's names). */
export function monthRows(month: string, query: Record<string, string> = {}): Destination {
  return { screen: "transactions", id: "", query: { ...monthWindow(month), ...query } };
}

/** Whether a month ("2026-10") is a valid one to ask for. */
export function isMonth(value: string): boolean {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

/** The months' pages to download zipped, with the day the analysis wrote them; said so when not written yet. */
export function ExportLink({ kind, thisMonth = false }: { kind: ExportKind; thisMonth?: boolean }) {
  const { t } = useTranslation("monthEnd");
  const exports = useExports();
  const found = exports.data?.find((item) => item.kind === kind);
  if (exports.isPending) {
    return null;
  }
  if (exports.isSuccess && !found) {
    return <p className={SMALL}>{t("export.missing")}</p>;
  }
  // Without the list (it could not be read) the download is still offered; the service says if it is missing.
  return (
    <div className="flex flex-col items-start gap-1">
      <a href={`/api/exports/${kind}`} download className={LINK_BUTTON}>
        {t("export.download")}
      </a>
      {found ? (
        <p className={SMALL}>
          {t("export.hint", { time: formatTime(found.made_at) })}
          {thisMonth ? ` ${t("export.thisMonth")}` : ""}
        </p>
      ) : null}
    </div>
  );
}
