// The suffixes Turkish writes after numbers and years, as the service writes them (insights.py: year_suffix, pct;
// features.md: "Sayılardan ve yıllardan sonraki ekler yardımcı işlevlerle kurulur"). A number takes the suffix its
// spoken form asks for: the last word decides the vowel (harmony) and whether d hardens to t. The suffix follows an
// apostrophe, as Turkish writes it after digits: 2026'da, %64'ü, ayın 3'ünde.

import { formatMonth } from "./format";

const ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"] as const;
const TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"] as const;
// What a number ending in 000 is called by its lowest group of three digits that is not zero.
const GROUPS = ["bin", "milyon", "milyar", "trilyon", "katrilyon"] as const;

const VOWELS = "aeıioöuü";
const BACK_VOWELS = "aıou";
// After a voiceless consonant the d of -da/-dan turns into t: üç → 3'te, kırk → 40'ta.
const VOICELESS = "çfhkpsşt";
// The four-way harmony of the possessive: a/ı → ı, o/u → u, e/i → i, ö/ü → ü.
const FOUR_WAY: Readonly<Record<string, string>> = { a: "ı", ı: "ı", o: "u", u: "u", e: "i", i: "i", ö: "ü", ü: "ü" };

const MONTH_NAME = new Intl.DateTimeFormat("tr-TR", { month: "long", timeZone: "UTC" });
const PERCENT = new Intl.NumberFormat("tr-TR", { style: "percent", maximumFractionDigits: 0 });
const CONJUNCTION = new Intl.ListFormat("tr-TR", { style: "long", type: "conjunction" });

/** The word a whole number ends with when spoken: 2026 → "altı", 2020 → "yirmi", 1900 → "yüz", 3000 → "bin". */
export function lastWord(value: number): string {
  let n = Math.abs(Math.trunc(value));
  if (n === 0) {
    return "sıfır";
  }
  if (n % 10 !== 0) {
    return ONES[n % 10] ?? "";
  }
  if (n % 100 !== 0) {
    return TENS[Math.floor(n / 10) % 10] ?? "";
  }
  if (n % 1000 !== 0) {
    return "yüz";
  }
  let group = 0;
  n = Math.floor(n / 1000);
  while (n % 1000 === 0 && group < GROUPS.length - 1) {
    n = Math.floor(n / 1000);
    group += 1;
  }
  return GROUPS[group] ?? "";
}

function lastVowel(word: string): string {
  for (let i = word.length - 1; i >= 0; i -= 1) {
    const letter = word.charAt(i);
    if (VOWELS.includes(letter)) {
      return letter;
    }
  }
  return "e";
}

const twoWay = (vowel: string): string => (BACK_VOWELS.includes(vowel) ? "a" : "e");

/** The locative after a number: 2026 → "'da", 2025 → "'te", 40 → "'ta", 1000 → "'de". */
export function locative(value: number): string {
  const word = lastWord(value);
  const d = VOICELESS.includes(word.charAt(word.length - 1)) ? "t" : "d";
  return `'${d}${twoWay(lastVowel(word))}`;
}

/** The ablative after a number: 2026 → "'dan", 2025 → "'ten". */
export function ablative(value: number): string {
  return `${locative(value)}n`;
}

/** The possessive after a number, as after a share: 64 → "'ü", 72 → "'si", 6 → "'sı", 1000 → "'i". */
export function possessive(value: number): string {
  const word = lastWord(value);
  const vowel = FOUR_WAY[lastVowel(word)] ?? "i";
  return VOWELS.includes(word.charAt(word.length - 1)) ? `'s${vowel}` : `'${vowel}`;
}

/** The possessive and the locative after a day of the month: ayın 3'ünde, 6'sında, 10'unda, 20'sinde. */
export function possessiveLocative(value: number): string {
  const suffix = possessive(value);
  // The n between them is the possessive's buffer; d stays d after it.
  return `${suffix}nd${twoWay(suffix.charAt(suffix.length - 1))}`;
}

/** A year's locative or ablative, as insights.year_suffix: "2026" → "'da" / "'dan", "2025" → "'te" / "'ten". */
export function yearSuffix(year: string | number, ablativeCase: boolean): string {
  const n = typeof year === "number" ? year : Number(year);
  return ablativeCase ? ablative(n) : locative(n);
}

/** Rounded as Python's round(): an exact half goes to the even neighbour, so the service and the interface agree. */
export function roundHalfEven(value: number): number {
  const floor = Math.floor(value);
  const rest = value - floor;
  if (rest !== 0.5) {
    return Math.round(value);
  }
  return floor % 2 === 0 ? floor : floor + 1;
}

/** A share as a whole percent, as Turkish writes it: 0.64 → "%64", −0.05 → "−%5". */
export function percent(share: number): string {
  return PERCENT.format(roundHalfEven(share * 100) / 100).replace("-", "−");
}

/** A share with the possessive Turkish needs after it, as insights.pct: 0.64 → "%64'ü", 0.06 → "%6'sı". */
export function percentPossessive(share: number): string {
  return `${percent(share)}${possessive(roundHalfEven(share * 100))}`;
}

/** "2026-03" → "Mart 2026'da". */
export function inMonth(month: string): string {
  return `${formatMonth(month)}${yearSuffix(month.slice(0, 4), false)}`;
}

/** "2026-05" → "Mayıs 2026'dan" ("… beri", "… itibaren"). */
export function fromMonth(month: string): string {
  return `${formatMonth(month)}${yearSuffix(month.slice(0, 4), true)}`;
}

/** As insights.months_in: ["2026-03", "2026-07", "2025-12"] → "Mart ve Temmuz 2026'da, Aralık 2025'te". */
export function monthsIn(months: readonly string[]): string {
  const byYear = new Map<string, string[]>();
  for (const month of months) {
    const [year = "", number = "1"] = month.split("-");
    const name = MONTH_NAME.format(new Date(Date.UTC(Number(year), Number(number) - 1, 1)));
    byYear.set(year, [...(byYear.get(year) ?? []), name]);
  }
  return [...byYear]
    .map(([year, names]) => `${CONJUNCTION.format(names)} ${year}${yearSuffix(year, false)}`)
    .join(", ");
}
