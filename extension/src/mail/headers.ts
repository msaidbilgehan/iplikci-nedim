/**
 * An RFC 822 message's header fields, enough for the trust rule's header half (ADR-0015): the sender's domain and
 * the topmost Authentication-Results. The service applies the rule again on every message it takes; the bridge only
 * uses it to send nothing it would refuse.
 */

export interface Header {
  readonly name: string;
  readonly value: string;
}

export interface Authentication {
  /** Who added the topmost Authentication-Results (Gmail: `mx.google.com`). */
  readonly server: string;
  /** The domain DMARC passed for; "" when it did not pass. */
  readonly dmarcPassFor: string;
}

const DMARC = /\bdmarc\s*=\s*pass\b[^;]*?\bheader\.from\s*=\s*"?([a-z0-9.-]+)/i;
const SERVER_HEADERS = ["received", "delivered-to", "message-id", "mime-version"];

/** The header fields in order, folded lines joined; the header ends at the first empty line. */
export function headers(raw: string): Header[] {
  const end = raw.search(/\r?\n\r?\n/);
  const fields: Header[] = [];
  for (const line of (end < 0 ? raw : raw.slice(0, end)).split(/\r?\n/)) {
    const last = fields.at(-1);
    if (/^[ \t]/.test(line) && last !== undefined) {
      fields[fields.length - 1] = { name: last.name, value: `${last.value} ${line.trim()}` };
      continue;
    }
    const colon = line.indexOf(":");
    if (colon > 0) {
      fields.push({ name: line.slice(0, colon).trim(), value: line.slice(colon + 1).trim() });
    }
  }
  return fields;
}

/** The value of the first field called name (any case); null when there is none. */
export function field(fields: readonly Header[], name: string): string | null {
  const wanted = name.toLowerCase();
  return fields.find((h) => h.name.toLowerCase() === wanted)?.value ?? null;
}

/** Whether the text is an e-mail message: header fields first, with From and one a mail server adds. */
export function looksLikeMessage(raw: string): boolean {
  const fields = headers(raw);
  const names = new Set(fields.map((h) => h.name.toLowerCase()));
  return fields.length >= 3 && names.has("from") && SERVER_HEADERS.some((name) => names.has(name));
}

/** The domain of the From address in lower case; "" when there is none. */
export function senderDomain(fields: readonly Header[]): string {
  const from = field(fields, "From") ?? "";
  const address = /<([^<>]*)>\s*$/.exec(from)?.[1] ?? from;
  const at = address.lastIndexOf("@");
  return at < 0 ? "" : (/^[a-z0-9.-]+/i.exec(address.slice(at + 1).trim())?.[0] ?? "").toLowerCase();
}

/** What the topmost Authentication-Results says; null when the message has none. */
export function topAuthentication(fields: readonly Header[]): Authentication | null {
  const top = field(fields, "Authentication-Results");
  if (top === null) {
    return null;
  }
  const value = top.replace(/\s+/g, " ");
  return {
    server: (value.split(";", 1)[0] ?? "").trim().toLowerCase(),
    dmarcPassFor: DMARC.exec(value)?.[1]?.toLowerCase() ?? "",
  };
}

/** Gmail's own topmost Authentication-Results shows DMARC pass for the From domain. */
export function verifiedByGmail(fields: readonly Header[]): boolean {
  const authentication = topAuthentication(fields);
  const domain = senderDomain(fields);
  return authentication?.server === "mx.google.com" && domain !== "" && authentication.dmarcPassFor === domain;
}

/** Whether a domain is on the sender list, itself or as a subdomain of a listed one. */
export function listed(domain: string, senders: readonly string[]): boolean {
  return domain !== "" && senders.some((sender) => domain === sender || domain.endsWith(`.${sender}`));
}
