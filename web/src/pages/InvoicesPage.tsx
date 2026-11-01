// The Bills screen (F14): the bills and receipts non-bank senders mailed, grouped by what the bank's rows say of them.
// A matched one shows the bank row that paid it; a pending one waits for its days or for the bank's documents to reach
// them; an unmatched one is information only, with what may explain it. None of them changes a total: the bank row
// is what counts. Every number comes from /api/invoices; the names of the kinds come from /api/labels.

import { Link } from "react-router";

import { useInvoices, useLabels } from "../api/queries";
import type { InvoiceItem, Invoices } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDay, formatMoney, formatPeriod } from "../lib/format";

const MUTED = "block text-xs text-zinc-600 dark:text-zinc-300";
const LINK =
  "rounded font-medium text-teal-800 underline focus-visible:outline-2 focus-visible:outline-teal-600 " +
  "dark:text-teal-200";
const INFO_ONLY = "bilgi — toplamlara girmez";

interface Group {
  status: InvoiceItem["status"];
  title: string;
  about: string;
  outcome: string; // the heading of the column that says what the bank's rows say
  caption: string;
}

const GROUPS: readonly Group[] = [
  {
    status: "pending",
    title: "Bekliyor",
    about:
      "Ödeme günü gelmedi ya da banka belgeleri bu günlere henüz ulaşmadı; onu ödeyen satır gelince eşleşir. Son " +
      "ödeme günü gelmemiş faturalar takvimde de görünür.",
    outcome: "Banka satırının arandığı günler",
    caption: "Bekleyen faturalar ve makbuzlar, ödeme gününe göre",
  },
  {
    status: "unmatched",
    title: "Eşleşmedi",
    about:
      "Aranan günler geçti ve banka belgeleri o günleri kapsıyor, ama onu ödeyen satır yok. Bunlar yalnızca " +
      "bilgidir; hiçbir toplamı değiştirmez.",
    outcome: "Olası nedenler",
    caption: "Eşleşmeyen faturalar ve makbuzlar, en yenisi önce",
  },
  {
    status: "matched",
    title: "Eşleşti",
    about: "Her biri onu ödeyen banka satırıyla birlikte; harcama o satırla sayılır.",
    outcome: "Ödeyen banka satırı",
    caption: "Eşleşen faturalar ve makbuzlar, en yenisi önce",
  },
];

export default function InvoicesPage() {
  const invoices = useInvoices();
  const labels = useLabels();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Faturalar</h1>
      <p className="max-w-3xl text-sm text-zinc-700 dark:text-zinc-300">
        Banka dışı göndericilerin e-postayla gelen faturaları ve makbuzları. Hiçbiri toplamlara girmez: harcama, onu
        ödeyen banka satırıyla sayılır.
      </p>
      {invoices.isPending ? <Loading /> : null}
      {invoices.isError ? <Failure error={invoices.error} onRetry={() => void invoices.refetch()} /> : null}
      {invoices.data ? <InvoiceGroups found={invoices.data} kinds={labels.data?.["InvoiceKind"] ?? {}} /> : null}
    </div>
  );
}

function InvoiceGroups({ found, kinds }: { found: Invoices; kinds: Record<string, string> }) {
  if (found.items.length === 0) {
    return (
      <Empty title="Henüz fatura ya da makbuz yok">
        Banka dışı göndericileri (telefon, internet, enerji, abonelik){" "}
        <Link to="/sistem" className={LINK}>
          Sistem
        </Link>{" "}
        sayfasından ekleyin; e-postayla gelen faturalar ve makbuzlar burada, onları ödeyen banka satırlarıyla görünür.
      </Empty>
    );
  }
  const { pending, unmatched, matched } = found.counts;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-zinc-600 dark:text-zinc-300">
        {found.items.length} belge: {pending} bekliyor, {unmatched} eşleşmedi, {matched} eşleşti.
      </p>
      {GROUPS.map((group) => {
        const items = found.items.filter((item) => item.status === group.status);
        if (items.length === 0) {
          return null;
        }
        return (
          <Card
            key={group.status}
            title={group.title}
            action={group.status === "unmatched" ? <Badge tone="neutral">Bilgi — toplamlara girmez</Badge> : undefined}
          >
            <div className="flex flex-col gap-2">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">{group.about}</p>
              <InvoiceTable items={items} group={group} kinds={kinds} />
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function InvoiceTable({ items, group, kinds }: { items: InvoiceItem[]; group: Group; kinds: Record<string, string> }) {
  return (
    <Table>
      <caption className="sr-only">{group.caption}</caption>
      <thead>
        <tr>
          <Th>Satıcı</Th>
          <Th>Tür</Th>
          <Th>Tarih</Th>
          <Th>Son ödeme</Th>
          <Th className="text-right">Tutar</Th>
          <Th>{group.outcome}</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.key}>
            <Td>
              <span className="font-medium">{item.seller}</span>
              {item.number ? <span className={MUTED}>No: {item.number}</span> : null}
              <span className={MUTED}>{item.document}</span>
              <Lines item={item} />
            </Td>
            <Td>{kinds[item.kind] ?? item.kind}</Td>
            <Td className="whitespace-nowrap">{formatDay(item.issued)}</Td>
            <Td className="whitespace-nowrap">{item.due ? formatDay(item.due) : "—"}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">
              {formatMoney(item.total)}
              {item.status === "unmatched" ? <span className={MUTED}>{INFO_ONLY}</span> : null}
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
  if (item.row) {
    return (
      <>
        <span className="whitespace-nowrap tabular-nums">
          {formatDay(item.row.day)} · {formatMoney(item.row.amount)}
        </span>
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
  if (item.lines.length === 0) {
    return null;
  }
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-teal-600">
        {item.lines.length} kalem
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
