// "İşyeri kuralı ekle" (F15): a merchant named with its patterns under a category, and its own level of necessity when
// it differs from its category's. The Yapılacaklar screen's "Kural ekle" opens the screen with the merchant's name in
// the address (?isyeri=), the form filled with it and the category to choose.

import { type FormEvent, useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Category, Labels, MerchantRule, Necessity, RuleChange } from "../../api/types";
import { labelOf } from "../../lib/labels";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { ChangePreview, Notice, useNotice, useRuleEdit, useSavedText } from "./ChangePreview";
import { control, type Errors, Field, focusFirst } from "./fields";

// The levels a merchant may have of its own; "Belirsiz" is what no rule saying anything means.
export const LEVELS: readonly Necessity[] = ["required", "optional", "unnecessary"];
// The service's limits (MerchantRuleIn): a pattern's length and how many a merchant has.
const PATTERN_MAX = 200;
const PATTERNS_MAX = 20;
// The Yapılacaklar screen's merchants no rule names, where a rule is made from.
const UNCATEGORIZED = { screen: "todo", id: "uncategorized", query: {} } as const;

type MerchantField = "merchant" | "patterns" | "category";
const ORDER: readonly MerchantField[] = ["merchant", "patterns", "category"];

/** The categories under their groups, in the rule file's order. */
export function byGroup(categories: readonly Category[]): Array<[string, Category[]]> {
  const groups = new Map<string, Category[]>();
  for (const category of categories) {
    groups.set(category.group, [...(groups.get(category.group) ?? []), category]);
  }
  return [...groups];
}

/** The patterns as typed, comma by comma. */
function patternsOf(text: string): string[] {
  return text
    .split(",")
    .map((pattern) => pattern.trim())
    .filter(Boolean);
}

interface MerchantRuleCardProps {
  categories: readonly Category[];
  labels: Labels;
  asked: string; // the merchant the screen was opened for ("" for none): its name and a first pattern
}

export function MerchantRuleCard({ categories, labels, asked }: MerchantRuleCardProps) {
  const { t } = useTranslation("rules");
  const flow = useRuleEdit();
  const notice = useNotice();
  const savedText = useSavedText();
  const [merchant, setMerchant] = useState(asked);
  const [patterns, setPatterns] = useState(asked);
  const [category, setCategory] = useState("");
  const [necessity, setNecessity] = useState<Necessity | "">("");
  const [errors, setErrors] = useState<Errors<MerchantField>>({});
  const ids: Record<MerchantField | "necessity", string> = {
    merchant: useId(),
    patterns: useId(),
    category: useId(),
    necessity: useId(),
  };

  // Opened for a merchant: what is left to do is choosing its category.
  const categoryId = ids.category;
  useEffect(() => {
    if (asked) {
      document.getElementById(categoryId)?.focus();
    }
  }, [asked, categoryId]);

  function changed(field: MerchantField | "necessity") {
    if (field !== "necessity" && errors[field]) {
      setErrors({ ...errors, [field]: undefined });
    }
    flow.forget();
    notice.clear();
  }

  function rule(): MerchantRule | null {
    const list = patternsOf(patterns);
    const found: Errors<MerchantField> = {};
    if (!merchant.trim()) {
      found.merchant = t("merchant.needName");
    }
    if (list.length === 0) {
      found.patterns = t("merchant.needPatterns");
    } else if (list.length > PATTERNS_MAX) {
      found.patterns = t("merchant.tooManyPatterns");
    } else if (list.some((pattern) => pattern.length > PATTERN_MAX)) {
      found.patterns = t("merchant.longPattern");
    }
    if (!category) {
      found.category = t("merchant.needCategory");
    }
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirst(ORDER, found, ids);
      return null;
    }
    return {
      action: "merchant",
      category,
      merchant: merchant.trim(),
      patterns: list,
      ...(necessity ? { necessity } : {}),
    };
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const made = rule();
    if (made) {
      flow.ask(made);
    }
  }

  function saved(change: RuleChange) {
    setMerchant("");
    setPatterns("");
    setCategory("");
    setNecessity("");
    notice.show(savedText(change));
  }

  return (
    <Card title={t("merchant.title")}>
      <Say next={{ link: UNCATEGORIZED, label: t("merchant.next") }}>{t("merchant.say")}</Say>
      <div className="flex flex-col gap-4">
        <form noValidate onSubmit={submit} className="flex flex-col gap-3">
          <Field id={ids.merchant} label={t("merchant.name")} hint={t("merchant.nameHint")} error={errors.merchant}>
            <input
              type="text"
              value={merchant}
              maxLength={120}
              autoComplete="off"
              onChange={(event) => {
                setMerchant(event.target.value);
                changed("merchant");
              }}
              {...control(ids.merchant, { hint: true, error: errors.merchant })}
            />
          </Field>
          <Field
            id={ids.patterns}
            label={t("merchant.patterns")}
            hint={t("merchant.patternsHint")}
            error={errors.patterns}
          >
            <input
              type="text"
              value={patterns}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => {
                setPatterns(event.target.value);
                changed("patterns");
              }}
              {...control(ids.patterns, { hint: true, error: errors.patterns })}
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id={ids.category} label={t("merchant.category")} error={errors.category}>
              <select
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  changed("category");
                }}
                {...control(ids.category, { error: errors.category })}
              >
                <option value="">{t("merchant.chooseCategory")}</option>
                {byGroup(categories).map(([group, members]) => (
                  <optgroup key={group} label={group}>
                    {members.map((member) => (
                      <option key={member.name} value={member.name}>
                        {member.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </Field>
            <Field id={ids.necessity} label={t("merchant.necessity")}>
              <select
                value={necessity}
                onChange={(event) => {
                  setNecessity(LEVELS.find((level) => level === event.target.value) ?? "");
                  changed("necessity");
                }}
                {...control(ids.necessity, {})}
              >
                <option value="">{t("merchant.categoryLevel")}</option>
                {LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {labelOf(labels, "Necessity", level)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Button type="submit" variant="secondary" className="self-start" disabled={flow.preview.isPending}>
            {t("merchant.preview")}
          </Button>
        </form>
        <ChangePreview flow={flow} labels={labels} onSaved={saved} />
        <Notice notice={notice} />
      </div>
    </Card>
  );
}
