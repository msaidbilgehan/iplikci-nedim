// Every chart's frame (features.md: every chart has a table view): a sentence saying what it shows — its window and
// numbers — and a "Grafik / Tablo" switch between the drawing and a table of the same data. The figure is named after
// the chart; the drawing takes the sentence as its description, and its values are in the table, which the keyboard
// and screen readers reach as any table. When the drawing's parts lead to their rows, a line under it says what a
// click opens; the table's names lead to the same places.

import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import { CursorClickIcon } from "../ui/Icons";
import { Tab, TabList, TabPanel, Tabs } from "../ui/Tabs";

interface ChartFrameProps {
  title: string; // the chart's name for screen readers: "Aylık giderler, ana gruplara göre"
  summary: ReactNode; // shown above it: what it shows, its window and numbers
  summaryId: string; // the drawing's description points here
  legend?: ReactNode;
  chart: ReactNode;
  table: ReactNode; // the same data, as a table
  empty?: boolean; // nothing to draw: said once, without a switch
  hint?: string | undefined; // what a click on the drawing opens
}

type View = "chart" | "table";

export function ChartFrame({ title, summary, summaryId, legend, chart, table, empty = false, hint }: ChartFrameProps) {
  const { t } = useTranslation("charts");
  const [view, setView] = useState<View>("chart");
  return (
    <figure aria-label={title} aria-describedby={summaryId} className="flex min-w-0 flex-col">
      <Tabs value={view} onValueChange={(next) => setView(next === "table" ? "table" : "chart")}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p id={summaryId} className="min-w-0 max-w-prose flex-1 text-sm text-zinc-700 dark:text-zinc-300">
            {summary}
          </p>
          {empty ? null : (
            <TabList look="segmented" aria-label={t("views", { title })}>
              <Tab value="chart">{t("chart")}</Tab>
              <Tab value="table">{t("table")}</Tab>
            </TabList>
          )}
        </div>
        {empty ? (
          <p className="py-8 text-center text-sm text-zinc-600 dark:text-zinc-300">{t("empty")}</p>
        ) : (
          <>
            <TabPanel value="chart" className="mt-3 flex flex-col gap-2">
              {legend}
              {chart}
              {hint ? (
                <p className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300">
                  <CursorClickIcon className="size-3.5 shrink-0" />
                  {hint}
                </p>
              ) : null}
            </TabPanel>
            <TabPanel value="table" className="mt-3">
              {table}
            </TabPanel>
          </>
        )}
      </Tabs>
    </figure>
  );
}
