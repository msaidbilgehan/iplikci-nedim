// "Kategoriler" and "En çok harcama yapılan yerler" (the MVP report's ranked bars): the spending the filters keep, the
// largest first, each bar in its group's colour. The chart shows twelve and folds the rest into one bar; the tables
// list them all. Each bar and name leads to its rows on the İşlemler screen, with the period and the filters the card
// counts (the service's link), so they add up to its total.

import { useTranslation } from "react-i18next";

import type { CategoryLine, MerchantLine, Spending } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { percentOrLess } from "../../lib/turkish";
import { type BarItem, HBars } from "../charts/HBars";
import { SLOT_BG, slotOf } from "../charts/palette";
import { Card } from "../ui/Card";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const NUMBER = "text-right whitespace-nowrap tabular-nums";
const SHOWN = 12; // bars in a chart, as the MVP's

function periodOf(found: Spending): { from: string; to: string } {
  return { from: formatMonth(found.period?.start ?? ""), to: formatMonth(found.period?.end ?? "") };
}

function Swatch({ slot }: { slot: number }) {
  return <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[slotOf(slot)])} />;
}

export function CategoriesCard({ found }: { found: Spending }) {
  const { t } = useTranslation("insights");
  const lines = found.categories;
  const rest = lines.slice(SHOWN);
  const items: BarItem[] = lines.slice(0, SHOWN).map((line) => ({
    key: line.category,
    label: line.category,
    value: line.total.minor,
    slot: slotOf(line.slot),
    link: line.link,
  }));
  if (rest.length > 0) {
    items.push({
      key: "", // no category is nameless: the rest's bar cannot share a category's key
      label: t("categories.rest", { count: rest.length }),
      value: rest.reduce((sum, line) => sum + line.total.minor, 0),
      slot: 0,
    });
  }
  const top = lines[0];
  return (
    <Card title={t("categories.title")}>
      <HBars
        title={t("categories.chart")}
        summary={
          top
            ? t("categories.summary", { ...periodOf(found), name: top.category, share: Number(top.share ?? 0) })
            : null
        }
        itemName={t("categories.category")}
        items={items}
        currency={top?.total.currency ?? "TRY"}
        table={<CategoryTable lines={lines} />}
      />
    </Card>
  );
}

function CategoryTable({ lines }: { lines: readonly CategoryLine[] }) {
  const { t } = useTranslation("insights");
  // The average counts the complete months alone: spent only in a partial month, it is no zero but no average.
  const average = (line: CategoryLine) =>
    !line.average ? "–" : line.average.minor > 0 ? formatMoney(line.average) : t("categories.onlyPartial");
  const currency = lines[0]?.total.currency ?? "TRY";
  const total = lines.reduce((sum, line) => sum + line.total.minor, 0);
  return (
    <Table>
      <caption className="sr-only">{t("categories.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("categories.category")}</Th>
          <Th>{t("categories.group")}</Th>
          <Th className="text-right">{t("categories.total")}</Th>
          <Th className="text-right">{t("categories.share")}</Th>
          <Th className="text-right">{t("categories.average")}</Th>
          <Th className="text-right">{t("categories.count")}</Th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => (
          <tr key={line.category}>
            <Td className="min-w-40">
              <span className="inline-flex items-center gap-1.5">
                <Swatch slot={line.slot} />
                <ScreenLink link={line.link}>{line.category}</ScreenLink>
              </span>
            </Td>
            <Td className="min-w-32">{line.group}</Td>
            <Td className={NUMBER}>{formatMoney(line.total)}</Td>
            <Td className={NUMBER}>{line.share === null ? "–" : percentOrLess(Number(line.share))}</Td>
            <Td className={NUMBER}>{average(line)}</Td>
            <Td className={NUMBER}>{line.count}</Td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <Th scope="row" colSpan={2} className="border-b-0 text-zinc-900 dark:text-zinc-100">
            {t("categories.total")}
          </Th>
          <Td className={cn(NUMBER, "border-b-0 font-semibold")}>{formatMoney({ minor: total, currency })}</Td>
          <Td className="border-b-0" colSpan={3} />
        </tr>
      </tfoot>
    </Table>
  );
}

export function MerchantsCard({ found }: { found: Spending }) {
  const { t } = useTranslation("insights");
  const lines = found.merchants;
  const top = lines[0];
  return (
    <Card title={t("merchants.title")}>
      <HBars
        title={t("merchants.chart")}
        summary={top ? t("merchants.summary", { ...periodOf(found), name: top.merchant, count: top.count }) : null}
        itemName={t("merchants.merchant")}
        items={lines.slice(0, SHOWN).map((line) => ({
          key: line.merchant,
          label: line.merchant,
          value: line.total.minor,
          slot: slotOf(line.slot),
          link: line.link,
        }))}
        currency={top?.total.currency ?? "TRY"}
        table={<MerchantTable lines={lines} />}
      />
    </Card>
  );
}

function MerchantTable({ lines }: { lines: readonly MerchantLine[] }) {
  const { t } = useTranslation("insights");
  return (
    <Table>
      <caption className="sr-only">{t("merchants.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("merchants.merchant")}</Th>
          <Th className="text-right">{t("merchants.count")}</Th>
          <Th className="text-right">{t("merchants.total")}</Th>
          <Th className="text-right">{t("merchants.perRow")}</Th>
          <Th>{t("merchants.last")}</Th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => (
          <tr key={line.merchant}>
            <Td className="min-w-44">
              <ScreenLink link={line.link} className="font-medium wrap-break-word">
                {line.merchant}
              </ScreenLink>
              <span className={cn("mt-0.5 flex items-center gap-1.5", SMALL)}>
                <Swatch slot={line.slot} />
                {line.category}
              </span>
            </Td>
            <Td className={NUMBER}>{line.count}</Td>
            <Td className={NUMBER}>{formatMoney(line.total)}</Td>
            <Td className={NUMBER}>{formatMoney(line.per_row)}</Td>
            <Td className="whitespace-nowrap tabular-nums">{formatDay(line.last)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
