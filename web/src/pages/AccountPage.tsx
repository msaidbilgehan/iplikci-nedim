// An account's page (F07) at /hesaplar/:id: where it stands and how far its documents reach, what its type adds (a
// card's statements and installments, an overdraft's cost, a deposit's return, a holding's value, a portfolio, a
// loan), its balance by day, its months, its fees, the regular payments and income through it, and its rows a page at
// a time with the row's detail at the side (?satir=), in three parts shown one at a time (?bolum=). The user may give
// it a name of their own and say the day it closed.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { ACCOUNT_ROWS, useAccount, useLabels } from "../api/queries";
import type { AccountPage as Page, Labels } from "../api/types";
import { AliasForm } from "../components/accounts/AliasForm";
import { ClosingForm } from "../components/accounts/ClosingForm";
import {
  BrokerageDetails,
  CardDetails,
  DepositDetails,
  HoldingDetails,
  LoanDetails,
  OverdraftDetails,
} from "../components/accounts/Details";
import { CurveCard, FeesCard, MonthsCard, SeriesCard, StatusCard } from "../components/accounts/Sections";
import { useView } from "../components/Preferences";
import { Failure, Loading } from "../components/QueryState";
import { atOffset, offsetOf, ROW, withRow } from "../components/transactions/query";
import { RowPanel } from "../components/transactions/RowPanel";
import { Pager, RowsTable } from "../components/transactions/RowsTable";
import { Totals } from "../components/transactions/Totals";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ArrowLeftIcon } from "../components/ui/Icons";
import { PageHeader } from "../components/ui/PageHeader";
import { SectionCount, SectionTabs } from "../components/ui/SectionTabs";
import { NextStep } from "../components/ui/Say";
import { cn } from "../lib/cn";
import { labelOf } from "../lib/labels";

const BACK = cn(
  "inline-flex min-h-8 items-center gap-1 self-start rounded text-sm font-medium underline underline-offset-2",
  "text-teal-800 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export default function AccountPage() {
  const { t } = useTranslation("accounts");
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const page = useAccount(id, offsetOf(params));
  const labels = useLabels().data ?? {};
  const [editing, setEditing] = useState<"" | "alias" | "closing">("");
  const [said, setSaid] = useState("");
  const found = page.data;
  const item = found?.account;
  const edit = (form: "alias" | "closing") => () => {
    setSaid("");
    setEditing(form);
  };
  const done = (what: string) => {
    setSaid(what);
    setEditing("");
  };
  return (
    <div className="flex flex-col gap-6">
      <Link to="/hesaplar" className={BACK}>
        <ArrowLeftIcon className="size-4" />
        {t("page.back")}
      </Link>
      <PageHeader
        title={item ? item.account.label : t("page.title")}
        description={
          item
            ? [
                item.bank,
                labelOf(labels, "AccountType", item.type),
                item.alias ? t("page.bankName", { label: item.label }) : "",
                item.closed_on ? t("page.closedOn", { day: item.closed_on }) : item.closed ? t("page.closed") : "",
              ]
                .filter(Boolean)
                .join(" · ")
            : null
        }
        actions={
          item && !editing ? (
            <>
              <Button variant="secondary" onClick={edit("alias")}>
                {t("alias.edit")}
              </Button>
              <Button variant="secondary" onClick={edit("closing")}>
                {item.closed_on ? t("closing.change") : t("closing.edit")}
              </Button>
            </>
          ) : null
        }
      />
      <p aria-live="polite" className="-mt-4 text-sm empty:hidden">
        {said}
      </p>
      {item && editing === "alias" ? <AliasForm item={item} onDone={done} /> : null}
      {item && editing === "closing" ? <ClosingForm item={item} onDone={done} /> : null}
      {page.isPending ? <Loading /> : null}
      {page.isError ? <Failure error={page.error} onRetry={() => void page.refetch()} /> : null}
      {found ? <Sections found={found} labels={labels} /> : null}
    </div>
  );
}

// The page in three parts, one shown at a time (?bolum=): where the account stands and its months, what is paid
// through it regularly with its fees, and its rows.
function Sections({ found, labels }: { found: Page; labels: Labels }) {
  const { t } = useTranslation("accounts");
  const { view } = useView();
  const item = found.account;
  // Side by side the cards read at a glance; the detailed view's tables need the screen's width.
  const grid = cn("grid items-start gap-4", view === "simple" && "lg:grid-cols-2");
  return (
    <SectionTabs
      label={t("page.sections.label")}
      sections={[
        {
          id: "ozet",
          label: t("page.sections.summary"),
          content: () => (
            <>
              <div className={grid}>
                <StatusCard item={item} labels={labels} />
                {found.overdraft ? <OverdraftDetails overdraft={found.overdraft} /> : null}
                {found.deposit ? <DepositDetails deposit={found.deposit} /> : null}
                {found.holding ? (
                  <HoldingDetails holding={found.holding} title={labelOf(labels, "AccountType", item.type)} />
                ) : null}
                {found.brokerage ? <BrokerageDetails brokerage={found.brokerage} /> : null}
                {found.loan ? <LoanDetails loan={found.loan} labels={labels} /> : null}
              </div>
              {found.card ? <CardDetails card={found.card} labels={labels} /> : null}
              <CurveCard
                account={item.account.id}
                curve={found.curve}
                note={found.curve_note}
                label={item.account.label}
              />
              <MonthsCard account={item.account.id} months={found.months} />
            </>
          ),
        },
        {
          id: "duzenli",
          label: t("page.sections.regular"),
          badge: <SectionCount count={found.payments.length + found.income.length} />,
          content: () => (
            <div className={grid}>
              <SeriesCard title={t("payments.title")} series={found.payments} labels={labels} />
              <SeriesCard title={t("income.title")} series={found.income} labels={labels} />
              <FeesCard account={item.account.id} fees={found.fees} />
            </div>
          ),
        },
        {
          id: "islemler",
          label: t("page.sections.rows"),
          badge: <SectionCount count={found.totals.count} />,
          content: () => <Rows found={found} labels={labels} />,
        },
      ]}
    />
  );
}

/** The account's rows, the newest first, a page at a time; a row's name opens its detail at the side. */
function Rows({ found, labels }: { found: Page; labels: Labels }) {
  const { t } = useTranslation("accounts");
  const [params, setParams] = useSearchParams();
  const rowHref = (fingerprint: string) => `?${withRow(params, fingerprint).toString()}`;
  const id = found.account.account.id;
  return (
    <Card
      title={t("rows.title")}
      action={
        <NextStep step={{ link: { screen: "transactions", id: "", query: { account: id } }, label: t("rows.all") }} />
      }
    >
      <div className="flex flex-col gap-3">
        {found.rows.length === 0 ? (
          <p className="text-sm">{t("rows.none")}</p>
        ) : (
          <>
            <Totals totals={found.totals} />
            <RowsTable rows={found.rows} labels={labels} ordering={{ sort: "day", order: "desc" }} rowHref={rowHref} />
            <Pager
              offset={found.offset}
              shown={found.rows.length}
              count={found.totals.count}
              next={found.next}
              size={ACCOUNT_ROWS}
              onPage={(at) => setParams((was) => atOffset(was, at))}
            />
          </>
        )}
      </div>
      <RowPanel
        fingerprint={params.get(ROW) ?? ""}
        onClose={() => setParams((was) => withRow(was, null))}
        rowHref={rowHref}
      />
    </Card>
  );
}
