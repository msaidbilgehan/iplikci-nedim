/**
 * What the delivery run and the scan of Gmail share: the account key, the layers a Gmail page it does not know stops,
 * the delivery of one message, and how trouble reads in Turkish. Requests to Gmail go one at a time, a second apart.
 */

import { FormatError } from "../gmail/errors";
import { type Fetcher as GmailFetcher, HttpError } from "../gmail/http";
import { NoRawText, type Original, type PageTraits, readOriginal } from "../gmail/original";
import { readAccountKey } from "../gmail/session";
import { type Fetcher, NotTheService, type Paired, Refused, ServiceDown, alarm, deliver } from "./service";
import type { BridgeState, Outcome, Store } from "./state";

export interface Environment {
  readonly gmail: GmailFetcher;
  readonly service: Fetcher;
  readonly sleep: (ms: number) => Promise<void>;
  readonly now: () => Date;
  /** The extension's version: a layer stopped by an older one tries again. */
  readonly version: string;
}

export const PACE_MS = 1000;
const SKIPPED_KEPT = 500;
/** The service's answers for a message it can never take: retrying would only download it again. */
const UNTAKEABLE: ReadonlySet<string> = new Set(["message_too_large", "message_empty"]);
/** Whether the service no longer knows the pairing: it refuses the token, or says so when asked to prove itself. */
export function revoked(error: unknown): boolean {
  return error instanceof Refused && (error.status === 401 || error.code === "bridge_unknown");
}

export type Layer = 1 | 2 | 3;

/** A layer met a Gmail page it does not know; what a "Show original" page showed, when it was one. */
export class LayerStopped extends Error {
  constructor(
    readonly layer: Layer,
    readonly page?: PageTraits,
  ) {
    super(`layer ${layer} met a page it does not know`);
  }
}

/** read, with a format error turned into the stop of its layer. */
export async function layer<T>(which: Layer, read: () => Promise<T>): Promise<T> {
  try {
    return await read();
  } catch (error) {
    throw error instanceof FormatError ? new LayerStopped(which) : error;
  }
}

/** Whether one of the layers is stopped for this version of the extension. */
export function stoppedNow(state: BridgeState, version: string, ...layers: Layer[]): boolean {
  return layers.some((which) => state.stopped[String(which)] === version);
}

/**
 * Whether a check asked for by hand, or the first after pairing, scans Gmail rather than reading the inbox feed: the
 * service lacks the history (the scan delivers the new messages too), and the scan's layers can run.
 */
export function scansFirst(state: BridgeState, version: string): boolean {
  return state.paired !== null && state.historyDue && !stoppedNow(state, version, 2, 3);
}

/** Stop a layer for this version and tell the service once; the stop holds even when the service does not hear. */
export async function stopLayer(env: Environment, store: Store, paired: Paired, stop: LayerStopped): Promise<void> {
  await store.update({ stopped: { ...(await store.get()).stopped, [String(stop.layer)]: env.version } });
  try {
    await alarm(env.service, paired, stop.layer, env.version, stop.page);
  } catch {
    // the service hears of it at the next stop: the stop is kept here
  }
}

/** Messages in a row whose "Show original" page may show no raw text before the page counts as changed. */
const UNSHOWN_IN_A_ROW = 3;
/** The wait after such a page: Gmail may be busy, and the next request comes later. */
export const UNSHOWN_WAIT_MS = 10_000;

/**
 * The messages whose "Show original" page showed no raw text. One such message among shown ones is that message's
 * own trouble (Gmail does not show a message too large, it may be): it is skipped, counted and left for the user to
 * download from Gmail. Several in a row mean the page changed: the layer stops, and those messages are tried again
 * by the version that fixes it.
 */
export class Unshown {
  private streak: string[] = [];
  /** The messages skipped so far. */
  count = 0;

  constructor(
    private readonly env: Environment,
    private readonly store: Store,
  ) {}

