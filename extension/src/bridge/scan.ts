/**
 * "Gmail'de eksikleri tara", ADR-0016's way for the history and for missed mail when the full scan (layer 2) does not
 * answer. A tab opens Gmail's search for the listed banks' messages from the start day on; the collector reads the
 * conversations page by page and the tab closes. The list names a conversation's first and last message; for one it
 * shows read throughout, the print view names the messages in between that have attachments. The service says which
 * of the messages it lacks; those are downloaded through "Show original" (layer 3) and delivered, oldest first, a
 * second apart. Nothing in Gmail changes: no conversation is opened, and the print view of one with an unread message
 * is never asked for, so nothing is marked read. Where the scan stands is kept for the extension's window; a scan cut
 * short goes on from what the service holds when it is started again. A finished scan tells the service what it
 * searched: the history is scanned again only when the start day or the senders change.
 */

import { FormatError } from "../gmail/errors";
import { HttpError, Redirected } from "../gmail/http";
import { type Conversation, type ListPage, searchHash, searchQuery, searchUrl } from "../gmail/list";
import { type PrintedMessage, readPrint } from "../gmail/print";
import { decimalId } from "../gmail/search";
import { listed } from "../mail/headers";
import { type Cursor, MAX_MESSAGE_BYTES, type Paired, cursor, missing, prove, scanned } from "./service";
import type { ScanSummary, Store } from "./state";
import {
  type Environment,
  LayerStopped,
  PACE_MS,
  Originals,
  accountKey,
  deliverOne,
  layer,
  sentence,
  serviceProblem,
  skip,
  stopLayer,
  stoppedNow,
  trouble,
  unshownSentence,
} from "./steps";

/** The browser tab the scan reads Gmail's search in. */
export interface TabDriver {
  /** Open a tab at url and wait until it has loaded; the tab's id. */
  open(url: string): Promise<number>;
  /** Read the tab's conversation list once it moved on from `before` (collectList). */
  collect(tab: number, waitMs: number, before: string): Promise<ListPage>;
  /** Show another page of the search. */
  go(tab: number, hash: string): Promise<void>;
  close(tab: number): Promise<void>;
}

/** The tab left Gmail: the chosen account is signed out and Gmail sent the tab to the sign-in page. */
export class NotGmail extends Error {
  override name = "NotGmail";
}

/** The tab was closed during the scan. */
export class TabGone extends Error {
  override name = "TabGone";
}

/** The tab shows no page the collector can read: Gmail did not load (no network, an error page). */
export class TabUnreadable extends Error {
  override name = "TabUnreadable";
}

export interface ScanEnvironment extends Environment {
  readonly tabs: TabDriver;
}

const MAX_PAGES = 200;
const FIRST_WAIT_MS = 45_000; // Gmail's app loads before it shows the first list
const PAGE_WAIT_MS = 15_000;
const CALM_MS = 60_000;
const STOPPED = "Gmail'in bir sayfası tanınmadı; eklentinin güncellenmesi bekleniyor.";

type Report = (patch: Partial<ScanSummary>) => Promise<ScanSummary>;

/** Scan Gmail for the messages the service lacks and deliver them; where it ended. */
export async function scanGmail(env: ScanEnvironment, store: Store): Promise<ScanSummary> {
  let summary: ScanSummary = {
    at: env.now().toISOString(),
    phase: "searching",
    pages: 0,
    conversations: 0,
    found: 0,
    missing: 0,
    delivered: 0,
    unshown: 0,
    between: 0,
    betweenUnread: 0,
    detail: "Gmail'de aranıyor…",
  };
  const report: Report = async (patch) => {
    summary = { ...summary, ...patch };
    await store.update({ scan: summary });
    return summary;
  };
  const stop = (detail: string): Promise<ScanSummary> => report({ phase: "stopped", detail });
  await report({});
  const state = await store.get();
  const paired = state.paired;
  if (paired === null) {
    return stop("Önce eklentiyi İplikçi Nedim ile eşleştirin.");
  }
  if (stoppedNow(state, env.version, 2, 3)) {
    return stop(STOPPED);
  }
  let where: Cursor;
  try {
    await prove(env.service, paired);
    where = await cursor(env.service, paired);
  } catch (error) {
    return stop(serviceProblem(error)?.[1] ?? `İplikçi Nedim beklenmeyen bir yanıt verdi (${trouble(error)}).`);
  }
  await store.update({ historyDue: where.historyDue, startDay: where.startDay });
  if (where.senders.length === 0) {
    return stop("İplikçi Nedim'deki banka göndericisi listesi boş.");
  }
  try {
    const found = await search(env, report, state.account, searchQuery(where.senders, where.startDay));
    const inside = await middles(env, store, report, state.account, found, where.senders);
    const ids = messageIds(found, inside.ids);
    const lacking = (await missing(env.service, paired, ids)).filter((id) => !state.skipped.includes(id));
    const conversations = [...found.values()];
    await report({
      phase: "downloading",
      found: ids.length,
      missing: lacking.length,
      between: Math.max(0, between(conversations) - inside.named),
      betweenUnread: between(conversations.filter((c) => !c.read)),
      detail: lacking.length === 0 ? "Eksik ileti yok." : `${lacking.length} eksik ileti indiriliyor…`,
    });
    await download(env, store, report, paired, state.account, lacking);
    // A service that cannot record it now, or knows no such record, leaves the history as its cursor said.
    const due = await scanned(env.service, paired, where.startDay, where.senders).catch(() => where.historyDue);
    await store.update({ historyDue: due });
    return report({ phase: "done", detail: finished(summary) });
  } catch (error) {
    return scanTrouble(env, store, paired, error, stop);
  }
}

