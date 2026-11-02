// The Belgeler screen (F03's archive, F02's adding by hand): every kept document with its kind, accounts, period,
// status and the way it came, newest first, narrowed by a full-text search, the kind, the way, the account and the
// bank, all in the address; a tab of what was not read, each with why and a reading to try again. Documents are added
// through a plan the user sees and confirms. A document's name opens it in the viewer (/belgeler/:id).

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";

import { ApiError } from "../api/client";
import { useAccounts, useDocuments, useLabels, useReparse } from "../api/queries";
import type { DocumentItem } from "../api/types";
import { DocumentList } from "../components/documents/DocumentList";
import { Filters } from "../components/documents/Filters";
import {
  choosesNone,
  isFiltered,
  listQuery,
  onTab,
  type Tab,
  tabOf,
  withoutFilters,
} from "../components/documents/query";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { ArrowRightIcon } from "../components/ui/Icons";
import { PageHeader } from "../components/ui/PageHeader";
import { STEP } from "../components/ui/Say";
import { Segmented } from "../components/ui/Segmented";
import { cn } from "../lib/cn";
import { labelOf } from "../lib/labels";
import { UploadPanel } from "./UploadPanel";

/** What the page before said in passing (the viewer, after a document went to the Trash). */
function saidOf(state: unknown): string {
  return typeof state === "object" && state !== null && "said" in state && typeof state.said === "string"
    ? state.said
    : "";
}

export default function DocumentsPage() {
  const { t } = useTranslation("documents");
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const labels = useLabels().data ?? {};
  const accounts = useAccounts();
  const none = choosesNone(params);
  const list = useDocuments(listQuery(params), !none);
  const reparse = useReparse();
  const [said, setSaid] = useState(() => saidOf(location.state));
  useEffect(() => {
    // Said once: the address keeps no message for the back button to bring again.
    if (saidOf(location.state)) {
      void navigate({ pathname: location.pathname, search: location.search }, { replace: true, state: null });
    }
  }, [location, navigate]);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const tab = tabOf(params);
  const change = (next: URLSearchParams, replace = false) => setParams(next, replace ? { replace: true } : undefined);
  const reset = () => change(withoutFilters(params));
  const readAgain = (document: DocumentItem) => {
    setSaid("");
    reparse.mutate(document.sha256, {
      onSuccess: ({ status }) =>
        setSaid(
          status === "removed"
            ? t("unread.company", { name: document.name })
            : t("unread.reparsed", { name: document.name, status: labelOf(labels, "DocumentStatus", status) }),
        ),
    });
  };
  const resetButton = (
    <Button variant="secondary" className="mt-2" onClick={reset}>
      {t("empty.reset")}
    </Button>
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <UploadPanel />
      <div className="flex flex-col gap-4">
        {/* Its own width: the column would stretch the joined buttons across the screen. */}
        <div>
          <Segmented<Tab>
            legend={t("tabs.label")}
            options={[
              { value: "all", label: t("tabs.all") },
              { value: "unread", label: t("tabs.unread") },
            ]}
            value={tab}
            onChange={(next) => change(onTab(params, next))}
          />
        </div>
        <Filters params={params} onChange={change} labels={labels} accounts={accounts.data} />
      </div>
      <p aria-live="polite" className="text-sm empty:hidden">
        {said}
      </p>
      {reparse.isError ? <Alert tone="critical" title={reparse.error.message} /> : null}
      {none ? <Empty title={t("empty.filtered")}>{resetButton}</Empty> : null}
      {!none && list.isPending ? <Loading /> : null}
      {!none && list.isError ? (
        list.error instanceof ApiError && list.error.code === "filter_invalid" ? (
          <Alert tone="critical" title={list.error.message}>
            {resetButton}
          </Alert>
        ) : (
          <Failure error={list.error} onRetry={() => void list.refetch()} />
        )
      ) : null}
      {!none && list.isSuccess && items.length === 0 ? (
        isFiltered(params) ? (
          <Empty title={t("empty.filtered")}>{resetButton}</Empty>
        ) : tab === "unread" ? (
          <Empty title={t("empty.unread")}>{t("empty.unreadText")}</Empty>
        ) : (
          <Empty title={t("empty.title")}>
            <p>{t("empty.text")}</p>
            <Link to="/kurulum/eklenti" className={cn(STEP, "mt-2")}>
              {t("empty.next")}
              <ArrowRightIcon className="size-4 shrink-0" />
            </Link>
          </Empty>
        )
      ) : null}
      {!none && items.length > 0 ? (
        <div
          aria-busy={list.isPlaceholderData}
          className={cn("flex flex-col gap-3", list.isPlaceholderData && "opacity-60")}
        >
          <DocumentList
            documents={items}
            labels={labels}
            reparsing={{ pending: reparse.isPending ? (reparse.variables ?? null) : null, onReparse: readAgain }}
          />
          {list.hasNextPage ? (
            <Button
              variant="secondary"
              className="self-start"
              onClick={() => void list.fetchNextPage()}
              disabled={list.isFetchingNextPage}
            >
              {list.isFetchingNextPage ? t("list.loadingMore") : t("list.more")}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
