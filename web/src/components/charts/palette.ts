// Every group and necessity level keeps one colour, whatever the filters (features.md, the charts' rules), chosen as
// the service chooses it (categorize.group_slot, NECESSITY_SLOTS): the first eight groups in the rule file's order
// take slots 1-8 of the palette (index.css), later groups and "Diğer" slot 0, the neutral grey.

import type { Necessity } from "../../api/schema";

export type Slot = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

export const MAX_COLORED_GROUPS = 8;
// The rule file's catch-all group (categorize.OTHER_GROUP): grey wherever it stands.
export const OTHER_GROUP = "Diğer";

/** A group's slot, as categorize.group_slot gives it: its place among the rule file's groups, from 1. */
export function groupSlot(groups: readonly string[], group: string): Slot {
  const found = groups.indexOf(group);
  const index = found === -1 ? groups.length : found;
  return index < MAX_COLORED_GROUPS && group !== OTHER_GROUP ? ((index + 1) as Slot) : 0;
}

// Blue, yellow and magenta passed the palette's checks as a stack of necessity levels in both themes.
export const NECESSITY_SLOTS: Readonly<Record<Necessity, Slot>> = {
  required: 1,
  optional: 4,
  unnecessary: 5,
  unknown: 0,
};

// Whole class names, so that Tailwind finds them in the source.
export const SLOT_FILL: Readonly<Record<Slot, string>> = {
  0: "fill-slot-0",
  1: "fill-slot-1",
  2: "fill-slot-2",
  3: "fill-slot-3",
  4: "fill-slot-4",
  5: "fill-slot-5",
  6: "fill-slot-6",
  7: "fill-slot-7",
  8: "fill-slot-8",
};

export const SLOT_STROKE: Readonly<Record<Slot, string>> = {
  0: "stroke-slot-0",
  1: "stroke-slot-1",
  2: "stroke-slot-2",
  3: "stroke-slot-3",
  4: "stroke-slot-4",
  5: "stroke-slot-5",
  6: "stroke-slot-6",
  7: "stroke-slot-7",
  8: "stroke-slot-8",
};

export const SLOT_BG: Readonly<Record<Slot, string>> = {
  0: "bg-slot-0",
  1: "bg-slot-1",
  2: "bg-slot-2",
  3: "bg-slot-3",
  4: "bg-slot-4",
  5: "bg-slot-5",
  6: "bg-slot-6",
  7: "bg-slot-7",
  8: "bg-slot-8",
};
