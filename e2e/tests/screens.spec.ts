// Every screen opens on the demo data folder, finishes loading without an error, and passes axe's WCAG 2.1 A and
// AA checks (features.md, shared rules) — in the light and the dark theme, one project each — and fits a phone's
// width in both views.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The screens and their main headings; each new screen joins this list.
const SCREENS = [
  { path: "/", heading: "Pano" },
  { path: "/akis", heading: "Akış" },
  { path: "/islemler", heading: "İşlemler" },
  { path: "/hesaplar", heading: "Hesaplar" },
  { path: "/hesaplar/teb-123456789", heading: "TEB Vadesiz TL 123456789" }, // the demo's TL account
  { path: "/sistem", heading: "Sistem" },
  { path: "/belgeler", heading: "Belgeler" },
  { path: "/abonelikler", heading: "Abonelikler" },
  { path: "/takvim", heading: "Takvim" },
  { path: "/degerlendirme", heading: "Değerlendirme" },
  { path: "/doviz", heading: "Döviz" },
  { path: "/faturalar", heading: "Faturalar" },
  { path: "/bildirimler", heading: "Bildirimler" },
  { path: "/kurulum/eklenti", heading: "Tarayıcı eklentisi" },
  { path: "/ay-sonu", heading: "Ay sonu" },
  { path: "/ay-sonu/2026-10", heading: "Ekim 2026" }, // a closed month of the demo
  { path: "/kurallar", heading: "Kurallar" },
  { path: "/yapilacaklar", heading: "Yapılacaklar" },
  { path: "/kurulum", heading: "Kurulum sihirbazı" },
  { path: "/ayarlar", heading: "Ayarlar" },
] as const;

for (const screen of SCREENS) {
  test(`${screen.heading} ekranı yüklenir ve erişilebilirlik denetiminden geçer`, async ({ page }) => {
    await page.goto(screen.path);
    await expect(page.getByRole("heading", { level: 1, name: screen.heading })).toBeVisible();
    // The live event stream keeps a request open, so "network idle" never comes: wait for the loading states.
    await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
    await expect(page.getByText("Yüklenemedi")).toHaveCount(0);
    await expect(page.getByText("Oturum kapandı")).toHaveCount(0);
    const found = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    // Each violation with its first elements and why they fail, so a failure in CI says what to fix.
    const violations = found.violations.map((v) => ({
      rule: v.id,
      impact: v.impact,
      where: v.nodes
        .slice(0, 5)
        .map((n) => `${n.target.join(" ")} — ${n.html.slice(0, 160)} — ${(n.failureSummary ?? "").slice(0, 300)}`),
    }));
    expect(violations).toEqual([]);
  });
}

// On a phone no screen scrolls sideways, in either view: a table wider than the screen scrolls inside its card.
for (const screen of SCREENS) {
  test(`${screen.heading} ekranı telefonda iki görünümde de yana taşmaz`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(screen.path);
    for (const view of ["simple", "detailed"] as const) {
      await page.evaluate((chosen) => window.localStorage.setItem("iplikci.view", chosen), view);
      await page.reload();
      await expect(page.getByRole("heading", { level: 1, name: screen.heading })).toBeVisible();
      await expect(page.getByRole("status", { name: "Yükleniyor…" })).toHaveCount(0, { timeout: 15_000 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${view}: ${overflow} px fazla`).toBeLessThanOrEqual(0);
    }
  });
}

test("bilinmeyen bir adres sayfanın olmadığını söyler", async ({ page }) => {
  await page.goto("/boyle-bir-yer-yok");
  await expect(page.getByRole("heading", { level: 1, name: "Böyle bir sayfa yok" })).toBeVisible();
});
