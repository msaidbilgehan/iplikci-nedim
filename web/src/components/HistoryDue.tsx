// The browser extension has not scanned Gmail for the start day and the senders set now (ADR-0016): it scans after
// pairing, and again when either changes.

import { useTranslation } from "react-i18next";

import { formatDay } from "../lib/format";
import { Alert } from "./ui/Alert";

export function HistoryDue({ startDay }: { startDay: string }) {
  const { t } = useTranslation("extension");
  return (
    <Alert tone="neutral" title={t("history.title")}>
      <p>{t("history.text", { day: formatDay(startDay) })}</p>
    </Alert>
  );
}
