// The Abonelikler screen (F08): the monthly and periodic payments with their status, what they cost while they run,
// their last and next payment and their price change, then what ended or was cancelled, the regular income and the
// card purchases with installments left. A payment after the month the user cancelled one leads the screen as a
// warning. A series' panel (?seri=<id>) shows the payments it rests on, each leading to its row, and "İptal ettim" or
// "Yeniden bekle", the change shown before it is written. Every number comes from /api/subscriptions; the statuses'
// and periods' names from /api/labels.

import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { useCategoryRules, useLabels, useSubscriptions } from "../api/queries";
import type { CategoryRules, Labels, Series, Subscriptions } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import { IncomeList } from "../components/subscriptions/IncomeList";
import { InstallmentList } from "../components/subscriptions/InstallmentList";
import { type Act, SeriesPanel } from "../components/subscriptions/SeriesPanel";
import { NAME, type Opening, SeriesList, SMALL } from "../components/subscriptions/SeriesList";
import { isRunning, SERIES } from "../components/subscriptions/series";
import { Alert } from "../components/ui/Alert";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep, Say } from "../components/ui/Say";
import { Term } from "../components/ui/Term";
import { formatDay, formatMoney, formatMonth } from "../lib/format";

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;
const CALENDAR = { screen: "calendar", id: "", query: {} } as const;

/** The address with a series' panel open, or none. */
function withSeries(params: URLSearchParams, id: string | null): URLSearchParams {
  const next = new URLSearchParams(params);
  if (id) {
    next.set(SERIES, id);
  } else {
    next.delete(SERIES);
  }
  return next;
}

export default function SubscriptionsPage() {
  const { t } = useTranslation("subscriptions");
  const subscriptions = useSubscriptions();
  const labels = useLabels().data ?? {};
  const rules = useCategoryRules();
  const [params, setParams] = useSearchParams();
  const [act, setAct] = useState<Act>(null);
  const open = params.get(SERIES) ?? "";
  const opening: Opening = {
    hrefOf: (id) => `?${withSeries(params, id).toString()}`,
    onAct: (id, next) => {
      setAct(next);
      setParams((was) => withSeries(was, id));
    },
  };
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {subscriptions.isPending ? <Loading /> : null}
      {subscriptions.isError ? (
        <Failure error={subscriptions.error} onRetry={() => void subscriptions.refetch()} />
      ) : null}
      {subscriptions.data ? (
        <>
          <Overview found={subscriptions.data} labels={labels} rules={rules.data} opening={opening} />
          <SeriesPanel
            id={open}
            found={subscriptions.data}
            labels={labels}
            rules={rules}
            act={act}
            onClose={() => {
              setAct(null);
              setParams((was) => withSeries(was, null));
            }}
          />
        </>
      ) : null}
    </div>
  );
}

interface OverviewProps {
  found: Subscriptions;
  labels: Labels;
  rules: CategoryRules | undefined; // the `_biten` entries: what each series offers
  opening: Opening;
}

function Overview({ found, labels, rules, opening }: OverviewProps) {
  const { t } = useTranslation("subscriptions");
  const listed = found.series.filter((series) => series.listed);
  const monthly = listed.filter((series) => series.period === "month" && isRunning(series));
  const periodic = listed.filter((series) => series.period !== "month" && isRunning(series));
  const ended = listed.filter((series) => !isRunning(series));
  const income = found.income.filter((series) => series.listed);
  if (listed.length === 0 && income.length === 0 && found.installments.length === 0) {
    return (
      <Empty title={t("empty")}>
        <p>{t("emptyText")}</p>
        <NextStep step={{ link: DOCUMENTS, label: t("emptyNext") }} className="mt-2" />
      </Empty>
    );
  }
  const shared = { asOf: found.as_of, labels, rules, opening };
  return (
    <>
      <AfterCancel series={found.series.filter((series) => series.status === "paid_after_cancel")} opening={opening} />
      <div className="flex flex-col gap-1">
        <Say next={{ link: CALENDAR, label: t("sayNext") }}>{sayOf(monthly, periodic, t)}</Say>
        <WindowLine found={found} />
      </div>
      {monthly.length > 0 ? (
        <Card title={t("monthly.title")}>
          <SeriesList series={monthly} kind="monthly" caption={t("monthly.caption")} {...shared} />
        </Card>
      ) : null}
      {periodic.length > 0 ? (
        <Card title={t("periodic.title")}>
          <p className={`mb-3 ${SMALL}`}>{t("periodic.text")}</p>
          <SeriesList series={periodic} kind="periodic" caption={t("periodic.caption")} {...shared} />
        </Card>
      ) : null}
      {ended.length > 0 ? (
        <Card title={t("ended.title")}>
          <p className={`mb-3 ${SMALL}`}>{t("ended.text")}</p>
          <SeriesList series={ended} kind="ended" caption={t("ended.caption")} {...shared} />
        </Card>
      ) : null}
      {income.length > 0 ? (
        <Card title={t("income.title")}>
          <p className={`mb-3 ${SMALL}`}>{t("income.text")}</p>
          <IncomeList income={income} {...shared} />
        </Card>
      ) : null}
      {found.installments.length > 0 ? (
        <Card title={t("installments.title")}>
          <InstallmentList installments={found.installments} />
        </Card>
      ) : null}
    </>
  );
}

/** The simple view's sentence: what the running monthly payments come to in a month, and the periodic ones apart. */
function sayOf(monthly: readonly Series[], periodic: readonly Series[], t: TFunction<"subscriptions">): string {
  if (monthly.length === 0) {
    return periodic.length > 0 ? t("sayOnlyPeriodic", { count: periodic.length }) : t("sayNone");
  }
  const minor = monthly.reduce((sum, series) => sum + series.amount.minor, 0);
  const total = formatMoney({ minor, currency: monthly[0]?.amount.currency ?? "TRY" });
  const said = t("say", { count: monthly.length, total });
  return periodic.length > 0 ? `${said} ${t("sayPeriodic", { count: periodic.length })}` : said;
}

/** What the statuses rest on: the newest statement's end, and the complete months the list looks back on. */
function WindowLine({ found }: { found: Subscriptions }) {
  const { t } = useTranslation("subscriptions");
  const first = found.window[0];
  const last = found.window.at(-1);
  return (
    <p className={SMALL}>
      {t("asOf", { day: formatDay(found.as_of) })}
      {first && last ? (
        <>
          {" "}
          {t("window", { from: formatMonth(first), to: formatMonth(last), count: found.window.length })}{" "}
          <Term id="completeMonth">{t("windowTerm")}</Term> {t("windowEnd")}
        </>
      ) : null}
    </p>
  );
}

/** The payments made after the month the user's rules give as the last, each opening its panel: check them first. */
function AfterCancel({ series, opening }: { series: readonly Series[]; opening: Opening }) {
  const { t } = useTranslation("subscriptions");
  if (series.length === 0) {
    return null;
  }
  return (
    <Alert tone="warning" title={t("afterCancel.title", { count: series.length })}>
      <ul className="flex flex-col gap-1">
        {series.map((s) => (
          <li key={s.id}>
            <Link to={opening.hrefOf(s.id)} className={NAME}>
              {s.payee}
            </Link>
            : {s.note}
          </li>
        ))}
      </ul>
    </Alert>
  );
}
