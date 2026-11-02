// The Belgeler screen's filters (F03): a full-text search, the kind (a document no reader took among them), the way it
// came, the account its reading names and the bank, each kept in the address in the API's names. Every filter that is
// set has a chip that takes it off; a status a link narrowed the tab to has one too.

import { useTranslation } from "react-i18next";

import type { Accounts, Labels } from "../../api/types";
import { labelOf } from "../../lib/labels";
import { selectionOf, withSelection } from "../../lib/selection";
import { accountOptions } from "../filters";
import {
  type FilterChip,
  FilterChips,
  type FilterOption,
  FilterPopover,
  type Selection,
  useSelectionSummary,
} from "../ui/FilterPopover";
import { SearchInput } from "../ui/SearchInput";
import { NO_READER, narrowsStatus, onTab, tabOf, withoutFilters } from "./query";

const KINDS = ["card_statement", "account_statement", "receipt", "notice", "invoice"];
const SOURCES = ["email", "upload", "inbox", "import"];
const STATUSES = ["processed", "unprocessed", "unreadable"];
const POPOVERS = ["kind", "source", "account", "bank"] as const;

interface FiltersProps {
  params: URLSearchParams;
  onChange: (next: URLSearchParams, replace?: boolean) => void;
  labels: Labels;
  accounts: Accounts | undefined;
}

/** The banks of the accounts, as filter choices: a document's bank is its accounts'. */
function bankOptions(accounts: Accounts | undefined): FilterOption[] {
  const every = accounts ? [...accounts.groups.flatMap((group) => group.accounts), ...accounts.closed] : [];
  const banks = [...new Set(every.map((item) => item.bank).filter(Boolean))].sort((a, b) => a.localeCompare(b, "tr"));
  return banks.map((bank) => ({ value: bank, label: bank }));
}

export function Filters({ params, onChange, labels, accounts }: FiltersProps) {
  const { t } = useTranslation("documents");
  const summarize = useSelectionSummary();
  const options: Record<(typeof POPOVERS)[number] | "status", readonly FilterOption[]> = {
    kind: [
      ...KINDS.map((kind) => ({ value: kind, label: labelOf(labels, "DocumentKind", kind) })),
      { value: NO_READER, label: t("filters.noReader") },
    ],
    source: SOURCES.map((source) => ({ value: source, label: labelOf(labels, "SourceKind", source) })),
    account: accountOptions(accounts, labels, t("filters.closed")),
    bank: bankOptions(accounts),
    status: STATUSES.map((status) => ({ value: status, label: labelOf(labels, "DocumentStatus", status) })),
  };
  const choose = (name: (typeof POPOVERS)[number], selected: Selection) =>
    onChange(withSelection(params, name, selected));
  const remove = (name: string) => {
    const next = new URLSearchParams(params);
    next.delete(name);
    onChange(next);
  };

  const chips: FilterChip[] = [];
  if (narrowsStatus(params)) {
    // Taking a narrowed status off widens it to its tab's.
    chips.push({
      key: "status",
      name: t("filters.status"),
      value: summarize(selectionOf(params, "status"), options.status),
      onRemove: () => onChange(onTab(params, tabOf(params))),
    });
  }
  for (const name of POPOVERS) {
    const selected = selectionOf(params, name);
    if (selected !== null) {
      chips.push({
        key: name,
        name: t(`filters.${name}`),
        value: summarize(selected, options[name]),
        onRemove: () => remove(name),
      });
    }
  }
  const q = params.get("q");
  if (q) {
    chips.push({ key: "q", name: t("filters.q"), value: q, onRemove: () => remove("q") });
  }

  return (
    <div role="search" aria-label={t("filters.label")} className="flex flex-col gap-3">
      <SearchInput
        label={t("filters.q")}
        hint={t("filters.qHint")}
        value={q ?? ""}
        onChange={(text) => {
          const next = new URLSearchParams(params);
          if (text.trim()) {
            next.set("q", text.trim());
          } else {
            next.delete("q");
          }
          onChange(next, true);
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        {POPOVERS.filter((name) => options[name].length > 0).map((name) => (
          <FilterPopover
            key={name}
            label={t(`filters.${name}`)}
            options={options[name]}
            selected={selectionOf(params, name)}
            onChange={(selected) => choose(name, selected)}
          />
        ))}
      </div>
      <FilterChips chips={chips} {...(chips.length > 1 ? { onReset: () => onChange(withoutFilters(params)) } : {})} />
    </div>
  );
}
