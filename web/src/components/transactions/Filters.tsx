// The Transactions screen's filters (F04): the period, the account, the kind, the category (by group), the necessity,
// the certainty, tags and a text search, each kept in the address in the API's names. The İşlemler screen adds a
// named period beside the search ("Bu ay", "Geçen ay", … or days of one's own), which way the money goes and the
// amount's bounds; the Değerlendirme screen, which has its own period presets, keeps the days in the panel. A merchant
// or a group comes with a link from another screen and shows as a chip; every filter that is set has a chip that takes
// it off. The search and the period are always in view, the rest behind one button, so the rows come first.

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useTransactionTags } from "../../api/queries";
import type { CategoryRules, Labels, TagCount } from "../../api/types";
import { liraInput, parseLira } from "../../lib/amount";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { monthDays, SPENDING_KINDS } from "../../lib/rows";
import { searchInWords } from "../../lib/search";
import { selectionOf, withSelection } from "../../lib/selection";
import { SLOT_BG, slotOf } from "../charts/palette";
import { certaintyOptions } from "../filters";
import { Button } from "../ui/Button";
import {
  type ChipAction,
  type FilterChip,
  FilterChips,
  type FilterOption,
  FilterPopover,
  type Selection,
  useSelectionSummary,
} from "../ui/FilterPopover";
import { ChevronDownIcon, FilterIcon } from "../ui/Icons";
import { SearchInput } from "../ui/SearchInput";
import { filtered, MANY, ONE, PERIODS, type PeriodName, periodOf, withPeriod } from "./query";

const INPUT = [
  "min-h-11 rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");
const KINDS = [
  "purchase",
  "refund",
  "interest_fee",
  "p2p_transfer",
  "loan_principal",
  "cash_advance",
  "investment",
  "income",
  "card_payment_no_statement",
  "card_payment",
  "own_transfer",
  "transfer_candidate",
];
const NECESSITIES = ["required", "optional", "unnecessary", "unknown"];
const DIRECTIONS = ["in", "out"] as const;
const SHOWN_TAGS = 12; // the most used tags offered under the tag field
const CUSTOM = "custom"; // the period select's choice of one's own days
const PERIOD_NAMES: ReadonlySet<string> = new Set(["period", "from", "to"]); // the filters that name the days

/** Whether the kinds chosen are the spending's own, as a chart's or a card's link writes them out. */
function isSpending(selected: ReadonlySet<string>): boolean {
  return selected.size === SPENDING_KINDS.length && SPENDING_KINDS.every((kind) => selected.has(kind));
}
const SWATCH = "inline-block size-3 shrink-0 rounded-sm"; // a category's group colour beside its name

/** The days between from and to in words: a whole month by its name, else the two days ("…" for an open end). */
export function daysInWords(from: string, to: string): string {
  const month = from.slice(0, 7);
  if (from && to && monthDays(month).from === from && monthDays(month).to === to) {
    return formatMonth(month);
  }
  return [from ? formatDay(from) : "…", to ? formatDay(to) : "…"].join(" – ");
}

/** An amount the address holds ("1500.5") in TL as the screens write it; "" for none or no number. */
function amountInWords(value: string): string {
  const number = Number(value);
  return value && Number.isFinite(number) ? formatMoney({ minor: Math.round(number * 100), currency: "TRY" }) : "";
}

interface FiltersProps {
  params: URLSearchParams;
  onChange: (next: URLSearchParams, replace?: boolean) => void;
  labels: Labels;
  accounts: readonly FilterOption[];
  rules: CategoryRules | undefined;
  /**
   * The İşlemler screen's own: a named period beside the search, which way the money goes and the amount's bounds.
   * Değerlendirme has its own period presets and counts spending, so its days stay in the panel.
   */
  rows?: boolean;
}

