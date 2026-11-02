// "Değerlendirme ve strateji" (F10, the MVP report's first card): the highlights, each with its window and numbers and
// the rows it rests on, the steps with the money they free a month where the data prices it, and the monthly budget —
// the typical month today against the one the steps lead to. It reads the complete months; no filter changes it.

import type { TFunction } from "i18next";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { BudgetLine, Insights, Labels, Tone as FindingTone } from "../../api/types";
import { formatDay, formatFlow, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { percentOrLess } from "../../lib/turkish";
import { Detailed, Simple } from "../Preferences";
import { Badge, type Tone } from "../ui/Badge";
import { Card } from "../ui/Card";
import { NextStep } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { shiftMonth } from "./query";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const TONES: Record<FindingTone, Tone> = { attention: "warning", info: "neutral", good: "good" };

/** What the interpretation reads: its complete months, the balances' day, and the months it left out. */
export function windowOf(found: Insights, t: TFunction<"insights">): string {
  const { months, as_of: asOf } = found.window;
  const first = months[0];
  const last = months.at(-1);
  if (!first || !last) {
    return "";
  }
  const said = t("interpretation.window", {
    count: months.length,
    from: formatMonth(first),
    to: formatMonth(last),
    day: formatDay(asOf),
  });
  const skipped: string[] = [];
  for (let month = first; month <= asOf.slice(0, 7); month = shiftMonth(month, 1)) {
    if (!months.includes(month)) {
      skipped.push(formatMonth(month));
    }
  }
  return skipped.length ? `${said} ${t("interpretation.skipped", { months: skipped.join(", ") })}` : said;
}

function Subhead({ id, children }: { id: string; children: string }) {
  return (
    <h3 id={id} className="text-base font-semibold">
      {children}
    </h3>
  );
}

export function Interpretation({ found, labels }: { found: Insights; labels: Labels }) {
  const { t } = useTranslation("insights");
  const findings = useId();
  const steps = useId();
  const budget = useId();
  return (
    <Card title={t("interpretation.title")}>
      <p className={`mb-4 ${SMALL}`}>{windowOf(found, t)}</p>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section aria-labelledby={findings} className="flex flex-col gap-2">
          <Subhead id={findings}>{t("interpretation.findings")}</Subhead>
          {found.findings.length === 0 ? <p className="text-sm">{t("interpretation.noFindings")}</p> : null}
          <ul className="flex flex-col gap-3">
            {found.findings.map((finding) => (
              <li key={finding.title} className="flex flex-col items-start gap-1 text-sm">
                <span className="flex flex-wrap items-center gap-2">
                  <Badge tone={TONES[finding.tone]}>{labelOf(labels, "Tone", finding.tone)}</Badge>
                  <strong className="font-semibold">{finding.title}</strong>
                </span>
                <p>{finding.text}</p>
                {/* A finding about the whole picture leads to this screen itself: no step to take there. */}
                {finding.link.screen === "insights" ? null : (
                  <NextStep
                    step={{ link: finding.link, label: t("interpretation.openRows") }}
                    context={finding.title}
                  />
                )}
              </li>
            ))}
          </ul>
        </section>
        <section aria-labelledby={steps} className="flex flex-col gap-2">
          <Subhead id={steps}>{t("interpretation.steps")}</Subhead>
          {found.steps.length === 0 ? <p className="text-sm">{t("interpretation.noSteps")}</p> : null}
          <ol className="flex list-decimal flex-col gap-3 pl-5 text-sm">
            {found.steps.map((step) => (
              <li key={step.title}>
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <strong className="font-semibold">{step.title}</strong>
                  {step.monthly ? (
                    <span className="font-medium text-emerald-800 dark:text-emerald-300">
                      {t("interpretation.monthly", { amount: formatMoney(step.monthly) })}
                    </span>
                  ) : null}
                </span>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
      <section aria-labelledby={budget} className="mt-6 flex flex-col gap-2">
        <Subhead id={budget}>{t("interpretation.budget")}</Subhead>
        <Budget lines={found.budget} />
      </section>
    </Card>
  );
}

/** The budget's lines: the income first, each line's share of it, the plan and the difference; what is left below. */
function Budget({ lines }: { lines: readonly BudgetLine[] }) {
  const { t } = useTranslation("insights");
  const income = lines[0];
  const left = lines.at(-1);
  if (!income || !left || lines.length < 2) {
    return <p className="text-sm">{t("interpretation.budgetNone")}</p>;
  }
  const share = (line: BudgetLine, index: number) =>
    index > 0 && income.now.minor > 0 ? percentOrLess(line.now.minor / income.now.minor) : "–";
  const diff = (line: BudgetLine) => {
    const moved = line.plan.minor - line.now.minor;
    return Math.abs(moved) >= 100
      ? formatFlow({ minor: Math.abs(moved), currency: line.now.currency }, moved > 0 ? "in" : "out")
      : "–";
  };
  const cells = (line: BudgetLine, index: number) => (
    <>
      <Td className="text-right whitespace-nowrap tabular-nums">{formatMoney(line.now)}</Td>
      <Td className="text-right whitespace-nowrap tabular-nums">{share(line, index)}</Td>
      <Td className="text-right whitespace-nowrap tabular-nums">{formatMoney(line.plan)}</Td>
      <Td className="text-right whitespace-nowrap tabular-nums">{diff(line)}</Td>
      <Td className={`min-w-40 ${SMALL}`}>{line.note}</Td>
    </>
  );
  return (
    <>
      <Simple>
        <p className="text-sm">
          {t("interpretation.sayBudget", { plan: formatMoney(left.plan), now: formatMoney(left.now) })}
        </p>
      </Simple>
      <Detailed>
        <p className={SMALL}>{t("interpretation.budgetHint")}</p>
        <Table>
          <caption className="sr-only">{t("interpretation.budgetCaption")}</caption>
          <thead>
            <tr>
              <Th>{t("interpretation.line")}</Th>
              <Th className="text-right">{t("interpretation.now")}</Th>
              <Th className="text-right">{t("interpretation.share")}</Th>
              <Th className="text-right">{t("interpretation.plan")}</Th>
              <Th className="text-right">{t("interpretation.diff")}</Th>
              <Th>{t("interpretation.note")}</Th>
            </tr>
          </thead>
          <tbody>
            {lines.slice(0, -1).map((line, index) => (
              <tr key={line.label}>
                <Th scope="row" className="min-w-48 font-normal text-zinc-900 dark:text-zinc-100">
                  {line.label}
                </Th>
                {cells(line, index)}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <Th scope="row" className="border-b-0 font-semibold text-zinc-900 dark:text-zinc-100">
                {left.label}
              </Th>
              {cells(left, lines.length - 1)}
            </tr>
          </tfoot>
        </Table>
      </Detailed>
    </>
  );
}
