// The name the user gives an account (F07's "takma ad"): the screens show it in the bank's label's place. The bank's
// label stays the account's own: the report, the exports and the MCP tools keep it. An empty name gives it back.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useRename } from "../../api/queries";
import type { AccountItem } from "../../api/types";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";

const MAX = 60; // accounts.rename: at most 60 characters once the spaces are trimmed
const INPUT = [
  "min-h-11 w-full max-w-sm rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
].join(" ");

interface AliasFormProps {
  item: AccountItem;
  onDone: (said: string) => void; // saved or taken back (what to say about it), or given up (""): the form closes
}

export function AliasForm({ item, onDone }: AliasFormProps) {
  const { t } = useTranslation("accounts");
  const rename = useRename(item.account.id);
  const [alias, setAlias] = useState(item.alias || item.account.label);
  const id = useId();
  const hint = useId();
  const save = (name: string) =>
    rename.mutate(name.trim(), { onSuccess: () => onDone(name.trim() ? t("alias.saved") : t("alias.removed")) });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save(alias);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
      <label htmlFor={id} className="font-medium">
        {t("alias.label")}
      </label>
      <input
        id={id}
        value={alias}
        maxLength={MAX}
        aria-describedby={hint}
        onChange={(event) => setAlias(event.target.value)}
        className={INPUT}
      />
      <span id={hint} className="text-xs text-zinc-600 dark:text-zinc-300">
        {t("alias.hint", { label: item.label })}
      </span>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!alias.trim() || alias.trim() === item.alias || rename.isPending}>
          {t("alias.save")}
        </Button>
        {item.alias ? (
          <Button variant="secondary" disabled={rename.isPending} onClick={() => save("")}>
            {t("alias.remove")}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={() => onDone("")}>
          {t("alias.cancel")}
        </Button>
      </div>
      {rename.isError ? <Alert tone="critical" title={rename.error.message} /> : null}
    </form>
  );
}
