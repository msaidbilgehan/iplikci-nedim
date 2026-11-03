/**
 * İplikçi Nedim's word on the money in the extension's window (ADR-0020): the logo above it takes the colour of how
 * the money stands, as the Pano's face does (web/src/components/dashboard/NedimSays.tsx), and his line is said under
 * it with the situation it is about. The colour never says it alone: the line and its sentence say the same.
 */

import type { Mood } from "../bridge/service";

/** His face for each mood: the logo when the money goes well, the others drawn from it (packaging/icons.py). */
export const FACES: Readonly<Record<Mood, string>> = {
  good: "icons/icon-128.png",
  warning: "icons/face-warning.png",
  critical: "icons/face-critical.png",
  neutral: "icons/face-neutral.png",
};

/** A line as it is spoken: one sentence in quotation marks, a dialogue's turns each on a line of its own. */
export function spoken(lines: readonly string[]): string {
  return lines.length === 1 ? `“${lines[0] ?? ""}”` : lines.map((line) => `– ${line}`).join("\n");
}
