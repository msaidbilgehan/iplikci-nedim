// A document itself, as the service shows it (F03's viewer, architecture §18): a PDF's pages drawn as images, one at a
// time, the chosen row's box over its page (or its line marked in the page's text); a sheet's table, the chosen row
// marked; an e-mail's text with the chosen row's words marked, and the sender's own markup only in a sandboxed frame
// that runs no script and loads nothing; an HTML document's or a text's words. The original never opens in the
// interface's origin: it downloads.

import { type RefObject, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { ApiError } from "../../api/client";
import { useDocumentView, usePageLines } from "../../api/queries";
import type { DocumentMailOut, PageSizeOut, TableOut } from "../../api/schema";
import type { DocumentItem, DocumentRow, ViewKind } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatTime } from "../../lib/format";
import { Failure, Loading } from "../QueryState";
import { Button } from "../ui/Button";
import { Facts } from "../ui/Card";
import { Segmented } from "../ui/Segmented";
import { PAGE } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
// Positioned, so a mark's offsetTop counts from the frame's top when the frame scrolls it into the middle.
const FRAME = cn("relative max-h-[75vh] overflow-auto rounded-md border border-zinc-200 dark:border-zinc-700", FOCUS);
const MARKED = "bg-amber-100 font-medium text-zinc-950 dark:bg-amber-300 dark:text-zinc-950";
const AROUND = 3; // the lines of a page's text shown on each side of the row's
const WORDS = 160; // the characters shown on each side of a row's words when its line cannot be found

type Mode = "text" | "original";

interface ViewerProps {
  document: DocumentItem;
  kind: ViewKind; // how the detail says it is shown: nothing is asked for a document that is not
  row: DocumentRow | null; // the chosen row, shown where it is printed
}

