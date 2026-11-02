// The Döviz screen (F12, its Phase 6 part): the net worth in TL, euros, dollars and grams of gold, how the assets
// spread over currencies, every asset and debt with its value at the rate the documents print, and the rates
// themselves. Only the documents' own rates are used; the central banks' rates come in Phase 8.

import { useTranslation } from "react-i18next";

import { useFxRates, useHoldings, useLabels } from "../api/queries";
import type { Holdings, Labels } from "../api/types";
import { AssetTable } from "../components/fx/AssetTable";
import { currencyName } from "../components/fx/currency";
import { RatesCard } from "../components/fx/RatesCard";
import { SpreadCard } from "../components/fx/SpreadCard";
import { WorthSummary } from "../components/fx/WorthSummary";
import { Empty, Failure, Loading } from "../components/QueryState";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep, Say } from "../components/ui/Say";
import { formatMoney } from "../lib/format";

const ACCOUNTS = { screen: "accounts", id: "", query: {} } as const;
const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;

export default function FxPage() {
  const { t } = useTranslation("fx");
  const holdings = useHoldings();
  const rates = useFxRates();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {holdings.isPending ? <Loading /> : null}
      {holdings.isError ? <Failure error={holdings.error} onRetry={() => void holdings.refetch()} /> : null}
      {holdings.data ? <Worth found={holdings.data} labels={labels} /> : null}
      {rates.isPending ? <Loading /> : null}
      {rates.isError ? <Failure error={rates.error} onRetry={() => void rates.refetch()} /> : null}
      {rates.data ? <RatesCard found={rates.data} labels={labels} /> : null}
    </div>
  );
}

function Worth({ found, labels }: { found: Holdings; labels: Labels }) {
  const { t } = useTranslation("fx");
  if (found.holdings.length === 0 && found.worth.left_out.length === 0) {
    return (
      <Empty title={t("empty")}>
        <p>{t("emptyText")}</p>
        <NextStep step={{ link: DOCUMENTS, label: t("emptyNext") }} className="mt-2" />
      </Empty>
    );
  }
  const largest = found.spread.find((s) => s.share !== null);
  return (
    <>
      <div className="flex flex-col gap-2">
        <Say next={{ link: ACCOUNTS, label: t("next") }}>
          {t("say", { total: formatMoney(found.worth.total) })}
          {largest?.share != null
            ? ` ${t("sayShare", { share: largest.share, currency: currencyName(t, largest.currency) })}`
            : ""}
        </Say>
        <WorthSummary found={found} />
      </div>
      {found.spread.length > 0 ? <SpreadCard spread={found.spread} /> : null}
      {found.holdings.length > 0 ? <AssetTable assets={found.holdings} labels={labels} note={found.note} /> : null}
    </>
  );
}
