// The merchants whose spending the user weighs apart from their category (F15, `_gereklilik_işyeri`): each with its own
// level, changed in the form below or given back to its category's level.

import { type FormEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Labels, MerchantNecessity, Necessity, RuleChange } from "../../api/types";
import { cn } from "../../lib/cn";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { ChangePanel, ChangePreview, MUTED, Notice, useNotice, useRuleEdit, useSavedText } from "./ChangePreview";
import { control, type Errors, Field, focusFirst } from "./fields";
import { LEVELS } from "./MerchantRuleCard";

type NecessityField = "merchant" | "level";
const ORDER: readonly NecessityField[] = ["merchant", "level"];

interface NecessityCardProps {
  merchants: readonly MerchantNecessity[];
  labels: Labels;
}

export function NecessityCard({ merchants, labels }: NecessityCardProps) {
  const { t } = useTranslation("rules");
  const panel = useRuleEdit();
  const form = useRuleEdit();
  const notice = useNotice();
  const savedText = useSavedText();
  const [asked, setAsked] = useState<string | null>(null);
  const [merchant, setMerchant] = useState("");
  const [level, setLevel] = useState<Necessity | "">("");
  const [errors, setErrors] = useState<Errors<NecessityField>>({});
  const heading = useId();
  const ids: Record<NecessityField, string> = { merchant: useId(), level: useId() };
  const levelField = useRef<HTMLSelectElement>(null);

  function giveBack(name: string) {
    notice.clear();
    panel.ask({ action: "necessity", merchant: name, necessity: null });
    setAsked(name);
  }

  /** The form, filled with a listed merchant: its level is what is left to choose. */
  function edit(entry: MerchantNecessity) {
    setMerchant(entry.merchant);
    setLevel(entry.necessity === "unknown" ? "" : entry.necessity);
    setErrors({});
    form.forget();
    notice.clear();
    levelField.current?.focus();
  }

  function close() {
    setAsked(null);
    panel.forget();
  }

  function changed(field: NecessityField) {
    if (errors[field]) {
      setErrors({ ...errors, [field]: undefined });
    }
    form.forget();
    notice.clear();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found: Errors<NecessityField> = {};
    if (!merchant.trim()) {
      found.merchant = t("necessity.needMerchant");
    }
    if (!level) {
      found.level = t("necessity.needLevel");
    }
    setErrors(found);
    if (!level || Object.keys(found).length > 0) {
      focusFirst(ORDER, found, ids);
      return;
    }
    form.ask({ action: "necessity", merchant: merchant.trim(), necessity: level });
  }

  function savedFromForm(change: RuleChange) {
    setMerchant("");
    setLevel("");
    notice.show(savedText(change));
  }

  function savedFromPanel(change: RuleChange) {
    close();
    notice.show(savedText(change));
  }

  const actions = (entry: MerchantNecessity) => (
    <span className="flex flex-wrap justify-end gap-2">
      <Button
        variant="secondary"
        className="px-3"
        aria-label={`${t("necessity.edit")}: ${entry.merchant}`}
        onClick={() => edit(entry)}
      >
        {t("necessity.edit")}
      </Button>
      <Button
        variant="secondary"
        className="px-3"
        aria-label={`${t("necessity.back")}: ${entry.merchant}`}
        onClick={() => giveBack(entry.merchant)}
      >
        {t("necessity.back")}
      </Button>
    </span>
  );

  return (
    <Card title={t("necessity.title")}>
      <Say>{merchants.length > 0 ? t("necessity.say", { count: merchants.length }) : t("necessity.sayNone")}</Say>
      <div className="flex flex-col gap-4">
        {merchants.length === 0 ? (
          <Detailed>
            <p className={MUTED}>{t("necessity.empty")}</p>
          </Detailed>
        ) : null}
        {merchants.length > 0 ? (
          <>
            <Simple>
              <ul className="flex flex-col">
                {merchants.map((entry) => (
                  <li
                    key={entry.merchant}
                    className={cn(
                      "flex flex-wrap items-center justify-between gap-2 py-1.5 text-sm",
                      "border-b border-zinc-100 last:border-b-0 dark:border-zinc-800",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block font-medium break-words">{entry.merchant}</span>
                      <span className="block text-xs text-zinc-600 dark:text-zinc-300">
                        {labelOf(labels, "Necessity", entry.necessity)}
                      </span>
                    </span>
                    {actions(entry)}
                  </li>
                ))}
              </ul>
            </Simple>
            <Detailed>
              <Table>
                <caption className="sr-only">{t("necessity.caption")}</caption>
                <thead>
                  <tr>
                    <Th>{t("necessity.merchant")}</Th>
                    <Th>{t("necessity.level")}</Th>
                    <Th>
                      <span className="sr-only">{t("necessity.action")}</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {merchants.map((entry) => (
                    <tr key={entry.merchant}>
                      <Td className="break-words">{entry.merchant}</Td>
                      <Td>{labelOf(labels, "Necessity", entry.necessity)}</Td>
                      <Td>{actions(entry)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Detailed>
          </>
        ) : null}
        <Notice notice={notice} />
        <div className="flex flex-col gap-3 border-t border-zinc-200 pt-4 dark:border-zinc-700">
          <form noValidate onSubmit={submit} aria-labelledby={heading} className="flex flex-col gap-3">
            <h3 id={heading} className="text-sm font-semibold">
              {t("necessity.add")}
            </h3>
            <p className={MUTED}>{t("necessity.addText")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field id={ids.merchant} label={t("necessity.merchant")} error={errors.merchant}>
                <input
                  type="text"
                  value={merchant}
                  maxLength={120}
                  autoComplete="off"
                  onChange={(event) => {
                    setMerchant(event.target.value);
                    changed("merchant");
                  }}
                  {...control(ids.merchant, { error: errors.merchant })}
                />
              </Field>
              <Field id={ids.level} label={t("necessity.level")} error={errors.level}>
                <select
                  ref={levelField}
                  value={level}
                  onChange={(event) => {
                    setLevel(LEVELS.find((option) => option === event.target.value) ?? "");
                    changed("level");
                  }}
                  {...control(ids.level, { error: errors.level })}
                >
                  <option value="">{t("necessity.chooseLevel")}</option>
                  {LEVELS.map((option) => (
                    <option key={option} value={option}>
                      {labelOf(labels, "Necessity", option)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Button type="submit" variant="secondary" className="self-start" disabled={form.preview.isPending}>
              {t("necessity.preview")}
            </Button>
          </form>
          <ChangePreview flow={form} labels={labels} onSaved={savedFromForm} />
        </div>
      </div>
      <ChangePanel
        open={asked !== null}
        title={t("panel.necessityBack", { merchant: asked ?? "" })}
        text={t("panel.necessityBackText")}
        flow={panel}
        labels={labels}
        onSaved={savedFromPanel}
        onClose={close}
      />
    </Card>
  );
}