export function Viewer({ document, kind, row }: ViewerProps) {
  const { t } = useTranslation("documents");
  const view = useDocumentView(kind === "none" ? "" : document.sha256);
  if (kind === "none") {
    return <p className="text-sm">{t("view.none")}</p>;
  }
  if (view.isPending) {
    return <Loading />;
  }
  if (view.isError) {
    // A document the viewing process cannot open (an encrypted PDF) stays so: trying again would not help.
    if (view.error instanceof ApiError && view.error.code === "document_unshown") {
      return (
        <div className="flex flex-col gap-1 text-sm">
          <p>{view.error.message}</p>
          <p className={SMALL}>{t("view.none")}</p>
        </div>
      );
    }
    return <Failure error={view.error} onRetry={() => void view.refetch()} />;
  }
  const shown = view.data;
  const unplaced = row !== null && row.ref === null ? <p className="text-sm">{t("view.noPlace")}</p> : null;
  const name = document.name;
  let body = <p className="text-sm">{t("view.none")}</p>;
  if (shown.kind === "pdf") {
    body = <PdfView sha256={document.sha256} name={name} pages={shown.pages} row={row} />;
  } else if (shown.kind === "table" && shown.table) {
    body = <TableView name={name} table={shown.table} row={row} />;
  } else if (shown.kind === "mail" && shown.mail) {
    body = <MailView sha256={document.sha256} name={name} mail={shown.mail} hasHtml={shown.has_html} row={row} />;
  } else if (shown.kind === "html" || shown.kind === "text") {
    body = (
      <TextView
        sha256={document.sha256}
        name={name}
        text={shown.text}
        hasHtml={shown.has_html}
        row={row}
        asWritten={shown.kind === "text"}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {unplaced}
      {body}
    </div>
  );
}

/** Scrolls a frame so its mark stands in the middle, whenever what is marked changes. */
function useCentred(frame: RefObject<HTMLElement | null>, mark: RefObject<HTMLElement | null>, marked: unknown): void {
  useEffect(() => {
    if (frame.current && mark.current) {
      frame.current.scrollTop = mark.current.offsetTop - frame.current.clientHeight / 2;
    }
  }, [frame, mark, marked]);
}

interface PdfViewProps {
  sha256: string;
  name: string;
  pages: PageSizeOut[];
  row: DocumentRow | null;
}

/** A PDF a page at a time, opened at the chosen row's page; the address keeps the page turned to (?sayfa=). */
function PdfView({ sha256, name, pages, row }: PdfViewProps) {
  const { t } = useTranslation("documents");
  const [params, setParams] = useSearchParams();
  const count = pages.length;
  if (count === 0) {
    return <p className="text-sm">{t("view.noPages")}</p>;
  }
  const rowPage = row?.ref?.page ?? null;
  const asked = Number(params.get(PAGE) ?? "");
  const page = Math.min(count, Math.max(1, Number.isInteger(asked) && asked >= 1 ? asked : (rowPage ?? 1)));
  const ref = row?.ref ?? null;
  const box = ref && ref.page === page ? ref.box : null;
  const line = ref && ref.page === page && !box ? ref.line : null;
  const turn = (to: number) =>
    setParams(
      (was) => {
        const next = new URLSearchParams(was);
        next.set(PAGE, String(to));
        return next;
      },
      { replace: true },
    );
  return (
    <div className="flex flex-col gap-3">
      {count > 1 ? (
        <nav aria-label={t("view.pages")} className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={page <= 1} onClick={() => turn(page - 1)}>
            {t("view.previous")}
          </Button>
          <span className="text-sm tabular-nums" aria-live="polite">
            {t("view.page", { page, count })}
          </span>
          <Button variant="secondary" disabled={page >= count} onClick={() => turn(page + 1)}>
            {t("view.next")}
          </Button>
          {rowPage !== null && rowPage !== page && rowPage <= count ? (
            <Button variant="secondary" onClick={() => turn(rowPage)}>
              {t("view.toRow", { page: rowPage })}
            </Button>
          ) : null}
        </nav>
      ) : null}
      <PageImage sha256={sha256} name={name} page={page} size={pages[page - 1] ?? null} box={box} />
      {line !== null ? <PageText sha256={sha256} page={page} line={line} /> : null}
    </div>
  );
}

interface PageImageProps {
  sha256: string;
  name: string;
  page: number;
  size: PageSizeOut | null;
  box: number[] | null; // the row's box in points from the page's top left: x0, top, x1, bottom
}

/** The page as the service draws it, the row's box over it scaled by the page's size in points. */
function PageImage({ sha256, name, page, size, box }: PageImageProps) {
  const { t } = useTranslation("documents");
  const frame = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLDivElement>(null);
  const marked = box !== null && box.length === 4 && size !== null && size.width > 0 && size.height > 0;
  const percent = (value: number, of: number) => `${(value / of) * 100}%`;
  const centre = () => {
    if (frame.current && mark.current) {
      frame.current.scrollTop = mark.current.offsetTop - frame.current.clientHeight / 2;
    }
  };
  useCentred(frame, mark, box);
  const label = marked ? t("view.imageMarked", { name, page }) : t("view.image", { name, page });
  return (
    <div ref={frame} tabIndex={0} role="region" aria-label={label} className={FRAME}>
      <div className="relative">
        <img
          src={`/api/documents/${sha256}/pages/${page}.png?width=1200`}
          alt={label}
          onLoad={centre}
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
  );
}

/** The page's text around the row's line, the line marked: a row a text reader placed by its line. */
function PageText({ sha256, page, line }: { sha256: string; page: number; line: number }) {
  const { t } = useTranslation("documents");
  const lines = usePageLines(sha256, page);
  if (!lines.data) {
    return null;
  }
  const all = lines.data.lines;
  const start = Math.max(1, line - AROUND);
  const end = Math.min(all.length, line + AROUND);
  return (
    <ol
      aria-label={t("view.pageText", { page })}
      start={start}
      className="rounded-md border border-zinc-200 p-2 font-mono text-xs dark:border-zinc-700"
    >
      {all.slice(start - 1, end).map((text, index) => {
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

/** A sheet's rows as the service read them, numbered as the sheet numbers them, the chosen row marked. */
function TableView({ name, table, row }: { name: string; table: TableOut; row: DocumentRow | null }) {
  const { t } = useTranslation("documents");
  const frame = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLTableRowElement>(null);
  const sheet = row?.ref?.sheet ?? null;
  // The service shows a spreadsheet's first sheet: a row on another one is said, not marked.
  const elsewhere = sheet !== null && table.name !== "" && sheet !== table.name;
  const target = elsewhere ? null : (row?.ref?.row ?? null);
  useCentred(frame, mark, target);
  const label = target !== null ? t("view.tableMarked", { name }) : t("view.table", { name });
  return (
    <div className="flex flex-col gap-2">
      {table.name ? <p className={SMALL}>{t("view.sheet", { name: table.name })}</p> : null}
      {elsewhere ? <p className="text-sm">{t("view.otherSheet", { sheet })}</p> : null}
      <div ref={frame} tabIndex={0} role="region" aria-label={label} className={FRAME}>
        <table className="w-full border-collapse text-left text-xs">
          <caption className="sr-only">{label}</caption>
          <tbody>
            {table.rows.map((cells, index) => {
              const number = index + 1;
              const isRow = number === target;
              return (
                <tr
                  key={number}
                  ref={isRow ? mark : undefined}
                  className={cn("border-b border-zinc-100 dark:border-zinc-800", isRow && MARKED)}
                >
                  <th
                    scope="row"
                    className={cn(
                      "sticky left-0 px-2 py-1 font-normal tabular-nums",
                      isRow
                        ? "bg-amber-100 text-zinc-950 dark:bg-amber-300"
                        : "bg-white text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300",
                    )}
                  >
                    {number}
                    {isRow ? " " : null}
                    {isRow ? <span className="sr-only">({t("view.marked")})</span> : null}
                  </th>
                  {cells.map((cell, column) => (
                    <td key={column} className="whitespace-nowrap px-2 py-1">
                      {cell}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {table.more ? <p className={SMALL}>{t("view.tableMore", { count: table.rows.length })}</p> : null}
    </div>
  );
}

interface MailViewProps {
  sha256: string;
  name: string;
  mail: DocumentMailOut;
  hasHtml: boolean;
  row: DocumentRow | null;
}

/** An e-mail: its subject, sender's domain and date, its text with the row's words marked, or its own markup. */
function MailView({ sha256, name, mail, hasHtml, row }: MailViewProps) {
  const { t } = useTranslation("documents");
  const none = t("list.none");
  const [mode, setMode] = useState<Mode>("text");
  return (
    <div className="flex flex-col gap-3">
      <Facts
        items={[
          [t("view.subject"), mail.subject || none],
          [t("view.sender"), mail.sender || none],
          [t("view.sent"), mail.sent ? formatTime(mail.sent) : none],
        ]}
      />
      {hasHtml ? <ModeSwitch mode={mode} onChange={setMode} /> : null}
      {hasHtml && mode === "original" ? (
        <Sandboxed sha256={sha256} name={name} />
      ) : (
        <MailBody name={name} mail={mail} span={row?.ref?.span ?? null} />
      )}
    </div>
  );
}

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  const { t } = useTranslation("documents");
  return (
    <Segmented<Mode>
      legend={t("view.mode")}
      options={[
        { value: "text", label: t("view.text") },
        { value: "original", label: t("view.original") },
      ]}
      value={mode}
      onChange={onChange}
    />
  );
}

/**
 * The body as a browser breaks it into lines. The row's span counts in the body's collapsed text; its words are marked
 * in the line that holds them, or shown with the words around them when they run over lines.
 */
function MailBody({ name, mail, span }: { name: string; mail: DocumentMailOut; span: number[] | null }) {
  const { t } = useTranslation("documents");
  const frame = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLElement>(null);
  const [from = 0, to = 0] = span ?? [];
  const words = span ? mail.text.slice(from, to).trim() : "";
  const at = words ? mail.lines.findIndex((line) => line.includes(words)) : -1;
  useCentred(frame, mark, `${at}:${words}`);
  if (mail.lines.length === 0) {
    return <p className="text-sm">{t("view.empty")}</p>;
  }
  const label = at >= 0 ? t("view.bodyMarked", { name }) : t("view.body", { name });
  return (
    <>
      {span && words && at < 0 ? <Excerpt text={mail.text} from={from} to={to} /> : null}
      <div ref={frame} tabIndex={0} role="region" aria-label={label} className={cn(FRAME, "p-3 text-sm")}>
        {mail.lines.map((line, index) => (
          // The lines never move: their place is their key.
          <p key={index} className="mb-2 wrap-break-word last:mb-0">
            {index === at ? <Marked text={line} words={words} markRef={mark} /> : line}
          </p>
        ))}
      </div>
    </>
  );
}

function Marked({ text, words, markRef }: { text: string; words: string; markRef: RefObject<HTMLElement | null> }) {
  const from = text.indexOf(words);
  return (
    <>
      {text.slice(0, from)}
      <mark ref={markRef} className={cn("rounded px-0.5", MARKED)}>
        {words}
      </mark>
      {text.slice(from + words.length)}
    </>
  );
}

/** The words around a row's span in a collapsed text, the span marked. */
function Excerpt({ text, from, to }: { text: string; from: number; to: number }) {
  const { t } = useTranslation("documents");
  const caption = useId();
  const start = Math.max(0, from - WORDS);
  const end = Math.min(text.length, to + WORDS);
  return (
    <figure aria-labelledby={caption} className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-700">
      <figcaption id={caption} className="mb-1 text-xs font-medium text-zinc-600 dark:text-zinc-300">
        {t("view.excerpt")}
      </figcaption>
      <p className="wrap-break-word">
        {start > 0 ? "… " : ""}
        {text.slice(start, from)}
        <mark className={cn("rounded px-0.5", MARKED)}>{text.slice(from, to)}</mark>
        {text.slice(to, end)}
        {end < text.length ? " …" : ""}
      </p>
    </figure>
  );
}

interface TextViewProps {
  sha256: string;
  name: string;
  text: string;
  hasHtml: boolean;
  row: DocumentRow | null;
  asWritten: boolean; // a text document as it is (an e-invoice's XML): its lines and spaces kept
}

/** An HTML document's visible text or a text document, the row's span marked; an HTML document's own markup too. */
function TextView({ sha256, name, text, hasHtml, row, asWritten }: TextViewProps) {
  const { t } = useTranslation("documents");
  const [mode, setMode] = useState<Mode>("text");
  const frame = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLElement>(null);
  const [from = -1, to = -1] = row?.ref?.span ?? [];
  const marked = from >= 0 && to > from && to <= text.length;
  useCentred(frame, mark, marked ? `${from}:${to}:${mode}` : mode);
  const label = marked ? t("view.bodyMarked", { name }) : t("view.body", { name });
  const Words = asWritten ? "pre" : "p";
  return (
    <div className="flex flex-col gap-3">
      {hasHtml ? <ModeSwitch mode={mode} onChange={setMode} /> : null}
      {hasHtml && mode === "original" ? (
        <Sandboxed sha256={sha256} name={name} />
      ) : text ? (
        <div ref={frame} tabIndex={0} role="region" aria-label={label} className={cn(FRAME, "p-3 text-sm")}>
          <Words className={cn("wrap-break-word", asWritten && "whitespace-pre-wrap font-mono text-xs")}>
            {marked ? (
              <>
                {text.slice(0, from)}
                <mark ref={mark} className={cn("rounded px-0.5", MARKED)}>
                  {text.slice(from, to)}
                </mark>
                {text.slice(to)}
              </>
            ) : (
              text
            )}
          </Words>
        </div>
      ) : (
        <p className="text-sm">{t("view.empty")}</p>
      )}
    </div>
  );
}

/**
 * The sender's own markup in a frame that runs no script, sends no form and loads nothing from elsewhere: the frame's
 * sandbox and the answer's own policy both say so (ADR-0009). Images from elsewhere stay out.
 */
function Sandboxed({ sha256, name }: { sha256: string; name: string }) {
  const { t } = useTranslation("documents");
  return (
    <div className="flex flex-col gap-2">
      <p className={SMALL}>{t("view.originalNote")}</p>
      <iframe
        title={t("view.originalTitle", { name })}
        src={`/api/documents/${sha256}/original.html`}
        sandbox=""
        referrerPolicy="no-referrer"
        className="h-[75vh] w-full rounded-md border border-zinc-200 bg-white dark:border-zinc-700"
      />
    </div>
  );
}
