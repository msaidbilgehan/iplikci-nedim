/**
 * A conversation's print view (`view=pt`), for the messages a scan's list does not name: the list shows only a
 * conversation's first and last message. The page shows every message of the conversation under its sender, and the
 * links to a message's attachments carry that message's id. Only those ids and the senders' domains are read; a
 * message without an attachment names no id on the page and stays out of reach. Whether the page marks messages read
 * is not known, so the scan asks for it only for a conversation Gmail lists as read throughout (ADR-0016).
 */

import { FormatError } from "./errors";
import { type Fetcher, ORIGIN, get } from "./http";
import { decimalId } from "./search";

/** A message of the print view that has an attachment: its id in hexadecimal and its sender's domain. */
export interface PrintedMessage {
  readonly id: string;
  readonly senderDomain: string;
}

export function printUrl(account: number, thread: string, ik: string | null): string {
  const query = new URLSearchParams();
  if (ik !== null) {
    query.set("ik", ik);
  }
  query.set("view", "pt");
  query.set("search", "all");
  query.set("permthid", `thread-f:${decimalId(thread)}`);
  return `${ORIGIN}/mail/u/${account}/?${query.toString()}`;
}

export async function readPrint(
  fetcher: Fetcher,
  account: number,
  thread: string,
  ik: string | null,
): Promise<PrintedMessage[]> {
  const response = await get(fetcher, printUrl(account, thread, ik));
  return parsePrint(await response.text());
}

/**
 * The messages with an attachment the page shows, in its order. Each message is a table of the class "message" whose
 * first font holds the sender ("Name <address>"); its attachments' links carry `view=att&th=<id>`. A page without
 * such a table is not a print view.
 */
export function parsePrint(html: string): PrintedMessage[] {
  const blocks = html.split(/<table\b[^>]*\bclass="?message"?[\s>]/i).slice(1);
  if (blocks.length === 0) {
    throw new FormatError("the print view shows no message");
  }
  const messages: PrintedMessage[] = [];
  for (const block of blocks) {
    const id = /\bview=att&(?:amp;)?th=([0-9a-f]{1,16})\b/.exec(block)?.[1];
    if (id === undefined) {
      continue;
    }
    const head = /<font\b[^>]*>([\s\S]*?)<\/font>/i.exec(block)?.[1] ?? "";
    const senderDomain = (/@([a-z0-9.-]+)/i.exec(head)?.[1] ?? "").toLowerCase();
    messages.push({ id, senderDomain });
  }
  return messages;
}
