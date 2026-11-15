// The README's pictures, made again from the demo data folder (../gorseller.config.ts, `npm run gorseller`): each
// screen once its data has loaded, in the light theme and the simple view unless its name says otherwise. The moving
// ones are recorded with Chrome's own screencast, a frame each time the page changes, and turned into GIFs by ffmpeg
// from the moment the page is drawn; Playwright's video recorder would need an ffmpeg of its own. A recording shows no
// mouse pointer, so the two that point at something draw one. The setup wizard is photographed on a service of its own
// on a new, empty data folder, as a first run sees it. Only the demo's fake documents are shown, and no screen with a
// token or a folder's path. The pictures go to docs/gorseller/ at the repo's root (IPLIKCI_GORSELLER names another
// folder); the frames stay in a temporary folder. The last picture changes the demo's rules, so it runs last.

import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";

import {
  type Browser,
  type BrowserContext,
  type BrowserContextOptions,
  expect,
  type Locator,
  type Page,
  test,
} from "@playwright/test";

import { loginLink, startOwnService } from "../ownService";
import { BASE_URL, STATE, STATE_DIR } from "../service";

const OUT = resolve(process.env.IPLIKCI_GORSELLER ?? join(import.meta.dirname, "..", "..", "docs", "gorseller"));
const DESKTOP = { width: 1280, height: 800 };
const KB = 1024;
const MB = 1024 * KB;
const PNG_LIMIT = 450 * KB; // a picture in the README loads at once
const HEADER = 56; // the top bar stays on top (Layout): a part scrolled to stops under it
const LOADS = { timeout: 30_000 }; // the first page of a run may wait for the service's first analysis
const SAVES = { timeout: 30_000 }; // a rule change: the service makes its analysis again before it answers

// As the config's own `use`, for the browsers a picture opens itself (a recording, a phone, the dark theme).
const BROWSER: BrowserContextOptions = {
  baseURL: BASE_URL,
  storageState: STATE,
  locale: "tr-TR",
  timezoneId: "Europe/Istanbul",
  viewport: DESKTOP,
  deviceScaleFactor: 1,
  colorScheme: "light",
};

let scratch = ""; // the recordings' frames, outside the repo

test.beforeAll(() => {
  try {
    execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
  } catch {
    throw new Error("ffmpeg was not found on PATH: it turns the recordings into GIFs (macOS: brew install ffmpeg)");
  }
  mkdirSync(OUT, { recursive: true });
  scratch = mkdtempSync(join(tmpdir(), "iplikci-gorseller-"));
});

test.afterAll(() => {
  if (scratch) {
    rmSync(scratch, { recursive: true, force: true });
  }
});

// --- waiting for a screen -------------------------------------------------------------------------------------------

/** Nothing loading, nothing failed, and the fonts and the images in view drawn. */
async function settled(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, LOADS);
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
  await expect(page.getByText("Oturum kapandı")).toHaveCount(0);
  await page.evaluate(async () => {
    await document.fonts.ready;
    const shown = [...document.images].filter((image) => image.getBoundingClientRect().top < window.innerHeight);
    await Promise.all(shown.map((image) => image.decode().catch(() => undefined)));
    await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  });
}

async function screen(page: Page, heading: string): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible(LOADS);
  await settled(page);
}

const months = (page: Page): Locator => page.getByRole("region", { name: "Aylara göre gelen ve giden" });
const nextDays = (page: Page): Locator => page.getByRole("region", { name: "Önümüzdeki 30 gün" });

/** The simple view's Pano with every part of its story drawn: the month, its charts, the next 30 days, the advice. */
async function pano(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name: "Pano" })).toBeVisible(LOADS);
  await expect(page.getByRole("region", { name: "İplikçi Nedim'in paranız hakkındaki sözü" })).toBeVisible(LOADS);
  await expect(page.getByRole("region", { name: /: paranız ne durumda\?$/ })).toBeVisible(LOADS);
  await expect(months(page).getByRole("img", { name: /yığılmış sütun grafiği/ })).toBeVisible(LOADS);
  const where = page.getByRole("region", { name: "Paranız nereye gitti?" });
  await expect(where.getByRole("listitem").first()).toBeVisible(LOADS);
  await expect(nextDays(page).getByRole("img", { name: /çizgi grafiği/ })).toBeVisible(LOADS);
  await expect(page.getByRole("region", { name: "Ne yapmalısınız?" })).toBeVisible(LOADS);
  await settled(page);
}

// --- pictures -------------------------------------------------------------------------------------------------------

