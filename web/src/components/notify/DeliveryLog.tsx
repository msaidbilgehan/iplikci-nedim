// The delivery history (F13): every notification on every channel as it was sent, kept back for a digest, retried or
// given up, with the error of its last attempt and what its event concerns. The names of the channels, statuses,
// levels and events come from /api/labels.

import { Link } from "react-router";

import { useLabels, useNotificationLog, useNotifySettings } from "../../api/queries";
import type { DeliveryStatus, Labels, NotificationItem } from "../../api/types";
import { formatMonth, formatTime } from "../../lib/format";
import { Empty, Failure, Loading } from "../QueryState";
import { Badge, type Tone } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Table, Td, Th } from "../ui/Table";
import { labelOf, LINK, MUTED } from "./common";

const STATUS_TONES: Record<DeliveryStatus, Tone> = {
  pending: "neutral",
  sent: "good",
  held: "neutral",
  digested: "good",
  failed: "critical",
};
const STATUSES: readonly DeliveryStatus[] = ["sent", "digested", "held", "pending", "failed"];
const TEST_KIND = "test"; // a test the user asked for: no event behind it
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

export function DeliveryLog() {
  const log = useNotificationLog();
  const labels = useLabels().data ?? {};
  const items = log.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Card title="Teslim kaydı">
      <div className="flex flex-col gap-3">
        <StatusCounts labels={labels} />
        {log.isPending ? <Loading /> : null}
        {log.isError ? <Failure error={log.error} onRetry={() => void log.refetch()} /> : null}
        {log.isSuccess && items.length === 0 ? (
          <Empty title="Henüz teslim kaydı yok">Gönderilen her bildirim kanalı ve durumuyla burada listelenir.</Empty>
        ) : null}
        {items.length > 0 ? <LogTable items={items} labels={labels} /> : null}
        {log.hasNextPage ? (
          <Button
            variant="secondary"
            className="self-start"
            onClick={() => void log.fetchNextPage()}
            disabled={log.isFetchingNextPage}
          >
            {log.isFetchingNextPage ? "Yükleniyor…" : "Daha eski kayıtlar"}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

/** How many notifications stand at each status, from the channels' settings. */
function StatusCounts({ labels }: { labels: Labels }) {
  const counts = useNotifySettings().data?.counts ?? {};
  const shown = STATUSES.filter((status) => (counts[status] ?? 0) > 0);
  if (shown.length === 0) {
    return null;
  }
  return (
    <p className="text-sm text-zinc-600 dark:text-zinc-300">
      {shown.map((status) => `${labelOf(labels, "DeliveryStatus", status)}: ${counts[status] ?? 0}`).join(" · ")}
    </p>
  );
}

function LogTable({ items, labels }: { items: NotificationItem[]; labels: Labels }) {
  return (
    <Table>
      <caption className="sr-only">Gönderilen bildirimler, en yenisi önce</caption>
      <thead>
        <tr>
          <Th>Zaman</Th>
          <Th>Kanal</Th>
          <Th>Durum</Th>
          <Th>Kural</Th>
          <Th>Bildirim</Th>
          <Th>İlgili</Th>
          <Th className="text-right">Başarısız deneme</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <Td className="whitespace-nowrap">
              {formatTime(item.created_at)}
              {item.sent_at && item.sent_at !== item.created_at ? (
                <span className={`block ${MUTED}`}>gönderim {formatTime(item.sent_at)}</span>
              ) : null}
            </Td>
            <Td>
              {labelOf(labels, "Channel", item.channel)}
              <span className={`block ${MUTED}`}>{labelOf(labels, "DetailLevel", item.detail)}</span>
            </Td>
            <Td>
              <Badge tone={STATUS_TONES[item.status]}>{labelOf(labels, "DeliveryStatus", item.status)}</Badge>
              {item.error ? (
                <span className="mt-1 block text-xs text-red-800 dark:text-red-200">{item.error}</span>
              ) : null}
            </Td>
            <Td>
              {item.rule}
              <span className={`block ${MUTED}`}>
                {item.kind === TEST_KIND ? "Deneme" : labelOf(labels, "EventKind", item.kind)}
              </span>
            </Td>
            <Td>
              <span className="font-medium">{item.title}</span>
              <span className={`block ${MUTED}`}>{item.body}</span>
            </Td>
            <Td>
              <Concerns item={item} />
            </Td>
            <Td className="text-right tabular-nums">{item.attempts || "—"}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/**
 * What the notification's event concerns: a document or a row (no screen of its own yet, so its short code), the
 * screen that shows a bill, a payment ahead or a series, or the month; nothing for an event standing for many.
 */
function Concerns({ item }: { item: NotificationItem }) {
  const { kind, target } = item;
  if (!target) {
    return "—";
  }
  if (kind.startsWith("document.")) {
    return <Code label="Belge" value={target} />;
  }
  if (kind.startsWith("transaction.") || ROW_KINDS.has(kind)) {
    return <Code label="İşlem" value={target} />;
  }
  if (kind.startsWith("month.")) {
    return <span className="whitespace-nowrap">{formatMonth(target)}</span>;
  }
  if (kind.startsWith("invoice.")) {
    return <ScreenLink to="/faturalar" name="Faturalar" />;
  }
  if (CALENDAR_KINDS.has(kind)) {
    return <ScreenLink to="/takvim" name="Takvim" />;
  }
  return SERIES_KINDS.has(kind) ? <ScreenLink to="/abonelikler" name="Abonelikler" /> : "—";
}

function Code({ label, value }: { label: string; value: string }) {
  return (
    <span className="whitespace-nowrap">
      {label} <code title={value}>{value.slice(0, SHORT)}</code>
    </span>
  );
}

function ScreenLink({ to, name }: { to: string; name: string }) {
  return (
    <Link to={to} className={`whitespace-nowrap ${LINK}`}>
      {name} ekranı
    </Link>
  );
}
