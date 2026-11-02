// Where a row is printed, shown in its document with the row marked (F03, F04's "belge önizlemesi, satırı
// vurgulanmış"; architecture §18): a PDF's page as the service draws it with the row's box over it, or the page's
// text with its line marked; a sheet's rows around the row; an e-mail's or a text's words around the row's span. The
// original never opens in the interface's own origin: it is downloaded.

import { type ReactNode, useId, useRef } from "react";
import { useTranslation } from "react-i18next";

import { useDocumentDetail, useDocumentView, useLabels, usePageLines } from "../../api/queries";
import type { PageSizeOut, SourceRefOut, TableOut } from "../../api/schema";
import type { Printed } from "../../api/types";
import { cn } from "../../lib/cn";
import { labelOf } from "../../lib/labels";
import { Failure, Loading } from "../QueryState";
import { NextStep } from "../ui/Say";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const FRAME = "max-h-[28rem] overflow-auto rounded-md border border-zinc-200 dark:border-zinc-700";
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
const MARKED = "bg-amber-100 font-medium text-zinc-950 dark:bg-amber-300 dark:text-zinc-950";
const AROUND = 3; // the lines and rows shown on each side of the row's own
const WORDS = 160; // the characters of text shown on each side of the row's span
const PLACED: ReadonlySet<string> = new Set(["pdf", "mail", "html", "text"]); // a row's place is in the document's rows
const LINK = "rounded text-sm font-medium text-teal-800 underline underline-offset-2 dark:text-teal-300";

interface RowPreviewProps {
  printed: Printed;
  fingerprint: string; // the row's own: a split row's parts are printed as the one row they come from
}

