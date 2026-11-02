// A category correction made a rule (F04's "kural olarak", F15): every row whose description has one of the patterns
// gets the category, not only this one. The change is always shown before it is written: the rows it moves, from
// which category to which, some of them, and the rule file's difference. The rule then goes into the user's own rule
// file, the earlier version into its history.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePreviewRule, useSaveRule } from "../../api/queries";
import type { MerchantRule, Row } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Table, Td, Th } from "../ui/Table";

const INPUT = [
  "min-h-11 w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

/**
 * A first pattern for a row: the first word of what the bank printed that is long enough to mean something, without
 * the marks around it ("*ORNEK*"); else the merchant's name. A pattern matches at the start of a word, with Turkish
 * letters and case folded (categorize._compile), so "IYZICO/ORNEKSHOP" finds itself.
 */
export function suggestedPattern(row: Row): string {
  const word = row.description
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ""))
    .find((w) => w.replace(/[^\p{L}\p{N}]/gu, "").length >= 3);
  return word ?? (row.merchant || row.title);
}

interface RuleFormProps {
  row: Row;
  category: string;
  onDone: () => void; // saved or given up: the form closes
}

export function RuleForm({ row, category, onDone }: RuleFormProps) {
  const { t } = useTranslation("transactions");
  const preview = usePreviewRule();
  const save = useSaveRule();
  const [merchant, setMerchant] = useState(row.merchant || row.title);
  const [patterns, setPatterns] = useState(suggestedPattern(row));
  const merchantId = useId();
  const patternsId = useId();
  const hintId = useId();
  const rule = (): MerchantRule => ({
    action: "merchant",
    category,
    merchant: merchant.trim(),
    patterns: patterns
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean),
  });
  const ready = merchant.trim() !== "" && rule().patterns.length > 0;
  const change = preview.data;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (ready) {
      save.reset();
      preview.mutate(rule());
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-md border border-zinc-200 p-3 dark:border-zinc-700">
      <p className="font-medium">{t("rule.title")}</p>
      <p className={SMALL}>{t("rule.intro")}</p>
      <form onSubmit={submit} className="flex flex-col gap-2 text-sm">
        <label htmlFor={merchantId}>{t("rule.merchant")}</label>
        <input
          id={merchantId}
          value={merchant}
          maxLength={120}
          onChange={(event) => {
            setMerchant(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        />
        <label htmlFor={patternsId}>{t("rule.patterns")}</label>
        <input
          id={patternsId}
          value={patterns}
          aria-describedby={hintId}
          onChange={(event) => {
            setPatterns(event.target.value);
            preview.reset();
          }}
          className={INPUT}
        />
        <span id={hintId} className={SMALL}>
          {t("rule.patternsHint")}
        </span>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="secondary" disabled={!ready || preview.isPending}>
            {preview.isPending ? t("rule.previewing") : t("rule.preview")}
          </Button>
          <Button variant="secondary" onClick={onDone}>
            {save.isSuccess ? t("rule.close") : t("rule.cancel")}
          </Button>
        </div>
      </form>
      {preview.isError ? <Alert tone="critical" title={preview.error.message} /> : null}
      {change ? (
        <div aria-live="polite" className="flex flex-col gap-2 text-sm">
          <p className="font-medium">
            {change.changed > 0 ? t("rule.changes", { count: change.changed }) : t("rule.noChange")}
          </p>
          {change.moves.length > 0 ? (
            <ul className="list-disc pl-5">
              {change.moves.map((move) => (
                <li key={`${move.before}-${move.after}`}>
                  {t("rule.move", {
                    before: move.before,
                    after: move.after,
                    count: move.count,
                    total: formatMoney(move.total),
                  })}
                </li>
              ))}
            </ul>
          ) : null}
          {change.examples.length > 0 ? (
            <Table>
              <caption className="text-left text-xs font-medium">{t("rule.examples")}</caption>
              <thead>
                <tr>
                  <Th>{t("table.day")}</Th>
                  <Th>{t("table.title")}</Th>
                  <Th>{t("rule.exampleBefore")}</Th>
                  <Th>{t("rule.exampleAfter")}</Th>
                </tr>
              </thead>
              <tbody>
                {change.examples.map((example) => (
                  <tr key={example.fingerprint}>
                    <Td className="whitespace-nowrap">{formatDay(example.day)}</Td>
                    <Td>{example.description}</Td>
                    <Td>{example.before.category}</Td>
                    <Td>{example.after.category}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : null}
          {change.diff ? (
            <details>
              <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-teal-600">
                {t("rule.diff")}
              </summary>
              <pre className="mt-1 overflow-x-auto rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">{change.diff}</pre>
            </details>
          ) : null}
          <Button
            className="self-start"
            disabled={save.isPending || change.changed === 0}
            onClick={() => save.mutate(rule(), { onSuccess: () => preview.reset() })}
          >
            {save.isPending ? t("rule.saving") : t("rule.save")}
          </Button>
        </div>
      ) : null}
      {/* Saved, the preview is gone: what the rule changed stays said until the form closes. */}
      {save.isSuccess ? <Alert tone="good" title={t("rule.saved", { count: save.data.changed })} live /> : null}
      {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
    </div>
  );
}
