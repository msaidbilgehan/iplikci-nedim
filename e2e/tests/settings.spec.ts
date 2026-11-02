// The Settings screen on the service itself (F17, ADR-0017): the days backups are kept are saved and put back; the
// service's own steps say what they need, and stopping asks first, which passes axe; the detailed view passes axe.
// settings.toml is one file, so only the light theme's project changes it; the dark one only reads. No step that ends
// the service is ever confirmed here: the tests' service is not registered with the computer, and ending it would end
// every test beside this one.

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function open(page: Page): Promise<void> {
  await page.goto("/ayarlar");
  await expect(page.getByRole("heading", { level: 1, name: "Ayarlar" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
}

async function violations(page: Page): Promise<string[]> {
  const found = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  return found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`);
}

test("yedeklerin saklandığı gün sayısı kaydedilir ve geri alınır", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "acik", "settings.toml'u yalnızca bir proje değiştirir");
  await open(page);
  const backup = page.getByRole("region", { name: "Yedekler" });
  const days = backup.getByLabel("Günlük yedekler kaç gün saklansın");
  const before = await days.inputValue();
  await days.fill("45");
  await backup.getByRole("button", { name: "Kaydet" }).click();
  await expect(backup.getByText("Kaydedildi: günlük yedekler 45 gün saklanır.")).toBeVisible();
  await days.fill(before);
  await backup.getByRole("button", { name: "Kaydet" }).click();
  await expect(backup.getByText(`Kaydedildi: günlük yedekler ${before} gün saklanır.`)).toBeVisible();
});

test("servisin adımları kaydı ister, durdurmak önce sorar ve soru denetimden geçer", async ({ page }) => {
  await open(page);
  const service = page.getByRole("region", { name: "Servis" });
  // The tests' service runs by hand for the demo's folder: restarting and removing it wait for a registered one.
  await expect(service.getByText(/^Servis bu bilgisayara bu veri klasörü için kayıtlı değil\./)).toBeVisible();
  await expect(service.getByRole("button", { name: "Yeniden başlat" })).toBeDisabled();
  await expect(service.getByRole("button", { name: "Servisi kaldır" })).toBeDisabled();
  const stop = service.getByRole("button", { name: "Servisi durdur" });
  await stop.click();
  const asked = page.getByRole("alertdialog", { name: "Servis durdurulsun mu?" });
  await expect(asked).toBeVisible();
  await expect(asked.getByRole("button", { name: "Vazgeç" })).toBeFocused(); // the safe choice first
  expect(await violations(page)).toEqual([]);
  await asked.getByRole("button", { name: "Vazgeç" }).click();
  await expect(asked).toBeHidden();
  await expect(stop).toBeFocused();
});

test("ayrıntılı görünüm erişilebilirlik denetiminden geçer", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /^Görünüm: / }).click(); // the header's display menu
  await page.getByRole("group", { name: "Görünüm" }).getByText("Ayrıntılı").click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("region", { name: "Ayarların değerleri" })).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
