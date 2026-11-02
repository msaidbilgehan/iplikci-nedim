// The Yapılacaklar screen (F19): what keeps the data from being complete and right, kind by kind in F19's order, each
// item with the steps that settle it. The dashboard's count leads here, narrowed to a kind (?tur=). What the user takes
// off the list can be put back at once, or later from the items taken off.

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { keys, useIgnoreTodo, useLabels, useReparse, useTodos } from "../api/queries";
import type { Labels, TodoItem, TodoKind, Todos } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import type { TodoHandlers } from "../components/todo/Steps";
import { TodoGroup } from "../components/todo/TodoGroup";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { Say } from "../components/ui/Say";
import { cn } from "../lib/cn";
import { labelOf } from "../lib/labels";

export default function TodoPage() {
  const { t } = useTranslation("todo");
  const [withIgnored, setWithIgnored] = useState(false);
  const todos = useTodos(withIgnored);
  const labels = useLabels().data ?? {};
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      {todos.isPending ? <Loading /> : null}
      {todos.isError ? <Failure error={todos.error} onRetry={() => void todos.refetch()} /> : null}
      {todos.data ? (
        <List found={todos.data} labels={labels} withIgnored={withIgnored} onWithIgnored={setWithIgnored} />
      ) : null}
    </div>
  );
}

interface Notice {
  text: string;
  undo: TodoItem | null; // the item just taken off, to put back
  at: number;
}

/** The items' kinds in the order the list gives them: the service's counts first (F19's order), then any other. */
function kindsOf(found: Todos): TodoKind[] {
  const kinds = Object.keys(found.counts) as TodoKind[];
  for (const item of found.items) {
    if (!kinds.includes(item.kind)) {
      kinds.push(item.kind);
    }
  }
  return kinds;
}

interface ListProps {
  found: Todos;
  labels: Labels;
  withIgnored: boolean;
  onWithIgnored: (on: boolean) => void;
}

