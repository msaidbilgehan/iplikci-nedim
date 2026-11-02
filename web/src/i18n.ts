// The interface's words (ADR-0008: react-i18next, Turkish only). Each area has a namespace, a JSON file under
// locales/tr/, and reads it with useTranslation("<namespace>"); i18next.d.ts types the keys from those files, so a
// missing or misspelt key fails the typecheck. A new screen adds locales/tr/<screen>.json and registers it below.
//
// Two kinds of words are not here. Codes' Turkish names come from /api/labels, the service's one mapping module. And a
// suffix after a number or a year is never typed into a string: a formatter attaches it as lib/turkish.ts builds it,
// so "{{year, ablative}}" reads "2026'dan" and "{{share, percentPossessive}}" reads "%64'ü". A number is written with
// its thousands ("1.000'de"); a string is written as it is given ("2026'da").

import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import type { Money } from "./api/types";
import { formatDay, formatMoney, formatMonth } from "./lib/format";
import {
  ablative,
  fromMonth,
  inMonth,
  locative,
  onDay,
  percent,
  percentPossessive,
  possessive,
  possessiveLocative,
} from "./lib/turkish";
import accounts from "./locales/tr/accounts.json";
import calendar from "./locales/tr/calendar.json";
import charts from "./locales/tr/charts.json";
import common from "./locales/tr/common.json";
import dashboard from "./locales/tr/dashboard.json";
import documents from "./locales/tr/documents.json";
import extension from "./locales/tr/extension.json";
import feed from "./locales/tr/feed.json";
import fx from "./locales/tr/fx.json";
import glossary from "./locales/tr/glossary.json";
import insights from "./locales/tr/insights.json";
import invoices from "./locales/tr/invoices.json";
import monthEnd from "./locales/tr/monthEnd.json";
import notifications from "./locales/tr/notifications.json";
import shell from "./locales/tr/shell.json";
import subscriptions from "./locales/tr/subscriptions.json";
import system from "./locales/tr/system.json";
import transactions from "./locales/tr/transactions.json";

export const defaultNS = "common";
export const resources = {
  tr: {
    common,
    shell,
    glossary,
    charts,
    feed,
    dashboard,
    transactions,
    accounts,
    documents,
    extension,
    subscriptions,
    calendar,
    insights,
    invoices,
    fx,
    system,
    monthEnd,
    notifications,
  },
} as const;

const WHOLE = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0, useGrouping: "always" });

/** A number as it stands before its suffix, and the number the suffix is chosen by. */
function written(value: unknown): [string, number] {
  if (typeof value === "number") {
    return [WHOLE.format(value), value];
  }
  const text = String(value);
  return [text, Number(text.replaceAll(".", "").replace(",", "."))];
}

function suffixed(suffix: (n: number) => string): (value: unknown) => string {
  return (value) => {
    const [text, n] = written(value);
    return `${text}${suffix(n)}`;
  };
}

void i18next.use(initReactI18next).init({
  lng: "tr",
  fallbackLng: "tr",
  supportedLngs: ["tr"],
  ns: Object.keys(resources.tr),
  defaultNS,
  resources,
  initAsync: false, // the words are bundled: t() works as soon as this module has run
  interpolation: { escapeValue: false }, // React escapes what it renders
  react: { useSuspense: false },
});

const FORMATTERS: Record<string, (value: unknown) => string> = {
  locative: suffixed(locative),
  ablative: suffixed(ablative),
  possessive: suffixed(possessive),
  possessiveLocative: suffixed(possessiveLocative),
  percent: (value) => percent(Number(value)),
  percentPossessive: (value) => percentPossessive(Number(value)),
  money: (value) => formatMoney(value as Money),
  day: (value) => formatDay(String(value)),
  month: (value) => formatMonth(String(value)),
  onDay: (value) => onDay(String(value)),
  inMonth: (value) => inMonth(String(value)),
  fromMonth: (value) => fromMonth(String(value)),
};
for (const [name, format] of Object.entries(FORMATTERS)) {
  i18next.services.formatter?.add(name, format);
}

export default i18next;
