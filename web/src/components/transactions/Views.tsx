// The views the user keeps (F04's "kayıtlı görünümler"): the filters and the order under a name. Opening one puts its
// filters into the address; the screen's filters are kept under a new name, or replace a view of the same name.
// Removing one asks first.

import * as Popover from "@radix-ui/react-popover";
import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useRemoveView, useSaveView, useSavedViews } from "../../api/queries";
import { cn } from "../../lib/cn";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/Dialog";
import { POPOVER_HEIGHT } from "../ui/FilterPopover";
import { ChevronDownIcon, CloseIcon } from "../ui/Icons";
import { paramsOfView, viewQuery } from "./query";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

interface ViewsProps {
  params: URLSearchParams;
  onOpen: (params: URLSearchParams) => void;
}

export function Views({ params, onOpen }: ViewsProps) {
  const { t } = useTranslation("transactions");
  const views = useSavedViews();
  const save = useSaveView();
  const remove = useRemoveView();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [saved, setSaved] = useState("");
  const nameId = useId();
  const hintId = useId();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const named = name.trim();
    if (!named) {
      return;
    }
    save.mutate(
      { name: named, query: viewQuery(params) },
      {
        onSuccess: () => {
          setSaved(t("views.saved", { name: named }));
          setName("");
        },
      },
    );
  };

  return (
    <>
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger
          className={cn(
            "inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-medium",
            "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
            "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
            FOCUS,
          )}
        >
          {t("views.button")}
          <ChevronDownIcon className="size-4 text-zinc-600 dark:text-zinc-300" />
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            aria-label={t("views.title")}
            align="end"
            sideOffset={6}
            collisionPadding={8}
            // Many kept views scroll inside it rather than run off the screen.
            className={cn(
              "z-50 flex w-80 max-w-[calc(100vw-1rem)] flex-col gap-3 overflow-y-auto rounded-lg border p-3 text-sm",
              POPOVER_HEIGHT,
              "border-zinc-200 bg-white text-zinc-900 shadow-lg dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
            )}
          >
            <p className="font-medium">{t("views.title")}</p>
            {views.data && views.data.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {views.data.map((view) => (
                  <li key={view.name} className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      aria-label={t("views.apply", { name: view.name })}
                      onClick={() => {
                        onOpen(paramsOfView(view.query));
                        setOpen(false);
                      }}
                      className={cn(
                        "min-h-9 flex-1 truncate rounded px-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-700",
                        FOCUS,
                      )}
                    >
                      {view.name}
                    </button>
                    <button
                      type="button"
                      aria-label={t("views.remove", { name: view.name })}
                      onClick={() => setRemoving(view.name)}
                      className={cn(
                        "inline-flex size-9 items-center justify-center rounded text-zinc-600 hover:bg-zinc-100",
                        "dark:text-zinc-300 dark:hover:bg-zinc-700",
                        FOCUS,
                      )}
                    >
                      <CloseIcon className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-zinc-600 dark:text-zinc-300">{t("views.none")}</p>
            )}
            <form onSubmit={submit} className="flex flex-col gap-1 border-t border-zinc-200 pt-3 dark:border-zinc-600">
              <label htmlFor={nameId} className="font-medium">
                {t("views.save")}
              </label>
              <div className="flex gap-2">
                <input
                  id={nameId}
                  value={name}
                  maxLength={60}
                  aria-describedby={hintId}
                  placeholder={t("views.name")}
                  onChange={(event) => setName(event.target.value)}
                  className={cn(
                    "min-h-11 min-w-0 flex-1 rounded-md border px-3",
                    "border-zinc-300 bg-white dark:border-zinc-600 dark:bg-zinc-900",
                    FOCUS,
                  )}
                />
                <Button type="submit" disabled={!name.trim() || save.isPending}>
                  {t("views.saveButton")}
                </Button>
              </div>
              <span id={hintId} className="text-xs text-zinc-600 dark:text-zinc-300">
                {t("views.replaces")}
              </span>
            </form>
            <p aria-live="polite" className="text-xs">
              {saved}
            </p>
            {save.isError ? <Alert tone="critical" title={save.error.message} /> : null}
            {remove.isError ? <Alert tone="critical" title={remove.error.message} /> : null}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(next) => (next ? undefined : setRemoving(null))}
        title={t("views.removeTitle")}
        description={t("views.removeText", { name: removing ?? "" })}
        confirmLabel={t("views.removeConfirm")}
        variant="danger"
        busy={remove.isPending}
        onConfirm={() => {
          if (removing !== null) {
            remove.mutate(removing, { onSettled: () => setRemoving(null) });
          }
        }}
      />
    </>
  );
}
