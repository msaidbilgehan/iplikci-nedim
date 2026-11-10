/**
 * The bank messages an open Gmail tab shows (ADR-0016, note of 2026-11-10), on the service worker's side. The content
 * script (content.ts) names them while its tab shows the Gmail account the bridge reads; their ids wait in the stored
 * state for the next delivery run. The run reads the inbox feed first, so an unread message the feed lists keeps its
 * date (the service's cursor moves only with dated deliveries); then it asks the service which of the waiting ids it
 * lacks, and those come through "Show original" (layer 3) like the feed's, oldest first, a second apart. They carry
 * no date, as the scan's deliveries do: the cursor stays where it is.
 */

import type { Watch } from "../gmail/visible";
import { MAX_MESSAGE_BYTES, type Paired, missing } from "./service";
import type { BridgeState, Store } from "./state";
import {
  type Environment,
  type Originals,
  PACE_MS,
  accountKey,
  deliverOne,
  oldestFirst,
  remember,
  skip,
  stoppedNow,
} from "./steps";

/** Ids waiting at most; the newest are kept: older messages are the scan's to find. */
const SEEN_KEPT = 1000;

/**
 * What a Gmail tab showing `account` looks for: the senders, while the bridge takes messages from that tab. Null when
 * it takes none: unpaired, another account, no senders heard of yet, or Gmail's list or "Show original" (layers 2
 * and 3) stopped for this version.
 */
export function watchFor(state: BridgeState, version: string, account: number): Watch | null {
  if (state.paired === null || account !== state.account || state.senders.length === 0) {
    return null;
  }
  return stoppedNow(state, version, 2, 3) ? null : { senders: state.senders };
}

/** Of the ids a Gmail tab names, those the bridge has not dealt with: not known, not skipped, not waiting already. */
export function unhandled(state: BridgeState, ids: readonly string[]): string[] {
  const dealt = new Set([...state.known, ...state.skipped, ...state.seen]);
  return [...new Set(ids)].filter((id) => !dealt.has(id));
}

/** Keep the ids for the run; nothing while unpaired. */
export async function keep(store: Store, ids: readonly string[]): Promise<void> {
  await store.update((state) => {
    const fresh = state.paired === null ? [] : unhandled(state, ids);
    return fresh.length === 0 ? {} : { seen: [...state.seen, ...fresh].slice(-SEEN_KEPT) };
  });
}

/** Take ids off the waiting list. */
async function drop(store: Store, ids: Iterable<string>): Promise<void> {
  const gone = new Set(ids);
  await store.update((state) => ({ seen: state.seen.filter((id) => !gone.has(id)) }));
}

/**
 * The run's step for the waiting ids: those the service lacks are downloaded and delivered; how many were. An id the
 * service holds is known from then on. A message Gmail shows no original for stays waiting until the run settles it
 * (skipped), or for the version that knows the page when the layer stops.
 */
export async function deliverSeen(
  env: Environment,
  store: Store,
  paired: Paired,
  account: number,
  originals: Originals,
): Promise<number> {
  const state = await store.get();
  const dealt = new Set([...state.known, ...state.skipped]);
  const waiting = state.seen.filter((id) => !dealt.has(id));
  const lacking = new Set(waiting.length === 0 ? [] : await missing(env.service, paired, waiting));
  const wanted = new Set(waiting.filter((id) => lacking.has(id))); // what a Gmail tab named, nothing else
  await remember(store, waiting.filter((id) => !wanted.has(id))); // held already, or refused under these settings
  await drop(store, state.seen.filter((id) => !wanted.has(id)));
  let delivered = 0;
  for (const id of oldestFirst(wanted)) {
    await env.sleep(PACE_MS);
    const ik = await accountKey(env, store, account);
    const raw = await originals.read(account, id, ik);
    if (raw === null) {
      continue;
    }
    if (raw.byteLength > MAX_MESSAGE_BYTES) {
      await skip(store, id);
    } else if (await deliverOne(env, store, paired, raw, id, "")) {
      delivered += 1;
    }
    await drop(store, [id]);
  }
  return delivered;
}
