// The interface's notification box (F13): what the rules said, newest first, the unseen ones marked. "Tümünü
// okundu say" marks them seen up to the newest one shown, so one that arrives meanwhile stays unread.

import { useMarkNotificationsRead, useNotificationBox } from "../../api/queries";
import type { NotificationItem } from "../../api/types";
import { formatTime } from "../../lib/format";
import { cn } from "../../lib/cn";
import { Empty, Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { MUTED } from "./common";

export function NotificationBox() {
  const box = useNotificationBox();
  const mark = useMarkNotificationsRead();
  const items = box.data?.pages.flatMap((page) => page.items) ?? [];
  const unread = box.data?.pages[0]?.unread ?? 0;
  const newest = items[0];
  return (
    <Card
      title="Bildirim kutusu"
      action={
        <Button
          variant="secondary"
          disabled={unread === 0 || newest === undefined || mark.isPending}
          onClick={() => newest && mark.mutate(newest.id)}
        >
          {mark.isPending ? "İşaretleniyor…" : "Tümünü okundu say"}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        {box.isPending ? <Loading /> : null}
        {box.isError ? <Failure error={box.error} onRetry={() => void box.refetch()} /> : null}
        {box.isSuccess && items.length === 0 ? (
          <Empty title="Henüz bildirim yok">
            Kurallara uyan bir olay olunca bildirim burada görünür; açık kanallara da gönderilir.
          </Empty>
        ) : null}
        {items.length > 0 ? (
          <>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">
              {unread > 0 ? `${unread} okunmamış bildirim` : "Okunmamış bildirim yok"}
            </p>
            <ul aria-label="Bildirimler, en yenisi önce" className="flex flex-col gap-2">
              {items.map((item) => (
                <BoxItem key={item.id} item={item} />
              ))}
            </ul>
          </>
        ) : null}
        {mark.isError ? (
          <Alert tone="critical" title="Okundu sayılamadı" live>
            <p>{mark.error.message}</p>
          </Alert>
        ) : null}
        {box.hasNextPage ? (
          <Button
            variant="secondary"
            className="self-start"
            onClick={() => void box.fetchNextPage()}
            disabled={box.isFetchingNextPage}
          >
            {box.isFetchingNextPage ? "Yükleniyor…" : "Daha eski bildirimler"}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function BoxItem({ item }: { item: NotificationItem }) {
  return (
    <li
      className={cn(
        "flex flex-col gap-1 rounded-md border p-3 text-sm",
        item.read
          ? "border-zinc-200 dark:border-zinc-700"
          : "border-teal-600 bg-teal-50 dark:border-teal-500 dark:bg-teal-950",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          {item.title}
          {item.read ? null : <Badge tone="neutral">Yeni</Badge>}
        </p>
        <time dateTime={item.created_at} className={MUTED}>
          {formatTime(item.created_at)}
        </time>
      </div>
      <p className="whitespace-pre-line text-zinc-800 dark:text-zinc-100">{item.body}</p>
      <p className={MUTED}>Kural: {item.rule}</p>
    </li>
  );
}
