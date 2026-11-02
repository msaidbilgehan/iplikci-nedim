// The dashboard's smaller cards (F06): this month against the typical month, the payments due within a week, the open
// alerts and how much there is to see to. Each leads to its screen. The detailed view shows them; the simple view's
// home tells the same in pictures (Overview).

import { useTranslation } from "react-i18next";

import type { Dashboard, Labels } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { DueTable } from "../DueList";
import { PaceFigures } from "../Pace";
import { Detailed } from "../Preferences";
import { NextStep, ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { DashboardCard } from "./DashboardCard";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

export function MonthCard({ month }: { month: Dashboard["month"] }) {
  const { t } = useTranslation("dashboard");
  return (
    <DashboardCard title={t("month.title")} say={month.say} next={{ link: month.link, label: t("month.next") }}>
      <PaceFigures pace={month.pace} />
    </DashboardCard>
  );
}

export function DueCard({ due, labels }: { due: Dashboard["due"]; labels: Labels }) {
  const { t } = useTranslation("dashboard");
  return (
    <DashboardCard title={t("due.title")} say={due.say} next={{ link: due.link, label: t("due.next") }} quiet>
      {due.items.length > 0 ? (
        <>
          <p className={`mb-2 ${SMALL}`}>{t("due.until", { end: formatDay(due.end) })}</p>
          <DueTable items={due.items} caption={t("due.caption", { end: formatDay(due.end) })} labels={labels} />
          <p className="mt-2 text-sm font-medium">{t("due.total", { amount: formatMoney(due.total) })}</p>
        </>
      ) : (
        <p className="text-sm">{due.say}</p>
      )}
    </DashboardCard>
  );
}

export function AlertsCard({ alerts }: { alerts: Dashboard["alerts"] }) {
  const { t } = useTranslation("dashboard");
  const { t: tc } = useTranslation();
  return (
    <DashboardCard title={t("alerts.title")} say={alerts.say} next={{ link: alerts.link, label: t("alerts.next") }}>
      {alerts.items.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {alerts.items.map((alert, index) => (
            <li key={`${alert.kind}-${index}`} className="text-sm">
              <Status tone={alert.level === "critical" ? "critical" : "warning"}>
                <span className="font-medium">
                  {t(`alerts.level.${alert.level}`)}: {alert.title}
                </span>
              </Status>
              <p className="mt-0.5">{alert.text}</p>
              {alert.account || alert.count > 1 ? (
                <p className={SMALL}>
                  {[alert.account?.label ?? "", alert.count > 1 ? t("alerts.count", { count: alert.count }) : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
              <NextStep step={{ link: alert.link, label: tc(`open.${alert.link.screen}`) }} context={alert.title} />
            </li>
          ))}
        </ul>
      ) : (
        <Detailed>
          <p className="text-sm">{alerts.say}</p>
        </Detailed>
      )}
    </DashboardCard>
  );
}

export function TodoCard({ todo, labels }: { todo: Dashboard["todo"]; labels: Labels }) {
  const { t } = useTranslation("dashboard");
  return (
    <DashboardCard title={t("todo.title")} say={todo.say} next={{ link: todo.link, label: t("todo.next") }}>
      {todo.total > 0 ? (
        <>
          <p className="text-2xl font-semibold tabular-nums">{t("todo.total", { count: todo.total })}</p>
          <ul className="mt-2 flex flex-col gap-1 text-sm">
            {todo.kinds.map((kind) => (
              <li key={kind.kind} className="flex justify-between gap-3">
                <ScreenLink link={kind.link}>{labelOf(labels, "TodoKind", kind.kind)}</ScreenLink>
                <span className="tabular-nums">{kind.count}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <Detailed>
          <p className="text-sm">{todo.say}</p>
        </Detailed>
      )}
    </DashboardCard>
  );
}
