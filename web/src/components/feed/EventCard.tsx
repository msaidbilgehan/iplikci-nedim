// An event of the feed as a row of its day's list (F05): what happened, as the service says it in a sentence, when, and
// the row or the document it concerns as the ledger and the archive keep them now (a receipt's row a statement
// confirmed since shows confirmed). It leads to its row, document, month or screen; the detailed view adds every value
// the event carries.

import type { TFunction } from "i18next";
import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";

import type { FeedItem, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatClock, formatDay, formatMoney, formatMonth, formatPeriod, formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple, useView } from "../Preferences";
import type { Tone } from "../ui/Badge";
import { Facts } from "../ui/Card";
import { Money } from "../ui/Money";
import { NextStep } from "../ui/Say";
import { Status } from "../ui/Status";

// How each kind reads; a kind not listed is neutral news (a document arrived, a new row).
const TONES: Readonly<Record<string, Tone>> = {
  "document.processed": "good",
  "document.unprocessed": "warning",
  "document.unreadable": "critical",
  "transaction.confirmed": "good",
  "transaction.large": "warning",
  "evidence.unmatched": "warning",
  "invoice.matched": "good",
  "invoice.unmatched": "warning",
  "payment.due_soon": "warning",
  "expected_payment.missing": "warning",
  "balance.forecast_negative": "critical",
  "subscription.price_changed": "warning",
  "subscription.paid_after_cancel": "warning",
  "income.received": "good",
  "income.late": "warning",
  "month.closed": "good",
  "month.needs_check": "warning",
  "parser.format_alarm": "critical",
  "mail.auth_failed": "critical",
  "mail.bridge_alarm": "warning",
  "mail.bridge_silent": "warning",
  "backup.failed": "critical",
  "bridge.paired": "good",
};

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

// The document news whose sentence only restates its name ("Yeni bir belge geldi.", "Bir belge okundu.").
const PLAIN_DOCUMENT_NEWS: ReadonlySet<string> = new Set(["document.received", "document.processed"]);

/** What the event is about, in a few words: its row, its document, the name its detail gives, or its account. */
export function subjectOf(item: FeedItem): string {
  return item.row?.title || item.document?.name || item.detail.title || item.account?.label || "";
}

interface EventCardProps {
  item: FeedItem;
  labels: Labels;
  isNew: boolean; // came after the list was first shown
}

export function EventCard({ item, labels, isNew }: EventCardProps) {
  const { t } = useTranslation("feed");
  const { t: tc } = useTranslation();
  const { view } = useView();
  const heading = useId();
  // A document's arrival and its reading say no more than their name and the document's: the simple view leaves the
  // sentence out when the document is named below it.
  const said = view === "detailed" || !PLAIN_DOCUMENT_NEWS.has(item.kind) || item.document === null;
  return (
    <article
      aria-labelledby={heading}
      className={cn("px-4 py-3", isNew && "bg-teal-50 dark:bg-teal-950/50")}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h4 id={heading} className="text-sm font-medium">
          <Status tone={TONES[item.kind] ?? "neutral"}>{item.label}</Status>
        </h4>
        <span className={cn("flex items-center gap-2", SMALL)}>
          {isNew ? (
            <span className="rounded-full bg-teal-700 px-2 py-0.5 font-medium text-white dark:bg-teal-400 dark:text-zinc-950">
              {t("events.new")}
            </span>
          ) : null}
          <time dateTime={item.at}>{formatClock(item.at)}</time>
        </span>
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 pl-6">
        <div className="min-w-0">
          {said ? <p className="text-sm text-zinc-800 dark:text-zinc-200">{item.text}</p> : null}
          <Simple>
            <Subject item={item} labels={labels} />
          </Simple>
          <Detailed>
            <div className="mt-2">
              <Facts items={factsOf(item, labels, t)} />
            </div>
          </Detailed>
        </div>
        {item.link ? (
          <NextStep
            step={{ link: item.link, label: tc(`open.${item.link.screen}`) }}
            context={subjectOf(item)}
            className="shrink-0"
          />
        ) : null}
      </div>
    </article>
  );
}

