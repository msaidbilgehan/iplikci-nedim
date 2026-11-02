// The Bills screen (F14): the bills and receipts non-bank senders mailed, grouped by what the bank's rows say of them.
// A matched one shows the bank row that paid it, which opens in İşlemler; a pending one waits for its days or for the
// bank's documents to reach them; an unmatched one is information only, with what may explain it. None of them changes
// a total: the bank row is what counts. Each opens in the viewer; the simple view names the nearest due day.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useInvoices, useLabels } from "../api/queries";
import type { InvoiceItem, Invoices, Labels } from "../api/types";
import { useView } from "../components/Preferences";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { Say, ScreenLink } from "../components/ui/Say";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDay, formatMoney, formatPeriod } from "../lib/format";
import { labelOf } from "../lib/labels";

const MUTED = "block text-xs text-zinc-600 dark:text-zinc-300";
const LINK =
  "rounded font-medium text-teal-800 underline focus-visible:outline-2 focus-visible:outline-teal-600 " +
  "dark:text-teal-200";
const STATUSES = ["pending", "unmatched", "matched"] as const;
const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

type Status = (typeof STATUSES)[number];

export default function InvoicesPage() {
  const { t } = useTranslation("invoices");
  const invoices = useInvoices();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("title")} description={t("description")} />
      {invoices.isPending ? <Loading /> : null}
      {invoices.isError ? <Failure error={invoices.error} onRetry={() => void invoices.refetch()} /> : null}
      {invoices.data ? <InvoiceGroups found={invoices.data} labels={labels} /> : null}
    </div>
  );
}

/** The simple view's sentence: the pending bill due soonest, or that none waits. */
function Sentence({ found }: { found: Invoices }) {
  const { t } = useTranslation("invoices");
  const pending = found.items.filter((item) => item.status === "pending");
  const due = pending
    .filter((item): item is InvoiceItem & { due: string } => item.due !== null)
    .sort((a, b) => a.due.localeCompare(b.due))[0];
  if (due) {
    return (
      <Say next={{ link: CALENDAR, label: t("next") }}>
        {t("sayDue", { day: due.due, seller: due.seller, amount: formatMoney(due.total) })}
      </Say>
    );
  }
  return pending.length === 0 ? <Say>{t("sayNone")}</Say> : null;
}

function InvoiceGroups({ found, labels }: { found: Invoices; labels: Labels }) {
  const { t } = useTranslation("invoices");
  if (found.items.length === 0) {
    return (
      <Empty title={t("empty")}>
        {t("emptyBefore")}{" "}
        <Link to="/sistem" className={LINK}>
          {t("emptyLink")}
        </Link>{" "}
        {t("emptyAfter")}
      </Empty>
    );
  }
  const { pending, unmatched, matched } = found.counts;
  return (
    <div className="flex flex-col gap-4">
      <Sentence found={found} />
      <p className="text-sm text-zinc-600 dark:text-zinc-300">
        {t("counts", { total: found.items.length, pending, unmatched, matched })}
      </p>
      {STATUSES.map((status) => {
        const items = found.items.filter((item) => item.status === status);
        if (items.length === 0) {
          return null;
        }
        return (
          <Card
            key={status}
            title={t(`group.${status}.title`)}
            action={status === "unmatched" ? <Badge tone="neutral">{t("infoOnly")}</Badge> : undefined}
          >
            <div className="flex flex-col gap-2">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">{t(`group.${status}.about`)}</p>
              <InvoiceTable items={items} status={status} labels={labels} />
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function InvoiceTable({ items, status, labels }: { items: InvoiceItem[]; status: Status; labels: Labels }) {
  const { t } = useTranslation("invoices");
  const detailed = useView().view === "detailed";
  return (
    <Table>
      <caption className="sr-only">{t(`group.${status}.caption`)}</caption>
      <thead>
        <tr>
          <Th>{t("seller")}</Th>
          <Th>{t("kind")}</Th>
          <Th>{t("issued")}</Th>
          <Th>{t("due")}</Th>
          <Th className="text-right">{t("amount")}</Th>
          <Th>{t(`group.${status}.outcome`)}</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.key}>
            <Td>
              <ScreenLink link={{ screen: "document", id: item.sha256, query: {} }} className="font-medium">
                {item.seller}
              </ScreenLink>
              {item.number ? <span className={MUTED}>{t("number", { number: item.number })}</span> : null}
              {detailed ? <span className={MUTED}>{item.document}</span> : null}
              <Lines item={item} />
            </Td>
            <Td>{labelOf(labels, "InvoiceKind", item.kind)}</Td>
            <Td className="whitespace-nowrap">{formatDay(item.issued)}</Td>
            <Td className="whitespace-nowrap">{item.due ? formatDay(item.due) : t("noDue")}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">
              {formatMoney(item.total)}
              {item.status === "unmatched" ? <span className={MUTED}>{t("infoOnlyRow")}</span> : null}
            </Td>
            <Td>
              <Outcome item={item} />
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** What the bank's rows say: the row that paid it, what may explain why none did, or the days it is looked for in. */
function Outcome({ item }: { item: InvoiceItem }) {
  const { t } = useTranslation("invoices");
  if (item.row) {
    return (
      <>
        <ScreenLink
          link={{ screen: "transaction", id: item.row.fingerprint, query: {} }}
          className="whitespace-nowrap tabular-nums"
        >
          {t("row", { day: formatDay(item.row.day), amount: formatMoney(item.row.amount) })}
        </ScreenLink>
        <span className={MUTED}>{item.row.account.label}</span>
        <span className={MUTED}>{item.row.description}</span>
      </>
    );
  }
  if (item.reasons.length > 0) {
    return (
      <ul className="ml-4 list-disc text-xs text-zinc-700 dark:text-zinc-300">
        {item.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    );
  }
  return <span className="whitespace-nowrap">{formatPeriod(item.window.start, item.window.end)}</span>;
}

/** The items the document prints, with their quantity when it prints one. */
function Lines({ item }: { item: InvoiceItem }) {
  const { t } = useTranslation("invoices");
  if (item.lines.length === 0) {
    return null;
  }
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-teal-600">
        {t("lines", { count: item.lines.length })}
      </summary>
      <ul className="mt-1 flex flex-col gap-1">
        {item.lines.map((line, index) => (
          // The items of a document never move: their place tells two of the same name apart.
          <li key={`${index}-${line.description}`}>
            {line.description}
            {line.quantity ? ` × ${line.quantity.replace(".", ",")}` : ""} · {formatMoney(line.amount)}
          </li>
        ))}
      </ul>
    </details>
  );
}
