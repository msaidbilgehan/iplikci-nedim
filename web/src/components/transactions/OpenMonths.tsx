// What the listed days' months still wait for (F04, F11): a month that has not closed lists its rows as far as its
// documents go. One waiting for its statements is not missing anything: each account's awaited document is named
// with its days and its cut, so a row not here yet is known to be coming, and by when. One missing a document or
// wanting a check says so; the month that runs runs on. Each but the running month leads to its month-end page. The
// service says which months and accounts the listed days and the account filter touch (TransactionsOut.open).

import { useTranslation } from "react-i18next";

import type { OpenMonth } from "../../api/types";
import { Alert } from "../ui/Alert";
import { NextStep } from "../ui/Say";

export function OpenMonths({ months }: { months: readonly OpenMonth[] }) {
  const { t } = useTranslation("transactions");
  if (months.length === 0) {
    return null;
  }
  return (
    <section aria-label={t("unclosed.label")} className="flex flex-col gap-2">
      {months.map((month) => (
        <OpenMonthNote key={month.month} month={month} />
      ))}
    </section>
  );
}

function OpenMonthNote({ month }: { month: OpenMonth }) {
  const { t } = useTranslation("transactions");
  if (month.status === "closed") {
    return null; // the service lists no closed month; a closed one has nothing to say here
  }
  const title =
    month.status === "waiting"
      ? t("unclosed.waiting", { context: month.closes_by ? "" : "undated", month: month.month, day: month.closes_by ?? "" })
      : t(`unclosed.${month.status}`, { month: month.month });
  return (
    <Alert tone={month.status === "check" ? "warning" : "neutral"} title={title}>
      {month.accounts.length > 0 ? (
        <ul className="list-disc pl-5">
          {month.accounts.map((held) => (
            <li key={held.account.id}>
              {/* A late statement's words say it is late: "… 14 Ekim–13 Kasım ekstresinde (gecikti)". */}
              <span className="font-medium">{held.account.label}</span>: {held.waiting_for}
            </li>
          ))}
        </ul>
      ) : null}
      {month.status === "running" ? null : (
        <NextStep step={{ link: month.link, label: t("unclosed.page", { month: month.month }) }} className="mt-1" />
      )}
    </Alert>
  );
}
