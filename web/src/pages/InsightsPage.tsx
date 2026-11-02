// The Değerlendirme screen (F10), the MVP report's cards in the interface: the period presets and the İşlemler screen's
// filters, kept in the address in the API's names; the summary tiles and what the spending leaves out; the
// interpretation (highlights, steps, budget); the net worth, the months' closing and how the debts moved; the months by
// group and by necessity with the habits; income and spending; the next three months; the categories and merchants; how
// the spending moved and what is worth a look; the regular payments; the rows as a list and as CSV; and where the data
// comes from. The cards the filters narrow come from /api/spending, the interpretation from /api/insights, which no
// filter changes; each card says which it is, with its window and numbers.

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { ApiError } from "../api/client";
import {
  useAccounts,
  useCategoryRules,
  useCoverage,
  useDashboard,
  useExports,
  useInsights,
  useLabels,
  useSpending,
  useSubscriptions,
  useSystem,
} from "../api/queries";
import type { Dashboard, Insights, Labels, Spending } from "../api/types";
import { ClosingCard } from "../components/dashboard/ClosingCard";
import { NetWorthCard } from "../components/dashboard/NetWorthCard";
import { accountOptions } from "../components/filters";
import { TrendCard, UnusualCard } from "../components/insights/Changes";
import { DebtCard } from "../components/insights/Debt";
import { FlowCard } from "../components/insights/Flow";
import { ForecastCard } from "../components/insights/Forecast";
import { Interpretation } from "../components/insights/Interpretation";
import { MonthlyCard, NecessityCard } from "../components/insights/Months";
import { Presets } from "../components/insights/Presets";
import { spendingQuery, withKind, withRange } from "../components/insights/query";
import { CategoriesCard, MerchantsCard } from "../components/insights/Rankings";
import { RegularCard } from "../components/insights/Regular";
import { RowsCard } from "../components/insights/Rows";
import { SourcesCard } from "../components/insights/Sources";
import { LeftOut, Tiles } from "../components/insights/Tiles";
import { useView } from "../components/Preferences";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Filters } from "../components/transactions/Filters";
import { choosesNone, filtered, isFiltered, MANY, ONE } from "../components/transactions/query";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep } from "../components/ui/Say";
import { cn } from "../lib/cn";

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;
const LINK_BUTTON = cn(
  "inline-flex min-h-11 items-center rounded-md border px-3 text-sm font-medium",
  "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

/** Two cards side by side in the simple view; in the detailed one their tables need the screen's width, as on Pano. */
function usePair(from: "lg" | "xl" = "lg"): string {
  const { view } = useView();
  const side = from === "lg" ? "lg:grid-cols-2" : "xl:grid-cols-2";
  return cn("grid grid-cols-1 items-start gap-6", view === "simple" && side);
}

/** A filter the service refused (a day it cannot read, a code it does not know): the request, not the service. */
function isRefused(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 400 || error.status === 422);
}

export default function InsightsPage() {
  const { t } = useTranslation("insights");
  const { t: tt } = useTranslation("transactions");
  const [params, setParams] = useSearchParams();
  const labels = useLabels().data ?? {};
  const accounts = useAccounts();
  const rules = useCategoryRules();
  const none = choosesNone(params);
  const spending = useSpending(spendingQuery(params), !none);
  const insights = useInsights();
  const dashboard = useDashboard();
  const subscriptions = useSubscriptions();
  const system = useSystem();
  const coverage = useCoverage();
  const change = (next: URLSearchParams, replace = false) => setParams(next, replace ? { replace: true } : undefined);
  const reset = () =>
    setParams((was) =>
      filtered(was, (next) => {
        for (const name of [...MANY, ...ONE]) {
          next.delete(name);
        }
      }),
    );
  const resetButton = (
    <Button variant="secondary" className="mt-2" onClick={reset}>
      {t("reset")}
    </Button>
  );
  const data = none ? undefined : spending.data;
  const isBlank = data?.period === null && !isFiltered(params);
  const found = data?.period && data.tiles.count > 0 ? data : undefined;
  const pair = usePair();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} actions={<Exports />} />
      <div className="flex flex-col gap-3">
        {data?.period ? (
          <Presets period={data.period} params={params} onChoose={(range) => change(withRange(params, range))} />
        ) : null}
        <Filters
          params={params}
          onChange={change}
          labels={labels}
          accounts={accountOptions(accounts.data, labels, tt("filters.closed"))}
          rules={rules.data}
        />
      </div>
      {none ? <Empty title={t("noneChosen")}>{resetButton}</Empty> : null}
      {!none && spending.isPending ? <Loading /> : null}
      {!none && spending.isError ? (
        isRefused(spending.error) ? (
          <Alert tone="warning" title={t("refused")}>
            <p>{spending.error.message}</p>
            {resetButton}
          </Alert>
        ) : (
          <Failure error={spending.error} onRetry={() => void spending.refetch()} />
        )
      ) : null}
      {isBlank ? (
        <>
          <Empty title={t("emptyArchive")}>
            <p>{t("emptyArchiveText")}</p>
            <NextStep step={{ link: DOCUMENTS, label: t("emptyArchiveNext") }} className="mt-2" />
          </Empty>
          <SourcesCard dashboard={dashboard} system={system} coverage={coverage} labels={labels} />
        </>
      ) : (
        <>
          {data && !found && !isBlank ? <Empty title={t("empty")}>{resetButton}</Empty> : null}
          <div
            aria-busy={spending.isPlaceholderData}
            className={cn("flex flex-col gap-6", spending.isPlaceholderData && "opacity-60")}
          >
            {found ? (
              <div className="flex flex-col gap-3">
                <Tiles found={found} params={params} />
                <LeftOut params={params} labels={labels} onAdd={(kind) => change(withKind(params, kind))} />
              </div>
            ) : null}
            <InsightsPart query={insights} title={t("interpretation.title")}>
              {(ins) => <Interpretation found={ins} labels={labels} />}
            </InsightsPart>
            <DashboardPart query={dashboard} labels={labels} />
            {insights.data ? <DebtCard insights={insights.data} /> : null}
            {found ? <SpendingCards found={found} insights={insights.data} labels={labels} params={params} /> : null}
            {insights.data ? (
              <div className={pair}>
                <TrendCard trend={insights.data.trend} />
                <UnusualCard found={insights.data.unusual} labels={labels} />
              </div>
            ) : null}
            {subscriptions.data ? (
              <RegularCard found={subscriptions.data} />
            ) : (
              <Card title={t("regular.title")}>
                {subscriptions.isError ? (
                  <Failure error={subscriptions.error} onRetry={() => void subscriptions.refetch()} />
                ) : (
                  <Loading />
                )}
              </Card>
            )}
            {found ? <RowsCard found={found} params={params} /> : null}
            <SourcesCard dashboard={dashboard} system={system} coverage={coverage} labels={labels} />
          </div>
        </>
      )}
    </div>
  );
}

