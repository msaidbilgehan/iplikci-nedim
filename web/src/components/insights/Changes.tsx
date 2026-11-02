// How the spending moved (F10): the recent whole months against the ones before, with and without the large one-off
// purchases the averages keep apart, the categories that changed most, and the movements worth a look — only flagged,
// every row still counts. Both read the interpretation's complete months; no filter changes them.

import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { Labels, Trend, Unusual } from "../../api/types";
import { formatDay, formatFlow, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { percent } from "../../lib/turkish";
import { Detailed, Simple } from "../Preferences";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { NextStep, ScreenLink } from "../ui/Say";
import { Stat } from "../ui/Stat";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const NUMBER = "text-right whitespace-nowrap tabular-nums";
const LIRA = 100;
const CHANGES_SHOWN = 8;

/** The months of a window in words: "Nisan 2026 – Ekim 2026", or the one month. */
function span(months: readonly string[]): { from: string; to: string } {
  return { from: formatMonth(months[0] ?? ""), to: formatMonth(months.at(-1) ?? "") };
}

export function TrendCard({ trend }: { trend: Trend | null }) {
  const { t } = useTranslation("insights");
  if (!trend || trend.recent.length === 0 || trend.before.length === 0) {
    return (
      <Card title={t("trend.title")}>
        <p className="text-sm">{t("trend.none")}</p>
      </Card>
    );
  }
  const recent = span(trend.recent);
  const before = span(trend.before);
  const usual = (average: Trend["before_average"], without: Trend["usual_before"]) =>
    Math.abs(average.minor - without.minor) >= LIRA ? t("trend.usual", { amount: formatMoney(without) }) : null;
  const largeTotal = trend.large.reduce((sum, row) => sum + row.amount.minor, 0);
  return (
    <Card title={t("trend.title")}>
      <p className={`mb-3 ${SMALL}`}>
        {t("trend.hint", {
          recentCount: trend.recent.length,
          recentFrom: recent.from,
          recentTo: recent.to,
          beforeCount: trend.before.length,
          beforeFrom: before.from,
          beforeTo: before.to,
        })}
      </p>
      <Simple>
        <p className="mb-3 text-sm">
          {t("trend.say", {
            recentCount: trend.recent.length,
            recent: formatMoney(trend.recent_average),
            beforeCount: trend.before.length,
            before: formatMoney(trend.before_average),
          })}
          {trend.large.length > 0
            ? ` ${t("trend.sayLarge", {
                count: trend.large.length,
                amount: formatMoney({ minor: largeTotal, currency: trend.threshold.currency }),
              })}`
            : ""}
        </p>
      </Simple>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Stat
          label={t("trend.before")}
          value={formatMoney(trend.before_average)}
          meta={[t("trend.window", before), usual(trend.before_average, trend.usual_before)]
            .filter(Boolean)
            .join(" · ")}
        />
        <Stat
          label={t("trend.recent")}
          value={formatMoney(trend.recent_average)}
          meta={[t("trend.window", recent), usual(trend.recent_average, trend.usual_recent)]
            .filter(Boolean)
            .join(" · ")}
        />
      </div>
      <Detailed>
        <Changes trend={trend} />
        <Large trend={trend} />
      </Detailed>
    </Card>
  );
}

/** The categories whose monthly average moved most between the two windows. */
function Changes({ trend }: { trend: Trend }) {
  const { t } = useTranslation("insights");
  const heading = useId();
  const moved = trend.changes
    .map((change) => ({ change, by: change.recent.minor - change.before.minor }))
    .filter(({ by }) => Math.abs(by) >= LIRA)
    .sort((a, b) => Math.abs(b.by) - Math.abs(a.by))
    .slice(0, CHANGES_SHOWN);
  return (
    <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {t("trend.changes")}
      </h3>
      {moved.length === 0 ? (
        <p className="text-sm">{t("trend.noChanges")}</p>
      ) : (
        <Table>
          <caption className="sr-only">{t("trend.changesCaption")}</caption>
          <thead>
            <tr>
              <Th>{t("trend.category")}</Th>
              <Th className="text-right">{t("trend.beforeColumn")}</Th>
              <Th className="text-right">{t("trend.recentColumn")}</Th>
              <Th className="text-right">{t("trend.change")}</Th>
            </tr>
          </thead>
          <tbody>
            {moved.map(({ change, by }) => (
              <tr key={change.category}>
                <Td className="min-w-40">
                  <ScreenLink link={{ screen: "transactions", id: "", query: { category: change.category } }}>
                    {change.category}
                  </ScreenLink>
                </Td>
                <Td className={NUMBER}>{formatMoney(change.before)}</Td>
                <Td className={NUMBER}>{formatMoney(change.recent)}</Td>
                <Td className={NUMBER}>
                  {formatFlow({ minor: Math.abs(by), currency: change.recent.currency }, by > 0 ? "in" : "out")}
                  {change.before.minor > 0 ? (
                    <span className={`block ${SMALL}`}>
                      {by > 0 ? "+" : "−"}
                      {percent(Math.abs(by) / change.before.minor)}
                    </span>
                  ) : null}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </section>
  );
}

/** The single purchases over the threshold, which the averages "without one-offs" leave out. */
function Large({ trend }: { trend: Trend }) {
  const { t } = useTranslation("insights");
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {t("trend.large")}
      </h3>
      <p className={SMALL}>{t("trend.largeHint", { amount: formatMoney(trend.threshold) })}</p>
      {trend.large.length === 0 ? (
        <p className="text-sm">{t("trend.noLarge")}</p>
      ) : (
        <Table>
          <caption className="sr-only">{t("trend.largeCaption")}</caption>
          <thead>
            <tr>
              <Th>{t("trend.day")}</Th>
              <Th>{t("trend.row")}</Th>
              <Th className="text-right">{t("trend.amount")}</Th>
            </tr>
          </thead>
          <tbody>
            {trend.large.map((row) => (
              <tr key={row.fingerprint}>
                <Td className="whitespace-nowrap tabular-nums">{formatDay(row.day)}</Td>
                <Td className="min-w-40">
                  <ScreenLink link={{ screen: "transaction", id: row.fingerprint, query: {} }} className="font-medium">
                    {row.merchant || row.title}
                  </ScreenLink>
                  <span className={`block ${SMALL}`}>
                    {[row.category, row.account.label].filter(Boolean).join(" · ")}
                  </span>
                </Td>
                <Td className={NUMBER}>{formatMoney(row.amount)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </section>
  );
}

export function UnusualCard({ found, labels }: { found: readonly Unusual[]; labels: Labels }) {
  const { t } = useTranslation("insights");
  return (
    <Card title={t("unusual.title")}>
      <p className={`mb-3 ${SMALL}`}>{t("unusual.hint")}</p>
      {found.length === 0 ? (
        <p className="text-sm">{t("unusual.none")}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {found.map((item) => (
            <li key={`${item.kind}:${item.row.fingerprint}`} className="flex flex-col items-start gap-1 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <Badge tone="warning">{labelOf(labels, "UnusualKind", item.kind)}</Badge>
                <span className="tabular-nums">{formatDay(item.row.day)}</span>
                <strong className="font-semibold">{item.row.merchant || item.row.title}</strong>
                <span className="tabular-nums">{formatMoney(item.row.amount)}</span>
              </span>
              <p>{item.text}</p>
              <NextStep
                step={{ link: item.link, label: t("unusual.open") }}
                context={item.row.merchant || item.row.title}
              />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
