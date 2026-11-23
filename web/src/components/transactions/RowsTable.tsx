// The ledger's rows as a table (F04, and an account's page in F07): the day, the row's name, the account, the kind, the
// category, the necessity and the amount with its certainty; a row the statements leave out ("ekstrede yok") stays
// in the list but faded, as it counts in no total. Each name opens the row's detail; a column's heading sorts by it.
// The simple view keeps the day, the name and the amount; the detailed view shows every column. A month's saving's
// rows say which way each moved the savings: euros earned came into them, euros sold left them, though both are money
// coming into an account.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Sort } from "../../api/schema";
import type { Labels, Row } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { useView } from "../Preferences";
import { Button } from "../ui/Button";
import { ChevronDownIcon } from "../ui/Icons";
import { Money } from "../ui/Money";
import { Table, Td, Th } from "../ui/Table";
import type { Ordering } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

export interface Selecting {
  selected: ReadonlySet<string>;
  onToggle: (fingerprint: string, on: boolean) => void;
  onTogglePage: (on: boolean) => void;
}

interface RowsTableProps {
  rows: readonly Row[];
  labels: Labels;
  ordering: Ordering;
  onSort?: (column: Sort) => void; // without it the headings do not sort
  rowHref: (fingerprint: string) => string; // the address that opens a row's detail
  selecting?: Selecting; // the rows a bulk action will change
  saving?: boolean; // the rows are a saving's (the saving filter): say what each set aside or took out
}

/** Whether a row can carry a correction: one the statements leave out counts in nothing and carries none. */
export function isCorrectable(row: Row): boolean {
  return row.certainty !== "excluded";
}

/** A part's number among its row's parts, from its fingerprint: the row's with "-<n>" after it. */
export function partNumber(fingerprint: string): number {
  return Number(fingerprint.slice(fingerprint.lastIndexOf("-") + 1));
}

