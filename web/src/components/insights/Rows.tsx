// "İşlemler" (the MVP report's transactions card): how many rows the cards count and what they add up to, the İşlemler
// screen with the same filters — the spending's kinds written out when none is chosen, so the list shows the very rows
// the cards count — and those rows as CSV.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Spending } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { isReady } from "../navigation";
import { Card } from "../ui/Card";
import { ArrowRightIcon } from "../ui/Icons";
import { DownloadLink } from "../ui/LinkButton";
import { STEP } from "../ui/Say";
import { rowsFilters } from "./query";

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
        <DownloadLink href={`/api/transactions.csv?${query}`} aria-label={t("rows.csvOf")}>
          {t("rows.csv")}
        </DownloadLink>
      </div>
    </Card>
  );
}
