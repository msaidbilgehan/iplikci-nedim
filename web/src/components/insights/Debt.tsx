// How the debts moved over the interpretation's window (F10, "Borç görünümü"): the card statements' balances and the
// overdraft used at the end of the month before the window and at the end of its last month, and the change between
// them. Like the interpretation it takes the complete months, and no filter changes it; today's debts are the net
// worth's.

import { useTranslation } from "react-i18next";

import type { Insights } from "../../api/types";
import { formatMoney, formatMonth } from "../../lib/format";
import { Card, Facts } from "../ui/Card";
import { Say } from "../ui/Say";
import { shiftMonth } from "./query";

const ACCOUNTS = { screen: "accounts", id: "", query: {} } as const;
const SOME = 100; // a lira: less is no debt, as the interpretation counts it

export function DebtCard({ insights }: { insights: Insights }) {
  const { t } = useTranslation("insights");
  const { flow } = insights;
  const first = insights.window.months[0];
  const last = insights.window.months.at(-1);
  if (!flow || !first || !last) {
    return null;
  }
  const before = formatMonth(shiftMonth(first, -1));
  const end = formatMonth(last);
  const start = flow.debt_start;
  const finish = flow.debt_end;
  const change = { minor: finish.minor - start.minor, currency: finish.currency };
  if (start.minor < SOME && finish.minor < SOME) {
    return (
      <Card title={t("debt.title")}>
        <p className="text-sm">{t("debt.none", { from: formatMonth(first), to: end })}</p>
      </Card>
    );
  }
  const amount = formatMoney({ ...change, minor: Math.abs(change.minor) });
  const say =
    change.minor > 0
      ? t("debt.up", { from: before, to: end, amount })
      : change.minor < 0
        ? t("debt.down", { from: before, to: end, amount })
        : t("debt.same", { from: before, to: end });
  return (
    <Card title={t("debt.title")}>
      <div className="flex flex-col gap-3">
        <Say next={{ link: ACCOUNTS, label: t("debt.next") }}>{say}</Say>
        <Facts
          items={[
            [t("debt.at", { month: before }), formatMoney(start)],
            [t("debt.at", { month: end }), formatMoney(finish)],
            [t("debt.change"), `${change.minor > 0 ? "+" : ""}${formatMoney(change)}`],
          ]}
        />
      </div>
    </Card>
  );
}
