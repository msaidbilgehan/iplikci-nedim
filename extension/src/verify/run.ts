/**
 * The ADR-0016 verification, run in the extension's service worker. Can the bridge
 *   1. read the inbox feed with the browser's Gmail session and get message ids,
 *   2. download a bank message's raw text, whose topmost Authentication-Results shows DMARC pass, while the message
 *      stays unread,
 *   3. find an old, read and archived bank message with a full search,
 *   4. and on which platform did it run?
 * The report holds no address, subject or message text: the user copies it into the chat.
 */

import { FormatError } from "../gmail/errors";
import { type Feed, readFeed, sameMessage } from "../gmail/feed";
import { type Fetcher, HttpError, Redirected, get } from "../gmail/http";
import { type Original, readOriginal } from "../gmail/original";
import { answerKind, decimalId, senderQuery, threadIds, threadListUrl } from "../gmail/search";
import { type AccountKey, readAccountKey } from "../gmail/session";
import { headers, listed, looksLikeMessage, senderDomain, topAuthentication, verifiedByGmail } from "../mail/headers";
import { BANK_SENDERS } from "./senders";

export interface Check {
  readonly title: string;
  /** null: the check could not be tried. */
  readonly ok: boolean | null;
  readonly lines: readonly string[];
}

export interface Report {
  readonly checks: readonly Check[];
  readonly text: string;
}

export interface Environment {
  readonly fetcher: Fetcher;
  readonly sleep: (ms: number) => Promise<void>;
  /** The operating system as `chrome.runtime.getPlatformInfo` names it: "mac", "win", "linux", … */
  readonly os: string;
  readonly browser: string;
  /** The extension's version. */
  readonly version: string;
  readonly now: () => Date;
}

/** ADR-0016: requests go one at a time, a second apart, so that Google's abuse protection is never woken. */
export const PACE_MS = 1000;
/** How long to wait before looking whether the downloaded message is still unread. */
export const SETTLE_MS = 3000;

export const TITLES = {
  feed: "1. Gelen kutusu akışı (yeni iletiler)",
  original: "2. Ham ileti ve DMARC; ileti okunmamış kalmalı",
  search: "3. Tam tarama (okunmuş ve arşivlenmiş eski iletiler)",
  platform: "4. Platform",
} as const;

const NO_UNREAD =
  'Gelen kutusunda okunmamış ileti yok. Gmail\'de bir banka iletisini seçip "Okunmadı olarak işaretle" deyin ve ' +
  "yeniden deneyin.";
const OS_NAMES: Readonly<Record<string, string>> = { mac: "macOS", win: "Windows", linux: "Linux", cros: "ChromeOS" };
const ANSWER_NAMES = { json: "veri yanıtı", html: "HTML sayfası", other: "tanınmayan yanıt" } as const;

export async function verify(env: Environment, account: number): Promise<Report> {
  const { check: feedCheck, feed } = await checkFeed(env, account);
  await env.sleep(PACE_MS);
  const key = await readKey(env, account);
  const checks = [
    feedCheck,
    await checkOriginal(env, account, feed, key),
    await checkSearch(env, account, key.found),
    checkPlatform(env),
  ];
  return { checks, text: reportText(env, account, checks) };
}

async function checkFeed(env: Environment, account: number): Promise<{ check: Check; feed: Feed | null }> {
  let feed: Feed;
  try {
    feed = await readFeed(env.fetcher, account);
  } catch (error) {
    return { check: { title: TITLES.feed, ok: false, lines: [`Akış okunamadı: ${failure(error)}`] }, feed: null };
  }
  const banks = feed.entries.filter((entry) => listed(entry.senderDomain, BANK_SENDERS)).length;
  const lines = [
    `Akış oturumla okundu: kutuda ${feed.unread} okunmamış ileti var, akış ${feed.entries.length} tanesini listeliyor.`,
  ];
  if (feed.entries.length === 0) {
    return { check: { title: TITLES.feed, ok: null, lines: [...lines, NO_UNREAD] }, feed };
  }
  lines.push(`Listelenenlerden ${banks} tanesi listedeki bir bankadan.`);
  lines.push(
    feed.entries.every(sameMessage)
      ? "İleti kimlikleri alındı; ondalık ve onaltılık kimlikler aynı iletiyi gösteriyor."
      : "İleti kimlikleri alındı; bazılarının onaltılık kimliği yok ya da ondalık kimlikle uyuşmuyor.",
  );
  return { check: { title: TITLES.feed, ok: true, lines }, feed };
}

