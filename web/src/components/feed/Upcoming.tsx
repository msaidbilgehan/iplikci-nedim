// The Akış screen's "Yaklaşanlar" (F05): the payments and income the calendar expects in the next 14 days, by day, with
// a sentence on how many there are and which comes first. They are estimates, as the calendar's are.

import type { UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { Labels, Now } from "../../api/types";
import { addDays, daysBetween } from "../../lib/format";
import { DueList, DueTable } from "../DueList";
import { Detailed, Simple } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";

const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

/** How a sentence names a day ahead: "bugün", "yarın", or the day with its locative (feed.json, upcoming). */
export function whenKey(day: string, today: string): "today" | "tomorrow" | "on" {
  if (day === today) {
    return "today";
  }
  return day === addDays(today, 1) ? "tomorrow" : "on";
}

export function UpcomingCard({ now, labels }: { now: UseQueryResult<Now>; labels: Labels }) {
  const { t } = useTranslation("feed");
  return (
    <Card title={t("upcoming.title")}>
      {now.isPending ? <Loading /> : null}
      {now.isError ? <Failure error={now.error} onRetry={() => void now.refetch()} /> : null}
      {now.data ? <Upcoming now={now.data} labels={labels} /> : null}
    </Card>
  );
}

function Upcoming({ now, labels }: { now: Now; labels: Labels }) {
  const { t } = useTranslation("feed");
  const days = daysBetween(now.today, now.end) + 1;
  const items = now.upcoming;
  const first = items[0];
  if (!first) {
    return <p className="text-sm">{t("upcoming.empty", { days })}</p>;
  }
  const payments = items.filter((item) => item.direction === "out").length;
  const incomes = items.length - payments;
  const when = t(`upcoming.${whenKey(first.day, now.today)}`, { day: first.day });
  const values = { days, payments, incomes, when, title: first.title };
  const say =
    payments && incomes
      ? t("upcoming.sayBoth", values)
      : payments
        ? t("upcoming.sayPayments", values)
        : t("upcoming.sayIncomes", values);
  return (
    <>
      <Say next={{ link: CALENDAR, label: t("upcoming.next") }}>{say}</Say>
      <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-300">{t("upcoming.estimate")}</p>
      <Simple>
        <DueList items={items} today={now.today} labels={labels} />
      </Simple>
      <Detailed>
        <DueTable items={items} caption={t("upcoming.caption", { days })} labels={labels} />
      </Detailed>
    </>
  );
}
