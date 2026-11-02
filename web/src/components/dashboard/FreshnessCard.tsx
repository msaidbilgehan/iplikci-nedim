// The dashboard's data freshness (F06): how far each open account's documents reach, the most behind first, when its
// next statement is due and whether it is late, and the months its statements cover only partly or not at all.

import { useTranslation } from "react-i18next";

import type { Freshness, Labels } from "../../api/types";
import { formatDay, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";
import { DashboardCard } from "./DashboardCard";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";

interface FreshnessCardProps {
  accounts: Freshness[];
  say: string;
  next: Freshness["link"];
  labels: Labels;
}

export function FreshnessCard({ accounts, say, next, labels }: FreshnessCardProps) {
  const { t } = useTranslation("dashboard");
  const behind = (f: Freshness) =>
    f.behind === 0 ? t("freshness.behindToday") : t("freshness.behindDays", { count: f.behind });
  return (
    <DashboardCard title={t("freshness.title")} say={say} next={{ link: next, label: t("freshness.next") }}>
      <Simple>
        <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
          {accounts.map((f) => (
            <li key={f.account.id} className="py-1.5 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <ScreenLink link={f.link} className="font-medium">
                  {f.account.label}
                </ScreenLink>
                {f.late ? <Status tone="warning">{t("freshness.late")}</Status> : null}
              </div>
              <p className={SMALL}>
                {f.note} · {behind(f)}
              </p>
              {f.missing.length > 0 ? (
                <p className={SMALL}>
                  {t("freshness.missing")}: {f.missing.map(formatMonth).join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("freshness.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("freshness.account")}</Th>
              <Th>{t("freshness.kind")}</Th>
              <Th>{t("freshness.last")}</Th>
              <Th>{t("freshness.behind")}</Th>
              <Th>{t("freshness.expected")}</Th>
              <Th>{t("freshness.missing")}</Th>
              <Th>{t("freshness.note")}</Th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((f) => (
              <tr key={f.account.id}>
                <Td>
                  <ScreenLink link={f.link}>{f.account.label}</ScreenLink>
                </Td>
                <Td>
                  {labelOf(labels, "DocumentKind", f.kind)}
                  {f.name ? (
                    <ScreenLink
                      link={{ screen: "document", id: f.document, query: {} }}
                      className={`block wrap-break-word ${SMALL}`}
                    >
                      {f.name}
                    </ScreenLink>
                  ) : null}
                </Td>
                <Td className="whitespace-nowrap tabular-nums">{formatDay(f.last)}</Td>
                <Td className="whitespace-nowrap">{behind(f)}</Td>
                <Td className="whitespace-nowrap">
                  {f.expected ? t("freshness.expectedDay", { day: formatDay(f.expected) }) : "—"}
                  {f.late ? (
                    <span className="mt-1 block">
                      <Status tone="warning">{t("freshness.late")}</Status>
                    </span>
                  ) : null}
                </Td>
                <Td>{f.missing.length > 0 ? f.missing.map(formatMonth).join(", ") : "—"}</Td>
                <Td className={SMALL}>{f.note}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </DashboardCard>
  );
}
