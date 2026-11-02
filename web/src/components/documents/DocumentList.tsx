// The kept documents (F03's list), newest first. The simple view shows each as a card: its name leading to the viewer,
// its kind, accounts and period, when and how it came, its status in words. The detailed view is a table of every
// value, the bank and the account apart. A document that was not read says why, with its original to download and a
// reading to try again ("Claude'a ver" comes with the MCP server).

import { useTranslation } from "react-i18next";

import type { DocumentItem, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDate, formatPeriod, formatSize } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Badge, type Tone } from "../ui/Badge";
import { Button } from "../ui/Button";
import { DownloadLink } from "../ui/LinkButton";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
// One framed list with a line between the documents: a long archive reads as a list, not a pile of cards.
const LIST = cn(
  "flex flex-col divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white",
  "dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900",
);
const CARD = "flex flex-col gap-0.5 px-4 py-3 text-sm";
export const STATUS_TONES: Record<DocumentItem["status"], Tone> = {
  processed: "good",
  unprocessed: "neutral",
  unreadable: "critical",
};

export interface Reparsing {
  pending: string | null; // the document being read again: one at a time
  onReparse: (document: DocumentItem) => void;
}

interface DocumentListProps {
  documents: readonly DocumentItem[];
  labels: Labels;
  reparsing: Reparsing;
}

export function DocumentList({ documents, labels, reparsing }: DocumentListProps) {
  const { t } = useTranslation("documents");
  return (
    <>
      <Simple>
        <ul aria-label={t("list.caption")} className={LIST}>
          {documents.map((document) => (
            <DocumentCard key={document.sha256} document={document} labels={labels} reparsing={reparsing} />
          ))}
        </ul>
      </Simple>
      <Detailed>
        <DocumentTable documents={documents} labels={labels} reparsing={reparsing} />
      </Detailed>
    </>
  );
}

function kindOf(document: DocumentItem, labels: Labels, unknown: string): string {
  return document.kind ? labelOf(labels, "DocumentKind", document.kind) : unknown;
}

function banksOf(document: DocumentItem): string {
  return [...new Set(document.accounts.map((account) => account.bank).filter(Boolean))].join(", ");
}

function accountsOf(document: DocumentItem): string {
  return document.accounts.map((account) => account.label).join(", ");
}

function sourcesOf(document: DocumentItem, labels: Labels): string {
  return document.sources.map((source) => labelOf(labels, "SourceKind", source)).join(", ");
}

const viewerOf = (document: DocumentItem) => ({ screen: "document" as const, id: document.sha256, query: {} });

function StatusBadges({ document, labels }: { document: DocumentItem; labels: Labels }) {
  const { t } = useTranslation("documents");
  return (
    <span className="flex flex-wrap gap-1">
      <Badge tone={STATUS_TONES[document.status]}>{labelOf(labels, "DocumentStatus", document.status)}</Badge>
      {document.verified === false ? <Badge tone="warning">{t("list.unverified")}</Badge> : null}
    </span>
  );
}

interface DocumentCardProps {
  document: DocumentItem;
  labels: Labels;
  reparsing: Reparsing;
}

function DocumentCard({ document, labels, reparsing }: DocumentCardProps) {
  const { t } = useTranslation("documents");
  const line = [
    kindOf(document, labels, t("list.noKind")),
    accountsOf(document) || banksOf(document),
    formatPeriod(document.period_start, document.period_end),
  ].filter(Boolean);
  return (
    <li className={CARD}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <ScreenLink link={viewerOf(document)} className="min-w-0 font-medium wrap-break-word">
          {document.name}
        </ScreenLink>
        <StatusBadges document={document} labels={labels} />
      </div>
      <p className={SMALL}>{line.join(" · ")}</p>
      <p className={SMALL}>
        {t("list.arrived", { day: formatDate(document.added_at), sources: sourcesOf(document, labels) })}
      </p>
      {document.status === "processed" ? null : <Unread document={document} reparsing={reparsing} />}
    </li>
  );
}

/** Why a document was not read, its original to download, and a reading to try again (F03). */
function Unread({ document, reparsing }: { document: DocumentItem; reparsing: Reparsing }) {
  const { t } = useTranslation("documents");
  const busy = reparsing.pending === document.sha256;
  return (
    <div className="mt-1 flex flex-col gap-2 text-sm">
      <p>{document.reason ? t("unread.reason", { reason: document.reason }) : t("unread.noReason")}</p>
      <div className="flex flex-wrap items-center gap-2">
        <DownloadLink
          href={`/api/documents/${document.sha256}/download`}
          aria-label={t("unread.downloadOf", { name: document.name })}
        >
          {t("unread.download")}
        </DownloadLink>
        <Button
          variant="secondary"
          disabled={reparsing.pending !== null}
          aria-label={busy ? t("unread.reparsing") : t("unread.reparseOf", { name: document.name })}
          onClick={() => reparsing.onReparse(document)}
        >
          {busy ? t("unread.reparsing") : t("unread.reparse")}
        </Button>
      </div>
    </div>
  );
}

function DocumentTable({ documents, labels, reparsing }: DocumentListProps) {
  const { t } = useTranslation("documents");
  const none = t("list.none");
  return (
    <Table>
      <caption className="sr-only">{t("list.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("list.document")}</Th>
          <Th>{t("list.kind")}</Th>
          <Th>{t("list.bank")}</Th>
          <Th>{t("list.account")}</Th>
          <Th>{t("list.period")}</Th>
          <Th>{t("list.status")}</Th>
          <Th>{t("list.source")}</Th>
          <Th>{t("list.added")}</Th>
          <Th className="text-right">{t("list.size")}</Th>
        </tr>
      </thead>
      <tbody>
        {documents.map((document) => (
          <tr key={document.sha256}>
            <Td className="min-w-48">
              <ScreenLink link={viewerOf(document)} className="font-medium wrap-break-word">
                {document.name}
              </ScreenLink>
              {document.name !== document.file ? (
                <span className={cn("block wrap-break-word", SMALL)}>{document.file}</span>
              ) : null}
            </Td>
            <Td className="min-w-40">
              {document.kind ? labelOf(labels, "DocumentKind", document.kind) : none}
              {document.reader ? <span className={cn("block", SMALL)}>{document.reader}</span> : null}
            </Td>
            <Td>{banksOf(document) || none}</Td>
            <Td className="min-w-36">{accountsOf(document) || none}</Td>
            <Td className="whitespace-nowrap">{formatPeriod(document.period_start, document.period_end) || none}</Td>
            <Td className="min-w-48">
              <StatusBadges document={document} labels={labels} />
              {document.status === "processed" ? null : <Unread document={document} reparsing={reparsing} />}
            </Td>
            <Td>{sourcesOf(document, labels)}</Td>
            <Td className="whitespace-nowrap">{formatDate(document.added_at)}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">{formatSize(document.size)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