async function search(
  env: ScanEnvironment,
  report: Report,
  account: number,
  query: string,
): Promise<Map<string, Conversation>> {
  const found = new Map<string, Conversation>();
  const tab = await env.tabs.open(searchUrl(account, query));
  let first: ListPage | null = null;
  try {
    let before = "";
    let shown = 0;
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      if (page > 1) {
        await env.tabs.go(tab, searchHash(query, page));
      }
      const list = await layer(2, () => env.tabs.collect(tab, page === 1 ? FIRST_WAIT_MS : PAGE_WAIT_MS, before));
      first ??= list;
      if (list.unknownRows > 0 && list.conversations.length === 0) {
        throw new LayerStopped(2);
      }
      const fresh = list.conversations.filter((c) => !found.has(c.thread));
      if (fresh.length === 0) {
        break; // the page did not move on: the search has no more pages
      }
      for (const c of fresh) {
        found.set(c.thread, c);
      }
      await report({ pages: page, conversations: found.size, detail: `Gmail'de aranıyor: ${found.size} konuşma…` });
      if (page > 1 && list.conversations.length < shown) {
        break; // a page shorter than the one before is the last
      }
      before = list.conversations[0]?.thread ?? "";
      shown = list.conversations.length;
    }
  } finally {
    await env.tabs.close(tab).catch(() => undefined); // closed by the user already
  }
  if (found.size === 0 && first !== null && !first.main) {
    throw new TabUnreadable("Gmail'in sayfasında ana bölüm yok"); // Gmail did not come up, or its page changed
  }
  if (found.size === 0 && first !== null && first.rows > 0) {
    throw new NothingRecognised(first.rows);
  }
  return found;
}

/** Gmail showed rows, none of them a conversation's: an empty search shows none, so its page may have changed. */
class NothingRecognised extends Error {
  constructor(readonly rows: number) {
    super(`no conversation among ${rows} rows`);
  }
}

async function download(
  env: ScanEnvironment,
  store: Store,
  report: Report,
  paired: Paired,
  account: number,
  lacking: readonly string[],
): Promise<void> {
  const originals = new Originals(env, store);
  let delivered = 0;
  for (const id of lacking) {
    await env.sleep(PACE_MS);
    const ik = await accountKey(env, store, account);
    const raw = await originals.read(account, id, ik);
    if (raw === null) {
      continue;
    }
    if (raw.byteLength > MAX_MESSAGE_BYTES) {
      await skip(store, id);
      continue;
    }
    if (await deliverOne(env, store, paired, raw, id, "")) {
      delivered += 1;
      await report({ delivered, detail: `${delivered}/${lacking.length} ileti teslim edildi…` });
    }
  }
  await originals.settle();
  await report({ unshown: originals.unshown });
}

/**
 * The messages in the middle of the conversations the list shows read throughout, from each one's print view: the
 * ids (decimal) of those with an attachment from a listed sender, and how many messages in the middle it named in
 * all. A print view Gmail shows otherwise than the scan knows leaves the rest of the middles out of reach.
 */