  /** The message's original, or null when its page showed no raw text (LayerStopped after too many in a row). */
  async read(account: number, id: string, ik: string | null): Promise<Original | null> {
    try {
      const original = await readOriginal(this.env.gmail, account, id, ik);
      await this.settle();
      return original;
    } catch (error) {
      if (!(error instanceof NoRawText)) {
        throw error instanceof FormatError ? new LayerStopped(3) : error;
      }
      this.streak.push(id);
      if (this.streak.length >= UNSHOWN_IN_A_ROW) {
        throw new LayerStopped(3, error.traits);
      }
      await this.env.sleep(UNSHOWN_WAIT_MS);
      return null;
    }
  }

  /** The run is over, or a message was shown: the messages not shown before are judged to be their own trouble. */
  async settle(): Promise<void> {
    for (const id of this.streak) {
      await skip(this.store, id);
    }
    this.count += this.streak.length;
    this.streak = [];
  }
}

/** What a run or a scan says of the messages Gmail did not show; "" for none. */
export function unshownSentence(count: number): string {
  if (count === 0) {
    return "";
  }
  return (
    ` Gmail ${count} iletinin aslını göstermedi (büyük ekli olabilir): eklerini Gmail'den indirip İplikçi Nedim'e ` +
    "yükleyebilirsiniz."
  );
}

/** The account key for Gmail's links: kept, else read once from the Gmail page; null when the page has none. */
export async function accountKey(env: Environment, store: Store, account: number): Promise<string | null> {
  const kept = (await store.get()).keys[String(account)];
  if (kept !== undefined) {
    return kept;
  }
  const found = await readAccountKey(env.gmail, account);
  await env.sleep(PACE_MS);
  if (found === null) {
    return null;
  }
  await store.update({ keys: { ...(await store.get()).keys, [String(account)]: found.ik } });
  return found.ik;
}

/**
 * Deliver one message; false when the service can never take it (too large, empty), so it is skipped and remembered
 * rather than downloaded again. gmailDate "" leaves the service's cursor where it is.
 */
export async function deliverOne(
  env: Environment,
  store: Store,
  paired: Paired,
  raw: Uint8Array<ArrayBuffer>,
  gmailId: string,
  gmailDate: string,
): Promise<boolean> {
  try {
    await deliver(env.service, paired, raw, gmailId, gmailDate);
    return true;
  } catch (error) {
    if (!(error instanceof Refused && UNTAKEABLE.has(error.code))) {
      throw error;
    }
  }
  await skip(store, gmailId);
  return false;
}

/** Remember a message the service can never take, so it is not downloaded again and again. */
export async function skip(store: Store, gmailId: string): Promise<void> {
  await store.update({ skipped: [...(await store.get()).skipped, gmailId].slice(-SKIPPED_KEPT) });
}

/** How a service error reads, with its outcome; null when the error is not the service's. */
export function serviceProblem(error: unknown): [Outcome, string] | null {
  if (error instanceof ServiceDown) {
    return ["service-down", "İplikçi Nedim bu bilgisayarda çalışmıyor; açılınca iletiler alınır."];
  }
  if (error instanceof NotTheService) {
    return [
      "not-the-service",
      "Bu bilgisayarda eşleşilen İplikçi Nedim yerine başka bir program yanıt veriyor; ileti gönderilmedi.",
    ];
  }
  if (revoked(error)) {
    return ["revoked", "Eşleşme İplikçi Nedim'de iptal edilmiş; yeniden eşleştirin."];
  }
  if (error instanceof Refused && error.status === 404) {
    return ["failed", "İplikçi Nedim bu eklentiden eski bir sürüm: bu iş için onu güncelleyin."];
  }
  return null;
}

/** What went wrong, in Turkish and without a closing period; never an address, subject or message text. */
export function trouble(error: unknown): string {
  if (error instanceof HttpError || error instanceof Refused) {
    return error.message.replace(/\.$/, "");
  }
  if (error instanceof TypeError) {
    return "Gmail'e ulaşılamadı (ağ bağlantısı ya da tarayıcı izni)";
  }
  return `beklenmeyen hata: ${error instanceof Error ? error.name : typeof error}`;
}

/** text with its first letter capitalised, as Turkish writes it. */
export function sentence(text: string): string {
  return `${text.charAt(0).toLocaleUpperCase("tr-TR")}${text.slice(1)}`;
}
