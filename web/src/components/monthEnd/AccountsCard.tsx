// Each account's closing in one month (F11): its status as the account's closing reads it, what it waits for ("TEB
// Bonus •4321: 19–31 Ekim, 19 Ekim–18 Kasım ekstresinde": a card statement runs from one cut to the next), and the
// service's note on it. The detailed view adds the days its documents cover, the next cut (the day the statement
// before prints, or "~" a month on when it prints none), the documents themselves with their checks, the receipts and
// the balance a list prints.

import { useTranslation } from "react-i18next";

import type { Labels, MonthEndAccount, MonthStatus } from "../../api/types";
import { formatDay, formatMoney, formatPeriod } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Say, ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";
import { MonthStatusMark, SMALL } from "./parts";

interface AccountsCardProps {
  accounts: readonly MonthEndAccount[];
  status: MonthStatus; // the month's
  labels: Labels;
}

export function AccountsCard({ accounts, status, labels }: AccountsCardProps) {
  const { t } = useTranslation("monthEnd");
  const open = accounts.filter((a) => a.blocking && a.status !== "closed");
  let say = t("accounts.sayClosed");
  if (status === "running") {
    say = open.length > 0 ? t("accounts.sayRunning", { count: open.length }) : t("accounts.sayRunningCovered");
  } else if (open.length > 0) {
    say = t("accounts.sayOpen", { count: open.length });
  }
  return (
    <Card title={t("accounts.title")}>
      {accounts.length === 0 ? (
        <p className="text-sm">{t("accounts.none")}</p>
      ) : (
        <>
          <Say>{say}</Say>
          <Simple>
            <ul className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
              {accounts.map((a) => (
                <li key={a.account.id} className="flex flex-col gap-1 py-2 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <ScreenLink link={{ screen: "account", id: a.account.id, query: {} }} className="font-medium">
                      {a.account.label}
                    </ScreenLink>
                    <MonthStatusMark status={a.status} labels={labels} label={a.label} />
                  </div>
                  {a.waiting_for ? <p>{t("accounts.waiting", { what: a.waiting_for })}</p> : null}
                  <Marks account={a} />
                  {a.note ? <p className={SMALL}>{a.note}</p> : null}
                </li>
              ))}
            </ul>
          </Simple>
          <Detailed>
            <AccountsTable accounts={accounts} labels={labels} />
          </Detailed>
        </>
      )}
    </Card>
  );
}

/** What else is to know of an account this month: late, never holding the month open, known from a passbook only. */
function Marks({ account }: { account: MonthEndAccount }) {
  const { t } = useTranslation("monthEnd");
  if (!account.late && account.blocking && !account.untracked) {
    return null;
  }
  return (
    <p className="flex flex-wrap items-center gap-2">
      {account.late ? <Badge tone="warning">{t("accounts.late")}</Badge> : null}
      {account.blocking ? null : <Badge tone="neutral">{t("accounts.notBlocking")}</Badge>}
      {account.untracked ? <span className={SMALL}>{t("accounts.untracked")}</span> : null}
    </p>
  );
}

function AccountsTable({ accounts, labels }: { accounts: readonly MonthEndAccount[]; labels: Labels }) {
  const { t } = useTranslation("monthEnd");
  return (
    <Table>
      <caption className="sr-only">{t("accounts.caption")}</caption>
      <thead>
        <tr>
          <Th>{t("accounts.account")}</Th>
          <Th>{t("accounts.statusName")}</Th>
          <Th>{t("accounts.days")}</Th>
          <Th>{t("accounts.expected")}</Th>
          <Th>{t("accounts.documents")}</Th>
          <Th>{t("accounts.receiptsName")}</Th>
          <Th className="text-right">{t("accounts.balanceName")}</Th>
          <Th>{t("accounts.note")}</Th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((a) => {
          const r = a.receipts;
          const receipts = r.matched + r.provisional + r.unmatched + r.no_statement;
          return (
            <tr key={a.account.id}>
              <Td className="min-w-40">
                <ScreenLink link={{ screen: "account", id: a.account.id, query: {} }} className="font-medium">
                  {a.account.label}
                </ScreenLink>
              </Td>
              <Td>
                <MonthStatusMark status={a.status} labels={labels} label={a.label} />
                <div className="mt-1">
                  <Marks account={a} />
                </div>
              </Td>
              <Td className="min-w-40">
                {t("accounts.covered", { covered: a.covered, needed: a.needed })}
                {a.open.length > 0 ? (
                  <span className={`block ${SMALL}`}>
                    {t("accounts.open", { days: a.open.map((o) => formatPeriod(o.start, o.end)).join(", ") })}
                  </span>
                ) : null}
              </Td>
              <Td className="min-w-40">
                {a.waiting_for || "—"}
                {a.next_cut ? (
                  <span className={`block ${SMALL}`}>
                    {t("accounts.nextCut", {
                      context: a.next_cut_printed ? "" : "reckoned",
                      day: formatDay(a.next_cut),
                    })}
                  </span>
                ) : null}
              </Td>
              <Td className="min-w-48">
                {a.statements.length > 0 ? (
                  <ul className="flex flex-col gap-1">
                    {a.statements.map((s) => (
                      <li key={`${s.document}-${s.start}`}>
                        <ScreenLink link={{ screen: "document", id: s.document, query: {} }}>
                          {t("accounts.statement", {
                            kind: s.card ? t("accounts.card") : t("accounts.list"),
                            period: formatPeriod(s.start, s.end),
                          })}
                        </ScreenLink>
                        <span className={`block ${SMALL}`}>{labelOf(labels, "StatementCheck", s.check)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </Td>
              <Td className={SMALL}>
                {receipts > 0
                  ? t("accounts.receipts", {
                      matched: r.matched,
                      provisional: r.provisional,
                      unmatched: r.unmatched,
                      none: r.no_statement,
                    })
                  : "—"}
              </Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                {a.balance ? formatMoney(a.balance) : "—"}
              </Td>
              <Td className={`min-w-48 ${SMALL}`}>{a.note || "—"}</Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
