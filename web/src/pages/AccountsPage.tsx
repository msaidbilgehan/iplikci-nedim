// The Hesaplar screen (F07): the open accounts in their groups — credit cards, current, deposit, overdraft, foreign
// currency, gold, brokerage, loans — each group with its assets and debts apart and its total, every account with its
// balance, how far its documents reach and this month's money in and out; the closed accounts apart, in no total.
// Accounts can be chosen to see them together, and the money's way between them shows as a Sankey with its table.

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAccounts, useLabels } from "../api/queries";
import type { AccountItem, Accounts, Labels } from "../api/types";
import { AccountList } from "../components/accounts/AccountList";
import { Combined } from "../components/accounts/Combined";
import { FlowsSection } from "../components/accounts/Flows";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Card } from "../components/ui/Card";
import { Explain } from "../components/ui/Explain";
import { PageHeader } from "../components/ui/PageHeader";
import { NextStep, Say } from "../components/ui/Say";
import { formatMoney } from "../lib/format";
import { labelOf } from "../lib/labels";

const DOCUMENTS = { screen: "documents", id: "", query: {} } as const;
const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const TOTAL = "min-w-36 flex-1 rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900";

export default function AccountsPage() {
  const { t } = useTranslation("accounts");
  const accounts = useAccounts();
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {accounts.isPending ? <Loading /> : null}
      {accounts.isError ? <Failure error={accounts.error} onRetry={() => void accounts.refetch()} /> : null}
      {accounts.data ? <AccountMap found={accounts.data} labels={labels} /> : null}
    </div>
  );
}

function AccountMap({ found, labels }: { found: Accounts; labels: Labels }) {
  const { t } = useTranslation("accounts");
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const every = [...found.groups.flatMap((group) => group.accounts), ...found.closed];
  if (every.length === 0) {
    return (
      <Empty title={t("empty")}>
        <p>{t("emptyText")}</p>
        <NextStep step={{ link: DOCUMENTS, label: t("emptyNext") }} className="mt-2" />
      </Empty>
    );
  }
  const select = (id: string, on: boolean) =>
    setChosen((was) => {
      const next = new Set(was);
      if (on) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  const open = found.groups.flatMap((group) => group.accounts);
  const picked: AccountItem[] = every.filter((item) => chosen.has(item.account.id));
  return (
    <>
      <section aria-label={t("summary.label")} className="flex flex-col gap-2">
        <Say>
          {t("say", {
            assets: formatMoney(found.assets),
            debts: formatMoney(found.debts),
            total: formatMoney(found.total),
          })}
          <LeftOut accounts={open} />
        </Say>
        {/* Side by side while the amounts fit; on a phone the net total takes a row of its own. */}
        <dl className="flex flex-wrap gap-3 sm:max-w-xl">
          {(
            [
              ["assets", found.assets],
              ["debts", found.debts],
              ["total", found.total],
            ] as const
          ).map(([key, value]) => (
            <div key={key} className={TOTAL}>
              <dt className="text-sm text-zinc-600 dark:text-zinc-300">{t(`summary.${key}`)}</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatMoney(value)}</dd>
            </div>
          ))}
        </dl>
        {found.note ? (
          <Explain>
            <p>{found.note}</p>
          </Explain>
        ) : null}
      </section>
      <Combined accounts={picked} onClear={() => setChosen(new Set())} />
      {found.groups.map((group) => {
        const name = labelOf(labels, "AccountGroup", group.group);
        return (
          <Card
            key={group.group}
            title={name}
            action={<span className="text-sm font-semibold tabular-nums">{formatMoney(group.total)}</span>}
          >
            <p className={`mb-3 ${SMALL}`}>
              {t("group.figures", { assets: formatMoney(group.assets), debts: formatMoney(group.debts) })}
              {group.unvalued > 0 ? (
                <span className="block">
                  <LeftOut accounts={group.accounts} />
                </span>
              ) : null}
            </p>
            <AccountList
              accounts={group.accounts}
              caption={t("group.caption", { group: name })}
              labels={labels}
              selected={chosen}
              onSelect={select}
            />
          </Card>
        );
      })}
      {found.closed.length > 0 ? (
        <Card title={t("closed.title")}>
          <p className={`mb-3 ${SMALL}`}>{t("closed.text")}</p>
          <AccountList
            accounts={found.closed}
            caption={t("closed.title")}
            labels={labels}
            selected={chosen}
            onSelect={select}
          />
        </Card>
      ) : null}
      <FlowsSection labels={labels} />
    </>
  );
}

/**
 * Why some accounts are in no total, in words: no document gives the balance, or no rate gives a balance in another
 * currency its TL value. Nothing when every account counts.
 */
function LeftOut({ accounts }: { accounts: readonly AccountItem[] }) {
  const { t } = useTranslation("accounts");
  const noBalance = accounts.filter((item) => item.balance === null).length;
  const noValue = accounts.filter((item) => item.balance !== null && item.value === null).length;
  if (noBalance > 0 && noValue > 0) {
    return <> {t("leftOut.both", { noBalance, noValue })}</>;
  }
  if (noBalance > 0) {
    return <> {t("leftOut.noBalance", { count: noBalance })}</>;
  }
  return noValue > 0 ? <> {t("leftOut.noValue", { count: noValue })}</> : null;
}
