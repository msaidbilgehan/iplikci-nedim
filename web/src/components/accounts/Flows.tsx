// Where the money went between the accounts (F07's Sankey and its table): from the payers of income into the
// accounts, between them, and out to the spending groups, people, savings, loans and cash, over a window of days the
// address keeps (?from=&to=); without one, the service's newest complete month. Every band leads to its rows on the
// Transactions screen.

import { useId } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useCategoryRules, useFlows } from "../../api/queries";
import type { Category, FlowNode, Flows, Labels } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { slotOf } from "../charts/palette";
import { Sankey } from "../charts/Sankey";
import type { FlowBand, FlowPoint } from "../charts/flowLayout";
import { Failure, Loading } from "../QueryState";
import { Explain } from "../ui/Explain";
import { Card } from "../ui/Card";
import { NextStep } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const INPUT = [
  "min-h-11 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");
const tl = (minor: number) => ({ minor, currency: "TRY" });

/** A place's name: an account's as the screens show it, a payer's or a spending group's own, else its kind's. */
export function placeName(node: FlowNode, labels: Labels): string {
  return node.account?.label ?? (node.name || labelOf(labels, "FlowKind", node.kind));
}

/** A spending group keeps its colour slot (the rule file's); every other place is drawn in the neutral ink. */
function slotOfPlace(node: FlowNode, categories: readonly Category[]): FlowPoint["slot"] {
  if (node.kind !== "spending") {
    return null;
  }
  const found = categories.find((category) => category.group === node.name);
  return found ? slotOf(found.slot) : 0;
}

export function FlowsSection({ labels }: { labels: Labels }) {
  const { t } = useTranslation("accounts");
  const [params, setParams] = useSearchParams();
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const flows = useFlows(from, to);
  const rules = useCategoryRules();
  const set = (name: "from" | "to", day: string) =>
    setParams(
      (was) => {
        const next = new URLSearchParams(was);
        if (day) {
          next.set(name, day);
        } else {
          next.delete(name);
        }
        return next;
      },
      { replace: true },
    );
  return (
    <Card title={t("flows.title")}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <DayInput label={t("flows.from")} value={from || flows.data?.start || ""} onChange={(day) => set("from", day)} />
          <DayInput label={t("flows.to")} value={to || flows.data?.end || ""} onChange={(day) => set("to", day)} />
        </div>
        {flows.isPending ? <Loading /> : null}
        {flows.isError ? <Failure error={flows.error} onRetry={() => void flows.refetch()} /> : null}
        {flows.data ? <FlowChart flows={flows.data} labels={labels} categories={rules.data?.categories ?? []} /> : null}
      </div>
    </Card>
  );
}

function DayInput({ label, value, onChange }: { label: string; value: string; onChange: (day: string) => void }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="date" value={value} onChange={(event) => onChange(event.target.value)} className={INPUT} />
    </div>
  );
}

interface FlowChartProps {
  flows: Flows;
  labels: Labels;
  categories: readonly Category[];
}

function FlowChart({ flows, labels, categories }: FlowChartProps) {
  const { t } = useTranslation("accounts");
  const byId = new Map(flows.nodes.map((node) => [node.id, node]));
  const name = (id: string) => {
    const node = byId.get(id);
    return node ? placeName(node, labels) : id;
  };
  const kindOf = (id: string) => byId.get(id)?.kind;
  const points: FlowPoint[] = flows.nodes.map((node) => ({
    id: node.id,
    label: placeName(node, labels),
    slot: slotOfPlace(node, categories),
  }));
  const bands: FlowBand[] = flows.edges.map((edge) => ({
    key: `${edge.source}>${edge.target}`,
    source: edge.source,
    target: edge.target,
    value: edge.amount.minor,
  }));
  const income = flows.edges.filter((edge) => kindOf(edge.source) === "income");
  const out = flows.edges.filter((edge) => kindOf(edge.target) !== "account" && kindOf(edge.source) === "account");
  const sum = (edges: typeof flows.edges) => formatMoney(tl(edges.reduce((total, edge) => total + edge.amount.minor, 0)));
  const largest = flows.edges[0];
  const span = { start: formatDay(flows.start), end: formatDay(flows.end) };
  const summary = largest
    ? t("flows.say", {
        ...span,
        income: sum(income),
        out: sum(out),
        source: name(largest.source),
        target: name(largest.target),
        amount: formatMoney(largest.amount),
      })
    : t("flows.none", span);

  const table = (
    <Table>
      <caption className="sr-only">{t("flows.caption", span)}</caption>
      <thead>
        <tr>
          <Th>{t("flows.source")}</Th>
          <Th>{t("flows.target")}</Th>
          <Th className="text-right">{t("flows.amount")}</Th>
          <Th className="text-right">{t("flows.rows")}</Th>
          <Th>{t("flows.kinds")}</Th>
          <Th>
            <span className="sr-only">{t("flows.open")}</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {flows.edges.map((edge) => (
          <tr key={`${edge.source}>${edge.target}`}>
            <Td>{name(edge.source)}</Td>
            <Td>{name(edge.target)}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(edge.amount)}</Td>
            <Td className="text-right tabular-nums">{edge.rows}</Td>
            <Td className="text-xs">
              {edge.kinds.map((kind) => labelOf(labels, "TransactionKind", kind)).join(", ")}
            </Td>
            <Td>
              <NextStep
                step={{ link: edge.link, label: t("flows.open") }}
                context={`${name(edge.source)} → ${name(edge.target)}`}
              />
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  return (
    <>
      <Sankey
        title={t("flows.chart")}
        summary={summary}
        points={points}
        bands={bands}
        table={table}
      />
      {flows.note ? (
        <Explain>
          <p>{flows.note}</p>
        </Explain>
      ) : null}
    </>
  );
}
