// The accounts of a group (F07's account map): each with its balance and the day it knows of, its TL value where the
// documents give a rate, how far its documents reach, and this month's money in and out. The simple view shows each
// account as a card; the detailed view, a table of every value. Each account can be chosen, to see several together.

import { useTranslation } from "react-i18next";

import type { AccountItem, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Detailed, Simple } from "../Preferences";
import { Money } from "../ui/Money";
import { ScreenLink } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const CHECKBOX = cn(
  "size-4 accent-teal-700 dark:accent-teal-400",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

interface AccountListProps {
  accounts: readonly AccountItem[];
  caption: string; // the table's name for screen readers: the group's
  labels: Labels;
  selected: ReadonlySet<string>;
  onSelect: (id: string, on: boolean) => void;
}

export function AccountList({ accounts, caption, labels, selected, onSelect }: AccountListProps) {
  const { t } = useTranslation("accounts");
  return (
    <>
      <Simple>
        <ul className="grid gap-3 md:grid-cols-2">
          {accounts.map((item) => (
            <li
              key={item.account.id}
              className={cn(
                "flex flex-col gap-2 rounded-xl border p-4",
                selected.has(item.account.id)
                  ? "border-teal-600 bg-teal-50/40 dark:border-teal-500 dark:bg-teal-950/40"
                  : "border-zinc-200 dark:border-zinc-800",
              )}
            >
              <AccountCard item={item} labels={labels} />
              {/* Said in words beside the box, so what it does is plain: several chosen accounts are summed above. */}
              <label className="flex min-h-8 cursor-pointer items-center gap-2 self-start text-xs text-zinc-700 dark:text-zinc-200">
                <input
                  type="checkbox"
                  aria-label={t("account.select", { name: item.account.label })}
                  checked={selected.has(item.account.id)}
                  onChange={(event) => onSelect(item.account.id, event.target.checked)}
                  className={cn(CHECKBOX, "shrink-0")}
                />
                {t("account.selectShort")}
              </label>
            </li>
          ))}
        </ul>
      </Simple>
      <Detailed>
        <AccountTable accounts={accounts} caption={caption} labels={labels} selected={selected} onSelect={onSelect} />
      </Detailed>
    </>
  );
}

function AccountCard({ item, labels }: { item: AccountItem; labels: Labels }) {
  const { t } = useTranslation("accounts");
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
      <div>
        <ScreenLink link={item.link} className="font-medium wrap-break-word">
          {item.account.label}
        </ScreenLink>
        <p className={SMALL}>{[item.bank, labelOf(labels, "AccountType", item.type)].filter(Boolean).join(" · ")}</p>
      </div>
      <Balance item={item} />
      <Freshness item={item} />
      <MonthFlow item={item} />
      {item.note ? <p className={SMALL}>{item.note}</p> : null}
    </div>
  );
}

/** The balance in its own currency with how sure it is, the day it knows of, and its TL value for another currency. */
export function Balance({ item }: { item: AccountItem }) {
  const { t } = useTranslation("accounts");
  if (item.balance === null) {
    return <p className="text-base">{t("account.balanceUnknown")}</p>;
  }
  return (
    <div>
      <p className="flex flex-wrap items-baseline gap-x-2">
        <Money value={item.balance} certainty={item.certainty ?? "confirmed"} className="text-base font-semibold" />
        {item.day ? <span className={SMALL}>{t("account.asOf", { day: formatDay(item.day) })}</span> : null}
      </p>
      {item.balance.currency !== "TRY" ? (
        <p className={SMALL}>
          {item.value ? t("account.inTl", { value: formatMoney(item.value) }) : t("account.valueUnknown")}
        </p>
      ) : null}
    </div>
  );
}

function Freshness({ item }: { item: AccountItem }) {
  const { t } = useTranslation("accounts");
  const f = item.freshness;
  if (!f) {
    return null;
  }
  return (
    <div className={cn("flex flex-col items-start gap-1", SMALL)}>
      <p>
        {[f.note, f.behind === 0 ? t("account.today") : t("account.behind", { count: f.behind })]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {f.late ? <Status tone="warning">{t("account.late")}</Status> : null}
      {f.missing.length > 0 ? (
        <Status tone="warning">{t("account.missing", { months: f.missing.map(formatMonth).join(", ") })}</Status>
      ) : null}
    </div>
  );
}

function MonthFlow({ item }: { item: AccountItem }) {
  const { t } = useTranslation("accounts");
  const m = item.month;
  if (m.rows === 0) {
    return (
      <p className={SMALL}>
        {t("account.monthNone", { month: formatMonth(m.month) })}
        {m.note ? ` (${m.note})` : ""}
      </p>
    );
  }
  return (
    <p className={SMALL}>
      {t("account.month", {
        month: formatMonth(m.month),
        moneyIn: formatMoney(m.money_in),
        moneyOut: formatMoney(m.money_out),
      })}
      {m.provisional > 0 ? ` ${t("account.monthProvisional", { count: m.provisional })}` : ""}
      {m.note ? `; ${m.note}` : ""}
    </p>
  );
}

function AccountTable({ accounts, caption, labels, selected, onSelect }: AccountListProps) {
  const { t } = useTranslation("accounts");
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <Th className="w-10">
            <span className="sr-only">{t("table.select")}</span>
          </Th>
          <Th>{t("table.account")}</Th>
          <Th className="text-right">{t("table.balance")}</Th>
          <Th className="text-right">{t("table.value")}</Th>
          <Th>{t("table.freshness")}</Th>
          <Th className="text-right">{t("table.moneyIn")}</Th>
          <Th className="text-right">{t("table.moneyOut")}</Th>
          <Th>{t("table.note")}</Th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((item) => (
          <tr key={item.account.id}>
            <Td>
              <input
                type="checkbox"
                aria-label={t("account.select", { name: item.account.label })}
                checked={selected.has(item.account.id)}
                onChange={(event) => onSelect(item.account.id, event.target.checked)}
                className={CHECKBOX}
              />
            </Td>
            <Td className="min-w-48">
              <ScreenLink link={item.link} className="font-medium">
                {item.account.label}
              </ScreenLink>
              <span className={cn("block", SMALL)}>
                {[item.bank, labelOf(labels, "AccountType", item.type), item.alias ? item.label : ""]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </Td>
            <Td className="text-right">
              {item.balance ? (
                <Money value={item.balance} certainty={item.certainty ?? "confirmed"} className="justify-end" />
              ) : (
                "—"
              )}
              {item.day ? <span className={cn("block", SMALL)}>{formatDay(item.day)}</span> : null}
            </Td>
            <Td className="whitespace-nowrap text-right tabular-nums">
              {item.value ? formatMoney(item.value) : t("table.unknown")}
            </Td>
            <Td className={SMALL}>
              {item.freshness
                ? [
                    item.freshness.note,
                    labelOf(labels, "DocumentKind", item.freshness.kind),
                    formatDay(item.freshness.last),
                    item.freshness.late ? t("account.late") : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "—"}
            </Td>
            <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(item.month.money_in)}</Td>
            <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(item.month.money_out)}</Td>
            <Td className={SMALL}>{[item.note, item.month.note].filter(Boolean).join(" · ")}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