/** The PNG without its ancillary chunks (text, times, EXIF, colour profiles): the pixels and nothing else. */
function bare(png: Buffer): Buffer {
  const kept = [png.subarray(0, 8)];
  for (let at = 8; at < png.length; ) {
    const type = png.toString("latin1", at + 4, at + 8);
    const end = at + 12 + png.readUInt32BE(at);
    if (/^[A-Z]/.test(type) || type === "tRNS") {
      kept.push(png.subarray(at, end)); // the critical ones: IHDR, PLTE, IDAT, IEND
    }
    at = end;
  }
  return Buffer.concat(kept);
}

function save(name: string, png: Buffer): void {
  const kept = bare(png);
  expect(kept.length, `${name}: ${Math.round(kept.length / KB)} KB`).toBeLessThanOrEqual(PNG_LIMIT);
  writeFileSync(join(OUT, name), kept);
}

/** The window as it is; or, given a height, the page's top down to it. */
async function photograph(page: Page, name: string, height?: number): Promise<void> {
  const clip = height === undefined ? undefined : { x: 0, y: 0, width: DESKTOP.width, height };
  save(name, await page.screenshot({ animations: "disabled", fullPage: clip !== undefined, clip }));
}

/** Where a part of the page starts and ends, from the page's top. */
async function spans(parts: Locator): Promise<Array<{ top: number; bottom: number }>> {
  return parts.evaluateAll((elements) =>
    elements.map((element) => {
      const box = element.getBoundingClientRect();
      return { top: box.top + window.scrollY, bottom: box.bottom + window.scrollY };
    }),
  );
}

/**
 * Where a picture of the page's top ends, at most limit pixels down: between two of the items (a table's rows, a
 * list's cards), a little below the last that fits whole and before the next begins, so no item is cut in two.
 */
async function between(items: Locator, limit: number): Promise<number> {
  const found = await spans(items);
  const fits = found.filter((item) => item.bottom <= limit).map((item) => item.bottom);
  if (fits.length === 0) {
    return limit;
  }
  const end = Math.max(...fits);
  const next = Math.min(...found.filter((item) => item.top >= end - 0.5).map((item) => item.top), Infinity);
  return Math.floor(Math.min(next, end + 16));
}

// --- moving pictures ------------------------------------------------------------------------------------------------

interface Frame {
  file: string;
  at: number; // when Chrome drew it, in seconds by the clock
}

interface Recording {
  context: BrowserContext;
  page: Page;
  folder: string;
  frames: Frame[];
  stop: () => Promise<void>;
}

/** A mouse pointer drawn on the page, as recordings show none: a dark dot in a white ring, smaller while pressed. */
function drawPointer(): void {
  const draw = (): void => {
    const size = 22;
    const dot = document.createElement("div");
    dot.setAttribute("aria-hidden", "true");
    Object.assign(dot.style, {
      position: "fixed",
      left: "0",
      top: "0",
      width: `${size}px`,
      height: `${size}px`,
      boxSizing: "border-box",
      borderRadius: "50%",
      background: "rgba(24, 24, 27, 0.82)",
      border: "3px solid #fff",
      boxShadow: "0 1px 6px rgba(0, 0, 0, 0.45)",
      pointerEvents: "none",
      zIndex: "2147483647",
      display: "none",
    });
    let x = 0;
    let y = 0;
    let pressed = false;
    const place = (): void => {
      dot.style.transform = `translate(${x - size / 2}px, ${y - size / 2}px) scale(${pressed ? 0.7 : 1})`;
    };
    const follow = (event: MouseEvent): void => {
      x = event.clientX;
      y = event.clientY;
      dot.style.display = "block";
      place();
    };
    const press = (down: boolean) => (): void => {
      pressed = down;
      place();
    };
    window.addEventListener("mousemove", follow, true);
    window.addEventListener("mousedown", press(true), true);
    window.addEventListener("mouseup", press(false), true);
    document.body.append(dot);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", draw);
  } else {
    draw();
  }
}

/** A page whose every change Chrome hands over as a frame, kept as a JPEG with the time it was drawn. */
async function record(browser: Browser, { pointer }: { pointer: boolean }): Promise<Recording> {
  const context = await browser.newContext(BROWSER);
  if (pointer) {
    await context.addInitScript(drawPointer);
  }
  const page = await context.newPage();
  const folder = mkdtempSync(join(scratch, "kayit-"));
  const drawn: Frame[] = [];
  const cdp = await context.newCDPSession(page);
  cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
    const file = join(folder, `${String(drawn.length).padStart(5, "0")}.jpg`);
    writeFileSync(file, Buffer.from(data, "base64"));
    drawn.push({ file, at: metadata.timestamp ?? Date.now() / 1000 });
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined); // the next frame waits for it
  });
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 92,
    maxWidth: DESKTOP.width,
    maxHeight: DESKTOP.height,
  });
  const stop = async (): Promise<void> => {
    await cdp.send("Page.stopScreencast").catch(() => undefined);
    await context.close();
  };
  return { context, page, folder, frames: drawn, stop };
}

