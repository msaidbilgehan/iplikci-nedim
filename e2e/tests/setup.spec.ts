// The setup wizard on the service itself (F17): every step opens from its address with its number and name, and passes
// axe with what it holds — the extension's pairing, the IMAP form, the senders, the upload panel, the channels. Nothing
// is changed, so both themes' projects run it side by side.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const STEPS = [
  ["data_folder", "Veri klasörü"],
  ["names", "Adınız"],
  ["business_names", "Şirket adları"],
  ["mail", "E-posta"],
  ["senders", "Bankalar ve göndericiler"],
  ["documents", "Eski belgeler"],
  ["notifications", "Bildirimler"],
  ["service", "Servis"],
  ["remote", "Uzaktan erişim"],
] as const;

test("sihirbazın her adımı adresinden açılır ve erişilebilirlik denetiminden geçer", async ({ page }) => {
  for (const [index, [step, name]] of STEPS.entries()) {
    await page.goto(`/kurulum?adim=${step}`);
    await expect(page.getByRole("heading", { level: 2, name: `Adım ${index + 1}/9: ${name}` })).toBeVisible();
    await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
    await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
    const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const violations = found.violations.map((v) => `${step} ${v.id}: ${v.nodes[0]?.target.join(" ")}`);
    expect(violations).toEqual([]);
  }
});

test("e-posta adımında uygulama şifresi seçilince form açılır ve erişilebilirlik denetiminden geçer", async ({
  page,
}) => {
  await page.goto("/kurulum?adim=mail");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page.getByText("Uygulama şifresi (IMAP)").click();
  await expect(page.getByLabel("Uygulama şifresi", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Hesabı kur" })).toBeDisabled(); // nothing typed
  const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
});

test("son adımdaki Bitir kurulumun özetini gösterir ve özet erişilebilirlik denetiminden geçer", async ({ page }) => {
  await page.goto("/kurulum?adim=remote");
  await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
  await page.getByRole("button", { name: "Bitir" }).click();
  await expect(page).toHaveURL(/\/kurulum\?adim=ozet$/);
  const summary = page.getByRole("region", { name: /^Kurulum(da \d+ adım bekliyor| tamamlandı)$/ });
  await expect(summary.getByRole("heading", { level: 2 })).toBeFocused();
  await expect(summary.getByText(/^\d adımın \d tanesi tamam$/)).toBeVisible();
  await expect(summary.getByRole("link", { name: "Pano'ya git" })).toHaveAttribute("href", "/");
  const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(found.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
});
