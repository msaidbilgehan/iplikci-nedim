// A month's page (F11) at /ay-sonu/:ay: its status and the closing in a sentence, each account's closing and what it
// waits for, the totals against the month before and the typical month (closed months only), the last twelve months'
// spending, where the money went, the regular payments paid and expected, the big purchases, the provisional rows and
// the receipts no statement shows. A row opens its detail at the side (?satir=), and from there its document; the
// month's script-free page is among the months' pages to download. A month to come has no page yet.

import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { useLabels, useMonthEnd, useMonthEnds } from "../api/queries";
import type { Labels, MonthEndDetail, MonthEndList } from "../api/types";
import { AccountsCard } from "../components/monthEnd/AccountsCard";
import { ExportLink, isMonth, MonthStatusMark } from "../components/monthEnd/parts";
import { RegularCard } from "../components/monthEnd/RegularCard";
import { RowsCard, useBigSay } from "../components/monthEnd/RowsCard";
import { SpendingCard } from "../components/monthEnd/SpendingCard";
import { TotalsCard } from "../components/monthEnd/TotalsCard";
import { TrendCard } from "../components/monthEnd/TrendCard";
import { useView } from "../components/Preferences";
import { Empty, Failure, Loading } from "../components/QueryState";
import { ROW, withRow } from "../components/transactions/query";
import { RowPanel } from "../components/transactions/RowPanel";
import { Card } from "../components/ui/Card";
import { ArrowLeftIcon, ArrowRightIcon } from "../components/ui/Icons";
import { LinkButton } from "../components/ui/LinkButton";
import { PageHeader } from "../components/ui/PageHeader";
import { cn } from "../lib/cn";
import { formatMonth } from "../lib/format";

const BACK = cn(
  "inline-flex min-h-8 items-center gap-1 self-start rounded text-sm font-medium underline underline-offset-2",
  "text-teal-800 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export default function MonthPage() {
  const { t } = useTranslation("monthEnd");
  const { ay = "" } = useParams();
  const valid = isMonth(ay);
  const list = useMonthEnds();
  const detail = useMonthEnd(ay, valid);
  const labels = useLabels().data ?? {};
  const today = list.data?.today.slice(0, 7);
  const future = valid && today !== undefined && ay > today;
  const found = detail.data;
  const shown = found && !future && !list.isPending ? found : undefined;
  return (
    <div className="flex flex-col gap-6">
      <Link to="/ay-sonu" className={BACK}>
        <ArrowLeftIcon className="size-4" />
        {t("page.back")}
      </Link>
      <PageHeader
        title={valid ? formatMonth(ay) : t("page.title")}
        description={
          shown ? (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <MonthStatusMark status={shown.month.status} labels={labels} />
              <span>{shown.month.summary}</span>
            </span>
          ) : null
        }
        actions={shown ? <Neighbours detail={shown} today={today} /> : null}
      />
      {valid ? null : (
        <Empty title={t("page.notMonth")}>
          <p>{t("page.notMonthText")}</p>
          <MonthsLink />
        </Empty>
      )}
      {future ? (
        <Empty title={t("page.future", { month: formatMonth(ay) })}>
          <p>{t("page.futureText")}</p>
          <MonthsLink />
        </Empty>
      ) : null}
      {valid && !future && (detail.isPending || list.isPending) ? <Loading /> : null}
      {detail.isError ? <Failure error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {shown ? <Sections detail={shown} list={list.data} labels={labels} /> : null}
    </div>
  );
}

const MONTHS_LINK = cn(
  "mt-2 inline-block rounded font-medium underline underline-offset-2",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

function MonthsLink() {
  const { t } = useTranslation("monthEnd");
  return (
    <Link to="/ay-sonu" className={MONTHS_LINK}>
      {t("page.showMonths")}
    </Link>
  );
}

/** The month before and the month after; none after the month that runs now. */
function Neighbours({ detail, today }: { detail: MonthEndDetail; today: string | undefined }) {
  const { t } = useTranslation("monthEnd");
  const last = today ?? (detail.month.status === "running" ? detail.month.month : undefined);
  const hasNext = last !== undefined && detail.next_month <= last;
  return (
    <nav aria-label={t("page.months")} className="flex flex-wrap gap-2">
      <LinkButton
        to={`/ay-sonu/${detail.previous_month}`}
        aria-label={t("page.previous", { month: formatMonth(detail.previous_month) })}
      >
        <ArrowLeftIcon className="size-4" />
        {formatMonth(detail.previous_month)}
      </LinkButton>
      {hasNext ? (
        <LinkButton
          to={`/ay-sonu/${detail.next_month}`}
          aria-label={t("page.next", { month: formatMonth(detail.next_month) })}
        >
          {formatMonth(detail.next_month)}
          <ArrowRightIcon className="size-4" />
        </LinkButton>
      ) : null}
    </nav>
  );
}

interface SectionsProps {
  detail: MonthEndDetail;
  list: MonthEndList | undefined; // the months' statuses: the month before is compared with when it is closed
  labels: Labels;
}

function Sections({ detail, list, labels }: SectionsProps) {
  const { t } = useTranslation("monthEnd");
  const { view } = useView();
  const [params, setParams] = useSearchParams();
  const rowHref = (fingerprint: string) => `?${withRow(params, fingerprint).toString()}`;
  const bigSay = useBigSay(detail.big);
  const previousClosed = list?.months.find((m) => m.month === detail.previous_month)?.status === "closed";
  const nothing = detail.accounts.length === 0 && detail.count === 0;
  // Side by side the cards read at a glance; the detailed view's tables need the screen's width.
  const grid = cn("grid items-start gap-4", view === "simple" && "lg:grid-cols-2");
  return (
    <>
      {nothing ? <Empty title={t("page.noDocuments")} /> : null}
      <div className={grid}>
        <AccountsCard accounts={detail.accounts} status={detail.month.status} labels={labels} />
        <TotalsCard detail={detail} previousClosed={previousClosed} />
      </div>
      <TrendCard detail={detail} />
      <div className={grid}>
        <SpendingCard detail={detail} />
        <RegularCard
          regular={detail.regular}
          rowHref={rowHref}
          partial={detail.month.status !== "closed" && detail.month.status !== "running"}
        />
      </div>
      <RowsCard
        title={t("rows.big")}
        say={bigSay}
        none={t("rows.bigNone")}
        rows={detail.big}
        order="amount"
        labels={labels}
        rowHref={rowHref}
      />
      <div className={grid}>
        <RowsCard
          title={t("rows.provisional")}
          about={t("rows.provisionalText")}
          none={t("rows.provisionalNone")}
          rows={detail.provisional}
          order="day"
          labels={labels}
          rowHref={rowHref}
        />
        <RowsCard
          title={t("rows.unmatched")}
          about={t("rows.unmatchedText")}
          none={t("rows.unmatchedNone")}
          rows={detail.unmatched}
          order="day"
          labels={labels}
          rowHref={rowHref}
        />
      </div>
      <Card title={t("export.monthTitle")}>
        <ExportLink kind={detail.export} thisMonth />
      </Card>
      <RowPanel
        fingerprint={params.get(ROW) ?? ""}
        onClose={() => setParams((was) => withRow(was, null))}
        rowHref={rowHref}
      />
    </>
  );
}
