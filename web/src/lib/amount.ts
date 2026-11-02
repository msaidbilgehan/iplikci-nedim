// Amounts the user types: Turkish lira as Turkish readers write them, dots between thousands and a decimal comma
// ("7.500" or "7.500,50"), carried as kuruş, the minor units the API speaks (ADR-0006). Integers all the way, so no
// amount is rounded on the way.

const WHOLE = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0, useGrouping: "always" });
// Whole lira with or without dots between the thousands, then up to two digits of kuruş after a comma. A dot with
// one or two digits after it ("7500.50") is refused: in Turkish it would mean thousands.
const TYPED = /^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$/;

/** "7.500", "7500" or "7.500,5" (a trailing "TL" allowed) → 750000, 750000, 750050 kuruş; null for anything else. */
export function parseLira(text: string): number | null {
  const found = TYPED.exec(text.replace(/\s+/g, "").replace(/tl$/i, ""));
  if (!found) {
    return null;
  }
  const lira = Number((found[1] ?? "").replaceAll(".", ""));
  const kurus = Number((found[2] ?? "").padEnd(2, "0"));
  const total = lira * 100 + kurus;
  return Number.isSafeInteger(total) ? total : null;
}

/** Kuruş as the user would type them back: 750000 → "7.500", 750050 → "7.500,50". */
export function liraInput(kurus: number): string {
  const whole = WHOLE.format(Math.trunc(kurus / 100));
  const rest = kurus % 100;
  return rest ? `${whole},${String(rest).padStart(2, "0")}` : whole;
}
