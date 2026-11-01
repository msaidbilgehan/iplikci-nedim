/**
 * Layer 3 (ADR-0016): a message as Gmail's "Show original" page shows it, the raw RFC 822 text in a `<pre>`, and
 * the page's "Download original" link. Not documented by Google: an unknown page is a format error.
 *
 * The page leaves the contents of attachments out: an attachment's part keeps its headers and comes empty. A message
 * that names a file is therefore taken whole, byte for byte, through "Download original".
 */

import { FormatError } from "./errors";
import { type Fetcher, ORIGIN, download, get } from "./http";
import { attribute, decodeEntities } from "./xml";

export interface Original {
  readonly raw: string;
  /** The page's "Download original" address; null when the page has no such link. */
  readonly download: string | null;
  /** The size of the page, for the verification report. */
  readonly pageBytes: number;
}

/**
 * What a "Show original" page without the raw text showed, for the format alarm: no text of it but its title, with
 * digits masked and anything that looks like an address left out.
 */
export interface PageTraits {
  readonly length: number;
  readonly title: string;
  /** Whether the page has the "Download original" link. */
  readonly download: boolean;
  /** Whether the page names the raw text's element at all. */
  readonly rawId: boolean;
}

/** The page shows no raw text: Gmail does not show this message (one too large, it may be), or its page changed. */
export class NoRawText extends FormatError {
  override name = "NoRawText";

  constructor(readonly traits: PageTraits) {
    super('"Orijinali göster" sayfasında iletinin metni bulunamadı');
  }
}

const RAW = /<pre\b[^>]*\bid\s*=\s*["']?raw_message_text\b["']?[^>]*>([\s\S]*?)<\/pre>/i;
const TITLE = /<title\b[^>]*>([\s\S]*?)<\/title>/i;

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

/** Whether the raw text names a file of its own: "Show original" has left the file's contents out. */
export function namesAFile(raw: string): boolean {
  return /\bfilename\*?\s*=|;\s*name\*?\s*=/i.test(raw);
}

/** The whole message, attachments included, byte for byte, as "Download original" gives it. */
export async function downloadOriginal(fetcher: Fetcher, link: string): Promise<Uint8Array<ArrayBuffer>> {
  const bytes = new Uint8Array(await (await download(fetcher, link)).arrayBuffer());
  if (bytes.byteLength === 0) {
    throw new FormatError('"Orijinali indir" boş döndü');
  }
  return bytes;
}

export function parseOriginal(html: string, pageUrl: string): Original {
  const match = RAW.exec(html);
  if (match === null) {
    throw new NoRawText(traits(html, pageUrl));
  }
  // HTML drops a newline that directly follows <pre>.
  const raw = decodeEntities(match[1] ?? "").replace(/^\r?\n/, "");
  return { raw, download: downloadLink(html, pageUrl), pageBytes: html.length };
}

function traits(html: string, pageUrl: string): PageTraits {
  const words = decodeEntities(TITLE.exec(html)?.[1] ?? "")
    .split(/\s+/)
    .filter((word) => word !== "" && !word.includes("@"));
  return {
    length: html.length,
    title: words.join(" ").replace(/\d/g, "#").slice(0, 60),
    download: downloadLink(html, pageUrl) !== null,
    rawId: html.includes("raw_message_text"),
  };
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
