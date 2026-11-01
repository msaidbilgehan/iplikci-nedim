/**
 * One delivery run (ADR-0016, layers 1 and 3): the inbox feed shows the unread messages; those from a listed bank
 * that the service has not taken yet are downloaded through "Show original" and delivered raw. The service applies the
 * trust rule (DMARC) and keeps where delivery stands. Requests to Gmail go one at a time, a second apart; when Gmail
 * asks to slow down, the bridge waits longer each time. A Gmail page it does not know stops that layer and tells the
 * service once (the fix comes with an update). A message the service can never take (too large, empty) is skipped
 * and remembered; any other trouble stops the run and the next one waits longer each time. Nothing in Gmail changes:
 * GETs only.
 */

import { FormatError } from "../gmail/errors";
import { type FeedEntry, readFeed } from "../gmail/feed";
import { type Fetcher as GmailFetcher, HttpError, Redirected } from "../gmail/http";
import { readOriginal } from "../gmail/original";
import { readAccountKey } from "../gmail/session";
import { listed } from "../mail/headers";
import {
  type Cursor,
  type Fetcher,
  MAX_MESSAGE_BYTES,
  NotTheService,
  type Paired,
  Refused,
  ServiceDown,
  alarm,
  cursor,
  deliver,
  prove,
} from "./service";
import type { BridgeState, Outcome, RunSummary, Store } from "./state";

export interface RunEnvironment {
  readonly gmail: GmailFetcher;
  readonly service: Fetcher;
  readonly sleep: (ms: number) => Promise<void>;
  readonly now: () => Date;
  /** The extension's version: a layer stopped by an older one tries again. */
  readonly version: string;
}

export const PACE_MS = 1000;
const FIRST_CALM_MS = 60_000;
const LONGEST_CALM_MS = 60 * 60_000;
const SKIPPED_KEPT = 50;
/** The service's answers for a message it can never take: retrying would only download it again. */
const UNTAKEABLE: ReadonlySet<string> = new Set(["message_too_large", "message_empty"]);
/** The service's answers for a pairing it no longer knows. */
const GONE: ReadonlySet<number> = new Set([401, 404]);

/**
 * Run once: deliver the new bank messages of the inbox; what happened, kept for the extension's window. While the
 * bridge waits after a trouble, nothing is asked of Gmail or the service and the last run's summary stands.
 */
export async function deliverNew(env: RunEnvironment, store: Store): Promise<RunSummary> {
  const state = await store.get();
  if (state.paired !== null && state.lastRun !== null && env.now().getTime() < state.calmUntil) {
    return state.lastRun;
  }
  const summary = await attempt(env, store, state);
  await store.update({ lastRun: summary });
  return summary;
}

async function attempt(env: RunEnvironment, store: Store, state: BridgeState): Promise<RunSummary> {
  const done = (outcome: Outcome, detail: string, delivered = 0): RunSummary => ({
    at: env.now().toISOString(),
    outcome,
    delivered,
    detail,
  });
  const paired = state.paired;
  if (paired === null) {
    return done("unpaired", "Eklenti henüz İplikçi Nedim ile eşleşmedi.");
  }
  if (state.stopped["1"] === env.version || state.stopped["3"] === env.version) {
    return done("stopped", "Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi bekleniyor.");
  }
  let where: Cursor;
  try {
    await prove(env.service, paired);
    where = await cursor(env.service, paired);
  } catch (error) {
    return serviceTrouble(error, done);
  }
  try {
    const delivered = await deliverFresh(env, store, state, paired, where);
    await store.update({ calmUntil: 0, failures: 0 });
    return delivered === 0
      ? done("nothing-new", "Yeni banka iletisi yok.")
      : done("delivered", `${delivered} yeni ileti İplikçi Nedim'e teslim edildi.`, delivered);
  } catch (error) {
    return gmailTrouble(env, store, state, paired, error, done);
  }
}

async function deliverFresh(
  env: RunEnvironment,
  store: Store,
  state: BridgeState,
  paired: Paired,
  where: Cursor,
): Promise<number> {
  const feed = await layer(1, () => readFeed(env.gmail, state.account));
  const fresh = feed.entries
    .filter((entry) => listed(entry.senderDomain, where.senders) && isNew(entry, where, state.skipped))
    .sort((a, b) => a.issued.localeCompare(b.issued)); // oldest first: the service's position only moves forward
  let delivered = 0;
  for (const entry of fresh) {
    await env.sleep(PACE_MS);
    const ik = await accountKey(env, store, state.account);
    const original = await layer(3, () => readOriginal(env.gmail, state.account, entry.id, ik));
    const raw = new TextEncoder().encode(original.raw);
    if (raw.byteLength > MAX_MESSAGE_BYTES || !(await take(env, paired, raw, entry))) {
      const skipped = [...(await store.get()).skipped, entry.id].slice(-SKIPPED_KEPT);
      await store.update({ skipped });
      continue;
    }
    delivered += 1;
  }
  return delivered;
}

