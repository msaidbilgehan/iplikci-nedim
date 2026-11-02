// Several accounts seen together (F07's "birleşik akış"): what the chosen accounts are worth together in TL, the ones
// without a TL value apart, their money in and out this month, and their rows together on the Transactions screen,
// with what those add up to.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { AccountItem } from "../../api/types";
import { formatMoney } from "../../lib/format";
import { Button } from "../ui/Button";
import { ArrowRightIcon } from "../ui/Icons";
import { STEP } from "../ui/Say";

interface CombinedProps {
  accounts: readonly AccountItem[]; // the chosen ones
  onClear: () => void;
}

const tl = (minor: number) => ({ minor, currency: "TRY" });

export function Combined({ accounts, onClear }: CombinedProps) {
  const { t } = useTranslation("accounts");
  if (accounts.length === 0) {
    return null;
  }
  const valued = accounts.filter((item) => item.value !== null);
  const worth = valued.reduce((sum, item) => sum + (item.value?.minor ?? 0), 0);
  const moneyIn = accounts.reduce((sum, item) => sum + item.month.money_in.minor, 0);
  const moneyOut = accounts.reduce((sum, item) => sum + item.month.money_out.minor, 0);
  const month = accounts[0]?.month.month ?? "";
  const said = [
    t("combined.worth", { count: accounts.length, worth: formatMoney(tl(worth)) }),
    accounts.length > valued.length ? t("combined.unvalued", { count: accounts.length - valued.length }) : "",
    t("combined.month", {
      month,
      moneyIn: formatMoney(tl(moneyIn)),
      moneyOut: formatMoney(tl(moneyOut)),
    }),
  ].filter(Boolean);
  return (
    <section
      aria-label={t("combined.label")}
      className="flex flex-col gap-2 rounded-lg border border-teal-600 bg-teal-50 p-3 dark:border-teal-400 dark:bg-teal-950"
    >
      <p aria-live="polite" className="text-sm">
        {said.join(" ")}
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {/* The Transactions screen narrowed by every chosen account: a filter of many values, in the API's names. */}
        <Link to={`/islemler?${new URLSearchParams(accounts.map((item) => ["account", item.account.id]))}`} className={STEP}>
          {t("combined.rows")}
          <ArrowRightIcon className="size-4 shrink-0" />
        </Link>
        <Button variant="secondary" onClick={onClear}>
          {t("combined.clear")}
        </Button>
      </div>
    </section>
  );
}