function Subject({ item, labels }: { item: FeedItem; labels: Labels }) {
  const { row, document } = item;
  if (row) {
    return (
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-medium">{row.title}</span>
        <Money value={row.amount} direction={row.direction} certainty={row.certainty} />
        <span className={SMALL}>
          {row.account.label} · {formatDay(row.day)}
        </span>
      </p>
    );
  }
  if (document) {
    return (
      <p className="mt-0.5 text-sm">
        <span className="font-medium wrap-break-word">{document.name}</span>
        {document.status === "processed" ? null : (
          <span className={SMALL}> · {labelOf(labels, "DocumentStatus", document.status)}</span>
        )}
      </p>
    );
  }
  return item.account ? <p className={`mt-1 ${SMALL}`}>{item.account.label}</p> : null;
}

/** Every value the event carries, named: the detailed view's raw data. */
function factsOf(item: FeedItem, labels: Labels, t: TFunction<"feed">): Array<[string, ReactNode]> {
  const d = item.detail;
  const facts: Array<[string, ReactNode]> = [
    [t("events.facts.event"), `${item.kind} · #${item.id}`],
    [t("events.facts.at"), formatTime(item.at)],
  ];
  const add = (shown: boolean, name: string, value: () => ReactNode) => {
    if (shown) {
      facts.push([name, value()]);
    }
  };
  add(item.account !== null, t("events.facts.account"), () => item.account?.label);
  add(item.row !== null, t("events.facts.row"), () => item.row && <RowFact row={item.row} labels={labels} />);
  add(item.document !== null, t("events.facts.document"), () => {
    const doc = item.document;
    if (!doc) {
      return null;
    }
    const kind = doc.kind ? ` · ${labelOf(labels, "DocumentKind", doc.kind)}` : "";
    return `${doc.name} · ${labelOf(labels, "DocumentStatus", doc.status)}${kind}`;
  });
  add(Boolean(d.title) && item.row === null, t("events.facts.title"), () => d.title);
  add(d.amount !== null, t("events.facts.amount"), () => d.amount && formatMoney(d.amount));
  add(d.minimum !== null, t("events.facts.minimum"), () => d.minimum && formatMoney(d.minimum));
  add(d.balance !== null, t("events.facts.balance"), () => d.balance && formatMoney(d.balance));
  add(d.old !== null && d.new !== null, t("events.facts.price"), () =>
    d.old && d.new ? `${formatMoney(d.old)} → ${formatMoney(d.new)}` : null,
  );
  add(d.day !== null, t("events.facts.day"), () => d.day && formatDay(d.day));
  add(d.payment !== null, t("events.facts.payment"), () => d.payment && labelOf(labels, "PaymentKind", d.payment));
  add(d.period !== null, t("events.facts.period"), () => d.period && labelOf(labels, "SeriesPeriod", d.period));
  add(Boolean(d.cancelled), t("events.facts.cancelled"), () => formatMonth(d.cancelled));
  add(d.status !== null, t("events.facts.status"), () => d.status && labelOf(labels, "MonthStatus", d.status));
  add(d.count !== null, t("events.facts.count"), () => d.count);
  add(d.first !== null && d.last !== null, t("events.facts.span"), () => formatPeriod(d.first ?? "", d.last ?? ""));
  add(d.provisional === true, t("events.facts.provisional"), () => t("events.facts.provisionalYes"));
  add(d.source !== null, t("events.facts.source"), () => d.source && labelOf(labels, "SourceKind", d.source));
  add(d.document_kind !== null && item.document === null, t("events.facts.documentKind"), () =>
    d.document_kind ? labelOf(labels, "DocumentKind", d.document_kind) : null,
  );
  add(Boolean(d.reader || d.parser), t("events.facts.reader"), () =>
    [d.reader || d.parser, d.version].filter(Boolean).join(" · "),
  );
  add(Boolean(d.reason), t("events.facts.reason"), () => d.reason);
  add(Boolean(d.stage), t("events.facts.stage"), () => d.stage);
  add(d.unverified.length > 0, t("events.facts.unverified"), () => d.unverified.map((a) => a.label).join(", "));
  return facts;
}

function RowFact({ row, labels }: { row: NonNullable<FeedItem["row"]>; labels: Labels }) {
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <span>{row.title}</span>
      <Money value={row.amount} direction={row.direction} certainty={row.certainty} />
      <span className={SMALL}>
        {formatDay(row.day)} · {row.category || labelOf(labels, "TransactionKind", row.kind)}
      </span>
    </span>
  );
}
