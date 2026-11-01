/**
 * The few XML and HTML text helpers the Gmail adapter needs. An extension's service worker has no DOMParser, and
 * Gmail's answers are small and regular enough for patterns.
 */

const NAMED: Readonly<Record<string, string>> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: "\u00a0",
};

/** Text with its character references (`&amp;`, `&#39;`, `&#x27;`) replaced by the characters they stand for. */
export function decodeEntities(text: string): string {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (reference: string, body: string) => {
    if (body.startsWith("#")) {
      const hex = body[1] === "x" || body[1] === "X";
      const code = Number.parseInt(body.slice(hex ? 2 : 1), hex ? 16 : 10);
      return code >= 0 && code <= 0x10ffff ? String.fromCodePoint(code) : reference;
    }
    return NAMED[body.toLowerCase()] ?? reference;
  });
}

/** The inner source of every `<name>…</name>` element, in order; elements of one name do not nest in Gmail's feed. */
export function elements(xml: string, name: string): string[] {
  const pattern = new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "g");
  return [...xml.matchAll(pattern)].map((match) => match[1] ?? "");
}

/** The decoded text of the first `<name>` element; "" when there is none. */
export function text(xml: string, name: string): string {
  const [first] = elements(xml, name);
  return first === undefined ? "" : decodeEntities(first.trim());
}

/** The decoded value of an attribute in a start tag; null when the tag has no such attribute. */
export function attribute(tag: string, name: string): string | null {
  const match = new RegExp(`\\s${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)')`, "i").exec(tag);
  return match ? decodeEntities(match[1] ?? match[2] ?? "") : null;
}