async function middles(
  env: ScanEnvironment,
  store: Store,
  report: Report,
  account: number,
  found: ReadonlyMap<string, Conversation>,
  senders: readonly string[],
): Promise<{ ids: string[]; named: number }> {
  const ids: string[] = [];
  let named = 0;
  const read = [...found.values()].filter((c) => c.read && between([c]) > 0);
  if (read.length > 0) {
    await report({ detail: "Konuşmaların ortasındaki iletilere bakılıyor…" });
  }
  for (const c of read) {
    await env.sleep(PACE_MS);
    const ik = await accountKey(env, store, account);
    let printed: PrintedMessage[];
    try {
      printed = await readPrint(env.gmail, account, c.thread, ik);
    } catch (error) {
      if (error instanceof FormatError) {
        break;
      }
      throw error;
    }
    for (const m of printed.filter((p) => p.id !== c.thread && p.id !== c.last)) {
      named += 1;
      if (listed(m.senderDomain, senders)) {
        ids.push(decimalId(m.id));
      }
    }
  }
  return { ids, named };
}

/**
 * The messages the scan names, in decimal and oldest first (Gmail's ids grow with time): each conversation's first
 * message, which carries the conversation's id, its last, and those in the middle its print view named.
 */
function messageIds(found: ReadonlyMap<string, Conversation>, inside: readonly string[]): string[] {
  const ids = new Set<string>(inside);
  for (const c of found.values()) {
    ids.add(decimalId(c.thread));
    ids.add(decimalId(c.last));
  }
  return [...ids].sort((a, b) => (BigInt(a) < BigInt(b) ? -1 : BigInt(a) > BigInt(b) ? 1 : 0));
}

/** The messages between the conversations' first and last that the list does not name, where it shows a count. */
function between(conversations: readonly Conversation[]): number {
  let count = 0;
  for (const c of conversations) {
    count += Math.max(0, c.count - (c.thread === c.last ? 1 : 2));
  }
  return count;
}

function finished(summary: ScanSummary): string {
  if (summary.found === 0) {
    return "Gmail'in aramasında listedeki bankalardan ileti çıkmadı.";
  }
  const found = `Gmail'de listedeki bankalardan ${summary.found} ileti bulundu`;
  const result =
    summary.missing === 0
      ? `${found}; hepsi İplikçi Nedim'de.`
      : `${found}; eksik ${summary.missing} iletiden ${summary.delivered} tanesi teslim edildi.`;
  return `${result}${unshownSentence(summary.unshown)}${betweenSentence(summary.between, summary.betweenUnread)}`;
}

/** The messages in the middle of conversations the scan could not name, and why. */
function betweenSentence(between: number, unread: number): string {
  const unnamed = between - unread;
  const inRead =
    unnamed > 0
      ? ` Konuşmaların ortasındaki ${unnamed} ileti alınamadı: Gmail, eki olmayan iletilerin kimliğini konuşma ` +
        "açılmadan göstermiyor."
      : "";
  const inUnread =
    unread > 0
      ? ` Okunmamış konuşmaların ortasındaki ${unread} ileti alınamadı: konuşmayı açmak iletilerini okundu yapar. ` +
        "Gmail'de okuduğunuz konuşmaların ekli iletileri sonraki taramada alınır."
      : "";
  return `${inRead}${inUnread}`;
}

async function scanTrouble(
  env: ScanEnvironment,
  store: Store,
  paired: Paired,
  error: unknown,
  stop: (detail: string) => Promise<ScanSummary>,
): Promise<ScanSummary> {
  if (error instanceof LayerStopped) {
    await stopLayer(env, store, paired, error);
    return stop(STOPPED);
  }
  if (error instanceof Redirected || error instanceof NotGmail) {
    return stop("Bu tarayıcıda seçilen Gmail hesabına girilmemiş; Gmail'e girip taramayı yeniden başlatın.");
  }
  if (error instanceof TabGone) {
    return stop("Tarama sekmesi kapatıldı; tarama durdu. Yeniden başlatılabilir.");
  }
  if (error instanceof NothingRecognised) {
    return stop(
      `Gmail'in arama sayfasında ${error.rows} satır vardı ama hiçbiri bir konuşma gibi okunamadı; ` +
        "eklentinin güncellenmesi gerekebilir.",
    );
  }
  if (error instanceof TabUnreadable) {
    return stop("Gmail sekmede açılamadı (ağ bağlantısı olmayabilir); tarama durdu, yeniden başlatılabilir.");
  }
  const problem = serviceProblem(error);
  if (problem !== null) {
    return stop(problem[1]);
  }
  if (error instanceof HttpError && error.status === 429) {
    await store.update({ calmUntil: env.now().getTime() + CALM_MS }); // the feed's runs wait too
    return stop("Gmail yavaşlamayı istedi; taramayı biraz sonra yeniden başlatın, eksikler kaldığı yerden alınır.");
  }
  return stop(`${sentence(trouble(error))}; tarama durdu, yeniden başlatılabilir.`);
}