export function Filters({ params, onChange, labels, accounts, rules, rows = false }: FiltersProps) {
  const { t } = useTranslation("transactions");
  const [open, setOpen] = useState(false);
  const [ownDays, setOwnDays] = useState(false); // "Tarih aralığı seç…" chosen before any day is
  const panel = useId();
  const summarize = useSelectionSummary();
  const set = (change: (next: URLSearchParams) => void, replace = false) => onChange(filtered(params, change), replace);
  const setOne = (name: (typeof ONE)[number], value: string, replace = false) =>
    set((next) => setOrDelete(next, name, value), replace);
  // A day of one's own takes the place of a named period.
  const setDay = (name: "from" | "to", day: string) =>
    set((next) => {
      next.delete("period");
      setOrDelete(next, name, day);
    });
  const options: Record<"account" | "kind" | "category" | "necessity" | "certainty", readonly FilterOption[]> = {
    account: accounts,
    kind: KINDS.map((kind) => ({ value: kind, label: labelOf(labels, "TransactionKind", kind) })),
    category: (rules?.categories ?? []).map((c) => ({
      value: c.name,
      label: c.name,
      group: c.group,
      mark: <span aria-hidden="true" className={cn(SWATCH, SLOT_BG[slotOf(c.slot)])} />,
    })),
    necessity: NECESSITIES.map((code) => ({ value: code, label: labelOf(labels, "Necessity", code) })),
    // "Yalnızca bilgi" is a non-bank bill's: no row of the ledger has it.
    certainty: certaintyOptions(labels).filter((option) => option.value !== "info"),
  };
  const popovers = ["account", "kind", "category", "necessity", "certainty"] as const;
  const choose = (name: (typeof popovers)[number], selected: Selection) =>
    onChange(filtered(withSelection(params, name, selected), () => undefined));
  const addTag = (tag: string) =>
    set((next) => {
      if (!next.getAll("tag").includes(tag)) {
        next.append("tag", tag);
      }
    });

  const period = periodOf(params);
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const days = rows && (ownDays || ((from !== "" || to !== "") && period === null));
  const choosePeriod = (chosen: PeriodName | "" | typeof CUSTOM) => {
    setOwnDays(chosen === CUSTOM);
    if (chosen === CUSTOM) {
      if (period !== null) {
        onChange(withPeriod(params, ""));
      }
      return;
    }
    onChange(withPeriod(params, chosen));
  };

  const chips: FilterChip[] = [];
  if (period !== null) {
    chips.push({
      key: "period",
      name: t("filters.period"),
      value: t(`filters.periods.${period}`),
      onRemove: () => choosePeriod(""),
    });
  } else if (from || to) {
    chips.push({
      key: "period",
      name: t("filters.period"),
      value: daysInWords(from, to),
      onRemove: () => choosePeriod(""),
    });
  }
  for (const name of popovers) {
    const selected = selectionOf(params, name);
    if (selected !== null) {
      chips.push({
        key: name,
        name: t(`filters.${name}`),
        // The spending's kinds are named as what they add up to, not counted as three of twelve.
        value: name === "kind" && isSpending(selected) ? t("filters.spending") : summarize(selected, options[name]),
        onRemove: () => set((next) => next.delete(name)),
      });
    }
  }
  const direction = DIRECTIONS.find((way) => way === params.get("direction"));
  if (direction) {
    chips.push({
      key: "direction",
      name: t("filters.direction"),
      value: t(`filters.directionChip.${direction}`),
      onRemove: () => set((next) => next.delete("direction")),
    });
  }
  const least = amountInWords(params.get("min") ?? "");
  const most = amountInWords(params.get("max") ?? "");
  if (least || most) {
    chips.push({
      key: "amount",
      name: t("filters.amount"),
      value:
        least && most
          ? t("filters.amountBetween", { least, most })
          : least
            ? t("filters.amountLeast", { amount: least })
            : t("filters.amountMost", { amount: most }),
      onRemove: () =>
        set((next) => {
          next.delete("min");
          next.delete("max");
        }),
    });
  }
  for (const value of params.getAll("group")) {
    chips.push({
      key: `group-${value}`,
      name: t("filters.group"),
      value,
      onRemove: () => set((next) => removeValue(next, "group", value)),
    });
  }
  for (const value of params.getAll("tag")) {
    chips.push({
      key: `tag-${value}`,
      name: t("filters.tag"),
      value,
      onRemove: () => set((next) => removeValue(next, "tag", value)),
    });
  }
  const merchant = params.get("merchant");
  if (merchant) {
    chips.push({
      key: "merchant",
      name: t("filters.merchant"),
      value: merchant,
      onRemove: () => set((next) => next.delete("merchant")),
    });
  }
  const q = params.get("q");
  if (q) {
    // The search's parts as alternatives: "market, kira" is "market veya kira".
    chips.push({
      key: "q",
      name: t("filters.q"),
      value: searchInWords(q) || q,
      onRemove: () => set((next) => next.delete("q")),
    });
  }
  const reset = () => {
    setOwnDays(false);
    set((next) => {
      for (const name of [...MANY, ...ONE]) {
        next.delete(name);
      }
    });
  };
  // A chart's part opens the list narrowed to its kind of rows within a month; the whole month's rows are one click
  // away: the period stays, every other filter goes.
  const wholePeriod: ChipAction[] =
    rows && chips.some((chip) => chip.key === "period") && chips.length > 1
      ? [
          {
            key: "period",
            label: t("filters.wholePeriod"),
            onClick: () =>
              set((next) => {
                for (const name of [...MANY, ...ONE].filter((n) => !PERIOD_NAMES.has(n))) {
                  next.delete(name);
                }
              }),
          },
        ]
      : [];

  // The search and the period stay in view; the choices and the tags open under "Süzgeçler", whose button counts what
  // is set. The chips below say it in words whether the panel is open or not, each with its button to take it off.
  const set_ = chips.filter((chip) => chip.key !== "q" && !(rows && chip.key === "period")).length;
  const dates = (
    <div className="flex flex-wrap items-start gap-2">
      <DateInput label={t("filters.from")} value={from} max={to} onChange={(day) => setDay("from", day)} />
      <DateInput label={t("filters.to")} value={to} min={from} onChange={(day) => setDay("to", day)} />
    </div>
  );
  return (
    <div role="search" aria-label={t("filters.label")} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start gap-2">
        <SearchInput
          label={t("filters.q")}
          hint={t("filters.qHint")}
          value={params.get("q") ?? ""}
          onChange={(q) => setOne("q", q, true)}
        />
        {rows ? <PeriodSelect value={period ?? (days ? CUSTOM : "")} onChange={choosePeriod} /> : null}
        <Button
          variant="secondary"
          aria-expanded={open}
          aria-controls={panel}
          onClick={() => setOpen((was) => !was)}
          // Level with the fields beside it, below their labels; alone on a phone's line under the search, at its top.
          className={rows ? "mt-6" : "sm:mt-6"}
        >
          <FilterIcon className="size-4" />
          {t("filters.more")}
          {set_ > 0 ? (
            <span className="rounded-full bg-teal-700 px-1.5 text-xs font-semibold text-white dark:bg-teal-400 dark:text-zinc-950">
              <span className="sr-only">(</span>
              {t("filters.setCount", { count: set_ })}
              <span className="sr-only">)</span>
            </span>
          ) : null}
          <ChevronDownIcon className={cn("size-4 transition-transform", open && "rotate-180")} />
        </Button>
      </div>
      {days ? dates : null}
      <div
        id={panel}
        hidden={!open}
        className={cn(
          "flex-col gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60",
          open && "flex",
        )}
      >
        {rows ? (
          <div className="flex flex-wrap items-end gap-2">
            <DirectionSelect value={direction ?? ""} onChange={(way) => setOne("direction", way)} />
            <AmountInput label={t("filters.least")} value={params.get("min") ?? ""} onCommit={(v) => setOne("min", v)} />
            <AmountInput label={t("filters.most")} value={params.get("max") ?? ""} onCommit={(v) => setOne("max", v)} />
          </div>
        ) : (
          dates
        )}
        <div className="flex flex-wrap items-center gap-2">
          {popovers
            .filter((name) => options[name].length > 0)
            .map((name) => (
              <FilterPopover
                key={name}
                label={t(`filters.${name}`)}
                options={options[name]}
                selected={selectionOf(params, name)}
                onChange={(selected) => choose(name, selected)}
              />
            ))}
        </div>
        <TagFilter chosen={params.getAll("tag")} onAdd={addTag} />
      </div>
      <FilterChips chips={chips} actions={wholePeriod} {...(chips.length > 1 ? { onReset: reset } : {})} />
    </div>
  );
}

