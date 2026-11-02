// "Alışkanlıklar ve tasarruf fırsatları" (the MVP report's habits): the optional merchants and the avoidable costs,
// each with how often it comes and what it costs a month from now on — the last three months' average for a monthly
// or new habit, an occasional one's total spread over the window. A one-off or a stopped habit costs nothing from now
// on: it is listed apart and never turned into a monthly figure. No filter changes it.

import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { Habit, Insights, Labels } from "../../api/types";
import { cn } from "../../lib/cn";
import { formatMoney, formatMonth } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { NECESSITY_SLOTS, SLOT_BG } from "../charts/palette";
import { Detailed, Simple } from "../Preferences";
import { ScreenLink } from "../ui/Say";
import { Table, Td, Th } from "../ui/Table";

const SMALL = "text-xs text-zinc-600 dark:text-zinc-300";
const LIRA = 100; // a monthly cost under a lira is none
const PAST_FROM = 50_000; // the MVP listed what stopped from 500 TL spent in the window on
const PAST_SHOWN = 8;

export function Habits({ found, labels }: { found: Insights; labels: Labels }) {
  const { t } = useTranslation("insights");
  const heading = useId();
  const going = found.habits.filter((habit) => habit.monthly.minor >= LIRA);
  const past = found.habits
    .filter((habit) => habit.monthly.minor < LIRA && habit.total.minor >= PAST_FROM)
    .slice(0, PAST_SHOWN);
  const months = found.window.months;
  const total = going.reduce((sum, habit) => sum + habit.monthly.minor, 0);
  const largest = going.reduce<Habit | undefined>(
    (best, habit) => (best && best.monthly.minor >= habit.monthly.minor ? best : habit),
    undefined,
  );
  return (
    <section aria-labelledby={heading} className="mt-6 flex flex-col gap-2">
      <h3 id={heading} className="text-base font-semibold">
        {t("habits.title")}
      </h3>
      {months[0] && months.at(-1) ? (
        <p className={SMALL}>
          {t("habits.hint", {
            count: months.length,
            from: formatMonth(months[0]),
            to: formatMonth(months.at(-1) ?? ""),
          })}
        </p>
      ) : null}
      <Simple>
        <p className="text-sm">
          {largest
            ? t("habits.say", {
                amount: formatMoney({ minor: total, currency: largest.monthly.currency }),
                name: largest.name,
                each: formatMoney(largest.monthly),
              })
            : t("habits.sayNone")}
        </p>
      </Simple>
      <Detailed>
        {going.length === 0 && past.length === 0 ? (
          <p className="text-sm">{t("habits.none")}</p>
        ) : (
          <Table>
            <caption className="sr-only">{t("habits.caption")}</caption>
            <thead>
              <tr>
                <Th>{t("habits.item")}</Th>
                <Th>{t("habits.status")}</Th>
                <Th>{t("habits.pattern")}</Th>
                <Th className="text-right">{t("habits.recent")}</Th>
                <Th className="text-right">{t("habits.total", { count: months.length })}</Th>
                <Th className="text-right">{t("habits.monthly")}</Th>
              </tr>
            </thead>
            <tbody>
              {going.map((habit) => (
                <HabitRow key={`${habit.by_category}:${habit.name}`} habit={habit} labels={labels} />
              ))}
              {past.length > 0 ? (
                <tr>
                  <Th scope="colgroup" colSpan={6} className="text-zinc-900 dark:text-zinc-100">
                    {t("habits.past")}
                  </Th>
                </tr>
              ) : null}
              {past.map((habit) => (
                <HabitRow key={`${habit.by_category}:${habit.name}`} habit={habit} labels={labels} />
              ))}
            </tbody>
            <tfoot>
              <tr>
                <Th scope="row" colSpan={5} className="border-b-0 text-zinc-900 dark:text-zinc-100">
                  {t("habits.footer")}
                </Th>
                <Td className="border-b-0 text-right font-semibold whitespace-nowrap tabular-nums">
                  {formatMoney({ minor: total, currency: "TRY" })}
                </Td>
              </tr>
            </tfoot>
          </Table>
        )}
      </Detailed>
    </section>
  );
}

function HabitRow({ habit, labels }: { habit: Habit; labels: Labels }) {
  const { t } = useTranslation("insights");
  const level = habit.necessity ?? "unknown";
  return (
    <tr>
      <Td className="min-w-44">
        <ScreenLink link={habit.link} className="font-medium">
          {habit.name}
        </ScreenLink>
        <span className={cn("mt-0.5 flex items-center gap-1.5", SMALL)}>
          <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-sm", SLOT_BG[NECESSITY_SLOTS[level]])} />
          {habit.by_category ? `${labelOf(labels, "Necessity", level)} · ${t("habits.byCategory")}` : habit.category}
        </span>
      </Td>
      <Td className="whitespace-nowrap">{labelOf(labels, "HabitStatus", habit.status)}</Td>
      <Td className={cn("min-w-36", SMALL)}>{habit.pattern}</Td>
      <Td className="text-right whitespace-nowrap tabular-nums">
        {habit.recent.minor >= LIRA ? formatMoney(habit.recent) : "–"}
      </Td>
      <Td className="text-right whitespace-nowrap tabular-nums">{formatMoney(habit.total)}</Td>
      <Td className="text-right whitespace-nowrap tabular-nums">
        {habit.monthly.minor >= LIRA ? formatMoney(habit.monthly) : "–"}
      </Td>
    </tr>
  );
}
