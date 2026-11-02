// The dashboard's closing card (F06, F11): the current month and the six before it with documents, oldest first, each
// with its status (an icon and its name, never the colour alone), and in the detailed view the totals, the rows only
// receipts and notices show, and the documents each open month still waits for.

import { useTranslation } from "react-i18next";

import type { Labels, MonthClosing } from "../../api/types";
import type { MonthStatus } from "../../api/schema";
import { formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import type { Tone } from "../ui/Badge";
import { ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";
import { DashboardCard } from "./DashboardCard";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

// A closed month is settled; one still running or waiting for its statement is no fault; a missing document wants a
// look; numbers that do not add up want one first.
export const MONTH_TONES: Readonly<Record<MonthStatus, Tone>> = {
  closed: "good",
  running: "neutral",
  waiting: "neutral",
  missing: "warning",
  check: "critical",
};

interface ClosingCardProps {
  months: MonthClosing[];
  say: string;
  next: MonthClosing["link"];
  labels: Labels;
}

export function ClosingCard({ months, say, next, labels }: ClosingCardProps) {
  const { t } = useTranslation("dashboard");
  const status = (month: MonthClosing) => labelOf(labels, "MonthStatus", month.status);
  return (
    <DashboardCard title={t("closing.title")} say={say} next={{ link: next, label: t("closing.next") }}>
      <Simple>
        <ol className="flex flex-col gap-1.5">
          {months.map((month) => (
            <li key={month.month} className="text-sm">
              <Status tone={MONTH_TONES[month.status]}>
                <ScreenLink link={month.link}>{formatMonth(month.month)}</ScreenLink>: {status(month)}
              </Status>
            </li>
          ))}
        </ol>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("closing.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("closing.month")}</Th>
              <Th>{t("closing.status")}</Th>
              <Th className="text-right">{t("closing.expense")}</Th>
              <Th className="text-right">{t("closing.income")}</Th>
              <Th className="text-right">{t("closing.left")}</Th>
              <Th className="text-right">{t("closing.provisional")}</Th>
              <Th className="text-right">{t("closing.unmatched")}</Th>
              <Th>{t("closing.waiting")}</Th>
            </tr>
          </thead>
          <tbody>
            {months.map((month) => (
              <tr key={month.month}>
                <Td className="whitespace-nowrap">
                  <ScreenLink link={month.link}>{formatMonth(month.month)}</ScreenLink>
                </Td>
                <Td>
                  <Status tone={MONTH_TONES[month.status]}>{status(month)}</Status>
                  <span className={`mt-1 block ${SMALL}`}>{month.summary}</span>
                </Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(month.expense)}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">
                  {month.income ? formatMoney(month.income) : t("closing.unknown")}
                </Td>
                <Td className="whitespace-nowrap text-right tabular-nums">
                  {month.left ? formatMoney(month.left) : t("closing.unknown")}
                </Td>
                <Td className="text-right tabular-nums">{month.provisional}</Td>
                <Td className="text-right tabular-nums">{month.unmatched}</Td>
                <Td className={SMALL}>
                  {month.waiting.map((w) => `${w.account.label}: ${w.waiting_for}`).join("; ")}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </DashboardCard>
  );
}