/** Deliver one message; false when the service can never take it, so it is skipped rather than tried again. */
async function take(
  env: RunEnvironment,
  paired: Paired,
  raw: Uint8Array<ArrayBuffer>,
  entry: FeedEntry,
): Promise<boolean> {
  try {
    await deliver(env.service, paired, raw, entry.id, entry.issued);
    return true;
  } catch (error) {
    if (error instanceof Refused && UNTAKEABLE.has(error.code)) {
      return false;
    }
    throw error;
  }
}

/** Whether the service has not taken the entry yet: newer than its position, and from the start day on. */
function isNew(entry: FeedEntry, where: Cursor, skipped: readonly string[]): boolean {
  if (skipped.includes(entry.id) || entry.issued.slice(0, 10) < where.startDay) {
    return false;
  }
  return entry.issued > where.lastDate || (entry.issued === where.lastDate && entry.id !== where.lastId);
}

/** The account key for Gmail's links: kept, else read once from the Gmail page; null when the page has none. */
async function accountKey(env: RunEnvironment, store: Store, account: number): Promise<string | null> {
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

class LayerStopped extends Error {
  constructor(readonly layer: 1 | 3) {
    super(`layer ${layer} met a page it does not know`);
  }
}

async function layer<T>(which: 1 | 3, read: () => Promise<T>): Promise<T> {
  try {
    return await read();
  } catch (error) {
    throw error instanceof FormatError ? new LayerStopped(which) : error;
  }
}

function serviceTrouble(error: unknown, done: (o: Outcome, d: string) => RunSummary): RunSummary {
  if (error instanceof ServiceDown) {
    return done("service-down", "İplikçi Nedim bu bilgisayarda çalışmıyor; açılınca iletiler alınır.");
  }
  if (error instanceof NotTheService) {
    return done("not-the-service", "Bu bilgisayarda eşleşilen İplikçi Nedim yerine başka bir program yanıt veriyor; ileti gönderilmedi.");
  }
  if (error instanceof Refused && GONE.has(error.status)) {
    return done("revoked", "Eşleşme İplikçi Nedim'de iptal edilmiş; yeniden eşleştirin.");
  }
  return done("failed", `İplikçi Nedim beklenmeyen bir yanıt verdi (${trouble(error)}).`);
}

async function gmailTrouble(
  env: RunEnvironment,
  store: Store,
  state: BridgeState,
  paired: Paired,
  error: unknown,
  done: (o: Outcome, d: string) => RunSummary,
): Promise<RunSummary> {
  if (error instanceof LayerStopped) {
    await store.update({ stopped: { ...state.stopped, [String(error.layer)]: env.version } });
    try {
      await alarm(env.service, paired, error.layer, env.version);
    } catch {
      // the service hears of it at the next run: the stop is kept here
    }
    return done("stopped", "Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi bekleniyor.");
  }
  if (error instanceof Redirected) {
    return done("gmail-signed-out", "Bu tarayıcıda seçilen Gmail hesabına girilmemiş.");
  }
  if (error instanceof ServiceDown || (error instanceof Refused && GONE.has(error.status))) {
    return serviceTrouble(error, done);
  }
  const failures = state.failures + 1;
  const calm = Math.min(FIRST_CALM_MS * 2 ** (failures - 1), LONGEST_CALM_MS);
  await store.update({ failures, calmUntil: env.now().getTime() + calm });
  if (error instanceof HttpError && error.status === 429) {
    return done("gmail-busy", "Gmail yavaşlamayı istedi; biraz sonra yeniden denenecek.");
  }
  if (error instanceof Refused) {
    return done("failed", `İplikçi Nedim bir iletiyi almadı (${trouble(error)}); biraz sonra yeniden denenecek.`);
  }
  const what = trouble(error);
  return done("failed", `${what.charAt(0).toLocaleUpperCase("tr-TR")}${what.slice(1)}; biraz sonra yeniden denenecek.`);
}

/** What went wrong, in Turkish and without a closing period; never an address, subject or message text. */
function trouble(error: unknown): string {
  if (error instanceof HttpError || error instanceof Refused) {
    return error.message.replace(/\.$/, "");
  }
  if (error instanceof TypeError) {
    return "Gmail'e ulaşılamadı (ağ bağlantısı ya da tarayıcı izni)";
  }
  return `beklenmeyen hata: ${error instanceof Error ? error.name : typeof error}`;
}
