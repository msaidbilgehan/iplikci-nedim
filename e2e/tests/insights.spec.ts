// The Değerlendirme screen on the service itself (F10), its parts one tab at a time: a preset writes its period into
// the address, the monthly spending's heat table passes axe, and the cards' rows open on the İşlemler screen with the
// same filters — the very rows the cards count, adding up to the same total. The regular payments follow every filter
// but the period and say which they cannot. The detailed view shows the budget, the habits and the forecast line by
// line. Nothing is changed, so both themes run side by side on the one demo data folder.

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
  // The demo's documents reach November through the cards' statements: the last 3 months are September to November.
  await expect(page).toHaveURL(/[?&]from=2026-09-01&to=2026-11-30$/);
  await expect(presets.getByRole("button", { name: "Son 3 ay" })).toHaveAttribute("aria-pressed", "true");
  const tiles = page.getByRole("region", { name: "Özet", exact: true });
  await expect(tiles).toContainText("Eylül 2026 – Kasım 2026");

  const parts = page.getByRole("tablist", { name: "Değerlendirmenin bölümleri" });
  await parts.getByRole("tab", { name: "Harcamalar" }).click();
  await expect(page).toHaveURL(/[?&]bolum=harcamalar(&|$)/);
  const monthly = page.getByRole("region", { name: "Aylık giderler", exact: true });
  await monthly.getByRole("tab", { name: "Tablo" }).click();
  await expect(monthly.getByRole("table", { name: "Aylık giderler, ana gruplara göre" })).toBeVisible();
  await expect(monthly.getByRole("rowheader", { name: /^Aylık ortalama \(\d+ tam ay\)$/ })).toBeVisible();
  expect(await violations(page, "main figure")).toEqual([]); // the charts, the heat table among them

  await parts.getByRole("tab", { name: "İşlemler ve veriler" }).click();
  const rows = page.getByRole("region", { name: "İşlemler", exact: true });
  const said = (await rows.getByText(/^Bu süzgeçlerle \d+ işlem, toplam .+ TL\.$/).textContent()) ?? "";
  const [, count, total] = /^Bu süzgeçlerle (\d+) işlem, toplam (.+ TL)\.$/.exec(said) ?? [];
  expect(Number(count)).toBeGreaterThan(0);
  await rows.getByRole("link", { name: "İşlemleri bu süzgeçlerle göster" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "İşlemler" })).toBeVisible();
  await expect(page).toHaveURL(/[?&]kind=purchase&kind=refund&kind=interest_fee(&|$)/);
  await expect(page).toHaveURL(/[?&]from=2026-09-01&to=2026-11-30(&|$)/);
  await loaded(page);
  await expect(page.getByText(`${count} işlem; harcama ${total},`)).toBeVisible();
});

test("düzenli ödemeler dönemden başka her süzgece uyar, uyamadığını söyler", async ({ page }) => {
  // The demo's two Migros payments, the merchant written as the bank prints it; the period is before the data.
  await page.goto("/degerlendirme?merchant=MIGROS&tag=ev&from=2025-01-01&to=2025-01-31&bolum=gelecek");
  await expect(page.getByRole("heading", { level: 1, name: "Değerlendirme" })).toBeVisible({ timeout: 30_000 });
  await loaded(page);
  const regular = page.getByRole("region", { name: "Düzenli ödemeler ve abonelikler" });
  await expect(regular.getByText("Bu süzgeçlerle süren 2 aylık ödeme ayda 3.990,00 TL tutuyor.")).toBeVisible();
  await expect(regular).toContainText(
    "Dönem süzgecinden bağımsızdır, diğer süzgeçlere uyar; durumlar bugüne göredir. Etiket süzgecini dikkate almaz,",
  );
});

test("ayrıntılı görünüm bütçeyi, alışkanlıkları ve tahmini kalem kalem gösterir", async ({ page }) => {
  test.slow();
  await page.addInitScript(() => window.localStorage.setItem("iplikci.view", "detailed"));
  await page.goto("/degerlendirme");
  await expect(page.getByRole("heading", { level: 1, name: "Değerlendirme" })).toBeVisible({ timeout: 30_000 });
  await loaded(page);
  const parts = page.getByRole("tablist", { name: "Değerlendirmenin bölümleri" });
  await expect(page.getByRole("table", { name: "Aylık bütçe: bugünkü tipik ay ve önerilen ay" })).toBeVisible();
  expect(await violations(page, "main table")).toEqual([]);
  await parts.getByRole("tab", { name: "Harcamalar" }).click();
  await expect(page.getByRole("table", { name: "Alışkanlıklar ve bundan sonra aylık maliyetleri" })).toBeVisible();
  expect(await violations(page, "main table")).toEqual([]);
  await parts.getByRole("tab", { name: "Önümüzdeki aylar" }).click();
  const forecast = page.getByRole("table", { name: "Önümüzdeki üç ayın tahmini, kalem kalem" });
  await expect(forecast).toBeVisible();
  await expect(forecast.getByRole("rowheader", { name: "Tahmini toplam gider" })).toBeVisible();
  expect(await violations(page, "main table")).toEqual([]);
});
