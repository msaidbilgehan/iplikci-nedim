// The dashboard's first row (F06): four figures to read at a glance — the net worth, this month's spending against the
// typical month, what is to be paid within a week and how much there is to see to — each a link to the screen that
// tells the rest. The cards below them carry the lists and, in the detailed view, the tables. A tile is one link, so
// it holds no button of its own: a figure that is not certain says so in words.

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { Dashboard, Destination, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatDay, formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { hrefOf } from "../../lib/links";
import { untoldTotal } from "../accounts/UntoldNote";
import { PaceMeter } from "../Pace";
import { BankIcon, CalendarIcon, ChecklistIcon, PulseIcon } from "../ui/Icons";

interface TileProps {
  label: string;
  icon: ReactNode;
  value: ReactNode;
  link: Destination;
  tone?: "plain" | "attention";
  children?: ReactNode; // a line or two under the figure
}

function Tile({ label, icon, value, link, tone = "plain", children }: TileProps) {
  const href = hrefOf(link);
  const body = (
    <>
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-600 dark:text-zinc-300">
        <span
          className={cn(
            "grid size-7 shrink-0 place-items-center rounded-lg",
            tone === "attention"
              ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
              : "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
          )}
        >
          {icon}
        </span>
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-zinc-900 dark:text-zinc-50">
        {value}
      </div>
      {children ? <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-300">{children}</div> : null}
    </>
  );
  const look = cn(
    "block min-w-0 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900",
  );
  if (!href) {
    return <div className={look}>{body}</div>;
  }
  return (
    <Link
      to={href}
      className={cn(
        look,
        "transition-colors hover:border-teal-600 hover:bg-teal-50/40 dark:hover:border-teal-500 dark:hover:bg-zinc-800",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
      )}
    >
      {body}
    </Link>
  );
}

export function Highlights({ found, labels }: { found: Dashboard; labels: Labels }) {
  const { t } = useTranslation("dashboard");
  const { net_worth: worth, month, due, todo } = found;
  const pace = month.pace;
  // No document reaches the month yet: that nothing was spent is not known, so no zero and no meter are shown.
  const unread = pace.covered === 0 && pace.spent.minor === 0;
  const [first] = due.items;
  const untold = untoldTotal(worth.untold);
  return (
    <section aria-label={t("highlights.label")} className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Tile
        label={t("highlights.worth")}
        icon={<BankIcon className="size-4" />}
        value={formatMoney(worth.total)}
        link={worth.link}
      >
        {t("highlights.worthParts", { assets: formatMoney(worth.assets), debts: formatMoney(worth.debts) })}
        {untold ? <span className="block">{t("highlights.worthUntold", { amount: formatMoney(untold) })}</span> : null}
        {worth.certainty === "confirmed" ? null : <span className="block">{t("highlights.provisional")}</span>}
        {worth.left_out.length > 0 ? (
          <span className="block">{t("highlights.leftOut", { count: worth.left_out.length })}</span>
        ) : null}
      </Tile>
      <Tile
        label={t("highlights.month")}
        icon={<PulseIcon className="size-4" />}
        value={unread ? t("highlights.monthNone") : formatMoney(pace.spent)}
        link={month.link}
      >
        {unread ? (
          <>
            <span className="block">{t("highlights.monthNoneText", { month: formatMonth(pace.month) })}</span>
            {pace.typical ? (
              <span className="block">{t("highlights.typicalOnly", { amount: formatMoney(pace.typical) })}</span>
            ) : null}
          </>
        ) : pace.typical ? (
          <>
            <span className="block">
              {t("highlights.typical", { month: formatMonth(pace.month), amount: formatMoney(pace.typical) })}
            </span>
            <PaceMeter pace={pace} />
          </>
        ) : (
          t("highlights.noTypical", { month: formatMonth(pace.month) })
        )}
      </Tile>
      <Tile
        label={t("highlights.due")}
        icon={<CalendarIcon className="size-4" />}
        value={due.items.length > 0 ? formatMoney(due.total) : t("highlights.dueNone")}
        link={due.link}
      >
        {first
          ? t("highlights.dueFirst", { count: due.items.length, day: formatDay(first.day), title: first.title })
          : t("highlights.dueUntil", { end: formatDay(due.end) })}
      </Tile>
      <Tile
        label={t("highlights.todo")}
        icon={<ChecklistIcon className="size-4" />}
        value={todo.total > 0 ? t("todo.total", { count: todo.total }) : t("highlights.todoNone")}
        link={todo.link}
        tone={todo.total > 0 ? "attention" : "plain"}
      >
        {todo.kinds.length > 0
          ? todo.kinds.map((kind) => `${labelOf(labels, "TodoKind", kind.kind)} ${kind.count}`).join(" · ")
          : t("highlights.todoText")}
      </Tile>
    </section>
  );
}
