// A currency's name and its colour on the Döviz screen. Each unit keeps one colour slot (features.md, the charts' rules):
// the lira blue, the euro orange, the dollar green, gold amber; any other currency the neutral grey.

import type { TFunction } from "i18next";

import type { Slot } from "../charts/palette";

const NAMED = ["TRY", "EUR", "USD", "GR"] as const;
type Named = (typeof NAMED)[number];

const SLOTS: Readonly<Record<Named, Slot>> = { TRY: 1, EUR: 2, USD: 3, GR: 4 };

function named(currency: string): currency is Named {
  return (NAMED as readonly string[]).includes(currency);
}

/** "Euro", "Gram altın"; a currency without a Turkish name by its code. */
export function currencyName(t: TFunction<"fx">, currency: string): string {
  return named(currency) ? t(`currency.${currency}`) : currency;
}

export function currencySlot(currency: string): Slot {
  return named(currency) ? SLOTS[currency] : 0;
}
