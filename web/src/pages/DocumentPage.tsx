// A kept document (F03's detail and viewer) at /belgeler/:id: what it is and how far it was read, the document itself
// as the service shows it, the rows read from it — a row chosen (?satir=) is marked where it is printed —, the
// statements' checks and how it arrived. Its original downloads under its readable name; it can be read again, or moved
// to the system Trash once the user confirms it (ADR-0003).

import type { TFunction } from "i18next";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { useDocumentDetail, useLabels, useReparse, useRemoveDocument } from "../api/queries";
import type { DocumentDetail, Labels } from "../api/types";
import { ArrivalsCard, ChecksCard, FactsCard, RowsCard } from "../components/documents/Detail";
import { LINK_BUTTON } from "../components/documents/DocumentList";
import { PAGE, ROW } from "../components/documents/query";
import { Viewer } from "../components/documents/Viewer";
import { Detailed } from "../components/Preferences";
import { Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/Dialog";
import { ArrowLeftIcon } from "../components/ui/Icons";
import { PageHeader } from "../components/ui/PageHeader";
import { Say } from "../components/ui/Say";
import { cn } from "../lib/cn";
import { formatPeriod } from "../lib/format";
import { labelOf } from "../lib/labels";

const BACK = cn(
  "inline-flex min-h-8 items-center gap-1 self-start rounded text-sm font-medium underline underline-offset-2",
  "text-teal-800 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export default function DocumentPage() {
  const { t } = useTranslation("documents");
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const detail = useDocumentDetail(id);
  const labels = useLabels().data ?? {};
  const reparse = useReparse();
  const remove = useRemoveDocument();
  const [asking, setAsking] = useState(false);
  const [said, setSaid] = useState("");
  const found = detail.data;
  const document = found?.document;

  const readAgain = () => {
    if (!document) {
      return;
    }
    setSaid("");
    reparse.mutate(document.sha256, {
      onSuccess: ({ status }) => {
        if (status === "removed") {
          void navigate("/belgeler", { replace: true, state: { said: t("actions.company", { name: document.name }) } });
        } else {
          setSaid(t("actions.reparsed", { status: labelOf(labels, "DocumentStatus", status) }));
        }
      },
    });
  };
  const moveToTrash = () => {
    if (!document) {
      return;
    }
    remove.mutate(document.sha256, {
      onSuccess: () =>
        void navigate("/belgeler", { replace: true, state: { said: t("actions.removed", { name: document.name }) } }),
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Link to="/belgeler" className={BACK}>
        <ArrowLeftIcon className="size-4" />
        {t("viewer.back")}
      </Link>
      <PageHeader
        title={document ? document.name : t("viewer.title")}
        description={found ? describe(found, labels, t("viewer.noKind")) : null}
        actions={
          document ? (
            <>
              <a href={`/api/documents/${document.sha256}/download`} download className={LINK_BUTTON}>
                {t("actions.download")}
              </a>
              <Button variant="secondary" disabled={reparse.isPending} onClick={readAgain}>
                {reparse.isPending ? t("actions.reparsing") : t("actions.reparse")}
              </Button>
              <Button variant="secondary" onClick={() => setAsking(true)}>
                {t("actions.remove")}
              </Button>
            </>
          ) : null
        }
      />
      <p aria-live="polite" className="-mt-4 text-sm empty:hidden">
        {said}
      </p>
      {reparse.isError ? (
        <Alert tone="critical" title={t("actions.reparseFailed")}>
          <p>{reparse.error.message}</p>
        </Alert>
      ) : null}
      {detail.isPending ? <Loading /> : null}
      {detail.isError ? <Failure error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {found ? <Body found={found} labels={labels} /> : null}
      {document ? (
        <ConfirmDialog
          open={asking}
          onOpenChange={(open) => {
            setAsking(open);
            if (!open) {
              remove.reset();
            }
          }}
          title={t("actions.removeTitle")}
          description={t("actions.removeText", { name: document.name })}
          confirmLabel={remove.isPending ? t("actions.removing") : t("actions.remove")}
          onConfirm={moveToTrash}
          variant="danger"
          busy={remove.isPending}
        >
          {remove.isError ? <Alert tone="critical" title={remove.error.message} /> : null}
        </ConfirmDialog>
      ) : null}
    </div>
  );
}

/** The document in a line: its kind, period and accounts. */
function describe(found: DocumentDetail, labels: Labels, noKind: string): string {
  const document = found.document;
  return [
    document.kind ? labelOf(labels, "DocumentKind", document.kind) : noKind,
    formatPeriod(document.period_start, document.period_end),
    document.accounts.map((account) => account.label).join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
}

function Body({ found, labels }: { found: DocumentDetail; labels: Labels }) {
  const { t } = useTranslation("documents");
  const [params, setParams] = useSearchParams();
  const viewer = useRef<HTMLDivElement>(null);
  const document = found.document;
  const chosen = params.get(ROW) ?? "";
  const row = found.rows.find((candidate) => candidate.fingerprint === chosen) ?? null;
  // A row chosen again lets go of it; the viewer turns to the row's own page and comes into sight.
  const choose = (fingerprint: string) => {
    setParams(
      (was) => {
        const next = new URLSearchParams(was);
        next.delete(PAGE);
        if (fingerprint === chosen) {
          next.delete(ROW);
        } else {
          next.set(ROW, fingerprint);
        }
        return next;
      },
      { replace: true },
    );
    viewer.current?.scrollIntoView?.({ block: "nearest" });
  };
  return (
    <>
      {document.status === "processed" ? (
        <Say>{sayOf(found, labels, t)}</Say>
      ) : (
        <Alert tone="warning" title={labelOf(labels, "DocumentStatus", document.status)}>
          <p>
            {t(document.status === "unreadable" ? "viewer.unreadable" : "viewer.unprocessed", {
              reason: document.reason || t("viewer.noReason"),
            })}
          </p>
          <p className="mt-1">{t("viewer.unreadNext")}</p>
        </Alert>
      )}
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div ref={viewer} className="min-w-0 scroll-mt-4">
          <Card title={t("view.title")}>
            <Viewer document={document} kind={found.view} row={row} />
          </Card>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <RowsCard rows={found.rows} more={found.more_rows} chosen={chosen} onChoose={choose} labels={labels} />
          <ChecksCard checks={found.checks} />
          <ArrivalsCard
            arrivals={found.arrivals}
            parent={found.parent}
            attachments={found.attachments}
            labels={labels}
          />
          <Detailed>
            <FactsCard found={found} labels={labels} />
          </Detailed>
        </div>
      </div>
    </>
  );
}

/** The simple view's sentence: what the document is, how many rows were read from it, whether its totals hold. */
function sayOf(found: DocumentDetail, labels: Labels, t: TFunction<"documents">): string {
  const document = found.document;
  const kind = document.kind ? labelOf(labels, "DocumentKind", document.kind) : t("viewer.noKind");
  const period = formatPeriod(document.period_start, document.period_end);
  const count = found.rows.length;
  const verified = found.checks.length > 0 ? found.checks.every((check) => check.verified) : document.verified;
  return [
    period ? t("viewer.sayWhat", { kind, period }) : t("viewer.sayWhatOnly", { kind }),
    count === 0
      ? t("viewer.sayNoRows")
      : found.more_rows
        ? t("viewer.sayMoreRows", { count })
        : t("viewer.sayRows", { count }),
    verified === null ? "" : verified ? t("viewer.sayVerified") : t("viewer.sayUnverified"),
    count > 0 ? t("viewer.sayNext") : "",
  ]
    .filter(Boolean)
    .join(" ");
}
