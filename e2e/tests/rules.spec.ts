// The Kurallar screen on the service itself (F15): a merchant rule is previewed against the demo's ledger — the rows it
// moves, from which category to which — and written; a change from a list is asked in a side panel; both views pass
// axe. Each theme's project names a merchant of its own, so the two run side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

// One row of the demo each, moved to a category it is not in.
const RULES = {
  acik: { merchant: "Örnek Teknoloji Mağazası", pattern: "TEKNOSA", category: "Ev & Yaşam" },
  koyu: { merchant: "Örnek Havayolu", pattern: "TURKISH AIRLINES", category: "Konaklama" },
} as const;
const SETTLES = { timeout: 20_000 }; // the service analyses again before it answers a save
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function violations(page: Page, within?: string): Promise<string[]> {
  const axe = new AxeBuilder({ page }).withTags(WCAG);
  const found = await (within ? axe.include(within) : axe).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")} — ${v.nodes[0]?.failureSummary ?? ""}`);
}

async function open(page: Page): Promise<void> {
  await page.goto("/kurallar");
  await expect(page.getByRole("heading", { level: 1, name: "Kurallar" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
}

test("bir işyeri kuralı önizlenir ve kaydedilir", async ({ page }, testInfo) => {
  const rule = RULES[testInfo.project.name as keyof typeof RULES];
  await open(page);
  const card = page.getByRole("region", { name: "İşyeri kuralı ekle" });
  await card.getByLabel("İşyerinin adı").fill(rule.merchant);
  await card.getByLabel("Desenler").fill(rule.pattern);
  await card.getByLabel("Kategori").selectOption({ label: rule.category });
  await card.getByRole("button", { name: "Önizle" }).click();
  // The other project may save its rule meanwhile: the counts are the service's, the move is this rule's.
  await expect(card.getByText(/^Bu değişiklik \d+ işlemin/)).toBeVisible(SETTLES);
  await expect(card.getByText(new RegExp(`→ ${rule.category}: 1 işlem`))).toBeVisible();
  await expect(card.getByRole("table", { name: "Değişecek işlemlerden örnekler" })).toContainText(rule.pattern);
  expect(await violations(page)).toEqual([]);
  await card.getByRole("button", { name: "Kaydet" }).click();
  await expect(card.getByText(/^Kaydedildi: \d+ işlem değişti\./)).toBeVisible(SETTLES);
  await expect(card.getByLabel("İşyerinin adı")).toHaveValue("");
});

test("listeden bir değişiklik yan panelde önizlenir; vazgeçilince bir şey yazılmaz", async ({ page }) => {
  await open(page);
  const categories = page.getByRole("region", { name: "Kategoriler" });
  const toggle = categories.getByRole("button", { name: "Taahhüt say: Eczane" });
  await toggle.click();
  const panel = page.getByRole("dialog", { name: "Eczane taahhüt kategorisi olsun" });
  await expect(panel.getByRole("button", { name: "Kaydet" })).toBeVisible(SETTLES);
  expect(await violations(page, '[role="dialog"]')).toEqual([]);
  await panel.getByRole("button", { name: "Vazgeç" }).click();
  await expect(panel).toHaveCount(0);
  await expect(toggle).toBeFocused();
});

test("ayrıntılı görünümün tabloları ve kural dosyası erişilebilirlik denetiminden geçer", async ({ page }) => {
  await open(page);
  // The choice's label: the radio button itself is hidden under it.
  await page.getByRole("group", { name: "Görünüm" }).getByText("Ayrıntılı").click();
  await expect(page.getByRole("radio", { name: "Ayrıntılı" })).toBeChecked();
  await expect(page.getByRole("table", { name: "Kategoriler, grupları ve gereklilik düzeyleri" })).toBeVisible();
  await expect(page.getByLabel("Kişisel kurallar")).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
