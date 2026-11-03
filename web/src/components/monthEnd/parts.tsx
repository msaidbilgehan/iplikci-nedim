// What the month-end screens share (F11): a month's status as an icon and its name, and the download of the months'
// script-free pages (F20). The pages are written by the analysis and downloaded zipped, the month's own among them; the
// interface writes none of its own. Where a month's rows are is lib/rows'.

import { useTranslation } from "react-i18next";

import { useExports } from "../../api/queries";
import type { ExportKind, Labels, MonthStatus } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { MONTH_TONES } from "../dashboard/ClosingCard";
import { DownloadLink } from "../ui/LinkButton";
import { Status } from "../ui/Status";

export const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

// A link that opens a row's detail at the side of the page.
export const ROW_LINK = cn(
  "rounded underline decoration-1 underline-offset-2 hover:decoration-2",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

/** A month's status, an account's in it too: its icon and its name, never the colour alone. */
export function MonthStatusMark({ status, labels, label }: { status: MonthStatus; labels: Labels; label?: string }) {
  return <Status tone={MONTH_TONES[status]}>{label ?? labelOf(labels, "MonthStatus", status)}</Status>;
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
      <DownloadLink href={`/api/exports/${kind}`}>{t("export.download")}</DownloadLink>
      {found ? (
        <p className={SMALL}>
          {t("export.hint", { time: formatTime(found.made_at) })}
          {thisMonth ? ` ${t("export.thisMonth")}` : ""}
        </p>
      ) : null}
    </div>
  );
}