async function readKey(env: Environment, account: number): Promise<{ found: AccountKey | null; line: string }> {
  try {
    const found = await readAccountKey(env.fetcher, account);
    return {
      found,
      line: found
        ? `Hesap anahtarı (ik) Gmail sayfasında bulundu (${found.where}).`
        : "Hesap anahtarı (ik) Gmail sayfasında bulunamadı.",
    };
  } catch (error) {
    return { found: null, line: `Gmail sayfası açılamadı: ${failure(error)}` };
  }
}

async function checkOriginal(
  env: Environment,
  account: number,
  feed: Feed | null,
  key: { found: AccountKey | null; line: string },
): Promise<Check> {
  const lines = [key.line];
  const bank = feed?.entries.find((entry) => listed(entry.senderDomain, BANK_SENDERS));
  const target = bank ?? feed?.entries[0];
  if (feed === null) {
    return { title: TITLES.original, ok: null, lines: [...lines, "Akış okunamadığı için denenemedi."] };
  }
  if (target === undefined) {
    return { title: TITLES.original, ok: null, lines: [...lines, NO_UNREAD] };
  }
  if (bank === undefined) {
    lines.push("Okunmamış banka iletisi yok; deneme en yeni okunmamış iletiyle yapıldı.");
  }
  await env.sleep(PACE_MS);
  let original: Original;
  try {
    original = await readOriginal(env.fetcher, account, target.id, key.found?.ik ?? null);
  } catch (error) {
    lines.push(`"Orijinali göster" sayfası alınamadı: ${failure(error)}`);
    return { title: TITLES.original, ok: false, lines };
  }
  const fields = headers(original.raw);
  const isMessage = looksLikeMessage(original.raw);
  lines.push(`"Orijinali göster" sayfası alındı (${kb(original.pageBytes)}); iletinin metni ${kb(original.raw.length)}.`);
  lines.push(isMessage ? "Metin başlıklarıyla birlikte bir e-posta iletisi." : "Metin bir e-posta iletisine benzemiyor.");
  if (bank !== undefined) {
    const domain = senderDomain(fields);
    lines.push(listed(domain, BANK_SENDERS) ? `Gönderen: ${domain} (listede).` : "Gönderen, akıştaki bankayla uyuşmuyor.");
  }
  lines.push(authenticationLine(fields));
  lines.push(await tryDownload(env, original));
  await env.sleep(SETTLE_MS);
  const unread = await stillUnread(env, account, target.id);
  lines.push(unread.line);
  return { title: TITLES.original, ok: isMessage && verifiedByGmail(fields) && unread.ok, lines };
}

function authenticationLine(fields: ReturnType<typeof headers>): string {
  const authentication = topAuthentication(fields);
  if (authentication === null) {
    return "İletide Authentication-Results başlığı yok.";
  }
  const server = authentication.server === "mx.google.com" ? "Gmail (mx.google.com)" : "başka bir sunucu";
  let dmarc = "geçmemiş ya da hiç denenmemiş";
  if (authentication.dmarcPassFor !== "") {
    dmarc = authentication.dmarcPassFor === senderDomain(fields) ? "From alan adı için geçmiş" : "başka bir alan adı için geçmiş";
  }
  return `En üstteki Authentication-Results'ı ${server} eklemiş; DMARC ${dmarc}.`;
}

async function tryDownload(env: Environment, original: Original): Promise<string> {
  if (original.download === null) {
    return 'Sayfada "İletiyi indir" bağlantısı bulunamadı.';
  }
  await env.sleep(PACE_MS);
  try {
    const body = await (await get(env.fetcher, original.download)).text();
    const same = comparable(body) === comparable(original.raw) ? "aynı" : "farklı";
    return `"İletiyi indir" bağlantısı ham iletiyi verdi (${kb(body.length)}); sayfadaki metinle ${same}.`;
  } catch (error) {
    return `"İletiyi indir" bağlantısı kullanılamadı: ${failure(error)}`;
  }
}

