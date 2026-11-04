// Money that came into an account which no document tells yet (F07, F12): the account paid out more than its documents
// show it held, so the money came in first, from where the documents most likely still count it (another own account,
// an FX sale). The account's balance is zero for it and the totals take it off; this says so beside the totals, with
// the account and the amount, so the sum adds up in front of the user.

import { useTranslation } from "react-i18next";

import type { Money, Untold } from "../../api/types";
import { formatMoney } from "../../lib/format";

/** The money no document tells yet, added up; null when there is none. A sentence says it was taken off. */
export function untoldTotal(untold: readonly Untold[]): Money | null {
  if (untold.length === 0) {
    return null;
  }
  return { minor: untold.reduce((sum, u) => sum + u.value.minor, 0), currency: "TRY" };
}

/** The same as a figure beside the assets and the debts: below zero, as the totals take it off. */
export function untoldTaken(untold: readonly Untold[]): Money | null {
  const total = untoldTotal(untold);
  return total ? { ...total, minor: -total.minor } : null;
}

/** The money in no document tells yet, a sentence for each account it came into; nothing when there is none. */
export function UntoldNote({ untold, className }: { untold: readonly Untold[]; className?: string }) {
  const { t } = useTranslation("common");
  if (untold.length === 0) {
    return null;
  }
  return (
    <ul className={className}>
      {untold.map((u) => (
        <li key={u.account.id}>{t("untold.text", { account: u.account.label, amount: formatMoney(u.value) })}</li>
      ))}
    </ul>
  );
}
