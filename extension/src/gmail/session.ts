/**
 * The account key (`ik`) Gmail's own links carry, read from the Gmail page of an account. The page keeps it in its
 * `GLOBALS` array (the tenth item); some links in the page carry it too.
 */

import { type Fetcher, ORIGIN, get } from "./http";

export interface AccountKey {
  readonly ik: string;
  /** Where the page held it, for the verification report. */
  readonly where: "GLOBALS" | "bağlantı";
}

const IK = /^[0-9a-f]{6,16}$/;

export function appUrl(account: number): string {
  return `${ORIGIN}/mail/u/${account}/`;
}

export async function readAccountKey(fetcher: Fetcher, account: number): Promise<AccountKey | null> {
  const response = await get(fetcher, appUrl(account));
  return parseAccountKey(await response.text());
}

export function parseAccountKey(html: string): AccountKey | null {
  const globals = /\bvar GLOBALS\s*=\s*\[/.exec(html);
  if (globals !== null) {
    const item = topLevelItems(html, globals.index + globals[0].length, 10)[9] ?? "";
    const value = /^"([^"]*)"$/.exec(item)?.[1] ?? "";
    if (IK.test(value)) {
      return { ik: value, where: "GLOBALS" };
    }
  }
  const link = /[?&](?:amp;)?ik=([0-9a-f]{6,16})\b/.exec(html)?.[1];
  return link === undefined ? null : { ik: link, where: "bağlantı" };
}

/** The source of the first `count` top-level items of the array literal whose items start at `start`. */
function topLevelItems(source: string, start: number, count: number): string[] {
  const items: string[] = [];
  let depth = 0;
  let quote = "";
  let itemStart = start;
  for (let i = start; i < source.length && items.length < count; i++) {
    const ch = source[i];
    if (quote !== "") {
      if (ch === "\\") {
        i++;
      } else if (ch === quote) {
        quote = "";
      }
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === "[" || ch === "{" || ch === "(") {
      depth++;
    } else if (ch === "]" || ch === "}" || ch === ")") {
      if (depth === 0) {
        items.push(source.slice(itemStart, i).trim());
        break;
      }
      depth--;
    } else if (ch === "," && depth === 0) {
      items.push(source.slice(itemStart, i).trim());
      itemStart = i + 1;
    }
  }
  return items;
}