async function stillUnread(env: Environment, account: number, id: string): Promise<{ ok: boolean; line: string }> {
  try {
    const feed = await readFeed(env.fetcher, account);
    return feed.entries.some((entry) => entry.id === id)
      ? { ok: true, line: "İleti indirildikten sonra da okunmamış duruyor." }
      : { ok: false, line: "İleti akıştan düştü: okundu sayılmış olabilir." };
  } catch (error) {
    return { ok: false, line: `Akış yeniden okunamadı: ${failure(error)}` };
  }
}

async function checkSearch(env: Environment, account: number, key: AccountKey | null): Promise<Check> {
  if (key === null) {
    return { title: TITLES.search, ok: null, lines: ["Hesap anahtarı (ik) olmadan denenemedi."] };
  }
  await env.sleep(PACE_MS);
  let body: string;
  try {
    const query = senderQuery(BANK_SENDERS, "-in:inbox -is:unread");
    body = await (await get(env.fetcher, threadListUrl(account, key.ik, query))).text();
  } catch (error) {
    return { title: TITLES.search, ok: false, lines: [`Gmail'in konu listesi adresi yanıt vermedi: ${failure(error)}`] };
  }
  const kind = answerKind(body);
  const ids = kind === "html" ? [] : threadIds(body);
  const lines = [`Konu listesi adresi yanıt verdi: ${ANSWER_NAMES[kind]}, ${kb(body.length)}; ${ids.length} konu kimliği.`];
  const first = ids[0];
  if (first === undefined) {
    return { title: TITLES.search, ok: false, lines };
  }
  await env.sleep(PACE_MS);
  try {
    const original = await readOriginal(env.fetcher, account, decimalId(first), key.ik);
    const domain = senderDomain(headers(original.raw));
    const ok = looksLikeMessage(original.raw) && listed(domain, BANK_SENDERS);
    lines.push(ok ? `Bulunan ilk ileti indirildi; gönderen ${domain}.` : "Bulunan ilk kimlik listedeki bir bankanın iletisi değil.");
    return { title: TITLES.search, ok, lines };
  } catch (error) {
    lines.push(`Bulunan ilk ileti indirilemedi: ${failure(error)}`);
    return { title: TITLES.search, ok: false, lines };
  }
}

function checkPlatform(env: Environment): Check {
  return {
    title: TITLES.platform,
    ok: true,
    lines: [
      `${OS_NAMES[env.os] ?? env.os} · ${env.browser} · eklenti ${env.version}`,
      "Doğrulama macOS'ta ve Windows'ta ayrı ayrı çalıştırılmalı.",
    ],
  };
}

/** What went wrong, in Turkish; never the address that was asked. */
function failure(error: unknown): string {
  if (error instanceof Redirected) {
    return "Gmail başka bir adrese yönlendirdi (çoğunlukla oturum açma sayfası: bu hesapla Gmail açık olmayabilir).";
  }
  if (error instanceof HttpError) {
    return `Gmail ${error.status} yanıtı verdi.`;
  }
  if (error instanceof FormatError) {
    return `${error.message}.`;
  }
  if (error instanceof TypeError) {
    return "istek tamamlanamadı (ağ bağlantısı ya da tarayıcı izni).";
  }
  return `beklenmeyen hata (${error instanceof Error ? error.name : typeof error}).`;
}

function comparable(text: string): string {
  return text.replace(/\r\n/g, "\n").trimEnd();
}

function kb(chars: number): string {
  return `${Math.max(1, Math.round(chars / 1024))} KB`;
}

function reportText(env: Environment, account: number, checks: readonly Check[]): string {
  const when = `${env.now().toISOString().slice(0, 16).replace("T", " ")} UTC`;
  const lines = ["İplikçi Nedim Köprüsü — ADR-0016 doğrulaması", `${when} · Gmail hesap sırası: ${account + 1}`, ""];
  for (const check of checks) {
    const mark = check.ok === null ? "– (denenemedi)" : check.ok ? "✓" : "✗";
    lines.push(`${mark} ${check.title}`, ...check.lines.map((line) => `    ${line}`));
  }
  lines.push("", "Bu metinde e-posta adresi, konu ya da ileti içeriği yoktur.");
  // A safety net: nothing above writes an address, and nothing that looks like one may leave the page.
  return lines.join("\n").replace(/[^\s@]+@[^\s@]+/g, "[adres]");
}
