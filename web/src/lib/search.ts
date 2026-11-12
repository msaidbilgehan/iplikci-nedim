// A search box's text as the service reads it (domain/search.py): a comma separates its parts and a row needs one of
// them ("market, kira"); the spaces of a part separate its words and a row needs all of them ("migros kadıköy"); a
// quoted term is kept as written, commas included; a comma between two digits is a decimal comma ("1,50"). The screens
// read it so where they narrow something themselves (Değerlendirme's regular payments) and to name the parts.

import { fold } from "./turkish";

const QUOTES = new Set(['"', "“", "”", "„"]); // a straight quote and the curly ones a keyboard or a paste may give
const DIGIT = /^[0-9]$/;
const DISJUNCTION = new Intl.ListFormat("tr-TR", { style: "long", type: "disjunction" });

/** One of a search's parts: a row is found by it when it has every one of its terms. */
export interface SearchPart {
  text: string; // as written, its terms one space apart and a quoted one in straight quotes
  terms: readonly string[]; // folded
}

function isDecimalComma(text: string, at: number): boolean {
  return DIGIT.test(text[at - 1] ?? "") && DIGIT.test(text[at + 1] ?? "");
}

/** text's parts, each its terms as written with whether the term was quoted. */
function pieces(text: string): [string, boolean][][] {
  const parts: [string, boolean][][] = [[]];
  const current = () => parts[parts.length - 1]!;
  let word = "";
  let phrase: string | null = null; // inside quotes: the term so far
  for (let at = 0; at < text.length; at += 1) {
    const c = text[at]!;
    if (phrase !== null) {
      if (QUOTES.has(c)) {
        current().push([phrase, true]);
        phrase = null;
      } else {
        phrase += c;
      }
      continue;
    }
    if (QUOTES.has(c) || /\s/.test(c) || (c === "," && !isDecimalComma(text, at))) {
      if (word) {
        current().push([word, false]);
        word = "";
      }
      if (QUOTES.has(c)) {
        phrase = "";
      } else if (c === ",") {
        parts.push([]);
      }
      continue;
    }
    word += c;
  }
  if (phrase !== null) {
    current().push([phrase, true]); // a quote left open runs to the end
  } else if (word) {
    current().push([word, false]);
  }
  return parts;
}

/** A search box's text read into its parts; empty parts and terms are left out, a part written twice is kept once. */
export function searchParts(text: string): SearchPart[] {
  const parts = new Map<string, SearchPart>();
  for (const piece of pieces(text)) {
    const kept = piece
      .map(([written, quoted]) => [written.split(/\s+/).filter(Boolean).join(" "), quoted] as const)
      .filter(([written]) => fold(written) !== "");
    const terms = kept.map(([written]) => fold(written));
    const key = JSON.stringify(terms);
    if (terms.length > 0 && !parts.has(key)) {
      parts.set(key, { text: kept.map(([w, quoted]) => (quoted ? `"${w}"` : w)).join(" "), terms });
    }
  }
  return [...parts.values()];
}

/** Whether a text, folded, has every term of one of the parts; no part finds every text. */
export function isFound(parts: readonly SearchPart[], folded: string): boolean {
  return parts.length === 0 || parts.some((part) => part.terms.every((term) => folded.includes(term)));
}

/** A search in words, its parts as alternatives: "market, kira" → "market veya kira". */
export function searchInWords(text: string): string {
  return DISJUNCTION.format(searchParts(text).map((part) => part.text));
}
