/**
 * The paired İplikçi Nedim service, on this computer only (ADR-0016): pairing with a code, the proof that the
 * service is the one paired with, where delivery stands, the delivery of raw messages, and a login link for the
 * interface (ADR-0019). The token goes in the Authorization header only; no cookie is sent.
 */

import type { PageTraits } from "../gmail/original";
import { expectedProof, newNonce } from "./proof";

export const SERVICE = "http://127.0.0.1:8643";
/** What the service takes at most (its MAX_MESSAGE_BYTES). */
export const MAX_MESSAGE_BYTES = 40 * 1024 * 1024;
/** How many ids the service checks in one call (its KnownIn). */
const KNOWN_PER_CALL = 1000;

export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

export interface Paired {
  readonly id: string;
  readonly token: string;
}

export interface Cursor {
  /** Gmail's id and date of the newest message the service took from this bridge; "" before the first. */
  readonly lastId: string;
  readonly lastDate: string;
  /** The history begins on this day (YYYY-MM-DD). */
  readonly startDay: string;
  /** The sender domains whose messages are delivered. */
  readonly senders: readonly string[];
  /** No finished scan of Gmail searched this start day and these senders (false from a service that does not say). */
  readonly historyDue: boolean;
}

/** The service does not answer: it is not running on this computer. */
export class ServiceDown extends Error {
  override name = "ServiceDown";
}

/** The service refused: an expired code, a revoked pairing, a message too large; message is its Turkish title. */
export class Refused extends Error {
  override name = "Refused";

  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** The process on 127.0.0.1:8643 could not prove it is the paired service. */
export class NotTheService extends Error {
  override name = "NotTheService";
}

async function call(fetcher: Fetcher, path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetcher(`${SERVICE}${path}`, { ...init, credentials: "omit", cache: "no-store" });
  } catch {
    throw new ServiceDown("İplikçi Nedim bu bilgisayarda çalışmıyor");
  }
  if (!response.ok) {
    let code = `http_${response.status}`;
    let title = `servis ${response.status} yanıtı verdi`;
    try {
      const problem = (await response.json()) as { code?: unknown; title?: unknown };
      code = typeof problem.code === "string" ? problem.code : code;
      title = typeof problem.title === "string" ? problem.title : title;
    } catch {
      // not a problem document: keep the status
    }
    throw new Refused(response.status, code, title);
  }
  return response;
}

function bearer(paired: Paired): Record<string, string> {
  return { Authorization: `Bearer ${paired.token}` };
}

/** Trade a pairing code (from the service's page) for this bridge's token. */
export async function pair(fetcher: Fetcher, code: string, name: string): Promise<Paired> {
  const response = await call(fetcher, "/api/bridge/pair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: code.trim(), name }),
  });
  const found = (await response.json()) as { id?: unknown; token?: unknown };
  if (typeof found.id !== "string" || typeof found.token !== "string") {
    throw new Refused(response.status, "pairing_answer", "servisin eşleştirme yanıtı anlaşılamadı");
  }
  return { id: found.id, token: found.token };
}

/** Make the service prove it holds this bridge's secret; NotTheService when it cannot. */
export async function prove(fetcher: Fetcher, paired: Paired, nonce: string = newNonce()): Promise<void> {
  const query = new URLSearchParams({ id: paired.id, nonce });
  let answer: unknown;
  try {
    answer = await (await call(fetcher, `/api/bridge/hello?${query.toString()}`, { method: "GET" })).json();
  } catch (error) {
    if (error instanceof Refused && error.status === 404) {
      throw error; // the service does not know this pairing (revoked): not a stranger
    }
    if (error instanceof ServiceDown) {
      throw error;
    }
    throw new NotTheService("bu bilgisayardaki servis eşleşilen servis değil");
  }
  const proof = (answer as { proof?: unknown }).proof;
  if (typeof proof !== "string" || proof !== (await expectedProof(paired.token, nonce))) {
    throw new NotTheService("bu bilgisayardaki servis eşleşilen servis değil");
  }
}

/**
 * A one-time login link for the interface, as the command line gets one (ADR-0019): it opens a browser session
 * within two minutes, once. What it leads to is the caller's to check.
 */
