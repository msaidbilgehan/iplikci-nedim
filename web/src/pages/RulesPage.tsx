// The Rules screen (F15): the categories under their groups with their necessity and the commitment categories, the
// payments that ended, the merchants weighed apart from their category, a merchant rule to add, and in the detailed
// view the user's rule file itself; its earlier versions are listed. Every change shows the rows it moves before it is
// written, and nothing is written that the program cannot build the rules from.

import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useCategoryRules, useLabels } from "../api/queries";
import type { CategoryRules, Labels } from "../api/types";
import { useView } from "../components/Preferences";
import { Failure, Loading } from "../components/QueryState";
import { CategoriesCard } from "../components/rules/CategoriesCard";
import { EndedCard } from "../components/rules/EndedCard";
import { FileCard, HistoryCard } from "../components/rules/FileCard";
import { MerchantRuleCard } from "../components/rules/MerchantRuleCard";
import { NecessityCard } from "../components/rules/NecessityCard";
import { PageHeader } from "../components/ui/PageHeader";

export default function RulesPage() {
  const { t } = useTranslation("rules");
  const rules = useCategoryRules();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {rules.isPending ? <Loading /> : null}
      {rules.isError ? <Failure error={rules.error} onRetry={() => void rules.refetch()} /> : null}
      {rules.data ? <Cards rules={rules.data} labels={labels} /> : null}
    </div>
  );
}

function Cards({ rules, labels }: { rules: CategoryRules; labels: Labels }) {
  const { view } = useView();
  const [params] = useSearchParams();
  // Opened for a merchant (the Yapılacaklar screen's "Kural ekle"): the form starts again with each one.
  const asked = params.get("isyeri")?.trim() ?? "";
  const merchant = <MerchantRuleCard key={asked} categories={rules.categories} labels={labels} asked={asked} />;
  const categories = <CategoriesCard categories={rules.categories} labels={labels} />;
  const ended = <EndedCard ended={rules.ended} labels={labels} />;
  const necessity = <NecessityCard merchants={rules.merchant_necessity} labels={labels} />;
  const history = <HistoryCard history={rules.history} hasFile={rules.content !== ""} />;
  if (view === "simple") {
    // Two columns that do not move as a card grows: the forms on one side, what the rules hold on the other.
    return (
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          {merchant}
          {ended}
          {necessity}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          {categories}
          {history}
        </div>
      </div>
    );
  }
  // The detailed view's tables and the file need the screen's width: one card under the other.
  return (
    <div className="grid items-start gap-4">
      {merchant}
      {categories}
      {ended}
      {necessity}
      <FileCard content={rules.content} labels={labels} />
      {history}
    </div>
  );
}
