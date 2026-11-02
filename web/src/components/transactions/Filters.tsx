// The Transactions screen's filters (F04): the period, the account, the kind, the category (by group), the necessity,
// the certainty, tags and a text search, each kept in the address in the API's names. A merchant or a group comes
// with a link from another screen and shows as a chip; every filter that is set has a chip that takes it off.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { CategoryRules, Labels } from "../../api/types";
import { formatDay } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { selectionOf, withSelection } from "../../lib/selection";
import { cn } from "../../lib/cn";
import { SLOT_BG, slotOf } from "../charts/palette";
import { certaintyOptions } from "../filters";
import { Button } from "../ui/Button";
import {
  type FilterChip,
  FilterChips,
  type FilterOption,
  FilterPopover,
  type Selection,
  useSelectionSummary,
} from "../ui/FilterPopover";
import { SearchInput } from "../ui/SearchInput";
import { filtered, MANY, ONE } from "./query";

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
const SWATCH = "inline-block size-3 shrink-0 rounded-sm"; // a category's group colour beside its name

interface FiltersProps {
  params: URLSearchParams;
  onChange: (next: URLSearchParams, replace?: boolean) => void;
  labels: Labels;
  accounts: readonly FilterOption[];
  rules: CategoryRules | undefined;
}

export function Filters({ params, onChange, labels, accounts, rules }: FiltersProps) {
  const { t } = useTranslation("transactions");
  const summarize = useSelectionSummary();
  const set = (change: (next: URLSearchParams) => void, replace = false) => onChange(filtered(params, change), replace);
  const setOne = (name: (typeof ONE)[number], value: string, replace = false) =>
    set((next) => setOrDelete(next, name, value), replace);
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

  const chips: FilterChip[] = [];
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  if (from || to) {
    chips.push({
      key: "period",
      name: t("filters.period"),
      value: [from ? formatDay(from) : "…", to ? formatDay(to) : "…"].join(" – "),
      onRemove: () =>
        set((next) => {
          next.delete("from");
          next.delete("to");
        }),
    });
  }
  for (const name of popovers) {
    const selected = selectionOf(params, name);
    if (selected !== null) {
      chips.push({
        key: name,
        name: t(`filters.${name}`),
        value: summarize(selected, options[name]),
        onRemove: () => set((next) => next.delete(name)),
      });
    }
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
  for (const name of ["merchant", "q"] as const) {
    const value = params.get(name);
    if (value) {
      chips.push({ key: name, name: t(`filters.${name}`), value, onRemove: () => set((next) => next.delete(name)) });
    }
  }
  const reset = () =>
    set((next) => {
      for (const name of [...MANY, ...ONE]) {
        next.delete(name);
      }
    });

  return (
    <div role="search" aria-label={t("filters.label")} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start gap-2">
        <DateInput label={t("filters.from")} value={from} onChange={(day) => setOne("from", day)} />
        <DateInput label={t("filters.to")} value={to} onChange={(day) => setOne("to", day)} />
        <SearchInput
          label={t("filters.q")}
          hint={t("filters.qHint")}
          value={params.get("q") ?? ""}
          onChange={(q) => setOne("q", q, true)}
        />
      </div>
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
        <TagInput onAdd={addTag} />
      </div>
      <FilterChips chips={chips} {...(chips.length > 1 ? { onReset: reset } : {})} />
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

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (day: string) => void }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="date" value={value} onChange={(event) => onChange(event.target.value)} className={INPUT} />
    </div>
  );
}

function TagInput({ onAdd }: { onAdd: (tag: string) => void }) {
  const { t } = useTranslation("transactions");
  const id = useId();
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
        onChange={(event) => setTag(event.target.value)}
        className={`${INPUT} w-32`}
      />
      <Button type="submit" variant="secondary" disabled={!tag.trim()}>
        {t("filters.tagAdd")}
      </Button>
    </form>
  );
}
