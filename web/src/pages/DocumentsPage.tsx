// The Documents screen (F03's list, F02's upload): every kept document with its kind, reader, period, status and
// how it arrived, newest first; documents are added through a plan the user sees and confirms.

import { useDeferredValue, useState } from "react";

import { type DocumentFilter, useDocuments, useLabels } from "../api/queries";
import type { DocumentItem, Labels } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Badge, type Tone } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDate, formatPeriod } from "../lib/format";
import { UploadPanel } from "./UploadPanel";

const FILTERS: Array<{ value: DocumentFilter; label: string }> = [
  { value: "all", label: "Tümü" },
  { value: "unprocessed", label: "İşlenmeyenler ve okunamayanlar" },
];

const STATUS_TONES: Record<DocumentItem["status"], Tone> = {
  processed: "good",
  unprocessed: "neutral",
  unreadable: "critical",
};

export default function DocumentsPage() {
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const [search, setSearch] = useState("");
  const words = useDeferredValue(search).toLocaleLowerCase("tr-TR").split(/\s+/).filter(Boolean);
  const documents = useDocuments(filter);
  const labels = useLabels();
  const all = documents.data?.pages.flatMap((page) => page.items) ?? [];
  const shown = all.filter((d) => matches(d, words));
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Belgeler</h1>
      <UploadPanel />
      <div className="flex flex-wrap items-end gap-3">
        <fieldset className="flex flex-wrap gap-1">
          <legend className="sr-only">Hangi belgeler</legend>
          {FILTERS.map((f) => (
            <Button
              key={f.value}
              variant={filter === f.value ? "primary" : "secondary"}
              aria-pressed={filter === f.value}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </fieldset>
        <label className="flex flex-col gap-1 text-sm">
          <span>Ara</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ad, okuyucu ya da neden"
            className="min-h-11 rounded-md border border-zinc-300 bg-white px-3 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
      </div>
      {documents.isPending ? <Loading /> : null}
      {documents.isError ? <Failure error={documents.error} onRetry={() => void documents.refetch()} /> : null}
      {documents.isSuccess && all.length === 0 ? (
        <Empty title={filter === "all" ? "Arşivde henüz belge yok" : "İşlenmeyen ya da okunamayan belge yok"}>
          {filter === "all" ? "Belgeleri yukarıdan ekleyin ya da e-posta bağlantısını kurun." : null}
        </Empty>
      ) : null}
      {all.length > 0 && shown.length === 0 ? <Empty title="Bu aramayla belge yok" /> : null}
      {shown.length > 0 ? <DocumentTable documents={shown} labels={labels.data ?? {}} /> : null}
      {documents.hasNextPage ? (
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => void documents.fetchNextPage()}
          disabled={documents.isFetchingNextPage}
        >
          {documents.isFetchingNextPage ? "Yükleniyor…" : "Daha eski belgeler"}
        </Button>
      ) : null}
    </div>
  );
}

function matches(d: DocumentItem, words: string[]): boolean {
  const text = `${d.name} ${d.file} ${d.reader} ${d.reason}`.toLocaleLowerCase("tr-TR");
  return words.every((w) => text.includes(w));
}

function DocumentTable({ documents, labels }: { documents: DocumentItem[]; labels: Labels }) {
  const kinds = labels["DocumentKind"] ?? {};
  const statuses = labels["DocumentStatus"] ?? {};
  const sources = labels["SourceKind"] ?? {};
  return (
    <Table>
      <caption className="sr-only">Arşivdeki belgeler, en yenisi önce</caption>
      <thead>
        <tr>
          <Th>Belge</Th>
          <Th>Tür</Th>
          <Th>Dönem</Th>
          <Th>Durum</Th>
          <Th>Kaynak</Th>
          <Th>Geliş</Th>
        </tr>
      </thead>
      <tbody>
        {documents.map((d) => (
          <tr key={d.sha256}>
            <Td>
              <span className="font-medium">{d.name}</span>
              {d.name !== d.file ? (
                <span className="block text-xs text-zinc-500 dark:text-zinc-400">{d.file}</span>
              ) : null}
            </Td>
            <Td>
              {d.kind ? (kinds[d.kind] ?? d.kind) : "—"}
              {d.reader ? <span className="block text-xs text-zinc-500 dark:text-zinc-400">{d.reader}</span> : null}
            </Td>
            <Td>{formatPeriod(d.period_start, d.period_end) || "—"}</Td>
            <Td>
              <Badge tone={STATUS_TONES[d.status]}>{statuses[d.status] ?? d.status}</Badge>
              {d.verified === false ? (
                <span className="mt-1 block">
                  <Badge tone="warning">Doğrulanmadı</Badge>
                </span>
              ) : null}
              {d.reason ? <span className="mt-1 block text-xs text-zinc-600 dark:text-zinc-300">{d.reason}</span> : null}
            </Td>
            <Td>{d.sources.map((s) => sources[s] ?? s).join(", ")}</Td>
            <Td>{formatDate(d.added_at)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
