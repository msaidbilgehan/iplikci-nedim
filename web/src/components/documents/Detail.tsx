// What a document's page tells beside the document itself (F03's detail): the rows read from it in its own order, each
// one shown in the viewer where it is printed; the statements' own checks; how it arrived (an e-mail's sender, subject
// and a way to it in Gmail, a file's name and folder) and what it came with; and in the detailed view every fact the
// archive keeps of it.

import { useTranslation } from "react-i18next";

import type { Arrival, DocumentCheck, DocumentDetail, DocumentRow, Labels, SourceRef } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatFlow, formatMoney, formatPeriod, formatSize, formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Card, Facts } from "../ui/Card";
import { Money } from "../ui/Money";
import { NextStep, ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
const CHOSEN = "bg-amber-100 text-zinc-950 dark:bg-amber-300 dark:text-zinc-950";
const LINK = cn("rounded text-sm font-medium text-teal-800 underline underline-offset-2 dark:text-teal-300", FOCUS);

const documentLink = (sha256: string) => ({ screen: "document" as const, id: sha256, query: {} });

/** A row's amount the way its money goes: above zero it leaves the user. */
function flowOf(row: DocumentRow): { value: DocumentRow["amount"]; direction: "in" | "out" } {
  return {
    value: { minor: Math.abs(row.amount.minor), currency: row.amount.currency },
    direction: row.amount.minor > 0 ? "out" : "in",
  };
}

/** Where a row is printed, in words: its page and line, its sheet's row, or its place in a text. */
function usePlace(): (ref: SourceRef | null) => string {
  const { t } = useTranslation("documents");
  return (ref) => {
    if (!ref) {
      return "";
    }
    return [
      ref.page !== null ? t("rows.placePage", { page: ref.page }) : "",
      ref.line !== null ? t("rows.placeLine", { line: ref.line }) : "",
      ref.sheet ? ref.sheet : "",
      ref.row !== null ? t("rows.placeRow", { row: ref.row }) : "",
      ref.span ? t("rows.placeText") : "",
    ]
      .filter(Boolean)
      .join(" · ");
  };
}

interface RowsCardProps {
  rows: readonly DocumentRow[];
  more: boolean; // more rows were read than the service lists
  chosen: string; // the fingerprint of the row the viewer shows
  onChoose: (fingerprint: string) => void;
  labels: Labels;
}

export function RowsCard({ rows, more, chosen, onChoose, labels }: RowsCardProps) {
  const { t } = useTranslation("documents");
  const row = rows.find((candidate) => candidate.fingerprint === chosen) ?? null;
  return (
    <Card title={t("rows.title")}>
      {rows.length === 0 ? (
        <p className="text-sm">{t("rows.none")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <Simple>
            <RowList rows={rows} chosen={chosen} onChoose={onChoose} />
          </Simple>
          <Detailed>
            <RowTable rows={rows} chosen={chosen} onChoose={onChoose} labels={labels} />
          </Detailed>
          {more ? <p className={SMALL}>{t("rows.more", { count: rows.length })}</p> : null}
          {row ? <ChosenRow row={row} labels={labels} /> : null}
        </div>
      )}
    </Card>
  );
}

/** The rows as buttons, each showing its row in the viewer; a row the ledger does not count is said so. */
function RowList({ rows, chosen, onChoose }: Omit<RowsCardProps, "more" | "labels">) {
  const { t } = useTranslation("documents");
  return (
    <ol
      aria-label={t("rows.caption")}
      className={cn(
        "flex max-h-[28rem] flex-col divide-y divide-zinc-100 overflow-auto rounded-md border border-zinc-200",
        "dark:divide-zinc-800 dark:border-zinc-700",
      )}
    >
      {rows.map((row) => {
        const on = row.fingerprint === chosen;
        const { value, direction } = flowOf(row);
        return (
          <li key={row.fingerprint}>
            <button
              type="button"
              aria-pressed={on}
              onClick={() => onChoose(row.fingerprint)}
              className={cn(
                "flex w-full flex-wrap items-baseline gap-x-3 px-3 py-2 text-left text-sm",
                on ? CHOSEN : "hover:bg-zinc-50 dark:hover:bg-zinc-800",
                FOCUS,
              )}
            >
              {/* The spaces keep the button's name in words: a flex box lays its items out without them. */}
              <span className="w-20 shrink-0 tabular-nums">{formatDay(row.day)}</span>{" "}
              <span className="min-w-0 flex-1 wrap-break-word">{row.description}</span>{" "}
              <span
                className={cn(
                  "whitespace-nowrap tabular-nums",
                  !row.counted && !on && "text-zinc-600 dark:text-zinc-400",
                )}
              >
                {formatFlow(value, direction)}
                {row.counted ? "" : ` · ${t("rows.notCounted")}`}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/** Every value of the rows; a row's description shows it in the viewer. */
function RowTable({ rows, chosen, onChoose, labels }: Omit<RowsCardProps, "more">) {
  const { t } = useTranslation("documents");
  const place = usePlace();
  return (
    <Table>
      <caption className="sr-only">{t("rows.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("rows.day")}</Th>
          <Th>{t("rows.description")}</Th>
          <Th className="text-right">{t("rows.amount")}</Th>
          <Th>{t("rows.kind")}</Th>
          <Th>{t("rows.account")}</Th>
          <Th>{t("rows.category")}</Th>
          <Th>{t("rows.place")}</Th>
          <Th>{t("rows.evidence")}</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const on = row.fingerprint === chosen;
          const { value, direction } = flowOf(row);
          return (
            <tr key={row.fingerprint} className={cn(on && CHOSEN)}>
              <Td className="whitespace-nowrap tabular-nums">{formatDay(row.day)}</Td>
              <Td className="min-w-48">
                <button
                  type="button"
                  aria-pressed={on}
                  aria-label={t("rows.show", { description: row.description, day: formatDay(row.day) })}
                  onClick={() => onChoose(row.fingerprint)}
                  className={cn("rounded text-left underline decoration-1 underline-offset-2", FOCUS)}
                >
                  {row.description}
                </button>
              </Td>
              <Td className="text-right">
                <Money
                  value={value}
                  direction={direction}
                  certainty={row.provisional ? "provisional" : "confirmed"}
                  className="justify-end"
                />
              </Td>
              <Td>{labelOf(labels, "TransactionKind", row.kind)}</Td>
              <Td>{row.account}</Td>
              <Td>{row.category}</Td>
              <Td className="whitespace-nowrap">{place(row.ref)}</Td>
              <Td>
                {row.evidence ? labelOf(labels, "EvidenceStatus", row.evidence) : ""}
                {row.counted ? null : <span className={cn("block", SMALL)}>{t("rows.notCounted")}</span>}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

/** The chosen row's facts, and the way to it on the İşlemler screen. */
function ChosenRow({ row, labels }: { row: DocumentRow; labels: Labels }) {
  const { t } = useTranslation("documents");
  const place = usePlace();
  const { value, direction } = flowOf(row);
  const facts = [
    formatDay(row.day),
    labelOf(labels, "TransactionKind", row.kind),
    row.account,
    row.category,
    place(row.ref),
    row.evidence ? labelOf(labels, "EvidenceStatus", row.evidence) : "",
  ].filter(Boolean);
  return (
    <section
      aria-label={t("rows.chosen")}
      className={cn(
        "flex flex-col gap-1 rounded-md border border-amber-400 bg-amber-50 p-3 text-sm",
        "dark:border-amber-500 dark:bg-amber-950",
      )}
    >
      <p className="font-medium wrap-break-word">{row.description}</p>
      <p className="tabular-nums">{formatFlow(value, direction)}</p>
      <p className="text-xs text-zinc-700 dark:text-zinc-300">{facts.join(" · ")}</p>
      <NextStep step={{ link: { screen: "transaction", id: row.fingerprint, query: {} }, label: t("rows.open") }} />
    </section>
  );
}

/**
 * The statements' own checks. A card statement holds when the total it prints is what its rows and the previous
 * balance add up to; an account list, when every running balance it prints follows from the rows before it.
 */
export function ChecksCard({ checks }: { checks: readonly DocumentCheck[] }) {
  const { t } = useTranslation("documents");
  if (checks.length === 0) {
    return null;
  }
  const sayOf = (check: DocumentCheck, period: string): string => {
    const named = { account: check.account, period };
    if (check.balance_checks) {
      return check.printed
        ? t("checks.list", { ...named, printed: formatMoney(check.printed) })
        : t("checks.listNoPrinted", named);
    }
    return check.printed
      ? t("checks.card", { ...named, printed: formatMoney(check.printed), counted: formatMoney(check.counted) })
      : t("checks.cardNoPrinted", { ...named, counted: formatMoney(check.counted) });
  };
  return (
    <Card title={t("checks.title")}>
      <ul className="flex flex-col gap-3 text-sm">
        {checks.map((check) => {
          const period = formatPeriod(check.start ?? "", check.cut);
          const facts = [
            t("checks.rows", { count: check.rows }),
            check.balance_checks
              ? t("checks.balances", { held: check.balance_checks[0] ?? 0, of: check.balance_checks[1] ?? 0 })
              : "",
          ].filter(Boolean);
          return (
            <li key={`${check.account}-${check.cut}`} className="flex flex-col gap-1">
              <Status tone={check.verified ? "good" : "critical"}>
                {check.verified ? t("checks.verified") : t("checks.unverified")}
              </Status>
              <p>{sayOf(check, period)}</p>
              <p className={SMALL}>{facts.join(" · ")}</p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

interface ArrivalsCardProps {
  arrivals: readonly Arrival[];
  parent: string; // the message it came attached to
  attachments: DocumentDetail["attachments"];
  labels: Labels;
}

/** How the document came, every time it came: an e-mail with a way to it in Gmail, a file with its folder. */
export function ArrivalsCard({ arrivals, parent, attachments, labels }: ArrivalsCardProps) {
  const { t } = useTranslation("documents");
  return (
    <Card title={t("arrivals.title")}>
      <div className="flex flex-col gap-3 text-sm">
        {arrivals.length === 0 ? (
          <p>{t("arrivals.none")}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {arrivals.map((arrival, index) => (
              // An arrival has no id of its own; the list is the archive's, in the order they came.
              <li key={index} className="flex flex-col gap-0.5">
                <p className="font-medium">
                  {labelOf(labels, "SourceKind", arrival.kind)}
                  {arrival.received_at ? ` · ${formatTime(arrival.received_at)}` : ""}
                </p>
                {arrival.kind === "email" ? <MailArrival arrival={arrival} /> : <FileArrival arrival={arrival} />}
              </li>
            ))}
          </ul>
        )}
        {parent ? (
          <ScreenLink link={documentLink(parent)} className="self-start">
            {t("arrivals.parent")}
          </ScreenLink>
        ) : null}
        {attachments.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="font-medium">{t("arrivals.attachments")}</p>
            <ul className="flex flex-col gap-1">
              {attachments.map((attachment) => (
                <li key={attachment.sha256}>
                  <ScreenLink link={documentLink(attachment.sha256)} className="wrap-break-word">
                    {attachment.name}
                  </ScreenLink>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function MailArrival({ arrival }: { arrival: Arrival }) {
  const { t } = useTranslation("documents");
  return (
    <>
      <p className="wrap-break-word">{t("arrivals.email", { sender: arrival.sender, subject: arrival.subject })}</p>
      {arrival.sent_at ? <p className={SMALL}>{t("arrivals.sent", { time: formatTime(arrival.sent_at) })}</p> : null}
      {arrival.gmail ? (
        // Gmail's own page, in a tab of its own: nothing of the interface goes with it (no referrer).
        <a href={arrival.gmail} target="_blank" rel="noreferrer noopener" className={cn(LINK, "self-start")}>
          {t("arrivals.gmail")}{" "}
          <span className="sr-only">{t("arrivals.newTab")}</span>
        </a>
      ) : null}
    </>
  );
}

function FileArrival({ arrival }: { arrival: Arrival }) {
  const { t } = useTranslation("documents");
  return (
    <>
      <p className="wrap-break-word">{arrival.name}</p>
      {arrival.origin ? (
        <p className={cn(SMALL, "wrap-break-word")}>{t("arrivals.origin", { origin: arrival.origin })}</p>
      ) : null}
    </>
  );
}

/** Every fact the archive keeps of the document: the detailed view's. */
export function FactsCard({ found, labels }: { found: DocumentDetail; labels: Labels }) {
  const { t } = useTranslation("documents");
  const document = found.document;
  const none = t("list.none");
  const verified =
    document.verified === null ? none : document.verified ? t("facts.verifiedYes") : t("facts.verifiedNo");
  return (
    <Card title={t("facts.title")}>
      <Facts
        items={[
          [t("facts.kind"), document.kind ? labelOf(labels, "DocumentKind", document.kind) : none],
          [t("facts.status"), labelOf(labels, "DocumentStatus", document.status)],
          [t("facts.period"), formatPeriod(document.period_start, document.period_end) || none],
          [t("facts.accounts"), document.accounts.map((account) => account.label).join(", ") || none],
          [
            t("facts.reader"),
            document.reader ? t("facts.readerText", { reader: document.reader, version: found.parser_version }) : none,
          ],
          [t("facts.parser"), document.parser || none],
          [t("facts.verified"), verified],
          [t("facts.file"), document.file],
          [t("facts.size"), formatSize(document.size)],
          [t("facts.added"), formatTime(document.added_at)],
          [t("facts.sha256"), <code className="break-all text-xs">{document.sha256}</code>],
        ]}
      />
    </Card>
  );
}
