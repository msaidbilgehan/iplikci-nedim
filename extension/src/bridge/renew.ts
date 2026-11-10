/**
 * An unpacked extension keeps up with the program (ADR-0022). When İplikçi Nedim updates itself, the service rewrites
 * the extension's folder in the data folder at its next start and its cursor tells the version it carries. An
 * unpacked extension older than that loads itself again from its folder (chrome.runtime.reload), between runs and
 * never during a scan of Gmail, and only once for a version: an extension loaded from another folder, which did not
 * change, would otherwise load itself again and again. An extension from the Chrome Web Store is the store's to
 * update.
 */

import type { BridgeState } from "./state";

/** A version's numbers ("0.10.0" after "0.9.1"), the zeros at its end left out; null for what is no version. */
export function versionKey(text: string): number[] | null {
  const found = /^\d+(?:\.\d+)*/.exec(text);
  if (found === null) {
    return null;
  }
  const numbers = found[0].split(".").map(Number);
  while (numbers.length > 1 && numbers.at(-1) === 0) {
    numbers.pop();
  }
  return numbers;
}

/** Whether version is newer than `than`; never when either is no version. */
export function newer(version: string, than: string): boolean {
  const mine = versionKey(version);
  const theirs = versionKey(than);
  if (mine === null || theirs === null) {
    return false;
  }
  for (let i = 0; i < Math.max(mine.length, theirs.length); i += 1) {
    const a = mine[i] ?? 0;
    const b = theirs[i] ?? 0;
    if (a !== b) {
      return a > b;
    }
  }
  return false;
}

/** Whether this extension loads itself again now: unpacked, older than the program's, not tried for this version. */
export function shouldRenew(state: BridgeState, own: string, unpacked: boolean): boolean {
  return unpacked && state.paired !== null && newer(state.carried, own) && state.reloadedFor !== state.carried;
}