function List({ found, labels, withIgnored, onWithIgnored }: ListProps) {
  const { t } = useTranslation("todo");
  const [params] = useSearchParams();
  const chosen = params.get("tur") ?? "";
  const client = useQueryClient();
  const ignore = useIgnoreTodo();
  const reparse = useReparse();
  const [notice, setNotice] = useState<Notice | null>(null);
  const noticeBox = useRef<HTMLDivElement>(null);

  // The step's button left with its item: the focus goes to what the step did, and to its undo.
  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timer = setTimeout(() => {
      if (!document.activeElement || document.activeElement === document.body) {
        noticeBox.current?.focus();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [notice]);

  const say = (text: string, undo: TodoItem | null = null) => setNotice({ text, undo, at: Date.now() });
  const handlers: TodoHandlers = {
    ignore: (item) =>
      ignore.mutate(
        { key: item.key, ignored: true },
        { onSuccess: () => say(t("ignoredDone", { title: item.title }), item) },
      ),
    restore: (item) =>
      ignore.mutate(
        { key: item.key, ignored: false },
        { onSuccess: () => say(t("restoredDone", { title: item.title })) },
      ),
    reparse: (item) =>
      reparse.mutate(item.target, {
        onSuccess: (done) =>
          say(t("reparsed", { title: item.title, status: labelOf(labels, "DocumentStatus", done.status) })),
        // The list is asked again now, however it went; the analysis's event refreshes it again once it is done.
        onSettled: () => void client.invalidateQueries({ queryKey: keys.dashboard }),
      }),
    busy: (item) =>
      (ignore.isPending && ignore.variables.key === item.key) ||
      (reparse.isPending && reparse.variables === item.target),
    failure: (item) => {
      if (ignore.isError && ignore.variables.key === item.key) {
        return ignore.error.message;
      }
      return reparse.isError && reparse.variables === item.target ? reparse.error.message : "";
    },
  };

  const kinds = kindsOf(found);
  const count = (kind: TodoKind) => found.counts[kind] ?? 0;
  const waiting = kinds.filter((kind) => count(kind) > 0);
  const total = waiting.reduce((sum, kind) => sum + count(kind), 0);
  const shown = chosen ? kinds.filter((kind) => kind === chosen) : kinds;
  const groups = shown
    .map((kind) => [kind, found.items.filter((item) => item.kind === kind)] as const)
    .filter(([, items]) => items.length > 0);
  const counted = waiting.map((kind) =>
    t("kindCount", { kind: labelOf(labels, "TodoKind", kind), count: count(kind) }),
  );

  return (
    <div className="flex flex-col gap-4">
      {total > 0 ? <Say>{t("say", { count: total, kinds: counted.join(", ") })}</Say> : null}
      {waiting.length > 1 || chosen ? (
        <Kinds kinds={waiting} counts={found.counts} total={total} chosen={chosen} labels={labels} />
      ) : null}
      <div
        ref={noticeBox}
        tabIndex={-1}
        className="rounded-md empty:hidden focus-visible:outline-2 focus-visible:outline-teal-600"
      >
        {notice ? (
          <Alert tone="good" title={notice.text} live>
            {notice.undo ? (
              <Button
                variant="secondary"
                className="mt-2"
                disabled={ignore.isPending}
                onClick={() => notice.undo && handlers.restore(notice.undo)}
              >
                {t("undo")}
              </Button>
            ) : null}
          </Alert>
        ) : null}
      </div>
      {groups.length === 0 && chosen ? (
        <Empty title={t("kindEmpty")}>
          <Link to={{ search: "" }} className={LINK}>
            {t("showAll")}
          </Link>
        </Empty>
      ) : null}
      {groups.length === 0 && !chosen ? (
        <Empty title={t("empty")}>
          <p>{t("emptyText")}</p>
        </Empty>
      ) : null}
      {groups.map(([kind, items]) => (
        <TodoGroup key={kind} kind={kind} items={items} labels={labels} handlers={handlers} />
      ))}
      {found.ignored > 0 || withIgnored ? (
        <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-700 dark:text-zinc-300">
          <span>{t("ignoredCount", { count: found.ignored })}</span>
          {/* A switch: its words stay, its state is said (pressed while what was taken off is listed). */}
          <Button variant="secondary" aria-pressed={withIgnored} onClick={() => onWithIgnored(!withIgnored)}>
            {t("showIgnored")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

const LINK = cn(
  "rounded font-medium underline",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

const CHIP = cn(
  "inline-flex min-h-11 items-center rounded-full border px-3 text-sm font-medium transition-colors",
  "border-zinc-300 text-zinc-800 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-100 dark:hover:bg-zinc-800",
  "aria-[current=true]:border-teal-700 aria-[current=true]:bg-teal-700 aria-[current=true]:text-white",
  "dark:aria-[current=true]:border-teal-400 dark:aria-[current=true]:bg-teal-400",
  "dark:aria-[current=true]:text-zinc-950",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

interface KindsProps {
  kinds: readonly TodoKind[];
  counts: Todos["counts"];
  total: number;
  chosen: string;
  labels: Labels;
}

/** The kinds with items waiting, each narrowing the list to itself; "Tümü" shows them all again. */
function Kinds({ kinds, counts, total, chosen, labels }: KindsProps) {
  const { t } = useTranslation("todo");
  return (
    <nav aria-label={t("kinds")}>
      <ul className="flex flex-wrap gap-2">
        <li>
          <Link to={{ search: "" }} aria-current={chosen === "" ? "true" : undefined} className={CHIP}>
            {t("all", { count: total })}
          </Link>
        </li>
        {kinds.map((kind) => (
          <li key={kind}>
            <Link
              to={{ search: `?${new URLSearchParams({ tur: kind }).toString()}` }}
              aria-current={chosen === kind ? "true" : undefined}
              className={CHIP}
            >
              {t("kindCount", { kind: labelOf(labels, "TodoKind", kind), count: counts[kind] ?? 0 })}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
