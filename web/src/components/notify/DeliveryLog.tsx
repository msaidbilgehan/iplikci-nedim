// The delivery history (F13): every notification on every channel as it was sent, kept back for a digest, retried or
// given up, with the error of its last attempt and what its event concerns. The simple view says how many went and
// lists each with its channel and status; the detailed view's table adds the rule, the level of detail, the attempts
// and what the event concerns. The names of the channels, statuses, levels and events come from /api/labels.

import { useTranslation } from "react-i18next";

import { useLabels, useNotificationLog, useNotifySettings } from "../../api/queries";
import type { DeliveryStatus, Labels, NotificationItem } from "../../api/types";
import { formatTime } from "../../lib/format";
import { Detailed, Simple } from "../Preferences";
import { Empty, Failure, Loading } from "../QueryState";
import { Badge, type Tone } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { labelOf, MUTED } from "./common";
import { Concerns } from "./Concerns";

const STATUS_TONES: Record<DeliveryStatus, Tone> = {
  pending: "neutral",
  sent: "good",
  held: "neutral",
  digested: "good",
  failed: "critical",
};
const STATUSES: readonly DeliveryStatus[] = ["sent", "digested", "held", "pending", "failed"];
const TEST_KIND = "test"; // a test the user asked for: no event behind it
const ERROR = "text-xs text-red-800 dark:text-red-200";

export function DeliveryLog() {
  const { t } = useTranslation("notifications");
  const log = useNotificationLog();
  const labels = useLabels().data ?? {};
  const counts = useNotifySettings().data?.counts ?? {};
  const items = log.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Card title={t("log.title")}>
      {items.length > 0 ? <LogSay counts={counts} /> : null}
      <div className="flex flex-col gap-3">
        <StatusCounts counts={counts} labels={labels} />
        {log.isPending ? <Loading /> : null}
        {log.isError ? <Failure error={log.error} onRetry={() => void log.refetch()} /> : null}
        {log.isSuccess && items.length === 0 ? <Empty title={t("log.empty")}>{t("log.emptyText")}</Empty> : null}
        {items.length > 0 ? (
          <>
            <Simple>
              <LogList items={items} labels={labels} />
            </Simple>
            <Detailed>
              <LogTable items={items} labels={labels} />
            </Detailed>
          </>
        ) : null}
        {log.hasNextPage ? (
          <Button
            variant="secondary"
            className="self-start"
            onClick={() => void log.fetchNextPage()}
            disabled={log.isFetchingNextPage}
          >
            {log.isFetchingNextPage ? t("log.loadingOlder") : t("log.older")}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

/** How many went and how many could not; those kept for a digest besides. */
function LogSay({ counts }: { counts: Readonly<Record<string, number>> }) {
  const { t } = useTranslation("notifications");
  const sent = (counts["sent"] ?? 0) + (counts["digested"] ?? 0);
  const held = counts["held"] ?? 0;
  return (
    <Say>
      {t("log.say", { sent, failed: counts["failed"] ?? 0 })}
      {held > 0 ? ` ${t("log.sayHeld", { count: held })}` : ""}
    </Say>
  );
}

/** How many notifications stand at each status, from the channels' settings. */
function StatusCounts({ counts, labels }: { counts: Readonly<Record<string, number>>; labels: Labels }) {
  const { t } = useTranslation("notifications");
  const shown = STATUSES.filter((status) => (counts[status] ?? 0) > 0);
  if (shown.length === 0) {
    return null;
  }
  return (
    <p className="text-sm text-zinc-600 dark:text-zinc-300">
      {shown
        .map((status) => t("log.count", { status: labelOf(labels, "DeliveryStatus", status), count: counts[status] }))
        .join(" · ")}
    </p>
  );
}

function StatusBadge({ item, labels }: { item: NotificationItem; labels: Labels }) {
  return <Badge tone={STATUS_TONES[item.status]}>{labelOf(labels, "DeliveryStatus", item.status)}</Badge>;
}

/** Each notification with its channel, its status and when it was made; a failed one with why. */
function LogList({ items, labels }: { items: NotificationItem[]; labels: Labels }) {
  const { t } = useTranslation("notifications");
  return (
    <ul aria-label={t("log.list")} className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
      {items.map((item) => (
        <li key={item.id} className="flex flex-col gap-1 py-2 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{item.title}</span>
            <StatusBadge item={item} labels={labels} />
          </div>
          <span className={MUTED}>
            {labelOf(labels, "Channel", item.channel)} · {formatTime(item.created_at)}
          </span>
          {item.error ? <span className={ERROR}>{item.error}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function LogTable({ items, labels }: { items: NotificationItem[]; labels: Labels }) {
  const { t } = useTranslation("notifications");
  return (
    <Table>
      <caption className="sr-only">{t("log.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("log.time")}</Th>
          <Th>{t("log.channel")}</Th>
          <Th>{t("log.status")}</Th>
          <Th>{t("log.rule")}</Th>
          <Th>{t("log.notification")}</Th>
          <Th>{t("log.concerns")}</Th>
          <Th className="text-right">{t("log.attempts")}</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <Td className="whitespace-nowrap">
              {formatTime(item.created_at)}
              {item.sent_at && item.sent_at !== item.created_at ? (
                <span className={`block ${MUTED}`}>{t("log.sentAt", { time: formatTime(item.sent_at) })}</span>
              ) : null}
            </Td>
            <Td>
              {labelOf(labels, "Channel", item.channel)}
              <span className={`block ${MUTED}`}>{labelOf(labels, "DetailLevel", item.detail)}</span>
            </Td>
            <Td>
              <StatusBadge item={item} labels={labels} />
              {item.error ? <span className={`mt-1 block ${ERROR}`}>{item.error}</span> : null}
            </Td>
            <Td>
              {item.rule}
              <span className={`block ${MUTED}`}>
                {item.kind === TEST_KIND ? t("test") : labelOf(labels, "EventKind", item.kind)}
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
