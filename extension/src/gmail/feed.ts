/**
 * Layer 1 (ADR-0016): Gmail's inbox feed, an Atom document Google documents. It lists the unread messages of the
 * inbox and its categories, at most 20. Nothing of a message's subject, text or addresses is kept: the feed's title
 * and its links carry the user's address.
 */

import { FormatError } from "./errors";
import { type Fetcher, ORIGIN, get } from "./http";
import { attribute, elements, text } from "./xml";

export interface FeedEntry {
  /** Gmail's message id in decimal, as "Show original" takes it (`msg-f:…`). */
  readonly id: string;
  /** The legacy hexadecimal id in the entry's link; "" when the link has none. */
  readonly hexId: string;
  readonly issued: string;
  /** The sender's domain in lower case; "" when the entry names no address. */
  readonly senderDomain: string;
}

export interface Feed {
  /** How many unread messages the inbox holds; the feed lists at most 20 of them. */
  readonly unread: number;
  readonly entries: readonly FeedEntry[];
}

const ENTRY_ID = /^tag:gmail\.google\.com,2004:(\d+)$/;

export function feedUrl(account: number): string {
  return `${ORIGIN}/mail/u/${account}/feed/atom`;
}

export async function readFeed(fetcher: Fetcher, account: number): Promise<Feed> {
  const response = await get(fetcher, feedUrl(account));
  return parseFeed(await response.text());
}

export function parseFeed(xml: string): Feed {
  if (!/<feed[\s>]/.test(xml) || !xml.includes("http://purl.org/atom/ns#")) {
    throw new FormatError("gelen kutusu akışı Atom biçiminde değil");
  }
  const entries = elements(xml, "entry").map(parseEntry);
  const unread = Number.parseInt(text(xml, "fullcount"), 10);
  return { unread: Number.isNaN(unread) ? entries.length : unread, entries };
}

function parseEntry(entry: string): FeedEntry {
  const id = ENTRY_ID.exec(text(entry, "id"))?.[1];
  if (id === undefined) {
    throw new FormatError("akıştaki bir iletinin kimliği tanınmadı");
  }
  const email = text(elements(entry, "author")[0] ?? "", "email");
  const at = email.lastIndexOf("@");
  return {
    id,
    hexId: hexIdOf(entry),
    issued: text(entry, "issued"),
    senderDomain: at < 0 ? "" : email.slice(at + 1).toLowerCase(),
  };
}

function hexIdOf(entry: string): string {
  const link = /<link\s[^>]*>/.exec(entry)?.[0];
  const href = link === undefined ? null : attribute(link, "href");
  if (href === null || !URL.canParse(href)) {
    return "";
  }
  const hex = new URL(href).searchParams.get("message_id") ?? "";
  return /^[0-9a-f]{1,16}$/i.test(hex) ? hex.toLowerCase() : "";
}

/** Whether an entry's two ids name the same message: the decimal id is the hexadecimal one written in base 10. */
export function sameMessage(entry: FeedEntry): boolean {
  return entry.hexId !== "" && BigInt(`0x${entry.hexId}`).toString() === entry.id;
}
