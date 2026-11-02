// The Sankey's geometry (F07's flow between the accounts), apart from drawing it: d3-sankey places the nodes in
// columns by where the money goes and sizes each by what passes through it; a link is a band as wide as its amount,
// drawn as a curve from the right edge of its source to the left edge of its target. A flow with a loop cannot be
// drawn (the service nets two places' money both ways, so it should have none): the layout gives null, and the table
// view still shows every link.

import { sankey, sankeyJustify } from "d3-sankey";

import type { Margin, Size } from "./layout";
import type { Slot } from "./palette";

export interface FlowPoint {
  id: string;
  label: string;
  slot: Slot | null; // a spending group's colour; null for the neutral ink of the accounts and the rest
}

export interface FlowBand {
  key: string;
  source: string; // a point's id
  target: string;
  value: number; // minor units, above zero
}

export interface PlacedPoint extends FlowPoint {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  value: number; // what passes through it
  labelOnRight: boolean; // its label stands right of it in the left half, left of it in the right half
}

export interface PlacedBand {
  key: string;
  source: PlacedPoint;
  target: PlacedPoint;
  value: number;
  width: number;
  d: string;
}

export interface SankeyLayout {
  points: PlacedPoint[];
  bands: PlacedBand[];
}

export const NODE_WIDTH = 12;
export const NODE_PADDING = 18; // room for a one-line label between two nodes of a column

const round = (n: number): number => Math.round(n * 100) / 100;

/** The nodes and links placed in the plot; null when there is nothing to draw or the flow has a loop. */
export function sankeyLayout(
  points: readonly FlowPoint[],
  bands: readonly FlowBand[],
  size: Size,
  margin: Margin,
): SankeyLayout | null {
  const drawn = bands.filter((band) => band.value > 0);
  if (drawn.length === 0) {
    return null;
  }
  const used = new Set(drawn.flatMap((band) => [band.source, band.target]));
  try {
    const graph = sankey<FlowPoint, FlowBand>()
      .nodeId((point) => point.id)
      .nodeAlign(sankeyJustify)
      .nodeWidth(NODE_WIDTH)
      .nodePadding(NODE_PADDING)
      .extent([
        [margin.left, margin.top],
        [size.width - margin.right, size.height - margin.bottom],
      ])({
      nodes: points.filter((point) => used.has(point.id)).map((point) => ({ ...point })),
      links: drawn.map((band) => ({ ...band })),
    });
    const middle = size.width / 2;
    const placed = new Map<string, PlacedPoint>();
    for (const node of graph.nodes) {
      const [x0, x1, y0, y1] = [node.x0 ?? 0, node.x1 ?? 0, node.y0 ?? 0, node.y1 ?? 0];
      placed.set(node.id, {
        id: node.id,
        label: node.label,
        slot: node.slot,
        x0: round(x0),
        x1: round(x1),
        y0: round(y0),
        y1: round(y1),
        value: node.value ?? 0,
        labelOnRight: x0 < middle,
      });
    }
    const pointOf = (end: unknown): PlacedPoint | undefined =>
      typeof end === "object" && end !== null && "id" in end ? placed.get(String(end.id)) : undefined;
    const found: PlacedBand[] = [];
    for (const link of graph.links) {
      const source = pointOf(link.source);
      const target = pointOf(link.target);
      if (!source || !target) {
        continue;
      }
      const [y0, y1, xm] = [round(link.y0 ?? 0), round(link.y1 ?? 0), round((source.x1 + target.x0) / 2)];
      found.push({
        key: link.key,
        source,
        target,
        value: link.value,
        width: Math.max(1, round(link.width ?? 0)),
        d: `M${source.x1},${y0}C${xm},${y0} ${xm},${y1} ${target.x0},${y1}`,
      });
    }
    return { points: [...placed.values()], bands: found };
  } catch {
    return null; // a loop, or a link to a node the flow does not name
  }
}

/** How tall the drawing is for the most nodes one column holds: each a line of label and the room between. */
export function sankeyHeight(points: readonly FlowPoint[], bands: readonly FlowBand[], least = 240): number {
  const sources = new Set(bands.map((band) => band.source));
  const targets = new Set(bands.map((band) => band.target));
  const starts = points.filter((point) => sources.has(point.id) && !targets.has(point.id)).length;
  const ends = points.filter((point) => targets.has(point.id) && !sources.has(point.id)).length;
  const between = points.filter((point) => sources.has(point.id) && targets.has(point.id)).length;
  return Math.max(least, Math.max(starts, ends, between) * (NODE_PADDING + 22) + 40);
}
