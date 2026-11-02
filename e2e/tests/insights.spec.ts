// The Değerlendirme screen on the service itself (F10): a preset writes its period into the address, the monthly
// spending's heat table passes axe, and the cards' rows open on the İşlemler screen with the same filters — the very
// rows the cards count, adding up to the same total. The detailed view shows the budget, the habits and the forecast
// line by line. Nothing is changed, so both themes run side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function loaded(page: Page): Promise<void> {
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
}

/** axe's findings within the elements a selector names: the whole screen's are the screens' test's. */
async function violations(page: Page, selector: string): Promise<string[]> {
  const found = await new AxeBuilder({ page }).include(selector).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`);
}

test("bir dönem seçilir, ısı tablosu erişilebilir, işlemler aynı toplamla İşlemler'de açılır", async ({ page }) => {
  test.slow(); // the screen asks for a dozen cards at once
  await page.goto("/degerlendirme");
  await expect(page.getByRole("heading", { level: 1, name: "Değerlendirme" })).toBeVisible({ timeout: 30_000 });
  await loaded(page);

  const presets = page.getByRole("group", { name: "Dönem" });
  await expect(presets.getByRole("button", { name: "Son 12 ay" })).toHaveAttribute("aria-pressed", "true");
  await presets.getByRole("button", { name: "Son 3 ay" }).click();
  await expect(page).toHaveURL(/[?&]from=2026-08-01&to=2026-10-31$/);
  await expect(presets.getByRole("button", { name: "Son 3 ay" })).toHaveAttribute("aria-pressed", "true");
  const tiles = page.getByRole("region", { name: "Özet", exact: true });
  await expect(tiles).toContainText("Ağustos 2026 – Ekim 2026");

  const monthly = page.getByRole("region", { name: "Aylık giderler", exact: true });
  await monthly.getByRole("tab", { name: "Tablo" }).click();
  await expect(monthly.getByRole("table", { name: "Aylık giderler, ana gruplara göre" })).toBeVisible();
  await expect(monthly.getByRole("rowheader", { name: /^Aylık ortalama \(\d+ tam ay\)$/ })).toBeVisible();
  expect(await violations(page, "main figure")).toEqual([]); // the charts, the heat table among them

  const rows = page.getByRole("region", { name: "İşlemler", exact: true });
  const said = (await rows.getByText(/^Bu süzgeçlerle \d+ işlem, toplam .+ TL\.$/).textContent()) ?? "";
  const [, count, total] = /^Bu süzgeçlerle (\d+) işlem, toplam (.+ TL)\.$/.exec(said) ?? [];
  expect(Number(count)).toBeGreaterThan(0);
  await rows.getByRole("link", { name: "İşlemleri bu süzgeçlerle göster" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "İşlemler" })).toBeVisible();
  await expect(page).toHaveURL(/[?&]kind=purchase&kind=refund&kind=interest_fee(&|$)/);
  await expect(page).toHaveURL(/[?&]from=2026-08-01&to=2026-10-31(&|$)/);
  await loaded(page);
  await expect(page.getByText(`${count} işlem; harcama ${total},`)).toBeVisible();
});

test("ayrıntılı görünüm bütçeyi, alışkanlıkları ve tahmini kalem kalem gösterir", async ({ page }) => {
  test.slow();
  await page.addInitScript(() => window.localStorage.setItem("iplikci.view", "detailed"));
  await page.goto("/degerlendirme");
  await expect(page.getByRole("heading", { level: 1, name: "Değerlendirme" })).toBeVisible({ timeout: 30_000 });
  await loaded(page);
  await expect(page.getByRole("table", { name: "Aylık bütçe: bugünkü tipik ay ve önerilen ay" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Alışkanlıklar ve bundan sonra aylık maliyetleri" })).toBeVisible();
  const forecast = page.getByRole("table", { name: "Önümüzdeki üç ayın tahmini, kalem kalem" });
  await expect(forecast).toBeVisible();
  await expect(forecast.getByRole("rowheader", { name: "Tahmini toplam gider" })).toBeVisible();
  expect(await violations(page, "main table")).toEqual([]);
});
