// "Veri kaynakları ve kapsam" (the MVP report's sources card): how many documents are kept and how many were read, and
// how far each account's documents reach — the last day, how long ago, whether a new one is late and the months they
// leave out — leading to the Belgeler and Hesaplar screens. It is about the archive; no filter changes it.

import { useTranslation } from "react-i18next";

import type { useDashboard, useSystem } from "../../api/queries";
import type { Freshness, Labels } from "../../api/types";
import { formatDay, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Failure, Loading } from "../QueryState";
import { Card } from "../ui/Card";
import { NextStep, ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;
const ACCOUNTS = { screen: "accounts", id: "", query: {} } as const;
const REMOVED = "removed"; // in the Trash: no longer kept (ADR-0003)

interface SourcesCardProps {
  dashboard: ReturnType<typeof useDashboard>;
  system: ReturnType<typeof useSystem>;
  labels: Labels;
}

export function SourcesCard({ dashboard, system, labels }: SourcesCardProps) {
  const { t } = useTranslation("insights");
  return (
    <Card title={t("sources.title")}>
      <div className="flex flex-col gap-4">
        {system.isPending ? <Loading /> : null}
        {system.isError ? <Failure error={system.error} onRetry={() => void system.refetch()} /> : null}
        {system.data ? <Documents counts={system.data.documents} labels={labels} /> : null}
        {dashboard.isPending ? <Loading /> : null}
        {dashboard.isError ? <Failure error={dashboard.error} onRetry={() => void dashboard.refetch()} /> : null}
        {dashboard.data ? <Reach accounts={dashboard.data.freshness.accounts} /> : null}
      </div>
    </Card>
  );
}

/** "12 belge kayıtlı: 10 işlendi, 1 işlenmedi, 1 okunamadı." */
function Documents({ counts, labels }: { counts: Record<string, number>; labels: Labels }) {
  const { t } = useTranslation("insights");
  const kept = Object.entries(counts).filter(([status, count]) => status !== REMOVED && count > 0);
  const total = kept.reduce((sum, [, count]) => sum + count, 0);
  const parts = kept
    .map(([status, count]) => `${count} ${labelOf(labels, "DocumentStatus", status).toLocaleLowerCase("tr-TR")}`)
    .join(", ");
  return (
    <div className="flex flex-col items-start gap-1">
      <p className="text-sm">
        {total > 0 ? t("sources.documents", { count: total, parts }) : t("sources.noDocuments")}
      </p>
      <NextStep step={{ link: DOCUMENTS, label: t("sources.openDocuments") }} />
    </div>
  );
}

/** How far each account's documents reach, the most behind first as the service orders them. */
function Reach({ accounts }: { accounts: readonly Freshness[] }) {
  const { t } = useTranslation("insights");
  if (accounts.length === 0) {
    return null;
  }
  const late = accounts.filter((f) => f.late).length;
  const missing = accounts.filter((f) => f.missing.length > 0).length;
  const behind = (f: Freshness) =>
    f.behind === 0 ? t("sources.behindToday") : t("sources.behind", { count: f.behind });
  return (
    <div className="flex flex-col items-start gap-2">
      <Simple>
        <p className="text-sm">
          {late === 0 && missing === 0
            ? t("sources.sayAllGood", { count: accounts.length })
            : t("sources.say", {
                count: accounts.length,
                parts: [
                  late > 0 ? t("sources.sayLate", { count: late }) : "",
                  missing > 0 ? t("sources.sayMissing", { count: missing }) : "",
                ]
                  .filter(Boolean)
                  .join(", "),
              })}
        </p>
      </Simple>
      <Detailed>
        <div className="w-full">
          <Table>
            <caption className="sr-only">{t("sources.caption")}</caption>
            <thead>
              <tr>
                <Th>{t("sources.account")}</Th>
                <Th>{t("sources.reach")}</Th>
                <Th>{t("sources.missing")}</Th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((f) => (
                <tr key={f.account.id}>
                  <Td className="min-w-40">
                    <ScreenLink link={f.link} className="font-medium">
                      {f.account.label}
                    </ScreenLink>
                    {f.note ? <span className={`block ${SMALL}`}>{f.note}</span> : null}
                  </Td>
                  <Td className="min-w-36">
                    <span className="block whitespace-nowrap">{t("sources.reachDay", { day: formatDay(f.last) })}</span>
                    <span className={`block ${SMALL}`}>{behind(f)}</span>
                    {f.late ? (
                      <span className="mt-1 block">
                        <Status tone="warning">{t("sources.late")}</Status>
                      </span>
                    ) : null}
                  </Td>
                  <Td className="min-w-32">
                    {f.missing.length > 0 ? f.missing.map(formatMonth).join(", ") : t("sources.noMissing")}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Detailed>
      <NextStep step={{ link: ACCOUNTS, label: t("sources.openAccounts") }} />
    </div>
  );
}