export function RowsTable({ rows, labels, ordering, onSort, rowHref, selecting, saving = false }: RowsTableProps) {
  const { t } = useTranslation("transactions");
  const { view } = useView();
  const detailed = view === "detailed";
  const columns: Record<Sort, string> = {
    day: t("table.day"),
    title: t("table.title"),
    account: t("table.account"),
    category: t("table.category"),
    amount: t("table.amount"),
  };
  const direction = ordering.order === "asc" ? t("table.ascending") : t("table.descending");
  const selectable = rows.filter(isCorrectable);
  const allOn =
    selecting !== undefined && selectable.length > 0 && selectable.every((r) => selecting.selected.has(r.fingerprint));
  const heading = (column: Sort, className?: string) => (
    <SortHeading
      column={column}
      name={columns[column]}
      ordering={ordering}
      {...(onSort ? { onSort } : {})}
      {...(className ? { className } : {})}
    />
  );
  return (
    <Table>
      <caption className="sr-only">
        {t("table.caption", { order: t("table.sortedBy", { column: columns[ordering.sort], direction }) })}
      </caption>
      <thead>
        <tr>
          {selecting ? (
            <Th className="w-10">
              <input
                type="checkbox"
                aria-label={t("table.selectPage")}
                checked={allOn}
                disabled={selectable.length === 0}
                onChange={(event) => selecting.onTogglePage(event.target.checked)}
                className={cn("size-4 accent-teal-700 dark:accent-teal-400", FOCUS)}
              />
            </Th>
          ) : null}
          {heading("day")}
          {heading("title")}
          {detailed ? heading("account") : null}
          {detailed ? <Th>{t("table.kind")}</Th> : null}
          {detailed ? heading("category") : null}
          {detailed ? <Th>{t("table.necessity")}</Th> : null}
          {heading("amount", "text-right")}
          {detailed ? <Th>{t("table.notes")}</Th> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const faded = row.certainty === "excluded";
          return (
            <tr key={row.fingerprint} className={cn(faded && "text-zinc-600 dark:text-zinc-400")}>
              {selecting ? (
                <Td>
                  <input
                    type="checkbox"
                    aria-label={t("table.select", { title: row.title, day: formatDay(row.day) })}
                    checked={selecting.selected.has(row.fingerprint)}
                    disabled={!isCorrectable(row)}
                    onChange={(event) => selecting.onToggle(row.fingerprint, event.target.checked)}
                    className={cn("size-4 accent-teal-700 dark:accent-teal-400", FOCUS)}
                  />
                </Td>
              ) : null}
              <Td className="whitespace-nowrap tabular-nums">{formatDay(row.day)}</Td>
              <Td className="min-w-48">
                <Link
                  to={rowHref(row.fingerprint)}
                  className={cn("rounded font-medium underline-offset-2 hover:underline", FOCUS)}
                >
                  {row.title}
                </Link>
                {detailed ? (
                  <span className={cn("block", SMALL)}>{row.description}</span>
                ) : (
                  <span className={cn("block", SMALL)}>
                    {[row.category, row.account.label].filter(Boolean).join(" · ")}
                  </span>
                )}
                {row.split_of ? (
                  <span className={cn("block", SMALL)}>
                    {t("table.split", { number: partNumber(row.fingerprint), total: row.split_parts })}
                  </span>
                ) : null}
                {row.installment ? (
                  <span className={cn("block", SMALL)}>{t("table.installment", { installment: row.installment })}</span>
                ) : null}
                {row.original ? <span className={cn("block", SMALL)}>{row.original}</span> : null}
                {saving && row.saving ? (
                  <span className={cn("block font-medium", SMALL)}>
                    {t(row.saving.minor < 0 ? "table.savingOut" : "table.savingIn", {
                      amount: formatMoney({ minor: Math.abs(row.saving.minor), currency: row.saving.currency }),
                    })}
                  </span>
                ) : null}
              </Td>
              {detailed ? <Td>{row.account.label}</Td> : null}
              {detailed ? <Td>{labelOf(labels, "TransactionKind", row.kind)}</Td> : null}
              {detailed ? (
                <Td>
                  {row.category}
                  {row.group ? <span className={cn("block", SMALL)}>{row.group}</span> : null}
                </Td>
              ) : null}
              {detailed ? <Td>{row.necessity ? labelOf(labels, "Necessity", row.necessity) : "—"}</Td> : null}
              <Td className="text-right">
                <Money value={row.amount} direction={row.direction} certainty={row.certainty} className="justify-end" />
              </Td>
              {detailed ? (
                <Td className={SMALL}>
                  {[row.tags.map((tag) => `#${tag}`).join(" "), row.note].filter(Boolean).join(" · ")}
                </Td>
              ) : null}
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

interface SortHeadingProps {
  column: Sort;
  name: string;
  ordering: Ordering;
  onSort?: (column: Sort) => void;
  className?: string;
}

/** A column's heading: a button that sorts by it, and the order it is in for screen readers (aria-sort). */
function SortHeading({ column, name, ordering, onSort, className }: SortHeadingProps) {
  const { t } = useTranslation("transactions");
  const current = ordering.sort === column;
  const sort = current ? (ordering.order === "asc" ? "ascending" : "descending") : "none";
  if (!onSort) {
    return (
      <Th aria-sort={sort} className={className}>
        {name}
      </Th>
    );
  }
  return (
    <Th aria-sort={sort} className={className}>
      <button
        type="button"
        onClick={() => onSort(column)}
        aria-label={t("table.sortBy", { column: name })}
        className={cn(
          "inline-flex min-h-8 items-center gap-1 rounded font-medium hover:text-zinc-900 dark:hover:text-zinc-50",
          FOCUS,
        )}
      >
        {name}
        <ChevronDownIcon
          className={cn(
            "size-3.5 transition-transform motion-reduce:transition-none",
            current ? "opacity-100" : "opacity-40",
            current && ordering.order === "asc" && "rotate-180",
          )}
        />
      </button>
    </Th>
  );
}

interface PagerProps {
  offset: number;
  shown: number; // rows on this page
  count: number; // rows the filters keep
  next: number | null;
  size: number;
  onPage: (offset: number) => void;
}

/** "1–50 / 93" with the pages before and after. */
export function Pager({ offset, shown, count, next, size, onPage }: PagerProps) {
  const { t } = useTranslation("transactions");
  if (count === 0) {
    return null;
  }
  return (
    <nav aria-label={t("table.pager")} className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - size))}>
        {t("table.previous")}
      </Button>
      <span className="text-sm tabular-nums" aria-live="polite">
        {t("table.pages", { from: offset + 1, to: offset + shown, count })}
      </span>
      <Button variant="secondary" disabled={next === null} onClick={() => next !== null && onPage(next)}>
        {t("table.next")}
      </Button>
    </nav>
  );
}
