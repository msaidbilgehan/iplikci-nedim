// The Turkish names of the service's codes come from /api/labels, its one mapping module (architecture §16). A code
// this version of the interface has no name for is shown as it is rather than hidden.

import type { Labels } from "../api/types";

/** The Turkish name of a code of a type ("EventKind", "Certainty", …), or the code itself when it has none. */
export function labelOf(labels: Labels, type: string, code: string): string {
  return labels[type]?.[code] ?? code;
}
