// The summary tiles (the MVP report's KPIs): the spending the filters keep over the period, its monthly average over
// the whole months alone, the monthly income where account lists tell it, what went on avoidable costs, and the last
// month against the whole months before it. Under them, what the spending leaves out (money sent to people, debt
// principal, cash advances, card payments without a statement), each with a button that adds it to the total.

import { useTranslation } from "react-i18next";

import { useKindTotals } from "../../api/queries";
import type { Labels, Spending } from "../../api/types";
import { formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Stat } from "../ui/Stat";
import { LEFT_OUT, spendingQuery } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

interface TilesProps {
  found: Spending;
  params: URLSearchParams;
}

export function Tiles({ found, params }: TilesProps) {
  const { t } = useTranslation("insights");
  const { tiles, period } = found;
  const kinds = params.getAll("kind").length > 0;
  const total = tiles.total.minor;
  const change = tiles.last_change === null ? null : Number(tiles.last_change);
  const base = tiles.last_base_months; // the whole months before the last one its change is measured against
  return (
    <section
      aria-label={t("tiles.label")}
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5"
    >
      <Stat
        label={kinds ? t("tiles.totalKinds") : t("tiles.total")}
        value={formatMoney(tiles.total)}
        meta={
          period
            ? t("tiles.totalMeta", { from: formatMonth(period.start), to: formatMonth(period.end), count: tiles.count })
            : null
        }
      />
      <Stat
        label={t("tiles.average")}
        value={tiles.average ? formatMoney(tiles.average) : "—"}
        meta={
          tiles.average_months > 0
            ? [
                t("tiles.averageMeta", { count: tiles.average_months }),
                tiles.partial_months > 0 ? t("tiles.averagePartial", { count: tiles.partial_months }) : "",
              ]
                .filter(Boolean)
                .join(" · ")
            : t("tiles.averageNone")
        }
      />
      <Stat
        label={t("tiles.income")}
        value={tiles.income_average ? formatMoney(tiles.income_average) : "—"}
        meta={
          tiles.income_months > 0
            ? [
                t("tiles.incomeMeta", { count: tiles.income_months }),
                tiles.income_share !== null ? t("tiles.incomeShare", { share: Number(tiles.income_share) }) : "",
              ]
                .filter(Boolean)
                .join(" · ")
            : t("tiles.incomeNone")
        }
      />
      <Stat
        label={t("tiles.unnecessary")}
        value={formatMoney(tiles.unnecessary)}
        meta={[
          t("tiles.unnecessaryMeta"),
          total > 0 ? t("tiles.unnecessaryShare", { share: tiles.unnecessary.minor / total }) : "",
        ]
          .filter(Boolean)
          .join(" · ")}
      />
      {tiles.last_month ? (
        <Stat
          label={t("tiles.last")}
          value={formatMoney(tiles.last_total)}
          meta={
            <>
              <span className="block">
                {formatMonth(tiles.last_month)}
                {tiles.last_partial ? ` · ${t("tiles.lastPartial")}` : ""}
              </span>
              {change !== null && base > 0 ? (
                <span className="block">
                  <span aria-hidden="true">{change >= 0 ? "▲ " : "▼ "}</span>
                  {change >= 0
                    ? t("tiles.lastUp", { count: base, share: Math.abs(change) })
                    : t("tiles.lastDown", { count: base, share: Math.abs(change) })}
                </span>
              ) : null}
            </>
          }
        />
      ) : null}
    </section>
  );
}

interface LeftOutProps {
  params: URLSearchParams;
  labels: Labels;
  onAdd: (kind: string) => void;
}

/** "Toplama dahil değil": the kinds the spending leaves out, with their totals under the same filters. */
export function LeftOut({ params, labels, onAdd }: LeftOutProps) {
  const { t } = useTranslation("insights");
  const chosen = params.getAll("kind").length > 0;
  const totals = useKindTotals(spendingQuery(params), LEFT_OUT, !chosen);
  if (chosen) {
    return null; // the user chose the kinds: nothing is left out behind their back
  }
  const found = LEFT_OUT.map((kind, index) => ({ kind, totals: totals[index]?.data?.totals }))
    .filter((item) => item.totals && Math.abs(item.totals.money_out.minor) >= 100) // a lira at least
    .map((item) => ({ kind: item.kind, amount: formatMoney(item.totals!.money_out) }));
  if (found.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className={SMALL}>{t("excluded.label")}</span>
      {found.map(({ kind, amount }) => {
        const name = labelOf(labels, "TransactionKind", kind);
        return (
          <button
            key={kind}
            type="button"
            aria-label={t("excluded.addOf", { kind: name, amount })}
            onClick={() => onAdd(kind)}
            className={
              "min-h-8 rounded-md border border-dashed border-zinc-400 px-2 text-xs text-zinc-800 hover:bg-zinc-100 " +
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 " +
              "dark:border-zinc-500 dark:text-zinc-200 dark:hover:bg-zinc-800"
            }
          >
            {t("excluded.add", { kind: name, amount })}
          </button>
        );
      })}
    </div>
  );
}