function setOrDelete(params: URLSearchParams, name: string, value: string): void {
  if (value.trim()) {
    params.set(name, value.trim());
  } else {
    params.delete(name);
  }
}

function removeValue(params: URLSearchParams, name: string, value: string): void {
  const kept = params.getAll(name).filter((v) => v !== value);
  params.delete(name);
  for (const v of kept) {
    params.append(name, v);
  }
}

interface PeriodSelectProps {
  value: PeriodName | "" | typeof CUSTOM;
  onChange: (value: PeriodName | "" | typeof CUSTOM) => void;
}

/** The period by name, every day, or days of one's own, which open the two day fields under it. */
function PeriodSelect({ value, onChange }: PeriodSelectProps) {
  const { t } = useTranslation("transactions");
  const id = useId();
  const parse = (chosen: string) => PERIODS.find((name) => name === chosen) ?? (chosen === CUSTOM ? CUSTOM : "");
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{t("filters.period")}</label>
      <select id={id} value={value} onChange={(event) => onChange(parse(event.target.value))} className={INPUT}>
        <option value="">{t("filters.periodAll")}</option>
        {PERIODS.map((name) => (
          <option key={name} value={name}>
            {t(`filters.periods.${name}`)}
          </option>
        ))}
        <option value={CUSTOM}>{t("filters.periodOwn")}</option>
      </select>
    </div>
  );
}

function DirectionSelect({ value, onChange }: { value: string; onChange: (way: string) => void }) {
  const { t } = useTranslation("transactions");
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{t("filters.direction")}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} className={INPUT}>
        <option value="">{t("filters.directionAll")}</option>
        {DIRECTIONS.map((way) => (
          <option key={way} value={way}>
            {t(`filters.directions.${way}`)}
          </option>
        ))}
      </select>
    </div>
  );
}

interface AmountInputProps {
  label: string;
  value: string; // the address's, in TL as the API takes it: "1500.5"; "" for none
  onCommit: (value: string) => void;
}

