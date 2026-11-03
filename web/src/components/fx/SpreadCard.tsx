// How the assets spread over currencies (F12): each unit's TL value as a bar in its own colour, with the table of the
// same; the assets of a unit without a rate (gold, whose price no document prints) are named apart, outside the bars
// and the shares, with their amounts in their own unit. A unit one account holds alone leads to that account's page.

import { useTranslation } from "react-i18next";

import type { CurrencyShare } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { HBars, type BarItem } from "../charts/HBars";
import { Card } from "../ui/Card";
import { currencyName, currencySlot } from "./currency";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

export function SpreadCard({ spread }: { spread: CurrencyShare[] }) {
  const { t } = useTranslation("fx");
  const valued = spread.filter((s) => s.value !== null);
  const unvalued = spread.filter((s) => s.value === null);
  const items: BarItem[] = valued.map((s) => {
    const [only, ...more] = s.accounts;
    return {
      key: s.currency,
      label: currencyName(t, s.currency),
      value: s.value?.minor ?? 0,
      slot: currencySlot(s.currency),
      ...(only && more.length === 0 ? { link: { screen: "account" as const, id: only.id, query: {} } } : {}),
    };
  });
  const largest = valued[0];
  const total = valued.reduce((sum, s) => sum + (s.value?.minor ?? 0), 0);
  return (
    <Card title={t("spread.title")}>
      {largest ? (
        <HBars
          title={t("spread.chart")}
          summary={t("spread.summary", {
            total: formatMoney({ minor: total, currency: "TRY" }),
            currency: currencyName(t, largest.currency),
            share: largest.share ?? 0,
          })}
          itemName={t("spread.itemName")}
          items={items}
        />
      ) : null}
      {unvalued.length > 0 ? (
        <div className={largest ? "mt-4" : undefined}>
          <h3 className="text-sm font-medium">{t("spread.unvalued")}</h3>
          <p className={SMALL}>{t("spread.unvaluedText")}</p>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm">
            {unvalued.map((s) => (
              <li key={s.currency}>
                {currencyName(t, s.currency)}: <span className="tabular-nums">{formatMoney(s.amount)}</span>{" "}
                <span className="text-zinc-600 dark:text-zinc-300">
                  ({t("spread.accounts")}: {s.accounts.map((a) => a.label).join(", ")})
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}
