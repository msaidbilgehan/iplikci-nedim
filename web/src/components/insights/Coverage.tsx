// The months each account's statements and account lists cover (the MVP report's coverage grid): a row per account
// and a cell per month, from the first month any document covers to the last, each month covered whole, in part or not
// at all. The table view says the same in words: each account's first and last month, its whole months, the months
// covered in part with their share, and the months between them no document covers. Receipts and bank notices cover
// no month, so an account they alone tell is not here.

import { Fragment, useId } from "react";
import { useTranslation } from "react-i18next";

import type { AccountCover, Coverage } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMonth } from "../../lib/format";
import { percent } from "../../lib/turkish";
import { ChartFrame } from "../charts/ChartFrame";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const WHOLE = 0.97; // covered to within a day: whole, as the MVP report counted it
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const CELL = {
  whole: "bg-seq-500 dark:bg-seq-400",
  part: "bg-seq-200 dark:bg-seq-700",
  none: "bg-chart-grid",
} as const;

type Cover = keyof typeof CELL;

function coverOf(share: number): Cover {
  return share >= WHOLE ? "whole" : share > 0 ? "part" : "none";
}

interface Span {
  first: string;
  last: string;
  whole: string[];
  part: { month: string; share: number }[];
  none: string[]; // between its first and last month
}

/** An account's months between the first and the last its documents cover; null when they cover none. */
function spanOf(months: readonly string[], account: AccountCover): Span | null {
  const shares = account.shares.map(Number);
  const first = shares.findIndex((share) => share > 0);
  const last = shares.findLastIndex((share) => share > 0);
  if (first < 0) {
    return null;
  }
  const span: Span = { first: months[first] ?? "", last: months[last] ?? "", whole: [], part: [], none: [] };
  for (let i = first; i <= last; i += 1) {
    const month = months[i] ?? "";
    const share = shares[i] ?? 0;
    const cover = coverOf(share);
    if (cover === "whole") {
      span.whole.push(month);
    } else if (cover === "part") {
      span.part.push({ month, share });
    } else {
      span.none.push(month);
    }
  }
  return span;
}

/** The years over the months, each above its own months. */
function years(months: readonly string[]): { year: string; count: number }[] {
  const found: { year: string; count: number }[] = [];
  for (const month of months) {
    const year = month.slice(0, 4);
    const last = found.at(-1);
    if (last?.year === year) {
      last.count += 1;
    } else {
      found.push({ year, count: 1 });
    }
  }
  return found;
}

export function CoverageGrid({ coverage }: { coverage: Coverage }) {
  const { t } = useTranslation("insights");
  const summaryId = useId();
  const { months, accounts } = coverage;
  if (months.length === 0 || accounts.length === 0) {
    return null;
  }
  const from = months[0] ?? "";
  const to = months.at(-1) ?? "";
  const spans = accounts.map((account) => spanOf(months, account));
  const gaps = spans.filter((span) => span && (span.part.length > 0 || span.none.length > 0)).length;
  const columns = { gridTemplateColumns: `repeat(${months.length}, minmax(0.375rem, 1fr))` };
  const name = (account: AccountCover) =>
    account.closed ? t("coverage.closedName", { name: account.account.label }) : account.account.label;
  const status = (cover: Cover) => t(`coverage.${cover}`);

  const chart = (
    <div className="flex flex-col gap-2">
      <ul aria-label={t("coverage.legend")} className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {(Object.keys(CELL) as Cover[]).map((cover) => (
          <li key={cover} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("size-2.5 rounded-[2px]", CELL[cover])} />
            {status(cover)}
          </li>
        ))}
      </ul>
      <div className="grid items-center gap-x-3 gap-y-1 text-sm" style={{ gridTemplateColumns: "max-content 1fr" }}>
        <span />
        <div aria-hidden="true" className="grid gap-px" style={columns}>
          {years(months).map(({ year, count }) => (
            <span
              key={year}
              className="overflow-hidden whitespace-nowrap text-[0.6875rem] text-zinc-600 dark:text-zinc-300"
              style={{ gridColumn: `span ${count}` }}
            >
              {count >= 3 ? year : ""}
            </span>
          ))}
        </div>
        {accounts.map((account) => (
          <Fragment key={account.account.id}>
            <ScreenLink link={account.link} className="max-w-48 truncate">
              {name(account)}
            </ScreenLink>
            <div aria-hidden="true" className="grid gap-px" style={columns}>
              {account.shares.map((share, i) => {
                const month = months[i] ?? "";
                const cover = coverOf(Number(share));
                return (
                  <span
                    key={month}
                    className={cn("h-4 rounded-[2px]", CELL[cover])}
                    title={`${account.account.label} · ${formatMonth(month)}: ${status(cover)}`}
                  />
                );
              })}
            </div>
          </Fragment>
        ))}
      </div>
    </div>
  );

  const table = (
    <Table>
      <caption className="sr-only">{t("coverage.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("coverage.account")}</Th>
          <Th>{t("coverage.span")}</Th>
          <Th>{t("coverage.wholeMonths")}</Th>
          <Th>{t("coverage.partMonths")}</Th>
          <Th>{t("coverage.noneMonths")}</Th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((account, index) => {
          const span = spans[index];
          return (
            <tr key={account.account.id}>
              <Td className="min-w-40">
                <ScreenLink link={account.link} className="font-medium">
                  {account.account.label}
                </ScreenLink>
                {account.closed ? <span className={`block ${SMALL}`}>{t("coverage.closed")}</span> : null}
              </Td>
              <Td className="whitespace-nowrap">
                {span ? t("coverage.period", { from: formatMonth(span.first), to: formatMonth(span.last) }) : null}
              </Td>
              <Td className="whitespace-nowrap">{t("coverage.months", { count: span?.whole.length ?? 0 })}</Td>
              <Td className="min-w-36">
                {span && span.part.length > 0
                  ? span.part.map((p) => t("coverage.share", { month: formatMonth(p.month), share: percent(p.share) }))
                      .join(", ")
                  : t("coverage.nothing")}
              </Td>
              <Td className="min-w-32">
                {span && span.none.length > 0 ? span.none.map(formatMonth).join(", ") : t("coverage.nothing")}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );

  return (
    <ChartFrame
      title={t("coverage.title")}
      summary={
        gaps === 0
          ? t("coverage.sayWhole", { from: formatMonth(from), to: formatMonth(to), count: accounts.length })
          : t("coverage.sayGaps", { from: formatMonth(from), to: formatMonth(to), count: accounts.length, gaps })
      }
      summaryId={summaryId}
      chart={chart}
      table={table}
    />
  );
}
