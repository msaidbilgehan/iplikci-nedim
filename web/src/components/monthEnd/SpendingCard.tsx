// Where a month's money went (F11): its spending by main group, each in the group's fixed colour, and the merchants
// it went to most; the detailed view adds the necessity levels and the categories and merchants in full. A category,
// a merchant or a group leads to its rows of the month on the Transactions screen.

import { useTranslation } from "react-i18next";

import type { MonthEndDetail, MonthEndShare } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { HBars } from "../charts/HBars";
import { slotOf } from "../charts/palette";
import { Detailed, Simple } from "../Preferences";
import { Card } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { monthRows } from "./parts";

const TOP = 5; // the merchants the simple view names

export function SpendingCard({ detail }: { detail: MonthEndDetail }) {
  const { t } = useTranslation("monthEnd");
  const month = detail.month.month;
  const top = detail.groups[0];
  if (!top) {
    return (
      <Card title={t("spending.title")}>
        <p className="text-sm">{t("spending.none")}</p>
      </Card>
    );
  }
  const total = detail.month.totals.expense;
  const bars = (shares: readonly MonthEndShare[]) =>
    shares.map((share) => ({
      key: share.name,
      label: share.name,
      value: share.amount.minor,
      slot: slotOf(share.slot),
    }));
  return (
    <Card title={t("spending.title")}>
      <Say next={{ link: monthRows(month), label: t("spending.all") }}>
        {t("spending.say", {
          count: detail.count,
          total: formatMoney(total),
          group: top.name,
          amount: formatMoney(top.amount),
        })}
      </Say>
      <div className="flex flex-col gap-6">
        <HBars
          title={t("spending.groups")}
          summary={t("spending.groupsSay", { month, count: detail.groups.length, total: formatMoney(total) })}
          itemName={t("spending.group")}
          items={bars(detail.groups)}
        />
        <Simple>
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">{t("spending.top")}</h3>
            <ol className="flex flex-col gap-1 text-sm">
              {detail.merchants.slice(0, TOP).map((share) => (
                <li key={share.name} className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <ScreenLink link={monthRows(month, { merchant: share.name })}>{share.name}</ScreenLink>
                  <span className="whitespace-nowrap tabular-nums">{formatMoney(share.amount)}</span>
                </li>
              ))}
            </ol>
          </div>
        </Simple>
        <Detailed>
          {detail.levels.length > 0 ? (
            <HBars
              title={t("spending.levels")}
              summary={t("spending.levelsSay", { month })}
              itemName={t("spending.level")}
              items={bars(detail.levels)}
            />
          ) : null}
          <SharesTable
            title={t("spending.categories")}
            name={t("spending.category")}
            shares={detail.categories}
            link={(share) => monthRows(month, { category: share.name })}
          />
          <SharesTable
            title={t("spending.merchants")}
            name={t("spending.merchant")}
            shares={detail.merchants}
            link={(share) => monthRows(month, { merchant: share.name })}
          />
        </Detailed>
      </div>
    </Card>
  );
}

interface SharesTableProps {
  title: string;
  name: string; // what the rows are: "Kategori", "İşyeri"
  shares: readonly MonthEndShare[];
  link: (share: MonthEndShare) => ReturnType<typeof monthRows>;
}

/** The categories or the merchants of the month, the most spent first, each leading to its rows. */
function SharesTable({ title, name, shares, link }: SharesTableProps) {
  const { t } = useTranslation("monthEnd");
  if (shares.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <Table>
        <caption className="sr-only">{title}</caption>
        <thead>
          <tr>
            <Th>{name}</Th>
            <Th className="text-right">{t("spending.rows")}</Th>
            <Th className="text-right">{t("spending.amount")}</Th>
          </tr>
        </thead>
        <tbody>
          {shares.map((share) => (
            <tr key={share.name}>
              <Td>
                <ScreenLink link={link(share)}>{share.name}</ScreenLink>
              </Td>
              <Td className="text-right tabular-nums">{share.count ?? "—"}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(share.amount)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
