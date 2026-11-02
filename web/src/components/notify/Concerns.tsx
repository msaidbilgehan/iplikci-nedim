// What a notification's event concerns (architecture §13), told by its kind and target: a document, a row or a month
// with the page that opens it, or the screen that shows a bill, a payment ahead or a series; nothing for an event that
// stands for many. A page not built yet is named without a link (lib/links.ts).

import { useTranslation } from "react-i18next";

import type { Destination, NotificationItem } from "../../api/types";
import { formatMonth } from "../../lib/format";
import { ScreenLink } from "../ui/Say";

// The events whose target is a row's fingerprint, besides transaction.* (architecture §13).
const ROW_KINDS: ReadonlySet<string> = new Set(["income.received", "evidence.unmatched"]);
// The events about what the days ahead hold, and those about a series of payments: their screens show them.
const CALENDAR_KINDS: ReadonlySet<string> = new Set(["payment.due_soon", "balance.forecast_negative"]);
const SERIES_KINDS: ReadonlySet<string> = new Set([
  "expected_payment.missing",
  "income.late",
  "subscription.price_changed",
  "subscription.paid_after_cancel",
]);
const SHORT = 8; // the characters of a fingerprint or a sha256 that tell it apart at a glance

const screen = (name: Destination["screen"], id = ""): Destination => ({ screen: name, id, query: {} });

export function Concerns({ item }: { item: NotificationItem }) {
  const { t } = useTranslation("notifications");
  const { kind, target } = item;
  if (!target) {
    return "—";
  }
  if (kind.startsWith("document.")) {
    return <Code label={t("log.document")} value={target} link={screen("document", target)} />;
  }
  if (kind.startsWith("transaction.") || ROW_KINDS.has(kind)) {
    return <Code label={t("log.row")} value={target} link={screen("transaction", target)} />;
  }
  if (kind.startsWith("month.")) {
    return (
      <ScreenLink link={screen("month", target)} className="whitespace-nowrap">
        {formatMonth(target)}
      </ScreenLink>
    );
  }
  if (kind.startsWith("invoice.")) {
    return <Named link={screen("invoices")} name={t("log.screens.invoices")} />;
  }
  if (CALENDAR_KINDS.has(kind)) {
    return <Named link={screen("calendar")} name={t("log.screens.calendar")} />;
  }
  return SERIES_KINDS.has(kind) ? <Named link={screen("subscription")} name={t("log.screens.subscriptions")} /> : "—";
}

/** A document's or a row's short code, the whole one on hover, leading to its page. */
function Code({ label, value, link }: { label: string; value: string; link: Destination }) {
  return (
    <ScreenLink link={link} className="whitespace-nowrap">
      {label} <code title={value}>{value.slice(0, SHORT)}</code>
    </ScreenLink>
  );
}

function Named({ link, name }: { link: Destination; name: string }) {
  const { t } = useTranslation("notifications");
  return (
    <ScreenLink link={link} className="whitespace-nowrap">
      {t("log.screen", { name })}
    </ScreenLink>
  );
}