export function RowPreview({ printed, fingerprint }: RowPreviewProps) {
  const { t } = useTranslation("transactions");
  const labels = useLabels().data ?? {};
  const view = useDocumentView(printed.document);
  const kind = view.data?.kind;
  // A PDF row's box, and an e-mail's or a text's span, are in the document's rows; a sheet's row is in `printed`.
  const detail = useDocumentDetail(printed.document, kind !== undefined && PLACED.has(kind));
  const ref = detail.data?.rows.find((row) => row.fingerprint === fingerprint)?.ref ?? null;
  const located = !detail.isPending; // the rows were read, or could not be: the box is known or there is none
  const where = [
    printed.page !== null ? t("printed.page", { page: printed.page }) : "",
    printed.line !== null ? t("printed.line", { line: printed.line }) : "",
    printed.sheet ? t("printed.sheet", { sheet: printed.sheet }) : "",
    printed.row !== null ? t("printed.row", { row: printed.row }) : "",
  ].filter(Boolean);
  return (
    <div className="flex flex-col gap-2">
      <div>
        <p className="font-medium wrap-break-word">{printed.name}</p>
        <p className={SMALL}>
          {[printed.kind ? labelOf(labels, "DocumentKind", printed.kind) : "", ...where].filter(Boolean).join(" · ")}
        </p>
      </div>
      {view.isPending ? <Loading /> : null}
      {view.isError ? <Failure error={view.error} onRetry={() => void view.refetch()} /> : null}
      {view.data ? (
        <Body
          kind={view.data.kind}
          printed={printed}
          pages={view.data.pages}
          table={view.data.table}
          text={view.data.mail?.text ?? view.data.text}
          refOf={ref}
          located={located}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <NextStep
          step={{
            link: { screen: "document", id: printed.document, query: { satir: fingerprint } },
            label: t("printed.open"),
          }}
        />
        <a href={`/api/documents/${printed.document}/download`} download className={cn(LINK, FOCUS)}>
          {t("printed.download")}
        </a>
      </div>
    </div>
  );
}

interface BodyProps {
  kind: string;
  printed: Printed;
  pages: PageSizeOut[];
  table: TableOut | null;
  text: string;
  refOf: SourceRefOut | null;
  located: boolean;
}

function Body({ kind, printed, pages, table, text, refOf, located }: BodyProps): ReactNode {
  const { t } = useTranslation("transactions");
  if (kind === "pdf" && printed.page !== null) {
    return (
      <PdfPage
        sha256={printed.document}
        name={printed.name}
        page={printed.page}
        size={pages[printed.page - 1] ?? null}
        box={refOf?.box ?? null}
        line={located ? printed.line : null}
      />
    );
  }
  if (kind === "table" && table && printed.row !== null) {
    return <TableExcerpt table={table} row={printed.row} />;
  }
  if ((kind === "mail" || kind === "html" || kind === "text") && refOf?.span) {
    return <TextExcerpt text={text} span={refOf.span} />;
  }
  return <p className="text-sm">{kind === "none" ? t("printed.noPreview") : t("printed.none")}</p>;
}

interface PdfPageProps {
  sha256: string;
  name: string;
  page: number;
  size: PageSizeOut | null;
  box: number[] | null;
  line: number | null;
}

/** The page as an image with the row's box over it, scaled by the page's size in points; or its text by line. */
function PdfPage({ sha256, name, page, size, box, line }: PdfPageProps) {
  const { t } = useTranslation("transactions");
  const frame = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLDivElement>(null);
  const marked = box !== null && box.length === 4 && size !== null && size.width > 0 && size.height > 0;
  const lines = usePageLines(sha256, page, !marked && line !== null);
  const percent = (value: number, of: number) => `${(value / of) * 100}%`;
  // The row's box in the middle of the frame once the page has loaded.
  const showMark = () => {
    if (frame.current && mark.current) {
      frame.current.scrollTop = mark.current.offsetTop - frame.current.clientHeight / 2;
    }
  };
  const label = marked ? t("printed.image", { name, page }) : t("printed.imagePlain", { name, page });
  return (
    <>
      <div ref={frame} tabIndex={0} role="region" aria-label={label} className={cn(FRAME, FOCUS)}>
        <div className="relative">
          <img
            src={`/api/documents/${sha256}/pages/${page}.png?width=1000`}
            alt={label}
            onLoad={showMark}
            className="block w-full bg-white"
          />
          {marked && size && box ? (
            <div
              ref={mark}
              aria-hidden="true"
              className="absolute rounded-sm bg-amber-300/30 ring-2 ring-amber-500"
              style={{
                left: percent(box[0] ?? 0, size.width),
                top: percent(box[1] ?? 0, size.height),
                width: percent((box[2] ?? 0) - (box[0] ?? 0), size.width),
                height: percent((box[3] ?? 0) - (box[1] ?? 0), size.height),
              }}
            />
          ) : null}
        </div>
      </div>
      {!marked && line !== null && lines.data ? <LinesExcerpt lines={lines.data.lines} line={line} /> : null}
    </>
  );
}

/** The page's text around the row's line, the line marked. */
function LinesExcerpt({ lines, line }: { lines: string[]; line: number }) {
  const { t } = useTranslation("transactions");
  const start = Math.max(1, line - AROUND);
  const end = Math.min(lines.length, line + AROUND);
  return (
    <ol
      aria-label={t("printed.lines")}
      start={start}
      className="rounded-md border border-zinc-200 p-2 font-mono text-xs dark:border-zinc-700"
    >
      {lines.slice(start - 1, end).map((text, index) => {
        const number = start + index;
        return (
          <li key={number} value={number} className={cn("whitespace-pre-wrap px-1", number === line && MARKED)}>
            {number === line ? <mark className="bg-transparent text-inherit">{text}</mark> : text}
          </li>
        );
      })}
    </ol>
  );
}

/** A sheet's rows around the row's own, numbered as the sheet numbers them, the row marked. */
function TableExcerpt({ table, row }: { table: TableOut; row: number }) {
  const { t } = useTranslation("transactions");
  const start = Math.max(1, row - AROUND);
  const end = Math.min(table.rows.length, row + AROUND);
  return (
    <div tabIndex={0} role="region" aria-label={t("printed.tableRows")} className={cn(FRAME, FOCUS)}>
      <table className="w-full border-collapse text-left text-xs">
        <caption className="sr-only">{t("printed.tableRows")}</caption>
        <tbody>
          {table.rows.slice(start - 1, end).map((cells, index) => {
            const number = start + index;
            const isRow = number === row;
            return (
              <tr key={number} className={cn("border-b border-zinc-100 dark:border-zinc-800", isRow && MARKED)}>
                <th
                  scope="row"
                  className={cn(
                    "px-2 py-1 font-normal tabular-nums",
                    isRow ? "text-zinc-950" : "text-zinc-600 dark:text-zinc-300",
                  )}
                >
                  {number}
                  {isRow ? " " : null}
                  {isRow ? <span className="sr-only">({t("printed.marked")})</span> : null}
                </th>
                {cells.map((cell, column) => (
                  <td key={column} className="px-2 py-1">
                    {cell}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The words around the row's span in an e-mail's or a text's collapsed text, the span marked. */
function TextExcerpt({ text, span }: { text: string; span: number[] }) {
  const { t } = useTranslation("transactions");
  const caption = useId();
  const [from = 0, to = 0] = span;
  const start = Math.max(0, from - WORDS);
  const end = Math.min(text.length, to + WORDS);
  return (
    <figure aria-labelledby={caption} className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-700">
      <figcaption id={caption} className="sr-only">
        {t("printed.excerpt")}
      </figcaption>
      <p>
        {start > 0 ? "… " : ""}
        {text.slice(start, from)}
        <mark className={cn("rounded px-0.5", MARKED)}>{text.slice(from, to)}</mark>
        {text.slice(to, end)}
        {end < text.length ? " …" : ""}
      </p>
    </figure>
  );
}