interface SpendingCardsProps {
  found: Spending;
  insights: Insights | undefined;
  labels: Labels;
  params: URLSearchParams;
}

/** The cards the filters narrow, in the MVP report's order. */
function SpendingCards({ found, insights, labels, params }: SpendingCardsProps) {
  const [, setParams] = useSearchParams();
  const pair = usePair("xl");
  const chooseLevel = (level: string | null) =>
    setParams(
      filtered(params, (next) => {
        next.delete("necessity");
        if (level) {
          next.append("necessity", level);
        }
      }),
    );
  return (
    <>
      <MonthlyCard found={found} />
      <NecessityCard
        found={found}
        insights={insights}
        labels={labels}
        chosen={params.getAll("necessity")}
        onChoose={chooseLevel}
      />
      <FlowCard found={found} insights={insights} labels={labels} />
      <ForecastCard found={found.forecast} labels={labels} />
      <div className={pair}>
        <CategoriesCard found={found} />
        <MerchantsCard found={found} />
      </div>
    </>
  );
}

interface InsightsPartProps {
  query: ReturnType<typeof useInsights>;
  title: string;
  children: (found: Insights) => ReactNode;
}

/** A card of the interpretation, or its place while it loads or when it cannot be read. */
function InsightsPart({ query, title, children }: InsightsPartProps) {
  if (query.data) {
    return children(query.data);
  }
  return (
    <Card title={title}>
      {query.isError ? <Failure error={query.error} onRetry={() => void query.refetch()} /> : <Loading />}
    </Card>
  );
}

/** The net worth and the months' closing, as the dashboard has them: they are about today, not the filters. */
function DashboardPart({ query, labels }: { query: ReturnType<typeof useDashboard>; labels: Labels }) {
  const { t } = useTranslation("dashboard");
  const pair = usePair();
  const found: Dashboard | undefined = query.data;
  if (!found) {
    return (
      <Card title={t("netWorth.title")}>
        {query.isError ? <Failure error={query.error} onRetry={() => void query.refetch()} /> : <Loading />}
      </Card>
    );
  }
  return (
    <div className={pair}>
      <NetWorthCard worth={found.net_worth} />
      <ClosingCard months={found.closing.months} say={found.closing.say} next={found.closing.link} labels={labels} />
    </div>
  );
}

/** The report and the Excel file the last analysis wrote, when it wrote them; neither follows the filters. */
function Exports() {
  const { t } = useTranslation("insights");
  const exports = useExports();
  const kinds = new Set((exports.data ?? []).map((item) => item.kind));
  return (
    <>
      {kinds.has("report") ? (
        <a href="/api/exports/report" download aria-label={t("exports.reportOf")} className={LINK_BUTTON}>
          {t("exports.report")}
        </a>
      ) : null}
      {kinds.has("xlsx") ? (
        <a href="/api/exports/xlsx" download aria-label={t("exports.excelOf")} className={LINK_BUTTON}>
          {t("exports.excel")}
        </a>
      ) : null}
    </>
  );
}
