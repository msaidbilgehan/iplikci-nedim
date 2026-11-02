// The İşlemler screen (F04): every row of the ledger, filtered by period, account, kind, category, necessity,
// certainty, tag and text, sorted by any column and paged, with what the rows add up to; the filters kept as views and
// downloaded as CSV. A row's name opens its detail at the side: why it is what it is, where it is printed and the
// corrections it may carry. Rows can be chosen for one category or a tag at once. The address holds it all, in the
// API's names, so other screens link here narrowed and the back button undoes a step.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useAccounts, useCategoryRules, useLabels, useTransactions } from "../api/queries";
import { accountOptions } from "../components/filters";
import { Empty, Failure, Loading } from "../components/QueryState";
import { BulkBar } from "../components/transactions/BulkBar";
import { Filters } from "../components/transactions/Filters";
import {
  atOffset,
  choosesNone,
  filtersOf,
  isFiltered,
  listQuery,
  MANY,
  ONE,
  orderingOf,
  PAGE_SIZE,
  ROW,
  sortedBy,
  withRow,
} from "../components/transactions/query";
import { RowPanel } from "../components/transactions/RowPanel";
import { isCorrectable, Pager, RowsTable } from "../components/transactions/RowsTable";
import { Totals } from "../components/transactions/Totals";
import { Views } from "../components/transactions/Views";
import { Button } from "../components/ui/Button";
import { DownloadLink } from "../components/ui/LinkButton";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep } from "../components/ui/Say";
import { cn } from "../lib/cn";

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;

interface Chosen {
  query: string; // the list it was chosen in: another filter, order or page starts with none chosen
  fingerprints: ReadonlySet<string>;
}

function toggle(set: Set<string>, fingerprints: readonly string[], on: boolean): void {
  for (const fingerprint of fingerprints) {
    if (on) {
      set.add(fingerprint);
    } else {
      set.delete(fingerprint);
    }
  }
}

export default function TransactionsPage() {
  const { t } = useTranslation("transactions");
  const { t: tc } = useTranslation();
  const [params, setParams] = useSearchParams();
  const labels = useLabels().data ?? {};
  const accounts = useAccounts();
  const rules = useCategoryRules();
  const none = choosesNone(params);
  const query = listQuery(params);
  const list = useTransactions(query, !none);
  const [chosen, setChosen] = useState<Chosen>({ query, fingerprints: new Set() });
  const selected = chosen.query === query ? chosen.fingerprints : new Set<string>();
  const rows = list.data?.rows ?? [];
  const ordering = orderingOf(params);
  const offset = list.data?.offset ?? 0;
  const open = params.get(ROW) ?? "";

  const select = (change: (was: Set<string>) => void) => {
    const next = new Set(selected);
    change(next);
    setChosen({ query, fingerprints: next });
  };
  const rowHref = (fingerprint: string) => `?${withRow(params, fingerprint).toString()}`;
  const reset = () =>
    setParams((was) => {
      const next = new URLSearchParams(was);
      for (const name of [...MANY, ...ONE, "offset"]) {
        next.delete(name);
      }
      return next;
    });
  const resetButton = (
    <Button variant="secondary" className="mt-2" onClick={reset}>
      {t("table.reset")}
    </Button>
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <>
            <Views params={params} onOpen={(next) => setParams(next)} />
            <DownloadLink href={`/api/transactions.csv?${filtersOf(params, true).toString()}`}>{t("csv")}</DownloadLink>
          </>
        }
      />
      <Filters
        params={params}
        onChange={(next, replace) => setParams(next, replace ? { replace: true } : undefined)}
        labels={labels}
        accounts={accountOptions(accounts.data, labels, t("filters.closed"))}
        rules={rules.data}
      />
      {none ? <Empty title={t("table.empty")}>{resetButton}</Empty> : null}
      {!none && list.isPending ? <Loading label={tc("loading")} /> : null}
      {!none && list.isError ? <Failure error={list.error} onRetry={() => void list.refetch()} /> : null}
      {!none && list.data ? (
        <>
          <Totals totals={list.data.totals} />
          <BulkBar
            selected={selected}
            categories={rules.data?.categories ?? []}
            onDone={() => setChosen({ query, fingerprints: new Set() })}
          />
          {rows.length === 0 ? (
            isFiltered(params) ? (
              <Empty title={t("table.empty")}>{resetButton}</Empty>
            ) : (
              <Empty title={t("table.emptyAll")}>
                <p>{t("table.emptyText")}</p>
                <NextStep step={{ link: DOCUMENTS, label: tc("open.documents") }} className="mt-2" />
              </Empty>
            )
          ) : (
            <div
              aria-busy={list.isPlaceholderData}
              className={cn("flex flex-col gap-3", list.isPlaceholderData && "opacity-60")}
            >
              <RowsTable
                rows={rows}
                labels={labels}
                ordering={ordering}
                onSort={(column) => setParams((was) => sortedBy(was, column))}
                rowHref={rowHref}
                selecting={{
                  selected,
                  onToggle: (fingerprint, on) => select((next) => toggle(next, [fingerprint], on)),
                  onTogglePage: (on) =>
                    select((next) => toggle(next, rows.filter(isCorrectable).map((row) => row.fingerprint), on)),
                }}
              />
              <Pager
                offset={offset}
                shown={rows.length}
                count={list.data.totals.count}
                next={list.data.next}
                size={PAGE_SIZE}
                onPage={(at) => setParams((was) => atOffset(was, at))}
              />
            </div>
          )}
        </>
      ) : null}
      <RowPanel fingerprint={open} onClose={() => setParams((was) => withRow(was, null))} rowHref={rowHref} />
    </div>
  );
}
