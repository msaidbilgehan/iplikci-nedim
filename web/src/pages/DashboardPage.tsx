// The Pano screen (F06), the home page: the net worth, this month against the typical month, the payments due within a
// week, the open alerts, the last seven months' closing, how fresh each account's documents are and how much there is
// to see to. Every card says in one sentence what it shows (the service's `say`) and leads to its screen (`link`).

import { useTranslation } from "react-i18next";

import { useDashboard, useLabels } from "../api/queries";
import type { Dashboard, Labels } from "../api/types";
import { AlertsCard, DueCard, MonthCard, TodoCard } from "../components/dashboard/Cards";
import { ClosingCard } from "../components/dashboard/ClosingCard";
import { FreshnessCard } from "../components/dashboard/FreshnessCard";
import { NetWorthCard } from "../components/dashboard/NetWorthCard";
import { useView } from "../components/Preferences";
import { Empty, Failure, Loading } from "../components/QueryState";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep } from "../components/ui/Say";
import { formatDay } from "../lib/format";

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;

export default function DashboardPage() {
  const { t } = useTranslation("dashboard");
  const dashboard = useDashboard();
  const labels = useLabels().data ?? {};
  const found = dashboard.data;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("title")}
        description={found ? t("description", { today: formatDay(found.today), asOf: formatDay(found.as_of) }) : null}
      />
      {dashboard.isPending ? <Loading /> : null}
      {dashboard.isError ? <Failure error={dashboard.error} onRetry={() => void dashboard.refetch()} /> : null}
      {found ? <Cards found={found} labels={labels} /> : null}
    </div>
  );
}

function Cards({ found, labels }: { found: Dashboard; labels: Labels }) {
  const { t } = useTranslation("dashboard");
  const { view } = useView();
  // Side by side the cards read at a glance. They differ in height, so they stand in columns rather than a grid's
  // rows: each card goes under the one before without a gap, and the eye reads each column down, in the order a screen
  // reader reads them. The detailed view's tables need the screen's width: one card under the other.
  const grid =
    view === "simple"
      ? "gap-4 *:mb-4 *:break-inside-avoid md:columns-2 xl:columns-3"
      : "grid items-start gap-4";
  if (found.freshness.accounts.length === 0 && found.net_worth.parts.length === 0) {
    // No document yet: what could still ask for attention (the mail, a backup) and the first step.
    return (
      <>
        <Empty title={t("empty")}>
          <p>{t("emptyText")}</p>
          <NextStep step={{ link: DOCUMENTS, label: t("emptyNext") }} className="mt-2" />
        </Empty>
        <div className={grid}>
          <AlertsCard alerts={found.alerts} />
          <TodoCard todo={found.todo} labels={labels} />
        </div>
      </>
    );
  }
  return (
    <div className={grid}>
      <NetWorthCard worth={found.net_worth} />
      <MonthCard month={found.month} />
      <DueCard due={found.due} today={found.today} labels={labels} />
      <AlertsCard alerts={found.alerts} />
      <ClosingCard
        months={found.closing.months}
        say={found.closing.say}
        next={found.closing.link}
        labels={labels}
      />
      <FreshnessCard
        accounts={found.freshness.accounts}
        say={found.freshness.say}
        next={found.freshness.link}
        labels={labels}
      />
      <TodoCard todo={found.todo} labels={labels} />
    </div>
  );
}
