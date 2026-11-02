// Where money went, as bands from one place to another (F07's flow between the accounts): each place a bar as tall as
// what passed through it, each band as wide as its amount. A spending group keeps its colour slot; the accounts and
// the other places are drawn in the neutral ink, so colour never carries the meaning alone: every place is named
// beside its bar with its amount. The pointer names a band; the table view lists every band with its numbers.

import { type ReactNode, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/cn";
import { formatMoney, formatMoneyShort } from "../../lib/format";
import { ChartFrame } from "./ChartFrame";
import { SLOT_FILL, SLOT_STROKE } from "./palette";
import { type FlowBand, type FlowPoint, sankeyHeight, sankeyLayout } from "./flowLayout";
import { useWidth } from "./useWidth";

interface SankeyProps {
  title: string;
  summary: ReactNode;
  points: readonly FlowPoint[];
  bands: readonly FlowBand[];
  table: ReactNode; // every band with its numbers, as the caller words them
  currency?: string;
}

const MARGIN = { top: 8, right: 4, bottom: 8, left: 4 };
const HALO = "[paint-order:stroke] stroke-white stroke-[3px] [stroke-linejoin:round] dark:stroke-zinc-900";
// Narrower, a middle column's labels run into the last column's: a phone's screen scrolls the drawing sideways.
const LEAST_WIDTH = 720;

export function Sankey({ title, summary, points, bands, table, currency = "TRY" }: SankeyProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const [measure, width] = useWidth();
  const [active, setActive] = useState<string | null>(null);
  const size = { width: Math.max(LEAST_WIDTH, width), height: sankeyHeight(points, bands) };
  const layout = sankeyLayout(points, bands, size, MARGIN);
  const money = (minor: number) => ({ minor, currency });
  const shown = layout?.bands.find((band) => band.key === active);

  const chart = layout ? (
    <div className="flex flex-col gap-1">
      {/* A region the keyboard reaches, so a drawing wider than the screen can be scrolled without a pointer. */}
      <div
        ref={measure}
        tabIndex={0}
        role="region"
        aria-label={title}
        className={cn(
          "relative overflow-x-auto rounded",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
        )}
      >
        <svg
          width={size.width}
          height={size.height}
          role="img"
          aria-label={t("image.sankey", { title })}
          aria-describedby={summaryId}
          className="block overflow-visible"
        >
          <g fill="none">
            {layout.bands.map((band) => (
              <path
                key={band.key}
                d={band.d}
                strokeWidth={band.width}
                strokeOpacity={active === band.key ? 0.65 : 0.3}
                className={cn(
                  band.target.slot !== null ? SLOT_STROKE[band.target.slot] : "stroke-chart-muted",
                  "transition-[stroke-opacity] motion-reduce:transition-none",
                )}
                onPointerEnter={() => setActive(band.key)}
                onPointerLeave={() => setActive(null)}
              />
            ))}
          </g>
          {layout.points.map((point) => (
            <g key={point.id}>
              <rect
                x={point.x0}
                y={point.y0}
                width={point.x1 - point.x0}
                height={Math.max(1, point.y1 - point.y0)}
                rx={2}
                className={point.slot !== null ? SLOT_FILL[point.slot] : "fill-chart-ink-2"}
              />
              <text
                x={point.labelOnRight ? point.x1 + 6 : point.x0 - 6}
                y={(point.y0 + point.y1) / 2}
                dy="0.32em"
                textAnchor={point.labelOnRight ? "start" : "end"}
                className={cn("fill-chart-ink text-[11px]", HALO)}
              >
                {point.label}
                <tspan className="fill-chart-ink-2"> · {formatMoneyShort(money(point.value))}</tspan>
              </text>
            </g>
          ))}
        </svg>
        {shown ? (
          <p
            aria-hidden="true"
            className={cn(
              "pointer-events-none absolute left-2 top-2 rounded-md border px-2 py-1 text-xs shadow-sm",
              "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
            )}
          >
            {shown.source.label} → {shown.target.label}: {formatMoney(money(shown.value))}
          </p>
        ) : null}
      </div>
      {/* A phone's screen shows the first column only: say there is more to the side, and where the numbers are. */}
      {width < LEAST_WIDTH ? <p className="text-xs text-zinc-600 dark:text-zinc-300">{t("sankeyScroll")}</p> : null}
    </div>
  ) : (
    <div ref={measure} className="py-6 text-center text-sm text-zinc-600 dark:text-zinc-300">
      {t("sankeyUnavailable")}
    </div>
  );

  return (
    <ChartFrame
      title={title}
      summary={summary}
      summaryId={summaryId}
      chart={chart}
      table={table}
      empty={bands.length === 0}
    />
  );
}
