/**
 * The way to İplikçi Nedim's program on the extension's pages (ADR-0024). Not paired, with nothing answering on the
 * service's address, the window from the toolbar button and the settings page say that the program is needed and
 * offer this system's installer, with the steps to install and open it, for someone who knows nothing about software.
 * A system the releases carry no installer for gets the releases' page and a sentence saying so. While a page is open
 * it asks again every few seconds and goes on to pairing once the program answers. The download opens in a new tab:
 * the browser fetches the file, the extension asks nothing of GitHub.
 */

import type { Status } from "../bridge/messages";
import { type Download, INSTALLERS, type Installer, downloadFor } from "../bridge/program";
import { ask, askService, say } from "./dom";

/** How often a page asks again whether İplikçi Nedim answers, while nothing does. */
export const WAIT_MS = 3000;

/** What a page shows of İplikçi Nedim's download. */
export interface Guide {
  /** The button's words. */
  readonly button: string;
  /** Where the button leads. */
  readonly url: string;
  /** Under the button: the file for this system, or why there is none. */
  readonly target: string;
  /** How to install and open it, in order; none without an installer. */
  readonly steps: readonly string[];
}

/** The steps for each system, its installer's name in the first. The warnings are the systems' own words (ADR-0024
 * says where each was checked). */
const STEPS: Readonly<Record<Installer["os"], (file: string) => string[]>> = {
  mac: (file) => [
    `İndirdiğiniz “${file}” dosyasını açın; tarayıcının indirilenler listesinde ve İndirilenler klasöründe durur.`,
    "Açılan pencerede İplikçi Nedim'i yanındaki “Applications” klasörünün üzerine sürükleyin: uygulama Uygulamalar " +
      "klasörünüze kopyalanır.",
    "Uygulamalar klasöründe İplikçi Nedim'e çift tıklayın.",
    "İlk açılışta macOS “İplikçi Nedim” Açılmadı penceresini gösterir, çünkü uygulama Apple'a onaylatılmadı. " +
      "“Bitti”ye basın; sonra Sistem Ayarları → Gizlilik ve Güvenlik'te aşağıya inip İplikçi Nedim'in yanındaki " +
      "“Yine de Aç”a basın ve parolanızı girin. macOS bir kez daha sorarsa yine “Yine de Aç”ı seçin.",
  ],
  win: (file) => [
    `İndirdiğiniz “${file}” dosyasını açın.`,
    "Windows uygulamayı tanımadığını söylerse “Ek bilgi”ye, sonra “Yine de çalıştır”a basın: kurulum programı " +
      "imzasız olduğu için Windows bunu bir kez sorar.",
    "Kurulumu bitirin; yönetici izni gerekmez. İplikçi Nedim kendiliğinden açılır; sonra Başlat menüsünden açarsınız.",
  ],
  linux: (file) => [
    `İndirdiğiniz “${file}” dosyasının çalıştırılmasına izin verin: dosya yöneticisinde dosyaya sağ tıklayıp ` +
      "Özellikler'i açın ve dosyanın program olarak çalıştırılmasına izin veren seçeneği açın.",
    "Dosyaya çift tıklayın.",
    "İplikçi Nedim kendini uygulama menüsüne ekler; sonra oradan açarsınız.",
  ],
};

/** The systems the releases carry an installer for, in a sentence: "A, B ve C". */
function offered(): string {
  const names = INSTALLERS.map((each) => each.name);
  return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} ve ${names.at(-1) ?? ""}`;
}

export function guideFor(download: Download): Guide {
  const { installer } = download;
  if (installer === null) {
    return {
      button: "Sürüm sayfasını aç",
      url: download.url,
      target:
        `Bu bilgisayar (${download.system}) için İplikçi Nedim'in kurulum paketi yok: paketler ${offered()} ` +
        "içindir. Sürüm sayfası hepsini gösterir.",
      steps: [],
    };
  }
  return {
    button: "İplikçi Nedim'i indir",
    url: download.url,
    target: `${installer.name} için: ${installer.file}`,
    steps: STEPS[installer.os](installer.file),
  };
}

/** The guide for this computer, as the browser names its system. */
export async function guideHere(): Promise<Guide> {
  return guideFor(downloadFor(await chrome.runtime.getPlatformInfo()));
}

/** The guide's parts on a page: the button's words, the line under it and the list of steps. */
export interface GuideParts {
  readonly label: HTMLElement;
  readonly target: HTMLElement;
  readonly steps: HTMLOListElement;
}

export function showGuide(parts: GuideParts, guide: Guide): void {
  say(parts.label, guide.button);
  say(parts.target, guide.target);
  const document = parts.steps.ownerDocument;
  parts.steps.replaceChildren(
    ...guide.steps.map((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      return item;
    }),
  );
  parts.steps.hidden = guide.steps.length === 0;
}

/** The download, or the releases' page, in a new tab in front: the browser fetches it. */
export async function openDownload(guide: Guide): Promise<void> {
  await chrome.tabs.create({ url: guide.url, active: true });
}

/** Where the bridge stands, and whether İplikçi Nedim is missing: not paired, and nothing answers on its address. */
export interface Seen {
  readonly status: Status | null;
  readonly missing: boolean;
}

/** What the service worker says now. A worker that does not answer says nothing of the program. */
export async function look(): Promise<Seen> {
  const status = await ask({ kind: "status" });
  return { status, missing: status !== null && !status.paired && (await askService()) === false };
}

/**
 * Keeps a page up to date: `show` gets what `find` says now, and again every `wait` ms while the program is missing,
 * so the page goes on by itself once the program answers. A look a later one overtook shows nothing. The function
 * returned looks again at once: when the stored state changes, or the page comes back into view.
 */
export function follow(
  show: (seen: Seen) => void,
  find: () => Promise<Seen> = look,
  wait: number = WAIT_MS,
): () => Promise<void> {
  let turn = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const again = async (): Promise<void> => {
    turn += 1;
    const mine = turn;
    clearTimeout(timer);
    const seen = await find();
    if (mine !== turn) {
      return;
    }
    show(seen);
    if (seen.missing) {
      timer = setTimeout(() => void again(), wait);
    }
  };
  return again;
}
