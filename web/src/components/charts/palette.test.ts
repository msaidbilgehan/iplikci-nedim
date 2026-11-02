import { describe, expect, it } from "vitest";

import { groupSlot, NECESSITY_SLOTS, SLOT_BG, SLOT_FILL, SLOT_STROKE, type Slot } from "./palette";

const GROUPS = [
  "Market & Gıda",
  "Ulaşım",
  "Ev & Faturalar",
  "Sağlık",
  "Eğlence",
  "Giyim",
  "Eğitim",
  "Banka & Finans",
  "Bağış",
  "Diğer",
];

describe("groupSlot", () => {
  it("gives the first eight groups of the rule file slots 1 to 8, as categorize.group_slot does", () => {
    expect(GROUPS.slice(0, 8).map((group) => groupSlot(GROUPS, group))).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it("leaves later groups and Diğer grey, wherever Diğer stands", () => {
    expect(groupSlot(GROUPS, "Bağış")).toBe(0);
    expect(groupSlot(GROUPS, "Diğer")).toBe(0);
    expect(groupSlot(["Diğer", "Market & Gıda"], "Diğer")).toBe(0);
    expect(groupSlot(["Diğer", "Market & Gıda"], "Market & Gıda")).toBe(2);
  });

  it("gives a group the rules do not list the next place, as the service does", () => {
    expect(groupSlot(["Market & Gıda", "Ulaşım"], "Yeni grup")).toBe(3);
    expect(groupSlot(GROUPS, "Yeni grup")).toBe(0);
  });

  it("keeps a group's slot whatever else is shown: it depends on the rule file's order only", () => {
    const shown = ["Sağlık", "Ulaşım"];
    expect(shown.map((group) => groupSlot(GROUPS, group))).toEqual([4, 2]);
  });
});

describe("slots", () => {
  it("colours the necessity levels blue, yellow and magenta, and the unknown one grey", () => {
    expect(NECESSITY_SLOTS).toEqual({ required: 1, optional: 4, unnecessary: 5, unknown: 0 });
  });

  it("names every slot's fill, stroke and background in full, for Tailwind to find", () => {
    const slots: Slot[] = [0, 1, 2, 3, 4, 5, 6, 7, 8];
    for (const slot of slots) {
      expect(SLOT_FILL[slot]).toBe(`fill-slot-${slot}`);
      expect(SLOT_STROKE[slot]).toBe(`stroke-slot-${slot}`);
      expect(SLOT_BG[slot]).toBe(`bg-slot-${slot}`);
    }
  });
});