/** Now, in the frames' time. */
const now = (): number => Date.now() / 1000;

/**
 * The recording from `from` to now as a GIF, 960 pixels wide, each frame shown as long as the page kept it: each try a
 * little lighter until the GIF is no larger than limit. The recording's browser is closed.
 */
async function gif(recording: Recording, from: number, name: string, limit: number): Promise<void> {
  const to = now();
  await recording.page.waitForTimeout(200); // the last frame before `to` handed over
  await recording.stop();
  const all = recording.frames;
  const first = Math.max(
    all.findLastIndex((frame) => frame.at <= from),
    0,
  );
  const shown = all.slice(first).filter((frame) => frame.at < to);
  const last = shown.at(-1);
  if (last === undefined) {
    throw new Error(`${name}: Chrome handed over no frame`);
  }
  const lines = ["ffconcat version 1.0"];
  shown.forEach((frame, index) => {
    const length = (shown[index + 1]?.at ?? to) - Math.max(frame.at, from);
    lines.push(`file '${basename(frame.file)}'`, `duration ${Math.max(length, 0.001).toFixed(3)}`);
  });
  lines.push(`file '${basename(last.file)}'`); // the concat demuxer takes the last duration only from a file after it
  const list = join(recording.folder, "kareler.ffconcat");
  writeFileSync(list, `${lines.join("\n")}\n`);
  const out = join(OUT, name);
  for (const [fps, colors] of [
    [12, 160],
    [10, 128],
    [8, 96],
  ] as const) {
    const graph =
      `fps=${fps},scale=960:-1:flags=lanczos,split[a][b];` +
      `[a]palettegen=max_colors=${colors}:stats_mode=diff[p];` +
      "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle";
    execFileSync("ffmpeg", ["-y", "-v", "error", "-f", "concat", "-i", list, "-vf", graph, "-loop", "0", out]);
    if (statSync(out).size <= limit) {
      return;
    }
  }
  throw new Error(`${name} is over ${limit / MB} MB even at 8 frames a second`);
}

/** The page scrolled, eased in and out over ms, until part stands just under the top bar (or the page ends). */
async function glide(page: Page, part: Locator, ms: number): Promise<void> {
  const [span] = await spans(part);
  if (span === undefined) {
    throw new Error(`${part.toString()} is not on the page`);
  }
  await page.evaluate(
    ([to, duration]) =>
      new Promise<void>((done) => {
        const from = window.scrollY;
        const end = Math.max(0, Math.min(to, document.documentElement.scrollHeight - window.innerHeight));
        const start = performance.now();
        const step = (time: number): void => {
          const t = duration > 0 ? Math.min(1, (time - start) / duration) : 1;
          const eased = t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
          window.scrollTo({ top: from + (end - from) * eased, behavior: "instant" });
          if (t < 1) {
            requestAnimationFrame(step);
          } else {
            done();
          }
        };
        requestAnimationFrame(step);
      }),
    [span.top - HEADER - 16, ms] as const,
  );
}

