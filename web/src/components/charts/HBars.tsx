// Ranked horizontal bars — categories, merchants — as the MVP report drew them: each row's name, its bar in its group's
// colour with the data end rounded by 4 px, and its amount written beside the bar. The rows are a list in HTML rather
// than SVG text, so a long name wraps or shortens as text does (the bar widths still come from d3-scale). Nothing
// below zero has a bar; its amount says so with its sign. The table view adds each row's share of the whole.

import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { formatMoney } from "../../lib/format";
import { percent } from "../../lib/turkish";
import { Table, Td, Th } from "../ui/Table";
import { ChartFrame } from "./ChartFrame";
import { barShares } from "./layout";
import { SLOT_BG, type Slot } from "./palette";

export interface BarItem {
  key: string;
  label: string;
  value: number; // minor units
  slot: Slot; // its group's colour
}

interface HBarsProps {
  title: string;
  summary: ReactNode;
  itemName: string; // what the rows are, the table's first column: "Kategori", "İşyeri"
  items: readonly BarItem[]; // in the order to show, the largest first
  currency?: string;
}

export function HBars({ title, summary, itemName, items, currency = "TRY" }: HBarsProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const shares = barShares(items.map((item) => item.value));
  const whole = items.reduce((sum, item) => sum + item.value, 0);
  const money = (minor: number) => formatMoney({ minor, currency });

  const chart = (
    <ol aria-label={title} aria-describedby={summaryId} className="flex flex-col gap-1">
      {items.map((item, index) => {
        const share = shares[index] ?? 0;
        return (
          <li key={item.key} className="grid grid-cols-[minmax(7rem,38%)_1fr] items-center gap-x-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[item.slot])} />
              <span className="truncate" title={item.label}>
                {item.label}
              </span>
            </span>
            <span className="flex min-h-7 min-w-0 items-center gap-2">
              <span className="sr-only">: </span>
              <span
                aria-hidden="true"
                className={cn("h-3.5 shrink-0 rounded-r-[4px]", SLOT_BG[item.slot], share > 0 && "min-w-0.5")}
                style={{ width: `calc((100% - 8rem) * ${share / 100})` }}
              />
              <span className="whitespace-nowrap text-xs tabular-nums text-zinc-700 dark:text-zinc-300">
                {money(item.value)}
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );

  const table = (
    <Table>
      <caption className="sr-only">{title}</caption>
      <thead>
        <tr>
          <Th>{itemName}</Th>
          <Th className="text-right">{t("amount")}</Th>
          <Th className="text-right">{t("share")}</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.key}>
            <Td>
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[item.slot])} />
                {item.label}
              </span>
            </Td>
            <Td className="whitespace-nowrap text-right tabular-nums">{money(item.value)}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">
              {whole > 0 ? percent(item.value / whole) : t("none")}
            </Td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <Td className="font-medium">{t("total")}</Td>
          <Td className="whitespace-nowrap text-right font-medium tabular-nums">{money(whole)}</Td>
          <Td />
        </tr>
      </tfoot>
    </Table>
  );

  return (
    <ChartFrame
      title={title}
      summary={summary}
      summaryId={summaryId}
      chart={chart}
      table={table}
      empty={items.length === 0}
    />
  );
}
