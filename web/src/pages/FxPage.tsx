// The Döviz screen (F12) in four parts, one shown at a time (?bolum=): the assets — the net worth in TL, euros, dollars
// and grams of gold, how they spread over currencies, every asset and debt with its value; the rates — TCMB's, ECB's
// where TCMB could not be reached, else the documents' own, with their days; what the banks' rates cost against TCMB's
// (kur makası); and the income that comes in a foreign currency. A part asks for its data only when it is opened.

import { useTranslation } from "react-i18next";

import { useFxIncome, useFxRates, useFxSpread, useHoldings, useLabels } from "../api/queries";
import type { Holdings, Labels } from "../api/types";
import { AssetTable } from "../components/fx/AssetTable";
import { CostCard } from "../components/fx/CostCard";
import { currencyName } from "../components/fx/currency";
import { IncomeCard } from "../components/fx/IncomeCard";
import { RatesCard } from "../components/fx/RatesCard";
import { SpreadCard } from "../components/fx/SpreadCard";
import { WorthSummary } from "../components/fx/WorthSummary";
import { Empty, Failure, Loading } from "../components/QueryState";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep, Say } from "../components/ui/Say";
import { SectionTabs } from "../components/ui/SectionTabs";
import { formatMoney } from "../lib/format";

const ACCOUNTS = { screen: "accounts", id: "", query: {} } as const;
const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;

export default function FxPage() {
  const { t } = useTranslation("fx");
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <SectionTabs
        label={t("sections")}
        sections={[
          { id: "varliklar", label: t("section.assets"), content: () => <AssetsSection labels={labels} /> },
          { id: "kurlar", label: t("section.rates"), content: () => <RatesSection labels={labels} /> },
          { id: "kur-makasi", label: t("section.cost"), content: () => <CostSection labels={labels} /> },
          { id: "doviz-geliri", label: t("section.income"), content: () => <IncomeSection /> },
        ]}
      />
    </div>
  );
}

function AssetsSection({ labels }: { labels: Labels }) {
  const holdings = useHoldings();
  if (holdings.isPending) {
    return <Loading />;
  }
  if (holdings.isError) {
    return <Failure error={holdings.error} onRetry={() => void holdings.refetch()} />;
  }
  return <Worth found={holdings.data} labels={labels} />;
}

function RatesSection({ labels }: { labels: Labels }) {
  const rates = useFxRates();
  if (rates.isPending) {
    return <Loading />;
  }
  if (rates.isError) {
    return <Failure error={rates.error} onRetry={() => void rates.refetch()} />;
  }
  return <RatesCard found={rates.data} labels={labels} />;
}

function CostSection({ labels }: { labels: Labels }) {
  const spread = useFxSpread();
  if (spread.isPending) {
    return <Loading />;
  }
  if (spread.isError) {
    return <Failure error={spread.error} onRetry={() => void spread.refetch()} />;
  }
  return <CostCard found={spread.data} labels={labels} />;
}

function IncomeSection() {
  const income = useFxIncome();
  if (income.isPending) {
    return <Loading />;
  }
  if (income.isError) {
    return <Failure error={income.error} onRetry={() => void income.refetch()} />;
  }
  return <IncomeCard found={income.data} />;
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
