// The month's pace (F05's "Ay içi tempo", F06's "bu ay ile tipik ay"): what was spent so far, the part only receipts
// and notices show yet, a bar against the typical month with a mark where it stood on the same day, the typical
// month's same days and the whole of it, and what the numbers rest on. The typical month comes from complete months
// only; without three of them there is nothing to measure against (docs/domain/interpretation.md).

import { useTranslation } from "react-i18next";

import type { Pace } from "../api/types";
import { formatMoney } from "../lib/format";
import { Money } from "./ui/Money";
import { Term } from "./ui/Term";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

/** The bar: spent so far against the typical month. The numbers are written beside it, so it is hidden from readers. */
export function PaceMeter({ pace }: { pace: Pace }) {
  if (pace.typical === null || pace.typical.minor <= 0) {
    return null;
  }
  const scale = Math.max(pace.typical.minor, pace.spent.minor);
  const share = (minor: number) => `${Math.min(100, Math.max(0, (minor / scale) * 100))}%`;
  return (
    <div aria-hidden="true" className="relative my-3 h-3 rounded-full bg-zinc-200 dark:bg-zinc-700">
      <div className="h-3 rounded-full bg-chart-accent" style={{ width: share(pace.spent.minor) }} />
      {pace.by_day ? (
        <div
          className="absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-zinc-900 dark:bg-zinc-100"
          style={{ left: share(pace.by_day.minor) }}
        />
      ) : null}
    </div>
  );
}

export function PaceFigures({ pace }: { pace: Pace }) {
  const { t } = useTranslation();
  return (
    <>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">{t("pace.spent", { month: pace.month })}</p>
      <p className="text-2xl font-semibold">
        <Money value={pace.spent} />
      </p>
      {pace.provisional.minor > 0 ? (
        <p className={SMALL}>
          {t("pace.provisional", { amount: formatMoney(pace.provisional) })} <Term id="provisional" />
        </p>
      ) : null}
      <PaceMeter pace={pace} />
      {pace.typical && pace.by_day ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-zinc-600 dark:text-zinc-300">{t("pace.byDay")}</dt>
          <dd className="tabular-nums">{formatMoney(pace.by_day)}</dd>
          <dt className="text-zinc-600 dark:text-zinc-300">
            <Term id="typicalMonth">{t("pace.typical")}</Term>
          </dt>
          <dd className="tabular-nums">{formatMoney(pace.typical)}</dd>
        </dl>
      ) : (
        <p className="text-sm">{t("pace.noTypical")}</p>
      )}
      <p className={`mt-2 ${SMALL}`}>{pace.note}</p>
    </>
  );
}