export async function loginLink(fetcher: Fetcher, paired: Paired): Promise<string> {
  const response = await call(fetcher, "/api/bridge/login-link", { method: "POST", headers: bearer(paired) });
  const found = (await response.json()) as { url?: unknown };
  if (typeof found.url !== "string") {
    throw new Refused(response.status, "login_link_answer", "servisin giriş bağlantısı yanıtı anlaşılamadı");
  }
  return found.url;
}

export async function cursor(fetcher: Fetcher, paired: Paired): Promise<Cursor> {
  const response = await call(fetcher, "/api/ingest/mail/cursor", { method: "GET", headers: bearer(paired) });
  const found = (await response.json()) as Record<string, unknown>;
  const senders = Array.isArray(found["senders"]) ? found["senders"].filter((s) => typeof s === "string") : [];
  return {
    lastId: typeof found["last_id"] === "string" ? found["last_id"] : "",
    lastDate: typeof found["last_date"] === "string" ? found["last_date"] : "",
    startDay: typeof found["start_day"] === "string" ? found["start_day"] : "",
    senders,
    historyDue: found["history_due"] === true,
  };
}

/** Deliver one raw message; what the service did with it (stored, known, unlisted, unverified, business, …). */
export async function deliver(
  fetcher: Fetcher,
  paired: Paired,
  raw: Uint8Array<ArrayBuffer>,
  gmailId: string,
  gmailDate: string,
): Promise<string> {
  const response = await call(fetcher, "/api/ingest/mail", {
    method: "POST",
    headers: { ...bearer(paired), "Content-Type": "message/rfc822", "X-Gmail-Id": gmailId, "X-Gmail-Date": gmailDate },
    body: raw,
  });
  const found = (await response.json()) as { taken?: unknown };
  return typeof found.taken === "string" ? found.taken : "";
}

/** Of the Gmail ids a scan found (in decimal), those the service holds no message for, in the order given. */
export async function missing(fetcher: Fetcher, paired: Paired, ids: readonly string[]): Promise<string[]> {
  const out: string[] = [];
  for (let start = 0; start < ids.length; start += KNOWN_PER_CALL) {
    const response = await call(fetcher, "/api/ingest/mail/known", {
      method: "POST",
      headers: { ...bearer(paired), "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids.slice(start, start + KNOWN_PER_CALL) }),
    });
    const found = (await response.json()) as { missing?: unknown };
    if (!Array.isArray(found.missing)) {
      throw new Refused(response.status, "known_answer", "servisin yanıtı anlaşılamadı");
    }
    out.push(...found.missing.filter((id): id is string => typeof id === "string"));
  }
  return out;
}

/**
 * Tell the service a scan of Gmail finished, with what it searched (as the cursor said when it began); whether the
 * history still needs a scan, as the settings may have changed meanwhile.
 */
export async function scanned(
  fetcher: Fetcher,
  paired: Paired,
  startDay: string,
  senders: readonly string[],
): Promise<boolean> {
  const response = await call(fetcher, "/api/ingest/mail/scanned", {
    method: "POST",
    headers: { ...bearer(paired), "Content-Type": "application/json" },
    body: JSON.stringify({ start_day: startDay, senders }),
  });
  const found = (await response.json()) as { history_due?: unknown };
  return found.history_due === true;
}

/**
 * Tell the service a layer stopped on a Gmail page it does not know (ADR-0016's format alarm), with what a "Show
 * original" page showed when it was one: its length, masked title and links, never its text.
 */
export async function alarm(
  fetcher: Fetcher,
  paired: Paired,
  layer: 1 | 2 | 3,
  version: string,
  page?: PageTraits,
): Promise<void> {
  const shown =
    page === undefined
      ? {}
      : { page: { length: page.length, title: page.title, download: page.download, raw_id: page.rawId } };
  await call(fetcher, "/api/ingest/mail/alarm", {
    method: "POST",
    headers: { ...bearer(paired), "Content-Type": "application/json" },
    body: JSON.stringify({ layer, version, ...shown }),
  });
}
