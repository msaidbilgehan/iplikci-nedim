// The categories under their groups (F15), each with its group's colour, its level of necessity and whether it is a
// commitment category (`_düzenli`: its payments are regular even when the amount changes), which the user turns on or
// off here. The simple view lists them group by group; the detailed view is one table, with whose rule names each.

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Category, Labels, RuleChange } from "../../api/types";
import { cn } from "../../lib/cn";
import { labelOf } from "../../lib/labels";
import { SLOT_BG, slotOf } from "../charts/palette";
import { Simple, Detailed } from "../Preferences";
import { Empty } from "../QueryState";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { ChangePanel, MUTED, Notice, useNotice, useRuleEdit, useSavedText } from "./ChangePreview";
import { byGroup } from "./MerchantRuleCard";

interface CategoriesCardProps {
  categories: readonly Category[];
  labels: Labels;
}

export function CategoriesCard({ categories, labels }: CategoriesCardProps) {
  const { t } = useTranslation("rules");
  const flow = useRuleEdit();
  const notice = useNotice();
  const savedText = useSavedText();
  const [asked, setAsked] = useState<Category | null>(null);
  const groups = byGroup(categories);
  const regular = categories.filter((category) => category.regular).length;

  function toggle(category: Category) {
    notice.clear();
    flow.ask({ action: "commitment", category: category.name, on: !category.regular });
    setAsked(category);
  }

  function close() {
    setAsked(null);
    flow.forget();
  }

  function saved(change: RuleChange) {
    close();
    notice.show(savedText(change));
  }

  const necessityOf = (category: Category) => labelOf(labels, "Necessity", category.necessity ?? "unknown");
  const button = (category: Category) => {
    const label = category.regular ? t("categories.dropCommitment") : t("categories.makeCommitment");
    // Its category in its name, among many alike; browsers join a hidden part of the text unevenly.
    return (
      <Button
        variant="secondary"
        className="shrink-0 px-3"
        aria-label={`${label}: ${category.name}`}
        onClick={() => toggle(category)}
      >
        {label}
      </Button>
    );
  };

  return (
    <Card title={t("categories.title")}>
      <Say>{t("categories.say", { count: categories.length, groups: groups.length, regular })}</Say>
      <div className="flex flex-col gap-3">
        <p className={MUTED}>{t("categories.intro")}</p>
        <Notice notice={notice} />
        {categories.length === 0 ? <Empty title={t("categories.empty")} /> : null}
        <Simple>
          <div className="flex flex-col gap-4">
            {groups.map(([group, members]) => (
              <div key={group}>
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <Swatch slot={members[0]?.slot ?? 0} />
                  {group}
                </h3>
                <ul className="mt-1 flex flex-col">
                  {members.map((category) => (
                    <li
                      key={category.name}
                      className={cn(
                        "flex items-center justify-between gap-3 py-1.5 text-sm",
                        "border-b border-zinc-100 last:border-b-0 dark:border-zinc-800",
                      )}
                    >
                      {/* The name wraps, never the button: each keeps its row's end, so the buttons line up. */}
                      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="break-words">{category.name}</span>
                        <span className="text-xs text-zinc-600 dark:text-zinc-300">{necessityOf(category)}</span>
                        {category.regular ? <Badge tone="neutral">{t("categories.isCommitment")}</Badge> : null}
                      </span>
                      {button(category)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Simple>
        <Detailed>
          {categories.length > 0 ? (
            <Table>
              <caption className="sr-only">{t("categories.caption")}</caption>
              <thead>
                <tr>
                  <Th>{t("categories.group")}</Th>
                  <Th>{t("categories.name")}</Th>
                  <Th>{t("categories.necessity")}</Th>
                  <Th>{t("categories.commitment")}</Th>
                  <Th>{t("categories.source")}</Th>
                  <Th>
                    <span className="sr-only">{t("categories.change")}</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {categories.map((category) => (
                  <tr key={category.name}>
                    <Td>
                      <span className="inline-flex items-center gap-2">
                        <Swatch slot={category.slot} />
                        {category.group}
                      </span>
                    </Td>
                    <Td className="break-words">{category.name}</Td>
                    <Td>{necessityOf(category)}</Td>
                    <Td>{category.regular ? t("categories.yes") : t("categories.no")}</Td>
                    <Td>{labelOf(labels, "RuleLayer", category.own ? "own" : "shipped")}</Td>
                    <Td className="text-right">{button(category)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : null}
        </Detailed>
      </div>
      <ChangePanel
        open={asked !== null}
        title={
          asked?.regular
            ? t("panel.commitmentOff", { category: asked.name })
            : t("panel.commitmentOn", { category: asked?.name ?? "" })
        }
        text={asked?.regular ? t("panel.commitmentOffText") : t("panel.commitmentOnText")}
        flow={flow}
        labels={labels}
        onSaved={saved}
        onClose={close}
      />
    </Card>
  );
}

/** A group's colour, beside its name: the name says it, the colour only repeats it. */
function Swatch({ slot }: { slot: number }) {
  return <span aria-hidden="true" className={cn("size-3 shrink-0 rounded-sm", SLOT_BG[slotOf(slot)])} />;
}
