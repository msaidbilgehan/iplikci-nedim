// The parts of a search of many (F04, "market, kira"): each with how many rows it finds among those the other filters
// keep (TransactionsOut.search_parts), so a part that finds none, a name misspelt say, is told rather than lost among
// the other parts' rows. A part's name lists its rows alone, with their totals; the back button brings the others back.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { SearchPart } from "../../api/types";
import { cn } from "../../lib/cn";
import { filtered } from "./query";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
const LINK = cn("rounded font-medium text-teal-800 underline underline-offset-2 dark:text-teal-300", FOCUS);

interface SearchPartsProps {
  parts: readonly SearchPart[];
  params: URLSearchParams; // the screen's address: a part's link keeps its other filters
}

export function SearchParts({ parts, params }: SearchPartsProps) {
  const { t } = useTranslation("transactions");
  if (parts.length < 2) {
    return null;
  }
  return (
    <section aria-label={t("searchParts.label")} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
      <span className="text-zinc-600 dark:text-zinc-300">{t("searchParts.lead")}</span>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {parts.map((part) => (
          <li key={part.text}>
            <Link
              to={`?${filtered(params, (next) => next.set("q", part.text)).toString()}`}
              aria-label={t("searchParts.only", { part: part.text })}
              className={LINK}
            >
              {part.text}
            </Link>{" "}
            {part.count > 0 ? (
              <span className="tabular-nums">{t("searchParts.count", { count: part.count })}</span>
            ) : (
              <span className="font-medium text-amber-800 dark:text-amber-200">{t("searchParts.none")}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
