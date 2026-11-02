// A month's regular payments (F11): those paid this month with what was paid, and those expected and not seen yet
// with the day they were expected. A paid one leads to its rows; the detailed view lists them all with what each
// costs a month.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { MonthEndRegular } from "../../api/types";
import { formatDay, formatMoney } from "../../lib/format";
import { Detailed, Simple } from "../Preferences";
import { Card } from "../ui/Card";
import { Say } from "../ui/Say";
import { Status } from "../ui/Status";
import { Table, Td, Th } from "../ui/Table";
import { ROW_LINK, SMALL } from "./parts";

interface RegularCardProps {
  regular: readonly MonthEndRegular[];
  rowHref: (fingerprint: string) => string;
}

/** Keys for the payments: two series may share a payee and a category (two shops of one chain). */
function keyed(regular: readonly MonthEndRegular[]): Array<[string, MonthEndRegular]> {
  const seen = new Map<string, number>();
  return regular.map((r) => {
    const base = `${r.payee}\u0000${r.category}\u0000${r.monthly.minor}`;
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    return [count === 0 ? base : `${base}\u0000${count}`, r];
  });
}

export function RegularCard({ regular, rowHref }: RegularCardProps) {
  const { t } = useTranslation("monthEnd");
  if (regular.length === 0) {
    return (
      <Card title={t("regular.title")}>
        <p className="text-sm">{t("regular.none")}</p>
      </Card>
    );
  }
  const paid = regular.filter((r) => r.paid.length > 0).length;
  const expected = regular.filter((r) => r.paid.length === 0 && r.expected !== null).length;
  const items = keyed(regular);
  return (
    <Card title={t("regular.title")}>
      <Say>{t("regular.say", { paid, expected })}</Say>
      <Simple>
        <ul className="flex flex-col divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
          {items.map(([key, r]) => {
            const first = r.paid[0];
            return (
              <li key={key} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 py-1.5">
                <span className="min-w-0">
                  {first ? (
                    <Link to={rowHref(first.fingerprint)} className={`font-medium ${ROW_LINK}`}>
                      {r.payee}
                    </Link>
                  ) : (
                    <span className="font-medium">{r.payee}</span>
                  )}
                  <span className={`block ${SMALL}`}>
                    {r.category} · {t("regular.monthly", { amount: formatMoney(r.monthly) })}
                  </span>
                </span>
                <State regular={r} />
              </li>
            );
          })}
        </ul>
      </Simple>
      <Detailed>
        <Table>
          <caption className="sr-only">{t("regular.caption")}</caption>
          <thead>
            <tr>
              <Th>{t("regular.payment")}</Th>
              <Th>{t("regular.category")}</Th>
              <Th className="text-right">{t("regular.thisMonth")}</Th>
              <Th className="text-right">{t("regular.monthlyName")}</Th>
              <Th>{t("regular.state")}</Th>
              <Th>{t("regular.rows")}</Th>
            </tr>
          </thead>
          <tbody>
            {items.map(([key, r]) => (
              <tr key={key}>
                <Td className="font-medium">{r.payee}</Td>
                <Td>{r.category}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(r.this_month)}</Td>
                <Td className="whitespace-nowrap text-right tabular-nums">{formatMoney(r.monthly)}</Td>
                <Td>
                  <State regular={r} />
                </Td>
                <Td>
                  {r.paid.length > 0 ? (
                    <ul className="flex flex-col gap-0.5">
                      {r.paid.map((row) => (
                        <li key={row.fingerprint}>
                          <Link to={rowHref(row.fingerprint)} className={ROW_LINK}>
                            {formatDay(row.day)} · {formatMoney(row.amount)}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    "—"
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Detailed>
    </Card>
  );
}

/** Paid, with what was paid; or expected on a day and not seen yet. */
function State({ regular }: { regular: MonthEndRegular }) {
  const { t } = useTranslation("monthEnd");
  if (regular.paid.length > 0) {
    return <Status tone="good">{t("regular.paid", { amount: formatMoney(regular.this_month) })}</Status>;
  }
  if (regular.expected) {
    return <Status tone="neutral">{t("regular.expected", { day: formatDay(regular.expected) })}</Status>;
  }
  return <Status tone="neutral">{t("regular.notSeen")}</Status>;
}
