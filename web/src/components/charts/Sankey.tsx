// Where money went, as bands from one place to another (F07's flow between the accounts): each place a bar as tall as
// what passed through it, each band as wide as its amount. A spending group keeps its colour slot; the accounts and
// the other places are drawn in the neutral ink, so colour never carries the meaning alone: every place is named
// beside its bar with its amount. The pointer names a band; the table view lists every band with its numbers. A band
// may lead to the rows it adds up (open): a click opens them, and the table's rows carry the same links.

import { type ReactNode, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { cn } from "../../lib/cn";
import { formatMoney, formatMoneyShort } from "../../lib/format";
import { hrefOf } from "../../lib/links";
import { ArrowRightIcon } from "../ui/Icons";
import { ChartFrame } from "./ChartFrame";
import { type ChartOpen, isTouch, useDismiss, useOpener } from "./open";
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
  open?: ChartOpen<string>; // where a band leads, by its key
}

/** The band the pointer is on, and whether a touch chose it: then it stays until the next press. */
interface Aim {
  key: string;
  touch: boolean;
}

const MARGIN = { top: 8, right: 4, bottom: 8, left: 4 };
const HALO = "[paint-order:stroke] stroke-white stroke-[3px] [stroke-linejoin:round] dark:stroke-zinc-900";
// Narrower, a middle column's labels run into the last column's: a phone's screen scrolls the drawing sideways.
const LEAST_WIDTH = 720;

export function Sankey({ title, summary, points, bands, table, currency = "TRY", open }: SankeyProps) {
  const { t } = useTranslation("charts");
  const summaryId = useId();
  const [measure, width, box] = useWidth();
  const [aim, setAim] = useState<Aim | null>(null);
  const pressed = useRef<Aim | null>(null);
  const opener = useOpener();
  useDismiss(box, aim?.touch === true, () => setAim(null));
  const size = { width: Math.max(LEAST_WIDTH, width), height: sankeyHeight(points, bands) };
  const layout = sankeyLayout(points, bands, size, MARGIN);
  const money = (minor: number) => ({ minor, currency });
  const active = aim?.key ?? null;
  const shown = layout?.bands.find((band) => band.key === active);
  const link = active === null ? null : (open?.link(active) ?? null);
  const href = link ? hrefOf(link) : null;

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
                  open && open.link(band.key) !== null && "cursor-pointer",
                )}
                onPointerEnter={(event) => {
                  if (!isTouch(event)) {
                    setAim({ key: band.key, touch: false });
                  }
                }}
                onPointerLeave={(event) => {
                  if (!isTouch(event)) {
                    setAim(null);
                  }
                }}
                onPointerDown={(event) => {
                  const next = { key: band.key, touch: isTouch(event) };
                  opener.press(event, aim?.key === band.key);
                  pressed.current = next;
                  setAim(next);
                }}
                onPointerCancel={() => {
                  // A finger that scrolls the drawing chose nothing.
                  if (pressed.current?.touch) {
                    pressed.current = null;
                    setAim(null);
                  }
                }}
                onClick={open ? () => opener.click(open.link(band.key)) : undefined}
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
          <div
            aria-hidden="true"
            className={cn(
              "absolute left-2 top-2 rounded-md border px-2 py-1 text-xs shadow-sm",
              "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100",
              href && aim?.touch ? "pointer-events-auto" : "pointer-events-none",
            )}
          >
            <p>
              {shown.source.label} → {shown.target.label}: {formatMoney(money(shown.value))}
            </p>
            {href && !aim?.touch ? (
              <p className="text-zinc-600 dark:text-zinc-300">{t("open.click", { what: t("open.band") })}</p>
            ) : null}
            {href && aim?.touch ? (
              // A touch's tip stays: its link opens the band, out of the keyboard's way (the table's rows link too).
              <Link
                to={href}
                tabIndex={-1}
                className="flex min-h-11 items-center gap-2 font-medium text-teal-800 underline dark:text-teal-300"
              >
                {t("open.tap", { what: t("open.band") })}
                <ArrowRightIcon className="size-4 shrink-0" />
              </Link>
            ) : null}
          </div>
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
      hint={open?.hint}
    />
  );
}