/** The address's amount ("1500.5") as the user would type it back ("1.500,50"); "" for none or no number. */
function typedOf(value: string): string {
  const number = Number(value);
  return value && Number.isFinite(number) ? liraInput(Math.round(number * 100)) : "";
}

/**
 * An amount's bound typed as Turkish readers write it ("1.500" or "1.500,50"), sent when the field is left or Enter is
 * pressed rather than at every key, so the list is not asked for each digit. When the address changes from elsewhere
 * (a chip took it off), the field follows it.
 */
function AmountInput({ label, value, onCommit }: AmountInputProps) {
  const { t } = useTranslation("transactions");
  const id = useId();
  const error = useId();
  const [text, setText] = useState(() => typedOf(value));
  const [wrong, setWrong] = useState(false);
  const sent = useRef(value);
  useEffect(() => {
    if (value !== sent.current) {
      sent.current = value;
      setText(typedOf(value));
      setWrong(false);
    }
  }, [value]);
  const commit = () => {
    const minor = text.trim() ? parseLira(text) : null;
    setWrong(text.trim() !== "" && minor === null);
    if (text.trim() !== "" && minor === null) {
      return;
    }
    const clean = minor === null ? "" : String(minor / 100);
    if (clean !== sent.current) {
      sent.current = clean;
      onCommit(clean);
    }
  };
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        inputMode="decimal"
        autoComplete="off"
        value={text}
        aria-invalid={wrong || undefined}
        aria-describedby={wrong ? error : undefined}
        onChange={(event) => setText(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            commit();
          }
        }}
        className={cn(INPUT, "w-36", wrong && "border-red-700 dark:border-red-400")}
      />
      {wrong ? (
        <span id={error} className="max-w-36 text-xs text-red-800 dark:text-red-300">
          {t("filters.amountWrong")}
        </span>
      ) : null}
    </div>
  );
}

interface DateInputProps {
  label: string;
  value: string;
  min?: string;
  max?: string;
  onChange: (day: string) => void;
}

function DateInput({ label, value, min, max, onChange }: DateInputProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="date"
        value={value}
        // The other end bounds the picker: the start never after the end.
        min={min || undefined}
        max={max || undefined}
        onChange={(event) => onChange(event.target.value)}
        className={INPUT}
      />
    </div>
  );
}

/**
 * A tag to filter by: typed, with the tags the rows carry offered as one types, and the most used of them as buttons
 * under the field, so a tag is chosen rather than guessed.
 */
function TagFilter({ chosen, onAdd }: { chosen: readonly string[]; onAdd: (tag: string) => void }) {
  const { t } = useTranslation("transactions");
  const known = useTransactionTags().data ?? [];
  const offered = known.filter((tag) => !chosen.includes(tag.tag)).slice(0, SHOWN_TAGS);
  return (
    <div className="flex flex-col gap-2">
      <TagInput known={known} onAdd={onAdd} />
      {offered.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          <span className="text-zinc-700 dark:text-zinc-300">{t("filters.tagsKnown")}</span>
          {offered.map((tag) => (
            <button
              key={tag.tag}
              type="button"
              aria-label={t("filters.tagChoose", { tag: tag.tag, count: tag.count })}
              onClick={() => onAdd(tag.tag)}
              className={cn(
                "inline-flex min-h-9 items-center gap-1 rounded-full border px-3",
                "border-zinc-300 bg-white hover:bg-zinc-100 dark:border-zinc-600 dark:bg-zinc-800 dark:hover:bg-zinc-700",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
              )}
            >
              {tag.tag}
              <span aria-hidden="true" className="text-xs text-zinc-600 dark:text-zinc-300">
                {tag.count}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TagInput({ known, onAdd }: { known: readonly TagCount[]; onAdd: (tag: string) => void }) {
  const { t } = useTranslation("transactions");
  const id = useId();
  const list = useId();
  const [tag, setTag] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (tag.trim()) {
      onAdd(tag.trim());
      setTag("");
    }
  };
  return (
    <form onSubmit={submit} className="flex items-center gap-1">
      <label htmlFor={id} className="sr-only">
        {t("filters.tagAdd")}
      </label>
      <input
        id={id}
        value={tag}
        placeholder={t("filters.tag")}
        maxLength={40}
        list={known.length > 0 ? list : undefined}
        onChange={(event) => setTag(event.target.value)}
        className={`${INPUT} w-40`}
      />
      {known.length > 0 ? (
        <datalist id={list}>
          {known.map((found) => (
            <option key={found.tag} value={found.tag} />
          ))}
        </datalist>
      ) : null}
      <Button type="submit" variant="secondary" disabled={!tag.trim()}>
        {t("filters.tagAdd")}
      </Button>
    </form>
  );
}
