// The feed's events (F05): newest first under their days' headings, narrowed by account, kind and certainty. The
// filters live in the address (?account=…&kind=…&certainty=…), in the API's names. The event stream refreshes the list
// as events come; those that came after it was first shown are marked, and a screen reader hears how many arrived.

import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { choosesNothing, type FeedFilter, useFeed } from "../../api/queries";
import type { FeedItem, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatWeekday, localDay } from "../../lib/format";
import { selectionOf, sentOf, withSelection } from "../../lib/selection";
import { certaintyOptions, kindOptions, sentKinds } from "../filters";
import { useView } from "../Preferences";
import { Empty, Failure, Loading } from "../QueryState";
import { Button } from "../ui/Button";
import {
  type FilterChip,
  FilterChips,
  type FilterOption,
  FilterPopover,
  type Selection,
  useSelectionSummary,
} from "../ui/FilterPopover";
import { Say } from "../ui/Say";
import { EventCard } from "./EventCard";

const FILTERS = ["account", "kind", "certainty"] as const;
type FilterName = (typeof FILTERS)[number];

const NOTIFICATIONS = { screen: "notifications", id: "", query: {} } as const;

/** The events by the local day they happened on, newest first as the feed gives them. */
function byDay(items: readonly FeedItem[]): Array<[string, FeedItem[]]> {
  const days = new Map<string, FeedItem[]>();
  for (const item of items) {
    const day = localDay(item.at);
    days.set(day, [...(days.get(day) ?? []), item]);
  }
  return [...days];
}

interface EventsProps {
  labels: Labels;
  accounts: readonly FilterOption[];
}

export function EventsSection({ labels, accounts }: EventsProps) {
  const { t } = useTranslation("feed");
  const heading = useId();
  const summarize = useSelectionSummary();
  const [params, setParams] = useSearchParams();
  const chosen: Record<FilterName, Selection> = {
    account: selectionOf(params, "account"),
    kind: selectionOf(params, "kind"),
    certainty: selectionOf(params, "certainty"),
  };
  const options: Record<FilterName, readonly FilterOption[]> = {
    account: accounts,
    kind: kindOptions(labels, (group) => t(`events.kinds.${group}`)),
    certainty: certaintyOptions(labels),
  };
  const kinds = sentOf(chosen.kind);
  const filter: FeedFilter = {
    account: sentOf(chosen.account),
    kind: kinds === null ? null : sentKinds(kinds, options.kind.map((option) => option.value)),
    certainty: sentOf(chosen.certainty),
  };
  const feed = useFeed(filter);
  const set = (name: FilterName, selected: Selection) => setParams((was) => withSelection(was, name, selected));
  const reset = () =>
    setParams((was) => {
      const next = new URLSearchParams(was);
      for (const name of FILTERS) {
        next.delete(name);
      }
      return next;
    });
  const names: Record<FilterName, string> = {
    account: t("events.account"),
    kind: t("events.kind"),
    certainty: t("events.certainty"),
  };
  const chips: FilterChip[] = FILTERS.filter((name) => chosen[name] !== null).map((name) => ({
    key: name,
    name: names[name],
    value: summarize(chosen[name], options[name]),
    onRemove: () => set(name, null),
  }));

  const items = feed.data?.pages.flatMap((page) => page.items) ?? [];
  const arrived = useArrivals(JSON.stringify(filter), feed.isSuccess ? (items[0]?.id ?? 0) : null);
  const fresh = items.filter((item) => item.id > arrived).length;
  const nothing = choosesNothing(filter);
  const filtered = chips.length > 0;

  return (
    <section aria-labelledby={heading} className="flex flex-col gap-3">
      <h2 id={heading} className="sr-only">
        {t("events.title")}
      </h2>
      <Say next={{ link: NOTIFICATIONS, label: t("events.next") }}>{t("events.say")}</Say>
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.filter((name) => options[name].length > 0).map((name) => (
          <FilterPopover
            key={name}
            label={names[name]}
            options={options[name]}
            selected={chosen[name]}
            onChange={(selected) => set(name, selected)}
          />
        ))}
      </div>
      <FilterChips chips={chips} {...(chips.length > 1 ? { onReset: reset } : {})} />
      {chosen.certainty ? <p className="text-xs text-zinc-600 dark:text-zinc-300">{t("events.certaintyNote")}</p> : null}
      <p aria-live="polite" className="sr-only">
        {fresh > 0 ? t("events.arrived", { count: fresh }) : ""}
      </p>
      {nothing ? (
        <Empty title={t("events.emptyFiltered")} />
      ) : feed.isPending ? (
        <Loading />
      ) : feed.isError ? (
        <Failure error={feed.error} onRetry={() => void feed.refetch()} />
      ) : items.length === 0 ? (
        <Empty title={filtered ? t("events.emptyFiltered") : t("events.empty")}>
          {filtered ? null : t("events.emptyText")}
        </Empty>
      ) : (
        <EventDays items={items} labels={labels} arrived={arrived} />
      )}
      {feed.hasNextPage && !nothing ? (
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => void feed.fetchNextPage()}
          disabled={feed.isFetchingNextPage}
        >
          {feed.isFetchingNextPage ? t("events.loadingMore") : t("events.more")}
        </Button>
      ) : null}
    </section>
  );
}

/**
 * The newest event id when the list with these filters was first shown: events above it arrived since. Kept per
 * filter, so narrowing the list marks nothing as new. Until the list has loaded every event counts as seen.
 */
function useArrivals(filterKey: string, newest: number | null): number {
  const [seen, setSeen] = useState<{ key: string; upTo: number } | null>(null);
  if (newest !== null && seen?.key !== filterKey) {
    setSeen({ key: filterKey, upTo: newest }); // React's way to keep a value from an earlier render
  }
  return seen?.key === filterKey ? seen.upTo : Number.POSITIVE_INFINITY;
}

// What reading a document came to: once one of these is in the list, its "arrived" says nothing more.
const READ_KINDS: ReadonlySet<string> = new Set(["document.processed", "document.unprocessed", "document.unreadable"]);

/** The simple view's list: a document's arrival left out when the list also says how its reading went. */
export function foldArrivals(items: readonly FeedItem[]): FeedItem[] {
  const read = new Set(
    items.filter((item) => READ_KINDS.has(item.kind) && item.document).map((item) => item.document?.sha256),
  );
  return items.filter(
    (item) => !(item.kind === "document.received" && item.document && read.has(item.document.sha256)),
  );
}

function EventDays({ items, labels, arrived }: { items: FeedItem[]; labels: Labels; arrived: number }) {
  const { t } = useTranslation("feed");
  const { view } = useView();
  const today = localDay(new Date().toISOString());
  const yesterday = localDay(new Date(Date.now() - 86_400_000).toISOString());
  const heading = (day: string) =>
    day === today ? t("events.today") : day === yesterday ? t("events.yesterday") : formatWeekday(day);
  const shown = view === "simple" ? foldArrivals(items) : items;
  return (
    <ol className="flex flex-col gap-5">
      {byDay(shown).map(([day, list]) => (
        <li key={day}>
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-200">{heading(day)}</h3>
          <ol
            className={cn(
              "divide-y divide-zinc-100 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm",
              "dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900",
            )}
          >
            {list.map((item) => (
              <li key={item.id}>
                <EventCard item={item} labels={labels} isNew={item.id > arrived} />
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ol>
  );
}
