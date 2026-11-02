// "İşlemler" (the MVP report's transactions card): how many rows the cards count and what they add up to, the İşlemler
// screen with the same filters — the spending's kinds written out when none is chosen, so the list shows the very rows
// the cards count — and those rows as CSV.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Spending } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney } from "../../lib/format";
import { isReady } from "../navigation";
import { Card } from "../ui/Card";
import { ArrowRightIcon } from "../ui/Icons";
import { STEP } from "../ui/Say";
import { rowsFilters } from "./query";

const LINK_BUTTON = cn(
  "inline-flex min-h-11 items-center rounded-md border px-3 text-sm font-medium",
  "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export function RowsCard({ found, params }: { found: Spending; params: URLSearchParams }) {
  const { t } = useTranslation("insights");
  const query = rowsFilters(params).toString();
  return (
    <Card title={t("rows.title")}>
      <p className="text-sm">
        {t("rows.say", { count: found.tiles.count, amount: formatMoney(found.tiles.total) })}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        {isReady("transactions") ? (
          <Link to={`/islemler?${query}`} className={STEP}>
            {t("rows.open")}
            <ArrowRightIcon className="size-4 shrink-0" />
          </Link>
        ) : null}
        <a href={`/api/transactions.csv?${query}`} download aria-label={t("rows.csvOf")} className={LINK_BUTTON}>
          {t("rows.csv")}
        </a>
      </div>
    </Card>
  );
}
