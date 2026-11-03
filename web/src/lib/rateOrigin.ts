// Where a rate comes from, said beside its day (F12, architecture §15): the row's own document, TCMB's bulletin, or
// ECB's reference rate, from Frankfurter or from ECB itself. Two forms, as Turkish needs them: the rate itself
// ("TCMB'nin 13.11.2026 kuru") and a value found with it ("TCMB'nin 13.11.2026 kuruyla"). A rate without a source
// is a document's, as every rate was before the providers came.

import type { TFunction } from "i18next";

import type { RateSource } from "../api/types";
import { formatDay } from "./format";

export type RateForm = "of" | "by";

/** "TCMB'nin 13.11.2026 kuru" (of), "13.11.2026 belgesindeki kurla" (by). */
export function rateOrigin(
  t: TFunction<"common">,
  source: RateSource | null | undefined,
  day: string,
  form: RateForm,
): string {
  return t(`rateOrigin.${form}.${source ?? "document"}`, { day: formatDay(day) });
}
