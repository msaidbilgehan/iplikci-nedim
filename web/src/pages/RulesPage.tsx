// The Rules screen (F15), one tab each (?bolum=…): a merchant rule to add, the categories under their groups with their
// necessity and the commitment categories, the payments that ended, the merchants weighed apart from their category,
// and the rule file's earlier versions, with the file itself in the detailed view. Every change shows the rows it moves before it is
// written, and nothing is written that the program cannot build the rules from.

import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useCategoryRules, useLabels } from "../api/queries";
import type { CategoryRules, Labels } from "../api/types";
import { Detailed } from "../components/Preferences";
import { Failure, Loading } from "../components/QueryState";
import { CategoriesCard } from "../components/rules/CategoriesCard";
import { EndedCard } from "../components/rules/EndedCard";
import { FileCard, HistoryCard } from "../components/rules/FileCard";
import { MerchantRuleCard } from "../components/rules/MerchantRuleCard";
import { NecessityCard } from "../components/rules/NecessityCard";
import { PageHeader } from "../components/ui/PageHeader";
import { SectionCount, SectionTabs } from "../components/ui/SectionTabs";

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
  const { t } = useTranslation("rules");
  const [params] = useSearchParams();
  // Opened for a merchant (the Yapılacaklar screen's "Kural ekle"): the form starts again with each one.
  const asked = params.get("isyeri")?.trim() ?? "";
  return (
    <SectionTabs
      label={t("sections.label")}
      sections={[
        {
          id: "isyeri",
          label: t("sections.merchant"),
          content: () => (
            <MerchantRuleCard key={asked} categories={rules.categories} labels={labels} asked={asked} />
          ),
        },
        {
          id: "kategoriler",
          label: t("sections.categories"),
          content: () => <CategoriesCard categories={rules.categories} labels={labels} />,
        },
        {
          id: "biten",
          label: t("sections.ended"),
          badge: <SectionCount count={rules.ended.length} />,
          content: () => <EndedCard ended={rules.ended} labels={labels} />,
        },
        {
          id: "gereklilik",
          label: t("sections.necessity"),
          content: () => <NecessityCard merchants={rules.merchant_necessity} labels={labels} />,
        },
        {
          id: "dosya",
          label: t("sections.file"),
          // The file itself is the detailed view's: the simple view keeps its earlier versions alone.
          content: () => (
            <>
              <Detailed>
                <FileCard content={rules.content} labels={labels} />
              </Detailed>
              <HistoryCard history={rules.history} hasFile={rules.content !== ""} />
            </>
          ),
        },
      ]}
    />
  );
}
