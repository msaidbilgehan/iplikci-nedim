/**
 * Layer 3 (ADR-0016): a message as Gmail's "Show original" page shows it, the raw RFC 822 text in a `<pre>`, and
 * the page's "Download original" link. Not documented by Google: an unknown page is a format error.
 */

import { FormatError } from "./errors";
import { type Fetcher, ORIGIN, get } from "./http";
import { attribute, decodeEntities } from "./xml";

export interface Original {
  readonly raw: string;
  /** The page's "Download original" address; null when the page has no such link. */
  readonly download: string | null;
  /** The size of the page, for the verification report. */
  readonly pageBytes: number;
}

const RAW = /<pre\b[^>]*\bid\s*=\s*["']?raw_message_text\b["']?[^>]*>([\s\S]*?)<\/pre>/i;

export function originalUrl(account: number, id: string, ik: string | null): string {
  const query = new URLSearchParams();
  if (ik !== null) {
    query.set("ik", ik);
  }
  query.set("view", "om");
  query.set("permmsgid", `msg-f:${id}`);
  return `${ORIGIN}/mail/u/${account}/?${query.toString()}`;
}

export async function readOriginal(fetcher: Fetcher, account: number, id: string, ik: string | null): Promise<Original> {
  const url = originalUrl(account, id, ik);
  const response = await get(fetcher, url);
  return parseOriginal(await response.text(), url);
}

export function parseOriginal(html: string, pageUrl: string): Original {
  const match = RAW.exec(html);
  if (match === null) {
    throw new FormatError('"Orijinali göster" sayfasında iletinin metni bulunamadı');
  }
  // HTML drops a newline that directly follows <pre>.
  const raw = decodeEntities(match[1] ?? "").replace(/^\r?\n/, "");
  return { raw, download: downloadLink(html, pageUrl), pageBytes: html.length };
}

function downloadLink(html: string, pageUrl: string): string | null {
  for (const tag of html.match(/<a\s[^>]*>/gi) ?? []) {
    const href = attribute(tag, "href");
    if (href !== null && /[?&]view=att\b/.test(href) && /[?&](?:disp=comp|attid=0)\b/.test(href)) {
      return URL.canParse(href, pageUrl) ? new URL(href, pageUrl).toString() : null;
    }
  }
  return null;
}
