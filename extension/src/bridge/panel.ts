/**
 * "İplikçi Nedim'i aç" (ADR-0019): the interface of the service on this computer, in a tab of this browser.
 *
 * A tab that shows it comes to the front, and nothing is asked of the service. A tab of it that is in front already
 * is opened again with a login link: its session may have ended, or it may show the browser's error page from a time
 * the service was not running. Otherwise a paired extension has the service prove itself, as before every delivery,
 * asks it for a one-time login link and opens the link: in the tab that shows the service's sign-in page, or in a new
 * one. The session the link opens is the browser's own cookie; the extension never reads it. Without a link (not
 * paired, the pairing revoked, an older service) the address opens all the same, as the browser may hold a session.
 * Nothing opens when nothing answers there, or when what answers is not the paired service.
 */

import { type Fetcher, NotTheService, type Paired, Refused, SERVICE, ServiceDown, loginLink, prove } from "./service";
import { revoked } from "./steps";

/** The title of the service's sign-in pages (src/iplikci/api/pages.py); the interface's tabs carry another. */
export const SIGN_IN_TITLE = "Giriş · İplikçi Nedim";
/** Where the service's login links lead; a link that leads anywhere else is not opened. */
export const LOGIN_PREFIX = `${SERVICE}/giris?`;
export const HOME = `${SERVICE}/`;

/** A browser tab on the service's address. */
export interface ServiceTab {
  readonly id: number;
  readonly windowId: number;
  readonly url: string;
  readonly title: string;
  /** The tab is the one shown in the window the user is in. */
  readonly front: boolean;
  /** When the tab was last shown, in ms since the epoch; 0 where the browser does not say. */
  readonly lastAccessed: number;
}

/** The browser's tabs, as far as "İplikçi Nedim'i aç" needs them. */
export interface PanelTabs {
  /** The tabs open on the service's address. */
  find(): Promise<readonly ServiceTab[]>;
  /** Bring the tab and its window to the front, showing url in the tab first when one is given. */
  show(tab: ServiceTab, url?: string): Promise<void>;
  /** Open url in a new tab, in front. */
  open(url: string): Promise<void>;
}

export interface PanelEnvironment {
  readonly service: Fetcher;
  readonly tabs: PanelTabs;
}

export type PanelOutcome =
  | "shown" // a tab with the interface came to the front
  | "signed-in" // a login link opened
  | "opened" // the address opened without a link
  | "service-down" // nothing answers on the address: nothing opened
  | "not-the-service"; // something else than the paired service answers there: nothing opened

/** What "İplikçi Nedim'i aç" did; the detail is Turkish, for the extension's window and its settings page. */
export interface PanelAnswer {
  readonly outcome: PanelOutcome;
  readonly detail: string;
}

const DOWN = "İplikçi Nedim bu bilgisayarda çalışmıyor; uygulamayı açıp yeniden deneyin.";
const STRANGER = "Bu bilgisayarda eşleşilen İplikçi Nedim yerine başka bir program yanıt veriyor; açılmadı.";
const UNPAIRED =
  "İplikçi Nedim'in adresi açıldı. Giriş isterse eklentiyi eşleştirin ya da arayüzü İplikçi Nedim uygulamasından " +
  "açın.";

export async function openPanel(env: PanelEnvironment, paired: Paired | null): Promise<PanelAnswer> {
  const tabs = await env.tabs.find();
  const shown = latest(tabs.filter((tab) => !signingIn(tab)));
  if (shown !== undefined && !shown.front) {
    await env.tabs.show(shown);
    return { outcome: "shown", detail: "İplikçi Nedim'in açık sekmesi öne getirildi." };
  }
  const reused = shown ?? latest(tabs.filter(signingIn));
  const go = (url: string): Promise<void> => (reused === undefined ? env.tabs.open(url) : env.tabs.show(reused, url));
  if (paired === null) {
    await go(HOME);
    return { outcome: "opened", detail: UNPAIRED };
  }
  let link: string;
  try {
    await prove(env.service, paired);
    link = await loginLink(env.service, paired);
  } catch (error) {
    if (error instanceof ServiceDown) {
      return { outcome: "service-down", detail: DOWN };
    }
    if (error instanceof NotTheService) {
      return { outcome: "not-the-service", detail: STRANGER };
    }
    await go(HOME); // the service is there but gave no link: the browser may hold a session
    return { outcome: "opened", detail: withoutLink(error) };
  }
  if (!link.startsWith(LOGIN_PREFIX)) {
    await go(HOME);
    return {
      outcome: "opened",
      detail: "İplikçi Nedim'in verdiği giriş bağlantısı bu bilgisayarın adresine gitmiyordu; adres bağlantısız açıldı.",
    };
  }
  await go(link);
  return { outcome: "signed-in", detail: "İplikçi Nedim açıldı." };
}

/** A tab that shows the service's sign-in page, or is on its way through a login link. */
export function signingIn(tab: ServiceTab): boolean {
  if (tab.title === SIGN_IN_TITLE) {
    return true;
  }
  try {
    return new URL(tab.url).pathname === "/giris";
  } catch {
    return false;
  }
}

/** The tab shown last: in front, else the one the user looked at most recently. */
function latest(tabs: readonly ServiceTab[]): ServiceTab | undefined {
  return [...tabs].sort((a, b) => Number(b.front) - Number(a.front) || b.lastAccessed - a.lastAccessed)[0];
}

/** Why the address opened without a link, though the service answered. */
function withoutLink(error: unknown): string {
  if (revoked(error)) {
    return "Eşleşme İplikçi Nedim'de iptal edilmiş; adres giriş bağlantısı olmadan açıldı. Eklentiyi yeniden eşleştirin.";
  }
  // A service from before the link knows no such address, or refuses a bridge's token on it.
  if (error instanceof Refused && (error.status === 404 || error.code === "forbidden")) {
    return "İplikçi Nedim bu eklentiden eski bir sürüm; adres giriş bağlantısı olmadan açıldı.";
  }
  return "İplikçi Nedim giriş bağlantısı vermedi; adres bağlantısız açıldı.";
}
