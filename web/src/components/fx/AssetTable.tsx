// Every asset and debt on Döviz (F12): its account (leading to the account's page), its kind, the amount in its own
// unit, and its TL value at the rate the documents print, or "no rate in the documents" — never zero. The detailed
// view adds the rate and its day, the cost where the documents tell it (gold bought from a TL account of the same
// bank), the difference the rate made, the day of its newest document and how the service found it.

import { useTranslation } from "react-i18next";

import type { Asset, Labels } from "../../api/types";
import { formatDay, formatMoney, formatRate } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { useView } from "../Preferences";
import { Card } from "../ui/Card";
import { Money } from "../ui/Money";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const MUTED = "text-zinc-600 dark:text-zinc-300";

interface AssetTableProps {
  assets: Asset[];
  labels: Labels;
  note: string; // how the values and costs were found, and what is missing
}

export function AssetTable({ assets, labels, note }: AssetTableProps) {
  const { t } = useTranslation("fx");
  const detailed = useView().view === "detailed";
  return (
    <Card title={t("assets.title")}>
      <Table>
        <caption className="sr-only">{t("assets.caption")}</caption>
        <thead>
          <tr>
            <Th>{t("assets.account")}</Th>
            <Th>{t("assets.group")}</Th>
            <Th className="text-right">{t("assets.amount")}</Th>
            <Th className="text-right">{t("assets.value")}</Th>
            {detailed ? (
              <>
                <Th className="whitespace-nowrap">{t("assets.rate")}</Th>
                <Th className="whitespace-nowrap text-right">{t("assets.cost")}</Th>
                <Th className="whitespace-nowrap text-right">{t("assets.gain")}</Th>
                <Th className="whitespace-nowrap">{t("assets.day")}</Th>
              </>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.account.id}>
              {/* Wide enough to read on a phone, where the table scrolls inside its card. */}
              <Td className="min-w-44">
                <ScreenLink link={{ screen: "account", id: asset.account.id, query: {} }} className="font-medium">
                  {asset.account.label}
                </ScreenLink>
                {detailed && asset.note ? <span className={`block ${SMALL}`}>{asset.note}</span> : null}
              </Td>
              <Td>{labelOf(labels, "AccountGroup", asset.group)}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                {formatMoney(asset.amount)}
                {asset.amount.minor < 0 ? <span className={`block ${SMALL}`}>{t("assets.debt")}</span> : null}
              </Td>
              <Td className="text-right">
                {asset.value ? (
                  <Money value={asset.value} certainty={asset.certainty} className="justify-end" />
                ) : (
                  <span className={MUTED}>{t("assets.noValue")}</span>
                )}
              </Td>
              {detailed && asset.amount.currency === "TRY" ? <InLira /> : null}
              {detailed && asset.amount.currency !== "TRY" ? (
                <>
                  <Td>
                    {asset.rate ? (
                      <>
                        <span className="whitespace-nowrap tabular-nums">
                          {t("assets.rateText", { rate: formatRate(asset.rate) })}
                        </span>
                        {asset.rate_day ? (
                          <span className={`block ${SMALL}`}>
                            {t("assets.rateDay", { day: formatDay(asset.rate_day) })}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className={MUTED}>{t("assets.unknown")}</span>
                    )}
                  </Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">
                    {asset.cost ? formatMoney(asset.cost) : <span className={MUTED}>{t("assets.unknown")}</span>}
                  </Td>
                  <Td className="whitespace-nowrap text-right tabular-nums">
                    {asset.gain ? formatMoney(asset.gain) : <span className={MUTED}>{t("assets.unknown")}</span>}
                  </Td>
                </>
              ) : null}
              {detailed ? <Td className="whitespace-nowrap tabular-nums">{formatDay(asset.day)}</Td> : null}
            </tr>
          ))}
        </tbody>
      </Table>
      {note ? <p className={`mt-2 ${SMALL}`}>{note}</p> : null}
    </Card>
  );
}

/** A lira holding has no rate, cost or difference to show: a dash, and the reason for screen readers. */
function InLira() {
  const { t } = useTranslation("fx");
  return (
    <>
      {[0, 1, 2].map((cell) => (
        <Td key={cell} className={cell === 0 ? undefined : "text-right"}>
          <span aria-hidden="true">–</span>
          <span className="sr-only">{t("assets.inLira")}</span>
        </Td>
      ))}
    </>
  );
}
