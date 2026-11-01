/**
 * Layer 2 (ADR-0016): finding read and archived messages, the history, with Gmail's search. Gmail's web interface
 * documents no search address; this tries the thread list its pages used to load (`view=tl`). The verification
 * reports whether it still answers; if not, the ADR's fallback collects the messages an open Gmail tab shows.
 */

import { ORIGIN } from "./http";

export function senderQuery(senders: readonly string[], extra: string): string {
  return `from:(${senders.join(" OR ")}) ${extra}`.trim();
}

export function threadListUrl(account: number, ik: string, query: string): string {
  const params = new URLSearchParams({
    ui: "2",
    ik,
    view: "tl",
    start: "0",
    num: "50",
    search: "query",
    q: query,
  });
  return `${ORIGIN}/mail/u/${account}/?${params.toString()}`;
}

/** What kind of answer a body is, for the verification report. */
export function answerKind(body: string): "json" | "html" | "other" {
  const head = body.trimStart().slice(0, 200).toLowerCase();
  if (head.startsWith(")]}'") || head.startsWith("while(1);") || head.startsWith("[")) {
    return "json";
  }
  return head.startsWith("<!doctype html") || head.startsWith("<html") ? "html" : "other";
}

/** The hexadecimal thread ids a thread-list answer names, in order and without repeats. */
export function threadIds(body: string): string[] {
  const ids = [...body.matchAll(/["'[,]([0-9a-f]{16})["',\]]/g)].map((match) => match[1] ?? "");
  return [...new Set(ids.filter((id) => id !== ""))];
}

/** A hexadecimal id in decimal, as "Show original" takes it. */
export function decimalId(hexId: string): string {
  return BigInt(`0x${hexId}`).toString();
}
