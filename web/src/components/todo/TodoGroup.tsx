// One kind of to-do (F19) as a card: its name from /api/labels with how much it matters (an icon and a word, never the
// colour alone), what the kind means, and its items with their steps. The simple view lists them; the detailed view
// is a table with how many rows each stands for, their total, its target and the request it would give Claude.

import { useTranslation } from "react-i18next";

import type { Labels, TodoItem, TodoKind } from "../../api/types";
import { cn } from "../../lib/cn";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Badge, type Tone } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Money } from "../ui/Money";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { Steps, type TodoHandlers } from "./Steps";

type Severity = Extract<Tone, "critical" | "warning" | "neutral">;

// How much a kind matters: a statement that does not add up and a reader that no longer knows its bank's format first
// (verification is the safety net), then what leaves data out; the rest is for a better picture. A kind this version
// does not know is neutral.
const SEVERITIES: Partial<Record<string, Severity>> = {
  unverified_statement: "critical",
  format_alarm: "critical",
  unmatched_evidence: "warning",
  missing_documents: "warning",
  unprocessed_document: "warning",
  split_dropped: "warning",
};

export function severityOf(kind: string): Severity {
  return SEVERITIES[kind] ?? "neutral";
}

const MUTED = "text-sm text-zinc-700 dark:text-zinc-300";
const SUMMARY = "cursor-pointer rounded text-xs focus-visible:outline-2 focus-visible:outline-teal-600";

interface TodoGroupProps {
  kind: TodoKind;
  items: readonly TodoItem[];
  labels: Labels;
  handlers: TodoHandlers;
}

export function TodoGroup({ kind, items, labels, handlers }: TodoGroupProps) {
  const { t } = useTranslation("todo");
  const tone = severityOf(kind);
  const label = labelOf(labels, "TodoKind", kind);
  const about = t(`about.${kind}`, { defaultValue: "" });
  return (
    <Card title={label} action={<Badge tone={tone}>{t(`tone.${tone}`)}</Badge>}>
      <div className="flex flex-col gap-3">
        {about ? <p className={MUTED}>{about}</p> : null}
        <Simple>
          <ul className="flex flex-col">
            {items.map((item) => (
              <li
                key={item.key}
                className={cn(
                  "flex flex-col gap-2 border-b border-zinc-100 py-3 last:border-b-0 dark:border-zinc-800",
                  item.ignored && "opacity-80",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="min-w-0 font-medium break-words">
                    <Title item={item} />
                  </h3>
                  {item.ignored ? <Badge tone="neutral">{t("ignoredBadge")}</Badge> : null}
                </div>
                <p className={MUTED}>{item.detail}</p>
                <Steps item={item} labels={labels} handlers={handlers} />
              </li>
            ))}
          </ul>
        </Simple>
        <Detailed>
          <Table>
            <caption className="sr-only">{t("table.caption", { kind: label })}</caption>
            <thead>
              <tr>
                <Th>{t("table.item")}</Th>
                <Th>{t("table.detail")}</Th>
                <Th className="text-right">{t("table.count")}</Th>
                <Th className="text-right">{t("table.amount")}</Th>
                <Th>{t("table.target")}</Th>
                <Th>{t("table.steps")}</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.key}>
                  <Td className="min-w-40 break-words">
                    <Title item={item} />
                    {item.ignored ? (
                      <span className="mt-1 block">
                        <Badge tone="neutral">{t("ignoredBadge")}</Badge>
                      </span>
                    ) : null}
                  </Td>
                  <Td className="min-w-56">
                    <p>{item.detail}</p>
                    {item.prompt ? (
                      <details className="mt-1">
                        <summary className={SUMMARY}>{t("prompt")}</summary>
                        <p className="mt-1 text-xs text-zinc-700 dark:text-zinc-300">{item.prompt}</p>
                      </details>
                    ) : null}
                  </Td>
                  <Td className="text-right tabular-nums">{item.count}</Td>
                  <Td className="text-right">
                    {item.amount ? (
                      <Money
                        value={{ ...item.amount, minor: Math.abs(item.amount.minor) }}
                        direction={item.amount.minor < 0 ? "in" : "out"}
                      />
                    ) : (
                      "—"
                    )}
                  </Td>
                  <Td>
                    <code className="text-xs break-all">{item.target}</code>
                  </Td>
                  <Td className="min-w-48">
                    <Steps item={item} labels={labels} handlers={handlers} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Detailed>
      </div>
    </Card>
  );
}

/** The item's name, leading where the interface shows it once that screen is built. */
function Title({ item }: { item: TodoItem }) {
  return item.link ? <ScreenLink link={item.link}>{item.title}</ScreenLink> : <>{item.title}</>;
}
