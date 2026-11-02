// The interface's notification box (F13): what the rules said, newest first, the unseen ones marked. "Tümünü
// okundu say" marks them seen up to the newest one shown, so one that arrives meanwhile stays unread. The simple view
// says in a sentence what is new; the detailed view adds each notification's event and what it concerns.

import { useTranslation } from "react-i18next";

import { useLabels, useMarkNotificationsRead, useNotificationBox } from "../../api/queries";
import type { Labels, NotificationItem } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatTime } from "../../lib/format";
import { Detailed } from "../Preferences";
import { Empty, Failure, Loading } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { labelOf, MUTED } from "./common";
import { Concerns } from "./Concerns";

const TEST_KIND = "test"; // a test the user asked for: no event behind it

export function NotificationBox() {
  const { t } = useTranslation("notifications");
  const box = useNotificationBox();
  const mark = useMarkNotificationsRead();
  const labels = useLabels().data ?? {};
  const items = box.data?.pages.flatMap((page) => page.items) ?? [];
  const unread = box.data?.pages[0]?.unread ?? 0;
  const newest = items[0];
  const newestUnseen = items.find((item) => !item.read);
  return (
    <Card
      title={t("box.title")}
      action={
        <Button
          variant="secondary"
          disabled={unread === 0 || newest === undefined || mark.isPending}
          onClick={() => newest && mark.mutate(newest.id)}
        >
          {mark.isPending ? t("box.marking") : t("box.markAll")}
        </Button>
      }
    >
      {newest ? (
        <Say>
          {unread > 0 && newestUnseen
            ? t("box.say", { count: unread, title: newestUnseen.title })
            : t("box.sayAllSeen")}
        </Say>
      ) : null}
      <div className="flex flex-col gap-3">
        {box.isPending ? <Loading /> : null}
        {box.isError ? <Failure error={box.error} onRetry={() => void box.refetch()} /> : null}
        {box.isSuccess && items.length === 0 ? <Empty title={t("box.empty")}>{t("box.emptyText")}</Empty> : null}
        {items.length > 0 ? (
          <>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">
              {unread > 0 ? t("box.unread", { count: unread }) : t("box.noneUnread")}
            </p>
            <ul aria-label={t("box.list")} className="flex flex-col gap-2">
              {items.map((item) => (
                <BoxItem key={item.id} item={item} labels={labels} />
              ))}
            </ul>
          </>
        ) : null}
        {mark.isError ? (
          <Alert tone="critical" title={t("box.markFailed")} live>
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
            {box.isFetchingNextPage ? t("box.loadingOlder") : t("box.older")}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function BoxItem({ item, labels }: { item: NotificationItem; labels: Labels }) {
  const { t } = useTranslation("notifications");
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
          {item.read ? null : <Badge tone="neutral">{t("box.new")}</Badge>}
        </p>
        <time dateTime={item.created_at} className={MUTED}>
          {formatTime(item.created_at)}
        </time>
      </div>
      <p className="whitespace-pre-line text-zinc-800 dark:text-zinc-100">{item.body}</p>
      <p className={MUTED}>{t("box.rule", { rule: item.rule })}</p>
      <Detailed>
        <p className={cn(MUTED, "flex flex-wrap items-center gap-x-3 gap-y-1")}>
          <span>
            {t("box.event", { event: item.kind === TEST_KIND ? t("test") : labelOf(labels, "EventKind", item.kind) })}
          </span>
          {item.target ? <Concerns item={item} /> : null}
        </p>
      </Detailed>
    </li>
  );
}
