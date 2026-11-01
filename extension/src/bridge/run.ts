/**
 * One delivery run (ADR-0016, layers 1 and 3): the inbox feed shows the unread messages; those from a listed bank
 * that the service has not taken yet are downloaded through "Show original" and delivered raw. The service applies the
 * trust rule (DMARC) and keeps where delivery stands. Requests to Gmail go one at a time, a second apart; when Gmail
 * asks to slow down, the bridge waits longer each time. A Gmail page it does not know stops that layer and tells the
 * service once (the fix comes with an update). A message the service can never take (too large, empty) is skipped
 * and remembered; any other trouble stops the run and the next one waits longer each time. Nothing in Gmail changes:
 * GETs only.
 */

import { type FeedEntry, readFeed } from "../gmail/feed";
import { HttpError, Redirected } from "../gmail/http";
import { readOriginal } from "../gmail/original";
import { listed } from "../mail/headers";
import { type Cursor, MAX_MESSAGE_BYTES, type Paired, Refused, cursor, prove } from "./service";
import type { BridgeState, Outcome, RunSummary, Store } from "./state";
import {
  type Environment,
  LayerStopped,
  PACE_MS,
  accountKey,
  deliverOne,
  layer,
  sentence,
  serviceProblem,
  skip,
  stopLayer,
  stoppedNow,
  trouble,
} from "./steps";

export type RunEnvironment = Environment;
export { PACE_MS } from "./steps";

const FIRST_CALM_MS = 60_000;
const LONGEST_CALM_MS = 60 * 60_000;
const STOPPED = "Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi bekleniyor.";

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
  if (stoppedNow(state, env.version, 1, 3)) {
    return done("stopped", STOPPED);
  }
  let where: Cursor;
  try {
    await prove(env.service, paired);
    where = await cursor(env.service, paired);
  } catch (error) {
    const [outcome, detail] = serviceProblem(error) ?? ["failed", unexpected(error)];
    return done(outcome, detail);
  }
  await store.update({ historyDue: where.historyDue, startDay: where.startDay });
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
    if (raw.byteLength > MAX_MESSAGE_BYTES) {
      await skip(store, entry.id);
      continue;
    }
    if (await deliverOne(env, store, paired, raw, entry.id, entry.issued)) {
      delivered += 1;
    }
  }
  return delivered;
}

function unexpected(error: unknown): string {
  return `İplikçi Nedim beklenmeyen bir yanıt verdi (${trouble(error)}).`;
}

/** Whether the service has not taken the entry yet: newer than its position, and from the start day on. */
function isNew(entry: FeedEntry, where: Cursor, skipped: readonly string[]): boolean {
  if (skipped.includes(entry.id) || entry.issued.slice(0, 10) < where.startDay) {
    return false;
  }
  return entry.issued > where.lastDate || (entry.issued === where.lastDate && entry.id !== where.lastId);
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
    await stopLayer(env, store, paired, error.layer);
    return done("stopped", STOPPED);
  }
  if (error instanceof Redirected) {
    return done("gmail-signed-out", "Bu tarayıcıda seçilen Gmail hesabına girilmemiş.");
  }
  const problem = serviceProblem(error);
  if (problem !== null) {
    return done(...problem);
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
  return done("failed", `${sentence(trouble(error))}; biraz sonra yeniden denenecek.`);
}