/** The middle of what a locator shows, where the mouse goes. */
async function middle(part: Locator): Promise<{ x: number; y: number }> {
  const box = await part.boundingBox();
  if (box === null) {
    throw new Error(`${part.toString()} is not shown`);
  }
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

/** A click where the mouse is, held for a few frames: the pointer shrinks, so the click is seen. */
async function click(page: Page): Promise<void> {
  await page.mouse.down();
  await page.waitForTimeout(160);
  await page.mouse.up();
}

/** The mouse put aside on the menu's empty part, under its last item, where it covers nothing the picture shows. */
async function putAside(page: Page): Promise<void> {
  await page.mouse.move(120, DESKTOP.height - 140, { steps: 14 });
}

// --- the pictures ---------------------------------------------------------------------------------------------------

test("pano.gif: sade Pano'nun hikâyesi yukarıdan aşağı", async ({ browser }) => {
  const recording = await record(browser, { pointer: false });
  const { page } = recording;
  await page.goto("/");
  await pano(page);
  const from = now();
  await page.waitForTimeout(2600); // İplikçi Nedim's line and the month's money, with its verdict
  await glide(page, months(page), 1100); // the months as bars, and where the money went beside them
  await page.waitForTimeout(2600);
  await glide(page, nextDays(page), 1000);
  await page.waitForTimeout(1600);
  await glide(page, page.getByRole("region", { name: "Ne yapmalısınız?" }), 1000);
  await page.waitForTimeout(2600);
  await gif(recording, from, "pano.gif", 4 * MB);
});

test("grafikten-islemlere.gif: bir ayın giden sütununa tıklayınca o ayın işlemleri açılır", async ({ browser }) => {
  const recording = await record(browser, { pointer: true });
  const { page } = recording;
  await page.goto("/");
  await pano(page);
  await glide(page, months(page), 0);
  const chart = months(page).getByRole("img", { name: /yığılmış sütun grafiği/ });
  // The newest month's money gone out: the last orange column, under the line. The mouse comes to it from the right,
  // from the empty space under the chart beside it, so it passes over no other month and no other chart.
  const out = await middle(chart.locator("path.fill-slot-2").last());
  const where = await page.getByRole("region", { name: "Paranız nereye gitti?" }).boundingBox();
  const start = { x: out.x + 220, y: Math.max(out.y + 60, (where?.y ?? 0) + (where?.height ?? 0) + 40) };
  await page.mouse.move(start.x, start.y);
  await settled(page);
  const from = now();
  await page.waitForTimeout(700);
  await page.mouse.move(out.x, out.y, { steps: 28 });
  await page.waitForTimeout(1500); // the month's figures in the chart's tip
  await click(page);
  await expect(page).toHaveURL(/\/islemler\?from=\d{4}-\d{2}-01&to=/, LOADS);
  await screen(page, "İşlemler");
  await expect(page.getByRole("region", { name: "Toplamlar" })).toBeVisible();
  await putAside(page);
  await page.waitForTimeout(300);
  // The month the filters keep, the totals (what went out is the column's) and the rows they add up from.
  await glide(page, page.getByText("Dönemin bütün işlemleri"), 900);
  await page.waitForTimeout(2200);
  await gif(recording, from, "grafikten-islemlere.gif", 3 * MB);
});

test("arama.gif: İşlemler'de virgülle iki şey birden aranır", async ({ browser }) => {
  const recording = await record(browser, { pointer: true });
  const { page } = recording;
  await page.goto("/islemler");
  await screen(page, "İşlemler");
  const search = page.getByRole("searchbox", { name: "Ara" });
  const box = await middle(search);
  await page.mouse.move(box.x + 240, box.y + 260);
  await settled(page);
  const from = now();
  await page.waitForTimeout(400);
  await page.mouse.move(box.x + 120, box.y, { steps: 16 });
  await click(page);
  await page.keyboard.type("migros", { delay: 110 });
  await expect(page).toHaveURL(/\?q=migros$/, LOADS);
  await settled(page);
  await page.waitForTimeout(700);
  await page.keyboard.type(", netflix", { delay: 110 });
  const parts = page.getByRole("region", { name: "Aramanın parçaları" });
  await expect(parts).toContainText("netflix", LOADS);
  await settled(page);
  await putAside(page);
  await page.waitForTimeout(1200); // how many rows each part finds, and their totals
  await glide(page, parts, 800);
  await page.waitForTimeout(1800);
  await gif(recording, from, "arama.gif", 3 * MB);
});

test("takvim.png: önümüzdeki 60 günün ödemeleri ve gelirleri", async ({ page }) => {
  await page.goto("/takvim");
  await screen(page, "Takvim");
  const rows = page.getByRole("region", { name: "Önümüzdeki 60 gün" }).getByRole("row");
  await photograph(page, "takvim.png", await between(rows, DESKTOP.height));
});

test("duzenli-odemeler.png: her ay ödenenler ve düzenli gelirler", async ({ page }) => {
  await page.goto("/abonelikler");
  await screen(page, "Düzenli ödemeler");
  // Three rows of the monthly payments: the rent and the shopping, the bills and the subscriptions.
  const cards = page.getByRole("region", { name: "Aylık ödemeler" }).locator("ul[aria-label] > li");
  await photograph(page, "duzenli-odemeler.png", await between(cards, 1010));
});

test("degerlendirme.png: Değerlendirme'nin özeti, öne çıkanlar ve önerilen adımlar", async ({ page }) => {
  await page.goto("/degerlendirme");
  await screen(page, "Değerlendirme");
  // Down to the end of the advice and of the finding beside it, before the next finding begins: no line cut in two.
  const card = page.getByRole("region", { name: "Değerlendirme ve strateji" });
  const [advice] = await spans(card.getByRole("region", { name: "Önerilen adımlar" }).getByRole("list"));
  const findings = await spans(card.getByRole("region", { name: "Öne çıkanlar" }).getByRole("listitem"));
  if (advice === undefined || findings.length === 0) {
    throw new Error("Değerlendirme shows no advice or no finding");
  }
  const beside = findings.findIndex(
    (finding, index) => finding.bottom >= advice.bottom - 40 && (findings[index + 1]?.top ?? Infinity) > advice.bottom,
  );
  const end = Math.max(advice.bottom, ...(beside < 0 ? findings : [findings[beside]]).map((f) => f?.bottom ?? 0));
  const next = beside < 0 ? Infinity : (findings[beside + 1]?.top ?? Infinity);
  await photograph(page, "degerlendirme.png", Math.floor(Math.min(end + 20, next)));
});

test("belge-ekle.png: bankadan indirilen belgeler bir klasörle eklenir", async ({ page }) => {
  await page.goto("/belge-ekle");
  await screen(page, "Belge ekle");
  await photograph(page, "belge-ekle.png");
});

test("telefon.png: Pano telefonda", async ({ browser }) => {
  const context = await browser.newContext({ ...BROWSER, viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  await page.goto("/");
  await pano(page);
  save("telefon.png", await page.screenshot({ animations: "disabled" }));
  await context.close();
});

test("koyu-tema.png: ayrıntılı Pano koyu temada", async ({ browser }) => {
  const context = await browser.newContext({ ...BROWSER, colorScheme: "dark" });
  await context.addInitScript(() => window.localStorage.setItem("iplikci.view", "detailed"));
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Pano" })).toBeVisible(LOADS);
  await expect(page.getByRole("region", { name: "Net varlık" })).toBeVisible(LOADS);
  await settled(page);
  await photograph(page, "koyu-tema.png");
  await context.close();
});

test("kurulum.png: ilk açılışta kurulum sihirbazı, boş bir veri klasöründe", async ({ browser }) => {
  const home = join(STATE_DIR, "gorseller-ilk-acilis");
  const service = await startOwnService(home, join(STATE_DIR, "gorseller-ilk-acilis.log"), 90_000);
  try {
    const context = await browser.newContext({
      ...BROWSER,
      baseURL: service.base,
      storageState: { cookies: [], origins: [] },
    });
    const page = await context.newPage();
    await page.goto(await loginLink(service.base));
    await expect(page).toHaveURL(`${service.base}/kurulum`, LOADS);
    // Opened without a step, the wizard starts at the first one still to do: the user's names.
    await expect(page.getByRole("heading", { level: 2, name: /^Adım 2\/\d+: Adınız/ })).toBeVisible(LOADS);
    await screen(page, "Kurulum sihirbazı");
    await photograph(page, "kurulum.png");
    await context.close();
  } finally {
    await service.stop();
    rmSync(home, { recursive: true, force: true });
  }
});

// Last: it changes the demo's rules. A payment marked cancelled in October came again in November, and the
// notification "İptalden sonra ödeme" lands in the box, as it would for the user.
test("bildirimler.png: iptal edilen bir ödeme yine çekilince bildirim kutuya düşer", async ({ page }) => {
  await page.goto("/abonelikler");
  await screen(page, "Düzenli ödemeler");
  const monthly = page.getByRole("region", { name: "Aylık ödemeler" });
  await monthly.getByRole("button", { name: "İptal ettim: Netflix" }).click();
  const panel = page.getByRole("dialog", { name: "Netflix" });
  await panel.getByLabel("Son ödeme ayı").selectOption("2026-10");
  await panel.getByRole("button", { name: "Önizle" }).click();
  await panel.getByRole("button", { name: "Kaydet" }).click();
  await expect(panel.getByText(/^Kaydedildi: Netflix/)).toBeVisible(SAVES);
  await page.keyboard.press("Escape");

  await page.goto("/bildirimler");
  const notice = page
    .getByRole("region", { name: "Bildirim kutusu" })
    .getByRole("listitem")
    .filter({ hasText: "İptalden sonra ödeme" });
  // The notifications follow the analysis the rule change asked for.
  await expect(async () => {
    await page.reload();
    await expect(notice).toBeVisible({ timeout: 2_000 });
  }).toPass(SAVES);
  await screen(page, "Bildirimler");
  await photograph(page, "bildirimler.png");
});
