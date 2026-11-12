// The İşlemler screen's corrections on the service itself (F04): a row's panel passes axe, a note is kept by the
// row's fingerprint, a split into parts shows once the service's new analysis settles, and the row is joined again.
// Each theme's project corrects a row of its own, so the two run side by side on the one demo data folder.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page, test } from "@playwright/test";

const MERCHANT = "Ornek Kahve";
const SETTLES = { timeout: 20_000 }; // the service analyses again after a correction; the screen asks again meanwhile

async function openRow(page: Page, project: string): Promise<Locator> {
  await page.goto(`/islemler?merchant=${encodeURIComponent(MERCHANT)}`);
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page
    .getByRole("link", { name: MERCHANT, exact: true })
    .nth(project === "koyu" ? 1 : 0)
    .click();
  const panel = page.getByRole("dialog", { name: MERCHANT });
  await expect(panel.getByRole("region", { name: "Düzeltmeler" })).toBeVisible();
  return panel;
}

test("bir satırın paneli erişilebilirlik denetiminden geçer, not kalır, satır bölünür ve yeniden birleşir", async ({
  page,
}, testInfo) => {
  const panel = await openRow(page, testInfo.project.name);
  const found = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);

  const fix = panel.getByRole("region", { name: "Düzeltmeler" });
  const note = `uçtan uca deneme, ${testInfo.project.name}`;
  await fix.getByLabel("Not").fill(note);
  await fix.getByRole("button", { name: "Notu kaydet" }).click();
  await expect(fix.getByText("Kaydedildi.")).toBeVisible();
  await expect(panel.getByRole("region", { name: "Ayrıntılar" }).getByText(note)).toBeVisible(SETTLES);

  await fix.getByRole("button", { name: "Parçalara böl…" }).click();
  const split = fix.getByRole("region", { name: "Bölme" });
  const second = split.getByRole("group", { name: "Parça 2" });
  await second.getByLabel("Tutar (TL)").fill("10");
  await second.getByLabel("Kategori").selectOption({ label: "Market & Gıda" });
  await split.getByRole("button", { name: "Böl", exact: true }).click();
  await expect(panel.getByText("2 parçaya bölünmüş; her parça kendi kategorisinde sayılıyor.")).toBeVisible(SETTLES);
  const parts = panel.getByRole("region", { name: "Parçalar" }).getByRole("row");
  await expect(parts).toHaveCount(3); // the heading and the two parts
  await expect(parts.nth(2)).toContainText("Market & Gıda");

  await fix.getByRole("region", { name: "Bölme" }).getByRole("button", { name: "Bölmeyi kaldır" }).click();
  const ask = page.getByRole("alertdialog", { name: "Bölme kaldırılsın mı?" });
  await ask.getByRole("button", { name: "Bölmeyi kaldır" }).click();
  await expect(panel.getByText(/parçaya bölünmüş/)).toHaveCount(0, SETTLES);
  await expect(fix.getByRole("button", { name: "Parçalara böl…" })).toBeVisible();
});

test("dönem aramanın yanında seçilir; yön ve tutar süzgeçlerde, hepsi erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await page.goto("/islemler");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page.getByLabel("Dönem", { exact: true }).selectOption({ label: "Son 3 ay" });
  await expect(page).toHaveURL(/\/islemler\?period=last_3_months$/);
  await page.getByRole("button", { name: /^Süzgeçler/ }).click();
  await page.getByLabel("Yön", { exact: true }).selectOption({ label: "Yalnızca çıkan para" });
  await expect(page).toHaveURL(/direction=out/);
  const least = page.getByLabel("En az (TL)", { exact: true });
  await least.fill("1.000");
  await least.press("Enter");
  await expect(page).toHaveURL(/min=1000/);
  await expect(page.getByRole("button", { name: "Tutar süzgecini kaldır" })).toBeVisible();
  // The account filter's options read whole, numbers and all.
  await page.getByRole("button", { name: /^Hesap:/ }).click();
  await expect(page.getByRole("dialog", { name: "Hesap" })).toBeVisible();
  const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
});

test("bir süzgecin seçenekleri kısa bir pencerede ekranın içinde kalır, kayar, Tümü hep görünür", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 640 });
  await page.goto("/islemler?period=last_month&kind=income");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page.getByRole("button", { name: /^Süzgeçler/ }).click();
  await page.getByRole("button", { name: /^Tür:/ }).click();
  const kinds = page.getByRole("dialog", { name: "Tür" });
  await expect(kinds).toBeVisible();
  const box = await kinds.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(640);
  // The last kind is reached by scrolling the list; "Tümü" stays in view above it.
  await kinds.getByRole("checkbox", { name: "Çözülmemiş transfer" }).scrollIntoViewIfNeeded();
  await expect(kinds.getByRole("button", { name: "Tümü" })).toBeInViewport();
  await kinds.getByRole("button", { name: "Tümü" }).click();
  await expect(page).not.toHaveURL(/kind=/);
});

test("virgülle birkaç şey birden aranır, her parçanın bulduğu yazar, erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await page.goto("/islemler");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page.getByRole("searchbox", { name: "Ara" }).fill("spotify, turkcell, spotfy");
  await expect(page).toHaveURL(/\/islemler\?q=spotify%2C\+turkcell%2C\+spotfy$/);
  const parts = page.getByRole("region", { name: "Aramanın parçaları" });
  await expect(parts).toContainText("spotify 10 işlem");
  await expect(parts).toContainText("turkcell 10 işlem");
  await expect(parts).toContainText("spotfy bulunamadı"); // a part misspelt is told, not lost among the others
  await expect(page.getByRole("region", { name: "Toplamlar" })).toContainText("20 işlem");
  await expect(page.getByRole("button", { name: "Ara süzgecini kaldır" })).toBeVisible();
  const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
  await parts.getByRole("link", { name: "Yalnızca bunu ara: turkcell" }).click();
  await expect(page).toHaveURL(/\/islemler\?q=turkcell$/);
  await expect(page.getByRole("region", { name: "Toplamlar" })).toContainText("10 işlem");
});
